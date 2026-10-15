"""Verificación de la prueba real: contenido, bordes, audio y evidencias consecutivas."""
import sys,subprocess,io,json
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
import numpy as np
import workflow as w
from auditar_temporal import audit

def pixels(path,t,filter='scale=270:480'):
    b=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','2','-ss',str(t),'-i',str(w.inside(path)),'-frames:v','1','-vf',filter,'-f','image2pipe','-vcodec','mjpeg','-'])
    return Image.open(io.BytesIO(b)).convert('RGB')

def correlate(a,b):
    a=np.asarray(a,dtype=np.float32).ravel();b=np.asarray(b,dtype=np.float32).ravel()
    return float(np.corrcoef(a,b)[0,1])

def run(ID):
    folder='proyectos/'+ID;p=w.read_json(folder+'/proyecto.json');path=folder+'/'+p['muestra_nombre']
    probe=w.probe(path);v=next(s for s in probe['streams'] if s['codec_type']=='video');a=next(s for s in probe['streams'] if s['codec_type']=='audio')
    temporal=audit(w.inside(path));w.write_json(folder+'/auditoria_temporal_v4.json',temporal)
    frames=np.frombuffer(subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-threads','2','-i',str(w.inside(path)),'-vf','scale=180:320','-f','rawvideo','-pix_fmt','rgb24','-']),dtype=np.uint8).reshape(-1,320,180,3)
    expected=np.array([244,241,233]);bad=[]
    for i in range(128,233):
        bottom=frames[i,-8:,25:-25].astype(float).mean((0,1))
        if np.max(np.abs(bottom-expected))>18:bad.append({'frame':i,'tiempo_s':round(i/30,3),'rgb_inferior':bottom.tolist()})
    evidence={}
    # Prueba de identidad del b-roll: compara zonas auténticas del MP4 con sus fuentes.
    observed=pixels(path,3.45,'scale=270:480');source=pixels('assets/broll/Trabajo_pantalla.mp4',.3+3.45-2.84)
    evidence['trabajo']={'render_s':3.45,'fuente_s':.91,'correlacion_rgb':correlate(observed,source)}
    # Excluir titular superior y barrido luminoso inferior: comparar solo la interfaz.
    observed=np.array(pixels(path,1.20,'crop=1080:1152:0:0,scale=360:384'))[80:280,15:330]
    source=np.array(pixels('assets/broll/Claude_lectura_web.mp4',4.78,'scale=2432:1368,crop=1080:1152:620:130,scale=360:384'))[80:280,15:330]
    evidence['claude']={'render_s':1.2,'fuente_s':4.78,'correlacion_rgb':correlate(observed,source),'recorte':'x>=489 del original; rostro ajeno excluido'}
    def pcm(file):
        return np.frombuffer(subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-i',str(w.inside(file)),'-t','10','-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-']),dtype=np.float32)
    original=pcm(p['original']['archivo']);mixed=pcm(path);length=min(len(original),len(mixed));voice=correlate(original[:length],mixed[:length])
    times=[.30,.95,1.55,2.40,3.45,4.50,4.95,5.50,6.00,6.85,7.50,8.50,8.98,9.55]
    sheet=Image.new('RGB',(7*270,2*514),INK:='#191b1e');draw=ImageDraw.Draw(sheet)
    for i,t in enumerate(times):
        x=i%7*270;y=i//7*514;sheet.paste(pixels(path,t),(x,y));draw.text((x+8,y+486),f'{t:.2f}s · MP4',fill='white')
    sheet.save(w.inside(folder+'/prueba_v4_fotogramas.jpg'),quality=95)
    # Cada tira contiene fotogramas contiguos a 30 FPS, tomados del MP4 definitivo de prueba.
    contacts=[]
    for k,start in enumerate([.56,1.74,2.70,3.92,4.62,5.14,5.74,6.22,7.74,8.02,8.58,8.74]):
        first=round(start*30);strip=Image.new('RGB',(8*180,3*346),INK);draw=ImageDraw.Draw(strip)
        for j in range(24):
            i=first+j
            if i>=len(frames):break
            x=j%8*180;y=j//8*346;strip.paste(Image.fromarray(frames[i]),(x,y));draw.text((x+4,y+324),f'f{i} · {i/30:.3f}s',fill='white')
        f=f'.estado/tmp/v4_continuidad_{k:02d}.jpg';strip.save(w.inside(f),quality=95);contacts.append(f)
    checks={'1080x1920':(v['width'],v['height'])==(1080,1920),'30fps':v['r_frame_rate']=='30/1','h264':v['codec_name']=='h264','aac':a['codec_name']=='aac','duracion_10s':abs(float(probe['format']['duration'])-10)<.05,'300_frames':len(frames)==300,'sin_alternancias':not temporal['alternancias_sospechosas'],'sin_franja_gris_en_fondos_claros':not bad,'broll_trabajo_identificado':evidence['trabajo']['correlacion_rgb']>.9,'broll_claude_identificado':evidence['claude']['correlacion_rgb']>.85,'voz_original_alineada':voice>.92}
    result={'estado':'verificacion_tecnica_superada_pendiente_revision_usuario' if all(checks.values()) else 'requiere_correccion','archivo':path,'sha256':w.digest(path),'edicion_sha256':w.edit_digest(p),'comprobaciones':checks,'bordes':{'frames_fondo_claro_revisados':105,'fallos':bad,'regla':'Comprobar el color esperado, también detecta franjas grises que el detector negro no detecta'},'brolls':evidence,'audio':{'correlacion_voz_original_mezcla':voice,'pico_pcm':float(np.max(np.abs(mixed))),'limite':'Comparación de señal y temporización; revisión perceptual final a cargo del usuario'},'fotogramas_consecutivos':contacts,'frames_analisis_temporal':300,'presencia_prevista':p['decisiones'],'fuentes':w.read_json('sistema/perfil.json')['archivos_tipografia'],'criterio_editorial':'Revisar visualmente las tiras, las capturas nativas y el segmento antes de registrar observaciones. Las métricas no aprueban sofisticación o narrativa.'}
    w.write_json(folder+'/auditoria_muestra.json',result)
    print(json.dumps({k:result[k] for k in ['estado','comprobaciones','brolls','audio']},ensure_ascii=False,indent=2))
    if not all(checks.values()):raise ValueError('No entregar la prueba hasta corregir las comprobaciones fallidas')
    return result

if __name__=='__main__':run(sys.argv[1])
