"""Compilador y renderizador local de componentes CLONE. Sin instalaciones."""
import argparse,base64,concurrent.futures,hashlib,json,math,os,pathlib,re,shutil,subprocess,sys
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'sistema'))
import workflow as w
from skills import cli
from PIL import Image,ImageDraw
import composition

def write(path,data):w.write_json(path,data)
def load(path,default=None):return w.read_json(path,default)
def digest(path):return w.digest(path)
def data_url(path):
    p=w.inside(path);mime={'.svg':'image/svg+xml','.png':'image/png','.ttf':'font/ttf','.woff2':'font/woff2','.js':'text/javascript'}[p.suffix]
    return 'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()

def catalog():
    files=sorted((HERE/'components').glob('*.js'))
    script="const fs=require('fs'),vm=require('vm');const window={};const context={window,Map};vm.createContext(context);"
    script+=f"vm.runInContext(fs.readFileSync({json.dumps(str(HERE/'runtime.js'))},'utf8'),context);context.Clone=window.Clone;"
    for f in files:script+=f"vm.runInContext(fs.readFileSync({json.dumps(str(f))},'utf8'),context);"
    script+="console.log(JSON.stringify([...window.Clone.definitions].map(([id,d])=>({id,defaults:d.defaults||{},durationRange:d.durationRange||[1,15],description:d.description||'',reference:d.reference||[],parameters:d.parameters||{},source:d.source||''}))));"
    r=subprocess.run(['node','-e',script],cwd=ROOT,capture_output=True,text=True,check=True)
    result=json.loads(r.stdout)
    for item in result:
        source=item.get('source')
        if isinstance(source,dict) and not any('entry_s'in ref for ref in item['reference']):
            item['reference']=[{'source':source['path'],'entry_s':source['start'],'exit_s':source['end'],'evidence':item['reference']}]
    result.append({'id':'cancelled','defaults':{'final_price':214},'durationRange':[1.2,4.8],
      'description':'Suscripciones acumuladas, contador, barridos de cancelación, impacto y sello CANCELLED; diseño aprobado reutilizado.',
      'reference':[{'source':'recursos/B2_CLONE.mp4','entry_s':1.6,'exit_s':3.2}],
      'parameters':{'final_price':'número positivo<10000; dato de referencia o aportado'},'source':'ejemplos/clone_componente/timeline.gsap.js'})
    presentations=load(HERE/'presentation.json',{}).get('families',{})
    for item in result:
        item['presentation']=presentations.get(item['id'],{})
        item['continuity']=composition.capabilities(item['id'])
        item['layout']={'profiles':composition.LAYOUTS.get(item['id'],[]),'units':'pixels1080x1920','guides':'center_axis_and_flexible_thirds'}
    return result

