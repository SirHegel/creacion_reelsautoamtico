"""Deterministic, editable motion compositions. No external service or GPU.

These are conceptual animations, never recordings of a real application. The
storyboard supplies every label and number; templates do not invent metrics.
"""
from __future__ import annotations

import math
from pathlib import Path
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont


def clamp(value, low=0.0, high=1.0):
    return min(high, max(low, float(value)))


def ease(value):
    """Smoothstep, with bounded position and no alternating scale."""
    t = clamp(value)
    return t * t * (3 - 2 * t)


def font(path: str, size: int):
    if not Path(path).is_file():
        raise ValueError("Falta el archivo de fuente declarado; no se sustituye.")
    stat = Path(path).stat()
    return _font_cached(path, size, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=128)
def _font_cached(path, size, inode, mtime, ctime):
    return ImageFont.truetype(path, max(8, int(size)))


def fit_font(path, text, size, width):
    face = font(str(path), int(size))
    while face.getlength(str(text)) > width and size > 8:
        size -= 1
        face = font(str(path), int(size))
    return face


def text(image, content, xy, face, color="white", anchor="mm", shadow=True):
    if not content:
        return
    draw = ImageDraw.Draw(image)
    x, y = xy
    if shadow:
        # Small, defined shadow; no blur on the footage or glyphs.
        unit = max(1, round(image.width / 540))
        draw.text((x + unit, y + 2 * unit), str(content), font=face,
                  fill=(0, 0, 0, 225), anchor=anchor,
                  stroke_width=max(1, unit // 2), stroke_fill=(0, 0, 0, 225))
    draw.text((x, y), str(content), font=face, fill=color, anchor=anchor)


def wrap(content, face, width, max_lines=4):
    lines = []
    for word in str(content).split():
        if not lines or face.getlength(lines[-1] + " " + word) > width:
            lines.append(word)
        else:
            lines[-1] += " " + word
    # Text is never silently discarded. Reduce the font upstream when needed.
    return lines


def multiline(image, content, center, path, size, width, color="white",
              line_spacing=1.1, shadow=True):
    size = max(8, int(size))
    face = font(str(path), size)
    lines = wrap(content, face, width)
    while (len(lines) > 4 or any(face.getlength(line) > width for line in lines)) and size > 8:
        size -= 1
        face = font(str(path), size)
        lines = wrap(content, face, width)
    step = size * line_spacing
    y = center[1] - (len(lines) - 1) * step / 2
    for line in lines:
        text(image, line, (center[0], y), face, color, shadow=shadow)
        y += step


def keyframe_state(keyframes, local_time):
    """Local seconds; x/y are normalized offsets, scale is a factor."""
    defaults = {"x": 0.0, "y": 0.0, "scale": 1.0, "opacity": 1.0}
    if not keyframes:
        return defaults
    frames = sorted(keyframes, key=lambda item: float(item.get("time", 0)))
    if local_time <= float(frames[0].get("time", 0)):
        return {key: float(frames[0].get(key, val)) for key, val in defaults.items()}
    for left, right in zip(frames, frames[1:]):
        if local_time <= float(right["time"]):
            span = float(right["time"]) - float(left.get("time", 0))
            ratio = ease((local_time - float(left.get("time", 0))) / max(span, .001))
            return {key: float(left.get(key, val)) + ratio *
                    (float(right.get(key, val)) - float(left.get(key, val)))
                    for key, val in defaults.items()}
    return {key: float(frames[-1].get(key, val)) for key, val in defaults.items()}


def transform(image, state):
    scale = clamp(state.get("scale", 1), .1, 4)
    opacity = clamp(state.get("opacity", 1))
    if (abs(scale - 1) < 1e-5 and abs(state.get("x", 0)) < 1e-5 and
            abs(state.get("y", 0)) < 1e-5 and opacity == 1):
        return image
    layer = image.convert("RGBA").resize((round(image.width * scale),
                                           round(image.height * scale)), Image.Resampling.LANCZOS)
    if opacity != 1:
        layer.putalpha(layer.getchannel("A").point(lambda a: int(a * opacity)))
    result = Image.new("RGBA", image.size, (16, 18, 23, 255))
    offset = (round((image.width - layer.width) / 2 + state.get("x", 0) * image.width),
              round((image.height - layer.height) / 2 + state.get("y", 0) * image.height))
    result.alpha_composite(layer, offset)
    return result.convert("RGB")


def _node(image, box, label, primary, activated=0, accent=False):
    draw = ImageDraw.Draw(image)
    width = image.width
    x0, y0, x1, y1 = [round(v) for v in box]
    shift = max(1, int(width * .01))
    draw.rounded_rectangle((x0 + shift, y0 + shift, x1 + shift, y1 + shift),
                           radius=width * .028, fill=(4, 6, 12))
    fill = tuple(round(a + (b - a) * activated) for a, b in
                 zip((32, 37, 48), (90, 32, 40) if accent else (57, 67, 83)))
    draw.rounded_rectangle((x0, y0, x1, y1), radius=width * .028,
                           fill=fill, outline=(100, 107, 119), width=max(1, width // 320))
    multiline(image, label, ((x0 + x1) / 2, (y0 + y1) / 2), primary,
              width * .062, max(10, x1 - x0 - width * .04))


def _workflow(image, scene, p, primary, accent):
    """Input packet -> transfer -> node reaction -> merged result -> exit."""
    w, h = image.size
    draw = ImageDraw.Draw(image)
    supplied = scene.get("nodes") or scene.get("motion", {}).get("nodes")
    if not supplied:
        # Generic process labels clearly represent a conceptual diagram.
        supplied = ["Entrada", "Proceso", "Resultado"]
    labels = [str(n.get("label", "")) if isinstance(n, dict) else str(n) for n in supplied][:3]
    if len(labels) != 3:
        raise ValueError("Workflow necesita tres nodos declarados.")
    centers = [(w * .5, h * .35), (w * .5, h * .53), (w * .5, h * .71)]
    entry = ease(p / .12)
    convergence = ease((p - .76) / .14)
    exit_amount = ease((p - .92) / .08)
    for i, (cx, cy) in enumerate(centers):
        cy = cy + (1 - entry) * h * .16 + convergence * (h * .53 - cy) - exit_amount * h * .8
        activated = ease((p - (.15 + i * .2)) / .1)
        size = 1 + .04 * math.sin(activated * math.pi)
        halfw, halfh = w * .32 * size, h * .056 * size
        _node(image, (cx - halfw, cy - halfh, cx + halfw, cy + halfh),
              labels[i], primary, activated)
    if .16 < p < .78:
        transfer = clamp((p - .16) / .52)
        y = h * (.4 + .28 * transfer)
        radius = w * .024
        # A moving data packet changes the receiving node; lines are secondary.
        draw.line((w * .5, h * .406, w * .5, h * .655), fill=(90, 100, 119), width=max(2, w // 180))
        draw.ellipse((w * .5 - radius, y - radius, w * .5 + radius, y + radius), fill=(244, 247, 252))
    if convergence > .5:
        _node(image, (w * .16, h * .465 - exit_amount * h * .8,
                      w * .84, h * .6 - exit_amount * h * .8), labels[-1], primary, 1)


def _compare(image, scene, p, primary, accent):
    w, h = image.size
    labels = scene.get("motion", {}).get("labels", scene.get("labels", ["Antes", "Después"]))
    if len(labels) < 2:
        raise ValueError("Comparación necesita dos etiquetas.")
    reveal = ease(p / .16)
    merge = ease((p - .55) / .25)
    exit_amount = ease((p - .91) / .09)
    y = h * .53 - exit_amount * h * .85
    left_x = w * (.25 + .25 * merge)
    right_x = w * (.75 - .25 * merge)
    for i, cx in enumerate((left_x, right_x)):
        halfw = w * (.2 + .13 * merge)
        halfh = h * (.15 - .075 * merge)
        _node(image, (cx - halfw, y - halfh + (1 - reveal) * h * .3,
                      cx + halfw, y + halfh + (1 - reveal) * h * .3),
              labels[min(i, 1)], primary, merge, i == 0 and bool(scene.get("red_reason")))
    # Transformation resolves the comparison into the supplied second state.
    if merge > .85:
        _node(image, (w * .17, y - h * .075, w * .83, y + h * .075), labels[1], primary, 1)


def _counter(image, scene, p, primary, accent):
    w, h = image.size
    data = scene.get("motion", {})
    if "value" not in data:
        raise ValueError("Contador requiere un valor del guion; no se inventan métricas.")
    value = float(data["value"])
    start = float(data.get("from", 0))
    completion = ease((p - .15) / .55)
    shown = start + (value - start) * completion
    decimals = int(clamp(data.get("decimals", 0), 0, 4))
    label = f"{shown:.{decimals}f}{data.get('suffix', '')}"
    draw = ImageDraw.Draw(image)
    y = h * .57 - ease((p - .92) / .08) * h * .8
    # Fill physically converges into the final result, rather than only fading.
    draw.rounded_rectangle((w * .12, y + h * .09, w * .88, y + h * .115),
                           radius=w * .014, fill=(48, 55, 65))
    if completion > 0:
        draw.rounded_rectangle((w * .12, y + h * .09,
                                w * (.12 + .76 * completion), y + h * .115),
                               radius=w * .014, fill=(242, 242, 247))
    text(image, label, (w * .5, y), fit_font(primary, label, w * .18, w * .83))


def _kinetic(image, scene, p, primary, accent):
    title = str(scene.get("title", ""))
    if not title:
        return
    w, h = image.size
    layer = Image.new("RGBA", image.size)
    entrance = ease(p / .14)
    exit_amount = ease((p - .9) / .1)
    multiline(layer, title, (w * .5, h * (.42 + (1 - entrance) * .12 - exit_amount * .5)),
              accent if scene.get("font") == "accent" else primary, w * .105, w * .85,
              color=scene.get("text_color", "white"))
    # Moving reveal mask reveals the composed phrase, not ASR word captions.
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rectangle((0, 0, w * entrance, h), fill=255)
    alpha = layer.getchannel("A")
    from PIL import ImageChops
    layer.putalpha(ImageChops.multiply(alpha, mask))
    image.paste(layer, (0, 0), layer)
    emphasis = scene.get("emphasis", "")
    if emphasis:
        multiline(image, emphasis, (w * .5 + w * .02 * math.sin(p * math.pi), h * .63),
                  accent, w * .14, w * .85,
                  color=(216, 28, 45) if scene.get("red_reason") else "white")


def compose(scene, local_time, duration, size, primary, accent):
    image = Image.new("RGB", size, (16, 18, 23))
    w, h = size
    # Subtle perspective grid, whose motion is secondary to the action.
    draw = ImageDraw.Draw(image)
    step = max(16, w // 9)
    drift = int(local_time * w * .012) % step
    for x in range(-step, w + step, step):
        draw.line((x + drift, 0, x + drift, h), fill=(22, 25, 31))
    for y in range(-step, h + step, step):
        draw.line((0, y + drift, w, y + drift), fill=(22, 25, 31))
    p = clamp(local_time / max(duration, .001))
    template = scene.get("template", "workflow")
    handlers = {"workflow": _workflow, "compare": _compare,
                "counter": _counter, "kinetic": _kinetic}
    if template not in handlers:
        raise ValueError(f"Plantilla de motion desconocida: {template}")
    handlers[template](image, scene, p, primary, accent)
    if template != "kinetic" and scene.get("title"):
        multiline(image, scene["title"], (w * .5, h * .15), accent if scene.get("font") == "accent" else primary, w * .09, w * .86, color=scene.get("text_color", "white"))
    return image
