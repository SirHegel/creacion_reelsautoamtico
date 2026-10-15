"""Additional audit regressions requested during the software build."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from studio import core, jobs, render, motion, server
from test_core import sandbox, valid_project, add_receipt, approving_review, REAL_ROOT


def test_approved_preview_survives_later_candidate_and_edits(sandbox):
    p = valid_project(sandbox)
    p, candidate = add_receipt(p, sandbox)
    approved = core.record_review(p["id"], approving_review())
    saved_path = core.confined(approved["approved_export"]["path"])
    old_bytes = saved_path.read_bytes()
    approved["timeline"][1]["title"] = "A changed composition"
    updated = core.save_project(p["id"], approved)
    candidate.write_bytes(b"a different unapproved candidate")
    assert updated["review"] == {}
    assert saved_path.read_bytes() == old_bytes
    assert updated["approved_export"]["sha256"] == core.digest(saved_path)


def test_full_authorization_rejects_changed_approved_artifact(sandbox, monkeypatch):
    monkeypatch.setattr(server, "ROOT", sandbox)
    p = valid_project(sandbox)
    p, candidate = add_receipt(p, sandbox)
    p = core.record_review(p["id"], approving_review())
    core.confined(p["approved_export"]["path"]).write_bytes(b"modified after approval")
    with pytest.raises(core.StudioError, match="aprobada falta o cambió"):
        server.authorize_full(p["id"], {"authorized": True, "notes": "Explicit fixture authorization"})


def test_original_presenter_cannot_bypass_face_budget_as_broll(sandbox):
    p = valid_project(sandbox)
    p["timeline"] = [{"id": "masked", "start": 0, "end": 10, "type": "broll", "asset_id": p["source"], "title": "Hidden presenter"}]
    result = core.validate_project(p)
    assert not result["valid"]
    assert any("ocultarse como b-roll" in e for e in result["errors"])


def test_private_font_paths_cannot_be_saved_or_exported(sandbox):
    p = valid_project(sandbox)
    private = sandbox / ".estado/tmp/private_font.ttf"
    private.write_bytes((sandbox / p["fonts"]["primary"]).read_bytes())
    p["fonts"]["primary"] = core.relative(private)
    with pytest.raises(core.StudioError, match="archivos privados"):
        core.save_project(p["id"], p)
    # The same protection applies to an externally altered local project file.
    core.atomic_json(core.project_path(p["id"]), p)
    with pytest.raises(core.StudioError, match="archivos privados"):
        jobs.export_bundle(p["id"])
    assert not (sandbox / f"exports/{p['id']}_editable.zip").exists()


def test_attaching_an_existing_raw_reopens_its_canonical_editable(sandbox):
    canonical = valid_project(sandbox)
    blank = core.create_project("Another empty draft")
    before = core.project_path(canonical["id"]).read_bytes()
    reused = core.attach_asset(blank["id"], canonical["source"], source=True)
    assert reused["id"] == canonical["id"]
    assert core.get_project(blank["id"])["source"] is None
    assert core.project_path(canonical["id"]).read_bytes() == before
    assert len([p for p in core.project_list() if p.get("source") == canonical["source"]]) == 1


def test_project_put_cannot_bypass_raw_project_uniqueness(sandbox):
    canonical = valid_project(sandbox)
    blank = core.create_project("A pending draft")
    before = core.project_path(blank["id"]).read_bytes()
    blank.update(source=canonical["source"], assets=copy.deepcopy(canonical["assets"]))
    with pytest.raises(core.StudioError, match="proyecto canónico") as error:
        core.save_project(blank["id"], blank)
    assert error.value.status == 409 and error.value.details["project_id"] == canonical["id"]
    assert core.project_path(blank["id"]).read_bytes() == before


def test_drive_identity_does_not_silently_reuse_a_different_raw(sandbox, monkeypatch):
    from studio import analysis
    canonical = valid_project(sandbox)
    canonical["drive_id"] = "fixture_drive_raw"
    canonical = core.save_project(canonical["id"], canonical)
    other = sandbox / "different.mp4"
    other.write_bytes(b"another fake video probe fixture")
    monkeypatch.setattr(analysis, "probe", lambda path: {"streams": [{"codec_type": "video"}], "format": {"duration": "2"}})
    monkeypatch.setattr(analysis, "thumbnails", lambda *args: [])
    imported = core.register_asset(other)
    before = core.project_path(canonical["id"]).read_bytes()
    with pytest.raises(core.StudioError, match="otro contenido") as error:
        core.create_project("Changed raw", imported["id"], "fixture_drive_raw")
    assert error.value.status == 409
    assert core.project_path(canonical["id"]).read_bytes() == before
    assert core.create_project("Same raw", canonical["source"], "fixture_drive_raw")["id"] == canonical["id"]


def test_video_cannot_be_imported_as_static_image(sandbox, monkeypatch):
    sample = sandbox / ".estado/tmp/sample.mp4"
    sample.write_bytes(b"fake media probe fixture")
    from studio import analysis
    monkeypatch.setattr(analysis, "probe", lambda path: {"streams": [{"codec_type": "video"}], "format": {"duration": "1"}})
    with pytest.raises(core.StudioError, match="imagen estática"):
        core.register_asset(sample, kind="image")
    assert sample.read_bytes() == b"fake media probe fixture"
    assert core.assets() == []


def test_later_browser_preview_refresh_does_not_change_editorial_revision(sandbox):
    p = valid_project(sandbox)
    fingerprint = core.editorial_digest(p)
    before = core.project_path(p["id"]).read_bytes()
    catalog = core.assets()
    catalog[0].update(preview_url="/api/files/assets/previews/source.mp4", preview_is_derivative=True)
    catalog[0]["metadata"] = {"content": "A library note is not a project decision"}
    core.atomic_json(".estado/assets.json", catalog)
    refreshed = core.get_project(p["id"])
    assert refreshed["assets"][0]["preview_is_derivative"] is True
    assert refreshed["assets"][0]["metadata"] == p["assets"][0]["metadata"]
    assert refreshed["revision"] == p["revision"]
    assert core.editorial_digest(refreshed) == fingerprint
    assert core.project_path(p["id"]).read_bytes() == before


def test_manual_acknowledgment_rejects_a_stale_browser_copy(sandbox):
    p = valid_project(sandbox)
    expected = {name: info["sha256"] for name, info in core.manual_fingerprints().items()}
    before = core.project_path(p["id"]).read_bytes()
    (sandbox.parent / "PROMPT_MAESTRO.md").write_text("Changed fixture manual", encoding="utf-8")
    with pytest.raises(core.StudioError, match="manual cambió") as error:
        core.refresh_manual(p["id"], expected)
    assert error.value.status == 409
    assert core.project_path(p["id"]).read_bytes() == before
    current = {name: info["sha256"] for name, info in core.manual_fingerprints().items()}
    result = core.refresh_manual(p["id"], current)
    assert result["manual"] == core.manual_fingerprints()


def test_public_model_downloads_isolate_modern_caches_and_do_not_inherit_tokens(sandbox, monkeypatch):
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HF_API_TOKEN"):
        monkeypatch.setenv(key, "synthetic-fixture-token")
    for key in ("HF_HUB_CACHE", "HF_XET_CACHE", "HF_ASSETS_CACHE", "HF_TOKEN_PATH"):
        monkeypatch.setenv(key, str(sandbox.parent / "outside-fixture-config"))
    monkeypatch.setenv("HF_HUB_DISABLE_IMPLICIT_TOKEN", "0")
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "0")
    core.setup()
    assert all(key not in os.environ for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HF_API_TOKEN"))
    for key in ("HF_HUB_CACHE", "HF_XET_CACHE", "HF_ASSETS_CACHE", "HF_TOKEN_PATH"):
        assert Path(os.environ[key]).is_relative_to(sandbox)
    assert os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
    assert not (sandbox.parent / "outside-fixture-config").exists()


def test_split_motion_title_is_composed_once(monkeypatch):
    from PIL import Image
    calls = []
    monkeypatch.setattr(motion, "_kinetic", lambda *a, **k: calls.append(True))
    scene = {"id": "s", "start": 0, "end": 2, "_planned_end": 2, "type": "split", "title": "One title", "chin_y": .65}
    render._decorate(Image.new("RGB", (160, 284)), {"style": {"hook_seconds": 4.5}}, scene, .5, {"primary": "unused", "accent": "unused"}, [])
    assert calls == []


def test_face_caption_position_tracks_keyframe_zoom_and_offset(monkeypatch):
    from PIL import Image
    y_positions = []
    monkeypatch.setattr(motion, "text", lambda frame, content, center, *a, **kw: y_positions.append(center[1]))
    scene = {"id": "s", "start": 5, "end": 7, "_planned_end": 7, "type": "presenter", "subtitle": "Small caption", "chin_y": .6,
             "keyframes": [{"time": 0, "scale": 1.1, "y": .02}]}
    render._decorate(Image.new("RGB", (160, 284)), {}, scene, 5,
                     {"primary": str(REAL_ROOT / core.fonts()["primary"]),
                      "accent": str(REAL_ROOT / core.fonts()["accent"])}, [])
    expected_chin = 142 + (.6 * 284 - 142) * 1.1 + .02 * 284
    assert y_positions[0] == pytest.approx(expected_chin + .04 * 284)


def test_task_release_allows_another_agent_to_resume(sandbox):
    p = valid_project(sandbox)
    jobs.create_tasks(p["id"])
    claimed = jobs.claim_task("director", "agent A")
    jobs.release_task(claimed["id"], claimed["lease"])
    next_claim = jobs.claim_task("director", "agent B")
    assert next_claim["id"] == claimed["id"]
    assert next_claim["lease"] != claimed["lease"]
    with pytest.raises(core.StudioError):
        jobs.release_task(next_claim["id"], claimed["lease"])


def test_persisted_cancellation_is_seen_by_a_fresh_executor(sandbox, monkeypatch):
    p = valid_project(sandbox)
    j = jobs.submit(p["id"], "analyze", {})
    jobs.cancel_job(j["id"])
    jobs.CANCEL.clear()
    monkeypatch.setattr(jobs, "_execute", lambda jid: pytest.fail("Cancelled job cannot execute"))
    jobs.execute(j["id"])
    assert jobs.get_job(j["id"])["status"] == "cancelled"


def test_cpu_work_is_serial_between_independent_processes(sandbox):
    log = sandbox / ".estado/cpu_events.jsonl"
    script = """
