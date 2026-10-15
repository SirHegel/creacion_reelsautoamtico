"""Real HTTP/SQLite ACL and CAS tests; transport fixtures perform no rendering."""
import copy
import json
import threading
import urllib.parse
from http.server import ThreadingHTTPServer

import pytest

from studio import accounts, gateway
from studio.sharing import Sharing
from test_gateway_security import TransportFixtureHandler, FixtureBackends, listening, request


class ProjectTransport(TransportFixtureHandler):
    def reply(self, head=False):
        owner = self.server.owners.get(self.headers.get('X-Ascendia-Backend'))
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length) if length else b''
        self.server.requests.append({'owner': owner, 'method': self.command, 'path': self.path,
                                     'body': raw, 'headers': dict(self.headers)})
        if owner is None:
            return self.send_json({'error': 'Unauthorized transport'}, 401, head)
        path = urllib.parse.urlsplit(self.path).path
        project = self.server.projects[owner]
        pid = project['id']
        if path == '/api/projects/' + pid:
            if self.command == 'PUT':
                incoming = json.loads(raw)
                with self.server.lock:
                    current = self.server.projects[owner]
                    if incoming.get('revision') != current['revision']:
                        return self.send_json({'error': 'Revision conflict', 'details': {'revision': current['revision']}}, 409, head)
                    incoming['revision'] += 1
                    self.server.projects[owner] = incoming
                    directory = self.server.store.workspace_path(self.server.principals[owner]) / 'projects' / pid
                    (directory / 'project.json').write_text(json.dumps(incoming))
                project = incoming
            return self.send_json(project, head=head)
        if path == '/api/status':
            return self.send_json({'app': 'fixture', 'version': 'test', 'scope': 'private-path', 'policy': {'private_branding': 'PRIVATE_FUTURE'},
                                   'capabilities': {'render': {'available': True}}, 'manual': {}, 'restart_required': False,
                                   'active_external': ['PRIVATE_PROCESS']}, head=head)
        if path == '/api/font-library':
            return self.send_json({'roles': [{'name': 'PRIVATE_FUTURE_FONT'}],
                                   'fonts': [{'id': 'a_font', 'asset_id': 'a_font'}, {'id': 'a_private_font', 'asset_id': 'a_private_font'}]}, head=head)
        if path == '/api/templates':
            return self.send_json({'templates': []}, head=head)
        if path == '/api/text-presets':
            return self.send_json({'presets': []}, head=head)
        if path == '/api/manual':
            return self.send_json({'documents': [{'name': 'Software style', 'content': 'Public style'}]}, head=head)
        if path.startswith('/api/media/'):
            if path not in ('/api/media/a_video', '/api/media/a_font'):
                return self.send_json({'error': 'Unknown asset'}, 404, head)
            value = ('ATTACHED:' + owner).encode()
            if self.headers.get('Range') == 'bytes=0-7':
                return self.send_bytes(value[:8], 206, 'video/mp4', head,
                                       {'Content-Range': f'bytes 0-7/{len(value)}', 'Accept-Ranges': 'bytes'})
            return self.send_bytes(value, 200, 'video/mp4', head)
        if path.endswith('/export'):
            return self.send_json({'url': f'/api/files/exports/{pid}_editable.zip'}, head=head)
        if path == '/api/text-layout':
            return self.send_json({'layout': {'measured': True}, 'persisted': False}, head=head)
        return self.send_json({'error': 'Unsupported fixture'}, 404, head)


