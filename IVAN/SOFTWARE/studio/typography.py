"""Closed text styles, measured local layout and seek-safe animation.

Pillow/RAQM measures the layout once. Native, SVG/GSAP and the editor consume
the same line coordinates. These are original editor presets, not CLONE
reconstructions or third-party commercial animation recipes.
"""
from __future__ import annotations

import copy
from functools import lru_cache
from importlib.metadata import version
import math
from pathlib import Path
import re
import struct
import unicodedata

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features
import regex
from fontTools.ttLib import TTFont, TTLibError

from . import core

PRESETS = ("none", "fade_up", "slide", "pop", "wipe", "typewriter", "word_reveal")
EXITS = ("none", "fade", "slide")
DEFAULT_STYLE = {"align": "left", "vertical_align": "top", "letter_spacing": 0,
                 "line_height": 1.15, "stroke": {"width": 0, "color": "#000000"},
                 "shadow": {"enabled": True, "x": 2, "y": 4, "blur": 0,
                            "color": "#000000", "opacity": .85}}
MAX_TEXT_UNITS = 2000
MAX_SCENE_TEXT_UNITS = 8000


def runtime_versions():
    return {"regex":version("regex"),"fontTools":version("fonttools"),"Pillow":version("Pillow"),
            "RAQM_available":features.check("raqm"),"RAQM":features.version("raqm"),
            "FreeType":features.version("freetype2"),"HarfBuzz":features.version("harfbuzz")}


def _closed(value, keys, label):
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value) or set(value) - set(keys):
        raise core.StudioError(label + " requiere un objeto de campos admitidos.")
    return value


