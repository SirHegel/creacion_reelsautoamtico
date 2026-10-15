"""Segunda inferencia de integración: conserva íntegro el SceneIR de CLONE.

Decide cámara, representación de palabras y cues; nunca cambia las familias.
No renderiza, transcribe, modifica módulos ni usa un plan manual de reemplazo.
"""
import argparse,copy,json,math,os,pathlib,re,signal,subprocess,sys,time
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import planner as p
ROOT=p.ROOT
VERSION='2.2.0_production_complete'
class IntegrationError(p.PlannerError):pass

def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def arr(items,maximum=100):return {'type':'array','items':items,'maxItems':maximum}
def integer(lo=0,hi=10000):return {'type':'integer','minimum':lo,'maximum':hi}
def enum(*values):return {'type':'string','enum':list(values)}
TEXT={'type':'string'}
BLOCK=obj({'id':TEXT,'start_frame':integer(),'end_frame':integer(),'word_start':integer(),'word_end':integer(),
           'sequence':TEXT,'font':enum('Sequel','Scholar'),'color':enum('white','ink','red'),
           'emphasis_word_indices':arr(integer(),12),'red_reason':TEXT,'placement':enum('hook','under_chin','composition')})
# Capacidad opcional: identidad oficial integrada con el titular sobre cámara.
# Sin permiso para dibujar un logo, posicionarlo mediante código libre o asumir
# que un recurso empaquetado se ve en el render.
BLOCK['properties'].update(brand_asset={'type':['string','null']},brand_entity_id={'type':['string','null']},brand_reason={'type':'string'})
SCHEMA=obj({'schema_version':{'type':'integer','enum':[1]},'conceptual':{'type':'boolean'},'camera_budget_reason':TEXT,
            'camera_windows':arr(obj({'start_frame':integer(),'end_frame':integer(),'state':enum('full','split'),
                 'transition_frames':integer(0,18),'exit_frames':integer(0,18),'anchor_indices':arr(integer(),100),'reason':TEXT}),24),
            'hook_end_frame':integer(1,180),'hook_blocks':arr(BLOCK,30),'caption_blocks':arr(BLOCK,100),
            'phase_cues':arr(obj({'scene_id':TEXT,'cue_id':TEXT,'anchor_index':integer(),'reason':TEXT}),100),
            'omissions':arr(obj({'word_start':integer(),'word_end':integer(),'scene_id':TEXT,'field_path':TEXT,'reason':TEXT}),50)})
# Opcionales locales para conservar las direcciones V2 sin reescribirlas.
# La copia estricta del proveedor exige declarar la pose/proporción elegidas.
SCHEMA['properties'].update(camera_mode=enum('full_first','split_first'),
                            split_top={'type':'number','enum':[.5,.55]},split_ratio_reason=TEXT,
                            profile=enum('legacy','production_complete'),
                            focus_windows=arr(obj({'scene_id':TEXT,'start_frame':integer(),'end_frame':integer(),
                                'primary_target':TEXT,'support_target':{'type':['string','null']},'reason':TEXT}),48))
SCHEMA['properties']['camera_windows']['items']['properties'].update(
    split_top={'anyOf':[{'type':'number','enum':[.5,.55]},{'type':'null'}]},split_ratio_reason=TEXT)


def constraint_contract(value=None):
    if value is None:return {}
    keys={'camera_mode','split_top','scope_end_frame','max_primary','max_support','profile'}
    if not isinstance(value,dict)or set(value)-keys:raise IntegrationError('Restricción de integración no publicada')
    result=copy.deepcopy(value)
    if 'profile'in result and result['profile']not in ('legacy','production_complete'):raise IntegrationError('Perfil de integración no publicado')
    if 'camera_mode'in result and(not isinstance(result['camera_mode'],str)or result['camera_mode']not in {'full_first','split_first'}):raise IntegrationError('Modo de cámara no disponible')
    if 'split_top'in result and(isinstance(result['split_top'],bool)or not isinstance(result['split_top'],(int,float))or result['split_top']not in {.5,.55}):raise IntegrationError('Split admite50/50 o55/45')
    if 'scope_end_frame'in result and(isinstance(result['scope_end_frame'],bool)or not isinstance(result['scope_end_frame'],int)or result['scope_end_frame']<1):raise IntegrationError('Alcance requiere frame final exclusive entero positivo')
    if result.get('profile')=='production_complete'and 'scope_end_frame'in result:raise IntegrationError('Producción completa no deriva un prefijo ni solicita muestra parcial')
    if 'max_primary'in result and(type(result['max_primary'])is not int or result['max_primary']!=1):raise IntegrationError('Jerarquía admite un protagonista por momento')
    if 'max_support'in result and(type(result['max_support'])is not int or not 0<=result['max_support']<=1):raise IntegrationError('Jerarquía admite como máximo un apoyo')
    return result


def scoped_inputs(spec,narration,constraints=None):
    """Prefijo en frontera existente, sin replan ni alterar una sola acción.

    La evidencia primaria sigue perteneciendo al origen. El subconjunto deriva
    del alcance autorizado, no de una nueva selección manual de familias.
    """
    constraints=constraint_contract(constraints)
    if 'scope_end_frame'not in constraints:return copy.deepcopy(spec),copy.deepcopy(narration),None
    frames=constraints['scope_end_frame'];source_frames=round(spec['duration']*30);duration=frames/30
    if not 0<frames<source_frames:raise IntegrationError('Un prefijo autorizado debe ser más corto que el SceneIR origen')
    if spec['timing']['anchors']!=p.narration_items(narration):raise IntegrationError('Anclas origen no corresponden a la narración')
    selected=[scene for scene in spec['scenes']if round((scene['start']+scene['duration'])*30)<=frames]
    if not selected or round((selected[-1]['start']+selected[-1]['duration'])*30)!=frames:
        raise IntegrationError('El recorte debe terminar en una frontera existente; no truncar escenas/steps')
    words=p.narration_items(narration)
    if any(word['start']<duration<word['end']for word in words):raise IntegrationError('El prefijo recorta una palabra alineada; no inventar nuevos tiempos')
    indices=[i for i,word in enumerate(words)if word['end']<=duration]
    if not indices or indices!=list(range(len(indices))):raise IntegrationError('Las palabras del prefijo deben ser un rango inicial íntegro')
    anchored=[i for scene in selected for i in scene['narration_anchors']]
    if sorted(anchored)!=indices or len(anchored)!=len(set(anchored)):raise IntegrationError('Escenas existentes no cubren exactamente las palabras del prefijo')
    child=copy.deepcopy(spec);voice=copy.deepcopy(narration)
    child['scenes']=copy.deepcopy(selected);child['duration']=duration
    child['timing']['anchors']=copy.deepcopy(words[:len(indices)])
    child['timing']['note']='Prefijo de anclas originales en una frontera existente; sin nueva inferencia primaria ni retime.'
    source_words=narration.get('words')
    if not isinstance(source_words,list):raise IntegrationError('Un recorte trazable necesita words originales, no reconstruir alineación desde segmentos')
    voice['words']=copy.deepcopy(source_words[:len(indices)])
    voice['text']=' '.join(word['text']for word in voice['words'])
    voice['text_asr']=' '.join(word.get('asr_text',word['text'])for word in voice['words'])
    voice.update(start=0,end=duration,duration=duration,video_duration=duration)
    if 'segments'in voice:voice['segments']=[s for s in voice['segments']if s.get('end',duration+1)<=duration]
    if 'editorial_normalizations'in voice:
        kept={word.get('id')for word in voice['words']};voice['editorial_normalizations']=[s for s in voice['editorial_normalizations']if s.get('word_id')in kept]
    receipt={'kind':'prefix_at_existing_scene_boundary','start_frame':0,'end_frame':frames,'fps':30,
             'source_frames':source_frames,'source_duration':spec['duration'],'word_indices':indices,
             'selected_scene_ids':[s['id']for s in selected],'excluded_scene_ids':[s['id']for s in spec['scenes']if s not in selected],
             'scene_parameters_and_steps_unchanged':all(child['scenes'][i]==selected[i]for i in range(len(selected))),
             'primary_inference_reused':True,'new_primary_inference':False,'semantic_analysis':'inherited original context, not re-authored for prefix',
             'audio':'Original source and speed preserved; AAC packet-cut duration requires renderer measurement, not assumed equal to visual scope.'}
    child['scope']=copy.deepcopy(receipt);voice['scope']=copy.deepcopy(receipt)
    return child,voice,receipt


