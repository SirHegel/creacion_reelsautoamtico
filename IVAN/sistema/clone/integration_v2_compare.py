"""Comparación de exports reales y fotogramas de referencia, sin aprobar estética."""
import argparse,json,math,pathlib,subprocess,sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import engine as e
from integration import folders
from PIL import Image,ImageDraw

def run(raw_id):
    _,folder=folders(raw_id);p=e.load(folder/'proyecto.json')
    v2=folder/p['output_name'];v1=folder/p['previous_version']['output_name']
    if e.digest(v1)!=p['previous_version']['sha256']:raise ValueError('V1 alterada')
    qc=e.load(folder/'integration_qc.json');source=e.source_fingerprint(folder)['sha256']
    if qc['final_mp4_sha256']!=e.digest(v2) or qc['source_sha256']!=source:raise ValueError('Render obsoleto')
    out=folder/'evidencia_qa/visual_v2';out.mkdir(parents=True,exist_ok=True)
    # Misma cronología a30FPS. La pista AAC de V2 se copia sin mezcla ni recodificación.
    target=folder/'comparacion_integracion_v1_v2.mp4';partial=target.with_suffix('.part.mp4')
    filters="[0:v]scale=540:960,setsar=1[a];[1:v]scale=540:960,setsar=1[b];[a][b]hstack=2,pad=1080:1080:0:100:color=0x171719,drawtext=fontfile=recursos/Sequel_Sans_Bold_Disp.ttf:text='V1':fontcolor=white:fontsize=44:x=235:y=25,drawtext=fontfile=recursos/Sequel_Sans_Bold_Disp.ttf:text='V2':fontcolor=white:fontsize=44:x=775:y=25[v]"
    subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-i',str(v1),'-i',str(v2),'-filter_complex',filters,'-map','[v]','-map','1:a:0','-c:v','h264_nvenc','-preset','p5','-cq','18','-b:v','0','-pix_fmt','yuv420p','-c:a','copy','-frames:v',str(p['frames']),'-movflags','+faststart','-y',str(partial)],check=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(partial)],text=True))
    video=next(s for s in probe['streams']if s['codec_type']=='video')
    if int(video['nb_read_frames'])!=p['frames']:raise ValueError('Comparación desalineada')
    partial.replace(target)
    # Cada fotograma del MP4 final se decodifica con fallo duro ante corrupción.
    small=e.ROOT/'.estado/tmp/v2/visual_final_frames';small.mkdir(parents=True,exist_ok=True)
    for file in small.glob('f_*.png'):file.unlink()
    subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-err_detect','explode','-i',str(v2),'-map','0:v:0','-fps_mode','passthrough','-vf','scale=180:320','-start_number','0','-y',str(small/'f_%04d.png')],check=True)
    frames=sorted(small.glob('f_*.png'))
    if len(frames)!=p['frames']:raise ValueError('Decodificación incompleta')
    # Cuatro hojas legibles y ordenadas contienen los237frames, sin muestreo.
    sheets=[]
    for page,start in enumerate(range(0,len(frames),60)):
        subset=frames[start:start+60];sheet=Image.new('RGB',(6*180,math.ceil(len(subset)/6)*344),(20,20,22));d=ImageDraw.Draw(sheet)
        for j,path in enumerate(subset):
            with Image.open(path)as im:sheet.paste(im,(j%6*180,j//6*344+24))
            n=start+j;d.text((j%6*180+5,j//6*344+5),f'F{n:03d} {n/30:.3f}s',fill='white')
        path=out/f'consecutivos_{page+1}.jpg';sheet.save(path,quality=95);sheets.append(str(path.relative_to(e.ROOT)))
    def frame(src,t,path):
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-ss',str(t),'-i',str(src),'-frames:v','1','-y',str(path)],check=True)
    def pair(a,b,label_a,label_b,path):
        result=Image.new('RGB',(1080,1016),(20,20,22));d=ImageDraw.Draw(result)
        d.text((20,12),label_a,fill='white');d.text((560,12),label_b,fill='white')
        for n,src in enumerate((a,b)):
            with Image.open(src)as im:result.paste(im.resize((540,960),Image.Resampling.LANCZOS),(n*540,56))
        result.save(path,quality=96)
    captures=[]
    for t in (.55,.8,1.4,2.6,3.35,4.5,6.4,7.55):
        name=str(t).replace('.','_');a=out/f'v1_{name}.png';b=out/f'v2_{name}.png'
        frame(v1,t,a);frame(v2,t,b);pair(a,b,f'V1 · {t:.2f}s',f'V2 · {t:.2f}s',out/f'v1_v2_{name}.jpg');captures.append(str(b.relative_to(e.ROOT)))
    # Referencias auténticas, identificadas por tiempo; adaptación, no identidad de guion.
    refs=[]
    for key,source_path,at,ours,why in [('YO_hook','recursos/A3_YO.mp4',1.05,.8,'Frase acumulada y palabra de conflicto roja'),('YO_split','recursos/A3_YO.mp4',.8,1.4,'Ancho completo y fondo original; V2 aplica55/45 por directiva'),('CLONE_radial','recursos/B2_CLONE.mp4',22.4,4.5,'Personaje pixelado, marcas/fuentes y transferencia hacia objetivo')]:
        original=out/(key+'_original.png');new=out/(key+'_v2.png');frame(e.ROOT/source_path,at,original);frame(v2,ours,new)
        comp=out/(key+'_comparacion.jpg');pair(original,new,f'{key} referencia · {at:.2f}s',f'V2 · {ours:.2f}s',comp)
        refs.append({'source':source_path,'source_sha256':e.digest(e.ROOT/source_path),'reference_time':at,'v2_time':ours,'comparison':str(comp.relative_to(e.ROOT)),'purpose':why})
    record={'generated':e.w.utc(),'mp4_sha256':e.digest(v2),'composition_sha256':source,'comparison_mp4':str(target.relative_to(e.ROOT)),'comparison_sha256':e.digest(target),'frames':len(frames),'consecutive_sheets':sheets,'captures':captures,'references':refs,'aesthetic_approval':False}
    e.write(out/'evidencia.json',record);return record

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('raw_id');args=ap.parse_args();r=run(args.raw_id)
    print(json.dumps({k:r[k]for k in ('mp4_sha256','composition_sha256','comparison_mp4','frames','consecutive_sheets')},indent=2))
