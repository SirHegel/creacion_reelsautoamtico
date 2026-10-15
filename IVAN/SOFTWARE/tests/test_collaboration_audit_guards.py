"""Independent collaboration guards, real HTTP/SQLite and real file Handler.

Transport fixtures isolate project CAS from rendering. File tests use the actual
backend Handler, public OFL notices and private canaries under SOFTWARE/.estado.
No source clip, production account, renderer or inference provider participates.
"""
from __future__ import annotations

import copy
import hashlib
import http.client
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer

import pytest

from studio import branding, core, fonts, gateway, server
from test_collaboration_gateway import collab, grant, scope
from test_gateway_security import listening, request


def delayed_put(c, actor, incoming):
    raw = json.dumps(incoming).encode()
    connection = http.client.HTTPConnection('127.0.0.1', c['server'].server_port, timeout=5)
    connection.putrequest('PUT', scope(c))
    for name, value in {'Cookie': f"{gateway.COOKIE}={actor['session']}",
                        'X-CSRF-Token': actor['principal']['csrf_token'],
                        'X-Workspace-ID': actor['principal']['workspace']['id'],
                        'Content-Type': 'application/json', 'Content-Length': str(len(raw))}.items():
        connection.putheader(name, value)
    connection.endheaders()
    return connection, raw


@pytest.mark.parametrize('barrier,expected', [('revoke', 403), ('logout', 401), ('expiry', 401), ('downgrade', 403)])
def test_pending_http_body_does_not_preserve_revoked_identity_or_permission(collab, monkeypatch, barrier, expected):
    c = collab
    row = grant(c, 'editor')
    waiting = threading.Event()
    original = gateway.GatewayHandler.body
    def observed(self, maximum=10 * 1024 * 1024):
        if self.command == 'PUT': waiting.set()
        return original(self, maximum)
    monkeypatch.setattr(gateway.GatewayHandler, 'body', observed)
    incoming = copy.deepcopy(c['project']); incoming['name'] = 'Body received after invalidation'
    connection, raw = delayed_put(c, c['recipient'], incoming)
    try:
        assert waiting.wait(5)
        if barrier == 'revoke':
            assert request(c, 'DELETE', '/api/projects/' + c['pid'] + '/shares/' + row['id'],
                           {'expected_revision': row['revision']}, c['owner'])[0] == 200
        elif barrier == 'logout':
            assert request(c, 'POST', '/api/auth/logout', {}, c['recipient'])[0] == 200
        elif barrier == 'expiry':
            with c['store'].connect() as db:
                db.execute('UPDATE sessions SET expires=0 WHERE hash=?', (c['recipient']['principal']['credential_hash'],))
        else:
            assert request(c, 'POST', '/api/projects/' + c['pid'] + '/shares',
                           {'email': c['recipient']['principal']['user']['email'], 'role': 'viewer',
                            'expected_revision': row['revision']}, c['owner'])[0] == 201
        connection.send(raw)
        response = connection.getresponse(); value = json.loads(response.read())
        assert response.status == expected, value
        assert 'error' in value
        assert not any(item['method'] == 'PUT' for item in c['transport'].requests)
        assert c['transport'].projects[c['wid']]['name'] == c['project']['name']
    finally:
        connection.close()


