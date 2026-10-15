"""SceneIR transaction, HTTP and queue contracts in a private test workspace."""
import copy
import json

import pytest

from studio import core, jobs, mcp, scene_ir_actions
from test_core import sandbox, valid_project
from test_api import api_workspace, fixture_media, http_server, request, real_project, cli_process


def document():
    return {"schema": "ascendia.sceneir/1", "content": {"text": "{{subject}} moves"},
            "narrative_goal": "Authored synthetic geometry, no verified CLONE equivalence",
            "family": "authored_transfer", "representation": "conceptual", "duration": 2,
            "composition": {"background": "#102030"}, "parameters": {"subject": "DATA"},
            "components": [{"id": "box", "type": "shape", "color": "#607080", "x": .1, "y": .3,
                            "width": .2, "height": .1},
                           {"id": "label", "type": "text", "text": "{{subject}}", "x": .1,
                            "y": .5, "width": .6, "height": .1}],
            "actions": [{"target_id": "box", "time": 0, "properties": {"x": .1}},
                        {"target_id": "box", "time": 2, "properties": {"x": .6}, "ease": "power2.out"}]}


def test_preview_no_writes_and_apply_is_optimistic_and_unapproved(sandbox):
    p = valid_project(sandbox)
    before = core.project_path(p["id"]).read_bytes()
    result = scene_ir_actions.preview(p["id"], document())
    assert result["can_apply"] and result["validation"]["valid"]
    assert core.project_path(p["id"]).read_bytes() == before
    assert result["project"]["source"] == p["source"]
    saved = scene_ir_actions.apply(p["id"], document(), p["revision"])
    assert saved["mode"] == "scene_ir_component" and len(saved["timeline"]) == 1
    assert saved["timeline"][0]["motion_design"]["elements"][1]["text"] == "DATA"
    assert not saved["review"] and not saved["approval_current"]
    assert saved["audio"] == p["audio"] and saved["transcript"] == p["transcript"]
    with pytest.raises(core.StudioError) as error:
        scene_ir_actions.apply(p["id"], document(), p["revision"])
    assert error.value.status == 409


@pytest.mark.parametrize("revision", [True, 1.5, "1", None, 0])
def test_apply_requires_integer_revision_without_writes(sandbox, revision):
    p = valid_project(sandbox); before = core.project_path(p["id"]).read_bytes()
    with pytest.raises(core.StudioError):
        scene_ir_actions.apply(p["id"], document(), revision)
    assert core.project_path(p["id"]).read_bytes() == before


def test_ordinary_edits_cannot_forge_mode_or_origin(sandbox):
    p = valid_project(sandbox); p.update(mode="scene_ir_component", scene_ir={"forged": True})
    p = core.save_project(p["id"], p)
    assert "mode" not in p and "scene_ir" not in p
    p = scene_ir_actions.apply(p["id"], document(), p["revision"])
    old = copy.deepcopy(p["scene_ir"])
    p["mode"] = "reel"; p["scene_ir"]["status"] = "approved"
    p["timeline"][0]["motion_design"]["elements"][0]["x"] = .2
    p = core.save_project(p["id"], p)
    assert p["mode"] == "scene_ir_component" and p["scene_ir"] == old


def test_component_render_uses_actual_length_without_component_approval(sandbox):
    p = valid_project(sandbox); p = scene_ir_actions.apply(p["id"], document(), p["revision"])
    job = jobs.submit(p["id"], "render", {"seconds": 10, "technical": False})
    assert job["options"]["seconds"] == 2 and job["options"]["technical"] is True
    assert job["options"]["component_qc"] == "pending"
    assert not core.approval_is_current(p)
    with pytest.raises(core.StudioError) as error:
        jobs.submit(p["id"], "render", {"seconds": 11})
    assert error.value.status == 409
    assert not core.validate_project(p, strict=True)["valid"]
    tasks = jobs.create_tasks(p["id"])
    assert len(tasks) == 5 and all(t["constraints"]["human_approval"] is False for t in tasks)
    assert all(t["constraints"]["auto_editorial_approval"] is False for t in tasks)
    assert "stock" in next(t for t in tasks if t["role"] == "resources")["purpose"]


@pytest.mark.parametrize("args", [{"kind":"video","original_graphic_author":"Fixture"},
                                 {"kind":"image","original_graphic_author":" "},
                                 {"kind":"image","original_graphic_author":"x"*501}])
def test_original_graphic_declaration_checks_author_before_import(sandbox, args):
    with pytest.raises(core.StudioError):
        mcp.call_tool("asset_import", {"path":"missing.png", **args})
    assert core.assets() == []


@pytest.mark.parametrize("path,value", [
    (("style",), []), (("style",), None), (("settings",), []), (("fonts",), []),
    (("transcript",), []), (("timeline",), [None]), (("audio",), [[]]), (("assets",), [None]),
    (("timeline", 0, "id"), []), (("timeline", 0, "template"), []),
    (("timeline", 0, "keyframes"), [None]), (("timeline", 0, "overlays"), [None]),
    (("timeline", 0, "decision"), []), (("source",), []),
])
def test_malformed_project_json_is_controlled_without_changes(sandbox, path, value):
    p = valid_project(sandbox); before = core.project_path(p["id"]).read_bytes()
    target = p
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(core.StudioError): core.save_project(p["id"], p)
    assert core.project_path(p["id"]).read_bytes() == before


def test_http_cli_mcp_share_scene_ir_contract(api_workspace, fixture_media, http_server):
    p = real_project(api_workspace, fixture_media); url = '/api/projects/' + p['id']
    before = core.project_path(p["id"]).read_bytes()
    status, _, schema = request(http_server, "GET", "/api/scene-ir/schema")
    assert status == 200 and schema["additionalProperties"] is False
    status, _, proposal = request(http_server, "POST", url + "/scene_ir_preview", {"document": document()})
    assert status == 200 and proposal["can_apply"]
    assert core.project_path(p["id"]).read_bytes() == before
    for value in ({"document": document(), "approve": True}, {"document": {"script": "alert(1)"}}):
        assert request(http_server, "POST", url + "/scene_ir_preview", value)[0] == 400
    assert request(http_server, "POST", url + "/scene_ir", {"document": document(), "expected_revision": True})[0] == 400
    status, _, saved = request(http_server, "POST", url + "/scene_ir", {"document": document(), "expected_revision": p["revision"]})
    assert status == 200 and saved["mode"] == "scene_ir_component"
    assert request(http_server, "POST", url + "/scene_ir", {"document": document(), "expected_revision": p["revision"]})[0] == 409
    invalid = copy.deepcopy(saved); invalid["style"] = []
    assert request(http_server, "PUT", url, invalid)[0] == 400
    assert {"scene_ir_schema", "scene_ir_preview", "scene_ir_apply"} <= {t["name"] for t in mcp.TOOLS}
    assert mcp.call_tool("scene_ir_preview", {"project_id": p["id"], "document": document()})["can_apply"]
    completed = cli_process(api_workspace, ["scene-ir-schema"])
    assert completed.returncode == 0 and json.loads(completed.stdout)["additionalProperties"] is False