def validate_spec(spec,allow_unknown=False):
    if spec.get('schema_version')!=1:raise ValueError('SceneIR versión1 requerida')
    scenes=spec.get('scenes',[])
    if not 1<=len(scenes)<=40:raise ValueError('1–40 escenas por composición')
    ids=set();end=0;defs={d['id']:d for d in catalog()}
    for scene in scenes:
        ident=scene.get('id','')
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,59}',ident) or ident in ids:raise ValueError('ID inválido/repetido')
        ids.add(ident);family=scene.get('family');definition=defs.get(family)
        if not definition and family!='cancelled':raise ValueError('Familia inexistente: '+str(family))
        dur=scene.get('duration');start=scene.get('start',end)
        if not isinstance(dur,(int,float)) or isinstance(dur,bool) or not math.isfinite(dur):raise ValueError('Duración finita requerida')
        lo,hi=definition['durationRange']if definition else(1.2,4.8)
        if not isinstance(start,(int,float)) or isinstance(start,bool) or not math.isfinite(start):raise ValueError('Inicio finito requerido')
        if not lo<=dur<=hi or start<end-.001:raise ValueError('Duración/superposición inválida')
        if abs(round(dur*30)-dur*30)>.001 or abs(round(start*30)-start*30)>.001:raise ValueError('Inicio/duración deben alinearse a30fps')
        scene['start']=start;end=start+dur
        if not scene.get('objective') or not scene.get('content'):raise ValueError('Faltan significado y objetivo narrativo')
        params=scene.get('params',{})
        if not isinstance(params,dict):raise ValueError('params debe ser objeto')
        allowed=set(definition.get('defaults',{}))|set(definition.get('parameters',{})) if definition else {'final_price'}
        if set(params)-allowed:raise ValueError('Parámetros inexistentes: '+','.join(sorted(set(params)-allowed)))
        for key,value in params.items():
            rule=definition.get('parameters',{}).get(key,'') if definition else ''
            limit=re.search(r'≤(\d+)',rule)
            if limit and isinstance(value,str) and len(value)>int(limit[1]):raise ValueError('Texto excede el límite: '+key)
        def safe(value,depth=0):
            if depth>10:raise ValueError('Parámetros demasiado anidados')
            if isinstance(value,str) and len(value)>2000:raise ValueError('Texto excesivo')
            if isinstance(value,float) and not math.isfinite(value):raise ValueError('Valor numérico no finito')
            if isinstance(value,list):
                if len(value)>36:raise ValueError('Más de36 elementos: dividir escena')
                for x in value:safe(x,depth+1)
            if isinstance(value,dict):
                for k,v in value.items():
                    if k in ('html','javascript','script','eval','video','broll','stock','iframe'):raise ValueError('Código/medio no permitido en parámetros')
                    if k in ('accent','fromColor','color','fill') and (not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v)):raise ValueError('Color hex de6dígitos requerido')
                    safe(v,depth+1)
        safe(params)
        framing=scene.get('framing')
        if framing is not None:
            if not isinstance(framing,dict) or set(framing)!={'view_box'}:raise ValueError('framing exige solo view_box')
            box=framing['view_box']
            if not isinstance(box,list) or len(box)!=4 or any(not isinstance(n,(int,float)) or isinstance(n,bool) or not math.isfinite(n) for n in box):raise ValueError('view_box requiere cuatro números finitos')
            x,y,bw,bh=box
            if bw<600 or bh<1066 or x<0 or y<0 or x+bw>720.001 or y+bh>1280.001 or abs(bw/bh-9/16)>.001:raise ValueError('Reencuadre debe permanecer dentro del lienzo, conservar9:16 y evitar recorte excesivo')
        presentation=scene.get('presentation')
        if presentation is not None:
            if not isinstance(presentation,dict) or set(presentation)-{'labels','omit'}:raise ValueError('presentation admite solo labels/omit')
            contract=definition.get('presentation',{})
            labels=presentation.get('labels',{});omit=presentation.get('omit',[])
            if not isinstance(labels,dict) or set(labels)-set(contract.get('labels',{})):raise ValueError('Etiqueta de presentación no autorizada')
            for key,value in labels.items():
                if not isinstance(value,str) or not value.strip() or len(value)>contract['labels'][key]['max_chars']:raise ValueError('Etiqueta vacía/excesiva: '+key)
            if not isinstance(omit,list) or any(not isinstance(k,str) or k not in contract.get('omit',{}) for k in omit) or len(omit)!=len(set(omit)):raise ValueError('Área omitida no autorizada')
        composition.validate_composition(scene)
        scene.setdefault('composition','full_motion');scene.setdefault('actions',[])
        if not isinstance(scene['actions'],list):raise ValueError('actions debe ser lista')
        for action in scene['actions']:
            if not isinstance(action,dict):raise ValueError('Acción debe ser objeto')
            t=action.get('at',0);length=action.get('duration',0)
            if any(not isinstance(n,(int,float)) or isinstance(n,bool) or not math.isfinite(n) for n in (t,length)):raise ValueError('Tiempo/duración de acción deben ser finitos')
            if t<0 or length<0 or t+length>dur+.001:raise ValueError('Acción fuera de escena')
        for key in ('transition_in','transition_out'):
            transition=scene.setdefault(key,{'kind':'cut','duration':0})
            if transition['kind'] not in ('cut','wipe','push','match','mask'):raise ValueError('Transición desconocida')
            length=transition.get('duration',0)
            if not isinstance(length,(int,float)) or isinstance(length,bool) or not math.isfinite(length):raise ValueError('Duración de transición debe ser finita')
            if not 0<=length<=min(.6,dur/3):raise ValueError('Transición fuera de límites')
    composition.validate_continuity(spec,defs)
    spec['duration']=end
    if end>180:raise ValueError('Dividir composiciones superiores a180s')
    return spec

def font_css():
    sources=[('Sequel','recursos/Sequel_Sans_Bold_Disp.ttf',700),('Scholar','recursos/Scholar_Italic.ttf',400),
      ('InterUI','.agents/skills/hyperframes-creative/frame-presets/code-editorial/fonts/Inter-400.woff2',400),
      ('InterUI','.agents/skills/hyperframes-creative/frame-presets/code-editorial/fonts/Inter-700.woff2',700)]
    for weight in (400,700):
        mono=next(iter((ROOT/'.agents/skills').rglob(f'JetBrainsMono-{weight}.woff2')),None)
        if mono:
            for alias in ('Mono','JetBrains'):sources.append((alias,str(mono.relative_to(ROOT)),weight))
    return ''.join('@font-face{font-family:'+name+';font-weight:'+str(weight)+';src:url("'+data_url(file)+'")}'for name,file,weight in sources)

def bundled_assets(brand_context='editorial_reel'):
    assets=load(HERE/'assets.json',{})
    entries=assets.get('assets',assets)
    result={}
    for key,record in entries.items():
        if not isinstance(record,dict) or not record.get('archivo'):continue
        result[key]={**record,'data':data_url(record['archivo'])}
    # El registro amplía recursos de nuevas instancias; no modifica el catálogo
    # aprobado ni su arte. La preparación privada no concede derechos públicos.
    try:
        import brand_registry
    except ModuleNotFoundError as exc:
        if exc.name!='brand_registry':raise
    else:
        for key,record in brand_registry.assets_for_engine(data_uri=True,context=brand_context).items():
            if key in result:raise ValueError('ID de marca colisiona con recurso aprobado: '+key)
            result[key]=record
    return result

