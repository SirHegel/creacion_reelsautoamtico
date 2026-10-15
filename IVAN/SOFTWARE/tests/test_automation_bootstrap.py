"""Offline tracking bootstrap: real installed bytes, no browser or inference."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from studio import automation, core, jobs, tracking


REAL_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def private_root(tmp_path, monkeypatch):
    assert tmp_path.is_relative_to(REAL_ROOT / '.estado/tmp')
    if not shutil.which('google-chrome') and not shutil.which('chromium'):
        pytest.skip('Optional local Chrome/Chromium is required by tracking runtime validation')
    root = tmp_path / 'private'
    root.mkdir()
    monkeypatch.setattr(core, 'ROOT', root)
    monkeypatch.setattr(jobs, 'ROOT', root)
    monkeypatch.setattr(jobs, 'SHARED_CPU_LOCK', root / '.estado/cpu_worker.lock')
    return root


def public_fixture(tmp_path, monkeypatch, large=False):
    root = tmp_path / 'public'
    directory = root / tracking.RUNTIME
    directory.mkdir(parents=True)
    files = {}
    for name in ('vision_bundle.mjs', 'face_landmarker.task', 'face_detector.tflite',
                 'wasm/vision_wasm_internal.js', 'wasm/vision_wasm_internal.wasm'):
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(('offline unit runtime ' + name).encode())
        if large and name == 'face_landmarker.task':
            with path.open('r+b') as stream:
                stream.truncate(64 * 1024 ** 2 + 1)
        files[name] = core.digest(path)
    manifest = {'runtime_version': 'unit-fixture', 'files': files,
                'inference_executed': False}
    (directory / 'provenance.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(automation, 'CODE_ROOT', root)
    return root, directory, manifest


def test_actual_43mb_public_runtime_clones_all_verified_files_and_reuses(private_root, monkeypatch):
    root = private_root
    source = REAL_ROOT / tracking.RUNTIME
    required = ('provenance.json', 'vision_bundle.mjs', 'face_landmarker.task', 'face_detector.tflite',
                'wasm/vision_wasm_internal.js', 'wasm/vision_wasm_internal.wasm')
    missing = [name for name in required if not (source / name).is_file()]
    if missing:
        pytest.skip('Optional installed local tracking model/runtime is not bundled with public sources: '+', '.join(missing))
    manifest = tracking._runtime(REAL_ROOT)
    hashes = {'provenance.json': core.digest(source / 'provenance.json'), **manifest['files']}
    total = sum((source / name).stat().st_size for name in hashes)
    assert len(manifest['files']) == 10
    assert 32 * 1024 ** 2 < total <= automation.MAX_TRACKING_RUNTIME_BYTES == 64 * 1024 ** 2
    monkeypatch.setattr(automation, 'CODE_ROOT', REAL_ROOT)
    with jobs.cpu_slot():
        automation._tracking_runtime(root)
    copied = root / tracking.RUNTIME
    assert {path.relative_to(copied).as_posix() for path in copied.rglob('*') if path.is_file()} == set(hashes)
    assert all(core.digest(copied / name) == expected == core.digest(source / name)
               for name, expected in hashes.items())
    before = {name: (copied / name).stat().st_mtime_ns for name in hashes}
    monkeypatch.setattr(automation, 'CODE_ROOT', root / 'absent_public_cache')
    automation._tracking_runtime(root)
    assert before == {name: (copied / name).stat().st_mtime_ns for name in hashes}
    assert tracking.capability(root)['available'] is True


def test_bootstrap_rejects_verified_runtime_over_64mib_before_copy(private_root, tmp_path, monkeypatch):
    public_fixture(tmp_path, monkeypatch, large=True)
    with pytest.raises(core.StudioError, match='64MiB'):
        automation._tracking_runtime(private_root)
    assert not (private_root / tracking.RUNTIME).exists()


@pytest.mark.parametrize('change', ['missing', 'hash', 'escape'])
def test_bootstrap_rejects_incomplete_changed_or_external_public_files(private_root, tmp_path, monkeypatch, change):
    _, directory, manifest = public_fixture(tmp_path, monkeypatch)
    path = directory / 'face_landmarker.task'
    if change == 'missing':
        path.unlink()
    elif change == 'hash':
        path.write_bytes(b'changed public model')
    else:
        outside = tmp_path / 'unrelated.task'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
    with pytest.raises(core.StudioError):
        automation._tracking_runtime(private_root)
    assert not (private_root / tracking.RUNTIME).exists()


def test_bootstrap_detects_source_change_after_public_validation(private_root, tmp_path, monkeypatch):
    public, directory, _ = public_fixture(tmp_path, monkeypatch)
    original = tracking._runtime

    def changing_runtime(root):
        result = original(root)
        if root == public:
            (directory / 'vision_bundle.mjs').write_bytes(b'changed after proof')
        return result

    monkeypatch.setattr(tracking, '_runtime', changing_runtime)
    with pytest.raises(core.StudioError, match='Cambió el runtime'):
        automation._tracking_runtime(private_root)
    assert tracking.capability(private_root)['available'] is False


def test_bootstrap_detects_source_change_between_hash_and_copy(private_root, tmp_path, monkeypatch):
    _, directory, _ = public_fixture(tmp_path, monkeypatch)
    original = Path.read_bytes
    source = directory / 'vision_bundle.mjs'
    reads = 0

    def change_after_check(path):
        nonlocal reads
        value = original(path)
        if path == source:
            reads += 1
            if reads == 1:
                source.write_bytes(b'mutated between validation and copying')
        return value

    monkeypatch.setattr(Path, 'read_bytes', change_after_check)
    with pytest.raises(core.StudioError):
        automation._tracking_runtime(private_root)
    assert reads >= 2 and tracking.capability(private_root)['available'] is False


def test_bootstrap_never_overwrites_an_existing_private_model(private_root, tmp_path, monkeypatch):
    public_fixture(tmp_path, monkeypatch)
    private = private_root / tracking.RUNTIME / 'face_landmarker.task'
    private.parent.mkdir(parents=True)
    private.write_bytes(b'private altered model to preserve')
    before = hashlib.sha256(private.read_bytes()).hexdigest()
    with pytest.raises(core.StudioError, match='no se reemplaza'):
        automation._tracking_runtime(private_root)
    assert core.digest(private) == before
