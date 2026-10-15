"""Regression tests for confinement, editorial validity and concurrent editing.

All fixture files, including simulated files outside the *fixture* root, live
under SOFTWARE/.estado/tmp when run with the documented pytest --basetemp.
No real client project, ASR model, GPU or production worker is used.
"""
from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from studio import analysis, core, jobs


REAL_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((REAL_ROOT / ".estado/tmp").resolve()), "pytest must use SOFTWARE/.estado/tmp/pytest_audit as --basetemp"
    root = tmp_path / "SOFTWARE"
    root.mkdir()
    original_confined = core.confined

    def local_confined(path, root_override=None, must_exist=False, **kwargs):
        return original_confined(path, root=kwargs.get("root", root_override) or root, must_exist=must_exist)

    for module in (core, analysis, jobs):
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module, "confined", local_confined)
    monkeypatch.setattr(core, "MANUAL_ROOT", root.parent)
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
    for key in ("TMPDIR", "XDG_CACHE_HOME", "HF_HOME", "HUGGINGFACE_HUB_CACHE", "TORCH_HOME", "MPLCONFIGDIR", "NUMBA_CACHE_DIR", "TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "CUDA_VISIBLE_DEVICES"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    core.setup()
    # Other gates are isolated from the explicitly absent production adapter.
    # Dedicated current-policy tests restore it and prove real production is blocked.
    monkeypatch.setattr(core, "production_motion_errors", lambda project: [])
    from studio import skills
    monkeypatch.setattr(skills, "validate_application", lambda project: [])
    for name in core.DOCUMENTS:
        (root.parent / name).write_text(f"Fixture manual: {name}\n", encoding="utf-8")
    for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf"):
        (root / "assets/fonts" / name).write_bytes(b"fixture font; never rendered")
    from PIL import ImageFont

    class FixtureFont:
        def __init__(self, path):
            self.path = str(path)

        def getname(self):
            return ("Sequel Sans", "Bold Disp") if "Sequel" in self.path else ("Scholar", "Italic")

    monkeypatch.setattr(ImageFont, "truetype", lambda path, size, **kw: FixtureFont(path))
    monkeypatch.setattr(jobs, "QUEUE", __import__("queue").Queue())
    monkeypatch.setattr(jobs, "CANCEL", {})
    monkeypatch.setattr(jobs, "WORKER", None)
    return root


def valid_project(root):
    source_path = root / "assets/video/source.mp4"
    source_path.write_bytes(b"fixture source media - never decoded")
    evidence = root / ".estado/tmp/reference.txt"
    evidence.write_text("Fixture reference observations", encoding="utf-8")
    item = {"id": "a_source", "name": "source.mp4", "path": "assets/video/source.mp4", "kind": "video",
            "sha256": core.digest(source_path), "md5": core.digest(source_path, "md5"), "size": source_path.stat().st_size,
            "duration": 12., "probe": {"streams": [{"codec_type": "video"}, {"codec_type": "audio"}]},
            "verification": {"visual": True, "audio": True, "rights": "fixture_owned", "evidence": [".estado/tmp/reference.txt"]}, "metadata": {}}
    core.atomic_json(".estado/assets.json", [item])
    p = core.create_project("Fixture reel", item["id"])
    decision = {"search": "Fixture library searched", "reason": "Explains fixture narration", "evidence": [".estado/tmp/reference.txt"]}
    p["timeline"] = [
        {"id": "s_split", "start": 0., "end": 1.5, "type": "split", "title": "Fixture hook", "chin_y": .65, "chin_reviewed": True, "template": "workflow", "decision": copy.deepcopy(decision)},
        {"id": "s_motion", "start": 1.5, "end": 12., "type": "motion", "title": "Fixture process", "template": "workflow", "decision": copy.deepcopy(decision)},
    ]
    p["transcript"] = {"words": [{"start": 6., "end": 6.5, "word": "fixture"}], "segments": [{"start": 0., "end": 12., "text": "Fixture narration"}], "status": "imported"}
    p["reference_review"] = {"identity_observations": "Fixture observations", "evidence": [".estado/tmp/reference.txt"],
                             "motion_reference": "CLONE", "motion_observations": "Fixture motion observations",
                             "motion_evidence": [".estado/tmp/reference.txt"]}
    p["audio"] = [{"asset_id": item["id"], "start": 0., "end": 3., "role": "sfx", "is_riser": True, "impact_at": 3., "visual_event": "Fixture transformation"}]
    return core.save_project(p["id"], p)


def add_receipt(p, root, *, exists=True, duration=10.):
    output = root / "projects" / p["id"] / "ascendia_test_v5_10s.mp4"
    if exists:
        output.write_bytes(b"fixture exported video; not a real render")
    receipt = {"path": core.relative(output), "sha256": core.digest(output) if exists else "0" * 64,
               "duration": duration, "editorial_digest": core.editorial_digest(p),
               "technical": {"decode_ok": True, "original_voice_present": True, "editorial_approved": False, "audio_listened": False}}
    p["renders"] = [receipt]
    return core.save_project(p["id"], p, action="rendered"), output


def approving_review():
    return {"visual": True, "audio": True, "sync": True, "spelling": True, "resources": True,
            "movement": True, "identity": True, "safe_zones": True, "reviewer": "Fixture reviewer", "notes": "Fixture review, not a client approval", "approve_preview": True}


def test_confinement_rejects_parent_and_symlink_escape(sandbox):
    outside = sandbox.parent / "sentinel.txt"
    outside.write_text("preserve", encoding="utf-8")
    (sandbox / "escape").symlink_to(outside)
    for path in ("../sentinel.txt", outside, "escape"):
        with pytest.raises(core.StudioError) as error:
            core.atomic_json(path, {"overwrite": True})
        assert error.value.status == 403
    assert outside.read_text() == "preserve"


def test_failed_atomic_json_keeps_previous_file_and_removes_temp(sandbox):
    core.atomic_json(".estado/example.json", {"valid": True})
    with pytest.raises(ValueError):
        core.atomic_json(".estado/example.json", {"invalid": float("nan")})
    assert core.read_json(".estado/example.json") == {"valid": True}
    assert not list((sandbox / ".estado").glob("example.json.*.tmp"))


def test_asset_dedup_uses_content_and_preserves_source_files(sandbox, monkeypatch):
    monkeypatch.setattr(analysis, "probe", lambda path: {"streams": [{"codec_type": "video"}], "format": {"duration": "2"}})
    monkeypatch.setattr(analysis, "thumbnails", lambda *args: [])
    first = sandbox / "first.mp4"
    second = sandbox / "copy.mov"
    first.write_bytes(b"same fixture content")
    second.write_bytes(first.read_bytes())
    a = core.register_asset(first)
    b = core.register_asset(second)
    assert a["id"] == b["id"]
    assert len(core.assets()) == 1
    assert first.exists() and second.exists()
    assert core.confined(a["path"]).read_bytes() == first.read_bytes()


def test_project_dedup_and_optimistic_revision_conflict(sandbox):
    p = valid_project(sandbox)
    assert core.create_project("duplicate", p["source"])["id"] == p["id"]
    a, b = copy.deepcopy(p), copy.deepcopy(p)
    a["name"] = "first edit"
    core.save_project(p["id"], a)
    b["name"] = "stale edit"
    with pytest.raises(core.StudioError) as error:
        core.save_project(p["id"], b)
    assert error.value.status == 409
    assert core.get_project(p["id"])["name"] == "first edit"


def test_two_simultaneous_editors_cannot_both_commit(sandbox):
    p = valid_project(sandbox)
    barrier = threading.Barrier(2)

    def edit(name):
        candidate = copy.deepcopy(p)
        candidate["name"] = name
        barrier.wait(timeout=5)
        try:
            return core.save_project(p["id"], candidate)["name"]
        except core.StudioError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(edit, ["editor A", "editor B"]))
    assert outcomes.count(409) == 1
    assert core.get_project(p["id"])["revision"] == p["revision"] + 1


