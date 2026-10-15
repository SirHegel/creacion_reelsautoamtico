"""Read-only crop proposals from explicit synthetic measurement fixtures."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from studio import core, tracking, tracking_actions
from test_core import sandbox, valid_project


def register_fixture_metadata(project):
    """Fixture-only declaration; never edits the application library."""
    source = next(a for a in project["assets"] if a["id"] == project["source"])
    catalog = core.assets()
    catalog = [copy.deepcopy(source) if a["id"] == source["id"] else a for a in catalog]
    core.atomic_json(".estado/assets.json", catalog)


@pytest.fixture
def measured(sandbox, monkeypatch):
    p = valid_project(sandbox)
    p["settings"].update(width=160, height=320)
    p["timeline"] = [{"id": "cam", "type": "presenter", "start": 0., "end": 1., "source_in": 0., "template": "kinetic"}]
    source = next(a for a in p["assets"] if a["id"] == p["source"])
    source["probe"]["streams"][0].update(width=320, height=640, sample_aspect_ratio="1:1")
    catalog = core.assets(); catalog[0] = copy.deepcopy(source); core.atomic_json(".estado/assets.json", catalog)
    options = tracking.validate_options({"end": 1., "sample_fps": 4.})
    runtime = {"runtime_version": "unit-fixture-no-model-inference", "files": {}}
    monkeypatch.setattr(tracking, "_runtime", lambda root: copy.deepcopy(runtime))
    identity = {"source_sha256": source["sha256"], "options": options, "runtime_files": {},
                "engine_code_sha256": core.digest(Path(tracking.__file__))}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    directory = sandbox / f"projects/{p['id']}/tracking/{key}"
    directory.mkdir(parents=True)
    report = {"identity": identity, "source": source["id"], "source_sha256": source["sha256"],
              "interval": [0., 1.], "samples": [], "evidence": [], "path": core.relative(directory / "measurements.json")}
    for index, when in enumerate((0., .25, .5, .75)):
        path = directory / f"frame_{index:04d}.jpg"
        Image.new("RGB", (100, 200), (30 + index, 50, 60)).save(path)
        coordinates = {"focus_x": .5, "focus_y": .35, "chin_x": .5, "chin_y": .46 + index * .005}
        report["samples"].append({"time": when, "detected": True, "face_count": 1, "confidence": .95,
            "raw": copy.deepcopy(coordinates), "smoothed": copy.deepcopy(coordinates),
            "evidence": core.relative(path), "bbox": {"x": .38, "y": .25, "width": .24, "height": .23}})
        report["evidence"].append({"path": core.relative(path), "sha256": core.digest(path), "source_time": when})
    receipt_path = f".estado/tracking/receipts/{p['id']}_{key}.json"
    def persist():
        core.atomic_json(report["path"], report)
        core.atomic_json(receipt_path, {"report_sha256": core.digest(sandbox / report["path"]),
            "source_sha256": source["sha256"], "engine_code_sha256": identity["engine_code_sha256"]})
    persist()
    p["tracking"] = {"path": report["path"], "samples": [{"fake": True}], "proposals": [{"apply_automatically": True}]}
    p = core.save_project(p["id"], p, action="tracking_measured")
    return p, sandbox, report, runtime, persist, receipt_path


def test_presenter_proposal_uses_verified_file_not_forged_embedded_samples(measured):
    p, root, _, _, _, _ = measured
    before = copy.deepcopy(p)
    bytes_before = core.project_path(p["id"]).read_bytes()
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is True, result
    proposal = result["proposals"][0]
    assert proposal["status"] == "pending_visual_review"
    assert proposal["suggested_changes"]["chin_y"] == pytest.approx(.475)
    assert proposal["geometry"]["target_size"] == [160, 320]
    assert proposal["geometry"]["crop_origin"] == [0, 0]
    assert p == before and core.project_path(p["id"]).read_bytes() == bytes_before
    assert proposal["reviewed"] is False and proposal["apply_automatically"] is False
    assert "chin_reviewed" not in proposal["suggested_changes"]
    assert len(proposal["chin_samples"]) == 4
    assert result["read_only"] is True and result["editorial_approved"] is False


def test_split_chin_is_transformed_to_actual_lower_crop_region(measured):
    p, _, _, _, _, _ = measured
    p["timeline"][0]["type"] = "split"
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is True, result
    proposal = result["proposals"][0]
    assert proposal["status"] == "pending_visual_review", proposal
    geometry = proposal["geometry"]
    assert geometry["target_size"] == [160, 144]
    assert geometry["scaled_size"] == [160, 320]
    crop_y = geometry["crop_origin"][1]
    assert proposal["suggested_changes"]["chin_y"] == pytest.approx((.475 * 320 - crop_y) / 144, abs=.000001)
    assert proposal["suggested_changes"]["chin_y"] != .475


def test_current_scene_source_in_and_range_are_recomputed(measured):
    p, _, report, _, _, _ = measured
    p["timeline"][0].update(start=2., end=2.5, source_in=.25)
    result = tracking_actions.propose_tracking(p)
    proposal = result["proposals"][0]
    assert proposal["source_interval"] == [.25, .75]
    assert [s["source_time"] for s in proposal["chin_samples"]] == [.25, .5]
    assert [s["output_time"] for s in proposal["chin_samples"]] == [2., 2.25]


@pytest.mark.parametrize("kind", ["no_face", "multiple", "gap", "incomplete", "prefix_missing"])
def test_missing_or_ambiguous_coverage_blocks_scene(measured, kind):
    p, _, report, _, persist, _ = measured
    if kind == "no_face":
        report["samples"][1].update(detected=False, face_count=0)
    elif kind == "multiple":
        report["samples"][1]["face_count"] = 2
    elif kind == "gap":
        report["samples"].pop(1); report["evidence"].pop(1)
    elif kind == "incomplete":
        p["timeline"][0]["end"] = 2.
    else:
        report["interval"][0] = .25
        report["samples"].pop(0); report["evidence"].pop(0)
    persist()
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is True, result
    assert result["proposals"][0]["status"] == "blocked"
    assert result["proposals"][0]["suggested_changes"] is None


@pytest.mark.parametrize("target", ["source", "report", "evidence", "receipt"])
def test_tampered_bytes_invalidate_proposals(measured, target):
    p, root, report, _, _, receipt = measured
    path = {"source": root / p["assets"][0]["path"], "report": root / report["path"],
            "evidence": root / report["evidence"][0]["path"], "receipt": root / receipt}[target]
    path.write_bytes(b"Changed own fixture bytes")
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and result["errors"]
    assert result["proposals"] == []


def test_runtime_change_invalidates_and_never_reinstalls(measured):
    p, root, _, runtime, _, _ = measured
    runtime["files"]["different.tflite"] = "f" * 64
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "runtime" in result["errors"][0]
    assert not (root / tracking.RUNTIME).exists()


def test_tracking_code_change_invalidates_without_modifying_a_module(measured, monkeypatch):
    p, _, _, _, _, _ = measured
    original = core.digest
    monkeypatch.setattr(core, "digest", lambda path, *args, **kw: "f" * 64 if Path(path) == Path(tracking.__file__) else original(path, *args, **kw))
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "motor" in result["errors"][0]


@pytest.mark.parametrize("path", ["../outside.json", ".estado/elsewhere.json", "projects/other/tracking/" + "a" * 24 + "/measurements.json", "nul\x00path"])
def test_receipt_paths_are_confined_to_canonical_project(measured, path):
    p, _, _, _, _, _ = measured
    p["tracking"]["path"] = path
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and not result["proposals"]


@pytest.mark.parametrize("sar", ["2:1", "N/A", None, True])
def test_nonunit_or_unknown_sar_is_not_guessed(measured, sar):
    p, _, _, _, _, _ = measured
    p["assets"][0]["probe"]["streams"][0]["sample_aspect_ratio"] = sar
    register_fixture_metadata(p)
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "SAR" in result["errors"][0]


@pytest.mark.parametrize("rotation", [90, -90, 180, 270])
def test_orthogonal_autorotation_uses_landmarks_without_rotating_twice(measured, rotation):
    p, _, _, _, _, _ = measured
    stream = p["assets"][0]["probe"]["streams"][0]
    stream["rotation"] = rotation
    if abs(rotation) % 180 == 90:
        stream.update(width=640, height=320)
    register_fixture_metadata(p)
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is True, result
    assert result["proposals"][0]["suggested_changes"]["chin_y"] == pytest.approx(.475)


@pytest.mark.parametrize("rotation", [45, "invalid", True])
def test_uncertain_rotation_is_rejected(measured, rotation):
    p, _, _, _, _, _ = measured
    p["assets"][0]["probe"]["streams"][0]["rotation"] = rotation
    register_fixture_metadata(p)
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "Rotación" in result["errors"][0]


def test_missing_rotation_is_not_guessed_when_evidence_aspect_contradicts_probe(measured):
    p, _, _, _, _, _ = measured
    p["assets"][0]["probe"]["streams"][0].update(width=640, height=320)
    register_fixture_metadata(p)
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "aspect ratio" in result["errors"][0]


def test_cropped_face_blocks_instead_of_clamping_chin(measured):
    p, _, report, _, persist, _ = measured
    p["timeline"][0]["type"] = "split"
    for s in report["samples"]:
        s["bbox"].update(y=.05, height=.8)
        s["raw"]["chin_y"] = .85
    persist()
    proposal = tracking_actions.propose_tracking(p)["proposals"][0]
    assert proposal["status"] == "blocked" and proposal["suggested_changes"] is None


@pytest.mark.parametrize("mutation", ["time_nan", "timestamp_mismatch", "coordinates_nan", "shape_invalid"])
def test_malformed_measurements_are_controlled_errors(measured, mutation):
    p, root, report, _, persist, _ = measured
    if mutation == "time_nan":
        report["samples"][0]["time"] = "invalid"
    elif mutation == "timestamp_mismatch":
        report["evidence"][0]["source_time"] = .1
    elif mutation == "coordinates_nan":
        report["samples"][0]["raw"]["chin_y"] = "invalid"
    else:
        report["samples"] = None
    persist()
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and result["errors"]


def test_get_proposals_launches_no_process_and_creates_no_files(measured, monkeypatch):
    import subprocess
    p, root, _, _, _, _ = measured
    before = {str(f.relative_to(root)): core.digest(f) for f in root.rglob("*") if f.is_file()}
    monkeypatch.setattr(subprocess, "run", lambda *args, **kw: pytest.fail("GET may not run a decoder"))
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kw: pytest.fail("GET may not run a browser"))
    assert tracking_actions.propose_tracking(p)["valid"] is True
    after = {str(f.relative_to(root)): core.digest(f) for f in root.rglob("*") if f.is_file()}
    assert after == before


def test_report_cannot_claim_a_different_canonical_path(measured):
    p, _, report, _, persist, _ = measured
    original_path = report["path"]
    # Persist malformed content at the real protected path, with a matching
    # fixture receipt, to isolate schema validation from the byte-hash guard.
    report["path"] = "projects/another/tracking/forged.json"
    data = copy.deepcopy(report); report["path"] = original_path
    root = core.ROOT
    core.atomic_json(original_path, data)
    receipt_path = measured[-1]
    receipt = core.read_json(receipt_path)
    receipt["report_sha256"] = core.digest(root / original_path)
    core.atomic_json(receipt_path, receipt)
    assert tracking_actions.propose_tracking(p)["valid"] is False


@pytest.mark.parametrize("size", [(160.5, 320), (160, 321)])
def test_invalid_project_dimensions_are_not_silently_truncated(measured, size):
    p, _, _, _, _, _ = measured
    p["settings"].update(width=size[0], height=size[1])
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and result["errors"]


@pytest.mark.parametrize("field,value", [("probe", {"streams": [{"codec_type": "video", "width": 999, "height": 999}]}),
                                       ("kind", "image"), ("path", "assets/video/forged.mp4"), ("sha256", "f" * 64)])
def test_project_dict_cannot_forge_source_registration_geometry(measured, field, value):
    p, _, _, _, _, _ = measured
    p["assets"][0][field] = value
    result = tracking_actions.propose_tracking(p)
    assert result["valid"] is False and "registrado" in result["errors"][0]
