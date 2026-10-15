"""Real private HTTP/MCP review endpoints; queue execution is explicit here.

Samples use an actual private PNG. No model, narrative renderer, live account,
or automatic editorial approval participates in this protocol audit.
"""
import copy
from http.client import HTTPConnection
import json
import queue

import pytest
from PIL import Image

from studio import analysis, core, jobs, mcp, resource_review as review, server
from test_resource_review import observed
from test_workspace_api import workspace_api


@pytest.fixture
def resource_api(workspace_api, monkeypatch):
    listener, root = workspace_api
    for module in (analysis, jobs):
        monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
    monkeypatch.setattr(jobs, "QUEUE", queue.Queue())
    monkeypatch.setattr(jobs, "CANCEL", {})
    monkeypatch.setattr(jobs, "WORKER", None)
    monkeypatch.setattr(jobs, "start_worker", lambda: None)
    monkeypatch.setattr(jobs, "LOADED_ENGINE_FINGERPRINTS", core.engine_fingerprints())
    own = root / ".estado/tmp/own_http_resource.png"
    Image.new("RGBA", (64, 96), (200, 25, 20, 255)).save(own)
    item = core.register_asset(own, kind="image", metadata={"source": "private_synthetic_protocol_fixture"})
    return listener, root, item


def http(listener, method, path, body=None, *, headers=None, raw=None, token="fixture-backend-token"):
    connection = HTTPConnection("127.0.0.1", listener.server_port, timeout=10)
    values = {"X-Ascendia-Backend": token}
    values.update(headers or {})
    payload = raw if raw is not None else json.dumps(body).encode() if body is not None else None
    if payload is not None:
        values.setdefault("Content-Type", "application/json")
    try:
        connection.request(method, path, body=payload, headers=values)
        response = connection.getresponse()
        content = response.read()
        data = json.loads(content) if content and (response.getheader("Content-Type") or "").startswith("application/json") else content
        return response.status, dict(response.getheaders()), data
    finally:
        connection.close()


def route(item, suffix="review"):
    return "/api/assets/" + item["id"] + "/" + suffix


def rpc(listener, name, arguments):
    status, _, response = http(listener, "POST", "/api/mcp", {"jsonrpc": "2.0", "id": 73,
        "method": "tools/call", "params": {"name": name, "arguments": arguments}})
    assert status == 200 and response["id"] == 73
    payload = response["result"]
    return payload["isError"], json.loads(payload["content"][0]["text"])


def test_real_http_get_head_and_current_sample_range(resource_api):
    listener, root, item = resource_api
    status, _, state = http(listener, "GET", route(item))
    assert status == 200 and state["valid"] is False
    prepared = review.prepare(item["id"])
    media = route(item, "review-files/frame_00.png")
    actual = (root / prepared["frames"][0]["path"]).read_bytes()
    status, headers, content = http(listener, "GET", media)
    assert status == 200 and content == actual
    assert headers["Content-Type"] == "image/png" and int(headers["Content-Length"]) == len(actual)
    status, headers, content = http(listener, "HEAD", media)
    assert status == 200 and content == b"" and int(headers["Content-Length"]) == len(actual)
    status, headers, content = http(listener, "GET", media, headers={"Range": "bytes=0-7"})
    assert status == 206 and content == actual[:8]
    assert headers["Content-Range"] == "bytes 0-7/" + str(len(actual))
    status, headers, content = http(listener, "HEAD", route(item))
    assert status == 200 and content == b"" and int(headers["Content-Length"]) > 0
    assert not core.asset(item["id"])["verification"]["visual"]


def test_real_http_record_is_scoped_observation_not_editorial_approval(resource_api):
    listener, _, item = resource_api
    prepared = review.prepare(item["id"])
    status, _, result = http(listener, "POST", route(item), observed(prepared))
    assert status == 200 and result["review"]["scope"] == "observed_samples"
    assert result["editorial_approved"] is False and result["reel_approved"] is False
    assert result["review"]["rights_authority"] is False and result["review"]["audio_listened"] is False
    status, _, current = http(listener, "GET", route(item))
    assert status == 200 and current["valid"] is True and current["coverage"] == "points_only"
    assert http(listener, "POST", route(item), observed(prepared))[0] == 409
    assert core.project_list() == []