def cancelled_module():
    """La geometría y timeline canónicas se adaptan sin modificar sus archivos."""
    p=load('ejemplos/clone_componente/proyecto.json');a=p['aprobacion_diseno']
    if digest('ejemplos/clone_componente/diseno.svg')!=a['diseno_sha256']:raise ValueError('Base aprobada modificada')
    source=w.inside('ejemplos/clone_componente/index.html').read_text()
    svg=source[source.index('<svg '):source.index('</svg>')+6]
    code=w.inside('ejemplos/clone_componente/timeline.gsap.js').read_text()
    code=code.split('document.fonts.ready.then(() => {',1)[1].rsplit('});',1)[0]
    code=code[:code.index('  window.__timelines=')]
    code=code.replace('const F = n => (n - 48) / 30;','const ratio=C.duration/1.6;const F=n=>(n-48)/30*ratio;')
    svg_ids=set(re.findall(r'id="([^"]+)"',svg))
    # Un selector empieza por#, pero también un color. Namespaces solo para
    # IDs/prefijos presentes en la geometría aprobada; conservar hex cromáticos.
    code=re.sub(r"'#([a-z][a-z0-9_-]*)'",lambda m:"Q+'"+m[1]+"'" if any(name.startswith(m[1])for name in svg_ids)else m[0],code)
    code=re.sub(r'duration:(\d+)/30',r'duration:\1/30*ratio',code).replace('},i/30));','},i/30*ratio));')
    code=code.replace('184,190,196,200,204,207,210,212,213,214];','184,190,196,200,204,207,210,212,213,214].map(n=>Math.round(n*C.params.final_price/214));')
    code=code.replace('const counter={value:29};','const counter={value:prices[0]};')
    return """Clone.register('cancelled',{durationRange:[1.2,4.8],defaults:{final_price:214},build(C){
      if(!Number.isFinite(C.params.final_price)||C.params.final_price<=0||C.params.final_price>=10000)throw Error('Importe inválido');
      const Q='#'+C.prefix+'-';
      const svg="""+json.dumps(svg).replace('</','<\\/')+""";
      C.root.innerHTML=svg.replace(/id="([^"]+)"/g,(_,id)=>'id="'+C.id(id)+'"').replace(/url\\(#([^)]*)\\)/g,(_,id)=>'url(#'+C.id(id)+')');
      """+code+"\n return tl;}});"

def device_handoffs(scenes):
    """Continuidad geométrica opt-in basada en la entidad compartida del plan.

    No reconoce formas ni inventa morphing: mueve los marcos nativos hasta una
    pose coincidente y cambia el contenido mediante el corte solicitado.
    """
    poses={'phone_recon':[56,135,322],'phone_rebuild':[190,112,340],
           'phone_qa':[56,130,322],'problem_resolution':[61,126,325]}
    actors={'phone_recon':('agent',[427,236,240]),'phone_rebuild':('worker',[465,750,180]),
            'phone_qa':('agent',[425,210,240]),'problem_resolution':('agent',[449,553,218])}
    result={}
    for first,second in zip(scenes,scenes[1:]):
        a,b=first['family'],second['family'];incoming=second.get('handoff',{})
        real_device=next((op for op in (second.get('continuity') or {}).get('operations',[]) if op['kind']=='device_pose_match'),None)
        if a not in poses or b not in poses or (not real_device and (not first.get('presentation') or not second.get('presentation'))):continue
        if second['transition_in']['kind']!='cut' or incoming.get('incoming_scene')!=first['id'] or not incoming.get('shared_entity_ids'):continue
        if first.get('framing')!=second.get('framing'):continue
        if first['params'].get('appName')!=second['params'].get('appName'):continue
        duration=real_device['duration'] if real_device else round(min(.3,first['duration']*.1)*30)/30
        out={'direction':'out','source':poses[a],'target':poses[b],'duration':duration,'kind':'native_pose_match'}
        inn={'direction':'in','source':poses[a],'target':poses[b],'duration':duration,'kind':'native_pose_match'}
        if first['params'].get('agent')==second['params'].get('agent'):
            out['actor']={'group':actors[a][0],'source':actors[a][1],'target':actors[b][1]}
            inn['actor']={'group':actors[b][0],'source':actors[a][1],'target':actors[b][1]}
        result.setdefault(first['id'],[]).append(out);result.setdefault(second['id'],[]).append(inn)
    return result

