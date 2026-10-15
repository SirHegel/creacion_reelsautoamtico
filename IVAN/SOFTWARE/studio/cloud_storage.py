"""Disabled-by-default private storage foundation, independent of AI credentials.

The administrator owns configuration. No API routes or background synchronizer
are installed here. Restore only stages bytes; it never applies a project.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import hmac
import http.client
import ipaddress
import io
import json
import os
import queue
from pathlib import Path, PurePosixPath
import re
import secrets
import socket
import ssl
import stat
import threading
import time
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import quote

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .core import StudioError

CODE_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'ascendia.cloud-storage/1'
MAX_BLOB_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_SECONDS = 60
REGIONS = frozenset(('us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'sa-east-1',
    'ca-central-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-central-1', 'eu-central-2',
    'eu-north-1', 'ap-south-1', 'ap-southeast-1', 'ap-southeast-2',
    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3'))
WID = re.compile(r'w_[a-f0-9]{32}')
PID = re.compile(r'p_[a-f0-9]{16}')
SHA = re.compile(r'[a-f0-9]{64}')
ETAG = re.compile(r'"[A-Za-z0-9._-]{1,128}"')
DNS_SLOTS = threading.BoundedSemaphore(2)
EDITABLE_FIELDS = frozenset(('id', 'name', 'revision', 'source', 'settings', 'style',
    'timeline', 'transcript', 'audio', 'fonts'))
PROJECT_FIELDS = EDITABLE_FIELDS | frozenset(('created_at', 'updated_at', 'stage', 'assets',
    'mode', 'scene_ir', 'reference_review', 'library_searches', 'history', 'tracking',
    'automation', 'pipeline', 'design_snapshots', 'design_reviews', 'renders'))
SNAPSHOT_SCHEMA = 'ascendia.cloud-snapshot/2'
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024
MAX_FILES = 512
_DROP_KEYS = frozenset(('api_key', 'api_keys', 'secret', 'secret_access_key', 'access_key_id',
    'password', 'password_hash', 'token', 'tokens', 'agent_tokens', 'session', 'sessions',
    'cookies', 'cookie', 'credentials', 'authorization', 'shares', 'memberships', 'endpoint',
    'proxy', 'commands', 'stdout', 'stderr', 'filename', 'tags', 'url', 'preview_url',
    'manual', 'skills_applied', 'full_authorization', 'approved_export', 'approval_current'))


def _cancel(cancel):
    if cancel is not None and (cancel.is_set() if hasattr(cancel, 'is_set') else cancel()):
        raise StudioError('Respaldo cancelado; el outbox se conserva pendiente.', 409, {'kind': 'cloud_cancelled'})


def _decode(data, label):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result: raise ValueError()
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise StudioError(label + ' no contiene JSON canónico finito.', 409) from None


def _portable(value, depth=0):
    """Archive editable data without authentication, commands or reusable approvals."""
    if depth > 64: raise StudioError('El proyecto tiene una estructura demasiado profunda.', 413)
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str): raise StudioError('El proyecto requiere claves JSON de texto.')
            lowered = key.lower().replace('-', '_')
            if lowered in _DROP_KEYS or lowered.endswith(('_token', '_api_key')) or any(term in lowered for term in ('password', 'credential', 'client_secret', 'private_key', 'sessiontoken', 'accesstoken', 'refreshtoken', 'apikey')): continue
            if key in ('approved', 'editorial_approved', 'production_conformant', 'audio_listened',
                       'visual_reviewed', 'chin_reviewed', 'verified_execution', 'verified_external_inference'):
                result[key] = False
            elif key == 'path' or key.endswith('_path'):
                # Private engine receipts are provenance, not files to execute or
                # permission to include arbitrary .estado objects.
                if isinstance(item, str) and not (item.startswith('.estado/') or item.startswith('/') or '..' in PurePosixPath(item).parts or '\\' in item or ':' in item or '%' in item):
                    result[key] = item
            else: result[key] = _portable(item, depth + 1)
        return result
    if isinstance(value, list): return [_portable(item, depth + 1) for item in value]
    if value is None or type(value) in (str, bool, int, float): return value
    raise StudioError('Datos no JSON en el proyecto.')


def _file_name(value):
    if not isinstance(value, str) or not value or len(value) > 1024 or '\\' in value or '%' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise StudioError('Nombre de archivo del snapshot inválido.', 403)
    pure = PurePosixPath(value)
    if pure.is_absolute() or pure.as_posix() != value or any(x in ('', '.', '..', '.estado') for x in value.split('/')):
        raise StudioError('Ruta privada o ajena en el snapshot.', 403)
    return value


@contextmanager
def _project_lock(root, wid, pid):
    _identifier(wid, WID, 'Espacio'); _identifier(pid, PID, 'Proyecto')
    path = _path(root, '.estado/cloud_storage/project_locks/' + wid + '_' + pid + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a+b') as stream:
        if os.fstat(stream.fileno()).st_nlink != 1: raise StudioError('Lock de nube inválido.', 403)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


@contextmanager
def _workspace_lock(root, wid):
    """Use the fixed worker StoreLock, or its same POSIX file without rebinding ROOT."""
    from . import core
    expected = root / 'workspaces' / wid
    path = _path(root, 'workspaces/' + wid + '/.estado/store.lock')
    if core.ROOT == expected:
        with core.LOCK: yield
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a+b') as stream:
        if os.fstat(stream.fileno()).st_nlink != 1: raise StudioError('Lock canónico inválido.', 403)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _sealed(root, relative, record):
    value = copy.deepcopy(record)
    value.pop('seal', None)
    value['seal'] = hmac.new(_key(root), _json(value), hashlib.sha256).hexdigest()
    _write(root, relative, _json(value))
    return value


def _verify_sealed(root, relative):
    value = _decode(_read(root, relative), 'Recibo de nube')
    if not isinstance(value, dict): raise StudioError('Recibo de nube inválido.', 409)
    seal = value.pop('seal', None)
    actual = hmac.new(_key(root), _json(value), hashlib.sha256).hexdigest()
    if not isinstance(seal, str) or not hmac.compare_digest(seal, actual):
        raise StudioError('El recibo de nube fue alterado.', 409)
    return {**value, 'seal': seal}


def _validate_snapshot2(snapshot, wid):
    _closed(snapshot, {'schema', 'workspace_id', 'project_id', 'project_revision', 'project', 'files',
                       'source_project_sha256', 'editorial_approved', 'restore_requires_canonical_import'})
    if snapshot['schema'] != SNAPSHOT_SCHEMA or snapshot['workspace_id'] != wid or snapshot['editorial_approved'] is not False or snapshot['restore_requires_canonical_import'] is not True:
        raise StudioError('Snapshot completo ajeno o con aprobaciones heredadas.', 403)
    pid = _identifier(snapshot['project_id'], PID, 'Proyecto')
    _identifier(snapshot['source_project_sha256'], SHA, 'SHA de proyecto original')
    p = snapshot['project']
    reset_fields = {'review', 'gates', 'approved_export', 'approval_current', 'full_authorization', 'editorial_approved', 'production_conformant'}
    if not isinstance(p, dict) or set(p) - (PROJECT_FIELDS | reset_fields) or p.get('id') != pid or type(p.get('revision')) is not int or p['revision'] < 1 or type(snapshot['project_revision']) is not int or snapshot['project_revision'] != p['revision']:
        raise StudioError('Proyecto del snapshot fuera de contrato.', 403)
    if p.get('review') != {} or p.get('gates') != {} or p.get('approved_export') is not None or p.get('full_authorization') is not None or p.get('approval_current') is not False or p.get('editorial_approved') is not False or p.get('production_conformant') is not False:
        raise StudioError('La restauración no puede heredar una aprobación.', 403)
    if _portable({k: v for k, v in p.items() if k in PROJECT_FIELDS}) != {k: v for k, v in p.items() if k in PROJECT_FIELDS}:
        raise StudioError('El snapshot contiene rutas privadas, secretos o revisiones reutilizables.', 403)
    _json(p)
    for key, kind in (('settings', dict), ('style', dict), ('fonts', dict), ('timeline', list), ('transcript', dict), ('audio', list), ('assets', list)):
        if not isinstance(p.get(key), kind): raise StudioError('Proyecto incompleto: ' + key)
    if not isinstance(snapshot['files'], list) or not 1 <= len(snapshot['files']) <= MAX_FILES:
        raise StudioError('Tabla de archivos del snapshot inválida.', 413)
    files, total = {}, 0
    for entry in snapshot['files']:
        _closed(entry, {'path', 'role', 'sha256', 'bytes', 'asset_id'}, {'path', 'role', 'sha256', 'bytes'})
        name = _file_name(entry['path']); role = entry['role']
        if name in files or type(entry['bytes']) is not int or not 0 < entry['bytes'] <= MAX_BLOB_BYTES:
            raise StudioError('Archivo duplicado o tamaño inválido en snapshot.')
        _identifier(entry['sha256'], SHA, 'SHA de archivo')
        allowed = ((role == 'project' and name == 'project.json') or
                   (role == 'branding' and name == 'branding.json') or
                   (role == 'asset' and re.fullmatch(r'assets/(?:video|broll|audio|images|fonts)/[^/]+\.[A-Za-z0-9]{1,8}', name)) or
                   (role == 'font_notice' and re.fullmatch(r'assets/fonts/licenses/[a-f0-9]{24}\.txt', name) and entry['bytes'] <= 65536) or
                   (role == 'artifact' and (name in {'editable.zip', 'receipts.json'} or re.fullmatch(r'outputs/[a-f0-9]{64}\.mp4', name) or re.fullmatch(r'artifacts/(?:tracking|automation|design)/[a-f0-9]{64}\.(?:json|png|jpg|csv)', name))))
        if not allowed or (role != 'asset' and 'asset_id' in entry): raise StudioError('Archivo ajeno a la cobertura del proyecto.', 403)
        if role == 'asset' and (not isinstance(entry.get('asset_id'), str) or not re.fullmatch(r'a_[A-Za-z0-9_-]{1,100}', entry['asset_id'])):
            raise StudioError('ID de archivo adjunto inválido.')
        files[name] = entry; total += entry['bytes']
    if total > MAX_SNAPSHOT_BYTES: raise StudioError('El snapshot supera 256 MiB.', 413)
    project_data = _json(p)
    if files.get('project.json', {}).get('sha256') != hashlib.sha256(project_data).hexdigest() or files['project.json']['bytes'] != len(project_data):
        raise StudioError('project.json no está cubierto por su SHA/tamaño.', 409)
    ids, asset_paths = set(), set()
    if len(p['assets']) > 256: raise StudioError('Demasiados recursos adjuntos.', 413)
    for asset in p['assets']:
        if not isinstance(asset, dict) or not isinstance(asset.get('id'), str) or not isinstance(asset.get('path'), str) or not isinstance(asset.get('kind'), str) or not re.fullmatch(r'a_[A-Za-z0-9_-]{1,100}', asset['id']) or asset['id'] in ids or asset['path'] in asset_paths or asset.get('kind') not in {'video', 'broll', 'audio', 'music', 'sfx', 'image', 'font'}:
            raise StudioError('Recurso incompleto o repetido en snapshot.')
        if not isinstance(asset.get('metadata', {}), dict) or (asset['kind'] == 'font' and not isinstance(asset.get('font_info'), dict)):
            raise StudioError('Metadata o descriptor de fuente inválidos.')
        entry = files.get(asset.get('path'))
        if not entry or entry['role'] != 'asset' or entry.get('asset_id') != asset['id'] or entry['sha256'] != asset.get('sha256') or type(asset.get('size')) is not int or entry['bytes'] != asset['size']:
            raise StudioError('Falta cobertura íntegra de un recurso.', 409)
        ids.add(asset['id']); asset_paths.add(asset['path'])
        notice = asset.get('metadata', {}).get('font_notice')
        if notice is not None:
            if asset['kind'] != 'font' or not isinstance(notice, dict): raise StudioError('Aviso asociado a recurso no tipográfico.')
            sha = _identifier(notice.get('sha256'), SHA, 'SHA de aviso')
            name = 'assets/fonts/licenses/' + sha[:24] + '.txt'
            if notice.get('path') != name or files.get(name, {}).get('sha256') != sha or files[name]['role'] != 'font_notice':
                raise StudioError('Falta el aviso íntegro de una fuente.', 409)
    if not isinstance(p.get('source'), str) or p['source'] not in ids: raise StudioError('El snapshot carece de fuente propia.', 403)
    if {f.get('asset_id') for f in files.values() if f['role'] == 'asset'} != ids:
        raise StudioError('Un medio no pertenece a los adjuntos del proyecto.', 403)
    fonts = {a['path']: a for a in p['assets'] if a['kind'] == 'font'}
    if set(p['fonts']) != {'primary', 'accent'} or any(not isinstance(path, str) or path not in fonts for path in p['fonts'].values()):
        raise StudioError('Las fuentes de rol no están cubiertas.', 409)
    kinds = {a['id']: a['kind'] for a in p['assets']}
    def reference(value, font=False):
        if not isinstance(value, str) or value not in ids or (font and kinds[value] != 'font'):
            raise StudioError('Una escena o pista referencia un recurso no incluido.', 409)
    for scene in p['timeline']:
        if not isinstance(scene, dict): raise StudioError('Escena inválida en snapshot.')
        for key in ('asset_id', 'transition_asset_id'):
            if scene.get(key) is not None: reference(scene[key])
        layers = scene.get('overlays', [])
        if not isinstance(layers, list): raise StudioError('Capas inválidas en snapshot.')
        for layer in layers:
            if not isinstance(layer, dict): raise StudioError('Capa inválida en snapshot.')
            reference(layer.get('asset_id'))
        design = scene.get('motion_design')
        if design is not None:
            if not isinstance(design, dict) or not isinstance(design.get('elements'), list): raise StudioError('Motion editable inválido.')
            for element in design['elements']:
                if not isinstance(element, dict): raise StudioError('Elemento editable inválido.')
                if element.get('type') == 'media': reference(element.get('asset_id'))
                if element.get('font_asset_id') is not None: reference(element['font_asset_id'], True)
    for track in p['audio']:
        if not isinstance(track, dict): raise StudioError('Pista inválida en snapshot.')
        reference(track.get('asset_id'))
    brand = p['style'].get('branding')
    if brand is not None:
        from .brand_bundles import SNAPSHOT_FIELDS, FACE_FIELDS, COLORS
        if not isinstance(brand, dict) or set(brand) - (SNAPSHOT_FIELDS | {'bundle_import'}) or not SNAPSHOT_FIELDS <= set(brand) or brand.get('editorial_approved') is not False or brand.get('id') != 'ivan_branding' or brand.get('base') != 'ivan_yo_clone' or brand.get('font_override_explicit') is not True:
            raise StudioError('Marca portable fuera de contrato.', 403)
        if type(brand['revision']) is not int or brand['revision'] < 1 or not isinstance(brand['name'], str) or not 1 <= len(brand['name']) <= 120 or not isinstance(brand['instructions'], str) or len(brand['instructions']) > 8000 or not isinstance(brand['language'], str) or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z]{2,4})?', brand['language']):
            raise StudioError('Texto o revisión de marca inválidos.')
        if not isinstance(brand.get('colors'), dict) or set(brand['colors']) != COLORS or any(not isinstance(c, str) or not re.fullmatch(r'#[a-fA-F0-9]{6}', c) for c in brand['colors'].values()):
            raise StudioError('Paleta de marca inválida.')
        _identifier(brand['base_rules_sha256'], SHA, 'SHA de perfil')
        if not isinstance(brand['fonts'], dict) or set(brand['fonts']) != {'primary', 'accent'}:
            raise StudioError('Roles de marca inválidos.')
        for role, face in brand['fonts'].items():
            actual = fonts[p['fonts'][role]]
            if not isinstance(face, dict) or set(face) != FACE_FIELDS or face.get('asset_id') != actual['id'] or face.get('path') != actual['path'] or face.get('sha256') != actual['sha256'] or any(face.get(k) != actual.get('font_info', {}).get(k) for k in ('family', 'style')):
                raise StudioError('La marca no coincide con sus fuentes reales.', 409)
        if brand['logo_asset_id'] is not None and not any(a['id'] == brand['logo_asset_id'] and a['kind'] == 'image' for a in p['assets']):
            raise StudioError('Logo no incluido en la marca.', 409)
        data = _json(brand)
        if files.get('branding.json', {}).get('sha256') != hashlib.sha256(data).hexdigest() or files['branding.json']['bytes'] != len(data):
            raise StudioError('Marca sin cobertura de bytes.', 409)
    elif 'branding.json' in files: raise StudioError('Descriptor de marca sin vínculo al proyecto.', 403)
    return files


def _editable_zip(data, original, portable, source_data):
    """Inspect an existing own editable and remove reusable approvals in JSON."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= MAX_FILES or len({e.filename for e in entries}) != len(entries): raise ValueError()
            total = 0
            allowed = set(source_data) | {'project.json', 'README.txt', 'transcript.srt', 'transcript.vtt', 'broll_manifest.csv', 'approved_preview.mp4', 'hyperframes_editable.zip'}
            for entry in entries:
                name = _file_name(entry.filename); mode = entry.external_attr >> 16
                total += entry.file_size
                if name not in allowed or entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) or entry.file_size > MAX_BLOB_BYTES or total > MAX_SNAPSHOT_BYTES or entry.file_size > 1024 * 1024 and entry.file_size / max(1, entry.compress_size) > 250:
                    raise StudioError('El editable incluye contenido privado, aliases o tamaños no admitidos.', 403)
            if archive.testzip() is not None: raise ValueError()
            p = _decode(archive.read('project.json'), 'Editable existente')
            if not isinstance(p, dict) or not isinstance(p.get('assets'), list): raise StudioError('Proyecto del ZIP inválido.')
            for key in ('source', 'settings', 'style', 'fonts', 'timeline', 'transcript', 'audio'):
                if p.get(key) != original.get(key): raise StudioError('El editable existente está obsoleto; regénéralo antes del respaldo.', 409)
            archived_assets = {a.get('id'): a for a in p.get('assets', []) if isinstance(a, dict)}
            if set(archived_assets) != {a['id'] for a in portable['assets']}:
                raise StudioError('El editable no cubre los recursos actuales.', 409)
            for item in portable['assets']:
                old = archived_assets[item['id']]
                if old.get('path') != item['path'] or old.get('sha256') != item['sha256']:
                    raise StudioError('El editable contiene un recurso antiguo.', 409)
            for name, actual in source_data.items():
                if name.startswith('assets/') and archive.read(name) != actual:
                    raise StudioError('El editable contiene bytes distintos de los medios actuales.', 409)
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as target:
                for entry in entries:
                    name = entry.filename
                    target.writestr(name, _json(portable) if name == 'project.json' else archive.read(name))
            result = output.getvalue()
            if len(result) > MAX_BLOB_BYTES: raise StudioError('Editable expandido supera 64 MiB.', 413)
            return result
    except StudioError: raise
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, RuntimeError):
        raise StudioError('El ZIP editable no superó CRC, cobertura o JSON.', 409) from None


