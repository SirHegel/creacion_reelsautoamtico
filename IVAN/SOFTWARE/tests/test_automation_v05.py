"""Model outputs are explicit mocked fixtures, never a live API claim."""
import copy
import hashlib
import json
from pathlib import Path
import queue
import shutil
import threading
import types

import pytest

from studio import core,analysis,automation as auto,jobs,tracking,typography,fonts

REAL_ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def space(tmp_path,monkeypatch):
    assert tmp_path.is_relative_to(REAL_ROOT/'.estado/tmp')
    missing=[name for name in ('Sequel_Sans_Bold_Disp.ttf','Scholar_Italic.ttf')
             if not (REAL_ROOT/'assets/fonts'/name).is_file()]
    if missing:
        pytest.skip('Optional licensed local Sequel/Scholar fonts are absent from the public source: '+', '.join(missing))
    root=tmp_path/'SOFTWARE';root.mkdir()
    for module in (core,analysis,jobs):monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(core,'MANUAL_ROOT',root.parent)
    monkeypatch.setattr(jobs,'SHARED_CPU_LOCK',root/'.estado/cpu_worker.lock')
    monkeypatch.setattr(jobs,'QUEUE',queue.Queue());monkeypatch.setattr(jobs,'CANCEL',{})
    monkeypatch.setattr(core,'production_motion_errors',lambda p:[])
    from studio import skills
    monkeypatch.setattr(skills,'validate_application',lambda p:[])
    core.setup()
    for name in core.DOCUMENTS:(root.parent/name).write_text('Fixture manual '+name)
    for name in ('Sequel_Sans_Bold_Disp.ttf','Scholar_Italic.ttf'):
        shutil.copyfile(REAL_ROOT/'assets/fonts'/name,root/'assets/fonts'/name)
    source=root/'assets/video/raw.mp4';source.write_bytes(b'unit fixture source; no media decode or ASR')
    asset={'id':'a_raw','name':'raw.mp4','path':'assets/video/raw.mp4','kind':'video','sha256':core.digest(source),
           'md5':core.digest(source,'md5'),'size':source.stat().st_size,'duration':10.,'metadata':{},
           'probe':{'streams':[{'codec_type':'video','width':360,'height':640},{'codec_type':'audio'}]}}
    core.atomic_json('.estado/assets.json',[asset])
    project=core.create_project('Independent automation unit fixture','a_raw')
    project['settings'].update(width=360,height=640,fps=12)
    project=core.save_project(project['id'],project)
    return root,project


def transcript():
    return {'status':'transcribed','engine':'mocked_unit_fixture','words':[{'start':i*.5,'end':i*.5+.3,'word':word} for i,word in enumerate('Conectamos la entrada procesamos los datos y mostramos resultados reales'.split())],
            'segments':[{'start':0,'end':5,'text':'Conectamos la entrada procesamos los datos y mostramos resultados reales'}]}


def ir(duration,family='problem_resolution'):
    return {'schema':'ascendia.sceneir/1','content':{'text':'Conectamos la entrada','entities':['entrada','salida'],'actions':['transferencia'],'results':['salida'],'relations':['entrada causa salida']},
            'narrative_goal':'Conectar entrada a salida con transferencia observable','family':family,'representation':'conceptual','duration':duration,
            'composition':{'background':'#101318'},'components':[
                {'id':'packet','type':'shape','shape':'rect','x':.1,'y':.4,'width':.12,'height':.12,'color':'#20bb89'},
                {'id':'receiver','type':'shape','shape':'rect','x':.7,'y':.4,'width':.15,'height':.15,'color':'#445566'},
                {'id':'label','type':'text','text':'Datos reales','font':'primary','font_size':54,'x':.1,'y':.1,'width':.8,'height':.2,'color':'#ffffff'}],
            'actions':[{'target_id':'packet','time':0,'properties':{'x':.1,'opacity':0}},
                       {'target_id':'packet','time':duration*.3,'properties':{'x':.4,'opacity':1}},
                       {'target_id':'packet','time':duration*.8,'properties':{'x':.7,'scale':.5}},
                       {'target_id':'receiver','time':duration*.8,'properties':{'scale':1.2}},
                       {'target_id':'receiver','time':duration,'properties':{'scale':1}}]}


