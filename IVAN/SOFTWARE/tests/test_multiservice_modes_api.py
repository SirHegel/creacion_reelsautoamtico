"""Actual private HTTP, selected-track CPU mixing and manual full export.

The synthetic source contains silence and a tone, never alleged speech. Queue
execution is explicit; no provider, ASR, parent project or cloud is involved.
"""
import copy
import queue
import wave

import numpy as np
import pytest

from studio import analysis, core, jobs, media_tools
from test_resource_review_api import http
from test_workspace_api import workspace_api


@pytest.fixture
def modes(workspace_api, monkeypatch):
    listener, root = workspace_api
    for module in (analysis, jobs):
        monkeypatch.setattr(module, 'ROOT', root)
    monkeypatch.setattr(jobs, 'SHARED_CPU_LOCK', root / '.estado/cpu_worker.lock')
    monkeypatch.setattr(jobs, 'QUEUE', queue.Queue())
    monkeypatch.setattr(jobs, 'CANCEL', {})
    monkeypatch.setattr(jobs, 'WORKER', None)
    monkeypatch.setattr(jobs, 'start_worker', lambda: None)
    monkeypatch.setattr(jobs, 'LOADED_ENGINE_FINGERPRINTS', core.engine_fingerprints())
    source = root / '.estado/tmp/selected_audio.mkv'
    with jobs.cpu_slot():
        media_tools._run('ffmpeg', ['-nostdin', '-v', 'error', '-filter_threads', '1',
            '-filter_complex_threads', '1', '-f', 'lavfi', '-i', 'color=c=navy:s=160x284:r=10:d=12',
            '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo:d=12', '-itsoffset', '0.5',
            '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=11.5',
            '-map', '0:v:0', '-map', '1:a:0', '-map', '2:a:0', '-c:v', 'ffv1',
            '-c:a', 'pcm_s16le', '-ac:a:1', '2', '-threads', '1', '-n', str(source)], root)
        item = core.register_asset(source, kind='video')
    project = core.create_project('Manual and audio protocol fixture', item['id'])
    project['settings'].update(width=160, height=284, fps=10, engine='native')
    project['timeline'] = [{'id': 'own_motion', 'start': 0, 'end': 12, 'type': 'motion',
                            'template': 'workflow', 'title': 'Fuente propia'}]
    project = core.save_project(project['id'], project)
    return listener, root, item, project


def test_real_http_audio_job_selects_global_track_and_preserves_original(modes):
    listener, root, item, project = modes
    status, _, job = http(listener, 'POST', '/api/assets/' + item['id'] + '/audio-tracks',
                          {'start': 0, 'duration': 2})
    assert status == 202, job
    jobs.execute(job['id'])
    status, _, completed = http(listener, 'GET', '/api/jobs/' + job['id'])
    assert status == 200 and completed['status'] == 'completed', completed
    result = completed['result']
    assert result['recommended_stream_index'] == 2
    assert result['voice_verified'] is False and result['audio_listened'] is False
    assert result['source_sha256'] == item['sha256']
    assert core.get_project(project['id'])['revision'] == project['revision']
    assert core.digest(root / item['path']) == item['sha256']
    assert http(listener, 'POST', '/api/assets/' + item['id'] + '/audio-tracks',
                {'selected_index': True})[0] == 400


@pytest.mark.parametrize('index', [True, '2', 2.0, -1, 1024, 0, 42])
def test_voice_selection_rejects_non_audio_or_non_global_index(modes, index):
    listener, _, _, project = modes
    draft = copy.deepcopy(project)
    draft['settings']['voice_audio_stream'] = index
    assert http(listener, 'PUT', '/api/projects/' + project['id'], draft)[0] in (400, 409)
    assert core.get_project(project['id'])['revision'] == project['revision']


def test_manual_full_render_actual_selected_pcm_clock_and_editable(modes):
    listener, root, item, project = modes
    draft = copy.deepcopy(project)
    draft['settings']['voice_audio_stream'] = 2
    code, _, saved = http(listener, 'PUT', '/api/projects/' + project['id'], draft)
    assert code == 200, saved
    route = '/api/projects/' + project['id'] + '/render'
    # Legacy technical-preview authorization remains limited to ten seconds.
    assert http(listener, 'POST', route, {'seconds': 12, 'technical': True})[0] == 409
    code, _, job = http(listener, 'POST', route,
                         {'seconds': 12, 'technical': True, 'draft_full': True, 'engine': 'native'})
    assert code == 202, job
    jobs.execute(job['id'])
    completed = jobs.get_job(job['id'])
    assert completed['status'] == 'completed', completed
    receipt = completed['result']
    assert receipt['mode'] == 'manual_full_technical_draft'
    assert receipt['approved'] is False and receipt['production_conformant'] is False
    assert receipt['technical']['decode_ok'] is True
    assert receipt['technical']['original_audio_stream_index'] == 2
    assert receipt['duration'] == pytest.approx(12, abs=.02)
    with jobs.cpu_slot():
        decoded = media_tools.process({'id': 'rendered_audio_fixture', 'path': receipt['path'],
            'sha256': receipt['sha256'], 'duration': 12}, 'extract_audio',
            {'channels': 1}, root)
    with wave.open(str(root / decoded['path']), 'rb') as audio:
        rate = audio.getframerate()
        samples = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2').astype(float) / 32768
    assert np.max(np.abs(samples[:int(.4 * rate)])) < .001
    active = samples[int(1 * rate):int(2 * rate)]
    assert np.sqrt(np.mean(active ** 2)) > .04
    frequency = np.argmax(np.abs(np.fft.rfft(active))) * rate / len(active)
    assert frequency == pytest.approx(880, abs=2)
    code, _, bundle = http(listener, 'POST', '/api/projects/' + project['id'] + '/export', {})
    assert code == 200 and bundle['verified_crc_and_sha256'] is True, bundle
    assert core.digest(root / item['path']) == item['sha256']
    current = core.get_project(project['id'])
    assert not current.get('approved_export') and not current.get('review')
    assert http(listener, 'GET', '/api/media/' + item['id'])[0] == 200


def test_private_font_notice_route_has_actual_bytes_and_no_unrestricted_text(modes):
    listener, root, _, project = modes
    font = next(item for item in project['assets'] if item.get('kind') == 'font')
    code, _, data = http(listener, 'GET', '/api/font-notices/' + font['id'])
    assert code == 200 and b'SIL OPEN FONT LICENSE' in data.upper()
    path = core.confined(font['metadata']['font_notice']['path'])
    assert data == path.read_bytes()
    assert http(listener, 'GET', '/api/files/' + font['metadata']['font_notice']['path'])[0] == 403
