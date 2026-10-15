"""Adversarial cutout tests: private fixtures, no inference or real approvals.

Run with --basetemp=.estado/tmp/pytest_segmentation_audit and cache disabled.
The synthetic media/receipts below test validation only; they never constitute
evidence that MediaPipe ran, a person listened, or a client approved an edit.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import threading
import time
from types import SimpleNamespace

from PIL import Image
import pytest

from studio import core, segmentation as seg
from test_core import sandbox


@pytest.fixture
def prepared(sandbox, monkeypatch):
    (sandbox / ".estado/tools").mkdir(parents=True, exist_ok=True)
    source = sandbox / "assets/video/source.mp4"
    source.write_bytes(b"private fixture source; never decoded")
    asset = {"id": "fixture_source", "path": str(source.relative_to(sandbox)),
             "kind": "video", "sha256": core.digest(source)}
    runtime = {"engine": seg.ENGINE, "runtime_version": "1.1.0", "runtime_files": {},
               "model_sha256": seg.MODEL_SHA256, "confidence_mask_channels": 1,
               "person_mask_index": 0, "label": "selfie", "binaries": {},
               "pixel_code_sha256": {"segmentation.py": core.digest(seg.__file__), "media_tools.py": core.digest(seg.media.__file__)}}
    monkeypatch.setattr(seg, "_runtime", lambda root: copy.deepcopy(runtime))
    monkeypatch.setattr(seg, "_run", lambda *args, **kw: pytest.fail("no subprocess expected"))
    monkeypatch.setattr(seg, "_spawn", lambda *args, **kw: pytest.fail("no process expected"))
    return sandbox, source, asset, runtime


def identity_key(source_sha, options, runtime):
    value = {"source_sha256": source_sha, "parameters": options, "runtime": runtime}
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]


def write_marker(root, receipt, value):
    marker = root / ".estado/segmentation/integration.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"receipt_path": str(receipt.relative_to(root)),
                                 "semantic_receipt_sha256": seg.semantic_receipt_digest(value) if isinstance(value, dict) else "0" * 64}))
    return marker


def fixture_receipt(prepared, *, options=None):
    root, source, asset, runtime = prepared
    options = seg.validate_options({"duration": .2, "fps": 10} if options is None else options)
    key = identity_key(core.digest(source), options, runtime)
    output = root / f".estado/tools/{key}.mov"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"fixture alpha video; not decoded")
    evidence = []
    for frame in range(2):
        for role in ("source", "alpha", "checkerboard", "rgba", "encoded"):
            name = f"encoded_{frame:04d}.png" if role == "encoded" else f"sample_{frame:04d}_{role}.png"
            path = root / f".estado/segmentation/evidence/{key}/{name}"
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (160, 160), (50, 80, 100, frame * 255)).save(path)
            evidence.append({"path": str(path.relative_to(root)), "sha256": core.digest(path),
                             "index": frame, "output_time": frame / options["fps"],
                             "role": "encoded_rgba" if role == "encoded" else role})
    result = {"kind": "process", "operation": seg.OPERATION, "path": str(output.relative_to(root)),
              "identity": {"source_sha256": core.digest(source), "parameters": copy.deepcopy(options), "runtime": copy.deepcopy(runtime)},
              "sha256": core.digest(output), "duration": .2, "width": 160, "height": 160,
              "fps": 10, "frame_count": 2, "runtime": copy.deepcopy(runtime), "reused": False,
              "md5": core.digest(output, "md5"), "size": output.stat().st_size,
              "probe": {"streams": [{"codec_type": "video", "codec_name": "qtrle", "pix_fmt": "argb", "width": 160, "height": 160}], "format": {"duration": ".2"}},
              "frame_measurements": [{"index": i, "output_time": i / 10, "alpha_min": 0, "alpha_max": 255} for i in range(2)],
              "browser": {"count": 2, "labels": ["selfie"], "confidence_mask_channels": 1, "delegate": "CPU"},
              "verification": {"decode_ok": True, "alpha_encoded_pixels_verified": True,
                               "visual": False, "audio": False, "approved": False,
                               "visual_reviewed": False, "audio_listened": False, "editorial_approved": False},
              "evidence": evidence,
              "provenance": {"operation": seg.OPERATION, "source_asset_id": asset["id"],
                             "source_path": asset["path"], "source_sha256": core.digest(source),
                             "parameters": options, "source_span": {"start": options["start"], "duration": .2},
                             "requested_duration": .2, "encoded_duration": .2, "cfr_pts": [0., .1],
                             "changes_narration_timing": False, "audio_preserved": False,
                             "gpu_used": False, "delegate": "CPU", "workers": 1, "ffmpeg_threads": 2,
                             "qc": "pending", "visual_reviewed": False, "audio_listened": False,
                             "approved_for_ascendia": False}}
    receipt = root / f".estado/tools/{key}.json"
    receipt.write_text(json.dumps(result), encoding="utf-8")
    return result, receipt, output


@pytest.mark.parametrize("key", list(seg.DEFAULTS))
@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), "1", [], {}])
def test_option_numbers_reject_bool_nonfinite_and_objects(key, value):
    with pytest.raises(core.StudioError):
        seg.validate_options({key: value})


@pytest.mark.parametrize("options", [[], False, "", {1: 2}, {"model_url": "https://example.invalid/model"},
                                     {"max_width": 161}, {"max_height": 159}, {"fps": 10.5},
                                     {"duration": 30.01}, {"threshold": 0}, {"softness": 0},
                                     {"temporal_smoothing": .81}, {"feather": 9}, {"start": -1}])
def test_options_closed_and_bounded(options):
    with pytest.raises(core.StudioError):
        seg.validate_options(options)


def test_options_keep_duration_none_and_do_not_mutate_input():
    supplied = {"duration": None, "fps": 10., "max_width": 160., "max_height": 1080.}
    result = seg.validate_options(supplied)
    assert result["duration"] is None and type(result["fps"]) is int
    assert supplied == {"duration": None, "fps": 10., "max_width": 160., "max_height": 1080.}
    result["threshold"] = .9
    assert seg.DEFAULTS["threshold"] == .5


def test_person_mask_polarity_and_transfer_are_not_background_inversion():
    raw = struct.pack("<5f", 0, .45, .5, .55, 1)
    mask = seg._alpha(raw, (5, 1), seg.validate_options({}))
    pixels = list(mask.tobytes())
    assert pixels[0] == 0 and pixels[-1] == 255 and pixels[2] == 128
    assert pixels == sorted(pixels)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -.1, 1.1])
def test_model_mask_rejects_invalid_confidence(value):
    with pytest.raises(core.StudioError):
        seg._alpha(struct.pack("<f", value), (1, 1), seg.validate_options({}))


@pytest.mark.parametrize("dimensions,values", [((2, 2), [1]), ((0, 1), []), ((257, 1), [0] * 257)])
def test_model_mask_dimensions_match_payload_and_are_bounded(dimensions, values):
    with pytest.raises(core.StudioError):
        seg._alpha(struct.pack("<" + "f" * len(values), *values), dimensions, seg.validate_options({}))


def test_temporal_smoothing_is_opt_in_and_keeps_previous_mask_intact():
    previous = Image.new("L", (1, 1), 255)
    raw = struct.pack("<f", 0)
    assert seg._alpha(raw, (1, 1), seg.validate_options({}), previous).getpixel((0, 0)) == 0
    softened = seg._alpha(raw, (1, 1), seg.validate_options({"temporal_smoothing": .8}), previous)
    assert softened.getpixel((0, 0)) == 204 and previous.getpixel((0, 0)) == 255


def test_cancelled_before_processing_never_probes_or_creates_output(prepared):
    root, source, asset, _ = prepared
    before = source.read_bytes()
    cancel = threading.Event(); cancel.set()
    with pytest.raises(core.StudioError, match="cancelada"):
        seg.process(asset, {"duration": .2}, root, cancel=cancel)
    assert source.read_bytes() == before and not list((root / ".estado/tools").glob("*"))


def test_changed_catalog_source_is_rejected_before_probe(prepared):
    root, source, asset, _ = prepared
    source.write_bytes(b"changed private source")
    with pytest.raises(core.StudioError, match="catálogo") as error:
        seg.process(asset, {"duration": .2}, root)
    assert error.value.status == 409 and source.read_bytes() == b"changed private source"


@pytest.mark.parametrize("relative", ["../outside.mp4", ".estado/tmp/../../../../outside.mp4"])
def test_source_traversal_is_rejected_before_probe(prepared, relative):
    root, _, asset, _ = prepared
    asset["path"] = relative
    with pytest.raises(core.StudioError) as error:
        seg.process(asset, {}, root)
    assert error.value.status == 403


def test_source_symlink_escape_and_destination_alias_are_rejected(prepared):
    root, source, asset, _ = prepared
    outside = root.parent / "outside.mp4"; outside.write_bytes(b"preserve")
    escape = root / "escape.mp4"; escape.symlink_to(outside)
    asset["path"] = "escape.mp4"
    with pytest.raises(core.StudioError) as error: seg.process(asset, {}, root)
    assert error.value.status == 403 and outside.read_bytes() == b"preserve"
    alias = root / ".estado/tools/alias.mov"; alias.symlink_to(source)
    with pytest.raises(core.StudioError) as error: seg._destination(root, alias)
    assert error.value.status == 403 and source.exists()


def test_missing_receipt_keeps_existing_output_and_source(prepared):
    root, source, asset, _ = prepared
    _, receipt, output = fixture_receipt(prepared)
    receipt.unlink(); before = output.read_bytes()
    with pytest.raises(core.StudioError, match="carece de recibo"):
        seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert output.read_bytes() == before and source.exists()


@pytest.mark.parametrize("target", ["source", "output", "evidence"])
def test_cached_byte_changes_reject_reuse_without_overwriting(prepared, target):
    root, source, asset, runtime = prepared
    result, receipt, output = fixture_receipt(prepared)
    path = {"source": source, "output": output, "evidence": root / result["evidence"][0]["path"]}[target]
    path.write_bytes(b"mutation must survive failed reuse")
    with pytest.raises(core.StudioError): seg._verify_cache(result, root, runtime)
    assert path.read_bytes() == b"mutation must survive failed reuse" and receipt.exists()


@pytest.mark.parametrize("field,value", [("decode_ok", False), ("decode_ok", "true"),
                                        ("decode_ok", 1), ("alpha_encoded_pixels_verified", False)])
def test_unverified_cache_cannot_claim_verified_execution(prepared, field, value):
    root, _, _, runtime = prepared
    result, _, _ = fixture_receipt(prepared)
    result["verification"][field] = value
    with pytest.raises(core.StudioError): seg._verify_cache(result, root, runtime)


@pytest.mark.parametrize("field,value", [("verification", []), ("provenance", []),
                                        ("evidence", {}), ("browser", []), ("frame_count", True),
                                        ("frame_count", 0), ("path", "assets/video/source.mp4")])
def test_malformed_cache_objects_fail_with_domain_error(prepared, field, value):
    root, _, _, runtime = prepared
    result, _, _ = fixture_receipt(prepared); result[field] = value
    with pytest.raises(core.StudioError): seg._verify_cache(result, root, runtime)


def test_cache_receipt_for_other_parameters_cannot_be_used_for_request(prepared):
    root, _, asset, runtime = prepared
    old, _, old_output = fixture_receipt(prepared)
    requested = seg.validate_options({"duration": .2, "fps": 10, "threshold": .7})
    requested_key = identity_key(asset["sha256"], requested, runtime)
    sentinel = root / f".estado/tools/{requested_key}.mov"; sentinel.write_bytes(b"existing requested derivative")
    swapped = root / f".estado/tools/{requested_key}.json"; swapped.write_text(json.dumps(old))
    with pytest.raises(core.StudioError) as error: seg.process(asset, requested, root)
    assert error.value.status == 409 and sentinel.read_bytes() == b"existing requested derivative" and old_output.exists()


def test_cache_path_is_not_allowed_to_alias_another_derivative_without_registered_binding(prepared):
    root, _, asset, _ = prepared
    result, _, output = fixture_receipt(prepared)
    target = root / ".estado/tools/target.mov"; output.rename(target); output.symlink_to(target)
    with pytest.raises(core.StudioError): seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert output.is_symlink() and target.read_bytes() == b"fixture alpha video; not decoded"


def bind_fixture_to_real_catalog(prepared):
    root, _, asset, _ = prepared
    result, receipt, output = fixture_receipt(prepared)
    target = root / "assets/video/fixture_canonical.mov"; target.write_bytes(output.read_bytes())
    canonical = {"id": "fixture_canonical", "path": str(target.relative_to(root)), "kind": "video",
                 "name": "fixture_canonical.mov", "sha256": core.digest(target), "md5": core.digest(target, "md5"),
                 "size": target.stat().st_size, "duration": .2, "probe": copy.deepcopy(result["probe"]), "metadata": {},
                 "verification": {"visual": False, "audio": False, "rights": "pending", "evidence": []}}
    core.atomic_json(".estado/assets.json", [copy.deepcopy(asset), canonical])
    write_marker(root, receipt, result)
    bound = seg.media.bind_canonical(result, canonical, root)
    return bound, receipt, output, target, canonical


def test_registered_canonical_binding_reuses_without_duplicate_bytes_or_losing_status(prepared):
    root, source, asset, runtime = prepared
    before = source.read_bytes()
    _, receipt, output, target, canonical = bind_fixture_to_real_catalog(prepared)
    assert output.is_symlink() and output.resolve() == target
    recorded = json.loads(receipt.read_text())
    assert recorded["canonical_asset_id"] == canonical["id"]
    seg._verify_cache(recorded, root, runtime)
    result = seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert result["reused"] is True and result["canonical_asset_id"] == canonical["id"]
    status = seg.capability(root)
    assert status["verified_execution"] is True and status["editorial_approved"] is False
    assert source.read_bytes() == before and output.is_symlink()


@pytest.mark.parametrize("mutation", ["missing_catalog_id", "catalog_hash", "catalog_kind", "binding_path"])
def test_canonical_binding_requires_exact_live_catalog_asset(prepared, mutation):
    root, _, _, runtime = prepared
    _, receipt, output, target, canonical = bind_fixture_to_real_catalog(prepared)
    recorded = json.loads(receipt.read_text())
    if mutation == "missing_catalog_id": recorded["canonical_asset_id"] = "absent"
    elif mutation == "binding_path": recorded["canonical_path"] = "assets/video/source.mp4"
    else:
        rows = core.assets()
        live = next(row for row in rows if row["id"] == canonical["id"])
        live["sha256" if mutation == "catalog_hash" else "kind"] = "0" * 64 if mutation == "catalog_hash" else "audio"
        core.atomic_json(".estado/assets.json", rows)
    with pytest.raises(core.StudioError): seg._verify_cache(recorded, root, runtime)
    assert target.read_bytes() == b"fixture alpha video; not decoded" and output.is_symlink()


def test_fixture_cache_is_valid_before_adversarial_mutations(prepared):
    root, _, asset, runtime = prepared
    result, _, output = fixture_receipt(prepared)
    seg._verify_cache(result, root, runtime)
    reused = seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert reused["reused"] is True and reused["sha256"] == core.digest(output)
    assert reused["verification"]["visual"] is False and reused["verification"]["audio"] is False
    assert reused["verification"]["approved"] is False


@pytest.mark.parametrize("change", ["source", "runtime", "cancel"])
def test_cache_revalidates_cancel_and_source_runtime_after_receipt_verification(prepared, monkeypatch, change):
    root, source, asset, runtime = prepared
    _, _, output = fixture_receipt(prepared)
    verify = seg._verify_cache
    cancel = threading.Event()
    def mutation_after_verification(*args):
        verify(*args)
        if change == "source": source.write_bytes(b"source changed during cache validation")
        elif change == "runtime": runtime["model_sha256"] = "0" * 64
        else: cancel.set()
    monkeypatch.setattr(seg, "_verify_cache", mutation_after_verification)
    with pytest.raises(core.StudioError): seg.process(asset, {"duration": .2, "fps": 10}, root, cancel=cancel)
    assert output.read_bytes() == b"fixture alpha video; not decoded"


@pytest.mark.parametrize("field,value", [("duration", -1), ("duration", float("nan")),
                                        ("duration", 10), ("fps", True), ("fps", 30),
                                        ("width", True), ("height", 5000), ("width", 161)])
def test_cache_cannot_forge_measured_geometry_or_cfr_timing(prepared, field, value):
    root, _, _, runtime = prepared
    result, _, _ = fixture_receipt(prepared)
    result[field] = value
    with pytest.raises(core.StudioError): seg._verify_cache(result, root, runtime)


@pytest.mark.parametrize("mutation", ["duplicate", "missing_encoded", "wrong_frame", "wrong_time", "foreign_key"])
def test_cache_evidence_is_bound_to_frames_roles_and_this_derivative(prepared, mutation):
    root, _, _, runtime = prepared
    result, _, _ = fixture_receipt(prepared)
    if mutation == "duplicate": result["evidence"] = [copy.deepcopy(result["evidence"][0])] * 5
    elif mutation == "missing_encoded": result["evidence"] = [row for row in result["evidence"] if row["role"] != "encoded_rgba"]
    elif mutation == "wrong_frame": result["evidence"][0]["index"] = 900
    elif mutation == "wrong_time": result["evidence"][0]["output_time"] = 500
    else:
        row = result["evidence"][0]
        old = root / row["path"]
        foreign = root / (".estado/segmentation/evidence/" + "f" * 24 + "/" + old.name)
        foreign.parent.mkdir(parents=True); foreign.write_bytes(old.read_bytes())
        row["path"] = str(foreign.relative_to(root))
    with pytest.raises(core.StudioError): seg._verify_cache(result, root, runtime)


@pytest.mark.parametrize("cached", [[], None, 1, "bad", {"operation": seg.OPERATION, "verification": []}])
def test_capability_bad_receipt_never_raises_or_claims_execution(prepared, cached):
    root, _, _, _ = prepared
    receipt = root / ".estado/tools/fixture.json"; receipt.write_text(json.dumps(cached))
    write_marker(root, receipt, cached)
    status = seg.capability(root)
    assert status["available"] and status["verified_execution"] is False
    assert status["editorial_approved"] is False and status.get("reason")


def test_capability_prepared_model_alone_has_no_execution_claim(prepared):
    root, _, _, _ = prepared
    status = seg.capability(root)
    assert status["available"] and not status["verified_execution"] and not status["editorial_approved"]


def test_capability_marker_does_not_accept_missing_encoded_alpha_verification(prepared):
    root, _, _, _ = prepared
    result, receipt, _ = fixture_receipt(prepared)
    result["verification"]["alpha_encoded_pixels_verified"] = False
    receipt.write_text(json.dumps(result))
    write_marker(root, receipt, result)
    status = seg.capability(root)
    assert status["available"] and status["verified_execution"] is False and not status["editorial_approved"]


def test_expired_deadline_fails_immediately():
    with pytest.raises(core.StudioError, match="excedido"): seg._check(None, time.monotonic() - 1)


def install_probe_stub(prepared, monkeypatch, info, *, geometry=(160, 160), diagnostic=None):
    root, _, _, runtime = prepared
    runtime["binaries"] = {key: {"path": str(root / (key + "_fixture"))} for key in ("ffmpeg", "ffprobe")}
    calls = []
    def fake_run(args, root_arg, work, cancel, deadline, tag):
        calls.append((tag, list(args)))
        if tag == "input_probe": return json.dumps(info).encode(), b""
        if tag == "geometry": Image.new("RGB", geometry).save(args[-1]); return b"", b""
        if tag == "decode":
            count = math.ceil(float(info["format"]["duration"]) * 10 - 1e-9)
            Path(args[-1]).write_bytes(bytes(geometry[0] * geometry[1] * 4 * count))
            if diagnostic is not None: return b"", diagnostic
            return b"", b"\n".join(f"n: {i} pts: {i} pts_time:{i/10:.8f}".encode() for i in range(count))
        pytest.fail("unexpected subprocess: " + tag)
    monkeypatch.setattr(seg, "_run", fake_run)
    return calls


def probe_info(duration=1., **video):
    return {"streams": [{"index": 1, "codec_type": "video", "codec_name": "h264",
                         "width": 160, "height": 160, "sample_aspect_ratio": "1:1", **video}],
            "format": {"duration": str(duration)}}


@pytest.mark.parametrize("transfer", ["smpte2084", "arib-std-b67"])
def test_hdr_never_silently_segmented_as_sdr(prepared, monkeypatch, transfer):
    root, source, asset, _ = prepared
    calls = install_probe_stub(prepared, monkeypatch, probe_info(color_transfer=transfer))
    with pytest.raises(core.StudioError, match="HDR"): seg.process(asset, {"fps": 10}, root)
    assert [c[0] for c in calls] == ["input_probe"] and source.exists()


def test_default_duration_is_full_remainder_and_never_truncates_over_limit(prepared, monkeypatch):
    root, source, asset, _ = prepared
    calls = install_probe_stub(prepared, monkeypatch, probe_info(30.01))
    with pytest.raises(core.StudioError, match="tramo válido"): seg.process(asset, {}, root)
    assert [c[0] for c in calls] == ["input_probe"] and source.exists()


def test_memory_bound_rejects_before_raw_decode(prepared, monkeypatch):
    root, source, asset, _ = prepared
    calls = install_probe_stub(prepared, monkeypatch, probe_info())
    monkeypatch.setattr(seg, "MAX_RGBA_BYTES", 100)
    with pytest.raises(core.StudioError, match="2 GiB"): seg.process(asset, {"fps": 10}, root)
    assert [c[0] for c in calls] == ["input_probe", "geometry"] and source.exists()


def test_disk_budget_includes_raw_encoder_and_second_video_copy_for_audio(prepared, monkeypatch):
    root, source, asset, _ = prepared
    info = probe_info()
    info["streams"].append({"index": 2, "codec_type": "audio", "codec_name": "aac"})
    calls = install_probe_stub(prepared, monkeypatch, info)
    run = seg._run
    def reject_decode(*args, **kwargs):
        if args[-1] == "decode": pytest.fail("disk budget must stop before allocating raw video")
        return run(*args, **kwargs)
    monkeypatch.setattr(seg, "_run", reject_decode)
    raw_bytes = 10 * 160 * 160 * 4
    available = 256 * 1024 ** 2 + raw_bytes * 5 // 2
    monkeypatch.setattr(seg.shutil, "disk_usage", lambda path: SimpleNamespace(free=available))
    with pytest.raises(core.StudioError, match="espacio"): seg.process(asset, {"fps": 10}, root)
    assert [c[0] for c in calls] == ["input_probe", "geometry"] and source.exists()


def test_noninteger_duration_requires_measured_count_and_cfr_pts(prepared, monkeypatch):
    root, _, asset, _ = prepared
    diagnostic = b"\n".join(f"n: {i} pts: {i} pts_time:{i/10+.025:.8f}".encode() for i in range(11))
    calls = install_probe_stub(prepared, monkeypatch, probe_info(1.05), diagnostic=diagnostic)
    with pytest.raises(core.StudioError, match="CFR"): seg.process(asset, {"fps": 10}, root)
    decode_args = next(args for tag, args in calls if tag == "decode")
    filter_value = decode_args[decode_args.index("-vf") + 1]
    assert "trim=end_frame=11" in filter_value and "fps=10" in filter_value


def test_probe_and_decode_inputs_are_local_whitelisted_with_cpu_threads(prepared, monkeypatch):
    root, _, asset, _ = prepared
    calls = install_probe_stub(prepared, monkeypatch, probe_info(), diagnostic=b"wrong PTS")
    with pytest.raises(core.StudioError): seg.process(asset, {"fps": 10}, root)
    for tag, args in calls:
        assert args[args.index("-protocol_whitelist") + 1] == "file,pipe"
        assert args[args.index("-format_whitelist") + 1] == seg.media.FORMATS
        if tag != "input_probe":
            assert "-noautorotate" not in args
            assert all(args[i + 1] == "2" for i, arg in enumerate(args) if arg in {"-threads", "-filter_threads", "-filter_complex_threads"})
            assert "reset_sar=1" in args[args.index("-vf") + 1]


def install_pipeline_stub(prepared, monkeypatch, *, audio=True, wrong_pixels=False, decode_count=2,
                          output_audio=True, after_infer=None):
    """Exercise commit/rollback orchestration without executing media engines."""
    root, _, _, runtime = prepared
    model = root / seg.MODEL; model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"private fixture model; never loaded")
    for name in ("ffmpeg", "ffprobe"):
        path = root / (name + "_fixture"); path.write_bytes(b"not executable")
        runtime["binaries"][name] = {"path": str(path), "resolved": str(path),
                                     "signature": list(seg._signature(path)), "sha256": core.digest(path)}
    calls = []
    def fake_run(args, root_arg, work, cancel, deadline, tag):
        calls.append((tag, list(args)))
        if tag == "input_probe":
            info = probe_info(.2)
            if audio: info["streams"].insert(0, {"index": 0, "codec_type": "audio", "codec_name": "aac"})
            return json.dumps(info).encode(), b""
        if tag == "geometry": Image.new("RGB", (160, 160)).save(args[-1]); return b"", b""
        if tag == "decode":
            Path(args[-1]).write_bytes(bytes(2 * 160 * 160 * 4))
            return b"", b"n: 0 pts: 0 pts_time:0\nn: 1 pts: 1 pts_time:0.1"
        if tag == "audio": Path(args[-1]).write_bytes(b"private fixture alpha and PCM media"); return b"", b""
        if tag == "output_probe":
            info = {"streams": [{"codec_type": "video", "codec_name": "qtrle", "pix_fmt": "argb", "width": 160, "height": 160}],
                    "format": {"duration": ".2"}}
            if audio and output_audio: info["streams"].append({"codec_type": "audio", "codec_name": "pcm_s16le"})
            return json.dumps(info).encode(), b""
        if tag == "full_decode": return f"frame={decode_count}\n".encode(), b""
        if tag.startswith("alpha_"):
            frame = int(tag.split("_")[1])
            with Image.open(work / f"sample_{frame:04d}_rgba.png") as image:
                pixels = image.convert("RGBA")
            if wrong_pixels: pixels.putpixel((0, 0), (0, 0, 0, 255))
            pixels.save(args[-1]); return b"", b""
        pytest.fail("unexpected subprocess: " + tag)
    def fake_spawn(args, root_arg, stdout, stderr, stdin=None, **kwargs):
        calls.append(("encoder", list(args)))
        Path(args[-1]).write_bytes(b"private fixture alpha media")
        return SimpleNamespace(stdin=io.BytesIO(), poll=lambda: 0, returncode=0)
    def fake_infer(raw, size, count, opts, encoder, runtime_arg, root_arg, work, cancel, deadline, progress, guard):
        rows = []
        for index in range(count):
            guard(index)
            for role in ("source", "alpha", "checkerboard", "rgba"):
                path = work / f"sample_{index:04d}_{role}.png"
                Image.new("RGBA", size, (50, 80, 100, index * 255)).save(path)
                rows.append({"local": path, "role": role, "index": index, "output_time": index / opts["fps"]})
        if after_infer: after_infer(model)
        return {"evidence": rows, "measurements": [{"index": i, "output_time": i / opts["fps"],
                "alpha_min": 0, "alpha_max": 255} for i in range(count)],
                "browser": {"count": count, "labels": ["selfie"], "confidence_mask_channels": 1, "delegate": "CPU"}}
    monkeypatch.setattr(seg, "_run", fake_run)
    monkeypatch.setattr(seg, "_spawn", fake_spawn)
    monkeypatch.setattr(seg, "_infer", fake_infer)
    return calls


def assert_no_promoted_outputs(root):
    assert not list((root / ".estado/tools").glob("*.mov"))
    assert not list((root / ".estado/tools").glob("*.json"))
    assert not (root / ".estado/segmentation/integration.json").exists()
    assert not list((root / ".estado/segmentation/evidence").rglob("*.png"))


@pytest.mark.parametrize("audio", [False, True])
def test_pipeline_metadata_does_not_approve_original_and_preserves_explicit_audio_mapping(prepared, monkeypatch, audio):
    root, source, asset, _ = prepared
    before = source.read_bytes()
    calls = install_pipeline_stub(prepared, monkeypatch, audio=audio)
    result = seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert source.read_bytes() == before and result["path"] != asset["path"]
    assert result["provenance"]["audio_preserved"] is audio
    assert result["provenance"]["approved_for_ascendia"] is False
    assert result["provenance"]["visual_reviewed"] is False and result["provenance"]["audio_listened"] is False
    assert result["verification"]["approved"] is False
    audio_calls = [args for tag, args in calls if tag == "audio"]
    assert len(audio_calls) == int(audio)
    if audio:
        args = audio_calls[0]
        assert "1:a:0" in args and "pcm_s16le" in args and "48000" in args
        assert args[args.index("-af") + 1] == "asetpts=PTS-STARTPTS"


@pytest.mark.parametrize("failure", ["lost_audio", "missing_frames", "alpha_pixels"])
def test_decode_audio_and_encoded_alpha_failures_never_promote(prepared, monkeypatch, failure):
    root, source, asset, _ = prepared
    before = source.read_bytes()
    install_pipeline_stub(prepared, monkeypatch, output_audio=failure != "lost_audio",
                          decode_count=1 if failure == "missing_frames" else 2,
                          wrong_pixels=failure == "alpha_pixels")
    with pytest.raises(core.StudioError): seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert_no_promoted_outputs(root)
    assert source.read_bytes() == before


@pytest.mark.parametrize("mutation", ["source", "model"])
def test_source_or_model_mutation_during_inference_never_promotes(prepared, monkeypatch, mutation):
    root, source, asset, _ = prepared
    def mutate(model): (source if mutation == "source" else model).write_bytes(b"changed after inference")
    install_pipeline_stub(prepared, monkeypatch, after_infer=mutate)
    with pytest.raises(core.StudioError, match="cambió"): seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert_no_promoted_outputs(root)
    assert source.read_bytes() == (b"changed after inference" if mutation == "source" else b"private fixture source; never decoded")


def test_cancel_just_before_commit_discards_evidence_and_mov(prepared, monkeypatch):
    root, source, asset, _ = prepared
    install_pipeline_stub(prepared, monkeypatch)
    cancel = threading.Event()
    def progress(value, message):
        if value >= .98: cancel.set()
    with pytest.raises(core.StudioError, match="cancelada"): seg.process(asset, {"duration": .2, "fps": 10}, root, progress=progress, cancel=cancel)
    assert_no_promoted_outputs(root)
    assert source.read_bytes() == b"private fixture source; never decoded"


def test_source_mutation_after_receipt_link_rolls_back_all_promoted_files(prepared, monkeypatch):
    root, source, asset, _ = prepared
    install_pipeline_stub(prepared, monkeypatch)
    original_link = seg.os.link
    def mutate_at_last_link(a, b, *args, **kwargs):
        original_link(a, b, *args, **kwargs)
        if Path(b).suffix == ".json": source.write_bytes(b"changed concurrently at publication")
    monkeypatch.setattr(seg.os, "link", mutate_at_last_link)
    with pytest.raises(core.StudioError, match="cambió"): seg.process(asset, {"duration": .2, "fps": 10}, root)
    assert_no_promoted_outputs(root)
    assert source.read_bytes() == b"changed concurrently at publication"