def family_layout_capabilities():
    """Puertos de encuadre existentes; no seleccionan ni reconstruyen familias."""
    return {d['id']:{'mode':'semantic_reflow'if d['id']=='composition_graph'else'native_surface_measured',
                    'phase_targets':[phase[3]for phase in p.FAMILY_CAPABILITIES.get(d['id'],{}).get('phases',[])],
                    'continuity_ports':d.get('continuity',{}).get('ports',[]),
                    'layout_profiles':d.get('layout',{}).get('profiles',[]),
                    'fit':'Measured per scene; split cannot certify mobile legibility until browser QA.',
                    'native_source_modified':False}for d in p.engine.catalog()}

def focus_targets(spec):
    """Solo IDs que el builder actual publica de forma inequívoca."""
    result={}
    for scene in spec['scenes']:
        targets={}
        if scene['family']=='composition_graph':
            for node in scene['params']['nodes']:
                entry=next((step['at']for step in scene['params']['steps']if step['op']=='enter'and step['target']==node['id']),None)
                if entry is not None:targets[node['id']]={'kind':node['kind'],'label':node['label'],'enter_native_at':entry}
        result[scene['id']]=targets
    return result


def requested_entry_time(scene,pairs,native_at):
    """Entrada según el único reloj solicitado, no según una posición DOM."""
    duration=scene['duration'];knots=[(0,0),(duration,duration)]
    knots.extend((target,native)for native,target in pairs)
    knots.extend((point['at'],point['native_at'])for point in (scene.get('rhythm')or{}).get('clock_knots',[]))
    ordered=[]
    for target,native in sorted(knots):
        if ordered and abs(target-ordered[-1][0])<1e-6:
            if abs(native-ordered[-1][1])>1e-6:raise IntegrationError('Foco no puede usar dos estados nativos en el mismo frame')
            continue
        if ordered:
            rate=(native-ordered[-1][1])/(target-ordered[-1][0])
            if not 0<=rate<=6+1e-6:raise IntegrationError('Reloj de foco no monótono o fuera de capacidad6x')
        ordered.append((target,native))
    for (ta,na),(tb,nb)in zip(ordered,ordered[1:]):
        if na-1e-6<=native_at<=nb+1e-6:
            return scene['start']+(ta if abs(nb-na)<1e-6 else ta+(native_at-na)/(nb-na)*(tb-ta))
    raise IntegrationError('Entrada nativa del foco fuera de su escena')


def normalize_focus(raw,spec,mapping,constraints):
    windows=raw.setdefault('focus_windows',[]);hook_end=raw['hook_end_frame'];frames=round(spec['duration']*30)
    if not windows:
        if 'max_primary'in constraints or 'max_support'in constraints:raise IntegrationError('Jerarquía explícita necesita focus_windows ejecutables, no una promesa textual')
        return
    targets=focus_targets(spec);scenes={s['id']:s for s in spec['scenes']};cursor=0
    for window in windows:
        a,b=frame_window(window,frames);scene=scenes.get(window['scene_id']);available=targets.get(window['scene_id'],{})
        if a!=cursor or b>hook_end:raise IntegrationError('Ventanas de foco deben cubrir exactamente el hook sin huecos/solapamientos')
        if not scene or a<round(scene['start']*30)or b>round((scene['start']+scene['duration'])*30):raise IntegrationError('Foco fuera de su escena existente')
        primary=window['primary_target'];support=window['support_target']
        if primary not in available or support is not None and support not in available:raise IntegrationError('Target de foco inexistente o sin puerto nativo publicado')
        if primary==support:raise IntegrationError('Principal y apoyo no pueden duplicar el mismo objeto')
        if support is not None and constraints.get('max_support',1)==0:raise IntegrationError('El encargo excluye objetos de apoyo')
        if len(window['reason'].strip())<20:raise IntegrationError('Jerarquía sin motivo semántico')
        for target in (primary,support):
            if target is None:continue
            enters=requested_entry_time(scene,mapping[scene['id']],available[target]['enter_native_at'])
            if a<math.ceil(enters*30-1e-6):raise IntegrationError('Foco activa un nodo antes de su enter: '+target)
        window.update(primary_kind=available[primary]['kind'],support_kind=available[support]['kind']if support else None,
                      execution='requested_adapter_focus',execution_verified=False)
        cursor=b
    if cursor!=hook_end:raise IntegrationError('Foco no cubre el final del hook')

def token_text(value):return re.sub(r'[^\w\s]','',p.norm(value))
def word_range(block,words):
    a,b=block['word_start'],block['word_end']
    if not 0<=a<=b<len(words):raise IntegrationError('Rango de palabras inexistente')
    return list(range(a,b+1))
def frame_window(item,frames):
    a,b=item['start_frame'],item['end_frame']
    if not 0<=a<b<=frames:raise IntegrationError('Ventana fuera del video original; end_frame es exclusive')
    return a,b