@pytest.fixture
def collab(tmp_path):
    store = accounts.Accounts(tmp_path)
    sessions = []
    with store.connect() as db:
        for number in range(1, 4):
            uid, wid = 'u_' + f'{number:032x}', 'w_' + f'{number:032x}'
            db.execute('INSERT INTO users VALUES (?,?,?,?,?)', (uid, f'member{number}@test.invalid', f'Member {number}', 'unused', 1))
            db.execute('INSERT INTO workspaces VALUES (?,?,?)', (wid, uid, f'Member {number}'))
    for number in range(1, 4):
        sessions.append(store.new_session('u_' + f'{number:032x}'))
    owner, recipient, stranger = sessions
    wid = owner['principal']['workspace']['id']
    pid = 'p_' + 'a' * 16
    project = {'id': pid, 'name': 'Collaborative film', 'revision': 1, 'source': 'a_video',
               'assets': [{'id': 'a_video', 'sha256': 'c' * 64}, {'id': 'a_font', 'sha256': 'f' * 64}],
               'style': {'branding': {'fonts': {'primary': {'family': 'Project Font', 'style': 'Bold'}}}},
               'timeline': [], 'renders': []}
    for session in sessions:
        root = store.workspace_path(session['principal'])
        directory = root / 'projects' / pid
        directory.mkdir(parents=True)
        (directory / 'project.json').write_text(json.dumps(project))
        (root / '.estado').mkdir()
        (root / '.estado/assets.json').write_text(json.dumps([
            {'id': 'a_video', 'sha256': 'c' * 64, 'path': 'assets/video/c.mp4', 'url': '/api/media/a_video'},
            {'id': 'a_font', 'sha256': 'f' * 64, 'kind': 'font', 'path': 'assets/fonts/f.ttf'},
            {'id': 'a_unrelated', 'sha256': 'd' * 64, 'path': 'assets/video/d.mp4'}]))
    transport = ThreadingHTTPServer(('127.0.0.1', 0), ProjectTransport)
    transport.owners, transport.requests, transport.store = {}, [], store
    transport.projects = {s['principal']['workspace']['id']: copy.deepcopy(project) for s in sessions}
    transport.principals = {s['principal']['workspace']['id']: s['principal'] for s in sessions}
    transport.lock = threading.RLock()
    public = ThreadingHTTPServer(('127.0.0.1', 0), gateway.GatewayHandler)
    public.public_origin = f'http://127.0.0.1:{public.server_port}'
    public.allowed_hosts = {f'127.0.0.1:{public.server_port}'}
    public.accounts, public.sharing = store, Sharing(store)
    public.backends = FixtureBackends(store, transport)
    with listening(transport), listening(public):
        yield {'root': tmp_path, 'store': store, 'server': public, 'transport': transport,
               'owner': owner, 'recipient': recipient, 'stranger': stranger, 'pid': pid, 'wid': wid, 'project': project}


def grant(c, role='viewer'):
    _, _, current = request(c, 'GET', '/api/projects/' + c['pid'] + '/shares', session=c['owner'])
    revision = next((row['revision'] for row in current['shares'] if row['email'] == c['recipient']['principal']['user']['email']), 0)
    status, _, result = request(c, 'POST', '/api/projects/' + c['pid'] + '/shares',
                                {'email': c['recipient']['principal']['user']['email'], 'role': role, 'expected_revision': revision}, c['owner'])
    assert status == 201
    return result['shares'][0]


def scope(c, suffix=''):
    return '/w/' + c['wid'] + '/api/projects/' + c['pid'] + suffix


def test_shared_context_returns_only_project_resources(collab):
    c = collab
    grant(c)
    status, _, value = request(c, 'GET', scope(c, '/editor-context'), session=c['recipient'])
    assert status == 200
    assert value['access']['role'] == 'viewer' and not value['access']['can_edit']
    assert value['access']['actor_workspace_id'] == c['recipient']['principal']['workspace']['id']
    assert {a['id'] for a in value['assets']} == {'a_video', 'a_font'}
    assert [a['id'] for a in value['font_library']['fonts']] == ['a_font']
    encoded = json.dumps(value)
    assert 'PRIVATE_' not in encoded and 'a_unrelated' not in encoded and 'private-path' not in encoded
    assert '?project_id=' in value['assets'][0]['url'] and 'actor_workspace_id=' in value['assets'][0]['url']
    status, _, listing = request(c, 'GET', '/api/shared/projects', session=c['recipient'])
    assert status == 200 and listing['projects'][0]['project_id'] == c['pid']


def test_viewer_reads_exports_but_cannot_edit(collab):
    c = collab
    grant(c)
    assert request(c, 'GET', scope(c), session=c['recipient'])[0] == 200
    assert request(c, 'PUT', scope(c), c['project'], c['recipient'])[0] == 403
    assert request(c, 'POST', scope(c, '/render'), {'technical': True}, c['recipient'])[0] == 403
    assert request(c, 'POST', scope(c, '/export'), {}, c['recipient'])[0] == 200


