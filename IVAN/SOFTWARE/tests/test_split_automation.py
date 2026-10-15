"""Actual SceneIR/font geometry, with explicitly mocked landmark/model input.

No inference, narrator, new reel or production approval is claimed by fixtures.
"""
import copy
import json

import pytest

from studio import automation,core,mcp,pipeline,render,typography
from test_automation_v05 import space,plan,transcript
from test_pipeline import full,external_body
from test_pipeline_integration import integrated
from test_pipeline_integration import private_http
from test_resource_review_api import http


@pytest.mark.parametrize('height,ratio,upper',[(620,.5,310),(620,.55,342),(642,.5,322),(642,.55,354),
    (640,.5,320),(640,.55,352),(1080,.5,540),(1080,.55,594),(1920,.5,960),(1920,.55,1056)])
def test_scene_ir_uses_actual_configured_upper_pixel_region(space,height,ratio,upper):
    _,project=space
    project['settings'].update(height=height,split_motion_ratio=ratio)
    document=plan(4)
    document['scenes'][0]['scene_ir']['composition'].update(width=360,height=upper)
    assert render.split_height(height,ratio)==upper and upper%2==0 and (height-upper)%2==0
    compiled=automation.validate_plan(project,document,transcript(),4)
    assert compiled['settings']['height']==height and compiled['settings']['split_motion_ratio']==ratio
    assert compiled['timeline'][0]['type']=='split' and compiled['timeline'][0]['template']=='custom'
    wrong=copy.deepcopy(document);wrong['scenes'][0]['scene_ir']['composition']['height']=upper+2
    with pytest.raises(core.StudioError,match='dimensiones|coincidir|altura|canvas|composición'):
        automation.validate_plan(project,wrong,transcript(),4)


def test_absent_ratio_retains_legacy_upper_region_in_scene_ir(space):
    _,project=space;project['settings']['height']=620;project['settings'].pop('split_motion_ratio',None)
    document=plan(4);document['scenes'][0]['scene_ir']['composition'].update(width=360,height=342)
    compiled=automation.validate_plan(project,document,transcript(),4)
    assert 'split_motion_ratio' not in compiled['settings']
    assert render.split_height(620)==342


@pytest.mark.parametrize('height,ratio',[(620,.5),(620,.55),(642,.5),(642,.55),(640,.5),(640,.55)])
def test_measured_chin_reprojects_to_actual_camera_region_and_not_static_45percent(space,monkeypatch,height,ratio):
    _,project=space
    project['settings'].update(height=height,split_motion_ratio=ratio)
    project['timeline']=[{'id':'camera','start':0,'end':1,'type':'split','decision':{'evidence':[]}}]
    monkeypatch.setattr(render,'probe_media',lambda *a:{'streams':[{'codec_type':'video','width':360,'height':642,'sample_aspect_ratio':'1:1'}]})
    source_chin=.42
    measurements={'samples':[{'time':time,'detected':True,'smoothed':{'focus_x':.5,'focus_y':.18,'chin_y':source_chin}}
                             for time in (0,.5)],'evidence':[]}
    compiled=automation._apply_anchors(project,measurements)
    camera=compiled['timeline'][0];lower=height-render.split_height(height,ratio)
    for anchor in camera['camera_anchors']:
        # Inverse crop on the actual portrait's 642px geometry. This verifies
        # coordinates affect the right lower viewport, rather than a ratio tag.
        reprojection=(source_chin*642-(642-lower)*anchor['focus_y'])/lower
        assert anchor['chin_y']==pytest.approx(reprojection,abs=1e-8)
        assert reprojection==pytest.approx(.65,abs=1e-8) and 0<anchor['focus_y']<1
    assert camera['chin_reviewed'] is False


@pytest.mark.parametrize('ratio',[.5,.55])
def test_pipeline_qc_measures_text_in_the_same_upper_region_as_scene_ir(space,monkeypatch,ratio):
    _,project=space;project['settings'].update(height=642,split_motion_ratio=ratio)
    compiled=automation.validate_plan(project,plan(4),transcript(),4)
    actual_layout=typography.layout_element;seen=[]
    def measure(element,size,*a,**kw):
        seen.append(size);return actual_layout(element,size,*a,**kw)
    monkeypatch.setattr(typography,'layout_element',measure)
    result=pipeline.quality_control(compiled)
    assert seen[0]==(360,render.split_height(642,ratio)) and seen[1]==(360,642)
    assert result['ok'] is True and result['editorial_approved'] is False
    assert result['visual_readability_verified'] is False


