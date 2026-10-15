"""CPU tracking regressions; all fixtures live under SOFTWARE/.estado/tmp."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil

import pytest

from studio import core, jobs, tracking

REAL_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((REAL_ROOT / ".estado/tmp").resolve())
    root = tmp_path / "SOFTWARE"
    root.mkdir()
    monkeypatch.setattr(core, "ROOT", root)
    monkeypatch.setattr(jobs, "ROOT", root)
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
    (root / ".estado/tmp").mkdir(parents=True)
    return root


@pytest.fixture
def simulated(workspace, monkeypatch):
    path = workspace / "source.mp4"
    path.write_bytes(b"private synthetic unit fixture, not a detected face")
    source = {"id": "source", "path": "source.mp4", "sha256": tracking._hash(path)}
    project = {"id": "p_tracking", "source": "source", "assets": [source], "timeline": [
        {"id": "s1", "start": 0, "end": 1, "type": "talking", "source_in": 1}]}
    monkeypatch.setattr(tracking, "_runtime", lambda root: {"runtime_version": "unit-fixture", "files": {}})
    monkeypatch.setattr(tracking, "_probe", lambda path, root: (3., {"width": 320, "height": 480}))

    def extract(args, root, **kw):
        Path(args[-1]).write_bytes(b"unit evidence, no image claim")
        when = args[args.index("-ss") + 1]
        return b"", f"n: 0 pts: 1 pts_time:{when}".encode()
    monkeypatch.setattr(tracking, "_run", extract)
    monkeypatch.setattr(tracking, "_browser", lambda root, frames, options, runtime, work: [
        {"time": frame["time"], "detections": [], "faces": []} for frame in frames])
    return project


def face(when=0, x=.5, chin_y=.65, score=.95, count=478):
    return {"time": when, "detections": [{"score": score}], "faces": [
        {"count": count, "chin": {"x": x, "y": chin_y}, "nose": {"x": x, "y": .45},
         "bounds": {"x": x - .12, "y": .3, "right": x + .12, "bottom": chin_y}}]}


def frames(times):
    return [{"time": value, "path": f"frame_{i}.jpg"} for i, value in enumerate(times)]


@pytest.mark.parametrize("options", [None, {}, {"end": 10, "sample_fps": 2}, {"start": 8, "end": 9.5}])
def test_valid_options(options):
    result = tracking.validate_options(options)
    assert result["min_confidence"] == .6


@pytest.mark.parametrize("options", [False, [], {"gpu": True}, {"sample_fps": 0},
    {"sample_fps": True}, {"sample_fps": float("nan")}, {"end": "10"}, {"start": -1},
    {"start": 3, "end": 2}, {"end": 121}, {"max_samples": 3.2}, {"min_confidence": 1.1},
    {"minimum_coverage": .4}, {"smoothing": 0}])
def test_invalid_options_rejected(options):
    with pytest.raises(core.StudioError):
        tracking.validate_options(options)


def test_missing_landmarks_and_low_score_do_not_invent_face():
    low = face(0, score=.59)
    missing = {"time": 1, "detections": [], "faces": []}
    samples = tracking._measure_samples([low, missing], frames([0, 1]), tracking.validate_options())
    assert not any(s["detected"] for s in samples)
    assert all(s["confidence"] is None and s["raw"] is None and s["smoothed"] is None for s in samples)


def test_smoothing_uses_real_sample_positions_and_resets_after_gap_or_cut():
    measurements = [face(0, x=.4), face(1, x=.5), {"time": 2, "detections": [], "faces": []},
                    face(3, x=.52), face(4, x=.75)]
    samples = tracking._measure_samples(measurements, frames(range(5)), tracking.validate_options())
    assert samples[1]["smoothed"]["focus_x"] == pytest.approx(.44)
    assert samples[2]["smoothed"] is None
    assert samples[3]["smoothed"]["focus_x"] == .52 and samples[3]["smoothing_reset"] is True
    assert samples[4]["smoothed"]["focus_x"] == .75 and samples[4]["smoothing_reset"] is True


def test_multiple_people_do_not_choose_a_random_presenter():
    raw = face()
    raw["detections"].append({"score": .9})
    result = tracking._measure_samples([raw], frames([0]), tracking.validate_options())[0]
    assert result["status"] == "ambiguous_multiple_faces" and result["raw"] is None


@pytest.mark.parametrize("raw", [[None], [{"time": None}], [{"time": float("nan")}],
    [{"time": 0, "faces": None, "detections": []}], [{"time": 0, "faces": [None], "detections": []}], []])
def test_malformed_engine_result_is_a_controlled_error(raw):
    with pytest.raises(core.StudioError):
        tracking._measure_samples(raw, frames([0]), tracking.validate_options())


def test_landmark_outside_frame_remains_unreviewed_no_position():
    raw = face(chin_y=1.2)
    sample = tracking._measure_samples([raw], frames([0]), tracking.validate_options())[0]
    assert sample["detected"] is False and sample["raw"] is None
    assert sample["status"] == "invalid_or_clipped_landmarks"


@pytest.mark.parametrize("scene_type", ["presenter", "split", "talking", "camera"])
def test_source_time_proposals_do_not_mutate_or_approve_project(scene_type):
    project = {"timeline": [{"id": "s1", "start": 0, "end": 1, "source_in": 3, "type": scene_type}]}
    before = copy.deepcopy(project)
    options = tracking.validate_options({"sample_fps": 2})
    samples = tracking._measure_samples([face(3), face(3.5, x=.52)], frames([3, 3.5]), options)
    p = tracking._proposals(project, samples, options)[0]
    assert project == before
    assert p["source_start"] == 3 and p["source_end"] == 4
    assert p["status"] == "pending_geometry_and_visual_review"
    assert p["changes"] is None and p["reviewed"] is False and p["apply_automatically"] is False


def test_partial_range_does_not_propose_whole_scene():
    p = {"timeline": [{"id": "s", "start": 0, "end": 10, "source_in": 0, "type": "camera"}]}
    o = tracking.validate_options()
    samples = tracking._measure_samples([face(0), face(.25)], frames([0, .25]), o)
    assert tracking._proposals(p, samples, o)[0]["status"] == "insufficient_detection"


def test_analysis_has_hashed_evidence_no_face_and_keeps_editable(simulated, workspace):
    before = copy.deepcopy(simulated)
    result = tracking.analyze_tracking(simulated, {"start": 1, "end": 2, "sample_fps": 2})
    assert simulated == before
    assert [s["time"] for s in result["samples"]] == [1, 1.5]
    assert result["summary"]["no_face_samples"] == 2
    assert result["summary"]["detected_samples"] == 0
    assert result["proposals"][0]["status"] == "insufficient_detection"
    assert result["editorial_approved"] is False and result["reviewed"] is False
    for item in result["evidence"]:
        assert tracking._hash(workspace / item["path"]) == item["sha256"]
    assert (workspace / result["path"]).is_file()


def test_dedup_reuses_intact_measurements_and_detects_tampering(simulated, workspace, monkeypatch):
    options = {"end": 1, "sample_fps": 1}
    first = tracking.analyze_tracking(simulated, options)
    monkeypatch.setattr(tracking, "_browser", lambda *args: pytest.fail("must reuse measurements"))
    second = tracking.analyze_tracking(simulated, options)
    assert second["reused"] is True and second["evidence"] == first["evidence"]
    (workspace / first["evidence"][0]["path"]).write_bytes(b"changed evidence")
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated, options)
    assert error.value.status == 409


def test_tampered_report_cannot_claim_detection(simulated, workspace):
    options = {"end": 1, "sample_fps": 1}
    result = tracking.analyze_tracking(simulated, options)
    path = workspace / result["path"]
    changed = json.loads(path.read_text()); changed["reviewed"] = True
    path.write_text(json.dumps(changed))
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated, options)
    assert error.value.status == 409


def test_changed_source_hash_rejected_before_browser(simulated, workspace, monkeypatch):
    (workspace / "source.mp4").write_bytes(b"changed source")
    monkeypatch.setattr(tracking, "_browser", lambda *args: pytest.fail("must reject first"))
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated, {"end": 1})
    assert error.value.status == 409


def test_changed_source_during_inference_has_no_promoted_report(simulated, workspace, monkeypatch):
    def changing(root, frames, *rest):
        (root / "source.mp4").write_bytes(b"changed during inference")
        return [{"time": f["time"], "detections": [], "faces": []} for f in frames]
    monkeypatch.setattr(tracking, "_browser", changing)
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated, {"end": 1})
    assert error.value.status == 409
    assert not list((workspace / "projects").rglob("measurements.json"))
    assert not list((workspace / "projects").rglob("frame_*.jpg"))


def test_runtime_change_during_inference_rejects_without_promoting(simulated, workspace, monkeypatch):
    calls = []
    def runtime(root):
        calls.append(1)
        return {"runtime_version": "unit", "files": {} if len(calls) == 1 else {"changed": "new"}}
    monkeypatch.setattr(tracking, "_runtime", runtime)
    with pytest.raises(core.StudioError, match="runtime cambió") as error:
        tracking.analyze_tracking(simulated, {"end": 1})
    assert error.value.status == 409
    assert not list((workspace / "projects").rglob("measurements.json"))


def test_code_change_during_inference_rejects_without_mutating_code(simulated, workspace, monkeypatch):
    original_hash = tracking._hash
    changed = []
    def hashing(path):
        if Path(path) == Path(tracking.__file__) and changed:
            return "f" * 64
        return original_hash(path)
    def browser(root, frames, *rest):
        changed.append(True)
        return [{"time": f["time"], "detections": [], "faces": []} for f in frames]
    monkeypatch.setattr(tracking, "_hash", hashing)
    monkeypatch.setattr(tracking, "_browser", browser)
    with pytest.raises(core.StudioError, match="código del seguimiento cambió"):
        tracking.analyze_tracking(simulated, {"end": 1})
    assert not list((workspace / "projects").rglob("measurements.json"))


def test_missing_real_frame_timestamp_never_creates_fake_time(simulated, workspace, monkeypatch):
    def extract(args, root, **kw):
        Path(args[-1]).write_bytes(b"unit frame")
        return b"", b"FFmpeg output with no frame pts confirmation"
    monkeypatch.setattr(tracking, "_run", extract)
    with pytest.raises(core.StudioError, match="timestamp"):
        tracking.analyze_tracking(simulated, {"end": 1})
    assert not list((workspace / "projects").rglob("frame_*.jpg"))


def test_cancellation_arriving_during_inference_is_respected(simulated, workspace, monkeypatch):
    import threading
    cancel = threading.Event()
    def browser(root, frames, *rest):
        cancel.set()
        return [{"time": f["time"], "detections": [], "faces": []} for f in frames]
    monkeypatch.setattr(tracking, "_browser", browser)
    with pytest.raises(core.StudioError, match="cancelado"):
        tracking.analyze_tracking(simulated, {"end": 1}, cancel=cancel)
    assert not list((workspace / "projects").rglob("measurements.json"))


def test_cancel_preserves_source_and_publishes_nothing(simulated, workspace):
    import threading
    cancel = threading.Event(); cancel.set()
    original = (workspace / "source.mp4").read_bytes()
    with pytest.raises(core.StudioError, match="cancelado"):
        tracking.analyze_tracking(simulated, {"end": 1}, cancel=cancel)
    assert (workspace / "source.mp4").read_bytes() == original
    assert not list((workspace / "projects").rglob("measurements.json"))


def test_limits_stop_decode_and_import_paths_are_confined(simulated, workspace):
    with pytest.raises(core.StudioError, match="max_samples"):
        tracking.analyze_tracking(simulated, {"end": 3, "sample_fps": 10, "max_samples": 2})
    outside = workspace.parent / "outside.mp4"; outside.write_bytes(b"private outside fixture")
    simulated["assets"][0]["path"] = str(outside)
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated)
    assert error.value.status == 403


@pytest.mark.parametrize("change", [{"timeline": None}, {"assets": {}}, {"id": "../outside"}])
def test_malformed_project_json_is_a_controlled_error(simulated, change):
    simulated.update(change)
    with pytest.raises(core.StudioError):
        tracking.analyze_tracking(simulated)


def test_embedded_nul_path_is_a_controlled_error(simulated):
    simulated["assets"][0]["path"] = "source\x00.mp4"
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated)
    assert error.value.status == 403


def test_cpu_before_store_is_enforced(simulated):
    with core.LOCK:
        with pytest.raises(core.StudioError) as error:
            tracking.analyze_tracking(simulated, {"end": 1})
    assert error.value.status == 409


def test_tracking_output_cannot_follow_even_internal_symlink(simulated, workspace):
    (workspace / "projects").mkdir()
    (workspace / "victim").mkdir()
    (workspace / "projects/p_tracking").symlink_to(workspace / "victim", target_is_directory=True)
    with pytest.raises(core.StudioError) as error:
        tracking.analyze_tracking(simulated, {"end": 1})
    assert error.value.status == 403 and list((workspace / "victim").iterdir()) == []


def test_local_runtime_missing_is_unavailable_without_installation(workspace):
    result = tracking.capability()
    assert result["available"] is False
    assert not (workspace / tracking.RUNTIME).exists()


@pytest.fixture(scope="module")
def black_video():
    root = REAL_ROOT / ".estado/validacion/tracking_tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "black.mp4"
    if not path.exists():
        tracking._run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=160x240:r=10:d=1",
                       "-c:v", "libx264", "-filter_threads", "2", "-threads", "2", "-pix_fmt", "yuv420p", "-n", str(path)], REAL_ROOT)
    return path


def test_actual_cpu_detector_on_black_video_has_no_face(black_video, workspace):
    # Existing local runtime only: no model/network installation in pytest.
    if not tracking.capability(REAL_ROOT)["available"]:
        pytest.skip("offline runtime not copied in this checkout")
    shutil.copytree(REAL_ROOT / tracking.RUNTIME, workspace / tracking.RUNTIME)
    shutil.copyfile(black_video, workspace / "black.mp4")
    p = {"id": "p_black", "source": "black", "assets": [
        {"id": "black", "path": "black.mp4", "sha256": tracking._hash(workspace / "black.mp4")}],
        "timeline": [{"id": "s", "type": "talking", "start": 0, "end": 1, "source_in": 0}]}
    before = copy.deepcopy(p)
    result = tracking.analyze_tracking(p, {"end": 1, "sample_fps": 1})
    assert p == before
    assert result["device"] == "cpu" and result["gpu_used"] is False
    assert result["summary"]["detected_samples"] == 0 and result["summary"]["no_face_samples"] == 1
    assert result["samples"][0]["confidence"] is None
    assert result["proposals"][0]["changes"] is None


def test_real_decode_timestamp_is_measured_and_not_invented_from_request(black_video, workspace):
    if not tracking.capability(REAL_ROOT)["available"]:
        pytest.skip("offline runtime not copied in this checkout")
    shutil.copytree(REAL_ROOT / tracking.RUNTIME, workspace / tracking.RUNTIME)
    shutil.copyfile(black_video, workspace / "black.mp4")
    source = {"id": "black", "path": "black.mp4", "sha256": tracking._hash(workspace / "black.mp4")}
    project = {"id": "p_pts", "source": "black", "assets": [source], "timeline": []}
    result = tracking.analyze_tracking(project, {"end": .5, "sample_fps": 4})
    assert result["samples"][1]["requested_time"] == .25
    # This actual synthetic input has 10fps, so the next decodable frame is .3.
    assert result["samples"][1]["time"] == pytest.approx(.3, abs=.0001)
    assert result["sampling"]["times"] == "measured_decoded_pts_seconds_relative_to_container_start"