def test_editor_revision_conflict_prevents_overwrite(collab):
    c = collab
    grant(c, 'editor')
    first = copy.deepcopy(c['project']); first['name'] = 'Editor change'
    status, _, updated = request(c, 'PUT', scope(c), first, c['recipient'])
    assert status == 200 and updated['revision'] == 2
    stale = copy.deepcopy(c['project']); stale['name'] = 'Stale overwrite'
    status, _, result = request(c, 'PUT', scope(c), stale, c['recipient'])
    assert status == 409 and result['details']['revision'] == 2
    assert c['transport'].projects[c['wid']]['name'] == 'Editor change'


@pytest.mark.parametrize('route', ['/api/providers', '/api/agent-tokens', '/api/branding', '/api/assets', '/api/projects', '/api/tasks', '/mcp'])
def test_share_never_grants_owner_global_endpoints(collab, route):
    c = collab
    grant(c, 'editor')
    before = len(c['transport'].requests)
    path = '/w/' + c['wid'] + route + '?project_id=' + c['pid']
    assert request(c, 'GET', path, session=c['recipient'])[0] == 403
    assert len(c['transport'].requests) == before


def test_attached_media_ranges_revoke_and_actor_cookie_guard(collab):
    c = collab
    row = grant(c)
    aid = c['recipient']['principal']['workspace']['id']
    url = '/w/' + c['wid'] + '/api/media/a_video?project_id=' + c['pid'] + '&actor_workspace_id=' + aid
    status, headers, raw = request(c, 'GET', url, session=c['recipient'], headers={'Range': 'bytes=0-7'})
    assert status == 206 and raw == b'ATTACHED' and headers['Accept-Ranges'] == 'bytes'
    # A stale native media element carries its actor hint even without custom headers.
    assert request(c, 'GET', url, session=c['stranger'])[0] == 409
    assert request(c, 'GET', url.replace('a_video', 'a_unrelated'), session=c['recipient'])[0] == 403
    assert request(c, 'DELETE', '/api/projects/' + c['pid'] + '/shares/' + row['id'], {'expected_revision': row['revision']}, c['owner'])[0] == 200
    assert request(c, 'GET', url, session=c['recipient'])[0] == 403


def test_shared_edit_does_not_attach_private_owner_asset(collab):
    c = collab
    grant(c, 'editor')
    edited = copy.deepcopy(c['project'])
    edited['assets'].append({'id': 'a_unrelated', 'sha256': 'd' * 64})
    before = len(c['transport'].requests)
    assert request(c, 'PUT', scope(c), edited, c['recipient'])[0] == 403
    assert len(c['transport'].requests) == before


def test_shared_text_layout_is_readonly_and_font_scoped(collab):
    c = collab
    grant(c)
    path = '/w/' + c['wid'] + '/api/text-layout?project_id=' + c['pid']
    body = {'project_id': c['pid'], 'element': {'type': 'text', 'font_asset_id': 'a_font'}}
    assert request(c, 'POST', path, body, c['recipient'])[0] == 200
    body['element']['font_asset_id'] = 'a_private_font'
    assert request(c, 'POST', path, body, c['recipient'])[0] == 403
    body['project_id'] = 'p_' + 'b' * 16
    assert request(c, 'POST', path, body, c['recipient'])[0] == 403


def test_share_and_editor_namespace_require_real_owner_and_csrf(collab):
    c = collab
    grant(c)
    url = '/editor?workspace=' + c['wid'] + '&project=' + c['pid']
    assert request(c, 'GET', url, session=c['recipient'])[0] == 200
    assert request(c, 'GET', url, session=c['stranger'])[0] == 409
    assert request(c, 'POST', scope(c, '/export'), {}, c['recipient'], headers={'X-Workspace-ID': c['wid']})[0] == 409
    assert request(c, 'POST', scope(c, '/export'), {}, c['recipient'], headers={'X-CSRF-Token': 'invalid'})[0] == 403
