"""Real, small FFmpeg transformations using self-owned local fixture footage."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import queue

import pytest

from studio import media_tools as tools
from studio.core import StudioError
from studio import core, analysis, jobs

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def media_workspace(tmp_path_factory):
    folder = tmp_path_factory.mktemp("media-tools")
    assert folder.resolve().is_relative_to((ROOT / ".estado/tmp").resolve())
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg/FFprobe are required for actual media tools")
    (folder / ".estado/tmp").mkdir(parents=True)
    source = folder / "source.mp4"
    tools._run("ffmpeg", ["-nostdin", "-v", "error", "-filter_complex_threads", "2", "-y",
                         "-f", "lavfi", "-i", "color=c=red:s=160x284:r=10:d=1",
                         "-f", "lavfi", "-i", "color=c=blue:s=160x284:r=10:d=1",
                         "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
                         "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-threads", "2", str(source)], folder)
    greenscreen = folder / "green.mp4"
    tools._run("ffmpeg", ["-nostdin", "-v", "error", "-filter_threads", "2", "-y", "-f", "lavfi", "-i",
                         "color=c=0x00FF00:s=160x284:r=10:d=1,drawbox=x=60:y=100:w=40:h=60:color=red:t=fill",
                         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-threads", "2", str(greenscreen)], folder)
    silent = folder / "silence.wav"
    tools._run("ffmpeg", ["-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                         "-t", "1", "-c:a", "pcm_s16le", "-threads", "2", str(silent)], folder)
    return folder


def fixture_asset(root, filename="source.mp4"):
    path = root / filename
    return {"id": "fixture_" + filename, "path": filename, "sha256": tools._hash(path)}


def stream(result, type):
    return next(s for s in result["probe"]["streams"] if s["codec_type"] == type)


def frame(path, root, at=.1):
    nice = shutil.which("nice")
    command = ([nice, "-n", "10"] if nice else []) + [shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-threads", "2",
               "-ss", str(at), "-i", str(path), "-frames:v", "1", "-pix_fmt", "rgba", "-threads", "2", "-f", "rawvideo", "pipe:1"]
    result = subprocess.run(command, cwd=root, env={"PATH": os.environ["PATH"], "TMPDIR": str(root / ".estado/tmp"), "CUDA_VISIBLE_DEVICES": ""},
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True)
    return result.stdout


def test_catalog_declares_real_tools_and_bounded_parameters():
    operations = tools.catalog()
    assert {s["id"] for s in operations} == {"probe", "scene_detect", "extract_audio", "denoise_audio", "normalize_audio", "proxy_video", "speed_video", "reverse_video", "chromakey_video", "loudness_analysis", "remove_background_video"}
    for item in operations:
        assert item["implemented"] is True
        assert item["limits"]["gpu"] is False
        assert item["limits"]["ffmpeg_threads"] == 2
        assert all("key" in p and "type" in p and "default" in p for p in item["parameters"])


def test_probe_and_scene_detection_have_real_times_and_scores(media_workspace):
    root = media_workspace
    probe = tools.analyze(fixture_asset(root), "probe", root=root)
    assert stream(probe, "video")["width"] == 160
    assert stream(probe, "audio")["sample_rate"] == "48000"
    scene = tools.analyze(fixture_asset(root), "scene_detect", {"threshold": .1}, root)
    assert any(abs(s["timestamp"] - 1.) < .15 and s["score"] > .1 for s in scene["scenes"]), scene
    assert "path" not in scene
    assert scene["provenance"]["approved_for_ascendia"] is False


def test_extract_audio_is_pcm_48k_and_does_not_mutate_source(media_workspace):
    root = media_workspace
    source = fixture_asset(root)
    result = tools.process(source, "extract_audio", {"channels": 1}, root)
    audio = stream(result, "audio")
    assert audio["sample_rate"] == "48000"
    assert audio["codec_name"] == "pcm_s16le" and audio["channels"] == 1
    assert float(result["probe"]["format"]["duration"]) == pytest.approx(2, abs=.08)
    assert tools._hash(root / source["path"]) == source["sha256"]
    assert result["path"].startswith(".estado/tools/")
    assert result["verification"]["decode_ok"] and not result["verification"]["audio"]
    again = tools.process(source, "extract_audio", {"channels": 1}, root)
    assert again["reused"] and again["path"] == result["path"]


def test_denoise_processes_samples_and_preserves_duration(media_workspace):
    root = media_workspace
    raw = tools.process(fixture_asset(root), "extract_audio", {"channels": 2}, root)
    result = tools.process(fixture_asset(root), "denoise_audio", {"highpass_hz": 200}, root)
    assert result["sha256"] != raw["sha256"]
    assert float(result["probe"]["format"]["duration"]) == pytest.approx(2, abs=.08)
    assert result["provenance"]["audio_listened"] is False
    assert stream(result, "audio")["sample_rate"] == "48000"


def test_loudness_and_two_pass_normalization_report_measured_results(media_workspace):
    root = media_workspace
    measurements = tools.analyze(fixture_asset(root), "loudness_analysis", root=root)
    assert isinstance(measurements["measurements"]["integrated_lufs"], float)
    assert measurements["audio_listened"] is False
    result = tools.process(fixture_asset(root), "normalize_audio", root=root)
    after = result["loudness_after"]["measurements"]
    assert after["integrated_lufs"] == pytest.approx(-16, abs=.8)
    assert after["true_peak_dbtp"] <= -1.4
    assert result["loudness_before"]["measurements"]["integrated_lufs"] < after["integrated_lufs"]


def test_silent_audio_reports_no_finite_loudness_and_cannot_normalize(media_workspace):
    root = media_workspace
    measured = tools.analyze(fixture_asset(root, "silence.wav"), "loudness_analysis", root=root)
    assert measured["measurements"]["integrated_lufs"] is None
    with pytest.raises(StudioError, match="silencio"):
        tools.process(fixture_asset(root, "silence.wav"), "normalize_audio", root=root)


def test_proxy_has_real_resize_fps_and_preserved_audio(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root), "proxy_video", {"max_width": 160, "max_height": 160, "fps": 20}, root)
    video = stream(result, "video")
    assert video["width"] <= 160 and video["height"] <= 160
    assert video["width"] % 2 == 0 and video["height"] % 2 == 0
    assert video["codec_name"] == "h264"
    assert video["avg_frame_rate"] == "20/1"
    assert stream(result, "audio")["codec_name"] == "aac"
    assert float(result["probe"]["format"]["duration"]) == pytest.approx(2, abs=.15)


@pytest.mark.parametrize("rate", [.25, .5, 4.])
def test_speed_changes_video_and_audio_duration_together(media_workspace, rate):
    root = media_workspace
    result = tools.process(fixture_asset(root), "speed_video", {"rate": rate}, root)
    target = 2 / rate
    assert float(result["probe"]["format"]["duration"]) == pytest.approx(target, abs=.16)
    assert abs(float(stream(result, "video")["duration"]) - float(stream(result, "audio")["duration"])) <= .16
    assert result["provenance"]["changes_narration_timing"] is True
    assert all(.5 <= float(stage.split("=")[1]) <= 2 for stage in tools._tempo_chain(rate).split(","))


def test_reverse_reorders_real_frames_and_retains_audio(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root), "reverse_video", root=root)
    before = frame(root / "source.mp4", root)
    after = frame(root / result["path"], root)
    assert before[0] > before[2] + 100
    assert after[2] > after[0] + 100
    assert stream(result, "audio")["codec_name"] == "aac"
    assert float(result["probe"]["format"]["duration"]) == pytest.approx(2, abs=.15)
    assert result["provenance"]["estimated_reverse_buffer_bytes"] <= tools.MAX_REVERSE_BYTES


def test_chromakey_produces_alpha_for_green_and_preserves_red_subject(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root, "green.mp4"), "chromakey_video", {"similarity": .2}, root)
    video = stream(result, "video")
    assert video["codec_name"] == "qtrle" and video["pix_fmt"] == "argb"
    rgba = frame(root / result["path"], root)
    green_alpha = rgba[(20 * 160 + 20) * 4 + 3]
    subject_alpha = rgba[(120 * 160 + 80) * 4 + 3]
    assert green_alpha < 10 and subject_alpha > 240
    assert result["path"].endswith(".mov")


@pytest.mark.parametrize("operation, options", [
    ("scene_detect", {"threshold": "0.2;movie=/etc/passwd"}),
    ("denoise_audio", {"noise_reduction_db": float("nan")}),
    ("speed_video", {"rate": True}),
    ("speed_video", {"rate": 10}),
    ("chromakey_video", {"color": "green,scale=100:100"}),
    ("proxy_video", {"max_width": 161}),
    ("extract_audio", {"output": "../outside.wav"}),
    ("reverse_video", {"duration": 61}),
])
def test_invalid_parameters_are_rejected_before_subprocess(media_workspace, monkeypatch, operation, options):
    def fail(*args, **kwargs):
        pytest.fail("Invalid options must not execute a subprocess")
    monkeypatch.setattr(tools, "_run", fail)
    with pytest.raises(StudioError):
        tools.process(fixture_asset(media_workspace), operation, options, media_workspace)


def test_source_escape_and_changed_registered_bytes_are_rejected(media_workspace):
    root = media_workspace
    for path in ("../outside.mp4", "/etc/passwd"):
        with pytest.raises(StudioError) as error:
            tools.process({"path": path}, "probe", root=root)
        assert error.value.status == 403
    asset = fixture_asset(root)
    asset["sha256"] = "0" * 64
    with pytest.raises(StudioError) as error:
        tools.process(asset, "probe", root=root)
    assert error.value.status == 409


def test_disguised_concat_cannot_follow_external_file_references(media_workspace):
    root = media_workspace
    disguised = root / "disguised.mp4"
    disguised.write_text("ffconcat version 1.0\nfile '../outside.wav'\n", encoding="utf-8")
    with pytest.raises(StudioError):
        tools.process(fixture_asset(root, "disguised.mp4"), "probe", root=root)
    assert "concat" not in tools.FORMATS.split(",") and "hls" not in tools.FORMATS.split(",")


def test_ffmpeg_command_has_nice_thread_caps_safe_formats_and_private_temp(media_workspace, monkeypatch):
    seen = []

    class Done:
        returncode = 0
        stdout = b""
        stderr = b""

    def runner(command, **kwargs):
        seen.append((command, kwargs))
        return Done()

    monkeypatch.setattr(tools.subprocess, "run", runner)
    tools._run("ffmpeg", tools._base() + tools._input(media_workspace / "source.mp4", 0, 1) + ["-threads", "2", "-f", "null", "-"], media_workspace)
    command, kwargs = seen[0]
    if shutil.which("nice"):
        assert command[1:3] == ["-n", "10"]
    assert "-format_whitelist" in command and "-protocol_whitelist" in command
    assert all(command[index + 1] == "2" for index, token in enumerate(command) if token in ("-threads", "-filter_threads", "-filter_complex_threads"))
    assert Path(kwargs["env"]["TMPDIR"]).is_relative_to(media_workspace)
    assert kwargs["env"]["CUDA_VISIBLE_DEVICES"] == ""
    assert "shell" not in kwargs


def test_altered_derivative_is_preserved_instead_of_overwritten(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root), "extract_audio", {"duration": .5}, root)
    output = root / result["path"]
    output.write_bytes(b"different file which must be preserved")
    with pytest.raises(StudioError) as error:
        tools.process(fixture_asset(root), "extract_audio", {"duration": .5}, root)
    assert error.value.status == 409
    assert output.read_bytes() == b"different file which must be preserved"


def test_reverse_memory_cap_rejects_large_source_without_decoding(media_workspace, monkeypatch):
    info = {"format": {"duration": "60"}, "streams": [{"codec_type": "video", "width": 3840, "height": 2160, "avg_frame_rate": "60/1"}]}
    monkeypatch.setattr(tools, "_probe", lambda *args: info)
    monkeypatch.setattr(tools, "_run", lambda *args, **kwargs: pytest.fail("Oversized reverse must not decode"))
    with pytest.raises(StudioError, match="512 MiB"):
        tools.process(fixture_asset(media_workspace), "reverse_video", root=media_workspace)


def test_registered_derivative_uses_one_canonical_copy_with_working_cache(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root), "extract_audio", {"duration": .75}, root)
    cache = root / result["path"]
    canonical = root / "assets/audio" / (result["sha256"] + ".wav")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cache, canonical)
    asset = {"id": "a_registered", "path": canonical.relative_to(root).as_posix(), "sha256": result["sha256"]}
    bound = tools.bind_canonical(result, asset, root)
    assert cache.is_symlink() and cache.resolve() == canonical
    assert tools._hash(canonical) == result["sha256"]
    assert bound["canonical_asset_id"] == asset["id"]
    again = tools.process(fixture_asset(root), "extract_audio", {"duration": .75}, root)
    assert again["reused"] and again["canonical_path"] == asset["path"]
    tools.bind_canonical(again, asset, root)
    assert cache.resolve() == canonical


def test_cache_binding_rejects_wrong_hash_without_replacing_any_file(media_workspace):
    root = media_workspace
    result = tools.process(fixture_asset(root), "extract_audio", {"duration": .8}, root)
    cache = root / result["path"]
    before = cache.read_bytes()
    with pytest.raises(StudioError) as error:
        tools.bind_canonical(result, {"path": "source.mp4", "sha256": "0" * 64}, root)
    assert error.value.status == 409
    assert not cache.is_symlink() and cache.read_bytes() == before


def test_media_job_registers_wav_once_and_preserves_original(media_workspace, tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((ROOT / ".estado/tmp").resolve())
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
    monkeypatch.setattr(jobs, "QUEUE", queue.Queue())
    monkeypatch.setattr(jobs, "CANCEL", {})
    monkeypatch.setattr(jobs, "WORKER", None)
    core.setup()
    source = root / "source.mp4"
    shutil.copyfile(media_workspace / "source.mp4", source)
    original_sha = tools._hash(source)
    asset = core.register_asset(source)
    first = jobs.submit_media(asset["id"], "extract_audio", {"duration": 1.})
    jobs.execute(first["id"])
    completed = jobs.get_job(first["id"])
    assert completed["status"] == "completed", completed
    derivative = completed["result"]["asset"]
    assert derivative["path"].endswith(".wav")
    assert derivative["name"].endswith(".wav")
    assert derivative["probe"]["format"]["format_name"] == "wav"
    assert derivative["verification"]["visual"] is False and derivative["verification"]["audio"] is False
    second = jobs.submit_media(asset["id"], "extract_audio", {"duration": 1.})
    jobs.execute(second["id"])
    repeated = jobs.get_job(second["id"])
    assert repeated["status"] == "completed", repeated
    assert repeated["result"]["reused"] is True
    assert repeated["result"]["asset"]["id"] == derivative["id"]
    assert len(core.assets()) == 2
    assert len(list((root / "assets/audio").glob("*.wav"))) == 1
    assert all(path.is_symlink() for path in (root / ".estado/tools").glob("*.wav"))
    assert tools._hash(source) == original_sha
    assert tools._hash(core.confined(asset["path"])) == original_sha
