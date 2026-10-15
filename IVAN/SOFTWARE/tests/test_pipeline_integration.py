"""Worker and authenticated HTTP integration with explicitly mocked pixels/AI.

CAS, queue records and editable ZIP export are real private filesystem actions.
The mocked renderer never demonstrates video quality, ASR or live API use.
"""
import copy
import json
import threading
import zipfile
from http.server import ThreadingHTTPServer

import pytest

from studio import analysis,core,hyperframes,jobs,mcp,pipeline,providers,server
from test_pipeline import full,space,api_options,external_body,plan
from test_resource_review_api import http


@pytest.fixture
def integrated(full,monkeypatch):
    root,project,calls,engine,callbacks=full
    monkeypatch.setattr(jobs,'engine_fingerprints',core.engine_fingerprints)
    monkeypatch.setattr(jobs,'LOADED_ENGINE_FINGERPRINTS',core.engine_fingerprints())
    monkeypatch.setattr(jobs,'start_worker',lambda:None)
    monkeypatch.setattr(providers.Connections,'infer',lambda self,*a,**kw:callbacks['infer'](*a,**kw))
    def fixture_renderer(p,render_root,output,seconds=10,progress=None,cancel=None):
        receipt=callbacks['render'](p,seconds,progress,cancel)
        source=root/receipt['path'];output.write_bytes(source.read_bytes())
        receipt.update(path=core.relative(output),sha256=core.digest(output),used_assets=[])
        receipt['technical'].pop('hyperframes',None)
        if progress:progress(.9,'Explicit mocked pixels; no actual render claim.')
        return receipt
    monkeypatch.setattr(hyperframes,'render',fixture_renderer)
    def fixture_verification(receipt,duration,p,cancel=None):
        assert receipt['technical']['fixture_only'] is True
        assert receipt['duration']==duration
        assert receipt['approved'] is False
        pipeline._verify_output(receipt)
    monkeypatch.setattr(pipeline,'_verify_render',fixture_verification)
    # The source fixture was created before the public-profile mock replaced
    # manual hashes; align its acknowledged manual before exercising real gates.
    project['manual']=core.manual_fingerprints()
    project['style']['branding']={'id':'explicit_unit_brand','revision':1,'colors':{},'language':'es',
        'instructions':'','fonts':copy.deepcopy(project['fonts'])}
    project=core.save_project(project['id'],project,action='branding_applied')
    return root,project,calls,engine,callbacks


@pytest.fixture
def private_http(integrated,monkeypatch):
    root,project,*_=integrated
    monkeypatch.setattr(server,'ROOT',root)
    monkeypatch.setattr(server,'start_worker',lambda:None)
    monkeypatch.setenv('ASCENDIA_BACKEND_TOKEN','fixture-backend-token')
    listener=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    listener.daemon_threads=True
    thread=threading.Thread(target=listener.serve_forever,kwargs={'poll_interval':.02},daemon=True);thread.start()
    yield listener,integrated
    listener.shutdown();listener.server_close();thread.join(timeout=3)


