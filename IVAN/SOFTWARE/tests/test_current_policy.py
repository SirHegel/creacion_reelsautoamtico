"""Current reference policy gates, using explicitly synthetic store fixtures.

These tests verify policy enforcement and invalidation, not HyperFrames/GSAP
integration, motion quality or a production approval. No actual reel is read.
"""
from __future__ import annotations

import copy
import json

import pytest

from studio import core, jobs
from test_core import sandbox, valid_project, add_receipt, approving_review

ORIGINAL_PRODUCTION_MOTION_ERRORS = core.production_motion_errors


def test_new_project_distinguishes_three_second_architecture_from_narrative_preview(sandbox):
    project = core.create_project("Synthetic current policy")
    assert project["style"]["identity"] == "YO"
    assert project["style"]["motion_references"] == ["CLONE"]
    assert project["style"]["technical_preview_seconds"] == 3
    assert project["style"]["preview_seconds"] == 10
    assert project["style"]["full_render"] == "requires_explicit_authorization"
    assert project["review"] == {} and project["renders"] == []


@pytest.mark.parametrize("field,value", [
    ("identity", "CLONE"),
    ("identity", "AGENT"),
    ("motion_references", ["AGENT", "EDIT", "CLONE"]),
    ("motion_references", ["CLONE", "EDIT"]),
    ("motion_references", ["AGENT"]),
    ("motion_references", []),
])
def test_strict_policy_rejects_old_or_mixed_references_but_draft_checks_remain_available(sandbox, field, value):
    project = valid_project(sandbox)
    assert core.validate_project(project, strict=True)["valid"]
    project["style"][field] = value
    strict = core.validate_project(project, strict=True)
    assert not strict["valid"]
    assert any("CLONE como referencia exclusiva" in message for message in strict["errors"])
    assert core.validate_project(project, strict=False)["valid"]
    saved = core.save_project(project["id"], project)
    assert saved["style"][field] == value and saved["review"] == {}


@pytest.mark.parametrize("change", ["missing_reference", "agent", "edit", "empty_observations", "empty_evidence", "missing_file", "escape", "symlink"])
def test_clone_review_requires_exact_reference_observations_and_real_confined_evidence(sandbox, change):
    project = valid_project(sandbox)
    review = project["reference_review"]
    if change == "missing_reference":
        review.pop("motion_reference")
    elif change in ("agent", "edit"):
        review["motion_reference"] = change.upper()
    elif change == "empty_observations":
        review["motion_observations"] = ""
    elif change == "empty_evidence":
        review["motion_evidence"] = []
    elif change == "missing_file":
        review["motion_evidence"] = [".estado/tmp/no_such_observation.txt"]
    else:
        outside = sandbox.parent / "outside_fixture_observation.txt"
        outside.write_text("Only a synthetic sentinel outside the fixture app root", encoding="utf-8")
        if change == "symlink":
            (sandbox / ".estado/tmp/linked_observation.txt").symlink_to(outside)
            review["motion_evidence"] = [".estado/tmp/linked_observation.txt"]
        else:
            review["motion_evidence"] = ["../outside_fixture_observation.txt"]
    result = core.validate_project(project, strict=True)
    assert not result["valid"]
    assert any("CLONE" in error for error in result["errors"])
    assert core.validate_project(project, strict=False)["valid"]


def test_missing_clone_evidence_blocks_narrative_approval_even_with_all_review_flags(sandbox):
    project = valid_project(sandbox)
    project["reference_review"]["motion_reference"] = "AGENT"
    project = core.save_project(project["id"], project)
    project, output = add_receipt(project, sandbox)
    before = core.project_path(project["id"]).read_bytes()
    export_before = output.read_bytes()
    with pytest.raises(core.StudioError) as error:
        core.record_review(project["id"], approving_review())
    assert error.value.status == 409
    assert any("CLONE" in message for message in error.value.details["errors"])
    assert core.project_path(project["id"]).read_bytes() == before
    assert output.read_bytes() == export_before
    assert not (output.parent / "approved_preview.mp4").exists()


