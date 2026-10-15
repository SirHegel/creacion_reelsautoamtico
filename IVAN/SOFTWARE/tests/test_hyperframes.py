"""Independent software fixtures; never use or approve an active reel."""
import array
import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

from PIL import Image
import pytest

from studio import design, hyperframes as hf, render as native
from studio.core import StudioError


@pytest.fixture
def composition(tmp_path):
    assert tmp_path.resolve().is_relative_to(hf.ROOT / ".estado")
    missing_fonts = [name for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf")
                     if not (hf.ROOT / "assets/fonts" / name).is_file()]
    if missing_fonts:
        pytest.skip("Optional licensed local Sequel/Scholar fonts are absent from the public source: " + ", ".join(missing_fonts))
    dependencies = hf._dependencies()
    missing_runtime = [name for name in ("cli", "cli_bundle", "cli_package", "gsap", "path_plugin", "gsap_package",
                                         "node", "browser", "ffmpeg", "ffprobe") if not dependencies[name].is_file()]
    if missing_runtime:
        pytest.skip("Optional local HyperFrames/GSAP runtime is unavailable: " + ", ".join(missing_runtime))
    root = tmp_path
    fonts = root / "assets/fonts"
    fonts.mkdir(parents=True)
    for file in (hf.ROOT / "assets/fonts").glob("*.ttf"):
        shutil.copyfile(file, fonts / file.name)
    original = root / "source.mp4"
    native._run([native._tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i",
                 "color=c=0x343434:s=160x240:r=12:d=1.5", "-f", "lavfi", "-i",
                 "sine=frequency=440:sample_rate=48000:duration=1.5", "-c:v", "libx264",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-threads", "1", "-shortest", str(original)], root)
    rgba = root / "resource.png"
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 0))
    for x in range(5, 15):
        for y in range(5, 15):
            image.putpixel((x, y), (224, 164, 36, 255))
    image.save(rgba)
    packet = {"id": "packet", "type": "shape", "shape": "rect", "color": "#24d397",
              "x": .1, "y": .25, "width": .08, "height": .06, "radius": 8,
              "path": {"points": [{"x": .1, "y": .25}, {"x": .7, "y": .25}, {"x": .7, "y": .65}], "orient": False},
              "keyframes": [{"time": 0, "scale": 1}, {"time": 1.5, "scale": 1.2, "ease": "power2.inOut", "ease_window": [.15, .8]}]}
    panel = {"id": "panel", "type": "shape", "shape": "rect", "color": "#2a66ce",
             "x": .2, "y": .72, "width": .35, "height": .12, "radius": 12,
             "mask": {"type": "inset", "inset": {"left": .1, "right": .1, "top": 0, "bottom": 0}},
             "keyframes": [{"time": 0, "mask_progress": 0}, {"time": 1.5, "mask_progress": 1, "ease": "linear"}]}
    media = {"id": "resource", "type": "media", "asset_id": "resource", "source_in": 0,
             "x": .1, "y": .42, "width": .25, "height": .16,
             "mask": {"type": "circle"}, "keyframes": [{"time": 0, "rotation": 0}, {"time": 1.5, "rotation": 20}]}
    scene = {"id": "independent_software_test", "type": "motion", "template": "custom", "start": 0., "end": 1.5,
             "motion_design": {"canvas": {"background": "#101318"}, "elements": [packet, panel, media,
                 {"id": "text", "type": "text", "text": "Datos en tránsito", "font": "accent", "font_size": 76,
                  "x": .1, "y": .1, "width": .8, "height": .13, "color": "#ffffff"}]}}
    project = {"source": "source", "assets": [{"id": "source", "kind": "video", "path": "source.mp4"},
                {"id": "resource", "kind": "image", "path": "resource.png"}],
               "fonts": {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"},
               "settings": {"width": 160, "height": 240, "fps": 12}, "timeline": [scene], "audio": []}
    return root, project


def node_run(root, code):
    runtime, dependencies, _ = hf._runtime(root)
    script = root / ("probe_" + str(time.time_ns()) + ".mjs")
    script.write_text(code)
    command = [str(dependencies["node"]), str(script)]
    if shutil.which("nice"):
        command = [shutil.which("nice"), "-n", "10", *command]
    return subprocess.run(command, cwd=root, env=hf._environment(root, runtime, dependencies),
                          capture_output=True, text=True, timeout=20, check=True).stdout


def test_availability_is_not_execution_or_approval(composition):
    root, _ = composition
    status = hf.availability(root)
    assert status["available"] and status["cli_version"] == "0.8.147"
    assert status["gsap_version"] == "3.15.0"
    assert not status["verified_execution"] and not status["editorial_approved"]
    assert status["hardware_gpu"] is False and status["workers"] == 1
    assert "Standard" in status["gsap_license"]
    assert not (root / ".estado/hyperframes").exists()


def test_environment_and_isolator_reject_external_effects(composition):
    root, _ = composition
    runtime, dependencies, _ = hf._runtime(root)
    env = hf._environment(root, runtime, dependencies)
    assert "HOME" not in env and "GEMINI_API_KEY" not in env and "HEYGEN_API_KEY" not in env
    for key in ("TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PUPPETEER_CACHE_DIR"):
        assert Path(env[key]).is_relative_to(root)
    outside = root.parent / "forbidden_runtime_write"
    code = """import fs from 'node:fs';import cp from 'node:child_process';import os from 'node:os';
const errors=[];
for(const call of [()=>fs.writeFileSync(OUTSIDE,'bad'),()=>fs.readFileSync('/home/nonexistent-private-access.json'),()=>fetch('https://example.com'),()=>cp.spawn('ffmpeg',['-hwaccel','cuda']),()=>cp.exec('echo bad')]){try{call();}catch(e){errors.push(e.message);}}
console.log(JSON.stringify({errors,home:os.homedir()}));
""".replace("OUTSIDE", json.dumps(str(outside)))
    result = json.loads(node_run(root, code))
    assert len(result["errors"]) == 5
    assert not outside.exists()
    assert Path(result["home"]).is_relative_to(root)


def test_real_gsap_curve_window_matches_editor_interpolation(composition):
    root, _ = composition
    runtime, _, _ = hf._runtime(root)
    output = []
    for name in design.EASES:
        for window in ([0, 1], [.2, .72], [.999, 1]):
            frame = {"ease": name, "ease_window": window}
            expression = hf._ease(frame)
            if expression.startswith('"'):
                expression = "gsap.parseEase(" + expression + ")"
            output.append(f"({expression})(.37)")
    code = f"import {{createRequire}} from 'node:module';const require=createRequire(import.meta.url);const gsap=require({json.dumps(str(runtime/'gsap.min.js'))}).gsap;console.log(JSON.stringify([{','.join(output)}]));"
    values = json.loads(node_run(root, code))
    expected = [design.ease_value(.37, name, window) for name in design.EASES for window in ([0, 1], [.2, .72], [.999, 1])]
    assert values == pytest.approx(expected, abs=1e-9)


def test_generated_gsap_state_inherits_and_travels_by_pixel_distance(composition):
    root, project = composition
    element = project["timeline"][0]["motion_design"]["elements"][0]
    runtime, _, _ = hf._runtime(root)
    animation = hf._animate_element("#target", "#inner", element, 1.5, 160, 240).replace('"#target"', "target").replace('"#inner"', "inner")
    code = f"import {{createRequire}} from 'node:module';const require=createRequire(import.meta.url);const gsap=require({json.dumps(str(runtime/'gsap.min.js'))}).gsap;const target={{}},inner={{}},tl=gsap.timeline({{paused:true}});{animation}\nconst result=[];for(const t of [0,.375,.75,1.125,1.5,.2]){{tl.seek(t,false);result.push({{t,x:target.x,y:target.y,scale:target.scale,opacity:target.opacity}});}}console.log(JSON.stringify(result));"
    values = json.loads(node_run(root, code))
    for value in values:
        expected = design.element_state(element, value["t"], 1.5, 160, 240)
        assert value["x"] == pytest.approx(expected["x"] * 160, abs=1e-4)
        assert value["y"] == pytest.approx(expected["y"] * 240, abs=1e-4)
        assert value["scale"] == pytest.approx(expected["scale"], abs=1e-6)


def test_promisified_execfile_keeps_stdout_stderr_and_scope(composition):
    root,_=composition
    result=json.loads(node_run(root,"import {execFile} from 'node:child_process';import {promisify} from 'node:util';const result=await promisify(execFile)(process.execPath,['--version']);console.log(JSON.stringify(result));"))
    assert result["stdout"].startswith("v") and result["stderr"]==""


def test_loaded_code_and_mid_execution_change_cannot_claim_current_proof(composition,monkeypatch):
    root,project=composition
    before=hf._installation(root)
    changed=copy.deepcopy(before)
    changed["pixel_code_sha256"]["render.py"]="0"*64
    with pytest.raises(StudioError,match="cambiaron"):
        hf._unchanged(before,changed)
    monkeypatch.setattr(hf,"LOADED_ADAPTER_SHA256","0"*64)
    assert hf.availability(root)["module_current"] is False
    with pytest.raises(StudioError,match="reinicia"):
        hf.render(project,root,root/"stale.mp4",.5)
    assert not (root/"stale.mp4").exists()


def test_build_is_local_editable_escaped_and_does_not_overwrite(composition):
    root, project = composition
    dangerous = '</script><script>fetch("https://example.com")</script>'
    project["timeline"][0]["motion_design"]["elements"][-1]["text"] = dangerous
    original_sha = hf._sha(root / "source.mp4")
    manifest = hf.build(project, root, root / ".estado/hyperframes/build", .5)
    scene = (root / manifest["directory"] / "compositions/scene_000.html").read_text()
    assert dangerous not in scene and "&lt;/script&gt;" in scene
    assert 'data-composition-id="scene_000"' in scene and "paused:true" in scene
    assert "ease:" in scene and "clipPath" in scene
    assert "duration:1.5" in scene  # requested crop does not speed up the path
    assert not manifest["editorial_approved"]
    assert all(item["editable_dom_motion"] for item in manifest["scene_engines"])
    assert hf._sha(root / "source.mp4") == original_sha
    assert all((root / path).is_file() for path in manifest["editable_files"])
    with pytest.raises(StudioError, match="vacía"):
        hf.build(project, root, root / manifest["directory"], .5)


@pytest.mark.parametrize("case", ["escape", "source", "missing", "window", "font"])
def test_invalid_inputs_fail_before_browser_execution(composition, case):
    root, project = composition
    if case == "escape":
        project["assets"][0]["path"] = "../outside.mp4"
    elif case == "source":
        project["timeline"][0]["motion_design"]["elements"][2]["asset_id"] = "source"
    elif case == "missing":
        project["timeline"][0]["motion_design"]["elements"][2]["asset_id"] = "missing"
    elif case == "window":
        project["timeline"][0]["motion_design"]["elements"][0]["keyframes"][-1]["ease_window"] = [.8, .2]
    else:
        font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        if not font.exists():
            pytest.skip("No test replacement font installed")
        shutil.copyfile(font, root / "assets/fonts/wrong.ttf")
        project["fonts"]["primary"] = "assets/fonts/wrong.ttf"
    with pytest.raises((StudioError, native.RenderError)):
        hf.build(project, root, root / ".estado/hyperframes/invalid", .5)


def test_execution_lock_is_cancelable_without_touching_owner(composition):
    root, _ = composition
    entered, release = threading.Event(), threading.Event()
    def owner():
        with hf._execution_lock(root):
            entered.set()
            release.wait(3)
    thread = threading.Thread(target=owner)
    thread.start()
    assert entered.wait(1)
    cancelled = threading.Event()
    cancelled.set()
    try:
        with pytest.raises(StudioError, match="cancelado"):
            with hf._execution_lock(root, cancelled):
                pass
        assert thread.is_alive()
    finally:
        release.set()
        thread.join(3)


def test_cli_cancel_terminates_only_its_own_process_group(composition, monkeypatch):
    root, _ = composition
    runtime, dependencies, status = hf._runtime(root)
    script = root / "cancel_fixture.mjs"
    pid_file = root / "fixture_pids.json"
    script.write_text("import fs from 'node:fs';import cp from 'node:child_process';const child=cp.spawn(process.execPath,['-e','setInterval(()=>{},1000)']);fs.writeFileSync("+json.dumps(str(pid_file))+",JSON.stringify({parent:process.pid,child:child.pid}));setInterval(()=>{},1000);")
    dependencies = {**dependencies,"cli":script}
    monkeypatch.setattr(hf,"_runtime",lambda _: (runtime,dependencies,status))
    directory = root / ".estado/hyperframes/cancel"
    directory.mkdir(parents=True)
    event = threading.Event()
    def signal():
        for _ in range(100):
            if pid_file.exists():
                event.set()
                return
            time.sleep(.02)
    thread = threading.Thread(target=signal)
    thread.start()
    try:
        with pytest.raises(StudioError,match="cancelado"):
            hf._cli(root,directory,[],"cancel",event,timeout=10)
    finally:
        thread.join(3)
    pids = json.loads(pid_file.read_text())
    for pid in pids.values():
        stat = Path(f"/proc/{pid}/stat")
        assert not stat.exists() or stat.read_text().split()[2] == "Z"
    assert not event is None and (root / "source.mp4").is_file()


def test_copied_raw_video_and_sidecar_are_not_overwritten(composition):
    root,project = composition
    copy_path = root / "disguised_raw.mp4"
    shutil.copyfile(root/"source.mp4",copy_path)
    project["assets"].append({"id":"disguised","kind":"video","path":copy_path.name})
    project["timeline"][0]["motion_design"]["elements"][2]["asset_id"]="disguised"
    with pytest.raises((StudioError,native.RenderError),match="crudo"):
        hf.build(project,root,root/".estado/hyperframes/disguised",.5)
    project["timeline"][0]["motion_design"]["elements"][2]["asset_id"]="resource"
    (root/"export.json").write_text('{"private_note":"keep"}')
    with pytest.raises(StudioError,match="no pertenece"):
        hf.render(project,root,root/"export.mp4",.5)
    assert (root/"export.json").read_text() == '{"private_note":"keep"}'


def _green_center(image):
    pixels = [(x, y) for y in range(image.height) for x in range(image.width)
              if (lambda c: c[1] > 110 and c[1] > c[0] * 1.7 and c[1] > c[2] * 1.15)(image.getpixel((x,y)))]
    assert pixels
    return sum(x for x,y in pixels)/len(pixels),sum(y for x,y in pixels)/len(pixels)


def _pixels(image):
    data=image.tobytes()
    return zip(data[0::3],data[1::3],data[2::3])


def test_real_browser_render_static_capture_and_voice_receipt(composition):
    root, project = composition
    original_sha = hf._sha(root / "source.mp4")
    static = hf.snapshot_design(project, project["timeline"][0]["id"], root, root / "design.png")
    assert static["technical"]["static"] and hf.verify_receipt(static, root)
    assert not hf.availability(root)["verified_execution"]
    with Image.open(root / static["path"]) as image:
        center = _green_center(image.convert("RGB"))
        assert center == pytest.approx((22, 66.5), abs=2)
    receipt = hf.render(project, root, root / "technical.mp4", 1.5)
    assert hf.verify_receipt(receipt, root)
    assert hf.availability(root)["verified_execution"]
    assert hf.availability(root)["tested_duration"] == pytest.approx(1.5,abs=.03)
    technical = receipt["technical"]
    adapter = technical["hyperframes"]
    assert adapter["verified_execution"] and adapter["hardware_gpu"] is False
    assert adapter["workers"] == 1 and adapter["max_ffmpeg_threads"] == 2
    check = json.loads((root / adapter["check_path"]).read_text())
    assert check["ok"] is True and check["browserSkipped"] is False
    assert technical["consecutive_frames_decoded"] == 18
    assert adapter["runtime_versions"]["node"].startswith("v")
    assert "Chrome" in adapter["runtime_versions"]["browser"]
    execution=json.loads((root/adapter["execution_path"]).read_text())
    assert execution["observed_browser_processes"] >= 3 and execution["observed_encoder_processes"] >= 1
    assert technical["video_codec"] == "h264" and technical["audio_codec"] == "aac"
    assert technical["original_voice_present"] and not technical["audio_listened"]
    assert not technical["editorial_approved"] and not adapter["production_conformant"]
    assert receipt["duration"] == pytest.approx(1.5, abs=.03)
    assert hf._sha(root / "source.mp4") == original_sha
    assert any(item["role"] == "motion_element" and item["asset_id"] == "resource" for item in receipt["used_assets"])
    snapshots = [Image.open(root / path).convert("RGB") for path in adapter["browser_snapshots"]]
    first, middle, last = map(_green_center, (snapshots[0],snapshots[1],snapshots[-1]))
    assert first[0] < middle[0] < last[0] + 2 and last[1] > first[1] + 70
    blue_counts=[sum(c[2]>130 and c[2]>c[1]*1.3 and c[2]>c[0]*2 for c in _pixels(image)) for image in snapshots]
    assert blue_counts[0] == 0 and blue_counts[-1] > blue_counts[1] > 0
    orange=sum(c[0]>150 and c[1]>100 and c[2]<80 for c in _pixels(snapshots[0]))
    assert orange>30  # actual RGBA image survives contain, alpha and circle mask
    # The final PCM still carries the original 440Hz narration fixture.
    pcm = root / "voice.s16"
    native._run([native._tool("ffmpeg"),"-v","error","-y","-i",str(root/receipt["path"]),"-vn","-ac","1","-ar","48000","-f","s16le",str(pcm)],root)
    samples = array.array("h",pcm.read_bytes())
    samples = samples[4800:24000]
    crossings = sum(a <= 0 < b for a,b in zip(samples,samples[1:]))
    assert crossings / (len(samples)/48000) == pytest.approx(440, abs=5)
    proof = root / adapter["proof_files"][0]["path"]
    proof.write_text(proof.read_text()+"\n")
    assert not hf.verify_receipt(receipt, root)
    assert not hf.availability(root)["verified_execution"]


def test_hybrid_source_clip_and_real_rgba_mov(composition):
    root,project=composition
    raw=root/"alpha.rgba"
    with raw.open("wb") as stream:
        for frame in range(18):
            image=Image.new("RGBA",(20,20),(0,0,0,0))
            for x in range(4+(frame%3),14+(frame%3)):
                for y in range(5,15):
                    image.putpixel((x,y),(224,164,36,255))
            stream.write(image.tobytes())
    clip=root/"alpha.mov"
    native._run([native._tool("ffmpeg"),"-v","error","-y","-f","rawvideo","-pixel_format","rgba",
                 "-video_size","20x20","-framerate","12","-i",str(raw),"-c:v","qtrle","-threads","1",str(clip)],root)
    project["assets"].append({"id":"alpha","kind":"video","path":"alpha.mov"})
    scene=project["timeline"][0]
    scene["start"]=.25
    for element in scene["motion_design"]["elements"]:
        for frame in element.get("keyframes",[]):
            frame["time"]*=1.25/1.5
    element=scene["motion_design"]["elements"][2]
    element.update(asset_id="alpha",mask={"type":"none"},start=.25,end=1.25,keyframes=[])
    project["timeline"].insert(0,{"id":"authentic_source_fixture","type":"presenter","start":0,"end":.25})
    receipt=hf.render(project,root,root/"hybrid.mp4",1.5)
    assert hf.verify_receipt(receipt,root)
    engines=receipt["technical"]["scene_engines"]
    assert "native CPU raster" in engines[0]["engine"] and engines[0]["editable_dom_motion"] is False
    assert engines[1]["editable_dom_motion"] is True
    assert any(item["asset_id"]=="source" and item["role"]=="presenter" and item["end"]==.25 for item in receipt["used_assets"])
    element_use=next(item for item in receipt["used_assets"] if item["asset_id"]=="alpha" and item["role"]=="motion_element")
    assert element_use["start"]==.5 and element_use["end"]==1.5
    rgba=root/"actual.rgb"
    native._run([native._tool("ffmpeg"),"-v","error","-y","-i",str(root/receipt["path"]),"-an","-f","rawvideo","-pix_fmt","rgb24",str(rgba)],root)
    data=rgba.read_bytes(); frame_bytes=160*240*3
    frames=[Image.frombytes("RGB",(160,240),data[i*frame_bytes:(i+1)*frame_bytes]) for i in range(18)]
    assert frames[0].getpixel((80,100))==pytest.approx((52,52,52),abs=3)
    # Original transparency must reveal the actual dark canvas, not a matte.
    with Image.open(root/receipt["technical"]["hyperframes"]["browser_snapshots"][2]) as image:
        assert image.convert("RGB").getpixel((17,102))==(16,19,24)
    assert frames[10].getpixel((17,102))==pytest.approx((16,19,24),abs=10)
    assert sum(c[0]>150 and c[1]>100 and c[2]<80 for c in _pixels(frames[10]))>20
    centers=[]
    for index in (6,7,8):
        pixels=[(x,y) for y in range(100,145) for x in range(12,64)
                if (lambda c:c[0]>150 and c[1]>100 and c[2]<80)(frames[index].getpixel((x,y)))]
        assert pixels
        centers.append(sum(x for x,y in pixels)/len(pixels))
    assert centers[1]>centers[0]+1 and centers[2]>centers[1]+1
    # No DOM motion on this media: the shift comes from decoded source frames.
    assert receipt["technical"]["original_audio_present"]
