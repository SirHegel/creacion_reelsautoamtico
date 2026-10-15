"""Reproduce the actual JPEG/planar-RGB right-edge defect without a browser."""
import json
from pathlib import Path
import subprocess

from PIL import Image
import pytest

from studio import hyperframes as hf, jobs


SDR_CHAIN = "scale=in_color_matrix=bt601:in_range=pc:flags=neighbor,format=gbrp,scale=out_color_matrix=bt709:out_range=tv:flags=neighbor"


def isolated_run(root, tool, arguments):
    runtime, dependencies, _ = hf._runtime(root)
    script = root / "encode.mjs"
    script.write_text("import {execFile} from 'node:child_process';import {promisify} from 'node:util';"
                      "await promisify(execFile)(" + json.dumps(str(dependencies[tool])) + ","
                      + json.dumps(arguments) + ",{timeout:20000});")
    env = hf._environment(root, runtime, dependencies)
    env["ASCENDIA_HF_TRACE"] = str(root / "trace.jsonl")
    subprocess.run([str(dependencies["node"]), str(script)], cwd=root, env=env,
                   capture_output=True, timeout=30, check=True)
    trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
    return next(item["args"] for item in trace if item.get("type") == "subprocess" and
                Path(item["file"]).name == tool)


def isolated_encode(root, source, destination, filters):
    arguments = ["-v", "error", "-i", str(source), "-vf", filters, "-frames:v", "1",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-colorspace:v", "bt709", "-color_primaries:v", "bt709", "-color_trc:v", "bt709",
                 "-color_range", "tv", str(destination)]
    return isolated_run(root, "ffmpeg", arguments)


@pytest.mark.parametrize("width", [360, 1080])
def test_sdr_jpeg_encoding_preserves_the_last_partial_block(tmp_path, width):
    assert tmp_path.resolve().is_relative_to(hf.ROOT / ".estado")
    source, output = tmp_path / "original.jpg", tmp_path / "encoded.mp4"
    image = Image.new("RGB", (width, 64), (16, 19, 24))
    # A differently colored edge proves this fix keeps real content at the
    # original coordinates rather than filling the missing columns.
    for x in range(width - 8, width):
        for y in range(64):
            image.putpixel((x, y), (72, 112, 160))
    image.save(source, quality=95)
    original = source.read_bytes()
    with jobs.cpu_slot():
        arguments = isolated_encode(tmp_path, source, output, SDR_CHAIN)
        decoded = subprocess.run([str(hf._dependencies()["ffmpeg"]), "-v", "error", "-threads", "2",
            "-filter_threads", "2", "-filter_complex_threads", "2", "-i", str(output), "-frames:v", "1",
            "-threads", "2", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            cwd=tmp_path, capture_output=True, timeout=20, check=True).stdout
    assert len(decoded) == width * 64 * 3
    pixels = [tuple(decoded[(32 * width + x) * 3:(32 * width + x + 1) * 3]) for x in range(width)]
    assert max(abs(a - b) for a, b in zip(pixels[width // 2], (16, 19, 24))) <= 5
    assert all(min(pixel) >= 55 for pixel in pixels[-6:])
    assert pixels[-1][2] > pixels[-1][1] > pixels[-1][0]
    assert source.read_bytes() == original
    actual = arguments[arguments.index("-vf") + 1]
    assert actual == SDR_CHAIN.replace("flags=neighbor", "flags=neighbor+full_chroma_int+accurate_rnd")
    assert "crop=" not in actual and "pad=" not in actual and "scale=" in actual
    assert all(arguments[index + 1] == "2" for index, value in enumerate(arguments)
               if value in {"-threads", "-filter_threads", "-filter_complex_threads"})


def test_nonmatching_media_filters_are_not_rewritten(tmp_path):
    assert tmp_path.resolve().is_relative_to(hf.ROOT / ".estado")
    source, output = tmp_path / "original.jpg", tmp_path / "encoded.mp4"
    Image.new("RGB", (160, 64), (30, 45, 60)).save(source)
    filters = "scale=160:64:flags=neighbor,format=yuv420p"
    with jobs.cpu_slot():
        arguments = isolated_encode(tmp_path, source, output, filters)
    assert arguments[arguments.index("-vf") + 1] == filters


@pytest.mark.parametrize("tool,option,value", [
    ("ffprobe", "-vf", SDR_CHAIN),
    ("ffmpeg", "-metadata", "note=" + SDR_CHAIN),
    ("ffmpeg", "-vf", "zscale=transferin=smpte2084:transfer=linear,format=gbrpf32le"),
    ("ffmpeg", "-vf", SDR_CHAIN + ",setsar=1"),
])
def test_sdr_workaround_does_not_hijack_probe_metadata_or_hdr(tmp_path,tool,option,value):
    assert tmp_path.resolve().is_relative_to(hf.ROOT / ".estado")
    with jobs.cpu_slot():
        arguments = isolated_run(tmp_path, tool, ["-version", option, value])
    assert arguments[arguments.index(option) + 1] == value
