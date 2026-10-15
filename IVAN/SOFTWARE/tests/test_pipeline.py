"""Durability tests use explicitly mocked engines/providers, not live claims."""
import copy
import json
import math
import threading
import zipfile
from pathlib import Path

import pytest

from studio import analysis,automation,branding,core,hyperframes,pipeline,tracking,fonts,render as native
from test_automation_v05 import space,plan,transcript,ir

REAL_PROBE=native.probe_media


@pytest.fixture
def full(space,monkeypatch):
    root,project=space
    source=project['assets'][0];source['duration']=14
    source['probe']={'streams':[{'index':0,'codec_type':'video','width':360,'height':640},{'index':1,'codec_type':'audio'},{'index':2,'codec_type':'audio'}]}
    core.atomic_json('.estado/assets.json',[source])
    project['settings']['voice_audio_stream']=2
    project=core.save_project(project['id'],project)
    selected_fonts=project['fonts'].copy()
    monkeypatch.setattr(core,'WORKSPACE_MODE',True)
    monkeypatch.setattr(core,'fonts',lambda:selected_fonts)
    declared={'fonts':{role:fonts.inspect_font(core.confined(path),root) for role,path in selected_fonts.items()}}
    monkeypatch.setattr(branding,'validate_project_binding',lambda *a:declared)
    monkeypatch.setattr(core,'manual_fingerprints',lambda:{'unit_public_profile':{'sha256':'1'*64,'missing':False}})
    engine={'analysis.py':'a'*64,'tracking.py':'b'*64,'pipeline.py':'c'*64,'automation.py':'d'*64}
    monkeypatch.setattr(core,'engine_fingerprints',lambda:engine.copy())
    monkeypatch.setattr(analysis,'probe',lambda *a:{'format':{'duration':'14'},'streams':[{'index':0,'codec_type':'video','width':360,'height':640},{'index':1,'codec_type':'audio'},{'index':2,'codec_type':'audio'}]})
    monkeypatch.setattr(analysis,'offline_model',lambda model:{'model':model,'path':root/'mocked_model','files':{}})
    monkeypatch.setattr(automation,'_tracking_runtime',lambda *a:None)
    monkeypatch.setattr(tracking,'_runtime',lambda *a:{'files':{'declared_unit_model':'e'*64}})
    from studio import render,brand_assets
    monkeypatch.setattr(render,'probe_media',lambda *a:{'streams':[{'index':0,'codec_type':'video','width':360,'height':640}]})
    monkeypatch.setattr(brand_assets,'catalog',lambda *a:{'records':[],'revision':0,'digest':'f'*64,'private_fixture':True})
    monkeypatch.setattr(brand_assets,'origin_catalog',lambda:{'entities':[],'downloads_executed':False})
    calls={'asr':0,'tracking':0,'infer':0,'commit':0,'render':0,'export':0}
    def asr(*a,**kw):
        calls['asr']+=1
        assert kw['audio_stream_index']==2
        result=transcript();result['words']=[{'start':i*.5,'end':i*.5+.4,'word':('Conectamos','la','entrada')[i%3]} for i in range(28)]
        result['segments']=[{'start':0,'end':14,'text':' '.join(w['word'] for w in result['words'])}]
        result['engine']='explicit_mocked_asr_fixture';return result
    def face(p,opts,*a):
        calls['tracking']+=1
        samples=[{'time':opts['start']+i*.5,'detected':True,'smoothed':{'focus_x':.5,'focus_y':.5,'chin_y':.6}} for i in range(math.ceil((opts['end']-opts['start'])*2))]
        result={'samples':samples,'evidence':[],'runtime_provenance':{'files':{'declared_unit_model':'e'*64}},'path':f'projects/{p["id"]}/tracking/fixture_{opts["start"]}/measurements.json','engine':'explicit_mocked_tracking_fixture'}
        core.atomic_json(result['path'],result);return result
    monkeypatch.setattr(analysis,'transcribe',asr);monkeypatch.setattr(tracking,'analyze_tracking',face)
    def infer(provider,system,prompt,max_tokens):
        calls['infer']+=1
        data=json.loads(prompt);document=plan(data['seconds'])
        return {'text':json.dumps(document),'provider':provider,'model':'explicit_mocked_provider_not_live','usage':{},'inference_executed':True}
    def commit(draft,expected):
        calls['commit']+=1
        return core.save_project(draft['id'],draft,expected=expected,action='pipeline_compiled')
    def render(p,duration,*a):
        calls['render']+=1
        path=core.confined(f'projects/{p["id"]}/full_unit_fixture.mp4');path.write_bytes(b'explicit mocked renderer output, not a real encoded video')
        return {'path':core.relative(path),'sha256':core.digest(path),'duration':duration,'approved':False,'technical':{'decode_ok':True,'fixture_only':True,'hyperframes':{'fixture_only':True}}}
    monkeypatch.setattr(hyperframes,'verify_receipt',lambda receipt,root:receipt.get('technical',{}).get('fixture_only') is True)
    def export(p,receipt):
        calls['export']+=1;path=core.confined(f'projects/{p["id"]}/full_unit_fixture.zip')
        with zipfile.ZipFile(path,'w') as archive:archive.writestr('project.json',json.dumps(p))
        return {'path':core.relative(path),'sha256':core.digest(path)}
    return root,project,calls,engine,{'infer':infer,'commit':commit,'render':render,'export':export}


