"""Read-only framing proposals from verified offline facial measurements.

No decoder, browser, ASR, model download, project write or automatic approval.
Coordinates are estimates from sampled frames; final framing remains editorial.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image

from . import core, tracking


def _number(value, label, lo=0, hi=1):
    return core.finite_number(value, label, lo, hi)


def _file(path):
    try:
        return core.confined(path, must_exist=True)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        raise core.StudioError("Ruta inválida en la evidencia de tracking.", 403) from error


def _json(path):
    path = _file(path)
    if path.stat().st_size > 8_000_000:
        raise core.StudioError("Registro de tracking demasiado grande.", 409)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise core.StudioError("Registro de tracking no válido.", 409) from error
    if not isinstance(result, dict):
        raise core.StudioError("Registro de tracking requiere un objeto.", 409)
    return result


def _verified(project):
    if not isinstance(project, dict) or not isinstance(project.get("assets"), list):
        raise core.StudioError("Proyecto no válido para proponer encuadre.")
    project_id = project.get("id")
    if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", project_id):
        raise core.StudioError("ID de proyecto inválido.")
    source = next((a for a in project["assets"] if isinstance(a, dict) and a.get("id") == project.get("source")), None)
    if not source:
        raise core.StudioError("Asigna el crudo original antes de proponer encuadre.")
    canonical = core.asset(source.get("id"))
    if any(canonical.get(field) != source.get(field) for field in ("path", "sha256", "probe", "kind")):
        raise core.StudioError("La geometría y el crudo deben coincidir con el recurso registrado; no se aceptan probes forjados.", 409)
    source = canonical
    registration = project.get("tracking")
    if not isinstance(registration, dict):
        raise core.StudioError("Ejecuta seguimiento facial antes de pedir propuestas.", 409)
    path = _file(registration.get("path"))
    relative = path.relative_to(core.ROOT).as_posix()
    match = re.fullmatch(r"projects/" + re.escape(project_id) + r"/tracking/([a-f0-9]{24})/measurements\.json", relative)
    if not match:
        raise core.StudioError("El recibo de tracking debe pertenecer al proyecto canónico.", 403)
    key = match.group(1)
    report = _json(path)
    if report.get("path") != relative:
        raise core.StudioError("La ruta declarada del seguimiento no coincide con su registro canónico.", 409)
    receipt = _json(f".estado/tracking/receipts/{project_id}_{key}.json")
    if receipt.get("report_sha256") != core.content_hash(path):
        raise core.StudioError("Las medidas faciales cambiaron desde su ejecución.", 409)
    identity = report.get("identity")
    if not isinstance(identity, dict):
        raise core.StudioError("Falta identidad del análisis facial.", 409)
    actual_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    if actual_key != key:
        raise core.StudioError("Identidad del tracking incoherente.", 409)
    source_sha = core.content_hash(_file(source.get("path")))
    if (report.get("source") != source.get("id") or source_sha != source.get("sha256") or
        source_sha != report.get("source_sha256") or source_sha != identity.get("source_sha256") or
        source_sha != receipt.get("source_sha256")):
        raise core.StudioError("El crudo cambió; vuelve a medir su rostro.", 409)
    code_hash = core.digest(Path(tracking.__file__))
    if code_hash != identity.get("engine_code_sha256") or code_hash != receipt.get("engine_code_sha256"):
        raise core.StudioError("El motor de tracking cambió; vuelve a ejecutarlo.", 409)
    runtime = tracking._runtime(core.ROOT)
    if runtime.get("files") != identity.get("runtime_files"):
        raise core.StudioError("El modelo/runtime de tracking cambió.", 409)
    options = tracking.validate_options(identity.get("options"))
    samples, evidence = report.get("samples"), report.get("evidence")
    if not isinstance(samples, list) or not 1 <= len(samples) <= 600 or not isinstance(evidence, list) or len(evidence) != len(samples):
        raise core.StudioError("El seguimiento no contiene muestras y evidencias completas.", 409)
    interval = report.get("interval")
    if not isinstance(interval, list) or len(interval) != 2:
        raise core.StudioError("Falta el intervalo real del seguimiento.", 409)
    _number(interval[0], "inicio seguimiento", 0, 14400)
    _number(interval[1], "fin seguimiento", interval[0] + .000001, 14400)
    hashes, sizes, times = {}, {}, {}
    for item in evidence:
        if not isinstance(item, dict):
            raise core.StudioError("Evidencia facial malformada.", 409)
        picture = _file(item.get("path"))
        if picture.parent != path.parent or not re.fullmatch(r"frame_\d{4}\.jpg", picture.name):
            raise core.StudioError("Evidencia ajena al análisis facial canónico.", 403)
        if item.get("sha256") != core.content_hash(picture):
            raise core.StudioError("Un fotograma del tracking cambió.", 409)
        with Image.open(picture) as image:
            size = image.size
            if image.format != "JPEG" or not 1 <= size[0] <= 640 or not 1 <= size[1] <= 4096:
                raise core.StudioError("Fotograma de tracking inválido.", 409)
            image.verify()
        if item["path"] in hashes:
            raise core.StudioError("Fotogramas repetidos en el registro de tracking.", 409)
        hashes[item["path"]] = item["sha256"]
        sizes[item["path"]] = size
        times[item["path"]] = _number(item.get("source_time"), "tiempo de evidencia", 0, 14400)
    previous = -1
    for sample in samples:
        if not isinstance(sample, dict) or sample.get("evidence") not in hashes:
            raise core.StudioError("Una muestra no tiene evidencia propia.", 409)
        when = _number(sample.get("time"), "tiempo de muestra", 0, 14400)
        if when <= previous:
            raise core.StudioError("Las muestras requieren tiempos distintos y crecientes.", 409)
        previous = when
        if abs(when - times[sample["evidence"]]) > .000001 or not interval[0] <= when < interval[1]:
            raise core.StudioError("Los tiempos no corresponden al fotograma y al intervalo medidos.", 409)
        if sample.get("detected") is True:
            _number(sample.get("confidence"), "score del detector", options["min_confidence"], 1)
            for kind in ("raw", "smoothed"):
                values = sample.get(kind)
                if not isinstance(values, dict):
                    raise core.StudioError("Faltan coordenadas faciales medidas.", 409)
                for field in ("focus_x", "focus_y", "chin_x", "chin_y"):
                    _number(values.get(field), field)
    if core.content_hash(path) != receipt["report_sha256"] or core.content_hash(_file(source["path"])) != source_sha:
        raise core.StudioError("Las entradas cambiaron mientras se leían las propuestas.", 409)
    return source, report, options, sizes


def _geometry(source, sizes):
    info = source.get("probe", {})
    if not isinstance(info, dict) or not isinstance(info.get("streams"), list):
        raise core.StudioError("Falta geometría de video verificada.", 409)
    stream = next((s for s in info["streams"] if isinstance(s, dict) and s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    if not stream:
        raise core.StudioError("La geometría requiere video real, distinto de una portada.", 409)
    width, height = (_number(stream.get(k), k, 1, 32768) for k in ("width", "height"))
    if width != int(width) or height != int(height):
        raise core.StudioError("Dimensiones de video no enteras.", 409)
    sar = stream.get("sample_aspect_ratio")
    if isinstance(sar, bool) or sar not in ("1:1", "1/1", 1, 1.0):
        raise core.StudioError("Propuestas disponibles solo con SAR 1:1 explícito; no se adivina geometría.", 409)
    rotations = []
    if "rotation" in stream:
        rotations.append(stream["rotation"])
    if isinstance(stream.get("tags"), dict) and "rotate" in stream["tags"]:
        rotations.append(stream["tags"]["rotate"])
    for side in stream.get("side_data_list", []):
        if isinstance(side, dict) and "rotation" in side:
            rotations.append(side["rotation"])
    normalized = []
    for value in rotations or [0]:
        if isinstance(value, bool):
            raise core.StudioError("Rotación de video inválida.", 409)
        try:
            angle = float(value)
        except (TypeError, ValueError) as error:
            raise core.StudioError("Rotación de video inválida.", 409) from error
        if not math.isfinite(angle) or abs(angle / 90 - round(angle / 90)) > .00001:
            raise core.StudioError("Rotación no ortogonal: requiere revisión manual.", 409)
        normalized.append(round(angle) % 360)
    if len(set(normalized)) != 1:
        raise core.StudioError("Metadata de rotación contradictoria.", 409)
    rotation = normalized[0]
    if rotation in (90, 270):
        width, height = height, width
    # Landmarks already belong to autorotated JPEGs. Do not rotate them twice.
    for frame_width, frame_height in sizes.values():
        expected_height = height * frame_width / width
        if abs(frame_height - expected_height) > 2.01:
            raise core.StudioError("El aspect ratio de la evidencia contradice el probe; no se adivina rotación/SAR.", 409)
    return int(width), int(height), rotation


def _cover(source_size, target_size, nose):
    sw, sh = source_size
    tw, th = target_size
    # ff_scale_adjust_dimensions / AV_ROUND_NEAR_INF with force_original_aspect_ratio=increase.
    scaled_w = max(tw, (th * sw * 2 + sh) // (2 * sh))
    scaled_h = max(th, (tw * sh * 2 + sw) // (2 * sw))
    excess_x, excess_y = scaled_w - tw, scaled_h - th
    # Keeping the nose near 40% leaves room for the chin and caption beneath.
    # This is an explicit framing suggestion, not a measured YO design rule.
    focus_x = min(1., max(0., (nose[0] * scaled_w - tw * .5) / excess_x)) if excess_x else .5
    focus_y = min(1., max(0., (nose[1] * scaled_h - th * .4) / excess_y)) if excess_y else .5
    # Renderer prints focus to six decimals; FFmpeg crop uses nearest-even for RGB24.
    focus_x, focus_y = round(focus_x, 6), round(focus_y, 6)
    crop_x, crop_y = round(excess_x * focus_x), round(excess_y * focus_y)
    return {"source_size": [sw, sh], "target_size": [tw, th], "scaled_size": [scaled_w, scaled_h],
            "crop_origin": [crop_x, crop_y], "focus_x": focus_x, "focus_y": focus_y,
            "suggested_nose_y": .4, "method": "native scale=increase/crop/setsar=1/RGB24"}


def _scene_proposal(scene, samples, options, source_size, settings, interval):
    start = _number(scene.get("start"), "inicio escena", 0, 86400)
    end = _number(scene.get("end"), "fin escena", start + .00001, 86400)
    source_in = _number(scene.get("source_in", start), "entrada crudo", 0, 14400)
    span = end - start
    relevant = [s for s in samples if source_in <= s["time"] < source_in + span]
    proposal = {"scene_id": scene.get("id"), "status": "blocked", "errors": [], "source_interval": [source_in, source_in + span],
                "reviewed": False, "apply_automatically": False, "suggested_changes": None}
    step = 1 / options["sample_fps"]
    if source_in < interval[0] - .0001 or source_in + span > interval[1] + .0001 or not relevant or relevant[0]["time"] > source_in + step + .0001 or relevant[-1]["time"] < source_in + span - step - .0001:
        proposal["errors"].append("El seguimiento no cubre todo el intervalo de fuente de la escena.")
    elif any(s.get("detected") is not True or s.get("face_count") != 1 for s in relevant):
        proposal["errors"].append("Hay muestras sin rostro único: no se interpola ni se elige una persona automáticamente.")
    elif any(b["time"] - a["time"] > step * 1.75 for a, b in zip(relevant, relevant[1:])):
        proposal["errors"].append("Hay un hueco en las muestras; vuelve a medir el intervalo.")
    if proposal["errors"]:
        return proposal
    width = _number(settings.get("width"), "ancho del proyecto", 160, 3840)
    height = _number(settings.get("height"), "alto del proyecto", 160, 3840)
    if width != int(width) or height != int(height) or width % 2 or height % 2:
        raise core.StudioError("Las dimensiones del proyecto requieren enteros pares.")
    w, h = int(width), int(height)
    # This matches the native compositor's exact region, including rounding.
    from .render import split_height
    lower_h = h - split_height(h, settings.get('split_motion_ratio', .55)) if scene["type"] == "split" else h
    nose = (sum(s["smoothed"]["focus_x"] for s in relevant) / len(relevant),
            sum(s["smoothed"]["focus_y"] for s in relevant) / len(relevant))
    cover = _cover(source_size, (w, lower_h), nose)
    scaled_w, scaled_h = cover["scaled_size"]
    crop_x, crop_y = cover["crop_origin"]
    transformed = []
    for sample in relevant:
        raw = sample["raw"]
        chin_x, chin_y = (raw["chin_x"] * scaled_w - crop_x) / w, (raw["chin_y"] * scaled_h - crop_y) / lower_h
        box = sample.get("bbox")
        if not isinstance(box, dict):
            proposal["errors"].append("Falta la caja facial para comprobar su recorte.")
            break
        bx, by = (_number(box.get(k), "caja " + k) for k in ("x", "y"))
        bw, bh = (_number(box.get(k), "caja " + k, .000001, 1) for k in ("width", "height"))
        if not 0 <= chin_x <= 1 or not 0 <= chin_y <= .95 or bx * scaled_w < crop_x - 1 or by * scaled_h < crop_y - 1 or (bx + bw) * scaled_w > crop_x + w + 1 or (by + bh) * scaled_h > crop_y + lower_h + 1:
            proposal["errors"].append("El recorte propuesto corta parte del rostro o deja la barbilla fuera de rango; revisa manualmente.")
            break
        transformed.append({"source_time": sample["time"], "scene_local_time": sample["time"] - source_in,
                            "output_time": start + sample["time"] - source_in, "source_chin": [raw["chin_x"], raw["chin_y"]],
                            "cropped_chin": [round(chin_x, 6), round(chin_y, 6)], "evidence": sample["evidence"], "confidence": sample["confidence"]})
    if proposal["errors"]:
        return proposal
    proposal.update(status="pending_visual_review", geometry=cover, chin_samples=transformed,
                    minimum_confidence=min(s["confidence"] for s in relevant),
                    suggested_changes={"focus_x": cover["focus_x"], "focus_y": cover["focus_y"],
                                       "chin_y": round(max(s["cropped_chin"][1] for s in transformed), 6)},
                    limitations=["Barbilla estimada por modelo y solo en muestras: no certifica todos los frames.",
                                 "Se propone una constante conservadora; no crea claves ni marca chin_reviewed.",
                                 "Revisar rostro, micrófono, zooms y espacio de subtítulo en el render real."])
    return proposal


def propose_tracking(project):
    """Verify persisted evidence and return current-scene suggestions, without writes."""
    result = {"valid": False, "errors": [], "proposals": [], "read_only": True,
              "apply_automatically": False, "reviewed": False, "editorial_approved": False}
    try:
        source, report, options, sizes = _verified(project)
        width, height, rotation = _geometry(source, sizes)
        settings = project.get("settings")
        if not isinstance(settings, dict) or not isinstance(project.get("timeline"), list):
            raise core.StudioError("Falta cronología o configuración del proyecto.")
        proposals = [_scene_proposal(scene, report["samples"], options, (width, height), settings, report["interval"])
                     for scene in project["timeline"] if isinstance(scene, dict) and scene.get("type") in ("presenter", "split")]
        result.update(valid=True, proposals=proposals, source_sha256=report["source_sha256"],
                      report_path=report["path"], rotation_applied=rotation,
                      note="Las sugerencias no se aplican ni certifican revisión editorial.")
    except (core.StudioError, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        result["errors"] = [str(error)]
        if isinstance(error, core.StudioError):
            result["error_status"] = error.status
    return result