def plan(seconds=4):
    result={'schema':auto.SCHEMA,'summary':'Entrada, acción y resultado de la frase completa, cámara auténtica breve y transferencia conceptual.',
            'narrative_goal':'Mostrar causalidad sin inventar aplicaciones o cifras','facts':[],'scenes':[]}
    for index,(lo,hi,kind) in enumerate(((0,1,'split'),(1,seconds,'motion'))):
        row={'id':'s_'+str(index),'start':lo,'end':hi,'type':kind,'family':'problem_resolution','narration':'Conectamos la entrada',
             'reason':'La transferencia visual explica la conexión que dice la fuente.',
             'alternatives':[{'family':'composition_graph','reason':'El grafo añade relaciones que la frase no necesita.'}],
             'phases':{'entry':'entra el dato','action':'se transfiere','reaction':'recibe','transformation':'cambia receptor','exit':'se estabiliza'},'fact_ids':[],
             'scene_ir':ir(hi-lo)}
        result['scenes'].append(row)
    return result


@pytest.mark.parametrize('change',[{}, {'confirmed':False},{'confirmed':1},{'provider':[]},{'asr_model':[]},{'plan_only':1},
                                  {'seconds':True},{'seconds':float('nan')},{'seconds':11},{'max_tokens':True},{'max_tokens':999},
                                  {'language':'es-CO'},{'model':'tiny'},{'transcribe':True},{'instructions':'x'*12001}])
def test_options_closed_and_confirmation_required(change):
    values={'provider':'openai','confirmed':True,**change}
    if change=={}:values={}
    with pytest.raises(core.StudioError):auto.validate_options(values)


def test_options_default_and_no_network_from_catalog():
    result=auto.validate_options({'provider':'anthropic','confirmed':True})
    assert result['asr_model']=='tiny' and result['seconds']==10 and not result['plan_only']
    catalog=auto.catalog()
    assert len(catalog['families'])==16 and all(f['upstream_component_imported'] is False for f in catalog['families'])


def test_compile_multiscene_split_and_motion_preserves_source_voice_and_brand(space):
    root,project=space;original=copy.deepcopy(project)
    result=auto.validate_plan(project,plan(),transcript(),4)
    assert project==original
    assert [s['type'] for s in result['timeline']]==['split','motion']
    assert all(s['template']=='custom' and s['motion_design']['elements'][0]['keyframes'] for s in result['timeline'])
    assert result['source']==project['source'] and result['fonts']==project['fonts']
    assert result['settings']['height']==640 and result['settings']['engine']=='hyperframes'
    assert 'mode' not in result and not result['review'] and 'full_authorization' not in result
    assert result['timeline'][0]['source_in']==0 and result['timeline'][1]['source_in']==1


@pytest.mark.parametrize('mutation',[
    lambda p:p.update(schema='invalid'),lambda p:p.update(script='alert(1)'),lambda p:p.update(facts=[{'id':'fake','value':'99','quote':'99 agentes'}]),
    lambda p:p['scenes'][0].update(narration='Resultado inexistente en el audio'),
    lambda p:p['scenes'][0].update(end=True),lambda p:p['scenes'][1].update(start=1.2),
    lambda p:p['scenes'][0].update(family='made_up'),lambda p:p['scenes'][0]['scene_ir'].update(family='composition_graph'),
    lambda p:p['scenes'][0]['scene_ir'].update(actions=[]),
    lambda p:p['scenes'][0]['scene_ir']['components'][2].update(text='99 agentes'),
    lambda p:p['scenes'][0]['scene_ir']['components'][2].update(text='Un bloque muy largo '*30,font_size=200),
    lambda p:p['scenes'][0]['scene_ir']['components'].append({'id':'hidden_raw','type':'media','asset_id':'a_raw','x':0,'y':0,'width':1,'height':1}),
    lambda p:p['scenes'][0].update(type='motion'),lambda p:p['scenes'][0].update(alternatives=[]),
])
def test_plan_rejects_unfounded_or_unrenderable_data(space,mutation):
    root,project=space;candidate=plan();mutation(candidate)
    with pytest.raises(core.StudioError):auto.validate_plan(project,candidate,transcript(),4)


