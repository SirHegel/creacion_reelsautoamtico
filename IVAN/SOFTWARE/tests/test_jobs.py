"""Persisted queue and agent workflow regressions; no real workers/models."""
from __future__ import annotations

import copy
import csv
import threading

import pytest

from studio import analysis, core, jobs, render
from test_core import sandbox, valid_project


def test_submit_rejects_duplicate_active_job(sandbox):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {"transcribe": False})
    with pytest.raises(core.StudioError) as error:
        jobs.submit(p["id"], "analyze", {"transcribe": False})
    assert error.value.status == 409
    assert [job["id"] for job in jobs.list_jobs()] == [j["id"]]


@pytest.mark.parametrize("duration", [float("nan"), float("inf"), -1, 0, 86401])
def test_submit_rejects_nonfinite_or_out_of_range_render_duration(sandbox, duration):
    p = valid_project(sandbox)
    with pytest.raises(core.StudioError, match="Duración de render inválida"):
        jobs.submit(p["id"], "render", {"seconds": duration})
    assert jobs.list_jobs() == []


def test_complete_render_stays_blocked_without_authorization(sandbox):
    p = valid_project(sandbox)
    with pytest.raises(core.StudioError) as error:
        jobs.submit(p["id"], "render", {"seconds": 12})
    assert error.value.status == 409
    assert jobs.list_jobs() == []


def test_changed_revision_fails_before_analysis_runs(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {"transcribe": False})
    p["name"] = "edit while queued"
    core.save_project(p["id"], p)
    monkeypatch.setattr(analysis, "analyze_project", lambda *args: pytest.fail("Stale job must never analyze"))
    jobs.execute(j["id"])
    assert jobs.get_job(j["id"])["status"] == "failed"


def test_queued_cancellation_does_not_run_backend(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {"transcribe": False})
    jobs.cancel_job(j["id"])
    monkeypatch.setattr(analysis, "analyze_project", lambda *args: pytest.fail("Cancelled job must never analyze"))
    jobs.execute(j["id"])
    assert jobs.get_job(j["id"])["status"] == "cancelled"
    assert core.get_project(p["id"])["revision"] == p["revision"]


def test_backend_error_is_persisted_with_local_log(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {"transcribe": False})

    def fail(*args):
        raise core.StudioError("Fixture decode failure")

    monkeypatch.setattr(analysis, "analyze_project", fail)
    jobs.execute(j["id"])
    result = jobs.get_job(j["id"])
    assert result["status"] == "failed"
    assert result["error"] == "Fixture decode failure"
    assert (sandbox / ".estado/logs" / f"{j['id']}.log").is_file()
    assert core.get_project(p["id"])["revision"] == p["revision"]


def test_render_revalidates_manual_changed_after_submission(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "render", {"seconds": 10})
    (sandbox.parent / "PROMPT_MAESTRO.md").write_text("Changed fixture instructions", encoding="utf-8")
    called = []

    def fake_render(project, root, output, **kwargs):
        called.append(True)
        output.write_bytes(b"fixture render")
        return {"sha256": core.digest(output), "duration": 10., "used_assets": []}

    monkeypatch.setattr(render, "render", fake_render)
    jobs.execute(j["id"])
    assert not called, "Manual gates must be checked before executing the renderer, not only at submit"
    assert jobs.get_job(j["id"])["status"] == "failed"


def test_edit_during_render_conserves_candidate_without_promoting(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "render", {"seconds": 10})

    def fake_render(project, root, output, **kwargs):
        output.write_bytes(b"fixture stale render")
        changed = core.get_project(project["id"])
        changed["timeline"][1]["title"] = "Changed while rendering"
        core.save_project(project["id"], changed)
        return {"sha256": core.digest(output), "duration": 10., "used_assets": []}

    monkeypatch.setattr(render, "render", fake_render)
    jobs.execute(j["id"])
    result = jobs.get_job(j["id"])
    assert result["status"] == "failed"
    assert result["details"]["stale"] is True
    assert (sandbox / result["details"]["path"]).is_file()
    current = core.get_project(p["id"])
    assert current["timeline"][1]["title"] == "Changed while rendering"
    assert not current["renders"] and not current["review"]


def test_media_bytes_changed_during_render_invalidate_the_receipt(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "render", {"seconds": 10})

    def fake_render(project, root, output, **kwargs):
        output.write_bytes(b"fixture rendered from initial source")
        core.confined(project["assets"][0]["path"]).write_bytes(b"media changed while render was in progress")
        return {"sha256": core.digest(output), "duration": 10., "used_assets": []}

    monkeypatch.setattr(render, "render", fake_render)
    jobs.execute(j["id"])
    result = jobs.get_job(j["id"])
    assert result["status"] == "failed", "Receipt must bind to the pre-render bytes, not post-render hashes"
    assert not core.get_project(p["id"])["renders"]


