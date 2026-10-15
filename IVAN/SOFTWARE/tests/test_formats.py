"""Small real format corpus, isolated imports, streams, and browser proxies.

Fixtures contain geometric video and a tone, not human speech. ASR is never
loaded and no model is downloaded. Running requires SOFTWARE/.estado/tmp as
pytest --basetemp, as with the other integration tests.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image
import pytest

from studio import analysis, core
from test_api import REAL_ROOT, api_workspace

VIDEO = {"mp4": ("libx264", "aac"), "mov": ("libx264", "pcm_s16le"),
         "mkv": ("ffv1", "flac"), "webm": ("libvpx-vp9", "libopus"),
         "avi": ("mpeg4", "pcm_s16le"), "mxf": ("mpeg2video", "pcm_s16le")}
AUDIO = {"wav": "pcm_s16le", "mp3": "libmp3lame", "m4a": "aac", "flac": "flac", "ogg": "libvorbis"}


def command(root, args):
    nice = shutil.which("nice")
    binary = shutil.which("ffmpeg")
    if not binary:
        pytest.skip("FFmpeg required for format corpus")
    full = ([nice, "-n", "10"] if nice else []) + [binary, "-hide_banner", "-loglevel", "error", "-y", "-filter_threads", "1"] + args
    return subprocess.run(full, cwd=root, capture_output=True, timeout=30,
                          env={**os.environ, "TMPDIR": str(root / ".estado/tmp"), "CUDA_VISIBLE_DEVICES": "",
                               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"})


def check_generation(result, *, optional=False):
    if optional and result.returncode:
        pytest.skip("Installed build cannot generate fixture: " + result.stderr.decode("utf-8", "replace")[-300:])
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")


def receipt(name, value):
    folder = REAL_ROOT / ".estado/validacion/formatos"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")


@pytest.mark.parametrize("extension", list(VIDEO))
def test_real_video_container_import_analysis_and_required_browser_proxy(api_workspace, monkeypatch, extension):
    path = api_workspace / ("corpus." + extension)
    vcodec, acodec = VIDEO[extension]
    size, rate = ("720x576", 25) if extension == "mxf" else ("160x284", 25)
    args = ["-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration=0.4",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4",
            "-c:v", vcodec, "-pix_fmt", "yuv422p" if extension == "mxf" else "yuv420p", "-c:a", acodec,
            "-ar", "48000", "-threads", "1", "-shortest"]
    if vcodec == "libx264":
        args += ["-preset", "veryfast"]
    if vcodec == "libvpx-vp9":
        args += ["-deadline", "realtime", "-cpu-used", "8"]
    args += [str(path)]
    check_generation(command(api_workspace, args), optional=extension == "mxf")
    source_sha = core.digest(path)
    begin = time.perf_counter()
    asset = core.register_asset(path)
    elapsed = time.perf_counter() - begin
    assert asset["kind"] == "video" and asset["sha256"] == source_sha
    assert asset["duration"] == pytest.approx(.4, abs=.12)
    streams = asset["probe"]["streams"]
    assert next(s for s in streams if s["codec_type"] == "video")["codec_name"] == vcodec.removeprefix("lib").replace("x264", "h264").replace("vpx-vp9", "vp9")
    assert any(s["codec_type"] == "audio" for s in streams)
    p = core.create_project("Synthetic " + extension, asset["id"])
    monkeypatch.setattr(analysis, "transcribe", lambda *a, **kw: pytest.fail("Format analysis must not trigger ASR"))
    analyzed = analysis.analyze_project(copy.deepcopy(p), {"transcribe": False})
    assert len(analyzed["analysis"]["video"]) == 1 and len(analyzed["analysis"]["audio_tracks"]) == 1
    assert analyzed["analysis"]["voice_detection"] == "pending_asr"
    assert asset.get("waveform", {}).get("seconds", 0) > .3
    assert core.digest(path) == source_sha and core.digest(core.confined(asset["path"])) == source_sha
    if extension not in {"mp4", "webm"}:
        assert asset.get("preview_is_derivative") is True, asset
        assert asset.get("preview_provenance", {}).get("decode_ok") is True
        assert asset["preview_probe"]["streams"][0]["codec_name"] == "h264"
        assert asset["preview_provenance"]["approved_for_ascendia"] is False
    else:
        assert asset.get("preview_is_derivative") is False
    assert not any(p.is_file() for p in (api_workspace / ".estado/models").rglob("*"))
    receipt("video_" + extension, {"format": extension, "imported": True, "asset_kind": asset["kind"],
                                  "codecs": [s.get("codec_name") for s in streams], "duration": asset["duration"],
                                  "import_seconds": round(elapsed, 3), "voice_detection": analyzed["analysis"]["voice_detection"],
                                  "preview_is_derivative": asset.get("preview_is_derivative"),
                                  "original_sha256_preserved": True, "synthetic_tone_not_speech": True,
                                  "gpu_used": False, "audio_listened": False, "editorial_approved": False})


@pytest.mark.parametrize("extension", list(AUDIO))
def test_real_audio_format_is_audio_and_cannot_be_original_video(api_workspace, extension):
    path = api_workspace / ("tone." + extension)
    args = ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4",
            "-c:a", AUDIO[extension], "-threads", "1", str(path)]
    check_generation(command(api_workspace, args))
    before = core.digest(path)
    asset = core.register_asset(path)
    assert asset["kind"] == "audio"
    assert asset.get("waveform", {}).get("seconds", 0) > .3
    assert any(s["codec_type"] == "audio" for s in asset["probe"]["streams"])
    assert not any(s["codec_type"] == "video" for s in asset["probe"]["streams"])
    with pytest.raises(core.StudioError, match="video real"):
        core.create_project("Audio cannot be a reel", asset["id"])
    assert core.project_list() == [] and core.digest(path) == before
    receipt("audio_" + extension, {"format": extension, "imported": True, "asset_kind": "audio",
                                  "codecs": [s.get("codec_name") for s in asset["probe"]["streams"]],
                                  "waveform_seconds": asset["waveform"]["seconds"], "video_source_rejected": True,
                                  "synthetic_tone_not_speech": True, "gpu_used": False, "audio_listened": False})


def test_video_without_audio_reports_no_audio_without_loading_asr(api_workspace, monkeypatch):
    path = api_workspace / "silent_video.mp4"
    check_generation(command(api_workspace, ["-f", "lavfi", "-i", "color=c=red:size=160x284:rate=25:duration=0.4",
                                           "-c:v", "libx264", "-preset", "veryfast", "-an", "-threads", "1", str(path)]))
    asset = core.register_asset(path)
    p = core.create_project("Silent fixture", asset["id"])
    monkeypatch.setattr(analysis, "transcribe", lambda *args, **kwargs: pytest.fail("No audio must not reach ASR"))
    analyzed = analysis.analyze_project(p, {"transcribe": True})
    assert analyzed["analysis"]["voice_detection"] == "no_audio_track"
    assert analyzed["analysis"]["audio_tracks"] == []
    receipt("video_no_audio", {"imported": True, "voice_detection": "no_audio_track", "asr_called": False, "gpu_used": False})


def test_audio_cover_art_is_not_classified_as_video_source(api_workspace):
    cover = api_workspace / "cover.jpg"
    Image.new("RGB", (64, 64), (220, 30, 50)).save(cover)
    path = api_workspace / "audio_with_cover.m4a"
    check_generation(command(api_workspace, ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4",
                                           "-i", str(cover), "-map", "0:a", "-map", "1:v", "-c:a", "aac", "-c:v", "copy",
                                           "-disposition:v:0", "attached_pic", "-threads", "1", str(path)]), optional=True)
    asset = core.register_asset(path)
    assert asset["kind"] == "audio"
    pictures = [s for s in asset["probe"]["streams"] if s.get("codec_type") == "video"]
    assert pictures and all(s.get("disposition", {}).get("attached_pic") == 1 for s in pictures)
    with pytest.raises(core.StudioError, match="portada"):
        core.create_project("Cover is not a presenter", asset["id"])
    assert core.project_list() == []
    receipt("audio_attached_pic", {"imported": True, "asset_kind": asset["kind"], "attached_pic_detected": True,
                                  "video_source_rejected": True, "gpu_used": False, "audio_listened": False})


@pytest.mark.parametrize("extension", ["png", "jpg", "bmp", "tif", "tiff"])
def test_genuine_still_image_cannot_be_raw_video(api_workspace, extension):
    path = api_workspace / ("still." + extension)
    Image.new("RGB", (64, 96), (40, 50, 60)).save(path)
    original_hash = core.digest(path)
    asset = core.register_asset(path)
    assert asset["kind"] == "image" and core.digest(path) == original_hash
    if extension in {"tif", "tiff"}:
        assert asset["preview_is_derivative"] and asset["preview_path"].endswith(".png"), asset
        assert asset["preview_probe"]["streams"][0]["codec_name"] == "png"
        assert asset["sha256"] == original_hash and asset["preview_provenance"]["source_sha256"] == original_hash
        assert asset["preview_provenance"]["approved_for_ascendia"] is False
    with pytest.raises(core.StudioError, match="video real"):
        core.create_project("Still is not a reel", asset["id"])
    assert core.project_list() == []
    receipt("image_" + extension, {"format": extension, "imported": True, "asset_kind": asset["kind"],
                                  "video_source_rejected": True, "gpu_used": False})