def compile_multiscene(spec,out):
    """Hosts reales HyperFrames; cada archivo hijo utiliza un reloj local.

    La duración lógica deSceneIR permanece intacta. La ventana visible saliente
    se extiende únicamente durante el reveal siguiente para mantener continuidad.
    """
    scenes=spec['scenes']
    if scenes[0]['start']!=0 or any(abs(b['start']-a['start']-a['duration'])>.001 for a,b in zip(scenes,scenes[1:])):
        raise ValueError('Multiescena requiere cobertura continua desde0, sin huecos')
    if any(scene['id']=='clone-main' for scene in scenes):raise ValueError('clone-main está reservado para el host')
    previous_mounts=load(out/'mounts.json',{});previous_sources=load(out/'source_manifest.json',{}).get('files',{})
    compositions=out/'compositions';shared=out/'shared'
    compositions.mkdir(exist_ok=True);shared.mkdir(exist_ok=True)
    safe_json=lambda x:json.dumps(x,ensure_ascii=False).replace('</','<\\/')
    module=(HERE/'runtime.js').read_text()+'\n'+''.join(f.read_text()+'\n' for f in sorted((HERE/'components').glob('*.js')))
    if any(scene['family']=='cancelled' for scene in scenes):module+='\n'+cancelled_module()
    extensions='\n'.join((HERE/name).read_text() for name in ('presentation.js','layout.js','continuity.js'))
    brand_context=spec.get('planner',{}).get('asset_resolution',{}).get('context','editorial_reel')
    bootstrap='window.CLONE_ASSETS='+safe_json(bundled_assets(brand_context))+';window.CLONE_DESIGN='+safe_json(load(HERE/'design-system.json',{}))+';window.CLONE_PRESENTATION='+safe_json(load(HERE/'presentation.json',{}))+';\n'+module+'\n'+extensions
    bootstrap+='''\nwindow.__timelines=window.__timelines||{};
window.__cloneInstances=[];window.renderReady=false;
window.CloneFontsReady=Promise.all(['700 30px Sequel','400 30px Scholar','400 30px InterUI','700 30px InterUI','400 30px Mono','700 30px Mono','400 30px JetBrains','700 30px JetBrains'].map(f=>document.fonts.load(f)));
window.CloneMountReady=(instance)=>{
  window.__cloneInstances=window.__cloneInstances.filter(x=>x.id!==instance.id);
  window.__cloneInstances.push(instance);
  window.renderReady=window.CLONE_MOUNT_IDS.every(id=>window.__timelines[id]);
  if(window.renderReady)window.dispatchEvent(new Event('hf-timelines-built'));
};
'''
    actor_bridges=composition.bridges(scenes)
    bootstrap+='window.CLONE_MOUNT_IDS='+safe_json([scene['id'] for scene in scenes]+[op['id'] for op in actor_bridges])+';\n'
    (shared/'clone-bundle.js').write_text(bootstrap)
    (shared/'fonts.css').write_text(font_css())
    (shared/'gsap.min.js').write_bytes(w.inside('recursos/gsap.min.js').read_bytes())
    hosts=[];compiled=[];handoffs=device_handoffs(scenes)
    for index,scene in enumerate(scenes):
        ident=scene['id'];next_in=scenes[index+1]['transition_in'] if index+1<len(scenes) else {'kind':'cut','duration':0}
        tail=next_in['duration'] if next_in['kind']!='cut' else 0
        visible_duration=scene['duration']+tail
        local={**scene,'visible_duration':visible_duration,'tail':tail,'next_transition':next_in,'render_handoff':handoffs.get(ident),'render_actor_bridges':[op for op in actor_bridges if ident in (op['source_scene'],op['target_scene'])],'conceptual':spec.get('semantic_analysis',{}).get('conceptual',False)}
        code='''(async()=>{
  await window.CloneFontsReady;
  const scene=SCENE;
  const surface=document.getElementById('__clone-surface-'+scene.id);
  const built=CloneBuildCreative(scene,surface);
  const presentation=ClonePresent(built,scene);
  presentation.layout=CloneLayout(built,scene);
  presentation.closing=CloneClosing(built,scene);
  presentation.actor_bridges=CloneActorMask(built,scene);
  const tl=built.renderTl||built.tl,tin=scene.transition_in,tout=scene.transition_out;
  const svg=surface.querySelector('svg');
  const view=svg?.getAttribute('viewBox')?.trim().split(/\\s+/).map(Number);
  const zoomView=scale=>{
    if(!view||view.length!==4||!view.every(Number.isFinite)||view[2]<=0||view[3]<=0)throw Error('Match requiere SVG con viewBox finito');
    return [view[0]+view[2]*(1-1/scale)/2,view[1]+view[3]*(1-1/scale)/2,view[2]/scale,view[3]/scale].join(' ');
  };
  // Entrada ysalida pertenecen al wrapper local, nunca al clip del host.
  if(tin.kind!=='cut'&&tin.duration>0){
    const initial={x:tin.kind==='push'?1080:0,scale:1,
      clipPath:tin.kind==='mask'?'circle(0% at 50% 45%)':tin.kind==='push'?'inset(0% 0% 0% 0%)':'inset(0% 100% 0% 0%)'};
    gsap.set(surface,initial);
    tl.fromTo(surface,initial,{x:0,scale:1,clipPath:tin.kind==='mask'?'circle(150% at 50% 45%)':'inset(0% 0% 0% 0%)',duration:tin.duration,ease:'power3.out',immediateRender:true},0);
  }
  // Zoom de match sobre el viewBox: conserva vectores/textos nítidos y evita
  // rasterización CSS distinta entre búsquedas directas e inversas.
  if(tin.kind==='match'&&tin.duration>0){
    gsap.set(svg,{attr:{viewBox:zoomView(1.07)}});
    tl.fromTo(svg,{attr:{viewBox:zoomView(1.07)}},{attr:{viewBox:view.join(' ')},duration:tin.duration,ease:'power3.out',immediateRender:true},0);
  }
  if(tout.kind==='match'&&tout.duration>0)tl.fromTo(svg,{attr:{viewBox:view.join(' ')}},{attr:{viewBox:zoomView(1.07)},duration:tout.duration,ease:'power2.inOut',immediateRender:false},scene.duration-tout.duration);
  if(scene.tail>0&&scene.next_transition.kind==='push')tl.to(surface,{x:-1080,duration:scene.tail,ease:'power3.out'},scene.duration);
  // Calentar también el wrapper añadido después del builder; su pose inicial
  // debe existir cuando el transporte local todavía está exactamente en0.
  const real=CloneTimelineReal(tl);
  real.seek(real.duration(),false);real.seek(0,false);
  if(built.context.presentZero)built.context.presentZero();
  CloneRegisterNative(scene.id,built);
  await document.fonts.ready;
  window.__timelines[scene.id]=tl;
  window.CloneMountReady({id:scene.id,family:scene.family,start:scene.start,duration:scene.duration,visible_duration:scene.visible_duration,
    labels:tl.labels,tweens:tl.getChildren(true,true,false).length,used_assets:[...built.context.usedAssets],presentation,local_clock:true});
})();'''.replace('SCENE',safe_json(local),1).replace('window.__timelines[scene.id]=tl;',f'window.__timelines[{json.dumps(ident)}]=tl;')
        template=f'''<!doctype html><html><head><meta charset="utf-8"></head><body><template>
<link rel="stylesheet" href="../shared/fonts.css">
<style>#__clone-root-{ident},#__clone-surface-{ident}{{position:absolute;inset:0;width:100%;height:100%;overflow:hidden}}#__clone-surface-{ident}>svg{{display:block;width:100%;height:100%}}</style>
<div id="__clone-root-{ident}" data-composition-id="{ident}" data-width="1080" data-height="1920" data-duration="{visible_duration}"><div id="__clone-surface-{ident}"></div></div>
<script>{code}</script></template></body></html>'''
        file=compositions/(ident+'.html');file.write_text(template)
        compiled.append({'id':ident,'family':scene['family'],'file':str(file.relative_to(out)),'start':scene['start'],
                         'duration':scene['duration'],'visible_duration':visible_duration,'tail':tail})
        hosts.append(f'<div class="clip" id="__clone-host-{ident}" data-composition-id="{ident}" data-composition-src="compositions/{ident}.html" data-start="{scene["start"]}" data-duration="{visible_duration}" data-track-index="1" data-track-kind="graphics" data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:{index}"></div>')
    for op in actor_bridges:
        ident=op['id'];duration=op['duration']
        code='(async()=>{await window.CloneFontsReady;await CloneActorBridge('+safe_json(op)+',document.getElementById("__clone-bridge-'+ident+'"));})();'
        (compositions/(ident+'.html')).write_text(f'<html><body><template><div data-composition-id="{ident}" data-width="1080" data-height="1920" data-duration="{duration}" id="__clone-bridge-{ident}" style="position:absolute;inset:0;width:100%;height:100%"></div><script>{code}</script></template></body></html>')
        hosts.append(f'<div class="clip" data-composition-id="{ident}" data-composition-src="compositions/{ident}.html" data-start="{op["start"]}" data-duration="{duration}" data-track-index="2" data-track-kind="graphics" data-width="1080" data-height="1920" style="position:absolute;inset:0;z-index:100;pointer-events:none"></div>')
        compiled.append({'id':ident,'family':'compositor_actor_bridge','file':'compositions/'+ident+'.html','start':op['start'],'duration':duration,'visible_duration':duration,'tail':0,'role':'transition'})
    html='''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>CLONE · composición modular</title>
<link rel="stylesheet" href="shared/fonts.css"><script src="shared/gsap.min.js"></script><script src="shared/clone-bundle.js"></script>
<script>window.__timelines['clone-main']=gsap.timeline({paused:true});</script>
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#f3f3f5}#__clone-film{position:relative;width:100%;height:100%;overflow:hidden}</style></head><body>
'''+f'<div id="__clone-film" data-composition-id="clone-main" data-width="1080" data-height="1920" data-duration="{spec["duration"]}">'+''.join(hosts)+'</div></body></html>'
    (out/'index.html').write_text(html)
    write(out/'scene.json',spec)
    write(out/'mounts.json',{'version':1,'architecture':'hyperframes_subcompositions','root_clock':'global','child_clocks':'local',
                            'scene_duration':'logical','visible_tail':'previous state retained only during the next reveal','mounts':compiled})
    # Eliminar solo HTMLs derivados de la compilación anterior de este proyecto.
    active={item['file'] for item in compiled}
    for old_record in previous_mounts.get('mounts',[]):
        old=w.inside(out/old_record['file'])
        if old_record['file'] not in active and old.is_file() and previous_sources.get(str(old.relative_to(ROOT)))==digest(old):old.unlink()
    write(out/'source_manifest.json',source_fingerprint(out))
    return out