def legal_cues(spec):
    result={}
    for scene in spec['scenes']:
        cues=[]
        if scene['family']=='composition_graph':
            for index,step in enumerate(scene['params']['steps']):
                cues.append({'cue_id':'step:'+str(index),'native_at':step['at'],'runtime_label':None,
                             'timing_basis':'declared_step_time','approximate':False,'op':step['op'],'target':step['target']})
        else:
            for action in scene.get('actions',[]):
                if action.get('enabled',True)and action.get('visible',True)and action.get('phase_id'):
                    cues.append({'cue_id':'phase:'+action['phase_id'],'native_at':action['at'],'runtime_label':None,
                                 'timing_basis':'derived_phase_window','approximate':True,'op':action['op'],'target':action['target']})
        result[scene['id']]=cues
    return result

def protected_sources():
    paths=list((HERE/'components').glob('*.js'))+[ROOT/'ejemplos/clone_componente/timeline.gsap.js']
    return {str(path.relative_to(ROOT)):p.engine.digest(path)for path in paths}

def normalize(raw,spec,narration,constraints=None):
    constraints=constraint_contract(constraints)
    import jsonschema
    try:jsonschema.validate(raw,SCHEMA)
    except Exception as exc:raise IntegrationError('Contrato de integración inválido: '+str(exc).splitlines()[0])from exc
    raw=copy.deepcopy(raw);words=p.narration_items(narration);frames=round(spec['duration']*30)
    profile=raw.get('profile',constraints.get('profile','legacy'));production=profile=='production_complete'
    if constraints.get('profile',profile)!=profile:raise IntegrationError('Dirección contradice perfil explícito del encargo')
    if constraints.get('scope_end_frame',frames)!=frames:raise IntegrationError('Alcance de dirección no coincide con el prefijo derivado')
    brand_context=spec.get('planner',{}).get('asset_resolution',{}).get('context','editorial_reel');brand_assets=p.resolved_assets(brand_context)
    if spec['timing']['anchors']!=words:raise IntegrationError('Palabras no corresponden al SceneIR original')
    if not raw['conceptual']:raise IntegrationError('La integración no es una prueba auténtica de ejecución de software')
    windows=raw['camera_windows']
    if not production and len(windows)>8:raise IntegrationError('Perfil legacy admite como máximo8 ventanas')
    if not windows or windows[0]['start_frame']!=0:raise IntegrationError('Cámara inicial debe ser visible desde frame0')
    mode=raw.get('camera_mode','split_first'if windows[0]['state']=='split'else'full_first')
    if windows[0]['state']!=('split'if mode=='split_first'else'full'):raise IntegrationError('camera_mode contradice la pose inicial real')
    split_top=raw.get('split_top',.5 if mode=='split_first'else .55);ratio_reason=raw.get('split_ratio_reason','')
    if constraints.get('camera_mode',mode)!=mode or constraints.get('split_top',split_top)!=split_top:raise IntegrationError('Dirección contradice modo/proporción explícitos del encargo')
    if mode=='split_first'and split_top==.55 and len(ratio_reason.strip())<20:raise IntegrationError('Split-first55/45 necesita motivo concreto de encuadre')
    ranges=[];previous=0
    for index,window in enumerate(windows):
        a,b=frame_window(window,frames)
        window_ratio=window.get('split_top')
        if window_ratio is not None:
            if not production and window_ratio!=split_top:raise IntegrationError('Ratio por ventana requiere perfil production_complete')
            if window['state']!='split':raise IntegrationError('Ratio por ventana sólo corresponde a split')
            if index==0 and window_ratio!=split_top:raise IntegrationError('Ratio inicial contradice split_top del encargo')
            if window_ratio!=split_top and len(window.get('split_ratio_reason','').strip())<20:raise IntegrationError('Cambio de ratio requiere motivo concreto de encuadre')
        if not production and(max(window['transition_frames'],window['exit_frames'])>10):raise IntegrationError('Perfil legacy admite transiciones de hasta10 frames')
        if a<previous:raise IntegrationError('Ventanas de cámara solapadas/desordenadas')
        if len(window['reason'].strip())<20:raise IntegrationError('Cámara sin motivo narrativo')
        if window['transition_frames']>b-a or window['exit_frames']>b-a:raise IntegrationError('Transición fuera de la ventana visible')
        if window['transition_frames']+window['exit_frames']>b-a:raise IntegrationError('Entrada y salida se superponen dentro de una aparición')
        if index==0 and window['transition_frames']!=0:raise IntegrationError('Primer rostro visible desde0, sin fade previo')
        pose_change=index and a==windows[index-1]['end_frame']and(window['state']!=windows[index-1]['state']or(window.get('split_top')or split_top)!=(windows[index-1].get('split_top')or split_top))
        if pose_change and not (9 if production else 4)<=window['transition_frames']<=(18 if production else 10):
            raise IntegrationError('Cambio contiguo de pose necesita transición '+('suave9–18frames'if production else'rápida')+' dentro de su ventana')
        if production and index and a!=windows[index-1]['end_frame']and not 9<=window['transition_frames']<=18:raise IntegrationError('Nueva aparición necesita entrada suave9–18frames')
        if production and(not index+1<len(windows)or b!=windows[index+1]['start_frame'])and not 6<=window['exit_frames']<=18:raise IntegrationError('Cada aparición production necesita salida6–18frames dentro de su ventana')
        if index<len(windows)-1 and window['exit_frames'] and b==windows[index+1]['start_frame']:raise IntegrationError('No desvanecer rostro antes de un reencuadre contiguo')
        if not window['anchor_indices']or len(set(window['anchor_indices']))!=len(window['anchor_indices']):raise IntegrationError('Cámara sin anclas reales únicas')
        for anchor in window['anchor_indices']:
            if not 0<=anchor<len(words)or words[anchor]['end']*30<=a or words[anchor]['start']*30>=b:raise IntegrationError('Ancla de cámara no intersecta su ventana')
        if ranges and a==ranges[-1][1]:ranges[-1]=(ranges[-1][0],b)
        else:ranges.append((a,b))
        previous=b
    if windows[-1]['exit_frames']<6:raise IntegrationError('Última aparición necesita6frames de salida dentro de su ventana')
    visible=sum(b-a for a,b in ranges)
    if any(b-a>90 for a,b in ranges):raise IntegrationError('Rostro supera3s continuos incluyendo full/split/transiciones')
    if visible/frames>.2 and len(raw['camera_budget_reason'].strip())<20:raise IntegrationError('Presencia superior al objetivo requiere justificación; no es cuota mínima')
    hook_end=raw['hook_end_frame']
    if not min(120,frames)<=hook_end<=min(180,frames):raise IntegrationError('Hook debe respetar4–6s o cubrir el segmento autorizado más corto')
    if production and words[0]['start']==0 and (not raw['hook_blocks']or raw['hook_blocks'][0]['word_start']!=0 or raw['hook_blocks'][0]['start_frame']!=0):raise IntegrationError('La primera identidad/frase ya pronunciada empieza en frame0, sin una pausa gráfica artificial')
    coverage=set();ids=set();sequences={};last_start=-1;last_end=0
    brands={token_text(entity['name'])for entity in spec['semantic_analysis']['entities']if entity.get('kind')in ('organización','producto','fuente mencionada','brand','tool','platform','organization','product')}
    for kind,blocks in [('hook',raw['hook_blocks']),('caption',raw['caption_blocks'])]:
        if not blocks and(kind=='hook'or hook_end<frames):raise IntegrationError('Falta representación textual del hook o del desarrollo')
        if kind=='caption'and blocks and hook_end==frames:raise IntegrationError('Un segmento completamente hook no tiene desarrollo para captions posteriores')
        for block in blocks:
            indices=word_range(block,words);a,b=frame_window(block,frames);ident=block['id']
            if not re.fullmatch(r'[a-z][a-z0-9_-]{0,45}',ident)or ident in ids:raise IntegrationError('ID textual inválido/repetido')
            ids.add(ident)
            if kind=='hook':
                if block['placement']!='hook'or not 2<=len(indices)<=8 or b>hook_end or b-a>90:raise IntegrationError('Hook debe ser frase integrada breve, nunca palabra aislada')
                if not block['sequence']:raise IntegrationError('Hook sin secuencia editorial')
                prior=sequences.get(block['sequence'])
                if prior and(block['word_start']!=prior['word_start']or block['word_end']<=prior['word_end']or a<prior['end_frame']):raise IntegrationError('Hook incremental altera rango, retrocede o duplica capas')
                if not prior and block['font']!='Sequel':raise IntegrationError('Titular principal debe usar Sequel')
                if prior and (block.get('brand_asset'),block.get('brand_entity_id'))!=(prior.get('brand_asset'),prior.get('brand_entity_id')):raise IntegrationError('La identidad de marca debe mantenerse en toda la secuencia incremental del hook')
                sequences[block['sequence']]=block
            else:
                if block['placement']=='hook'or block['sequence']or not 2<=len(indices)<=3 or a<hook_end or a<last_end:raise IntegrationError('Caption debe agrupar2–3palabras después del hook, sin solapamientos')
                if set(indices)&coverage:raise IntegrationError('Caption duplica palabras ya representadas')
                face=any(x<=a and b<=y for x,y in ranges)
                if(block['placement']=='under_chin')!=face:raise IntegrationError('Placement no corresponde a presencia del rostro')
                last_end=b
            if a<last_start:raise IntegrationError('Bloques de texto desordenados')
            last_start=a
            if a>round(words[indices[-1]]['end']*30)+2 or b<round(words[indices[-1]]['end']*30)-1:raise IntegrationError('Texto no permanece durante el final de su frase real')
            if a<round(words[indices[0]]['start']*30)-1:raise IntegrationError('Texto adelantado fuera de su frase')
            emphasis=block['emphasis_word_indices']
            if len(set(emphasis))!=len(emphasis)or set(emphasis)-set(indices):raise IntegrationError('Énfasis fuera de su bloque')
            if block['color']=='red':
                if not emphasis or len(emphasis)==len(indices)or len(block['red_reason'].strip())<20:raise IntegrationError('Rojo requiere palabra semántica, no bloque completo')
                if any(token_text(words[i]['text'])in brands or(not production and token_text(words[i]['text'])in {'internet','sin','ninguna','pagar','api'})for i in emphasis):raise IntegrationError('Rojo aplicado a marca, título o ventaja positiva')
            elif emphasis or block['red_reason']:raise IntegrationError('Énfasis rojo declarado con color no rojo')
            asset=block.get('brand_asset');entity_id=block.get('brand_entity_id');brand_reason=block.get('brand_reason','')
            if asset is not None:
                if kind!='hook'or not isinstance(brand_reason,str):raise IntegrationError('Logo editorial solo dentro del hook integrado')
                entity=next((e for e in spec['semantic_analysis']['entities']if e['id']==entity_id),None)
                if entity is not None and token_text(entity['name'])not in token_text(narration['text']):raise IntegrationError('Logo del hook pertenece a una entidad fuera de la narración autorizada')
                fake_scene={'family':'integration_hook','asset_bindings':[{'path':'icon','asset':asset,'entity_id':entity_id,'reason':brand_reason}]}
                try:receipt=p.validate_asset_bindings(fake_scene,{'icon':asset},brand_assets,spec['semantic_analysis'])
                except p.PlannerError as exc:raise IntegrationError('Logo del hook: '+str(exc))from exc
                if not receipt:raise IntegrationError('Logo del hook requiere marca auténtica verificada')
                block['brand_identity_receipt']=receipt[0]
            elif entity_id is not None or brand_reason:raise IntegrationError('Binding de hook sin asset auténtico')
            block['text']=' '.join(words[i]['text']for i in indices);block['word_indices']=indices
            coverage.update(indices)
    scenes={scene['id']:scene for scene in spec['scenes']}
    for omission in raw['omissions']:
        indices=word_range(omission,words);scene=scenes.get(omission['scene_id'])
        if not scene or len(omission['reason'].strip())<20 or set(indices)&coverage:raise IntegrationError('Omisión no justificada o duplica texto')
        if omission['field_path']=='caption':raise IntegrationError('Caption nativa reemplazada no puede justificar una omisión')
        try:value=p.get_path(scene['params'],omission['field_path'])
        except Exception as exc:raise IntegrationError('Omisión referencia campo inexistente')from exc
        phrase=' '.join(words[i]['text']for i in indices)
        if not isinstance(value,str)or token_text(phrase)not in token_text(value):raise IntegrationError('SceneIR no contiene realmente el texto omitido')
        omission['text']=phrase;coverage.update(indices)
    if coverage!=set(range(len(words))):raise IntegrationError('Narración sin representación textual: '+str(sorted(set(range(len(words)))-coverage)))
    legal=legal_cues(spec);seen=set();mapping={}
    for cue in raw['phase_cues']:
        scene=scenes.get(cue['scene_id']);definition=next((c for c in legal.get(cue['scene_id'],[])if c['cue_id']==cue['cue_id']),None)
        key=(cue['scene_id'],cue['cue_id']);anchor=cue['anchor_index']
        if not scene or not definition or key in seen or anchor not in scene['narration_anchors']or len(cue['reason'].strip())<20:raise IntegrationError('Cue inexistente, duplicado o sin ancla de escena')
        seen.add(key);target=round(words[anchor]['start']*30)/30-scene['start']
        if not 0<=target<scene['duration']:raise IntegrationError('Cue fuera de escena')
        cue.update(definition,desired_global_frame=round(words[anchor]['start']*30),desired_local_time=target,execution_verified=False)
        mapping.setdefault(scene['id'],[]).append((definition['native_at'],target))
    if set(mapping)!=set(scenes):raise IntegrationError('Cada escena necesita al menos una correspondencia explícita')
    for pairs in mapping.values():
        pairs.sort()
        if any(y[0]<=x[0]or y[1]<=x[1]for x,y in zip(pairs,pairs[1:])):raise IntegrationError('Timewarp no monótono; omitir cues ambiguos, nunca invertir fases')
    # Un solo reloj: cues de voz y puntos/holds del primer modelo deben poder
    # convivir, sin sustituir decisiones ni crear dos retimados encadenados.
    for scene_id,pairs in mapping.items():
        scene=scenes[scene_id];rhythm=scene.get('rhythm')
        if not rhythm and not production:continue
        joint=[{'at':target,'native_at':native}for native,target in pairs]
        joint+=copy.deepcopy(rhythm['clock_knots'])if rhythm else[{'at':0,'native_at':0},{'at':scene['duration'],'native_at':scene['duration']}]
        joint.sort(key=lambda point:(point['at'],point['native_at']))
        unique=[]
        for point in joint:
            if unique and abs(point['at']-unique[-1]['at'])<1e-6:
                if abs(point['native_at']-unique[-1]['native_at'])>1e-6:raise IntegrationError('Cue de voz contradice un punto/hold de ritmo ya decidido')
                continue
            if unique:
                rate=(point['native_at']-unique[-1]['native_at'])/(point['at']-unique[-1]['at'])
                if not 0<=rate<=6+1e-6:raise IntegrationError('Cue de voz atraviesa/invierte un hold o supera capacidad6x del reloj')
            unique.append(point)
    normalize_focus(raw,spec,mapping,constraints)
    raw.update(schema_version=1,version=VERSION,profile=profile,duration=spec['duration'],frames=frames,fps=30,camera_mode=mode,split_top=split_top,split_ratio_reason=ratio_reason,
               visible_frames=visible,visible_fraction=visible/frames,visible_intervals_frames=ranges,
               integration_constraints=constraints,focus_execution={'mode':'requested_adapter_focus'if raw['focus_windows']else'native_existing_focus',
                 'max_primary':1 if raw['focus_windows']else None,'max_support':constraints.get('max_support',1)if raw['focus_windows']else None,'execution_verified':False},
               native_caption_overrides=[{'scene_id':s['id'],'parameter':'caption','mode':'replace_native_editorial_with_source_words','execution_verified':False}for s in spec['scenes']if 'caption'in s['params']],
               execution_verified=False,semantic_selection_modified=False,
               timing_note='Cues solicitados; preferir etiquetas runtime medidas. Las ventanas de fases derivadas son aproximadas, no sincronización interna comprobada.')
    return raw

