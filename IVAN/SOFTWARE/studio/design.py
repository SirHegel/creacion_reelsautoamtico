"""Data-only editable motion; deterministic state and local static proofs."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

from PIL import Image, ImageDraw, ImageFont

from .core import StudioError, content_hash, finite_number, confined
from . import typography

EASES = ("linear", "power1.inOut", "power2.out", "power2.inOut", "power3.out")
CHANNELS = ("x", "y", "scale", "opacity", "rotation", "mask_progress")


def color(value, field="color"):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise StudioError(f"{field} requiere #RRGGBB.")
    return value


def validate_design(scene, size=None):
    if not isinstance(scene, dict):
        raise StudioError("La escena del diseño requiere un objeto.")
    design = scene.get("motion_design")
    if design is None:
        if scene.get("template") == "custom":
            raise StudioError("La composición libre requiere un diseño editable.")
        return
    if not isinstance(design, dict) or scene.get("type") not in ("motion", "split") or scene.get("template") != "custom":
        raise StudioError("motion_design requiere escena motion o split con plantilla custom.")
    effects = scene.get("effects", {})
    if not isinstance(effects, dict):
        raise StudioError("Los efectos del diseño requieren un objeto.")
    for key, low, high in (("brightness", -1, 1), ("contrast", .1, 3), ("saturation", 0, 3)):
        if key in effects:
            finite_number(effects[key], "efecto " + key, low, high)
    if not isinstance(scene.get("id"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", scene["id"]):
        raise StudioError("El diseño requiere un ID de escena de letras, números, guion o subrayado.")
    canvas = design.get("canvas", {})
    if not isinstance(canvas, dict):
        raise StudioError("El lienzo del diseño requiere un objeto.")
    color(canvas.get("background", "#101318"), "fondo del lienzo")
    elements = design.get("elements", [])
    if not isinstance(elements, list) or not 1 <= len(elements) <= 64:
        raise StudioError("El diseño admite entre uno y 64 elementos.")
    start = finite_number(scene.get("start"), "inicio escena del diseño", 0, 86400)
    end = finite_number(scene.get("end"), "fin escena del diseño", 0, 86400)
    if end <= start:
        raise StudioError("La escena del diseño requiere duración positiva.")
    duration = end - start
    ids = set()
    text_units = 0
    for el in elements:
        if not isinstance(el, dict) or not isinstance(el.get("id"), str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", el["id"]) or el["id"] in ids:
            raise StudioError("Los elementos requieren IDs únicos de letras, números, guion o subrayado.")
        ids.add(el["id"])
        if el.get("type") not in ("text", "shape", "media"):
            raise StudioError("Elemento de diseño no admitido.")
        typography.validate_text_element(el, duration)
        start = finite_number(el.get("start", 0), "inicio elemento", 0, duration + 1e-7)
        end = finite_number(el.get("end", duration), "fin elemento", 0, duration + 1e-7)
        if end <= start:
            raise StudioError("El fin del elemento debe superar su inicio.")
        for key in ("x", "y"):
            finite_number(el.get(key, 0), f"{key} elemento", 0, 1)
        for key in ("width", "height"):
            finite_number(el.get(key, .25), f"{key} elemento", .005, 1)
        if el.get("x", 0) + el.get("width", .25) > 1.00001 or el.get("y", 0) + el.get("height", .25) > 1.00001:
            raise StudioError("La caja del diseño base debe caber en el lienzo; anima salidas con keyframes.")
        finite_number(el.get("opacity", 1), "opacidad elemento", 0, 1)
        finite_number(el.get("rotation", 0), "rotación elemento", -3600, 3600)
        finite_number(el.get("z", 0), "orden elemento", -1000, 1000)
        finite_number(el.get("radius", 0), "radio a 1080 px", 0, 540)
        color(el.get("color", "#ffffff"), "color elemento")
        if el["type"] == "text":
            if not isinstance(el.get("text"), str) or len(el["text"]) > 2000:
                raise StudioError("El texto del elemento debe ser una cadena de hasta 2000 caracteres.")
            if el.get("font", "primary") not in ("primary", "accent"):
                raise StudioError("El texto requiere Sequel o Scholar.")
            finite_number(el.get("font_size", 84), "tamaño fuente a 1080 px", 8, 400)
            text_units += len(typography.graphemes(el["text"]))
        if el["type"] == "shape" and el.get("shape", "rect") not in ("rect", "ellipse"):
            raise StudioError("Forma no admitida.")
        if el["type"] == "media":
            if not isinstance(el.get("asset_id"), str) or not el["asset_id"]:
                raise StudioError("El elemento de medio requiere un recurso.")
            finite_number(el.get("source_in", 0), "entrada medio elemento", 0, 86400)
        mask = el.get("mask", {"type": "none"})
        if not isinstance(mask, dict) or mask.get("type", "none") not in ("none", "circle", "inset"):
            raise StudioError("Máscara geométrica no admitida.")
        if mask.get("type") == "inset":
            inset = mask.get("inset", {})
            if not isinstance(inset, dict):
                raise StudioError("La máscara inset requiere coordenadas.")
            for side in ("top", "right", "bottom", "left"):
                finite_number(inset.get(side, 0), "máscara " + side, 0, 1)
            if inset.get("top", 0) + inset.get("bottom", 0) >= 1 or inset.get("left", 0) + inset.get("right", 0) >= 1:
                raise StudioError("La máscara no puede ocultar toda la caja.")
        keys = el.get("keyframes", [])
        if not isinstance(keys, list) or len(keys) > 128:
            raise StudioError("Cada elemento admite hasta 128 keyframes.")
        times = set()
        for frame in keys:
            if not isinstance(frame, dict):
                raise StudioError("Cada keyframe requiere un objeto.")
            t = finite_number(frame.get("time"), "tiempo keyframe del diseño", 0, duration + 1e-7)
            if t in times:
                raise StudioError("Los keyframes de un elemento requieren tiempos distintos.")
            times.add(t)
            if frame.get("ease", "linear") not in EASES:
                raise StudioError("Curva de animación no admitida.")
            window = frame.get("ease_window", [0, 1])
            if not isinstance(window, list) or len(window) != 2:
                raise StudioError("La ventana de easing requiere dos números.")
            lo = finite_number(window[0], "inicio ventana easing", 0, 1)
            hi = finite_number(window[1], "fin ventana easing", 0, 1)
            if hi - lo < 1e-6:
                raise StudioError("La ventana de easing debe tener una extensión positiva.")
            for key, lo, hi in (("x", -2, 2), ("y", -2, 2), ("scale", .01, 8), ("opacity", 0, 1), ("rotation", -3600, 3600), ("mask_progress", 0, 1)):
                if key in frame:
                    finite_number(frame[key], "keyframe " + key, lo, hi)
                    if key == "mask_progress" and mask.get("type", "none") == "none":
                        raise StudioError("La revelación requiere una máscara circle o inset.")
        if size:
            bw, bh = el.get("width", .25) * size[0], el.get("height", .25) * size[1]
            scale = max([1.] + [f.get("scale", 1.) for f in keys])
            # Bound both the resized tile and its worst rotated surface.
            if (bw + bh) ** 2 * scale ** 2 > 32_000_000:
                raise StudioError("La superficie animada de un elemento supera el límite de memoria local.")
        path = el.get("path")
        if path is not None:
            if not isinstance(path, dict) or path.get("orient", False) is not False:
                raise StudioError("La trayectoria requiere datos; orient debe ser false.")
            points = path.get("points", [])
            if not isinstance(points, list) or not 2 <= len(points) <= 64:
                raise StudioError("La trayectoria requiere entre dos y 64 puntos.")
            for point in points:
                if not isinstance(point, dict):
                    raise StudioError("Punto de trayectoria inválido.")
                for key in ("x", "y"):
                    finite_number(point.get(key), "punto " + key, -2, 2)
    if text_units > typography.MAX_SCENE_TEXT_UNITS:
        raise StudioError("La escena supera 8000 grafemas tipográficos; divide el contenido.")


def ease_value(u, ease, window=None):
    u = min(1, max(0, u))
    if window and window != [0, 1]:
        lo, hi = window
        a, b = ease_value(lo, ease), ease_value(hi, ease)
        return u if abs(b - a) < 1e-12 else (ease_value(lo + (hi - lo) * u, ease) - a) / (b - a)
    if ease == "linear":
        return u
    power = {"power1.inOut": 2, "power2.inOut": 3, "power2.out": 3, "power3.out": 4}[ease]
    if ease.endswith(".out"):
        return 1 - (1 - u) ** power
    return (2 * u) ** power / 2 if u < .5 else 1 - (2 * (1 - u)) ** power / 2


def element_state(element, time, scene_duration, width, height):
    state = {"x": element.get("x", 0), "y": element.get("y", 0), "scale": 1.,
             "opacity": element.get("opacity", 1), "rotation": element.get("rotation", 0), "mask_progress": 1.}
    poses = [(0., state.copy(), "linear", [0, 1])]
    for frame in sorted(element.get("keyframes", []), key=lambda x: x["time"]):
        target = {**poses[-1][1], **{k: frame[k] for k in CHANNELS if k in frame}}
        item = (frame["time"], target, frame.get("ease", "linear"), frame.get("ease_window", [0, 1]))
        if item[0] == poses[-1][0]:
            poses[-1] = item
        else:
            poses.append(item)
    t = min(scene_duration, max(0, time))
    state = poses[-1][1].copy()
    for left, right in zip(poses, poses[1:]):
        if t <= right[0]:
            u = ease_value((t - left[0]) / (right[0] - left[0]), right[2], right[3])
            state = {key: left[1][key] + (right[1][key] - left[1][key]) * u for key in CHANNELS}
            break
    path = element.get("path")
    if path:
        points = path["points"]
        distances = [math.hypot((b["x"] - a["x"]) * width, (b["y"] - a["y"]) * height) for a, b in zip(points, points[1:])]
        start, end = element.get("start", 0), element.get("end", scene_duration)
        travel = max(0, min(1, (t - start) / (end - start))) * sum(distances)
        if sum(distances) == 0:
            state.update(points[0])
        else:
            for a, b, distance in zip(points, points[1:], distances):
                if distance > 0 and travel <= distance:
                    u = travel / distance
                    state.update(x=a["x"] + (b["x"] - a["x"]) * u, y=a["y"] + (b["y"] - a["y"]) * u)
                    break
                travel -= distance
            else:
                state.update(points[-1])
    return state


def design_digest(scene, project=None):
    validate_design(scene)
    if not isinstance(scene.get("motion_design"), dict):
        raise StudioError("La huella estática requiere un diseño libre válido.")
    design = copy.deepcopy(scene["motion_design"])
    for el in design.get("elements", []):
        el.pop("keyframes", None)
        el.pop("path", None)
        el.pop("start", None)
        el.pop("end", None)
        el.pop("text_animation", None)
    effects = scene.get("effects", {})
    payload = {"scene_id": scene["id"], "scene_type": scene.get("type"), "design": design,
               "effects": {key: effects.get(key, default) for key, default in (("brightness", 0), ("contrast", 1), ("saturation", 1))}}
    if project:
        declared_fonts = project.get("fonts")
        if not isinstance(declared_fonts, dict) or not all(declared_fonts.get(name) for name in ("primary", "accent")):
            raise StudioError("La captura requiere declarar ambas fuentes reales.")
        payload["fonts"] = {name: content_hash(path) for name, path in declared_fonts.items()}
        ids = {el.get("asset_id") for el in design.get("elements", []) if el.get("asset_id")}
        payload["media"] = {a["id"]: content_hash(a["path"]) for a in project.get("assets", []) if a["id"] in ids}
        font_ids = {el.get("font_asset_id") for el in design.get("elements", []) if el.get("font_asset_id")}
        attached = {a["id"]: a for a in project.get("assets", [])}
        if any(aid not in attached or attached[aid].get("kind") != "font" for aid in font_ids):
            raise StudioError("Las fuentes del diseño deben estar adjuntas como recursos font.")
        payload["selected_fonts"] = {aid: content_hash(attached[aid]["path"]) for aid in sorted(font_ids)}
        payload["settings"] = {key: project.get("settings", {}).get(key) for key in ("width", "height")}
        payload["settings"]["engine"] = project.get("settings", {}).get("engine", "native")
        if scene.get("type") == "split":
            from .render import split_height, _camera_state
            source = next((a for a in project.get("assets", []) if a["id"] == project.get("source")), None)
            if not source:
                raise StudioError("El diseño split requiere el crudo original.")
            pose = _camera_state(scene, 0)
            payload["camera"] = {"source_sha256": content_hash(source["path"]),
                                 "source_in": scene.get("source_in", scene.get("start", 0)),
                                 "upper_height": split_height(project["settings"]["height"]),
                                 "focus_x": pose.get("focus_x", .5), "focus_y": pose.get("focus_y", .5)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def draw_design(scene, time, size, fonts, media_frames=None, animate=True, root=None, font_assets=None):
    validate_design(scene, size)
    width, height = size
    design = scene["motion_design"]
    frame = Image.new("RGBA", size, design.get("canvas", {}).get("background", "#101318"))
    duration = scene["end"] - scene["start"]
    media_frames = media_frames or {}
    for el in sorted(design["elements"], key=lambda item: item.get("z", 0)):
        if animate and not el.get("start", 0) <= time < el.get("end", duration):
            continue
        state = element_state(el, time, duration, width, height) if animate else {"x": el.get("x", 0), "y": el.get("y", 0), "scale": 1, "opacity": el.get("opacity", 1), "rotation": el.get("rotation", 0), "mask_progress": 1}
        box = (max(1, round(el.get("width", .25) * width)), max(1, round(el.get("height", .25) * height)))
        tile = Image.new("RGBA", box)
        draw = ImageDraw.Draw(tile)
        if el["type"] == "shape":
            if el.get("shape", "rect") == "ellipse":
                draw.ellipse((0, 0, box[0] - 1, box[1] - 1), fill=el.get("color", "#ffffff"))
            else:
                draw.rounded_rectangle((0, 0, box[0] - 1, box[1] - 1), radius=el.get("radius", 0) * width / 1080, fill=el.get("color", "#ffffff"))
        elif el["type"] == "text":
            tile = typography.draw_text(el, size, fonts, font_assets, root=root,
                                        time=time, scene_duration=duration, animate=animate)
        elif el["id"] in media_frames or el.get("asset_id") in media_frames:
            media = media_frames.get(el["id"], media_frames.get(el.get("asset_id"))).convert("RGBA").copy()
            media.thumbnail(box, Image.Resampling.LANCZOS)
            tile.alpha_composite(media, ((box[0] - media.width) // 2, (box[1] - media.height) // 2))
        mask = el.get("mask", {})
        if mask.get("type") in ("circle", "inset"):
            alpha = Image.new("L", box)
            md = ImageDraw.Draw(alpha)
            if mask["type"] == "circle":
                radius = min(box) / 2 * state["mask_progress"]
                if radius > 0:
                    md.ellipse((box[0] / 2 - radius, box[1] / 2 - radius, box[0] / 2 + radius, box[1] / 2 + radius), fill=255)
            else:
                inset = mask.get("inset", {})
                right = inset.get("right", 0) + (1 - inset.get("left", 0) - inset.get("right", 0)) * (1 - state["mask_progress"])
                if state["mask_progress"] > 0:
                    edges = (round(inset.get("left", 0) * box[0]), round(inset.get("top", 0) * box[1]), round((1 - right) * box[0]) - 1, round((1 - inset.get("bottom", 0)) * box[1]) - 1)
                    if edges[2] >= edges[0] and edges[3] >= edges[1]:
                        md.rectangle(edges, fill=255)
            from PIL import ImageChops
            tile.putalpha(ImageChops.multiply(tile.getchannel("A"), alpha))
        base_center = (state["x"] * width + box[0] / 2, state["y"] * height + box[1] / 2)
        scaled = (max(1, round(box[0] * state["scale"])), max(1, round(box[1] * state["scale"])))
        tile = tile.resize(scaled, Image.Resampling.LANCZOS)
        if state["rotation"]:
            tile = tile.rotate(-state["rotation"], resample=Image.Resampling.BICUBIC, expand=True)
        if state["opacity"] != 1:
            tile.putalpha(tile.getchannel("A").point(lambda a: round(a * state["opacity"])))
        frame.alpha_composite(tile, (round(base_center[0] - tile.width / 2), round(base_center[1] - tile.height / 2)))
    return frame
