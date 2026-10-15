from __future__ import annotations

import array
import collections
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .core import ROOT, StudioError, confined, relative, now, uid, digest
from .runtime import CODE_ROOT

LOCAL_MODEL_FILES = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")


def offline_model(model="tiny"):
    """Resolve a whitelisted, already installed public CPU model, read-only."""
    if not isinstance(model,str) or model not in {"tiny", "base", "small"}:
        raise StudioError("El ASR automatizado admite tiny, base o small locales.")
    cache = CODE_ROOT / ".estado/models/whisper"
    if cache.resolve() != cache or not cache.is_dir():
        raise StudioError("No existe la caché pública local de ASR.", 409)
    repository = cache / ("models--Systran--faster-whisper-" + model)
    if repository.resolve()!=repository or (repository/'refs').resolve()!=repository/'refs':
        raise StudioError('El repositorio ASR no admite alias entre modelos.',403)
    reference = repository / "refs/main"
    if reference.is_symlink() or not reference.is_file():
        raise StudioError("El modelo ASR elegido aún no está disponible localmente.", 409)
    revision = reference.read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise StudioError("Referencia del modelo ASR inválida.", 409)
    snapshot = repository / "snapshots" / revision
    if snapshot.resolve()!=snapshot or not snapshot.resolve().is_relative_to(cache):
        raise StudioError("La instantánea ASR no admite rutas ajenas.", 403)
    tree=repository/'trees'/f'{revision}.json'
    if tree.resolve()!=tree or not tree.resolve().is_relative_to(cache) or not tree.is_file() or tree.stat().st_size>65536:
        raise StudioError('Falta el índice de integridad del modelo ASR local.',409)
    try:
        index=json.loads(tree.read_text())['files']
        if not isinstance(index,dict):raise ValueError('índice inválido')
    except (ValueError,KeyError,TypeError) as error:
        raise StudioError('Índice del modelo ASR inválido.',409) from error
    files = {}
    for name in LOCAL_MODEL_FILES:
        path = snapshot / name
        resolved = path.resolve()
        if not resolved.is_relative_to(cache) or not resolved.is_file():
            raise StudioError("Faltan archivos locales del modelo ASR.", 409)
        expected=index.get(name)
        if not isinstance(expected,dict) or type(expected.get('size')) is not int or expected['size']!=resolved.stat().st_size:
            raise StudioError('Cambió el tamaño de un archivo del modelo ASR.',409)
        h = hashlib.sha256();git=hashlib.sha1(b'blob '+str(expected['size']).encode()+b'\0')
        with resolved.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(block)
                git.update(block)
        if expected.get('lfs_sha256'):
            valid=h.hexdigest()==expected['lfs_sha256']
        else:valid=git.hexdigest()==expected.get('blob_id')
        if not valid:raise StudioError('El modelo ASR local no coincide con su índice de contenido.',409)
        files[name] = {"sha256": h.hexdigest(), "size": resolved.stat().st_size}
    return {"model": model, "revision": revision, "path": snapshot, "files": files,"index_sha256":hashlib.sha256(tree.read_bytes()).hexdigest(), "network_used": False}

FORMATS = "mov,matroska,avi,mpegts,mpeg,mxf,ogg,mp3,wav,flac,aac,image2,png_pipe,jpeg_pipe,webp_pipe,gif,bmp_pipe,tiff_pipe,aiff,asf,flv,amr,ac3,eac3,au,ape,mp4,m4v,h264,hevc"


def input_media(path):
    return ["-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-threads", "2", "-i", str(confined(path, must_exist=True))]


def _check_cancel(cancel):
    if cancel is not None and (cancel() if callable(cancel) else cancel.is_set()):
        raise StudioError("Trabajo cancelado.", 409)


