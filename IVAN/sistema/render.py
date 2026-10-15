#!/usr/bin/env python3
"""Render determinista HyperFrames + mezcla FFmpeg. No aprueba resultados."""
import sys,subprocess,argparse,os,re,resource,fcntl
from pathlib import Path
sys.dont_write_bytecode=True
import workflow as w

def mix(project, image_video, output):
    source = w.inside(project['original']['archivo'])
    args = ['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(image_video), '-i', str(source)]
    duration = float(project['metadata']['format']['duration'])
    audio = project.get('audio', {})
    processing='' if audio.get('voz',{}).get('procesamiento')=='original_sin_procesar' else 'highpass=f=65,loudnorm=I=-16:TP=-1.5:LRA=9,'
    # Una fuente breve puede terminar antes de la resolución visual; conservar
    # la voz y añadir únicamente silencio, nunca repetirla ni estirarla.
    graph = [f'[1:a]{processing}apad,atrim=duration={duration},asplit=2[voz][control]']
    inputs, labels = 2, ['[voz]']
    music = audio.get('musica')
    if music:
        if not music.get('derechos'):
            raise ValueError('Registrar los derechos disponibles de la música seleccionada')
        args.extend(['-stream_loop', '-1', '-ss', str(music['entrada_archivo']), '-i', str(w.inside(music['archivo']))])
        graph.extend([f'[{inputs}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,volume={music.get("ganancia_db", -25)}dB,afade=t=in:d=0.2,afade=t=out:st={max(0,duration-.6):.3f}:d=0.6[musica]',
                      '[musica][control]sidechaincompress=threshold=.06:ratio=4:attack=20:release=250[fondo]'])
        labels.append('[fondo]'); inputs += 1
    else:
        graph.append('[control]anullsink')
    for i, cue in enumerate(audio.get('efectos', [])):
        if cue['inicio']>=duration:continue
        args.extend(['-i', str(w.inside(cue['archivo']))])
        graph.append(f'[{inputs}:a]volume={cue.get("ganancia_db", -18)}dB,adelay={round(cue["inicio"]*1000)}:all=1[fx{i}]')
        labels.append(f'[fx{i}]'); inputs += 1
    graph.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=.84:level=false:latency=1[audio]')
    args.extend(['-filter_complex', ';'.join(graph), '-map', '0:v', '-map', '[audio]', '-c:v', 'copy',
                 '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-t', str(duration), '-movflags', '+faststart', '-y', str(output)])
    subprocess.run(args, check=True)


def render(project_id, sample=None):
    # Los intermediarios y la GPU se comparten: no permitir renders que se pisan.
    with w.inside('.estado/render.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Ya hay un render de IVAN activo; esperar su finalización')
        try:return _render(project_id,sample)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def _render(project_id, sample=None):
    from preflight import require_ready
    require_ready()
    project=w.read_json('proyectos/'+project_id+'/proyecto.json')
    w.require_current_instructions(project)
    if project.get('requiere_aprobacion_prueba_v4') and not sample:
        if project.get('aprobacion_usuario_prueba',{}).get('estado')!='aprobada':
            raise ValueError('ASCENDIA V4: entregar prueba de 10 s y esperar aprobación explícita del usuario antes del completo')
        if project.get('motor',{}).get('alcance_hasta_s',0)<float(project['metadata']['format']['duration']):
            raise ValueError('Reconstruir las escenas pendientes del resto del reel antes del completo')
    w.require_resource_selection(project,hasta=sample)
    if w.read_json('sistema/perfil.json').get('skills_obligatorias'):
        from skills import validate,check_composition
        validate(project,phase='render');check_composition(project)
    folder=w.inside('proyectos/'+project_id)
    if not sample:
        review=project.get('muestra') or {}
        if review.get('estado')!='aprobada' or review.get('edicion_sha256')!=w.edit_digest(project):
            raise ValueError('Aprobar la muestra vigente de 8–12 s antes del render completo')
    composition=project['motor']['composicion']
    if sample:
        if not 8<=sample<=12:raise ValueError('La muestra debe durar 8–12 segundos')
        if project.get('requiere_aprobacion_prueba_v4') and sample!=10:raise ValueError('ASCENDIA V4 requiere los primeros 10 s')
        html=w.inside(composition).read_text()
        html=re.sub(r'(data-composition-id="ivan" data-start="0" data-duration=")[^"]+',lambda m:m.group(1)+str(sample),html)
        composition='.estado/tmp/muestra.html';w.inside(composition).write_text(html)
    video=w.inside('.estado/tmp/imagen.mp4')
    env=os.environ.copy()
    env.update(TMPDIR=f'/proc/{os.getpid()}/cwd/.estado/tmp',NODE_OPTIONS='--import '+str(w.inside('sistema/confinar.mjs')),CI='1')
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    browser_flag='--no-browser-gpu' if project.get('motor',{}).get('captura_cpu') else '--browser-gpu'
    cmd=['node',str(w.inside('.estado/herramientas/node_modules/hyperframes/bin/hyperframes.mjs')),'render',str(w.ROOT),'--composition',composition,'--output',str(video),'--fps','30','--crf','17','--workers','1',browser_flag,'--gpu','--video-frame-format','jpg','--sdr','--no-best-effort','--experimental-fast-capture=false']
    log=w.inside('.estado/tmp/render.log')
    with log.open('w') as output:
        result=subprocess.run(cmd,env=env,stdout=output,stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text()[-6000:]);raise RuntimeError('Falló HyperFrames; consultar '+str(log))
    print('HyperFrames: captura completa;',browser_flag,'; codificación NVENC solicitada. Diagnóstico en .estado/tmp/render.log')
    target=folder/(project.get('muestra_nombre','muestra.mp4') if sample else 'candidato.mp4')
    if sample:
        from copy import deepcopy
        shortened=deepcopy(project);shortened['metadata']['format']['duration']=str(sample)
        mix(shortened,video,target)
    else:mix(project,video,target)
    video.unlink();print('Render generado:',target)

if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('project_id');cli.add_argument('--muestra',type=float);args=cli.parse_args();render(args.project_id,args.muestra)
