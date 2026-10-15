#!/usr/bin/env python3
"""Parakeet TDT v3 en CUDA, con tiempos de tokens y palabras; todo dentro de IVAN."""
import os, sys, json, time, argparse, subprocess, wave, re, resource
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT/'.estado/python'))
os.chdir(ROOT)
for key, value in {
    'HF_HOME': '.estado/cache/huggingface', 'TORCH_HOME': '.estado/cache/torch',
    'TRITON_CACHE_DIR': '.estado/cache/triton', 'XDG_CACHE_HOME': '.estado/cache',
    'TMPDIR': '.estado/tmp', 'NUMBA_CACHE_DIR': '.estado/cache/numba',
}.items():
    os.environ[key] = str(ROOT/value)
    Path(os.environ[key]).mkdir(parents=True, exist_ok=True)
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def inside(value):
    p=(ROOT/value).resolve()
    if not p.is_relative_to(ROOT): raise ValueError('La ruta debe estar dentro de IVAN')
    return p

def words_from_tokens(tokens):
    words=[]; current=None
    for token in tokens:
        for part in re.findall(r'\s+|\S+',token['token']):
            if part.isspace():
                if current: words.append(current); current=None
            elif current is None:
                current={'word':part,'start':token['start'],'end':token['end']}
            else:
                current['word']+=part; current['end']=max(current['end'],token['end'])
    if current: words.append(current)
    return words

def wait_for_gpu(precision):
    required=4200 if precision=='float32' else 3000
    quiet=None;last_notice=0
    while True:
        active=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True)
        foreign=any(line.strip() and int(line.split(',',1)[0])!=os.getpid() for line in active.splitlines())
        available=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())
        if foreign or available<required:
            quiet=None
            if time.monotonic()-last_notice>=30:
                print('Esperando fin de tareas externas y VRAM suficiente antes de cargar Parakeet.',flush=True);last_notice=time.monotonic()
        else:
            quiet=quiet or time.monotonic()
            if time.monotonic()-quiet>=25:return
        time.sleep(5)

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument('entrada'); cli.add_argument('--salida',default='.estado/tmp/parakeet_prueba.json')
    cli.add_argument('--duracion',type=float); cli.add_argument('--precision',choices=['float32','bfloat16'],default='bfloat16')
    cli.add_argument('--bloque',type=float,default=20)
    args=cli.parse_args(); source=inside(args.entrada); target=inside(args.salida)
    ffmpeg=inside('.estado/herramientas/ffmpeg/bin/ffmpeg'); audio=inside('.estado/tmp/parakeet_entrada.wav')
    cmd=[str(ffmpeg),'-v','error','-y','-i',str(source),'-vn','-ac','1','-ar','16000']
    if args.duracion:cmd+=['-t',str(args.duracion)]
    subprocess.run(cmd+[str(audio)],check=True)
    import numpy as np
    import torch
    from transformers import AutoModelForTDT, AutoProcessor
    from huggingface_hub import snapshot_download
    if not torch.cuda.is_available(): raise RuntimeError('Parakeet requiere CUDA en este workflow')
    torch.set_num_threads(6)
    model_id='nvidia/parakeet-tdt-0.6b-v3'
    started=time.perf_counter()
    model_path=snapshot_download(model_id,allow_patterns=['*.json','*.safetensors','*.txt','*.model'],max_workers=4)
    processor=AutoProcessor.from_pretrained(model_path)
    wait_started=time.perf_counter()
    wait_for_gpu(args.precision)
    wait_seconds=time.perf_counter()-wait_started
    model=AutoModelForTDT.from_pretrained(model_path,dtype=getattr(torch,args.precision),device_map='cuda').eval()
    for module in model.modules():
        if isinstance(module,torch.nn.LSTM):module.flatten_parameters()
    load_seconds=time.perf_counter()-started-wait_seconds
    with wave.open(str(audio),'rb') as wav:
        samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype=np.int16).astype(np.float32)/32768.0
    # Bloques secuenciales: preservan la memoria disponible para el escritorio y el render.
    # La segmentación definitiva de un encargo debe elegir pausas antes de usar sus tiempos como subtítulos.
    tokens=[]; texts=[]; began=time.perf_counter(); torch.cuda.reset_peak_memory_stats()
    with torch.inference_mode():
        stride=int(args.bloque*16000)
        for start in range(0,len(samples),stride):
            data=samples[start:start+stride]
            inputs=processor(data,sampling_rate=16000,return_tensors='pt').to(model.device,dtype=model.dtype)
            out=model.generate(**inputs,return_dict_in_generate=True,max_new_tokens=4096)
            decoded,stamps=processor.decode(out.sequences,durations=out.durations,skip_special_tokens=True)
            texts.extend(decoded if isinstance(decoded,list) else [decoded])
            offset=start/16000
            for t in stamps[0]:tokens.append({**t,'start':round(t['start']+offset,4),'end':round(t['end']+offset,4)})
    torch.cuda.synchronize(); elapsed=time.perf_counter()-began
    words=words_from_tokens(tokens)
    proof={'herramienta':'NVIDIA Parakeet TDT 0.6B v3','estado':'operativo' if words else 'sin_transcripcion',
        'modelo':model_id,'revision':Path(model_path).name,'fecha':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        'dispositivo':torch.cuda.get_device_name(0),'cuda':torch.version.cuda,'torch':torch.__version__,
        'precision':args.precision,'duracion_audio':len(samples)/16000,'carga_modelo_s':round(load_seconds,3),'espera_gpu_s':round(wait_seconds,3),
        'inferencia_s':round(elapsed,3),'vram_pico_mib':round(torch.cuda.max_memory_allocated()/1048576),
        'vram_reservada_mib':round(torch.cuda.max_memory_reserved()/1048576),
        'texto':' '.join(texts),'words':words,'tokens':tokens}
    target.write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in proof.items() if k not in ['words','tokens']},ensure_ascii=False))
    audio.unlink(missing_ok=True)

if __name__=='__main__':main()