def run(args, timeout=120, binary=False, cancel=None, *, stderr=False):
    _check_cancel(cancel)
    try:
        if args and Path(args[0]).name in {"ffmpeg", "ffprobe"} and shutil.which("nice"):
            args = [shutil.which("nice"), "-n", "10", *args]
        temporary = confined('.estado/tmp');temporary.mkdir(parents=True,exist_ok=True)
        env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','LD_LIBRARY_PATH') if k in os.environ}
        env.update(TMPDIR=str(temporary),CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
        if cancel is None:
            result = subprocess.run(args, cwd=ROOT, env=env, shell=False, capture_output=True, timeout=timeout, check=False)
        else:
            process=subprocess.Popen(args,cwd=ROOT,env=env,shell=False,stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            began=time.monotonic()
            try:
                while True:
                    _check_cancel(cancel)
                    if time.monotonic()-began>timeout:raise subprocess.TimeoutExpired(args,timeout)
                    try:
                        stdout,stderr=process.communicate(timeout=.1);break
                    except subprocess.TimeoutExpired:continue
                result=subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid,signal.SIGKILL);process.communicate()
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudioError(f"No se pudo ejecutar {Path(args[0]).name}: {error}") from error
    if result.returncode:
        raise StudioError(f"{Path(args[0]).name}: " + result.stderr.decode("utf-8", "replace")[-1600:])
    _check_cancel(cancel)
    output=result.stderr if stderr else result.stdout
    return output if binary else output.decode("utf-8", "replace")


def validate_audio_stream_index(index):
    if index is not None and (type(index) is not int or not 0<=index<=1023):
        raise StudioError('audio_stream_index debe ser un índice global entero entre 0 y 1023.')
    return index


def select_audio_stream(info, index=None):
    """Select a GLOBAL ffprobe index. Never confuse it with audio ordinal."""
    validate_audio_stream_index(index)
    streams=info.get('streams',[]) if isinstance(info,dict) else None
    if not isinstance(streams,list):raise StudioError('Inventario de pistas inválido.')
    audios=[stream for stream in streams if isinstance(stream,dict) and stream.get('codec_type')=='audio']
    if not audios:raise StudioError('El archivo no contiene una pista de audio seleccionable.',409)
    indexes=[stream.get('index') for stream in audios]
    if any(type(value) is not int or not 0<=value<=1023 for value in indexes) or len(set(indexes))!=len(indexes):
        raise StudioError('FFprobe no devolvió índices globales de audio válidos.',409)
    selected=audios[0] if index is None else next((stream for stream in audios if stream['index']==index),None)
    if selected is None:raise StudioError('La pista global seleccionada no existe o no es audio.',409)
    return {**selected,'audio_ordinal':audios.index(selected),'ffmpeg_map':f"0:{selected['index']}"}


def audio_tracks(path, *, start=0, duration=30, selected_index=None, progress=None, cancel=None):
    """Rank measured activity in <=8 tracks/30s; this does not identify voice."""
    validate_audio_stream_index(selected_index)
    for value,name,lo,hi in ((start,'start',0,7200),(duration,'duration',.01,30)):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
            raise StudioError(f'{name} del análisis de pistas fuera de rango.')
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        _check_cancel(cancel);source=confined(path,must_exist=True);source_sha=digest(source)
        info=probe(source);audios=[s for s in info.get('streams',[]) if s.get('codec_type')=='audio']
        if not audios:
            if selected_index is not None:select_audio_stream(info,selected_index)
            return {'tracks':[],'recommended_stream_index':None,'voice_verified':False,'audio_listened':False,'source_sha256':source_sha}
        select_audio_stream(info,selected_index)
        try:total=float(info.get('format',{}).get('duration',0))
        except (ValueError,TypeError):total=0
        if not math.isfinite(total) or start>=total:raise StudioError('El tramo de análisis no existe.',409)
        span=min(duration,total-start);rows=[]
        for ordinal,stream in enumerate(audios[:8]):
            _check_cancel(cancel)
            data=run(['ffmpeg','-nostdin','-v','error']+input_media(source)+
                     ['-map',f"0:{stream['index']}",'-vn','-af',f'aresample=16000:async=1:first_pts=0,atrim=start={start:.8g}:duration={span:.8g}',
                      '-ac','1','-ar','16000','-threads','2','-filter_threads','2','-f','f32le','pipe:1'],120,True,cancel)
            values=array.array('f');values.frombytes(data[:len(data)//4*4])
            if len(values)>math.ceil(span*16000)+16000:raise StudioError('La decodificación excedió el tramo permitido.',409)
            if any(not math.isfinite(value) for value in values):raise StudioError('PCM no finito en la pista de audio.',409)
            energy=sum(value*value for value in values)
            rms=math.sqrt(energy/len(values)) if values else 0
            windows=[values[i:i+320] for i in range(0,len(values),320)]
            active=sum(math.sqrt(sum(v*v for v in part)/len(part))>=10**(-45/20) for part in windows if part)
            active_ratio=active/len(windows) if windows else 0
            score=active_ratio*(min(1,rms/(10**(-30/20))))
            rows.append({'stream_index':stream['index'],'audio_ordinal':ordinal,'channels':stream.get('channels'),
                         'sample_rate':stream.get('sample_rate'),'codec':stream.get('codec_name'),
                         'rms_dbfs':20*math.log10(rms) if rms else None,'peak_dbfs':20*math.log10(max(map(abs,values))) if rms else None,
                         'active_window_ratio':active_ratio,'activity_score':score,'decoded_seconds':len(values)/16000,
                         'pcm_sha256':hashlib.sha256(data).hexdigest(),'voice_verified':False,'speech_detection_executed':False})
            if progress:progress((ordinal+1)/min(8,len(audios)),f"Midiendo actividad de pista global {stream['index']}.")
        ranked=sorted(rows,key=lambda row:(-row['activity_score'],row['stream_index']))
        recommendation=ranked[0]['stream_index'] if ranked and ranked[0]['activity_score']>0 else None
        _check_cancel(cancel)
        if digest(source)!=source_sha:raise StudioError('El audio fuente cambió durante el análisis de pistas.',409)
        return {'tracks':rows,'ranking':[row['stream_index'] for row in ranked],
                'recommended_stream_index':recommendation,'selected_stream_index':selected_index,
                'method':'Activity only: fraction of 20ms RMS windows above -45 dBFS, weighted by RMS up to -30 dBFS',
                'voice_verified':False,'speech_detection_executed':False,'audio_listened':False,
                'source_sha256':source_sha,'source_start':start,'scope_seconds':span,
                'total_audio_tracks':len(audios),'unmeasured_stream_indices':[s['index'] for s in audios[8:]],
                'limitations':['Actividad puede ser música, ruido o voz; no identifica narrador, idioma ni hablantes.',
                               'Solo se mide el tramo indicado de hasta30s; selección explícita tiene prioridad sobre ranking.']}


def probe(path):
    if not shutil.which("ffprobe"):
        raise StudioError("FFprobe no está instalado.")
    p = confined(path, must_exist=True)
    info = json.loads(run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-show_format", "-show_streams", "-of", "json", str(p)], 30))
    # Omit arbitrary tags to keep imported metadata bounded and predictable.
    for stream in info.get("streams", []):
        # Preserve only the decoder's geometric rotation, not arbitrary tags.
        # Display-matrix side data takes precedence over legacy rotate tags.
        angles = [side.get("rotation") for side in stream.get("side_data_list", [])
                  if isinstance(side, dict) and "rotation" in side]
        tags = stream.get("tags", {})
        if isinstance(tags, dict) and "rotate" in tags:
            angles.append(tags["rotate"])
        for raw_angle in angles:
            try:
                if isinstance(raw_angle, bool):
                    continue
                angle = float(raw_angle)
            except (ValueError, TypeError):
                continue
            if math.isfinite(angle) and abs(angle) <= 3600:
                stream["rotation"] = angle
                break
        stream.pop("tags", None)
        stream.pop("side_data_list", None)
    info.get("format", {}).pop("tags", None)
    info.get("format", {}).pop("filename", None)
    return info


def thumbnails(path, asset_id, duration):
    paths = []
    for index, when in enumerate([0, max(0, duration * .33), max(0, duration * .66)]):
        output = confined(f"assets/images/{asset_id}_{index}.jpg")
        run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(when)] + input_media(path) + ["-frames:v", "1", "-vf", "scale=240:-2", "-threads", "2", "-y", str(output)], 30)
        if output.exists():
            paths.append(relative(output))
    return paths


def waveform(path, bins=240, *, audio_stream_index=None, cancel=None):
    validate_audio_stream_index(audio_stream_index)
    if type(bins) is not int or not 1<=bins<=4000:raise StudioError('bins debe ser entero entre 1 y 4000.')
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        source=confined(path,must_exist=True);initial=digest(source)
        selected=select_audio_stream(probe(source),audio_stream_index)
        data = run(["ffmpeg", "-nostdin", "-v", "error"] + input_media(source) + ["-map", selected['ffmpeg_map'], "-t", "3600",'-af','aresample=8000:async=1:first_pts=0', "-ac", "1", "-ar", "8000",'-filter_threads','2','-threads','2', "-f", "f32le", "pipe:1"], 120, True,cancel)
        if digest(source)!=initial:raise StudioError('Cambió la fuente durante el waveform.',409)
    values = array.array("f")
    values.frombytes(data[:len(data) // 4 * 4])
    if not values:
        return {"peaks": [], "rms": [], "sample_rate": 8000, "seconds": 0}
    size = max(1, math.ceil(len(values) / bins))
    peaks, rms = [], []
    for start in range(0, len(values), size):
        samples = values[start:start + size]
        peaks.append(round(max(abs(v) for v in samples), 4))
        rms.append(round(math.sqrt(sum(v * v for v in samples) / len(samples)), 4))
    return {"peaks": peaks, "rms": rms, "sample_rate": 8000, "seconds": round(len(values) / 8000, 3), "limited_to_seconds": 3600,
            'audio_stream_index':selected['index'],'source_sha256':initial,'audio_listened':False}


def silence_analysis(path, *, audio_stream_index=None, cancel=None):
    validate_audio_stream_index(audio_stream_index)
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        _check_cancel(cancel);source=confined(path,must_exist=True);initial=digest(source)
        selected=select_audio_stream(probe(source),audio_stream_index)
        args=['ffmpeg','-nostdin','-v','info']+input_media(source)+['-map',selected['ffmpeg_map'],'-af','aresample=8000:async=1:first_pts=0,silencedetect=noise=-35dB:d=0.35','-threads','2','-filter_threads','2','-f','null','-']
        text=run(args,120,False,cancel,stderr=True)
        _check_cancel(cancel)
        if digest(source)!=initial:raise StudioError('Cambió la fuente durante el análisis de silencio.',409)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", text)]
    return [{"start": start, "end": ends[i] if i < len(ends) else None} for i, start in enumerate(starts)]


def _transcribe(path, model="tiny", language="es", progress=None, cancel=None, *, local_model_path=None):
    if model not in ("tiny", "base", "small", "medium", "large-v3", "distil-large-v3"):
        raise StudioError("Modelo ASR no admitido.")
    if language and not re.fullmatch(r"[a-z]{2,3}", language):
        raise StudioError("Código de idioma inválido.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise StudioError("ASR necesita faster-whisper. Instálalo con ./instalar_asr.sh dentro de SOFTWARE.") from error
    local = None
    if local_model_path is not None:
        local = offline_model(model)
        if Path(local_model_path).absolute() != local["path"]:
            raise StudioError("La ruta ASR privada debe coincidir con el modelo autorizado.", 403)
        if progress:
            progress(.08, "Cargando modelo ASR CPU local verificado; sin descarga.")
        engine = WhisperModel(str(local["path"]), local_files_only=True, device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)
    else:
        if progress:
            progress(.08, "Cargando ASR CPU; descarga inicial del modelo en SOFTWARE/.estado/models.")
        cache = confined(".estado/models/whisper")
        cache.mkdir(parents=True, exist_ok=True)
        engine = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=2, num_workers=1, download_root=str(cache))
    segments, info = engine.transcribe(str(confined(path, must_exist=True)), language=language or None, word_timestamps=True, vad_filter=True, beam_size=3)
    phrases, words = [], []
    duration = max(float(info.duration), .001)
    for segment in segments:
        _check_cancel(cancel)
        phrases.append({"start": round(segment.start, 3), "end": round(segment.end, 3), "text": segment.text.strip()})
        for word in segment.words or []:
            words.append({"start": round(word.start, 3), "end": round(word.end, 3), "word": word.word.strip(), "probability": round(word.probability, 4)})
        if progress:
            progress(.1 + .85 * min(1, segment.end / duration), "Transcribiendo voz y alineando palabras.")
    _check_cancel(cancel)
    if local and offline_model(model) != local:
        raise StudioError("El modelo ASR cambió durante la transcripción.", 409)
    return {"status": "transcribed", "engine": "faster-whisper", "model": model, "device": "cpu", "language": info.language,
            "local_model": {k:v for k,v in local.items() if k!="path"} if local else None,
            "language_probability": round(info.language_probability, 4), "words": words, "segments": phrases,
            "reviewed": False, "at": now(), "limitations": ["ASR puede equivocarse: revisar nombres, cifras, ortografía y tiempos.", "Transcripción no equivale a audición perceptiva ni diarización de hablantes."]}


def transcribe(path, model="tiny", language="es", progress=None, cancel=None, *, local_model_path=None, audio_stream_index=None):
    """Explicit stream extraction preserves source timeline before CPU ASR."""
    validate_audio_stream_index(audio_stream_index)
    if not isinstance(model,str) or model not in ('tiny','base','small','medium','large-v3','distil-large-v3'):
        raise StudioError('Modelo ASR no admitido.')
    if language is not None and (not isinstance(language,str) or language and not re.fullmatch(r'[a-z]{2,3}',language)):
        raise StudioError('Código de idioma inválido.')
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        source=confined(path,must_exist=True);initial=digest(source);_check_cancel(cancel)
        if audio_stream_index is None:
            result=_transcribe(source,model,language,progress,cancel,local_model_path=local_model_path)
            audio_source={'source_path':relative(source),'source_sha256':initial,'selection':'decoder_default_first_audio'}
        else:
            info=probe(source);selected=select_audio_stream(info,audio_stream_index)
            try:duration=float(info.get('format',{}).get('duration',0))
            except (ValueError,TypeError):duration=0
            if not math.isfinite(duration) or not 0<duration<=7200:raise StudioError('ASR requiere una fuente de hasta7200s con duración real.',409)
            temporary=confined('.estado/tmp');temporary.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='asr-selected-',dir=temporary) as folder:
                wav=Path(folder)/'selected.wav'
                run(['ffmpeg','-nostdin','-v','error']+input_media(source)+
                    ['-map',selected['ffmpeg_map'],'-vn','-af','aresample=16000:async=1:first_pts=0,apad',
                     '-t',f'{duration:.8g}','-ac','1','-ar','16000','-c:a','pcm_s16le','-filter_threads','2','-threads','2','-n',str(wav)],
                    max(120,min(1800,duration*2+30)),False,cancel)
                pcm_sha=digest(wav)
                result=_transcribe(wav,model,language,progress,cancel,local_model_path=local_model_path)
                if digest(wav)!=pcm_sha:raise StudioError('Cambió el WAV seleccionado durante ASR.',409)
                audio_source={'source_path':relative(source),'source_sha256':initial,'stream_index':selected['index'],
                              'stream_ordinal':selected['audio_ordinal'],'ffmpeg_map':selected['ffmpeg_map'],
                              'sample_rate':16000,'channels':1,'asr_pcm_sha256':pcm_sha,'duration':duration,
                              'timeline':'Source-relative timestamp gaps preserved by aresample first_pts=0',
                              'voice_verified':False,'audio_listened':False}
        _check_cancel(cancel)
        if digest(source)!=initial:raise StudioError('La fuente cambió durante la transcripción.',409)
        result['audio_source']=audio_source
        return result


def validate_analysis_options(options=None):
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise StudioError("Las opciones de análisis requieren un objeto JSON.")
    if not isinstance(options.get("transcribe", False), bool):
        raise StudioError("transcribe debe ser booleano; ASR se ejecuta únicamente con true explícito.")
    if any(not isinstance(key,str) for key in options) or set(options)-{'transcribe','model','language','audio_stream_index'}:
        raise StudioError('Opciones de análisis no admitidas.')
    validate_audio_stream_index(options.get('audio_stream_index'))
    if 'model' in options and (not isinstance(options['model'],str) or options['model'] not in ('tiny','base','small','medium','large-v3','distil-large-v3')):
        raise StudioError('Modelo ASR no admitido.')
    language=options.get('language')
    if language is not None and (not isinstance(language,str) or language and not re.fullmatch(r'[a-z]{2,3}',language)):
        raise StudioError('Código de idioma inválido.')
    return options


def analyze_project(p, options=None, progress=None, cancel=None):
    options = validate_analysis_options(options)
    source = next((a for a in p["assets"] if a["id"] == p.get("source")), None)
    if not source:
        raise StudioError("Asigna el crudo antes de analizar.")
    path = confined(source["path"], must_exist=True)
    info = probe(path)
    audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    video_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    p["analysis"] = {"at": now(), "duration": source["duration"], "video": video_streams, "audio_tracks": audio_streams,
                     "format": info.get("format", {}), "voice_detection": "pending_asr", "preserve_original_cuts": True}
    if progress:
        progress(.03, "Formato, pistas de audio y video comprobados.")
    if audio_streams:
        requested=options.get('audio_stream_index')
        if requested is None:requested=p.get('settings',{}).get('voice_audio_stream')
        selection=select_audio_stream(info,requested)
        p['settings']['voice_audio_stream']=selection['index']
        p['analysis']['audio_selection']={'stream_index':selection['index'],'audio_ordinal':selection['audio_ordinal'],
                                         'ffmpeg_map':selection['ffmpeg_map'],'voice_verified':False,'method':'explicit' if requested is not None else 'first_audio_default'}
        p["analysis"]["silences"] = silence_analysis(path,audio_stream_index=selection['index'],cancel=cancel)
        p['analysis']['waveform']=waveform(path,audio_stream_index=selection['index'],cancel=cancel)
        if options.get("transcribe", False):
            p["transcript"] = transcribe(path, options.get("model", "tiny"), options.get("language", "es"), progress, cancel,audio_stream_index=selection['index'])
            p["analysis"]["voice_detection"] = "speech_transcribed" if p["transcript"]["words"] else "no_words_detected"
    else:
        p["analysis"]["voice_detection"] = "no_audio_track"
        p["analysis"]["warning"] = "El crudo no contiene audio; la identificación de voz requiere una pista real."
    p["stage"] = "analysis"
    return p


def tokens(text):
    return {w for w in re.findall(r"[a-záéíóúñ0-9]+", text.lower()) if len(w) > 3}


def propose_storyboard(p):
    source = next((a for a in p["assets"] if a["id"] == p.get("source")), None)
    if not source:
        raise StudioError("Asigna el crudo antes de crear el storyboard.")
    duration = min(10., source["duration"])
    if duration <= 0:
        raise StudioError("Duración del crudo no disponible.")
    phrases = p.get("transcript", {}).get("segments", [])
    full_text = " ".join(s["text"] for s in phrases if s["start"] < duration)
    if not full_text:
        raise StudioError("Transcribe el audio o importa una transcripción alineada antes del storyboard.")
    proposed = []
    boundaries = [0, min(1.5, duration), min(4.5, duration), min(7, duration), duration]
    boundaries = sorted(set(boundaries))
    for i, (start, end) in enumerate(zip(boundaries, boundaries[1:])):
        text = " ".join(s["text"] for s in phrases if s["start"] < end and s["end"] > start)
        if not text:
            text = " ".join(w["word"] for w in p["transcript"].get("words", []) if start <= w["start"] < end)
        words = tokens(text)
        candidates = []
        for a in p["assets"]:
            if a["id"] == p["source"] or a["kind"] not in ("broll", "video"):
                continue
            metadata = a.get("metadata", {})
            overlap = words & tokens(a["name"] + " " + metadata.get("content", "") + " " + " ".join(metadata.get("tags", [])))
            if overlap:
                candidates.append({"asset_id": a["id"], "lexical_matches": sorted(overlap), "requires_visual_and_semantic_review": True})
        template = "compare" if re.search(r"\b(antes|después|versus|mejor|peor)\b", text, re.I) else "counter" if re.search(r"\d", text) else "workflow" if re.search(r"(automat|agente|proceso|sistema|conecta|flujo)", text, re.I) else "kinetic"
        proposed.append({"id": uid("s_"), "start": start, "end": end, "type": "split" if i == 0 else "motion",
                         "template": template, "title": " ".join(text.split()[:12]), "subtitle": "", "narration": text,
                         "chin_y": .65, "chin_reviewed": False, "status": "draft", "keyframes": [],
                         "candidate_resources": candidates[:5], "decision": {"search": "", "reason": "", "evidence": []},
                         "notes": "Propuesta heurística: el director debe revisar hook, frase, referencias y recursos; no es selección semántica aprobada."})
        if template == "counter":
            number = re.search(r"(?<!\w)\d+(?:[.,]\d+)*", text)
            if number:
                literal = number.group()
                fraction = re.split(r"[.,]", literal)[-1] if re.search(r"[.,]", literal) else ""
                if len(re.findall(r"[.,]", literal)) > 1 or len(fraction) == 3 or len(fraction) > 4:
                    proposed[-1]["template"] = "kinetic"
                    proposed[-1]["notes"] += " Cifra con separador ambiguo: preservar literal y confirmar significado antes de animar un contador."
                else:
                    proposed[-1]["motion"] = {"value": float(literal.replace(",", ".")), "decimals": len(fraction), "label": literal, "source_text": text}
    p["timeline"], p["stage"] = proposed, "storyboard_draft"
    p["storyboard"] = {"status": "draft", "method": "local_rule_based_proposal", "scope_seconds": duration, "at": now(),
                       "limitations": ["Las coincidencias de texto proponen candidatos; no demuestran pertinencia.", "El montaje concreto requiere dirección y evidencias de revisión."]}
    return p


def subtitles(transcript, format="srt"):
    def stamp(t, sep):
        ms = round(t * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{sep}{ms % 1000:03}"
    groups, current = [], []
    for word in transcript.get("words", []):
        if word["start"] < 4.5:
            continue
        current.append(word)
        if len(current) == 3 or word["word"].endswith((".", "!", "?", ",", ";")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        groups = [[{"start": s["start"], "end": s["end"], "word": s["text"]}] for s in transcript.get("segments", []) if s["start"] >= 4.5]
    sep = "." if format == "vtt" else ","
    blocks = [f"{i}\n{stamp(group[0]['start'], sep)} --> {stamp(group[-1]['end'], sep)}\n{' '.join(w['word'] for w in group)}\n" for i, group in enumerate(groups, 1)]
    return ("WEBVTT\n\n" if format == "vtt" else "") + "\n".join(blocks)