def test_worker_full_callbacks_do_actual_two_cas_writes_and_actual_editable_export(integrated):
    root,project,calls,_,_=integrated
    original_source=core.digest(core.confined(project['assets'][0]['path']))
    job=jobs.submit(project['id'],'pipeline',api_options());jobs.execute(job['id'])
    done=jobs.get_job(job['id'])
    assert done['status']=='completed',done
    result=done['result'];saved=core.get_project(project['id'])
    assert result['status']=='completed' and saved['revision']==project['revision']+2
    assert result['project_revision']==saved['revision']
    assert calls['asr']==calls['tracking']==1 and calls['infer']==2 and calls['render']==1
    receipt=saved['renders'][-1]
    assert receipt['mode']=='pipeline_full_technical_draft' and receipt['approved'] is False
    assert receipt['production_conformant'] is False and saved['review']=={}
    assert saved['settings']['voice_audio_stream']==2
    seal=pipeline.validate_pipeline_receipt(saved);assert seal['scope_seconds']==14 and seal['editorial_approved'] is False
    bundle=pipeline._value(result,result['stages']['export']['output'])
    assert bundle['verified_crc_and_sha256'] is True and bundle['project_revision']==saved['revision']
    with zipfile.ZipFile(root/bundle['path']) as archive:
        assert archive.testzip() is None and 'approved_preview.mp4' not in archive.namelist()
        editable=json.loads(archive.read('project.json'))
        assert core.editorial_digest(editable)==core.editorial_digest(saved)
        assert editable['timeline'][-1]['end']==14
        assert set(saved['fonts'].values())<=set(archive.namelist())
        assert archive.read(saved['assets'][0]['path'])==core.confined(saved['assets'][0]['path']).read_bytes()
    assert core.digest(core.confined(saved['assets'][0]['path']))==original_source
    resumed=jobs.submit(project['id'],'pipeline_resume',{'generation':result['generation']});jobs.execute(resumed['id'])
    assert jobs.get_job(resumed['id'])['status']=='completed'
    assert calls['asr']==calls['tracking']==1 and calls['infer']==2 and calls['render']==1
    assert core.get_project(project['id'])['revision']==saved['revision']


def test_cancel_after_renderer_retains_compile_but_does_not_promote_receipt(integrated,monkeypatch):
    root,project,calls,_,_=integrated;original=hyperframes.render
    def cancelled(*a,**kw):
        result=original(*a,**kw);kw['cancel'].supplied.set();return result
    monkeypatch.setattr(hyperframes,'render',cancelled)
    job=jobs.submit(project['id'],'pipeline',api_options());jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status']=='cancelled'
    saved=core.get_project(project['id'])
    assert saved['revision']==project['revision']+1 and not saved['renders']
    assert pipeline.status(project['id'])['status']=='cancelled'
    assert not core.confined(f'exports/{project["id"]}_editable.zip').exists()
    # New explicit queue request has a fresh cancellation event; completed
    # analysis and committed direction are reused, not recomputed.
    monkeypatch.setattr(hyperframes,'render',original)
    next_job=jobs.submit(project['id'],'pipeline_resume',{'generation':1});jobs.execute(next_job['id'])
    assert jobs.get_job(next_job['id'])['status']=='completed'
    assert calls['asr']==calls['tracking']==1 and calls['infer']==2 and calls['render']==2


def test_editorial_change_during_render_never_promotes_or_exports(integrated,monkeypatch):
    _,project,_,_,_=integrated;original=hyperframes.render
    def edited(p,*a,**kw):
        result=original(p,*a,**kw);live=core.get_project(p['id'])
        live['timeline'][0]['title']='Actual user edit while mocked renderer runs'
        core.save_project(p['id'],live,expected=live['revision'])
        return result
    monkeypatch.setattr(hyperframes,'render',edited)
    job=jobs.submit(project['id'],'pipeline',api_options());jobs.execute(job['id'])
    result=jobs.get_job(job['id'])
    assert result['status']=='failed' and 'edición cambió' in result['error']
    assert not core.get_project(project['id'])['renders']
    assert not core.confined(f'exports/{project["id"]}_editable.zip').exists()


def test_queued_cancel_and_stale_project_stop_before_analysis(integrated):
    _,project,calls,_,_=integrated
    job=jobs.submit(project['id'],'pipeline',api_options());jobs.cancel_job(job['id']);jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status']=='cancelled' and calls['asr']==0
    queued=jobs.submit(project['id'],'pipeline',api_options())
    changed=core.get_project(project['id']);changed['name']='Changed revision'
    core.save_project(project['id'],changed)
    jobs.execute(queued['id'])
    assert jobs.get_job(queued['id'])['status']=='failed' and calls['asr']==0


def test_pipeline_job_rejects_duplicate_and_stale_resume_generation(integrated):
    _,project,_,_,_=integrated
    job=jobs.submit(project['id'],'pipeline',{'mode':'full','channel':'external'})
    with pytest.raises(core.StudioError,match='pendiente'):jobs.submit(project['id'],'pipeline',{'mode':'full','channel':'external'})
    jobs.execute(job['id'])
    with pytest.raises(core.StudioError,match='generación'):jobs.submit(project['id'],'pipeline_resume',{'generation':2})
    with pytest.raises(core.StudioError):jobs.submit(project['id'],'pipeline_resume',{'generation':True})