@pytest.mark.parametrize('options',[{}, {'mode':'preview','channel':'external'},{'mode':'full','channel':'unknown'},
    {'mode':'full','channel':'api','provider':'openai','confirmed':False},
    {'mode':'full','channel':'external','provider':'openai'}, {'mode':'full','channel':'external','confirmed':True},
    {'mode':'full','channel':'external','max_repairs':True},{'mode':'full','channel':'external','max_repairs':3},
    {'mode':'full','channel':'external','seconds':600},{'mode':'full','channel':'external','asr_model':'large'},
    {'mode':'full','channel':'external','language':True},{'mode':'full','channel':'external','max_tokens':float('nan')}])
def test_options_closed_and_cost_channel_explicit(options):
    with pytest.raises(core.StudioError):pipeline.validate_options(options)


def test_full_library_rejects_legacy_workspace(space):
    _,project=space
    with pytest.raises(core.StudioError,match='exclusivamente'):
        pipeline.create(project['id'],{'mode':'full','channel':'external'})


def test_api_full_runs_all_stages_once_with_global_audio_and_no_approval(full):
    root,project,calls,engine,callbacks=full
    created=pipeline.create(project['id'],{'mode':'full','channel':'api','provider':'openai','confirmed':True})
    result=pipeline.resume(project['id'],**callbacks)
    assert result['status']=='completed' and result['scope_seconds']==14
    assert calls=={'asr':1,'tracking':1,'infer':2,'commit':1,'render':1,'export':1}
    assert len(result['chunks'])==2 and result['inference_calls']==2
    assert result['editorial_approved'] is False and result['audio_listened'] is False
    saved=core.get_project(project['id'])
    assert saved['settings']['voice_audio_stream']==2 and saved['pipeline']['technical_only'] is True
    assert saved['timeline'][-1]['end']==14 and not saved.get('full_authorization')
    pipeline.resume(project['id'],**callbacks)
    assert calls=={'asr':1,'tracking':1,'infer':2,'commit':1,'render':1,'export':1}
    assert pipeline.validate_pipeline_receipt(saved)['mode']=='pipeline_full_technical_draft'


def test_external_waits_then_accepts_declared_plans_and_resumes_without_reanalysis(full):
    root,project,calls,engine,callbacks=full
    created=pipeline.create(project['id'],{'mode':'full','channel':'external'})
    before=core.get_project(project['id'])
    ready=pipeline.resume(project['id'],infer=lambda *a:pytest.fail('External direction cannot call a provider'))
    assert ready['status']=='waiting_external' and calls['asr']==calls['tracking']==1
    assert core.get_project(project['id'])==before
    assert all('context' not in chunk for chunk in pipeline.status(project['id'])['chunks'])
    assert pipeline.status(project['id'],True)['chunks'][0]['context']
    for chunk in ready['chunks']:
        pipeline.submit_external_plan(project['id'],{'generation':created['generation'],'chunk_id':chunk['id'],
            'expected_revision':project['revision'],'document':plan(chunk['end']-chunk['start']),
            'agent':{'name':'Declared external unit client','model':'not verified'}})
    complete=pipeline.resume(project['id'],**{k:v for k,v in callbacks.items() if k!='infer'})
    assert complete['status']=='completed' and calls['infer']==0 and calls['asr']==calls['tracking']==1
    assert complete['inference_calls']==0 and complete['options']['channel']=='external'


