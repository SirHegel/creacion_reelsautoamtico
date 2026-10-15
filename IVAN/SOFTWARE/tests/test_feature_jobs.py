"""New feature queue boundaries; fixtures never represent customer approval."""
import copy

import pytest

from studio import core, jobs, tracking, design_review
from test_core import sandbox, valid_project

REAL_PRODUCTION_ERRORS = core.production_motion_errors


def free_project(root):
    p = valid_project(root)
    p["timeline"] = [{"id": "free", "type": "motion", "template": "custom", "start": 0, "end": 12,
                      "motion_design": {"elements": [{"id": "box", "type": "shape"}]}}]
    return core.save_project(p["id"], p)


@pytest.mark.parametrize("engine", ["hyperframes", "invalid", True])
def test_render_engine_must_match_saved_choice(sandbox, engine):
    p = valid_project(sandbox)
    with pytest.raises(core.StudioError, match="motor|Motor"):
        jobs.submit(p["id"], "render", {"seconds": 2, "technical": True, "engine": engine})
    assert jobs.list_jobs() == []


def test_boolean_render_duration_is_not_one_second(sandbox):
    p = valid_project(sandbox)
    with pytest.raises(core.StudioError, match="Duración"):
        jobs.submit(p["id"], "render", {"seconds": True, "technical": True})


def test_changed_server_code_requires_restart_before_queue_or_execution(sandbox, monkeypatch):
    p = free_project(sandbox)
    queued = jobs.submit(p["id"], "tracking", {})
    monkeypatch.setattr(jobs, "engine_fingerprints", lambda: {"changed.py": "new implementation"})
    with pytest.raises(core.StudioError, match="reinicia"):
        jobs.submit(p["id"], "tracking", {})
    monkeypatch.setattr(tracking, "analyze_tracking", lambda *a: pytest.fail("old imported code must not run"))
    jobs.execute(queued["id"])
    assert jobs.get_job(queued["id"])["status"] == "failed"
    assert not core.get_project(p["id"]).get("tracking")


def test_native_motion_upper_split_cannot_pass_narrative_gate(sandbox):
    p = valid_project(sandbox)
    # Call the original implementation; fixture normally isolates this gate.
    errors = REAL_PRODUCTION_ERRORS(p)
    assert any("recurso superior real" in error for error in errors)


@pytest.mark.parametrize("field", ["tracking", "design_reviews", "design_snapshots"])
def test_project_updates_cannot_inject_feature_evidence(sandbox, field):
    p = free_project(sandbox)
    p[field] = {"approved": True, "sha256": "forged"}
    saved = core.save_project(p["id"], p)
    assert field not in saved
    actual = {"private_receipt": "fixture from dedicated endpoint"}
    saved[field] = actual
    core.atomic_json(core.project_path(p["id"]), saved)
    saved[field] = {"approved": True}
    assert core.save_project(p["id"], saved)[field] == actual


@pytest.mark.parametrize("options", [{}, {"scene_id": "absent"}, {"scene_id": "free", "approve": True}, {"scene_id": True}])
def test_snapshot_only_accepts_current_custom_scene(sandbox, options):
    p = free_project(sandbox)
    with pytest.raises(core.StudioError):
        jobs.submit(p["id"], "design_snapshot", options)


def test_manual_change_blocks_capture_before_queueing(sandbox):
    p = free_project(sandbox)
    (sandbox.parent / "PROMPT_MAESTRO.md").write_text("changed fixture instructions")
    with pytest.raises(core.StudioError, match="manual"):
        jobs.submit(p["id"], "design_snapshot", {"scene_id": "free"})


@pytest.mark.parametrize("action", ["tracking", "design_snapshot"])
def test_dedicated_results_are_protected_and_leave_review_pending(sandbox, monkeypatch, action):
    p = free_project(sandbox)
    result = {"fixture": True, "approved": False}
    if action == "tracking":
        monkeypatch.setattr(tracking, "analyze_tracking", lambda *args: copy.deepcopy(result))
        options, field = {}, "tracking"
    else:
        monkeypatch.setattr(design_review, "make_snapshot", lambda *args: copy.deepcopy(result))
        options, field = {"scene_id": "free"}, "design_snapshots"
    job = jobs.submit(p["id"], action, options)
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "completed"
    saved = core.get_project(p["id"])
    evidence = saved[field] if action == "tracking" else saved[field]["free"]
    assert evidence == result
    assert not saved["review"] and not saved["renders"]


@pytest.mark.parametrize("action", ["tracking", "design_snapshot"])
@pytest.mark.parametrize("change", ["revision", "source", "manual"])
def test_changed_inputs_during_measurement_cannot_promote_results(sandbox, monkeypatch, action, change):
    p = free_project(sandbox)
    def backend(*args):
        if change == "revision":
            live = core.get_project(p["id"])
            live["name"] = "newer edit"
            core.save_project(p["id"], live)
        elif change == "source":
            core.confined(p["assets"][0]["path"]).write_bytes(b"source changed in flight")
        else:
            (sandbox.parent / "PROMPT_MAESTRO.md").write_text("new fixture rules")
        return {"fixture_stale": True}
    options = {} if action == "tracking" else {"scene_id": "free"}
    monkeypatch.setattr(tracking if action == "tracking" else design_review,
                        "analyze_tracking" if action == "tracking" else "make_snapshot", backend)
    job = jobs.submit(p["id"], action, options)
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "failed"
    assert not core.get_project(p["id"]).get("tracking" if action == "tracking" else "design_snapshots")
