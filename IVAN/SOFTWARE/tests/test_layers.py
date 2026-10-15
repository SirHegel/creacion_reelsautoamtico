"""Real alpha/video layer composition and animation in tiny synthetic reels."""
from __future__ import annotations

import array
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw
import pytest

from studio import media_tools
from studio.render import RenderError, _decorate, measure_audio_levels, render
from test_api import api_workspace


@pytest.fixture
def layer_project(api_workspace):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required for real layer integration")
    source = api_workspace / "assets/video/source.mp4"
    command = [shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1",
               "-f", "lavfi", "-i", "color=c=blue:s=160x284:r=10:d=2",
               "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
               "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
               "-threads", "1", "-shortest", str(source)]
    subprocess.run(command, cwd=api_workspace, check=True, capture_output=True)
    project = {"source": "source", "assets": [{"id": "source", "path": str(source.relative_to(api_workspace)), "kind": "video",
                                                   "sha256": hashlib.sha256(source.read_bytes()).hexdigest(), "duration": 2}],
               "settings": {"width": 160, "height": 284, "fps": 10},
               "fonts": {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"},
               "timeline": [{"id": "s1", "start": 0., "end": 2., "type": "presenter", "overlays": []}],
               "audio": [], "transcript": {"words": [], "segments": []}}
    return project


def image_asset(project, root, name, color, size=(32, 32), *, transparent=False):
    path = root / "assets/images" / name
    image = Image.new("RGBA", size, color)
    if transparent:
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((size[0] // 4, 0, size[0] * 3 // 4 - 1, size[1] - 1), fill=color)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        image = image.convert("RGB")
    image.save(path, **({"lossless": True} if path.suffix == ".webp" else {}))
    asset = {"id": name, "path": str(path.relative_to(root)), "kind": "image", "duration": 0,
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    project["assets"].append(asset)
    return asset


def layer(asset_id, **changes):
    result = {"id": "layer1", "asset_id": asset_id, "start": 0., "end": 1., "source_in": 0.,
              "x": .1, "y": .1, "width": .5, "height": .3, "opacity": 1., "blend": "normal", "keyframes": [],
              "decision": {"search": "Synthetic fixture", "reason": "Tests actual layering", "evidence": []}}
    result.update(changes)
    return result


def frames(path, root):
    command = [shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(path),
               "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"]
    raw = subprocess.run(command, cwd=root, check=True, capture_output=True).stdout
    frame_size = 160 * 284 * 3
    return [Image.frombytes("RGB", (160, 284), raw[index:index + frame_size])
            for index in range(0, len(raw), frame_size)]


def audio_samples(path, root):
    command = [shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(path), "-vn", "-ac", "1",
               "-ar", "8000", "-f", "s16le", "-threads", "1", "pipe:1"]
    raw = subprocess.run(command, cwd=root, check=True, capture_output=True).stdout
    return array.array("h", raw)


def tone_energy(samples, tone):
    real = sum(sample * math.cos(2 * math.pi * tone * index / 8000) for index, sample in enumerate(samples))
    imaginary = sum(sample * math.sin(2 * math.pi * tone * index / 8000) for index, sample in enumerate(samples))
    return math.hypot(real, imaginary)


@pytest.mark.parametrize("extension", ["png", "tiff"])
def test_genuine_image_alpha_and_transparent_contain_letterbox(api_workspace, layer_project, extension):
    p = layer_project
    asset = image_asset(p, api_workspace, "transparency." + extension, (255, 0, 0, 128), (32, 16), transparent=True)
    p["timeline"][0]["overlays"] = [layer(asset["id"], start=.2, end=1.)]
    output = api_workspace / "exports/layer.mp4"
    result = render(p, api_workspace, output, 1.5)
    video = frames(output, api_workspace)
    assert len(video) == 15
    assert video[0].getpixel((56, 71))[2] > 240
    red, green, blue = video[5].getpixel((56, 71))
    assert 115 <= red <= 140 and green < 15 and 115 <= blue <= 140
    # Transparent source region and transparent letterboxing both retain raw blue.
    assert video[5].getpixel((20, 71))[2] > 240
    assert video[5].getpixel((56, 35))[2] > 240
    assert video[12].getpixel((56, 71))[2] > 240
    receipt = next(row for row in result["used_assets"] if row["role"] == "overlay")
    assert receipt["layer_id"] == "layer1" and receipt["start"] == .2 and receipt["end"] == 1.
    assert result["technical"]["overlay_count"] == 1
    assert result["technical"]["overlay_position_review_required"] is True


@pytest.mark.parametrize("extension", ["jpg", "webp", "bmp", "tif", "tiff"])
def test_static_images_with_zero_duration_play_and_pad_transparently(api_workspace, layer_project, extension):
    p = layer_project
    asset = image_asset(p, api_workspace, "still." + extension, (255, 0, 0, 255), (32, 16))
    p["timeline"][0]["overlays"] = [layer(asset["id"])]
    output = api_workspace / "exports/still.mp4"
    render(p, api_workspace, output, 1)
    video = frames(output, api_workspace)
    assert len(video) == 10
    assert all(frame.getpixel((56, 71))[0] > 230 for frame in video)
    assert all(frame.getpixel((56, 35))[2] > 230 for frame in video)


def test_screen_respects_alpha_and_layer_order(api_workspace, layer_project):
    p = layer_project
    red = image_asset(p, api_workspace, "red.png", (255, 0, 0, 255))
    green = image_asset(p, api_workspace, "green.png", (0, 255, 0, 128))
    red_layer = layer(red["id"], id="red", width=.4, height=.4)
    green_layer = layer(green["id"], id="green", width=.4, height=.4, blend="screen")
    p["timeline"][0]["overlays"] = [red_layer, green_layer]
    output = api_workspace / "exports/screen.mp4"
    render(p, api_workspace, output, 1)
    pixel = frames(output, api_workspace)[2].getpixel((48, 85))
    assert pixel[0] > 235 and 115 <= pixel[1] <= 140 and pixel[2] < 15
    q = copy.deepcopy(p)
    q["timeline"][0]["overlays"].reverse()
    reverse = api_workspace / "exports/reversed_layers.mp4"
    render(q, api_workspace, reverse, 1)
    pixel = frames(reverse, api_workspace)[2].getpixel((48, 85))
    assert pixel[0] > 235 and pixel[1] < 15 and pixel[2] < 15
    assert audio_samples(output, api_workspace) == audio_samples(reverse, api_workspace)


def test_keyframes_move_in_canvas_units_scale_about_center_and_keep_opacity(api_workspace, layer_project):
    p = layer_project
    red = image_asset(p, api_workspace, "moving.png", (255, 0, 0, 255))
    p["timeline"][0]["overlays"] = [layer(red["id"], x=0., y=0., width=.2, height=.2,
        keyframes=[{"time": 0., "x": 0., "y": 0., "scale": 1., "opacity": 1.},
                   {"time": .8, "x": .5, "y": .5, "scale": 2., "opacity": .5}])]
    output = api_workspace / "exports/moving.mp4"
    result = render(p, api_workspace, output, 1)
    video = frames(output, api_workspace)
    assert video[0].getpixel((16, 28))[0] > 235
    assert video[-1].getpixel((16, 28))[2] > 235
    final = video[-1].getpixel((96, 170))
    assert 115 <= final[0] <= 140 and 115 <= final[2] <= 140
    # Scaling remains centered, expanding left of the final top-left x=80.
    assert video[-1].getpixel((70, 170))[0] > 110
    metrics = json.loads((api_workspace / result["technical"]["temporal_metrics"]).read_text())
    assert max(frame["mean_rgb_difference"] for frame in metrics["frames"]) > .5


def test_mov_alpha_from_real_chromakey_composites_and_does_not_replace_voice(api_workspace, layer_project):
    green = api_workspace / "assets/video/greenscreen.mp4"
    command = [shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1", "-f", "lavfi", "-i",
               "color=c=0x00FF00:s=64x64:r=10:d=1,drawbox=x=16:y=16:w=32:h=32:color=red:t=fill",
               "-f", "lavfi", "-i", "sine=frequency=660:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-threads", "1", "-shortest", str(green)]
    subprocess.run(command, cwd=api_workspace, check=True, capture_output=True)
    processed = media_tools.process({"id": "green_clip", "path": str(green.relative_to(api_workspace))}, "chromakey_video",
                                    {"color": "#00ff00", "similarity": .2, "blend": 0}, root=api_workspace)
    assert processed["probe"]["streams"][0]["codec_name"] == "qtrle"
    p = layer_project
    p["assets"].append({"id": "alpha_mov", "path": processed["path"], "kind": "video", "sha256": processed["sha256"], "duration": 1})
    p["timeline"][0]["overlays"] = [layer("alpha_mov", x=0., y=0., width=.4, height=.4)]
    output = api_workspace / "exports/alpha_composite.mp4"
    result = render(p, api_workspace, output, 1)
    video = frames(output, api_workspace)
    assert video[2].getpixel((32, 57))[0] > 230
    assert video[2].getpixel((4, 57))[2] > 230
    assert video[2].getpixel((32, 10))[2] > 230  # Transparent contain padding.
    samples = audio_samples(output, api_workspace)
    assert tone_energy(samples, 440) > 20 * tone_energy(samples, 660)
    assert result["technical"]["original_voice_present"] is True
    assert next(row for row in result["used_assets"] if row["role"] == "overlay")["asset_id"] == "alpha_mov"


def test_overlay_global_intervals_are_intersected_and_keyframe_time_is_not_accelerated(api_workspace, layer_project):
    p = layer_project
    red = image_asset(p, api_workspace, "late.png", (255, 0, 0, 255))
    p["timeline"] = [
        {"id": "first", "start": 0., "end": .5, "type": "presenter"},
        {"id": "second", "start": .5, "end": 2., "type": "presenter", "overlays": [layer(red["id"], start=.2, end=1.,
            keyframes=[{"time": 0., "opacity": 0.}, {"time": .8, "opacity": 1.}])]},
    ]
    output = api_workspace / "exports/partial.mp4"
    result = render(p, api_workspace, output, .85)
    video = frames(output, api_workspace)
    receipt = next(row for row in result["used_assets"] if row["role"] == "overlay")
    assert receipt["start"] == .7 and receipt["end"] == .9
    # A clipped preview does not accelerate the planned .8s opacity animation.
    assert video[-1].getpixel((56, 71))[0] < 30
    assert video[-1].getpixel((56, 71))[2] > 220


@pytest.mark.parametrize("change", ["source", "source_alias", "missing_asset", "outside", "bounds", "opacity", "timing", "keyframe", "blend", "count", "duplicate", "image_seek"])
def test_invalid_layers_rejected_without_overwriting_previous_export(api_workspace, layer_project, change):
    p = layer_project
    red = image_asset(p, api_workspace, "invalid.png", (255, 0, 0, 255))
    row = layer(red["id"])
    layers = [row]
    if change == "source":
        row["asset_id"] = "source"
    elif change == "source_alias":
        p["assets"].append({**p["assets"][0], "id": "alias"})
        row["asset_id"] = "alias"
    elif change == "missing_asset":
        row["asset_id"] = "unknown"
    elif change == "outside":
        outside = api_workspace.parent / "outside.png"
        outside.write_bytes((api_workspace / red["path"]).read_bytes())
        red["path"] = "../outside.png"
    elif change == "bounds":
        row["x"] = .9
    elif change == "opacity":
        row["opacity"] = 1.2
    elif change == "timing":
        row["end"] = 3.
    elif change == "keyframe":
        row["keyframes"] = [{"time": 2., "scale": 0}]
    elif change == "blend":
        row["blend"] = "malicious; filter"
    elif change == "count":
        layers = [{**row, "id": str(number)} for number in range(9)]
    elif change == "duplicate":
        layers = [row, copy.deepcopy(row)]
    elif change == "image_seek":
        row["source_in"] = 1.
    p["timeline"][0]["overlays"] = layers
    output = api_workspace / "exports/keep.mp4"
    output.write_bytes(b"previous candidate remains intact")
    with pytest.raises(RenderError):
        render(p, api_workspace, output, 1)
    assert output.read_bytes() == b"previous candidate remains intact"


def test_overlay_clip_span_cannot_overrun_the_media(api_workspace, layer_project):
    short = api_workspace / "assets/video/short.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1", "-f", "lavfi", "-i",
                    "color=c=red:s=64x64:r=10:d=0.5", "-c:v", "libx264", "-threads", "1", str(short)],
                   cwd=api_workspace, check=True, capture_output=True)
    p = layer_project
    p["assets"].append({"id": "short", "path": str(short.relative_to(api_workspace)), "kind": "video"})
    p["timeline"][0]["overlays"] = [layer("short", end=1.)]
    with pytest.raises(RenderError, match="excede"):
        render(p, api_workspace, api_workspace / "exports/overrun.mp4", 1)


def tone_file(root, name, *, silent=False, hot=False):
    path = root / "assets/audio" / name
    generator = "anullsrc=r=48000:cl=mono" if silent else "sine=frequency=997:sample_rate=48000:duration=2"
    args = [shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1", "-f", "lavfi", "-i", generator, "-t", "2"]
    if hot:
        args += ["-af", "volume=8"]
    args += ["-c:a", "pcm_s16le", "-threads", "1", str(path)]
    subprocess.run(args, cwd=root, check=True, capture_output=True)
    return path


def test_audio_measurements_are_finite_or_none_and_peak_warnings_are_actual(api_workspace):
    silent = tone_file(api_workspace, "silence.wav", silent=True)
    levels = measure_audio_levels(silent, api_workspace)
    assert levels["available"] is True and levels["audio_listened"] is False
    assert levels["measurements"]["integrated_lufs"] is None
    assert levels["measurements"]["true_peak_dbtp"] is None
    json.dumps(levels, allow_nan=False)
    hot = tone_file(api_workspace, "hot.wav", hot=True)
    levels = measure_audio_levels(hot, api_workspace)
    assert isinstance(levels["measurements"]["integrated_lufs"], float)
    assert levels["measurements"]["true_peak_dbtp"] > -1.
    assert any("Pico real medido" in warning for warning in levels["warnings"])
    assert levels["audio_listened"] is False


def test_render_measures_encoded_mix_and_limiter_never_auto_amplifies(api_workspace, layer_project):
    p = layer_project
    hot = tone_file(api_workspace, "hot_mix.wav", hot=True)
    p["assets"].append({"id": "hot", "path": str(hot.relative_to(api_workspace)), "kind": "audio"})
    p["audio"] = [{"asset_id": "hot", "start": 0., "end": 1., "source_in": 0., "gain_db": 12., "role": "sfx"}]
    output = api_workspace / "exports/limited_mix.mp4"
    receipt = render(p, api_workspace, output, 1)
    technical = receipt["technical"]
    assert technical["mix_limiter"]["limit"] == .82
    assert technical["mix_limiter"]["automatic_gain"] is False
    assert technical["mix_limiter"]["nominal_sample_ceiling_dbfs"] < -1.7
    measured = technical["output_audio_levels"]
    assert measured["available"] is True and measured["audio_listened"] is False
    assert measured["measurements"]["true_peak_dbtp"] < -.3
    assert technical["editorial_approved"] is False and technical["audio_listened"] is False
    independently = measure_audio_levels(output, api_workspace)
    assert independently["measurements"] == measured["measurements"]


def subtitle_frame(root, *, chin=.65, subtitle="bien ahora", split=False, keyframes=None):
    p = {"style": {"hook_seconds": 4.5}, "transcript": {"words": []}}
    scene = {"id": "caption", "start": 5., "end": 6., "_planned_end": 6.,
             "type": "split" if split else "presenter", "asset_id": "resource" if split else None,
             "chin_y": chin, "subtitle": subtitle, "keyframes": keyframes or []}
    cfg = {"primary": str(root / "assets/fonts/Sequel_Sans_Bold_Disp.ttf"),
           "accent": str(root / "assets/fonts/Scholar_Italic.ttf"),
           "split_height": 156}  # Prepared legacy55/45 geometry at284px height.
    frame = Image.new("RGB", (160, 284), (0, 0, 255))
    return _decorate(frame, p, scene, 5.5, cfg, [])


def test_caption_rejects_chin_with_no_safe_space_instead_of_covering_face(api_workspace):
    with pytest.raises(RenderError, match="barbilla"):
        subtitle_frame(api_workspace, chin=.94)
    with pytest.raises(RenderError, match="barbilla"):
        subtitle_frame(api_workspace, chin=.90, keyframes=[{"time": 0., "scale": 1.2}])


def test_actual_font_caption_fits_one_line_below_split_chin_and_safe_zone(api_workspace):
    frame = subtitle_frame(api_workspace, split=True, subtitle="bien ahora")
    pixels = frame.load()
    white_pixels = [(x, y) for x in range(160) for y in range(284)
                    if min(pixels[x, y]) > 200]
    assert white_pixels
    chin = round(284 * .55) + .65 * (284 - round(284 * .55))
    assert min(y for _, y in white_pixels) > chin
    assert max(y for _, y in white_pixels) < 284 * .90
    long_words = subtitle_frame(api_workspace, chin=.45, subtitle="automatización extraordinaria")
    white = [(x, y) for x in range(160) for y in range(284) if min(long_words.getpixel((x, y))) > 200]
    assert white and min(y for _, y in white) > .45 * 284
    assert max(y for _, y in white) - min(y for _, y in white) < 14
    with pytest.raises(RenderError, match="bloque"):
        subtitle_frame(api_workspace, chin=.45, subtitle="extremadamente" * 100)