def test_store_lock_serializes_writers_in_separate_processes(sandbox):
    core.atomic_json(".estado/counter.json", {"count": 0})
    script = """
import sys, time
from pathlib import Path
from studio import core
workspace = Path(sys.argv[1])
original = core.confined
core.ROOT = workspace
core.confined = lambda path, root=workspace, must_exist=False: original(path, root=root, must_exist=must_exist)
for unused in range(30):
    with core.LOCK:
        value = core.read_json('.estado/counter.json')
        time.sleep(.003)
        value['count'] += 1
        core.atomic_json('.estado/counter.json', value)
"""
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(sandbox)], cwd=REAL_ROOT,
                                  env={**os.environ, "TMPDIR": str(sandbox / ".estado/tmp")}, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) for unused in range(2)]
    for process in processes:
        out, err = process.communicate(timeout=20)
        assert process.returncode == 0, (out, err)
    assert core.read_json(".estado/counter.json")["count"] == 60


def test_edit_cannot_inject_review_or_full_authorization(sandbox):
    p = valid_project(sandbox)
    p["review"] = {"approved_preview": True}
    p["renders"] = [{"sha256": "forged"}]
    p["full_authorization"] = {"authorized": True}
    saved = core.save_project(p["id"], p)
    assert not saved["review"]
    assert not saved["renders"]
    assert not saved.get("full_authorization")