def test_stale_revision_fails_before_asr_and_preserves_source(full):
    root,project,calls,engine,_=full
    pipeline.create(project['id'],{'mode':'full','channel':'external'})
    before=core.digest(core.confined(project['assets'][0]['path']))
    project['name']='Changed by user';core.save_project(project['id'],project)
    with pytest.raises(core.StudioError,match='proyecto cambió'):pipeline.resume(project['id'])
    assert calls['asr']==calls['tracking']==0 and pipeline.status(project['id'])['status']=='failed'
    assert core.digest(core.confined(project['assets'][0]['path']))==before


def test_engine_change_invalidates_pipeline_before_model_use(full):
    _,project,calls,engine,_=full
    pipeline.create(project['id'],{'mode':'full','channel':'external'});engine['pipeline.py']='9'*64
    with pytest.raises(core.StudioError,match='Cambió fuente'):pipeline.resume(project['id'])
    assert calls['asr']==0


def test_cancel_is_durable_and_resuming_does_not_transcribe(full):
    _,project,calls,_,_=full
    created=pipeline.create(project['id'],{'mode':'full','channel':'external'})
    pipeline.cancel(project['id'],created['generation'])
    with pytest.raises(core.StudioError,match='cancelada|cancelado'):pipeline.resume(project['id'])
    assert pipeline.status(project['id'])['status']=='cancelled' and calls['asr']==0


def test_missing_callback_never_claims_commit_render_or_export(full):
    _,project,calls,_,callbacks=full
    pipeline.create(project['id'],{'mode':'full','channel':'api','provider':'openai','confirmed':True})
    waiting=pipeline.resume(project['id'],infer=callbacks['infer'])
    assert waiting['status']=='waiting_commit' and calls['commit']==calls['render']==calls['export']==0
    waiting=pipeline.resume(project['id'],infer=callbacks['infer'],commit=callbacks['commit'])
    assert waiting['status']=='waiting_render' and calls['asr']==calls['tracking']==1
    waiting=pipeline.resume(project['id'],infer=callbacks['infer'],commit=callbacks['commit'],render=callbacks['render'])
    assert waiting['status']=='waiting_export' and calls['render']==1


def test_damaged_analysis_artifact_cannot_be_reused(full):
    root,project,calls,_,_=full
    pipeline.create(project['id'],{'mode':'full','channel':'external'});ready=pipeline.resume(project['id'])
    core.confined(ready['stages']['asr']['output']['path']).write_text('{}')
    with pytest.raises(core.StudioError,match='evidencia'):pipeline.resume(project['id'])
    assert calls['asr']==1


def test_callback_cannot_fake_a_real_cas(full):
    _,project,calls,_,callbacks=full
    pipeline.create(project['id'],{'mode':'full','channel':'api','provider':'openai','confirmed':True})
    with pytest.raises(core.StudioError,match='realmente confirmado'):
        pipeline.resume(project['id'],infer=callbacks['infer'],commit=lambda draft,revision:{**draft,'revision':revision+1})
    assert calls['render']==0


def test_output_receipt_cannot_point_to_the_source_or_wrong_duration(full):
    _,project,calls,_,callbacks=full
    pipeline.create(project['id'],{'mode':'full','channel':'api','provider':'openai','confirmed':True})
    source=project['assets'][0]
    def false_render(*a):return {'path':source['path'],'sha256':source['sha256'],'duration':4,'technical':{'decode_ok':True}}
    with pytest.raises(core.StudioError,match='duración completa'):
        pipeline.resume(project['id'],infer=callbacks['infer'],commit=callbacks['commit'],render=false_render)
    assert calls['export']==0


def api_options(**extra):
    return {'mode':'full','channel':'api','provider':'openai','confirmed':True,**extra}