def test_numerical_fact_must_bind_literal_and_cannot_just_name_it(space):
    root,project=space;candidate=plan();candidate['facts']=[{'id':'n','value':'12','quote':'12 procesos'}]
    candidate['scenes'][0]['scene_ir']['components'][2]['text']='12 procesos'
    with pytest.raises(core.StudioError):auto.validate_plan(project,candidate,transcript(),4,'12 procesos')
    candidate['scenes'][0]['fact_ids']=['n']
    assert auto.validate_plan(project,candidate,transcript(),4,'12 procesos')['timeline'][0]['motion_design']['elements'][2]['text']=='12 procesos'


def test_json_transport_rejects_duplicate_fields_and_nan():
    for value in ('{"schema":1,"schema":2}','{"x":NaN}','prefix {"x":1}',None):
        with pytest.raises(core.StudioError):auto._parse_response(value)
    assert auto._parse_response('```json\n{"x":"</script>"}\n```')=={'x':'</script>'}


def model_fixture(root,model='tiny'):
    cache=root/'.estado/models/whisper';revision='1'*40
    repo=cache/('models--Systran--faster-whisper-'+model)
    (repo/'refs').mkdir(parents=True);(repo/'refs/main').write_text(revision)
    snapshot=repo/'snapshots'/revision;snapshot.mkdir(parents=True)
    (repo/'blobs').mkdir()
    records={}
    for name in analysis.LOCAL_MODEL_FILES:
        blob=repo/'blobs'/name;blob.write_bytes(('public model fixture '+name).encode())
        (snapshot/name).symlink_to(Path('../../blobs')/name)
        data=blob.read_bytes();records[name]={'size':len(data),'blob_id':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}
    (repo/'trees').mkdir();(repo/'trees'/f'{revision}.json').write_text(json.dumps({'files':records}))
    return snapshot


def test_local_model_whitelist_snapshot_and_symlink_escape(space,monkeypatch):
    root,_=space;monkeypatch.setattr(analysis,'CODE_ROOT',root);snapshot=model_fixture(root)
    proof=analysis.offline_model('tiny')
    assert proof['path']==snapshot and len(proof['files'])==4 and not proof['network_used']
    with pytest.raises(core.StudioError):analysis.offline_model('large-v3')
    with pytest.raises(core.StudioError):analysis.offline_model('base')
    (snapshot/'model.bin').unlink();(snapshot/'model.bin').symlink_to(root/'assets/video/raw.mp4')
    with pytest.raises(core.StudioError):analysis.offline_model('tiny')


def test_actual_constructor_receives_local_files_only_cpu_and_two_threads(space,monkeypatch):
    root,project=space;monkeypatch.setattr(analysis,'CODE_ROOT',root);snapshot=model_fixture(root)
    calls=[]
    class Engine:
        def __init__(self,*args,**kw):calls.append((args,kw))
        def transcribe(self,*args,**kw):
            return iter([]),types.SimpleNamespace(duration=1,language='es',language_probability=.9)
    monkeypatch.setitem(__import__('sys').modules,'faster_whisper',types.SimpleNamespace(WhisperModel=Engine))
    result=analysis.transcribe(project['assets'][0]['path'],local_model_path=snapshot)
    assert calls[0][0]==(str(snapshot),)
    assert calls[0][1]=={'local_files_only':True,'device':'cpu','compute_type':'int8','cpu_threads':2,'num_workers':1}
    assert result['local_model']['network_used'] is False and result['reviewed'] is False


def test_cache_model_change_during_asr_is_rejected(space,monkeypatch):
    root,project=space;monkeypatch.setattr(analysis,'CODE_ROOT',root);snapshot=model_fixture(root)
    class Engine:
        def __init__(self,*a,**k):pass
        def transcribe(self,*a,**k):
            (snapshot/'config.json').write_bytes(b'mutated local model')
            return iter([]),types.SimpleNamespace(duration=1,language='es',language_probability=.9)
    monkeypatch.setitem(__import__('sys').modules,'faster_whisper',types.SimpleNamespace(WhisperModel=Engine))
    with pytest.raises(core.StudioError,match='modelo ASR'):
        analysis.transcribe(project['assets'][0]['path'],local_model_path=snapshot)


