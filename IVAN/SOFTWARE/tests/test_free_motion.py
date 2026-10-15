"""Independent geometry checks and real tiny native exports of free designs."""
from __future__ import annotations

import copy
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from studio import core, design, render

ROOT = Path(__file__).resolve().parents[1]


def scene(elements=None, duration=2):
    return {"id": "custom_scene", "type": "motion", "template": "custom", "start": 0, "end": duration,
            "motion_design": {"canvas": {"background": "#000000"}, "elements": elements or [
                {"id": "box", "type": "shape", "x": .1, "y": .1, "width": .2, "height": .2, "color": "#ffffff"}]}}


@pytest.mark.parametrize("change", [
    {"id": "../escape"}, {"motion_design": None},
    {"motion_design": {"elements": []}}, {"type": "presenter"},
])
def test_schema_rejects_invalid_free_design(change):
    candidate = {**scene(), **change}
    with pytest.raises(core.StudioError):
        design.validate_design(candidate)


def test_sub_ulp_local_duration_is_accepted_but_real_overrun_is_rejected():
    candidate = scene(duration=4.1)
    candidate["start"] = 2.3
    el = candidate["motion_design"]["elements"][0]
    el["end"] = 1.8
    el["keyframes"] = [{"time": 1.8, "x": .2}]
    design.validate_design(candidate)
    el["end"] = 1.80001
    with pytest.raises(core.StudioError):
        design.validate_design(candidate)


@pytest.mark.parametrize("curve", design.EASES)
def test_partial_easing_preserves_original_curve_after_trim(curve):
    # Cutting the middle of an animation must not restart its original ease.
    lo, hi = .23, .81
    a, b = design.ease_value(lo, curve), design.ease_value(hi, curve)
    for u in (0, .03, .2, .5, .79, .98, 1):
        reconstructed = a + (b - a) * design.ease_value(u, curve, [lo, hi])
        assert reconstructed == pytest.approx(design.ease_value(lo + (hi - lo) * u, curve), abs=1e-12)


def test_path_velocity_uses_physical_pixels_in_portrait_canvas():
    el = {"x": 0, "y": 0, "start": 0, "end": 3,
          "path": {"points": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}]}}
    first = design.element_state(el, 1, 3, 100, 200)
    second = design.element_state(el, 2, 3, 100, 200)
    assert first["x"] == pytest.approx(1)
    assert first["y"] == pytest.approx(0)
    assert second["x"] == pytest.approx(1)
    assert second["y"] == pytest.approx(.5)


def test_sparse_keys_inherit_channels_and_zero_key_replaces_base():
    el = {"x": .1, "y": .2, "opacity": .8, "keyframes": [
        {"time": 0, "x": .3}, {"time": 1, "opacity": .2}, {"time": 2, "y": .6}]}
    pose = design.element_state(el, 1.5, 2, 100, 200)
    assert pose["x"] == pytest.approx(.3)
    assert pose["y"] == pytest.approx(.4)
    assert pose["opacity"] == pytest.approx(.2)


def test_static_design_ignores_animation_but_digest_detects_layout_change():
    candidate = scene()
    el = candidate["motion_design"]["elements"][0]
    before = design.design_digest(candidate)
    el.update(start=1, end=2, keyframes=[{"time": 0, "x": .7, "opacity": 0}],
              path={"points": [{"x": .8, "y": .8}, {"x": .9, "y": .9}]})
    assert design.design_digest(candidate) == before
    static = design.draw_design(candidate, 0, (100, 200), {}, animate=False, root=ROOT)
    assert static.getpixel((15, 25)) == (255, 255, 255, 255)
    animated = design.draw_design(candidate, 0, (100, 200), {}, root=ROOT)
    assert animated.getpixel((15, 25)) == (0, 0, 0, 255)
    el["width"] = .3
    assert design.design_digest(candidate) != before


