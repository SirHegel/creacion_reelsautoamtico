"""Portable ZIP reopen, content identity, confinement, and approval reset."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import stat
import zipfile

import pytest
from PIL import Image

from studio import analysis, bundles, cli, core, jobs, mcp, server
from test_api import api_workspace, fixture_media, real_project


@pytest.fixture
def editable(api_workspace, fixture_media):
    p = real_project(api_workspace, fixture_media)
    result = jobs.export_bundle(p["id"])
    return p, api_workspace / result["path"]


def rewrite(root, original, *, update=None, extras=None, replace=None):
    target = root / ".estado/tmp/modified.zip"
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename == "project.json" and update:
                p = json.loads(content)
                update(p)
                content = json.dumps(p).encode()
            if replace and info.filename in replace:
                content = replace[info.filename]
            output.writestr(info.filename, content)
        for name, content in extras or []:
            output.writestr(name, content)
    return target


def new_workspace(root, archive, monkeypatch):
    destination = root.parent / "REOPENED"
    destination.mkdir()
    original = core.confined
    def local_confined(path, root_override=None, must_exist=False, **kwargs):
        return original(path, root=kwargs.get("root", root_override) or destination, must_exist=must_exist)
    for module in (core, analysis, jobs, cli, mcp, server):
        if hasattr(module, "ROOT"):
            monkeypatch.setattr(module, "ROOT", destination)
        if hasattr(module, "confined"):
            monkeypatch.setattr(module, "confined", local_confined)
    monkeypatch.setattr(core, "MANUAL_ROOT", destination.parent)
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", destination / ".estado/cpu_worker.lock")
    if hasattr(server, "MANUAL_ROOT"):
        monkeypatch.setattr(server, "MANUAL_ROOT", destination.parent)
    core.setup()
    target = destination / ".estado/tmp/reopen.zip"
    shutil.copyfile(archive, target)
    return destination, target


def test_actual_export_roundtrip_into_fresh_workspace_resets_approvals(api_workspace, editable, monkeypatch):
    old, archive = editable
    old_source = old["source"]
    def foreign_ids_and_untrusted_approval(p):
        p["source"] = "foreign_original"
        p["assets"][0]["id"] = "foreign_original"
        for track in p["audio"]:
            track["asset_id"] = "foreign_original"
        p["review"] = {"approved_preview": True}
        p["renders"] = [{"path": "approved_preview.mp4", "sha256": "untrusted"}]
        p["full_authorization"] = {"authorized": True}
        p["approved_export"] = {"path": "approved_preview.mp4"}
        p["timeline"][1]["motion"] = {"value": 42, "suffix": "%"}
        p["timeline"][1]["nodes"] = ["Entrada", "Acción", "Resultado"]
        p["timeline"][1]["effects"] = {"brightness": .05, "contrast": 1.1, "saturation": .9}
    changed = rewrite(api_workspace, archive, update=foreign_ids_and_untrusted_approval,
                      extras=[("approved_preview.mp4", b"untrusted previous candidate; never promoted")])
    reopened, incoming = new_workspace(api_workspace, changed, monkeypatch)
    result = bundles.import_bundle(incoming)
    assert result["reused"] is False
    p = result["project"]
    assert p["id"] != old["id"] and p["source"] == old_source
    assert next(a for a in p["assets"] if a["id"] == p["source"])["name"] == old["assets"][0]["name"]
    assert p["review"] == {} and p["renders"] == []
    assert not p.get("full_authorization") and not p.get("approved_export")
    assert p["stage"] == "imported_review_pending"
    assert p["reference_review"]["evidence"] == []
    assert p["transcript"]["reviewed"] is False
    assert all(s["status"] == "draft" and not s["chin_reviewed"] and s["decision"]["evidence"] == [] for s in p["timeline"])
    assert p["timeline"][1]["motion"]["value"] == 42
    assert p["timeline"][1]["nodes"] == ["Entrada", "Acción", "Resultado"]
    assert p["timeline"][1]["effects"]["brightness"] == .05
    assert p["audio"][0]["asset_id"] == p["source"]
    assert result["asset_count"] == 3  # Original + two actual mandatory fonts.
    assert len(core.assets()) == 3 and len(core.project_list()) == 1
    assert all(a["verification"]["visual"] is False for a in p["assets"])
    for key in ("primary", "accent"):
        font = p["fonts"][key]
        assert (reopened / font).is_file() and not Path(font).is_absolute() and ".." not in Path(font).parts
    assert not core.validate_project(p, strict=True)["valid"]
    assert not list((reopened / ".estado/tmp").glob("bundle_*"))
    second = bundles.import_bundle(incoming)
    assert second["reused"] is True and second["project"] == p
    assert len(core.assets()) == 3 and len(core.project_list()) == 1


def test_same_source_reuses_existing_project_without_overwriting_user_edit(api_workspace, editable):
    p, archive = editable
    p["timeline"][1]["title"] = "User changed this after exporting"
    p = core.save_project(p["id"], p)
    before_assets = copy.deepcopy(core.assets())
    result = bundles.import_bundle(archive)
    assert result["reused"] is True and result["project"] == p
    assert core.get_project(p["id"])["timeline"][1]["title"] == "User changed this after exporting"
    assert core.assets() == before_assets


@pytest.mark.parametrize("member", ["../outside.txt", "/absolute.txt", ".estado/credentials.json",
                                   "assets/video/../other.mp4", "assets//video/alias.mp4", "C:/absolute.mp4",
                                   "assets\\video\\clip.mp4", "unrelated.json"])
def test_zip_slip_private_and_irrelevant_members_rejected_without_mutation(api_workspace, editable, member):
    p, archive = editable
    bad = rewrite(api_workspace, archive, extras=[(member, b"fixture payload")])
    before = copy.deepcopy(core.assets())
    with pytest.raises(core.StudioError):
        bundles.import_bundle(bad)
    assert core.assets() == before and core.get_project(p["id"]) == p
    assert not (api_workspace.parent / "outside.txt").exists()
    assert not list((api_workspace / ".estado/tmp").glob("bundle_*"))


def test_duplicate_zip_member_and_unix_symlink_rejected(api_workspace, editable):
    p, archive = editable
    with pytest.warns(UserWarning, match="Duplicate name"):
        duplicate = rewrite(api_workspace, archive, extras=[("project.json", b"{}")])
    with pytest.raises(core.StudioError, match="repetidos"):
        bundles.import_bundle(duplicate)
    target = api_workspace / ".estado/tmp/symlink.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(target, "w") as output:
        for info in source.infolist():
            output.writestr(info.filename, source.read(info.filename))
        link = zipfile.ZipInfo("assets/video/link.mp4")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(link, "../../outside.mp4")
    with pytest.raises(core.StudioError, match="enlaces"):
        bundles.import_bundle(target)
    assert core.get_project(p["id"]) == p


def test_compression_bomb_rejected_before_project_parse(api_workspace):
    path = api_workspace / ".estado/tmp/bomb.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("project.json", b" " * (2 * 1024 ** 2))
    with pytest.raises(core.StudioError, match="compresión") as error:
        bundles.import_bundle(path)
    assert error.value.status == 413 and core.assets() == [] and core.project_list() == []


def test_size_budget_and_member_limit_rejected(api_workspace, editable, monkeypatch):
    _, archive = editable
    monkeypatch.setattr(bundles, "MAX_MEMBERS", 1)
    with pytest.raises(core.StudioError):
        bundles.import_bundle(archive)
    monkeypatch.setattr(bundles, "MAX_MEMBERS", 5000)
    monkeypatch.setattr(bundles, "MAX_BYTES", archive.stat().st_size + 1)
    with pytest.raises(core.StudioError, match="4 GiB"):
        bundles.import_bundle(archive)


@pytest.mark.parametrize("change", ["missing_hash", "wrong_hash", "missing_asset", "private_font", "invalid_motion", "wrong_source"])
def test_invalid_project_references_and_hashes_do_not_register_resources(api_workspace, editable, monkeypatch, change):
    _, archive = editable
    def update(p):
        if change == "missing_hash":
            p["assets"][0].pop("sha256")
        elif change == "wrong_hash":
            p["assets"][0]["sha256"] = "0" * 64
        elif change == "missing_asset":
            p["assets"][0]["path"] = "assets/video/absent.mp4"
        elif change == "private_font":
            p["fonts"]["primary"] = ".estado/tmp/font.ttf"
        elif change == "invalid_motion":
            p["timeline"][0]["start"] = -1
        elif change == "wrong_source":
            p["source"] = "absent"
    changed = rewrite(api_workspace, archive, update=update)
    reopened, incoming = new_workspace(api_workspace, changed, monkeypatch)
    with pytest.raises(core.StudioError):
        bundles.import_bundle(incoming)
    assert core.assets() == [] and core.project_list() == []
    assert not list((reopened / ".estado/tmp").glob("bundle_*"))


def test_archive_and_font_identity_are_verified(api_workspace, editable, monkeypatch):
    p, archive = editable
    invalid = api_workspace / ".estado/tmp/not_a_zip.zip"
    invalid.write_bytes(b"not a ZIP")
    with pytest.raises(core.StudioError):
        bundles.import_bundle(invalid)
    changed = rewrite(api_workspace, archive,
                      replace={p["fonts"]["primary"]: (api_workspace / p["fonts"]["accent"]).read_bytes()})
    _, incoming = new_workspace(api_workspace, changed, monkeypatch)
    with pytest.raises(core.StudioError, match="Sequel/Scholar"):
        bundles.import_bundle(incoming)
    assert core.assets() == [] and core.project_list() == []


def test_bundle_input_path_cannot_leave_software(api_workspace, editable):
    _, archive = editable
    outside = api_workspace.parent / "outside.zip"
    shutil.copyfile(archive, outside)
    (api_workspace / "escape.zip").symlink_to(outside)
    for path in (outside, "../outside.zip", "escape.zip"):
        with pytest.raises(core.StudioError) as error:
            bundles.import_bundle(path)
        assert error.value.status == 403


def test_empty_project_roundtrip_remains_editable_without_an_approval(api_workspace, monkeypatch):
    p = core.create_project("Empty draft")
    archive = api_workspace / jobs.export_bundle(p["id"])["path"]
    _, incoming = new_workspace(api_workspace, archive, monkeypatch)
    imported = bundles.import_bundle(incoming)
    assert imported["reused"] is False
    assert imported["project"]["source"] is None and imported["project"]["timeline"] == []
    assert imported["project"]["review"] == {} and imported["asset_count"] == 2


def test_drive_identity_collision_preserves_the_canonical_original(api_workspace, editable):
    p, archive = editable
    p["drive_id"] = "fixture_drive_id"
    p = core.save_project(p["id"], p)
    original = p["assets"][0]
    altered_bytes = (api_workspace / original["path"]).read_bytes() + b"fixture"
    def update(imported):
        imported["drive_id"] = p["drive_id"]
        imported["assets"][0]["size"] = len(altered_bytes)
        imported["assets"][0]["sha256"] = hashlib.sha256(altered_bytes).hexdigest()
    changed = rewrite(api_workspace, archive, update=update, replace={original["path"]: altered_bytes})
    before = copy.deepcopy(core.assets())
    with pytest.raises(core.StudioError, match="otro original") as error:
        bundles.import_bundle(changed)
    assert error.value.status == 409
    assert core.assets() == before and core.get_project(p["id"]) == p
    assert core.digest(api_workspace / original["path"]) == original["sha256"]


def test_changed_local_canonical_original_is_not_silently_overwritten(api_workspace, editable):
    p, archive = editable
    original = api_workspace / p["assets"][0]["path"]
    original.write_bytes(b"User changed local bytes; preserve them")
    with pytest.raises(core.StudioError, match="canónico cambió") as error:
        bundles.import_bundle(archive)
    assert error.value.status == 409
    assert original.read_bytes() == b"User changed local bytes; preserve them"
    assert core.get_project(p["id"]) == p


def test_layer_asset_ids_and_evidence_roundtrip_into_fresh_installation(api_workspace, editable, monkeypatch):
    p, _ = editable
    picture = api_workspace / "assets/images/layer_fixture.png"
    Image.new("RGBA", (32, 16), (240, 20, 40, 128)).save(picture)
    asset = core.register_asset(picture, kind="image")
    p["assets"].append(asset)
    p["timeline"][1]["overlays"] = [{"id": "overlay", "asset_id": asset["id"], "start": 0., "end": 1.,
        "source_in": 0., "x": .1, "y": .1, "width": .5, "height": .3, "opacity": .8, "blend": "screen",
        "keyframes": [{"time": 0., "x": 0.}, {"time": 1., "x": .2}],
        "decision": {"search": "Synthetic layer fixture", "reason": "Tests portable layer IDs", "evidence": [".estado/tmp/observations.txt"]}}]
    p = core.save_project(p["id"], p)
    archive = api_workspace / jobs.export_bundle(p["id"])["path"]
    def foreign_id(exported):
        next(a for a in exported["assets"] if a["id"] == asset["id"])["id"] = "foreign_layer_asset"
        exported["timeline"][1]["overlays"][0]["asset_id"] = "foreign_layer_asset"
    changed = rewrite(api_workspace, archive, update=foreign_id)
    _, incoming = new_workspace(api_workspace, changed, monkeypatch)
    result = bundles.import_bundle(incoming)
    layer = result["project"]["timeline"][1]["overlays"][0]
    assert layer["asset_id"] == asset["id"]
    assert layer["decision"]["evidence"] == [] and layer["decision"]["verification"] == "pending_reinspection"
    assert layer["blend"] == "screen" and layer["opacity"] == .8 and layer["keyframes"][1]["x"] == .2
    assert (core.ROOT / next(a for a in result["project"]["assets"] if a["id"] == layer["asset_id"])["path"]).is_file()