def test_meaningful_edit_invalidates_review_and_preserves_render_receipt(sandbox):
    p = valid_project(sandbox)
    p["review"] = {"approved_preview": True}
    p["renders"] = [{"sha256": "historical"}]
    core.atomic_json(core.project_path(p["id"]), p)
    p["timeline"][1]["title"] = "Changed meaning"
    saved = core.save_project(p["id"], p)
    assert saved["review"] == {}
    assert saved["renders"] == [{"sha256": "historical"}]


def test_contiguous_presenter_split_and_full_camera_share_limit(sandbox):
    p = valid_project(sandbox)
    p["timeline"] = [
        {"id": "a", "start": 0., "end": 2., "type": "split", "title": "Hook"},
        {"id": "b", "start": 2., "end": 4., "type": "presenter", "title": "Camera"},
        {"id": "c", "start": 4., "end": 12., "type": "motion", "title": "Process"},
    ]
    check = core.validate_project(p)
    assert check["metrics"]["max_presenter_continuous"] == 4
    assert any("Presencia continua" in error for error in check["errors"])


def test_missing_canonical_manual_cannot_validate(sandbox):
    p = valid_project(sandbox)
    for name in core.DOCUMENTS:
        (sandbox.parent / name).unlink()
    p["manual"] = core.manual_fingerprints()
    assert not core.validate_project(p, strict=True)["valid"]


def test_asset_bytes_changed_on_disk_invalidates_candidate(sandbox):
    p = valid_project(sandbox)
    core.confined(p["assets"][0]["path"]).write_bytes(b"different actual media")
    assert not core.validate_project(p, strict=True)["valid"]


