"""Own CPU segmentation fixtures; no actual reel edit or background replacement."""
import array
import copy
import hashlib
import json
from pathlib import Path
import shutil
import threading

from PIL import Image
import pytest

from studio import core, media_tools as media, segmentation as seg


@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    # Optional local integration: private portraits, models and runtimes are
    # never distributed. Pure option/confidence tests below need none of them.
    required = [core.ROOT / relative for relative in
                (seg.RUNTIME, '.estado/models/segmentation/local',
                 '.estado/validacion/segmentation/input_1s.mp4')]
    if not all(path.exists() for path in required):
        pytest.skip('Optional CPU segmentation integration needs an explicitly supplied local fixture and runtime/model; none are downloaded or bundled.')
    root = tmp_path_factory.mktemp("segmentation-own")
    assert root.resolve().is_relative_to(core.ROOT / ".estado/tmp")
    for relative in (seg.RUNTIME, ".estado/models/segmentation/local"):
        shutil.copytree(core.ROOT / relative, root / relative)
    source = root / "portrait.mp4"
    shutil.copyfile(core.ROOT / ".estado/validacion/segmentation/input_1s.mp4", source)
    asset = {"id": "own_segmentation_fixture", "path": "portrait.mp4", "sha256": media._hash(source)}
    return root, asset


def test_options_closed_finite_and_softening_opt_in():
    options = seg.validate_options({})
    assert options == seg.DEFAULTS and options is not seg.DEFAULTS
    assert options["duration"] is None and options["temporal_smoothing"] == 0
    assert options["max_width"] == 540 and options["max_height"] == 960
    assert seg.validate_options({"fps": 10., "max_width": 360})["fps"] == 10


@pytest.mark.parametrize("options", [None, {}, {"start": .2, "duration": .6},
    {"threshold": .05, "softness": 1, "feather": 8, "temporal_smoothing": .8},
    {"fps": 10, "max_width": 160, "max_height": 1080}])
def test_valid_parameter_boundaries(options):
    assert isinstance(seg.validate_options(options), dict)


@pytest.mark.parametrize("options", [[], {"duration": 30.01}, {"duration": 0}, {"duration": True},
    {"start": -1}, {"start": float("nan")}, {"threshold": float("inf")}, {"threshold": .049},
    {"threshold": .951}, {"softness": 0}, {"softness": 1.001}, {"feather": -1}, {"feather": 8.1},
    {"temporal_smoothing": True}, {"temporal_smoothing": .81}, {"fps": True}, {"fps": 10.5},
    {"fps": 31}, {"max_width": 161}, {"max_height": 1082}, {"model_url": "https://untrusted.example/weights"},
    {"output": "../outside.mov"}, {"gpu": True}])
def test_invalid_options_reject_before_any_processing(options):
    with pytest.raises(core.StudioError):
        seg.validate_options(options)


def floats(*values):
    data = array.array("f", values)
    if __import__("sys").byteorder != "little":
        data.byteswap()
    return data.tobytes()


def test_confidence_transfer_preserves_direction_and_soft_transition():
    result = seg._alpha(floats(0, .45, .5, .55, 1), (5, 1), seg.validate_options())
    values = list(result.tobytes())
    assert values[0] == 0 and values[-1] == 255 and 120 <= values[2] <= 135
    assert values == sorted(values)


def test_temporal_average_is_disabled_by_default_and_explicit_when_requested():
    old = Image.new("L", (1, 1), 255)
    current = seg._alpha(floats(0), (1, 1), seg.validate_options(), old)
    averaged = seg._alpha(floats(0), (1, 1), seg.validate_options({"temporal_smoothing": .5}), old)
    assert current.getpixel((0, 0)) == 0 and averaged.getpixel((0, 0)) in {127, 128}


@pytest.mark.parametrize("data,size", [(b"short", (1, 1)), (floats(float("nan")), (1, 1)),
    (floats(float("inf")), (1, 1)), (floats(-.1), (1, 1)), (floats(1.1), (1, 1)),
    (floats(.5), (True, 1)), (floats(.5), (0, 1)), (floats(.5), (257, 1)), (floats(.5), (2, 1))])
def test_invalid_confidence_bytes_and_shape_are_controlled(data, size):
    with pytest.raises(core.StudioError):
        seg._alpha(data, size, seg.validate_options())


def test_capability_is_read_only_and_presence_does_not_claim_execution(workspace, monkeypatch):
    root, _ = workspace
    before = {str(path): path.stat().st_mtime_ns for path in root.rglob("*") if path.is_file()}
    monkeypatch.setattr(seg, "_spawn", lambda *args, **kwargs: pytest.fail("Capability launched a process"))
    first = seg.capability(root)
    second = seg.capability(root)
    assert first["available"] and not first["verified_execution"] and not first["editorial_approved"]
    assert first["fingerprint"] == second["fingerprint"] and len(first["fingerprint"]) == 64
    assert first["device"] == "cpu" and first["gpu_used"] is False
    assert before == {str(path): path.stat().st_mtime_ns for path in root.rglob("*") if path.is_file()}


