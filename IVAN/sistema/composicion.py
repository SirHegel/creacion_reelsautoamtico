"""Lienzo seguro V4; el movimiento específico vive en el storyboard editable."""
import sys
sys.dont_write_bytecode=True
import workflow as w

def construir(ID):
    from preflight import require_ready
    require_ready()
    if ID!='demo_montaje_v4':
        raise ValueError('Este storyboard corresponde a Agent Reach. Para otro reel, diseñar su lienzo con los componentes de sistema/motion.js y selección propia; no copiar su guion ni encuadres')
    p=w.read_json('proyectos/'+ID+'/proyecto.json')
    w.require_current_instructions(p);w.require_resource_selection(p,hasta=10)
    folder='proyectos/'+ID
    media=''
    for b in p['broll']:
        media+=f'<div id="{b["id"]}Clip" class="filmClip"><div id="{b["id"]}Plane" class="filmPlane"><video id="{b["id"]}Video" class="filmSource" src="/{b["archivo"]}" muted playsinline preload="auto" data-start="{b["inicio"]}" data-duration="{b["fin"]-b["inicio"]}" data-media-start="{b["offset"]}"></video></div></div>'
    actor=''
    for i,a in enumerate(p.get('presentador',[])):
        suffix=str(i) if i else ''
        actor+=f'<div id="actor{suffix}" class="actor"><div id="actorPlane{suffix}" class="actorPlane"><video id="actorVideo{suffix}" class="actorVideo" src="/{p["original"]["archivo"]}" muted playsinline preload="auto" data-start="{a["inicio"]}" data-duration="{a["fin"]-a["inicio"]}" data-media-start="{a["inicio"]}"></video></div></div>'
    burn='<video id="burn" src="/recursos/Burn_01.mp4" muted playsinline preload="auto" data-start="2.65" data-duration="0.55" data-media-start="0.2"></video>'
    css='''@font-face{font-family:Sequel;src:url('/recursos/Sequel_Sans_Bold_Disp.ttf')}@font-face{font-family:Scholar;src:url('/recursos/Scholar_Italic.ttf')}*{box-sizing:border-box}html,body{margin:0;padding:0;width:1080px;height:1920px;overflow:hidden;background:#191b1e}#root{position:absolute;inset:0;width:1080px;height:1920px;overflow:hidden;background:#191b1e;color:#f4f1e9;font-family:Sequel;isolation:isolate}#stage{position:absolute;inset:0;perspective:1800px}.filmClip{position:absolute;overflow:hidden;left:0;top:0;width:1080px;height:1152px;z-index:10;background:#232321}.filmPlane{position:absolute;left:-620px;top:-130px;width:2432px;height:1368px;transform-origin:50% 50%}.filmSource{display:block;width:100%;height:100%;object-fit:fill}#workClip{height:1920px}#workPlane{left:0;top:0;width:1080px;height:1920px}#webFinalClip{top:580px;height:1050px}#webFinalPlane{top:-90px}#actor{position:absolute;inset:0;z-index:40;overflow:hidden}#actorPlane{position:absolute;inset:0;transform-origin:0 0;width:1080px;height:1920px}#actorVideo{display:block;width:1080px;height:1920px}#burn{position:absolute;inset:0;width:1080px;height:1920px;object-fit:cover;mix-blend-mode:screen;z-index:75}'''
    css+='html,body{overflow:clip;overscroll-behavior:none}#root{position:fixed;left:0;top:0;contain:layout paint size}.actor{position:absolute;inset:0;z-index:40;overflow:hidden}.actorPlane{position:absolute;inset:0;transform-origin:0 0;width:1080px;height:1920px}.actorVideo{display:block;width:1080px;height:1920px}'
    html=f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=1080,height=1920,initial-scale=1"><title>ASCENDIA V4 — prueba 10 s</title><script src="/recursos/gsap.min.js"></script><style>{css}</style></head><body><div id="root" data-project="{folder}" data-composition-id="ivan" data-start="0" data-duration="10" data-width="1080" data-height="1920" data-fps="30"><div id="stage"></div>{media}{actor}{burn}</div><script src="/sistema/motion.js"></script><script src="/{folder}/motion.js"></script></body></html>'
    w.inside(folder+'/index.html').write_text(html)
    print('Lienzo de prueba construido. No genera ni aprueba el completo.')

if __name__=='__main__':construir(sys.argv[1])