def test_private_http_external_workflow_returns_context_only_when_explicit(private_http):
    listener,(root,project,calls,_,_)=private_http;route='/api/projects/'+project['id']
    code,_,job=http(listener,'POST',route+'/pipeline',{'mode':'full','channel':'external'})
    assert code==202,job
    jobs.execute(job['id']);before=core.get_project(project['id'])
    code,_,state=http(listener,'GET',route+'/pipeline')
    assert code==200 and state['status']=='waiting_external'
    assert all('context' not in chunk for chunk in state['chunks'])
    code,_,state=http(listener,'GET',route+'/pipeline?include_context=true')
    assert code==200 and state['chunks'][0]['context']['input']['full_scope_seconds']==14
    for chunk in state['chunks']:
        code,_,result=http(listener,'POST',route+'/pipeline-plan',external_body(state,chunk,plan(chunk['end']-chunk['start'])))
        assert code==200,result
    assert core.get_project(project['id'])['revision']==before['revision']
    code,_,resume=http(listener,'POST',route+'/pipeline-resume',{'generation':state['generation']})
    assert code==202,resume
    jobs.execute(resume['id']);assert jobs.get_job(resume['id'])['result']['status']=='completed'
    assert calls['infer']==0 and calls['asr']==calls['tracking']==1


@pytest.mark.parametrize('context',['1','True','','true&include_context=false'])
def test_private_http_rejects_ambiguous_context_queries(private_http,context):
    listener,(_,project,*_)=private_http
    route='/api/projects/'+project['id']+'/pipeline?include_context='+context
    assert http(listener,'GET',route)[0] in (400,404)


def test_every_new_private_endpoint_still_requires_internal_backend_token(private_http):
    listener,(_,project,*_)=private_http;route='/api/projects/'+project['id']
    cases=[('GET',route+'/pipeline',None),('POST',route+'/pipeline',{'mode':'full','channel':'external'}),
           ('POST',route+'/pipeline-resume',{'generation':1}),('POST',route+'/pipeline-cancel',{'generation':1}),
           ('POST',route+'/pipeline-plan',{}),('POST','/api/assets/a_raw/audio-tracks',{})]
    for method,path,body in cases:assert http(listener,method,path,body,token='')[0]==401
    assert jobs.list_jobs()==[]


@pytest.mark.parametrize('body',[{'mode':'full','channel':'api','provider':'openai','confirmed':False},
    {'mode':'full','channel':'external','seconds':14},{'mode':'full','channel':'external','confirmed':True}])
def test_http_cannot_queue_unconfirmed_paid_calls_or_unknown_full_options(private_http,body):
    listener,(_,project,*_)=private_http
    assert http(listener,'POST','/api/projects/'+project['id']+'/pipeline',body)[0] in (400,409)
    assert jobs.list_jobs()==[]


def test_mcp_full_start_get_and_external_plan_scope_are_closed(integrated):
    _,project,calls,_,_=integrated
    job=mcp.call_tool('pipeline_start',{'project_id':project['id'],'options':{'mode':'full','channel':'external'}})
    jobs.execute(job['id'])
    compact=mcp.call_tool('pipeline_get',{'project_id':project['id'],'include_context':False})
    expanded=mcp.call_tool('pipeline_get',{'project_id':project['id']})
    assert 'context' not in compact['chunks'][0] and 'context' in expanded['chunks'][0]
    assert calls['infer']==0 and calls['asr']==calls['tracking']==1
    chunk=expanded['chunks'][0];body=external_body(expanded,chunk,plan(chunk['end']-chunk['start']))
    with pytest.raises(core.StudioError):mcp.call_tool('pipeline_plan',{'project_id':project['id'],**body,'model_usage':{'tokens':123}})
    with pytest.raises(core.StudioError):mcp.call_tool('pipeline_resume',{'project_id':project['id'],'generation':True})
    with pytest.raises(core.StudioError):mcp.call_tool('pipeline_get',{'project_id':'p_foreign_workspace'})
    assert core.get_project(project['id'])['revision']==project['revision']


