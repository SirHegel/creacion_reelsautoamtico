"""Adversarial data-only SceneIR audit; no client render or approval."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

from PIL import Image, ImageFont
import pytest

from studio import analysis, bundles, core, jobs, scene_ir
from test_core import sandbox, valid_project

REAL_TRUETYPE = ImageFont.truetype
REAL_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def explicit_scene(sandbox):
    project = valid_project(sandbox)
    project["settings"].update(width=160, height=284)
    document = {
        "schema": scene_ir.SCHEMA,
        "scene_id": "own_concept",
        "content": {"text": "{{name}} receives {{amount}} requests", "entities": ["Authored fictional subject"]},
        "narrative_goal": "Explain this authored concept; not a verified software demonstration",
        "family": "author_declared_process",
        "representation": "conceptual",
        "duration": 2,
        "composition": {"background": "#102030", "width": 160, "height": 284},
        "parameters": {"name": "Fixture", "amount": 214},
        "components": [
            {"id": "panel", "type": "shape", "x": .1, "y": .1, "width": .5, "height": .3,
             "shape": "rect", "color": "#405060"},
            {"id": "label", "type": "text", "x": .1, "y": .5, "width": .7, "height": .1,
             "text": "{{name}} / {{amount}}", "font": "primary", "font_size": 60},
        ],
        "actions": [
            {"target_id": "panel", "time": 0, "properties": {"x": .1, "opacity": 1}},
            {"target_id": "panel", "time": 1, "properties": {"x": .2}, "ease": "power2.out", "ease_window": [.2, .8]},
            {"target_id": "panel", "time": 2, "properties": {"opacity": 0}},
        ],
    }
    return project, document, sandbox


def own_graphic(project, root, *, declaration=True, lineage=None):
    path = root / "assets/images/owned_fixture.png"
    Image.new("RGB", (16, 16), "#204060").save(path)
    metadata = {"declaration_original": {"kind": "original_graphic", "author": "Fixture author only"}} if declaration else {}
    if lineage:
        metadata["provenance"] = lineage
    asset = {"id": "a_graphic", "name": path.name, "path": core.relative(path), "kind": "image",
             "sha256": core.digest(path), "md5": core.digest(path, "md5"), "size": path.stat().st_size,
             "duration": 0, "probe": {"streams": [{"codec_type": "video"}]},
             "metadata": metadata, "verification": {"visual": False, "audio": False}}
    core.atomic_json(".estado/assets.json", core.assets() + [asset])
    project["assets"].append(copy.deepcopy(asset))
    return asset


def add_graphic(document, asset_id):
    document["components"].append({"id": "graphic", "type": "media", "asset_id": asset_id,
                                   "x": .6, "y": .1, "width": .2, "height": .2, "source_in": 0})


def prepare_bundle_fonts_and_decoder(root, monkeypatch):
    missing = [name for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf")
               if not (REAL_ROOT / "assets/fonts" / name).is_file()]
    if missing:
        pytest.skip("Optional licensed local Sequel/Scholar fonts are absent from the public source: " + ", ".join(missing))
    for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf"):
        shutil.copyfile(REAL_ROOT / "assets/fonts" / name, root / "assets/fonts" / name)
    monkeypatch.setattr(ImageFont, "truetype", REAL_TRUETYPE)
    def own_probe(path):
        if Path(path).suffix == ".png":
            return {"streams": [{"codec_type": "video", "codec_name": "png", "width": 16, "height": 16}], "format": {"duration": "0"}}
        return {"streams": [{"codec_type": "video", "codec_name": "h264", "width": 160, "height": 284},
                            {"codec_type": "audio", "codec_name": "aac"}], "format": {"duration": "12"}}
    monkeypatch.setattr(analysis, "probe", own_probe)
    monkeypatch.setattr(analysis, "thumbnails", lambda *args, **kwargs: [])


def test_conversion_is_read_only_no_process_and_no_semantic_or_approval_claim(explicit_scene, monkeypatch):
    project, document, root = explicit_scene
    project.update(review={"fixture_only": True}, renders=[{"fixture_only": True}],
                   approved_export={"fixture_only": True}, full_authorization={"fixture_only": True},
                   design_reviews={"fixture_only": True}, design_snapshots={"fixture_only": True})
    original_project, original_document = copy.deepcopy(project), copy.deepcopy(document)
    files_before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    def forbidden(*args, **kwargs):
        pytest.fail("SceneIR must not launch a subprocess")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = scene_ir.compile_scene_ir(project, document)
    assert project == original_project and document == original_document
    assert {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()} == files_before
    assert result["source"] == project["source"] and result["audio"] == project["audio"]
    assert result["transcript"] == project["transcript"]
    assert result["timeline"][0]["start"] == 0 and result["timeline"][0]["end"] == 2
    assert result["review"] == result["design_reviews"] == result["design_snapshots"] == {}
    assert result["renders"] == [] and not result["approval_current"]
    assert not result.get("approved_export") and not result.get("full_authorization")
    evidence = result["scene_ir"]
    assert evidence["semantic_origin"] == "author_declared" and evidence["status"] == "pending_qc"
    assert evidence["clone_fidelity"] == "not_reviewed" and evidence["rights_verified"] is False
    assert evidence["representation"] == "conceptual"
    assert result["timeline"][0]["motion_design"]["elements"][1]["text"] == "Fixture / 214"
    assert [key["time"] for key in result["timeline"][0]["motion_design"]["elements"][0]["keyframes"]] == [0, 1, 2]


def test_parameter_substitution_keeps_injected_markup_and_nested_tokens_literal(explicit_scene):
    project, document, _ = explicit_scene
    literal = "</script><script>throw Error('never execute')</script>{{missing}}$()"
    document["parameters"]["name"] = literal
    result = scene_ir.compile_scene_ir(project, document)
    # The protected origin preserves the exact authored document and its hash;
    # resolved drawing primitives are separate from that declaration.
    assert result["scene_ir"]["document"] == document
    assert result["timeline"][0]["motion_design"]["elements"][1]["text"] == literal + " / 214"


@pytest.mark.parametrize("field", ["html", "javascript", "url", "path", "review", "design_reviews", "tracking", "approved_export", "semantic_verified"])
def test_unknown_root_fields_cannot_inject_execution_or_proofs(explicit_scene, field):
    project, document, _ = explicit_scene
    document[field] = {"approved": True}
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("field", ["html", "script", "src", "url", "onclick", "approved", "asset_path"])
def test_unknown_component_fields_are_rejected(explicit_scene, field):
    project, document, _ = explicit_scene
    document["components"][0][field] = "file:///outside"
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("value", [True, False, None, "2", float("nan"), float("inf"), -.1, 10.1])
def test_duration_requires_finite_bounded_number(explicit_scene, value):
    project, document, _ = explicit_scene
    document["duration"] = value
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("mutation", [
    lambda d: d["actions"][0].update(time=True),
    lambda d: d["actions"][0].update(time=2.01),
    lambda d: d["actions"][0]["properties"].update(x=False),
    lambda d: d["actions"][0]["properties"].update(x=2.01),
    lambda d: d["actions"][0]["properties"].update(opacity=1.01),
    lambda d: d["actions"][0]["properties"].update(script="alert(1)"),
    lambda d: d["actions"][0].update(ease="callback()"),
    lambda d: d["actions"][0].update(ease_window=[.5, .5]),
    lambda d: d["actions"][0].update(target_id="missing"),
    lambda d: d["actions"][0].update(target_id="../../sentinel"),
    lambda d: d["components"][0].update(id="../../sentinel"),
    lambda d: d["components"][0].update(start=1.5, end=1),
    lambda d: d["components"][0].update(width=1),
    lambda d: d["components"][0].update(mask={"type": "none", "inset": {"top": .1}}),
    lambda d: d["components"][0].update(path={"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}], "orient": True}),
    lambda d: d["composition"].update(width=162),
    lambda d: d["parameters"].update(name=True),
    lambda d: d["parameters"].update(__class__="exec"),
    lambda d: d["components"][1].update(text="{{undeclared}}"),
    lambda d: d["components"][1].update(text="{{ malformed }}"),
    lambda d: d["content"].update(results=[{"claim_verified": True}]),
    lambda d: d.update(representation="authentic_demo"),
])
def test_adversarial_types_geometry_timing_and_claims_are_rejected(explicit_scene, mutation):
    project, document, _ = explicit_scene
    mutation(document)
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


def test_conflicting_same_time_actions_are_rejected(explicit_scene):
    project, document, _ = explicit_scene
    document["actions"].append({"target_id": "panel", "time": 1, "properties": {"x": .3}})
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


def test_original_image_declaration_remains_an_unverified_attestation(explicit_scene):
    project, document, root = explicit_scene
    item = own_graphic(project, root)
    add_graphic(document, item["id"])
    result = scene_ir.compile_scene_ir(project, document)
    assert result["scene_ir"]["rights_verified"] is False
    assert result["scene_ir"]["status"] == "pending_qc"
    assert result["timeline"][0]["motion_design"]["elements"][-1]["asset_id"] == item["id"]


def test_project_metadata_cannot_forge_original_image_declaration(explicit_scene):
    project, document, root = explicit_scene
    item = own_graphic(project, root, declaration=False)
    project["assets"][-1]["metadata"] = {"declaration_original": {"kind": "original_graphic", "author": "Forged declaration"}}
    add_graphic(document, item["id"])
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("mutation", [
    lambda p: p["assets"][0].update(kind="image"),
    lambda p: p["assets"][0].update(path="../../source.mp4"),
    lambda p: p["assets"][0].update(probe={"streams": []}),
    lambda p: p["assets"][0].update(sha256="0" * 64),
    lambda p: p.update(source="missing"),
])
def test_source_and_graphic_identity_are_canonical(explicit_scene, mutation):
    project, document, _ = explicit_scene
    mutation(project)
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


def test_canonical_transitive_source_lineage_blocks_disguised_graphic(explicit_scene):
    project, document, root = explicit_scene
    source = core.asset(project["source"])
    path = root / "assets/video/own_derived_fixture.mp4"
    path.write_bytes(b"own derived parser fixture; never decoded")
    parent = copy.deepcopy(source)
    parent.update(id="a_derived", path=core.relative(path), sha256=core.digest(path),
                  md5=core.digest(path, "md5"), size=path.stat().st_size,
                  metadata={"provenance": {"source_asset_id": source["id"]}})
    core.atomic_json(".estado/assets.json", core.assets() + [parent])
    item = own_graphic(project, root, lineage={"source_asset_id": parent["id"]})
    project["assets"][-1]["metadata"] = {}  # A forged project declaration must not hide the canonical chain.
    add_graphic(document, item["id"])
    with pytest.raises(core.StudioError, match="derivado del crudo"):
        scene_ir.compile_scene_ir(project, document)


def test_raw_source_cannot_be_used_as_scene_ir_media(explicit_scene):
    project, document, _ = explicit_scene
    add_graphic(document, project["source"])
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("channel,value", [("opacity", True), ("x", False)])
def test_invalid_boolean_inline_keyframe_cannot_be_repaired_by_equal_numeric_action(explicit_scene, channel, value):
    project, document, _ = explicit_scene
    document["actions"] = [{"target_id": "panel", "time": 0, "properties": {channel: int(value)}}]
    document["components"][0]["keyframes"] = [{"time": 0, channel: value}]
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


def test_invalid_boolean_action_cannot_be_repaired_by_later_equal_numeric_action(explicit_scene):
    project, document, _ = explicit_scene
    document["actions"] = [{"target_id": "panel", "time": 0, "properties": {"x": False}},
                           {"target_id": "panel", "time": 0, "properties": {"x": 0}}]
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


def test_invalid_inline_ease_window_cannot_be_repaired_during_merge(explicit_scene):
    project, document, _ = explicit_scene
    document["components"][0]["keyframes"] = [{"time": 0, "x": 0, "ease_window": [False, 1]}]
    document["actions"] = [{"target_id": "panel", "time": 0, "properties": {"x": 0}, "ease_window": [0, 1]}]
    with pytest.raises(core.StudioError):
        scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("field,value", [("clone_fidelity", "verified"), ("rights_verified", True),
                                        ("status", "approved"), ("duration", 3),
                                        ("document_sha256", "0" * 64), ("semantic_origin", "semantic_engine")])
def test_compiled_origin_cannot_acquire_fabricated_verification(explicit_scene, field, value):
    project, document, _ = explicit_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled["scene_ir"][field] = value
    with pytest.raises(core.StudioError):
        scene_ir.validate_compiled_project(compiled)


def test_current_design_can_be_edited_without_changing_original_declaration(explicit_scene):
    project, document, _ = explicit_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    origin_before = copy.deepcopy(compiled["scene_ir"])
    compiled["timeline"][0]["motion_design"]["elements"][1]["text"] = "New author edit"
    scene_ir.validate_compiled_project(compiled)
    assert compiled["scene_ir"] == origin_before


def test_project_update_cannot_forge_scene_ir_mode_or_origin(explicit_scene):
    project, _, _ = explicit_scene
    incoming = copy.deepcopy(project)
    incoming.update(mode="scene_ir_component", scene_ir={"semantic_origin": "verified_generator", "rights_verified": True})
    saved = core.save_project(project["id"], incoming)
    assert saved.get("mode", "reel") == "reel" and not saved.get("scene_ir")
    assert not saved["approval_current"]


def test_component_update_preserves_protected_origin_and_rejects_escape_to_footage(explicit_scene):
    project, document, root = explicit_scene
    compiled = core.save_project(project["id"], scene_ir.compile_scene_ir(project, document), action="scene_ir_applied")
    original_origin = copy.deepcopy(compiled["scene_ir"])
    forged = copy.deepcopy(compiled)
    forged.update(mode="reel", scene_ir={"clone_fidelity": "verified", "rights_verified": True})
    saved = core.save_project(project["id"], forged)
    assert saved["mode"] == "scene_ir_component" and saved["scene_ir"] == original_origin
    project_before = core.project_path(project["id"]).read_bytes()
    escaped = copy.deepcopy(saved)
    escaped["mode"] = "reel"
    escaped["timeline"][0].update(type="broll", template="workflow", asset_id=project["source"])
    escaped["timeline"][0].pop("motion_design")
    with pytest.raises(core.StudioError):
        core.save_project(project["id"], escaped)
    assert core.project_path(project["id"]).read_bytes() == project_before


@pytest.mark.parametrize("field,value", [("asset_id", "a_source"), ("transition_asset_id", "a_source"),
                                        ("overlays", [{"id": "hidden", "asset_id": "a_source"}]),
                                        ("source_in", .25), ("broll_in", .25)])
def test_edited_component_cannot_introduce_secondary_footage_channels(explicit_scene, field, value):
    project, document, _ = explicit_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled["timeline"][0][field] = value
    with pytest.raises(core.StudioError):
        scene_ir.validate_compiled_project(compiled)


def test_edited_design_cannot_add_undeclared_stock_image(explicit_scene):
    project, document, root = explicit_scene
    own_graphic(project, root, declaration=False)
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled["timeline"][0]["motion_design"]["elements"].append({"id": "graphic", "type": "media", "asset_id": "a_graphic"})
    with pytest.raises(core.StudioError):
        scene_ir.validate_compiled_project(compiled)


def test_data_only_depth_limit_rejects_recursive_document(explicit_scene):
    project, document, _ = explicit_scene
    document["content"]["entities"] = [document]
    with pytest.raises(core.StudioError, match="estructura"):
        scene_ir.compile_scene_ir(project, document)


def test_implicit_scene_id_is_deterministic_and_schema_is_closed(explicit_scene):
    project, document, _ = explicit_scene
    document.pop("scene_id")
    first = scene_ir.compile_scene_ir(project, document)
    second = scene_ir.compile_scene_ir(project, copy.deepcopy(document))
    assert first["timeline"][0]["id"] == second["timeline"][0]["id"]
    assert first["scene_ir"]["document_sha256"] == second["scene_ir"]["document_sha256"]
    schema = scene_ir.describe_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["representation"]["const"] == "conceptual"
    json.dumps(schema, allow_nan=False)


@pytest.mark.parametrize("mutation", ["unknown_field", "boolean_action", "origin_hash", "raw_media", "secondary_footage", "fabricated_qc"])
def test_invalid_scene_ir_zip_is_rejected_before_catalog_writes(explicit_scene, monkeypatch, mutation):
    project, document, root = explicit_scene
    prepare_bundle_fonts_and_decoder(root, monkeypatch)
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled = core.save_project(project["id"], compiled, action="scene_ir_applied")
    original = root / jobs.export_bundle(compiled["id"])["path"]
    target = root / ".estado/tmp/negative_sceneir.zip"
    with zipfile.ZipFile(original) as incoming, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
        for info in incoming.infolist():
            content = incoming.read(info.filename)
            if info.filename == "project.json":
                value = json.loads(content)
                origin = value["scene_ir"]
                authored = origin["document"]
                if mutation == "unknown_field":
                    authored["html"] = "<script>never run</script>"
                elif mutation == "boolean_action":
                    authored["actions"][0]["properties"]["x"] = False
                elif mutation == "origin_hash":
                    origin["document_sha256"] = "0" * 64
                elif mutation == "raw_media":
                    add_graphic(authored, value["source"])
                    value["timeline"][0]["motion_design"]["elements"].append(copy.deepcopy(authored["components"][-1]))
                elif mutation == "secondary_footage":
                    value["timeline"][0]["asset_id"] = value["source"]
                else:
                    origin["clone_fidelity"] = "verified"
                if mutation != "origin_hash":
                    origin["document_sha256"] = scene_ir.document_digest(authored)
                content = json.dumps(value).encode()
            outgoing.writestr(info.filename, content)
    catalog_before = (root / ".estado/assets.json").read_bytes()
    project_before = core.project_path(project["id"]).read_bytes()
    calls = []
    def register_must_not_run(*args, **kwargs):
        calls.append(True)
        raise core.StudioError("Fixture observed premature catalog registration")
    # The fake source bytes are a parser fixture, not a decoded client video.
    # Media hash/ZIP extraction remain real; only decoder metadata is isolated.
    monkeypatch.setattr(bundles, "_existing_project", lambda *args: None)
    monkeypatch.setattr(core, "register_asset", register_must_not_run)
    expected = {"unknown_field": "Campos inválidos en SceneIR", "boolean_action": "Valor inválido",
                "origin_hash": "origen SceneIR", "raw_media": "crudo", "secondary_footage": "footage",
                "fabricated_qc": "origen SceneIR"}[mutation]
    with pytest.raises(core.StudioError, match=expected):
        bundles.import_bundle(target)
    assert calls == [], "Malformed SceneIR must fail before any catalog registration"
    assert (root / ".estado/assets.json").read_bytes() == catalog_before
    assert core.project_path(project["id"]).read_bytes() == project_before


def test_scene_ir_zip_roundtrip_maps_foreign_ids_and_preserves_original_graphic_attestation(explicit_scene, monkeypatch):
    from test_bundles import new_workspace
    project, document, root = explicit_scene
    prepare_bundle_fonts_and_decoder(root, monkeypatch)
    original_graphic = own_graphic(project, root)
    add_graphic(document, original_graphic["id"])
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled = core.save_project(project["id"], compiled, action="scene_ir_applied")
    original = root / jobs.export_bundle(compiled["id"])["path"]
    incoming_path = root / ".estado/tmp/foreign_sceneir.zip"
    with zipfile.ZipFile(original) as incoming, zipfile.ZipFile(incoming_path, "w", compression=zipfile.ZIP_DEFLATED) as outgoing:
        for info in incoming.infolist():
            content = incoming.read(info.filename)
            if info.filename == "project.json":
                value = json.loads(content)
                old_source = value["source"]
                value["source"] = "foreign_source"
                for asset in value["assets"]:
                    if asset["id"] == old_source:
                        asset["id"] = "foreign_source"
                    elif asset["id"] == original_graphic["id"]:
                        asset["id"] = "foreign_graphic"
                for track in value["audio"]:
                    if track["asset_id"] == old_source:
                        track["asset_id"] = "foreign_source"
                for scene in value["timeline"]:
                    for element in scene["motion_design"]["elements"]:
                        if element["type"] == "media":
                            element["asset_id"] = "foreign_graphic"
                for element in value["scene_ir"]["document"]["components"]:
                    if element["type"] == "media":
                        element["asset_id"] = "foreign_graphic"
                value["scene_ir"]["document_sha256"] = scene_ir.document_digest(value["scene_ir"]["document"])
                content = json.dumps(value).encode()
            outgoing.writestr(info.filename, content)
    reopened_root, incoming = new_workspace(root, incoming_path, monkeypatch)
    result = bundles.import_bundle(incoming)
    assert result["reused"] is False
    reopened = result["project"]
    assert reopened["mode"] == "scene_ir_component" and reopened["source"] != "foreign_source"
    graphics = [asset for asset in reopened["assets"] if asset["kind"] == "image"]
    assert len(graphics) == 1 and graphics[0]["id"] != "foreign_graphic"
    assert graphics[0]["sha256"] == original_graphic["sha256"]
    assert core.digest(reopened_root / graphics[0]["path"]) == original_graphic["sha256"]
    assert graphics[0]["metadata"]["declaration_original"]["kind"] == "original_graphic"
    assert graphics[0]["verification"]["visual"] is False
    current_media = reopened["timeline"][0]["motion_design"]["elements"][-1]
    origin_media = reopened["scene_ir"]["document"]["components"][-1]
    assert current_media["asset_id"] == origin_media["asset_id"] == graphics[0]["id"]
    assert reopened["scene_ir"]["document_sha256"] == scene_ir.document_digest(reopened["scene_ir"]["document"])
    assert reopened["scene_ir"]["rights_verified"] is False and reopened["scene_ir"]["clone_fidelity"] == "not_reviewed"
    assert reopened["review"] == {} and not reopened.get("approved_export") and not reopened.get("full_authorization")
    scene_ir.validate_compiled_project(reopened)