def test_missing_clone_evidence_blocks_production_queue_without_executing_a_renderer(sandbox):
    project = valid_project(sandbox)
    project["reference_review"].pop("motion_evidence")
    project = core.save_project(project["id"], project)
    with pytest.raises(core.StudioError) as error:
        jobs.submit(project["id"], "render", {"seconds": 10})
    assert error.value.status == 409
    assert any("CLONE" in message for message in error.value.details["errors"])
    assert jobs.list_jobs() == []


def test_explicit_manual_refresh_updates_policy_invalidates_review_and_leases_without_rewriting_history(sandbox):
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox)
    project = core.record_review(project["id"], approving_review())
    historical_renders = copy.deepcopy(project["renders"])
    historical_export = copy.deepcopy(project["approved_export"])
    approved_file = core.confined(historical_export["path"])
    approved_bytes = approved_file.read_bytes()
    historical_audit = sandbox / ".estado/tmp/historical_audit.json"
    historical_audit.write_text(json.dumps({"manual": project["manual"], "render_sha256": historical_export["sha256"], "fixture_only": True}), encoding="utf-8")
    audit_bytes = historical_audit.read_bytes()

    # Simulate a previously stored policy, not an edit approved under new rules.
    project["style"].update(identity="Legacy identity", motion_references=["AGENT", "EDIT", "CLONE"])
    project["style"].pop("technical_preview_seconds", None)
    project["full_authorization"] = {"authorized": True, "editorial_digest": core.editorial_digest(project)}
    core.atomic_json(core.project_path(project["id"]), project)
    jobs.create_tasks(project["id"])
    claim = jobs.claim_task("director", "Synthetic historical agent")
    (sandbox.parent / "PROMPT_MAESTRO.md").write_text("Changed fixture instruction: CLONE exclusive; architecture 3 seconds", encoding="utf-8")
    expected = {name: info["sha256"] for name, info in core.manual_fingerprints().items()}
    refreshed = core.refresh_manual(project["id"], expected)

    assert refreshed["style"]["identity"] == "YO" and refreshed["style"]["motion_references"] == ["CLONE"]
    assert refreshed["style"]["technical_preview_seconds"] == 3 and refreshed["style"]["preview_seconds"] == 10
    assert refreshed["manual"] == core.manual_fingerprints()
    assert refreshed["review"] == {} and not refreshed.get("full_authorization")
    assert refreshed["renders"] == historical_renders and refreshed["approved_export"] == historical_export
    assert approved_file.read_bytes() == approved_bytes and historical_audit.read_bytes() == audit_bytes
    assert refreshed["history"][-1]["action"] == "manual_refreshed_after_reading"
    with pytest.raises(core.StudioError, match="proyecto o el manual cambió") as error:
        jobs.finish_task(claim["id"], claim["lease"], {"observations": "Stale fixture work", "evidence": [".estado/tmp/reference.txt"]})
    assert error.value.status == 409
    assert not core.confined(claim["artifact"]).exists()
    new_tasks = jobs.create_tasks(project["id"])
    assert all(task["workflow_id"] != claim["workflow_id"] for task in new_tasks)
    assert next(task for task in jobs.tasks() if task["id"] == claim["id"])["status"] == "stale"


def test_three_second_architecture_receipt_cannot_approve_ten_second_narrative(sandbox):
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox, duration=3)
    with pytest.raises(core.StudioError, match="primeros diez segundos") as error:
        core.record_review(project["id"], approving_review())
    assert error.value.status == 409
    assert core.get_project(project["id"])["review"] == {}
    assert not (output.parent / "approved_preview.mp4").exists()


