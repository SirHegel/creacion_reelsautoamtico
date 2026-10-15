"""Render exclusivo del componente aprobado; no monta ni exporta un reel."""
import fcntl, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'sistema'))
import workflow as w
from skills import cli,validate,check_composition

def run():
    folder='ejemplos/clone_componente/'
    p=w.read_json(folder+'proyecto.json')
    w.require_current_instructions(p);validate(p,phase='render')
    a=p['aprobacion_diseno']
    if not a['usuario_aprobo']:raise ValueError('No existe aprobación del diseño')
    for name,key in [('diseno.svg','diseno_sha256'),('clone_diseno_estatico.png','png_sha256')]:
        if w.digest(HERE/name)!=a[key]:raise ValueError('El diseño aprobado cambió')
    with w.inside('.estado/render.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        check_composition(p)
        target=w.inside('.estado/tmp/clone_render_imagen.mp4')
        args=['render',str(ROOT),'--composition',p['motor']['composicion'],
          '--output',str(target),'--fps','30','--crf','17','--workers','1',
          '--browser-gpu','--gpu','--video-frame-format','jpg','--sdr',
          '--no-best-effort','--experimental-fast-capture=false']
        r=cli(args);(HERE/'render.log').write_text(r.stdout+'\n'+r.stderr)
        if r.returncode:raise RuntimeError('Render incompleto; ver render.log')
        audio=HERE/'assets/referencia_audio.wav'
        subprocess.run(['ffmpeg','-v','error','-i',str(ROOT/'recursos/B2_CLONE.mp4'),
          '-af','atrim=start=1.6:end=3.2,asetpts=N/SR/TB','-ar','48000','-ac','2',
          '-c:a','pcm_s16le','-y',str(audio)],check=True)
        out=HERE/'clone_segmento_animado.mp4'
        subprocess.run(['ffmpeg','-v','error','-i',str(target),'-i',str(audio),
          '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
          '-t','1.6','-movflags','+faststart','-y',str(out)],check=True)
        target.unlink()
        w.write_json(folder+'render_ejecucion.json',{'fecha':w.utc(),
          'comando':['hyperframes',*args],'returncode':r.returncode,
          'composicion_sha256':w.digest(p['motor']['composicion']),
          'timeline_sha256':w.digest(HERE/'timeline.gsap.js'),
          'mp4_sha256':w.digest(out),'duracion_s':1.6,'fps':30,
          'diseno_aprobado_intacto':True,
          'audio':'Audio del intervalo original CLONE1.6–3.2; mux FFmpeg posterior, sin nueva narración.',
          'audio_sha256':w.digest(audio)})
        print('MP4 generado: '+str(out.relative_to(ROOT)))
if __name__=='__main__':run()
