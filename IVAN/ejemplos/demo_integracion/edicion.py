"""Montaje V5 nuevo: identidad YO y secuencia contextual; solo prueba de 10 s."""
import sys, json
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sistema'))
import workflow as w
from preflight import require_ready
ID=Path(__file__).parent.name
FOLDER='proyectos/'+ID

def preparar():
    require_ready()
    p=w.read_json(FOLDER+'/proyecto.json');w.require_current_instructions(p)
    report=w.read_json(FOLDER+'/auditoria_recursos.json')
    # Alias local: la fuente histórica sigue intacta, sin segunda copia binaria.
    alias=w.ROOT/'assets/broll/Claude_agent_view.mp4'
    if not alias.exists(): alias.symlink_to('../../recursos/Claude_agent_view.mp4')
    p.update(etapa='produccion_prueba_v5',muestra_nombre='ascendia_test_v5_10s.mp4',
       motor={'nombre':'HyperFrames','composicion':FOLDER+'/index.html','fuente':FOLDER+'/motion.js','alcance_hasta_s':10,'captura_cpu':False},
       presentador=[{'inicio':0,'fin':1.30,'modo':'split','split_proporcion_superior':.55,'barbilla_destino_px':1610,'escala_split':1.15},
                    {'inicio':182/30,'fin':200/30,'modo':'split','split_proporcion_superior':.55,'barbilla_destino_px':1590,'escala_split':1.15}],
       subtitulos=[{'inicio':6.08,'fin':6.56,'texto':'a partir'},{'inicio':6.56,'fin':6.68,'texto':'de datos'}],
       broll=[{'id':'google','archivo':'assets/broll/Google_workspace.mp4','inicio':0,'fin':1.20,'offset':1.20},
              {'id':'claude','archivo':'assets/broll/Claude_agent_view.mp4','inicio':1.20,'fin':2.40,'offset':2.50},
              {'id':'fetch','archivo':'assets/broll/Claude_lectura_web.mp4','inicio':2.40,'fin':86/30,'offset':0}],
       burns=[{'inicio':79/30,'fin':3.2,'archivo':'recursos/Burn_01.mp4','offset':.2}],
       audio={'voz':{'procesamiento':'original_sin_procesar'},
              'musica':{'archivo':'recursos/Lovibe_A_Good_Man.mp3','entrada_archivo':12,'ganancia_db':-27,'derechos':'Biblioteca autorizada del cliente; no se afirma licencia independiente'},
              'efectos':[{'archivo':'recursos/Riser_1.wav','inicio':1.10,'ganancia_db':-20},
                         {'archivo':'recursos/Woosh_Effect_1.wav','inicio':3.60,'ganancia_db':-27},
                         {'archivo':'recursos/Woosh_Effect_1.wav','inicio':5.56,'ganancia_db':-27},
                         {'archivo':'recursos/SONIDO_UTIL.mp3','inicio':7.38,'ganancia_db':-28}]},
       cierre_visual={'inicio':7.918005,'fin':10,'voz_adicional':False,'motivo':'Fuente breve: terminar transformación sin alterar narración'},
       escenas=[{'id':'hook','inicio':0,'fin':1.20,'frase':'Herramienta de ejemplo','objetivo':'Provocación con identidad humana y marca auténtica','composicion':'split_55_45','estado':'pendiente'},
                {'id':'claude','inicio':1.20,'fin':2.40,'frase':'un asistente procesa una solicitud','objetivo':'Identificar Claude ejecutando tareas, sin atribuir scraping a esta demo','composicion':'demo_real_expandida','estado':'pendiente'},
                {'id':'fetch','inicio':2.40,'fin':86/30,'frase':'procesa','objetivo':'Mostrar lectura web auténtica de Calendly y extraer visualmente un fragmento','composicion':'demo_web_transformada','estado':'pendiente'},
                {'id':'web','inicio':86/30,'fin':4.10,'frase':'diversas fuentes de ejemplo','objetivo':'Transformar superficie de información en estructura de fuentes','composicion':'globo_2_5d','estado':'pendiente'},
                {'id':'fuentes','inicio':4.10,'fin':5.84,'frase':'Fuente A, Fuente B, Fuente C','objetivo':'Fuentes distintas entregan contenido que converge, representación conceptual','composicion':'fuentes_extraidas','estado':'pendiente'},
                {'id':'api','inicio':5.84,'fin':7.918005,'frase':'y entrega un resultado de ejemplo','objetivo':'Ruta alternativa al obstáculo de coste, sin cifras ni pruebas inventadas','composicion':'flujo_con_bypass_y_split','estado':'pendiente'},
                {'id':'cierre','inicio':7.918005,'fin':10,'frase':'Resolución visual de la frase original; sin narración añadida','objetivo':'Terminar ensamblaje y movimiento','composicion':'documento_editorial','estado':'pendiente'}],
       motion_graphics=['titular_construido_como_YO','viewport_expandido','extraccion_de_fragmentos','globo_de_fuentes_2_5D','mascaras_de_lectura','trayectorias_de_informacion','fuentes_que_reaccionan','bypass_API','morphing_de_superficie','camara_virtual_continua'])
    allpaths=[b['archivo'] for b in p['broll']]+['recursos/Burn_01.mp4','recursos/Lovibe_A_Good_Man.mp3','recursos/Riser_1.wav','recursos/Woosh_Effect_1.wav','recursos/SONIDO_UTIL.mp3']
    p['recursos']=[{'archivo':f,'sha256':w.digest(f)} for f in allpaths]
    evidence={c['archivo']:c for c in report['candidatos'] if c.get('archivo')}
    agent={'drive_id':'CONFIGURE_RECURSO_0637','archivo':p['broll'][1]['archivo'],'sha256':w.digest(p['broll'][1]['archivo']),
           'contenido_observado':'Comando en Claude Code, ejecución y expansión de ventanas de agentes. No demuestra scraping de plataformas.',
           'evidencias':['assets/broll/Claude_agents_action_v5_secuencia.jpg']}
    evidence[agent['archivo']]=agent
    sel={'proyecto_id':ID,'estado':'revisada_para_prueba','alcance_hasta_s':10,'manual':w.manual(),'inventario_sha256':w.digest('recursos/inventario_drive.json'),
         'bibliotecas_consultadas':['CONFIGURE_RECURSO_1792','CONFIGURE_RECURSO_1351'],'bloques':[]}
    for s in p['escenas']:
        clip=next((b for b in p['broll'] if b['id']==('google' if s['id']=='hook' else s['id'])),None)
        candidates=[]
        if clip:
            c=evidence[clip['archivo']];candidates=[{'drive_id':c['drive_id'],'motivo_contextual':s['objetivo'],'archivo':clip['archivo'],'sha256':w.digest(clip['archivo']),
                 'analisis_visual':{'estado':'revisado','contenido_observado':c['contenido_observado'],'evidencias':c['evidencias']}}]
            decision={'tipo':'broll','drive_id':c['drive_id'],'tramo_s':[clip['offset'],clip['offset']+clip['fin']-clip['inicio']],'motivo_contextual':s['objetivo']}
        else:
            decision={'tipo':'motion','motivo_contextual':s['objetivo'],
              'resultado_busqueda':'Ambas bibliotecas y candidatos de Google/Claude revisados. No se encontró ejecución auténtica de scraping de las tres plataformas. La secuencia conceptual muestra extracción, reacción, ruta y ensamblaje; no impone b-roll genérico ni datos ficticios.'}
        sel['bloques'].append({'escena_id':s['id'],'inicio':s['inicio'],'fin':s['fin'],'narracion':s['frase'],'intencion':s['objetivo'],
           'carpetas_consultadas':['CONFIGURE_RECURSO_0334','CONFIGURE_RECURSO_1090','CONFIGURE_RECURSO_1497','CONFIGURE_RECURSO_0704'],
           'candidatos':candidates,'decision':decision})
    w.write_json(FOLDER+'/seleccion_recursos.json',sel);w.write_json(FOLDER+'/proyecto.json',p)
    w.require_resource_selection(p,hasta=10)
    media=''
    for b in p['broll']:
        media+=f'<div id="{b["id"]}Clip" class="film"><div id="{b["id"]}Plane" class="plane"><video id="{b["id"]}Video" src="/{b["archivo"]}" muted playsinline preload="auto" data-start="{b["inicio"]}" data-duration="{round(b["fin"]-b["inicio"],9)}" data-media-start="{b["offset"]}"></video></div></div>'
    actors=''
    for i,a in enumerate(p['presentador']):
        suffix=str(i) if i else ''
        actors+=f'<div id="actor{suffix}" class="actor"><div id="actorPlane{suffix}" class="actorPlane"><video id="actorVideo{suffix}" src="/{p["original"]["archivo"]}" muted playsinline preload="auto" data-start="{a["inicio"]}" data-duration="{round(a["fin"]-a["inicio"],9)}" data-media-start="{a["inicio"]}"></video></div></div>'
    css="""@font-face{font-family:Sequel;src:url('/recursos/Sequel_Sans_Bold_Disp.ttf')}@font-face{font-family:Scholar;src:url('/recursos/Scholar_Italic.ttf')}*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1920px;overflow:clip;overscroll-behavior:none;background:#0d121b}#root{position:fixed;left:0;top:0;width:1080px;height:1920px;contain:layout paint size;overflow:hidden;isolation:isolate;color:white;font-family:Sequel;background:#0d121b}#stage{position:absolute;inset:0;perspective:1600px}.film{position:absolute;left:0;top:0;width:1080px;height:1056px;overflow:hidden;z-index:10}.plane{position:absolute;transform-origin:center center}.plane video{display:block;width:100%;height:100%}#googlePlane{width:1080px;height:1920px;left:0;top:-400px}#claudePlane{width:1877px;height:1056px;left:-398px;top:0}#fetchClip{height:1920px;background:#20221f}#fetchPlane{width:2560px;height:1440px;left:-690px;top:300px}.actor{position:absolute;inset:0;z-index:40;overflow:hidden}.actorPlane{position:absolute;inset:0;width:1080px;height:1920px;transform-origin:0 0}.actor video{display:block;width:1080px;height:1920px}#burn{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;mix-blend-mode:screen;z-index:75}.kinetic{font-family:Sequel;text-shadow:2px 4px 5px rgba(0,0,0,.85)}"""
    css+='#stage{z-index:50;transform-style:flat}.actor{z-index:60}'
    html=f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>ASCENDIA V5 — YO / 10 s</title><script src="/recursos/gsap.min.js"></script><style>{css}</style></head><body><div id="root" data-project="{FOLDER}" data-composition-id="ivan" data-start="0" data-duration="10" data-width="1080" data-height="1920" data-fps="30"><div id="stage"></div>{media}{actors}<video id="burn" src="/recursos/Burn_01.mp4" muted playsinline preload="auto" data-start="{79/30}" data-duration="{round(3.2-79/30,9)}" data-media-start=".2"></video></div><script src="/sistema/motion.js"></script><script src="/sistema/componentes_motion.js"></script><script src="/{FOLDER}/motion.js"></script></body></html>'
    w.inside(FOLDER+'/index.html').write_text(html)
    print('Montaje V5 nuevo preparado; selección contextual validada, alcance solo 10 s')

if __name__=='__main__':preparar()
