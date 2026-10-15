"""QA reutilizable de una prueba real: decode, todos los frames, voz y evidencias."""
import sys, subprocess, io, json
sys.dont_write_bytecode=True
import numpy as np
from PIL import Image, ImageDraw
import workflow as w
from auditar_temporal import audit

def frame(path,t,filter='scale=270:480'):
    b=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','2','-ss',str(t),'-i',str(w.inside(path)),'-frames:v','1','-vf',filter,'-f','image2pipe','-vcodec','mjpeg','-'])
    return Image.open(io.BytesIO(b)).convert('RGB')

def corr(a,b):
    a=np.asarray(a,dtype=np.float32).ravel();b=np.asarray(b,dtype=np.float32).ravel()
    return float(np.corrcoef(a,b)[0,1])

def run(ID):
    folder='proyectos/'+ID;p=w.read_json(folder+'/proyecto.json');path=folder+'/'+p['muestra_nombre']
    w.require_current_instructions(p);w.require_resource_selection(p,hasta=10)
    meta=w.probe(path);v=next(s for s in meta['streams'] if s['codec_type']=='video');a=next(s for s in meta['streams'] if s['codec_type']=='audio')
    frames=np.frombuffer(subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','2','-i',str(w.inside(path)),'-vf','scale=180:320','-f','rawvideo','-pix_fmt','rgb24','-']),dtype=np.uint8).reshape(-1,320,180,3)
    temporal=audit(w.inside(path));temporal['sha256']=w.digest(path);w.write_json(folder+'/auditoria_temporal.json',temporal)
    tiles=[]
    for k,start in enumerate(range(0,len(frames),30)):
        canvas=Image.new('RGB',(5*180,6*343),'#15191e');d=ImageDraw.Draw(canvas)
        for j,i in enumerate(range(start,min(start+30,len(frames)))):
            x=j%5*180;y=j//5*343;canvas.paste(Image.fromarray(frames[i]),(x,y));d.text((x+5,y+322),f'f{i} {i/30:.3f}s',fill='white')
        name=f'{folder}/continuidad/fotogramas_{k:02d}.jpg';w.inside(name).parent.mkdir(exist_ok=True);canvas.save(w.inside(name),quality=95);tiles.append(name)
    times=p.get('qa_fotogramas_s',[.2,.8,1.8,2.5,3.3,4.5,5.1,5.6,6.3,6.9,7.4,8.7,9.8])
    sheet=Image.new('RGB',(5*270,3*506),'#15191e');d=ImageDraw.Draw(sheet)
    for i,t in enumerate(times):
        x=i%5*270;y=i//5*506;sheet.paste(frame(path,t),(x,y));d.text((x+7,y+483),f'{t:.2f}s · MP4',fill='white')
    sheet.save(w.inside(folder+'/fotogramas_prueba.jpg'),quality=95)
    def pcm(file):
        return np.frombuffer(subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-i',str(w.inside(file)),'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32)
    original=pcm(p['original']['archivo']);mixed=pcm(path);voice=corr(original[:min(len(original),len(mixed))],mixed[:min(len(original),len(mixed))])
    border=[]
    for t in p.get('qa_bordes_s',[]):
        expected=w.inside(f'.estado/tmp/review_{t:.3f}.png')
        if not expected.exists():raise ValueError('Capturar referencia de lienzo para verificar borde inferior')
        x=np.asarray(Image.open(expected).convert('RGB').resize((180,320)),dtype=float)[-8:,20:-20]
        y=frames[round(t*30),-8:,20:-20].astype(float)
        border.append({'tiempo':t,'error_rgb_medio':float(np.mean(np.abs(x-y))),'rgb_esperado':x.mean((0,1)).tolist(),'rgb_render':y.mean((0,1)).tolist()})
    assets=[]
    for test in p.get('qa_medios',[]):
        observed=frame(path,test['render_s'],test['filtro_render'])
        matches=[]
        for shift in [-1/30,0,1/30]:
            source=frame(test['archivo'],max(0,test['fuente_s']+shift),test['filtro_fuente']);matches.append(corr(observed,source))
        assets.append({'archivo':test['archivo'],'render_s':test['render_s'],'fuente_s':test['fuente_s'],'correlacion_rgb':max(matches),'tolerancia_fuente_s':1/30})
    presence=w.presence_stats(p,duration=10);actor_s=presence['segundos'];max_run=presence['max_continuo_s']
    checks={'1080x1920':(v['width'],v['height'])==(1080,1920),'30fps':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','aac':a['codec_name']=='aac','duracion_10s':abs(float(meta['format']['duration'])-10)<.05,'300_frames_decodificados':len(frames)==300,'voz_original_alineada':voice>.92,'sin_banda_inferior_divergente':bool(border) and all(x['error_rgb_medio']<12 for x in border),'medios_reales_identificados':bool(assets) and all(x['correlacion_rgb']>.88 for x in assets),'max_presencia_3s':max_run<=3,'presencia_objetivo_20porciento':actor_s/10<=.20}
    checks['continuidad_temporal']=temporal['estado']=='sin_alternancia_detectada' and temporal['frames_revisados']==300
    result={'estado':'pendiente_revision_visual_en_secuencia','archivo':path,'sha256':w.digest(path),'edicion_sha256':w.edit_digest(p),'fecha':w.utc(),'comprobaciones':checks,'audio':{'correlacion_voz_original':voice,'pico_pcm':float(np.max(np.abs(mixed))),'duracion_original_s':float(p['metadata']['format']['duration']),'voz_adicional':False,'audicion_perceptiva':False},'bordes':border,'medios_reales':assets,'presencia_programada':{'segundos':actor_s,'porcentaje':actor_s*10,'max_continuo_s':max_run},'fotogramas_consecutivos':tiles,'frames_inspeccion_temporal':len(frames),'limite':'La técnica no aprueba dirección de arte; completar revisión editorial real antes de entregar.'}
    w.write_json(folder+'/auditoria_muestra.json',result)
    print(json.dumps({k:result[k] for k in ['comprobaciones','audio','bordes','medios_reales']},ensure_ascii=False,indent=2))
    if not all(checks.values()):raise ValueError('Prueba con comprobaciones fallidas; corregir antes de entregar')
    return result

if __name__=='__main__':run(sys.argv[1])