def _color(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise core.StudioError(label + " requiere #RRGGBB.")
    return value


def normalize_style(style=None):
    value = _closed({} if style is None else style, DEFAULT_STYLE, "text_style")
    result = copy.deepcopy(DEFAULT_STYLE)
    for key in ("align", "vertical_align", "letter_spacing", "line_height"):
        if key in value:
            result[key] = value[key]
    if result["align"] not in ("left", "center", "right") or result["vertical_align"] not in ("top", "middle", "bottom"):
        raise core.StudioError("Alineación tipográfica no admitida.")
    core.finite_number(result["letter_spacing"], "espaciado a 1080 px", -16, 80)
    core.finite_number(result["line_height"], "interlineado", .8, 3)
    stroke = _closed(value.get("stroke", {}), ("width", "color"), "stroke")
    result["stroke"].update(stroke)
    core.finite_number(result["stroke"]["width"], "grosor de texto a 1080 px", 0, 16)
    _color(result["stroke"]["color"], "color del borde")
    shadow = _closed(value.get("shadow", {}), DEFAULT_STYLE["shadow"], "shadow")
    result["shadow"].update(shadow)
    if type(result["shadow"]["enabled"]) is not bool:
        raise core.StudioError("shadow.enabled debe ser booleano.")
    for key, lo, hi in (("x", -40, 40), ("y", -40, 40), ("blur", 0, 20), ("opacity", 0, 1)):
        core.finite_number(result["shadow"][key], "sombra " + key, lo, hi)
    _color(result["shadow"]["color"], "color de sombra")
    return result


def normalize_animation(element, scene_duration):
    core.finite_number(scene_duration, "duración escena de texto", 1e-7, 86400)
    value = _closed(element.get("text_animation", {}),
                    ("preset", "duration", "exit", "exit_duration", "clock_start", "clock_offset", "clock_duration"),
                    "text_animation")
    start = core.finite_number(element.get("start", 0), "inicio texto", 0, scene_duration)
    end = core.finite_number(element.get("end", scene_duration), "fin texto", 0, scene_duration)
    if end <= start:
        raise core.StudioError("El intervalo del texto requiere duración positiva.")
    result = {"preset": "none", "duration": .6, "exit": "none", "exit_duration": .2,
              "clock_start": start, "clock_offset": 0, "clock_duration": end - start, **value}
    if result["preset"] not in PRESETS or result["exit"] not in EXITS:
        raise core.StudioError("Preset de texto no admitido.")
    for key, lo, hi in (("duration", .01, 10), ("exit_duration", .01, 10),
                        ("clock_start", -86400, 86400), ("clock_offset", 0, 86400),
                        ("clock_duration", 1e-7, 86400)):
        core.finite_number(result[key], "animación " + key, lo, hi)
    active = (result["duration"] if result["preset"] != "none" else 0) + (result["exit_duration"] if result["exit"] != "none" else 0)
    if active > result["clock_duration"] + 1e-7:
        raise core.StudioError("Entrada y salida no caben en el reloj original del texto.")
    elapsed_start = start - result["clock_start"] + result["clock_offset"]
    elapsed_end = end - result["clock_start"] + result["clock_offset"]
    if elapsed_start < -1e-7 or elapsed_end > result["clock_duration"] + 1e-7:
        raise core.StudioError("La ventana visible del texto debe estar dentro de su reloj original.")
    return result


def graphemes(text):
    if not isinstance(text, str):
        raise core.StudioError("El texto requiere una cadena.")
    return regex.findall(r"\X", text)


def validate_text_element(element, scene_duration):
    if element.get("type") != "text":
        if any(key in element for key in ("font_asset_id", "text_style", "text_animation")):
            raise core.StudioError("Fuentes, estilos y presets pertenecen a elementos text.")
        return
    text = element.get("text")
    if not isinstance(text, str) or len(text) > 2000 or len(graphemes(text)) > MAX_TEXT_UNITS:
        raise core.StudioError("El texto admite hasta 2000 caracteres/grafemas.")
    asset_id = element.get("font_asset_id")
    if asset_id is not None and (not isinstance(asset_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", asset_id)):
        raise core.StudioError("font_asset_id requiere un ID de fuente válido.")
    normalize_style(element.get("text_style"))
    normalize_animation(element, scene_duration)


def _signature(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _unchanged_font(metadata, signature):
    try:
        unchanged = _signature(metadata["path"]) == signature and core.content_hash(metadata["path"]) == metadata["sha256"]
    except (OSError, core.StudioError) as error:
        raise core.StudioError("La fuente cambió durante la medición/dibujo; no se devuelve geometría inconsistente.",409) from error
    if not unchanged:
        raise core.StudioError("La fuente cambió durante la medición/dibujo; no se devuelve geometría inconsistente.",409)


@lru_cache(maxsize=64)
def _coverage(path, signature):
    with TTFont(path, lazy=True, fontNumber=0) as face:
        return frozenset((face.getBestCmap() or {}).keys())


def resolve_font(element, fonts, font_assets=None, root=None):
    root = core.ROOT if root is None else Path(root).resolve()
    asset_id = element.get("font_asset_id")
    if asset_id:
        from .fonts import validate_asset_font
        asset = (font_assets or {}).get(asset_id)
        if not isinstance(asset, dict) or asset.get("id") != asset_id:
            raise core.StudioError("La fuente seleccionada debe estar adjunta y verificada.")
        metadata = validate_asset_font(asset, root)
        path = core.confined(metadata["path"], root=root, must_exist=True)
        return {**metadata, "path": str(path), "font_asset_id": asset_id, "role": None}
    role = element.get("font", "primary")
    if role not in ("primary", "accent") or not isinstance(fonts, dict) or not fonts.get(role):
        raise core.StudioError("El texto requiere declarar la fuente primary o accent real.")
    path = core.confined(fonts[role], root=root, must_exist=True)
    if not path.is_relative_to(root / "assets" / "fonts"):
        raise core.StudioError("Las fuentes del texto deben quedar en assets/fonts.", 403)
    from .fonts import inspect_font
    signature = _signature(path)
    result = {**inspect_font(path,root),"path":str(path),"font_asset_id":None,"role":role,"synthetic_style":False}
    _unchanged_font(result,signature)
    return result


def _supported(text, path):
    try:
        coverage = _coverage(str(path), _signature(path))
    except (OSError, ValueError, KeyError, TTLibError, struct.error, AssertionError, IndexError, OverflowError) as error:
        raise core.StudioError("No se pudo comprobar el mapa de glifos de la fuente.") from error
    # HarfBuzz composes canonical accents. Joiners/variation selectors are
    # shaping controls, not evidence of a separate visible glyph.
    missing = sorted({ord(ch) for cluster in graphemes(text) for ch in unicodedata.normalize("NFC", cluster)
                      if not ch.isspace() and unicodedata.category(ch) != "Cf"
                      and not (0xFE00 <= ord(ch) <= 0xFE0F or 0xE0100 <= ord(ch) <= 0xE01EF)
                      and ord(ch) not in coverage})
    if missing:
        labels = ", ".join(f"U+{point:04X}" for point in missing[:12])
        raise core.StudioError("La fuente no contiene los glifos solicitados: " + labels + ". No se sustituye por otra.")


def layout_element(element, canvas_size, fonts, font_assets=None, root=None):
    width, height = canvas_size
    for value in (width, height):
        core.finite_number(value, "dimensión de lienzo de texto", 1, 8192)
    if width * height > 32_000_000:
        raise core.StudioError("El lienzo tipográfico supera el límite local de memoria.")
    text = element.get("text", "")
    if not isinstance(text, str) or len(text) > 2000:
        raise core.StudioError("El texto admite hasta 2000 caracteres.")
    style = normalize_style(element.get("text_style"))
    metadata = resolve_font(element, fonts, font_assets, root)
    signature = _signature(metadata["path"])
    _unchanged_font(metadata,signature)
    _supported(text, metadata["path"])
    scale = width / 1080
    size = core.finite_number(element.get("font_size", 84), "tamaño fuente", 8, 400)
    bw = core.finite_number(element.get("width", .25), "ancho texto", .005, 1)
    bh = core.finite_number(element.get("height", .25), "alto texto", .005, 1)
    box = (max(1, round(bw * width)), max(1, round(bh * height)))
    face = ImageFont.truetype(metadata["path"], max(1, round(size * scale)))
    ascent, descent = face.getmetrics()
    spacing = style["letter_spacing"] * scale
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    clusters = graphemes(normalized)
    if len(clusters) > MAX_TEXT_UNITS:
        raise core.StudioError("El texto expandido admite hasta 2000 grafemas.")
    painted = [cluster for cluster in clusters if not cluster.isspace()]
    bearings = [face.getbbox(cluster,anchor="ls") for cluster in painted]
    stroke = style["stroke"]["width"] * scale
    shadow = style["shadow"]
    radius = shadow["blur"]*scale*3 if shadow["enabled"] and shadow["opacity"] else 0
    dx = shadow["x"]*scale if shadow["enabled"] and shadow["opacity"] else 0
    dy = shadow["y"]*scale if shadow["enabled"] and shadow["opacity"] else 0
    left_bearing = max([0]+[-bbox[0] for bbox in bearings])
    right_bearing = max([0]+[bbox[2]-face.getlength(cluster) for cluster,bbox in zip(painted,bearings)])
    padding = {"left":left_bearing+stroke+max(0,radius-dx),
               "right":right_bearing+stroke+max(0,radius+dx),
               "top":stroke+max(0,radius-dy),"bottom":stroke+max(0,radius+dy)}
    em_ascent = max([ascent]+[-bbox[1] for bbox in bearings])
    em_descent = max([descent]+[bbox[3] for bbox in bearings])
    available_width = box[0]-padding["left"]-padding["right"]
    if available_width <= 0:
        raise core.StudioError("El borde/sombra no deja espacio para el texto; amplía la caja o reduce el estilo.")
    tokens, current, word = [], [], -1
    in_word = False
    for index, cluster in enumerate(clusters):
        white = cluster.isspace()
        if not white and not in_word:
            word += 1
        in_word = not white
        unit = {"text": cluster, "index": index, "word_index": -1 if white else word}
        if cluster == "\n":
            if current:
                tokens.append(current)
                current = []
            tokens.append([unit])
        elif current and current[-1]["text"].isspace() != white:
            tokens.append(current)
            current = [unit]
        else:
            current.append(unit)
    if current:
        tokens.append(current)
    def line_width(units):
        return face.getlength("".join(unit["text"] for unit in units)) + max(0, len(units)-1) * spacing
    raw_lines, current = [], []
    for token in tokens:
        if token[0]["text"] == "\n":
            raw_lines.append(current)
            current = []
        elif current and not token[0]["text"].isspace() and line_width(current + token) > available_width:
            raw_lines.append(current)
            current = token.copy()
        else:
            current.extend(token)
    raw_lines.append(current)
    step = max(1, round(face.size * style["line_height"]))
    line_boxes = []
    for index, units in enumerate(raw_lines):
        value = "".join(unit["text"] for unit in units)
        bounds = face.getbbox(value or "Mg", anchor="ls")
        advance = max(0, line_width(units))
        x = padding["left"] + (0 if style["align"] == "left" else (available_width-advance)/2 if style["align"] == "center" else available_width-advance)
        baseline = padding["top"] + index * step + em_ascent
        prefix = ""
        placed = []
        for j, unit in enumerate(units):
            prefix += unit["text"]
            offset = face.getlength(prefix) - face.getlength(unit["text"]) + j * spacing
            placed.append({**unit, "x": x + offset})
        if spacing and any(b["x"] <= a["x"] for a,b in zip(placed,placed[1:])):
            raise core.StudioError("El espaciado produce avances de glifos no positivos; aumenta el tamaño o el espaciado.")
        line_boxes.append({"text": value, "x": x, "baseline": baseline,
                           "width": advance, "paint_bounds": list(bounds), "units": placed})
    painted_height = padding["top"]+em_ascent+em_descent+max(0,len(line_boxes)-1)*step+padding["bottom"]
    vertical = 0 if style["vertical_align"] == "top" else (box[1]-painted_height)/2 if style["vertical_align"] == "middle" else box[1]-painted_height
    for line in line_boxes:
        line["baseline"] += vertical
    overflow = any(line["width"] > available_width + .01 for line in line_boxes) or painted_height > box[1] + .01
    ink = []
    stroke = style["stroke"]["width"] * scale
    shadow = style["shadow"]
    for line in line_boxes:
        runs = [(line["x"],line["text"])] if style["letter_spacing"] == 0 else [(unit["x"],unit["text"]) for unit in line["units"]]
        for x,value in runs:
            if not value.strip():
                continue
            bounds = face.getbbox(value,anchor="ls")
            item = [x+bounds[0]-stroke,line["baseline"]+bounds[1]-stroke,x+bounds[2]+stroke,line["baseline"]+bounds[3]+stroke]
            ink.append(item)
            if shadow["enabled"] and shadow["opacity"]:
                # Gaussian blur has unbounded mathematical support. Three
                # sigma is an inspection estimate, not a pixel-perfect bound.
                radius=shadow["blur"]*scale*3
                ink.append([item[0]+shadow["x"]*scale-radius,item[1]+shadow["y"]*scale-radius,
                            item[2]+shadow["x"]*scale+radius,item[3]+shadow["y"]*scale+radius])
    ink_bounds = [min(v[0] for v in ink),min(v[1] for v in ink),max(v[2] for v in ink),max(v[3] for v in ink)] if ink else None
    ink_overflow = bool(ink_bounds and (ink_bounds[0]<-.01 or ink_bounds[1]<-.01 or ink_bounds[2]>box[0]+.01 or ink_bounds[3]>box[1]+.01))
    result = {"width": box[0], "height": box[1], "reference_scale": scale,
            "font_px": face.size, "ascent": ascent, "descent": descent,
            "padding":padding,"em_ascent":em_ascent,"em_descent":em_descent,"content_height":painted_height,
            "font": {key: metadata.get(key) for key in ("family", "style", "sha256", "font_asset_id", "role", "synthetic_style")},
            "style": style, "color": _color(element.get("color", "#ffffff"), "color texto"),
            "grapheme_count": len(clusters), "word_count": word+1, "lines": line_boxes,
            "overflow": overflow, "overflow_policy": "clip to declared box; no silent font shrink",
            "ink_bounds":ink_bounds,"ink_overflow":ink_overflow,
            "warnings":[message for condition,message in ((overflow,"El texto excede su caja y se recorta."),(ink_overflow,"Glifos, borde o sombra rozan/exceden la caja; revisar recorte.")) if condition],
            "runtime": runtime_versions(),
            "layout_engine": "Pillow/RAQM measured baselines; regex extended graphemes; tab size4"}
    _unchanged_font(metadata,signature)
    return result


def _clamp(value):
    return min(1, max(0, value))


def animation_state(element, time, scene_duration, layout=None):
    core.finite_number(time, "tiempo tipográfico", -86400, 86400)
    animation = normalize_animation(element, scene_duration)
    elapsed = time - animation["clock_start"] + animation["clock_offset"]
    u = _clamp(elapsed / animation["duration"])
    ease = 1 - (1-u)**3
    state = {"opacity": 1., "x": 0., "y": 0., "scale": 1., "wipe": 1.,
             "reveal_mode": "none", "reveal_fraction": 1.}
    preset = animation["preset"]
    if preset == "fade_up":
        state.update(y=36*(1-ease), opacity=u)
    elif preset == "slide":
        state.update(x=-48*(1-ease), opacity=u)
    elif preset == "pop":
        state.update(scale=.86+.14*(1-(1-u)**4), opacity=u)
    elif preset == "wipe":
        state["wipe"] = u
    elif preset in ("typewriter", "word_reveal"):
        state.update(reveal_mode="grapheme" if preset == "typewriter" else "word", reveal_fraction=u)
    v = _clamp((elapsed-(animation["clock_duration"]-animation["exit_duration"]))/animation["exit_duration"])
    if animation["exit"] != "none":
        state["opacity"] *= 1-v
        if animation["exit"] == "slide":
            eased = 4*v**3 if v < .5 else 1-4*(1-v)**3
            state["y"] += 32*eased
    return state


def line_prefix(line, state, layout):
    mode = state["reveal_mode"]
    count = layout["grapheme_count"] if mode == "grapheme" else layout["word_count"]
    visible = count if state["reveal_fraction"] >= 1 else math.floor(count*state["reveal_fraction"]+1e-10)
    return "".join(unit["text"] for unit in line["units"] if mode == "none" or
                   (unit["index"] < visible if mode == "grapheme" else unit["word_index"] < visible))


def _rgba(color, alpha=255):
    return tuple(int(color[i:i+2],16) for i in (1,3,5)) + (alpha,)


def draw_text(element, canvas_size, fonts, font_assets=None, root=None,
              time=0, scene_duration=1, animate=True):
    layout = layout_element(element, canvas_size, fonts, font_assets, root)
    metadata = resolve_font(element, fonts, font_assets, root)
    if metadata["sha256"] != layout["font"]["sha256"]:
        raise core.StudioError("La fuente cambió entre medición y dibujo.",409)
    signature = _signature(metadata["path"])
    _unchanged_font(metadata,signature)
    face = ImageFont.truetype(metadata["path"], layout["font_px"])
    style, scale = layout["style"], layout["reference_scale"]
    state = animation_state(element, time, scene_duration) if animate else {"opacity":1,"x":0,"y":0,"scale":1,"wipe":1,"reveal_mode":"none","reveal_fraction":1}
    size = (layout["width"], layout["height"])
    stroke = round(style["stroke"]["width"] * scale)
    mask = Image.new("L", size)
    md = ImageDraw.Draw(mask)
    placed_runs = []
    for line in layout["lines"]:
        prefix = line_prefix(line, state, layout)
        runs = [(line["x"], prefix)]
        if style["letter_spacing"] != 0:
            mode = state["reveal_mode"]
            count = layout["grapheme_count"] if mode == "grapheme" else layout["word_count"]
            limit = count if state["reveal_fraction"] >= 1 else math.floor(count*state["reveal_fraction"]+1e-10)
            runs = [(unit["x"],unit["text"]) for unit in line["units"] if mode == "none" or (unit["index"] < limit if mode == "grapheme" else unit["word_index"] < limit)]
        for x, text in runs:
            placed_runs.append((x,line["baseline"],text))
            md.text((x,line["baseline"]),text,font=face,anchor="ls",fill=255,stroke_width=stroke,stroke_fill=255)
    tile = Image.new("RGBA", size)
    shadow = style["shadow"]
    if shadow["enabled"] and shadow["opacity"]:
        if not shadow["blur"]:
            sd = ImageDraw.Draw(tile)
            color = _rgba(shadow["color"],round(shadow["opacity"]*255))
            for x,y,text in placed_runs:
                sd.text((x+shadow["x"]*scale,y+shadow["y"]*scale),text,font=face,anchor="ls",fill=color,stroke_width=stroke,stroke_fill=color)
        else:
            shifted = Image.new("L", size)
            shifted.paste(mask,(round(shadow["x"]*scale),round(shadow["y"]*scale)))
            shifted = shifted.filter(ImageFilter.GaussianBlur(shadow["blur"]*scale))
            shifted = shifted.point(lambda a:round(a*shadow["opacity"]))
            layer = Image.new("RGBA",size,_rgba(shadow["color"]))
            layer.putalpha(shifted)
            tile.alpha_composite(layer)
    draw = ImageDraw.Draw(tile)
    for x,y,text in placed_runs:
        draw.text((x,y),text,font=face,anchor="ls",fill=layout["color"],stroke_width=stroke,stroke_fill=style["stroke"]["color"])
    if state["wipe"] < 1:
        from PIL import ImageChops
        mask=Image.new("L",size)
        if state["wipe"] > 0:
            ImageDraw.Draw(mask).rectangle((0,0,max(0,round(size[0]*state["wipe"])-1),size[1]-1),fill=255)
        tile.putalpha(ImageChops.multiply(tile.getchannel("A"),mask))
    factor=state["scale"]
    scaled=tile.resize((max(1,round(size[0]*factor)),max(1,round(size[1]*factor))),Image.Resampling.LANCZOS)
    result=Image.new("RGBA",size)
    result.alpha_composite(scaled,(round((size[0]-scaled.width)/2+state["x"]*scale),round((size[1]-scaled.height)/2+state["y"]*scale)))
    if state["opacity"] != 1:
        result.putalpha(result.getchannel("A").point(lambda a:round(a*state["opacity"])))
    _unchanged_font(metadata,signature)
    return result


def catalog():
    return {"version":1,"presets":list(PRESETS),"exits":list(EXITS),"style_defaults":copy.deepcopy(DEFAULT_STYLE),
            "animation_defaults":{"preset":"none","duration":.6,"exit":"none","exit_duration":.2},
            "clock":"elapsed=scene_time-clock_start+clock_offset; clock_duration is the original visible interval, materialize before trim",
            "units":"geometry normalized; font_size, spacing, stroke, shadow and preset offsets are px at canvas width1080",
            "claim":"Original deterministic editor presets; no CLONE fidelity or editorial approval."}


CLIENT_JS = r'''(function(global){"use strict";
 const clamp=v=>Math.max(0,Math.min(1,v));
 function animationState(el,time,duration){
  const a=el.text_animation||{},start=el.start??0,end=el.end??duration;
  const d=a.duration??.6,exitd=a.exit_duration??.2,span=a.clock_duration??(end-start);
  const elapsed=time-(a.clock_start??start)+(a.clock_offset??0),u=clamp(elapsed/d),p=a.preset||'none',v=clamp((elapsed-(span-exitd))/exitd);
  const state={opacity:1,x:0,y:0,scale:1,wipe:1,reveal_mode:'none',reveal_fraction:1};
  if(p==='fade_up'){state.y=36*Math.pow(1-u,3);state.opacity=u;}
  else if(p==='slide'){state.x=-48*Math.pow(1-u,3);state.opacity=u;}
  else if(p==='pop'){state.scale=.86+.14*(1-Math.pow(1-u,4));state.opacity=u;}
  else if(p==='wipe')state.wipe=u;
  else if(p==='typewriter'||p==='word_reveal'){state.reveal_mode=p==='typewriter'?'grapheme':'word';state.reveal_fraction=u;}
  if(a.exit&&a.exit!=='none'){state.opacity*=1-v;if(a.exit==='slide')state.y+=32*(v<.5?4*v*v*v:1-4*Math.pow(1-v,3));}
  return state;
 }
 function visible(unit,state,layout){const mode=state.reveal_mode,n=mode==='grapheme'?layout.grapheme_count:layout.word_count,limit=state.reveal_fraction>=1?n:Math.floor(n*state.reveal_fraction+1e-10);return mode==='none'||(mode==='grapheme'?unit.index<limit:unit.word_index<limit);}
 function paintTextLayout(ctx,layout,state,options={}){
  const style=layout.style,k=layout.reference_scale,shadow=style.shadow,stroke=style.stroke;
  ctx.save();ctx.beginPath();ctx.rect(0,0,layout.width,layout.height);ctx.clip();
  ctx.translate(layout.width/2+state.x*k,layout.height/2+state.y*k);ctx.scale(state.scale,state.scale);ctx.translate(-layout.width/2,-layout.height/2);
  ctx.beginPath();ctx.rect(0,0,layout.width*state.wipe,layout.height);ctx.clip();ctx.globalAlpha*=state.opacity;
  ctx.font=`${options.fontItalic?'italic ':''}${layout.font_px}px "${options.fontFamily||'AscendiaPrimary'}"`;ctx.textAlign='left';ctx.textBaseline='alphabetic';ctx.fillStyle=layout.color;
  const render=()=>{for(const line of layout.lines){const units=line.units.filter(unit=>visible(unit,state,layout));if(style.letter_spacing===0){const text=units.map(unit=>unit.text).join('');if(stroke.width){ctx.lineWidth=stroke.width*k*2;ctx.strokeStyle=stroke.color;ctx.strokeText(text,line.x,line.baseline);}ctx.fillText(text,line.x,line.baseline);}else for(const unit of units){if(stroke.width){ctx.lineWidth=stroke.width*k*2;ctx.strokeStyle=stroke.color;ctx.strokeText(unit.text,unit.x,line.baseline);}ctx.fillText(unit.text,unit.x,line.baseline);}}};
  if(shadow.enabled&&shadow.opacity){ctx.save();ctx.translate(shadow.x*k,shadow.y*k);ctx.globalAlpha*=shadow.opacity;ctx.fillStyle=shadow.color;ctx.filter=shadow.blur?`blur(${shadow.blur*k}px)`:'none';for(const line of layout.lines){const units=line.units.filter(unit=>visible(unit,state,layout));const runs=style.letter_spacing===0?[{text:units.map(unit=>unit.text).join(''),x:line.x}]:units;for(const run of runs){if(stroke.width){ctx.lineWidth=stroke.width*k*2;ctx.strokeStyle=shadow.color;ctx.strokeText(run.text,run.x,line.baseline);}ctx.fillText(run.text,run.x,line.baseline);}}ctx.restore();}
  render();ctx.restore();
 }
 global.AscendiaTypography={animationState,paintTextLayout};
})(typeof window!=='undefined'?window:globalThis);'''
