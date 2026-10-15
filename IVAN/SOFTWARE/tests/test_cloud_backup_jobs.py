"""Owner queue boundaries. Mocked transport never certifies a live cloud account."""
import copy
import queue

import pytest

from studio import branding, cloud_storage, core, jobs, runtime, mcp


@pytest.fixture
def backup(tmp_path, monkeypatch):
    sandbox = tmp_path / ('w_' + 'b' * 32)
    sandbox.mkdir()
    monkeypatch.setattr(core, 'ROOT', sandbox)
    monkeypatch.setattr(jobs, 'ROOT', sandbox)
    monkeypatch.setattr(jobs, 'SHARED_CPU_LOCK', sandbox / '.estado/cpu_worker.lock')
    monkeypatch.setattr(core, 'WORKSPACE_MODE', True)
    monkeypatch.setattr(runtime, 'CODE_ROOT', sandbox)
    monkeypatch.setattr(jobs, 'QUEUE', queue.Queue())
    monkeypatch.setattr(jobs, 'CANCEL', {})
    monkeypatch.setattr(jobs, 'LOADED_ENGINE_FINGERPRINTS', core.engine_fingerprints())
    branding.bootstrap(sandbox, 'Cloud queue fixture')
    core.setup()
    project = core.create_project('Own cloud queue project')
    config = {'configured': True, 'enabled': True, 'revision': 3}
    monkeypatch.setattr(cloud_storage, 'status', lambda root: copy.deepcopy(config))
    calls = []
    class Storage:
        def __init__(self, root):
            assert root == sandbox
        def enqueue_project(self, wid, pid, revision, **kwargs):
            calls.append(('enqueue', wid, pid, revision, kwargs))
            assert revision == core.get_project(pid)['revision']
            return {'revision': 1}
        def run_outbox(self, wid, pid, revision, **kwargs):
            calls.append(('run', wid, pid, revision, kwargs))
            return {'revision': 2, 'pending': False, 'integrity_verified': True,
                    'live_remote_execution_verified': False, 'transport': 'injected',
                    'project_revision': project['revision'], 'editorial_approved': False}
        def outbox_status(self, wid, pid):
            calls.append(('status', wid, pid))
            return {'revision': 0, 'pending': False, 'status': 'absent', 'integrity_verified': False}
    monkeypatch.setattr(cloud_storage, 'CloudStorage', Storage)
    return sandbox, project, config, calls


def test_owner_backup_queue_uses_fixed_workspace_and_preserves_project(backup):
    root, project, _, calls = backup
    before = core.digest(core.confined(core.project_path(project['id'])))
    job = jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    assert job['cloud_config_revision'] == 3
    jobs.execute(job['id'])
    result = jobs.get_job(job['id'])
    assert result['status'] == 'completed', result
    assert result['result']['live_remote_execution_verified'] is False
    assert 'transporte de prueba' in result['message']
    assert [call[0] for call in calls] == ['enqueue', 'run']
    assert all(call[1] == root.name and call[2] == project['id'] for call in calls)
    assert calls[0][4]['expected_revision'] == 0
    assert calls[0][4]['include_outputs'] is True
    assert before == core.digest(core.confined(core.project_path(project['id'])))


@pytest.mark.parametrize('changes', [
    {'owner_workspace': 'w_' + 'f' * 32}, {'expected_revision': True},
    {'expected_revision': 0}, {'expected_revision': 999},
    {'expected_outbox_revision': True}, {'expected_outbox_revision': -1},
    {'expected_etag': '\r\nInjected: yes'}, {'expected_etag': 5},
    {'expected_etag': 'unquoted'}, {'expected_etag': 'W/"weak"'},
    {'expected_etag': '""'}, {'expected_etag': '"contains space"'},
    {'include_outputs': None}, {'include_outputs': 1},
])
def test_invalid_backup_options_never_enqueue(backup, changes):
    _, project, _, calls = backup
    with pytest.raises(core.StudioError):
        jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision'], **changes})
    assert jobs.list_jobs() == [] and calls == []


@pytest.mark.parametrize('disabled', ['configured', 'enabled'])
def test_disconnected_cloud_fails_before_queue_and_upload(backup, disabled):
    _, project, config, calls = backup
    config[disabled] = False
    with pytest.raises(core.StudioError, match='configurar'):
        jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    assert jobs.list_jobs() == [] and calls == []


def test_operator_cannot_use_saas_backup(backup, monkeypatch):
    _, project, _, calls = backup
    monkeypatch.setattr(core, 'WORKSPACE_MODE', False)
    with pytest.raises(core.StudioError) as denied:
        jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    assert denied.value.status == 403 and calls == []


def test_changed_cloud_config_cannot_run_old_queued_backup(backup):
    _, project, config, calls = backup
    job = jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    config['revision'] = 4
    jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status'] == 'failed' and calls == []


def test_stale_project_revision_fails_without_remote_put(backup):
    _, project, _, calls = backup
    job = jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    project['name'] = 'A later edit'
    core.save_project(project['id'], project)
    jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status'] == 'failed'
    assert all(call[0] != 'run' for call in calls)


def test_no_remote_integrity_receipt_never_completes(backup, monkeypatch):
    _, project, _, _ = backup
    monkeypatch.setattr(cloud_storage.CloudStorage, 'run_outbox', lambda *a, **k: {'pending': False, 'integrity_verified': False})
    job = jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status'] == 'failed'


def test_cancelled_backup_does_not_upload(backup):
    _, project, _, calls = backup
    job = jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
    jobs.cancel_job(job['id'])
    jobs.execute(job['id'])
    assert jobs.get_job(job['id'])['status'] == 'cancelled' and calls == []


def test_mcp_status_and_start_use_owner_without_extra_fields(backup, monkeypatch):
    root, project, _, calls = backup
    monkeypatch.setattr(jobs, 'start_worker', lambda: None)
    result = mcp.call_tool('cloud_backup_get', {'project_id': project['id']})
    assert result['status'] == 'absent' and calls == [('status', root.name, project['id'])]
    with pytest.raises(core.StudioError):
        mcp.call_tool('cloud_backup_start', {'project_id': project['id'], 'expected_revision': project['revision'], 'owner_workspace': 'foreign'})
    queued = mcp.call_tool('cloud_backup_start', {'project_id': project['id'], 'expected_revision': project['revision']})
    assert queued['action'] == 'cloud_backup'
    with pytest.raises(core.StudioError, match='pendiente'):
        jobs.submit(project['id'], 'cloud_backup', {'expected_revision': project['revision']})
