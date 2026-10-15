"""Comparación de lenguaje visual con fotogramas reales de CLONE por familia.

Los tiempos son fases normalizadas orientativas, no una medición de fidelidad
del movimiento ni una correlación render↔código.
"""
import argparse,json,sys,pathlib
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw
import engine as e,compare

def build(folder):
    out=e.w.inside(folder);spec=e.load(out/'scene.json');qc=e.load(out/'qc.json',{})
    if not qc.get('decoded_all_frames') or qc.get('mp4_sha256')!=e.digest(out/'preview.mp4'):raise ValueError('Render no comprobado o desactualizado')
    definitions={d['id']:d for d in e.catalog()};pairs=[]
    for scene in spec['scenes']:
        reference=definitions[scene['family']].get('reference',[])
        if not reference:continue
        ref=reference[0]
        for phase in (.45,.80):
            pairs.append({'scene':scene['id'],'family':scene['family'],'phase':phase,
                          'source_s':round(ref['entry_s']+(ref['exit_s']-ref['entry_s'])*phase,6),
                          'render_s':round(scene['start']+scene['duration']*phase,6),
                          'source_interval':[ref['entry_s'],ref['exit_s']]})
    sheet=Image.new('RGB',(560,len(pairs)*520),(242,242,244));draw=ImageDraw.Draw(sheet)
    source=e.w.inside('recursos/B2_CLONE.mp4')
    for i,pair in enumerate(pairs):
        row=i*520
        draw.text((8,row+5),pair['family']+' - fase '+str(pair['phase']),fill='#171719')
        for col,file,time,title in [(0,source,pair['source_s'],'CLONE'),(1,out/'preview.mp4',pair['render_s'],'Nuevo concepto')]:
            draw.text((col*280+8,row+22),f'{title} {time:.2f}s',fill='#171719')
            sheet.paste(compare.frame(file,time),(col*280,row+40))
    sheet.save(out/'comparacion_clone.png')
    result={'source':'recursos/B2_CLONE.mp4','source_sha256':e.digest(source),'mp4_sha256':qc['mp4_sha256'],
            'source_fingerprint':e.source_fingerprint(out)['sha256'],'pairs':pairs,
            'alignment':'Fases normalizadas por familia; no tracking ni equivalencia temporal exacta.',
            'scope':'Comparar jerarquía, recursos, paleta, profundidad y mecanismo. Texto/concepto nuevos; no reconstrucción literal de CLONE.',
            'aesthetic_approval':'pending_user_review'}
    e.write(out/'comparacion_clone.json',result)
    plan=['# '+spec.get('title',spec.get('id','Demostración')),'',
          'Guion de prueba conceptual, sin voz ni ejecución real. Decisiones producidas por inferencia semántica; aprobación estética pendiente.','',
          '| Tiempo | Familia | Contenido y objetivo | Razón visual |','|---|---|---|---|']
    for s in spec['scenes']:
        clean=lambda value:str(value).replace('|','/').replace('\n',' ')
        plan.append(f'| {s["start"]:.2f}–{s["start"]+s["duration"]:.2f}s | {s["family"]} | {clean(s["content"])} / {clean(s["objective"])} | {clean(s.get("visual_reason",s.get("semantic_reason","")))} |')
    plan+=['','Las acciones de las familias existentes describen las fases de su timeline. Solo `composition_graph.params.steps` admite acciones ejecutables arbitrarias.','']
    for s in spec['scenes']:
        plan+=['## '+s['id'],'','- Entrada: '+json.dumps(s['transition_in'],ensure_ascii=False),'- Salida: '+json.dumps(s['transition_out'],ensure_ascii=False),'- Justificación semántica: '+s.get('semantic_reason','')]
        alternatives=s.get('alternatives',s.get('alternatives_rejected',[]))
        if alternatives:plan+=['- Alternativas consideradas: '+json.dumps(alternatives,ensure_ascii=False)]
        plan+=['- Acciones y estados: '+json.dumps(s.get('actions',[]),ensure_ascii=False),'- Adaptación editorial: '+json.dumps(s.get('presentation'),ensure_ascii=False),'']
    (out/'PLAN_ESCENAS.md').write_text('\n'.join(plan))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folders',nargs='+');args=p.parse_args()
    for folder in args.folders:print(folder,len(build(folder)['pairs']),flush=True)