def test_environment_contains_only_private_cache_configuration(workspace):
    root, _ = workspace
    env = seg._environment(root)
    assert "HOME" not in env and "HEYGEN_API_KEY" not in env and "GEMINI_API_KEY" not in env
    assert env["CUDA_VISIBLE_DEVICES"] == "" and env["OMP_NUM_THREADS"] == "2"
    for key in ("TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        assert Path(env[key]).is_relative_to(root)


def test_invalid_source_and_hash_cannot_decode_or_replace(workspace, monkeypatch):
    root, asset = workspace
    monkeypatch.setattr(seg, "_run", lambda *args, **kwargs: pytest.fail("Invalid source was decoded"))
    for path in ("../outside.mp4", "/etc/passwd", "bad\x00.mp4"):
        with pytest.raises(core.StudioError):
            seg.process({"path": path}, root=root)
    bad = {**asset, "sha256": "f" * 64}
    with pytest.raises(core.StudioError, match="catálogo"):
        seg.process(bad, root=root)
    assert media._hash(root / asset["path"]) == asset["sha256"]


def test_oversize_rgba_budget_stops_before_model_or_full_decode(workspace, monkeypatch):
    root, asset = workspace
    monkeypatch.setattr(seg, "MAX_RGBA_BYTES", 1)
    monkeypatch.setattr(seg, "_infer", lambda *args: pytest.fail("Oversize run inferred a mask"))
    with pytest.raises(core.StudioError, match="2 GiB"):
        seg.process(asset, {"duration": .9, "fps": 10}, root)


def test_cancelled_operation_never_loads_model_or_creates_derivative(workspace, monkeypatch):
    root, asset = workspace
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(seg, "_runtime", lambda *args: pytest.fail("Already-cancelled operation loaded the model"))
    with pytest.raises(core.StudioError, match="cancelada"):
        seg.process(asset, {"duration": .7}, root, cancel=cancel)


def test_cancellation_during_real_inference_publishes_nothing(workspace):
    root, asset = workspace
    cancel = threading.Event()
    before = set((root / ".estado/tools").glob("*"))

    def progress(value, message):
        if value > .15:
            cancel.set()

    with pytest.raises(core.StudioError, match="cancelada"):
        seg.process(asset, {"duration": .4, "fps": 10}, root, progress=progress, cancel=cancel)
    assert set((root / ".estado/tools").glob("*")) == before
    assert media._hash(root / asset["path"]) == asset["sha256"]


def test_actual_person_mask_mov_audio_cfr_evidence_and_reuse(workspace):
    root, asset = workspace
    source_before = media._hash(root / asset["path"])
    options = {"duration": .25, "fps": 10, "max_width": 160, "max_height": 284}
    result = seg.process(asset, options, root)
    assert result["frame_count"] == 3 and result["duration"] == pytest.approx(.3, abs=.015)
    assert result["width"] <= 160 and result["height"] <= 284
    assert result["browser"] == {"count": 3, "labels": ["selfie"], "confidence_mask_channels": 1, "delegate": "CPU"}
    streams = result["probe"]["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    audio = next(s for s in streams if s["codec_type"] == "audio")
    assert video["codec_name"] == "qtrle" and video["pix_fmt"] == "argb" and audio["codec_name"] == "pcm_s16le"
    assert audio["sample_rate"] == "48000" and float(audio["duration"]) == pytest.approx(.25, abs=1 / 48000)
    assert result["provenance"]["changes_narration_timing"] is False
    assert result["provenance"]["source_asset_id"] == asset["id"] and result["provenance"]["source_sha256"] == source_before
    assert result["provenance"]["requested_duration"] == .25 and result["provenance"]["encoded_duration"] == .3
    assert result["verification"]["alpha_encoded_pixels_verified"] is True
    assert result["verification"]["approved"] is False and result["provenance"]["qc"] == "pending"
    assert min(row["alpha_min"] for row in result["frame_measurements"]) == 0
    assert max(row["alpha_max"] for row in result["frame_measurements"]) > 240
    roles = {row["role"] for row in result["evidence"]}
    assert roles == {"source", "alpha", "checkerboard", "rgba", "encoded_rgba"}
    for row in result["evidence"]:
        assert row["path"].startswith(".estado/segmentation/evidence/") and media._hash(root / row["path"]) == row["sha256"]
    repeated = seg.process(asset, options, root)
    assert repeated["reused"] and repeated["sha256"] == result["sha256"]
    assert seg.capability(root)["verified_execution"] and media._hash(root / asset["path"]) == source_before
    # Compare PCM sample bytes to the same original selected audio span.
    original = root / ".estado/tmp/expected_audio.pcm"
    derivative = root / ".estado/tmp/output_audio.pcm"
    for input_path, output_path in ((root / asset["path"], original), (root / result["path"], derivative)):
        media._run("ffmpeg", [*media._base(), *media._input(input_path, 0, .25), "-map", "0:a:0", "-vn",
                             "-c:a", "pcm_s16le", "-ar", "48000", "-threads", "2", "-f", "s16le", "-y", str(output_path)], root)
    assert original.read_bytes() == derivative.read_bytes()
    (root / result["evidence"][0]["path"]).write_bytes(b"altered evidence")
    assert not seg.capability(root)["verified_execution"]
    with pytest.raises(core.StudioError, match="evidencia"):
        seg.process(asset, options, root)
