"""Decodifica 90 frames y compara el MP4 HyperFrames con las poses GSAP reales."""
import sys,json,subprocess
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image,ImageDraw
import workflow as w
from auditar_temporal import audit
FOLDER='ejemplos/arquitectura_motion_3s'
def run():
    file=FOLDER+'/prueba_gsap_3s.mp4';meta=w.probe(file)
    video=next(s for s in meta['streams'] if s['codec_type']=='video')
    pixels=np.frombuffer(subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','2','-i',str(w.inside(file)),'-vf','scale=270:480','-pix_fmt','rgb24','-f','rawvideo','-']),dtype=np.uint8).reshape(-1,480,270,3)
    samples=[]
    for t in [.3,.5,.8,1,1.8,2.4,2.8]:
        expected=np.array(Image.open(w.inside(FOLDER+f'/evidencias/html_{t:.3f}.png')).convert('RGB').resize((270,480)),dtype=float)
        observed=pixels[round(t*30)].astype(float)
        region=(slice(90,400),slice(15,255))
        corr=float(np.corrcoef(expected[region].ravel(),observed[region].ravel())[0,1])
        samples.append({'tiempo_s':t,'correlacion_pose':corr,'error_rgb_medio':float(np.mean(np.abs(expected-observed)))})
    for second in range(3):
        sheet=Image.new('RGB',(6*270,5*506),'#15191e');draw=ImageDraw.Draw(sheet)
        for j in range(30):
            i=second*30+j;x=j%6*270;y=j//6*506;sheet.paste(Image.fromarray(pixels[i]),(x,y));draw.text((x+6,y+483),f'f{i} · {i/30:.3f}s',fill='white')
        sheet.save(w.inside(FOLDER+f'/continuidad_{second}.jpg'),quality=94)
    times=[.0,.2,.5,.8,1,1.2,1.5,1.8,2.1,2.4,2.7,2.966667]
    sheet=Image.new('RGB',(4*270,3*506),'#15191e');draw=ImageDraw.Draw(sheet)
    for j,t in enumerate(times):
        i=min(89,round(t*30));x=j%4*270;y=j//4*506;sheet.paste(Image.fromarray(pixels[i]),(x,y));draw.text((x+6,y+483),f'{i/30:.3f}s · MP4',fill='white')
    sheet.save(w.inside(FOLDER+'/fotogramas_gsap.jpg'),quality=96)
    temporal=audit(w.inside(file));temporal['sha256']=w.digest(file);w.write_json(FOLDER+'/auditoria_temporal.json',temporal)
    browser=w.read_json(FOLDER+'/verificacion_gsap.json');check=w.read_json(FOLDER+'/diagnosticos_skills/check.json')
    checks={'3s':abs(float(meta['format']['duration'])-3)<.01,'90_frames':len(pixels)==90,
      '1080x1920':(video['width'],video['height'])==(1080,1920),'30fps':video['r_frame_rate']=='30/1','h264':video['codec_name']=='h264',
      'poses_gsap_presentes_en_render':all(x['correlacion_pose']>.98 and x['error_rgb_medio']<8 for x in samples),
      'sin_alternancia_detectada':temporal['estado']=='sin_alternancia_detectada',
      'biblioteca_y_mecanismos_funcionales':all(browser['comprobaciones'].values()),
      'check_con_navegador':check.get('ok') is True and check.get('browserSkipped') is False,
      'codigo_timeline_vigente':browser['timeline_sha256']==w.digest(FOLDER+'/timeline.gsap.js') and browser['html_sha256']==w.digest(FOLDER+'/index.html')}
    result={'fecha':w.utc(),'estado':'pendiente_revision_visual','archivo':file,'sha256':w.digest(file),
      'timeline_sha256':w.digest(FOLDER+'/timeline.gsap.js'),'html_sha256':w.digest(FOLDER+'/index.html'),
      'comprobaciones':checks,'poses_comparadas':samples,'frames_revisados':90,'audio':'AAC silencioso; prueba técnica sin narración',
      'referencia_motion':'CLONE 0,60–3,60 s: agrupación, reorganización, cambio de estado y revelación. El morph es una implementación propia.',
      'limite':'Verifica arquitectura y correspondencia temporal del render; no aprueba un reel completo ni fidelidad editorial de un nuevo guion.'}
    w.write_json(FOLDER+'/auditoria_arquitectura.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
    if not all(checks.values()):raise ValueError('Prueba técnica fallida; corregir antes de entregar')
if __name__=='__main__':run()