@pytest.mark.parametrize('ratio',[.5,.55])
def test_director_context_declares_configured_ratio_and_same_half_up_formula(space,ratio):
    _,project=space;project['settings']['split_motion_ratio']=ratio
    context=automation.direction_context(project,transcript(),{'samples':[]},4,'',require_camera=False)
    assert context['prompt']['settings']['split_motion_ratio']==ratio
    formula=context['prompt']['contract']['split_canvas']
    assert 'floor' in formula and 'split_motion_ratio' in formula and '0.55' in formula
    assert 'round(project.height*.55' not in formula
    assert 'authentic camera below' in formula


def test_ratio_and_context_code_restart_reuses_current_full_asr_tracking(integrated):
    _,project,calls,engine,_=integrated
    first=pipeline.create(project['id'],{'mode':'full','channel':'external'});pipeline.resume(project['id'])
    current=core.get_project(project['id']);current['settings']['split_motion_ratio']=.5
    core.save_project(project['id'],current)
    engine['automation.py']='7'*64;engine['pipeline.py']='8'*64
    next_state=pipeline.create(project['id'],{'mode':'full','channel':'external'},restart=True)
    assert next_state['generation']==first['generation']+1
    assert {'asr','tracking'}<=next_state['stages'].keys()
    ready=pipeline.resume(project['id'])
    assert ready['status']=='waiting_external' and calls['asr']==calls['tracking']==1
    assert all(chunk['context']['input']['settings']['split_motion_ratio']==.5 for chunk in pipeline.status(project['id'],True)['chunks'])


def _external_qc_pending(project,monkeypatch):
    options={'mode':'full','channel':'external'}
    state=pipeline.create(project['id'],options);state=pipeline.resume(project['id'])
    for chunk in state['chunks']:
        pipeline.submit_external_plan(project['id'],external_body(state,chunk,plan(chunk['end']-chunk['start'])))
    actual=pipeline.quality_control
    def measured(p):
        result=actual(p);result.update(ok=False,issues=[{'scene_id':p['timeline'][0]['id'],
            'element_id':'label','code':'explicit_unit_qc_warning','required_seconds':.7}]);return result
    monkeypatch.setattr(pipeline,'quality_control',measured)
    return pipeline.resume(project['id'])


def test_remote_external_director_gets_current_plan_and_actual_qc_without_private_file_access(integrated,monkeypatch):
    _,project,calls,_,_=integrated
    pending=_external_qc_pending(project,monkeypatch)
    assert pending['status']=='waiting_external_repair'
    assert pending['qc']['ok'] is False and pending['qc']['issues'][0]['element_id']=='label'
    assert pending['chunks'][0]['current_plan']==plan(10)
    assert pending['chunks'][0]['context']['input']['repair_issues']==pending['qc']['issues']
    assert calls['infer']==0 and core.get_project(project['id'])['revision']==project['revision']
    compact=pipeline.status(project['id'],False)
    assert 'qc' not in compact and all('context' not in chunk and 'current_plan' not in chunk for chunk in compact['chunks'])
    expanded=mcp.call_tool('pipeline_get',{'project_id':project['id'],'include_context':True})
    assert expanded['qc']['editorial_approved'] is False and expanded['chunks'][0]['current_plan']['schema']==automation.SCHEMA


def test_rest_context_explicitly_exposes_pending_repair_data_and_plan_is_idempotent(private_http,monkeypatch):
    listener,(_,project,calls,_,_)=private_http
    pending=_external_qc_pending(project,monkeypatch);route='/api/projects/'+project['id']+'/pipeline'
    code,_,compact=http(listener,'GET',route)
    assert code==200 and 'qc' not in compact and 'current_plan' not in compact['chunks'][0]
    code,_,expanded=http(listener,'GET',route+'?include_context=true')
    assert code==200 and expanded['qc']['issues']==pending['qc']['issues']
    document=expanded['chunks'][0]['current_plan'];before=pipeline.status(project['id'])
    code,_,same=http(listener,'POST',route+'-plan',external_body(expanded,expanded['chunks'][0],document))
    assert code==200 and same['generation']==before['generation'] and same['stages']==before['stages']
    assert calls['asr']==calls['tracking']==1 and calls['infer']==0


@pytest.mark.parametrize('target',['plan','qc'])
def test_context_projection_rejects_changed_plan_or_qc_proof_and_compact_remains_metadata(integrated,monkeypatch,target):
    _,project,_,_,_=integrated;pending=_external_qc_pending(project,monkeypatch)
    ref=pending['chunks'][0]['plan'] if target=='plan' else pending['stages']['qc']['output']
    core.confined(ref['path']).write_text(json.dumps({'actual':'mutated private fixture proof'}))
    with pytest.raises(core.StudioError,match='evidencia'):
        mcp.call_tool('pipeline_get',{'project_id':project['id'],'include_context':True})
    assert pipeline.status(project['id'],False)['status']=='waiting_external_repair'
