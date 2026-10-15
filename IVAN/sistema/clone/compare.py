"""Compara renders reales con CLONE en fases equivalentes, sin métricas HTML↔MP4."""
import json,pathlib,subprocess,sys
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
import engine as e

def frame(file,time):
    data=subprocess.check_output(['/usr/bin/ffmpeg','-v','error','-ss',str(time),'-i',str(file),'-frames:v','1','-vf','scale=270:480','-f','image2pipe','-c:v','png','-'])
    import io
    return Image.open(io.BytesIO(data)).convert('RGB')

def compare(folder):
    path=e.w.inside(folder);spec=e.load(path/'scene.json');qc=e.load(path/'qc.json',{})
    if not qc.get('decoded_all_frames'):return None
    scene=spec['scenes'][0];definition=next(d for d in e.catalog()if d['id']==scene['family']);reference=definition['reference'][0]
    source=e.w.inside(reference['source']);start,end=reference['entry_s'],reference['exit_s']
    phases=[.2,.45,.7,.94];sheet=Image.new('RGB',(560,4*515),(244,244,245));draw=ImageDraw.Draw(sheet);pairs=[]
    for i,phase in enumerate(phases):
        source_t=start+phase*(end-start);render_t=phase*scene['duration'];row=i*515
        for col,(file,t,label)in enumerate([(source,source_t,'CLONE'),(path/'preview.mp4',render_t,'Biblioteca')]):
            sheet.paste(frame(file,t),(col*280,row+29));draw.text((col*280+8,row+8),f'{label} {t:.3f}s',fill=(24,24,28))
        pairs.append({'phase':phase,'source_t':source_t,'render_t':render_t})
    sheet.save(path/'comparison.png')
    record={'source':str(source.relative_to(e.ROOT)),'source_sha256':e.digest(source),'render':str((path/'preview.mp4').relative_to(e.ROOT)),'render_sha256':qc['mp4_sha256'],'pairs':pairs,
      'scope':'Estados de referencia frente a render real. Familias de split adaptadas a fullmotion; no equivalencia píxel a píxel ni reutilización del presentador ajeno.',
      'fidelity':'Requiere revisión visual separada; esta captura no promueve el componente por sí sola.'}
    e.write(path/'comparison.json',record);return record

if __name__=='__main__':
    folders=sys.argv[1:]or[str(p.parent.relative_to(e.ROOT))for p in sorted((e.ROOT/'proyectos/clone_motor/previews').glob('*/scene.json'))]
    for folder in folders:
        try:print(folder,bool(compare(folder)),flush=True)
        except Exception as error:print(folder,'PENDIENTE',str(error),flush=True)