def external_body(state,chunk,document):
    return {'generation':state['generation'],'chunk_id':chunk['id'],'expected_revision':state['project_revision'],
            'document':document,'agent':{'name':'Explicitly declared fixture director'}}


def test_actual_render_metadata_cas_advances_exactly_one_without_changing_edit(full):
    _,project,calls,_,callbacks=full
    original=callbacks['render']
    def rendered(p,*args):
        receipt=original(p,*args);live=core.get_project(p['id'])
        live['renders']=[receipt];live['stage']='technical_export_unapproved'
        saved=core.save_project(p['id'],live,expected=p['revision'],action='rendered')
        receipt['project_revision']=saved['revision'];return receipt
    pipeline.create(project['id'],api_options())
    result=pipeline.resume(project['id'],**{**callbacks,'render':rendered})
    assert result['project_revision']==project['revision']+2
    assert core.get_project(project['id'])['revision']==result['project_revision']
    assert pipeline.validate_pipeline_receipt(core.get_project(project['id']))['editorial_approved'] is False
    pipeline.resume(project['id'],**{**callbacks,'render':rendered})
    assert calls['render']==calls['export']==1


@pytest.mark.parametrize('fault',['reported_only','double_revision','editorial_change'])
def test_render_callback_cannot_forge_or_expand_accepted_revision(full,fault):
    _,project,calls,_,callbacks=full
    original=callbacks['render']
    def bad(p,*args):
        receipt=original(p,*args);live=core.get_project(p['id'])
        if fault=='editorial_change':live['timeline'][0]['title']='Changed behind the pipeline'
        if fault!='reported_only':
            live=core.save_project(p['id'],live,expected=live['revision'],action='rendered')
        if fault=='double_revision':live=core.save_project(p['id'],live,expected=live['revision'],action='rendered')
        receipt['project_revision']=p['revision']+1 if fault=='reported_only' else live['revision']
        return receipt
    pipeline.create(project['id'],api_options())
    with pytest.raises(core.StudioError,match='render cambió'):
        pipeline.resume(project['id'],**{**callbacks,'render':bad})
    assert calls['export']==0


def test_external_replacement_invalidates_prior_compile_and_qc_before_commit(full):
    _,project,calls,_,callbacks=full
    state=pipeline.create(project['id'],{'mode':'full','channel':'external'})
    state=pipeline.resume(project['id'])
    for chunk in state['chunks']:
        pipeline.submit_external_plan(project['id'],external_body(state,chunk,plan(chunk['end']-chunk['start'])))
    waiting=pipeline.resume(project['id'])
    assert waiting['status']=='waiting_commit' and 'qc' in waiting['stages']
    chunk=waiting['chunks'][0];changed=plan(chunk['end']-chunk['start'])
    changed['scenes'][0]['scene_ir']['components'][2]['text']='Cambio explícito'
    updated=pipeline.submit_external_plan(project['id'],external_body(waiting,chunk,changed))
    assert not {'direction','compile','qc'}&updated['stages'].keys()
    complete=pipeline.resume(project['id'],**{k:v for k,v in callbacks.items() if k!='infer'})
    assert complete['status']=='completed' and calls['asr']==calls['tracking']==1
    assert core.get_project(project['id'])['timeline'][0]['motion_design']['elements'][2]['text']=='Cambio explícito'


@pytest.mark.parametrize('stage',pipeline.STAGES[:7])
def test_full_seal_requires_every_analysis_direction_qc_and_commit_stage(full,stage):
    _,project,_,_,callbacks=full
    pipeline.create(project['id'],api_options());pipeline.resume(project['id'],**callbacks)
    state=pipeline._read(project['id']);state['stages'].pop(stage);pipeline._write(state)
    with pytest.raises(core.StudioError,match='Faltan etapas'):
        pipeline.validate_pipeline_receipt(core.get_project(project['id']))