def test_admitted_operation_serializes_revoke_without_blocking_other_project(collab, monkeypatch):
    c = collab
    row = grant(c, 'editor')
    entered, release, revoke_started, revoke_done = (threading.Event() for _ in range(4))
    original_backend = gateway.GatewayHandler.backend_json
    def backend(self, principal, path, method='GET', body=None):
        if method == 'PUT':
            entered.set()
            assert release.wait(5)
        return original_backend(self, principal, path, method, body)
    original_revoke = c['server'].sharing.revoke
    def revoke(*args, **kwargs):
        revoke_started.set()
        try: return original_revoke(*args, **kwargs)
        finally: revoke_done.set()
    monkeypatch.setattr(gateway.GatewayHandler, 'backend_json', backend)
    monkeypatch.setattr(c['server'].sharing, 'revoke', revoke)
    incoming = copy.deepcopy(c['project']); incoming['name'] = 'Already admitted edit'
    with ThreadPoolExecutor(max_workers=2) as executor:
        put = executor.submit(request, c, 'PUT', scope(c), incoming, c['recipient'])
        try:
            assert entered.wait(5)
            removal = executor.submit(request, c, 'DELETE', '/api/projects/' + c['pid'] + '/shares/' + row['id'],
                                      {'expected_revision': row['revision']}, c['owner'])
            assert revoke_started.wait(5)
            assert not revoke_done.wait(.1)
            pid = 'p_' + 'b' * 16
            directory = c['store'].workspace_path(c['owner']['principal']) / 'projects' / pid
            directory.mkdir(); other = copy.deepcopy(c['project']); other['id'] = pid
            (directory / 'project.json').write_text(json.dumps(other))
            assert request(c, 'POST', '/api/projects/' + pid + '/shares',
                           {'email': c['recipient']['principal']['user']['email'], 'role': 'viewer', 'expected_revision': 0}, c['owner'])[0] == 201
        finally: release.set()
        assert put.result(5)[0] == 200
        assert removal.result(5)[0] == 200
    assert request(c, 'GET', scope(c), session=c['recipient'])[0] == 403


def test_permission_cas_prevents_stale_regrant_and_revoke(collab):
    c = collab
    first = grant(c, 'viewer')
    changed = grant(c, 'editor')
    assert changed['id'] == first['id'] and changed['revision'] == first['revision'] + 1
    path = '/api/projects/' + c['pid'] + '/shares'
    assert request(c, 'POST', path, {'email': c['recipient']['principal']['user']['email'],
                                  'role': 'viewer', 'expected_revision': first['revision']}, c['owner'])[0] == 409
    assert request(c, 'DELETE', path + '/' + first['id'], {'expected_revision': first['revision']}, c['owner'])[0] == 409
    assert c['server'].sharing.access(c['recipient']['principal'], c['wid'], c['pid'], write=True)['role'] == 'editor'


@pytest.mark.parametrize('body', [{}, {'email': 'member2@test.invalid', 'role': 'editor'},
                                {'email': 'member2@test.invalid', 'role': 'editor', 'expected_revision': True}])
def test_permission_mutation_requires_real_revision(collab, body):
    c = collab
    assert request(c, 'POST', '/api/projects/' + c['pid'] + '/shares', body, c['owner'])[0] == 400
    assert c['server'].sharing.received(c['recipient']['principal'])['projects'] == []