def test_layer_order_alpha_and_same_asset_independent_elements():
    candidate = scene([
        {"id": "a", "type": "media", "asset_id": "same", "x": 0, "y": 0, "width": .5, "height": .5, "z": 2},
        {"id": "b", "type": "media", "asset_id": "same", "x": .5, "y": 0, "width": .5, "height": .5, "z": 1},
        {"id": "top", "type": "shape", "x": 0, "y": 0, "width": .1, "height": .1, "color": "#0000ff", "opacity": .5, "z": 3},
    ])
    frame = design.draw_design(candidate, 0, (100, 200), {},
                               {"a": Image.new("RGBA", (50, 100), "red"), "b": Image.new("RGBA", (50, 100), "green")}, root=ROOT)
    assert frame.getpixel((25, 25))[:3] == (255, 0, 0)
    assert frame.getpixel((75, 25))[:3] == (0, 128, 0)
    assert frame.getpixel((5, 5))[:3] == (127, 0, 128)


@pytest.mark.parametrize("mask", ["circle", "inset"])
def test_reveal_zero_hides_every_pixel_and_small_inset_does_not_crash(mask):
    candidate = scene()
    el = candidate["motion_design"]["elements"][0]
    el.update(width=.005, height=.02, mask={"type": mask},
              keyframes=[{"time": 0, "mask_progress": 0}, {"time": 2, "mask_progress": 1, "ease": "power2.inOut"}])
    zero = design.draw_design(candidate, 0, (160, 284), {}, root=ROOT)
    assert zero.convert("RGB").getbbox() is None
    for frame in range(30):
        design.draw_design(candidate, frame / 30, (160, 284), {}, root=ROOT)


def test_none_mask_rejects_reveal_and_memory_bound_rejects_huge_rotated_surface():
    candidate = scene()
    el = candidate["motion_design"]["elements"][0]
    el["keyframes"] = [{"time": 1, "mask_progress": 1}]
    with pytest.raises(core.StudioError, match="revelación"):
        design.validate_design(candidate)
    el["keyframes"] = [{"time": 1, "scale": 8}]
    el.update(x=0, y=0, width=1, height=1)
    with pytest.raises(core.StudioError, match="memoria"):
        design.validate_design(candidate, (1080, 1920))


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_real_custom_export_preserves_partial_last_frame_voice_and_source():
    # No source reel/parent project is edited; fixture media and temp files are local.
    cache = ROOT / ".estado/tmp"
    cache.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory(prefix="free_motion_test_", dir=cache) as work:
        folder = Path(work)
        source = folder / "source.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1",
                        "-f", "lavfi", "-i", "color=blue:s=160x284:r=12:d=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264",
                        "-c:a", "aac", "-pix_fmt", "yuv420p", "-threads", "1", "-shortest", str(source)], check=True)
        before = core.content_hash(source)
        custom = scene(duration=1.6)
        custom["motion_design"]["elements"][0].update(mask={"type": "inset"}, keyframes=[
            {"time": 0, "mask_progress": 0}, {"time": 1.6, "mask_progress": 1, "x": .5, "ease": "power2.inOut"}])
        project = {"source": "fixture_source", "assets": [{"id": "fixture_source", "path": source.relative_to(ROOT).as_posix(), "kind": "video", "duration": 2}],
                   "settings": {"width": 160, "height": 284, "fps": 12}, "fonts": core.fonts(),
                   "timeline": [custom], "audio": [], "transcript": {"words": []}}
        output = folder / "custom.mp4"
        receipt = render.render(project, ROOT, output, seconds=1.6)
        assert receipt["technical"]["decode_ok"] is True
        assert receipt["technical"]["original_voice_present"] is True
        assert receipt["technical"]["consecutive_frames_decoded"] == math.ceil(1.6 * 12)
        assert receipt["duration"] == pytest.approx(20 / 12, abs=.04)
        assert core.content_hash(source) == before
        raw = subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(output), "-an", "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"], check=True, stdout=subprocess.PIPE).stdout
        stride = 160 * 284 * 3
        first = Image.frombytes("RGB", (160, 284), raw[:stride])
        last = Image.frombytes("RGB", (160, 284), raw[-stride:])
        assert max(first.getpixel((20, 40))) < 5
        assert min(last.getpixel((90, 40))) > 230
        assert receipt["technical"]["editorial_approved"] is False
