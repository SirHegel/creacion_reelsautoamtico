"""Revisión editorial B_V2: reutiliza B_V1, sin nueva inferencia ni nuevas demos."""
import argparse, json, subprocess, sys
sys.dont_write_bytecode = True
import engine as e
import generate
import creative_compare

FOLDER = e.ROOT / 'proyectos/clone_motor/creatividad/comparacion'
V1_SHA = '918513396c7025c7b9d53eb80da9db9db2baaf442b36f9d60c0ec8d7dd28bcf8'

def revision():
    base = e.load(FOLDER / 'B_V1.scene.json')
    spec = e.load(FOLDER / 'scene.json')
    if e.digest(FOLDER / 'B_V1.mp4') != V1_SHA:
        raise ValueError('B_V1 cambió')
    if spec.get('semantic_analysis') != base.get('semantic_analysis') or spec.get('timing') != base.get('timing') or len(spec['scenes']) != len(base['scenes']):
        raise ValueError('B_V2 debe conservar significado, tiempos y dos escenas')
    editable = {'layout', 'closing', 'continuity', 'transition_in', 'transition_out'}
    for before, after in zip(base['scenes'], spec['scenes']):
        if {k:v for k,v in before.items() if k not in editable} != {k:v for k,v in after.items() if k not in editable}:
            raise ValueError('No cambiar familias, parámetros, texto o cifras al aplicar esta revisión')
    return e.validate_spec(spec)

def render():
    spec = revision()
    receipt = e.load(FOLDER / 'generation.json')
    receipt.update(version='B_V2', semantic_inference_repeated=False, manual=e.w.manual(), editorial_revision=spec['editorial_revision'])
    return generate.produce(FOLDER, spec, receipt)

def compare():
    revision()
    q = e.load(FOLDER / 'qc.json')
    if q['mp4_sha256'] != e.digest(FOLDER / 'preview.mp4') or not q.get('decoded_all_frames'):
        raise ValueError('B_V2 no tiene un render actual')
    output = FOLDER / 'B_V1_vs_B_V2.mp4'
    temporary = FOLDER / 'B_V1_vs_B_V2.part.mp4'
    # Titulares comparativos sobre el vídeo: no afectan la composición entregada.
    filters = "[0:v]drawbox=x=0:y=0:w=iw:h=66:color=black:t=fill,drawtext=fontfile=recursos/Sequel_Sans_Bold_Disp.ttf:text=B_V1:fontcolor=white:fontsize=38:x=24:y=12[l];[1:v]drawbox=x=0:y=0:w=iw:h=66:color=black:t=fill,drawtext=fontfile=recursos/Sequel_Sans_Bold_Disp.ttf:text=B_V2:fontcolor=white:fontsize=38:x=24:y=12[r];[l][r]hstack=inputs=2[v]"
    subprocess.run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(FOLDER/'B_V1.mp4'),'-i',str(FOLDER/'preview.mp4'),'-filter_complex',filters,'-map','[v]','-an','-c:v','h264_nvenc','-preset','p6','-cq','19','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(temporary)],cwd=e.ROOT,check=True)
    subprocess.run(['/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-xerror','-i',str(temporary),'-f','null','-'],cwd=e.ROOT,check=True)
    temporary.replace(output)
    creative_compare.build(FOLDER)
    result = {'source_v1_sha256': V1_SHA, 'source_v2_sha256': q['mp4_sha256'],
              'comparison_sha256': e.digest(output), 'duration':9, 'alignment':'Mismo tiempo del guion en ambos MP4; título comparativo externo.', 'aesthetic_approval':False}
    e.write(FOLDER / 'B_V1_vs_B_V2.json',result)
    return result

def report():
    revision()
    q=e.load(FOLDER/'qc.json');clock=e.load(FOLDER/'timeline_qc.json');qa=e.load(FOLDER/'bv2_compositor_qc.json',{});visual=e.load(FOLDER/'visual_review.json',{});comparison=e.load(FOLDER/'B_V1_vs_B_V2.json')
    fingerprint=e.source_fingerprint(FOLDER)['sha256']
    if q.get('mp4_sha256') != e.digest(FOLDER/'preview.mp4') or q.get('source_sha256') != fingerprint or not q.get('decoded_all_frames') or not clock.get('ok') or clock.get('source_sha256') != fingerprint:
        raise ValueError('Render o timeline desactualizados')
    if visual.get('mp4_sha256') != q['mp4_sha256'] or visual.get('composition_sha256') != fingerprint:
        raise ValueError('Falta revisión visual actual')
    if comparison['source_v2_sha256'] != q['mp4_sha256'] or comparison['comparison_sha256'] != e.digest(FOLDER/'B_V1_vs_B_V2.mp4'):
        raise ValueError('Comparación desactualizada')
    if qa.get('status') != 'PASS_CPU_B_V2' or not all(qa.get('checks', {}).values()):
        raise ValueError('Pruebas de reutilización del compositor pendientes')
    source_after=qa.get('source_after',{})
    if isinstance(source_after,dict) and source_after.get('sha256') and source_after['sha256'] != fingerprint:
        raise ValueError('QA de reutilización obsoleta')
    for filename,digest in qa.get('compositor_after',{}).items():
        if e.digest(e.HERE/filename) != digest:
            raise ValueError('Código de compositor cambió después del QA: '+filename)
    result={'version':'B_V2','generated':e.w.utc(),'mp4_sha256':q['mp4_sha256'],'composition_sha256':fingerprint,
            'families':['spotlight_agent','feedback_bars'],'frames':270,'duration':9,'resolution':[1080,1920],
            'structure_and_values_preserved':True,'comparison':comparison,'qa':{'file':'bv2_compositor_qc.json','sha256':e.digest(FOLDER/'bv2_compositor_qc.json'),'pass':True},
            'aesthetic_status':'pending_user_review','new_demos_generated':0,'limits':visual.get('observations',{}).get('pending',[])}
    e.write(FOLDER/'B_V2_INFORME.json',result)
    page='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>B_V2 · comparación</title><style>body{background:#f3f3f5;color:#19191b;font:16px system-ui;max-width:1150px;margin:32px auto;padding:20px}main{display:grid;grid-template-columns:1fr 1fr;gap:24px}video{width:100%;max-height:750px;background:#000}h1{font-size:32px}a{color:#74412e}@media(max-width:600px){main{grid-template-columns:1fr}}</style><h1>B_V2 · misma estructura, composición conectada</h1><p>Dos familias conservadas; layout compacto, personaje compartido y conclusión de cobertura. Prueba muda con datos ficticios declarados. Aprobación estética pendiente.</p><main><article><h2>B_V1</h2><video controls loop src="B_V1.mp4"></video></article><article><h2>B_V2</h2><video controls loop src="preview.mp4"></video></article></main><p><a href="B_V1_vs_B_V2.mp4">Comparación sincronizada</a> · <a href="B_V2_INFORME.md">Informe</a> · <a href="scene.json">Plan editable</a> · <a href="index.html">Composición editable</a> · <a href="bv2_compositor_qc.json">QA de reutilización</a></p></html>'''
    (FOLDER/'B_V2.html').write_text(page)
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['render','compare','report']);args=parser.parse_args()
    result=globals()[args.stage]()
    print(json.dumps(result,ensure_ascii=False,indent=2))