@pytest.fixture
def actual_files(collab, monkeypatch):
    c = collab
    root = c['store'].workspace_path(c['owner']['principal'])
    branding.bootstrap(root, 'Private file guard fixture')
    monkeypatch.setattr(core, 'ROOT', root)
    monkeypatch.setattr(core, 'WORKSPACE_MODE', True)
    monkeypatch.setattr(core, 'HASH_CACHE', {})
    monkeypatch.setattr(server, 'ROOT', root)
    monkeypatch.setenv('ASCENDIA_BACKEND_TOKEN', 'actual-file-guard-fixture')
    raw = b'PUBLIC_ATTACHED_FIXTURE_BYTES'
    path = root / 'assets/images/attached.png'; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    image = {'id': 'a_video', 'kind': 'image', 'path': 'assets/images/attached.png',
             'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw), 'url': '/api/media/a_video'}
    rows = [row for row in core.assets() if row.get('metadata', {}).get('provenance', {}).get('operation') == 'public_font_import']
    face = rows[0]
    rows.append(image); core.atomic_json('.estado/assets.json', rows)
    project = copy.deepcopy(c['project']); project['assets'] = [image, face]
    (root / 'projects' / c['pid'] / 'project.json').write_text(json.dumps(project))
    canary = root / '.estado/own_canary.txt'; canary.write_bytes(b'PRIVATE_CANARY_MUST_NEVER_BE_SERVED')
    backend = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    class FilesBackend:
        def get(self, principal):
            assert principal['workspace']['id'] == c['wid']
            return {'root': root, 'port': backend.server_port, 'secret': 'actual-file-guard-fixture'}
    c['server'].backends = FilesBackend()
    with listening(backend):
        yield c, root, path, canary, face, raw


@pytest.mark.parametrize('actor,method', [('owner', 'GET'), ('recipient', 'GET'), ('owner', 'HEAD'), ('recipient', 'HEAD')])
@pytest.mark.parametrize('mutation,status', [('symlink', 403), ('hardlink', 403), ('modified', 409), ('directory_symlink', 403)])
def test_actual_handler_never_serves_alias_or_changed_canonical_media(actual_files, actor, method, mutation, status):
    c, root, path, canary, _, raw = actual_files
    grant(c, 'viewer')
    if mutation == 'directory_symlink':
        path.unlink(); path.parent.rmdir(); path.parent.symlink_to(root / '.estado', target_is_directory=True)
        (root / '.estado/attached.png').write_bytes(canary.read_bytes())
    elif mutation == 'modified':
        path.write_bytes(canary.read_bytes())
    else:
        path.unlink()
        if mutation == 'symlink': path.symlink_to(canary)
        else: os.link(canary, path)
    url = '/w/' + c['wid'] + '/api/media/a_video'
    if actor == 'recipient': url += '?project_id=' + c['pid']
    code, _, value = request(c, method, url, session=c[actor])
    assert code == status, value
    assert b'PRIVATE_CANARY' not in (value if isinstance(value, bytes) else json.dumps(value).encode())


@pytest.mark.parametrize('actor', ['owner', 'recipient'])
def test_actual_handler_preserves_attached_media_range_and_notice(actual_files, actor):
    c, root, _, _, face, raw = actual_files
    grant(c, 'viewer')
    base = '/w/' + c['wid']; query = '?project_id=' + c['pid'] if actor == 'recipient' else ''
    code, headers, received = request(c, 'GET', base + '/api/media/a_video' + query, session=c[actor], headers={'Range': 'bytes=0-7'})
    assert code == 206 and received == raw[:8]
    assert headers['Content-Range'] == 'bytes 0-7/' + str(len(raw))
    license_info = fonts.license_info(face)
    expected = (root / license_info['notice_path']).read_bytes()
    url = base + '/api/font-notices/' + face['id'] + query
    code, headers, received = request(c, 'GET', url, session=c[actor])
    assert code == 200 and received == expected
    assert hashlib.sha256(received).hexdigest() == license_info['notice_sha256']
    code, headers, received = request(c, 'HEAD', url, session=c[actor])
    assert code == 200 and received == b'' and int(headers['Content-Length']) == len(expected)


def test_shared_notice_cannot_read_other_library_font_or_image(actual_files):
    c, _, _, _, attached, _ = actual_files
    grant(c, 'viewer')
    other = next(row for row in core.assets() if row['kind'] == 'font' and row['id'] != attached['id'])
    prefix = '/w/' + c['wid'] + '/api/font-notices/'
    for aid in (other['id'], 'a_video'):
        code, _, value = request(c, 'GET', prefix + aid + '?project_id=' + c['pid'], session=c['recipient'])
        assert code == 403 and 'error' in value


@pytest.mark.parametrize('mutation', ['bytes', 'symlink'])
def test_actual_font_notice_refuses_changed_or_private_alias(actual_files, mutation):
    c, root, _, canary, face, _ = actual_files
    grant(c, 'viewer')
    notice = root / fonts.license_info(face)['notice_path']
    if mutation == 'bytes': notice.write_bytes(canary.read_bytes())
    else: notice.unlink(); notice.symlink_to(canary)
    url = '/w/' + c['wid'] + '/api/font-notices/' + face['id'] + '?project_id=' + c['pid']
    code, _, value = request(c, 'GET', url, session=c['recipient'])
    assert code in (403, 404, 409)
    assert b'PRIVATE_CANARY' not in json.dumps(value).encode()


@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_font_notice_media_requires_immutable_workspace_url(actual_files, method):
    c, _, _, _, face, _ = actual_files
    code, _, value = request(c, method, '/api/font-notices/' + face['id'], session=c['owner'])
    assert code == 409, value


@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_shared_notice_actor_hint_rejects_cookie_identity_change(actual_files, method):
    c, _, _, _, face, _ = actual_files
    grant(c, 'viewer')
    actor = c['recipient']['principal']['workspace']['id']
    url = '/w/' + c['wid'] + '/api/font-notices/' + face['id'] + '?project_id=' + c['pid'] + '&actor_workspace_id=' + actor
    assert request(c, method, url, session=c['stranger'])[0] == 409