def mocked_pipeline(monkeypatch,project):
    from studio import media_tools,render
    monkeypatch.setattr(analysis,'probe',lambda *a,**k:{'format':{'duration':'10'},'streams':[{'index':0,'codec_type':'video'},{'index':1,'codec_type':'audio'}]})
    monkeypatch.setattr(analysis,'offline_model',lambda m:{'model':m,'path':core.ROOT/'model','files':{}})
    monkeypatch.setattr(media_tools,'process',lambda *a,**k:{'path':project['assets'][0]['path']})
    monkeypatch.setattr(analysis,'transcribe',lambda *a,**k:transcript())
    monkeypatch.setattr(auto,'_tracking_runtime',lambda root:None)
    samples=[{'time':t,'detected':True,'status':'detected_pending_review','smoothed':{'focus_x':.4+t*.02,'focus_y':.5,'chin_y':.6}} for t in (0,.5,1,1.5,2,2.5,3,3.5)]
    report={'samples':samples,'evidence':[],'reviewed':False,'path':f'projects/{project["id"]}/tracking/mock/measurements.json','runtime_provenance':{'files':{}}}
    core.atomic_json(report['path'],report)
    monkeypatch.setattr(tracking,'analyze_tracking',lambda *a,**k:copy.deepcopy(report))
    monkeypatch.setattr(tracking,'_runtime',lambda root:{'files':{}})
    monkeypatch.setattr(render,'probe_media',lambda *a:{'streams':[{'codec_type':'video','width':360,'height':640}]})
    return lambda *a,**k:{'text':json.dumps(plan()),'provider':'openai','model':'mocked_not_live','usage':{},'inference_executed':True}


def test_external_prepare_and_apply_no_provider_call_no_fake_inference_or_project_save(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    from studio.providers import Connections
    monkeypatch.setattr(Connections,'infer',lambda *a,**k:pytest.fail('External direction needs no provider key or API call'))
    before=core.get_project(project['id'])
    prepared=auto.ivan_prepare(project,{'seconds':4,'instructions':'Orden causal fiel a la voz.'})
    assert prepared['inference_executed'] is False and prepared['editorial_approved'] is False
    assert core.get_project(project['id'])==before
    result=auto.ivan_apply_plan(project,{'preparation_id':prepared['preparation_id'],'expected_revision':project['revision'],
                                       'document':plan(),'agent':{'name':'Mocked external Codex client','model':'client_declaration_not_verified','notes':'Explicit fixture'}})
    assert core.get_project(project['id'])==before
    assert result['automation']['source']=='external_agent_declared' and result['automation']['inference_executed'] is False
    assert result['automation']['verified_external_inference'] is False and 'usage' not in result['automation']
    assert auto.validate_draft_receipt(result['project'])


@pytest.mark.parametrize('mutation',[
    lambda o:o.update(preparation_id='../escape'),lambda o:o.update(expected_revision=True),
    lambda o:o['agent'].update(usage={'tokens':1}),lambda o:o['agent'].update(name=''),
    lambda o:o['agent'].update(model='x'*201),lambda o:o['agent'].update(notes='x'*2001),
    lambda o:o.update(inference_executed=True),lambda o:o.update(api_key='secret'),
])
def test_external_options_data_only_and_agent_claims_closed(mutation):
    opts={'preparation_id':'a'*24,'expected_revision':1,'document':plan(),'agent':{'name':'Client'}};mutation(opts)
    with pytest.raises(core.StudioError):auto.validate_apply_options(opts)


def test_external_prepare_reuse_and_tampered_private_context_rejected(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    record=auto.ivan_prepare(project,{'seconds':4})
    monkeypatch.setattr(analysis,'transcribe',lambda *a,**k:pytest.fail('Reuse cannot repeat ASR'))
    monkeypatch.setattr(tracking,'analyze_tracking',lambda *a,**k:pytest.fail('Reuse cannot repeat facial inference'))
    assert auto.ivan_prepare(project,{'seconds':4})==record
    path=auto._preparation_path(project['id'],record['preparation_id']);value=json.loads(path.read_text());value['transcript']['segments'][0]['text']='forged';path.write_text(json.dumps(value))
    with pytest.raises(core.StudioError,match='comprobante'):auto.ivan_apply_plan(project,{'preparation_id':record['preparation_id'],'expected_revision':project['revision'],'document':plan(),'agent':{'name':'Client'}})


def test_external_prepare_stale_revision_never_applies(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project);record=auto.ivan_prepare(project,{'seconds':4})
    current=core.get_project(project['id']);current['name']='User correction';current=core.save_project(project['id'],current)
    with pytest.raises(core.StudioError,match='cambió'):
        auto.ivan_apply_plan(current,{'preparation_id':record['preparation_id'],'expected_revision':current['revision'],'document':plan(),'agent':{'name':'Client'}})


def test_external_jobs_prepare_keeps_revision_apply_saves_and_enqueues_preview(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    prepare_job=jobs.submit(project['id'],'ivan_prepare',{'seconds':4});jobs._execute(prepare_job['id'])
    prepared=jobs.get_job(prepare_job['id']);assert prepared['status']=='completed'
    assert core.get_project(project['id'])['revision']==project['revision']
    monkeypatch.setattr(jobs,'validate_project',lambda *a,**k:{'valid':True})
    job=jobs.submit(project['id'],'ivan_apply_plan',{'preparation_id':prepared['result']['preparation_id'],'expected_revision':project['revision'],'document':plan(),'agent':{'name':'Unit client'}})
    jobs._execute(job['id']);done=jobs.get_job(job['id']);assert done['status']=='completed'
    saved=core.get_project(project['id']);assert saved['revision']==project['revision']+1 and saved['automation']['inference_executed'] is False
    assert jobs.get_job(done['result']['preview_job_id'])['status']=='queued'


def test_run_returns_no_store_changes_and_pending_realistic_artifacts(space,monkeypatch):
    root,project=space;infer=mocked_pipeline(monkeypatch,project)
    before=core.get_project(project['id'])
    result=auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},inference=infer)
    assert core.get_project(project['id'])==before
    assert result['automation']['inference_executed'] is True and result['automation']['editorial_approved'] is False
    assert result['project']['timeline'][0]['camera_anchors'][1]['focus_x']>.4
    assert all(core.digest(core.confined(a['path']))==a['sha256'] for a in result['automation']['artifacts'])


def test_model_failure_has_no_heuristic_fallback_and_no_edit(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    def infer(*a,**k):raise core.StudioError('Simulated provider failure')
    with pytest.raises(core.StudioError,match='provider failure'):auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},inference=infer)
    assert core.get_project(project['id'])['timeline']==project['timeline']
    assert not (root/'projects'/project['id']/'automation').exists()


