"""Reproducir la prueba autorizada de 3 s; no produce un reel completo."""
import sys,subprocess,os,fcntl
sys.dont_write_bytecode=True
import workflow as w
from skills import cli,validate,check_composition
FOLDER='ejemplos/arquitectura_motion_3s'
def run():
    p=w.read_json(FOLDER+'/proyecto.json');w.require_current_instructions(p);validate(p,phase='render')
    with w.inside('.estado/render.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Otro render de IVAN sigue activo')
        subprocess.run([sys.executable,'-B',str(w.inside(FOLDER+'/construir.py'))],check=True)
        check_composition(p)
        temp='.estado/tmp/prueba_gsap_imagen.mp4'
        args=['render',str(w.ROOT),'--composition',p['motor']['composicion'],'--output',str(w.inside(temp)),
          '--fps','30','--crf','17','--workers','1','--browser-gpu','--gpu','--video-frame-format','jpg',
          '--sdr','--no-best-effort','--experimental-fast-capture=false']
        result=cli(args);w.inside(FOLDER+'/render.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode:raise RuntimeError('HyperFrames no completó la prueba de 3 s')
        subprocess.run(['ffmpeg','-v','error','-i',str(w.inside(temp)),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo',
          '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-t','3','-movflags','+faststart',
          '-y',str(w.inside(FOLDER+'/prueba_gsap_3s.mp4'))],check=True)
        w.inside(temp).unlink();fcntl.flock(lock,fcntl.LOCK_UN)
    subprocess.run(['node',str(w.inside('sistema/verificar_gsap.mjs'))],check=True)
    subprocess.run([sys.executable,'-B',str(w.inside('sistema/auditar_gsap.py'))],check=True)
    print('Prueba técnica comprobada; completar revisión visual antes de publicación.')
if __name__=='__main__':run()