class _SourceLinks(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if values.get('data-composition-src'):self.links.append(values['data-composition-src'])
        if values.get('src'):self.links.append(values['src'])
        if tag=='link' and values.get('href'):self.links.append(values['href'])

def source_fingerprint(folder):
    """Hash actual transitivo, incluyendo hijos editados directamente enStudio."""
    folder=w.inside(folder);visited={};queue=[folder/'index.html']
    while queue:
        file=w.inside(queue.pop())
        if str(file) in visited:continue
        if not file.is_file():raise ValueError('Dependencia de render ausente: '+str(file))
        visited[str(file)]=digest(file);links=[]
        if file.suffix=='.html':
            parser=_SourceLinks();parser.feed(file.read_text());links=parser.links
        elif file.suffix=='.css':
            links=re.findall(r'url\(\s*[\'\"]?([^\'\")]+)',file.read_text())
        elif file.suffix in ('.js','.mjs'):
            links=re.findall(r'(?:from\s+|import\s*\()([\'\"])([^\'\"]+)\1',file.read_text())
            links=[item[1] for item in links]
        for link in links:
            url=urlsplit(link)
            if not url.path or link.startswith('#') or url.scheme=='data':continue
            if url.scheme or url.netloc:raise ValueError('Dependencia externa mutable no permitida: '+url.scheme)
            path=unquote(url.path)
            queue.append((ROOT/path.lstrip('/')) if path.startswith('/') else file.parent/path)
    records={str(pathlib.Path(file).relative_to(ROOT)):sha for file,sha in sorted(visited.items())}
    payload=json.dumps(records,sort_keys=True,separators=(',',':'))
    return {'sha256':hashlib.sha256(payload.encode()).hexdigest(),'files':records,'file_count':len(records)}

def compile_spec(spec,folder):
    spec=validate_spec(spec);out=w.inside(folder);out.mkdir(parents=True,exist_ok=True)
    if len(spec['scenes'])>1:return compile_multiscene(spec,out)
    if True:
        brand_context=spec.get('planner',{}).get('asset_resolution',{}).get('context','editorial_reel')
        assets=bundled_assets(brand_context);design=load(HERE/'design-system.json',{})
        safe_json=lambda x:json.dumps(x,ensure_ascii=False).replace('</','<\\/')
        module=(HERE/'runtime.js').read_text()+'\n'+''.join(f.read_text()+'\n'for f in sorted((HERE/'components').glob('*.js')))
        if any(s['family']=='cancelled'for s in spec['scenes']):module+='\n'+cancelled_module()
        extensions='\n'.join((HERE/name).read_text() for name in ('presentation.js','layout.js','continuity.js'))
        script='window.CLONE_ASSETS='+safe_json(assets)+';window.CLONE_DESIGN='+safe_json(design)+';window.CLONE_PLAN='+safe_json(spec)+';window.CLONE_PRESENTATION='+safe_json(load(HERE/'presentation.json',{}))+';\n'+module+'\n'+extensions
        script+='''\n(async()=>{
          // Un DOM aún vacío no solicita las @font-face; cargar explícitamente
          // antes de medir títulos, comandos y etiquetas dentro de los builders.
          await Promise.all(['700 30px Sequel','400 30px Scholar','400 30px InterUI','700 30px InterUI','400 30px Mono','700 30px Mono','400 30px JetBrains','700 30px JetBrains'].map(f=>document.fonts.load(f)));
          const main=gsap.timeline({paused:true});
          window.__cloneInstances=[];
          window.CLONE_PLAN.scenes.forEach((scene,index)=>{
            const host=document.getElementById('scene-'+scene.id);
            const inner=host.querySelector('.scene-world');
            const built=CloneBuildCreative(scene,inner);
            const presentation=ClonePresent(built,scene);
            presentation.layout=CloneLayout(built,scene);
            presentation.closing=CloneClosing(built,scene);
            gsap.set(host,{visibility:'hidden'});
            main.set(host,{visibility:'visible'},scene.start);
            const timeline=built.renderTl||built.tl;
            main.add(timeline,scene.start);timeline.paused(false);
            if(index<window.CLONE_PLAN.scenes.length-1)main.set(host,{visibility:'hidden'},scene.start+scene.duration);
            // La misma superficie se desplaza al cambiar de concepto; no fade negro.
            const tin=scene.transition_in,tout=scene.transition_out;
            if(tin.kind!=='cut')main.fromTo(inner,{x:tin.kind==='push'?1080:0,
              scale:tin.kind==='match'?1.07:1,
              clipPath:tin.kind==='mask'?'circle(0% at 50% 45%)':tin.kind==='wipe'?'inset(0% 100% 0% 0%)':'inset(0%)'},
              {x:0,scale:1,clipPath:tin.kind==='mask'?'circle(150% at 50% 45%)':'inset(0%)',duration:tin.duration,ease:'power3.out'},scene.start);
            // Mantener imagen saliente hasta el siguiente estado; nunca un hueco negro.
            if(tout.kind==='match')main.to(inner,{scale:1.07,duration:tout.duration,ease:'power2.inOut'},scene.start+scene.duration-tout.duration);
            window.__cloneInstances.push({id:scene.id,family:scene.family,labels:timeline.labels,tweens:timeline.getChildren(true,true,false).length,used_assets:[...built.context.usedAssets],presentation});
          });
          window.__timelines=window.__timelines||{};window.__timelines['clone-main']=main;
          await document.fonts.ready;
          const real=CloneTimelineReal(main);real.seek(real.duration(),false);real.seek(0,false);window.renderReady=true;
        })();'''
        hosts=''.join(f'<div class="clip scene-host" id="scene-{s["id"]}" data-start="{s["start"]}" data-duration="{s["duration"]}" data-track-index="{i}" data-track-kind="graphics" style="z-index:{i}"><div class="scene-world"></div></div>'for i,s in enumerate(spec['scenes']))
        html='<!doctype html><html><head><meta charset="utf-8"><title>CLONE Motion</title><style>'+font_css()+'''html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#f3f3f5}.scene-host,.scene-world{position:absolute;inset:0;width:100%;height:100%;overflow:hidden}.scene-world>svg{display:block;width:100%;height:100%}#clone-main{position:relative;width:100%;height:100%}</style></head><body>'''+f'<div id="clone-main" data-composition-id="clone-main" data-width="1080" data-height="1920" data-duration="{spec["duration"]}">{hosts}</div><script src="{data_url("recursos/gsap.min.js")}"></script><script>'+script+'</script></body></html>'
        (out/'index.html').write_text(html)
    write(out/'scene.json',spec)
    return out

def inspect(folder):
    folder=w.inside(folder)
    for operation,args in [('check',['--browser-gpu','--samples','11','--at-transitions','--max-transition-samples','40']),('keyframes',[])]:
        target=folder if operation=='check'else folder/'index.html'
        r=cli([operation,str(target),'--json',*args]);(folder/(operation+'.json')).write_text(r.stdout);(folder/(operation+'.log')).write_text(r.stderr)
        if operation=='check':
            data=json.loads(r.stdout)
            # AA es un control independiente: la paleta editorial medida de CLONE
            # y los estados intermedios transparentes pueden incumplirlo. No se
            # ocultan sus hallazgos ni se altera automáticamente el diseño fuente.
            technical=all(data.get(k,{}).get('ok') for k in ('lint','runtime','layout'))
            if not technical or data.get('browserSkipped')or not data['layout'].get('samples'):raise ValueError('Navegador no verificó la composición')
            write(folder/'check_gate.json',{'technical_ok':technical,'contrast_ok':data.get('contrast',{}).get('ok'),'contrast_findings':data.get('contrast',{}).get('findings',[]),'policy':'Contraste y semejanza visual se revisan por separado; los hallazgos AA se conservan completos.'})
        elif r.returncode:raise ValueError('Control '+operation+' falló: '+str(folder.relative_to(ROOT)))

def render(folder,force=False):
    """Render transitorio; publicar únicamente bytes decodificados de fuentes estables.

    La exclusión GPU continúa siendo externa (.estado/clone/render.lock).
    Un fallo conserva el MP4/QC anterior y registra render_pending.json aparte.
    """
    folder=w.inside(folder);spec=load(folder/'scene.json');duration=spec['duration']
    target=folder/'preview.mp4';partial=folder/'preview.part.mp4';poster_part=folder/'poster.part.png'
    previous=load(folder/'qc.json',{});sources=source_fingerprint(folder)
    code=digest(folder/'index.html');scene_sha=digest(folder/'scene.json')
    key=hashlib.sha256(str(folder.relative_to(ROOT)).encode()).hexdigest()[:10]+'_'+folder.name
    decoded=ROOT/'.estado/tmp/clone_qc'/key;decoding=decoded.with_name(key+'_part')
    def stable():
        current=source_fingerprint(folder)
        if current['sha256']!=sources['sha256'] or digest(folder/'scene.json')!=scene_sha:
            raise ValueError('Fuentes modificadas durante el render: recompilar y revisar; se conserva el MP4 anterior')
        return current
    try:
        inspect(folder);stable()
        unchanged=previous.get('source_sha256')==sources['sha256'] or (not previous.get('source_sha256') and sources['file_count']==1 and previous.get('html_sha256')==code)
        if not force and target.exists() and unchanged and previous.get('mp4_sha256')==digest(target):
            partial.unlink(missing_ok=True);poster_part.unlink(missing_ok=True)
            if decoding.exists():shutil.rmtree(w.inside(decoding))
            (folder/'render_pending.json').unlink(missing_ok=True)
            return previous
        partial.unlink(missing_ok=True);poster_part.unlink(missing_ok=True)
        if decoding.exists():shutil.rmtree(w.inside(decoding))
        decoding.mkdir(parents=True)
        args=['render',str(folder),'--output',str(partial),'--fps','30','--crf','17','--workers','1','--browser-gpu','--gpu','--video-frame-format','jpg','--sdr','--no-best-effort','--experimental-fast-capture=false']
        r=cli(args);(folder/'render.log').write_text(r.stdout+'\n'+r.stderr)
        if r.returncode:raise ValueError('Render falló: '+str(folder.relative_to(ROOT)))
        stable()
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(partial)],text=True))
        v=next(x for x in probe['streams']if x['codec_type']=='video');frames=int(v['nb_read_frames']);expected=round(duration*30)
        fps_num,fps_den=map(int,v['avg_frame_rate'].split('/'))
        if frames!=expected or v['width']!=1080 or v['height']!=1920 or fps_den<=0 or abs(fps_num/fps_den-30)>.001:raise ValueError('Frames/dimensiones/FPS incorrectos')
        # FFmpeg9 local codifica NVENC; el decodificador del sistema incluye PNG.
        # -xerror impide aceptar silenciosamente errores de decodificación.
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-err_detect','explode','-i',str(partial),'-map','0:v:0','-fps_mode','passthrough','-vf','scale=180:320','-start_number','0','-y',str(decoding/'f_%04d.png')],check=True)
        files=sorted(decoding.glob('f_*.png'))
        if len(files)!=frames:raise ValueError('Decodificación incompleta: se conserva el MP4 anterior')
        sheet=Image.new('RGB',(12*180,math.ceil(frames/12)*340),(20,20,22));d=ImageDraw.Draw(sheet)
        for i,file in enumerate(files):
            with Image.open(file)as frame:sheet.paste(frame,(i%12*180,i//12*340+20))
            d.text((i%12*180+4,i//12*340+3),f'{i/30:.2f}s',fill='white')
        sheet.save(decoding/'consecutivos.jpg')
        subprocess.run(['/usr/bin/ffmpeg','-v','error','-xerror','-ss',str(min(duration*.55,duration-1/30)),'-i',str(partial),'-frames:v','1','-y',str(poster_part)],check=True)
        stable()
        asset_records=load(HERE/'assets.json',{});asset_records=asset_records.get('assets',asset_records)
        qc={'estado':'render_tecnico_verificado_pendiente_revision_visual','html_sha256':code,'source_sha256':sources['sha256'],'source_files':sources['files'],'scene_sha256':scene_sha,'mp4_sha256':digest(partial),'duration':duration,'frames':frames,'fps':30,'decoded_all_frames':True,'sources_stable':True,'atomic_publication':True,'hardware_gpu':'hardware gpu'in r.stdout.lower(),'nvenc':v.get('tags',{}).get('encoder','').endswith('h264_nvenc'),'capturas':str((decoded/'consecutivos.jpg').relative_to(ROOT)),'reference_comparison':'pendiente','fidelidad_visual':'pendiente','movimiento':'pendiente','reutilizacion':'pendiente','consistencia':'pendiente','bundled_assets':{k:a.get('sha256')for k,a in asset_records.items()},'used_assets':'Pendiente recibo del navegador; empaquetar no significa mostrar.'}
        # El destino canónico se cambia solo después de todas las verificaciones.
        # Nunca contiene un archivo que siga siendo escrito por el encoder.
        partial.replace(target);poster_part.replace(folder/'poster.png')
        if decoded.exists():shutil.rmtree(w.inside(decoded))
        decoding.replace(decoded)
        write(folder/'qc.json',qc);(folder/'render_pending.json').unlink(missing_ok=True)
        return qc
    except Exception as error:
        partial.unlink(missing_ok=True);poster_part.unlink(missing_ok=True)
        if decoding.exists():shutil.rmtree(w.inside(decoding))
        write(folder/'render_pending.json',{'estado':'pendiente','motivo':str(error),'previous_mp4_preserved':target.exists(),'previous_mp4_sha256':digest(target)if target.exists()else None,'requested_source_sha256':sources['sha256']})
        raise

def build_defaults():
    jobs=[]
    for definition in catalog():
        ident=definition['id'];lo,hi=definition['durationRange'];ref=definition.get('reference',[])
        steps=definition.get('defaults',{}).get('steps',[])
        duration=(ref[0]['exit_s']-ref[0]['entry_s']) if ref else max(3,max((step.get('at',0)+step.get('duration',0) for step in steps),default=0))
        duration=round(min(hi,max(lo,duration))*30)/30
        if ident=='cancelled':duration=1.6
        spec={'schema_version':1,'id':ident,'scenes':[{'id':ident,'family':ident,'duration':duration,'content':definition['description']or ident,'objective':'Demostrar entrada, transformación y salida de la familia','params':definition['defaults'],'actions':[],'reference':definition['reference']}]}
        folder='proyectos/clone_motor/previews/'+ident
        try:compile_spec(spec,folder);jobs.append(folder)
        except Exception as e:write(w.inside(folder)/'qc.json',{'estado':'pendiente','motivo':str(e)})
    return jobs

def batch(jobs,workers=1):
    if not 1<=workers<=2:raise ValueError('Máximo2 renders independientes para preservar RAM/VRAM')
    reports=[]
    def work(job):
        try:return {'job':job,'ok':True,'qc':render(job)}
        except Exception as e:
            data={'job':job,'ok':False,'estado':'pendiente','motivo':str(e)}
            folder=w.inside(job)
            # render() conserva el QC del MP4 bueno; el lote no lo reemplaza
            # por un fallo de un intento posterior.
            pending=load(folder/'render_pending.json',{});write(folder/'render_pending.json',{**pending,**data})
            if not(folder/'qc.json').exists():write(folder/'qc.json',data)
            return data
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers)as pool:
        for result in pool.map(work,jobs):reports.append(result);print(result['job'],result['ok'],flush=True)
    write('proyectos/clone_motor/batch.json',reports);return reports

def gallery():
    report_file=HERE/'report.py'
    if report_file.is_file():
        import importlib.util
        module_spec=importlib.util.spec_from_file_location('clone_report',report_file)
        module=importlib.util.module_from_spec(module_spec);sys.modules['clone_report']=module
        module_spec.loader.exec_module(module)
        if not callable(getattr(module,'generate',None)):raise ValueError('report.py no expone generate()')
        return module.generate()
    folder=ROOT/'proyectos/clone_motor';records=[];cards=[]
    for path in sorted((folder/'previews').glob('*/scene.json')):
        ident=path.parent.name;spec=load(path);qc=load(path.parent/'qc.json',{})
        records.append({'id':ident,'scene':str(path.relative_to(ROOT)),'qc':qc})
        video=f'previews/{ident}/preview.mp4';poster=f'previews/{ident}/poster.png'
        cards.append(f'<article><h2>{ident}</h2><video controls loop preload="none" poster="{poster}" src="{video}"></video><p>{qc.get("estado","pendiente")}</p><details><summary>Parámetros y ejemplo</summary><pre>{__import__("html").escape(json.dumps(spec,ensure_ascii=False,indent=2))}</pre></details></article>')
    html='<!doctype html><html lang="es"><meta charset="utf-8"><title>Biblioteca CLONE</title><style>body{font:16px system-ui;background:#f3f3f5;color:#19191b;margin:28px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(275px,1fr));gap:24px}article{background:white;border-radius:14px;padding:18px;box-shadow:0 8px 24px #0001}video{width:100%;max-height:500px;background:#000;border-radius:10px}pre{overflow:auto;font-size:12px}h2{font-size:20px}a{color:#8c452f}</style><h1>CLONE · Biblioteca de motion graphics</h1><p>Previews reales. Los estados distinguen validación técnica, visual y pendientes. Una aprobación técnica no demuestra fidelidad.</p><p><a href="demo_nueva/preview.mp4">Demostración nueva</a> · <a href="registro_componentes.json">Registro y evidencias</a></p><main>'+''.join(cards)+'</main></html>'
    (folder/'galeria.html').write_text(html);write(folder/'registro_componentes.json',records)

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('catalog');sub.add_parser('defaults');sub.add_parser('gallery')
    b=sub.add_parser('batch');b.add_argument('--workers',type=int,default=1)
    c=sub.add_parser('compile');c.add_argument('spec');c.add_argument('--out',required=True)
    r=sub.add_parser('render');r.add_argument('folder');r.add_argument('--force',action='store_true')
    args=parser.parse_args()
    if args.cmd=='catalog':print(json.dumps(catalog(),ensure_ascii=False,indent=2))
    elif args.cmd=='defaults':print(json.dumps(build_defaults()))
    elif args.cmd=='compile':compile_spec(load(args.spec),args.out)
    elif args.cmd=='render':print(json.dumps(render(args.folder,args.force)))
    elif args.cmd=='batch':batch([str(p.parent.relative_to(ROOT))for p in sorted((ROOT/'proyectos/clone_motor/previews').glob('*/scene.json'))],args.workers)
    else:gallery()
if __name__=='__main__':main()