def test_audio_track_auxiliary_job_cannot_use_changed_source_or_apply_to_project(integrated,monkeypatch):
    _,project,calls,_,_=integrated
    monkeypatch.setattr(analysis,'audio_tracks',lambda *a,**kw:pytest.fail('Changed source must not be processed'))
    source=project['assets'][0];job=jobs.submit_audio_tracks(source['id'],{'selected_index':2,'duration':2})
    core.confined(source['path']).write_bytes(b'Actual mutation within this private fixture only')
    jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status']=='failed' and 'medio cambió' in jobs.get_job(job['id'])['error']
    assert core.get_project(project['id'])['revision']==project['revision'] and calls['asr']==0


def test_cancelled_same_input_restart_creates_new_generation_and_reuses_valid_analysis(integrated):
    _,project,calls,_,_=integrated
    initial=jobs.submit(project['id'],'pipeline',{'mode':'full','channel':'external'});jobs.execute(initial['id'])
    old=pipeline.status(project['id']);pipeline.cancel(project['id'],old['generation'])
    blocked=jobs.submit(project['id'],'pipeline_resume',{'generation':old['generation']});jobs.execute(blocked['id'])
    assert jobs.get_job(blocked['id'])['status']=='cancelled'
    restarted=jobs.submit(project['id'],'pipeline_restart',{'generation':old['generation'],
        'options':{'mode':'full','channel':'external'}});jobs.execute(restarted['id'])
    result=jobs.get_job(restarted['id'])
    assert result['status']=='completed',result
    fresh=result['result']
    assert fresh['generation']==old['generation']+1 and fresh['status']=='waiting_external'
    assert fresh['history'][-1]['status']=='cancelled' and calls['asr']==calls['tracking']==1
    assert core.get_project(project['id'])['revision']==project['revision']
    assert core.read_json(pipeline._path(project['id'],'cancel.json'),{})['generation']==old['generation']


def test_restart_worker_generation_cas_rejects_intervening_sdk_restart(integrated):
    _,project,_,_,_=integrated
    initial=jobs.submit(project['id'],'pipeline',{'mode':'full','channel':'external'});jobs.execute(initial['id'])
    pending=jobs.submit(project['id'],'pipeline_restart',{'generation':1,'options':{'mode':'full','channel':'external'}})
    newer=pipeline.create(project['id'],{'mode':'full','channel':'external'},restart=True)
    jobs.execute(pending['id'])
    failed=jobs.get_job(pending['id'])
    assert failed['status']=='failed' and 'generación' in failed['error']
    assert pipeline.status(project['id'])['generation']==newer['generation']==2


def test_restart_endpoint_is_authenticated_closed_and_cost_confirmation_still_required(private_http):
    listener,(_,project,calls,_,_)=private_http;route='/api/projects/'+project['id']
    code,_,first=http(listener,'POST',route+'/pipeline',{'mode':'full','channel':'external'})
    assert code==202;jobs.execute(first['id'])
    body={'generation':1,'options':{'mode':'full','channel':'external'}}
    assert http(listener,'POST',route+'/pipeline-restart',body,token='')[0]==401
    assert http(listener,'POST',route+'/pipeline-restart',{**body,'extra':True})[0]==400
    assert http(listener,'POST',route+'/pipeline-restart',{**body,'generation':True})[0]==400
    assert http(listener,'POST',route+'/pipeline-restart',{**body,'generation':2})[0]==409
    code,_,next_job=http(listener,'POST',route+'/pipeline-restart',body)
    assert code==202,next_job
    jobs.execute(next_job['id'])
    assert jobs.get_job(next_job['id'])['result']['generation']==2 and calls['asr']==calls['tracking']==1
    assert calls['infer']==0