@pytest.mark.parametrize("claim_location", ["project", "scene", "receipt"])
def test_real_production_gate_rejects_unintegrated_motion_despite_forged_claims(sandbox, monkeypatch, claim_location):
    project = valid_project(sandbox)
    claim = {"engine": "HyperFrames", "runtime": "GSAP", "verified": True, "approved": True,
             "technical_preview_seconds": 3, "browserSkipped": False, "production_conformant": True}
    if claim_location == "project":
        project["production_motion"] = claim
    elif claim_location == "scene":
        project["timeline"][1]["production_motion"] = claim
    project = core.save_project(project["id"], project)
    project, output = add_receipt(project, sandbox)
    if claim_location == "receipt":
        project["renders"][-1].update(production_motion=claim, mode="ascendia_narrative", production_conformant=True)
        core.atomic_json(core.project_path(project["id"]), project)
    monkeypatch.setattr(core, "production_motion_errors", ORIGINAL_PRODUCTION_MOTION_ERRORS)
    check = core.validate_project(project, strict=True)
    assert not check["valid"] and any("HyperFrames/GSAP" in message for message in check["errors"])
    assert core.validate_project(project, strict=False)["valid"]
    before = core.project_path(project["id"]).read_bytes()
    with pytest.raises(core.StudioError) as error:
        core.record_review(project["id"], approving_review())
    assert error.value.status == 409
    assert any("HyperFrames/GSAP" in message for message in error.value.details["errors"])
    assert core.project_path(project["id"]).read_bytes() == before
    assert not (output.parent / "approved_preview.mp4").exists()
    with pytest.raises(core.StudioError):
        jobs.submit(project["id"], "render", {"seconds": 10})
    assert jobs.list_jobs() == []


def test_technical_job_remains_available_and_receipt_cannot_claim_production(sandbox, monkeypatch):
    from studio import render as renderer
    project = valid_project(sandbox)
    project["reference_review"] = {}
    project = core.save_project(project["id"], project)
    monkeypatch.setattr(core, "production_motion_errors", ORIGINAL_PRODUCTION_MOTION_ERRORS)
    calls = []
    def simulated_renderer(incoming, root, output, seconds, progress, cancel):
        # A mocked result tests the job wrapper; it is not a real media receipt.
        calls.append((incoming["id"], root, output.name, seconds))
        output.write_bytes(b"Synthetic job-wrapper output; never decoded or approved")
        progress(.5, "Synthetic technical job fixture")
        return {"path": str(output), "sha256": core.digest(output), "duration": seconds, "used_assets": [],
                "mode": "ascendia_narrative", "approved": True, "production_conformant": True,
                "technical": {"decode_ok": False, "fixture_only": True, "editorial_approved": False, "audio_listened": False}}
    monkeypatch.setattr(renderer, "render", simulated_renderer)
    job = jobs.submit(project["id"], "render", {"seconds": 3, "technical": True})
    jobs.execute(job["id"])
    finished = jobs.get_job(job["id"])
    assert finished["status"] == "completed", finished
    assert calls == [(project["id"], sandbox, "technical_preview.mp4", 3.)]
    result = finished["result"]
    assert result["mode"] == "technical_library" and result["approved"] is False
    assert result["production_conformant"] is False and result["technical"]["fixture_only"]
    saved = core.get_project(project["id"])
    assert saved["stage"] == "technical_export_unapproved" and saved["review"] == {}
    assert saved["renders"][-1] == result
    with pytest.raises(core.StudioError, match="exportado técnico"):
        core.record_review(project["id"], approving_review())
    assert not (sandbox / "projects" / project["id"] / "approved_preview.mp4").exists()


@pytest.mark.parametrize("seconds", [10.1, 12, 7200])
def test_technical_job_cannot_render_complete_even_with_forged_full_authorization(sandbox, seconds):
    project = valid_project(sandbox)
    project["full_authorization"] = {"authorized": True, "editorial_digest": core.editorial_digest(project)}
    core.atomic_json(core.project_path(project["id"]), project)
    with pytest.raises(core.StudioError, match="máximo diez segundos") as error:
        jobs.submit(project["id"], "render", {"seconds": seconds, "technical": True})
    assert error.value.status == 409 and jobs.list_jobs() == []


