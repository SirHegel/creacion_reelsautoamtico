import copy
import json
import os

import pytest

from studio import accounts as account_module
from studio.accounts import Accounts
from studio.core import StudioError
from studio.gateway import shared_urls
from studio.sharing import Sharing


@pytest.fixture
def shared(tmp_path, monkeypatch):
    monkeypatch.setattr(account_module, 'CODE_ROOT', tmp_path)
    accounts = Accounts(tmp_path)
    actors = []
    with accounts.connect() as db:
        for number in range(1, 4):
            uid = 'u_' + f'{number:032x}'
            wid = 'w_' + f'{number:032x}'
            db.execute('INSERT INTO users VALUES (?,?,?,?,?)', (uid, f'user{number}@test.invalid', f'User {number}', 'unused', 1))
            db.execute('INSERT INTO workspaces VALUES (?,?,?)', (wid, uid, f'User {number}'))
    for number in range(1, 4):
        actor = accounts.new_session('u_' + f'{number:032x}')['principal']
        accounts.workspace_path(actor)
        actors.append(actor)
    owner, editor, stranger = actors
    pid = 'p_' + 'a' * 16
    root = accounts.workspace_path(owner)
    project = {'id': pid, 'name': 'Shared film', 'revision': 1, 'source': 'a_video',
               'assets': [{'id': 'a_video', 'sha256': 'c' * 64}], 'timeline': []}
    directory = root / 'projects' / pid
    directory.mkdir(parents=True)
    (directory / 'project.json').write_text(json.dumps(project))
    (root / '.estado').mkdir()
    (root / '.estado/assets.json').write_text(json.dumps([
        {'id': 'a_video', 'sha256': 'c' * 64, 'path': 'assets/video/c.mp4', 'preview_path': 'assets/previews/c.mp4'},
        {'id': 'a_unrelated', 'sha256': 'd' * 64, 'path': 'assets/video/d.mp4'}]))
    return Sharing(accounts), owner, editor, stranger, pid, project, root


def test_share_persists_and_is_limited_to_project(shared):
    sharing, owner, editor, stranger, pid, project, root = shared
    result = sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'editor', 'expected_revision': 0})
    assert len(result['shares']) == 1 and result['email_verified'] is False
    assert sharing.received(editor)['projects'][0]['project_id'] == pid
    assert sharing.received(stranger)['projects'] == []
    reopened = Sharing(sharing.accounts)
    assert reopened.access(editor, owner['workspace']['id'], pid)['can_edit']
    assert not reopened.access(editor, owner['workspace']['id'], pid)['can_automate']
    assert not reopened.access(editor, owner['workspace']['id'], pid)['can_share']
    with pytest.raises(StudioError):
        reopened.access(stranger, owner['workspace']['id'], pid)
    with pytest.raises(StudioError):
        reopened.access(editor, owner['workspace']['id'], 'p_' + 'b' * 16)


def test_viewer_and_revocation_next_lookup(shared):
    sharing, owner, editor, _, pid, _, _ = shared
    result = sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'viewer', 'expected_revision': 0})
    assert sharing.access(editor, owner['workspace']['id'], pid)['can_export']
    with pytest.raises(StudioError) as denied:
        sharing.access(editor, owner['workspace']['id'], pid, write=True)
    assert denied.value.status == 403
    sharing.revoke(owner, pid, result['shares'][0]['id'], result['shares'][0]['revision'])
    assert sharing.received(editor)['projects'] == []
    with pytest.raises(StudioError):
        sharing.access(editor, owner['workspace']['id'], pid)


def test_share_permission_compare_and_swap_and_no_duplicates(shared):
    sharing, owner, editor, _, pid, _, _ = shared
    row = sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'viewer', 'expected_revision': 0})['shares'][0]
    with pytest.raises(StudioError) as conflict:
        sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'editor', 'expected_revision': 0})
    assert conflict.value.status == 409
    updated = sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'editor', 'expected_revision': 1})['shares']
    assert len(updated) == 1 and updated[0]['id'] == row['id'] and updated[0]['revision'] == 2


@pytest.mark.parametrize('data', [None, [], {}, {'email': 'user2@test.invalid', 'role': 'owner'},
                                {'email': 'user2@test.invalid', 'role': 'editor', 'workspace': 'other'},
                                {'email': 'user2@test.invalid', 'role': 'editor', 'expected_revision': True},
                                {'email': 'missing@test.invalid', 'role': 'viewer'}])
def test_invalid_grants(shared, data):
    sharing, owner, _, _, pid, _, _ = shared
    with pytest.raises(StudioError):
        sharing.grant(owner, pid, data)


def test_recipient_cannot_regrant_or_manage_tokens_for_owner(shared):
    sharing, owner, editor, _, pid, _, _ = shared
    row = sharing.grant(owner, pid, {'email': editor['user']['email'], 'role': 'editor', 'expected_revision': 0})['shares'][0]
    with pytest.raises(StudioError):
        sharing.members(editor, pid)
    with pytest.raises(StudioError):
        sharing.revoke(editor, pid, row['id'], row['revision'])
    agent = copy.deepcopy(editor)
    agent['kind'] = 'agent'
    with pytest.raises(StudioError):
        sharing.access(agent, owner['workspace']['id'], pid)


