#!/usr/bin/env python3
"""Auditoría de TODOS los frames: bandas y alternancia A/B/A; no certifica calidad editorial."""
import os,sys,json,subprocess,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.dont_write_bytecode=True;os.chdir(ROOT)
def inside(value):
    p=(ROOT/value).resolve()
    if not p.is_relative_to(ROOT):raise ValueError('Solo rutas dentro de IVAN')
    return p
def audit(source,calibration=False):
    ffmpeg=inside('.estado/herramientas/ffmpeg/bin/ffmpeg')
    frames=np.frombuffer(subprocess.check_output([str(ffmpeg),'-v','error','-i',str(source),'-vf','scale=180:320','-f','rawvideo','-pix_fmt','rgb24','-']),dtype=np.uint8).reshape(-1,320,180,3)
    # Excluir esquinas del indicador. Un fondo negro deliberado no es por sí solo fallo.
    dark=np.mean(np.max(frames[:,:,12:-12,:],axis=3)<22,axis=2)>.98
    bands=[]
    for rows in dark:
        n=0
        for x in rows[::-1]:
            if not x:break
            n+=1
        bands.append(n)
    a=frames.astype(np.float32)
    delta=np.mean(np.abs(a[1:]-a[:-1]),axis=(1,2,3))
    aba=np.mean(np.abs(a[2:]-a[:-2]),axis=(1,2,3))
    lower=a[:,-96:]
    lower_delta=np.mean(np.abs(lower[1:]-lower[:-1]),axis=(1,2,3))
    lower_aba=np.mean(np.abs(lower[2:]-lower[:-2]),axis=(1,2,3))
    bands_a=np.array(bands)
    band_jump=np.abs(np.diff(bands_a))
    band_aba=np.abs(bands_a[2:]-bands_a[:-2])
    flags=np.where(((np.minimum(delta[:-1],delta[1:])>12)&(aba<np.minimum(delta[:-1],delta[1:])*.45))|
        ((np.minimum(lower_delta[:-1],lower_delta[1:])>12)&(lower_aba<np.minimum(lower_delta[:-1],lower_delta[1:])*.45))|
        ((np.minimum(band_jump[:-1],band_jump[1:])>=8)&(band_aba<=2)))[0]+1
    # Agrupar alternancias consecutivas, tolerando 2 frames de pausa entre detecciones.
    runs=[]
    for f in flags:
        if runs and f<=runs[-1][-1]+3:runs[-1].append(int(f))
        else:runs.append([int(f)])
    errors=[{'inicio_s':round(r[0]/30,3),'fin_s':round((r[-1]+1)/30,3),'frames_detectados':len(r)} for r in runs if len(r)>=3]
    proof={'archivo':str(source.relative_to(ROOT)),'frames_revisados':len(frames),'resolucion_analisis':[180,320],
      'max_banda_inferior_px_1080p':max(bands,default=0)*6,'frames_con_banda':sum(x>0 for x in bands),
      'alternancias_sospechosas':errors,'estado':'rechazado' if errors else 'sin_alternancia_detectada',
      'limite':'Heurística temporal; requiere inspección visual y revisión de cortes, captions y contenido. No aprueba el video.'}
    if calibration:
        # Esquinas fijas y fondo claro hasta el borde inferior, de geometría conocida.
        expected=np.array([[0,255,0],[0,0,255],[255,255,0],[0,255,255]])
        observed=np.stack([frames[:,1:7,1:7].mean((1,2)),frames[:,1:7,-7:-1].mean((1,2)),frames[:,-7:-1,1:7].mean((1,2)),frames[:,-7:-1,-7:-1].mean((1,2))],axis=1)
        bad=np.max(np.abs(observed-expected),axis=(1,2))>50
        bottom=frames[:,-5:,30:-30].mean((1,2,3))
        proof.update(frames_geometria_incorrecta=int(bad.sum()),frames_fondo_inferior_incorrecto=int((bottom<200).sum()))
        proof['estado']='aprobado' if len(frames)==60 and not bad.any() and (bottom>=200).all() and not errors else 'rechazado'
    return proof
if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('archivo');cli.add_argument('--calibracion',action='store_true');cli.add_argument('--salida',default='.estado/tmp/auditoria_temporal.json');args=cli.parse_args()
    result=audit(inside(args.archivo),args.calibracion);inside(args.salida).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
