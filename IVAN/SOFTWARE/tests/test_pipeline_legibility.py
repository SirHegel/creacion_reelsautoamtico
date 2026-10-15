"""Mobile type-size proxies use real font layout, not human-reading claims."""
import copy

import pytest

from studio import automation, core, pipeline, scene_ir
from test_automation_v05 import space


def draft(space,canvas_width=360,font_size=42,**element_changes):
    _,project=space;project=copy.deepcopy(project)
    project['settings'].update(width=canvas_width,height=canvas_width*16//9,fps=30)
    element={'id':'headline','type':'text','text':'Extrae contenido web','font':'primary','font_size':font_size,
             'x':.1,'y':.1,'width':.8,'height':.35,**element_changes}
    project['timeline']=[{'id':'c_000_narrative','type':'motion','template':'custom','start':0,'end':2,
        'narration':'Una skill que extrae toda Internet','motion_design':{'canvas':{'background':'#101318'},'elements':[element]}}]
    project['transcript']={'words':[{'start':0,'end':1.8,'word':'Internet'}],
                           'segments':[{'start':0,'end':2,'text':'Una skill que extrae toda Internet'}]}
    return project


def codes(qc):return {issue['code'] for issue in qc['issues']}


@pytest.mark.parametrize('width',[360,1080])
def test_reproduced_font42_is_too_small_at_every_output_resolution(space,width):
    qc=pipeline.quality_control(draft(space,width))
    assert 'text_too_small' in codes(qc) and qc['ok'] is False
    row=qc['narrative_text'][0]
    assert row['minimum_effective_font_px']==pytest.approx(16*width/360)
    assert row['maximum_visible_font_px']==pytest.approx(42*width/1080)
    assert qc['visual_readability_verified'] is False and qc['editorial_approved'] is False


@pytest.mark.parametrize('width',[360,1080])
def test_minimum_ref48_is_resolution_independent_and_reports_only_proxy(space,width):
    qc=pipeline.quality_control(draft(space,width,48))
    assert qc['ok'] is True and qc['narrative_text'][0]['legible_pose_seconds']==2
    assert qc['narrative_text'][0]['measurement'].startswith('10Hz')
    assert qc['visual_readability_verified'] is False and qc['audio_listened'] is False


@pytest.mark.parametrize('width',[360,1080])
def test_primary_headline_allows_small_secondary_ui_labels(space,width):
    project=draft(space,width,108,text='Web')
    project['timeline'][0]['motion_design']['elements'].append({'id':'helper','type':'text','text':'UI',
        'font':'accent','font_size':24,'x':.1,'y':.65,'width':.3,'height':.15,'start':.5,'end':.7})
    qc=pipeline.quality_control(project)
    assert qc['ok'] is True and 'text_too_small' not in codes(qc)


@pytest.mark.parametrize('scale,expected',[(.5,False),(1,True),(1.5,True)])
def test_pose_scale_affects_effective_font_not_only_declared_font(space,scale,expected):
    project=draft(space,360,54,text='Web',x=.35,width=.3)
    project['timeline'][0]['motion_design']['elements'][0]['keyframes']=[{'time':0,'scale':scale}]
    qc=pipeline.quality_control(project)
    assert qc['ok'] is expected
    assert qc['narrative_text'][0]['maximum_visible_font_px']==pytest.approx(18*scale)


@pytest.mark.parametrize('span',[.1,.2,.6])
def test_big_but_brief_text_does_not_make_small_body_legible(space,span):
    project=draft(space,360,108,text='Web',end=span)
    project['timeline'][0]['motion_design']['elements'].append({'id':'small','type':'text','text':'Contenido',
        'font_size':34,'x':.1,'y':.65,'width':.7,'height':.15})
    qc=pipeline.quality_control(project)
    assert 'missing_legible_text' in codes(qc) and qc['ok'] is False
    assert qc['narrative_text'][0]['legible_pose_seconds']==pytest.approx(span)
    assert qc['narrative_text'][0]['required_seconds']==.7


@pytest.mark.parametrize('change',[{'opacity':0},{'text':' \n\t '},
    {'keyframes':[{'time':0,'x':1.5}]},
    {'mask':{'type':'inset'},'keyframes':[{'time':0,'mask_progress':0}]}])
def test_hidden_or_offscreen_large_text_cannot_supply_primary_readability(space,change):
    qc=pipeline.quality_control(draft(space,360,108,**change))
    assert 'missing_legible_text' in codes(qc) and not qc['ok']


def test_large_text_with_pop_and_reveal_is_evaluated_on_actual_clock(space):
    qc=pipeline.quality_control(draft(space,360,108,text='Web',
        text_animation={'preset':'typewriter','duration':.5,'exit':'fade','exit_duration':.2}))
    assert qc['ok'] is True and 1.1<=qc['narrative_text'][0]['legible_pose_seconds']<=1.4


def test_arbitrary_roles_and_pause_flags_do_not_override_real_narrated_scene(space):
    project=draft(space)
    scene=project['timeline'][0];scene['pause']=True;scene['narration']='';scene['allow_small_text']=True
    scene['motion_design']['elements'][0]['role']='secondary'
    assert 'text_too_small' in codes(pipeline.quality_control(project))


def test_visual_narrative_without_text_elements_is_not_forced_to_add_a_title(space):
    project=draft(space)
    project['timeline'][0]['motion_design']['elements']=[{'id':'visual','type':'shape','x':.2,'y':.2,'width':.5,'height':.3}]
    qc=pipeline.quality_control(project)
    assert qc['ok'] is True and qc['narrative_text'][0]['applicable'] is False


def test_actual_silent_pause_keeps_small_interface_labels_optional(space):
    project=draft(space)
    project['transcript']={'words':[],'segments':[]};project['timeline'][0]['narration']='';project['timeline'][0]['pause']=True
    qc=pipeline.quality_control(project)
    assert qc['ok'] is True and qc['narrative_text'][0]['applicable'] is False


@pytest.mark.parametrize('ratio',[.5,.55])
def test_split_checks_reference_width_not_smaller_region_height(space,ratio):
    project=draft(space,360,42)
    project['settings']['split_motion_ratio']=ratio;project['timeline'][0]['type']='split'
    qc=pipeline.quality_control(project)
    assert 'text_too_small' in codes(qc)
    assert qc['narrative_text'][0]['minimum_effective_font_px']==16


def test_schema_and_external_director_context_explicitly_explain_reference_units(space):
    _,project=space
    variants=scene_ir.describe_schema()['properties']['components']['items']['oneOf']
    text=next(v for v in variants if v['properties']['type']['const']=='text')
    assert '1080' in text['properties']['font_size']['description']
    assert '42' in text['properties']['font_size']['description'] and '14' in text['properties']['font_size']['description']
    context=automation.direction_context(project,{'words':[],'segments':[]},{'samples':[]},2,'',require_camera=False)
    guidance=context['prompt']['contract']['text_bounds']
    assert '1080' in guidance and '360' in guidance and '48' in guidance and '16' in guidance


def test_legible_headline_need_not_repeat_asr_tokens(space):
    project=draft(space,360,72,width=.9)
    assert project['timeline'][0]['motion_design']['elements'][0]['text'] not in project['transcript']['segments'][0]['text']
    assert pipeline.quality_control(project)['ok'] is True


def test_subsample_flash_is_clipped_to_real_element_duration_not_a_full_qc_tick(space):
    project=draft(space,360,108,text='Web',end=.01)
    project['timeline'][0]['end']=.1
    qc=pipeline.quality_control(project)
    assert 'missing_legible_text' in codes(qc)
    assert qc['narrative_text'][0]['legible_pose_seconds']==.01
    assert qc['narrative_text'][0]['required_seconds']==.1