def test_editorial_digest_changes_when_bytes_change_with_same_size_and_mtime(sandbox):
    p = valid_project(sandbox)
    before = core.editorial_digest(p)
    media = core.confined(p["assets"][0]["path"])
    stat = media.stat()
    media.write_bytes(b"x" * stat.st_size)
    os.utime(media, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert core.editorial_digest(p) != before


def test_editorial_digest_includes_font_bytes(sandbox):
    p = valid_project(sandbox)
    before = core.editorial_digest(p)
    core.confined(p["fonts"]["primary"]).write_bytes(b"changed fixture font")
    assert core.editorial_digest(p) != before


def test_project_cannot_forge_registered_asset_hash(sandbox):
    p = valid_project(sandbox)
    p["assets"][0]["sha256"] = "0" * 64
    with pytest.raises(core.StudioError):
        core.save_project(p["id"], p)


def test_audio_end_before_start_is_invalid(sandbox):
    p = valid_project(sandbox)
    p["audio"][0].update(start=3., end=1.)
    with pytest.raises(core.StudioError):
        core.save_project(p["id"], p)


@pytest.mark.parametrize("kind, entry", [
    ("words", {"start": float("nan"), "end": 2., "word": "invalid"}),
    ("words", {"start": 3., "end": 1., "word": "invalid"}),
    ("segments", {"start": 3., "end": 1., "text": "invalid phrase"}),
])
def test_invalid_transcript_times_are_rejected_before_persisting(sandbox, kind, entry):
    p = valid_project(sandbox)
    p["transcript"][kind] = [entry]
    with pytest.raises(core.StudioError):
        core.save_project(p["id"], p)


def test_broll_needs_text_which_actually_overlaps_its_scene(sandbox):
    p = valid_project(sandbox)
    p["timeline"] = [
        {"id": "a", "start": 0., "end": 6., "type": "motion", "title": "Hook"},
        {"id": "b", "start": 6., "end": 8., "type": "broll", "asset_id": p["source"], "source_in": 0},
        {"id": "c", "start": 8., "end": 12., "type": "motion", "title": "Closing"},
    ]
    p["transcript"]["words"] = [{"start": 9., "end": 9.4, "word": "later"}]
    assert not core.validate_project(p)["valid"]


def test_review_rejects_missing_or_modified_export(sandbox):
    p = valid_project(sandbox)
    p, output = add_receipt(p, sandbox, exists=False)
    with pytest.raises(core.StudioError):
        core.record_review(p["id"], approving_review())
    output.write_bytes(b"replacement export")
    with pytest.raises(core.StudioError):
        core.record_review(p["id"], approving_review())


def test_preview_review_requires_current_policy_gates(sandbox):
    p = valid_project(sandbox)
    p["timeline"][0]["automatic_hook_captions"] = True
    p = core.save_project(p["id"], p)
    p, _ = add_receipt(p, sandbox)
    with pytest.raises(core.StudioError):
        core.record_review(p["id"], approving_review())


def test_review_can_approve_only_complete_explicit_checklist(sandbox):
    p = valid_project(sandbox)
    p, _ = add_receipt(p, sandbox)
    assert core.validate_project(p, strict=True)["valid"]
    incomplete = approving_review()
    incomplete["safe_zones"] = False
    with pytest.raises(core.StudioError):
        core.record_review(p["id"], incomplete)
    result = core.record_review(p["id"], approving_review())
    assert result["review"]["approved_preview"] is True
    assert result["review"]["render_sha256"] == p["renders"][0]["sha256"]
    assert result["review"]["editorial_digest"] == core.editorial_digest(result)


def test_short_diagnostic_render_cannot_be_approved_as_v5_preview(sandbox):
    p = valid_project(sandbox)
    p, _ = add_receipt(p, sandbox, duration=2.)
    with pytest.raises(core.StudioError):
        core.record_review(p["id"], approving_review())


def test_analysis_does_not_download_asr_without_opt_in(sandbox, monkeypatch):
    p = valid_project(sandbox)
    monkeypatch.setattr(analysis, "probe", lambda path: {"streams": [{"index": 0, "codec_type": "video"}, {"index": 1, "codec_type": "audio"}]})
    monkeypatch.setattr(analysis, "silence_analysis", lambda path, **kwargs: [])
    monkeypatch.setattr(analysis, "waveform", lambda path, **kwargs: {"peaks": [], "audio_stream_index": kwargs["audio_stream_index"]})

    def unexpected_asr(*args, **kwargs):
        pytest.fail("ASR model must only load after explicit transcribe=True")

    monkeypatch.setattr(analysis, "transcribe", unexpected_asr)
    analyzed = analysis.analyze_project(p)
    assert analyzed["analysis"]["voice_detection"] == "pending_asr"


def test_analysis_without_audio_reports_no_voice(sandbox, monkeypatch):
    p = valid_project(sandbox)
    monkeypatch.setattr(analysis, "probe", lambda path: {"streams": [{"codec_type": "video"}]})
    monkeypatch.setattr(analysis, "transcribe", lambda *args, **kwargs: pytest.fail("No audio must not reach ASR"))
    analyzed = analysis.analyze_project(p, {"transcribe": True})
    assert analyzed["analysis"]["voice_detection"] == "no_audio_track"
    assert analyzed["transcript"]["status"] == "imported"