import json,sys,time
from pathlib import Path
from studio import core,jobs
root=Path(sys.argv[1]); core.ROOT=root; jobs.ROOT=root
jobs.SHARED_CPU_LOCK=root/'.estado/cpu_worker.lock'
jobs.get_job=lambda unused: {'cancel_requested':False,'status':'queued'}
def operation(jid):
    with (root/'.estado/cpu_events.jsonl').open('a') as f:
        f.write(json.dumps({'job':jid,'event':'start'})+'\\n');f.flush()
        time.sleep(.15)
        f.write(json.dumps({'job':jid,'event':'end'})+'\\n');f.flush()
jobs._execute=operation
jobs.execute(sys.argv[2])
"""
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(sandbox), name], cwd=REAL_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for name in ("A", "B")]
    for p in processes:
        out, err = p.communicate(timeout=10)
        assert p.returncode == 0, err.decode()
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["event"] for e in events] == ["start", "end", "start", "end"]
    assert events[0]["job"] == events[1]["job"]
    assert events[2]["job"] == events[3]["job"]


@pytest.mark.parametrize("seconds", [float("nan"), float("inf"), 0, -10])
def test_validation_duration_is_finite(sandbox, seconds):
    with pytest.raises(core.StudioError):
        core.validate_project(valid_project(sandbox), seconds)