def validate_plan(direction,spec,narration):
    """Revalida el contrato normalizado sin mutar el plan o sus decisiones."""
    allowed=set(SCHEMA['properties'])|{'version','duration','frames','fps','visible_frames','visible_fraction','visible_intervals_frames','native_caption_overrides','execution_verified','semantic_selection_modified','timing_note','scene_ir_path','scene_ir_sha256','narration_path','narration_sha256','source_path','source_sha256','style_sha256','manual_sha256','protected_source_sha256','inference','integration_source_sha256','integration_constraints','focus_execution','scope_provenance_path','scope_provenance_sha256','source_scene_ir_path','source_scene_ir_sha256','source_narration_path','source_narration_sha256','source_manual_sha256'}
    if set(direction)-allowed:raise IntegrationError('Campos ajenos a la integración normalizada')
    raw={key:copy.deepcopy(direction[key])for key in SCHEMA['properties']if key in direction}
    for key in ('hook_blocks','caption_blocks'):
        fields=set(BLOCK['properties']);raw[key]=[{field:value for field,value in block.items()if field in fields}for block in raw[key]]
    fields=set(SCHEMA['properties']['phase_cues']['items']['properties'])
    raw['phase_cues']=[{key:value for key,value in cue.items()if key in fields}for cue in raw['phase_cues']]
    fields=set(SCHEMA['properties']['omissions']['items']['properties'])
    raw['omissions']=[{key:value for key,value in item.items()if key in fields}for item in raw['omissions']]
    fields=set(SCHEMA['properties']['focus_windows']['items']['properties'])
    if 'focus_windows'in raw:raw['focus_windows']=[{key:value for key,value in item.items()if key in fields}for item in raw['focus_windows']]
    result=normalize(raw,spec,narration,direction.get('integration_constraints'))
    for key in ('hook_blocks','caption_blocks'):
        for given,derived in zip(direction[key],result[key]):
            for field in ('text','word_indices'):
                if field in given and given[field]!=derived[field]:raise IntegrationError('Texto normalizado no coincide con las palabras originales')
    return {**copy.deepcopy(direction),**result}

