"""Metadata regressions with an explicitly mocked camera/runtime; no MP4 or browser.

The actual HyperFrames builder writes its manifest and DOM. Only media preparation
is mocked, so these fixtures never qualify as executed renderer evidence.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from studio import hyperframes as hf, render as native


@pytest.fixture
def mocked_split_builder(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(hf.CODE_ROOT / ".estado/tmp")
    missing = [name for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf")
               if not (hf.CODE_ROOT / "assets/fonts" / name).is_file()]
    if missing:
        pytest.skip("Optional licensed local Sequel/Scholar fonts are absent from the public source: " + ", ".join(missing))
    root = tmp_path
    fonts = root / "assets/fonts"
    fonts.mkdir(parents=True)
    for filename in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf"):
        shutil.copyfile(hf.CODE_ROOT / "assets/fonts" / filename, fonts / filename)
    source = root / "declared_source_fixture.bin"
    source.write_bytes(b"Synthetic source metadata fixture. Not a video.")
    runtime = root / ".estado/runtime_fixture"
    runtime.mkdir(parents=True)
    for name in ("gsap.min.js", "MotionPathPlugin.min.js", "third_party.json"):
        (runtime / name).write_text("Mock runtime metadata fixture; not executable.")

    def prepare(project, requested_root, seconds):
        assert Path(requested_root) == root
        settings = project["settings"]
        asset = {**project["assets"][0], "local": source}
        return {
            "width": settings["width"], "height": settings["height"],
            "split_height": native.split_height(settings["height"], settings.get("split_motion_ratio", .55)),
            "fps": 12, "duration": 1., "primary": fonts / "Sequel_Sans_Bold_Disp.ttf",
            "accent": fonts / "Scholar_Italic.ttf", "font_assets": {},
            "source": asset, "assets": {asset["id"]: asset},
            "source_info": {"streams": [{"codec_type": "audio", "index": 1}]},
            "scenes": [{**copy.deepcopy(project["timeline"][0]), "_planned_end": 1., "overlays": []}],
        }

    def camera(cfg, scene, requested_root, directory, cancel):
        assert requested_root == root
        data = b"Mock lower camera, no encode or playback proof."
        name = "media/" + hashlib.sha256(data).hexdigest() + ".fixture"
        destination = directory / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {"url": name, "image": False, "fixture_only": True}

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata fixture must not invoke a renderer, decoder, browser or CLI")

    monkeypatch.setattr(native, "_prepare", prepare)
    monkeypatch.setattr(native, "render", forbidden)
    monkeypatch.setattr(hf, "_runtime", lambda _: (runtime, {}, {"available": False, "fixture_only": True}))
    monkeypatch.setattr(hf, "_font_identity", lambda *args: None)
    monkeypatch.setattr(hf, "_split_camera", camera)
    monkeypatch.setattr(hf, "_caption_assets", lambda *args: [])
    monkeypatch.setattr(hf, "_cli", forbidden)
    project = {
        "source": "a_declared_fixture", "assets": [{"id": "a_declared_fixture", "kind": "video", "path": source.name}],
        "settings": {"width": 360, "height": 640, "fps": 12},
        "timeline": [{"id": "split_metadata", "type": "split", "template": "custom", "start": 0., "end": 1.,
                      "source_in": .25, "motion_design": {"canvas": {"background": "#101318"}, "elements": [
                          {"id": "shape", "type": "shape", "x": .1, "y": .1, "width": .2, "height": .2,
                           "color": "#ffffff", "shape": "rect"}]} }],
        "fonts": {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"},
    }
    return root, project


@pytest.mark.parametrize("height,ratio,upper", [
    (640, .50, 320), (640, .55, 352),
    (642, .50, 322), (642, .55, 354),
    (1920, .50, 960), (1920, .55, 1056),
])
def test_split_receipt_uses_actual_pixel_regions_and_preserves_source_use(mocked_split_builder, height, ratio, upper):
    root, project = mocked_split_builder
    project["settings"].update(height=height, split_motion_ratio=ratio)
    directory = root / ".estado/hyperframes/mock_build"
    manifest = hf.build(project, root, directory, 1.)
    persisted = json.loads((directory / "build.json").read_text())
    use = next(item for item in persisted["used_assets"] if item["role"] == "split")
    assert use == next(item for item in manifest["used_assets"] if item["role"] == "split")
    assert use["region"] == "lower_authentic_cpu_crop"
    assert (use["motion_height_px"], use["presenter_height_px"], use["output_height_px"]) == (upper, height-upper, height)
    assert use["motion_height_px"] + use["presenter_height_px"] == use["output_height_px"]
    assert (use["asset_id"], use["start"], use["end"], use["source_in"]) == (project["source"], 0., 1., .25)
    composition = (directory / "compositions/scene_000.html").read_text()
    assert f"top:{upper}px;width:360px;height:{height-upper}px" in composition
    assert f"height:{upper}px;overflow:hidden;background:" in composition
    assert manifest["adapter"] == {"available": False, "fixture_only": True}
    assert manifest["editorial_approved"] is False
    if height == 642:
        assert use["motion_height_px"] != height*ratio  # report rounding in pixels, never a fictitious exact percentage


def test_missing_split_setting_keeps_legacy_pixels_without_fixed_percent_label(mocked_split_builder):
    root, project = mocked_split_builder
    project["settings"]["height"] = 642
    manifest = hf.build(project, root, root / ".estado/hyperframes/legacy_mock_build", 1.)
    use = next(item for item in manifest["used_assets"] if item["role"] == "split")
    assert use["region"] == "lower_authentic_cpu_crop"
    assert (use["motion_height_px"], use["presenter_height_px"], use["output_height_px"]) == (354, 288, 642)
