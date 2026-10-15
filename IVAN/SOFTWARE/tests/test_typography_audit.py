"""Independent hostile-input audit; private fonts, no renders or production edits.

Run with python3 -B -m pytest -p no:cacheprovider and --basetemp inside
SOFTWARE/.estado/tmp. Parser/layout tests use real font bytes; HTTP/CPU boundary
tests call the handlers with an isolated fixture store and never a live server.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zipfile

from PIL import ImageFont
import pytest

from studio import bundles, core, fonts, jobs, server, typography as typo
from studio import motion_bundle as motion_zip
from test_api import api_workspace
from test_bundles import new_workspace, rewrite
from test_motion_bundle import bundle


SOFTWARE = Path(__file__).resolve().parents[1]
FONT_FIXTURES = {
    "Anton-Regular.ttf": ("a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab", ".ttf"),
    "IBMPlexMono-Regular.ttf": ("6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46", ".ttf"),
    "Anton-OFL.txt": ("ee67e6ee22790b7929f1a3769ca2801d565c64b5a9096942c1adf5596de9c9e4", ".txt"),
}


def font_fixture(name):
    expected, suffix = FONT_FIXTURES[name]
    relative = "assets/fonts/licenses/" + expected[:24] + suffix if suffix == ".txt" else "assets/fonts/" + expected[:20] + suffix
    path = SOFTWARE / relative
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text_element(**changes):
    return {"id": "audit_text", "type": "text", "text": "Texto auditable",
            "font": "primary", "font_size": 84, "x": .05, "y": .1,
            "width": .8, "height": .35, "start": 0, "end": 2,
            "color": "#ffffff", **changes}


@pytest.fixture
def audit_workspace(api_workspace, monkeypatch):
    """Only actual licensed copies in a temporary SOFTWARE-owned store."""
    assert api_workspace.resolve().is_relative_to(SOFTWARE / ".estado/tmp")
    for key in ("TMPDIR", "XDG_CACHE_HOME", "HF_HOME", "TORCH_HOME", "MPLCONFIGDIR"):
        monkeypatch.setenv(key, str(api_workspace / ".estado/tmp"))
    fonts._inspect.cache_clear()
    typo._coverage.cache_clear()
    yield api_workspace
    fonts._inspect.cache_clear()
    typo._coverage.cache_clear()


@pytest.fixture
def font_asset(audit_workspace):
    raw = font_fixture("Anton-Regular.ttf")
    notice_source = font_fixture("Anton-OFL.txt")
    assert raw.is_file() and notice_source.is_file(), "Read-only authorized font pack required"
    incoming = audit_workspace / ".estado/tmp/owned-font.ttf"
    shutil.copyfile(raw, incoming)
    content = notice_source.read_bytes()
    relative = "assets/fonts/licenses/" + sha(content)[:24] + ".txt"
    destination = audit_workspace / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return core.register_asset(incoming, metadata={"font_notice": {
        "path": relative, "sha256": sha(content), "license": "OFL-1.1",
        "source_status": "bundled_notice_unverified"}})


def font_project(root, item):
    project = core.create_project("Private typography security fixture")
    project["assets"] = [copy.deepcopy(item)]
    project["timeline"] = [{"id": "audit_motion", "type": "motion", "template": "custom",
                             "start": 0, "end": 2, "motion_design": {
                                 "elements": [text_element(font_asset_id=item["id"])]}}]
    project["audio"] = []
    return core.save_project(project["id"], project)


def sfnt_records(data):
    count = struct.unpack_from(">H", data, 4)[0]
    return {struct.unpack_from(">4s", data, 12 + index * 16)[0]:
            (12 + index * 16, *struct.unpack_from(">II", data, 20 + index * 16))
            for index in range(count)}


@pytest.mark.parametrize("case", ["short", "woff", "ttc", "zero_tables", "huge_tables",
                                 "truncated_directory", "offset_into_directory", "past_end", "duplicate"])
def test_sfnt_hostile_directory_rejected_before_native_decode(audit_workspace, monkeypatch, case):
    body = bytearray(font_fixture("Anton-Regular.ttf").read_bytes())
    if case == "short":
        body = body[:9]
    elif case in {"woff", "ttc"}:
        body[:4] = b"wOFF" if case == "woff" else b"ttcf"
    elif case in {"zero_tables", "huge_tables"}:
        struct.pack_into(">H", body, 4, 0 if case == "zero_tables" else 257)
    elif case == "truncated_directory":
        body = body[:15]
    elif case == "offset_into_directory":
        struct.pack_into(">I", body, 20, 12)
    elif case == "past_end":
        struct.pack_into(">I", body, 24, 0xFFFFFFFF)
    else:
        body[28:32] = body[12:16]
    target = audit_workspace / ".estado/tmp/hostile.ttf"
    target.write_bytes(body)
    monkeypatch.setattr(ImageFont, "truetype", lambda *a, **k: pytest.fail("Rejected SFNT reached native decoder"))
    with pytest.raises(core.StudioError):
        fonts.inspect_font(target)


@pytest.mark.parametrize("case", ["too_many", "truncated_records", "string_storage", "name_past_end"])
def test_hostile_name_offsets_are_bounded(case):
    table = bytearray(struct.pack(">HHH", 0, 1, 18) + struct.pack(">6H", 3, 1, 0x409, 1, 2, 0) + b"\x00A")
    if case == "too_many":
        struct.pack_into(">H", table, 2, 2049)
    elif case == "truncated_records":
        table = table[:10]
    elif case == "string_storage":
        struct.pack_into(">H", table, 4, 65535)
    else:
        struct.pack_into(">H", table, 14, 65535)
    with pytest.raises(core.StudioError):
        fonts._names(bytes(table))


def test_font_size_cap_is_enforced_before_decode(audit_workspace, monkeypatch):
    target = audit_workspace / ".estado/tmp/oversized.ttf"
    shutil.copyfile(font_fixture("Anton-Regular.ttf"), target)
    monkeypatch.setattr(fonts, "MAX_FONT_BYTES", 100)
    monkeypatch.setattr(ImageFont, "truetype", lambda *a, **k: pytest.fail("Oversized font reached native decoder"))
    with pytest.raises(core.StudioError) as error:
        fonts.inspect_font(target)
    assert error.value.status == 413


def test_font_symlink_cannot_read_other_fixture_directory(audit_workspace):
    external = audit_workspace.parent / "external.ttf"
    shutil.copyfile(font_fixture("Anton-Regular.ttf"), external)
    link = audit_workspace / "assets/fonts/escape.ttf"
    link.symlink_to(external)
    with pytest.raises(core.StudioError) as error:
        fonts.inspect_font(link)
    assert error.value.status == 403


def test_cached_inspection_does_not_return_stale_sha_after_signature_capture(audit_workspace, font_asset, monkeypatch):
    path = audit_workspace / font_asset["path"]
    fonts.inspect_font(path)
    signature = fonts._signature
    changed = False
    def capture_then_change(candidate):
        nonlocal changed
        result = signature(candidate)
        if not changed and Path(candidate) == path:
            changed = True
            path.write_bytes(path.read_bytes() + b"cache-hit-race")
        return result
    monkeypatch.setattr(fonts, "_signature", capture_then_change)
    with pytest.raises(core.StudioError) as error:
        fonts.validate_asset_font(font_asset)
    assert error.value.status == 409


def test_actual_font_hash_overrides_forged_cached_metadata(audit_workspace, font_asset):
    path = audit_workspace / font_asset["path"]
    old = fonts.inspect_font(path)
    forged = copy.deepcopy(font_asset)
    forged["font_info"] = old
    path.write_bytes(path.read_bytes() + b"different valid trailing bytes")
    with pytest.raises(core.StudioError, match="cambió"):
        fonts.validate_asset_font(forged)


def test_layout_detects_font_change_between_proof_and_measurement(audit_workspace, font_asset, monkeypatch):
    path = audit_workspace / font_asset["path"]
    supported = typo._supported
    def swap_after_supported(value, candidate):
        supported(value, candidate)
        shutil.copyfile(font_fixture("IBMPlexMono-Regular.ttf"), path)
    monkeypatch.setattr(typo, "_supported", swap_after_supported)
    with pytest.raises(core.StudioError) as error:
        typo.layout_element(text_element(font_asset_id=font_asset["id"]), (360, 640),
                            core.fonts(), {font_asset["id"]: font_asset}, root=audit_workspace)
    assert error.value.status == 409


@pytest.mark.parametrize("case", ["count_huge", "first_offset", "last_offset", "short_subtable"])
def test_malformed_cmap_is_a_studio_error_not_python_exception(audit_workspace, case):
    body = bytearray(font_fixture("Anton-Regular.ttf").read_bytes())
    _, offset, _ = sfnt_records(body)[b"cmap"]
    count = struct.unpack_from(">H", body, offset + 2)[0]
    if case == "count_huge":
        struct.pack_into(">H", body, offset + 2, 65535)
    elif case in {"first_offset", "last_offset"}:
        record = 0 if case == "first_offset" else count - 1
        struct.pack_into(">I", body, offset + 8 + record * 8, 0xFFFFFFFF)
    else:
        subtable = struct.unpack_from(">I", body, offset + 8)[0]
        struct.pack_into(">H", body, offset + subtable + 2, 4)
    path = audit_workspace / "assets/fonts/bad-cmap.ttf"
    path.write_bytes(body)
    # FreeType may accept the face while the higher-level cmap parser rejects it.
    with pytest.raises(core.StudioError):
        typo.layout_element(text_element(text="Árbol"), (360, 640), {"primary": str(path)}, root=audit_workspace)


def test_unknown_unicode_has_no_system_fallback_or_blank_success(audit_workspace, font_asset):
    with pytest.raises(core.StudioError, match="U\\+10FFFF"):
        typo.layout_element(text_element(text="\U0010ffff", font_asset_id=font_asset["id"]),
                            (360, 640), core.fonts(), {font_asset["id"]: font_asset}, root=audit_workspace)


def test_negative_tracking_does_not_claim_unclipped_layout(audit_workspace, font_asset):
    with pytest.raises(core.StudioError, match="avances|espaciado"):
        typo.layout_element(text_element(text="AAAAAA", font_size=8, width=.2,
                            font_asset_id=font_asset["id"], text_style={
                                "letter_spacing": -16, "shadow": {"enabled": False}}),
                            (1080, 1920), core.fonts(), {font_asset["id"]: font_asset}, root=audit_workspace)


def test_font_directory_symlink_cannot_launder_private_fonts(audit_workspace):
    ordinary = audit_workspace / "assets/fonts"
    private = audit_workspace / ".estado/private_fonts"
    ordinary.rename(private)
    ordinary.symlink_to(private, target_is_directory=True)
    with pytest.raises(core.StudioError) as error:
        core.font_path("assets/fonts/Sequel_Sans_Bold_Disp.ttf")
    assert error.value.status == 403
    with pytest.raises(core.StudioError):
        typo.resolve_font(text_element(), core.fonts(), root=audit_workspace)
    assert (private / "Sequel_Sans_Bold_Disp.ttf").is_file()


def test_directory_replacing_notice_does_not_create_catalog_500(audit_workspace, font_asset):
    notice = fonts.notice_file(font_asset)
    notice.unlink()
    notice.mkdir()
    result = fonts.license_info(font_asset)
    assert result["status"] == "supplied_by_user_unverified"
    assert result["notice_path"] is None


def test_font_path_substitution_is_ignored_in_descriptor(audit_workspace, font_asset):
    el = text_element(font_asset_id=font_asset["id"], font_path="/etc/shadow", font_family="Arial")
    result = typo.resolve_font(el, core.fonts(), {font_asset["id"]: font_asset}, audit_workspace)
    assert result["path"] == str(audit_workspace / font_asset["path"])
    assert result["family"] == fonts.inspect_font(audit_workspace / font_asset["path"])["family"]
    assert result["synthetic_style"] is False


def test_imported_license_claim_does_not_become_source_verified(audit_workspace, font_asset):
    font_asset["metadata"]["font_notice"].update(source_status="source_verified", rights_verified=True)
    font_asset["metadata"]["license"] = {"status": "source_verified", "rights_verified": True}
    result = fonts.license_info(font_asset)
    assert result["status"] == "bundled_notice_unverified"
    assert result["source_url"] is None


@pytest.mark.parametrize("metadata", [None, [], "OFL", 7, True])
def test_malformed_notice_metadata_has_no_success_or_500(audit_workspace, metadata):
    result = fonts.license_info({"kind": "font", "sha256": "0" * 64, "metadata": metadata})
    assert result["status"] == "supplied_by_user_unverified"
    assert result["notice_path"] is None


def test_license_notice_cannot_launder_private_or_aliased_file(audit_workspace, font_asset):
    private = audit_workspace / ".estado/tmp/private.txt"
    private.write_bytes(b"private fixture sentinel")
    forged = copy.deepcopy(font_asset)
    forged["metadata"]["font_notice"] = {"path": ".estado/tmp/private.txt", "sha256": sha(private.read_bytes())}
    with pytest.raises(core.StudioError):
        fonts.notice_file(forged)
    assert fonts.license_info(forged)["notice_path"] is None
    relative = "assets/fonts/licenses/" + sha(private.read_bytes())[:24] + ".txt"
    link = audit_workspace / relative
    link.symlink_to(private)
    forged["metadata"]["font_notice"]["path"] = relative
    with pytest.raises(core.StudioError):
        fonts.notice_file(forged)
    assert private.read_bytes() == b"private fixture sentinel"


def test_font_technical_and_notice_fields_cannot_be_forged_by_project_update(audit_workspace, font_asset):
    project = font_project(audit_workspace, font_asset)
    before = core.project_path(project["id"]).read_bytes()
    for field in ("font_info", "font_notice"):
        edited = copy.deepcopy(project)
        if field == "font_info":
            edited["assets"][0][field] = {"family": "Source Verified Fake"}
        else:
            edited["assets"][0]["metadata"][field]["sha256"] = "0" * 64
        with pytest.raises(core.StudioError) as error:
            core.save_project(project["id"], edited)
        assert error.value.status == 403
        assert core.project_path(project["id"]).read_bytes() == before


def layout_request(project, **changes):
    return {"project_id": project["id"], "element": text_element(),
            "scene_duration": 2, "width": 360, "height": 640, **changes}


@pytest.mark.parametrize("change", [{"width": True}, {"height": float("nan")},
                                   {"scene_duration": float("inf")}, {"width": 360.5},
                                   {"extra": "code"}, {"element": []},
                                   {"element": text_element(text_style={"shadow": {"blur": True}})},
                                   {"element": text_element(text_animation={"duration": float("nan")})}])
def test_layout_handler_rejects_payload_without_cpu_or_store_writes(audit_workspace, monkeypatch, change):
    project = core.create_project("Private API boundary fixture")
    before = core.project_path(project["id"]).read_bytes()
    monkeypatch.setattr(jobs, "cpu_slot", lambda: pytest.fail("Rejected payload reached CPU slot"))
    with pytest.raises(core.StudioError):
        server.text_layout(layout_request(project, **change))
    assert core.project_path(project["id"]).read_bytes() == before


def test_readonly_layout_uses_cpu_before_store_without_mutating_project(audit_workspace, font_asset, monkeypatch):
    project = font_project(audit_workspace, font_asset)
    before_project = core.project_path(project["id"]).read_bytes()
    before_assets = (audit_workspace / ".estado/assets.json").read_bytes()
    original = typo.layout_element
    def check_cpu(*args, **kwargs):
        assert jobs.CPU_ACTIVE.active is True
        assert getattr(core.LOCK.local, "depth", 0) == 0
        return original(*args, **kwargs)
    monkeypatch.setattr(typo, "layout_element", check_cpu)
    result = server.text_layout(layout_request(project, element=text_element(font_asset_id=font_asset["id"])))
    assert result["persisted"] is False and result["approved"] is False
    assert result["layout"]["font"]["sha256"] == font_asset["sha256"]
    assert str(audit_workspace) not in json.dumps(result)
    assert core.project_path(project["id"]).read_bytes() == before_project
    assert (audit_workspace / ".estado/assets.json").read_bytes() == before_assets


@pytest.fixture
def font_zip(audit_workspace, font_asset):
    project = font_project(audit_workspace, font_asset)
    result = jobs.export_bundle(project["id"])
    return project, audit_workspace / result["path"]


@pytest.mark.parametrize("attack", ["font_id_missing", "font_id_source", "font_kind_image", "font_kind_video", "notice_escape", "notice_hash"])
def test_zip_font_injection_rejected_before_catalog_writes(audit_workspace, font_asset, font_zip, attack, monkeypatch):
    project, original = font_zip
    def update(p):
        el = p["timeline"][0]["motion_design"]["elements"][0]
        item = next(a for a in p["assets"] if a["id"] == font_asset["id"])
        if attack == "font_id_missing":
            el["font_asset_id"] = "missing_font"
        elif attack == "font_id_source":
            el["font_asset_id"] = None
            p["source"] = item["id"]
        elif attack.startswith("font_kind"):
            item["kind"] = attack.rsplit("_", 1)[1]
        elif attack == "notice_escape":
            item["metadata"]["font_notice"]["path"] = ".estado/private.txt"
        else:
            item["metadata"]["font_notice"]["sha256"] = "0" * 64
    incoming = rewrite(audit_workspace, original, update=update)
    before_catalog = (audit_workspace / ".estado/assets.json").read_bytes()
    before_project = core.project_path(project["id"]).read_bytes()
    monkeypatch.setattr(core, "register_asset", lambda *a, **k: pytest.fail("Hostile ZIP wrote the catalog before rejection"))
    with pytest.raises(core.StudioError):
        bundles.import_bundle(incoming)
    assert (audit_workspace / ".estado/assets.json").read_bytes() == before_catalog
    assert core.project_path(project["id"]).read_bytes() == before_project


def test_font_zip_roundtrip_remaps_foreign_ids_and_keeps_notices_unverified(audit_workspace, font_asset, font_zip, monkeypatch):
    project, original = font_zip
    def update(p):
        next(a for a in p["assets"] if a["id"] == font_asset["id"])["id"] = "foreign_font"
        p["timeline"][0]["motion_design"]["elements"][0]["font_asset_id"] = "foreign_font"
        p["review"] = {"approved_preview": True}
        p["assets"][0]["metadata"]["font_notice"]["source_status"] = "source_verified"
    incoming = rewrite(audit_workspace, original, update=update)
    with zipfile.ZipFile(incoming) as archive:
        assert archive.testzip() is None
        assert archive.read(font_asset["metadata"]["font_notice"]["path"]) == fonts.notice_file(font_asset).read_bytes()
    reopened, local = new_workspace(audit_workspace, incoming, monkeypatch)
    result = bundles.import_bundle(local)
    p = result["project"]
    ref = p["timeline"][0]["motion_design"]["elements"][0]["font_asset_id"]
    item = next(a for a in p["assets"] if a["id"] == ref)
    assert ref == font_asset["id"] and ref != "foreign_font"
    assert item["sha256"] == font_asset["sha256"] and item["kind"] == "font"
    assert p["review"] == {} and not p.get("approved_export") and not p["renders"]
    assert fonts.license_info(item, reopened)["status"] == "bundled_notice_unverified"
    assert fonts.notice_file(item, reopened).read_bytes() == font_fixture("Anton-OFL.txt").read_bytes()
    assert fonts.validate_asset_font(item, reopened)["sha256"] == item["sha256"]


def _motion_add(bundle_value, name, data):
    root, directory, manifest, receipt, _ = bundle_value
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    entry = {"path": path.relative_to(root).as_posix(), "sha256": sha(data)}
    manifest["files"] = [item for item in manifest["files"] if item["path"] != entry["path"]] + [entry]
    receipt["technical"]["hyperframes"]["proof_files"] = copy.deepcopy(manifest["files"])
    (directory / "build.json").write_text(json.dumps(manifest))
    return entry


def _motion_font_bundle(bundle_value):
    binary = font_fixture("Anton-Regular.ttf").read_bytes()
    notice = font_fixture("Anton-OFL.txt").read_bytes()
    font_name = "fonts/" + sha(binary)[:20] + ".ttf"
    notice_name = "fonts/license_" + sha(notice)[:20] + ".txt"
    _motion_add(bundle_value, font_name, binary)
    _motion_add(bundle_value, notice_name, notice)
    record = {"file": font_name, "sha256": sha(binary), "family": "Anton", "style": "Regular",
              "synthetic_style": False, "license": {"status": "bundled_notice_unverified",
              "bundled_notice": notice_name, "notice_sha256": sha(notice)}}
    document = {"fonts": [record]}
    _motion_add(bundle_value, "fonts/font_manifest.json", json.dumps(document).encode())
    return document, font_name, notice_name


@pytest.mark.parametrize("attack", ["manifest_not_covered", "manifest_absent", "manifest_proof_absent",
    "orphan_font", "orphan_notice", "font_prefix", "notice_prefix", "font_hash", "notice_hash",
    "font_changed", "notice_changed", "synthetic_style", "duplicate_font", "wrong_records_type"])
def test_motion_zip_font_manifest_covers_exact_bytes_and_all_notices(bundle, attack):
    """External HF execution is mocked by bundle; this proves only ZIP guards."""
    root, directory, manifest, receipt, _ = bundle
    document, font_name, notice_name = _motion_font_bundle(bundle)
    record = document["fonts"][0]
    manifest_relative = (directory / "fonts/font_manifest.json").relative_to(root).as_posix()
    if attack == "manifest_not_covered":
        manifest["files"] = [item for item in manifest["files"] if item["path"] != manifest_relative]
        receipt["technical"]["hyperframes"]["proof_files"] = copy.deepcopy(manifest["files"])
    elif attack == "manifest_absent":
        (directory / "fonts/font_manifest.json").unlink()
    elif attack == "manifest_proof_absent":
        receipt["technical"]["hyperframes"]["proof_files"] = [item for item in manifest["files"] if item["path"] != manifest_relative]
    elif attack == "orphan_font":
        binary = font_fixture("IBMPlexMono-Regular.ttf").read_bytes()
        _motion_add(bundle, "fonts/" + sha(binary)[:20] + ".ttf", binary)
    elif attack == "orphan_notice":
        notice = b"Orphan independent notice fixture"
        _motion_add(bundle, "fonts/license_" + sha(notice)[:20] + ".txt", notice)
    elif attack in {"font_prefix", "notice_prefix"}:
        old = font_name if attack == "font_prefix" else notice_name
        new = "fonts/" + "0" * 20 + ".ttf" if attack == "font_prefix" else "fonts/license_" + "0" * 20 + ".txt"
        content = (directory / old).read_bytes()
        old_relative = (directory / old).relative_to(root).as_posix()
        manifest["files"] = [item for item in manifest["files"] if item["path"] != old_relative]
        _motion_add(bundle, new, content)
        if attack == "font_prefix":
            record["file"] = new
        else:
            record["license"]["bundled_notice"] = new
    elif attack == "font_hash":
        record["sha256"] = "0" * 64
    elif attack == "notice_hash":
        record["license"]["notice_sha256"] = "0" * 64
    elif attack in {"font_changed", "notice_changed"}:
        name = font_name if attack == "font_changed" else notice_name
        _motion_add(bundle, name, (directory / name).read_bytes() + b"changed")
    elif attack == "synthetic_style":
        record["synthetic_style"] = True
    elif attack == "duplicate_font":
        document["fonts"].append(copy.deepcopy(record))
    else:
        document["fonts"] = {"forged": record}
    if attack not in {"manifest_not_covered", "manifest_absent", "manifest_proof_absent"}:
        _motion_add(bundle, "fonts/font_manifest.json", json.dumps(document).encode())
    (directory / "build.json").write_text(json.dumps(manifest))
    destination = root / ".estado/tmp/font_audit.zip"
    with pytest.raises(core.StudioError):
        motion_zip.write_bundle(receipt, root, destination)
    assert not destination.exists()
    assert not list(destination.parent.glob("motion_*.tmp"))


def test_motion_zip_preserves_real_font_and_notice_bytes_without_approval(bundle):
    root, _, _, receipt, _ = bundle
    document, font_name, notice_name = _motion_font_bundle(bundle)
    result = motion_zip.write_bundle(receipt, root, root / ".estado/tmp/font_audit.zip")
    assert result["editorial_approved"] is False
    with zipfile.ZipFile(root / result["path"]) as archive:
        assert archive.testzip() is None
        assert archive.read(font_name) == font_fixture("Anton-Regular.ttf").read_bytes()
        assert archive.read(notice_name) == font_fixture("Anton-OFL.txt").read_bytes()
        assert json.loads(archive.read("fonts/font_manifest.json")) == document
        proof = json.loads(archive.read("bundle_manifest.json"))
        assert proof["editorial_approved"] is False
        names = [item["path"] for item in proof["files"]]
        assert names.count(font_name) == 1 and names.count(notice_name) == 1

