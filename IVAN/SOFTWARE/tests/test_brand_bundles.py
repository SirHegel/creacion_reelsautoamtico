"""Workspace ZIP branding, real font bytes, no rendering or global mutations."""
import copy
import json
from pathlib import Path
import shutil
import zipfile

import pytest
from PIL import Image

from studio import analysis, brand_bundles, branding, bundles, core, jobs

SOFTWARE = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspaces(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((SOFTWARE / ".estado/tmp").resolve())
    original = core.confined

    def activate(name):
        root = tmp_path / name
        root.mkdir(exist_ok=True)
        def local(path, root_override=None, must_exist=False, **kwargs):
            return original(path, root=kwargs.get("root", root_override) or root, must_exist=must_exist)
        for module in (core, analysis, jobs):
            monkeypatch.setattr(module, "ROOT", root)
            monkeypatch.setattr(module, "confined", local)
        monkeypatch.setattr(core, "WORKSPACE_MODE", True)
        monkeypatch.setattr(core, "HASH_CACHE", {})
        monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
        branding.bootstrap(root, "Local " + name)
        core.setup()
        return root
    return activate


def branded_project(root, *, drive_id=None):
    value = branding.get_branding(root)
    cfg = {k: copy.deepcopy(value[k]) for k in ("revision", "name", "colors", "fonts", "logo_asset_id", "instructions", "language")}
    cfg.update(name="Diseño extranjero explícito", instructions="Marca declarada; permisos por revisar", language="es-MX")
    cfg["colors"].update(background="#16314F", accent="#BA47DC")
    cfg["fonts"].update(primary="a_a4ba3a92350ebb031da0", accent="a_6a3412f058c7d8dfd917")
    logo_file = root / ".estado/tmp/logo.png"
    Image.new("RGB", (16, 16), "#BA47DC").save(logo_file)
    logo = core.register_asset(logo_file, kind="image")
    cfg["logo_asset_id"] = logo["id"]
    branding.save_branding(root, cfg)
    p = core.create_project("ZIP con marca", drive_id=drive_id)
    p["timeline"] = [{"id": "s_motion", "start": 0, "end": 2, "type": "motion", "template": "workflow", "title": "Diseño propio"}]
    return core.save_project(p["id"], p)


def rewrite(root, path, change=None, replacements=None):
    dest = root / ".estado/tmp/changed.zip"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as dst:
        for member in src.infolist():
            raw = src.read(member.filename)
            if member.filename == "project.json" and change:
                p = json.loads(raw)
                change(p)
                raw = json.dumps(p, ensure_ascii=False).encode()
            raw = (replacements or {}).get(member.filename, raw)
            dst.writestr(member.filename, raw)
    return dest


def archive(root, project):
    return root / jobs.export_bundle(project["id"])["path"]


def incoming(root, old_zip):
    target = root / ".estado/tmp/incoming.zip"
    shutil.copyfile(old_zip, target)
    return target


def test_real_font_branding_roundtrip_preserves_project_appearance_not_global(workspaces):
    first = workspaces("first")
    old = branded_project(first)
    zipped = archive(first, old)
    second = workspaces("second")
    global_before = (second / ".estado/branding.json").read_bytes()
    existing = core.create_project("No modificar")
    existing_bytes = core.project_path(existing["id"]).read_bytes()
    result = bundles.import_bundle(incoming(second, zipped))
    assert not result["reused"]
    p = result["project"]
    profile = p["style"]["branding"]
    assert profile["name"] == old["style"]["branding"]["name"]
    assert profile["colors"] == old["style"]["branding"]["colors"]
    assert profile["instructions"] == old["style"]["branding"]["instructions"]
    assert profile["language"] == "es-MX"
    assert profile["fonts"]["primary"]["family"] == "Anton"
    assert profile["fonts"]["accent"]["family"] == "IBM Plex Mono"
    assert profile["editorial_approved"] is False
    assert profile["bundle_import"]["permissions"] == "pending_reinspection"
    assert all(face["license"]["status"] == "bundled_notice_unverified" for face in profile["fonts"].values())
    assert profile["logo_asset_id"] == old["style"]["branding"]["logo_asset_id"]
    assert (second / ".estado/branding.json").read_bytes() == global_before
    assert core.project_path(existing["id"]).read_bytes() == existing_bytes
    assert p["history"][-1]["action"] == "branding_bundle_imported"
    assert branding.validate_project_binding(p, second) == profile
    assert p["style"]["current_production_phase"] == "ivan_multiservice"
    assert p["review"] == {} and not p.get("approved_export")
    for role, face in profile["fonts"].items():
        assert core.digest(second / p["fonts"][role]) == face["sha256"]
    # The imported sealed snapshot must itself be portable, without importing
    # a private seal or a global account configuration into the archive.
    reexported = archive(second, p)
    with zipfile.ZipFile(reexported) as z:
        assert z.testzip() is None
        assert not any(".estado" in n or "branding.json" in n for n in z.namelist())
    third = workspaces("third")
    again = bundles.import_bundle(incoming(third, reexported))["project"]
    assert again["style"]["branding"]["colors"] == profile["colors"]
    assert again["style"]["branding"]["fonts"]["primary"]["sha256"] == profile["fonts"]["primary"]["sha256"]
    assert not again["style"]["branding"]["editorial_approved"]


def test_foreign_font_and_logo_ids_remap_to_canonical_real_rows(workspaces):
    first = workspaces("foreign_first")
    p = branded_project(first)
    def change(value):
        mapping = {a["id"]: "foreign_" + str(i) for i, a in enumerate(value["assets"])}
        for a in value["assets"]:
            a["id"] = mapping[a["id"]]
        for face in value["style"]["branding"]["fonts"].values():
            face["asset_id"] = mapping[face["asset_id"]]
        value["style"]["branding"]["logo_asset_id"] = mapping[value["style"]["branding"]["logo_asset_id"]]
        value["review"] = {"approved_preview": True, "audio_listened": True}
        value["design_reviews"] = {"forged": True}
        value["tracking"] = {"path": ".estado/private.json"}
        value["full_authorization"] = {"authorized": True}
        value["style"]["branding"]["editorial_approved"] = True
    edited = rewrite(first, archive(first, p), change)
    second = workspaces("foreign_second")
    got = bundles.import_bundle(incoming(second, edited))["project"]
    assert all(a["id"].startswith("a_") for a in got["assets"])
    assert all(face["asset_id"].startswith("a_") for face in got["style"]["branding"]["fonts"].values())
    assert got["style"]["branding"]["logo_asset_id"].startswith("a_")
    assert not got["style"]["branding"]["editorial_approved"]
    assert got["review"] == {} and not got.get("tracking") and not got.get("design_reviews")
    assert not got.get("full_authorization")


def test_selected_text_font_remaps_without_changing_face_or_animation_clock(workspaces):
    first = workspaces("text_first")
    p = branded_project(first)
    aid = p["style"]["branding"]["fonts"]["accent"]["asset_id"]
    p["timeline"] = [{"id": "s_text", "type": "motion", "template": "custom", "start": 0, "end": 2,
                      "motion_design": {"elements": [{"id": "e_text", "type": "text", "text": "Marca propia",
                          "font": "accent", "font_asset_id": aid, "font_size": 84, "x": .1, "y": .1,
                          "width": .8, "height": .3, "start": 0, "end": 2}]}}]
    p = core.save_project(p["id"], p)
    def change(value):
        for item in value["assets"]:
            if item["id"] == aid:
                item["id"] = "foreign_selected_face"
        value["style"]["branding"]["fonts"]["accent"]["asset_id"] = "foreign_selected_face"
        value["timeline"][0]["motion_design"]["elements"][0]["font_asset_id"] = "foreign_selected_face"
    edited = rewrite(first, archive(first, p), change)
    second = workspaces("text_second")
    got = bundles.import_bundle(incoming(second, edited))["project"]
    el = got["timeline"][0]["motion_design"]["elements"][0]
    assert el["font_asset_id"] == aid
    assert el["font"] == "accent" and el["start"] == 0 and el["end"] == 2
    assert got["style"]["branding"]["fonts"]["accent"]["asset_id"] == aid
    assert branding.validate_project_binding(got, second)


ATTACKS = [
    ("snapshot_unknown", lambda b: b.update(token="private")),
    ("revision_bool", lambda b: b.update(revision=True)),
    ("revision_negative", lambda b: b.update(revision=-1)),
    ("name_long", lambda b: b.update(name="x" * 121)),
    ("name_control", lambda b: b.update(name="hello\x00")),
    ("colors_missing", lambda b: b["colors"].pop("muted")),
    ("css_color", lambda b: b["colors"].update(accent="url(https://evil)")),
    ("language_path", lambda b: b.update(language="../../en")),
    ("instructions_type", lambda b: b.update(instructions={})),
    ("instructions_large", lambda b: b.update(instructions="x" * 8001)),
    ("base_other", lambda b: b.update(base="arbitrary")),
    ("base_hash", lambda b: b.update(base_rules_sha256="0")),
    ("override_missing", lambda b: b.update(font_override_explicit=False)),
    ("refs_forged", lambda b: b.update(original_reference_fonts=["Arial"])),
    ("approval_type", lambda b: b.update(editorial_approved="true")),
    ("role_unknown", lambda b: b["fonts"].update(secondary=copy.deepcopy(b["fonts"]["primary"]))),
    ("face_unknown", lambda b: b["fonts"]["primary"].update(private_path="secret")),
    ("face_id_missing", lambda b: b["fonts"]["primary"].update(asset_id="missing")),
    ("face_id_path", lambda b: b["fonts"]["primary"].update(asset_id="../private")),
    ("face_sha_forged", lambda b: b["fonts"]["primary"].update(sha256="0" * 64)),
    ("face_family_forged", lambda b: b["fonts"]["primary"].update(family="Fake Font")),
    ("face_style_forged", lambda b: b["fonts"]["primary"].update(style="Fake Bold")),
    ("face_path_escape", lambda b: b["fonts"]["primary"].update(path="assets/fonts/../../secret.otf")),
    ("face_license_unknown", lambda b: b["fonts"]["primary"]["license"].update(owned=True)),
    ("face_notice_escape", lambda b: b["fonts"]["primary"]["license"].update(notice_path=".estado/secret")),
    ("face_notice_sha", lambda b: b["fonts"]["primary"]["license"].update(notice_sha256="0" * 64)),
    ("logo_missing", lambda b: b.update(logo_asset_id="missing")),
    ("logo_kind_font", lambda b: b.update(logo_asset_id=b["fonts"]["primary"]["asset_id"])),
    ("trace_forged", lambda b: b.update(bundle_import={"permissions": "approved"})),
]


@pytest.mark.parametrize("name,attack", ATTACKS, ids=[x[0] for x in ATTACKS])
def test_invalid_brand_snapshot_rejected_before_catalog_writes(workspaces, monkeypatch, name, attack):
    first = workspaces("attack_first")
    p = branded_project(first)
    changed = rewrite(first, archive(first, p), lambda value: attack(value["style"]["branding"]))
    second = workspaces("attack_second")
    catalog = (second / ".estado/assets.json").read_bytes()
    config = (second / ".estado/branding.json").read_bytes()
    calls = []
    monkeypatch.setattr(core, "register_asset", lambda *a, **kw: calls.append(a) or pytest.fail("Catalog write before validation"))
    with pytest.raises(core.StudioError):
        bundles.import_bundle(incoming(second, changed))
    assert not calls
    assert (second / ".estado/assets.json").read_bytes() == catalog
    assert (second / ".estado/branding.json").read_bytes() == config
    assert not core.project_list()


def test_actual_font_bytes_mismatch_rejected_before_catalog_write(workspaces, monkeypatch):
    first = workspaces("font_first")
    p = branded_project(first)
    original = (first / p["fonts"]["primary"]).read_bytes()
    invalid = bytes([original[0] ^ 1]) + original[1:]
    changed = rewrite(first, archive(first, p), replacements={p["fonts"]["primary"]: invalid})
    second = workspaces("font_second")
    monkeypatch.setattr(core, "register_asset", lambda *a, **kw: pytest.fail("Unexpected registration"))
    with pytest.raises(core.StudioError, match="SHA256"):
        bundles.import_bundle(incoming(second, changed))


def test_imported_license_verified_claim_is_downgraded(workspaces):
    first = workspaces("license_first")
    p = branded_project(first)
    def change(value):
        for face in value["style"]["branding"]["fonts"].values():
            face["license"].update(status="source_verified", source_url="https://example.invalid/owned")
    changed = rewrite(first, archive(first, p), change)
    second = workspaces("license_second")
    registry_before = (second / ".estado/fonts/licensed.json").read_bytes()
    got = bundles.import_bundle(incoming(second, changed))["project"]
    assert all(f["license"]["status"] == "bundled_notice_unverified" and f["license"]["source_url"] is None for f in got["style"]["branding"]["fonts"].values())
    assert (second / ".estado/fonts/licensed.json").read_bytes() == registry_before


@pytest.mark.parametrize("after_write", [False, True])
def test_failed_import_save_restores_new_project_and_private_seal(workspaces, monkeypatch, after_write):
    first = workspaces("rollback_first")
    p = branded_project(first)
    zipped = archive(first, p)
    second = workspaces("rollback_second")
    original = core.save_project
    captured = {}
    def fail(pid, value, **kwargs):
        if kwargs.get("action") == "branding_bundle_imported":
            captured["id"] = pid
            captured["old_project"] = core.project_path(pid).read_bytes()
            captured["old_record"] = json.dumps(branding.snapshot(second), ensure_ascii=False, sort_keys=True).encode()
            if after_write:
                original(pid, value, **kwargs)
            raise core.StudioError("CAS fixture failure", 409)
        return original(pid, value, **kwargs)
    monkeypatch.setattr(core, "save_project", fail)
    with pytest.raises(core.StudioError, match="CAS fixture"):
        bundles.import_bundle(incoming(second, zipped))
    pid = captured["id"]
    assert core.project_path(pid).read_bytes() == captured["old_project"]
    assert (second / ".estado/project_branding" / (pid + ".json")).read_bytes() == captured["old_record"]
    assert branding.validate_project_binding(core.get_project(pid), second)


def test_dedup_hit_does_not_rebrand_existing_project_or_account(workspaces):
    first = workspaces("dedup_first")
    p = branded_project(first, drive_id="fixture_unique_drive")
    zipped = archive(first, p)
    second = workspaces("dedup_second")
    existing = core.create_project("Existente", drive_id="fixture_unique_drive")
    project_before = core.project_path(existing["id"]).read_bytes()
    record = second / ".estado/project_branding" / (existing["id"] + ".json")
    binding_before = record.read_bytes()
    catalog_before = (second / ".estado/assets.json").read_bytes()
    result = bundles.import_bundle(incoming(second, zipped))
    assert result["reused"] is True and result["project"]["id"] == existing["id"]
    assert core.project_path(existing["id"]).read_bytes() == project_before
    assert record.read_bytes() == binding_before
    assert (second / ".estado/assets.json").read_bytes() == catalog_before


def test_private_binding_symlink_rejected_without_touching_target(workspaces):
    root = workspaces("symlink")
    target = root / ".estado/other_binding"
    target.mkdir()
    directory = root / ".estado/project_branding"
    directory.symlink_to(target, target_is_directory=True)
    with pytest.raises(core.StudioError, match="enlaces"):
        brand_bundles._record_path("p_fixture")
    assert not list(target.iterdir())


def test_legacy_workspace_plan_declares_appearance_fallback_without_font_substitution(workspaces):
    root = workspaces("legacy_plan")
    p = core.create_project("Plan de legado")
    p["style"].pop("branding")
    p["fonts"] = {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"}
    before = (root / ".estado/branding.json").read_bytes()
    plan = brand_bundles.prepare(p)
    assert plan["appearance"] == "workspace_fallback"
    assert plan["profile"]["name"] == "Local legacy_plan"
    assert plan["roles"] == {"primary": "sequel", "accent": "scholar"}
    assert plan["logo_asset_id"] is None
    assert (root / ".estado/branding.json").read_bytes() == before


def test_legacy_import_still_rejects_custom_font_without_explicit_snapshot(workspaces):
    first = workspaces("no_snapshot_first")
    p = branded_project(first)
    changed = rewrite(first, archive(first, p), lambda value: value["style"].pop("branding"))
    second = workspaces("no_snapshot_second")
    before = (second / ".estado/assets.json").read_bytes()
    with pytest.raises(core.StudioError, match="Sequel/Scholar"):
        bundles.import_bundle(incoming(second, changed))
    assert (second / ".estado/assets.json").read_bytes() == before


def test_personalized_zip_cannot_bypass_legacy_font_gates(workspaces, monkeypatch):
    first = workspaces("legacy_gate_first")
    p = branded_project(first)
    zipped = archive(first, p)
    second = workspaces("legacy_gate_second")
    monkeypatch.setattr(core, "WORKSPACE_MODE", False)
    before = (second / ".estado/assets.json").read_bytes()
    with pytest.raises(core.StudioError, match="Sequel/Scholar"):
        bundles.import_bundle(incoming(second, zipped))
    assert (second / ".estado/assets.json").read_bytes() == before
