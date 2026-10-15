"""Real HTTP for disconnected cloud: no fake synchronization or config writes."""
import json
import queue
import threading
from http.server import ThreadingHTTPServer

import pytest

from studio import branding, core, jobs, runtime, server
from test_workspace_api import request


@pytest.fixture
def cloud_http(tmp_path, monkeypatch):
    admin = tmp_path / 'admin'
    admin.mkdir()
    root = admin / 'workspaces' / ('w_' + 'c' * 32)
    root.mkdir(parents=True)
    branding.bootstrap(root, 'Offline cloud HTTP fixture')
    for module in (core, jobs, server):
        monkeypatch.setattr(module, 'ROOT', root)
    monkeypatch.setattr(core, 'WORKSPACE_MODE', True)
    monkeypatch.setattr(runtime, 'CODE_ROOT', admin)
    monkeypatch.setattr(jobs, 'QUEUE', queue.Queue())
    monkeypatch.setattr(jobs, 'CANCEL', {})
    monkeypatch.setattr(jobs, 'start_worker', lambda: None)
    monkeypatch.setattr(jobs, 'LOADED_ENGINE_FINGERPRINTS', core.engine_fingerprints())
    monkeypatch.setenv('ASCENDIA_BACKEND_TOKEN', 'fixture-backend-token')
    core.setup()
    project = core.create_project('Own disconnected cloud project')
    local = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    thread = threading.Thread(target=local.serve_forever, daemon=True)
    thread.start()
    yield local, admin, project
    local.shutdown()
    thread.join(timeout=5)
    local.server_close()


def test_actual_cloud_status_is_disconnected_without_config_side_effects(cloud_http):
    local, admin, project = cloud_http
    before = core.digest(core.project_path(project['id']))
    code, cloud = request(local, 'GET', '/api/cloud-storage')
    assert code == 200 and cloud['configured'] is False and cloud['remote'] is False
    assert cloud['project_backup_jobs'] is True
    code, backup = request(local, 'GET', '/api/projects/' + project['id'] + '/cloud-backup')
    assert code == 200, backup
    assert backup['revision'] == 0 and backup['integrity_verified'] is False
    assert backup['live_remote_execution_verified'] is False
    assert not (admin / '.estado/cloud_storage').exists()
    assert before == core.digest(core.project_path(project['id']))


def test_offline_backup_rejects_queue_and_cannot_set_credentials(cloud_http):
    local, admin, project = cloud_http
    route = '/api/projects/' + project['id'] + '/cloud-backup'
    code, error = request(local, 'POST', route, {'expected_revision': project['revision']})
    assert code == 409 and 'configurar' in error['error']
    assert jobs.list_jobs() == [] and not (admin / '.estado/cloud_storage').exists()
    for method in ('POST', 'PUT', 'DELETE'):
        code, _ = request(local, method, '/api/cloud-storage', {'credentials': 'synthetic-canary-never-a-real-key'})
        assert code == 404
    assert not (admin / '.estado/cloud_storage').exists()


def test_cloud_mcp_get_has_real_empty_receipt_and_closed_remote_owner_arguments(cloud_http):
    local, _, project = cloud_http
    code, result = request(local, 'POST', '/api/mcp', {'jsonrpc': '2.0', 'id': 1,
        'method': 'tools/call', 'params': {'name': 'cloud_backup_get', 'arguments': {'project_id': project['id']}}})
    assert code == 200 and result['result']['isError'] is False
    backup = json.loads(result['result']['content'][0]['text'])
    assert backup['integrity_verified'] is False and backup['revision'] == 0
    code, result = request(local, 'POST', '/api/mcp', {'jsonrpc': '2.0', 'id': 2,
        'method': 'tools/call', 'params': {'name': 'cloud_backup_start', 'arguments': {
            'project_id': project['id'], 'expected_revision': project['revision'], 'owner_workspace': 'foreign'}}})
    assert code == 200 and result['result']['isError'] is True
    assert jobs.list_jobs() == []
