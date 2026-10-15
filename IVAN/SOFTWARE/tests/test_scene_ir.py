"""Explicit semantics, secure SceneIR compilation and actual local rendering."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from studio import core, design, hyperframes as hf, render as native, scene_ir as ir
from studio.core import StudioError


@pytest.fixture
def scene_input(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(core.ROOT / ".estado")
    source = {"id": "source", "kind": "video", "path": "source.mp4", "sha256": "a" * 64,
              "duration": 15, "probe": {"streams": [{"codec_type": "video", "disposition": {}},
                                                     {"codec_type": "audio"}]}, "metadata": {}}
    graphic = {"id": "graphic", "kind": "image", "path": "graphic.png", "sha256": "b" * 64,
               "duration": 0, "probe": {"streams": [{"codec_type": "video", "codec_name": "png"}]},
               "metadata": {"declaration_original": {"kind": "original_graphic", "author": "Usuario"}}}
    catalog = [source, graphic]
    monkeypatch.setattr(core, "assets", lambda: copy.deepcopy(catalog))
    project = {"id": "existing_project", "source": "source", "assets": copy.deepcopy(catalog),
               "settings": {"width": 160, "height": 240, "fps": 12, "engine": "native"},
               "fonts": {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"},
               "timeline": [{"id": "old_scene", "start": 0, "end": 15, "type": "presenter"}],
               "transcript": {"words": [{"start": 0, "end": .2, "word": "Hola"}], "segments": []},
               "audio": [{"asset_id": "source", "start": 0, "end": 1, "role": "sfx", "gain_db": -60}],
               "review": {"status": "approved"}, "renders": [{"sha256": "historic"}],
               "approved_export": {"path": "old.mp4"}, "full_authorization": {"authorized": True},
               "design_reviews": {"old_scene": {"approved": True}}, "design_snapshots": {"old_scene": "old.png"}}
    document = {"schema": ir.SCHEMA, "scene_id": "conceptual_response", "representation": "conceptual",
                "content": {"text": "Personalizar {{count}} respuestas para {{name}}", "entities": ["solicitud", "respuesta"],
                            "actions": ["analizar", "responder"], "results": ["respuesta personalizada"],
                            "relations": ["la respuesta corresponde a una solicitud"]},
                "narrative_goal": "Representar la transformación de una solicitud en una respuesta personalizada.",
                "family": "request_response", "duration": 1.5,
                "composition": {"background": "#101318", "width": 160, "height": 240},
                "parameters": {"name": "Nora", "count": 3},
                "components": [{"id": "packet", "type": "shape", "shape": "rect", "color": "#2acb8e",
                                "x": .1, "y": .4, "width": .1, "height": .1, "radius": 8,
                                "mask": {"type": "inset"}},
                               {"id": "label", "type": "text", "text": "{{count}} respuestas: {{name}}",
                                "x": .1, "y": .15, "width": .8, "height": .2, "font": "accent", "font_size": 90}],
                "actions": [{"target_id": "packet", "time": 0, "properties": {"mask_progress": .1}},
                            {"target_id": "packet", "time": 1.5, "properties": {"x": .7, "mask_progress": 1},
                             "ease": "power2.inOut", "ease_window": [.1, .9]}]}
    return tmp_path, project, document, catalog


def test_compilation_is_deterministic_readonly_and_preserves_narration(scene_input, monkeypatch):
    root, project, document, _ = scene_input
    before_project, before_document = copy.deepcopy(project), copy.deepcopy(document)
    before_files = list(root.rglob("*"))
    monkeypatch.setattr(core, "atomic_json", lambda *args, **kwargs: pytest.fail("Compiler wrote to store"))
    result = ir.compile_scene_ir(project, document)
    assert project == before_project and document == before_document and list(root.rglob("*")) == before_files
    assert result["mode"] == "scene_ir_component" and result["timeline"][0]["template"] == "custom"
    assert result["timeline"][0]["start"] == 0 and result["timeline"][0]["end"] == 1.5
    for field in ("id", "source", "assets", "settings", "fonts", "transcript", "audio"):
        assert result[field] == project[field] and (not isinstance(result[field], (list, dict)) or result[field] is not project[field])
    assert result["scene_ir"]["document"] == document
    assert result["scene_ir"]["duration"] == 1.5 and result["scene_ir"]["status"] == "pending_qc"
    assert result["scene_ir"]["semantic_origin"] == "author_declared"
    assert result["scene_ir"]["clone_fidelity"] == "not_reviewed" and result["scene_ir"]["rights_verified"] is False
    assert result["timeline"][0]["motion_design"]["elements"][1]["text"] == "3 respuestas: Nora"
    assert ir.compile_scene_ir(project, copy.deepcopy(document)) == result
    assert ir.validate_compiled_project(result) is None


def test_old_approvals_are_not_inherited_by_new_component(scene_input):
    _, project, document, _ = scene_input
    result = ir.compile_scene_ir(project, document)
    for field in ("review", "renders", "design_reviews", "design_snapshots", "gates"):
        assert not result[field]
    assert result["approval_current"] is False
    assert "approved_export" not in result and "full_authorization" not in result
    assert project["review"]["status"] == "approved" and project["full_authorization"]["authorized"]


def test_default_scene_id_and_document_hash_are_reproducible(scene_input):
    _, project, document, _ = scene_input
    document.pop("scene_id")
    first = ir.compile_scene_ir(project, document)
    second = ir.compile_scene_ir(project, dict(reversed(list(document.items()))))
    assert first["timeline"] == second["timeline"]
    assert first["scene_ir"]["document_sha256"] == second["scene_ir"]["document_sha256"]
    assert first["timeline"][0]["id"].startswith("sceneir_")


def test_actions_merge_ordered_unique_keys_and_preserve_destination_ease(scene_input):
    _, project, document, _ = scene_input
    document["components"][0]["keyframes"] = [{"time": .5, "opacity": .4}]
    document["actions"].append({"target_id": "packet", "time": .5, "properties": {"scale": 1.2}})
    document["actions"] = list(reversed(document["actions"]))
    scene = ir.compile_scene_ir(project, document)["timeline"][0]
    keys = scene["motion_design"]["elements"][0]["keyframes"]
    assert [key["time"] for key in keys] == [0, .5, 1.5]
    assert keys[1] == {"time": .5, "opacity": .4, "scale": 1.2}
    assert keys[2]["ease"] == "power2.inOut" and keys[2]["ease_window"] == [.1, .9]
    state = design.element_state(scene["motion_design"]["elements"][0], 1, 1.5, 160, 240)
    assert .1 < state["x"] < .7 and .1 < state["mask_progress"] < 1


def test_parameter_values_are_literal_single_pass_text_not_code(scene_input):
    root, project, document, _ = scene_input
    literal = "<script>throw Error('never execute')</script>${7*7}{{unresolved_literal}}"
    document["parameters"]["name"] = literal
    result = ir.compile_scene_ir(project, document)
    assert literal in result["timeline"][0]["motion_design"]["elements"][1]["text"]
    assert result["scene_ir"]["document"]["parameters"]["name"] == literal
    assert not list(root.rglob("*"))


@pytest.mark.parametrize("field,value", [("schema", "ascendia.sceneir/999"), ("representation", "authentic_demo"),
    ("family", "https://remote.example/template"), ("scene_id", "../../outside"), ("duration", True),
    ("duration", 0), ("duration", 10.01), ("duration", float("nan")), ("duration", float("inf")),
    ("narrative_goal", ""), ("content", []), ("components", []), ("components", {}),
    ("actions", "animate()"), ("parameters", []), ("html", "<script/>"), ("approved", True)])
def test_document_rejects_unsupported_execution_claims_and_invalid_shape(scene_input, field, value):
    _, project, document, _ = scene_input
    document[field] = value
    before = copy.deepcopy(project)
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)
    assert project == before


@pytest.mark.parametrize("value", [True, None, {"eval": "2+2"}, [1, 2], float("nan"), float("inf")])
def test_parameters_allow_only_explicit_strings_or_finite_numbers(scene_input, value):
    _, project, document, _ = scene_input
    document["parameters"]["name"] = value
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("text", ["{{missing}}", "{{name + 1}}", "{{name}} }}", "{{ name }}", "\x00"])
def test_unknown_or_expression_parameter_tokens_are_rejected(scene_input, text):
    _, project, document, _ = scene_input
    document["components"][1]["text"] = text
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("field,value", [("x", True), ("x", -.1), ("width", 0), ("width", 1.1),
    ("end", 2), ("color", "url(https://remote.example/color)"), ("font", "system-font"),
    ("js", "fetch('https://remote.example')"), ("text", "unsupported shape text"),
    ("mask", {"type": "inset", "inset": {"script": "eval"}}),
    ("path", {"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1}], "orient": True}),
    ("path", {"points": [{"x": 0, "y": 0}, {"x": 1, "y": 1, "html": "bad"}]})])
def test_component_geometry_and_nested_fields_are_controlled(scene_input, field, value):
    _, project, document, _ = scene_input
    document["components"][0][field] = value
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("mutation", ["target", "time", "boolean", "scale", "opacity", "channel", "curve", "window", "empty", "conflict", "keys"])
def test_action_targets_properties_curves_and_conflicts_are_validated(scene_input, mutation):
    _, project, document, _ = scene_input
    action = document["actions"][1]
    if mutation == "target":
        action["target_id"] = "missing"
    elif mutation == "time":
        action["time"] = 1.6
    elif mutation == "boolean":
        action["properties"]["x"] = True
    elif mutation == "scale":
        action["properties"]["scale"] = 8.1
    elif mutation == "opacity":
        action["properties"]["opacity"] = -.1
    elif mutation == "channel":
        action["properties"]["innerHTML"] = "<script>bad</script>"
    elif mutation == "curve":
        action["ease"] = "function(){fetch('remote')}"
    elif mutation == "window":
        action["ease_window"] = [.8, .2]
    elif mutation == "empty":
        action["properties"] = {}
    elif mutation == "conflict":
        document["actions"].append({"target_id": "packet", "time": 1.5, "properties": {"x": .2}})
    else:
        document["components"][0]["keyframes"] = [{"time": 0, "x": .1}, {"time": 0, "y": .1}]
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


def add_media(document, asset_id="graphic"):
    document["components"].append({"id": "graphic_element", "type": "media", "asset_id": asset_id,
                                   "x": .4, "y": .6, "width": .2, "height": .2})


def test_declared_original_graphic_remains_only_an_attestation(scene_input):
    _, project, document, _ = scene_input
    add_media(document)
    result = ir.compile_scene_ir(project, document)
    assert result["timeline"][0]["motion_design"]["elements"][-1]["asset_id"] == "graphic"
    assert result["scene_ir"]["rights_verified"] is False and result["scene_ir"]["status"] == "pending_qc"


@pytest.mark.parametrize("mutation", ["unknown", "url", "path", "source", "video", "stock", "unattached", "forged_declaration", "forged_path", "derived", "offset"])
def test_media_is_canonical_original_graphic_without_source_lineage(scene_input, mutation):
    _, project, document, catalog = scene_input
    add_media(document)
    media = document["components"][-1]
    if mutation == "unknown":
        media["asset_id"] = "missing"
    elif mutation == "url":
        media["asset_id"] = "https://remote.example/movie.mp4"
    elif mutation == "path":
        media["asset_id"] = "../movie.mp4"
    elif mutation == "source":
        media["asset_id"] = "source"
    elif mutation == "video":
        catalog[1]["kind"] = project["assets"][1]["kind"] = "video"
    elif mutation == "stock":
        catalog[1]["metadata"]["declaration_original"]["kind"] = "stock"
    elif mutation == "unattached":
        project["assets"].pop()
    elif mutation == "forged_declaration":
        catalog[1]["metadata"] = {}
        assert project["assets"][1]["metadata"]["declaration_original"]
    elif mutation == "forged_path":
        project["assets"][1]["path"] = "private.json"
    elif mutation == "derived":
        catalog[1]["metadata"]["provenance"] = {"source_asset_id": "source", "source_sha256": "a" * 64}
    elif mutation == "offset":
        media["source_in"] = .1
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


@pytest.mark.parametrize("mutation", ["missing", "unattached", "audio", "cover", "tampered", "duplicate"])
def test_original_narration_source_cannot_be_fabricated(scene_input, mutation):
    _, project, document, catalog = scene_input
    if mutation == "missing":
        project["source"] = None
    elif mutation == "unattached":
        project["assets"].pop(0)
    elif mutation == "audio":
        catalog[0]["kind"] = "audio"
    elif mutation == "cover":
        catalog[0]["probe"]["streams"][0]["disposition"]["attached_pic"] = True
    elif mutation == "tampered":
        project["assets"][0]["sha256"] = "f" * 64
    else:
        project["assets"].append(copy.deepcopy(project["assets"][0]))
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)


def test_canvas_must_match_existing_project(scene_input):
    _, project, document, _ = scene_input
    document["composition"]["width"] = 1080
    with pytest.raises(StudioError, match="coincidir"):
        ir.compile_scene_ir(project, document)


def test_document_component_and_action_quotas_are_bounded(scene_input, monkeypatch):
    _, project, document, _ = scene_input
    monkeypatch.setattr(ir, "MAX_DOCUMENT_BYTES", 1)
    with pytest.raises(StudioError, match="2 MiB"):
        ir.compile_scene_ir(project, document)
    monkeypatch.setattr(ir, "MAX_DOCUMENT_BYTES", 2 * 1024 * 1024)
    document["components"] *= 33
    with pytest.raises(StudioError, match="64 componentes"):
        ir.compile_scene_ir(project, document)
    document["components"] = document["components"][:2]
    monkeypatch.setattr(ir, "MAX_ACTIONS", 1)
    with pytest.raises(StudioError, match="acciones"):
        ir.compile_scene_ir(project, document)


def test_origin_hash_is_protected_but_later_motion_edits_are_allowed(scene_input):
    _, project, document, _ = scene_input
    result = ir.compile_scene_ir(project, document)
    result["timeline"][0]["id"] = "edited_component"
    result["timeline"][0]["end"] = 2
    element = result["timeline"][0]["motion_design"]["elements"][0]
    element["x"] = .2
    element["keyframes"][-1]["rotation"] = 25
    assert ir.validate_compiled_project(result) is None
    result["scene_ir"]["document"]["parameters"]["name"] = "tampered origin"
    with pytest.raises(StudioError, match="origen SceneIR"):
        ir.validate_compiled_project(result)


@pytest.mark.parametrize("mutation", ["mode", "duration", "scene_type", "extra_scene", "overlay", "transition", "source_graphic"])
def test_edited_component_still_cannot_acquire_footage_or_full_render_scope(scene_input, mutation):
    _, project, document, _ = scene_input
    result = ir.compile_scene_ir(project, document)
    scene = result["timeline"][0]
    if mutation == "mode":
        result["mode"] = "narrative"
    elif mutation == "duration":
        scene["end"] = 11
    elif mutation == "scene_type":
        scene["type"] = "presenter"
    elif mutation == "extra_scene":
        result["timeline"].append(copy.deepcopy(scene))
    elif mutation == "overlay":
        scene["overlays"] = [{"asset_id": "source"}]
    elif mutation == "transition":
        scene["transition_asset_id"] = "source"
    else:
        scene["motion_design"]["elements"].append({"id": "hidden", "type": "media", "asset_id": "source"})
    with pytest.raises(StudioError):
        ir.validate_compiled_project(result)


def test_schema_is_closed_and_describes_declared_inputs_without_fake_engine_claims():
    schema = ir.describe_schema()
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema"]["const"] == "ascendia.sceneir/1"
    assert schema["properties"]["representation"]["const"] == "conceptual"
    assert schema["properties"]["actions"]["items"]["additionalProperties"] is False
    assert schema["properties"]["parameters"]["additionalProperties"]["oneOf"][1]["type"] == "number"
    schema["properties"]["schema"]["const"] = "changed caller copy"
    assert ir.describe_schema()["properties"]["schema"]["const"] == ir.SCHEMA


def test_semantic_color_reason_is_editable_bounded_text(scene_input):
    _, project, document, _ = scene_input
    document["components"][0].update(color="#d91424", color_reason="Representa una solicitud rechazada.")
    result = ir.compile_scene_ir(project, document)
    assert result["timeline"][0]["motion_design"]["elements"][0]["color_reason"] == "Representa una solicitud rechazada."
    document["components"][0]["color_reason"] = "x" * 2001
    with pytest.raises(StudioError):
        ir.compile_scene_ir(project, document)
    assert "color_reason" in ir.describe_schema()["properties"]["components"]["items"]["oneOf"][0]["properties"]


def test_import_preflight_uses_only_explicit_staging_catalog(scene_input, monkeypatch):
    root, project, document, catalog = scene_input
    result = ir.compile_scene_ir(project, document)
    before = copy.deepcopy(result)

    def forbidden_catalog():
        pytest.fail("ZIP preflight consulted the live catalog")

    monkeypatch.setattr(core, "assets", forbidden_catalog)
    assert ir.validate_import_project(result, copy.deepcopy(catalog)) is None
    assert ir.validate_import_project(result, {a["id"]: copy.deepcopy(a) for a in catalog}) is None
    assert result == before and not list(root.rglob("*"))


@pytest.mark.parametrize("mutation", ["missing_source", "duplicate", "bad_hash", "bad_probe", "outside", "bad_document", "forged_origin"])
def test_import_preflight_rejects_bad_staging_before_registration(scene_input, monkeypatch, mutation):
    _, project, document, catalog = scene_input
    result = ir.compile_scene_ir(project, document)
    staged = copy.deepcopy(catalog)
    monkeypatch.setattr(core, "assets", lambda: pytest.fail("Read live catalog during ZIP preflight"))
    monkeypatch.setattr(core, "register_asset", lambda *args, **kwargs: pytest.fail("Registered before preflight"))
    if mutation == "missing_source":
        staged.pop(0)
    elif mutation == "duplicate":
        staged.append(copy.deepcopy(staged[0]))
    elif mutation == "bad_hash":
        staged[0]["sha256"] = "missing-real-hash"
    elif mutation == "bad_probe":
        staged[0]["probe"] = {"streams": [None]}
    elif mutation == "outside":
        staged[0]["path"] = "/outside-software/source.mp4"
    elif mutation == "bad_document":
        result["scene_ir"]["document"]["components"][0]["js"] = "never execute"
    else:
        result["scene_ir"]["rights_verified"] = True
    with pytest.raises(StudioError):
        ir.validate_import_project(result, staged)


def test_document_digest_rehashes_original_ids_without_resolving_parameters(scene_input):
    _, project, document, _ = scene_input
    digest = ir.document_digest(document)
    assert digest == ir.compile_scene_ir(project, document)["scene_ir"]["document_sha256"]
    assert ir.document_digest(dict(reversed(list(document.items())))) == digest
    document["parameters"]["name"] = "Variant"
    assert ir.document_digest(document) != digest


def test_explicit_scene_ir_compiles_to_real_hyperframes_mp4_with_voice(scene_input):
    root, project, document, catalog = scene_input
    if not hf.availability(root)["available"]:
        pytest.skip("Local HyperFrames runtime unavailable")
    original = root / "source.mp4"
    native._run([native._tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=0x343434:s=160x240:r=12:d=1.5", "-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-threads", "1", "-shortest", str(original)], root)
    catalog[0].update(sha256=hashlib.sha256(original.read_bytes()).hexdigest(), duration=1.5,
                      probe=native.probe_media(original, root))
    catalog[:] = catalog[:1]
    project["assets"] = copy.deepcopy(catalog)
    fonts = root / "assets/fonts"
    fonts.mkdir(parents=True)
    for path in (hf.ROOT / "assets/fonts").glob("*.ttf"):
        shutil.copyfile(path, fonts / path.name)
    project["audio"] = []
    project["settings"]["engine"] = "hyperframes"
    result = ir.compile_scene_ir(project, document)
    ir.validate_compiled_project(result)
    (root / "scene_ir.json").write_text(json.dumps(document, ensure_ascii=False, indent=2))
    (root / "compiled_project.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    receipt = hf.render(result, root, root / "scene_ir_component.mp4", seconds=1.5)
    assert hf.verify_receipt(receipt, root)
    assert receipt["technical"]["original_audio_present"]
    assert receipt["technical"]["scene_engines"][0]["editable_dom_motion"] is True
    check = json.loads((root / receipt["technical"]["hyperframes"]["check_path"]).read_text())
    assert check["browserSkipped"] is False and check["ok"] is True
    assert receipt["technical"]["consecutive_frames_decoded"] == 18
    assert receipt["technical"]["original_voice_present"] and not receipt["technical"]["audio_listened"]
    assert result["scene_ir"]["status"] == "pending_qc" and not result["review"]
