"""ZIP transport guards; browser execution is tested in test_hyperframes.

These byte fixtures deliberately mock only the external execution verifier.
They neither assert a browser execution nor approve a project.
"""
import copy
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from studio import hyperframes as hf, motion_bundle as mb
from studio.core import StudioError


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(hf.ROOT / ".estado")
    root = tmp_path / "workspace"
    directory = root / ".estado/hyperframes/run_fixture"
    directory.mkdir(parents=True)
    contents = {
        "index.html": b'<div data-composition-src="compositions/scene_0.html"></div>',
        "hyperframes.json": b'{"entry":"index.html"}',
        "compositions/scene_0.html": b'<img src="../media/' + b"a" * 64 + b'.m4v">',
        "fonts/primary.ttf": b"transport-only-primary-font",
        "fonts/accent.ttf": b"transport-only-accent-font",
        "runtime/gsap.min.js": b"/* GSAP fixture, separate license */",
        "runtime/MotionPathPlugin.min.js": b"/* plugin transport fixture */",
        "runtime/third_party.json": b'{"license":"Standard no charge"}',
        "media/" + "a" * 64 + ".m4v": b"transport-only-video-bytes",
        "captions/scene_0_0.png": b"transport-only-caption-bytes",
    }
    files = []
    for name, data in contents.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        files.append({"path": path.relative_to(root).as_posix(),
                      "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {"directory": directory.relative_to(root).as_posix(), "files": files}
    build = directory / "build.json"
    build.write_text(json.dumps(manifest))
    receipt = {"sha256": "f" * 64, "technical": {"hyperframes": {
        "build_path": build.relative_to(root).as_posix(), "proof_files": copy.deepcopy(files),
        "cli_version": "0.8.147", "gsap_version": "3.15.0", "static_only": False}}}
    monkeypatch.setattr(hf, "verify_receipt", lambda receipt, root: True)
    return root, directory, manifest, receipt, contents


def update_manifest(directory, manifest):
    (directory / "build.json").write_text(json.dumps(manifest))


def test_portable_zip_contains_verified_sources_and_separate_license(bundle):
    root, _, _, receipt, contents = bundle
    result = mb.write_bundle(receipt, root, root / ".estado/tmp/editable.zip")
    destination = root / result["path"]
    assert result["sha256"] == hashlib.sha256(destination.read_bytes()).hexdigest()
    assert result["file_count"] == len(contents) + 2
    assert result["uncompressed_bytes"] == sum(map(len, contents.values()))
    assert result["editorial_approved"] is False
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == set(contents) | {"README.md", "bundle_manifest.json"}
        assert all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist())
        for name, data in contents.items():
            assert archive.read(name) == data
        metadata = json.loads(archive.read("bundle_manifest.json"))
        assert metadata["editorial_approved"] is False and metadata["render_sha256"] == receipt["sha256"]
        for entry in metadata["files"]:
            assert entry["sha256"] == hashlib.sha256(archive.read(entry["path"])).hexdigest()
            assert not Path(entry["path"]).is_absolute() and ".estado" not in entry["path"]
        readme = archive.read("README.md").decode()
        assert "Standard 'no charge'" in readme and "narración original" in readme
        assert "aprobación explícita" in readme and "permiso" in readme
    assert not list(destination.parent.glob("motion_*.tmp"))


@pytest.mark.parametrize("extension", [".m4v", ".mts", ".m2ts", ".ts", ".3gp", ".3g2", ".gif", ".flv", ".wmv", ".ogv"])
def test_all_registered_transport_extensions_are_portable(extension):
    assert mb._allowed(Path("media") / ("b" * 64 + extension))
    assert not mb._allowed(Path("media") / ("b" * 64 + ".mp3"))


def test_unverified_execution_cannot_be_packaged(bundle, monkeypatch):
    root, _, _, receipt, _ = bundle
    monkeypatch.setattr(hf, "verify_receipt", lambda receipt, root: False)
    with pytest.raises(StudioError, match="evidencia HyperFrames"):
        mb.write_bundle(receipt, root, root / ".estado/tmp/editable.zip")
    assert not (root / ".estado/tmp/editable.zip").exists()


@pytest.mark.parametrize("name", ["assets/editable.zip", ".estado/hyperframes/editable.zip", ".estado/tmp/editable.mp4", "../outside.zip"])
def test_destination_is_confined_to_new_temporary_zip(bundle, name):
    root, _, _, receipt, _ = bundle
    with pytest.raises(StudioError):
        mb.write_bundle(receipt, root, root / name)


def test_existing_destination_and_symlink_are_preserved(bundle):
    root, _, _, receipt, _ = bundle
    destination = root / ".estado/tmp/editable.zip"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing-user-content")
    with pytest.raises(StudioError, match="existentes"):
        mb.write_bundle(receipt, root, destination)
    assert destination.read_bytes() == b"existing-user-content"
    alias = destination.with_name("alias.zip")
    alias.symlink_to(destination)
    with pytest.raises(StudioError, match="simbólicos"):
        mb.write_bundle(receipt, root, alias)
    assert destination.read_bytes() == b"existing-user-content"


@pytest.mark.parametrize("mutation", ["hash", "proof", "missing", "duplicate", "private", "outside", "alias", "symlink"])
def test_broken_or_private_sources_cannot_escape_the_portable_manifest(bundle, mutation):
    root, directory, manifest, receipt, _ = bundle
    item = manifest["files"][-1]
    if mutation == "hash":
        (root / item["path"]).write_bytes(b"changed-after-render")
    elif mutation == "proof":
        receipt["technical"]["hyperframes"]["proof_files"] = []
    elif mutation == "missing":
        manifest["files"] = [entry for entry in manifest["files"] if not entry["path"].endswith("primary.ttf")]
    elif mutation == "duplicate":
        manifest["files"].append(copy.deepcopy(item))
    elif mutation in {"private", "outside", "alias", "symlink"}:
        if mutation == "private":
            path = directory / "browser_profile.json"
            path.write_bytes(b"never-export-private-settings")
        elif mutation == "outside":
            path = root / "private.json"
            path.write_bytes(b"never-export-outside-composition")
        elif mutation == "alias":
            path = directory / "compositions/../index.html"
        else:
            target = directory / "media" / ("a" * 64 + ".m4v")
            path = directory / "media" / ("c" * 64 + ".m4v")
            path.symlink_to(target)
        entry = {"path": path.relative_to(root).as_posix(), "sha256": hf._sha(path)}
        manifest["files"].append(entry)
        receipt["technical"]["hyperframes"]["proof_files"].append(copy.deepcopy(entry))
    update_manifest(directory, manifest)
    with pytest.raises(StudioError):
        mb.write_bundle(receipt, root, root / ".estado/tmp/editable.zip")
    assert not (root / ".estado/tmp/editable.zip").exists()
    assert not list((root / ".estado/tmp").glob("motion_*.tmp"))


@pytest.mark.parametrize("quota", ["bytes", "files"])
def test_manifest_quotas_reject_before_creating_zip(bundle, monkeypatch, quota):
    root, _, _, receipt, _ = bundle
    monkeypatch.setattr(mb, "MAX_BYTES" if quota == "bytes" else "MAX_FILES", 1)
    with pytest.raises(StudioError):
        mb.write_bundle(receipt, root, root / ".estado/tmp/editable.zip")
    assert not (root / ".estado/tmp").exists()


def test_receipt_change_during_packaging_leaves_no_deliverable(bundle, monkeypatch):
    root, _, _, receipt, _ = bundle
    checks = iter([True, False])
    monkeypatch.setattr(hf, "verify_receipt", lambda receipt, root: next(checks))
    with pytest.raises(StudioError, match="dejó de ser actual"):
        mb.write_bundle(receipt, root, root / ".estado/tmp/editable.zip")
    assert not (root / ".estado/tmp/editable.zip").exists()
    assert not list((root / ".estado/tmp").glob("motion_*.tmp"))


def test_atomic_commit_preserves_newly_appeared_destination(bundle, monkeypatch):
    root, _, _, receipt, _ = bundle
    destination = root / ".estado/tmp/editable.zip"

    def concurrent_destination(source, target):
        Path(target).write_bytes(b"concurrent-user-content")
        raise FileExistsError(target)

    monkeypatch.setattr(mb.os, "link", concurrent_destination)
    with pytest.raises(StudioError, match="apareció"):
        mb.write_bundle(receipt, root, destination)
    assert destination.read_bytes() == b"concurrent-user-content"
    assert not list(destination.parent.glob("motion_*.tmp"))