def _json(value):
    try:
        data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        raise StudioError('Los datos de nube deben ser JSON finito.', 400) from None
    if len(data) > MAX_JSON_BYTES:
        raise StudioError('El documento de nube supera su límite.', 413)
    return data


def _closed(value, fields, required=None):
    if not isinstance(value, dict) or set(value) - set(fields) or not set(required or fields) <= set(value):
        raise StudioError('Campos de almacenamiento no válidos.')
    return value


def _root(root=None):
    path = CODE_ROOT if root is None else Path(root).absolute()
    if path.resolve() != path or not path.is_relative_to(CODE_ROOT) or path.is_relative_to(CODE_ROOT / 'workspaces'):
        raise StudioError('La configuración administradora debe permanecer en SOFTWARE, fuera de los workspaces.', 403)
    if not path.is_dir():
        raise StudioError('Raíz administradora inexistente.', 403)
    return path


def _path(root, relative, existing=False):
    if not isinstance(relative, str) or '\\' in relative or '%' in relative or any(p in ('', '.', '..') for p in relative.split('/')):
        raise StudioError('Ruta de almacenamiento no válida.', 403)
    pure = PurePosixPath(relative)
    path = root / relative
    if pure.is_absolute() or path.resolve() != path or not path.is_relative_to(root):
        raise StudioError('Almacenamiento no admite enlaces ni rutas ajenas.', 403)
    if path.exists():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise StudioError('El archivo privado no admite aliases.', 403)
    elif existing:
        raise StudioError('Archivo de almacenamiento inexistente.', 404)
    return path


