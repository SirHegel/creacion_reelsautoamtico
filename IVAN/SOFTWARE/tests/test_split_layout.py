"""Geometry parity and invalid settings, without altering existing reels."""
import copy
import math

import pytest

from studio import core, render
from test_workspace_api import workspace_api, request
from test_multiservice_modes_api import modes


@pytest.mark.parametrize('height,ratio,upper', [(620,.55,342),(642,.5,322),(284,.5,142),
    (1920,.5,960),(1920,.55,1056),(1080,.55,594),(640,.53,340),(3840,.5,1920)])
def test_split_pixels_even_and_half_up_at_the_browser_tie(height, ratio, upper):
    assert render.split_height(height, ratio) == upper
    assert upper % 2 == 0 and (height-upper) % 2 == 0
    assert abs(upper-height*ratio) <= 1


def test_missing_ratio_preserves_legacy_percentage_and_uses_half_up():
    assert render.split_height(1920) == 1056
    assert render.split_height(620) == 342


@pytest.mark.parametrize('ratio', [None, True, '0.5', .49, .56, float('nan'), float('inf')])
def test_invalid_split_ratio_cannot_enter_a_renderer(ratio):
    with pytest.raises(render.RenderError):
        render.split_height(640, ratio)


def test_new_account_project_explicitly_uses_50_50(workspace_api):
    listener, _ = workspace_api
    code, project = request(listener, 'POST', '/api/projects', {'name': 'Own configurable layout'})
    assert code == 201 and project['settings']['split_motion_ratio'] == .5
    legacy = copy.deepcopy(project)
    legacy['settings'].pop('split_motion_ratio')
    code, saved = request(listener, 'PUT', '/api/projects/' + project['id'], legacy)
    assert code == 200 and 'split_motion_ratio' not in saved['settings']
    assert render.split_height(saved['settings']['height']) == 1056


@pytest.mark.parametrize('ratio', [True, '0.5', .49, .56, None])
def test_http_rejects_invalid_ratio_without_changing_revision(workspace_api, ratio):
    listener, _ = workspace_api
    _, project = request(listener, 'POST', '/api/projects', {'name': 'Ratio guard'})
    project['settings']['split_motion_ratio'] = ratio
    assert request(listener, 'PUT', '/api/projects/' + project['id'], project)[0] == 400
    _, current = request(listener, 'GET', '/api/projects/' + project['id'])
    assert current['revision'] == project['revision']


@pytest.mark.parametrize('height,ratio,expected', [(620,.55,342),(642,.5,322), (640,.53,340)])
def test_actual_canonical_media_preparation_uses_the_project_region(modes, height, ratio, expected):
    _, root, _, project = modes
    project['settings'].update(height=height, split_motion_ratio=ratio)
    project['timeline'] = [{'id': 'layout', 'type': 'split', 'template': 'workflow',
                            'start':0, 'end':1, 'chin_y':.65}]
    saved = core.save_project(project['id'], project)
    config = render._prepare(saved, root, 1)
    assert config['split_height'] == expected
    assert config['scenes'][0]['_design_size'] == (160, expected)
    assert config['source_info']['streams'][0]['codec_type'] == 'video'
    assert config['height'] - config['split_height'] == height-expected