def invoke(prompt,state,timeout=180):
    state=p.inside(state);state.mkdir(parents=True,exist_ok=True)
    for name in ('logs','sqlite','tmp','cache','config','data','runtime'):(state/name).mkdir(exist_ok=True)
    (state/'runtime').chmod(0o700)
    schema=state/'integration_schema.json';p.save(schema,p.strict_provider_schema(SCHEMA));p.save(state/'prompt.txt',prompt)
    command=p.provider_command(state);command[command.index('--output-schema')+1]=str(schema)
    response=state/'response.json'
    if response.exists():response.unlink()
    env=os.environ.copy();env.update({'TMPDIR':str(state/'tmp'),'XDG_CACHE_HOME':str(state/'cache'),'XDG_CONFIG_HOME':str(state/'config'),'XDG_DATA_HOME':str(state/'data'),'XDG_RUNTIME_DIR':str(state/'runtime')})
    started=time.monotonic();process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=process.communicate(prompt,timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.communicate();p.save(state/'provider_proof.json',{'real_inference':False,'error':'timeout','version':VERSION,'child_process_group_terminated':True})
        raise IntegrationError('Timeout de integración; sin fallback')from exc
    p.save(state/'events.jsonl',p.redacted(stdout));p.save(state/'stderr.log',p.redacted(stderr))
    events=[]
    for line in stdout.splitlines():
        try:events.append(json.loads(line))
        except json.JSONDecodeError:pass
    forbidden=[e.get('item',{}).get('type',e.get('type'))for e in events if e.get('item',{}).get('type')in {'command_execution','mcp_tool_call','web_search','file_change','image_view'}or e.get('type')in {'tool_call','function_call'}]
    proof={'provider':'codex','version':VERSION,'real_inference':False,'returncode':process.returncode,'elapsed_s':round(time.monotonic()-started,3),'prompt_sha256':p.hash_text(prompt),'schema_sha256':p.engine.digest(schema),'tool_calls':forbidden,'usage':[e.get('usage')for e in events if e.get('type')=='turn.completed'],'isolation':{'root':'read_only','writable_scope':str(state.relative_to(ROOT)),'auth':'global_read_only','HOME_changed':False,'CODEX_HOME_changed':False,'provider_command_reused':True}}
    p.save(state/'provider_proof.json',proof)
    if forbidden or process.returncode or not response.is_file()or not any(e.get('type')=='turn.completed'for e in events):raise IntegrationError('Proveedor de integración no completado/seguro; revisar recibo privado')
    raw=json.loads(response.read_text());proof.update(real_inference=True,response_sha256=p.engine.digest(response));p.save(state/'provider_proof.json',proof)
    return raw,proof

def make_prompt(spec,narration,style,error=None,constraints=None):
    constraints=constraint_contract(constraints)
    rules='''Eres director de integración CLONE+YO. Devuelve solo JSON tipado. No herramientas, archivos, comandos o nuevas familias. El SceneIR original es inmutable; no alterar params, actions, escenas, narración, hechos o duración. Conserva la credibilidad y unsupported_claims del SceneIR. Las notas de verificación, permisos y conceptualidad permanecen en reportes; no fabricar demostraciones auténticas ni convertir esas notas en títulos internos.
Elige cámara por significado y constraints explícitas: camera_mode full_first o split_first describe la POSE INICIAL, no una secuencia obligatoria. No es obligatorio comenzar full ni pasar de full a split. Split-first tiene primera ventana split desde frame0 y transition_frames:0: ya está compuesto, sin fade/reveal ni pose full escondida. Full-first tiene primera ventana full desde0 y transition_frames:0; puede mantenerse sin split si la narrativa lo permite. Un inicio admite una sola ventana. split_top:0.5 significa50/50 y es preferido para split-first;0.55 significa55/45 y split-first necesita split_ratio_reason concreto de encuadre. Constraints de modo/proporción son vinculantes, no alternativas que puedas ignorar. Cambios contiguos full↔split tienen transición4–10frames dentro de la ventana entrante. Última aparición reserva exit_frames>=6 dentro del end_frame exclusive; entrada y salida no se solapan. Unión de rostro<=90frames continuos incluyendo transiciones; cambiar pose no reinicia el contador. Presencia15–20% orientativa, no cuota mínima ni obligación de llenar. Reconocimiento inicial normalmente1–2,5s según voz, nunca fracción de segundo solo para cuadrar20%. Si supera20% justificar en camera_budget_reason. anchor_indices intersectan cada ventana y reason explica intención. Conservar luz, fondo, fuente y movimientos originales; no videos externos/blur/relleno ni retime.
Hook normalmente4–6s: hook_end_frame120–180 dentro de imagen. Si el alcance autorizado es más corto de4s, todo ese segmento puede ser hook: hook_end_frame=frames (p.ej.108frames para3,6s), sin inventar desarrollo. Frases integradas e incrementales, NO palabras aisladas. hook_blocks de2–8palabras contiguas; sequence es ID estable, mismo word_start y word_end creciente, bloques no solapados; cada uno<=90frames y conservarlo hasta el final real de su frase. Texto derivado solo de words; primer bloque de cada sequence Sequel, Scholar selectiva, placement:'hook'. No anticipar ni omitir narración para facilitar layout. semantic_analysis heredada puede contener contexto posterior: no introducir hechos/marcas fuera de las palabras del alcance actual.
Después del hook captions2–3palabras, sequence:'', font Sequel/Scholar, under_chin solo si el rostro permanece durante todo el bloque; deotro modo composition. Si todo el segmento es hook, caption_blocks:[] es correcto. Si queda desarrollo, no dejar captions vacías para suprimir texto. No crear aparición tardía por obligación. Captions sin solapamientos/duplicación del hook, conservando el final real de palabra. Cada palabra aparece en hook/caption o omission literal comprobable. Captions nativas se reemplazan SOLO en instancia y no justifican omissions. Omissions no puede esconder narración.
FOCO EJECUTABLE: focus_targets publica IDs nativos existentes y enter nativo, no nombres inventados ni selectores/código. Si constraints max_primary/max_support está presente, focus_windows cubre íntegramente el hook con intervalos contiguos [start_frame,end_frame), cada uno dentro de una escena existente: {scene_id,start_frame,end_frame,primary_target,support_target:null|ID,reason}. Un principal y como máximo un apoyo; no repetir el mismo target en ambos. Decidir relevos por significado, no por cuota de ventanas. No enfocar un nodo antes de enter según el reloj solicitado fusionado con phase_cues/rhythm. El titular y la identidad editorial pertenecen al mismo protagonista, no a objetos narrativos adicionales. Integrar la narración sin repetir la misma frase en interfaz y titular; el adaptador aplicará supresión instancial del texto duplicado y comprobará el render. No alterar params/steps/familias, añadir un personaje o inventar fuentes. Sin jerarquía solicitada se permite focus_windows:[] para conservar foco nativo. Los recibos siguen execution_verified:false hasta QA; elegir IDs no certifica jerarquía pintada ni presencia de un logo.
Color white|ink|red. red significa SOLO emphasis_word_indices dentro del rango; resto conserva principalwhite/ink segúnfondo. Nunca bloque entero rojo, marca, internet como título, sin/pagar/API como ventaja. red_reason justifica pérdida/riesgo/error/provocación real, por ejemplo furioso. Sin rojo: indices[] y red_reason:''.
phase_cues escoge SOLO IDs de legal_cues y anclas de ESA escena, reason semántico explícito. No crea acciones. IDs step:i refieren pasos ejecutables del grafo; phase:id refiere ventana derivada de familia fija, aproximada hasta medir etiquetas runtime. Cues deben producir mapa tiempo-nativo→voz estrictamente monótono, sin mover dos fases diferentes al mismo instante. Seleccionar los cues que aclaran el mensaje, no todos por cuota; mínimo uno por escena. Mantener límites0/d en adaptador. Cuando scene.rhythm exista, sus points/hold_s y clock_knots forman la decisión de ritmo ya aprobada por el primer modelo: NO modificarla. Solo añadir phase_cues compatibles con ese reloj monótono, sin colocar dos estados fuente distintos en el mismo tiempo de salida ni mover un cue a través de un hold existente. Si los puntos ya alinean esa idea, usa un cue compatible o el endpoint0. El compositor fusionará el reloj, no aplicará dos retimados sucesivos. El recibo y QA comprobarán ejecución; el plan no la afirma.
Hook puede solicitar opcionalmente brand_asset:<ID verificado>,brand_entity_id:<entidad real>,brand_reason:<motivo>. Si no hace falta, brand_asset:null,brand_entity_id:null,brand_reason:'' o campos ausentes. Si se utiliza, todos los bloques de esa misma sequence conservan brand_asset y brand_entity_id idénticos; el primero ya los declara. Es identidad oficial integrada junto a la frase encima de la cámara, con geometría calculada por el adaptador, no una demostración ni una nueva escena. Evaluar cuándo fullcam taparía la única aparición de Google/Claude u otra marca: todos los logos requeridos deben ser realmente visibles y legibles, no solo empaquetados. Usar overlay solo cuando aporte a la frase o rescate identidad tapada; no aplicar por obligación ni meter logos arbitrarios. Conservar condiciones de marcas/ratio/colores; ninguna rotación, sombra directa ni redibujo si el registro lo prohíbe. Respeta fuentes/sombra/identidad del STYLE_YO aportado. No modificar guion para facilitar estas reglas. Cada frame es1/30s; duración/frames originales aparecen en DATOS, audiooriginalAAC se preserva por adaptador sin retimar. Todos los tiempos dentro de imagen y end_frame exclusive.'''
    profile=constraints.get('profile','legacy')
    rules+='\nDeclara profile:'+profile+'. No cambiar el perfil del encargo.'
    if profile=='production_complete':
        rules=rules.replace('Cambios contiguos full↔split tienen transición4–10frames dentro de la ventana entrante.',
            'Cambios contiguos de pose o ratio tienen transición9–18frames (0,3–0,6s) dentro de la ventana entrante. Cada nueva aparición tras una ausencia necesita entrada9–18frames; cada salida a ausencia reserva6–18frames. El primer split está compuesto desde0 con transition_frames:0. Se permiten hasta24 ventanas en todo el reel sin cuota ni obligación de recurrencia. camera_windows[].split_top:null hereda el ratio global, o0.5/0.55 adapta una aparición; un cambio necesita split_ratio_reason de encuadre, nunca cambiar proporción para reducir artificialmente la presencia.')
        rules=rules.replace('Nunca bloque entero rojo, marca, internet como título, sin/pagar/API como ventaja.',
            'Nunca bloque entero rojo ni una marca por decoración. Evaluar el sentido completo de cada frase: rojo únicamente para riesgo, pérdida, error, negación o contraste provocado realmente por la voz. Una ventaja positiva no justifica rojo; no decidir por una lista de palabras del reel anterior.')
        rules=rules.replace('audiooriginalAAC se preserva por adaptador sin retimar.',
            'la pista de voz original se conserva sin retime; una mezcla adicional sólo se ejecuta cuando el proyecto tiene medios y recibo verificables. No afirmar igualdad binaria del audio final si hay música/FX.')
        rules+='\nPRODUCCIÓN COMPLETA: dirigir principio, desarrollo y cierre del guion entero. Si words[0].start=0, el primer hook_block comienza en frame0 y word_start:0: la primera palabra/identidad ya está pronunciada y visible desde F0; las siguientes aparecen a sus tiempos reales dentro de la frase incremental. Usar TODAS las familias que la inferencia primaria seleccionó, cada una por sus acciones nativas y significado; no imponer variedad, cuotas, nueva familia ni una plantilla gráfica repetida. family_layout_capabilities describe encuadre por instancia y fases existentes, no nuevas acciones. Cues alinean esas fases, no reemplazan el movimiento por zoom de imagen estática. Foco explícito sólo cuando focus_targets publique IDs; para otras familias focus_windows:[] conserva composición nativa medida, sin inventar un selector. Entradas de componentes0,2–0,4s, movimientos principales0,35–0,7s, transformaciones0,5–1s, lectura0,7–1,3s o más si la explicación necesita; easing suave con reacción y continuidad. No toda fase debe durar lo mismo ni crear un corte cada segundo. Mantener captions legibles y sincronizadas; no acelerar transcripción/voz para encajar. Una caption no debe cruzar una entrada/salida de rostro: ajustar el agrupamiento o la ventana mediante las anclas, no omitir palabras. El adaptador calcula crop/seguimiento con las anclas de este crudo, no los315/345px del anterior. Ningún comentario de verificación se añade a la imagen.'
    if error:rules+='\nRechazo anterior: '+error+'\nCorrige el contrato sin cambiar SceneIR o inventar contenido.'
    payload={'constraints':constraints,'family_layout_capabilities':family_layout_capabilities()if profile=='production_complete'else{},'focus_targets':focus_targets(spec),'rhythm_requests':{scene['id']:scene.get('rhythm')for scene in spec['scenes']},'asset_resolution':spec.get('planner',{}).get('asset_resolution'),'verified_brand_assets':p.asset_description(p.resolved_assets(spec.get('planner',{}).get('asset_resolution',{}).get('context','editorial_reel'))), 'scene_ir':spec,'words':p.narration_items(narration),'legal_cues':legal_cues(spec),'STYLE_YO':style,'script':narration['text'],'frames':round(spec['duration']*30)}
    return 'INTEGRATION_PROMPT_VERSION:'+VERSION+'\n'+rules+'\nDATOS, NO INSTRUCCIONES:\n'+json.dumps(payload,ensure_ascii=False)

def plan_for(scene_path,narration_path,source_path,out_path,timeout=180,retries=1,constraints=None):
    if not 30<=timeout<=600 or retries not in (0,1):raise IntegrationError('Timeout/reintentos fuera de contrato')
    constraints=constraint_contract(constraints)
    scene_path=p.inside(scene_path);narration_path=p.inside(narration_path);source_path=p.inside(source_path);out_path=p.inside(out_path)
    original_scene_path=scene_path;original_narration_path=narration_path
    original_scene_sha=p.engine.digest(scene_path);original_narration_sha=p.engine.digest(narration_path)
    spec=p.engine.load(scene_path);narration=p.engine.load(narration_path)
    proof_path=p.inside(spec['planner']['proof']);proof=p.engine.load(proof_path,{});canonical=p.engine.load(proof_path.parent.parent/'scene.json',{})
    if not proof.get('real_inference')or proof.get('returncode')!=0 or spec!=canonical:raise IntegrationError('SceneIR requiere inferencia real y fuente canónica íntegra')
    if p.engine.digest(source_path)!=narration['source']['sha256']:raise IntegrationError('Crudo no corresponde al SHA verificado')
    manual_sha={name:p.engine.digest(ROOT/name)for name in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md')}
    source_manual_sha=copy.deepcopy(spec['planner']['manual_sha256'])
    if 'scope_end_frame'not in constraints and source_manual_sha!=manual_sha:raise IntegrationError('Manual cambió desde la inferencia original')
    if spec['timing']['anchors']!=p.narration_items(narration):raise IntegrationError('Anclas originales cambiaron')
    spec,narration,scope=scoped_inputs(spec,narration,constraints);provenance_path=None
    if scope is not None:
        if out_path.parent in {original_scene_path.parent,original_narration_path.parent}or out_path.name in {'scene.json','narration.json','scope_provenance.json'}:
            raise IntegrationError('Prefijo requiere su carpeta canónica propia; no sobrescribir escenas/narración V2')
        scene_path=out_path.parent/'scene.json';narration_path=out_path.parent/'narration.json'
        p.save(scene_path,spec);p.save(narration_path,narration)
        provenance_path=out_path.parent/'scope_provenance.json'
        p.save(provenance_path,{**scope,'constraints':constraints,
            'source_scene_ir_path':str(original_scene_path.relative_to(ROOT)),'source_scene_ir_sha256':original_scene_sha,
            'source_narration_path':str(original_narration_path.relative_to(ROOT)),'source_narration_sha256':original_narration_sha,
            'scene_ir_path':str(scene_path.relative_to(ROOT)),'scene_ir_sha256':p.engine.digest(scene_path),
            'narration_path':str(narration_path.relative_to(ROOT)),'narration_sha256':p.engine.digest(narration_path),
            'source_path':str(source_path.relative_to(ROOT)),'source_sha256':narration['source']['sha256'],
            'source_primary_provider_proof':str(proof_path.relative_to(ROOT)),'source_manual_sha256':source_manual_sha,
            'direction_manual_sha256':manual_sha,'new_direction_inference':'pending; primary selection is reused unchanged'})
    initial_sha=p.engine.digest(scene_path);voice_sha=p.engine.digest(narration_path)
    style_path=ROOT/'STYLE_YO.md';style=style_path.read_text();style_sha=p.engine.digest(style_path);code_sha=p.engine.digest(pathlib.Path(__file__))
    identity=p.hash_text(initial_sha+voice_sha+style_sha+p.hash_text(json.dumps(SCHEMA,sort_keys=True))+code_sha+VERSION+
                         p.hash_text(json.dumps({'constraints':constraints,'manual_sha256':manual_sha},sort_keys=True)))[:16]
    state=p.inside('.estado/clone/planner/integration_'+identity);error=None;attempts=[];protected=protected_sources()
    for number in range(retries+1):
        attempt=state/('attempt_'+str(number+1));raw,receipt=invoke(make_prompt(spec,narration,style,error,constraints),attempt,timeout)
        try:result=normalize(raw,spec,narration,constraints)
        except IntegrationError as exc:
            error=str(exc);attempts.append({'attempt':number+1,'valid':False,'error':error});p.save(state/'validation.json',{'ok':False,'attempts':attempts})
            if number==retries:raise
            continue
        if p.engine.digest(scene_path)!=initial_sha:raise IntegrationError('SceneIR cambió durante segunda inferencia')
        if p.engine.digest(narration_path)!=voice_sha or p.engine.digest(original_scene_path)!=original_scene_sha or p.engine.digest(original_narration_path)!=original_narration_sha:raise IntegrationError('Origen o prefijo cambió durante dirección; no promover')
        if p.engine.digest(source_path)!=narration['source']['sha256']:raise IntegrationError('Crudo cambió durante dirección; no promover')
        if manual_sha!={name:p.engine.digest(ROOT/name)for name in manual_sha}or p.engine.digest(style_path)!=style_sha:raise IntegrationError('Manual/STYLE_YO cambió durante dirección; no atribuir aplicación retroactiva')
        if protected_sources()!=protected:raise IntegrationError('Familias/CANCELLED cambiaron durante integración; no promover')
        attempts.append({'attempt':number+1,'valid':True})
        result.update(scene_ir_path=str(scene_path.relative_to(ROOT)),scene_ir_sha256=initial_sha,narration_path=str(narration_path.relative_to(ROOT)),narration_sha256=voice_sha,source_path=str(source_path.relative_to(ROOT)),source_sha256=p.engine.digest(source_path),style_sha256=style_sha,manual_sha256=manual_sha,source_manual_sha256=source_manual_sha,protected_source_sha256=protected,integration_source_sha256=code_sha,inference={'real_inference':True,'provider_proof':str((attempt/'provider_proof.json').relative_to(ROOT)),'original_provider_proof':spec['planner']['proof'],'primary_inference_reused':scope is not None,'attempts':attempts,**{k:receipt[k]for k in ('prompt_sha256','response_sha256','schema_sha256')}})
        if provenance_path:
            provenance=p.engine.load(provenance_path);provenance['new_direction_inference']={'real_inference':True,'provider_proof':result['inference']['provider_proof']};p.save(provenance_path,provenance)
            result.update(scope_provenance_path=str(provenance_path.relative_to(ROOT)),scope_provenance_sha256=p.engine.digest(provenance_path),
                          source_scene_ir_path=str(original_scene_path.relative_to(ROOT)),source_scene_ir_sha256=original_scene_sha,
                          source_narration_path=str(original_narration_path.relative_to(ROOT)),source_narration_sha256=original_narration_sha)
        p.save(state/'integration.json',result);p.save(state/'validation.json',{'ok':True,'attempts':attempts});p.save(out_path,result)
        return result
    raise IntegrationError('No existe integración válida; sin reemplazo manual')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('scene','narration','source','out'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--timeout',type=int,default=180);parser.add_argument('--retries',type=int,default=1,choices=[0,1])
    parser.add_argument('--camera-mode',choices=['full_first','split_first']);parser.add_argument('--split-top',type=float,choices=[.5,.55]);parser.add_argument('--profile',choices=['legacy','production_complete'])
    parser.add_argument('--scope-end-frame',type=int);parser.add_argument('--max-primary',type=int,choices=[1]);parser.add_argument('--max-support',type=int,choices=[0,1])
    args=parser.parse_args();constraints={key:getattr(args,key)for key in ('camera_mode','split_top','scope_end_frame','max_primary','max_support','profile')if getattr(args,key)is not None}
    try:r=plan_for(args.scene,args.narration,args.source,args.out,args.timeout,args.retries,constraints)
    except Exception as exc:print('INTEGRATION_REJECTED: '+str(exc),file=sys.stderr);return 2
    print(json.dumps({'ok':True,'output':args.out,'camera_mode':r['camera_mode'],'split_top':r['split_top'],'frames':r['frames'],'visible_frames':r['visible_frames'],'hook_end_frame':r['hook_end_frame'],'cues':len(r['phase_cues']),'focus_windows':len(r['focus_windows']),'real_inference':True},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
