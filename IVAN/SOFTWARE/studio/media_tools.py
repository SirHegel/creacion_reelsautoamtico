"""Explicit, local FFmpeg tools; processed media never replaces an original.

Filter reference: https://ffmpeg.org/ffmpeg-filters.html
All analysis values come from decoded samples/frames. Neither measurement nor
successful processing means a person listened or approved an Ascendia edit.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
from fractions import Fraction
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid

from .core import StudioError
from .analysis import FORMATS, select_audio_stream
from .runtime import CODE_ROOT

ROOT = CODE_ROOT
LOCK = threading.RLock()
INPUT_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mpg", ".mpeg", ".mxf", ".mts", ".m2ts", ".ts", ".3gp", ".3g2", ".flv", ".ogv", ".wmv", ".wav", ".mp3", ".mp2", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".aiff", ".aif", ".wma", ".amr", ".ac3", ".eac3", ".au", ".ape"}
MAX_REVERSE_BYTES = 512 * 1024 * 1024


def _parameter(key, name, default, minimum=None, maximum=None, type="number", optional=False):
    return {"key": key, "name": name, "type": type, "default": default, "min": minimum, "max": maximum, "optional": optional}


SPAN = [_parameter("start", "Entrada del recurso (s)", 0, 0, 86400), _parameter("duration", "Duración del tramo (s)", None, .01, 3600, optional=True)]
AUDIO = [_parameter("channels", "Canales de salida", 2, 1, 2, "integer"),
         _parameter("audio_stream", "Ordinal de audio legacy (desde cero)", 0, 0, 31, "integer"),
         _parameter("audio_stream_index", "Índice global FFprobe (excluye ordinal)", None, 0, 1023, "integer", optional=True)]
OPERATIONS = [
    {"id": "probe", "name": "Inspeccionar formato y pistas", "kind": "analysis", "parameters": [], "limitations": ["El soporte de formatos depende del build instalado; no identifica de oído la voz."]},
    {"id": "scene_detect", "name": "Detectar cambios de plano", "kind": "analysis", "parameters": SPAN + [_parameter("threshold", "Umbral de cambio", .3, .05, .95)], "limitations": ["Scores FFmpeg en proxy de 320 px; cambios de iluminación/movimiento pueden parecer cortes."]},
    {"id": "loudness_analysis", "name": "Medir sonoridad y pico real", "kind": "analysis", "parameters": SPAN + AUDIO[1:], "limitations": ["Medición EBU R128, no escucha perceptiva; silencio puede producir medidas no finitas."]},
    {"id": "extract_audio", "name": "Extraer audio WAV 48 kHz", "kind": "process", "parameters": SPAN + AUDIO, "extension": ".wav", "limitations": ["PCM de 16 bits; selección explícita de una pista de audio."]},
    {"id": "denoise_audio", "name": "Reducir ruido de audio", "kind": "process", "parameters": SPAN + AUDIO + [_parameter("noise_reduction_db", "Reducción de ruido (dB)", 12, 3, 48), _parameter("noise_floor_db", "Piso de ruido (dB)", -50, -80, -20), _parameter("highpass_hz", "Filtro pasa alto (Hz; cero lo desactiva)", 65, 0, 300)], "extension": ".wav", "limitations": ["Filtro FFT convencional; no es restauración neuronal ni separación de hablantes. Revisar artefactos escuchando."]},
    {"id": "normalize_audio", "name": "Normalizar audio en dos pasadas", "kind": "process", "parameters": SPAN + AUDIO + [_parameter("target_i", "Objetivo LUFS", -16, -24, -9), _parameter("target_tp", "Máximo pico real (dBTP)", -1.5, -3, -1), _parameter("lra", "Rango de sonoridad (LU)", 9, 1, 20)], "extension": ".wav", "limitations": ["Se reportan medidas reales antes/después; el contenido puede exigir modo dinámico. No normaliza silencio puro."]},
    {"id": "proxy_video", "name": "Crear proxy H.264", "kind": "process", "parameters": SPAN + [_parameter("max_width", "Ancho máximo (par)", 540, 160, 1920, "integer"), _parameter("max_height", "Alto máximo (par)", 960, 160, 1920, "integer"), _parameter("fps", "FPS", 30, 10, 60, "integer")], "extension": ".mp4", "limitations": ["Proxy SDR H.264/AAC con resize/fps; conserva proporción y primer audio. No es mastering HDR."]},
    {"id": "speed_video", "name": "Cambiar velocidad con audio sincronizado", "kind": "process", "parameters": SPAN + [_parameter("rate", "Velocidad", 1, .25, 4)], "extension": ".mp4", "limitations": ["Retime explícito: cambia tiempos de narración y requiere realinear texto. Atempo conserva tono; no genera interpolación óptica."]},
    {"id": "reverse_video", "name": "Invertir video y audio", "kind": "process", "parameters": [SPAN[0], _parameter("duration", "Duración del tramo (s)", None, .01, 60, optional=True)], "extension": ".mp4", "limitations": ["Máximo 60 s y buffer estimado 512 MiB; usar proxy/tramo menor para fuentes grandes. Cambia el sentido de la narración."]},
    {"id": "chromakey_video", "name": "Chroma key con transparencia", "kind": "process", "parameters": SPAN + [_parameter("color", "Color del fondo", "#00ff00", type="color"), _parameter("similarity", "Similitud", .1, .01, .9), _parameter("blend", "Suavizado de borde", 0, 0, 1)], "extension": ".mov", "limitations": ["Solo chroma de un color suministrado, no segmentación IA. MOV qtrle con alpha; reproducción web depende del navegador."]},
    {"id": "remove_background_video", "name": "Eliminar fondo de persona · CPU", "kind": "process",
     "description": "Segmenta la persona y genera un video transparente nuevo con el primer audio original. No cambia el crudo ni aplica el resultado a escenas.",
     "parameters": [SPAN[0], _parameter("duration", "Duración del tramo (s; vacío = resto completo, hasta 30 s)", None, .01, 30, optional=True),
                    _parameter("fps", "FPS de salida", 30, 10, 30, "integer"),
                    _parameter("max_width", "Ancho máximo sin ampliar (par)", 540, 160, 1080, "integer"),
                    _parameter("max_height", "Alto máximo sin ampliar (par)", 960, 160, 1080, "integer"),
                    _parameter("threshold", "Umbral de persona", .5, .05, .95),
                    _parameter("softness", "Suavidad de la máscara", .1, .01, 1),
                    _parameter("feather", "Suavizado del borde (px)", 0, 0, 8),
                    _parameter("temporal_smoothing", "Suavizado temporal (0 = sin arrastre)", 0, 0, .8)],
     "extension": ".mov", "limitations": ["Segmentación de persona; cabello, dedos, oclusiones y movimiento requieren revisión. No es rotoscopia manual ni matting perfecto.",
                                               "Máximo 30 s, 900 fotogramas y 2 GiB de RGBA procesado; entrada SDR. MOV QTRLE con alfa y audio PCM; proxy WebM alfa para navegador.",
                                               "El resultado necesita revisión; no se usa automáticamente para reemplazar el fondo auténtico de Iván."]},
]


def catalog():
    operations = copy.deepcopy(OPERATIONS)
    available = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    for item in operations:
        item.update(implemented=True, available=available, limits={"scope": "SOFTWARE", "gpu": False, "ffmpeg_threads": 2, "niceness": 10, "max_input_seconds": 60 if item["id"] == "reverse_video" else 3600})
        if item["id"] == "remove_background_video":
            from .segmentation import capability
            status = capability()
            item.update(available=available and status.get("available", False), capability=status,
                        unavailable_reason=status.get("reason") if not status.get("available") else None)
            item["limits"].update(max_input_seconds=30, max_frames=900, max_processed_rgba_bytes=2 * 1024 ** 3)
    return operations


def validate_options(operation, options=None):
    spec = next((s for s in OPERATIONS if s["id"] == operation), None)
    if not spec:
        raise StudioError("Operación multimedia desconocida.")
    if operation == "remove_background_video":
        from .segmentation import validate_options as validate_segmentation
        return validate_segmentation(options)
    return _options(spec, options)


def _inside(root, path, exists=False):
    root = Path(root).resolve()
    if not root.is_relative_to(ROOT.resolve()):
        raise StudioError("El workspace de herramientas debe estar dentro de SOFTWARE.", 403)
    p = Path(path)
    p = (root / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_relative_to(root):
        raise StudioError("La herramienta no admite rutas fuera de SOFTWARE.", 403)
    if exists and not p.is_file():
        raise StudioError("El recurso local no existe.", 404)
    return p


def _hash(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _run(tool, args, root, timeout=120):
    binary = shutil.which(tool)
    if not binary:
        raise StudioError(f"{tool} no está disponible.")
    nice = shutil.which("nice")
    command = ([nice, "-n", "10"] if nice else []) + [binary] + [str(a) for a in args]
    temporary = _inside(root, ".estado/tmp")
    temporary.mkdir(parents=True, exist_ok=True)
    env = {k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH") if k in os.environ}
    env.update(TMPDIR=str(temporary), CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
    try:
        result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudioError(f"No se pudo ejecutar {tool}: {error}") from error
    if result.returncode:
        raise StudioError(f"{tool} no pudo procesar el recurso: " + result.stderr.decode("utf-8", "replace")[-1800:])
    return result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace")


def _probe(path, root):
    stdout, unused = _run("ffprobe", ["-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-show_format", "-show_streams", "-of", "json", str(path)], root, 30)
    info = json.loads(stdout)
    info.get("format", {}).pop("filename", None)
    info.get("format", {}).pop("tags", None)
    for stream in info.get("streams", []):
        stream.pop("tags", None)
        stream.pop("side_data_list", None)
    return info


def _number(value, key, lo, hi, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise StudioError(f"Parámetro {key} fuera de rango ({lo}–{hi}).")
    if integer and value != int(value):
        raise StudioError(f"{key} debe ser entero.")
    return int(value) if integer else float(value)


def _options(spec, options):
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise StudioError("Las opciones de herramienta deben ser un objeto.")
    if any(not isinstance(key, str) for key in options):
        raise StudioError("Los nombres de parámetros deben ser texto.")
    if options.get('audio_stream_index') is not None:
        if 'audio_stream' in options and options['audio_stream'] is not None:
            raise StudioError('audio_stream y audio_stream_index son mutuamente excluyentes.')
        if type(options['audio_stream_index']) is not int:
            raise StudioError('audio_stream_index debe ser un índice global entero.')
    allowed = {p["key"] for p in spec["parameters"]}
    if set(options) - allowed:
        raise StudioError("Parámetros no admitidos: " + ", ".join(sorted(set(options) - allowed)))
    normalized = {}
    for p in spec["parameters"]:
        if p['key']=='audio_stream' and options.get('audio_stream_index') is not None:
            continue
        value = options.get(p["key"], p["default"])
        if value is None and p["optional"]:
            normalized[p["key"]] = None
        elif p["type"] == "color":
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise StudioError("El color debe tener formato #RRGGBB.")
            normalized[p["key"]] = value.lower()
        else:
            normalized[p["key"]] = _number(value, p["key"], p["min"], p["max"], p["type"] == "integer")
    for key in ("max_width", "max_height"):
        if key in normalized and normalized[key] % 2:
            raise StudioError(f"{key} debe ser par.")
    if normalized.get('audio_stream_index') is not None:normalized.pop('audio_stream',None)
    return normalized


def _span(info, options, maximum):
    try:
        total = float(info.get("format", {}).get("duration", 0))
    except (TypeError, ValueError):
        total = 0
    if not math.isfinite(total) or total <= 0:
        raise StudioError("La herramienta requiere una duración real disponible.")
    start = options.get("start", 0)
    duration = options.get("duration")
    duration = total - start if duration is None else duration
    if duration <= 0 or duration > maximum or start + duration > total + .05:
        raise StudioError(f"Selecciona un tramo válido de hasta {maximum} s dentro del recurso ({total:.3f} s).")
    return start, min(duration, total - start)


def _input(path, start, duration):
    return ["-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-threads", "2", "-ss", f"{start:.6f}", "-t", f"{duration:.6f}", "-i", str(path)]


def _base(verbose="error"):
    return ["-nostdin", "-hide_banner", "-v", verbose, "-filter_threads", "2", "-filter_complex_threads", "2"]


def _loudness(path, root, start, duration, audio_stream=0, target_i=-16, target_tp=-1.5, lra=9, *, audio_stream_index=None):
    filter = f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}:print_format=json"
    mapping=f'0:{audio_stream_index}' if audio_stream_index is not None else f'0:a:{audio_stream}'
    unused, log = _run("ffmpeg", _base("info") + _input(path, start, duration) + ["-map", mapping, "-vn", "-af", filter, "-threads","2", "-f", "null", "-"], root, max(30, min(1800, duration * 5 + 30)))
    matches = list(re.finditer(r'\{\s*"input_i"[\s\S]*?\}', log))
    if not matches:
        raise StudioError("FFmpeg no devolvió medidas loudnorm verificables.")
    raw = json.loads(matches[-1].group())

    def finite(key):
        try:
            value = float(raw[key])
            return value if math.isfinite(value) else None
        except (KeyError, ValueError, TypeError):
            return None

    measured = {"integrated_lufs": finite("input_i"), "true_peak_dbtp": finite("input_tp"), "loudness_range_lu": finite("input_lra"), "threshold_lufs": finite("input_thresh")}
    return {"method": "FFmpeg loudnorm / EBU R128", "measurements": measured, "raw": raw, "audio_listened": False, "source_start": start, "duration": duration}


def _tempo_chain(rate):
    factors = []
    remaining = rate
    while remaining < .5 - 1e-10:
        factors.append(.5)
        remaining /= .5
    while remaining > 2 + 1e-10:
        factors.append(2.)
        remaining /= 2
    factors.append(remaining)
    return ",".join(f"atempo={factor:.8g}" for factor in factors)


def _fps(video):
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "30")))
    except (ZeroDivisionError, ValueError):
        fps = 30
    return fps if math.isfinite(fps) and 0 < fps <= 240 else 30


def _retime(source, candidate, root, start, duration, rate, video, has_audio):
    """Separate stream processing avoids short-clip FFmpeg scheduler stalls."""
    target = duration / rate
    visual = candidate.with_name("retimed_video.mp4")
    fps = _fps(video)
    video_filter = f"setpts=(PTS-STARTPTS)/{rate:.8g},fps={fps:.8g},tpad=stop_mode=clone:stop_duration=1,trim=duration={target:.8g}"
    args = _base() + _input(source, start, duration)
    args += ["-map", f"0:{video['index']}", "-an", "-sn", "-dn", "-vf", video_filter, "-t", f"{target:.8g}",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-threads", "2", "-y", str(visual)]
    timeout = max(30, min(1800, duration * 30 + 30))
    _run("ffmpeg", args, root, timeout)
    if not has_audio:
        os.replace(visual, candidate)
        return
    audio = candidate.with_name("retimed_audio.wav")
    audio_filter = f"asetpts=PTS-STARTPTS,{_tempo_chain(rate)},apad,atrim=duration={target:.8g}"
    _run("ffmpeg", _base() + _input(source, start, duration) + ["-map", "0:a:0", "-vn", "-af", audio_filter,
         "-t", f"{target:.8g}", "-c:a", "pcm_s16le", "-ar", "48000", "-threads", "2", "-y", str(audio)], root, timeout)
    _run("ffmpeg", _base() + _input(visual, 0, target) + _input(audio, 0, target) + ["-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{target:.8g}", "-movflags", "+faststart",
         "-map_metadata", "-1", "-threads", "2", "-y", str(candidate)], root, timeout)


@contextmanager
def _lock(root):
    with LOCK:
        path = _inside(root, ".estado/media_tools.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def process(asset: dict, operation: str, options: dict | None = None, root: Path | None = None, *, progress=None, cancel=None) -> dict:
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        from .analysis import _check_cancel
        _check_cancel(cancel)
        result=_process(asset,operation,options,root,progress=progress,cancel=cancel)
        _check_cancel(cancel)
        return result


def _process(asset: dict, operation: str, options: dict | None = None, root: Path | None = None, *, progress=None, cancel=None) -> dict:
    """Return a real analysis or a canonical derivative with provenance.

    Output paths are relative to root. The caller may register a derivative as
    a *new* asset after this succeeds; no source/project is changed here.
    """
    root = _inside(root or ROOT, ".")
    if operation == "remove_background_video":
        from .segmentation import process as segment
        return segment(asset, options, root, progress=progress, cancel=cancel)
    spec = next((s for s in OPERATIONS if s["id"] == operation), None)
    if not spec:
        raise StudioError("Operación multimedia desconocida.")
    normalized = _options(spec, options)
    if not isinstance(asset, dict) or not isinstance(asset.get("path"), str):
        raise StudioError("La herramienta requiere un recurso local con path.")
    source = _inside(root, asset["path"], True)
    if source.suffix.lower() not in INPUT_EXTENSIONS:
        raise StudioError("Formato de entrada no admitido por estas herramientas.")
    source_sha = _hash(source)
    if asset.get("sha256") and asset["sha256"] != source_sha:
        raise StudioError("El recurso cambió respecto al catálogo: revisar antes de procesar.", 409)
    with _lock(root):
        info = _probe(source, root)
        streams = info.get("streams", [])
        videos = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
        audios = [s for s in streams if s.get("codec_type") == "audio"]
        if operation in ("scene_detect", "proxy_video", "speed_video", "reverse_video", "chromakey_video") and not videos:
            raise StudioError("Esta operación requiere una pista de video real.")
        if operation in ("extract_audio", "denoise_audio", "normalize_audio", "loudness_analysis"):
            absolute=normalized.get('audio_stream_index')
            if absolute is None and (not audios or normalized.get("audio_stream", 0) >= len(audios)):
                raise StudioError("La pista de audio seleccionada no existe.")
            selected=select_audio_stream(info,absolute) if absolute is not None else select_audio_stream(info,audios[normalized.get('audio_stream',0)]['index'])
        provenance = {"operation": operation, "source_asset_id": asset.get("id"), "source_path": source.relative_to(root).as_posix(), "source_sha256": source_sha,
                      "parameters": normalized, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpu_used": False, "max_ffmpeg_threads": 2,
                      "niceness": 10 if shutil.which("nice") else None, "visual_reviewed": False, "audio_listened": False, "approved_for_ascendia": False,
                      "changes_narration_timing": operation in ("speed_video", "reverse_video"), "limitations": spec["limitations"]}
        if operation in ("extract_audio", "denoise_audio", "normalize_audio", "loudness_analysis"):
            provenance['audio_selection']={'stream_index':selected['index'],'audio_ordinal':selected['audio_ordinal'],
                                            'ffmpeg_map':selected['ffmpeg_map'],'voice_verified':False,'source_sha256':source_sha}
        if operation == "probe":
            if _hash(source) != source_sha:
                raise StudioError("El recurso cambió durante la inspección.", 409)
            return {"operation": operation, "kind": "analysis", "probe": info, "provenance": provenance}
        start, duration = _span(info, normalized, 60 if operation == "reverse_video" else 3600)
        provenance.update(source_span={"start": start, "duration": duration})
        if operation == "loudness_analysis":
            result = _loudness(source, root, start, duration, audio_stream_index=selected['index'])
            if _hash(source) != source_sha:
                raise StudioError("El recurso cambió durante el análisis.", 409)
            return {"operation": operation, "kind": "analysis", "probe": info, "provenance": provenance, **result}
        if operation == "scene_detect":
            filter = f"scale=320:-2,select='gt(scene,{normalized['threshold']:.8g})',metadata=mode=print:key=lavfi.scene_score"
            unused, log = _run("ffmpeg", _base("info") + _input(source, start, duration) + ["-map", "0:v:0", "-an", "-vf", filter, "-fps_mode", "vfr", "-f", "null", "-"], root, max(30, min(1800, duration * 10 + 30)))
            scenes = []
            current = None
            for line in log.splitlines():
                match = re.search(r"pts_time:([-+\d.eE]+)", line)
                if match:
                    current = float(match.group(1))
                score = re.search(r"lavfi\.scene_score=([-+\d.eE]+)", line)
                if score and current is not None:
                    scenes.append({"timestamp": round(start + current, 6), "score": float(score.group(1))})
            if _hash(source) != source_sha:
                raise StudioError("El recurso cambió durante la detección de cortes.", 409)
            return {"operation": operation, "kind": "analysis", "probe": info, "scenes": scenes[:10000], "truncated": len(scenes) > 10000, "method": "FFmpeg scene score, 320px proxy", "provenance": provenance}
        if operation == "reverse_video":
            video = videos[0]
            fps = _fps(video)
            estimated = math.ceil(duration * fps) * int(video["width"]) * int(video["height"]) * 4 + math.ceil(duration * 48000) * 8
            if estimated > MAX_REVERSE_BYTES:
                raise StudioError("El reverse supera el buffer estimado de 512 MiB. Usa un proxy o un tramo más corto.")
            provenance["estimated_reverse_buffer_bytes"] = estimated
        provenance["processor_sha256"] = _hash(__file__)
        key_data = {"source": source_sha, "operation": operation, "options": normalized, "processor": provenance["processor_sha256"]}
        key = hashlib.sha256(json.dumps(key_data, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
        folder = _inside(root, ".estado/tools")
        folder.mkdir(parents=True, exist_ok=True)
        output = _inside(root, folder / (key + spec["extension"]))
        receipt = _inside(root, folder / (key + ".json"))
        if output.exists():
            previous = json.loads(receipt.read_text()) if receipt.is_file() else None
            if not previous or previous.get("sha256") != _hash(output):
                raise StudioError("El derivado existente cambió o no tiene recibo; no se sobrescribe.", 409)
            if _hash(source) != source_sha:
                raise StudioError("El recurso cambió mientras se consultaba el derivado.", 409)
            return {**previous, "reused": True}
        if output == source:
            raise StudioError("Nunca se reemplaza el archivo fuente.", 403)
        before = None
        args = _base() + _input(source, start, duration)
        if operation in ("extract_audio", "denoise_audio", "normalize_audio"):
            args += ["-map", selected['ffmpeg_map'], "-vn"]
            filter = "aresample=48000:async=1:first_pts=0"
            if operation == "denoise_audio":
                filter += ','+(f"highpass=f={normalized['highpass_hz']}," if normalized["highpass_hz"] else "") + f"afftdn=nr={normalized['noise_reduction_db']}:nf={normalized['noise_floor_db']}"
            if operation == "normalize_audio":
                before = _loudness(source, root, start, duration, target_i=normalized["target_i"], target_tp=normalized["target_tp"], lra=normalized["lra"],audio_stream_index=selected['index'])
                if any(before["measurements"][key] is None for key in ("integrated_lufs", "true_peak_dbtp", "threshold_lufs")):
                    raise StudioError("No se puede normalizar silencio o audio sin sonoridad finita.")
                raw = before["raw"]
                filter += ','+f"loudnorm=I={normalized['target_i']}:TP={normalized['target_tp']}:LRA={normalized['lra']}:measured_I={float(raw['input_i'])}:measured_TP={float(raw['input_tp'])}:measured_LRA={float(raw['input_lra'])}:measured_thresh={float(raw['input_thresh'])}:offset={float(raw['target_offset'])}:linear=true"
            args += ["-af", filter, "-t",f'{duration:.8g}', "-ac", str(normalized["channels"]), "-ar", "48000", "-c:a", "pcm_s16le"]
        else:
            args += ["-map", f"0:{videos[0]['index']}", "-map", "0:a:0?", "-sn", "-dn"]
            if operation == "proxy_video":
                args += ["-vf", f"scale={normalized['max_width']}:{normalized['max_height']}:force_original_aspect_ratio=decrease:force_divisible_by=2,fps={normalized['fps']},setsar=1"]
            elif operation == "reverse_video":
                args += ["-vf", "reverse,setpts=PTS-STARTPTS"]
                if audios:
                    args += ["-af", "areverse,asetpts=PTS-STARTPTS"]
            elif operation == "chromakey_video":
                args += ["-vf", f"chromakey=color=0x{normalized['color'][1:]}:similarity={normalized['similarity']}:blend={normalized['blend']},format=argb"]
            if operation == "chromakey_video":
                args += ["-c:v", "qtrle", "-pix_fmt", "argb", "-c:a", "pcm_s16le", "-ar", "48000"]
            else:
                args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart"]
        args += ["-map_metadata", "-1", "-threads", "2"]
        temporary_root = _inside(root, ".estado/tmp")
        with tempfile.TemporaryDirectory(prefix="media-tool-", dir=temporary_root) as temporary:
            candidate = _inside(root, Path(temporary) / ("candidate" + spec["extension"]))
            if operation == "speed_video":
                _retime(source, candidate, root, start, duration, normalized["rate"], videos[0], bool(audios))
            else:
                _run("ffmpeg", args + ["-y", str(candidate)], root, max(30, min(1800, duration * 30 + 30)))
            measured = _probe(candidate, root)
            _run("ffmpeg", _base() + ["-xerror", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-threads", "2", "-i", str(candidate), "-threads", "2", "-f", "null", "-"], root, max(30, min(1800, duration * 10 + 30)))
            after = _loudness(candidate, root, 0, float(measured["format"]["duration"])) if before else None
            if _hash(source) != source_sha:
                raise StudioError("El original cambió durante el procesamiento; el derivado no se promueve.", 409)
            result = {"operation": operation, "kind": "process", "path": output.relative_to(root).as_posix(), "probe": measured, "provenance": provenance,
                      "sha256": _hash(candidate), "md5": _hash(candidate, "md5"), "size": candidate.stat().st_size, "reused": False,
                      "verification": {"decode_ok": True, "visual": False, "audio": False, "approved": False}}
            if before:
                result.update(loudness_before=before, loudness_after=after)
            os.replace(candidate, output)
            temp_receipt = _inside(root, Path(temporary) / "receipt.json")
            temp_receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            os.replace(temp_receipt, receipt)
            return result


def analyze(asset: dict, operation: str = "probe", options: dict | None = None, root: Path | None = None) -> dict:
    if operation not in {item["id"] for item in OPERATIONS if item["kind"] == "analysis"}:
        raise StudioError("analyze solo admite operaciones de medición.")
    return process(asset, operation, options, root)


def bind_canonical(result: dict, asset: dict, root: Path | None = None) -> dict:
    """Replace our duplicate cache bytes with a link to the registered asset.

    Only a generated cache file with a matching receipt may be replaced. The
    original and the registered canonical asset are never modified or deleted.
    """
    root = _inside(root or ROOT, ".")
    if result.get("kind") != "process" or not result.get("path"):
        return result
    path = Path(result["path"])
    if path.is_absolute() or path.parent.as_posix() != ".estado/tools" or not re.fullmatch(r"[a-f0-9]{24}\.(wav|mp4|mov)", path.name):
        raise StudioError("Solo se enlazan derivados canónicos propios de .estado/tools.", 403)
    raw_cache = root / path
    receipt = _inside(root, path.with_suffix(".json"), True)
    target = _inside(root, asset.get("path", ""), True)
    with _lock(root):
        cache = _inside(root, raw_cache, True)
        recorded = json.loads(receipt.read_text(encoding="utf-8"))
        expected = result.get("sha256")
        if not expected or any(value != expected for value in (recorded.get("sha256"), asset.get("sha256"), _hash(cache), _hash(target))):
            raise StudioError("No coinciden los bytes del derivado y el recurso canónico.", 409)
        if cache != target:
            if not raw_cache.parent.resolve().is_relative_to(root):
                raise StudioError("La ruta del cache salió de SOFTWARE.", 403)
            link = raw_cache.with_name(raw_cache.name + "." + uuid.uuid4().hex + ".link")
            try:
                link.symlink_to(os.path.relpath(target, raw_cache.parent))
                os.replace(link, raw_cache)
            finally:
                link.unlink(missing_ok=True)
        recorded.update(canonical_asset_id=asset.get("id"), canonical_path=target.relative_to(root).as_posix())
        temporary = receipt.with_name(receipt.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(json.dumps(recorded, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            os.replace(temporary, receipt)
        finally:
            temporary.unlink(missing_ok=True)
        return {**result, "canonical_asset_id": asset.get("id"), "canonical_path": recorded["canonical_path"]}