@pytest.mark.parametrize('target',['plan','inference','history','tracking_report'])
def test_full_seal_rechecks_nested_real_files_not_only_stage_wrapper(full,target):
    _,project,_,_,callbacks=full
    pipeline.create(project['id'],api_options());state=pipeline.resume(project['id'],**callbacks)
    if target=='tracking_report':
        tracking_value=pipeline._value(state,state['stages']['tracking']['output']);ref=tracking_value['reports'][0]
    elif target=='history':ref=state['inference_history'][0]
    else:ref=state['chunks'][0][target]
    core.confined(ref['path']).write_text('{}')
    with pytest.raises(core.StudioError,match='evidencia|resultado'):
        pipeline.validate_pipeline_receipt(core.get_project(project['id']))


def test_schema_failure_repair_records_real_calls_and_does_not_repeat_analysis(full):
    _,project,calls,_,callbacks=full
    original=callbacks['infer']
    def repair(*a,**kw):
        if calls['infer']==0:
            calls['infer']+=1;return {'text':'invalid JSON','provider':'openai','model':'explicit_fixture','inference_executed':True}
        assert 'validation_repair' in json.loads(a[2]) or calls['infer']>1
        return original(*a,**kw)
    pipeline.create(project['id'],api_options(max_repairs=1));state=pipeline.resume(project['id'],**{**callbacks,'infer':repair})
    assert state['status']=='completed' and state['repairs_used']==1
    assert state['inference_calls']==state['inference_attempts']==calls['infer']==3
    assert calls['asr']==calls['tracking']==1
    first=pipeline._value(state,state['inference_history'][0]);assert first['accepted'] is False and first['error']
    assert len(state['inference_history'])==3


def test_schema_failure_stops_at_cost_repair_bound_without_fallback(full):
    _,project,calls,_,callbacks=full
    def invalid(*a,**kw):
        calls['infer']+=1;return {'text':'{"unknown":true}','inference_executed':True,'model':'explicit_fixture'}
    pipeline.create(project['id'],api_options(max_repairs=1))
    with pytest.raises(core.StudioError):pipeline.resume(project['id'],**{**callbacks,'infer':invalid})
    state=pipeline.status(project['id']);assert state['status']=='failed'
    assert state['inference_calls']==state['inference_attempts']==2
    assert calls['commit']==calls['render']==calls['export']==0


def test_unconfigured_provider_is_an_explicit_failure_not_a_generated_plan(full):
    _,project,calls,_,callbacks=full
    pipeline.create(project['id'],api_options())
    with pytest.raises(core.StudioError,match='inferencia API confirmada'):
        pipeline.resume(project['id'],**{**callbacks,'infer':lambda *a,**kw:{'inference_executed':False,'text':json.dumps(plan())}})
    state=pipeline.status(project['id']);assert state['inference_calls']==0 and state['inference_attempts']==1
    assert calls['commit']==calls['render']==0


def test_qc_repairs_only_affected_chunk_then_rechecks_actual_new_layout(full,monkeypatch):
    _,project,calls,_,callbacks=full
    original=pipeline.quality_control;observed=[]
    def measured(p):
        value=original(p);observed.append(value)
        if len(observed)==1:value.update(ok=False,issues=[{'scene_id':p['timeline'][0]['id'],'code':'explicit_test_warning'}])
        return value
    monkeypatch.setattr(pipeline,'quality_control',measured)
    pipeline.create(project['id'],api_options(max_repairs=1))
    result=pipeline.resume(project['id'],**callbacks)
    assert result['status']=='completed' and result['repairs_used']==1 and len(observed)==2
    assert calls['infer']==3 and calls['asr']==calls['tracking']==1


def test_restart_reuses_complete_source_analysis_but_refreshes_changed_direction(full):
    _,project,calls,engine,_=full
    pipeline.create(project['id'],{'mode':'full','channel':'external'});first=pipeline.resume(project['id'])
    engine['pipeline.py']='8'*64
    fresh=pipeline.create(project['id'],{'mode':'full','channel':'external'},restart=True)
    assert fresh['generation']==first['generation']+1 and {'asr','tracking'}<=fresh['stages'].keys()
    state=pipeline.resume(project['id']);assert state['status']=='waiting_external'
    assert calls['asr']==calls['tracking']==1 and len(state['history'])==1