def _signature(path):
    s = path.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _read(root, relative, limit=MAX_JSON_BYTES):
    path = _path(root, relative, True); before = _signature(path)
    if relative.startswith('.estado/cloud_storage/') and path.stat().st_mode & 0o077:
        raise StudioError('El archivo de nube requiere permisos privados.', 403)
    if not 0 < before[2] <= limit:
        raise StudioError('Archivo privado fuera de sus límites.', 413)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if info.st_ino != before[1] or info.st_dev != before[0] or info.st_nlink != 1:
            raise StudioError('El archivo cambió antes de abrirse.', 409)
        data = stream.read(limit + 1)
    if len(data) != before[2] or _signature(_path(root, relative, True)) != before:
        raise StudioError('El archivo cambió durante su lectura.', 409)
    return data


def _write(root, relative, data):
    target = _path(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _path(root, relative)
    temp = target.with_name(target.name + '.' + secrets.token_hex(12) + '.tmp')
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        _path(root, relative)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return target


@contextmanager
def _lock(root):
    path = _path(root, '.estado/cloud_storage/lock')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'a+b') as stream:
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise StudioError('Bloqueo de almacenamiento inválido.', 403)
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def validate_config(config):
    if not isinstance(config, dict): raise StudioError('Configuración de nube inválida.')
    provider = config.get('provider')
    fields = {'provider', 'bucket', 'region', 'enabled'} if provider == 'aws_s3' else {'provider', 'bucket', 'account_id', 'enabled'}
    _closed(config, fields)
    bucket = config['bucket']
    if provider not in ('aws_s3', 'cloudflare_r2') or type(config['enabled']) is not bool:
        raise StudioError('Proveedor o activación de nube inválidos.')
    if not isinstance(bucket, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', bucket) or bucket.startswith(('xn--', 'sthree-', 'amzn-s3-demo-')) or bucket.endswith(('-s3alias', '--ol-s3', '--x-s3', '--table-s3')):
        raise StudioError('El bucket requiere un nombre simple admitido, sin puntos ni aliases.')
    result = copy.deepcopy(config)
    if provider == 'aws_s3':
        if not isinstance(config['region'], str) or config['region'] not in REGIONS: raise StudioError('Región AWS fuera de la lista admitida.')
        result['host'] = 's3.' + config['region'] + '.amazonaws.com'
    else:
        if not isinstance(config['account_id'], str) or not re.fullmatch(r'[a-f0-9]{32}', config['account_id']):
            raise StudioError('Cuenta R2 inválida.')
        result.update(region='auto', host=config['account_id'] + '.r2.cloudflarestorage.com')
    return result


def _credentials(value):
    _closed(value, {'access_key_id', 'secret_access_key', 'session_token'}, {'access_key_id', 'secret_access_key'})
    if not isinstance(value['access_key_id'], str) or not re.fullmatch(r'[A-Za-z0-9]{16,128}', value['access_key_id']):
        raise StudioError('Credencial de almacenamiento inválida.')
    for key in ('secret_access_key', 'session_token'):
        if key in value and (not isinstance(value[key], str) or not 16 <= len(value[key]) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value[key])):
            raise StudioError('Credencial de almacenamiento inválida.')
    return copy.deepcopy(value)


def _key(root, create=False):
    path = _path(root, '.estado/cloud_storage/master.key')
    if not path.exists():
        if not create: raise StudioError('Falta la llave privada de almacenamiento.', 409)
        _write(root, '.estado/cloud_storage/master.key', secrets.token_bytes(32))
    data = _read(root, '.estado/cloud_storage/master.key', 32)
    if len(data) != 32 or path.stat().st_mode & 0o077:
        raise StudioError('Llave de almacenamiento inválida o con permisos abiertos.', 403)
    return data


def _config_record(root):
    raw = _read(root, '.estado/cloud_storage/config.enc', MAX_JSON_BYTES)
    try:
        if len(raw) < 28: raise ValueError()
        record = json.loads(AESGCM(_key(root)).decrypt(raw[:12], raw[12:], SCHEMA.encode()))
        _closed(record, {'revision', 'config', 'credentials'})
        if type(record['revision']) is not int or record['revision'] < 1: raise ValueError()
        validate_config(record['config']); _credentials(record['credentials'])
        return record
    except StudioError: raise
    except Exception:
        raise StudioError('Configuración cifrada de almacenamiento inválida.', 409) from None


def status(root=None):
    root = _root(root)
    configured = _path(root, '.estado/cloud_storage/config.enc').exists()
    record = _config_record(root) if configured else None
    return {'foundation_available': True, 'configured': configured,
            'enabled': bool(record and record['config']['enabled']),
            'provider': record['config']['provider'] if record else 'local',
            'revision': record['revision'] if record else 0,
            'remote': False, 'live_remote_execution_verified': False,
            'automatic_sync': False, 'restore_applies_project': False,
            'max_single_part_bytes': MAX_BLOB_BYTES,
            'limitations': ['Foundation only; no live remote service verified.',
                'No multipart, distributed store, automatic outbox runner, quotas or billing.']}


def configure(config, credentials, expected_revision=0, root=None):
    """Administrator-only integration hook; never expose to workspace users."""
    root = _root(root); validate_config(config); credentials = _credentials(credentials)
    if type(expected_revision) is not int or expected_revision < 0: raise StudioError('Revisión administradora inválida.')
    with _lock(root):
        existing = _config_record(root) if _path(root, '.estado/cloud_storage/config.enc').exists() else None
        revision = existing['revision'] if existing else 0
        if revision != expected_revision: raise StudioError('La configuración de nube cambió.', 409)
        record = {'revision': revision + 1, 'config': copy.deepcopy(config), 'credentials': credentials}
        nonce = secrets.token_bytes(12)
        data = nonce + AESGCM(_key(root, True)).encrypt(nonce, _json(record), SCHEMA.encode())
        _write(root, '.estado/cloud_storage/config.enc', data)
    return status(root)


def _identifier(value, pattern, label):
    if not isinstance(value, str) or not pattern.fullmatch(value): raise StudioError(label + ' inválido.', 403)
    return value


