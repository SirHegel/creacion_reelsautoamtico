"""Offline CPU facial measurements. Results are proposals, never scene edits.

Reuses an existing, explicitly copied MediaPipe runtime/model; no installer,
network model resolver, parent imports, camera access or hardware GPU delegate.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import signal
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import core
from .analysis import FORMATS

RUNTIME = ".estado/models/tracking/local"
ENGINE = "MediaPipe FaceDetector + FaceLandmarker / WASM CPU"
DEFAULTS = {"start": 0., "end": None, "sample_fps": 4., "min_confidence": .6,
            "smoothing": .4, "minimum_coverage": .8, "max_samples": 240}
CHIN_INDEX = 152
PAGE = r'''<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; connect-src 'self'; img-src 'self'; worker-src 'self' blob:; object-src 'none'">
<pre id="result">pending</pre><script type="module">
import {FilesetResolver,FaceDetector,FaceLandmarker} from '/runtime/vision_bundle.mjs';
try {
 const input=await (await fetch('/input.json')).json();
 const files=await FilesetResolver.forVisionTasks('/runtime/wasm');
 const detector=await FaceDetector.createFromOptions(files,{
  baseOptions:{modelAssetPath:'/runtime/face_detector.tflite',delegate:'CPU'},
  runningMode:'IMAGE', minDetectionConfidence:input.min_confidence});
 const landmark=await FaceLandmarker.createFromOptions(files,{
  baseOptions:{modelAssetPath:'/runtime/face_landmarker.task',delegate:'CPU'},
  runningMode:'IMAGE', numFaces:2, minFaceDetectionConfidence:input.min_confidence,
  minFacePresenceConfidence:input.min_confidence, minTrackingConfidence:input.min_confidence,
  outputFaceBlendshapes:false, outputFacialTransformationMatrixes:false});
 const samples=[];
 for(const frame of input.frames){
  const image=new Image(); image.src=frame.url; await image.decode();
  const detected=detector.detect(image);
  const faces=landmark.detect(image).faceLandmarks;
  samples.push({time:frame.time,width:image.naturalWidth,height:image.naturalHeight,
   detections:detected.detections.map(d=>({score:d.categories[0]?.score??null,
      box:d.boundingBox})),
   faces:faces.map(f=>({count:f.length,chin:f[152],nose:f[1],
    bounds:{x:Math.min(...f.map(p=>p.x)),y:Math.min(...f.map(p=>p.y)),
      right:Math.max(...f.map(p=>p.x)),bottom:Math.max(...f.map(p=>p.y))}}))});
 }
 detector.close(); landmark.close();
 await fetch('/result.json',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({samples,delegate:'CPU',camera_used:false})});
 document.getElementById('result').textContent='completed';
}catch(error){
 await fetch('/result.json',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({error:String(error)})});
 document.getElementById('result').textContent='failed';
}
</script>'''


def validate_options(options=None):
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise core.StudioError("Las opciones de tracking deben ser un objeto.")
    unknown = set(options) - set(DEFAULTS)
    if unknown:
        raise core.StudioError("Opción de tracking desconocida: " + ", ".join(sorted(map(str, unknown))))
    out = {**DEFAULTS, **options}
    bounds = {"start": (0, 14400), "sample_fps": (.5, 10), "min_confidence": (.3, .99),
              "smoothing": (.05, 1), "minimum_coverage": (.5, 1), "max_samples": (1, 600)}
    for name, (lo, hi) in bounds.items():
        value = out[name]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not lo <= value <= hi:
            raise core.StudioError(f"{name} debe estar entre {lo} y {hi}.")
    if type(out["max_samples"]) is not int:
        raise core.StudioError("max_samples debe ser entero.")
    end = out["end"]
    if end is not None and (isinstance(end, bool) or not isinstance(end, (int, float)) or not math.isfinite(end) or end <= out["start"] or end > 14400):
        raise core.StudioError("end debe ser mayor que start y finito.")
    if end is not None and end - out["start"] > 120:
        raise core.StudioError("El seguimiento CPU admite hasta 120 segundos por análisis.")
    return out


def _hash(path):
    return core.digest(path)


def _path(root, value, exists=False):
    try:
        return core.confined(value, root=root, must_exist=exists)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        raise core.StudioError("Ruta de tracking inválida.", 403) from error


def capability(root=None):
    root = core.ROOT if root is None else Path(root)
    try:
        manifest = _runtime(root)
        return {"available": True, "engine": ENGINE, "device": "cpu",
                "runtime_version": manifest["runtime_version"], "confidence": "detector_score",
                "chin": "model_estimated_landmark_152", "automatic_application": False,
                "landmark_count": "468 or 478, reported per sample"}
    except core.StudioError as error:
        return {"available": False, "engine": ENGINE, "reason": str(error), "automatic_application": False}


def _runtime(root):
    directory = _path(root, RUNTIME)
    receipt = _path(root, directory / "provenance.json", True)
    try:
        manifest = json.loads(receipt.read_text(encoding="utf-8"))
        files = manifest["files"]
        required = {"vision_bundle.mjs", "face_landmarker.task", "face_detector.tflite",
                    "wasm/vision_wasm_internal.js", "wasm/vision_wasm_internal.wasm"}
        if not isinstance(files, dict) or not required.issubset(files):
            raise ValueError("runtime incompleto")
        for relative, sha in files.items():
            path = _path(root, directory / relative, True)
            if not path.is_relative_to(directory) or not re.fullmatch(r"[a-f0-9]{64}", str(sha)) or _hash(path) != sha:
                raise ValueError("huellas distintas")
        if not manifest.get("runtime_version"):
            raise ValueError("versión ausente")
    except (KeyError, TypeError, ValueError) as error:
        raise core.StudioError("Modelo/runtime facial local incompleto o alterado; no se instala automáticamente.", 409) from error
    if not shutil.which("google-chrome") and not shutil.which("chromium"):
        raise core.StudioError("Falta Chrome/Chromium local; no se instala automáticamente.", 409)
    return manifest


def _run(args, root, timeout=40, completed=None, details=False):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8",
           "TMPDIR": str(_path(root, ".estado/tmp")),
           "XDG_CACHE_HOME": str(_path(root, ".estado/cache/tracking")),
           "XDG_CONFIG_HOME": str(_path(root, ".estado/config/tracking")),
           "XDG_DATA_HOME": str(_path(root, ".estado/data/tracking")),
           "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
    for name in ("TMPDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        _path(root, env[name]).mkdir(parents=True, exist_ok=True)
    # Chrome's POSIX socket has a 108-byte path limit. This descriptor alias
    # resolves to our own .estado/tmp, keeps every byte there, and avoids /tmp.
    directory_fd = None
    if Path(args[0]).name in {"google-chrome", "chromium"}:
        directory_fd = os.open(env["TMPDIR"], os.O_RDONLY | os.O_DIRECTORY)
        env["TMPDIR"] = f"/proc/{os.getpid()}/fd/{directory_fd}"
    if shutil.which("nice"):
        args = [shutil.which("nice"), "-n", "10", *args]
    try:
        if completed is None:
            result = subprocess.run(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        else:
            with tempfile.TemporaryFile(dir=_path(root, ".estado/tmp")) as stdout, tempfile.TemporaryFile(dir=_path(root, ".estado/tmp")) as stderr:
                process = subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    deadline = time.monotonic() + timeout
                    while not completed.wait(.1):
                        if process.poll() is not None:
                            stderr.seek(0)
                            raise core.StudioError("El navegador terminó antes de medir: " + stderr.read()[-1200:].decode("utf-8", "replace"))
                        if time.monotonic() >= deadline:
                            raise core.StudioError("Tiempo de tracking CPU excedido; no se inventan resultados.")
                finally:
                    # Only the fresh browser process group created above; never
                    # signal an existing browser, render or production terminal.
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)
                return b""
    except (OSError, subprocess.TimeoutExpired) as error:
        raise core.StudioError("No se pudo ejecutar tracking CPU: " + str(error)) from error
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
    if result.returncode:
        raise core.StudioError("Tracking CPU: " + result.stderr.decode("utf-8", "replace")[-1200:])
    return (result.stdout, result.stderr) if details else result.stdout


def _probe(path, root):
    raw = _run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS,
                "-show_streams", "-show_format", "-of", "json", str(path)], root)
    try:
        data = json.loads(raw)
        stream = next(s for s in data["streams"] if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"))
        duration = float(data.get("format", {}).get("duration") or stream.get("duration") or 0)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duración no disponible")
        stream["_format_start_time"] = float(data.get("format", {}).get("start_time") or 0)
        return duration, stream
    except (ValueError, KeyError, TypeError, StopIteration) as error:
        raise core.StudioError("El seguimiento requiere un video real con duración.") from error


def _browser(root, frames, options, runtime, work):
    output = {}
    done = threading.Event()
    runtime_path = _path(root, RUNTIME)
    allowed = {"/": (PAGE.encode(), "text/html"), "/input.json": (json.dumps({"frames": frames, "min_confidence": options["min_confidence"]}).encode(), "application/json")}
    for name in runtime["files"]:
        path = _path(root, runtime_path / name, True)
        mime = "application/wasm" if path.suffix == ".wasm" else "text/javascript" if path.suffix in {".mjs", ".js"} else "application/octet-stream"
        allowed["/runtime/" + name] = (path, mime)
    for frame in frames:
        allowed[frame["url"]] = (_path(root, frame["path"], True), "image/jpeg")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("Host") != authority:
                self.send_error(403)
                return
            item = allowed.get(self.path)
            if not item:
                self.send_error(404)
                return
            data, mime = item
            content = data.read_bytes() if isinstance(data, Path) else data
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            if self.path != "/result.json" or self.headers.get("Host") != authority or self.headers.get("Origin") != address or done.is_set():
                self.send_error(403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 4_000_000:
                    raise ValueError("resultado excesivo")
                result = json.loads(self.rfile.read(size))
                if not isinstance(result, dict):
                    raise ValueError("resultado inválido")
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return
            output.update(result)
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            done.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    address = "http://127.0.0.1:" + str(server.server_port)
    authority = "127.0.0.1:" + str(server.server_port)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    browser = shutil.which("google-chrome") or shutil.which("chromium")
    profile = _path(root, work / "chrome_profile")
    command = [browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-gpu-compositing",
               "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--disable-vulkan",
               "--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-first-run",
               "--disable-default-apps", "--disable-extensions", "--disable-breakpad", "--disable-dev-shm-usage",
               "--renderer-process-limit=1", "--num-raster-threads=1", "--user-data-dir=" + str(profile),
               "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", address + "/"]
    try:
        _run(command, root, timeout=110, completed=done)
        if not done.wait(1):
            raise core.StudioError("El navegador CPU no devolvió medidas; no se inventa detección.")
        if output.get("error"):
            raise core.StudioError("MediaPipe CPU: " + str(output["error"])[:1200])
        if output.get("delegate") != "CPU" or not isinstance(output.get("samples"), list) or len(output["samples"]) != len(frames):
            raise core.StudioError("Resultado facial incompleto.")
        return output["samples"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def _point(value):
    if not isinstance(value, dict):
        return None
    vals = [value.get("x"), value.get("y")]
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in vals):
        return None
    return {"x": round(vals[0], 6), "y": round(vals[1], 6)}


def _measure_samples(raw, frames, options):
    if not isinstance(raw, list) or len(raw) != len(frames):
        raise core.StudioError("Número de muestras faciales inválido.")
    samples, previous = [], None
    for measure, frame in zip(raw, frames):
        when = measure.get("time") if isinstance(measure, dict) else None
        if isinstance(when, bool) or not isinstance(when, (int, float)) or not math.isfinite(when) or abs(when - frame["time"]) > .0001:
            raise core.StudioError("Timestamps del seguimiento no corresponden a las muestras.")
        detections = measure.get("detections", [])
        faces = measure.get("faces", [])
        if not isinstance(detections, list) or not isinstance(faces, list) or any(not isinstance(face, dict) for face in faces):
            raise core.StudioError("Medidas faciales inválidas.")
        valid = [d for d in detections if isinstance(d, dict) and isinstance(d.get("score"), (float, int))
                 and not isinstance(d["score"], bool) and math.isfinite(d["score"]) and options["min_confidence"] <= d["score"] <= 1]
        sample = {"time": frame["time"], "evidence": frame["path"], "detected": False,
                  "requested_time": frame.get("requested_time", frame["time"]),
                  "status": "no_face", "confidence": None, "face_count": len(valid),
                  "raw": None, "smoothed": None, "reviewed": False}
        if len(valid) > 1 or len(faces) > 1:
            sample["status"] = "ambiguous_multiple_faces"
        elif len(valid) == 1 and len(faces) == 1:
            face = faces[0]
            chin, nose = _point(face.get("chin")), _point(face.get("nose"))
            bounds = face.get("bounds", {})
            if not isinstance(bounds, dict):
                bounds = {}
            b = {k: bounds.get(k) for k in ("x", "y", "right", "bottom")}
            if chin and nose and all(not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in b.values()) and b["right"] > b["x"] and b["bottom"] > b["y"] and isinstance(face.get("count"), int) and 468 <= face["count"] <= 500:
                box = {"x": round(b["x"], 6), "y": round(b["y"], 6), "width": round(b["right"] - b["x"], 6), "height": round(b["bottom"] - b["y"], 6)}
                position = {"focus_x": nose["x"], "focus_y": nose["y"], "chin_x": chin["x"], "chin_y": chin["y"]}
                # Do not carry a stale face through gaps or sudden cuts/identity jumps.
                reset = previous is None or math.hypot(previous["focus_x"] - position["focus_x"], previous["focus_y"] - position["focus_y"]) > .18
                smooth = position.copy() if reset else {k: round(previous[k] + options["smoothing"] * (v - previous[k]), 6) for k, v in position.items()}
                sample.update(detected=True, status="detected_pending_review", confidence=round(valid[0]["score"], 6),
                              bbox=box, raw=position, smoothed=smooth, smoothing_reset=reset, landmark_count=face["count"])
                previous = smooth
            else:
                sample["status"] = "invalid_or_clipped_landmarks"
        if not sample["detected"]:
            previous = None
        samples.append(sample)
    return samples


def _proposals(project, samples, options):
    proposals = []
    for scene in project.get("timeline", []):
        if not isinstance(scene, dict) or scene.get("type") not in {"presenter", "split", "talking", "camera"}:
            continue
        try:
            start = float(scene.get("source_in", scene["start"]))
            span = float(scene["end"]) - float(scene["start"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(span) or start < 0 or span <= 0:
            continue
        relevant = [s for s in samples if start <= s["time"] < start + span]
        selected = [s for s in relevant if s["detected"]]
        coverage = len(selected) / len(relevant) if relevant else 0
        proposal = {"scene_id": scene.get("id"), "source_start": start, "source_end": start + span,
                    "coverage": round(coverage, 4), "reviewed": False, "apply_automatically": False,
                    "status": "insufficient_detection", "changes": None}
        covers_span = bool(relevant) and relevant[0]["time"] <= start + 1 / options["sample_fps"] and relevant[-1]["time"] >= start + span - 1 / options["sample_fps"]
        if selected and covers_span and coverage >= options["minimum_coverage"] and not any(s["status"] == "ambiguous_multiple_faces" for s in relevant):
            # Source coordinates must be transformed by the renderer's real crop,
            # zoom and split geometry before becoming scene.chin_y/focus_y.
            proposal.update(status="pending_geometry_and_visual_review",
                            source_coordinates={k: round(sum(s["smoothed"][k] for s in selected) / len(selected), 6) for k in selected[0]["smoothed"]},
                            samples=[{"source_time": s["time"], **s["smoothed"]} for s in selected],
                            minimum_confidence=min(s["confidence"] for s in selected),
                            evidence=[s["evidence"] for s in selected])
        proposals.append(proposal)
    return proposals


def analyze_tracking(project, options=None, progress=None, cancel=None):
    """Return measurements/artifacts only; leave the given project unchanged."""
    options = validate_options(options)
    if not isinstance(project, dict) or not isinstance(project.get("assets"), list) or not isinstance(project.get("timeline", []), list):
        raise core.StudioError("Proyecto inválido para seguimiento facial.")
    source = next((a for a in project["assets"] if isinstance(a, dict) and a.get("id") == project.get("source")), None)
    if not source or not isinstance(source.get("path"), str):
        raise core.StudioError("Asigna un crudo local antes de seguir el rostro.")
    root = core.ROOT
    path = _path(root, source["path"], True)
    project_id = project.get("id")
    if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", project_id):
        raise core.StudioError("ID de proyecto inválido.")
    # Late import avoids any parent system imports and respects the shared lock.
    from .jobs import cpu_slot
    with cpu_slot():
        return _analyze(project, source, path, root, options, progress, cancel)


def _analyze(project, source, path, root, options, progress, cancel):
    runtime = _runtime(root)
    source_sha = _hash(path)
    if source.get("sha256") and source["sha256"] != source_sha:
        raise core.StudioError("El crudo cambió respecto al contenido registrado.", 409)
    identity = {"source_sha256": source_sha, "options": options, "runtime_files": runtime["files"], "engine_code_sha256": _hash(Path(__file__))}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    directory = _path(root, f"projects/{project['id']}/tracking/{key}")
    expected = root / f"projects/{project['id']}/tracking/{key}"
    if directory != expected:
        raise core.StudioError("La evidencia de tracking no admite enlaces en su destino.", 403)
    directory.mkdir(parents=True, exist_ok=True)
    report = _path(root, directory / "measurements.json")
    receipt = _path(root, f".estado/tracking/receipts/{project['id']}_{key}.json")
    if report.exists():
        try:
            if not receipt.exists() or json.loads(receipt.read_text()).get("report_sha256") != _hash(report):
                raise ValueError("report alterado")
            cached = json.loads(report.read_text())
            if cached.get("identity") != identity or any(_hash(_path(root, f["path"], True)) != f["sha256"] for f in cached["evidence"]):
                raise ValueError("cache alterada")
            cached["reused"] = True
            cached["proposals"] = _proposals(project, cached["samples"], options)
            if _hash(path) != source_sha:
                raise core.StudioError("El crudo cambió durante la lectura del tracking.", 409)
            return cached
        except (KeyError, ValueError, TypeError, core.StudioError) as error:
            raise core.StudioError("La evidencia facial almacenada cambió; no se reutiliza ni sobrescribe.", 409) from error
    temp_base = _path(root, ".estado/tmp")
    temp_base.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="tracking_", dir=temp_base) as folder:
        work = Path(folder)
        snapshot = _path(root, work / ("source" + path.suffix))
        shutil.copyfile(path, snapshot)
        if _hash(snapshot) != source_sha or _hash(path) != source_sha:
            raise core.StudioError("El crudo cambió mientras se preparaba tracking.", 409)
        duration, stream = _probe(snapshot, root)
        end = min(duration, options["end"] if options["end"] is not None else options["start"] + 60)
        if options["start"] >= end:
            raise core.StudioError("El intervalo de seguimiento no existe en el crudo.")
        count = math.ceil((end - options["start"]) * options["sample_fps"] - 1e-9)
        if count > options["max_samples"]:
            raise core.StudioError("Intervalo demasiado largo para max_samples; ajusta end o sample_fps.")
        frames = []
        for index in range(count):
            if cancel is not None and cancel.is_set():
                raise core.StudioError("Seguimiento cancelado.", 409)
            when = round(options["start"] + index / options["sample_fps"], 6)
            final = _path(root, directory / f"frame_{index:04d}.jpg")
            target = _path(root, work / f"frame_{index:04d}.jpg")
            if final.exists():
                raise core.StudioError("Evidencia facial ocupada; no se sobrescribe.", 409)
            stream_index = stream.get("index", 0)
            if not isinstance(stream_index, int) or isinstance(stream_index, bool) or not 0 <= stream_index <= 1024:
                raise core.StudioError("Índice de stream de video inválido.")
            _, diagnostic = _run(["ffmpeg", "-nostdin", "-v", "info", "-copyts", "-ss", str(when), "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS,
                  "-threads", "2", "-i", str(snapshot), "-map", f"0:{stream_index}", "-frames:v", "1", "-vf", "scale='min(640,iw)':-2,showinfo",
                  "-filter_threads", "2", "-threads", "2", "-q:v", "3", "-n", str(target)], root, details=True)
            match = re.search(rb"\bn:\s*0\s+pts:\s*[-\d]+\s+pts_time:([-\d.eE+]+)", diagnostic)
            if not match or not target.is_file() or not target.stat().st_size:
                raise core.StudioError("FFmpeg no confirmó el fotograma y su timestamp; no se inventa tiempo.")
            actual_time = round(float(match.group(1)) - stream.get("_format_start_time", 0), 6)
            if not math.isfinite(actual_time):
                raise core.StudioError("Timestamp de fotograma no finito.")
            # Low-FPS inputs may map several requests to the same decoded frame.
            # Keep only distinct frames inside the requested source interval.
            if actual_time < options["start"] - .0001 or actual_time >= end or frames and actual_time <= frames[-1]["time"]:
                target.unlink()
                continue
            frames.append({"time": actual_time, "requested_time": when, "path": target.relative_to(root).as_posix(), "final_path": final.relative_to(root).as_posix(), "url": f"/frames/{index:04d}.jpg"})
            if progress:
                progress(.05 + .4 * (index + 1) / count, "Decodificando muestras faciales CPU.")
        if not frames:
            raise core.StudioError("El intervalo no contiene fotogramas decodificables distintos.")
        raw = _browser(root, frames, options, runtime, work)
        if cancel is not None and cancel.is_set():
            raise core.StudioError("Seguimiento cancelado.", 409)
        if _runtime(root)["files"] != runtime["files"]:
            raise core.StudioError("El modelo/runtime cambió durante el seguimiento.", 409)
        if _hash(Path(__file__)) != identity["engine_code_sha256"]:
            raise core.StudioError("El código del seguimiento cambió durante la ejecución.", 409)
        if _hash(path) != source_sha:
            raise core.StudioError("El crudo cambió durante el seguimiento; no se promueve resultado.", 409)
        final_frames = [{**frame, "path": frame["final_path"]} for frame in frames]
        samples = _measure_samples(raw, final_frames, options)
        if _hash(path) != source_sha:
            raise core.StudioError("El crudo cambió durante el seguimiento; no se promueve resultado.", 409)
        evidence = [{"path": f["final_path"], "sha256": _hash(_path(root, f["path"], True)), "source_time": f["time"]} for f in frames]
        detected = sum(s["detected"] for s in samples)
        result = {"at": core.now(), "engine": ENGINE, "device": "cpu", "gpu_used": False,
                  "identity": identity, "source": source["id"], "source_sha256": source_sha,
                  "original_unchanged": True, "duration": duration, "interval": [options["start"], end],
                  "sampling": {"requested_fps": options["sample_fps"], "count": len(samples), "times": "measured_decoded_pts_seconds_relative_to_container_start", "rotation": "FFmpeg metadata autorotation applied"},
                  "confidence_kind": "FaceDetector category score, not calibrated probability or landmark accuracy",
                  "chin_method": "estimated FaceLandmarker landmark 152; visual confirmation required",
                  "thresholds": {"detection": options["min_confidence"], "landmark_presence": options["min_confidence"]},
                  "summary": {"detected_samples": detected, "no_face_samples": sum(s["status"] == "no_face" for s in samples),
                              "ambiguous_samples": sum(s["status"] == "ambiguous_multiple_faces" for s in samples),
                              "coverage": round(detected / len(samples), 4)},
                  "samples": samples, "proposals": _proposals(project, samples, options), "evidence": evidence,
                  "runtime_provenance": runtime, "elapsed_seconds": round(time.monotonic() - began, 3),
                  "reviewed": False, "editorial_approved": False, "audio_listened": False,
                  "apply_automatically": False, "reused": False,
                  "path": report.relative_to(root).as_posix(), "url": "/api/files/" + report.relative_to(root).as_posix(),
                  "limitations": ["Muestras discretas: no demuestran rostro en cada frame ni presupuesto de presencia.",
                                  "Perfil, oclusión y varias personas pueden impedir seguimiento o cambiar identidad.",
                                  "No interpola rostros ausentes; smoothing se reinicia tras huecos o saltos.",
                                  "Coordenadas del original: transformar con el crop/split/keyframes antes de aplicar.",
                                  "Detección, barbilla y foco necesitan revisión visual; no cambia la edición."]}
        for frame in frames:
            final = _path(root, frame["final_path"])
            if final.exists():
                raise core.StudioError("Evidencia ocupada durante tracking; no se sobrescribe.", 409)
            # Exclusive hard-link publication prevents replacement of unmanaged
            # files even if they appeared after the preflight check.
            os.link(_path(root, frame["path"], True), final)
        core.atomic_json(report, result)
        core.atomic_json(receipt, {"report_sha256": _hash(report), "source_sha256": source_sha,
                                  "engine_code_sha256": identity["engine_code_sha256"]})
        if progress:
            progress(1, "Medidas faciales listas; propuestas pendientes de revisión.")
        return result
