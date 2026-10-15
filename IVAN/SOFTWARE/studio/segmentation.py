"""Local person segmentation: MediaPipe WASM CPU, alpha MOV and original audio.

Model card: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Selfie%20Segmentation.pdf
This is confidence segmentation, not hair matting or editorial approval.
"""
from __future__ import annotations

import array
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import select
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import core, media_tools as media

OPERATION = "remove_background_video"
ENGINE = "MediaPipe ImageSegmenter / WASM CPU · selfie_segmenter float16/1"
MODEL = ".estado/models/segmentation/local/selfie_segmenter.tflite"
MODEL_SHA256 = "191ac9529ae506ee0beefa6b2c945a172dab9d07d1e802a290a4e4038226658b"
RUNTIME = ".estado/models/tracking/local"
DEFAULTS = {"start": 0, "duration": None, "fps": 30, "max_width": 540, "max_height": 960,
            "threshold": .5, "softness": .1, "feather": 0, "temporal_smoothing": 0}
MAX_FRAMES = 900
MAX_RGBA_BYTES = 2 * 1024 ** 3
_BINARY_CACHE = {}

PAGE = r'''<!doctype html><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; connect-src 'self'; img-src 'self'; object-src 'none'; worker-src 'self' blob:">
<script type="module">
import {FilesetResolver,ImageSegmenter} from './runtime/vision_bundle.mjs';
let segmenter;
try {
 const files=await FilesetResolver.forVisionTasks(new URL('./runtime/wasm',location.href).href);
 segmenter=await ImageSegmenter.createFromOptions(files,{
  baseOptions:{modelAssetPath:new URL('./model.tflite',location.href).href,delegate:'CPU'},
  runningMode:'VIDEO',outputConfidenceMasks:true,outputCategoryMask:false});
 const labels=segmenter.getLabels();
 if(labels.length!==1 || labels[0]!=='selfie')throw Error('Unexpected model labels');
 let count=0;
 while(true){
  const item=await (await fetch('./next.json',{cache:'no-store'})).json();
  if(item.done)break;
  if(item.error)throw Error(item.error);
  const image=new Image();image.src='./frame.png?index='+item.index;await image.decode();
  let mask,width,height;
  segmenter.segmentForVideo(image,item.timestamp_ms,result=>{
   if(result.confidenceMasks?.length!==1)throw Error('Expected single person-confidence mask');
   const actual=result.confidenceMasks[0];width=actual.width;height=actual.height;
   // Memory belongs to the synchronous callback. Copy before releasing it.
   mask=new Float32Array(actual.getAsFloat32Array());
   result.close();
  });
  const response=await fetch('./mask',{method:'POST',headers:{
   'Content-Type':'application/octet-stream','X-Frame-Index':String(item.index),
   'X-Mask-Width':String(width),'X-Mask-Height':String(height)},body:mask.buffer});
  if(!response.ok)throw Error('Mask rejected '+response.status);
  count++;
 }
 segmenter.close();segmenter=undefined;
 await fetch('./complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({count,labels,confidence_mask_channels:1,delegate:'CPU'})});
}catch(error){
 if(segmenter)segmenter.close();
 await fetch('./error',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({error:String(error)})});
}
</script>'''


def validate_options(options=None):
    options = {} if options is None else options
    if not isinstance(options, dict) or any(not isinstance(key, str) for key in options):
        raise core.StudioError("Las opciones de segmentación requieren un objeto JSON.")
    if set(options) - set(DEFAULTS):
        raise core.StudioError("Opciones de segmentación no admitidas: " + ", ".join(sorted(set(options) - set(DEFAULTS))))
    result = {**DEFAULTS, **options}
    bounds = {"start": (0, 86400), "fps": (10, 30), "max_width": (160, 1080), "max_height": (160, 1080),
              "threshold": (.05, .95), "softness": (.01, 1), "feather": (0, 8), "temporal_smoothing": (0, .8)}
    for key, (lo, hi) in bounds.items():
        core.finite_number(result[key], key, lo, hi)
        if key in {"fps", "max_width", "max_height"}:
            if int(result[key]) != result[key]:
                raise core.StudioError(key + " debe ser entero.")
            result[key] = int(result[key])
    if result["max_width"] % 2 or result["max_height"] % 2:
        raise core.StudioError("Las dimensiones de segmentación deben ser pares.")
    if result["duration"] is not None:
        core.finite_number(result["duration"], "duration", .01, 30)
    return result


def _path(root, value, exists=False):
    try:
        return media._inside(root, value, exists)
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise core.StudioError("Ruta de segmentación inválida.", 403) from error


def _destination(root, value):
    raw = Path(value) if Path(value).is_absolute() else Path(root) / value
    actual = _path(root, raw)
    if raw.absolute() != actual or raw.is_symlink():
        raise core.StudioError("El destino de segmentación no admite enlaces ni alias.", 403)
    return actual


def _hash(path):
    return media._hash(path)


