"""Durable private full-reel orchestration. Technical success never approves art.

All media/model work uses the existing CPU engines. An external agent supplies
closed plans, not executable code; its model/name remain client declarations.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import zipfile
from contextlib import contextmanager

from . import core, analysis, automation

SCHEMA='ascendia.pipeline/1'
STAGES=('asr','tracking','context','direction','compile','qc','commit','render','export')
MAX_STATE_BYTES=8*1024**2


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def validate_options(options=None):
    value=automation._closed({} if options is None else options,
        {'mode','channel','provider','confirmed','instructions','asr_model','language','max_tokens','max_repairs'},
        {'mode','channel'},'pipeline completo')
    if value['mode']!='full' or value['channel'] not in ('api','external'):
        raise core.StudioError('Selecciona explícitamente modo full y canal api o external.')
    if value['channel']=='api':
        checked=automation.validate_options({'provider':value.get('provider'),'confirmed':value.get('confirmed'),
            **{k:v for k,v in value.items() if k in {'instructions','asr_model','language','max_tokens'}}})
    else:
        if 'provider' in value or 'confirmed' in value:
            raise core.StudioError('El canal externo no usa confirmación de costo ni una conexión API.')
        checked=automation.validate_options({'provider':'openai','confirmed':True,
            **{k:v for k,v in value.items() if k in {'instructions','asr_model','language','max_tokens'}}})
    repairs=value.get('max_repairs',2)
    if type(repairs) is not int or not 0<=repairs<=2:raise core.StudioError('max_repairs debe ser entero entre 0 y 2.')
    out={k:checked[k] for k in ('instructions','asr_model','language','max_tokens')}
    out.update(mode='full',channel=value['channel'],max_repairs=repairs)
    if value['channel']=='api':out.update(provider=checked['provider'],confirmed=True)
    return out


def _path(project_id,name=None):
    if not isinstance(project_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',project_id):
        raise core.StudioError('ID de pipeline inválido.')
    relative=f'.estado/pipelines/{project_id}.json' if name is None else f'.estado/pipelines/{project_id}/{name}'
    if name is not None and not re.fullmatch(r'(?:asr|tracking|context|direction|compile|qc|commit|render|export|cancel|plan_\d{3}|inference_\d{3}|attempt_\d{3}|lock)\.(?:json|lock)',name):
        raise core.StudioError('Nombre de evidencia de pipeline no admitido.',403)
    path=core.confined(relative)
    if path!=core.ROOT/relative:raise core.StudioError('El pipeline no admite alias ni rutas ajenas.',403)
    return path


@contextmanager
def _lock(project_id):
    path=_path(project_id,'lock.lock');path.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'a+b') as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def _write(state):
    state['updated_at']=core.now()
    if len(json.dumps(state,ensure_ascii=False,allow_nan=False).encode())>MAX_STATE_BYTES:
        raise core.StudioError('El estado del pipeline supera el límite permitido.',413)
    core.atomic_json(_path(state['project_id']),state)


def _read(project_id):
    path=_path(project_id)
    if not path.is_file():raise core.StudioError('Este proyecto aún no tiene un pipeline.',404)
    if path.stat().st_size>MAX_STATE_BYTES:raise core.StudioError('Estado de pipeline demasiado grande.',413)
    try:state=json.loads(path.read_text())
    except (ValueError,RecursionError) as error:raise core.StudioError('Estado de pipeline inválido.',409) from error
    if not isinstance(state,dict) or state.get('schema')!=SCHEMA or state.get('project_id')!=project_id:
        raise core.StudioError('El pipeline no pertenece al proyecto.',409)
    return state


def _artifact(state,name,value,signature=None):
    path=_path(state['project_id'],name+'.json')
    core.atomic_json(path,{'schema':SCHEMA,'generation':state['generation'],'signature':signature,'value':value})
    return {'path':core.relative(path),'sha256':core.digest(path),'signature':signature}


def _value(state,entry):
    if not isinstance(entry,dict) or set(entry)!={'path','sha256','signature'}:
        raise core.StudioError('Referencia de pipeline inválida.',409)
    path=core.confined(entry['path'],must_exist=True)
    if path.parent!=_path(state['project_id'],'asr.json').parent or path!=core.ROOT/entry['path']:
        raise core.StudioError('Cambió la evidencia del pipeline; no se reutiliza.',409)
    if path.stat().st_size>MAX_STATE_BYTES:raise core.StudioError('Evidencia de pipeline demasiado grande.',413)
    payload=path.read_bytes()
    if len(payload)>MAX_STATE_BYTES or hashlib.sha256(payload).hexdigest()!=entry['sha256']:
        raise core.StudioError('Cambió la evidencia del pipeline; no se reutiliza.',409)
    try:
        record=json.loads(payload)
        if not isinstance(record,dict) or record.get('schema')!=SCHEMA or record.get('signature')!=entry['signature'] or 'value' not in record:
            raise ValueError('contrato')
        return record['value']
    except (ValueError,TypeError,RecursionError) as error:
        raise core.StudioError('La evidencia pertenece a otra entrada o está malformada.',409) from error


def _source(project):
    if not project.get('source'):raise core.StudioError('Primero adjunta el crudo original al proyecto.',409)
    source=core.asset(project.get('source'))
    path=core.confined(source['path'],must_exist=True)
    if source['kind'] not in ('video','broll') or core.digest(path)!=source['sha256']:
        raise core.StudioError('El pipeline requiere un crudo canónico íntegro.',409)
    if core.source_background_removed(source,{asset['id']:asset for asset in core.assets()}):
        raise core.StudioError('La cámara IVAN requiere el crudo auténtico con su fondo original.',409)
    info=analysis.probe(path)
    try:duration=float(info['format']['duration'])
    except (KeyError,ValueError,TypeError):duration=0
    if not math.isfinite(duration) or not .1<=duration<=600:
        raise core.StudioError('El pipeline completo admite fuentes reales de hasta600s.',409)
    selected=analysis.select_audio_stream(info,project.get('settings',{}).get('voice_audio_stream'))
    return source,path,duration,selected


def _identity(project,options):
    if not core.WORKSPACE_MODE:raise core.StudioError('Los pipelines completos pertenecen exclusivamente a espacios privados del multiservicio.',409)
    from .branding import validate_project_binding
    validate_project_binding(project,core.ROOT)
    source,path,duration,selected=_source(project)
    local=analysis.offline_model(options['asr_model'])
    automation._tracking_runtime(core.ROOT)
    from .tracking import _runtime
    runtime=_runtime(core.ROOT)
    from .brand_assets import catalog as brand_catalog
    identity={'source_id':source['id'],'source_sha256':source['sha256'],'duration':duration,
              'voice_audio_stream':selected['index'],'branding':project.get('style',{}).get('branding'),
              'settings':{**project['settings'],'voice_audio_stream':selected['index'],'engine':'hyperframes'},'manual':core.manual_fingerprints(),'engine':core.engine_fingerprints(),
              'library_sha256':_hash(core.assets()),'model':{k:v for k,v in local.items() if k!='path'},
              'tracking_runtime':runtime['files'],'brand_registry_sha256':_hash(brand_catalog('private_review'))}
    return identity,local


def create(project_id,options=None,*,restart=False):
    """Create one canonical pipeline; restart is explicit and preserves history."""
    if type(restart) is not bool:raise core.StudioError('restart debe ser booleano.')
    options=validate_options(options)
    from .jobs import cpu_slot
    with cpu_slot(),_lock(project_id):
        project=core.get_project(project_id);identity,_=_identity(project,options)
        existing=_read(project_id) if _path(project_id).exists() else None
        if existing and not restart and existing['options']==options and existing['identity']==identity and existing['project_revision']==project['revision']:
            return _public(existing)
        if existing and not restart:raise core.StudioError('El pipeline previo tiene otra entrada; reinicia explícitamente para conservar la trazabilidad.',409)
        history=existing.get('history',[]) if existing else []
        if existing:history=[*history,{'generation':existing['generation'],'status':existing['status'],'identity_sha256':_hash(existing['identity']),'at':core.now()}][-20:]
        state={'schema':SCHEMA,'project_id':project_id,'generation':existing['generation']+1 if existing else 1,
               'project_revision':project['revision'],'initial_editorial_digest':core.editorial_digest(project),
               'identity':identity,'identity_sha256':_hash(identity),'options':options,'scope_seconds':identity['duration'],
               'status':'ready','stage':'asr','stages':{},'history':history,'chunks':[],
               'inference_calls':0,'inference_attempts':0,'max_inference_calls':math.ceil(identity['duration']/10)+options['max_repairs'],
               'repairs_used':0,'inference_history':[],'editorial_approved':False,'audio_listened':False,'technical_only':True,'created_at':core.now()}
        # Successful source-specific analysis survives a context-only restart.
        if existing:
            for name in ('asr','tracking'):
                entry=existing.get('stages',{}).get(name)
                if entry and entry.get('signature')==_signature(state,name):
                    _value(existing,entry['output']);state['stages'][name]=copy.deepcopy(entry)
        _write(state);return _public(state)


def _signature(state,name):
    identity=state['identity']
    common={'source':identity['source_sha256'],'duration':identity['duration']}
    if name=='asr':common.update(index=identity['voice_audio_stream'],model=identity['model'],language=state['options']['language'],code=identity['engine']['analysis.py'])
    elif name=='tracking':common.update(runtime=identity['tracking_runtime'],code=identity['engine']['tracking.py'])
    else:common.update(identity=state['identity_sha256'],options=state['options'],generation=state['generation'])
    return _hash(common)


def _public(state,include_context=False):
    result=copy.deepcopy(state)
    if include_context:
        for chunk in result.get('chunks',[]):
            if chunk.get('plan'):
                document=_value(state,chunk['plan'])
                if not isinstance(document,dict) or document.get('schema')!=automation.SCHEMA:
                    raise core.StudioError('El documento actual del tramo no conserva su contrato.',409)
                chunk['current_plan']=document
        qc=_cached(state,'qc')
        if qc is not None:
            if not isinstance(qc,dict) or type(qc.get('ok')) is not bool or not isinstance(qc.get('issues'),list) or qc.get('editorial_approved') is not False or qc.get('audio_listened') is not False:
                raise core.StudioError('El informe QC no conserva su contrato técnico.',409)
            result['qc']=qc
    else:
        result.pop('qc',None)
        for chunk in result.get('chunks',[]):
            chunk.pop('context',None);chunk.pop('current_plan',None)
    result['automatic_editorial_approval']=False
    result['pending_review']=['Visual and temporal editorial review','Perceptual audio listening','Publication rights when applicable']
    return result


def status(project_id,include_context=False):
    if type(include_context) is not bool:raise core.StudioError('include_context debe ser booleano.')
    return _public(_read(project_id),include_context)


def cancel(project_id,generation):
    state=_read(project_id)
    if type(generation) is not int or generation!=state['generation']:raise core.StudioError('Generación de pipeline obsoleta.',409)
    core.atomic_json(_path(project_id,'cancel.json'),{'generation':generation,'requested':True})
    return {**_public(state),'cancel_requested':True}


class _Cancellation:
    def __init__(self,state,supplied):self.state=state;self.supplied=supplied
    def is_set(self):
        if self.supplied is not None and (self.supplied() if callable(self.supplied) else self.supplied.is_set()):return True
        request=core.read_json(_path(self.state['project_id'],'cancel.json'),{})
        return request.get('generation')==self.state['generation'] and request.get('requested') is True


def _current(state,project):
    if project['revision']!=state['project_revision']:raise core.StudioError('El proyecto cambió; el pipeline no puede aplicar una entrada obsoleta.',409)
    identity,_=_identity(project,state['options'])
    if identity!=state['identity']:raise core.StudioError('Cambió fuente, branding, voz, manual, modelo, biblioteca o código; reinicia el pipeline.',409)
    expected=state.get('committed_editorial_digest',state['initial_editorial_digest'])
    if core.editorial_digest(project)!=expected:raise core.StudioError('El montaje cambió desde el pipeline.',409)


def _stage(state,name,value):
    signature=_signature(state,name)
    state['stages'][name]={'status':'complete','signature':signature,'output':_artifact(state,name,value,signature),'at':core.now()}
    state['stage']=name;_write(state)
    return value


def _cached(state,name):
    entry=state['stages'].get(name)
    if not entry:return None
    if entry.get('signature')!=_signature(state,name):return None
    return _value(state,entry['output'])


def _asr(state,project,progress,cancel):
    cached=_cached(state,'asr')
    if cached is not None:return cached
    source,path,_,_= _source(project)
    local=analysis.offline_model(state['options']['asr_model'])
    result=analysis.transcribe(path,state['options']['asr_model'],state['options']['language'],progress,cancel,
        local_model_path=local['path'],audio_stream_index=state['identity']['voice_audio_stream'])
    if not result.get('words'):raise core.StudioError('ASR no detectó palabras en la pista elegida; no se cobra dirección por IA.',409)
    result.update(source_sha256=source['sha256'],scope_seconds=state['scope_seconds'],voice_audio_stream_index=state['identity']['voice_audio_stream'])
    return _stage(state,'asr',result)


def _tracking(state,project,progress,cancel):
    cached=_cached(state,'tracking')
    if cached is not None:
        _verify_tracking(cached)
        return cached
    from .tracking import analyze_tracking
    duration=state['scope_seconds'];samples=[];evidence=[];reports=[];runtime_files=None
    for start in range(0,math.ceil(duration),120):
        automation._check(cancel)
        report=analyze_tracking(project,{'start':start,'end':min(duration,start+120),'sample_fps':2,'max_samples':240},progress,cancel)
        samples.extend(report['samples']);evidence.extend(report['evidence'])
        reports.append({'path':report['path'],'sha256':core.digest(core.confined(report['path'],must_exist=True))})
        runtime_files=report['runtime_provenance']['files']
    if not any(item.get('detected') is True for item in samples):raise core.StudioError('No hay rostro medido utilizable para el estilo IVAN; no se inventa cámara.',409)
    return _stage(state,'tracking',{'samples':samples,'evidence':evidence,'reports':reports,
                                   'runtime_provenance':{'files':runtime_files},'reviewed':False,'sample_fps':2})


def _verify_tracking(value):
    if not isinstance(value,dict) or not isinstance(value.get('reports'),list) or not value['reports'] or not isinstance(value.get('evidence'),list):
        raise core.StudioError('Faltan mediciones faciales completas del pipeline.',409)
    for ref in [*value['reports'],*value['evidence']]:
        if not isinstance(ref,dict):raise core.StudioError('Referencia facial inválida.',409)
        _verify_output(ref)


def _chunks(state,transcript,tracking,project):
    if state['chunks']:return
    duration=state['scope_seconds'];start=0.;index=0
    while start<duration-1e-6:
        end=min(duration,start+10)
        if 0<duration-end<.1:end=duration-.1
        words=[{**word,'start':max(0,word['start']-start),'end':min(end-start,word['end']-start)}
               for word in transcript['words'] if word['start']<end and word['end']>start]
        local={**transcript,'words':words,'segments':[{'start':0,'end':end-start,'text':' '.join(word['word'] for word in words)}]}
        measured={**tracking,'samples':[{**item,'time':item['time']-start} for item in tracking['samples'] if start<=item['time']<end]}
        context=automation.direction_context(project,local,measured,end-start,state['options']['instructions'],require_camera=False)
        context['prompt'].update(full_scope_seconds=duration,chunk_global_start=start,
                                full_narrative_text=' '.join(word['word'] for word in transcript['words']))
        context['prompt']['pause_contract']='A real interval without ASR words can use pause:true with narration:"", no facts, and explicitly justified motion/broll. Never invent spoken words.'
        if len(json.dumps(context['prompt'],ensure_ascii=False).encode())>128*1024:raise core.StudioError('Contexto completo demasiado grande; no se trunca silenciosamente.',413)
        state['chunks'].append({'id':f'c_{index:03}','start':start,'end':end,'transcript':local,'context':{'system':context['system'],'input':context['prompt']},'status':'waiting_plan'})
        start=end;index+=1
    _stage(state,'context',{'chunk_count':len(state['chunks']),'full_narrative_text_included':True})


def _chunk_document(state,chunk,project,document):
    duration=chunk['end']-chunk['start']
    automation.validate_chunk_plan(project,document,chunk['transcript'],duration,state['options']['instructions'])
    return document


def submit_external_plan(project_id,body):
    """Only closed data is accepted; supplied agent metadata is not API proof."""
    automation._closed(body,{'generation','chunk_id','expected_revision','document','agent'},
                       {'generation','chunk_id','expected_revision','document','agent'},'plan de pipeline externo')
    if type(body['generation']) is not int or type(body['expected_revision']) is not int or not isinstance(body['chunk_id'],str):
        raise core.StudioError('Generación/revisión/tramo externos inválidos.')
    agent=automation.validate_apply_options({'preparation_id':'0'*24,'expected_revision':body['expected_revision'],
                                            'document':body['document'],'agent':body['agent']})['agent']
    from .jobs import cpu_slot
    with cpu_slot(),_lock(project_id):
        state=_read(project_id);project=core.get_project(project_id);_current(state,project)
        if state['options']['channel']!='external' or body['generation']!=state['generation'] or body['expected_revision']!=state['project_revision']:
            raise core.StudioError('Canal o generación del plan externo no vigente.',409)
        chunk=next((item for item in state['chunks'] if item['id']==body['chunk_id']),None)
        if chunk is None:raise core.StudioError('Primero prepara los contextos del pipeline y elige un tramo real.',409)
        document=_chunk_document(state,chunk,project,body['document'])
        if chunk.get('plan'):
            if _value(state,chunk['plan'])==document:return _public(state)
            if state.get('committed_editorial_digest'):raise core.StudioError('Un plan ya aplicado no se reemplaza silenciosamente.',409)
        suffix=chunk['id'][2:]
        chunk['plan']=_artifact(state,'plan_'+suffix,document,_hash({'generation':state['generation'],'chunk':chunk['id']}))
        chunk['inference']=_artifact(state,'inference_'+suffix,{'source':'external_agent_declared','agent':agent,
            'inference_executed':False,'verified_external_inference':False,'at':core.now()},_signature(state,'direction'))
        # An unapplied correction replaces the direction, never cached QC of it.
        for name in ('direction','compile','qc'):state['stages'].pop(name,None)
        chunk['context']['input'].pop('repair_issues',None)
        chunk['status']='planned';state['status']='ready';_write(state)
        return _public(state)


def _direction(state,project,infer,progress,cancel):
    from .providers import Connections
    for index,chunk in enumerate(state['chunks']):
        automation._check(cancel)
        if chunk.get('plan'):
            _chunk_document(state,chunk,project,_value(state,chunk['plan']));_value(state,chunk['inference']);continue
        if state['options']['channel']=='external':
            state.update(status='waiting_external',stage='direction');_write(state);return False
        request=copy.deepcopy(chunk['context']['input'])
        request['full_reel_camera_contract']='At least one authentic camera/split appearance across the full reel; never >3s contiguous, including neighboring chunks.'
        if index and state['chunks'][index-1].get('plan'):
            request['previous_scene']=_value(state,state['chunks'][index-1]['plan'])['scenes'][-1]
        while True:
            _current(state,core.get_project(state['project_id']));automation._check(cancel)
            if state['inference_attempts']>=state['max_inference_calls']:raise core.StudioError('El pipeline alcanzó su presupuesto de intentos de IA.',409)
            state['inference_attempts']+=1;_write(state)
            response=(infer or Connections(core.ROOT).infer)(state['options']['provider'],chunk['context']['system'],
                             json.dumps(request,ensure_ascii=False,allow_nan=False),max_tokens=state['options']['max_tokens'])
            if not isinstance(response,dict) or response.get('inference_executed') is not True:
                raise core.StudioError('No hay inferencia API confirmada; no se utiliza un fallback ficticio.',409)
            state['inference_calls']+=1
            proof={k:v for k,v in response.items() if k!='text'}
            proof.update(chunk_id=chunk['id'],response_text_sha256=hashlib.sha256(str(response.get('text','')).encode()).hexdigest(),accepted=False)
            try:
                automation._check(cancel)
                document=_chunk_document(state,chunk,project,automation._parse_response(response.get('text')))
            except core.StudioError as error:
                proof['error']=str(error)
                state['inference_history'].append(_artifact(state,f'attempt_{state["inference_attempts"]:03}',proof,_signature(state,'direction')))
                _write(state);automation._check(cancel)
                if state['repairs_used']>=state['options']['max_repairs']:raise
                state['repairs_used']+=1
                request['validation_repair']={'error':str(error),'instruction':'Correct the closed JSON/data errors without changing the source facts or clock.'}
                _write(state);continue
            proof['accepted']=True
            state['inference_history'].append(_artifact(state,f'attempt_{state["inference_attempts"]:03}',proof,_signature(state,'direction')))
            _write(state);break
        suffix=chunk['id'][2:]
        chunk['plan']=_artifact(state,'plan_'+suffix,document,_hash({'generation':state['generation'],'chunk':chunk['id']}))
        chunk['inference']=_artifact(state,'inference_'+suffix,{k:v for k,v in response.items() if k!='text'},_signature(state,'direction'))
        chunk['status']='planned';_write(state)
        progress((index+1)/len(state['chunks']),'Dirección real del tramo '+chunk['id']+' conservada.')
    _stage(state,'direction',{'chunk_count':len(state['chunks']),'channel':state['options']['channel'],
                             'inference_calls':state['inference_calls'],'external_inference_verified':False})
    return True


def _merged(state):
    document={'schema':automation.SCHEMA,'narrative_goal':'Narración completa dirigida por tramos semánticos explícitos.',
              'summary':'Montaje completo editable; cada tramo conserva su dirección y su origen de inferencia.','facts':[],'scenes':[]}
    for chunk in state['chunks']:
        plan=_value(state,chunk['plan']);prefix=chunk['id']+'_'
        def identifier(value):return prefix+value if len(prefix+value)<=100 else prefix+hashlib.sha256(value.encode()).hexdigest()[:32]
        document['facts'].extend([{**fact,'id':identifier(fact['id'])} for fact in plan['facts']])
        for original in plan['scenes']:
            row=copy.deepcopy(original);row['id']=identifier(row['id'])
            row['start']+=chunk['start'];row['end']+=chunk['start']
            row['fact_ids']=[identifier(fid) for fid in row['fact_ids']]
            document['scenes'].append(row)
    return document


def _scene_narrated(project,scene):
    """Validated direction or real ASR overlap; not a text/ASR token match."""
    if isinstance(scene.get('narration'),str) and scene['narration'].strip():return True
    transcript=project.get('transcript',{})
    words=transcript.get('words',[])
    entries=words if words else transcript.get('segments',[])
    return any(isinstance(item.get('word',item.get('text')),str) and item.get('word',item.get('text')).strip()
               and item['start']<scene['end'] and item['end']>scene['start'] for item in entries)


def _text_on_canvas(layout,pose,text_pose,width,height):
    """Conservative ink-rectangle proxy, not rendered-pixel readability."""
    bounds=layout.get('ink_bounds')
    if not bounds or bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:return False
    bw,bh=layout['width'],layout['height'];inner=text_pose['scale'];k=width/1080
    xs=[(x-bw/2)*inner+bw/2+text_pose['x']*k for x in (bounds[0],bounds[2])]
    ys=[(y-bh/2)*inner+bh/2+text_pose['y']*k for y in (bounds[1],bounds[3])]
    area=(xs[1]-xs[0])*(ys[1]-ys[0])
    visible=max(0,min(bw,xs[1])-max(0,xs[0]))*max(0,min(bh,ys[1])-max(0,ys[0]))
    if area<=0 or visible/area<.95:return False
    angle=math.radians(pose['rotation']);co,si=math.cos(angle),math.sin(angle)
    center=(pose['x']*width+bw/2,pose['y']*height+bh/2)
    points=[(center[0]+((x-bw/2)*co-(y-bh/2)*si)*pose['scale'],
             center[1]+((x-bw/2)*si+(y-bh/2)*co)*pose['scale']) for x in xs for y in ys]
    left,top=min(p[0] for p in points),min(p[1] for p in points)
    right,bottom=max(p[0] for p in points),max(p[1] for p in points)
    area=(right-left)*(bottom-top)
    visible=max(0,min(width,right)-max(0,left))*max(0,min(height,bottom)-max(0,top))
    return area>0 and visible/area>=.95


def _longest_support(support):
    longest=streak=0.;previous_end=-1.
    for index,seconds in enumerate(support):
        at=index/10
        if seconds<=0:
            streak=0.;previous_end=-1.;continue
        streak=streak+seconds if abs(at-previous_end)<1e-6 else seconds
        longest=max(longest,streak);previous_end=at+seconds
    return round(longest,6)


def quality_control(project):
    """Deterministic text geometry/dwell; no claimed perceptual evaluation."""
    from .design import element_state
    from .fonts import font_assets
    from .render import split_height
    selected=font_assets(project,core.ROOT);issues=[];rows=[];rights=[];narrative_rows=[]
    for scene in project['timeline']:
        if scene['type'] not in ('motion','split'):continue
        width=project['settings']['width'];height=split_height(project['settings']['height'],project['settings'].get('split_motion_ratio',.55)) if scene['type']=='split' else project['settings']['height']
        duration=scene['end']-scene['start'];texts=[element for element in scene['motion_design']['elements'] if element['type']=='text']
        boxes={};samples=math.ceil(duration*10)
        minimum_px=48*width/1080;principal_support=[0.]*samples;maximum_visible_px=0.
        for element in texts:
            layout=automation.typography.layout_element(element,(width,height),project['fonts'],selected,core.ROOT)
            if layout['overflow']:issues.append({'scene_id':scene['id'],'element_id':element['id'],'code':'text_overflow'})
            visible=[]
            for index in range(samples):
                time=index/10
                pose=element_state(element,time,duration,width,height)
                text_pose=automation.typography.animation_state(element,time,duration,layout)
                start,end=element.get('start',0),element.get('end',duration)
                readable=start<=time<end and pose['opacity']*text_pose['opacity']>=.9 and pose['mask_progress']*text_pose['wipe']>=.9 and text_pose['reveal_fraction']>=1-1e-8
                visible.append(readable)
                if (readable and element.get('text','').strip() and not layout['overflow'] and
                        _text_on_canvas(layout,pose,text_pose,width,height)):
                    effective=element.get('font_size',84)*width/1080*pose['scale']*text_pose['scale']
                    maximum_visible_px=max(maximum_visible_px,effective)
                    if effective+1e-8>=minimum_px:
                        principal_support[index]=max(principal_support[index],min(.1,duration-time,end-time))
                if readable:
                    x,y=pose['x']*width,pose['y']*height
                    bw,bh=element['width']*width,element['height']*height
                    boxes.setdefault(index,[]).append((element['id'],x,y,bw,bh))
            longest=streak=0
            for visible_now in visible:
                streak=streak+1 if visible_now else 0;longest=max(longest,streak)
            interval=element.get('end',duration)-element.get('start',0)
            required=min(.7,interval)
            if longest/10+.100001<required:issues.append({'scene_id':scene['id'],'element_id':element['id'],'code':'short_text_dwell','measured_seconds':longest/10,'required_seconds':required})
            rows.append({'scene_id':scene['id'],'element_id':element['id'],'readable_pose_seconds':longest/10,'measurement':'10Hz opacity/mask interval; does not prove human reading'})
        applicable=bool(texts) and _scene_narrated(project,scene)
        sustained=_longest_support(principal_support);required=min(.7,duration)
        narrative_rows.append({'scene_id':scene['id'],'applicable':applicable,'reference_width':1080,
            'minimum_font_size_reference_px':48,'minimum_effective_font_px':minimum_px,
            'maximum_visible_font_px':maximum_visible_px,'legible_pose_seconds':sustained,'required_seconds':required,
            'measurement':'10Hz nominal font_size*canvas_width/1080*element_scale*preset_scale; opacity/reveal/ink-rectangle proxy, not human reading'})
        if applicable and sustained+1e-8<required:
            code='text_too_small' if 0<maximum_visible_px<minimum_px-1e-8 else 'missing_legible_text'
            issues.append({'scene_id':scene['id'],'code':code,'maximum_visible_font_px':maximum_visible_px,
                'minimum_effective_font_px':minimum_px,'minimum_font_size_reference_px':48,
                'measured_seconds':sustained,'required_seconds':required,
                'reason':'El bloque narrativo necesita tamaño visible y permanencia suficiente; las etiquetas pequeñas no sustituyen un principal legible.'})
        overlap={}
        for index,entries in boxes.items():
            for a_pos,a in enumerate(entries):
                for b in entries[a_pos+1:]:
                    area=max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))*max(0,min(a[2]+a[4],b[2]+b[4])-max(a[2],b[2]))
                    if area>.3*min(a[3]*a[4],b[3]*b[4]):overlap.setdefault((a[0],b[0]),[]).append(index)
        for pair,times in overlap.items():
            longest=streak=1
            for previous,current in zip(times,times[1:]):streak=streak+1 if current==previous+1 else 1;longest=max(longest,streak)
            if longest>=4:issues.append({'scene_id':scene['id'],'elements':list(pair),'code':'potential_text_occlusion','seconds':longest/10})
    for asset in project['assets']:
        if asset['id']==project['source'] or asset['kind']=='font':continue
        rights.append({'asset_id':asset['id'],'rights':asset.get('verification',{}).get('rights','unknown'),'publication_permission_verified':False})
    return {'ok':not issues,'issues':issues,'text_dwell':rows,'narrative_text':narrative_rows,'resource_rights':rights,'technical_only':True,
            'editorial_approved':False,'audio_listened':False,'visual_readability_verified':False,
            'limitations':['Type size is a nominal geometric proxy: 48px reference width1080 equals16px at360 before animated scale. Small secondary labels remain allowed when a main block meets this minimum.',
                           'Text presence/size/10Hz dwell and ink rectangles do not prove human reading, contrast, semantic pertinence or exact pixel/occlusion/mask coverage; visual review remains pending.',
                           'Geometry uses element boxes for overlap and ignores glyph-level occlusion/alpha/rotation; warnings require inspection.',
                           'Dwell and valid motion data do not certify narrative pertinence, aesthetics, CLONE fidelity or publication rights.']}


def _compile(state,project,transcript,tracking):
    document=_merged(state)
    # Join actual ASR word tokens consistently with per-chunk planning context.
    validation_transcript={**transcript,'segments':[{'start':0,'end':state['scope_seconds'],'text':' '.join(word['word'] for word in transcript['words'])}]}
    draft=automation.validate_full_plan(project,document,validation_transcript,state['scope_seconds'],state['options']['instructions'])
    draft['transcript']=copy.deepcopy(transcript)
    draft['settings'].update(engine='hyperframes',voice_audio_stream=state['identity']['voice_audio_stream'])
    # The store preserves the server-owned branding key, including legacy None.
    draft['style']['branding']=copy.deepcopy(project.get('style',{}).get('branding'))
    draft=automation._apply_anchors(draft,tracking)
    draft.update(stage='pipeline_full_technical_draft',review={})
    draft.pop('full_authorization',None);draft.pop('approved_export',None)
    draft['pipeline']={'schema':SCHEMA,'project_id':state['project_id'],'generation':state['generation'],
                       'source_sha256':state['identity']['source_sha256'],'input_identity_sha256':state['identity_sha256'],
                       'scope_seconds':state['scope_seconds'],'technical_only':True,'editorial_approved':False,
                       'audio_listened':False,'channel':state['options']['channel'],'external_inference_verified':False}
    draft['analysis']={'voice_detection':'speech_transcribed','asr_scope':[0,state['scope_seconds']],
                       'whole_reel_transcribed':True,'voice_audio_stream':state['identity']['voice_audio_stream'],'preserve_original_cuts':True}
    _stage(state,'compile',draft)
    return draft


def validate_pipeline_receipt(project):
    record=project.get('pipeline')
    if not isinstance(record,dict) or record.get('schema')!=SCHEMA or record.get('technical_only') is not True or record.get('editorial_approved') is not False:
        raise core.StudioError('El completo requiere un recibo privado de pipeline técnico vigente.',409)
    state=_read(project['id'])
    if record.get('project_id')!=project['id'] or type(record.get('generation')) is not int or record.get('generation')!=state['generation'] or record.get('input_identity_sha256')!=state['identity_sha256'] or record.get('source_sha256')!=state['identity']['source_sha256'] or record.get('scope_seconds')!=state['scope_seconds'] or record.get('audio_listened') is not False:
        raise core.StudioError('El sello de pipeline pertenece a otra entrada.',409)
    _current(state,project)
    _verify_stage_proofs(state,project)
    if not state.get('committed_editorial_digest') or core.editorial_digest(project)!=state['committed_editorial_digest']:
        raise core.StudioError('El pipeline no conserva compilación/QC/CAS actuales.',409)
    return {'mode':'pipeline_full_technical_draft','scope_seconds':state['scope_seconds'],'generation':state['generation'],'editorial_approved':False}


def _verify_stage_proofs(state,project):
    mandatory=set(STAGES[:7])
    if not mandatory.issubset(state['stages']) or not set(state['stages']).issubset(STAGES):
        raise core.StudioError('Faltan etapas reales de análisis/dirección/QC/CAS en el pipeline.',409)
    for name,entry in state['stages'].items():
        if entry.get('status')!='complete' or entry.get('signature')!=_signature(state,name) or entry.get('output',{}).get('path')!=core.relative(_path(state['project_id'],name+'.json')):
            raise core.StudioError('Una etapa del pipeline no conserva su contrato actual.',409)
        _value(state,entry['output'])
    transcript=_cached(state,'asr')
    if not isinstance(transcript,dict) or transcript.get('source_sha256')!=state['identity']['source_sha256'] or type(transcript.get('voice_audio_stream_index')) is not int or transcript['voice_audio_stream_index']!=state['identity']['voice_audio_stream'] or transcript.get('scope_seconds')!=state['scope_seconds']:
        raise core.StudioError('El ASR del pipeline no corresponde al crudo/pista/rango actuales.',409)
    _verify_tracking(_cached(state,'tracking'))
    cursor=0.
    for index,chunk in enumerate(state['chunks']):
        if chunk.get('id')!=f'c_{index:03}' or chunk.get('start')!=cursor or not .1-1e-6<=chunk.get('end',0)-cursor<=10+1e-6:
            raise core.StudioError('Los tramos del pipeline no forman una secuencia completa.',409)
        _chunk_document(state,chunk,project,_value(state,chunk.get('plan')))
        inference=_value(state,chunk.get('inference'))
        if not isinstance(inference,dict) or (state['options']['channel']=='api' and inference.get('inference_executed') is not True) or (state['options']['channel']=='external' and (inference.get('source')!='external_agent_declared' or inference.get('inference_executed') is not False or inference.get('verified_external_inference') is not False)):
            raise core.StudioError('Falta el origen real o declarado de la dirección del pipeline.',409)
        cursor=chunk['end']
    if not state['chunks'] or abs(cursor-state['scope_seconds'])>1e-6:
        raise core.StudioError('El plan no cubre el crudo completo.',409)
    for entry in state.get('inference_history',[]):_value(state,entry)
    draft=_cached(state,'compile');qc=_cached(state,'qc');commit=_cached(state,'commit')
    if not isinstance(draft,dict) or not isinstance(qc,dict) or qc.get('ok') is not True or qc.get('editorial_approved') is not False or not isinstance(commit,dict) or commit.get('editorial_digest')!=state.get('committed_editorial_digest') or core.editorial_digest(draft)!=state.get('committed_editorial_digest'):
        raise core.StudioError('El pipeline no conserva compilación/QC/CAS actuales.',409)


def resume(project_id,*,infer=None,commit=None,render=None,export=None,progress=None,cancel=None):
    """Resume completed stages; callbacks are trusted local integration hooks."""
    from .jobs import cpu_slot
    progress=progress or (lambda fraction,message:None)
    with cpu_slot(cancel=cancel),_lock(project_id):
        state=_read(project_id);project=core.get_project(project_id)
        cancel=_Cancellation(state,cancel)
        try:
            automation._check(cancel)
            if state.get('cancel_requested'):raise core.StudioError('Pipeline cancelado.',409)
            _current(state,project)
            state.update(status='running',error=None);_write(state)
            state['stage']='asr';_write(state)
            transcript=_asr(state,project,progress,cancel)
            automation._check(cancel);_current(state,core.get_project(project_id))
            state['stage']='tracking';_write(state)
            tracking=_tracking(state,project,progress,cancel)
            automation._check(cancel);_current(state,core.get_project(project_id))
            state['stage']='context';_write(state)
            _chunks(state,transcript,tracking,project)
            while True:
                state['stage']='direction';_write(state)
                if not _direction(state,project,infer,progress,cancel):return _public(state,True)
                draft=_cached(state,'compile') or _compile(state,project,transcript,tracking)
                qc=_cached(state,'qc') or _stage(state,'qc',quality_control(draft))
                if qc['ok']:break
                affected={issue['scene_id'].split('_')[1] for issue in qc['issues']}
                for chunk in state['chunks']:
                    if chunk['id'][2:] in affected:
                        chunk['context']['input']['repair_issues']=copy.deepcopy(qc['issues'])
                if state['options']['channel']=='external':
                    state.update(status='waiting_external_repair',stage='qc');_write(state);return _public(state,True)
                if state['repairs_used']>=state['options']['max_repairs']:raise core.StudioError('QC no resuelto tras el límite de reparaciones.',409,{'issues':qc['issues']})
                for chunk in state['chunks']:
                    if chunk['id'][2:] in affected:
                        chunk.pop('plan',None);chunk.pop('inference',None)
                state['repairs_used']+=1;state['stages'].pop('compile',None);state['stages'].pop('qc',None);_write(state)
                state.update(status='ready',stage='direction');_write(state)
            automation._check(cancel);_current(state,project)
            if 'commit' not in state['stages']:
                if commit is None:state.update(status='waiting_commit',stage='commit');_write(state);return _public(state)
                saved=commit(draft,state['project_revision'])
                if not isinstance(saved,dict) or saved.get('id')!=project_id or saved.get('revision')!=state['project_revision']+1:
                    raise core.StudioError('El callback no confirmó un CAS real del proyecto.',409)
                actual=core.get_project(project_id)
                if actual['revision']!=saved['revision'] or core.editorial_digest(actual)!=core.editorial_digest(saved):
                    raise core.StudioError('No existe el proyecto realmente confirmado por CAS.',409)
                if core.editorial_digest(actual)!=core.editorial_digest(draft):
                    raise core.StudioError('El CAS no conservó el montaje compilado del pipeline.',409)
                state['project_revision']=saved['revision'];state['committed_editorial_digest']=core.editorial_digest(saved)
                _stage(state,'commit',{'revision':saved['revision'],'editorial_digest':state['committed_editorial_digest']})
                project=saved
            else:project=core.get_project(project_id)
            validate_pipeline_receipt(project);automation._check(cancel)
            receipt=_cached(state,'render')
            if receipt is None:
                if render is None:state.update(status='waiting_render',stage='render');_write(state);return _public(state)
                receipt=render(project,state['scope_seconds'],progress,cancel)
                project=_accept_render_revision(state,receipt)
                _verify_output(receipt)
                _verify_render(receipt,state['scope_seconds'],project,cancel)
                _stage(state,'render',receipt)
            else:_verify_output(receipt);_verify_render(receipt,state['scope_seconds'],project,cancel)
            automation._check(cancel);_current(state,core.get_project(project_id))
            bundle=_cached(state,'export')
            if bundle is None:
                if export is None:state.update(status='waiting_export',stage='export');_write(state);return _public(state)
                bundle=export(project,receipt);_verify_output(bundle);_verify_bundle(bundle,project);_stage(state,'export',bundle)
            else:_verify_output(bundle);_verify_bundle(bundle,project)
            _verify_output(receipt)
            automation._check(cancel);_current(state,core.get_project(project_id))
            state.update(status='completed',stage='export');_write(state)
            return _public(state)
        except Exception as error:
            state.update(status='cancelled' if cancel.is_set() else 'failed',
                         error={'message':str(error),'stage':state['stage'],'at':core.now()})
            _write(state)
            raise


def _verify_output(receipt):
    if not isinstance(receipt,dict) or not isinstance(receipt.get('path'),str) or not isinstance(receipt.get('sha256'),str):
        raise core.StudioError('El callback debe devolver un archivo real con path y SHA256.',409)
    path=core.confined(receipt['path'],must_exist=True)
    if path==core.ROOT/receipt['path'] and re.fullmatch(r'[0-9a-f]{64}',receipt['sha256']) and core.digest(path)==receipt['sha256']:
        return
    raise core.StudioError('El resultado del callback cambió o no está confinado.',409)


def _accept_render_revision(state,receipt):
    if not isinstance(receipt,dict):raise core.StudioError('El render no devolvió un recibo real.',409)
    project=core.get_project(state['project_id'])
    current=state['project_revision'];reported=receipt.get('project_revision',current)
    if type(reported) is not int or reported not in (current,current+1) or project['revision']!=reported or core.editorial_digest(project)!=state['committed_editorial_digest']:
        raise core.StudioError('El render cambió el montaje o no confirmó su revisión real.',409)
    identity,_=_identity(project,state['options'])
    if identity!=state['identity']:raise core.StudioError('Cambió la entrada durante el render completo.',409)
    if reported!=current:
        state['project_revision']=reported;_write(state)
    return project


def _verify_render(receipt,duration,project,cancel=None):
    from .hyperframes import verify_receipt
    measured=receipt.get('duration')
    if isinstance(measured,bool) or not isinstance(measured,(int,float)) or not math.isfinite(measured) or abs(measured-duration)>1/project['settings']['fps']+.001:
        raise core.StudioError('El render no cubre la duración completa solicitada.',409)
    technical=receipt.get('technical')
    if receipt.get('approved') is not False or not isinstance(technical,dict) or technical.get('decode_ok') is not True or technical.get('editorial_approved',False) is not False or technical.get('audio_listened',False) is not False:
        raise core.StudioError('Falta un recibo técnico sin aprobación editorial del render completo.',409)
    if core.digest(core.confined(receipt['path'],must_exist=True))==project['pipeline']['source_sha256']:
        raise core.StudioError('El resultado debe ser una edición real, no el crudo original.',409)
    if 'hyperframes' in technical:
        if not verify_receipt(receipt,core.ROOT):raise core.StudioError('Falta recibo HyperFrames vigente del render completo técnico.',409)
        _verify_output(receipt)
        return
    # Native is a distinct engine. Validate its actual encoded output without
    # claiming HTML/GSAP execution or performing another render.
    from . import render as native
    path=core.confined(receipt['path'],must_exist=True);info=native.probe_media(path,core.ROOT)
    video=next((stream for stream in info['streams'] if stream.get('codec_type')=='video'),None)
    audio=next((stream for stream in info['streams'] if stream.get('codec_type')=='audio'),None)
    if not video or video.get('width')!=project['settings']['width'] or video.get('height')!=project['settings']['height'] or not audio or abs(info['duration']-duration)>1/project['settings']['fps']+.001 or technical.get('original_voice_present') is not True or technical.get('original_audio_present') is not True:
        raise core.StudioError('El render nativo no conserva dimensiones, duración o audio original.',409)
    native._run([native._tool('ffmpeg'),'-v','error','-xerror','-filter_threads','1']+native._input(path)+
                ['-map','0:v:0','-map','0:a:0','-threads','2','-f','null','-'],core.ROOT,cancel,timeout=min(2400,math.ceil(duration)*4+120))
    _verify_output(receipt)


def _verify_bundle(receipt,project=None):
    path=core.confined(receipt['path'],must_exist=True)
    try:
        with zipfile.ZipFile(path) as archive:
            members=archive.infolist();names=archive.namelist()
            if len(members)>5000 or len(set(names))!=len(names) or sum(item.file_size for item in members)>4*1024**3 or 'project.json' not in names or any(name.startswith('/') or '\\' in name or '..' in Path(name).parts or '.estado' in Path(name).parts or (item.external_attr>>16)&0o170000==0o120000 for name,item in zip(names,members)) or archive.testzip() is not None:
                raise ValueError('integridad/cobertura')
            if archive.getinfo('project.json').file_size>MAX_STATE_BYTES:raise ValueError('proyecto demasiado grande')
            if project is not None:
                editable=json.loads(archive.read('project.json'))
                if not isinstance(editable,dict) or editable.get('id')!=project['id'] or core.editorial_digest(editable)!=core.editorial_digest(project):
                    raise ValueError('proyecto de otra edición')
    except (OSError,ValueError,zipfile.BadZipFile) as error:raise core.StudioError('El editable no es un ZIP íntegro con proyecto canónico.',409) from error