def test_media_bytes_changed_during_analysis_do_not_promote_transcript(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {"transcribe": False})

    def fake_analysis(project, options, progress, event):
        core.confined(project["assets"][0]["path"]).write_bytes(b"source changed during analysis")
        project["transcript"]["segments"][0]["text"] = "Stale analysis result"
        return project

    monkeypatch.setattr(analysis, "analyze_project", fake_analysis)
    jobs.execute(j["id"])
    assert jobs.get_job(j["id"])["status"] == "failed"
    assert core.get_project(p["id"])["transcript"]["segments"][0]["text"] == "Fixture narration"


def test_agent_roles_wait_for_dependencies_and_have_distinct_artifacts(sandbox):
    p = valid_project(sandbox)
    workflow = jobs.create_tasks(p["id"])
    assert len({task["artifact"] for task in workflow}) == len(workflow)
    assert jobs.claim_task("motion", "fixture agent").get("task") is None
    director = jobs.claim_task("director", "director agent")
    assert director["status"] == "claimed"
    finished = jobs.finish_task(director["id"], director["lease"], {"observations": "Fixture read", "evidence": [".estado/tmp/reference.txt"]})
    assert finished["status"] == "done"
    resources = jobs.claim_task("resources", "resource agent")
    assert resources["status"] == "claimed"
    assert jobs.claim_task("motion", "fixture agent").get("task") is None


def test_task_lease_and_evidence_are_checked_before_mutation(sandbox):
    p = valid_project(sandbox)
    jobs.create_tasks(p["id"])
    t = jobs.claim_task("director", "fixture agent")
    for lease, evidence in (("wrong", ".estado/tmp/reference.txt"), (t["lease"], "../PROMPT_MAESTRO.md"), (t["lease"], ".estado/tmp/missing.txt")):
        with pytest.raises(core.StudioError):
            jobs.finish_task(t["id"], lease, {"observations": "Fixture result", "evidence": [evidence]})
    assert not (sandbox / t["artifact"]).exists()
    assert next(x for x in jobs.tasks() if x["id"] == t["id"])["status"] == "claimed"


def test_task_cannot_complete_after_project_content_changes(sandbox):
    p = valid_project(sandbox)
    jobs.create_tasks(p["id"])
    t = jobs.claim_task("director", "fixture agent")
    p["timeline"][1]["title"] = "Different narrative now"
    core.save_project(p["id"], p)
    with pytest.raises(core.StudioError) as error:
        jobs.finish_task(t["id"], t["lease"], {"observations": "Old narrative analyzed", "evidence": [".estado/tmp/reference.txt"]})
    assert error.value.status == 409
    assert not (sandbox / t["artifact"]).exists()


def test_new_workflow_replaces_stale_tasks_instead_of_deadlocking(sandbox):
    p = valid_project(sandbox)
    old = jobs.create_tasks(p["id"])
    claimed = jobs.claim_task("director", "old fixture agent")
    p["timeline"][1]["title"] = "New narrative"
    core.save_project(p["id"], p)
    fresh = jobs.create_tasks(p["id"])
    assert {t["id"] for t in old}.isdisjoint(t["id"] for t in fresh)
    director = jobs.claim_task("director", "new fixture agent")
    assert director["id"] != claimed["id"]
    assert director["workflow_id"] == fresh[0]["workflow_id"]


def test_manifest_uses_actual_ranges_for_repeated_asset(sandbox):
    p = valid_project(sandbox)
    broll = copy.deepcopy(p["assets"][0])
    broll_path = sandbox / "assets/broll/broll.mp4"
    broll_path.write_bytes(b"fixture broll media")
    broll.update(id="a_broll", name="broll.mp4", path="assets/broll/broll.mp4", kind="broll", sha256=core.digest(broll_path))
    p["assets"].append(broll)
    p["timeline"] = [
        {"id": "a", "start": 0., "end": 2., "type": "motion", "title": "Hook"},
        {"id": "b", "start": 2., "end": 4., "type": "broll", "asset_id": broll["id"], "title": "First use"},
        {"id": "c", "start": 4., "end": 11., "type": "motion", "title": "Process"},
        {"id": "d", "start": 11., "end": 12., "type": "broll", "asset_id": broll["id"], "title": "Outside preview"},
    ]
    receipt = {"duration": 10., "used_assets": [{"asset_id": broll["id"], "role": "broll", "start": 2., "end": 4.}]}
    manifest = jobs.write_manifest(p, receipt)
    with manifest.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    outside = next(row for row in rows if "11" in row["tiempo_previsto"])
    assert outside["tiempo_realmente_usado"].startswith("0"), outside
    inside = next(row for row in rows if row["frase"] == "First use")
    assert "2" in inside["tiempo_realmente_usado"] and "4" in inside["tiempo_realmente_usado"]