@pytest.mark.parametrize("name", ["receipt.json", "review.json", "../receipt.json", "unknown.png", "frame_11.png"])
def test_http_sample_route_never_serves_private_or_unprepared_files(resource_api, name):
    listener, _, item = resource_api
    review.prepare(item["id"])
    for method in ("GET", "HEAD"):
        assert http(listener, method, route(item, "review-files/" + name))[0] in {400, 403, 404, 409}


def test_http_evidence_revalidates_actual_bytes_and_source(resource_api):
    listener, root, item = resource_api
    prepared = review.prepare(item["id"])
    path = root / prepared["frames"][0]["path"]
    path.write_bytes(b"changed evidence bytes")
    assert http(listener, "GET", route(item, "review-files/frame_00.png"))[0] == 409
    assert http(listener, "POST", route(item), observed(prepared))[0] == 409
    assert core.asset(item["id"])["verification"]["visual"] is False


@pytest.mark.parametrize("options", [{"samples": True}, {"duration": float("nan")}, {"max_width": 159},
    {"unknown": "ignored?"}, {"start": False}, {"sequence": "true"}, {"samples": 13}, {"duration": 31}])
def test_http_async_prepare_closed_options_no_job_for_invalid_request(resource_api, options):
    listener, _, item = resource_api
    before = copy.deepcopy(jobs.list_jobs())
    assert http(listener, "POST", route(item, "review-prepare"), options)[0] == 400
    assert jobs.list_jobs() == before


def test_actual_async_prepare_queue_duplicate_cancel_and_manual_worker_execution(resource_api):
    listener, _, item = resource_api
    status, _, job = http(listener, "POST", route(item, "review-prepare"), {"samples": 1})
    assert status == 202 and job["status"] == "queued" and job["action"] == "asset_review_prepare"
    assert job["project_id"] is None and job["asset_id"] == item["id"]
    assert not core.asset(item["id"])["verification"]["visual"]
    assert http(listener, "POST", route(item, "review-prepare"), {})[0] == 409
    jobs.cancel_job(job["id"])
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "cancelled"
    status, _, next_job = http(listener, "POST", route(item, "review-prepare"), {"samples": 1})
    assert status == 202
    # No worker daemon is started by this fixture. This executes the real
    # production queue action once in the private store, not a mocked decoder.
    jobs.execute(next_job["id"])
    completed = jobs.get_job(next_job["id"])
    assert completed["status"] == "completed", completed
    assert completed["result"]["status"] == "pending"
    assert completed["result"]["visual_reviewed"] is False
    assert completed["result"]["frames"][0]["path"].startswith(".estado/resource_reviews/")
    assert http(listener, "GET", route(item, "review-files/frame_00.png"))[0] == 200
    assert core.project_list() == []


@pytest.mark.parametrize("method,suffix", [("GET", "review"), ("HEAD", "review"), ("POST", "review"),
    ("POST", "review-prepare"), ("GET", "review-files/frame_00.png")])
def test_worker_secret_required_for_every_review_operation(resource_api, method, suffix):
    listener, _, item = resource_api
    assert http(listener, method, route(item, suffix), {} if method == "POST" else None, token="")[0] == 401


