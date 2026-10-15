"""Queue/API contracts for person cutout; never changes customer productions."""
import copy
import fcntl
import threading

import pytest

from studio import core, jobs, media_tools, segmentation
from test_core import sandbox, valid_project
from test_api import api_workspace, fixture_media, http_server, request, real_project


@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setattr(segmentation, "capability", lambda root=None: {
        "available": True, "fingerprint": "fixture-model-v1", "verified_execution": False,
        "model_sha256": "1" * 64, "runtime_version": "fixture", "device": "cpu"})


def test_catalog_distinguishes_model_preparation_from_real_execution(sandbox, prepared):
    item = next(t for t in media_tools.catalog() if t["id"] == "remove_background_video")
    assert item["available"] and item["implemented"]
    assert not item["capability"]["verified_execution"]
    assert item["extension"] == ".mov" and item["limits"]["max_input_seconds"] == 30


def test_missing_model_rejected_before_queue(sandbox, monkeypatch):
    p = valid_project(sandbox)
    monkeypatch.setattr(segmentation, "capability", lambda root=None: {"available": False, "reason": "Fixture model missing"})
    with pytest.raises(core.StudioError, match="Fixture model missing") as error:
        jobs.submit_media(p["source"], "remove_background_video", {})
    assert error.value.status == 409 and jobs.list_jobs() == []
    item = next(t for t in media_tools.catalog() if t["id"] == "remove_background_video")
    assert item["implemented"] and not item["available"] and item["unavailable_reason"]


@pytest.mark.parametrize("options", [[], False, {"fps": True}, {"fps": 31}, {"max_width": 541},
                                     {"duration": 31}, {"softness": 0}, {"temporal_smoothing": 1},
                                     {"model_url": "https://example.invalid/model"}])
def test_bad_options_never_enqueue(sandbox, prepared, options):
    p = valid_project(sandbox)
    with pytest.raises(core.StudioError): jobs.submit_media(p["source"], "remove_background_video", options)
    assert jobs.list_jobs() == []


def test_model_changed_while_queued_never_runs_processor(sandbox, prepared, monkeypatch):
    p = valid_project(sandbox)
    job = jobs.submit_media(p["source"], "remove_background_video", {"duration": 1})
    monkeypatch.setattr(segmentation, "capability", lambda root=None: {"available": True, "fingerprint": "fixture-model-v2"})
    monkeypatch.setattr(media_tools, "process", lambda *args, **kwargs: pytest.fail("changed model must not run"))
    jobs.execute(job["id"])
    result = jobs.get_job(job["id"])
    assert result["status"] == "failed" and "cambió" in result["error"]


def test_direct_cpu_wait_can_be_cancelled_without_entering_processor(sandbox):
    cancel = threading.Event(); entered = threading.Event(); failures = []
    with core.confined('.estado/cpu_worker.lock').open('a+b') as owner:
        fcntl.flock(owner.fileno(), fcntl.LOCK_EX)
        def wait():
            try:
                with jobs.cpu_slot(cancel=cancel): entered.set()
            except core.StudioError as error: failures.append(error)
        thread = threading.Thread(target=wait); thread.start(); cancel.set(); thread.join(timeout=2)
        assert not thread.is_alive() and not entered.is_set()
        assert failures and failures[0].status == 409
        fcntl.flock(owner.fileno(), fcntl.LOCK_UN)
    with jobs.cpu_slot():
        assert jobs.CPU_ACTIVE.active
    assert not jobs.CPU_ACTIVE.active


def test_cancel_checkpoint_stops_before_registration_or_attachment(sandbox, prepared, monkeypatch):
    p = valid_project(sandbox); before = core.project_path(p["id"]).read_bytes()
    job = jobs.submit_media(p["source"], "remove_background_video", {"duration": 1}, p["id"])
    def processor(*args, progress, cancel):
        progress(.25, "Fixture mask processed")
        jobs.cancel_job(job["id"])
        progress(.5, "Must stop now")
        pytest.fail("cancel checkpoint must raise")
    monkeypatch.setattr(media_tools, "process", processor)
    monkeypatch.setattr(jobs, "register_asset", lambda *args, **kwargs: pytest.fail("cancelled output must not register"))
    jobs.execute(job["id"])
    result = jobs.get_job(job["id"])
    assert result["status"] == "cancelled" and not result.get("error")
    assert core.project_path(p["id"]).read_bytes() == before


def test_changed_project_retains_derivative_without_attaching_to_new_edit(sandbox, prepared, monkeypatch):
    p = valid_project(sandbox)
    job = jobs.submit_media(p["source"], "remove_background_video", {"duration": 1}, p["id"])
    row = copy.deepcopy(p["assets"][0]); row.update(id="fixture_derived", path="assets/video/derived.mov")
    def processor(*args, progress, cancel):
        live = core.get_project(p["id"]); live["name"] = "Concurrent edit preserved"; core.save_project(p["id"], live)
        progress(1, "Fixture processor completed")
        return {"operation": "remove_background_video", "kind": "process", "path": row["path"],
                "sha256": row["sha256"], "provenance": {"source_sha256": p["assets"][0]["sha256"]}}
    core.confined(row["path"]).write_bytes(b"fixture source media - never decoded")
    monkeypatch.setattr(media_tools, "process", processor)
    monkeypatch.setattr(jobs, "register_asset", lambda *args, **kwargs: row)
    monkeypatch.setattr(media_tools, "bind_canonical", lambda result, asset, root=None: result)
    monkeypatch.setattr(jobs, "attach_asset", lambda *args, **kwargs: pytest.fail("must not attach after concurrent edit"))
    jobs.execute(job["id"])
    result = jobs.get_job(job["id"])
    assert result["status"] == "completed"
    assert result["result"]["project_attachment"]["attached"] is False
    assert result["result"]["project_attachment"]["reason"] == "project_changed"
    live = core.get_project(p["id"])
    assert live["name"] == "Concurrent edit preserved" and row["id"] not in {a["id"] for a in live["assets"]}


def test_removed_background_cannot_pass_narrative_gate_even_through_proxy_lineage(sandbox):
    p = valid_project(sandbox); source = p["assets"][0]
    removed = {"id": "removed", "sha256": "f" * 64,
               "metadata": {"provenance": {"operation": "remove_background_video", "source_asset_id": "previous_source"}}}
    source["metadata"] = {"provenance": {"operation": "proxy_video", "source_asset_id": "removed"}}
    core.atomic_json('.estado/assets.json', [source, removed])
    assert core.source_background_removed(source, core.assets())
    assert any("fondo auténtico" in error for error in core.validate_project(p, strict=True)["errors"])
    assert not any("fondo auténtico" in error for error in core.validate_project(p, strict=False)["errors"])


def test_http_exposes_real_capability_and_validates_before_enqueue(api_workspace, fixture_media, http_server, prepared):
    p = real_project(api_workspace, fixture_media)
    status, _, listing = request(http_server, "GET", "/api/media-tools")
    tool = next(t for t in listing["operations"] if t["id"] == "remove_background_video")
    assert status == 200 and tool["available"] and not tool["capability"]["verified_execution"]
    url = "/api/assets/" + p["source"] + "/process"
    assert request(http_server, "POST", url, {"operation": "remove_background_video", "options": {"fps": True}})[0] == 400
    assert jobs.list_jobs() == []
    status, _, job = request(http_server, "POST", url, {"operation": "remove_background_video", "options": {"duration": 1}, "project_id": p["id"]})
    assert status == 202 and job["project_revision"] == p["revision"]
    assert job["segmentation_fingerprint"] == "fixture-model-v1" and job["options"]["fps"] == 30
