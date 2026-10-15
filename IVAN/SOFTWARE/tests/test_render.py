"""Integration checks use tiny synthetic media, entirely inside SOFTWARE."""
from __future__ import annotations

import copy
import json
import math
import array
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest

from PIL import Image

from studio import motion
from studio.render import RenderCancelled, RenderError, confined, probe_media, render


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg/FFprobe necesarios")
class RenderIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cache = ROOT / ".estado" / "tests"
        cache.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="render-", dir=cache)
        cls.folder = Path(cls.temporary.name)
        cls.source = cls.folder / "source.mp4"
        cls.broll = cls.folder / "broll.mp4"
        cls.burn = cls.folder / "burn.mp4"
        binary = shutil.which("ffmpeg")
        for path, color, tone in ((cls.source, "blue", 440), (cls.broll, "green", 660)):
            subprocess.run([binary, "-v", "error", "-y", "-filter_threads", "1",
                            "-f", "lavfi", "-i", f"color=c={color}:s=160x284:r=8:d=2",
                            "-f", "lavfi", "-i", f"sine=frequency={tone}:duration=2",
                            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
                            "-threads", "1", "-shortest", str(path)], check=True,
                           cwd=ROOT, env={"PATH": str(Path(binary).parent), "TMPDIR": str(cache)})
        subprocess.run([binary, "-v", "error", "-y", "-filter_threads", "1", "-f", "lavfi",
                        "-i", "color=c=white:s=160x284:r=8:d=0.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-threads", "1", str(cls.burn)], check=True, cwd=ROOT,
                       env={"PATH": str(Path(binary).parent), "TMPDIR": str(cache)})
        # These are explicitly declared real fonts for the fixture; no runtime fallback.
        for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf"):
            origin = ROOT.parent / "recursos" / name
            if not origin.is_file():
                raise unittest.SkipTest("Fuentes declaradas no disponibles para la prueba")
            shutil.copyfile(origin, cls.folder / name)
        cls.project = {
            "assets": [{"id": "source", "path": str(cls.source.relative_to(ROOT)), "kind": "video", "duration": 2},
                       {"id": "broll", "path": str(cls.broll.relative_to(ROOT)), "kind": "video", "duration": 2}],
            "source": "source", "settings": {"width": 160, "height": 284, "fps": 8},
            "fonts": {"primary": str((cls.folder / "Sequel_Sans_Bold_Disp.ttf").relative_to(ROOT)),
                      "accent": str((cls.folder / "Scholar_Italic.ttf").relative_to(ROOT))},
            "timeline": [{"id": "s1", "start": 0, "end": .75, "type": "split", "asset_id": "broll", "chin_y": .65},
                         {"id": "s2", "start": .75, "end": 1.25, "type": "broll", "asset_id": "broll", "source_in": .75},
                         {"id": "s3", "start": 1.25, "end": 2, "type": "motion", "template": "workflow", "title": "Una idea conecta", "nodes": ["Entrada", "Acción", "Resultado"]}],
            "transcript": {"words": [{"start": .1, "end": .5, "word": "PALABRA_PROHIBIDA_EN_HOOK"}]},
            "audio": [{"asset_id": "broll", "start": 0, "end": 2, "gain_db": -28, "role": "music"}]
        }

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_real_mp4_composition_voice_and_audit(self):
        output = self.folder / "candidate.mp4"
        notifications = []
        result = render(copy.deepcopy(self.project), ROOT, output, seconds=2,
                        progress=lambda fraction, message: notifications.append(fraction))
        self.assertTrue(output.is_file())
        self.assertGreater(result["size"], 1000)
        self.assertEqual(result["width"], 160)
        self.assertAlmostEqual(result["duration"], 2, delta=.15)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertTrue(result["technical"]["decode_ok"])
        self.assertTrue(result["technical"]["original_voice_present"])
        self.assertFalse(result["technical"]["editorial_approved"])
        self.assertFalse(result["technical"]["audio_listened"])
        self.assertTrue((ROOT / result["technical"]["motion_review"]).is_file())
        self.assertEqual(notifications[-1], 1)
        raw = subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(output),
                              "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"],
                             check=True, stdout=subprocess.PIPE).stdout
        first = Image.frombytes("RGB", (160, 284), raw)
        top, bottom = first.getpixel((80, 30)), first.getpixel((80, 260))
        self.assertGreater(top[1], top[2] + 30)
        self.assertGreater(bottom[2], bottom[1] + 30)
        # Split divider is precisely 55/45; one authentic source below.
        self.assertGreater(first.getpixel((80, 150))[1], 60)
        self.assertGreater(first.getpixel((80, 165))[2], 80)
        pcm = subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(output),
                              "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-threads", "1", "pipe:1"],
                             check=True, stdout=subprocess.PIPE).stdout
        samples = array.array("h", pcm)
        def energy(tone):
            real = sum(sample * math.cos(2 * math.pi * tone * index / 8000) for index, sample in enumerate(samples))
            imaginary = sum(sample * math.sin(2 * math.pi * tone * index / 8000) for index, sample in enumerate(samples))
            return math.hypot(real, imaginary)
        # Actual output contains the original 440 Hz narration surrogate,
        # louder than the separately mixed 660 Hz musical surrogate.
        self.assertGreater(energy(440), 10 * energy(660))
        self.assertEqual(result["technical"]["consecutive_frames_decoded"], 16)

    def test_real_burn_overlay_and_used_resource_receipt(self):
        project = copy.deepcopy(self.project)
        project["assets"].append({"id": "burn", "path": str(self.burn.relative_to(ROOT)), "kind": "video", "duration": .5})
        project["timeline"] = [{"id": "scene", "start": 0, "end": 1, "type": "presenter",
                                "transition_asset_id": "burn", "transition_duration": .5}]
        project["audio"] = []
        output = self.folder / "burned.mp4"
        result = render(project, ROOT, output, 1)
        transitions = [entry for entry in result["used_assets"] if entry.get("role") == "transition"]
        self.assertEqual(transitions[0]["asset_id"], "burn")
        self.assertEqual(transitions[0]["blend"], "screen")
        self.assertAlmostEqual(transitions[0]["start"], .5)
        raw = subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(output),
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-threads", "1", "pipe:1"],
                             check=True, stdout=subprocess.PIPE).stdout
        first = Image.frombytes("RGB", (160, 284), raw[:160 * 284 * 3])
        last = Image.frombytes("RGB", (160, 284), raw[-160 * 284 * 3:])
        self.assertLess(first.getpixel((80, 80))[0], 30)
        self.assertGreater(min(last.getpixel((80, 80))), 230)

    def test_path_escape_and_missing_font(self):
        with self.assertRaises(RenderError):
            confined(ROOT, "../fuera.mp4")
        project = copy.deepcopy(self.project)
        project["fonts"]["primary"] = ".estado/noexiste.ttf"
        with self.assertRaises(RenderError):
            render(project, ROOT, self.folder / "invalid.mp4", 2)

    def test_do_not_replace_original(self):
        original = self.source.read_bytes()
        with self.assertRaises(RenderError):
            render(self.project, ROOT, self.source, 2)
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_media_span_and_timeline_gap(self):
        project = copy.deepcopy(self.project)
        project["timeline"][1]["source_in"] = 1.9
        with self.assertRaises(RenderError):
            render(project, ROOT, self.folder / "overrun.mp4", 2)
        project = copy.deepcopy(self.project)
        project["timeline"][1]["start"] = .9
        with self.assertRaises(RenderError):
            render(project, ROOT, self.folder / "gap.mp4", 2)

    def test_cancel_preserves_previous_candidate(self):
        output = self.folder / "cancel.mp4"
        output.write_bytes(b"approved-existing-export")
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(RenderCancelled):
            render(self.project, ROOT, output, 2, cancel=cancel)
        self.assertEqual(output.read_bytes(), b"approved-existing-export")

    def test_motion_transfers_and_counter_has_no_invented_numbers(self):
        fonts = self.project["fonts"]
        primary, accent = str(ROOT / fonts["primary"]), str(ROOT / fonts["accent"])
        scene = self.project["timeline"][-1]
        frames = [motion.compose(scene, at, .75, (160, 284), primary, accent).tobytes() for at in (.03, .3, .6)]
        self.assertEqual(len(set(frames)), 3)
        with self.assertRaises(ValueError):
            motion.compose({"template": "counter"}, .5, 1, (160, 284), primary, accent)
        a = motion.keyframe_state([{"time": 0, "scale": 1}, {"time": .25, "scale": 1.1}], .125)
        self.assertAlmostEqual(a["scale"], 1.05)


if __name__ == "__main__":
    unittest.main()