def test_canonical_assets_and_edit_guard(shared):
    sharing, owner, _, _, _, project, _ = shared
    selected = sharing.assets(owner['workspace']['id'], project)
    assert [a['id'] for a in selected] == ['a_video']
    changed = copy.deepcopy(project)
    changed['name'] = 'New title'
    sharing.validate_edit(project, changed)
    changed['assets'].append({'id': 'a_unrelated', 'sha256': 'd' * 64})
    with pytest.raises(StudioError):
        sharing.validate_edit(project, changed)
    changed = copy.deepcopy(project)
    changed['source'] = 'a_unrelated'
    with pytest.raises(StudioError):
        sharing.validate_edit(project, changed)


@pytest.mark.parametrize('relative', ['../secret', '/absolute', 'projects/../other/a.mp4',
                                    'projects//a.mp4', r'projects\other\a.mp4', 'projects/%2e%2e/a.mp4',
                                    '.estado/providers.json', 'exports/other_editable.zip', 'assets/video/d.mp4'])
def test_unrelated_or_escaped_files_denied(shared, relative):
    sharing, owner, _, _, _, project, _ = shared
    assert not sharing.file_allowed(owner['workspace']['id'], project, relative)


def test_project_and_attached_files_allowed(shared):
    sharing, owner, _, _, pid, project, _ = shared
    for name in ['assets/video/c.mp4', 'assets/previews/c.mp4', f'projects/{pid}/technical_preview.mp4', f'exports/{pid}_editable.zip']:
        assert sharing.file_allowed(owner['workspace']['id'], project, name)


@pytest.mark.parametrize('alias', ['symlink', 'hardlink', 'directory_symlink'])
def test_json_aliases_are_rejected(shared, alias):
    sharing, owner, _, _, pid, _, root = shared
    path = root / 'projects' / pid / 'project.json'
    saved = path.read_bytes()
    elsewhere = root / 'elsewhere.json'
    elsewhere.write_bytes(saved)
    if alias == 'directory_symlink':
        directory = path.parent
        path.unlink()
        directory.rmdir()
        directory.symlink_to(root / 'alternate', target_is_directory=True)
        (root / 'alternate').mkdir()
        (root / 'alternate/project.json').write_bytes(saved)
    else:
        path.unlink()
        if alias == 'symlink':
            path.symlink_to(elsewhere)
        else:
            os.link(elsewhere, path)
    with pytest.raises(StudioError) as error:
        sharing.project(owner['workspace']['id'], pid)
    assert error.value.status == 403


def test_private_job_results_are_not_shared(shared):
    sharing, owner, _, _, pid, _, root = shared
    (root / '.estado/jobs.json').write_text(json.dumps([
        {'id': 'j_selected', 'project_id': pid, 'action': 'ivan_prepare', 'status': 'complete',
         'result': {'private_catalog': ['OTHER_PROJECT_RESOURCE']}, 'options': {'private_instructions': 'secret'}},
        {'id': 'j_other', 'project_id': 'p_' + 'b' * 16, 'status': 'complete'}]))
    jobs = sharing.jobs(owner['workspace']['id'], pid)
    assert [j['id'] for j in jobs] == ['j_selected']
    assert 'result' not in jobs[0] and 'options' not in jobs[0]


def test_transport_scope_does_not_rewrite_narration():
    value = {'url': '/api/media/a_video', 'document': {'text': '/api/media/a_video'}, 'text': '/api/media/a_video'}
    result = shared_urls(value, 'owner', 'project', 'actor')
    assert result['url'] == '/w/owner/api/media/a_video?project_id=project&actor_workspace_id=actor'
    assert result['document'] == value['document'] and result['text'] == value['text']


def test_attached_thumbnail_url_and_list_are_scoped_not_other_images(shared):
    sharing, owner, _, _, _, project, root = shared
    path = root / '.estado/assets.json'
    catalog = json.loads(path.read_text())
    catalog[0].update(thumbnail='/api/files/assets/images/c_0.jpg',
                      thumbnails=['assets/images/c_0.jpg', 'assets/images/c_1.jpg'])
    catalog[1]['thumbnail'] = '/api/files/assets/images/private_0.jpg'
    path.write_text(json.dumps(catalog))
    assert sharing.file_allowed(owner['workspace']['id'], project, 'assets/images/c_0.jpg')
    assert sharing.file_allowed(owner['workspace']['id'], project, 'assets/images/c_1.jpg')
    assert not sharing.file_allowed(owner['workspace']['id'], project, 'assets/images/private_0.jpg')
    images = root / 'assets/images'
    images.mkdir(parents=True)
    (images / 'c_0.jpg').symlink_to(root / '.estado/assets.json')
    assert not sharing.file_allowed(owner['workspace']['id'], project, 'assets/images/c_0.jpg')