def _public_ips(host):
    if not DNS_SLOTS.acquire(timeout=2): raise StudioError('La resolución de almacenamiento está ocupada.', 429)
    answer = queue.Queue(maxsize=1)
    def resolve():
        try: answer.put((True, socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
        except Exception: answer.put((False, None))
        finally: DNS_SLOTS.release()
    worker = threading.Thread(target=resolve, daemon=True)
    try: worker.start()
    except BaseException: DNS_SLOTS.release(); raise
    try: ok, rows = answer.get(timeout=5)
    except queue.Empty: raise StudioError('La resolución de almacenamiento agotó su plazo.', 504) from None
    if not ok: raise StudioError('No se pudo resolver el endpoint oficial.', 502)
    ips = sorted({row[4][0] for row in rows})
    try:
        public = bool(ips) and all(ipaddress.ip_address(ip).is_global and not ipaddress.ip_address(ip).is_multicast for ip in ips)
    except ValueError:
        public = False
    if not public:
        raise StudioError('El endpoint resolvió una dirección no pública.', 403)
    return ips


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, 443, timeout=10, context=ssl.create_default_context())
        self.address = address
    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try: self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException: raw.close(); raise


def _sign(config, credentials, method, uri, headers, payload, stamp=None):
    stamp = stamp or datetime.now(timezone.utc)
    day, full = stamp.strftime('%Y%m%d'), stamp.strftime('%Y%m%dT%H%M%SZ')
    signed = {key.lower(): str(value).strip() for key, value in headers.items()}
    signed.update(host=config['host'], **{'x-amz-date': full, 'x-amz-content-sha256': hashlib.sha256(payload).hexdigest()})
    if credentials.get('session_token'): signed['x-amz-security-token'] = credentials['session_token']
    names = ';'.join(sorted(signed)); canonical = ''.join(k + ':' + signed[k] + '\n' for k in sorted(signed))
    request = '\n'.join((method, uri, '', canonical, names, signed['x-amz-content-sha256']))
    scope = '/'.join((day, config['region'], 's3', 'aws4_request'))
    message = '\n'.join(('AWS4-HMAC-SHA256', full, scope, hashlib.sha256(request.encode()).hexdigest()))
    key = ('AWS4' + credentials['secret_access_key']).encode()
    for value in (day, config['region'], 's3', 'aws4_request'): key = hmac.new(key, value.encode(), hashlib.sha256).digest()
    signature = hmac.new(key, message.encode(), hashlib.sha256).hexdigest()
    signed['authorization'] = 'AWS4-HMAC-SHA256 Credential=' + credentials['access_key_id'] + '/' + scope + ', SignedHeaders=' + names + ', Signature=' + signature
    return signed


class HTTPSStorageTransport:
    """Fixed official host, pinned public DNS result, verified TLS; no proxies."""
    live = True
    def request(self, config, credentials, method, uri, headers, body, limit):
        if not isinstance(config, dict): raise StudioError('Endpoint de almacenamiento inválido.', 403)
        fields = {'provider', 'bucket', 'region', 'enabled'} if config.get('provider') == 'aws_s3' else {'provider', 'bucket', 'account_id', 'enabled'}
        fixed = validate_config({k: v for k, v in config.items() if k in fields})
        if config != fixed: raise StudioError('El transporte sólo usa endpoints oficiales derivados.', 403)
        credentials = _credentials(credentials)
        pattern = '/' + re.escape(config['bucket']) + r'/v1/w_[a-f0-9]{32}/(?:blobs/[a-f0-9]{64}|projects/p_[a-f0-9]{16}/manifest\.json)'
        if method not in ('GET', 'HEAD', 'PUT') or not isinstance(uri, str) or not re.fullmatch(pattern, uri):
            raise StudioError('Operación remota no admitida.', 403)
        started = time.monotonic()
        if not isinstance(headers, dict) or set(headers) - {'If-None-Match', 'If-Match', 'Content-Type', 'x-amz-meta-sha256'} or any(not isinstance(k, str) or not isinstance(v, str) or '\n' in k + v or '\r' in k + v for k, v in headers.items()):
            raise StudioError('Cabeceras de almacenamiento inválidas.')
        if not isinstance(body, bytes) or len(body) > MAX_BLOB_BYTES or type(limit) is not int or not 0 <= limit <= MAX_BLOB_BYTES: raise StudioError('Transferencia fuera de límite.', 413)
        connection = _PinnedHTTPS(config['host'], _public_ips(config['host'])[0])
        remaining = MAX_SECONDS - (time.monotonic() - started)
        if remaining <= 0: raise StudioError('Transferencia de nube agotó su plazo.', 504)
        connection.timeout = min(10, remaining)
        expired = threading.Event()
        def expire():
            expired.set()
            sock = getattr(connection, 'sock', None)
            if sock is not None:
                try: sock.shutdown(socket.SHUT_RDWR)
                except OSError: pass
            connection.close()
        timer = threading.Timer(remaining, expire); timer.daemon = True; timer.start()
        try:
            connection.putrequest(method, uri, skip_host=True, skip_accept_encoding=True)
            for key, value in _sign(config, credentials, method, uri, headers, body).items(): connection.putheader(key, value)
            connection.putheader('Content-Length', str(len(body))); connection.endheaders()
            for offset in range(0, len(body), 256 * 1024):
                if time.monotonic() - started > MAX_SECONDS: raise StudioError('Transferencia de nube agotó su plazo.', 504)
                connection.send(body[offset:offset + 256 * 1024])
            response = connection.getresponse()
            if 300 <= response.status < 400: raise StudioError('Redirección de almacenamiento rechazada.', 502)
            expected = response.getheader('Content-Length')
            if expected is not None and (not expected.isdigit() or int(expected) > limit) and method != 'HEAD':
                raise StudioError('Respuesta de almacenamiento fuera de límite.', 413)
            chunks, size = [], 0
            while method != 'HEAD':
                if time.monotonic() - started > MAX_SECONDS: raise StudioError('Transferencia de nube agotó su plazo.', 504)
                piece = response.read(min(256 * 1024, limit + 1 - size))
                if not piece: break
                size += len(piece)
                if size > limit: raise StudioError('Respuesta de almacenamiento fuera de límite.', 413)
                chunks.append(piece)
            return {'status': response.status, 'headers': dict(response.getheaders()), 'body': b''.join(chunks)}
        except StudioError: raise
        except (OSError, http.client.HTTPException):
            raise StudioError('Transferencia de nube agotó su plazo.' if expired.is_set() else 'Falló el transporte HTTPS de almacenamiento.', 504 if expired.is_set() else 502) from None
        finally: timer.cancel(); connection.close()


class CloudStorage:
    def __init__(self, root=None, transport=None):
        self.root = _root(root)
        self.transport = HTTPSStorageTransport() if transport is None else transport
        self.live = transport is None

    def _active(self):
        if not _path(self.root, '.estado/cloud_storage/config.enc').exists():
            raise StudioError('El almacenamiento remoto aún no está configurado.', 409)
        record = _config_record(self.root)
        if record['config']['enabled'] is not True: raise StudioError('El almacenamiento remoto está desactivado.', 409)
        return record

    def _request(self, method, key, headers=None, body=b'', limit=MAX_JSON_BYTES, expected_config=None):
        record = self._active(); config = validate_config(record['config'])
        if expected_config is not None and record != expected_config:
            raise StudioError('La configuración cambió durante el respaldo.', 409)
        if not isinstance(key, str) or not re.fullmatch(r'v1/w_[a-f0-9]{32}/(?:blobs/[a-f0-9]{64}|projects/p_[a-f0-9]{16}/manifest\.json)', key):
            raise StudioError('Clave remota fuera del espacio autorizado.', 403)
        uri = quote('/' + config['bucket'] + '/' + key, safe='/~-_.')
        reply = self.transport.request(config, record['credentials'], method, uri, headers or {}, body, limit)
        if _config_record(self.root) != record: raise StudioError('La configuración cambió durante la transferencia.', 409)
        if not isinstance(reply, dict) or set(reply) != {'status', 'headers', 'body'} or type(reply['status']) is not int or not isinstance(reply['headers'], dict) or not isinstance(reply['body'], bytes) or len(reply['body']) > limit:
            raise StudioError('Respuesta de almacenamiento inválida.', 502)
        if reply['status'] in (409, 412): raise StudioError('Conflicto de versión remota; recarga antes de confirmar.', 409,
                                                         {'kind': 'remote_precondition', 'remote_status': reply['status']})
        if not 200 <= reply['status'] < 300: raise StudioError('La operación de almacenamiento no se completó.', 502)
        return reply

    def _cache_blob(self, wid, data):
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BLOB_BYTES:
            raise StudioError('Un archivo del snapshot supera 64 MiB o está vacío.', 413)
        sha = hashlib.sha256(data).hexdigest()
        relative = '.estado/cloud_storage/blobs/' + wid + '/' + sha + '.blob'
        target = _path(self.root, relative)
        if target.exists():
            if _read(self.root, relative, MAX_BLOB_BYTES) != data:
                raise StudioError('Cambió un blob local inmutable.', 409)
        else: _write(self.root, relative, data)
        return sha

    def _complete_snapshot(self, wid, pid, expected_project_revision, include_outputs, progress, cancel):
        """Read a canonical workspace only; never invoke an exporter or renderer."""
        prefix = 'workspaces/' + wid + '/'
        captured = {}
        def read(relative, expected=None, limit=MAX_BLOB_BYTES):
            _cancel(cancel)
            data = _read(self.root, prefix + relative, limit)
            if expected is not None and hashlib.sha256(data).hexdigest() != expected:
                raise StudioError('Un archivo del proyecto cambió respecto al catálogo.', 409)
            captured[relative] = hashlib.sha256(data).hexdigest()
            return data
        raw = read('projects/' + pid + '/project.json', limit=MAX_JSON_BYTES)
        project = _decode(raw, 'Proyecto canónico')
        if not isinstance(project, dict) or project.get('id') != pid or type(expected_project_revision) is not int or expected_project_revision < 1 or type(project.get('revision')) is not int or project['revision'] != expected_project_revision:
            raise StudioError('El proyecto cambió antes del snapshot.', 409)
        catalog_raw = read('.estado/assets.json', limit=MAX_JSON_BYTES)
        catalog = _decode(catalog_raw, 'Catálogo propio')
        if not isinstance(catalog, list) or any(not isinstance(a, dict) or not isinstance(a.get('id'), str) for a in catalog) or len({a['id'] for a in catalog}) != len(catalog):
            raise StudioError('Catálogo de medios inválido.', 409)
        catalog = {a['id']: a for a in catalog}
        if not isinstance(project.get('assets'), list) or len(project['assets']) > 256:
            raise StudioError('El proyecto requiere recursos adjuntos acotados.')
        for field in ('style', 'settings', 'fonts', 'transcript'):
            if not isinstance(project.get(field), dict): raise StudioError('Proyecto canónico inválido: ' + field)
        portable = _portable({k: v for k, v in project.items() if k in PROJECT_FIELDS})
        portable.update(review={}, gates={}, approved_export=None, approval_current=False,
                        full_authorization=None, editorial_approved=False, production_conformant=False)
        portable['assets'] = []
        files, source_data, ids, paths, total = [], {}, set(), set(), 0
        def add(name, role, data, asset_id=None):
            nonlocal total
            _file_name(name)
            if name in paths:
                if source_data[name] != data: raise StudioError('Ruta repetida con bytes distintos.', 409)
                return
            if len(files) >= MAX_FILES or total + len(data) > MAX_SNAPSHOT_BYTES:
                raise StudioError('Snapshot fuera del límite de archivos/256 MiB.', 413)
            sha = self._cache_blob(wid, data)
            row = {'path': name, 'role': role, 'sha256': sha, 'bytes': len(data)}
            if asset_id is not None: row['asset_id'] = asset_id
            files.append(row); source_data[name] = data; paths.add(name); total += len(data)
        for item in project['assets']:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids or item['id'] not in catalog:
                raise StudioError('Un recurso no pertenece al catálogo propio.', 403)
            canonical = catalog[item['id']]
            if not isinstance(canonical.get('metadata', {}), dict) or not isinstance(canonical.get('kind'), str):
                raise StudioError('Metadata de recurso canónico inválida.')
            if any(item.get(k) != canonical.get(k) for k in ('path', 'sha256', 'kind')):
                raise StudioError('El recurso adjunto no coincide con su fuente canónica.', 409)
            name = _file_name(canonical.get('path'))
            if not re.fullmatch(r'assets/(?:video|broll|audio|images|fonts)/[^/]+\.[A-Za-z0-9]{1,8}', name) or canonical.get('kind') not in {'video', 'broll', 'audio', 'music', 'sfx', 'image', 'font'}:
                raise StudioError('Ruta de medio ajena al proyecto.', 403)
            sha = _identifier(canonical.get('sha256'), SHA, 'SHA de medio')
            data = read(name, sha)
            if type(canonical.get('size')) is not int or canonical['size'] != len(data):
                raise StudioError('Tamaño de medio distinto del catálogo.', 409)
            add(name, 'asset', data, canonical['id']); ids.add(canonical['id'])
            row = _portable(canonical)
            row['verification'] = {'visual': False, 'audio': False, 'rights': 'pending_reinspection'}
            if canonical['kind'] == 'font':
                from .fonts import inspect_font
                info = inspect_font(self.root / prefix / name, self.root / prefix)
                if info['sha256'] != sha: raise StudioError('La fuente cambió durante su inspección.', 409)
                row['font_info'] = _portable(info)
                notice = canonical.get('metadata', {}).get('font_notice')
                if notice is not None:
                    _closed(notice, {'path', 'sha256', 'license', 'source_url'}, {'path', 'sha256'})
                    notice_sha = _identifier(notice['sha256'], SHA, 'SHA de aviso')
                    notice_name = 'assets/fonts/licenses/' + notice_sha[:24] + '.txt'
                    if notice.get('path') != notice_name: raise StudioError('Aviso de fuente fuera del contenido canónico.', 403)
                    notice_data = read(notice_name, notice_sha, 65536)
                    try: notice_data.decode('utf-8')
                    except UnicodeDecodeError: raise StudioError('Aviso de fuente no UTF-8.') from None
                    add(notice_name, 'font_notice', notice_data)
            portable['assets'].append(row)
            progress(.1 + .3 * len(ids) / max(1, len(project['assets'])), 'Capturando recursos canónicos propios')
        if not isinstance(project.get('source'), str) or project['source'] not in ids: raise StudioError('Falta el crudo adjunto al snapshot.', 403)
        if not isinstance(project.get('fonts'), dict) or set(project['fonts']) != {'primary', 'accent'}:
            raise StudioError('El snapshot requiere dos fuentes explícitas.')
        font_rows = {a['path']: a for a in portable['assets'] if a['kind'] == 'font'}
        if any(not isinstance(path, str) or path not in font_rows for path in project['fonts'].values()):
            raise StudioError('Las fuentes de rol deben estar adjuntas al proyecto.', 409)
        brand = project.get('style', {}).get('branding')
        if brand is not None:
            authoritative = _decode(read('.estado/project_branding/' + pid + '.json', limit=MAX_JSON_BYTES), 'Marca canónica')
            if brand != authoritative: raise StudioError('La marca no coincide con su binding del servidor.', 409)
            if not isinstance(brand, dict) or not isinstance(brand.get('fonts'), dict) or set(brand['fonts']) != {'primary', 'accent'}:
                raise StudioError('Descriptor de marca inválido.', 409)
            for role, face in brand['fonts'].items():
                if not isinstance(face, dict) or project['fonts'][role] not in font_rows:
                    raise StudioError('Fuente de marca inexistente.', 409)
                actual = font_rows[project['fonts'][role]]
                if face.get('asset_id') != actual['id']:
                    raise StudioError('Identidad de fuente de marca distinta.', 409)
                if any(face.get(k) != actual.get(k) for k in ('path', 'sha256')) or any(face.get(k) != actual['font_info'].get(k) for k in ('family', 'style')):
                    raise StudioError('Los bytes reales de la marca no coinciden con su descriptor.', 409)
            if brand.get('logo_asset_id') is not None and (not isinstance(brand['logo_asset_id'], str) or brand['logo_asset_id'] not in ids):
                raise StudioError('Falta el logo de marca adjunto.', 409)
            add('branding.json', 'branding', _json(portable['style']['branding']))
        # Only receipts explicitly referenced by this project are selected.
        # No recursive directory walk and no configuration/cache/model copy.
        mapping, evidence_shas = {}, {}
        def artifact(name, expected, domain):
            allowed = (domain == 'automation' and isinstance(name, str) and re.fullmatch(re.escape('projects/' + pid + '/automation/') + r'[a-f0-9]{24}/(?:plan|transcript|inference|direction)\.json', name)) or (domain == 'tracking' and isinstance(name, str) and re.fullmatch(re.escape('projects/' + pid + '/tracking/') + r'[a-f0-9]{24}/(?:measurements\.json|frame_[0-9]{4}\.jpg)', name))
            if not allowed: raise StudioError('Evidencia documental ajena al proyecto.', 403)
            if expected is not None: _identifier(expected, SHA, 'SHA de evidencia')
            data = read(name, expected)
            if name.endswith('.json'): data = _json(_portable(_decode(data, 'Evidencia documental')))
            digest = hashlib.sha256(data).hexdigest()
            logical = 'artifacts/' + domain + '/' + digest + PurePosixPath(name).suffix
            add(logical, 'artifact', data); mapping[name] = logical; evidence_shas[name] = digest
        automation = project.get('automation')
        if automation is not None:
            if not isinstance(automation, dict) or not isinstance(automation.get('artifacts', []), list): raise StudioError('Recibo de dirección inválido.')
            for entry in automation.get('artifacts', []):
                if not isinstance(entry, dict): raise StudioError('Evidencia de dirección inválida.')
                artifact(entry.get('path'), entry.get('sha256'), 'automation')
        tracking = project.get('tracking')
        if tracking is not None:
            if not isinstance(tracking, dict) or not isinstance(tracking.get('evidence', []), list): raise StudioError('Evidencia de tracking inválida.')
            if tracking.get('path') is not None: artifact(tracking['path'], tracking.get('sha256'), 'tracking')
            for entry in tracking.get('evidence', []):
                if not isinstance(entry, dict): raise StudioError('Muestra facial inválida.')
                artifact(entry.get('path'), entry.get('sha256'), 'tracking')
        def remap(value):
            if isinstance(value, str): return mapping.get(value, value)
            if isinstance(value, list): return [remap(v) for v in value]
            if isinstance(value, dict):
                result = {k: remap(v) for k, v in value.items()}
                if value.get('path') in evidence_shas:
                    result['sha256'] = evidence_shas[value['path']]
                return result
            return value
        for key in ('automation', 'tracking'):
            if key in portable: portable[key] = remap(portable[key])
        # JSON data itself is the complete editable. Existing generated outputs
        # are archival bytes, never reusable approval receipts.
        renders = project.get('renders', [])
        if not isinstance(renders, list) or any(not isinstance(r, dict) for r in renders): raise StudioError('Lista de recibos de render inválida.')
        portable['renders'] = []
        for r in renders:
            archived = _portable(r); archived.pop('path', None)
            archived.update(approved=False, editorial_approved=False, proofs_revalidation_required=True, archival_only=True)
            portable['renders'].append(archived)
        if include_outputs:
            receipts = []
            for offset, receipt in enumerate(renders[-16:]):
                if not isinstance(receipt, dict): raise StudioError('Recibo de render inválido.')
                name = receipt.get('path'); sha = receipt.get('sha256')
                if not isinstance(name, str) or not (name.startswith('projects/' + pid + '/') or name.startswith('exports/' + pid + '_')) or PurePosixPath(name).suffix.lower() != '.mp4':
                    raise StudioError('El recibo no referencia un render propio.', 403)
                data = read(name, _identifier(sha, SHA, 'SHA de render'))
                output_name = 'outputs/' + sha + '.mp4'
                add(output_name, 'artifact', data)
                archived = _portable(receipt); archived.update(path=output_name, approved=False, editorial_approved=False, proofs_revalidation_required=True)
                receipts.append(archived)
                portable['renders'][max(0, len(renders) - 16) + offset] = archived
            if receipts: add('receipts.json', 'artifact', _json(receipts))
            bundle_name = 'exports/' + pid + '_editable.zip'
            if _path(self.root, prefix + bundle_name).exists():
                data = read(bundle_name)
                data = _editable_zip(data, project, portable, source_data)
                add('editable.zip', 'artifact', data)
        add('project.json', 'project', _json(portable))
        for name, sha in captured.items():
            _cancel(cancel)
            if hashlib.sha256(_read(self.root, prefix + name, MAX_BLOB_BYTES)).hexdigest() != sha:
                raise StudioError('El proyecto cambió mientras se capturaba; no se confirma el snapshot.', 409)
        snapshot = {'schema': SNAPSHOT_SCHEMA, 'workspace_id': wid, 'project_id': pid,
                    'project_revision': project['revision'], 'project': portable, 'files': files,
                    'source_project_sha256': hashlib.sha256(raw).hexdigest(),
                    'editorial_approved': False, 'restore_requires_canonical_import': True}
        _validate_snapshot2(snapshot, wid)
        return snapshot

    def enqueue_project(self, workspace_id, project_id, expected_project_revision, expected_revision=0,
                        expected_etag=None, include_outputs=True, progress=None, cancel=None):
        """Capture a complete own project; no network and no source writes."""
        _identifier(workspace_id, WID, 'Espacio'); _identifier(project_id, PID, 'Proyecto')
        if type(include_outputs) is not bool or type(expected_revision) is not int or expected_revision < 0:
            raise StudioError('Opciones de snapshot inválidas.')
        if expected_etag is not None and (not isinstance(expected_etag, str) or not ETAG.fullmatch(expected_etag)):
            raise StudioError('ETag de snapshot inválido.')
        config = self._active(); progress = progress or (lambda fraction, message: None)
        with _project_lock(self.root, workspace_id, project_id), _workspace_lock(self.root, workspace_id):
            old = self.outbox(workspace_id, project_id) if _path(self.root, self._outbox_path(workspace_id, project_id)).exists() else None
            if (old['revision'] if old else 0) != expected_revision:
                raise StudioError('El outbox cambió antes de capturar.', 409)
            snapshot = self._complete_snapshot(workspace_id, project_id, expected_project_revision, include_outputs, progress, cancel)
            data = _json(snapshot); sha = self._cache_blob(workspace_id, data)
            _cancel(cancel)
            if self._active() != config: raise StudioError('La configuración cambió durante el snapshot.', 409)
            if old and old.get('snapshot_sha256') == sha and old.get('configuration_revision') == config['revision'] and old.get('expected_etag') == expected_etag:
                return self.outbox_status(workspace_id, project_id)
            with _lock(self.root):
                _cancel(cancel)
                if self._active() != config: raise StudioError('La configuración cambió antes de confirmar el snapshot.', 409)
                current = _read(self.root, 'workspaces/' + workspace_id + '/projects/' + project_id + '/project.json')
                if hashlib.sha256(current).hexdigest() != snapshot['source_project_sha256']:
                    raise StudioError('El proyecto cambió antes de confirmar su snapshot.', 409)
                record = {'schema': SCHEMA, 'workspace_id': workspace_id, 'project_id': project_id,
                          'revision': expected_revision + 1, 'project_revision': expected_project_revision,
                          'status': 'queued', 'snapshot_sha256': sha, 'snapshot': snapshot,
                          'expected_etag': expected_etag, 'automatic_sync': False, 'editorial_approved': False,
                          'configuration_revision': config['revision']}
                _sealed(self.root, self._outbox_path(workspace_id, project_id), record)
            progress(1, 'Snapshot completo pendiente de envío explícito')
            return self.outbox_status(workspace_id, project_id)

    def _outbox_path(self, wid, pid):
        return '.estado/cloud_storage/outbox/' + wid + '_' + pid + '.json'

    def outbox_status(self, workspace_id, project_id):
        """Safe owner-facing status: no snapshot contents, endpoints or secrets."""
        _identifier(workspace_id, WID, 'Espacio'); _identifier(project_id, PID, 'Proyecto')
        path = self._outbox_path(workspace_id, project_id)
        if not _path(self.root, path).exists():
            return {'status': 'absent', 'revision': 0, 'project_revision': None, 'pending': False,
                    'snapshot_sha256': None, 'receipt_sha256': None, 'integrity_verified': False,
                    'live_remote_execution_verified': False, 'transport': None, 'manifest_etag': None, 'editorial_approved': False}
        record = self.outbox(workspace_id, project_id)
        verified = record.get('status') == 'verified'
        receipt_sha = record.get('receipt_sha256')
        if verified:
            receipt = self._receipt(workspace_id, project_id, record)
            verified = receipt.get('integrity_verified') is True
        return {'status': record.get('status'), 'revision': record['revision'],
                'project_revision': record.get('project_revision'), 'pending': record.get('status') == 'queued',
                'snapshot_sha256': record['snapshot_sha256'], 'receipt_sha256': receipt_sha,
                'integrity_verified': verified, 'live_remote_execution_verified': bool(verified and receipt.get('live_remote_execution_verified')),
                'transport': receipt.get('transport') if verified else None, 'manifest_etag': receipt.get('etag') if verified else None, 'editorial_approved': False}

    def _receipt(self, wid, pid, record):
        sha = _identifier(record.get('receipt_sha256'), SHA, 'SHA de recibo')
        path = '.estado/cloud_storage/receipts/' + sha + '.json'
        raw = _read(self.root, path)
        if hashlib.sha256(raw).hexdigest() != record.get('receipt_sha256'):
            raise StudioError('Cambió el recibo confirmado del outbox.', 409)
        receipt = _verify_sealed(self.root, path)
        if receipt.get('snapshot_sha256') != record['snapshot_sha256'] or receipt.get('workspace_id') != wid or receipt.get('project_id') != pid or receipt.get('editorial_approved') is not False:
            raise StudioError('El recibo no corresponde al snapshot propio.', 409)
        return receipt

    def run_outbox(self, workspace_id, project_id, expected_revision, progress=None, cancel=None):
        """Explicit synchronous runner; caller supplies an authenticated owner job."""
        _identifier(workspace_id, WID, 'Espacio'); _identifier(project_id, PID, 'Proyecto')
        if type(expected_revision) is not int or expected_revision < 1: raise StudioError('Revisión de outbox inválida.')
        config = self._active(); progress = progress or (lambda fraction, message: None)
        with _project_lock(self.root, workspace_id, project_id):
            record = self.outbox(workspace_id, project_id)
            if record['revision'] != expected_revision and not (record.get('status') == 'verified' and record.get('queued_revision') == expected_revision):
                raise StudioError('El outbox cambió antes de ejecutarse.', 409)
            if record.get('configuration_revision') != config['revision']:
                raise StudioError('El outbox pertenece a otra configuración; vuelve a capturarlo.', 409)
            snapshot = record['snapshot']; _validate_snapshot2(snapshot, workspace_id)
            hashes = sorted({f['sha256'] for f in snapshot['files']} | {record['snapshot_sha256']})
            # Uploads are immutable and always followed by a complete GET SHA.
            for index, sha in enumerate(hashes):
                _cancel(cancel)
                data = _read(self.root, '.estado/cloud_storage/blobs/' + workspace_id + '/' + sha + '.blob', MAX_BLOB_BYTES)
                if hashlib.sha256(data).hexdigest() != sha: raise StudioError('Blob pendiente alterado.', 409)
                key = self._blob_key(workspace_id, sha)
                if record.get('status') != 'verified':
                    try: self._request('PUT', key, {'If-None-Match': '*', 'x-amz-meta-sha256': sha, 'Content-Type': 'application/octet-stream'}, data, expected_config=config)
                    except StudioError as error:
                        if error.status != 409 or not isinstance(error.details, dict) or error.details.get('kind') != 'remote_precondition': raise
                _cancel(cancel)
                remote = self._request('GET', key, limit=MAX_BLOB_BYTES, expected_config=config)['body']
                if remote != data: raise StudioError('El almacenamiento no devolvió todos los bytes del snapshot.', 409)
                progress(.8 * (index + 1) / len(hashes), 'Verificando objetos del snapshot')
            _cancel(cancel)
            manifest = {'schema': 'ascendia.cloud-manifest/1', 'workspace_id': workspace_id, 'project_id': project_id,
                        'revision': record['project_revision'], 'snapshot_sha256': record['snapshot_sha256'],
                        'blobs': sorted({f['sha256'] for f in snapshot['files']})}
            key = 'v1/' + workspace_id + '/projects/' + project_id + '/manifest.json'
            manifest_data = _json(manifest)
            old_receipt = self._receipt(workspace_id, project_id, record) if record.get('status') == 'verified' else None
            if old_receipt is None:
                headers = {'Content-Type': 'application/json'}
                headers['If-None-Match' if record['expected_etag'] is None else 'If-Match'] = '*' if record['expected_etag'] is None else record['expected_etag']
                try: self._request('PUT', key, headers, manifest_data, expected_config=config)
                except StudioError as error:
                    if error.status != 409 or not isinstance(error.details, dict) or error.details.get('kind') != 'remote_precondition': raise
            head = self._request('GET', key, expected_config=config)
            if head['body'] != manifest_data: raise StudioError('Conflicto de manifiesto; no se sobrescribe otra revisión.', 409)
            etag = next((v for k, v in head['headers'].items() if str(k).lower() == 'etag'), None)
            if not isinstance(etag, str) or not ETAG.fullmatch(etag): raise StudioError('Falta ETag verificable del manifiesto.', 502)
            _cancel(cancel)
            if self._active() != config: raise StudioError('La configuración cambió antes del recibo.', 409)
            if old_receipt is not None and old_receipt['etag'] == etag:
                with _lock(self.root):
                    _cancel(cancel)
                    if self._active() != config: raise StudioError('La configuración cambió antes de confirmar reutilización.', 409)
                    return {**self.outbox_status(workspace_id, project_id), 'reused': True}
            with _lock(self.root):
                _cancel(cancel)
                if self._active() != config: raise StudioError('La configuración cambió antes de confirmar el recibo.', 409)
                if self.outbox(workspace_id, project_id) != record: raise StudioError('El outbox cambió antes de confirmar el recibo.', 409)
                receipt = {'schema': 'ascendia.cloud-backup-receipt/1', 'workspace_id': workspace_id, 'project_id': project_id,
                           'snapshot_sha256': record['snapshot_sha256'], 'project_revision': record['project_revision'],
                           'manifest_sha256': hashlib.sha256(manifest_data).hexdigest(), 'etag': etag,
                           'verified_blob_sha256': hashes, 'verified_at': datetime.now(timezone.utc).isoformat(),
                           'integrity_verified': True, 'live_remote_execution_verified': self.live,
                           'transport': 'official_https' if self.live else 'injected', 'editorial_approved': False}
                receipt['seal'] = hmac.new(_key(self.root), _json(receipt), hashlib.sha256).hexdigest()
                receipt_data = _json(receipt); receipt_sha = hashlib.sha256(receipt_data).hexdigest()
                receipt_path = '.estado/cloud_storage/receipts/' + receipt_sha + '.json'
                if _path(self.root, receipt_path).exists():
                    if _read(self.root, receipt_path) != receipt_data: raise StudioError('Recibo inmutable alterado.', 409)
                else: _write(self.root, receipt_path, receipt_data)
                record.pop('seal', None); record.update(status='verified', revision=record['revision'] + 1,
                    queued_revision=record.get('queued_revision', expected_revision), receipt_sha256=receipt_sha)
                _sealed(self.root, self._outbox_path(workspace_id, project_id), record)
            progress(1, 'Integridad del snapshot comprobada; sin aprobación editorial')
            return self.outbox_status(workspace_id, project_id)

    def _blob_key(self, wid, sha):
        return 'v1/' + _identifier(wid, WID, 'Espacio') + '/blobs/' + _identifier(sha, SHA, 'SHA')

    def _source(self, wid, path, expected_sha):
        _identifier(wid, WID, 'Espacio'); _identifier(expected_sha, SHA, 'SHA')
        if not isinstance(path, (str, Path)) or not str(path): raise StudioError('Ruta de medio inválida.', 403)
        path = Path(path)
        path = path if path.is_absolute() else self.root / 'workspaces' / wid / path
        expected_root = self.root / 'workspaces' / wid / 'assets'
        if not path.is_relative_to(expected_root) or path.resolve() != path: raise StudioError('El medio debe ser canónico del workspace propio.', 403)
        relative = path.relative_to(self.root).as_posix()
        data = _read(self.root, relative, MAX_BLOB_BYTES)
        if hashlib.sha256(data).hexdigest() != expected_sha: raise StudioError('El medio cambió antes de sincronizarse.', 409)
        return relative, data

    def put_blob(self, workspace_id, path, expected_sha256):
        relative, data = self._source(workspace_id, path, expected_sha256)
        key = self._blob_key(workspace_id, expected_sha256)
        headers = {'If-None-Match': '*', 'x-amz-meta-sha256': expected_sha256, 'Content-Type': 'application/octet-stream'}
        try: reply = self._request('PUT', key, headers, data, MAX_JSON_BYTES)
        except StudioError as error:
            if error.status != 409 or not isinstance(error.details, dict) or error.details.get('kind') != 'remote_precondition': raise
            existing = self._request('GET', key, limit=MAX_BLOB_BYTES)
            if existing['body'] != data: raise StudioError('El blob remoto existente no coincide con sus bytes.', 409)
            reply = existing
        if _read(self.root, relative, MAX_BLOB_BYTES) != data: raise StudioError('La fuente cambió durante la transferencia.', 409)
        return {'workspace_id': workspace_id, 'key': key, 'sha256': expected_sha256, 'bytes': len(data),
                'acknowledged': True, 'full_remote_bytes_verified': reply['body'] == data,
                'transport': 'official_https' if self.live else 'injected', 'live_remote_execution_verified': self.live,
                'editorial_approved': False}

    def get_blob(self, workspace_id, sha256, expected_config=None):
        reply = self._request('GET', self._blob_key(workspace_id, sha256), limit=MAX_BLOB_BYTES, expected_config=expected_config)
        data = reply['body']
        if not data or hashlib.sha256(data).hexdigest() != sha256: raise StudioError('Los bytes remotos no corresponden al SHA esperado.', 409)
        relative = '.estado/cloud_storage/staging/' + workspace_id + '_' + sha256 + '.blob'
        target = _path(self.root, relative)
        if target.exists():
            if _read(self.root, relative, MAX_BLOB_BYTES) != data: raise StudioError('El staging existente cambió; no se reemplaza.', 409)
        else: _write(self.root, relative, data)
        return {'path': relative, 'sha256': sha256, 'bytes': len(data), 'applied': False,
                'transport': 'official_https' if self.live else 'injected', 'live_remote_execution_verified': self.live}

    def put_manifest(self, workspace_id, project_id, document, expected_etag=None):
        _identifier(workspace_id, WID, 'Espacio'); _identifier(project_id, PID, 'Proyecto')
        _closed(document, {'schema', 'workspace_id', 'project_id', 'revision', 'snapshot_sha256', 'blobs'})
        if document['schema'] != 'ascendia.cloud-manifest/1' or document['workspace_id'] != workspace_id or document['project_id'] != project_id or type(document['revision']) is not int or document['revision'] < 1:
            raise StudioError('El manifiesto no pertenece al proyecto.', 403)
        _identifier(document['snapshot_sha256'], SHA, 'SHA de snapshot')
        if not isinstance(document['blobs'], list) or len(document['blobs']) > MAX_FILES or any(not isinstance(sha, str) for sha in document['blobs']) or len(set(document['blobs'])) != len(document['blobs']): raise StudioError('Referencias de medios inválidas.')
        for sha in document['blobs']: _identifier(sha, SHA, 'SHA de medio')
        if expected_etag is not None and (not isinstance(expected_etag, str) or not ETAG.fullmatch(expected_etag)):
            raise StudioError('ETag de concurrencia inválido.')
        headers = {'Content-Type': 'application/json', 'If-None-Match': '*'} if expected_etag is None else {'Content-Type': 'application/json', 'If-Match': expected_etag}
        reply = self._request('PUT', 'v1/' + workspace_id + '/projects/' + project_id + '/manifest.json', headers, _json(document))
        etag = next((v for k, v in reply['headers'].items() if str(k).lower() == 'etag'), None)
        if not isinstance(etag, str) or not ETAG.fullmatch(etag): raise StudioError('Falta el ETag real del manifiesto.', 502)
        return {'etag': etag, 'revision': document['revision'], 'acknowledged': True,
                'live_remote_execution_verified': self.live, 'editorial_approved': False,
                'referenced_blobs_verified': False, 'snapshot_bytes_verified': False}

    def enqueue_snapshot(self, workspace_id, project, assets, expected_revision=0):
        """Seal a local outbox record. Does not upload, run jobs or apply edits."""
        _identifier(workspace_id, WID, 'Espacio')
        if not isinstance(project, dict): raise StudioError('Snapshot de proyecto inválido.')
        pid = _identifier(project.get('id'), PID, 'Proyecto')
        if type(project.get('revision')) is not int or project['revision'] < 1 or type(expected_revision) is not int or expected_revision < 0:
            raise StudioError('Revisión de snapshot inválida.')
        if not isinstance(assets, list) or len(assets) > 256: raise StudioError('Medios de snapshot inválidos.')
        rows, ids = [], set()
        for asset in assets:
            if not isinstance(asset, dict) or not isinstance(asset.get('id'), str) or not re.fullmatch(r'a_[A-Za-z0-9_-]{1,100}', asset['id']) or asset['id'] in ids:
                raise StudioError('Identidad de medio de snapshot inválida.')
            ids.add(asset['id']); relative, data = self._source(workspace_id, asset.get('path', ''), asset.get('sha256'))
            rows.append({'id': asset['id'], 'path': relative.split('/' + workspace_id + '/', 1)[1],
                         'sha256': asset['sha256'], 'bytes': len(data)})
        if project.get('source') not in ids: raise StudioError('El snapshot requiere su crudo entre los medios.')
        snapshot = {'schema': 'ascendia.cloud-snapshot/1', 'workspace_id': workspace_id,
                    'project': {k: copy.deepcopy(v) for k, v in project.items() if k in EDITABLE_FIELDS}, 'assets': rows}
        data = _json(snapshot); sha = hashlib.sha256(data).hexdigest()
        relative = '.estado/cloud_storage/outbox/' + workspace_id + '_' + pid + '.json'
        with _lock(self.root):
            old = self.outbox(workspace_id, pid) if _path(self.root, relative).exists() else None
            revision = old['revision'] if old else 0
            if revision != expected_revision: raise StudioError('El outbox cambió; recarga su revisión.', 409)
            record = {'schema': SCHEMA, 'workspace_id': workspace_id, 'project_id': pid, 'revision': revision + 1,
                      'status': 'queued', 'snapshot_sha256': sha, 'snapshot': snapshot,
                      'automatic_sync': False, 'editorial_approved': False}
            record['seal'] = hmac.new(_key(self.root), _json(record), hashlib.sha256).hexdigest()
            _write(self.root, relative, _json(record))
        return record

    def outbox(self, workspace_id, project_id):
        _identifier(workspace_id, WID, 'Espacio'); _identifier(project_id, PID, 'Proyecto')
        raw = _read(self.root, '.estado/cloud_storage/outbox/' + workspace_id + '_' + project_id + '.json')
        try: record = json.loads(raw)
        except (ValueError, RecursionError): raise StudioError('Outbox malformado.', 409) from None
        if not isinstance(record, dict): raise StudioError('Outbox malformado.', 409)
        seal = record.pop('seal', None)
        actual = hmac.new(_key(self.root), _json(record), hashlib.sha256).hexdigest()
        if not isinstance(seal, str) or not hmac.compare_digest(seal, actual) or record.get('workspace_id') != workspace_id or record.get('project_id') != project_id:
            raise StudioError('El sello del outbox no corresponde al proyecto.', 409)
        if hashlib.sha256(_json(record.get('snapshot'))).hexdigest() != record.get('snapshot_sha256'):
            raise StudioError('Snapshot de outbox alterado.', 409)
        return {**record, 'seal': seal}

    def stage_restore(self, workspace_id, snapshot_sha256, progress=None, cancel=None):
        """Download and verify a snapshot and its assets into private staging only."""
        _cancel(cancel)
        config = self._active()
        snapshot_file = self.get_blob(workspace_id, snapshot_sha256, expected_config=config)
        snapshot = _decode(_read(self.root, snapshot_file['path']), 'Snapshot remoto')
        if isinstance(snapshot, dict) and snapshot.get('schema') == SNAPSHOT_SCHEMA:
            return self._stage_restore_complete(workspace_id, snapshot_sha256, snapshot, progress, cancel, config)
        _closed(snapshot, {'schema', 'workspace_id', 'project', 'assets'})
        if snapshot['schema'] != 'ascendia.cloud-snapshot/1' or snapshot['workspace_id'] != workspace_id or not isinstance(snapshot['project'], dict) or set(snapshot['project']) - EDITABLE_FIELDS:
            raise StudioError('Snapshot remoto ajeno o con campos privados.', 403)
        _identifier(snapshot['project'].get('id'), PID, 'Proyecto')
        if type(snapshot['project'].get('revision')) is not int or snapshot['project']['revision'] < 1:
            raise StudioError('Revisión del proyecto restaurado inválida.')
        if not isinstance(snapshot['assets'], list) or len(snapshot['assets']) > 256: raise StudioError('Medios restaurados inválidos.')
        validated, seen, paths = [], set(), set()
        for row in snapshot['assets']:
            _closed(row, {'id', 'path', 'sha256', 'bytes'})
            if not isinstance(row['id'], str) or not re.fullmatch(r'a_[A-Za-z0-9_-]{1,100}', row['id']) or row['id'] in seen or type(row['bytes']) is not int or not 0 < row['bytes'] <= MAX_BLOB_BYTES:
                raise StudioError('Medio restaurado fuera de contrato.')
            seen.add(row['id'])
            path = PurePosixPath(row['path']) if isinstance(row['path'], str) else None
            if path is None or path.is_absolute() or row['path'] in paths or not row['path'].startswith('assets/') or '\\' in row['path'] or '%' in row['path'] or any(part in ('', '.', '..') for part in row['path'].split('/')):
                raise StudioError('Ruta restaurada fuera de biblioteca.', 403)
            paths.add(row['path'])
            _identifier(row['sha256'], SHA, 'SHA de medio'); validated.append(row)
        if snapshot['project'].get('source') not in seen: raise StudioError('Snapshot sin fuente canónica.')
        staged = []
        for row in validated:
            _cancel(cancel)
            blob = self.get_blob(workspace_id, row['sha256'], expected_config=config)
            if blob['bytes'] != row['bytes']: raise StudioError('Tamaño restaurado no coincide.', 409)
            staged.append({**row, 'staging_path': blob['path']})
        return {'project': snapshot['project'], 'assets': staged, 'snapshot_sha256': snapshot_sha256,
                'applied': False, 'editorial_approved': False, 'requires': 'canonical import, metadata/font/probe validation and project CAS by owning server',
                'live_remote_execution_verified': self.live}

    def _stage_restore_complete(self, workspace_id, sha, snapshot, progress=None, cancel=None, config=None):
        files = _validate_snapshot2(snapshot, workspace_id)
        progress = progress or (lambda fraction, message: None)
        config = self._active() if config is None else config
        directory = '.estado/cloud_storage/restores/' + workspace_id + '_' + snapshot['project_id'] + '_' + sha
        staged = []
        for index, (name, entry) in enumerate(files.items()):
            _cancel(cancel)
            data = self._request('GET', self._blob_key(workspace_id, entry['sha256']), limit=MAX_BLOB_BYTES, expected_config=config)['body']
            if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
                raise StudioError('El archivo restaurado no corresponde a su SHA/tamaño.', 409)
            relative = directory + '/' + name
            target = _path(self.root, relative)
            if target.exists():
                if _read(self.root, relative, MAX_BLOB_BYTES) != data: raise StudioError('El staging completo fue alterado; no se sobrescribe.', 409)
            else: _write(self.root, relative, data)
            staged.append({**entry, 'staging_path': relative})
            progress(.85 * (index + 1) / len(files), 'Verificando archivos restaurados')
        project = snapshot['project']
        from .fonts import inspect_font
        for asset in project['assets']:
            if asset['kind'] == 'font':
                actual = inspect_font(self.root / directory / asset['path'], self.root)
                if actual['sha256'] != asset['sha256'] or any(actual.get(k) != asset.get('font_info', {}).get(k) for k in ('family', 'style')):
                    raise StudioError('La fuente restaurada no coincide con su variante real.', 409)
            notice = asset.get('metadata', {}).get('font_notice')
            if notice is not None:
                try: _read(self.root, directory + '/' + notice['path'], 65536).decode('utf-8')
                except UnicodeDecodeError: raise StudioError('Aviso restaurado no UTF-8.') from None
        if 'editable.zip' in files:
            content = {name: _read(self.root, directory + '/' + name, MAX_BLOB_BYTES) for name, entry in files.items() if entry['role'] in ('asset', 'font_notice')}
            _editable_zip(_read(self.root, directory + '/editable.zip', MAX_BLOB_BYTES), project, project, content)
        _cancel(cancel)
        if self._active() != config: raise StudioError('La configuración cambió durante la restauración.', 409)
        for entry in staged:
            if hashlib.sha256(_read(self.root, entry['staging_path'], MAX_BLOB_BYTES)).hexdigest() != entry['sha256']:
                raise StudioError('El staging cambió durante su verificación.', 409)
        proof = {'schema': 'ascendia.cloud-restore-receipt/1', 'workspace_id': workspace_id,
                 'project_id': snapshot['project_id'], 'snapshot_sha256': sha, 'files': staged,
                 'integrity_verified': True, 'applied': False, 'editorial_approved': False,
                 'live_remote_execution_verified': self.live, 'transport': 'official_https' if self.live else 'injected',
                 'requires': 'owner canonical import, fresh validation and project CAS'}
        _sealed(self.root, directory + '/restore_receipt.json', proof)
        progress(1, 'Restauración íntegra en staging; importación y revisión pendientes')
        return {**proof, 'project': project, 'staging_root': directory}