def test_voice_change_retranscribes_on_explicit_restart_but_keeps_tracking(full):
    _,project,calls,_,_=full
    pipeline.create(project['id'],{'mode':'full','channel':'external'});pipeline.resume(project['id'])
    current=core.get_project(project['id']);current['settings']['voice_audio_stream']=1
    core.save_project(project['id'],current)
    fresh=pipeline.create(project['id'],{'mode':'full','channel':'external'},restart=True)
    assert 'asr' not in fresh['stages'] and 'tracking' in fresh['stages']
    assert fresh['identity']['voice_audio_stream']==1 and calls['asr']==1


def pause_plan(duration):
    document=plan(max(2,duration));row=copy.deepcopy(document['scenes'][1])
    row.update(start=0,end=duration,narration='',pause=True,scene_ir=ir(duration))
    document['scenes']=[row];return document


def test_a_whole_silent_chunk_keeps_full_clock_and_requires_explicit_pause_plan(full,monkeypatch):
    _,project,calls,_,callbacks=full
    def sparse_asr(*a,**kw):
        calls['asr']+=1;return transcript()
    monkeypatch.setattr(analysis,'transcribe',sparse_asr)
    def direction(provider,system,prompt,max_tokens):
        calls['infer']+=1;context=json.loads(prompt)
        document=plan(context['seconds']) if context['transcript']['words'] else pause_plan(context['seconds'])
        return {'text':json.dumps(document),'model':'explicit_fixture','inference_executed':True}
    pipeline.create(project['id'],api_options());result=pipeline.resume(project['id'],**{**callbacks,'infer':direction})
    assert result['status']=='completed' and result['scope_seconds']==14
    final=core.get_project(project['id']);assert final['timeline'][-1]['pause'] is True and final['timeline'][-1]['narration']==''
    assert final['timeline'][-1]['start']==10 and final['timeline'][-1]['end']==14
    assert calls['asr']==calls['tracking']==1


def test_verified_pause_between_spoken_phrases_is_data_only_and_legacy_rejects_it(full):
    _,project,_,_,_=full
    actual=transcript();actual['words']=[{'start':.1,'end':.5,'word':'Conectamos'},{'start':3.1,'end':3.5,'word':'entrada'}]
    actual['segments']=[{'start':0,'end':4,'text':'Conectamos entrada'}]
    document=plan(4);first,last=document['scenes'];first['narration']=last['narration']='Conectamos'
    middle=copy.deepcopy(pause_plan(2)['scenes'][0]);middle.update(id='pause_scene',start=1,end=3)
    last.update(start=3,scene_ir=ir(1));document['scenes']=[first,middle,last]
    compiled=automation.validate_chunk_plan(project,document,actual,4)
    assert compiled['timeline'][1]['pause'] is True and compiled['timeline'][-1]['end']==4
    with pytest.raises(core.StudioError):automation.validate_plan(project,document,actual,4)


@pytest.mark.parametrize('fault',['actual_words','invented_narration','false_bool','numeric_bool','facts'])
def test_pause_must_be_empty_and_verified_against_real_word_intervals(full,fault):
    _,project,_,_,_=full
    actual={'words':[],'segments':[{'start':0,'end':4,'text':''}]};document=pause_plan(4)
    if fault=='actual_words':actual['words']=[{'start':2,'end':2.5,'word':'voz'}]
    if fault=='invented_narration':document['scenes'][0]['narration']='Inventada'
    if fault=='false_bool':document['scenes'][0]['pause']=False
    if fault=='numeric_bool':document['scenes'][0]['pause']=1
    if fault=='facts':document['scenes'][0]['fact_ids']=['fabricated']
    with pytest.raises(core.StudioError,match='pausa'):
        automation.validate_chunk_plan(project,document,actual,4)


def test_adjacent_chunks_cannot_reset_three_second_face_budget(full):
    _,project,calls,_,callbacks=full
    state=pipeline.create(project['id'],{'mode':'full','channel':'external'});state=pipeline.resume(project['id'])
    first=plan(10);first['scenes'][0].update(type='motion',start=0,end=8,scene_ir=ir(8))
    first['scenes'][1].update(type='split',start=8,end=10,scene_ir=ir(2))
    second=plan(4);second['scenes'][0].update(end=2,scene_ir=ir(2));second['scenes'][1].update(start=2,scene_ir=ir(2))
    for chunk,document in zip(state['chunks'],(first,second)):
        pipeline.submit_external_plan(project['id'],external_body(state,chunk,document))
    with pytest.raises(core.StudioError,match='tres segundos'):
        pipeline.resume(project['id'],**{k:v for k,v in callbacks.items() if k!='infer'})
    assert calls['commit']==calls['render']==0


