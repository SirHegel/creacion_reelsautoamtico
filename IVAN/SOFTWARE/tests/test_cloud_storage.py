"""Storage foundation: synthetic credentials + injected object-store transport.

No external request, bucket, account, live key, upload or production project.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import io
import threading
import zipfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from studio import cloud_storage as cloud
from studio.core import StudioError

W = 'w_' + '1' * 32
OTHER = 'w_' + '2' * 32
P = 'p_' + 'a' * 16
AWS = {'provider': 'aws_s3', 'bucket': 'fixture-private-bucket', 'region': 'us-east-1', 'enabled': True}
CREDS = {'access_key_id': 'AKIA' + 'A' * 16, 'secret_access_key': 'SYNTHETIC_ONLY_' + 'x' * 40}


class ObjectStore:
    """Explicit fake HTTP protocol service; byte/CAS behavior is real here."""
    def __init__(self): self.objects = {}; self.calls = []; self.callback = None
    @staticmethod
    def etag(data): return '"' + hashlib.md5(data).hexdigest() + '"'
    def request(self, config, credentials, method, uri, headers, body, limit):
        self.calls.append({'method': method, 'uri': uri, 'headers': dict(headers), 'bytes': len(body)})
        if self.callback: self.callback(method, uri)
        old = self.objects.get(uri)
        if method == 'PUT':
            if headers.get('If-None-Match') == '*' and old is not None or headers.get('If-Match') is not None and (old is None or headers['If-Match'] != self.etag(old)):
                return {'status': 412, 'headers': {}, 'body': b''}
            self.objects[uri] = body
            return {'status': 200, 'headers': {'ETag': self.etag(body)}, 'body': b''}
        if old is None: return {'status': 404, 'headers': {}, 'body': b''}
        return {'status': 200, 'headers': {'ETag': self.etag(old), 'Content-Length': str(len(old))}, 'body': old if method == 'GET' else b''}


@pytest.fixture
def root(tmp_path):
    assert tmp_path.resolve().is_relative_to(cloud.CODE_ROOT / '.estado/tmp')
    return tmp_path


@pytest.fixture
def store(root):
    cloud.configure(AWS, CREDS, root=root)
    transport = ObjectStore()
    return cloud.CloudStorage(root, transport), transport


def source(root, data=b'private own protocol media', wid=W, name='source.mp4'):
    path = root / 'workspaces' / wid / 'assets/video' / name
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    return path, {'id': 'a_' + sha[:20], 'path': 'assets/video/' + name, 'sha256': sha}


def project(asset):
    return {'id': P, 'name': 'Private fixture', 'revision': 1, 'source': asset['id'], 'settings': {},
            'style': {}, 'timeline': [], 'transcript': {}, 'audio': [], 'fonts': {},
            'review': {'approved': True}, 'approved_export': {'secret_private_path': 'not retained'},
            'agent_tokens': ['not retained'], 'api_keys': ['not retained'], 'shares': ['not retained']}


def manifest(sha):
    return {'schema': 'ascendia.cloud-manifest/1', 'workspace_id': W, 'project_id': P,
            'revision': 1, 'snapshot_sha256': 'd' * 64, 'blobs': [sha]}


def test_default_status_never_creates_keys_or_network(root, monkeypatch):
    monkeypatch.setattr(cloud.socket, 'getaddrinfo', lambda *a, **k: pytest.fail('Network accessed'))
    assert cloud.status(root)['configured'] is False and cloud.status(root)['remote'] is False
    assert list(root.iterdir()) == []
    with pytest.raises(StudioError) as error: cloud.CloudStorage(root, ObjectStore()).get_blob(W, 'a' * 64)
    assert error.value.status == 409 and list(root.iterdir()) == []


def test_encrypted_configuration_independent_key_and_cas(root):
    unrelated = root / '.estado/providers.key'; unrelated.parent.mkdir(); unrelated.write_bytes(b'OTHER_PRIVATE_KEY_NOT_USED')
    result = cloud.configure({**AWS, 'enabled': False}, CREDS, root=root)
    assert result['configured'] and result['revision'] == 1 and not result['enabled'] and not result['remote']
    encoded = (root / '.estado/cloud_storage/config.enc').read_bytes()
    assert all(v.encode() not in encoded for v in CREDS.values())
    assert (root / '.estado/cloud_storage/master.key').stat().st_mode & 0o077 == 0
    assert unrelated.read_bytes() == b'OTHER_PRIVATE_KEY_NOT_USED'
    with pytest.raises(StudioError) as error: cloud.configure(AWS, CREDS, expected_revision=0, root=root)
    assert error.value.status == 409
    assert cloud.configure(AWS, CREDS, expected_revision=1, root=root)['revision'] == 2
    assert 'credentials' not in json.dumps(cloud.status(root))


@pytest.mark.parametrize('change', ['unknown_url', 'private_endpoint', 'bad_region', 'list_region', 'bool_enabled', 'dots', 'bucket_escape', 'bad_provider', 'bad_r2_id'])
def test_closed_config_rejects_user_urls_or_malformed_fields_without_writes(root, change):
    cfg = dict(AWS)
    if change == 'unknown_url': cfg['endpoint'] = 'https://attacker.invalid'
    elif change == 'private_endpoint': cfg['url'] = 'http://169.254.169.254/latest/meta-data'
    elif change == 'bad_region': cfg['region'] = 'invalid-region'
    elif change == 'list_region': cfg['region'] = []
    elif change == 'bool_enabled': cfg['enabled'] = 1
    elif change == 'dots': cfg['bucket'] = 'bucket.with.dots'
    elif change == 'bucket_escape': cfg['bucket'] = '../private'
    elif change == 'bad_provider': cfg['provider'] = 'arbitrary'
    else: cfg = {'provider': 'cloudflare_r2', 'bucket': AWS['bucket'], 'enabled': False, 'account_id': 'evil.com'}
    with pytest.raises(StudioError): cloud.configure(cfg, CREDS, root=root)
    assert list(root.iterdir()) == []


@pytest.mark.parametrize('credentials', [None, {}, {'access_key_id': True, 'secret_access_key': 'x' * 40},
    {**CREDS, 'parent_key': 'fake'}, {**CREDS, 'secret_access_key': 'x\r\n' * 20}, {**CREDS, 'session_token': True}])
def test_credentials_closed_and_no_parent_reuse(root, credentials):
    with pytest.raises(StudioError): cloud.configure(AWS, credentials, root=root)
    assert list(root.iterdir()) == []


def test_fixed_aws_and_r2_hosts():
    assert cloud.validate_config(AWS)['host'] == 's3.us-east-1.amazonaws.com'
    r2 = cloud.validate_config({'provider': 'cloudflare_r2', 'bucket': 'fixture-private-bucket', 'enabled': False, 'account_id': 'a' * 32})
    assert r2['host'] == 'a' * 32 + '.r2.cloudflarestorage.com' and r2['region'] == 'auto'


@pytest.mark.parametrize('tamper', ['ciphertext', 'key', 'key_permissions', 'config_symlink', 'key_hardlink'])
def test_private_configuration_aliases_and_authentication_fail_closed(root, tamper):
    cloud.configure(AWS, CREDS, root=root)
    cfg = root / '.estado/cloud_storage/config.enc'; key = root / '.estado/cloud_storage/master.key'
    if tamper == 'ciphertext': cfg.write_bytes(cfg.read_bytes()[:-1] + bytes([cfg.read_bytes()[-1] ^ 1]))
    elif tamper == 'key': key.write_bytes(b'wrong key contents')
    elif tamper == 'key_permissions': key.chmod(0o644)
    else:
        selected = cfg if tamper == 'config_symlink' else key
        own = root / 'own_copy'; own.write_bytes(selected.read_bytes()); selected.unlink()
        if tamper == 'config_symlink': selected.symlink_to(own)
        else: os.link(own, selected)
    with pytest.raises(StudioError): cloud.status(root)


def test_config_root_cannot_be_a_tenant_or_symlink(root):
    alias = root / 'alias'; alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(StudioError): cloud.status(alias)
    with pytest.raises(StudioError): cloud.status(cloud.CODE_ROOT / 'workspaces' / W)


def test_blob_put_restore_exact_bytes_no_source_mutation_and_dedup(store, root):
    backend, remote = store
    path, asset = source(root)
    result = backend.put_blob(W, path, asset['sha256'])
    assert result['acknowledged'] and not result['full_remote_bytes_verified'] and not result['live_remote_execution_verified']
    assert result['key'] == 'v1/' + W + '/blobs/' + asset['sha256'] and result['transport'] == 'injected'
    again = backend.put_blob(W, path, asset['sha256'])
    assert again['full_remote_bytes_verified'] and len(remote.objects) == 1
    received = backend.get_blob(W, asset['sha256'])
    assert (root / received['path']).read_bytes() == path.read_bytes()
    assert received['applied'] is False and not received['live_remote_execution_verified']


@pytest.mark.parametrize('attack', ['foreign_workspace', 'state_path', 'symlink', 'hardlink', 'bad_sha', 'non_path'])
def test_blob_source_is_confined_canonical_and_hashed(store, root, attack):
    backend, remote = store
    path, asset = source(root)
    if attack == 'foreign_workspace': requested = OTHER
    else: requested = W
    if attack == 'state_path':
        path = root / '.estado/private_file'; path.write_bytes(b'private')
    elif attack in ('symlink', 'hardlink'):
        own = root / 'canary'; own.write_bytes(path.read_bytes()); path.unlink()
        if attack == 'symlink': path.symlink_to(own)
        else: os.link(own, path)
    elif attack == 'bad_sha': asset['sha256'] = '0' * 64
    elif attack == 'non_path': path = None
    with pytest.raises(StudioError): backend.put_blob(requested, path, asset['sha256'])
    assert remote.calls == []


def test_disabled_storage_never_calls_injected_transport(root):
    cloud.configure({**AWS, 'enabled': False}, CREDS, root=root)
    remote = ObjectStore(); backend = cloud.CloudStorage(root, remote); path, a = source(root)
    with pytest.raises(StudioError): backend.put_blob(W, path, a['sha256'])
    assert remote.calls == []


def test_source_or_configuration_change_during_upload_rejects_commit(store, root):
    backend, remote = store; path, a = source(root)
    remote.callback = lambda *_: path.write_bytes(b'changed')
    with pytest.raises(StudioError) as error: backend.put_blob(W, path, a['sha256'])
    assert error.value.status == 409
    path.write_bytes(b'private own protocol media')
    remote.callback = lambda *_: cloud.configure({**AWS, 'enabled': False}, CREDS, expected_revision=1, root=root)
    with pytest.raises(StudioError) as error: backend.put_blob(W, path, a['sha256'])
    assert error.value.status == 409
    assert remote.calls[-1]['method'] == 'PUT'


def test_remote_corrupt_blob_cannot_restore_or_be_treated_as_dedup(store, root):
    backend, remote = store; path, a = source(root)
    uri = '/' + AWS['bucket'] + '/' + backend._blob_key(W, a['sha256'])
    remote.objects[uri] = b'wrong remote content'
    with pytest.raises(StudioError): backend.get_blob(W, a['sha256'])
    with pytest.raises(StudioError): backend.put_blob(W, path, a['sha256'])
    assert not (root / '.estado/cloud_storage/staging').exists()


def test_manifest_create_then_cas_no_silent_overwrite(store, root):
    backend, remote = store; path, a = source(root); doc = manifest(a['sha256'])
    first = backend.put_manifest(W, P, doc)
    assert not first['referenced_blobs_verified'] and not first['snapshot_bytes_verified']
    changed = {**doc, 'revision': 2}
    with pytest.raises(StudioError) as error: backend.put_manifest(W, P, changed)
    assert error.value.status == 409
    with pytest.raises(StudioError): backend.put_manifest(W, P, changed, '"incorrect"')
    result = backend.put_manifest(W, P, changed, first['etag'])
    assert result['revision'] == 2 and result['etag'] != first['etag']


@pytest.mark.parametrize('mutation', ['foreign', 'extra', 'bool_revision', 'nan_revision', 'bad_snapshot', 'bad_blobs', 'duplicates', 'etag_crlf'])
def test_manifest_contract_closed_and_not_an_upload_url(store, root, mutation):
    backend, remote = store; _, a = source(root); doc = manifest(a['sha256']); etag = None
    if mutation == 'foreign': doc['workspace_id'] = OTHER
    elif mutation == 'extra': doc['url'] = 'http://127.0.0.1/private'
    elif mutation == 'bool_revision': doc['revision'] = True
    elif mutation == 'nan_revision': doc['revision'] = float('nan')
    elif mutation == 'bad_snapshot': doc['snapshot_sha256'] = '../secret'
    elif mutation == 'bad_blobs': doc['blobs'] = [{}]
    elif mutation == 'duplicates': doc['blobs'] *= 2
    else: etag = '"good"\r\nX-Evil: injected'
    with pytest.raises(StudioError): backend.put_manifest(W, P, doc, etag)
    assert remote.calls == []


def test_outbox_sealed_cas_no_network_and_no_privileged_project_fields(store, root):
    backend, remote = store; path, a = source(root); p = project(a)
    pending = backend.enqueue_snapshot(W, p, [a])
    assert pending['status'] == 'queued' and pending['automatic_sync'] is False and not remote.calls
    assert set(pending['snapshot']['project']) <= cloud.EDITABLE_FIELDS
    assert not any(k in pending['snapshot']['project'] for k in ('review', 'approved_export', 'agent_tokens', 'api_keys', 'shares'))
    assert backend.outbox(W, P) == pending
    with pytest.raises(StudioError) as error: backend.enqueue_snapshot(W, p, [a], expected_revision=0)
    assert error.value.status == 409
    assert backend.enqueue_snapshot(W, p, [a], expected_revision=1)['revision'] == 2
    assert path.read_bytes() == b'private own protocol media'


def test_outbox_forged_metadata_or_foreign_copy_is_rejected(store, root):
    backend, _ = store; _, a = source(root); value = backend.enqueue_snapshot(W, project(a), [a])
    path = root / '.estado/cloud_storage/outbox' / (W + '_' + P + '.json')
    value['editorial_approved'] = True; path.write_text(json.dumps(value))
    with pytest.raises(StudioError): backend.outbox(W, P)


def preload_snapshot(store, root, transform=None):
    backend, remote = store; _, a = source(root)
    snapshot = backend.enqueue_snapshot(W, project(a), [a])['snapshot']
    if transform: transform(snapshot)
    data = cloud._json(snapshot); sha = hashlib.sha256(data).hexdigest()
    remote.objects['/' + AWS['bucket'] + '/' + backend._blob_key(W, sha)] = data
    remote.objects['/' + AWS['bucket'] + '/' + backend._blob_key(W, a['sha256'])] = b'private own protocol media'
    return sha, snapshot


def test_restore_only_stages_hashed_bytes_and_never_applies_project(store, root):
    backend, _ = store; sha, snapshot = preload_snapshot(store, root)
    restored = backend.stage_restore(W, sha)
    assert restored['project'] == snapshot['project'] and not restored['applied'] and not restored['editorial_approved']
    assert len(restored['assets']) == 1 and (root / restored['assets'][0]['staging_path']).read_bytes() == b'private own protocol media'
    assert not (root / 'workspaces' / W / 'projects').exists()


@pytest.mark.parametrize('attack', ['foreign_owner', 'secret_fields', 'traversal', 'symlink_path', 'bool_bytes', 'bool_revision', 'duplicate_id', 'duplicate_path', 'missing_source', 'invalid_sha'])
def test_restore_rejects_forged_snapshot_before_downloading_media(store, root, attack):
    def mutate(s):
        if attack == 'foreign_owner': s['workspace_id'] = OTHER
        elif attack == 'secret_fields': s['project']['api_keys'] = ['fake']
        elif attack == 'traversal': s['assets'][0]['path'] = 'assets/../../secret'
        elif attack == 'symlink_path': s['assets'][0]['path'] = '/absolute/path'
        elif attack == 'bool_bytes': s['assets'][0]['bytes'] = True
        elif attack == 'bool_revision': s['project']['revision'] = True
        elif attack == 'duplicate_id': s['assets'].append(copy.deepcopy(s['assets'][0]))
        elif attack == 'duplicate_path': s['assets'].append({**s['assets'][0], 'id': 'a_other'})
        elif attack == 'missing_source': s['project']['source'] = 'a_missing'
        else: s['assets'][0]['sha256'] = 'bad'
    backend, remote = store; sha, _ = preload_snapshot(store, root, mutate)
    with pytest.raises(StudioError): backend.stage_restore(W, sha)
    assert len(remote.calls) == 1 and remote.calls[0]['method'] == 'GET'
    assert not (root / 'workspaces' / W / 'projects').exists()


@pytest.mark.parametrize('secret_name', ['session_token', 'access_token', 'refresh_token', 'client_secret', 'private_key', 'openai_api_key', 'apiKey'])
def test_nested_secret_keys_are_not_part_of_captured_project(store, complete_project, secret_name):
    backend, _ = store
    rewrite_project(complete_project, lambda p: p['settings'].update({secret_name: 'PRIVATE_SECRET_CANARY'}))
    backend.enqueue_project(W, P, 1)
    assert 'PRIVATE_SECRET_CANARY' not in json.dumps(backend.outbox(W, P))


@pytest.mark.parametrize('path', ['..\\.estado\\providers.json', 'C:\\Users\\private.key', '../private.json', '.estado/keys.json'])
def test_private_documentary_paths_removed_from_snapshot(store, complete_project, path):
    backend, _ = store
    rewrite_project(complete_project, lambda p: p.update(tracking={'report_path': path}))
    backend.enqueue_project(W, P, 1)
    assert 'report_path' not in backend.outbox(W, P)['snapshot']['project']['tracking']


@pytest.mark.parametrize('scope', ['scene', 'transition', 'overlay', 'motion_media', 'motion_font', 'audio'])
def test_snapshot_without_zip_requires_every_editable_resource_reference(store, complete_project, scope):
    backend, remote = store
    def mutate(p):
        scene = p['timeline'][0]
        if scope == 'scene': scene['asset_id'] = 'a_MISSING'
        elif scope == 'transition': scene['transition_asset_id'] = 'a_MISSING'
        elif scope == 'overlay': scene['overlays'] = [{'asset_id': 'a_MISSING'}]
        elif scope == 'motion_media': scene['motion_design'] = {'elements': [{'type': 'media', 'asset_id': 'a_MISSING'}]}
        elif scope == 'motion_font': scene['motion_design'] = {'elements': [{'type': 'text', 'font_asset_id': p['source']}]}
        else: p['audio'] = [{'asset_id': 'a_MISSING'}]
    rewrite_project(complete_project, mutate)
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1)
    assert remote.calls == []


@pytest.mark.parametrize('value', [None, {}, False])
def test_malformed_render_history_never_becomes_internal_500(store, complete_project, value):
    backend, _ = store
    rewrite_project(complete_project, lambda p: p.update(renders=value))
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1)


def test_source_project_change_between_capture_and_commit_keeps_queue_absent(store, complete_project, monkeypatch):
    backend, remote = store; saved = backend._cache_blob
    def mutate(wid, data):
        sha = saved(wid, data)
        if b'ascendia.cloud-snapshot/2' in data:
            rewrite_project(complete_project, lambda p: p.update(revision=2))
        return sha
    monkeypatch.setattr(backend, '_cache_blob', mutate)
    with pytest.raises(StudioError) as error: backend.enqueue_project(W, P, 1)
    assert error.value.status == 409 and backend.outbox_status(W, P)['status'] == 'absent'
    assert not remote.calls


@pytest.mark.parametrize('stage', ['enqueue', 'run'])
def test_configuration_late_commit_race_is_checked_inside_lock(store, root, complete_project, monkeypatch, stage):
    from contextlib import contextmanager
    backend, _ = store
    if stage == 'run': backend.enqueue_project(W, P, 1)
    original = cloud._lock; once = False
    @contextmanager
    def raced(target):
        nonlocal once
        if not once:
            once = True; cloud.configure(AWS, CREDS, expected_revision=1, root=root)
        with original(target): yield
    monkeypatch.setattr(cloud, '_lock', raced)
    with pytest.raises(StudioError) as error:
        backend.enqueue_project(W, P, 1) if stage == 'enqueue' else backend.run_outbox(W, P, 1)
    assert error.value.status == 409
    assert backend.outbox_status(W, P)['status'] == ('absent' if stage == 'enqueue' else 'queued')


def test_head_ack_before_local_commit_failure_is_recoverable_and_not_publicly_verified(store, complete_project, monkeypatch):
    backend, remote = store; queued = backend.enqueue_project(W, P, 1)
    original = cloud._sealed
    def fail_commit(root, path, record):
        if '/outbox/' in path and record.get('status') == 'verified': raise StudioError('Injected local commit failure', 409)
        return original(root, path, record)
    monkeypatch.setattr(cloud, '_sealed', fail_commit)
    with pytest.raises(StudioError): backend.run_outbox(W, P, 1)
    assert backend.outbox_status(W, P)['pending']
    assert any(key.endswith('manifest.json') for key in remote.objects)
    monkeypatch.setattr(cloud, '_sealed', original)
    assert backend.run_outbox(W, P, queued['revision'])['integrity_verified']


def test_concurrent_runner_is_idempotent_and_writes_one_head(store, complete_project):
    backend, remote = store; backend.enqueue_project(W, P, 1)
    results, errors = [], []
    def run():
        try: results.append(backend.run_outbox(W, P, 1))
        except Exception as error: errors.append(error)
    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads: thread.start()
    for thread in threads: thread.join(3)
    assert not errors and len(results) == 2 and all(r['integrity_verified'] for r in results)
    assert len([c for c in remote.calls if c['method'] == 'PUT' and c['uri'].endswith('manifest.json')]) == 1


def test_complete_outbox_status_absent_does_not_generate_configuration(root):
    backend = cloud.CloudStorage(root, ObjectStore())
    assert backend.outbox_status(W, P)['manifest_etag'] is None and list(root.iterdir()) == []
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1)
    assert list(root.iterdir()) == []


def test_documentary_direction_receipt_bytes_and_paths_are_covered(store, complete_project):
    backend, remote = store; p, ws = complete_project
    name = 'projects/' + P + '/automation/' + 'a' * 24 + '/plan.json'
    path = ws / name; path.parent.mkdir(parents=True)
    raw = b'{"scene":"fixture","session_token":"SECRET_CANARY"}'; path.write_bytes(raw)
    rewrite_project(complete_project, lambda p: p.update(automation={'artifacts': [{'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}], 'editorial_approved': False}))
    queued = backend.enqueue_project(W, P, 1)
    snapshot = backend.outbox(W, P)['snapshot']
    entry = snapshot['project']['automation']['artifacts'][0]
    file = next(f for f in snapshot['files'] if f['path'] == entry['path'])
    assert file['sha256'] == entry['sha256'] and entry['path'].startswith('artifacts/automation/')
    assert 'SECRET_CANARY' not in (backend.root / '.estado/cloud_storage/blobs' / W / (file['sha256'] + '.blob')).read_text()
    backend.run_outbox(W, P, queued['revision'])
    assert backend.stage_restore(W, queued['snapshot_sha256'])['integrity_verified']


@pytest.mark.parametrize('addresses', [['127.0.0.1'], ['169.254.169.254'], ['10.0.0.1'], ['::1'], ['224.0.0.1'], ['1.1.1.1', '127.0.0.1'], ['not-an-IP'], []])
def test_ssrf_dns_private_mixed_or_malformed_rejected(monkeypatch, addresses):
    monkeypatch.setattr(cloud.socket, 'getaddrinfo', lambda *_a, **_k: [(2, 1, 6, '', (ip, 443)) for ip in addresses])
    with pytest.raises(StudioError): cloud._public_ips('s3.us-east-1.amazonaws.com')


def test_dns_pin_avoids_second_hostname_resolution_and_uses_tls_hostname(monkeypatch):
    connections, tls = [], []
    class Context:
        def wrap_socket(self, raw, server_hostname): tls.append(server_hostname); return raw
    class Socket:
        def close(self): pass
    monkeypatch.setattr(cloud.socket, 'create_connection', lambda address, timeout: connections.append(address) or Socket())
    monkeypatch.setattr(cloud.ssl, 'create_default_context', lambda: Context())
    connection = cloud._PinnedHTTPS('s3.us-east-1.amazonaws.com', '1.1.1.1'); connection.connect(); connection.close()
    assert connections == [('1.1.1.1', 443)] and tls == ['s3.us-east-1.amazonaws.com']


def test_sigv4_is_deterministic_payload_bound_and_does_not_change_inputs():
    cfg = cloud.validate_config(AWS); stamp = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)
    original = copy.deepcopy(CREDS)
    a = cloud._sign(cfg, CREDS, 'PUT', '/fixture-private-bucket/v1/' + W + '/blobs/' + 'a' * 64, {'If-None-Match': '*'}, b'one', stamp)
    b = cloud._sign(cfg, CREDS, 'PUT', '/fixture-private-bucket/v1/' + W + '/blobs/' + 'a' * 64, {'If-None-Match': '*'}, b'two', stamp)
    assert a['authorization'] != b['authorization'] and a['x-amz-content-sha256'] == hashlib.sha256(b'one').hexdigest()
    assert '/20261014/us-east-1/s3/aws4_request' in a['authorization'] and CREDS == original


@pytest.mark.parametrize('reply', [{'status': True, 'headers': {}, 'body': b''}, {'status': 200, 'headers': [], 'body': b''},
                                {'status': 200, 'headers': {}, 'body': 'not bytes'}, {'status': 200, 'headers': {}, 'body': b'', 'verified': True}])
def test_injected_transport_cannot_forge_response_shape_or_verification(root, reply):
    cloud.configure(AWS, CREDS, root=root)
    class Fake:
        live = True
        def request(self, *_): return reply
    backend = cloud.CloudStorage(root, Fake())
    assert backend.live is False
    with pytest.raises(StudioError): backend.get_blob(W, 'a' * 64)


class Response:
    def __init__(self, status=200, data=b'fixture', declared=None):
        self.status, self.data, self.declared = status, data, declared
    def getheader(self, name): return self.declared if name == 'Content-Length' else None
    def getheaders(self): return [('Content-Length', self.declared)] if self.declared is not None else []
    def read(self, size):
        result, self.data = self.data[:size], self.data[size:]
        return result


class Connection:
    def __init__(self, response): self.response = response; self.headers = {}; self.closed = False; self.sock = None
    def putrequest(self, method, uri, **kwargs): self.method, self.uri, self.kwargs = method, uri, kwargs
    def putheader(self, key, value): self.headers[key.lower()] = value
    def endheaders(self): pass
    def send(self, data): pass
    def getresponse(self): return self.response
    def close(self): self.closed = True


def transport_fixture(monkeypatch, response):
    connection = Connection(response)
    monkeypatch.setattr(cloud, '_public_ips', lambda host: ['1.1.1.1'])
    monkeypatch.setattr(cloud, '_PinnedHTTPS', lambda host, address: connection)
    return cloud.HTTPSStorageTransport(), connection


def test_default_https_transport_ignores_proxy_env_and_never_sends_cookie(monkeypatch):
    monkeypatch.setenv('HTTPS_PROXY', 'http://private-proxy.invalid:8080')
    transport, connection = transport_fixture(monkeypatch, Response(declared='7'))
    result = transport.request(cloud.validate_config(AWS), CREDS, 'GET', '/' + AWS['bucket'] + '/v1/' + W + '/blobs/' + 'a' * 64, {}, b'', 16)
    assert result['body'] == b'fixture' and connection.closed
    assert connection.headers['host'] == 's3.us-east-1.amazonaws.com'
    assert 'cookie' not in connection.headers and 'proxy-authorization' not in connection.headers
    assert connection.headers['authorization'].startswith('AWS4-HMAC-SHA256 ')


@pytest.mark.parametrize('status', [301, 302, 307, 308])
def test_https_redirect_never_followed_or_reveals_location(monkeypatch, status):
    transport, connection = transport_fixture(monkeypatch, Response(status, b'wrong'))
    with pytest.raises(StudioError) as error:
        transport.request(cloud.validate_config(AWS), CREDS, 'GET', '/' + AWS['bucket'] + '/v1/' + W + '/blobs/' + 'a' * 64, {}, b'', 16)
    assert error.value.status == 502 and connection.closed


@pytest.mark.parametrize('declared,data', [('17', b'x'), ('NaN', b'x'), (None, b'x' * 17)])
def test_https_body_limit_even_without_content_length(monkeypatch, declared, data):
    transport, connection = transport_fixture(monkeypatch, Response(200, data, declared))
    with pytest.raises(StudioError) as error:
        transport.request(cloud.validate_config(AWS), CREDS, 'GET', '/' + AWS['bucket'] + '/v1/' + W + '/blobs/' + 'a' * 64, {}, b'', 16)
    assert error.value.status == 413 and connection.closed


@pytest.mark.parametrize('attack', ['host', 'url', 'query', 'foreign_key', 'cookie', 'header_crlf', 'bool_limit', 'string_body'])
def test_low_level_transport_cannot_bypass_fixed_endpoint_and_closed_transfer(monkeypatch, attack):
    monkeypatch.setattr(cloud, '_public_ips', lambda *_: pytest.fail('Endpoint should reject before DNS'))
    config = cloud.validate_config(AWS); uri = '/' + AWS['bucket'] + '/v1/' + W + '/blobs/' + 'a' * 64
    headers, body, limit = {}, b'', 16
    if attack == 'host': config['host'] = 'public-attacker.invalid'
    elif attack == 'url': config['endpoint'] = 'https://public-attacker.invalid'
    elif attack == 'query': uri += '?redirect=private'
    elif attack == 'foreign_key': uri = '/' + AWS['bucket'] + '/private/accounts.json'
    elif attack == 'cookie': headers['Cookie'] = 'secret'
    elif attack == 'header_crlf': headers['If-Match'] = '"a"\r\nsecret'
    elif attack == 'bool_limit': limit = True
    else: body = 'not bytes'
    with pytest.raises(StudioError): cloud.HTTPSStorageTransport().request(config, CREDS, 'GET', uri, headers, body, limit)


def test_https_transfer_deadline_closes_connection(monkeypatch):
    transport, connection = transport_fixture(monkeypatch, Response(200, b'fixture', None))
    ticks = iter([0, 0, 61])
    monkeypatch.setattr(cloud.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(StudioError) as error:
        transport.request(cloud.validate_config(AWS), CREDS, 'GET', '/' + AWS['bucket'] + '/v1/' + W + '/blobs/' + 'a' * 64, {}, b'', 16)
    assert error.value.status == 504 and connection.closed


def test_staging_corruption_is_never_overwritten_by_later_restore(store, root):
    backend, _ = store; path, a = source(root); backend.put_blob(W, path, a['sha256'])
    restored = backend.get_blob(W, a['sha256']); staged = root / restored['path']; staged.write_bytes(b'changed staging')
    with pytest.raises(StudioError) as error: backend.get_blob(W, a['sha256'])
    assert error.value.status == 409 and staged.read_bytes() == b'changed staging'


def test_private_outbox_requires_private_permissions(store, root):
    backend, _ = store; _, a = source(root); backend.enqueue_snapshot(W, project(a), [a])
    target = root / '.estado/cloud_storage/outbox' / (W + '_' + P + '.json'); target.chmod(0o644)
    with pytest.raises(StudioError) as error: backend.outbox(W, P)
    assert error.value.status == 403


@pytest.fixture
def complete_project(root, store):
    """Own canonical files + authentic OFL fonts, no FFmpeg or production data."""
    from studio.fonts import inspect_font
    ws = root / 'workspaces' / W
    _, video = source(root)
    video.update(size=len(b'private own protocol media'), kind='video', probe={'format': {'filename': '/PRIVATE_CANARY'}, 'streams': []}, metadata={}, verification={'visual': True})
    rows = [video]
    pack = json.loads((cloud.CODE_ROOT / 'packs/public_fonts.json').read_text())
    faces = [pack['fonts'][1], pack['fonts'][4]]
    for face in faces:
        path = ws / face['path']; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((cloud.CODE_ROOT / face['path']).read_bytes())
        notice = ws / face['notice_path']; notice.parent.mkdir(parents=True, exist_ok=True)
        notice.write_bytes((cloud.CODE_ROOT / face['notice_path']).read_bytes())
        info = inspect_font(path, ws)
        rows.append({'id': face['asset_id'], 'path': face['path'], 'sha256': face['sha256'], 'size': path.stat().st_size,
                     'kind': 'font', 'font_info': info, 'metadata': {'font_notice': {'path': face['notice_path'], 'sha256': face['notice_sha256'], 'license': 'OFL-1.1', 'source_url': face['notice_source_url']}}})
    p = project(video); p['assets'] = rows
    p['fonts'] = {'primary': rows[1]['path'], 'accent': rows[2]['path']}
    brand = {'id': 'ivan_branding', 'revision': 1, 'name': 'Own private fixture',
             'colors': {'background': '#ffffff', 'text': '#111111', 'accent': '#d71920', 'muted': '#555555'},
             'fonts': {role: {'asset_id': row['id'], 'path': row['path'], 'sha256': row['sha256'], 'family': row['font_info']['family'], 'style': row['font_info']['style'], 'license': {'status': 'pending'}} for role, row in zip(('primary', 'accent'), rows[1:])},
             'logo_asset_id': None, 'instructions': '', 'language': 'es', 'base': 'ivan_yo_clone',
             'base_rules_sha256': 'e' * 64, 'font_override_explicit': True,
             'original_reference_fonts': ['Sequel Sans Bold Disp', 'Scholar Italic'], 'editorial_approved': False}
    p['style'] = {'branding': brand}; p['settings']['api_key'] = 'NESTED_SECRET_NOT_ARCHIVED'
    p['timeline'] = [{'id': 'scene', 'type': 'presenter', 'start': 0, 'end': 1, 'chin_reviewed': True}]
    directory = ws / 'projects' / P; directory.mkdir(parents=True)
    (directory / 'project.json').write_text(json.dumps(p))
    (ws / '.estado/project_branding').mkdir(parents=True)
    (ws / '.estado/project_branding' / (P + '.json')).write_text(json.dumps(brand))
    (ws / '.estado/assets.json').write_text(json.dumps(rows))
    return p, ws


def rewrite_project(complete_project, change):
    p, ws = complete_project; value = copy.deepcopy(p); change(value)
    (ws / 'projects' / P / 'project.json').write_text(json.dumps(value))
    return value


def test_complete_snapshot_has_project_brand_fonts_notices_and_no_secrets(store, complete_project):
    backend, remote = store; p, ws = complete_project
    original = (ws / 'projects' / P / 'project.json').read_bytes()
    queued = backend.enqueue_project(W, P, 1)
    assert queued['status'] == 'queued' and queued['revision'] == 1 and queued['pending']
    assert remote.calls == [] and 'snapshot' not in queued and 'endpoint' not in queued
    snapshot = backend.outbox(W, P)['snapshot']
    roles = {f['role'] for f in snapshot['files']}
    assert roles == {'project', 'asset', 'font_notice', 'branding'}
    assert all(a['verification']['visual'] is False for a in snapshot['project']['assets'])
    assert snapshot['project']['review'] == {} and snapshot['project']['approved_export'] is None
    assert snapshot['project']['timeline'][0]['chin_reviewed'] is False
    assert '/PRIVATE_CANARY' not in json.dumps(snapshot) and 'NESTED_SECRET_NOT_ARCHIVED' not in json.dumps(snapshot)
    assert (ws / 'projects' / P / 'project.json').read_bytes() == original
    assert backend.enqueue_project(W, P, 1, expected_revision=1) == queued


def test_complete_backup_full_get_verified_roundtrip_no_application(store, complete_project):
    backend, remote = store; _, ws = complete_project
    original = (ws / 'projects' / P / 'project.json').read_bytes()
    queued = backend.enqueue_project(W, P, 1)
    result = backend.run_outbox(W, P, queued['revision'])
    assert result['status'] == 'verified' and result['revision'] == 2 and result['integrity_verified']
    assert result['transport'] == 'injected' and not result['live_remote_execution_verified']
    assert result['manifest_etag'].startswith('"') and result['receipt_sha256']
    assert 'snapshot' not in result and 'key' not in result and 'url' not in result
    puts = [c for c in remote.calls if c['method'] == 'PUT']
    assert puts[-1]['uri'].endswith('manifest.json')
    assert all(c['headers'].get('If-None-Match') == '*' for c in puts)
    retry = backend.run_outbox(W, P, 1)
    assert retry['reused'] and len([c for c in remote.calls if c['method'] == 'PUT']) == len(puts)
    restored = backend.stage_restore(W, queued['snapshot_sha256'])
    assert restored['integrity_verified'] and restored['applied'] is False and restored['editorial_approved'] is False
    assert restored['project']['review'] == {} and restored['project']['approval_current'] is False
    assert (ws / 'projects' / P / 'project.json').read_bytes() == original
    assert backend.stage_restore(W, queued['snapshot_sha256'])['staging_root'] == restored['staging_root']


def test_complete_snapshot_etag_cas_update_and_head_conflict(store, complete_project):
    backend, remote = store
    backend.enqueue_project(W, P, 1); first = backend.run_outbox(W, P, 1)
    rewrite_project(complete_project, lambda p: p.update(revision=2, name='Own changed project'))
    queued = backend.enqueue_project(W, P, 2, expected_revision=2, expected_etag=first['manifest_etag'])
    final = backend.run_outbox(W, P, queued['revision'])
    assert final['project_revision'] == 2 and final['manifest_etag'] != first['manifest_etag']
    rewrite_project(complete_project, lambda p: p.update(revision=3, name='Stale CAS request'))
    queued = backend.enqueue_project(W, P, 3, expected_revision=4, expected_etag=first['manifest_etag'])
    before = remote.objects.copy()
    with pytest.raises(StudioError) as error: backend.run_outbox(W, P, queued['revision'])
    assert error.value.status == 409 and backend.outbox_status(W, P)['pending']
    key = '/' + AWS['bucket'] + '/v1/' + W + '/projects/' + P + '/manifest.json'
    assert remote.objects[key] == before[key]


@pytest.mark.parametrize('mutation', ['project_revision', 'asset_missing', 'asset_hash', 'source_missing', 'fonts_missing', 'font_role_dict', 'brand_mismatch', 'brand_font_forgery', 'metadata_list', 'style_list', 'notice_escape', 'changed_notice', 'asset_link', 'asset_hardlink'])
def test_complete_capture_rejects_missing_forged_or_aliased_inputs(store, root, complete_project, mutation):
    backend, remote = store; p, ws = complete_project
    if mutation == 'project_revision': rewrite_project(complete_project, lambda v: v.update(revision=2))
    elif mutation == 'asset_missing': rewrite_project(complete_project, lambda v: v['assets'][0].update(id='a_FOREIGN'))
    elif mutation == 'asset_hash': (ws / p['assets'][0]['path']).write_bytes(b'modified')
    elif mutation == 'source_missing': rewrite_project(complete_project, lambda v: v.update(source=[]))
    elif mutation == 'fonts_missing': rewrite_project(complete_project, lambda v: v['fonts'].update(primary='assets/fonts/missing.ttf'))
    elif mutation == 'font_role_dict': rewrite_project(complete_project, lambda v: v['fonts'].update(primary={}))
    elif mutation == 'brand_mismatch': rewrite_project(complete_project, lambda v: v['style']['branding'].update(name='Forged branding'))
    elif mutation == 'brand_font_forgery':
        value = rewrite_project(complete_project, lambda v: v['style']['branding']['fonts']['primary'].update(family='Invented family'))
        (ws / '.estado/project_branding' / (P + '.json')).write_text(json.dumps(value['style']['branding']))
    elif mutation == 'style_list': rewrite_project(complete_project, lambda v: v.update(style=[]))
    elif mutation == 'changed_notice': (ws / p['assets'][1]['metadata']['font_notice']['path']).write_bytes(b'forged notice')
    elif mutation in ('metadata_list', 'notice_escape'):
        catalog = copy.deepcopy(p['assets'])
        if mutation == 'metadata_list': catalog[0]['metadata'] = []
        else: catalog[1]['metadata']['font_notice']['path'] = '.estado/providers.json'
        (ws / '.estado/assets.json').write_text(json.dumps(catalog))
    else:
        path = ws / p['assets'][0]['path']; own = ws / 'own_private_copy'; own.write_bytes(path.read_bytes()); path.unlink()
        if mutation == 'asset_link': path.symlink_to(own)
        else: os.link(own, path)
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1)
    assert remote.calls == [] and not (root / '.estado/cloud_storage/outbox').exists()


@pytest.mark.parametrize('include_outputs', [None, 1, [], 'yes'])
def test_complete_snapshot_boolean_option_closed(store, complete_project, include_outputs):
    backend, remote = store
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1, include_outputs=include_outputs)
    assert not remote.calls


def test_run_cancel_leaves_queue_and_no_head_then_resume_is_dedup(store, complete_project):
    backend, remote = store; queued = backend.enqueue_project(W, P, 1)
    cancel = threading.Event()
    remote.callback = lambda method, uri: cancel.set() if method == 'PUT' else None
    with pytest.raises(StudioError) as error: backend.run_outbox(W, P, queued['revision'], cancel=cancel)
    assert error.value.details['kind'] == 'cloud_cancelled'
    assert backend.outbox_status(W, P)['pending'] and not any(c['uri'].endswith('manifest.json') for c in remote.calls)
    remote.callback = None
    assert backend.run_outbox(W, P, queued['revision'])['integrity_verified']


def test_remote_corruption_and_configuration_mutation_never_confirm_head(store, root, complete_project):
    backend, remote = store; queued = backend.enqueue_project(W, P, 1)
    def mutate(method, uri):
        if method == 'GET':
            remote.callback = None
            cloud.configure(AWS, CREDS, expected_revision=1, root=root)
    remote.callback = mutate
    with pytest.raises(StudioError): backend.run_outbox(W, P, queued['revision'])
    assert backend.outbox_status(W, P)['pending'] and not any(c['uri'].endswith('manifest.json') for c in remote.calls)


def test_local_blob_or_confirmed_receipt_corruption_rejected(store, root, complete_project):
    backend, remote = store; queued = backend.enqueue_project(W, P, 1)
    blob = root / '.estado/cloud_storage/blobs' / W / (queued['snapshot_sha256'] + '.blob')
    original = blob.read_bytes(); blob.write_bytes(b'altered')
    with pytest.raises(StudioError): backend.run_outbox(W, P, 1)
    assert backend.outbox_status(W, P)['pending']
    blob.write_bytes(original); verified = backend.run_outbox(W, P, 1)
    receipt = root / '.estado/cloud_storage/receipts' / (verified['receipt_sha256'] + '.json')
    receipt.write_bytes(b'forged receipt')
    with pytest.raises(StudioError): backend.outbox_status(W, P)


def test_capture_complete_editable_zip_replaces_approvals_and_roundtrips(store, complete_project):
    backend, remote = store; p, ws = complete_project
    target = ws / 'exports' / (P + '_editable.zip'); target.parent.mkdir()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as archive:
        archive.writestr('project.json', json.dumps(p))
        names = {a['path'] for a in p['assets']} | {a['metadata']['font_notice']['path'] for a in p['assets'] if a['kind'] == 'font'}
        for name in names: archive.write(ws / name, name)
        archive.writestr('README.txt', 'Editable fixture, no inference or approval.')
    original = target.read_bytes()
    queued = backend.enqueue_project(W, P, 1)
    backend.run_outbox(W, P, queued['revision'])
    result = backend.stage_restore(W, queued['snapshot_sha256'])
    path = backend.root / result['staging_root'] / 'editable.zip'
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert json.loads(archive.read('project.json'))['review'] == {}
        assert 'NESTED_SECRET_NOT_ARCHIVED' not in archive.read('project.json').decode()
    assert target.read_bytes() == original


@pytest.mark.parametrize('mutation', ['private_member', 'stale_timeline', 'missing_font', 'wrong_font', 'symlink_member'])
def test_existing_editable_cannot_smuggle_private_or_stale_content(store, complete_project, mutation):
    backend, remote = store; p, ws = complete_project
    target = ws / 'exports' / (P + '_editable.zip'); target.parent.mkdir()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_STORED) as archive:
        archived = copy.deepcopy(p)
        if mutation == 'stale_timeline': archived['timeline'][0]['end'] = 2
        archive.writestr('project.json', json.dumps(archived))
        names = {a['path'] for a in p['assets']} | {a['metadata']['font_notice']['path'] for a in p['assets'] if a['kind'] == 'font'}
        for name in names:
            if mutation == 'missing_font' and name == p['fonts']['primary']: continue
            if mutation == 'wrong_font' and name == p['fonts']['primary']: archive.writestr(name, b'forged font')
            else: archive.write(ws / name, name)
        if mutation == 'private_member': archive.writestr('.estado/providers.json', 'PRIVATE_CANARY')
        elif mutation == 'symlink_member':
            info = zipfile.ZipInfo('README.txt'); info.external_attr = 0o120777 << 16; archive.writestr(info, 'private path')
    with pytest.raises(StudioError): backend.enqueue_project(W, P, 1)
    assert remote.calls == []


@pytest.mark.parametrize('mutation', ['metadata', 'font_info', 'source', 'file_path', 'file_size_bool', 'missing_notice', 'extra_secret', 'approval', 'brand_family'])
def test_remote_complete_snapshot_adversarial_shape_fails_before_file_fetch(store, complete_project, mutation):
    backend, remote = store; backend.enqueue_project(W, P, 1)
    snapshot = copy.deepcopy(backend.outbox(W, P)['snapshot'])
    if mutation == 'metadata': snapshot['project']['assets'][0]['metadata'] = []
    elif mutation == 'font_info': snapshot['project']['assets'][1]['font_info'] = None
    elif mutation == 'source': snapshot['project']['source'] = []
    elif mutation == 'file_path': snapshot['files'][0]['path'] = '.estado/providers.json'
    elif mutation == 'file_size_bool': snapshot['files'][0]['bytes'] = True
    elif mutation == 'missing_notice': snapshot['files'] = [f for f in snapshot['files'] if f['role'] != 'font_notice']
    elif mutation == 'extra_secret': snapshot['project']['settings']['api_key'] = 'PRIVATE_CANARY'
    elif mutation == 'approval': snapshot['project']['approval_current'] = True
    else: snapshot['project']['style']['branding']['fonts']['primary']['family'] = 'Fake family'
    # Cover modified project bytes too, so metadata guards—not a stale project
    # SHA—must reject the forged document.
    pbytes = cloud._json(snapshot['project'])
    for f in snapshot['files']:
        if f['path'] == 'project.json': f.update(sha256=hashlib.sha256(pbytes).hexdigest(), bytes=len(pbytes))
    raw = cloud._json(snapshot); sha = hashlib.sha256(raw).hexdigest()
    remote.objects['/' + AWS['bucket'] + '/' + backend._blob_key(W, sha)] = raw
    remote.calls.clear()
    with pytest.raises(StudioError): backend.stage_restore(W, sha)
    assert len(remote.calls) == 1 and remote.calls[0]['method'] == 'GET'