def test_cancel_after_inference_discards_plan_and_never_saves(space,monkeypatch):
    root,project=space;response=mocked_pipeline(monkeypatch,project);event=threading.Event()
    def infer(*a,**k):event.set();return response(*a,**k)
    with pytest.raises(core.StudioError,match='cancelada'):auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},cancel=event,inference=infer)
    assert core.get_project(project['id'])['timeline']==project['timeline']


def test_queue_auto_saves_cas_then_enqueues_separate_preview_without_nested_execution(space,monkeypatch):
    root,project=space;infer=mocked_pipeline(monkeypatch,project)
    computed=auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},inference=infer)
    monkeypatch.setattr(auto,'run',lambda *a,**k:computed)
    monkeypatch.setattr(jobs,'validate_project',lambda *a,**k:{'valid':True})
    job=jobs.submit(project['id'],'auto_ivan',{'provider':'openai','confirmed':True,'seconds':4})
    jobs._execute(job['id']);completed=jobs.get_job(job['id'])
    assert completed['status']=='completed' and completed['result']['approved'] is False
    preview=jobs.get_job(completed['result']['preview_job_id'])
    assert preview['status']=='queued' and preview['options']['technical'] is True and preview['options']['ivan_draft'] is True
    assert len(jobs.list_jobs())==2 and core.get_project(project['id'])['settings']['engine']=='hyperframes'


def test_queue_stale_cas_never_applies_or_renders(space,monkeypatch):
    root,project=space;computed=auto.validate_plan(project,plan(),transcript(),4)
    def run(*a,**k):
        live=core.get_project(project['id']);live['name']='Concurrent user edit';core.save_project(project['id'],live)
        return {'project':computed,'seconds':4,'plan_only':False,'automation':{}}
    monkeypatch.setattr(auto,'run',run)
    job=jobs.submit(project['id'],'auto_ivan',{'provider':'openai','confirmed':True,'seconds':4});jobs._execute(job['id'])
    assert jobs.get_job(job['id'])['status']=='failed' and len(jobs.list_jobs())==1
    assert core.get_project(project['id'])['name']=='Concurrent user edit'