@pytest.mark.parametrize("flag", [1, "true", [], {}])
def test_technical_flag_must_be_explicit_boolean(sandbox, flag):
    project = valid_project(sandbox)
    with pytest.raises(core.StudioError, match="booleano"):
        jobs.submit(project["id"], "render", {"seconds": 3, "technical": flag})
    assert jobs.list_jobs() == []


def test_technical_cancellation_before_execution_never_calls_engine(sandbox, monkeypatch):
    from studio import render as renderer
    project = valid_project(sandbox)
    job = jobs.submit(project["id"], "render", {"seconds": 3, "technical": True})
    jobs.cancel_job(job["id"])
    monkeypatch.setattr(renderer, "render", lambda *a, **kw: pytest.fail("Cancelled technical work must not render"))
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "cancelled"
    assert core.get_project(project["id"])["renders"] == []
    assert not (sandbox / "projects" / project["id"] / "technical_preview.mp4").exists()


def test_technical_output_is_kept_unpromoted_when_timeline_changes_during_render(sandbox, monkeypatch):
    from studio import render as renderer
    project = valid_project(sandbox)
    def edit_during_simulated_render(incoming, root, output, seconds, progress, cancel):
        output.write_bytes(b"Synthetic stale output; not an actual render")
        latest = core.get_project(incoming["id"])
        latest["timeline"][1]["title"] = "Changed synthetic motion during export"
        core.save_project(latest["id"], latest)
        return {"sha256": core.digest(output), "duration": seconds, "used_assets": [], "technical": {"fixture_only": True}}
    monkeypatch.setattr(renderer, "render", edit_during_simulated_render)
    job = jobs.submit(project["id"], "render", {"seconds": 3, "technical": True})
    jobs.execute(job["id"])
    finished = jobs.get_job(job["id"])
    assert finished["status"] == "failed" and "montaje cambió" in finished["error"]
    assert finished["details"]["stale"] and finished["details"]["mode"] == "technical_library"
    assert finished["details"]["approved"] is False and finished["details"]["production_conformant"] is False
    assert (sandbox / "projects" / project["id"] / "technical_preview.mp4").is_file()
    assert core.get_project(project["id"])["renders"] == []


def test_engine_code_fingerprint_change_invalidates_receipt_and_lease_without_editing_code(sandbox, monkeypatch):
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"studio/render.py": "before-fixture-hash"})
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox)
    jobs.create_tasks(project["id"])
    claim = jobs.claim_task("director", "Synthetic code fixture reviewer")
    before = output.read_bytes()
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"studio/render.py": "after-fixture-hash"})
    with pytest.raises(core.StudioError, match="cronología vigente") as error:
        core.record_review(project["id"], approving_review())
    assert error.value.status == 409
    with pytest.raises(core.StudioError, match="proyecto o el manual cambió"):
        jobs.finish_task(claim["id"], claim["lease"], {"observations": "Old code fixture", "evidence": [".estado/tmp/reference.txt"]})
    assert output.read_bytes() == before and core.get_project(project["id"])["review"] == {}


def test_computed_approval_status_is_current_read_only_and_cannot_be_asserted_by_editor_json(sandbox):
    project = valid_project(sandbox)
    project["approval_current"] = True
    saved = core.save_project(project["id"], project)
    assert saved["approval_current"] is False
    assert "approval_current" not in core.read_json(core.project_path(project["id"]))
    project, output = add_receipt(saved, sandbox)
    core.record_review(project["id"], approving_review())
    path = core.project_path(project["id"])
    before = path.read_bytes()
    first, again = core.get_project(project["id"]), core.get_project(project["id"])
    assert first["approval_current"] is True and again["approval_current"] is True
    assert first["revision"] == again["revision"] and path.read_bytes() == before
    assert output.is_file()