def test_mcp_tools_real_read_record_and_closed_top_level_arguments(resource_api):
    listener, _, item = resource_api
    status, _, tools = http(listener, "POST", "/api/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert status == 200
    names = {tool["name"] for tool in tools["result"]["tools"]}
    assert {"resource_review_prepare", "resource_review_get", "resource_review_record"} <= names
    bad, result = rpc(listener, "resource_review_get", {"asset_id": item["id"]})
    assert not bad and result["valid"] is False
    prepared = review.prepare(item["id"])
    bad, result = rpc(listener, "resource_review_record", {"asset_id": item["id"], "review": observed(prepared)})
    assert not bad and result["editorial_approved"] is False
    bad, result = rpc(listener, "resource_review_get", {"asset_id": item["id"]})
    assert not bad and result["valid"] is True and result["scope"] == "observed_samples"
    for name in ("resource_review_get", "resource_review_prepare", "resource_review_record"):
        arguments = {"asset_id": item["id"], "root": "/outside"}
        if name == "resource_review_record":
            arguments["review"] = observed(prepared)
        bad, result = rpc(listener, name, arguments)
        assert bad and "error" in result
    assert core.project_list() == []


@pytest.mark.parametrize("arguments", [{"asset_id": "a_missing", "options": {"samples": True}},
    {"asset_id": "a_missing", "options": {"unknown": 1}}, {"asset_id": True}, {"options": {}}, {"asset_id": "a_missing", "options": []}])
def test_mcp_prepare_bad_arguments_never_queue(resource_api, arguments):
    listener, _, item = resource_api
    if arguments.get("asset_id") == "a_missing":
        arguments = {**arguments, "asset_id": item["id"]}
    before = copy.deepcopy(jobs.list_jobs())
    bad, result = rpc(listener, "resource_review_prepare", arguments)
    assert bad and "error" in result
    assert jobs.list_jobs() == before


def test_mcp_queue_is_real_pending_action_until_fixture_executes_it(resource_api):
    listener, _, item = resource_api
    bad, job = rpc(listener, "resource_review_prepare", {"asset_id": item["id"], "options": {"samples": 1}})
    assert not bad and job["status"] == "queued"
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "completed"
    bad, result = rpc(listener, "resource_review_get", {"asset_id": item["id"]})
    assert not bad and result["valid"] is False
    assert core.asset(item["id"])["verification"]["visual"] is False


@pytest.mark.parametrize("change", ["extra_approval", "visual_integer", "wrapped_review", "missing_cas"])
def test_http_record_closed_payload_never_promotes_resource(resource_api, change):
    listener, _, item = resource_api
    prepared = review.prepare(item["id"])
    body = observed(prepared)
    if change == "extra_approval":
        body["approved"] = True
    elif change == "visual_integer":
        body["visual_reviewed"] = 1
    elif change == "wrapped_review":
        body = {"review": body}
    else:
        body.pop("expected_review_digest")
    assert http(listener, "POST", route(item), body)[0] == 400
    assert core.asset(item["id"])["verification"]["visual"] is False
    assert http(listener, "GET", route(item))[2]["valid"] is False


def test_workspace_project_put_cannot_forge_a_canonical_resource_observation(resource_api):
    listener, _, item = resource_api
    status, _, project = http(listener, "POST", "/api/projects", {"name": "Private anti-forgery protocol fixture"})
    assert status == 201
    status, _, project = http(listener, "POST", "/api/projects/" + project["id"] + "/assets", {"asset_id": item["id"]})
    assert status == 200
    row = next(a for a in project["assets"] if a["id"] == item["id"])
    row["verification"].update(visual=True, rights="source_verified", evidence=["anything"])
    row["metadata"].update(content="Inventado: recurso auténtico verificado por nombre y logo", visual_reviewed=True,
                           resource_review={"status": "observed", "visual_reviewed": True, "reel_approved": True})
    status, _, saved = http(listener, "PUT", "/api/projects/" + project["id"], project)
    assert status == 200, saved
    actual = next(a for a in saved["assets"] if a["id"] == item["id"])
    assert actual == core.asset(item["id"])
    assert actual["verification"]["visual"] is False
    assert not actual["metadata"].get("visual_reviewed") and not actual["metadata"].get("resource_review")
    assert http(listener, "GET", route(item))[2]["valid"] is False
    assert saved["review"] == {} and not saved.get("approved_export")