@pytest.mark.parametrize('visible,value,quote',[
    ('12','120','120 procesos'),('10','10','110 procesos'),('12','12','1.12 procesos'),
    ('3','30','30 procesos'),('1e3','3','3 procesos'),('ABC123','12','12 procesos'),
])
def test_numbers_require_exact_tokens_not_substring(space,visible,value,quote):
    root,project=space;candidate=plan()
    candidate['facts']=[{'id':'n','value':value,'quote':quote}]
    candidate['scenes'][0]['fact_ids']=['n'];candidate['scenes'][0]['scene_ir']['components'][2]['text']=visible
    with pytest.raises(core.StudioError):auto.validate_plan(project,candidate,transcript(),4,quote)


def test_only_fades_or_scales_are_rejected_as_connected_motion(space):
    root,project=space;candidate=plan()
    doc=candidate['scenes'][0]['scene_ir']
    doc['actions']=[{'target_id':el['id'],'time':time,'properties':{'opacity':time,'scale':1+time*.1}}
                    for el in doc['components'] for time in (0,.5,1)]
    with pytest.raises(core.StudioError,match='fades'):auto.validate_plan(project,candidate,transcript(),4)


def test_draft_receipt_tampered_evidence_or_edited_timeline_not_reused(space,monkeypatch):
    root,project=space;infer=mocked_pipeline(monkeypatch,project)
    computed=auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},inference=infer)
    p=computed['project'];assert auto.validate_draft_receipt(p)
    changed=copy.deepcopy(p);changed['timeline'][0]['motion_design']['elements'][0]['x']=.2
    with pytest.raises(core.StudioError):auto.validate_draft_receipt(changed)
    path=core.confined(p['automation']['artifacts'][0]['path']);path.write_text('{}')
    with pytest.raises(core.StudioError,match='evidencia'):auto.validate_draft_receipt(p)


