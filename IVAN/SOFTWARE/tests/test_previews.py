"""Browser-format conversions from self-owned, tiny CPU-only footage."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import shutil
import subprocess

from PIL import Image, ImageDraw
import pytest

from studio import previews
from studio import media_tools as tools
from studio.core import StudioError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def preview_sources(tmp_path_factory):
    root = tmp_path_factory.mktemp("preview-sources")
    assert root.resolve().is_relative_to((ROOT / ".estado/tmp").resolve())
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Actual browser proxies require FFmpeg and FFprobe")
    (root / ".estado/tmp").mkdir(parents=True)
    base = tools._base()
    tools._run("ffmpeg", base + ["-f", "lavfi", "-i", "color=c=red:s=160x284:r=10:d=2",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2",
                "-map", "0:v", "-map", "1:a", "-c:v", "mpeg4", "-q:v", "4", "-c:a", "pcm_s16le", "-threads", "2", "-y", str(root / "source.avi")], root)
    tools._run("ffmpeg", base + ["-f", "lavfi", "-i", "color=c=0x00FF00:s=160x284:r=10:d=2,drawbox=x=60:y=100:w=40:h=60:color=red:t=fill",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2", "-map", "0:v", "-map", "1:a",
                "-vf", "chromakey=color=0x00ff00:similarity=0.1:blend=0,format=argb", "-c:v", "qtrle", "-pix_fmt", "argb", "-c:a", "pcm_s16le",
                "-threads", "2", "-y", str(root / "alpha.mov")], root)
    tools._run("ffmpeg", base + ["-protocol_whitelist", "file,pipe", "-format_whitelist", tools.FORMATS,
                "-threads", "2", "-i", str(root / "source.avi"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-threads", "2", "-y", str(root / "compatible.mp4")], root)
    tools._run("ffmpeg", base + ["-protocol_whitelist", "file,pipe", "-format_whitelist", tools.FORMATS,
                "-threads", "2", "-i", str(root / "compatible.mp4"), "-c", "copy", "-threads", "2", "-y", str(root / "h264.mkv")], root)
    return root


@pytest.fixture
def preview_workspace(tmp_path, preview_sources):
    assert tmp_path.resolve().is_relative_to((ROOT / ".estado/tmp").resolve())
    (tmp_path / ".estado/tmp").mkdir(parents=True)
    for name in ("source.avi", "alpha.mov", "compatible.mp4", "h264.mkv"):
        shutil.copyfile(preview_sources / name, tmp_path / name)
    return tmp_path


def asset(root, filename="source.avi"):
    file = root / filename
    return {"id": "test-" + filename, "path": filename, "name": filename, "kind": "video", "sha256": tools._hash(file),
            "probe": tools._probe(file, root), "extension": file.suffix, "duration": 2.0}


def streams(info, kind):
    return [s for s in info["streams"] if s["codec_type"] == kind]


def alpha_frame(path, root, at=.2):
    command = [shutil.which("nice"), "-n", "10", shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-filter_threads", "2",
               "-protocol_whitelist", "file,pipe", "-format_whitelist", tools.FORMATS, "-threads", "2", "-c:v", "libvpx-vp9",
               "-ss", str(at), "-i", str(path), "-frames:v", "1", "-pix_fmt", "rgba", "-threads", "2", "-f", "rawvideo", "pipe:1"]
    done = subprocess.run(command, cwd=root, env={"PATH": os.environ["PATH"], "TMPDIR": str(root / ".estado/tmp"), "CUDA_VISIBLE_DEVICES": ""},
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=True)
    return done.stdout


def test_real_avi_preview_is_h264_aac_and_preserves_original_metadata(preview_workspace):
    root = preview_workspace
    original = asset(root)
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result, result
    assert result["preview_is_derivative"] is True
    assert result["preview_path"] == "assets/previews/" + original["sha256"][:20] + ".mp4"
    assert result["preview_url"] == "/api/files/" + result["preview_path"]
    assert result["probe"] == original["probe"] and result["path"] == original["path"]
    assert result["id"] == original["id"] and result["extension"] == ".avi"
    assert tools._hash(root / original["path"]) == original["sha256"]
    video = streams(result["preview_probe"], "video")[0]
    audio = streams(result["preview_probe"], "audio")[0]
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    assert video["width"] <= 540 and video["height"] <= 960
    assert video["avg_frame_rate"] == "30/1" and audio["codec_name"] == "aac"
    assert float(video["duration"]) == pytest.approx(2, abs=.08)
    assert float(audio["duration"]) == pytest.approx(2, abs=.08)
    assert result["preview_provenance"]["decode_ok"] is True
    assert result["preview_provenance"]["audio_listened"] is False
    assert result["preview_provenance"]["approved_for_ascendia"] is False
    assert "preview_path" not in original


def test_qtrle_alpha_preview_really_preserves_transparent_and_opaque_pixels(preview_workspace):
    root = preview_workspace
    original = asset(root, "alpha.mov")
    assert streams(original["probe"], "video")[0]["pix_fmt"] == "argb"
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result, result
    assert result["preview_path"].endswith(".webm") and result["preview_preserves_alpha"]
    video = streams(result["preview_probe"], "video")[0]
    assert video["codec_name"] == "vp9"
    assert streams(result["preview_probe"], "audio")[0]["codec_name"] == "opus"
    raw = alpha_frame(root / result["preview_path"], root)
    width, height = video["width"], video["height"]
    assert len(raw) == width * height * 4
    def pixel(x, y):
        at = (y * width + x) * 4
        return raw[at:at+4]
    assert pixel(10, 10)[3] <= 2
    center = pixel(width // 2, height // 2)
    assert center[0] > 200 and center[1] < 40 and center[3] >= 250
    assert float(result["preview_probe"]["format"]["duration"]) == pytest.approx(2, abs=.08)
    assert tools._hash(root / original["path"]) == original["sha256"]


def test_same_original_content_reuses_one_canonical_proxy(preview_workspace):
    root = preview_workspace
    first = previews.ensure_preview(asset(root), root)
    proxy = root / first["preview_path"]
    timestamp = proxy.stat().st_mtime_ns
    shutil.copyfile(root / "source.avi", root / "duplicate.avi")
    duplicate = asset(root, "duplicate.avi")
    again = previews.ensure_preview(duplicate, root)
    assert again["preview_reused"] and again["preview_path"] == first["preview_path"]
    assert again["id"] == duplicate["id"] and again["path"] == "duplicate.avi"
    assert proxy.stat().st_mtime_ns == timestamp
    assert len(list((root / "assets/previews").glob("*.mp4"))) == 1


def test_parallel_same_hash_generates_one_preview(preview_workspace, monkeypatch):
    root = preview_workspace
    original = asset(root)
    real_run = previews._run
    encodes = []
    def counting(tool, args, root, timeout=120):
        if tool == "ffmpeg" and "libx264" in args:
            encodes.append(True)
        return real_run(tool, args, root, timeout)
    monkeypatch.setattr(previews, "_run", counting)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda unused: previews.ensure_preview(original, root), range(2)))
    assert not any("preview_error" in r for r in results), results
    assert len(encodes) == 1 and sorted(r["preview_reused"] for r in results) == [False, True]


def test_h264_mp4_skips_expensive_conversion(preview_workspace, monkeypatch):
    root = preview_workspace
    original = asset(root, "compatible.mp4")
    monkeypatch.setattr(previews, "_run", lambda *args: pytest.fail("Compatible originals must not transcode"))
    result = previews.ensure_preview(original, root)
    assert not result["preview_is_derivative"] and result["preview_path"] == original["path"]
    assert "preview_error" not in result


def test_h264_matroska_still_gets_browser_container_proxy(preview_workspace):
    root = preview_workspace
    original = asset(root, "h264.mkv")
    result = previews.ensure_preview(original, root)
    assert result["preview_is_derivative"] and result["preview_path"].endswith(".mp4"), result


@pytest.mark.parametrize("video,audio", [("vp9", "opus"), ("av1", "vorbis"), ("vp8", "opus")])
def test_webm_profiles_are_browser_compatible(video, audio):
    assert previews._browser_compatible({"streams": [{"codec_type": "video", "codec_name": video}, {"codec_type": "audio", "codec_name": audio}]}, ".webm")


def test_incomplete_mock_codec_stays_pending_without_ffmpeg(preview_workspace, monkeypatch):
    root = preview_workspace
    original = asset(root)
    original["probe"]["streams"][0].pop("codec_name")
    monkeypatch.setattr(previews, "_run", lambda *args: pytest.fail("Incomplete metadata must not transcode"))
    result = previews.ensure_preview(original, root)
    assert result["preview_pending"] and not result["preview_is_derivative"]
    assert "preview_error" not in result


def test_failure_keeps_original_usable_and_does_not_promote_partial(preview_workspace, monkeypatch):
    root = preview_workspace
    original = asset(root)
    def failure(tool, args, root, timeout=120):
        if tool == "ffmpeg":
            Path(args[-1]).write_bytes(b"unfinished")
            raise StudioError("Fixture codec failure")
        return tools._run(tool, args, root, timeout)
    monkeypatch.setattr(previews, "_run", failure)
    result = previews.ensure_preview(original, root)
    assert "Fixture codec failure" in result["preview_error"]
    assert result["id"] == original["id"] and result["path"] == original["path"]
    assert tools._hash(root / original["path"]) == original["sha256"]
    assert not list((root / "assets/previews").iterdir())
    assert not list((root / ".estado/tmp").glob("browser-preview-*"))


def test_changed_derivative_is_preserved_and_reported(preview_workspace):
    root = preview_workspace
    original = asset(root)
    first = previews.ensure_preview(original, root)
    output = root / first["preview_path"]
    output.write_bytes(b"changed by external editor")
    again = previews.ensure_preview(original, root)
    assert "no se sobrescribe" in again["preview_error"]
    assert output.read_bytes() == b"changed by external editor"


def test_output_symlink_cannot_replace_source_even_inside_software(preview_workspace):
    root = preview_workspace
    original = asset(root)
    folder = root / "assets/previews"
    folder.mkdir(parents=True)
    (folder / (original["sha256"][:20] + ".mp4")).symlink_to(root / "source.avi")
    result = previews.ensure_preview(original, root)
    assert "enlaces" in result["preview_error"]
    assert tools._hash(root / "source.avi") == original["sha256"]


def test_arbitrary_path_and_workspace_escapes_are_reported_without_writes(preview_workspace):
    root = preview_workspace
    escaped = previews.ensure_preview({"path": "../../../../../../PROMPT_MAESTRO.md"}, root)
    assert "fuera de SOFTWARE" in escaped["preview_error"]
    invalid_root = previews.ensure_preview({"path": "source.avi"}, ROOT.parent)
    assert "dentro de SOFTWARE" in invalid_root["preview_error"]
    (root / "escaping.mov").symlink_to(ROOT.parent / "PROMPT_MAESTRO.md")
    result = previews.ensure_preview({"path": "escaping.mov"}, root)
    assert "fuera de SOFTWARE" in result["preview_error"]


def test_input_hash_change_and_disguised_manifest_never_transcode(preview_workspace):
    root = preview_workspace
    original = asset(root)
    original["sha256"] = "0" * 64
    assert "hash canónico" in previews.ensure_preview(original, root)["preview_error"]
    (root / "playlist.avi").write_text("ffconcat version 1.0\nfile source.avi\n")
    disguised = {"path": "playlist.avi", "probe": {"streams": [{"index": 0, "codec_type": "video", "codec_name": "mpeg4"}]}}
    result = previews.ensure_preview(disguised, root)
    assert "preview_error" in result and not result["preview_is_derivative"]


def test_failed_or_obsolete_preview_clears_prior_catalog_fields(preview_workspace):
    root = preview_workspace
    original = asset(root)
    previous = previews.ensure_preview(original, root)
    previous["sha256"] = "0" * 64
    failed = previews.ensure_preview(previous, root)
    assert failed["preview_url"] is None and failed["preview_probe"] is None
    assert failed["preview_provenance"] is None and not failed["preview_preserves_alpha"]
    compatible = asset(root, "compatible.mp4")
    compatible.update(preview_error="old failed generation", preview_probe={"old": True}, preview_pending=True)
    repaired = previews.ensure_preview(compatible, root)
    assert repaired["preview_error"] is None and repaired["preview_probe"] is None
    assert repaired["preview_pending"] is False


def test_encoding_commands_are_confined_cpu_two_threads(preview_workspace, monkeypatch):
    root = preview_workspace
    original = asset(root)
    calls = []
    real_run = previews._run
    def record(tool, args, root, timeout=120):
        calls.append((tool, list(args)))
        return real_run(tool, args, root, timeout)
    monkeypatch.setattr(previews, "_run", record)
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result
    for tool, args in calls:
        assert args[args.index("-protocol_whitelist") + 1] == "file,pipe"
        assert args[args.index("-format_whitelist") + 1] == tools.FORMATS
        if tool == "ffmpeg":
            assert all(args[i+1] == "2" for i, value in enumerate(args) if value in {"-threads", "-filter_threads", "-filter_complex_threads"})
            assert all("nvenc" not in str(value) and "cuda" not in str(value) for value in args)


def test_no_video_and_images_reuse_original_without_codec_work(preview_workspace, monkeypatch):
    root = preview_workspace
    monkeypatch.setattr(previews, "_run", lambda *args: pytest.fail("No video should not transcode"))
    for original in ({"id": "audio", "path": "source.avi", "probe": {"streams": [{"codec_type": "audio"}]}},
                     {"id": "image", "path": "source.avi", "kind": "image"}):
        result = previews.ensure_preview(original, root)
        assert not result["preview_is_derivative"] and "preview_error" not in result


def tiff_asset(root, filename="picture.tiff", size=(64, 96)):
    path = root / filename
    picture = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(picture).rectangle((size[0] // 4, size[1] // 4, size[0] * 3 // 4, size[1] * 3 // 4), fill=(230, 40, 60, 128))
    picture.save(path, format="TIFF")
    return {"id": "test-" + filename, "path": filename, "name": filename, "kind": "image", "sha256": tools._hash(path),
            "probe": tools._probe(path, root), "extension": path.suffix, "duration": 0.0}


@pytest.mark.parametrize("extension,size,dimensions", [("tif", (1200, 1800), (540, 810)), ("tiff", (600, 1600), (360, 960))])
def test_real_tiff_preview_is_rgba_png_with_alpha_and_bounded_dimensions(preview_workspace, extension, size, dimensions):
    root = preview_workspace
    original = tiff_asset(root, "picture." + extension, size)
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result, result
    assert result["preview_is_derivative"] and not result["preview_reused"]
    assert result["preview_preserves_alpha"] and result["preview_path"].endswith(".png")
    assert result["preview_url"] == "/api/files/" + result["preview_path"]
    assert result["probe"] == original["probe"] and result["path"] == original["path"]
    assert result["extension"] == original["extension"] and result["id"] == original["id"]
    with Image.open(root / result["preview_path"]) as image:
        assert image.format == "PNG" and image.mode == "RGBA" and image.size == dimensions
        assert image.getpixel((0, 0))[3] == 0
        center = image.getpixel((image.width // 2, image.height // 2))
        assert center[3] == 128 and all(abs(actual - expected) <= 2 for actual, expected in zip(center[:3], (230, 40, 60)))
    info = streams(result["preview_probe"], "video")[0]
    assert info["codec_name"] == "png" and (info["width"], info["height"]) == dimensions
    assert tools._hash(root / original["path"]) == original["sha256"]
    assert tools._hash(root / result["preview_path"]) == result["preview_sha256"]
    provenance = result["preview_provenance"]
    assert provenance["source_dimensions"] == list(size) and provenance["preview_dimensions"] == list(dimensions)
    assert provenance["decode_ok"] and provenance["source_sha256"] == original["sha256"]
    assert provenance["gpu_used"] is False and provenance["visual_reviewed"] is False
    assert provenance["approved_for_ascendia"] is False and provenance["audio_listened"] is False
    assert "preview_path" not in original and not list((root / ".estado/tmp").glob("browser-preview-*"))


def test_multipage_tiff_preview_uses_first_page_without_upscaling(preview_workspace):
    root = preview_workspace
    source = root / "multipage.tiff"
    Image.new("RGB", (32, 64), (220, 30, 50)).save(source, save_all=True, append_images=[Image.new("RGB", (64, 32), (0, 255, 0))])
    original = {"id": "multipage", "kind": "image", "path": source.name, "sha256": tools._hash(source)}
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result, result
    assert not result["preview_preserves_alpha"]
    with Image.open(root / result["preview_path"]) as image:
        assert image.size == (32, 64) and image.getpixel((16, 32)) == (220, 30, 50, 255)
    assert result["preview_provenance"]["source_pages"] == 2 and result["preview_provenance"]["preview_page"] == 0
    assert any("primera página" in text for text in result["preview_provenance"]["limitations"])
    assert tools._hash(source) == original["sha256"]


def test_identical_tiff_content_reuses_one_png_without_decoding_or_rewriting(preview_workspace, monkeypatch):
    root = preview_workspace
    original = tiff_asset(root)
    first = previews.ensure_preview(original, root)
    output = root / first["preview_path"]
    receipt = root / ".estado/previews" / (original["sha256"][:20] + ".json")
    before = output.stat().st_mtime_ns, receipt.stat().st_mtime_ns
    shutil.copyfile(root / original["path"], root / "duplicate.tiff")
    duplicate = {**original, "id": "duplicate", "path": "duplicate.tiff"}
    monkeypatch.setattr(previews.Image, "open", lambda *a, **kw: pytest.fail("Cached TIFF preview must not decode again"))
    monkeypatch.setattr(previews, "_probe", lambda *a: pytest.fail("Cached TIFF preview must not probe again"))
    again = previews.ensure_preview(duplicate, root)
    assert "preview_error" not in again, again
    assert again["preview_reused"] and again["preview_path"] == first["preview_path"]
    assert again["id"] == "duplicate" and again["path"] == "duplicate.tiff"
    assert before == (output.stat().st_mtime_ns, receipt.stat().st_mtime_ns)
    assert len(list((root / "assets/previews").glob("*.png"))) == 1


def test_parallel_tiff_same_hash_encodes_one_png(preview_workspace, monkeypatch):
    root = preview_workspace
    original = tiff_asset(root)
    real_save = Image.Image.save
    encodes = []
    def record_save(image, path, *args, **kwargs):
        if kwargs.get("format") == "PNG":
            encodes.append(str(path))
        return real_save(image, path, *args, **kwargs)
    monkeypatch.setattr(Image.Image, "save", record_save)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda unused: previews.ensure_preview(original, root), range(2)))
    assert not any("preview_error" in result for result in results), results
    assert len(encodes) == 1 and sorted(result["preview_reused"] for result in results) == [False, True]
    assert Path(encodes[0]).is_relative_to(root / ".estado/tmp")
    assert tools._hash(root / original["path"]) == original["sha256"]


@pytest.mark.parametrize("conflict", ["changed", "receipt_missing", "symlink"])
def test_tiff_existing_preview_conflicts_never_overwrite_output_or_source(preview_workspace, conflict):
    root = preview_workspace
    original = tiff_asset(root)
    first = previews.ensure_preview(original, root)
    output = root / first["preview_path"]
    if conflict == "changed":
        output.write_bytes(b"External edited preview")
    elif conflict == "receipt_missing":
        (root / ".estado/previews" / (original["sha256"][:20] + ".json")).unlink()
    else:
        output.unlink()
        output.symlink_to(root / original["path"])
    before = output.read_bytes()
    again = previews.ensure_preview(first, root)
    assert "preview_error" in again and not again["preview_is_derivative"]
    assert again["preview_path"] is None and again["preview_provenance"] is None
    assert output.read_bytes() == before and tools._hash(root / original["path"]) == original["sha256"]


def test_tiff_output_created_during_conversion_is_not_overwritten(preview_workspace, monkeypatch):
    root = preview_workspace
    original = tiff_asset(root)
    output = root / "assets/previews" / (original["sha256"][:20] + ".png")
    real_probe = previews._probe
    def external_writer(path, workspace):
        info = real_probe(path, workspace)
        output.write_bytes(b"External concurrent file")
        return info
    monkeypatch.setattr(previews, "_probe", external_writer)
    result = previews.ensure_preview(original, root)
    assert "no se sobrescribe" in result["preview_error"]
    assert output.read_bytes() == b"External concurrent file"
    assert tools._hash(root / original["path"]) == original["sha256"]
    assert not list((root / ".estado/tmp").glob("browser-preview-*"))


def test_failed_tiff_conversion_discards_partial_png_and_keeps_original(preview_workspace, monkeypatch):
    root = preview_workspace
    original = tiff_asset(root)
    def fail_save(image, path, *args, **kwargs):
        Path(path).write_bytes(b"Partial PNG fixture")
        raise StudioError("TIFF fixture decode failure")
    monkeypatch.setattr(Image.Image, "save", fail_save)
    result = previews.ensure_preview(original, root)
    assert "TIFF fixture decode failure" in result["preview_error"]
    assert tools._hash(root / original["path"]) == original["sha256"]
    assert not list((root / "assets/previews").iterdir())
    assert not list((root / ".estado/tmp").glob("browser-preview-*"))


def test_bmp_remains_original_without_unnecessary_conversion(preview_workspace, monkeypatch):
    root = preview_workspace
    path = root / "image.bmp"
    Image.new("RGB", (32, 64), (220, 30, 50)).save(path)
    original = {"id": "bmp", "kind": "image", "path": path.name, "sha256": tools._hash(path)}
    monkeypatch.setattr(previews, "_probe", lambda *args: pytest.fail("BMP does not need a browser conversion"))
    result = previews.ensure_preview(original, root)
    assert "preview_error" not in result and not result["preview_is_derivative"]
    assert result["preview_path"] == path.name and tools._hash(path) == original["sha256"]
