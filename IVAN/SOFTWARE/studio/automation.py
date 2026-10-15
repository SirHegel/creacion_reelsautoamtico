"""IVAN direction through a configured model, real ASR and editable SceneIR.

No semantic fallback, paid-service call without confirmation, source execution,
or inherited visual approval. Family descriptions are capabilities of this
editor's primitives; they do not import or certify upstream CLONE components.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

from . import core, analysis, scene_ir, typography
from .runtime import CODE_ROOT, MANUAL_ROOT

SCHEMA = "ascendia.ivan-plan/1"
MAX_TRACKING_RUNTIME_BYTES = 64 * 1024 ** 2
OPTIONS = {"provider", "confirmed", "instructions", "seconds", "language", "asr_model", "plan_only", "max_tokens"}
FAMILIES = {
    "apps_clone_orbit": "Duplicación conceptual de un mismo recurso gráfico y órbitas por trayectorias; no comparación entre aplicaciones distintas.",
    "cancelled": "Estado de suscripción que se cancela y transforma; cifras exclusivamente de hechos aportados; diseño propio, sin aprobación heredada.",
    "github_cards": "Evidencia de repositorio mediante paneles de texto declarados; no reputación, URLs, métricas o propietario inventados.",
    "pixel_agents": "Coordinación de roles con gráficos originales aportados; no simula personas o ejecuciones reales; píxel-art requiere recurso original.",
    "phone_recon": "Investigación conceptual de una interfaz en dispositivo 2D; campos y acciones explícitos, sin afirmar captura o aplicación real.",
    "phone_rebuild": "Transformación conectada de una interfaz conceptual 2D; no reconstrucción verificada de producto externo.",
    "phone_qa": "Comprobación conceptual de requisitos explícitos de una interfaz 2D; no pruebas ejecutadas ni calidad certificada.",
    "phone_compare": "Comparación conceptual original/reconstrucción, con diferencias declaradas; no equivalencia entre herramientas arbitrarias.",
    "spotlight_agent": "Énfasis de un rol gráfico original frente a los demás y reacción conectada; no rostro ni persona inventados.",
    "radial_research": "Investigación radial de fuentes/entidades declaradas; cifras y resultados requieren evidencia de la narración.",
    "feedback_bars": "Barras con categorías y valores explícitos; omitir cifras cuando no hay datos, nunca inventar un benchmark.",
    "problem_resolution": "Problema, acción y resolución específicos unidos por transformación y salida, con entidades causales.",
    "product_card": "Objeto/producto conceptual con información aportada; no precio, disponibilidad o características inventados.",
    "terminal_install": "Representación conceptual de pasos de instalación escritos; nunca ejecutar comandos, HTML, rutas o código recibido.",
    "agent_marquee": "Relevo/secuencia horizontal de roles originales con paso causal; no lista genérica de marcas.",
    "composition_graph": "Relaciones causales explícitas entre 2–6 entidades; únicamente si esa estructura explica mejor la frase. No fallback universal."
}


def _numbers(text):
    return set(re.findall(r'[-+]?\d+(?:[.,]\d+)*',text))


def _literal(value,text):
    return bool(re.search(r'(?<!\w)'+re.escape(value)+r'(?!\w)',text)) and _numbers(value).issubset(_numbers(text))


def _connected_motion(elements,duration,size):
    from .design import element_state
    animated=set();spatial=set();times=set()
    for element in elements:
        points={0.,duration,*[key['time'] for key in element.get('keyframes',[])]}
        if element.get('path'):points.add(duration*.5)
        states=[element_state(element,t,duration,*size) for t in sorted(points)]
        channels=('x','y','scale','opacity','rotation','mask_progress')
        for key in channels:
            if key=='mask_progress' and element.get('mask',{}).get('type','none')=='none':continue
            if max(s[key] for s in states)-min(s[key] for s in states)>1e-5:
                animated.add(element['id']);times.update(points)
                if key in {'x','y','rotation','mask_progress'}:spatial.add(element['id'])
    return len(animated)>=2 and bool(spatial) and len(times)>=3


def _closed(value, allowed, required, label):
    if not isinstance(value, dict) or set(value)-set(allowed) or set(required)-set(value):
        raise core.StudioError(f"Campos incorrectos en {label}.")
    return value


def _text(value, label, limit=2000, empty=False):
    if not isinstance(value,str) or len(value)>limit or not empty and not value.strip() or any(ord(c)<32 and c not in '\n\t' for c in value):
        raise core.StudioError(f"Texto inválido en {label}.")
    return value


def _number(value, label, low, high):
    return core.finite_number(value,label,low,high)


def validate_options(options=None):
    value = _closed(options if options is not None else {}, OPTIONS, {"provider","confirmed"}, "auto_ivan")
    from .providers import REGISTRY
    if value["confirmed"] is not True or not isinstance(value["provider"],str) or value["provider"] not in REGISTRY:
        raise core.StudioError("Confirma el uso de tu API y selecciona un proveedor configurado.",409)
    result={"provider":value["provider"],"confirmed":True,
            "instructions":_text(value.get("instructions",""),"indicaciones",12000,True),
            "seconds":_number(value.get("seconds",10),"duración de prueba",.1,10),
            "language":value.get("language","es"),"asr_model":value.get("asr_model","tiny"),
            "plan_only":value.get("plan_only",False),"max_tokens":value.get("max_tokens",8192)}
    if not isinstance(result["language"],str) or not re.fullmatch(r"[a-z]{2,3}",result["language"]):
        raise core.StudioError("Idioma ASR inválido.")
    if not isinstance(result["asr_model"],str) or result["asr_model"] not in {"tiny","base","small"} or type(result["plan_only"]) is not bool or type(result["max_tokens"]) is not int or not 1024<=result["max_tokens"]<=8192:
        raise core.StudioError("Opciones de ASR, planificación o tokens inválidas.")
    return result


def validate_prepare_options(options=None):
    fields={'instructions','seconds','language','asr_model'}
    value=_closed({} if options is None else options,fields,(), 'preparación IVAN')
    # Shared scalar validation only. This never confirms or calls an API.
    validated=validate_options({'provider':'openai','confirmed':True,**value})
    return {key:validated[key] for key in fields}


def validate_apply_options(options):
    _closed(options,{'preparation_id','expected_revision','document','agent'}, {'preparation_id','expected_revision','document','agent'},'plan externo')
    if not isinstance(options['preparation_id'],str) or not re.fullmatch(r'[0-9a-f]{24}',options['preparation_id']) or type(options['expected_revision']) is not int or options['expected_revision']<1:
        raise core.StudioError('Preparación o revisión externa inválida.')
    agent=_closed(options['agent'],{'name','model','notes'},{'name'},'declaración de agente')
    result=copy.deepcopy(options)
    result['agent']={'name':_text(agent['name'],'nombre de agente',120),
                     'model':_text(agent.get('model',''),'modelo declarado',200,True),
                     'notes':_text(agent.get('notes',''),'notas de agente',2000,True)}
    scene_ir._data_document(options['document'])
    return result


def catalog():
    inventory=MANUAL_ROOT / "sistema/clone/inventario_escenas.json"
    observed=None
    if inventory.is_file() and not inventory.is_symlink():
        observed=hashlib.sha256(inventory.read_bytes()).hexdigest()
    return {"schema":SCHEMA,"style_base":"ivan_yo_clone","families":[{"id":key,"direction":value,
             "implementation":"explicit_editable_sceneir_primitives","upstream_component_imported":False,
             "clone_fidelity":"not_reviewed","unsupported":["3D runtime", "automatic original sprite generation", "live application demo"]}
             for key,value in FAMILIES.items()],"catalog_source_sha256":observed,
             "scene_ir":scene_ir.describe_schema(),"preview_limit_seconds":10,"automatic_approval":False}


def _check(cancel):
    if cancel is not None and (cancel() if callable(cancel) else cancel.is_set()):
        raise core.StudioError("Automatización cancelada.",409)


def _parse_response(text):
    if not isinstance(text,str) or len(text.encode('utf-8'))>2*1024*1024:
        raise core.StudioError("La respuesta de dirección supera el tamaño admitido.")
    # A complete JSON fence is transport formatting, never arbitrary prose/code.
    match=re.fullmatch(r'\s*```(?:json)?\s*([\s\S]*?)\s*```\s*',text)
    if match:text=match.group(1)
    try:
        def unique(pairs):
            row={}
            for key,value in pairs:
                if key in row:raise ValueError("clave duplicada")
                row[key]=value
            return row
        return json.loads(text,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
    except (ValueError,RecursionError) as error:
        raise core.StudioError("La IA debe devolver únicamente un plan JSON cerrado y válido.") from error


def validate_plan(project, document, transcript, seconds, instructions=""):
    _number(seconds,'duración de prueba',.1,10)
    return _validate_plan(project,document,transcript,seconds,instructions)


def validate_full_plan(project,document,transcript,seconds,instructions=""):
    """Explicit full technical scope; legacy validate_plan stays <=10s."""
    _number(seconds,'duración completa',.1,600)
    return _validate_plan(project,document,transcript,seconds,instructions,maximum=600,max_scenes=500,allow_pauses=True)


def validate_chunk_plan(project,document,transcript,seconds,instructions=""):
    _number(seconds,'duración de tramo',.1,10)
    return _validate_plan(project,document,transcript,seconds,instructions,require_camera=False,allow_pauses=True)


def _validate_plan(project,document,transcript,seconds,instructions,*,maximum=10,max_scenes=30,require_camera=True,allow_pauses=False):
    """Compile a proposed timeline in memory against the canonical catalog."""
    scene_ir._data_document(document)
    _closed(document,{"schema","narrative_goal","summary","facts","scenes"},{"schema","narrative_goal","summary","facts","scenes"},"plan IVAN")
    if document["schema"]!=SCHEMA:raise core.StudioError("Versión del plan IVAN no admitida.")
    _text(document["narrative_goal"],"objetivo narrativo")
    _text(document["summary"],"dirección completa",6000)
    facts=document["facts"]
    if not isinstance(facts,list) or len(facts)>(6000 if maximum>10 else 100):raise core.StudioError("Hechos de narración inválidos.")
    text=" ".join(s["text"] for s in transcript.get("segments",[]))
    evidence=" ".join((text,instructions))
    by_fact={}
    for fact in facts:
        _closed(fact,{"id","value","quote"},{"id","value","quote"},"hecho")
        fid=_text(fact["id"],"id de hecho",100)
        value=_text(fact["value"],"valor literal",500)
        quote=_text(fact["quote"],"evidencia literal",2000)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',fid) or fid in by_fact or quote not in evidence or not _literal(value,quote):
            raise core.StudioError("Los hechos deben vincular valores literales a evidencia aportada; no inventar métricas.")
        by_fact[fid]=fact
    scenes=document["scenes"]
    if not isinstance(scenes,list) or not (2 if require_camera else 1)<=len(scenes)<=max_scenes:raise core.StudioError("Cantidad de escenas narrativas fuera del contrato.")
    result=copy.deepcopy(project)
    canonical={a['id']:a for a in core.assets()}
    referenced=set()
    for row in scenes:
        if isinstance(row,dict):
            if isinstance(row.get('asset_id'),str):referenced.add(row['asset_id'])
            ir=row.get('scene_ir')
            if isinstance(ir,dict) and isinstance(ir.get('components'),list):
                for element in ir['components']:
                    if isinstance(element,dict):
                        for key in ('asset_id','font_asset_id'):
                            if isinstance(element.get(key),str):referenced.add(element[key])
    attached={a['id']:a for a in result['assets']}
    for aid in sorted(referenced):
        item=canonical.get(aid)
        if not item or core.digest(core.confined(item['path'],must_exist=True))!=item.get('sha256'):
            raise core.StudioError('El recurso seleccionado no conserva contenido canónico vigente.',409)
        attached[aid]=copy.deepcopy(item)
    result['assets']=list(attached.values());project=result
    timeline=[];cursor=0.;face_start=None;camera_count=0
    for row in scenes:
        _closed(row,{"id","start","end","type","narration","reason","family","alternatives","phases","fact_ids","scene_ir","asset_id","source_in"}|({'pause'} if allow_pauses else set()),
                {"id","start","end","type","narration","reason","family","alternatives","phases","fact_ids"},"escena")
        sid=_text(row["id"],"id escena",100)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',sid) or any(s['id']==sid for s in timeline):raise core.StudioError("IDs de escenas inválidos.")
        start=_number(row["start"],"entrada",0,maximum);end=_number(row["end"],"salida",.1,maximum)
        if abs(start-cursor)>1e-6 or end<=start or end>seconds+1e-6:raise core.StudioError("El plan tiene huecos, solapamientos o duración fuera de la prueba.")
        kind=row["type"]
        if not isinstance(kind,str) or kind not in {"presenter","split","motion","broll"}:raise core.StudioError("Tipo narrativo no admitido.")
        if kind!='broll' and ('asset_id' in row or 'source_in' in row):
            raise core.StudioError('asset_id/source_in de escena solo seleccionan b-roll; cámara conserva el tiempo original y motion usa componentes explícitos.')
        if kind in {'presenter','broll'} and 'scene_ir' in row:
            raise core.StudioError('SceneIR pertenece a motion o región superior de split, no cámara/b-roll.')
        pause='pause' in row
        if pause:
            if row['pause'] is not True or row['narration']!='' or kind not in {'motion','broll'} or row['fact_ids']!=[]:
                raise core.StudioError('Una pausa explícita debe conservar silencio real sin narración ni hechos inventados.')
            if any(word['start']<end-1e-6 and word['end']>start+1e-6 for word in transcript.get('words',[])):
                raise core.StudioError('La pausa declarada contiene palabras reales del ASR.')
            narration=''
        else:
            narration=_text(row["narration"],"frase",4000)
            if narration not in text:raise core.StudioError("La frase de dirección debe corresponder literalmente al ASR aportado.")
        _text(row["reason"],"decisión semántica")
        if not isinstance(row["fact_ids"],list) or any(type(f) is not str or f not in by_fact for f in row["fact_ids"]):raise core.StudioError("Hechos referenciados inválidos.")
        phases=_closed(row["phases"],{"entry","action","reaction","transformation","exit"},{"entry","action","reaction","transformation","exit"},"fases conectadas")
        for phase in phases.values():_text(phase,"fase causal",1500)
        alternatives=row["alternatives"]
        if not isinstance(alternatives,list) or not 1<=len(alternatives)<=4:raise core.StudioError("Justifica al menos una familia alternativa.")
        for alternate in alternatives:
            _closed(alternate,{"family","reason"},{"family","reason"},"alternativa")
            if not isinstance(alternate["family"],str) or alternate["family"] not in FAMILIES:raise core.StudioError("Familia alternativa no disponible.")
            _text(alternate["reason"],"motivo de alternativa")
        base={"id":sid,"start":start,"end":end,"type":kind,"source_in":start,"title":"","subtitle":"","narration":narration,
              "decision":{"search":"Inventario canónico privado aportado al modelo.","reason":row["reason"],"evidence":[]},
              "status":"draft","family":row["family"],"phases":copy.deepcopy(phases),"notes":"Dirección de IA; pertinencia, diseño, continuidad y audio pendientes de revisión."}
        if pause:base['pause']=True
        if kind in {"presenter","split"}:
            camera_count+=1
            if face_start is None:face_start=start
            if end-face_start>3.00001:raise core.StudioError("El plan supera tres segundos continuos de rostro, incluido split.")
        else:face_start=None
        if kind in {"motion","split"}:
            family=row["family"]
            if not isinstance(family,str) or family not in FAMILIES or "scene_ir" not in row:raise core.StudioError("La escena motion/split necesita familia implementable y SceneIR explícito.")
            ir=copy.deepcopy(row["scene_ir"])
            if ir.get("family")!=family or abs(_number(ir.get("duration"),"duración SceneIR",.1,10)-(end-start))>1e-6:
                raise core.StudioError("Familia o duración SceneIR no coincide con su escena.")
            ir["scene_id"]=sid
            local=copy.deepcopy(project)
            if kind=="split":
                from .render import split_height
                local["settings"]["height"]=split_height(project["settings"]["height"],project['settings'].get('split_motion_ratio',.55))
            compiled=scene_ir.compile_scene_ir(local,ir)["timeline"][0]
            elements=compiled['motion_design']['elements']
            if family=='apps_clone_orbit':
                media=[e for e in elements if e['type']=='media']
                if len(media)<2 or len({e['asset_id'] for e in media})!=1 or not any(e.get('path') for e in media):
                    raise core.StudioError('La órbita de clones requiere repetir el mismo gráfico original con trayectoria editable; no comparar herramientas distintas.')
            if family in {'pixel_agents','spotlight_agent','agent_marquee'} and not any(e['type']=='media' for e in elements):
                raise core.StudioError('Esta familia requiere gráficos originales de roles aportados; no se inventan sprites o personas.')
            size=(project['settings']['width'],local['settings']['height'])
            if not _connected_motion(compiled['motion_design']['elements'],end-start,size):
                raise core.StudioError("La familia requiere transferencia/revelación y reacción entre al menos dos elementos; fades o escalas solos no demuestran acción conectada.")
            base.update(template="custom",motion_design=compiled["motion_design"],scene_ir_origin={"document":ir,"document_sha256":scene_ir.document_digest(ir),"status":"pending_qc","clone_fidelity":"not_reviewed"})
            digits=_numbers(" ".join(e.get('text','') for e in compiled['motion_design']['elements']))
            allowed=set().union(*(_numbers(by_fact[f]['value']) for f in row['fact_ids'])) if row['fact_ids'] else set()
            if not digits.issubset(allowed):raise core.StudioError("Una cifra visible carece de hecho literal exacto vinculado.")
            from .fonts import font_assets
            fonts=project['fonts'];selected=font_assets(project,core.ROOT)
            for element in base['motion_design']['elements']:
                if element['type']=='text' and typography.layout_element(element,size,fonts,selected,core.ROOT)['overflow']:
                    raise core.StudioError("El texto del plan sale de su caja; corrige tamaño y geometría antes de renderizar.")
        elif kind=="broll":
            aid=row.get("asset_id");asset=next((a for a in project['assets'] if a['id']==aid),None)
            source=next(a for a in project['assets'] if a['id']==project['source'])
            if not asset or core.source_related(asset,source,{a['id']:a for a in core.assets()}) or asset.get('kind') not in {'video','broll'}:
                raise core.StudioError("B-roll requiere un clip real canónico distinto del crudo.")
            metadata=asset.get('metadata',{})
            verification=asset.get('verification',{})
            evidence_paths=verification.get('evidence',[])
            if verification.get('visual') is not True or not metadata.get('content') or not isinstance(evidence_paths,list) or not evidence_paths or any(not isinstance(p,str) or not core.confined(p,must_exist=True).is_file() for p in evidence_paths):
                raise core.StudioError("El recurso b-roll todavía necesita inspección visual y contenido real.",409)
            entry=_number(row.get('source_in',0),'entrada recurso',0,7200)
            if entry+end-start>asset.get('duration',0)+.03:raise core.StudioError("Tramo de b-roll inexistente.")
            from .resource_review import current_review
            observed=current_review(asset)
            if observed.get('valid') is not True or observed.get('scope')!='sequence' or observed.get('coverage')!='continuous_declared' or entry<observed['interval']['start']-1e-6 or entry+end-start>observed['interval']['end']+1e-6:
                raise core.StudioError('El tramo b-roll elegido necesita una observación vigente de la secuencia completa; las fotos no acreditan movimiento.',409)
            base.update(asset_id=aid,source_in=entry)
        elif row.get('scene_ir') or row.get('asset_id'):raise core.StudioError("La cámara no admite medios visuales ocultos.")
        timeline.append(base);cursor=end
    if abs(cursor-seconds)>1e-6 or require_camera and not camera_count:raise core.StudioError("La prueba debe cubrir su intervalo y conservar una aparición auténtica del presentador.")
    result['timeline']=timeline;result.pop('mode',None);result.pop('scene_ir',None)
    result['settings']['engine']='hyperframes';result['transcript']=copy.deepcopy(transcript)
    result['stage']='ivan_draft_pending_qc';result['review']={};result.pop('full_authorization',None);result.pop('approved_export',None)
    return result


def _tracking_runtime(root):
    from . import tracking
    if tracking.capability(root)['available']:return
    shared=CODE_ROOT/tracking.RUNTIME
    manifest=tracking._runtime(CODE_ROOT)
    files={'provenance.json':hashlib.sha256((shared/'provenance.json').read_bytes()).hexdigest(),**manifest['files']}
    if sum((shared/name).stat().st_size for name in files)>MAX_TRACKING_RUNTIME_BYTES:raise core.StudioError("El runtime facial supera el presupuesto permitido de64MiB.")
    for name,expected in files.items():
        source=shared/name
        if not source.resolve().is_relative_to(shared) or hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise core.StudioError("Cambió el runtime facial compartido.",409)
        target=core.confined(root/tracking.RUNTIME/name)
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise core.StudioError("El modelo facial privado cambió; no se reemplaza.",409)
        else:
            with target.open('xb') as stream:stream.write(source.read_bytes())
    tracking._runtime(root)


def _apply_anchors(project, report):
    from .render import probe_media,split_height
    source=next(a for a in project['assets'] if a['id']==project['source'])
    info=probe_media(core.confined(source['path'],must_exist=True),core.ROOT)
    stream=next(s for s in info['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic'))
    sw,sh=stream['width'],stream['height']
    sar=stream.get('sample_aspect_ratio','1:1')
    try:a,b=map(float,sar.split(':'));sw*=a/b if a>0 and b>0 else 1
    except (ValueError,ZeroDivisionError):pass
    rotations=[s.get('rotation') for s in stream.get('side_data_list',[]) if isinstance(s,dict) and 'rotation' in s]
    rotation=float(rotations[0] if rotations else stream.get('rotation',stream.get('tags',{}).get('rotate',0)))
    if not math.isfinite(rotation) or abs(rotation/90-round(rotation/90))>.001:
        raise core.StudioError('La geometría facial requiere rotación ortogonal comprobada, no un ángulo arbitrario.',409)
    if abs(rotation)%180>45:sw,sh=sh,sw
    w,h=project['settings']['width'],project['settings']['height']
    for scene in project['timeline']:
        if scene['type'] not in {'presenter','split'}:continue
        target_h=h-split_height(h,project['settings'].get('split_motion_ratio',.55)) if scene['type']=='split' else h
        samples=[s for s in report['samples'] if scene['start']-1e-6<=s['time']<scene['end']]
        relevant=[s for s in samples if s.get('detected') is True]
        if not relevant or len(relevant)!=len(samples) or relevant[0]['time']>scene['start']+.500001 or relevant[-1]['time']<scene['end']-.500001:
            raise core.StudioError("La cámara necesita cobertura de muestras faciales reales sin huecos ni ambigüedad; no se inventa barbilla.",409)
        scale=max(w/sw,target_h/sh);scaled_h=sh*scale;scaled_w=sw*scale
        anchors=[]
        for sample in relevant:
            coords=sample['smoothed']
            fx=min(1,max(0,(coords['focus_x']*scaled_w-w*.5)/(scaled_w-w))) if scaled_w-w>1e-8 else .5
            fy=min(1,max(0,(coords['focus_y']*scaled_h-target_h*.5)/(scaled_h-target_h))) if scaled_h-target_h>1e-8 else .5
            if scene['type']=='split' and scaled_h-target_h>1e-8:
                # Move the real crop, rather than invent a chin coordinate.
                # Preserve room beneath the measured jaw for actual captions.
                fy=max(fy,min(1,max(0,(coords['chin_y']*scaled_h-target_h*.65)/(scaled_h-target_h))))
            chin=(coords['chin_y']*scaled_h-(scaled_h-target_h)*fy)/target_h
            if not 0<=chin<=.95:raise core.StudioError("La barbilla medida queda fuera del recorte; ajusta el encuadre.",409)
            anchors.append({'time':max(0,sample['time']-scene['start']),'focus_x':fx,'focus_y':fy,'chin_y':chin})
        scene['camera_anchors']=anchors;scene['focus_x']=anchors[0]['focus_x'];scene['focus_y']=anchors[0]['focus_y'];scene['chin_y']=anchors[0]['chin_y'];scene['chin_reviewed']=False
        scene['decision']['evidence']=[e['path'] for e in report['evidence']]
    project['tracking']=report
    return project


def validate_draft_receipt(project):
    record=project.get('automation')
    external=isinstance(record,dict) and record.get('source')=='external_agent_declared'
    execution_ok=isinstance(record,dict) and (record.get('inference_executed') is True if not external else record.get('inference_executed') is False and record.get('verified_external_inference') is False)
    if not execution_ok or record.get('schema')!=SCHEMA or record.get('editorial_approved') is not False or record.get('input_digest')!=core.editorial_digest(project):
        raise core.StudioError('La prueba IVAN requiere la dirección inferida vigente; una edición posterior conserva el origen y necesita una nueva prueba técnica.',409)
    if record.get('source_sha256')!=next((a['sha256'] for a in project['assets'] if a['id']==project['source']),None):
        raise core.StudioError('Cambió la fuente de la dirección IVAN.',409)
    artifacts=record.get('artifacts')
    if not isinstance(artifacts,list) or len(artifacts)!=3:raise core.StudioError('Faltan recibos de dirección IVAN.',409)
    seen=set()
    for item in artifacts:
        if not isinstance(item,dict) or set(item)!={'path','sha256'} or not isinstance(item['path'],str) or not re.fullmatch(re.escape('projects/'+project['id']+'/automation/')+r'[0-9a-f]{24}/(?:plan|transcript|inference|direction)\.json',item['path']) or item['path'] in seen:
            raise core.StudioError('Evidencia de dirección inválida.',409)
        path=core.confined(item['path'],must_exist=True)
        if path!=core.ROOT/item['path'] or core.digest(path)!=item['sha256']:
            raise core.StudioError('La evidencia de dirección cambió; no se usa un recibo alterado.',409)
        seen.add(item['path'])
    if external:
        prepared=_load_preparation(project['id'],record.get('preparation_id'))
        if prepared['identity']['source_sha256']!=record['source_sha256'] or record.get('preparation_sha256')!=prepared['_sha256']:
            raise core.StudioError('La dirección externa no conserva su preparación privada real.',409)
    return record


def voice_stream(project):
    source=next((a for a in project.get('assets',[]) if a['id']==project.get('source')),None)
    if not source:raise core.StudioError('Carga un crudo con audio antes de preparar contexto.',409)
    return analysis.select_audio_stream(analysis.probe(core.confined(source['path'],must_exist=True)),
                                        project.get('settings',{}).get('voice_audio_stream'))


def _asr_cached(project,source_sha,scope,model,language,audio_index=None):
    record=project.get('automation',{})
    if record.get('source_sha256')!=source_sha or record.get('scope_seconds')!=scope:return None
    entry=next((a for a in record.get('artifacts',[]) if isinstance(a,dict) and str(a.get('path','')).endswith('/transcript.json')),None)
    if entry is None:return None
    if not re.fullmatch(re.escape('projects/'+project['id']+'/automation/')+r'[0-9a-f]{24}/transcript\.json',str(entry.get('path',''))):
        raise core.StudioError('La transcripción previa no es evidencia privada válida.',409)
    path=core.confined(entry['path'],must_exist=True)
    if path!=core.ROOT/entry['path'] or core.digest(path)!=entry.get('sha256'):
        raise core.StudioError('Cambió la transcripción previa; no se reutiliza.',409)
    previous=json.loads(path.read_text())
    expected={k:v for k,v in model.items() if k!='path'}
    if previous.get('engine')=='faster-whisper' and previous.get('status')=='transcribed' and previous.get('local_model')==expected and previous.get('source_sha256')==source_sha and previous.get('scope_seconds')==scope and previous.get('requested_language')==language and (audio_index is None or previous.get('voice_audio_stream_index')==audio_index):
        return previous
    return None


def run(project, options, progress=None, cancel=None, *, inference=None):
    from .jobs import cpu_slot
    with cpu_slot(cancel=cancel):
        return _run(project,options,progress,cancel,inference=inference)


def _prepare_inputs(project, options, progress, cancel):
    from .media_tools import process
    from .branding import base_rules,validate_project_binding
    if core.WORKSPACE_MODE:validate_project_binding(project,core.ROOT)
    source=next((a for a in project['assets'] if a['id']==project.get('source')),None)
    if not source:raise core.StudioError("Carga un crudo con voz para automatizar IVAN.")
    path=core.confined(source['path'],must_exist=True);source_sha=core.digest(path)
    if source_sha!=source['sha256']:raise core.StudioError("Cambió el crudo original.",409)
    scope=min(options['seconds'],_number(source.get('duration'),'duración fuente',.1,7200))
    baseline=core.editorial_digest(project);manual=core.manual_fingerprints()
    local=analysis.offline_model(options['asr_model'])
    selected=voice_stream(project)
    transcript=_asr_cached(project,source_sha,scope,local,options['language'],selected['index'])
    if transcript is None:
        progress(.03,'Extrayendo voz original y preparando ASR local CPU.')
        audio=process(source,'extract_audio',{'start':0,'duration':scope,'audio_stream_index':selected['index'],'channels':1},core.ROOT)
        transcript=analysis.transcribe(audio['path'],options['asr_model'],options['language'],lambda n,m:progress(.05+n*.3,m),cancel,local_model_path=local['path'])
        transcript.update(source_sha256=source_sha,scope_seconds=scope,requested_language=options['language'],voice_audio_stream_index=selected['index'])
    _check(cancel)
    if not transcript['words']:raise core.StudioError("ASR no detectó palabras; revisa la pista antes de pagar dirección por IA.",409)
    _tracking_runtime(core.ROOT)
    from .tracking import analyze_tracking
    measured=analyze_tracking(project,{'start':0,'end':scope,'sample_fps':2},lambda n,m:progress(.33+n*.06,m),cancel)
    if not any(s.get('detected') is True for s in measured['samples']):
        raise core.StudioError('El tracking no encontró rostro utilizable; ajusta el crudo antes de solicitar dirección por IA.',409)
    context=direction_context(project,transcript,measured,scope,options['instructions'])
    return {'path':path,'source_sha':source_sha,'scope':scope,'baseline':baseline,'manual':manual,'local':local,
            'transcript':transcript,'measured':measured,'voice_stream':selected,**context}


def _brand_catalog():
    from .brand_assets import catalog
    if core.WORKSPACE_MODE:
        return catalog('private_review')
    return {'schema':'ascendia.brand-assets/1','context':'private_review','records':[],
            'digest':None,'available':False,'reason':'El registro pertenece a workspaces privados.',
            'rights_authority':False,'publication_approved':False,'editorial_approved':False}


def _library_identity():
    library=core.assets()
    value={'assets':library,'brand_registry':_brand_catalog()} if core.WORKSPACE_MODE else library
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def direction_context(project,transcript,measured,scope,instructions,*,require_camera=True):
    """Build closed planning context from actual inputs, without inference."""
    from .branding import base_rules
    source=next(a for a in project['assets'] if a['id']==project['source'])
    brand=project.get('style',{}).get('branding',{})
    library=core.assets();registry=_brand_catalog()
    identity={'assets':library,'brand_registry':registry} if core.WORKSPACE_MODE else library
    library_identity=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    from .resource_review import current_review
    inventory=[{'id':a['id'],'name':a['name'],'kind':a['kind'],'duration':a.get('duration'),
                'current_observation':current_review(a) if a['kind'] in {'image','video','broll'} else None,
                'verification':{k:a.get('verification',{}).get(k) for k in ('visual','audio','rights')},
                'metadata':{k:a.get('metadata',{}).get(k) for k in ('content','visual_reviewed','declaration_original')}}
               for a in library if not core.source_related(a,source,{a['id']:a for a in library})]
    for item in inventory:
        item['brand_references']=[]
        for record in registry['records']:
            if record.get('asset_id')!=item['id']:
                continue
            current=record.get('current',{})
            eligible=(current.get('valid') is True and current.get('visual_reviewed') is True and
                      current.get('render_ready') is True and current.get('eligible_for_context') is True)
            item['brand_references'].append({'entity':record['entity'],'asset_id':record['asset_id'],
                'sha256':record['sha256'],'context':'private_review','eligible_for_context':eligible,
                'source_verified':current.get('source_verified') is True,'image':record.get('image'),
                'observation_status':current.get('status'),'conditions':record.get('conditions'),
                'omission_reason':None if eligible else current.get('reason',current.get('status','pending_observation')),
                'original_authorship_claimed':False,'rights_authority':False,'publication_approved':False})
    from .brand_assets import origin_catalog
    prompt={'schema':SCHEMA,'seconds':scope,'settings':project['settings'],'branding':{k:brand.get(k) for k in ('colors','language','instructions')},
            'camera_measurements':{'sample_fps':2,'samples':[{'time':s['time'],'detected':s.get('detected') is True} for s in measured['samples']],
                                   'instruction':'Choose camera/split only in spans covered by detected samples; coordinates/crop will be applied from actual anchors.'},
            'instructions':instructions,'transcript':transcript,'assets':inventory,'families':catalog()['families'],
            'brand_registry':registry,'official_brand_origins':origin_catalog(),
            'scene_ir_schema':scene_ir.describe_schema(),'contract':{'root_fields':['schema','narrative_goal','summary','facts','scenes'],
            'facts':'[{id,value,quote}] only literal values present in transcript/instructions',
            'scene_fields':['id','start','end','type','narration','reason','family','alternatives','phases','fact_ids','scene_ir (motion/split)','asset_id (broll)','source_in (broll)'],
            'alternatives':'[{family,reason}]','phases':{'entry':'','action':'','reaction':'','transformation':'','exit':''},
            'split_canvas':'height=2*floor(project.height*settings.get("split_motion_ratio",0.55)/2+0.5); settings ratio0.50..0.55, fixed even regions, authentic camera below, no source in upper media',
            'text_bounds':'Use authentic roles primary/accent. font_size is pixels at REFERENCE canvas width1080, NOT output pixels:120 gives40px at360;42 gives14px. Effective type size also multiplies element/preset scale. In a narrated scene that declares text, sustain a main visible block at least48px reference (=16px at360), for min(.7s,scene duration); smaller secondary UI labels are allowed alongside it. No roles/flags override this QC. Headlines may paraphrase narration; no forced ASR token overlap. A visual-only scene may omit text when meaning supports it. Fit declared boxes, avoid clipping/microtype/unsupported glyphs; size checks do not prove human readability.',
            'face':('At least one camera/split appearance; ' if require_camera else 'Camera only when this phrase benefits; ')+ '<=3s consecutive including adjacent camera/split and neighboring chunks.',
            'numeric_text':'Only facts explicitly quoted and bound via fact_ids. No fake app metrics or claims.',
            'brand_graphics':'For an explicitly chosen brand, use media.asset_id + brand_entity from an eligible private_review brand_reference. Preserve the real raster. Omit unavailable/unobserved/SVG-only entries with the supplied reason; no invented authorship, logo, permission or publication approval. Presence in the registry does not prove semantic relevance.',
            'hook':'4–6s integrated conceptual headline/visual; do not automatically transcribe words in hook.',
            'subtitles':'Renderer adds short actual-ASR groups after hook; camera chin is measured separately.',
            'geometry':'components normalized in own canvas; actions scene-local; representation conceptual required.'}}
    system=base_rules()+"\nReturn ONLY one JSON object conforming to the supplied closed contract. Plan from full sentence meaning, compare families and supply actual editable SceneIR actions; never use keyword-template fallback or claim CLONE fidelity. The inventory may contain unreviewed or unrelated media; its presence does not prove relevance. No external URLs, shell, user-code, fabricated facts or approval."
    prompt_text=json.dumps(prompt,ensure_ascii=False,allow_nan=False)
    if len(prompt_text.encode('utf-8'))>128*1024:raise core.StudioError('El inventario y el contexto superan 128KiB; reduce el contexto antes de usar la API. No se ocultan recursos por truncado.')
    return {'library_identity':library_identity,'prompt':prompt,'prompt_text':prompt_text,'system':system}


def _run(project, options, progress=None, cancel=None, *, inference=None):
    """Compute an editable draft and immutable evidence; caller performs CAS save."""
    options=validate_options(options);progress=progress or (lambda fraction,message:None)
    _check(cancel)
    prepared=_prepare_inputs(project,options,progress,cancel)
    from .providers import Connections
    path,source_sha,scope,baseline,manual,local,transcript,measured,library_identity,prompt_text,system=tuple(prepared[k] for k in ('path','source_sha','scope','baseline','manual','local','transcript','measured','library_identity','prompt_text','system'))
    progress(.4,'Solicitando dirección narrativa con tu proveedor confirmado.')
    response=(inference or Connections(core.ROOT).infer)(options['provider'],system,prompt_text,max_tokens=options['max_tokens'])
    if not isinstance(response,dict) or response.get('inference_executed') is not True:raise core.StudioError("La dirección requiere una inferencia real confirmada; no hay fallback heurístico.",409)
    _check(cancel);document=_parse_response(response.get('text'))
    progress(.65,'Validando familias, hechos, tiempos y composición editable.')
    draft=validate_plan(project,document,transcript,scope,options['instructions'])
    draft=_apply_anchors(draft,measured)
    _check(cancel)
    if source_sha!=core.digest(path) or analysis.offline_model(options['asr_model'])!=local or manual!=core.manual_fingerprints() or baseline!=core.editorial_digest(core.get_project(project['id'])) or library_identity!=_library_identity():
        raise core.StudioError("Una entrada cambió durante la automatización; no se aplica el plan.",409)
    key=hashlib.sha256(json.dumps({'source':source_sha,'plan':document,'revision':project['revision'],'manual':manual},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
    directory=core.confined(f"projects/{project['id']}/automation/{key}");directory.mkdir(parents=True,exist_ok=True)
    artifacts=[]
    for filename,value in (('plan.json',document),('transcript.json',transcript),('inference.json',{k:v for k,v in response.items() if k!='text'})):
        destination=directory/filename
        payload=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
        if destination.exists() and destination.read_bytes()!=payload:raise core.StudioError("Evidencia de automatización ocupada; no se sobrescribe.",409)
        if not destination.exists():
            with destination.open('xb') as stream:stream.write(payload)
        artifacts.append({'path':core.relative(destination),'sha256':hashlib.sha256(payload).hexdigest()})
    draft['automation']={'schema':SCHEMA,'method':'configured_provider_inference+real_cpu_asr+explicit_sceneir',
                         'scope_seconds':scope,'source_sha256':source_sha,'inference_executed':True,'provider':response.get('provider'),
                         'model':response.get('model'),'usage':response.get('usage'),'artifacts':artifacts,'at':core.now(),
                         'tracking_applied':True,'qc':'pending','editorial_approved':False,'audio_listened':False,'clone_fidelity':'not_reviewed',
                         'voice_audio_stream':prepared['voice_stream']['index'],'limitations':['La pista seleccionada por índice global es explícita; actividad/ASR no certifican identidad de narrador.',
                         'Las anclas faciales proceden de muestras2fps; no prueban identidad, rostro ni recorte perfecto en cada fotograma.',
                         'Las familias usan primitivas2D propias y SceneIR explícito; no certifican fidelidad CLONE ni equivalencia comercial.']}
    draft['analysis']={'voice_detection':'speech_transcribed','asr_scope':[0,scope],'whole_reel_transcribed':False,'preserve_original_cuts':True}
    draft['automation']['input_digest']=core.editorial_digest(draft)
    progress(.98,'Borrador editable preparado; revisión audiovisual pendiente.')
    _check(cancel)
    return {'project':draft,'seconds':scope,'plan_only':options['plan_only'],'automation':draft['automation']}


def _preparation_path(project_id, key):
    if not isinstance(project_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',project_id) or not isinstance(key,str) or not re.fullmatch(r'[0-9a-f]{24}',key):
        raise core.StudioError('Identidad de preparación inválida.')
    relative=f'.estado/automation/preparations/{project_id}/{key}.json'
    path=core.confined(relative)
    if path!=core.ROOT/relative:raise core.StudioError('Las preparaciones no admiten alias ni rutas ajenas.',403)
    return path


def _write_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()
    if path.exists():
        if path.read_bytes()!=data:raise core.StudioError('Una evidencia ocupa esta identidad; no se reemplaza.',409)
    else:
        with path.open('xb') as output:output.write(data)
    return {'path':core.relative(path),'sha256':hashlib.sha256(data).hexdigest()}


def _tracking_reference(measured):
    path=core.confined(measured.get('path',''),must_exist=True)
    if not path.is_relative_to(core.ROOT/'projects') or not path.is_file():raise core.StudioError('Falta el recibo facial real de preparación.',409)
    return {'path':core.relative(path),'sha256':core.digest(path),'runtime_files':measured['runtime_provenance']['files']}


def _check_inputs(project,prepared,cancel=None):
    _check(cancel)
    if prepared['source_sha']!=core.digest(core.confined(next(a['path'] for a in project['assets'] if a['id']==project['source']),must_exist=True)) or analysis.offline_model(prepared['local']['model'])!=prepared['local'] or prepared['manual']!=core.manual_fingerprints() or prepared['baseline']!=core.editorial_digest(core.get_project(project['id'])) or prepared['library_identity']!=_library_identity():
        raise core.StudioError('La preparación perdió una entrada vigente; no se aplica ni aprueba.',409)
    from .tracking import _runtime
    if _runtime(core.ROOT)['files']!=prepared['measured']['runtime_provenance']['files']:
        raise core.StudioError('Cambió el runtime facial de la preparación.',409)


def _load_preparation(project_id,key):
    path=_preparation_path(project_id,key)
    marker=core.confined(path.with_suffix('.sha256'),must_exist=True)
    if marker!=path.with_suffix('.sha256') or not path.is_file() or path.stat().st_size>4*1024**2 or marker.read_text()!=core.digest(path):
        raise core.StudioError('La preparación privada cambió o perdió su comprobante.',409)
    try:record=json.loads(path.read_text())
    except (ValueError,RecursionError) as error:raise core.StudioError('Preparación privada mal formada.',409) from error
    if not isinstance(record,dict) or record.get('schema')!='ascendia.ivan-preparation/1' or record.get('preparation_id')!=key or record.get('project_id')!=project_id:
        raise core.StudioError('La preparación no pertenece al proyecto.',409)
    reference=record['identity']['tracking']
    target=core.confined(reference['path'],must_exist=True)
    if not target.is_relative_to(core.ROOT/'projects'/project_id/'tracking') or core.digest(target)!=reference['sha256']:
        raise core.StudioError('Cambió la evidencia facial de la preparación.',409)
    if record['identity'].get('engine_code')!=core.engine_fingerprints():
        raise core.StudioError('Cambió el algoritmo desde la preparación privada.',409)
    for evidence in record['tracking'].get('evidence',[]):
        path=core.confined(evidence['path'],must_exist=True)
        if not path.is_relative_to(target.parent) or path!=core.ROOT/evidence['path'] or core.digest(path)!=evidence['sha256']:
            raise core.StudioError('Cambió una muestra facial de la preparación.',409)
    record['_sha256']=core.digest(path)
    return record


def _prepare_signature(project,options):
    source=next((a for a in project['assets'] if a['id']==project.get('source')),None)
    if not source:raise core.StudioError('Carga un crudo antes de preparar contexto.')
    actual=core.digest(core.confined(source['path'],must_exist=True))
    if actual!=source['sha256']:raise core.StudioError('Cambió el crudo de preparación.',409)
    _tracking_runtime(core.ROOT)
    from .tracking import _runtime
    model=analysis.offline_model(options['asr_model'])
    value={'revision':project['revision'],'input_digest':core.editorial_digest(project),'options':options,
           'voice_audio_stream_index':voice_stream(project)['index'],
           'source_sha256':actual,'manual':core.manual_fingerprints(),'engine_code':core.engine_fingerprints(),
           'model':{k:v for k,v in model.items() if k!='path'},'tracking_runtime':_runtime(core.ROOT)['files'],
           'library_sha256':_library_identity()}
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def ivan_prepare(project,options=None,progress=None,cancel=None):
    """Real CPU inputs and scoped context for an externally connected director."""
    from .jobs import cpu_slot
    options=validate_prepare_options(options);progress=progress or (lambda n,m:None)
    with cpu_slot(cancel=cancel):
        signature=_prepare_signature(project,options)
        index=core.confined(f'.estado/automation/preparations/{project["id"]}/current.json')
        if index!=core.ROOT/f'.estado/automation/preparations/{project["id"]}/current.json':raise core.StudioError('Índice de preparación no canónico.',403)
        cached=core.read_json(index,None)
        if isinstance(cached,dict) and cached.get('signature')==signature:
            record=_load_preparation(project['id'],cached.get('preparation_id'))
            _check(cancel)
            if _prepare_signature(project,options)!=signature:raise core.StudioError('Una entrada cambió al reutilizar preparación.',409)
            if record['identity'].get('prepare_signature')!=signature:raise core.StudioError('Preparación previa incompatible.',409)
            progress(1,'Contexto real reutilizado sin repetir ASR ni inferencia facial.')
            return {k:v for k,v in record.items() if not k.startswith('_')}
        prepared=_prepare_inputs(project,options,progress,cancel)
        _check_inputs(project,prepared,cancel)
        identity={'revision':project['revision'],'input_digest':prepared['baseline'],'source_sha256':prepared['source_sha'],
                  'voice_audio_stream_index':prepared['voice_stream']['index'],
                  'engine_code':core.engine_fingerprints(),'prepare_signature':signature,
                  'manual':prepared['manual'],'library_sha256':prepared['library_identity'],
                  'asr_model':{k:v for k,v in prepared['local'].items() if k!='path'},
                  'tracking':_tracking_reference(prepared['measured'])}
        key=hashlib.sha256(json.dumps({'identity':identity,'options':options},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
        path=_preparation_path(project['id'],key)
        if path.exists():
            existing=_load_preparation(project['id'],key)
            if existing['identity']!=identity or existing['options']!=options:raise core.StudioError('Preparación previa incompatible.',409)
            return {k:v for k,v in existing.items() if not k.startswith('_')}
        context={'system':prepared['system'],'input':prepared['prompt'],
                 'direction_source':'external_agent_declared','inference_executed':False,'verified_external_inference':False,
                 'notice':'El software ejecutó ASR y tracking; nombre/modelo del agente serán declaraciones del cliente, sin prueba de inferencia externa ni uso API.'}
        record={'schema':'ascendia.ivan-preparation/1','preparation_id':key,'project_id':project['id'],'revision':project['revision'],
                'identity':identity,'options':options,'context':context,'scope_seconds':prepared['scope'],
                'transcript':prepared['transcript'],'tracking':prepared['measured'],'prepared_at':core.now(),
                'inference_executed':False,'editorial_approved':False,'audio_listened':False,'source':'external_agent_declared'}
        _check(cancel);proof=_write_new(path,record)
        marker=path.with_suffix('.sha256')
        if marker.exists():raise core.StudioError('El comprobante de preparación ya existe sin evidencia compatible.',409)
        with marker.open('x') as output:output.write(proof['sha256'])
        _check_inputs(project,prepared,cancel)
        if _prepare_signature(project,options)!=signature:raise core.StudioError('Una entrada cambió antes de confirmar preparación.',409)
        core.atomic_json(index,{'signature':signature,'preparation_id':key})
        progress(1,'Contexto real preparado; dirección externa y QC pendientes.')
        return record


def ivan_apply_plan(project,options,progress=None,cancel=None):
    """Validate external direction and return an editable copy for caller CAS."""
    from .jobs import cpu_slot
    options=validate_apply_options(options);progress=progress or (lambda n,m:None)
    with cpu_slot(cancel=cancel):
        _check(cancel)
        record=_load_preparation(project['id'],options['preparation_id'])
        identity=record['identity']
        if project['revision']!=options['expected_revision'] or project['revision']!=identity['revision']:
            raise core.StudioError('El proyecto cambió desde la preparación; vuelve a preparar contexto.',409)
        local=analysis.offline_model(record['options']['asr_model'])
        if {k:v for k,v in local.items() if k!='path'}!=identity['asr_model']:
            raise core.StudioError('Cambió el modelo ASR de la preparación.',409)
        prepared={'source_sha':identity['source_sha256'],'baseline':identity['input_digest'],'manual':identity['manual'],
                  'library_identity':identity['library_sha256'],'local':local,'measured':record['tracking']}
        _check_inputs(project,prepared,cancel)
        progress(.25,'Validando dirección declarada y SceneIR frente a las entradas reales.')
        draft=validate_plan(project,options['document'],record['transcript'],record['scope_seconds'],record['options']['instructions'])
        draft=_apply_anchors(draft,record['tracking'])
        _check_inputs(project,prepared,cancel)
        key=hashlib.sha256(json.dumps({'preparation':record['_sha256'],'document':options['document'],'agent':options['agent']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
        folder=core.confined(f'projects/{project["id"]}/automation/{key}')
        direction={'source':'external_agent_declared','agent':options['agent'],'preparation_id':options['preparation_id'],
                   'preparation_sha256':record['_sha256'],'inference_executed':False,'verified_external_inference':False}
        artifacts=[_write_new(folder/name,value) for name,value in (('plan.json',options['document']),('transcript.json',record['transcript']),('direction.json',direction))]
        draft['automation']={'schema':SCHEMA,'source':'external_agent_declared','method':'external_agent_declared+real_cpu_asr+explicit_sceneir',
                             'scope_seconds':record['scope_seconds'],'source_sha256':identity['source_sha256'],'agent':options['agent'],
                             'preparation_id':options['preparation_id'],'preparation_sha256':record['_sha256'],
                             'inference_executed':False,'verified_external_inference':False,'artifacts':artifacts,'at':core.now(),
                             'tracking_applied':True,'qc':'pending','editorial_approved':False,'audio_listened':False,'clone_fidelity':'not_reviewed','voice_audio_stream':identity['voice_audio_stream_index']}
        draft['analysis']={'voice_detection':'speech_transcribed','asr_scope':[0,record['scope_seconds']],'whole_reel_transcribed':False,'preserve_original_cuts':True}
        draft['automation']['input_digest']=core.editorial_digest(draft)
        _check_inputs(project,prepared,cancel);validate_draft_receipt(draft)
        progress(1,'Plan externo editable validado; sin aprobación audiovisual ni inferencia API atribuida.')
        return {'project':draft,'seconds':record['scope_seconds'],'plan_only':False,'automation':draft['automation']}