def test_computed_approval_status_rejects_changed_code_and_real_absent_engine(sandbox, monkeypatch):
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"render.py": "stable fixture engine"})
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox)
    core.record_review(project["id"], approving_review())
    path = core.project_path(project["id"])
    before = path.read_bytes()
    assert core.get_project(project["id"])["approval_current"] is True
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"render.py": "changed fixture engine"})
    assert core.get_project(project["id"])["approval_current"] is False
    assert path.read_bytes() == before and output.is_file()
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"render.py": "stable fixture engine"})
    monkeypatch.setattr(core, "production_motion_errors", ORIGINAL_PRODUCTION_MOTION_ERRORS)
    assert core.get_project(project["id"])["approval_current"] is False
    assert path.read_bytes() == before


def test_technical_export_and_comments_revoke_previous_full_authorization(sandbox, monkeypatch):
    from studio import render as renderer, server
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox)
    core.record_review(project["id"], approving_review())
    authorized = server.authorize_full(project["id"], {"authorized": True, "notes": "Explicit synthetic fixture authorization"})
    assert authorized["full_authorization"]["authorized"] is True
    def technical_fixture(incoming, root, output, seconds, progress, cancel):
        output.write_bytes(b"Synthetic technical wrapper fixture; not actual footage")
        return {"sha256": core.digest(output), "duration": seconds, "used_assets": [], "technical": {"fixture_only": True}}
    monkeypatch.setattr(renderer, "render", technical_fixture)
    job = jobs.submit(project["id"], "render", {"seconds": 3, "technical": True})
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "completed"
    technical = core.get_project(project["id"])
    assert technical["review"] == {} and not technical.get("full_authorization")
    comments = core.record_review(project["id"], {"approve_preview": False, "reviewer": "Fixture technical reviewer", "notes": "Only synthetic wrapper observations"})
    assert comments["review"]["approved_preview"] is False and not comments.get("full_authorization")
    assert comments["approval_current"] is False
    before = len(jobs.list_jobs())
    with pytest.raises(core.StudioError) as error:
        jobs.submit(project["id"], "render", {"seconds": 12})
    assert error.value.status == 409 and len(jobs.list_jobs()) == before
    with pytest.raises(core.StudioError) as error:
        server.authorize_full(project["id"], {"authorized": True, "notes": "This must not promote technical comments"})
    assert error.value.status == 409


@pytest.mark.parametrize("changed", ["review_revoked", "approved_bytes_changed"])
def test_complete_execution_rechecks_current_approval_after_queueing(sandbox, monkeypatch, changed):
    from studio import render as renderer, server
    project = valid_project(sandbox)
    project, output = add_receipt(project, sandbox)
    approved = core.record_review(project["id"], approving_review())
    authorized = server.authorize_full(project["id"], {"authorized": True, "notes": "Synthetic full queue regression"})
    job = jobs.submit(project["id"], "render", {"seconds": 12})
    if changed == "review_revoked":
        latest = core.get_project(project["id"])
        latest["review"]["approved_preview"] = False
        # Direct fixture state avoids an earlier revision check masking this gate.
        core.atomic_json(core.project_path(project["id"]), latest)
    else:
        core.confined(approved["approved_export"]["path"]).write_bytes(b"Modified approved fixture artifact")
    monkeypatch.setattr(renderer, "render", lambda *a, **kw: pytest.fail("A stale full approval must not reach the renderer"))
    jobs.execute(job["id"])
    finished = jobs.get_job(job["id"])
    assert finished["status"] == "failed", finished
    assert core.get_project(project["id"])["approval_current"] is False
    assert core.get_project(project["id"])["revision"] == authorized["revision"]
    assert not (output.parent / "candidate.mp4").exists()
