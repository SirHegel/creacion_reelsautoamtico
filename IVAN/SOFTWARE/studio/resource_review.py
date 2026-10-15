"""Private resource observation with actual samples and explicit scoped claims.

Decoding is preparation, never semantic approval. A record is the operator's
bounded observation, not a license, proof of inference, or approval of a reel.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

from PIL import Image, ImageDraw, ImageOps

from . import analysis, core

OPTIONS = {"start", "duration", "samples", "max_width", "max_height", "sequence"}
REVIEW_FIELDS = {"expected_source_sha256", "expected_review_digest", "receipt_sha256", "reviewer", "notes", "content",
                "interval", "scope", "evidence", "visual_reviewed", "rights_declaration", "sequence_viewed"}
REQUIRED_REVIEW = REVIEW_FIELDS - {"sequence_viewed"}
SHA = re.compile(r"[a-f0-9]{64}")
ASSET_ID = re.compile(r"a_[A-Za-z0-9_-]{1,100}")
FILE_NAME = re.compile(r"frame_[0-9]{2}\.png|contact_sheet\.png|sequence\.mp4|receipt\.json|review\.json")
MAX_FILE = 32 * 1024 * 1024
MAX_PIXELS = 40_000_000


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _text(value, label, lo=1, hi=8000):
    if (not isinstance(value, str) or len(value) > hi or not lo <= len(value.strip()) <= hi or
            any(ord(c) < 32 and c not in "\n\t" for c in value)):
        raise core.StudioError("Observación inválida: " + label)
    return value.strip()


def _hash(value, label):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise core.StudioError("SHA completo requerido: " + label)
    return value


def _directory(asset_id, *, create=False):
    if not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id):
        raise core.StudioError("ID de recurso inválido.")
    if not core.WORKSPACE_MODE:
        raise core.StudioError("La revisión de recursos requiere un workspace privado.", 409)
    root = Path(core.ROOT).resolve()
    from .providers import CODE_ROOT
    private = root / ".estado"
    if root == CODE_ROOT.resolve() or not root.is_relative_to(CODE_ROOT.resolve()) or private.resolve() != private or not private.is_dir():
        raise core.StudioError("El espacio privado del recurso dejó de ser canónico.", 403)
    directory = root / ".estado/resource_reviews" / asset_id
    if directory.resolve() != directory:
        raise core.StudioError("La evidencia privada no admite enlaces ni rutas alternativas.", 403)
    if create:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def _path(directory, name, *, exists=False):
    if not isinstance(name, str) or not FILE_NAME.fullmatch(name):
        raise core.StudioError("Nombre de evidencia inválido.", 403)
    path = directory / name
    if path.resolve() != path or not path.resolve().is_relative_to(Path(core.ROOT).resolve()):
        raise core.StudioError("La evidencia no admite enlaces ni escapes.", 403)
    if exists and (not path.is_file() or not 1 <= path.stat().st_size <= MAX_FILE):
        raise core.StudioError("Falta evidencia o excede su tamaño máximo.", 409)
    return path


def _source(asset_id):
    _directory(asset_id)
    item = core.asset(asset_id)
    if not isinstance(item.get("kind"), str) or item["kind"] not in {"image", "video", "broll"}:
        raise core.StudioError("Selecciona una imagen o video visual de tu biblioteca.")
    declared = item.get("path")
    if not isinstance(declared, str):
        raise core.StudioError("Ruta de recurso inválida.", 403)
    root = Path(core.ROOT).resolve()
    path = root / declared
    relative = path.relative_to(root).parts if path.is_relative_to(root) else ()
    if (path.resolve() != path or len(relative) < 3 or relative[0] != "assets" or
            relative[1] not in {"images", "video", "broll"}):
        raise core.StudioError("El recurso debe pertenecer a la biblioteca propia canónica.", 403)
    path = core.confined(path, must_exist=True)
    expected = _hash(item.get("sha256"), "source")
    if core.content_hash(path) != expected:
        raise core.StudioError("El recurso original cambió; vuelve a comprobar su contenido.", 409)
    metadata = item.get("metadata", {})
    if not isinstance(metadata, dict) or not isinstance(item.get("probe", {}), dict):
        raise core.StudioError("Metadata canónica inválida.")
    identity = {k: copy.deepcopy(item.get(k)) for k in ("id", "path", "sha256", "size", "kind", "duration", "probe")}
    identity["provenance"] = {k: copy.deepcopy(metadata.get(k)) for k in ("source", "provenance", "declaration_original")}
    return item, path, identity


def _review_digest(item):
    return _digest(item.get("metadata", {}).get("resource_review"))


def validate_options(item, options=None):
    options = {} if options is None else options
    if not isinstance(options, dict) or set(options) - OPTIONS:
        raise core.StudioError("Opciones de muestras desconocidas.")
    width = options.get("max_width", 512)
    height = options.get("max_height", 960)
    count = options.get("samples", 6)
    for value, name, lo, hi in ((width, "max_width", 160, 1080), (height, "max_height", 160, 1920), (count, "samples", 1, 12)):
        if type(value) is not int or not lo <= value <= hi:
            raise core.StudioError("Valor inválido para " + name)
    sequence = options.get("sequence", False)
    if type(sequence) is not bool:
        raise core.StudioError("sequence requiere un booleano.")
    start = core.finite_number(options.get("start", 0), "inicio de revisión", 0, 86400)
    requested = options.get("duration")
    if requested is not None:
        core.finite_number(requested, "duración de revisión", .01, 30)
    if item.get("kind") == "image":
        if start != 0 or requested is not None or sequence:
            raise core.StudioError("Las imágenes se observan como una muestra estática sin tramo ni secuencia.")
        count, duration = 1, 0
    else:
        total = core.finite_number(item.get("duration"), "duración original", .01, 86400)
        duration = total - start if requested is None else requested
        if duration <= 0 or duration > 30 or start + duration > total + 1e-6:
            raise core.StudioError("El tramo debe existir en el video y durar como máximo treinta segundos.")
    return {"start": float(start), "duration": float(duration), "samples": count,
            "max_width": width, "max_height": height, "sequence": sequence}


def _engine():
    return {"code": core.engine_fingerprints(), "manual": core.manual_fingerprints()}


def _check_cancel(cancel):
    if cancel is not None and bool(cancel() if callable(cancel) else cancel.is_set()):
        raise core.StudioError("Cancelado: la revisión del recurso conserva el estado anterior.", 409)


def _run(args, cancel=None):
    if not shutil.which(args[0]):
        raise core.StudioError("FFmpeg no está disponible.", 409)
    command = [shutil.which("nice"), "-n", "10", *args] if shutil.which("nice") else args
    try:
        _check_cancel(cancel)
        process = subprocess.Popen(command, cwd=core.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   env={**os.environ, "TMPDIR": str(core.confined(".estado/tmp")), "CUDA_VISIBLE_DEVICES": ""})
        deadline = time.monotonic() + 120
        try:
            while True:
                _check_cancel(cancel)
                if time.monotonic() > deadline:
                    raise core.StudioError("FFmpeg excedió el tiempo de preparación.", 409)
                try:
                    output, errors = process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired as error:
                    if len(error.stderr or b"") > 2 * 1024 * 1024:
                        raise core.StudioError("FFmpeg excedió el tamaño permitido del diagnóstico.", 413)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=2)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise core.StudioError("No se pudieron preparar muestras CPU.") from error
    if process.returncode:
        raise core.StudioError("FFmpeg no pudo decodificar el recurso: " + errors.decode("utf-8", "replace")[-1200:])
    _check_cancel(cancel)
    return errors.decode("utf-8", "replace")


def _scale(options):
    return ("scale=trunc(iw*sar/2)*2:ih,setsar=1,scale=" + str(options["max_width"]) + ":" + str(options["max_height"]) +
            ":force_original_aspect_ratio=decrease:force_divisible_by=2")


def _frame(path, output, requested, options, probe, cancel=None):
    # copyts lets showinfo report source timestamps rather than a new zero clock.
    logs = _run(["ffmpeg", "-nostdin", "-v", "info", "-ss", str(requested), "-copyts", *analysis.input_media(path),
                 "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", _scale(options) + ",showinfo",
                 "-frames:v", "1", "-threads", "2", "-filter_threads", "1", "-y", str(output)], cancel)
    times = re.findall(r"\bn:\s*0\s+pts:\s*[-0-9]+\s+pts_time:([-+0-9.eE]+)", logs)
    if not times or not output.is_file():
        raise core.StudioError("El decodificador no entregó el fotograma con tiempo comprobable.")
    raw = float(times[0])
    origin = float(probe.get("format", {}).get("start_time", 0) or 0)
    value = raw - origin
    if not math.isfinite(value) or value < -1e-3:
        raise core.StudioError("El fotograma no tiene un tiempo de fuente válido.")
    return max(0., value)


def _file(path):
    if not path.is_file() or not 1 <= path.stat().st_size <= MAX_FILE:
        raise core.StudioError("La evidencia generada falta o supera treinta y dos MiB.", 413)
    return {"path": core.relative(path), "sha256": core.digest(path), "size": path.stat().st_size}


def _sheet(frames, work, options):
    tiles = []
    for frame in frames:
        path = core.confined(frame["path"], must_exist=True)
        with Image.open(path) as src:
            tile = Image.new("RGB", (320, 240), "#20242a")
            picture = src.convert("RGBA")
            picture.thumbnail((304, 204))
            tile.paste(picture, ((320 - picture.width) // 2, 4), picture)
            draw = ImageDraw.Draw(tile)
            draw.text((8, 214), "t=" + format(frame["time"], ".3f") + " s", fill="white")
            tiles.append(tile)
    columns = min(3, len(tiles))
    sheet = Image.new("RGB", (320 * columns, 240 * math.ceil(len(tiles) / columns)), "#20242a")
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % columns) * 320, (i // columns) * 240))
    output = work / "contact_sheet.png"
    sheet.save(output)
    return _file(output)


def _safe_zones():
    return {"kind": "suggested_guides_not_content_detection", "x": [.06, .94], "y": [.10, .80],
            "content_clearance_verified": False, "face_detected": False}


def _load_receipt(asset_id):
    directory = _directory(asset_id)
    path = _path(directory, "receipt.json", exists=True)
    try:
        receipt = json.loads(path.read_text())
    except (ValueError, OSError) as error:
        raise core.StudioError("Recibo de muestras inválido.", 409) from error
    if not isinstance(receipt, dict) or receipt.get("asset_id") != asset_id or receipt.get("schema") != "ascendia.resource-observation/1":
        raise core.StudioError("Recibo de muestras ajeno o inválido.", 409)
    return directory, receipt, core.digest(path)


def _verify_receipt(asset_id, item, identity, *, expected=None):
    directory, receipt, actual = _load_receipt(asset_id)
    if expected is not None and actual != expected:
        raise core.StudioError("Las muestras cambiaron; vuelve a abrir su revisión.", 409)
    if receipt.get("source") != identity or receipt.get("engine") != _engine():
        raise core.StudioError("Cambió el original, su procedencia, el manual o el código de muestras.", 409)
    encoded = copy.deepcopy(receipt.get("options"))
    if item["kind"] == "image" and isinstance(encoded, dict) and encoded.get("duration") == 0:
        encoded["duration"] = None
    normalized = validate_options(item, encoded)
    if (receipt.get("options") != normalized or receipt.get("interval") != {"start": normalized["start"], "end": normalized["start"] + normalized["duration"]} or
            receipt.get("status") != "pending" or receipt.get("visual_reviewed") is not False or
            receipt.get("audio_listened") is not False or receipt.get("rights_authority") is not False or
            receipt.get("semantic_match_confirmed") is not False):
        raise core.StudioError("El recibo de preparación contiene afirmaciones o un alcance inválidos.", 409)
    entries = receipt.get("frames")
    if not isinstance(entries, list) or len(entries) != normalized["samples"]:
        raise core.StudioError("Recibo sin muestras comprobables.", 409)
    for number, entry in enumerate(entries):
        if not isinstance(entry, dict) or Path(str(entry.get("path", ""))).name != "frame_%02d.png" % number:
            raise core.StudioError("Las muestras requieren su nombre y orden canónicos.", 409)
        for key in ("time", "requested_time"):
            core.finite_number(entry.get(key), "tiempo de muestra", max(0, normalized["start"] - .05), normalized["start"] + normalized["duration"] + .05)
    if not isinstance(receipt.get("contact_sheet"), dict) or Path(str(receipt["contact_sheet"].get("path", ""))).name != "contact_sheet.png":
        raise core.StudioError("Falta la hoja de contacto canónica.", 409)
    if bool(receipt.get("sequence")) != normalized["sequence"]:
        raise core.StudioError("El recibo no corresponde al tipo de preparación.", 409)
    if normalized["sequence"]:
        sequence = receipt["sequence"]
        if not isinstance(sequence, dict) or Path(str(sequence.get("path", ""))).name != "sequence.mp4" or sequence.get("audio_included") is not False:
            raise core.StudioError("La secuencia preparada no tiene el contrato esperado.", 409)
    files = entries + [receipt.get("contact_sheet")]
    if receipt.get("sequence") is not None:
        files.append(receipt["sequence"])
    for entry in files:
        if not isinstance(entry, dict):
            raise core.StudioError("Evidencia de muestras inválida.", 409)
        rel = entry.get("path")
        if not isinstance(rel, str) or core.confined(rel) != directory / Path(rel).name:
            raise core.StudioError("Evidencia fuera del directorio canónico del recurso.", 403)
        path = _path(directory, Path(rel).name, exists=True)
        if core.digest(path) != entry.get("sha256") or path.stat().st_size != entry.get("size"):
            raise core.StudioError("Los bytes de una muestra cambiaron.", 409)
    return receipt, actual


def _result(item, receipt, receipt_sha, *, reused=False):
    return {**copy.deepcopy(receipt), "receipt_path": core.relative(_directory(item["id"]) / "receipt.json"),
            "receipt_sha256": receipt_sha, "expected_review_digest": _review_digest(item),
            "source_sha256": item["sha256"], "reused": reused,
            "visual_reviewed": False, "audio_listened": False, "reel_approved": False,
            "proposal_model_vision": "deferred_not_executed"}


def prepare(asset_id, options=None, progress=None, cancel=None):
    from .jobs import cpu_slot
    item, _, _ = _source(asset_id)
    validate_options(item, options)
    if progress is not None and not callable(progress):
        raise core.StudioError("El progreso requiere un callback.")
    if cancel is not None and not callable(cancel) and not callable(getattr(cancel, "is_set", None)):
        raise core.StudioError("La cancelación requiere un evento o callback.")
    _check_cancel(cancel)
    with cpu_slot(cancel=cancel):
        item, source, identity = _source(asset_id)
        normalized = validate_options(item, options)
        engine = _engine()
        baseline = _review_digest(item)
        try:
            receipt, receipt_sha = _verify_receipt(asset_id, item, identity)
            if receipt.get("options") == normalized:
                # Reusing evidence does not claim an additional observation.
                with core.LOCK:
                    live, _, current = _source(asset_id)
                    if current != identity or _engine() != engine:
                        raise core.StudioError("El recurso cambió antes de reutilizar muestras.", 409)
                    _check_cancel(cancel)
                    if progress:
                        progress(1, "Muestras existentes vigentes; observación explícita pendiente.")
                    _check_cancel(cancel)
                    return _result(live, receipt, receipt_sha, reused=True)
        except core.StudioError as error:
            if error.status not in {404, 409}:
                raise
        base = core.confined(".estado/tmp")
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="resource_review_", dir=base) as temporary:
            work = Path(temporary)
            frames, sequence = [], None
            if item["kind"] == "image":
                with Image.open(source) as src:
                    if src.width * src.height > MAX_PIXELS:
                        raise core.StudioError("La imagen supera cuarenta megapíxeles.", 413)
                    frame = ImageOps.exif_transpose(src).convert("RGBA")
                    frame.thumbnail((normalized["max_width"], normalized["max_height"]))
                    frame.save(work / "frame_00.png")
                frames.append({**_file(work / "frame_00.png"), "time": 0., "requested_time": 0.})
            else:
                actual_probe = analysis.probe(source)
                if actual_probe != item["probe"]:
                    raise core.StudioError("La metadata técnica ya no coincide con el recurso real.", 409)
                stream = next((s for s in actual_probe.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
                if not stream or not isinstance(stream.get("width"), int) or not isinstance(stream.get("height"), int) or stream["width"] * stream["height"] > MAX_PIXELS:
                    raise core.StudioError("Video sin dimensiones admisibles para muestras.", 413)
                try:
                    a, b = str(stream.get("avg_frame_rate", "30/1")).split("/")
                    period = float(b) / float(a)
                    if not math.isfinite(period) or period <= 0:
                        raise ValueError()
                except (ValueError, ZeroDivisionError):
                    period = .1
                span = max(0., normalized["duration"] - min(normalized["duration"], period))
                for i in range(normalized["samples"]):
                    _check_cancel(cancel)
                    requested = normalized["start"] + (span * i / max(1, normalized["samples"] - 1))
                    output = work / ("frame_%02d.png" % i)
                    when = _frame(source, output, requested, normalized, actual_probe, cancel)
                    if when < normalized["start"] - .05 or when > normalized["start"] + normalized["duration"] + .05:
                        raise core.StudioError("El fotograma decodificado salió del tramo solicitado.")
                    frames.append({**_file(output), "time": when, "requested_time": requested})
                    if progress:
                        progress(.1 + .6 * (i + 1) / normalized["samples"], "Fotograma decodificado; aún sin observación editorial.")
                if normalized["sequence"]:
                    output = work / "sequence.mp4"
                    _run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(normalized["start"]), *analysis.input_media(source),
                          "-map", "0:v:0", "-an", "-sn", "-dn", "-t", str(normalized["duration"]),
                          "-vf", _scale(normalized) + ",fps=15", "-c:v", "libx264", "-crf", "28", "-pix_fmt", "yuv420p",
                          "-threads", "2", "-filter_threads", "1", "-y", str(output)], cancel)
                    probe = analysis.probe(output)
                    actual_duration = float(probe.get("format", {}).get("duration", 0))
                    if not max(.01, normalized["duration"] - 1/15 - .02) <= actual_duration <= normalized["duration"] + .15 or any(s.get("codec_type") == "audio" for s in probe.get("streams", [])):
                        raise core.StudioError("La secuencia muda no tiene el tramo técnico esperado.")
                    sequence = {**_file(output), "duration": actual_duration, "audio_included": False,
                                "scope": "prepared_for_explicit_sequence_observation"}
            sheet = _sheet(frames, work, normalized)
            _check_cancel(cancel)
            directory = _directory(asset_id)
            def destination(entry):
                if entry is None:
                    return None
                return {**entry, "path": core.relative(directory / Path(entry["path"]).name),
                        "url": "/api/assets/" + asset_id + "/review-files/" + Path(entry["path"]).name}
            receipt = {"schema": "ascendia.resource-observation/1", "asset_id": asset_id, "source": identity,
                       "engine": engine, "options": normalized, "interval": {"start": normalized["start"], "end": normalized["start"] + normalized["duration"]},
                       "frames": [destination(f) for f in frames], "contact_sheet": destination(sheet), "sequence": destination(sequence),
                       "prepared_scope": "sequence_available" if sequence else "samples", "status": "pending",
                       "safe_zones": _safe_zones(), "audio_listened": False, "visual_reviewed": False,
                       "semantic_match_confirmed": False, "rights_authority": False,
                       "color_scope": "decoder_preview_no_hdr_fidelity_guarantee", "at": core.now()}
            with core.LOCK:
                _check_cancel(cancel)
                live, _, current = _source(asset_id)
                if current != identity or _review_digest(live) != baseline or _engine() != engine:
                    raise core.StudioError("El recurso o su revisión cambió durante la preparación.", 409)
                directory = _directory(asset_id, create=True)
                names = [p.name for p in work.iterdir()]
                all_names = set(names + ["receipt.json", "review.json"])
                all_names.update(p.name for p in directory.iterdir() if FILE_NAME.fullmatch(p.name))
                backup = {name: _path(directory, name, exists=True).read_bytes() for name in all_names if _path(directory, name).is_file()}
                catalog = core.assets()
                row = next(a for a in catalog if a["id"] == asset_id)
                before_catalog = copy.deepcopy(catalog)
                from .providers import private_write
                try:
                    for name in names:
                        private_write(_path(directory, name), (work / name).read_bytes())
                    for name in all_names - set(names) - {"receipt.json", "review.json"}:
                        _path(directory, name).unlink(missing_ok=True)
                    private_write(_path(directory, "receipt.json"), _json(receipt))
                    _path(directory, "review.json").unlink(missing_ok=True)
                    receipt_sha = core.digest(directory / "receipt.json")
                    row.setdefault("metadata", {})["resource_review"] = {"status": "pending", "source_sha256": item["sha256"],
                        "receipt_sha256": receipt_sha, "receipt_path": core.relative(directory / "receipt.json"), "visual_reviewed": False}
                    row["metadata"]["visual_reviewed"] = False
                    row.setdefault("verification", {})["visual"] = False
                    core.atomic_json(".estado/assets.json", catalog)
                    if progress:
                        progress(1, "Muestras preparadas; describe el contenido y su alcance observado.")
                    _check_cancel(cancel)
                    if _source(asset_id)[2] != identity or _engine() != engine:
                        raise core.StudioError("El recurso cambió antes de confirmar las muestras.", 409)
                except Exception:
                    for name in all_names:
                        target = _path(directory, name)
                        if name in backup:
                            private_write(target, backup[name])
                        else:
                            target.unlink(missing_ok=True)
                    core.atomic_json(".estado/assets.json", before_catalog)
                    raise
                return _result(row, receipt, receipt_sha)


def _validate_review(review):
    if not isinstance(review, dict) or set(review) - REVIEW_FIELDS or not REQUIRED_REVIEW <= set(review):
        raise core.StudioError("La revisión contiene campos incorrectos o incompletos.")
    for key in ("expected_source_sha256", "expected_review_digest", "receipt_sha256"):
        _hash(review[key], key)
    _text(review["reviewer"], "reviewer", 1, 120)
    _text(review["notes"], "notes", 24, 8000)
    _text(review["content"], "content", 16, 20000)
    _text(review["rights_declaration"], "rights_declaration", 8, 4000)
    if review["visual_reviewed"] is not True or type(review.get("sequence_viewed", False)) is not bool:
        raise core.StudioError("La observación visual requiere una afirmación explícita del revisor.")
    if not isinstance(review["scope"], str) or review["scope"] not in {"observed_samples", "sequence"}:
        raise core.StudioError("Alcance de observación inválido.")
    interval = review["interval"]
    if not isinstance(interval, dict) or set(interval) != {"start", "end"}:
        raise core.StudioError("El tramo observado requiere inicio y fin.")
    for key in ("start", "end"):
        core.finite_number(interval[key], "tramo observado " + key, 0, 86400)
    evidence = review["evidence"]
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 14:
        raise core.StudioError("La observación requiere evidencia preparada concreta.")
    seen = set()
    for row in evidence:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or not isinstance(row["path"], str) or row["path"] in seen:
            raise core.StudioError("Evidencia visual mal formada o repetida.")
        seen.add(row["path"])
        _hash(row["sha256"], "evidence")


def record(asset_id, review):
    _validate_review(review)
    with core.LOCK:
        item, _, identity = _source(asset_id)
        if item["sha256"] != review["expected_source_sha256"] or _review_digest(item) != review["expected_review_digest"]:
            raise core.StudioError("El recurso o su revisión cambió; recarga antes de registrar.", 409)
        receipt, receipt_sha = _verify_receipt(asset_id, item, identity, expected=review["receipt_sha256"])
        lo, hi = review["interval"]["start"], review["interval"]["end"]
        if lo < receipt["interval"]["start"] or hi > receipt["interval"]["end"] or hi < lo or (item["kind"] != "image" and hi <= lo):
            raise core.StudioError("El tramo observado no pertenece a las muestras preparadas.")
        entries = receipt["frames"] + [receipt["contact_sheet"]] + ([receipt["sequence"]] if receipt.get("sequence") else [])
        known = {f["path"]: f for f in entries}
        for e in review["evidence"]:
            if e["path"] not in known or known[e["path"]]["sha256"] != e["sha256"]:
                raise core.StudioError("La evidencia no pertenece al recibo actual.", 403)
        paths = {e["path"] for e in review["evidence"]}
        observed = [f["time"] for f in receipt["frames"] if f["path"] in paths and lo <= f["time"] <= hi]
        if receipt["contact_sheet"]["path"] in paths:
            observed = [f["time"] for f in receipt["frames"] if lo <= f["time"] <= hi]
        if review["scope"] == "sequence":
            if not receipt.get("sequence") or review.get("sequence_viewed") is not True or receipt["sequence"]["path"] not in paths:
                raise core.StudioError("Observar una secuencia requiere el clip preparado y afirmación explícita de visionado.")
        elif not observed:
            raise core.StudioError("Las muestras declaradas no acreditan puntos dentro del tramo observado.")
        history = item.get("metadata", {}).get("resource_review_history", [])
        if (not isinstance(history, list) or len(history) > 100 or any(not isinstance(h, dict) or
                set(h) != {"sha256", "previous_sha256", "at", "reviewer"} or not isinstance(h.get("sha256"), str) or
                not SHA.fullmatch(h["sha256"]) or (h.get("previous_sha256") is not None and
                (not isinstance(h["previous_sha256"], str) or not SHA.fullmatch(h["previous_sha256"]))) for h in history) or
                any(history[i]["previous_sha256"] != history[i-1]["sha256"] for i in range(1, len(history)))):
            raise core.StudioError("Historial de observación inválido.", 409)
        entry = {"status": "observed", "source_sha256": item["sha256"], "receipt_sha256": receipt_sha,
                 "receipt_path": core.relative(_directory(asset_id) / "receipt.json"), "reviewer": review["reviewer"],
                 "notes": review["notes"], "content": review["content"], "scope": review["scope"],
                 "interval": copy.deepcopy(review["interval"]), "evidence": copy.deepcopy(review["evidence"]),
                 "observed_times": sorted(set(observed)), "coverage": "continuous_declared" if review["scope"] == "sequence" else "points_only",
                 "sequence_viewed": review.get("sequence_viewed", False), "visual_reviewed": True, "audio_listened": False,
                 "rights_declaration": review["rights_declaration"], "rights_status": "supplied_by_user_unverified",
                 "rights_authority": False, "semantic_match_confirmed": False, "reel_approved": False,
                 "previous_review_digest": _review_digest(item), "previous_history_hash": history[-1]["sha256"] if history else None,
                 "at": core.now()}
        commit = {"sha256": _digest(entry), "previous_sha256": entry["previous_history_hash"], "at": entry["at"], "reviewer": entry["reviewer"]}
        directory = _directory(asset_id)
        private = _path(directory, "review.json")
        from .providers import private_write
        previous_bytes = private.read_bytes() if private.exists() else None
        catalog = core.assets()
        before = copy.deepcopy(catalog)
        live = next(a for a in catalog if a["id"] == asset_id)
        live.setdefault("metadata", {}).update(content=review["content"], visual_reviewed=True, resource_review=entry,
                                                resource_review_history=(history + [commit])[-100:])
        live.setdefault("verification", {}).update(visual=True, audio=False, rights="supplied_by_user_unverified",
                                                 evidence=[e["path"] for e in review["evidence"]])
        try:
            private_write(private, _json({"review": entry, "commit": commit}))
            core.atomic_json(".estado/assets.json", catalog)
            if _source(asset_id)[2] != identity:
                raise core.StudioError("El recurso cambió antes de confirmar la observación.", 409)
            _verify_receipt(asset_id, live, identity, expected=receipt_sha)
        except Exception:
            if previous_bytes is None:
                private.unlink(missing_ok=True)
            else:
                private_write(private, previous_bytes)
            core.atomic_json(".estado/assets.json", before)
            raise
        return {"asset": copy.deepcopy(live), "review": copy.deepcopy(entry), "review_digest": _review_digest(live),
                "editorial_approved": False, "reel_approved": False}


def current_review(asset):
    """Read-only integrity check. Samples confer points, never interval coverage."""
    try:
        aid = asset.get("id") if isinstance(asset, dict) else asset
        item, _, identity = _source(aid)
        claim = item.get("metadata", {}).get("resource_review", {})
        if not isinstance(claim, dict) or claim.get("status") != "observed":
            return {"valid": False, "status": "pending", "reason": "Falta una observación explícita vigente."}
        receipt, sha = _verify_receipt(aid, item, identity, expected=claim.get("receipt_sha256"))
        private = json.loads(_path(_directory(aid), "review.json", exists=True).read_text())
        if (private.get("review") != claim or private.get("commit", {}).get("sha256") != _digest(claim) or
                item.get("metadata", {}).get("resource_review_history", [])[-1] != private["commit"] or
                claim.get("visual_reviewed") is not True or claim.get("rights_authority") is not False or
                claim.get("reel_approved") is not False or item.get("metadata", {}).get("content") != claim.get("content") or
                item.get("metadata", {}).get("visual_reviewed") is not True or
                item.get("verification", {}).get("visual") is not True or
                item.get("verification", {}).get("rights") != "supplied_by_user_unverified" or
                item.get("verification", {}).get("evidence") != [e["path"] for e in claim.get("evidence", [])]):
            raise core.StudioError("La observación no coincide con su registro privado.", 409)
        return {"valid": True, "status": "observed", "scope": claim["scope"], "interval": copy.deepcopy(claim["interval"]),
                "coverage": claim["coverage"], "observed_times": claim["observed_times"], "content": claim["content"],
                "review_digest": _review_digest(item), "receipt_sha256": sha, "rights_authority": False,
                "semantic_match_confirmed": False, "editorial_approved": False, "reel_approved": False}
    except (core.StudioError, ValueError, TypeError, KeyError, IndexError, AttributeError, OSError) as error:
        return {"valid": False, "status": "stale_or_missing", "reason": str(error)[:500]}


def evidence_file(asset_id, name):
    """Resolve an authenticated UI sample; private receipts/reviews stay private."""
    if not isinstance(name, str) or name in {"receipt.json", "review.json"}:
        raise core.StudioError("Los recibos y registros privados no se sirven como medios.", 403)
    directory = _directory(asset_id)
    path = _path(directory, name, exists=True)
    item, _, identity = _source(asset_id)
    receipt, _ = _verify_receipt(asset_id, item, identity)
    entries = receipt["frames"] + [receipt["contact_sheet"]] + ([receipt["sequence"]] if receipt.get("sequence") else [])
    row = next((e for e in entries if Path(e["path"]).name == name), None)
    if not row or core.digest(path) != row["sha256"]:
        raise core.StudioError("La muestra no pertenece al recibo vigente.", 403)
    return path