def test_no_face_detection_aborts_before_paid_inference(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    monkeypatch.setattr(tracking,'analyze_tracking',lambda *a,**k:{'samples':[{'time':0,'detected':False}],'evidence':[]})
    def forbidden(*a,**k):pytest.fail('No facial coverage must fail before provider cost')
    with pytest.raises(core.StudioError,match='rostro'):
        auto.run(project,{'provider':'openai','confirmed':True,'seconds':4},inference=forbidden)


def test_face_gap_is_not_filled_with_an_invented_anchor(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project)
    p=auto.validate_plan(project,plan(),transcript(),4)
    report={'samples':[{'time':0,'detected':True,'smoothed':{'focus_x':.5,'focus_y':.5,'chin_y':.6}},
                       {'time':.5,'detected':False,'status':'no_face'}],'evidence':[]}
    with pytest.raises(core.StudioError,match='sin huecos'):auto._apply_anchors(p,report)


def test_selects_canonical_reviewed_library_clip_without_requiring_prior_attachment(space,monkeypatch):
    root,project=space;path=root/'assets/broll/reviewed.mp4';path.write_bytes(b'unit clip only; never decoded')
    evidence=root/'projects'/project['id']/'reviewed_fixture.txt';evidence.write_text('Explicit mocked unit observations')
    clip={'id':'a_reviewed','kind':'broll','name':'reviewed.mp4','path':core.relative(path),'sha256':core.digest(path),'duration':4,
          'probe':{'streams':[{'codec_type':'video'}]},'metadata':{'content':'Mocked fixture transferring data'},
          'verification':{'visual':True,'evidence':[core.relative(evidence)]}}
    core.atomic_json('.estado/assets.json',core.assets()+[clip])
    from studio import resource_review
    monkeypatch.setattr(resource_review,'current_review',lambda a:{'valid':True,'scope':'sequence','coverage':'continuous_declared','interval':{'start':0,'end':4}})
    candidate=plan();row=candidate['scenes'][1];row.pop('scene_ir');row.update(type='broll',asset_id=clip['id'],source_in=0)
    result=auto.validate_plan(project,candidate,transcript(),4)
    assert any(a['id']==clip['id'] for a in result['assets']) and all(a['id']!=clip['id'] for a in project['assets'])
    stale=copy.deepcopy(clip);stale['verification']['visual']=False;project['assets'].append(stale)
    result=auto.validate_plan(project,candidate,transcript(),4)
    assert next(a for a in result['assets'] if a['id']==clip['id'])['verification']['visual'] is True


def test_unreviewed_library_clip_never_becomes_broll_by_name_matching(space):
    root,project=space;path=root/'assets/broll/matches_every_word.mp4';path.write_bytes(b'unit clip only')
    clip={'id':'a_unreviewed','kind':'broll','name':'Conectamos la entrada.mp4','path':core.relative(path),'sha256':core.digest(path),'duration':4,
          'probe':{'streams':[{'codec_type':'video'}]},'metadata':{'content':'Conectamos la entrada'},'verification':{'visual':False,'evidence':[]}}
    core.atomic_json('.estado/assets.json',core.assets()+[clip])
    candidate=plan();candidate['scenes'][1].pop('scene_ir');candidate['scenes'][1].update(type='broll',asset_id=clip['id'],source_in=0)
    with pytest.raises(core.StudioError,match='inspección'):auto.validate_plan(project,candidate,transcript(),4)


def test_parameter_substitution_cannot_hide_an_unfounded_visible_number(space):
    root,project=space;candidate=plan();doc=candidate['scenes'][0]['scene_ir']
    doc['parameters']={'count':99};doc['components'][2]['text']='{{count}} procesos'
    with pytest.raises(core.StudioError,match='cifra'):auto.validate_plan(project,candidate,transcript(),4)


def test_split_caption_space_is_obtained_by_real_crop_not_a_guessed_chin(space,monkeypatch):
    root,project=space;mocked_pipeline(monkeypatch,project);p=auto.validate_plan(project,plan(),transcript(),4)
    samples=[{'time':t,'detected':True,'smoothed':{'focus_x':.5,'focus_y':.3,'chin_y':.42}} for t in (0,.5)]
    result=auto._apply_anchors(p,{'samples':samples,'evidence':[]})
    anchors=result['timeline'][0]['camera_anchors']
    target=640-__import__('studio.render',fromlist=['split_height']).split_height(640)
    for anchor in anchors:
        decoded_chin=(.42*640-(640-target)*anchor['focus_y'])/target
        assert anchor['chin_y']==pytest.approx(decoded_chin) and decoded_chin<=.650001
        assert anchor['focus_y']>.1


def test_full_request_never_silently_renders_only_a_preview_plan(space):
    root,project=space
    project['timeline']=[{'id':'short','type':'motion','start':0,'end':10}]
    with pytest.raises(core.StudioError,match='cronología'):
        jobs.check_render_authorization(project,20,False)


def test_async_resource_prepare_uses_same_cpu_worker_without_saving_project(space,monkeypatch):
    root,project=space;from studio import resource_review
    monkeypatch.setattr(core,'WORKSPACE_MODE',True)
    calls=[]
    def prepare(aid,options=None,progress=None,cancel=None):
        calls.append((aid,options));progress(.5,'Mocked unit preparation')
        return {'status':'pending','visual_reviewed':False,'audio_listened':False,'reel_approved':False,'frames':[]}
    monkeypatch.setattr(resource_review,'prepare',prepare)
    before=copy.deepcopy(core.get_project(project['id']))
    job=jobs.submit_resource_review(project['source'],{'duration':1,'sequence':True})
    jobs.execute(job['id']);done=jobs.get_job(job['id'])
    assert done['status']=='completed' and calls[0][0]==project['source']
    assert done['result']['visual_reviewed'] is False and core.get_project(project['id'])==before


def test_cancelled_resource_job_never_starts_decoder(space,monkeypatch):
    root,project=space;from studio import resource_review
    monkeypatch.setattr(core,'WORKSPACE_MODE',True)
    monkeypatch.setattr(resource_review,'prepare',lambda *a,**k:pytest.fail('Cancelled work cannot decode'))
    job=jobs.submit_resource_review(project['source'],{'duration':1});jobs.cancel_job(job['id']);jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status']=='cancelled'
