"""HTTP/CLI/MCP share protected design and facial-measurement contracts."""
import json

from studio import core, jobs, mcp
from test_api import api_workspace, fixture_media, http_server, request, real_project, cli_process


def custom(root, source):
    p = real_project(root, source)
    p["timeline"] = [{"id": "free", "type": "motion", "template": "custom", "start": 0, "end": 12,
                      "motion_design": {"elements": [{"id": "box", "type": "shape", "color": "#ffffff"}]}}]
    return core.save_project(p["id"], p)


def test_http_static_png_and_notes_do_not_approve(api_workspace, fixture_media, http_server):
    p = custom(api_workspace, fixture_media)
    url = "/api/projects/" + p["id"]
    status, _, job = request(http_server, "POST", url + "/design_snapshot", {"scene_id": "free"})
    assert status == 202
    jobs.execute(job["id"])
    result = jobs.get_job(job["id"])
    assert result["status"] == "completed", result
    snapshot = result["result"]
    assert snapshot["approved"] is False
    status, headers, image = request(http_server, "GET", snapshot["url"])
    assert status == 200 and headers["Content-Type"].startswith("image/png") and image[:8] == b"\x89PNG\r\n\x1a\n"
    review = {"scene_id": "free", "expected_sha256": snapshot["sha256"], "reviewer": "Test fixture", "notes": "Geometry checked, no client approval", "approve_design": False}
    status, _, saved = request(http_server, "POST", url + "/design_review", review)
    assert status == 200 and saved["design_reviews"]["free"]["approved"] is False
    assert not saved["review"] and saved["approval_current"] is False
    status, _, listing = request(http_server, "GET", url + "/designs")
    assert status == 200 and listing["snapshots"]["free"]["sha256"] == snapshot["sha256"]
    assert listing["errors"]
    review["expected_sha256"] = "0" * 64
    assert request(http_server, "POST", url + "/design_review", review)[0] == 409
    review["approve_design"] = "true"
    assert request(http_server, "POST", url + "/design_review", review)[0] == 400


def test_http_tracking_readouts_and_option_validation(api_workspace, fixture_media, http_server):
    p = custom(api_workspace, fixture_media)
    url = "/api/projects/" + p["id"]
    status, _, value = request(http_server, "GET", url + "/tracking")
    assert status == 200 and value == {"tracking": None, "automatic_application": False}
    status, _, value = request(http_server, "GET", url + "/tracking_proposals")
    assert status == 200 and value["valid"] is False and value["read_only"] is True
    for options in ({"sample_fps": True}, {"apply_automatically": True}, {"start": 3, "end": 2}):
        assert request(http_server, "POST", url + "/tracking", options)[0] == 400
    assert jobs.list_jobs() == []


def test_cli_and_mcp_expose_same_new_contracts(api_workspace, fixture_media):
    p = custom(api_workspace, fixture_media)
    completed = cli_process(api_workspace, ["tracking-proposals", p["id"]])
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["valid"] is False and result["read_only"] is True
    listed = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert {"face_tracking", "tracking_proposals", "design_snapshot", "design_review"}.issubset({t["name"] for t in listed["result"]["tools"]})
    response = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "tracking_proposals", "arguments": {"project_id": p["id"]}}})
    assert response["result"]["isError"] is False
    assert json.loads(response["result"]["content"][0]["text"])["valid"] is False
    response = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "design_review", "arguments": {"project_id": p["id"], "review": {"approve_design": True}}}})
    assert response["result"]["isError"] is True