def test_cancel_after_real_provider_response_never_commits(full):
    _,project,calls,_,callbacks=full;event=threading.Event();original=callbacks['infer']
    def direction(*a,**kw):
        value=original(*a,**kw);event.set();return value
    pipeline.create(project['id'],api_options())
    with pytest.raises(core.StudioError,match='cancelad'):
        pipeline.resume(project['id'],**{**callbacks,'infer':direction},cancel=event)
    assert calls['infer']==1 and calls['commit']==calls['render']==0
    assert pipeline.status(project['id'])['status']=='cancelled'


@pytest.mark.parametrize('seconds',[0,.05,600.01,float('inf'),float('nan')])
def test_real_probe_duration_must_fit_explicit_full_budget_before_analysis(full,monkeypatch,seconds):
    _,project,calls,_,_=full;original=analysis.probe
    monkeypatch.setattr(analysis,'probe',lambda *a:{**original(*a),'format':{'duration':seconds}})
    with pytest.raises(core.StudioError,match='hasta600s'):
        pipeline.create(project['id'],{'mode':'full','channel':'external'})
    assert calls['asr']==calls['tracking']==calls['infer']==0


@pytest.mark.parametrize('member',['../outside','/absolute','.estado/private.json','assets/../../private','assets\\secret'])
def test_export_callback_zip_rejects_escape_and_private_members(full,member):
    _,project,calls,_,callbacks=full
    def bad(p,receipt):
        path=core.confined(f'projects/{p["id"]}/bad_fixture.zip')
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('project.json','{}');archive.writestr(member,'private')
        return {'path':core.relative(path),'sha256':core.digest(path)}
    pipeline.create(project['id'],api_options())
    with pytest.raises(core.StudioError,match='ZIP íntegro'):
        pipeline.resume(project['id'],**{**callbacks,'export':bad})
    assert pipeline.status(project['id'])['status']=='failed'


def test_native_branch_probes_and_decodes_real_cpu_encoded_av_fixture(full,monkeypatch):
    root,project,_,_,_=full
    from studio.jobs import cpu_slot
    path=core.confined('.estado/tmp/pipeline_codec_fixture.mp4')
    with cpu_slot():
        native._run([native._tool('ffmpeg'),'-v','error','-y','-filter_threads','1','-f','lavfi','-i',
                     'color=c=0x234567:s=360x640:r=12:d=0.5','-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=0.5',
                     '-c:v','libx264','-preset','ultrafast','-threads','2','-c:a','aac','-ac','2','-t','0.5',str(path)],root)
        monkeypatch.setattr(native,'probe_media',REAL_PROBE)
        actual=REAL_PROBE(path,root)
        project['pipeline']={'source_sha256':project['assets'][0]['sha256']}
        receipt={'path':core.relative(path),'sha256':core.digest(path),'duration':actual['duration'],'approved':False,
                 'technical':{'decode_ok':True,'original_voice_present':True,'original_audio_present':True,
                              'fixture_audio':'Generated 880Hz test tone; no ASR or narration proof claimed'}}
        pipeline._verify_render(receipt,.5,project)
    assert [s['codec_name'] for s in actual['streams']]==['h264','aac']
    assert next(s for s in actual['streams'] if s['codec_type']=='audio')['channels']==2


def test_export_cannot_substitute_another_edit_or_change_render_after_receipt(full):
    _,project,calls,_,callbacks=full;original=callbacks['export']
    def altered(p,receipt):
        bundle=original(p,receipt);core.confined(receipt['path']).write_bytes(b'changed after bundle generation')
        return bundle
    pipeline.create(project['id'],api_options())
    with pytest.raises(core.StudioError,match='resultado'):
        pipeline.resume(project['id'],**{**callbacks,'export':altered})
    assert pipeline.status(project['id'])['status']=='failed' and calls['export']==1