def _signature(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _binary(name):
    path = shutil.which(name)
    if path is None:
        raise core.StudioError(name + " no está disponible localmente.", 409)
    resolved = Path(path).resolve()
    signature = _signature(resolved)
    cache = _BINARY_CACHE.get(str(resolved))
    if not cache or cache[0] != signature:
        cache = (signature, _hash(resolved))
        _BINARY_CACHE[str(resolved)] = cache
    result = {"path": path, "resolved": str(resolved), "sha256": cache[1], "signature": list(signature)}
    if name in {"google-chrome", "chromium"}:
        payload = resolved.with_name("chrome")
        if payload.is_file() and payload != resolved:
            payload_signature = _signature(payload)
            payload_cache = _BINARY_CACHE.get(str(payload))
            if not payload_cache or payload_cache[0] != payload_signature:
                payload_cache = (payload_signature, _hash(payload))
                _BINARY_CACHE[str(payload)] = payload_cache
            result["payload"] = {"resolved": str(payload), "sha256": payload_cache[1], "signature": list(payload_signature)}
    return result


def _runtime(root):
    directory = _path(root, RUNTIME)
    receipt = _path(root, directory / "provenance.json", True)
    model = _path(root, MODEL, True)
    model_receipt = _path(root, model.with_name("provenance.json"), True)
    try:
        manifest = json.loads(receipt.read_text())
        model_manifest = json.loads(model_receipt.read_text())
        names = {"vision_bundle.mjs", "package.json", "wasm/vision_wasm_internal.js", "wasm/vision_wasm_internal.wasm",
                 "wasm/vision_wasm_module_internal.js", "wasm/vision_wasm_module_internal.wasm",
                 "wasm/vision_wasm_nosimd_internal.js", "wasm/vision_wasm_nosimd_internal.wasm"}
        if manifest.get("runtime_version") != "1.1.0" or not names.issubset(manifest.get("files", {})):
            raise ValueError("runtime incompatible")
        files = {}
        for name in sorted(names):
            path = _path(root, directory / name, True)
            expected = manifest["files"][name]
            if not path.is_relative_to(directory) or _hash(path) != expected:
                raise ValueError("runtime alterado")
            files[name] = expected
        if _hash(model) != MODEL_SHA256 or model_manifest.get("sha256") != MODEL_SHA256:
            raise ValueError("modelo alterado")
        contract = model_manifest["mask_contract_verified_from_metadata_and_model_card"]
        if (any(type(contract.get(key)) is not int for key in ("output_tensor_channels", "expected_person_confidence_mask_index", "expected_runtime_confidence_mask_channels"))
                or contract.get("output_tensor_channels") != 1 or contract.get("expected_person_confidence_mask_index") != 0
                or contract.get("expected_runtime_confidence_mask_channels") != 1 or contract.get("label") != "selfie"):
            raise ValueError("contrato de máscara ausente")
        code = {"segmentation.py": _hash(__file__), "media_tools.py": _hash(media.__file__)}
        if code["segmentation.py"] != LOADED_CODE_SHA256:
            raise ValueError("reinicia el proceso después de cambiar el módulo")
        browser = "google-chrome" if shutil.which("google-chrome") else "chromium"
        binaries = {name: _binary(name) for name in ("ffmpeg", "ffprobe", browser)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise core.StudioError("Runtime/modelo de segmentación local incompleto, alterado o incompatible; no se instala automáticamente.", 409) from error
    return {"engine": ENGINE, "runtime_version": "1.1.0", "runtime_files": files,
            "runtime_receipt_sha256": _hash(receipt), "model_sha256": MODEL_SHA256, "model_version": "float16/1",
            "model_receipt_sha256": _hash(model_receipt), "model_license": "Apache-2.0", "pixel_code_sha256": code,
            "binaries": binaries, "confidence_mask_channels": 1, "person_mask_index": 0, "label": "selfie"}


def capability(root=None):
    root = core.ROOT if root is None else Path(root)
    result = {"operation": OPERATION, "engine": ENGINE, "available": False, "verified_execution": False,
              "device": "cpu", "gpu_used": False, "workers": 1, "max_ffmpeg_threads": 2,
              "max_seconds": 30, "max_frames": MAX_FRAMES, "max_rgba_bytes": MAX_RGBA_BYTES,
              "editorial_approved": False, "quality": "person confidence segmentation; not hair matting"}
    try:
        root = _path(root, ".")
        runtime = _runtime(root)
        result.update(available=True, runtime_version=runtime["runtime_version"], model_sha256=MODEL_SHA256,
                      fingerprint=hashlib.sha256(json.dumps(runtime, sort_keys=True, allow_nan=False).encode()).hexdigest())
        proof = _path(root, ".estado/segmentation/integration.json")
        if proof.is_file():
            marker = json.loads(proof.read_text())
            receipt = _destination(root, marker["receipt_path"])
            cached = json.loads(receipt.read_text())
            if semantic_receipt_digest(cached) == marker["semantic_receipt_sha256"]:
                _verify_cache(cached, root, runtime)
                result.update(verified_execution=True, tested_duration=cached["duration"], tested_dimensions=[cached["width"], cached["height"]])
    except (core.StudioError, KeyError, ValueError, TypeError, OSError, AttributeError) as error:
        result["reason"] = str(error)
    return result


def _environment(root):
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH") if key in os.environ}
    for key, relative in {"TMPDIR": ".estado/tmp", "XDG_CACHE_HOME": ".estado/cache/segmentation",
                          "XDG_CONFIG_HOME": ".estado/config/segmentation", "XDG_DATA_HOME": ".estado/data/segmentation"}.items():
        path = _destination(root, relative)
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
    return env


def _stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=3)


def _spawn(args, root, stdout, stderr, stdin=subprocess.DEVNULL, env=None):
    command = [str(arg) for arg in args]
    if shutil.which("taskset") and hasattr(os, "sched_getaffinity"):
        cores = sorted(os.sched_getaffinity(0))[:2]
        command = [shutil.which("taskset"), "-c", ",".join(map(str, cores)), *command]
    if shutil.which("nice"):
        command = [shutil.which("nice"), "-n", "10", *command]
    return subprocess.Popen(command, cwd=root, env=env or _environment(root), stdin=stdin,
                            stdout=stdout, stderr=stderr, start_new_session=True, shell=False)


def _check(cancel, deadline):
    if cancel is not None and cancel.is_set():
        raise core.StudioError("Segmentación cancelada.", 409)
    if time.monotonic() > deadline:
        raise core.StudioError("Tiempo de segmentación CPU excedido.", 409)


def _run(args, root, work, cancel, deadline, tag):
    out, log = work / (tag + ".out"), work / (tag + ".log")
    with out.open("wb") as stdout, log.open("wb") as stderr:
        process = _spawn(args, root, stdout, stderr)
        try:
            while process.poll() is None:
                _check(cancel, deadline)
                time.sleep(.05)
            if process.returncode:
                raise core.StudioError("Segmentación CPU: " + log.read_bytes()[-1600:].decode("utf-8", "replace"))
        finally:
            _stop(process)
    _check(cancel, deadline)
    return out.read_bytes(), log.read_bytes()


def _alpha(confidence, dimensions, options, previous=None):
    width, height = dimensions
    values = array.array("f")
    try:
        values.frombytes(confidence)
    except (TypeError, ValueError) as error:
        raise core.StudioError("La máscara requiere bytes Float32 completos.") from error
    if os.sys.byteorder != "little":
        values.byteswap()
    if type(width) is not int or type(height) is not int or len(values) != width * height or not 1 <= width <= 256 or not 1 <= height <= 256:
        raise core.StudioError("Dimensiones de máscara incompatibles.")
    if any(not math.isfinite(v) or not -.00001 <= v <= 1.00001 for v in values):
        raise core.StudioError("La máscara contiene confidencias no finitas o fuera de rango.")
    # Confidence transfer, not a calibrated physical alpha estimate.
    threshold, softness = options["threshold"], options["softness"]
    pixels = bytearray()
    for value in values:
        u = min(1, max(0, (value - threshold + softness / 2) / softness))
        pixels.append(round(255 * u * u * (3 - 2 * u)))
    mask = Image.frombytes("L", dimensions, bytes(pixels))
    if previous is not None and options["temporal_smoothing"]:
        mask = Image.blend(mask, previous, options["temporal_smoothing"])
    return mask


def _checkerboard(image):
    background = Image.new("RGBA", image.size, (220, 220, 220, 255))
    draw = ImageDraw.Draw(background)
    for y in range(0, image.height, 20):
        for x in range(0, image.width, 20):
            if (x // 20 + y // 20) % 2:
                draw.rectangle((x, y, x + 19, y + 19), fill=(165, 165, 165, 255))
    return Image.alpha_composite(background, image).convert("RGB")


def _write_pipe(process, data, cancel, deadline):
    fd = process.stdin.fileno()
    os.set_blocking(fd, False)
    remaining = memoryview(data)
    while remaining:
        _check(cancel, deadline)
        if process.poll() is not None:
            raise core.StudioError("El encoder terminó antes de recibir todos los fotogramas.")
        if select.select([], [fd], [], .1)[1]:
            try:
                length = os.write(fd, remaining[:65536])
            except BlockingIOError:
                continue
            remaining = remaining[length:]


def _infer(raw, size, count, options, encoder, runtime, root, work, cancel, deadline, progress, guard):
    state = {"next": 0, "received": 0, "pending": None, "png": None, "previous": None,
             "image": None, "error": None, "evidence": [], "measurements": [], "done": threading.Event()}
    lock = threading.RLock()
    selected = {0, min(1, count - 1), count // 2, min(count // 2 + 1, count - 1), max(0, count - 2), count - 1}
    token = hashlib.sha256(os.urandom(32)).hexdigest()
    prefix = "/" + token + "/"
    runtime_directory = _path(root, RUNTIME)
    allowed = {prefix: (PAGE.encode(), "text/html"), prefix + "model.tflite": (_path(root, MODEL, True), "application/octet-stream")}
    for name in runtime["runtime_files"]:
        mime = "application/wasm" if name.endswith(".wasm") else "text/javascript" if name.endswith((".js", ".mjs")) else "application/json"
        allowed[prefix + "runtime/" + name] = (_path(root, runtime_directory / name, True), mime)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, data, mime="application/json", code=200):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def fail(self, error):
            state["error"] = str(error)
            state["done"].set()
            self.send(json.dumps({"error": str(error)}).encode(), code=409)

        def do_GET(self):
            if self.headers.get("Host") != authority:
                self.send_error(403)
                return
            try:
                with lock:
                    _check(cancel, deadline)
                    if self.path == prefix + "next.json":
                        if state["pending"] is not None:
                            raise core.StudioError("El navegador pidió otro frame antes de entregar su máscara.")
                        index = state["next"]
                        if index >= count:
                            self.send(b'{"done":true}')
                            return
                        guard(index)
                        data = raw.read(size[0] * size[1] * 4)
                        if len(data) != size[0] * size[1] * 4:
                            raise core.StudioError("Fotograma decodificado incompleto.")
                        image = Image.frombytes("RGBA", size, data)
                        thumbnail = image.convert("RGB")
                        thumbnail.thumbnail((256, 256), Image.Resampling.LANCZOS)
                        buffer = io.BytesIO()
                        thumbnail.save(buffer, "PNG")
                        state.update(image=image, png=buffer.getvalue(), pending=index, mask_dimensions=thumbnail.size)
                        self.send(json.dumps({"index": index, "timestamp_ms": index * 1000 / options["fps"]}).encode())
                    elif self.path == prefix + "frame.png?index=" + str(state["pending"]):
                        if state["png"] is None:
                            raise core.StudioError("Fotograma pendiente inexistente.")
                        self.send(state["png"], "image/png")
                    elif self.path in allowed:
                        data, mime = allowed[self.path]
                        self.send(data.read_bytes() if isinstance(data, Path) else data, mime)
                    else:
                        self.send_error(404)
            except Exception as error:
                self.fail(error)

        def do_POST(self):
            if self.headers.get("Host") != authority or self.headers.get("Origin") != address or state["done"].is_set():
                self.send_error(403)
                return
            try:
                with lock:
                    _check(cancel, deadline)
                    length = int(self.headers.get("Content-Length", "0"))
                    if self.path == prefix + "mask":
                        index = int(self.headers.get("X-Frame-Index", "-1"))
                        dimensions = (int(self.headers.get("X-Mask-Width", "0")), int(self.headers.get("X-Mask-Height", "0")))
                        if index != state["pending"] or index != state["received"] or dimensions != state["mask_dimensions"] or length != dimensions[0] * dimensions[1] * 4 or not 0 < length <= 256 * 256 * 4:
                            raise core.StudioError("La máscara no corresponde al fotograma esperado.")
                        body = self.rfile.read(length)
                        mask = _alpha(body, dimensions, options, state["previous"])
                        state["previous"] = mask
                        full = mask.resize(size, Image.Resampling.BILINEAR)
                        if options["feather"]:
                            full = full.filter(ImageFilter.GaussianBlur(options["feather"]))
                        image = state["image"]
                        original_alpha = image.getchannel("A")
                        output = image.copy()
                        output.putalpha(ImageChops.multiply(original_alpha, full))
                        _write_pipe(encoder, output.tobytes(), cancel, deadline)
                        low, high = output.getchannel("A").getextrema()
                        state["measurements"].append({"index": index, "output_time": index / options["fps"], "alpha_min": low, "alpha_max": high})
                        if index in selected:
                            for role, picture in (("source", image), ("alpha", output.getchannel("A")), ("checkerboard", _checkerboard(output)), ("rgba", output)):
                                target = work / f"sample_{index:04d}_{role}.png"
                                picture.save(target, "PNG")
                                state["evidence"].append({"local": target, "role": role, "index": index, "output_time": index / options["fps"]})
                        state.update(next=index + 1, received=index + 1, pending=None, image=None, png=None)
                        if progress:
                            progress(.15 + .65 * (index + 1) / count, f"Segmentación CPU: {index + 1}/{count} fotogramas.")
                        self.send(b"{}")
                    elif self.path in {prefix + "complete", prefix + "error"}:
                        if not 0 < length <= 16384:
                            raise core.StudioError("Respuesta de navegador excesiva.")
                        result = json.loads(self.rfile.read(length))
                        if self.path.endswith("error"):
                            raise core.StudioError(str(result.get("error", "Error MediaPipe")))
                        if result != {"count": count, "labels": ["selfie"], "confidence_mask_channels": 1, "delegate": "CPU"} or state["received"] != count:
                            raise core.StudioError("Ejecución de segmentación incompleta o modelo incompatible.")
                        state["browser_result"] = result
                        self.send(b"{}")
                        state["done"].set()
                    else:
                        self.send_error(404)
            except Exception as error:
                self.fail(error)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    address = "http://127.0.0.1:" + str(server.server_port)
    authority = "127.0.0.1:" + str(server.server_port)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    browser = next(value["path"] for key, value in runtime["binaries"].items() if key in {"google-chrome", "chromium"})
    env = _environment(root)
    directory_fd = os.open(env["TMPDIR"], os.O_RDONLY | os.O_DIRECTORY)
    env["TMPDIR"] = f"/proc/{os.getpid()}/fd/{directory_fd}"
    args = [browser, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-gpu-compositing", "--disable-vulkan",
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--renderer-process-limit=1",
            "--num-raster-threads=1", "--disable-background-networking", "--disable-component-update", "--disable-sync",
            "--no-first-run", "--disable-default-apps", "--disable-extensions", "--disable-breakpad", "--disable-dev-shm-usage",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1", "--user-data-dir=" + str(work / "chrome_profile"), address + prefix]
    try:
        with (work / "browser.out").open("wb") as out, (work / "browser.log").open("wb") as log:
            process = _spawn(args, root, out, log, env=env)
            try:
                while not state["done"].wait(.05):
                    _check(cancel, deadline)
                    if process.poll() is not None:
                        raise core.StudioError("El navegador terminó sin máscaras: " + (work / "browser.log").read_bytes()[-1600:].decode("utf-8", "replace"))
                if state["error"]:
                    raise core.StudioError("Segmentación MediaPipe CPU: " + state["error"])
                _check(cancel, deadline)
                return {"evidence": state["evidence"], "measurements": state["measurements"], "browser": state["browser_result"]}
            finally:
                _stop(process)
    finally:
        os.close(directory_fd)
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


def _validate_cache(result, root, runtime):
    verification = result.get("verification") if isinstance(result, dict) else None
    if (not isinstance(result, dict) or result.get("operation") != OPERATION or result.get("runtime") != runtime
            or not isinstance(verification, dict) or verification.get("decode_ok") is not True
            or verification.get("alpha_encoded_pixels_verified") is not True
            or any(verification.get(key) is not False for key in ("visual", "audio", "approved"))):
        raise core.StudioError("La evidencia de segmentación no corresponde al motor actual.", 409)
    if (not isinstance(result.get("path"), str) or not re.fullmatch(r"\.estado/tools/[a-f0-9]{24}\.mov", result["path"])
            or type(result.get("frame_count")) is not int or not 1 <= result["frame_count"] <= MAX_FRAMES):
        raise core.StudioError("Ruta o conteo del recibo de segmentación inválido.", 409)
    provenance = result.get("provenance")
    if not isinstance(provenance, dict):
        raise core.StudioError("El recibo requiere procedencia de segmentación.", 409)
    parameters = validate_options(provenance.get("parameters"))
    identity = {"source_sha256": provenance.get("source_sha256"), "parameters": parameters, "runtime": runtime}
    expected_key = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
    if result.get("identity") != identity or result["path"] != f".estado/tools/{expected_key}.mov":
        raise core.StudioError("El recibo no corresponde a la identidad de sus bytes/opciones.", 409)
    fps = core.finite_number(result.get("fps"), "FPS del recibo", 10, 30)
    if int(fps) != fps or fps != parameters["fps"]:
        raise core.StudioError("El recibo cambió los FPS procesados.", 409)
    for key in ("width", "height"):
        dimension = core.finite_number(result.get(key), "dimensión del recibo", 2, parameters["max_" + key])
        if int(dimension) != dimension or dimension % 2:
            raise core.StudioError("Dimensiones del recibo no enteras/pares.", 409)
    actual_duration = core.finite_number(result.get("duration"), "duración del recibo", .01, 30.02)
    encoded_duration = result["frame_count"] / fps
    span = provenance.get("source_span")
    if not isinstance(span, dict):
        raise core.StudioError("Falta el tramo original del recibo.", 409)
    requested = core.finite_number(span.get("duration"), "duración original del recibo", .01, 30)
    if (span.get("start") != parameters["start"] or math.ceil(requested * fps - 1e-9) != result["frame_count"]
            or provenance.get("requested_duration") != requested or provenance.get("encoded_duration") != encoded_duration
            or abs(actual_duration - encoded_duration) > .02):
        raise core.StudioError("Tramos/frames/duración del recibo no son coherentes.", 409)
    pts = provenance.get("cfr_pts")
    if not isinstance(pts, list) or len(pts) != result["frame_count"]:
        raise core.StudioError("Faltan timestamps CFR comprobados.", 409)
    for index, when in enumerate(pts):
        core.finite_number(when, "timestamp CFR del recibo", 0, 30)
        if abs(when - index / fps) > 1e-5:
            raise core.StudioError("Timestamp CFR alterado.", 409)
    probe = result.get("probe")
    if not isinstance(probe, dict) or not isinstance(probe.get("streams"), list):
        raise core.StudioError("El recibo no tiene inspección de medios.", 409)
    video = next((s for s in probe["streams"] if isinstance(s, dict) and s.get("codec_type") == "video"), {})
    if (video.get("codec_name") != "qtrle" or video.get("pix_fmt") != "argb"
            or any(video.get(key) != result[key] for key in ("width", "height"))):
        raise core.StudioError("El probe no confirma el MOV alfa y sus dimensiones.", 409)
    try:
        probe_duration = float(probe["format"]["duration"])
    except (KeyError, TypeError, ValueError) as error:
        raise core.StudioError("La duración medida del MOV no está disponible.", 409) from error
    if not math.isfinite(probe_duration) or abs(probe_duration - actual_duration) > 1e-6:
        raise core.StudioError("La duración del recibo difiere del probe.", 409)
    source = _path(root, result["provenance"]["source_path"], True)
    output = _path(root, result["path"], True)
    raw_output = root / result["path"]
    binding_id, binding_path = result.get("canonical_asset_id"), result.get("canonical_path")
    if raw_output.absolute() != output or raw_output.is_symlink() or binding_id is not None or binding_path is not None:
        if not isinstance(binding_id, str) or not isinstance(binding_path, str) or Path(binding_path).is_absolute():
            raise core.StudioError("El alias no tiene binding canónico válido.", 409)
        target = _destination(root, binding_path)
        registered = next((a for a in core.assets() if a.get("id") == binding_id), None)
        if (registered is None or registered.get("path") != binding_path or registered.get("sha256") != result["sha256"]
                or registered.get("kind") not in {"video", "broll"} or target != output or not raw_output.is_symlink()
                or not any(s.get("codec_type") == "video" and s.get("codec_name") == "qtrle"
                           for s in registered.get("probe", {}).get("streams", []))):
            raise core.StudioError("El enlace no corresponde al recurso canónico registrado.", 409)
    if _hash(source) != result["provenance"]["source_sha256"] or _hash(output) != result["sha256"]:
        raise core.StudioError("La fuente o el derivado de segmentación cambió.", 409)
    evidence_rows = result.get("evidence")
    if not isinstance(evidence_rows, list) or not 5 <= len(evidence_rows) <= 30:
        raise core.StudioError("El recibo no contiene las muestras visuales acotadas.", 409)
    selected = {0, min(1, result["frame_count"] - 1), result["frame_count"] // 2,
                min(result["frame_count"] // 2 + 1, result["frame_count"] - 1), max(0, result["frame_count"] - 2), result["frame_count"] - 1}
    required = {(index, role) for index in selected for role in ("source", "alpha", "checkerboard", "rgba", "encoded_rgba")}
    observed = set()
    for evidence in evidence_rows:
        if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str) or not re.fullmatch(
                r"\.estado/segmentation/evidence/[a-f0-9]{24}/(?:sample_[0-9]{4}_(?:source|alpha|checkerboard|rgba)|encoded_[0-9]{4})\.png", evidence["path"]):
            raise core.StudioError("Ruta de evidencia de segmentación inválida.", 409)
        index, role = evidence.get("index"), evidence.get("role")
        if type(index) is not int or (index, role) not in required or (index, role) in observed:
            raise core.StudioError("Cobertura/roles de evidencia incompletos o repetidos.", 409)
        expected_name = f"encoded_{index:04d}.png" if role == "encoded_rgba" else f"sample_{index:04d}_{role}.png"
        expected_path = f".estado/segmentation/evidence/{expected_key}/{expected_name}"
        when = core.finite_number(evidence.get("output_time"), "tiempo de evidencia", 0, 30)
        if evidence["path"] != expected_path or abs(when - index / fps) > 1e-6:
            raise core.StudioError("La evidencia no corresponde al frame/tramo de esta ejecución.", 409)
        observed.add((index, role))
        if _hash(_destination(root, evidence["path"])) != evidence["sha256"]:
            raise core.StudioError("La evidencia de segmentación cambió.", 409)
    if observed != required:
        raise core.StudioError("Faltan estados consecutivos/original/alfa/RGBA codificado en la evidencia.", 409)
    measurements = result.get("frame_measurements")
    if not isinstance(measurements, list) or len(measurements) != result["frame_count"]:
        raise core.StudioError("El recibo requiere medidas de alfa por fotograma.", 409)
    for index, row in enumerate(measurements):
        if not isinstance(row, dict) or type(row.get("index")) is not int or row["index"] != index:
            raise core.StudioError("Índice de medida alfa alterado.", 409)
        when = core.finite_number(row.get("output_time"), "tiempo medida alfa", 0, 30)
        low = core.finite_number(row.get("alpha_min"), "mínimo alfa", 0, 255)
        high = core.finite_number(row.get("alpha_max"), "máximo alfa", 0, 255)
        if abs(when - index / fps) > 1e-6 or int(low) != low or int(high) != high or high < low:
            raise core.StudioError("Medida alfa no corresponde al fotograma.", 409)
    browser = result.get("browser")
    if (not isinstance(browser, dict) or type(browser.get("count")) is not int
            or type(browser.get("confidence_mask_channels")) is not int
            or browser != {"count": result.get("frame_count"), "labels": ["selfie"], "confidence_mask_channels": 1, "delegate": "CPU"}):
        raise core.StudioError("La evidencia no contiene ejecución del modelo verificada.", 409)


def _verify_cache(result, root, runtime):
    try:
        return _validate_cache(result, root, runtime)
    except core.StudioError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as error:
        raise core.StudioError("El recibo de segmentación tiene estructura o archivos inválidos.", 409) from error


def semantic_receipt_digest(receipt):
    """Binding only links identical bytes; all other proof fields stay sealed."""
    if not isinstance(receipt, dict):
        raise core.StudioError("El recibo semántico requiere un objeto.")
    selected = {key: value for key, value in receipt.items() if key not in {"canonical_asset_id", "canonical_path"}}
    return hashlib.sha256(json.dumps(selected, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def process(asset, options=None, root=None, progress=None, cancel=None):
    """Create/cache a new derivative; never replace or apply the original."""
    options = validate_options(options)
    root = _path(root or core.ROOT, ".")
    if not isinstance(asset, dict) or not isinstance(asset.get("path"), str):
        raise core.StudioError("Segmentación requiere un recurso local con path.")
    source = _path(root, asset["path"], True)
    if source.suffix.lower() not in media.INPUT_EXTENSIONS:
        raise core.StudioError("La segmentación requiere video local en formato admitido.")
    from .jobs import cpu_slot
    _check(cancel, time.monotonic() + 900)
    with cpu_slot(cancel=cancel):
        with media._lock(root):
            return _process(asset, source, options, root, progress, cancel)


def _process(asset, source, options, root, progress, cancel):
    began = time.monotonic()
    deadline = began + 900
    _check(cancel, deadline)
    runtime = _runtime(root)
    source_sha, signature = _hash(source), _signature(source)
    if asset.get("sha256") and asset["sha256"] != source_sha:
        raise core.StudioError("El recurso cambió respecto al catálogo.", 409)
    identity = {"source_sha256": source_sha, "parameters": options, "runtime": runtime}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()[:24]
    output_raw = root / f".estado/tools/{key}.mov"
    receipt = _destination(root, f".estado/tools/{key}.json")
    if output_raw.exists():
        if not receipt.is_file():
            raise core.StudioError("El derivado existente carece de recibo; no se sobrescribe.", 409)
        try:
            result = json.loads(receipt.read_text())
            _verify_cache(result, root, runtime)
            if result.get("identity") != identity or result.get("path") != str(output_raw.relative_to(root)):
                raise core.StudioError("El derivado almacenado pertenece a otra solicitud; no se reutiliza.", 409)
        except (ValueError, KeyError, TypeError, OSError) as error:
            raise core.StudioError("El recibo existente no es válido; no se sobrescribe.", 409) from error
        _check(cancel, deadline)
        if _signature(source) != signature or _hash(source) != source_sha or _runtime(root) != runtime:
            raise core.StudioError("La fuente/runtime cambió durante la consulta; no se reutiliza el derivado.", 409)
        return {**result, "reused": True}
    output = _destination(root, output_raw)
    if receipt.exists():
        raise core.StudioError("Existe un recibo sin su derivado; no se reemplaza.", 409)
    temp_base = _destination(root, ".estado/tmp")
    temp_base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="segmentation_", dir=temp_base) as folder:
        work = Path(folder)
        tool = runtime["binaries"]["ffmpeg"]["path"]
        stdout, _ = _run([runtime["binaries"]["ffprobe"]["path"], "-v", "error", "-protocol_whitelist", "file,pipe",
                         "-format_whitelist", media.FORMATS, "-show_streams", "-show_format", "-of", "json", str(source)], root, work, cancel, deadline, "input_probe")
        try:
            info = json.loads(stdout)
            video = next(s for s in info["streams"] if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic"))
        except (ValueError, TypeError, KeyError, StopIteration) as error:
            raise core.StudioError("La segmentación requiere una pista de video real.") from error
        if video.get("color_transfer") in {"smpte2084", "arib-std-b67"}:
            raise core.StudioError("Segmentación SDR: HDR requiere una conversión de color explícita previa.")
        start, duration = media._span(info, options, 30)
        count = math.ceil(duration * options["fps"] - 1e-9)
        if not 1 <= count <= MAX_FRAMES:
            raise core.StudioError("La segmentación CPU admite hasta 900 fotogramas.")
        deadline = began + min(900, max(120, count * 2))
        scale = f"scale=w='min({options['max_width']},iw)':h='min({options['max_height']},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1"
        first = work / "first.png"
        _run([tool, *media._base(), *media._input(source, start, duration), "-map", f"0:{video['index']}", "-frames:v", "1",
              "-vf", scale + ",setsar=1", "-threads", "2", "-y", str(first)], root, work, cancel, deadline, "geometry")
        with Image.open(first) as image:
            size = image.size
        raw_bytes = count * size[0] * size[1] * 4
        if raw_bytes > MAX_RGBA_BYTES:
            raise core.StudioError("El tramo supera el límite de 2 GiB RGBA; reduce duración, FPS o dimensiones.")
        has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
        # With audio, immutable visual.mov and the complete muxed MOV coexist.
        required_disk = raw_bytes * (3 if has_audio else 2) + 256 * 1024 ** 2
        if shutil.disk_usage(temp_base).free < required_disk:
            raise core.StudioError("No hay espacio para el tramo RGBA, MOV y reserva local.")
        encoded_duration = count / options["fps"]
        raw_file = work / "decoded.rgba"
        filter = scale + f",setsar=1,tpad=stop_mode=clone:stop_duration={1/options['fps']:.10f},fps={options['fps']},trim=end_frame={count},showinfo"
        _, diagnostic = _run([tool, *media._base("info"), *media._input(source, start, duration), "-map", f"0:{video['index']}", "-an",
                              "-vf", filter, "-pix_fmt", "rgba", "-threads", "2", "-f", "rawvideo", "-y", str(raw_file)], root, work, cancel, deadline, "decode")
        if raw_file.stat().st_size != raw_bytes:
            raise core.StudioError("La decodificación no produjo todos los frames CFR previstos.")
        pts = [float(value) for value in re.findall(rb"\bn:\s*\d+\s+pts:\s*[-\d]+\s+pts_time:([-+\d.eE]+)", diagnostic)]
        if len(pts) != count or any(not math.isfinite(t) or abs(t - i/options["fps"]) > 1e-5 for i, t in enumerate(pts)):
            raise core.StudioError("FFmpeg no confirmó los timestamps CFR; no se inventa alineación.")
        if progress:
            progress(.15, "Fotogramas CFR decodificados; iniciando máscara de persona CPU.")
        watched = {source: signature, Path(__file__): _signature(__file__), Path(media.__file__): _signature(media.__file__),
                   _path(root, MODEL): _signature(_path(root, MODEL))}
        for name in runtime["runtime_files"]:
            path = _path(root, Path(RUNTIME) / name)
            watched[path] = _signature(path)
        for binary in runtime["binaries"].values():
            watched[Path(binary["resolved"])] = tuple(binary["signature"])
            if binary.get("payload"):
                watched[Path(binary["payload"]["resolved"])] = tuple(binary["payload"]["signature"])

        def guard(index):
            _check(cancel, deadline)
            if any(_signature(path) != before for path, before in watched.items()):
                raise core.StudioError("La fuente, código, modelo o runtime cambió durante la segmentación.", 409)
            if index % 30 == 0 and _runtime(root) != runtime:
                raise core.StudioError("Los bytes del runtime cambiaron durante la segmentación.", 409)

        candidate = work / "candidate.mov"
        encoder_args = [tool, *media._base(), "-threads", "2", "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{size[0]}x{size[1]}",
                        "-framerate", str(options["fps"]), "-i", "pipe:0", "-an", "-c:v", "qtrle", "-pix_fmt", "argb", "-threads", "2", "-y", str(candidate)]
        with (work / "encoder.log").open("wb") as log:
            encoder = _spawn(encoder_args, root, subprocess.DEVNULL, log, stdin=subprocess.PIPE)
            try:
                with raw_file.open("rb") as raw:
                    inference = _infer(raw, size, count, options, encoder, runtime, root, work, cancel, deadline, progress, guard)
                encoder.stdin.close()
                while encoder.poll() is None:
                    _check(cancel, deadline)
                    time.sleep(.05)
                if encoder.returncode:
                    raise core.StudioError("Encoder alpha: " + (work / "encoder.log").read_bytes()[-1500:].decode("utf-8", "replace"))
            finally:
                _stop(encoder)
        if has_audio:
            merged = work / "mixed.mov"
            _run([tool, *media._base(), *media._input(candidate, 0, encoded_duration), *media._input(source, start, duration),
                  "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "pcm_s16le", "-ar", "48000",
                  "-af", "asetpts=PTS-STARTPTS", "-map_metadata", "-1", "-threads", "2", "-y", str(merged)], root, work, cancel, deadline, "audio")
            candidate = merged
        stdout, _ = _run([runtime["binaries"]["ffprobe"]["path"], "-v", "error", "-show_streams", "-show_format", "-of", "json", str(candidate)], root, work, cancel, deadline, "output_probe")
        measured = json.loads(stdout)
        v = next(s for s in measured["streams"] if s.get("codec_type") == "video")
        if v.get("codec_name") != "qtrle" or v.get("pix_fmt") != "argb" or (v["width"], v["height"]) != size:
            raise core.StudioError("El MOV no conserva QTRLE, alfa y dimensiones verificables.")
        if has_audio and not any(s.get("codec_type") == "audio" and s.get("codec_name") == "pcm_s16le" for s in measured["streams"]):
            raise core.StudioError("El derivado perdió el audio original.")
        actual_duration = float(measured["format"]["duration"])
        if not math.isfinite(actual_duration) or abs(actual_duration - encoded_duration) > 1/options["fps"] + .02 or candidate.stat().st_size > MAX_RGBA_BYTES:
            raise core.StudioError("La duración o tamaño de salida no conserva el tramo acotado.")
        decoded, _ = _run([tool, *media._base(), "-xerror", "-threads", "2", "-i", str(candidate), "-threads", "2", "-progress", "pipe:1", "-f", "null", "-"], root, work, cancel, deadline, "full_decode")
        counts = re.findall(rb"(?m)^frame=(\d+)$", decoded)
        if not counts or int(counts[-1]) != count:
            raise core.StudioError("El MOV no decodifica todos los fotogramas esperados.")
        # QTRLE is lossless: inspect actual encoded selected frames, not only masks.
        for row in [item for item in inference["evidence"] if item["role"] == "rgba"]:
            encoded = work / f"encoded_{row['index']:04d}.png"
            _run([tool, *media._base(), "-threads", "2", "-ss", str(row["output_time"]), "-i", str(candidate), "-frames:v", "1",
                  "-pix_fmt", "rgba", "-threads", "2", "-y", str(encoded)], root, work, cancel, deadline, "alpha_" + str(row["index"]))
            with Image.open(encoded) as picture, Image.open(row["local"]) as expected:
                if picture.convert("RGBA").tobytes() != expected.convert("RGBA").tobytes():
                    raise core.StudioError("Los píxeles RGBA codificados difieren de la máscara aplicada.")
            inference["evidence"].append({"local": encoded, "role": "encoded_rgba", "index": row["index"], "output_time": row["output_time"]})
        guard(count)
        if _runtime(root) != runtime or _hash(source) != source_sha:
            raise core.StudioError("La fuente/modelo/código cambió; no se promueve el derivado.", 409)
        evidence_dir = _destination(root, f".estado/segmentation/evidence/{key}")
        if evidence_dir.exists():
            raise core.StudioError("El destino de evidencia ya existe; no se sobrescribe.", 409)
        evidence = [{"path": str((evidence_dir / item["local"].name).relative_to(root)), "sha256": _hash(item["local"]),
                     **{k: item[k] for k in ("role", "index", "output_time")}} for item in inference["evidence"]]
        source_relative = str(source.relative_to(root))
        result = {"operation": OPERATION, "kind": "process", "identity": identity, "path": str(output.relative_to(root)), "probe": measured,
                  "sha256": _hash(candidate), "md5": media._hash(candidate, "md5"), "size": candidate.stat().st_size,
                  "duration": actual_duration, "width": size[0], "height": size[1], "fps": options["fps"], "frame_count": count,
                  "runtime": runtime, "browser": inference["browser"], "evidence": evidence,
                  "frame_measurements": inference["measurements"], "reused": False, "elapsed_seconds": round(time.monotonic() - began, 3),
                  "verification": {"decode_ok": True, "alpha_encoded_pixels_verified": True, "visual": False, "audio": False, "approved": False},
                  "provenance": {"operation": OPERATION, "source_asset_id": asset.get("id"), "source_path": source_relative,
                  "source_sha256": source_sha, "source_span": {"start": start, "duration": duration}, "parameters": options,
                  "gpu_used": False, "delegate": "CPU", "max_ffmpeg_threads": 2, "workers": 1, "niceness": 10,
                  "processor_sha256": runtime["pixel_code_sha256"]["segmentation.py"], "model_sha256": MODEL_SHA256,
                  "rotation": "FFmpeg metadata autorotation applied, pixels then encoded with no rotation tag",
                  "sample_aspect_ratio": "converted to square pixels by FFmpeg scale reset_sar=1",
                  "timing": "explicit CFR resampling; measured output pts, source request times are not measured original frame PTS",
                  "cfr_pts": pts, "requested_duration": duration, "encoded_duration": encoded_duration,
                  "changes_narration_timing": False, "audio_preserved": has_audio, "audio_policy": "first original audio track decoded to PCM48k, no denoise/normalization",
                  "estimated_rgba_bytes": raw_bytes, "buffering": "bounded raw disk <=2GiB, one frame and <=256² confidence mask in RAM",
                  "temporal_smoothing": "opt-in; may leave motion trails" if options["temporal_smoothing"] else "disabled",
                  "at": core.now(), "qc": "pending", "visual_reviewed": False, "audio_listened": False, "approved_for_ascendia": False,
                  "limitations": ["Confidence segmentation, not physical alpha/hair matting; borders need moving review.",
                                  "Foreground may contain several people; no identity selection or invisible-face budget claim.",
                                  "No automatic use/replacement of the original background in ASCENDIA presenter scenes."]}}
        staged_receipt = work / "receipt.json"
        staged_receipt.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        if progress:
            progress(.98, "Decode y alfa comprobados; verificando huellas antes de guardar.")
        output.parent.mkdir(parents=True, exist_ok=True)
        evidence_dir.mkdir(parents=True)
        created = []
        try:
            for item in inference["evidence"]:
                target = evidence_dir / item["local"].name
                os.link(item["local"], target)
                created.append(target)
            _check(cancel, deadline)
            os.link(candidate, output)
            created.append(output)
            os.link(staged_receipt, receipt)
            created.append(receipt)
            guard(count)
            if _runtime(root) != runtime or _hash(source) != source_sha:
                raise core.StudioError("La fuente o motor cambió durante la publicación; se descarta el derivado.", 409)
        except Exception:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            evidence_dir.rmdir()
            raise
        marker = _destination(root, ".estado/segmentation/integration.json")
        core.atomic_json(marker, {"receipt_path": str(receipt.relative_to(root)), "semantic_receipt_sha256": semantic_receipt_digest(result)})
        if progress:
            progress(1, "MOV con transparencia listo; revisión de bordes y movimiento pendiente.")
        return result


LOADED_CODE_SHA256 = _hash(__file__)
