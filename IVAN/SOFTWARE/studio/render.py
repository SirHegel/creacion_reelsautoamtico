"""CPU render engine for the editable ASCENDIA timeline.

All assets, exports, evidence, and temporary files are confined to SOFTWARE.
The engine produces a candidate, never an editorial approval. Rendering does
not certify semantic pertinence, face safety, permissions, or heard audio.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageStat

from . import motion

_RENDER_LOCK = threading.Lock()
_FORMATS = ("mov,matroska,avi,mpegts,mpeg,mxf,ogg,mp3,wav,flac,aac,"
            "image2,png_pipe,jpeg_pipe,webp_pipe,gif,bmp_pipe,tiff_pipe,"
            "aiff,asf,flv,amr,ac3,eac3,au,ape,mp4,m4v,h264,hevc")
_OVERLAY_IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


class RenderError(ValueError):
    pass


class RenderCancelled(RenderError):
    pass


def confined(root: Path, value, *, exists=False) -> Path:
    root = Path(root).resolve()
    path = Path(value)
    target = (path if path.is_absolute() else root / path).resolve()
    if not target.is_relative_to(root):
        raise RenderError("La ruta sale de SOFTWARE.")
    if exists and not target.is_file():
        raise RenderError(f"No existe el archivo local: {target.relative_to(root)}")
    return target


def _environment(root):
    cache = confined(root, ".estado/render")
    cache.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(TMPDIR=str(cache), TEMP=str(cache), TMP=str(cache),
               XDG_CACHE_HOME=str(confined(root, ".estado/cache")),
               PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1",
               OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    return env


def _cancelled(cancel):
    return bool(cancel and (cancel.is_set() if hasattr(cancel, "is_set") else cancel()))


def _process_command(args):
    command = [str(item) for item in args]
    nice = shutil.which("nice")
    if nice and Path(command[0]).name in {"ffmpeg", "ffprobe"}:
        return [nice, "-n", "10"] + command
    return command


def _run(args, root, cancel=None, timeout=1200, return_stderr=False):
    import time
    process = subprocess.Popen(_process_command(args), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=root,
                               env=_environment(root), shell=False)
    begin = time.monotonic()
    try:
        while True:
            if _cancelled(cancel):
                raise RenderCancelled("Render cancelado.")
            if time.monotonic() - begin > timeout:
                raise RenderError("La operación local excedió el tiempo permitido.")
            try:
                out, err = process.communicate(timeout=.25)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            message = err.decode("utf-8", "replace")[-3000:]
            raise RenderError(f"Falló FFmpeg/FFprobe: {message}")
        return (out, err) if return_stderr else out
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for stream in (process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()


def _tool(name):
    binary = shutil.which(name)
    if not binary:
        raise RenderError(f"Falta {name} en el entorno local.")
    return binary


def _input(path):
    # Disallow URLs, HLS/playlists, and remote nested protocols.
    return ["-protocol_whitelist", "file,pipe", "-format_whitelist", _FORMATS,
            "-threads", "1", "-i", str(path)]


def split_height(height, ratio=.55):
    """Even regions with the same half-up rounding as the browser canvas.

    Missing project settings preserve the legacy 55/45 ratio; new SaaS
    projects explicitly store 50/50. Changing layout never resets face time.
    """
    if type(height) not in (int, float) or not math.isfinite(height) or height < 4 or height % 2:
        raise RenderError('El alto del split requiere píxeles pares.')
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or not .5 <= ratio <= .55:
        raise RenderError('La proporción superior del split debe estar entre .50 y .55.')
    return 2 * math.floor(height * ratio / 2 + .5)


def probe_media(path: Path, root: Path | None = None) -> dict:
    root = Path(root or Path(path).parent).resolve()
    path = confined(root, path, exists=True)
    raw = _run([_tool("ffprobe"), "-v", "error", "-protocol_whitelist", "file,pipe",
                "-format_whitelist", _FORMATS, "-show_format", "-show_streams",
                "-of", "json", str(path)], root, timeout=60)
    info = json.loads(raw)
    info["duration"] = float(info.get("format", {}).get("duration", 0) or 0)
    return info


def _number(value, name, low, high):
    if isinstance(value, bool):
        raise RenderError(f"{name} debe ser un número, no un booleano.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise RenderError(f"{name} debe ser un número.") from None
    if not math.isfinite(number) or not low <= number <= high:
        raise RenderError(f"{name} fuera de rango ({low}–{high}).")
    return number


def _prepare_overlays(scene, assets, source, root, ancestry=None):
    from .core import source_related
    layers = scene.get("overlays", [])
    if not isinstance(layers, list) or len(layers) > 8:
        raise RenderError("Cada escena admite hasta ocho capas superpuestas.")
    duration = scene["_planned_end"] - scene["start"]
    seen, result = set(), []
    for layer in layers:
        if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or not layer["id"] or layer["id"] in seen:
            raise RenderError("Cada capa necesita un ID único en su escena.")
        seen.add(layer["id"])
        asset_id = layer.get("asset_id")
        if not isinstance(asset_id, str) or asset_id not in assets:
            raise RenderError("Una capa referencia un recurso inexistente.")
        asset = assets[asset_id]
        if (source_related(asset, source, ancestry or assets) or asset["local"].samefile(source["local"])):
            raise RenderError("El crudo original no se puede duplicar ni ocultar como capa.")
        start = _number(layer.get("start", 0), "Entrada local de capa", 0, duration)
        end = _number(layer.get("end", duration), "Salida local de capa", 0, duration)
        if end <= start:
            raise RenderError("La salida de la capa debe ser posterior a su entrada.")
        x = _number(layer.get("x", 0), "Posición X de capa", 0, 1)
        y = _number(layer.get("y", 0), "Posición Y de capa", 0, 1)
        width = _number(layer.get("width", .3), "Ancho normalizado de capa", .001, 1)
        height = _number(layer.get("height", .3), "Alto normalizado de capa", .001, 1)
        if x + width > 1.000001 or y + height > 1.000001:
            raise RenderError("La caja base de la capa debe quedar dentro de la pantalla.")
        opacity = _number(layer.get("opacity", 1), "Opacidad de capa", 0, 1)
        source_in = _number(layer.get("source_in", 0), "Entrada del medio de capa", 0, 7200)
        if layer.get("blend", "normal") not in {"normal", "screen"}:
            raise RenderError("Modo de mezcla de capa no admitido.")
        frames = layer.get("keyframes", [])
        if not isinstance(frames, list) or len(frames) > 500:
            raise RenderError("Keyframes de capa inválidos o demasiado numerosos.")
        for keyframe in frames:
            if not isinstance(keyframe, dict):
                raise RenderError("Cada keyframe de capa debe ser un objeto.")
            _number(keyframe.get("time", -1), "Tiempo local de keyframe de capa", 0, end - start)
            for key, default, low, high in (("x", 0, -1, 1), ("y", 0, -1, 1),
                                          ("scale", 1, .1, 4), ("opacity", 1, 0, 1)):
                _number(keyframe.get(key, default), "Keyframe de capa " + key, low, high)
        info = asset.get("_overlay_info")
        if info is None:
            info = probe_media(asset["local"], root)
            asset["_overlay_info"] = info
        if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
            raise RenderError("El medio de una capa no contiene imagen o video decodificable.")
        is_image = asset["local"].suffix.lower() in _OVERLAY_IMAGES
        if is_image and source_in != 0:
            raise RenderError("Una imagen estática usa entrada de medio cero.")
        if asset.get("kind") == "image" and not is_image:
            raise RenderError("Las capas de imagen admiten PNG, JPG, WebP, BMP y TIFF.")
        if not is_image and (info["duration"] <= 0 or source_in + end - start > info["duration"] + .03):
            raise RenderError("El tramo planificado de una capa excede el clip; no se repite ni se congela.")
        result.append({**layer, "start": start, "end": end, "source_in": source_in,
                       "x": x, "y": y, "width": width, "height": height,
                       "opacity": opacity, "blend": layer.get("blend", "normal"),
                       "keyframes": frames, "_static_image": is_image})
    return result


def _prepare(project, root, seconds):
    from . import core
    if not isinstance(project, dict):
        raise RenderError("Proyecto inválido.")
    from .scene_ir import validate_brand_media
    try:
        validate_brand_media(project, root)
    except core.StudioError as error:
        raise RenderError(str(error)) from error
    settings = project.get("settings", {})
    w = int(_number(settings.get("width", 1080), "Ancho", 64, 3840))
    h = int(_number(settings.get("height", 1920), "Alto", 64, 3840))
    fps = _number(settings.get("fps", 30), "FPS", 1, 60)
    hook_seconds = _number(project.get("style", {}).get("hook_seconds", 4.5), "Duración del hook", 4, 6)
    if w % 2 or h % 2:
        raise RenderError("H.264 requiere ancho y alto pares.")
    seconds = _number(seconds, "Duración", .05, 7200)
    fonts = project.get("fonts", {})
    primary = confined(root, fonts.get("primary", ""), exists=True)
    accent = confined(root, fonts.get("accent", ""), exists=True)
    try:
        motion.font(str(primary), 24)
        motion.font(str(accent), 24)
    except OSError as error:
        raise RenderError("Los archivos de fuentes no son válidos.") from error
    assets = {}
    for asset in project.get("assets", []):
        if not isinstance(asset, dict) or not asset.get("id") or asset["id"] in assets:
            raise RenderError("IDs de recursos ausentes o repetidos.")
        assets[asset["id"]] = {**asset, "local": confined(root, asset.get("path", ""), exists=True)}
    branding = None
    if project.get("style", {}).get("branding") is not None:
        from .branding import validate_project_binding
        try:
            branding = validate_project_binding(project, root)
        except core.StudioError as error:
            raise RenderError(str(error)) from error
    from .fonts import font_assets as verify_font_assets
    try:
        font_assets = verify_font_assets(project, root)
    except core.StudioError as error:
        raise RenderError(str(error)) from error
    if branding:
        from .fonts import validate_asset_font
        for face in branding['fonts'].values():
            item=assets.get(face['asset_id'])
            validate_asset_font(item,root)
            font_assets[face['asset_id']]=item
    source = assets.get(project.get("source"))
    if not source:
        raise RenderError("Falta el crudo original del proyecto.")
    ancestry = dict(assets)
    if root.resolve() == core.ROOT.resolve():
        ancestry.update({a["id"]: a for a in core.assets()})
    source_info = probe_media(source["local"], root)
    if not any(stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic") for stream in source_info.get("streams", [])):
        raise RenderError("El crudo debe contener video.")
    available = source_info["duration"]
    if available <= 0:
        raise RenderError("No se pudo medir la duración del crudo.")
    timeline = sorted(project.get("timeline", []), key=lambda scene: float(scene.get("start", 0)))
    if not timeline:
        raise RenderError("La cronología está vacía.")
    planned = float(timeline[-1].get("end", 0))
    requested_duration = min(seconds, available, planned)
    frame_count = max(1, math.ceil(requested_duration * fps - 1e-8))
    duration = frame_count / fps
    scenes, cursor, face_start = [], 0.0, None
    for scene in timeline:
        start = _number(scene.get("start", -1), "Entrada de escena", 0, 7200)
        end = _number(scene.get("end", -1), "Salida de escena", 0, 7200)
        if start >= requested_duration - 1e-8:
            break
        if end <= start or abs(start - cursor) > .0001:
            raise RenderError("La cronología tiene huecos, solapamientos o duraciones inválidas.")
        kind = scene.get("type")
        if kind not in {"presenter", "split", "broll", "motion"}:
            raise RenderError(f"Tipo de escena desconocido: {kind}")
        scene = {**scene, "start": start, "end": min(end, requested_duration), "_planned_end": end}
        if kind in {"presenter", "split"}:
            if face_start is None:
                face_start = start
            if scene["end"] - face_start > 3.001:
                raise RenderError("El rostro excede tres segundos continuos, incluido split.")
        else:
            face_start = None
        asset_id = scene.get("asset_id")
        if kind == "broll" and not asset_id:
            raise RenderError("La escena b-roll necesita un recurso real.")
        if kind == "broll" and core.source_related(assets.get(asset_id), source, ancestry):
            raise RenderError("El crudo del presentador no se puede ocultar como b-roll.")
        if asset_id and asset_id not in assets:
            raise RenderError("La escena referencia un recurso inexistente.")
        if kind == "split" and core.source_related(assets.get(asset_id), source, ancestry):
            raise RenderError("El split no admite duplicar el crudo en ambas regiones.")
        transition_id = scene.get("transition_asset_id")
        if transition_id:
            if transition_id not in assets:
                raise RenderError("La transición referencia un recurso inexistente.")
            if core.source_related(assets[transition_id], source, ancestry):
                raise RenderError("El crudo o sus derivados no se pueden ocultar en una transición.")
            _number(scene.get("transition_duration", .5), "Duración de burn", .3, 1)
            _number(scene.get("transition_source_in", 0), "Entrada de burn", 0, 7200)
        if kind in {"presenter", "split"} and start >= hook_seconds:
            _number(scene.get("chin_y", -1), "Barbilla normalizada", 0, .95)
        for keyframe in scene.get("keyframes", []):
            _number(keyframe.get("time", -1), "Tiempo de keyframe", 0, end - start)
            for key, default, low, high in (("x", 0, -1, 1), ("y", 0, -1, 1),
                                          ("scale", 1, .1, 4), ("opacity", 1, 0, 1)):
                _number(keyframe.get(key, default), key, low, high)
        scene["overlays"] = _prepare_overlays(scene, assets, source, root, ancestry)
        _camera_anchors(scene)
        scene["_design_media"] = []
        design_height = split_height(h, project['settings'].get('split_motion_ratio', .55)) if kind == "split" else h
        scene["_design_size"] = (w, design_height)
        if scene.get("motion_design") is not None or scene.get("template") == "custom":
            from .design import validate_design
            from .core import StudioError
            try:
                validate_design({**scene, "end": scene["_planned_end"]}, (w, design_height))
            except (ValueError, StudioError) as error:
                raise RenderError(str(error)) from error
            for element in scene.get("motion_design", {}).get("elements", []):
                if element["type"] != "media":
                    continue
                item = assets.get(element.get("asset_id"))
                if not item:
                    raise RenderError("Un elemento del diseño referencia un recurso inexistente.")
                if (core.source_related(item, source, ancestry) or item["local"].samefile(source["local"])):
                    raise RenderError("El crudo no se puede ocultar dentro de una composición motion.")
                info = probe_media(item["local"], root)
                image = item["local"].suffix.lower() in _OVERLAY_IMAGES
                if not any(stream.get("codec_type") == "video" and (image or not stream.get("disposition", {}).get("attached_pic")) for stream in info.get("streams", [])):
                    raise RenderError("El elemento requiere imagen o video decodificable.")
                entry = element.get("source_in", 0)
                span = element.get("end", end - start) - element.get("start", 0)
                if image and entry != 0:
                    raise RenderError("Una imagen del diseño requiere entrada cero.")
                if not image and entry + span > info["duration"] + .03:
                    raise RenderError("El elemento solicita un tramo que supera el medio.")
                scene["_design_media"].append({**element, "_static_image": image})
            expected_bytes = sum(round(w * e.get("width", .25)) * round(design_height * e.get("height", .25)) * 4 * (1 if e["_static_image"] else math.ceil((e.get("end", end - start) - e.get("start", 0)) * fps)) for e in scene["_design_media"])
            if expected_bytes > 4 * 1024 ** 3:
                raise RenderError("Los medios de esta composición superarían 4 GiB de temporales; reduce resolución, duración o capas simultáneas.")
        scenes.append(scene)
        cursor = end
    if cursor + .0001 < requested_duration:
        raise RenderError("La cronología no cubre la duración solicitada.")
    return {"width": w, "height": h, "fps": fps, "duration": duration, "requested_duration": requested_duration,
            "frames": frame_count, "primary": str(primary), "accent": str(accent),
            "assets": assets, "font_assets": font_assets, "branding": branding, "source": source, "source_info": source_info, "scenes": scenes,
            "hook_seconds": hook_seconds, "split_height": split_height(h, project['settings'].get('split_motion_ratio', .55))}


def _camera_anchors(scene):
    anchors=scene.get('camera_anchors',[])
    if not isinstance(anchors,list) or len(anchors)>300 or anchors and scene.get('type') not in {'presenter','split'}:
        raise RenderError('Anclas faciales inválidas.')
    previous=-1
    for frame in anchors:
        if not isinstance(frame,dict) or set(frame)!={'time','focus_x','focus_y','chin_y'}:
            raise RenderError('Las anclas faciales admiten únicamente tiempo y coordenadas numéricas.')
        at=_number(frame['time'],'tiempo facial',0,float(scene.get('_planned_end',scene['end']))-scene['start'])
        if at-previous<1e-6:raise RenderError('Las anclas faciales deben estar ordenadas con separación mínima de un microsegundo.')
        previous=at
        for key in ('focus_x','focus_y','chin_y'):_number(frame[key],key,0,1)
    return anchors


def _camera_state(scene, local):
    anchors=_camera_anchors(scene)
    if not anchors:return scene
    if local<=anchors[0]['time']:return anchors[0]
    for left,right in zip(anchors,anchors[1:]):
        if local<right['time']:
            u=(local-left['time'])/(right['time']-left['time'])
            return {key:left[key]+(right[key]-left[key])*u for key in ('focus_x','focus_y','chin_y')}
    return anchors[-1]


def _decode(asset, target, source_in, count, fps, destination, root, scene, cancel):
    info = probe_media(asset["local"], root)
    if not any(stream.get("codec_type") == "video" for stream in info.get("streams", [])):
        raise RenderError("Un recurso visual no contiene una pista de video.")
    source_in = _number(source_in, "Entrada del recurso", 0, 7200)
    is_image = asset.get("kind") == "image" or asset["local"].suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    if not is_image and source_in + (count - 1) / fps > info["duration"] + .03:
        raise RenderError("El tramo solicitado excede el recurso; no se congela ni se repite.")
    w, h = target
    focus_x = _number(scene.get("focus_x", .5), "Foco X", 0, 1)
    focus_y = _number(scene.get("focus_y", .5), "Foco Y", 0, 1)
    scale = f"scale={w}:{h}:force_original_aspect_ratio=increase"
    anchors = _camera_anchors(scene)
    if anchors:
        offset = source_in - float(scene.get("source_in",scene.get("start",0)))
        def expression(key):
            clock=f"(n/{fps:.8f}+{offset:.8f})"
            result=f"{anchors[-1][key]:.8f}"
            for left,right in reversed(list(zip(anchors,anchors[1:]))):
                lo,hi=left['time'],right['time']
                part=f"({left[key]:.8f}+({right[key]-left[key]:.8f})*({clock}-{lo:.8f})/{hi-lo:.8f})"
                result=f"if(lt({clock},{hi:.8f}),{part},{result})"
            return f"if(lt({clock},{anchors[0]['time']:.8f}),{anchors[0][key]:.8f},{result})"
        crop=f"crop={w}:{h}:x='(iw-ow)*({expression('focus_x')})':y='(ih-oh)*({expression('focus_y')})'"
    else:
        crop = f"crop={w}:{h}:(iw-ow)*{focus_x:.6f}:(ih-oh)*{focus_y:.6f}"
    filters = f"fps={fps:.8f},scale=round(iw*sar):ih,setsar=1,{scale},{crop},setsar=1,format=rgb24"
    args = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-filter_threads", "1"]
    if is_image:
        args += ["-loop", "1"]
    args += ["-ss", f"{source_in:.8f}"] + _input(asset["local"])
    args += ["-an", "-sn", "-dn", "-vf", filters, "-frames:v", str(count),
             "-threads", "1", "-f", "rawvideo", str(destination)]
    _run(args, root, cancel)
    expected = w * h * 3 * count
    if destination.stat().st_size != expected:
        raise RenderError("La decodificación no produjo todos los fotogramas del tramo.")
    return info


def _decode_overlay(asset, target, source_in, count, fps, destination, root, is_image, cancel):
    """Preserve genuine source alpha, and contain inside a transparent box."""
    w, h = target
    args = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-filter_threads", "1"]
    if is_image:
        args += ["-loop", "1"]
        # A static image needs one decoded RGBA frame, rather than hundreds
        # of identical raw frames. It is reused only while its layer is active.
        count, source_in = 1, 0
    args += ["-ss", f"{source_in:.8f}"] + _input(asset["local"])
    filters = (f"fps={fps:.8f},format=rgba,scale={w}:{h}:force_original_aspect_ratio=decrease,"
               f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0,setsar=1,format=rgba")
    args += ["-an", "-sn", "-dn", "-vf", filters, "-frames:v", str(count),
             "-pix_fmt", "rgba", "-threads", "1", "-f", "rawvideo", str(destination)]
    _run(args, root, cancel)
    if destination.stat().st_size != w * h * 4 * count:
        raise RenderError("La capa no produjo todos sus fotogramas RGBA.")


def _composite_overlay(frame, rgba, layer, local_time):
    """Keyframes offset the top-left box in canvas units; scale about center."""
    state = motion.keyframe_state(layer.get("keyframes", []), local_time)
    opacity = layer["opacity"] * state["opacity"]
    if opacity <= 0:
        return frame
    scale = state["scale"]
    width, height = max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))
    left = round(layer["x"] * frame.width + state["x"] * frame.width + (rgba.width - width) / 2)
    top = round(layer["y"] * frame.height + state["y"] * frame.height + (rgba.height - height) / 2)
    x0, y0 = max(0, left), max(0, top)
    x1, y1 = min(frame.width, left + width), min(frame.height, top + height)
    if x1 <= x0 or y1 <= y0:
        return frame
    resized = rgba.resize((width, height), Image.Resampling.LANCZOS) if rgba.size != (width, height) else rgba
    visible = resized.crop((x0 - left, y0 - top, x1 - left, y1 - top))
    alpha = visible.getchannel("A")
    if opacity != 1:
        alpha = alpha.point(lambda value: round(value * opacity))
    underneath = frame.crop((x0, y0, x1, y1))
    color = visible.convert("RGB")
    if layer["blend"] == "screen":
        color = ImageChops.screen(underneath, color)
    frame.paste(Image.composite(color, underneath, alpha), (x0, y0))
    return frame


def _captions(project):
    hook_seconds = float(project.get("style", {}).get("hook_seconds", 4.5))
    words = sorted(project.get("transcript", {}).get("words", []), key=lambda word: float(word.get("start", 0)))
    chunks = []
    group = []
    for item in words:
        start = float(item.get("start", 0))
        end = float(item.get("end", start))
        if start < hook_seconds or end <= start:
            continue
        if group and (start - float(group[-1]["end"]) > .32 or len(group) >= 3):
            chunks.append((float(group[0]["start"]), float(group[-1]["end"]), " ".join(str(w.get("word", "")) for w in group)))
            group = []
        group.append(item)
    if group:
        chunks.append((float(group[0]["start"]), float(group[-1]["end"]), " ".join(str(w.get("word", "")) for w in group)))
    return chunks


def _caption(project, scene, at, chunks):
    if at < float(project.get("style", {}).get("hook_seconds", 4.5)):
        return ""  # Hook is storyboard typography, never automatic ASR captions.
    if scene.get("subtitle"):
        return str(scene["subtitle"])
    for start, end, content in chunks:
        if start <= at < end:
            return content
    return ""


def _decorate(frame, project, scene, at, cfg, chunks):
    w, h = frame.size
    local = at - scene["start"]
    kind = scene["type"]
    if kind != "motion" and not (kind == "split" and not scene.get("asset_id")) and scene.get("title"):
        region_h = cfg['split_height'] if kind == "split" else h
        region = Image.new("RGBA", (w, region_h))
        kinetic = {**scene, "template": "kinetic"}
        motion._kinetic(region, kinetic, motion.clamp(local / max(scene["_planned_end"] - scene["start"], .001)),
                        cfg["primary"], cfg["accent"])
        frame.paste(region, (0, 0), region)
    subtitle = _caption(project, scene, at, chunks)
    if subtitle and subtitle != scene.get("title"):
        subtitle = " ".join(subtitle.split())
        size = max(12, round(w / 15))
        face = motion.fit_font(cfg["primary"], subtitle, size, w * .86)
        bbox = face.getbbox(subtitle, anchor="mm")
        unit = max(1, round(w / 540))
        stroke = max(1, unit // 2)
        left, right = w * .5 + bbox[0] - stroke, w * .5 + bbox[2] + unit + stroke
        if face.getlength(subtitle) > w * .86 or left < w * .05 or right > w * .95:
            raise RenderError("Acorta el bloque de subtítulo: no cabe en una línea dentro de la zona segura.")
        max_y = min(h * .87, h * .90 - bbox[3] - 2 * unit - stroke)
        if kind in {"presenter", "split"}:
            chin = _number(_camera_state(scene,local).get("chin_y", -1), "Barbilla normalizada", 0, .95)
            region_start, region_height = (cfg['split_height'], h - cfg['split_height']) if kind == "split" else (0, h)
            base_chin = region_start + chin * region_height
            state = motion.keyframe_state(scene.get("keyframes", []), local)
            transformed_chin = h * .5 + (base_chin - h * .5) * state["scale"] + state["y"] * h
            # Never clamp a subtitle into the face. Its glyphs, including the
            # compact shadow, must fit between the transformed chin and the
            # reserved bottom zone. Prefer the observed small chin gap.
            min_y = transformed_chin + unit - bbox[1]
            if min_y > max_y:
                raise RenderError("No hay espacio para el subtítulo bajo la barbilla y dentro de la zona segura; ajusta reencuadre, barbilla o bloque.")
            y = min(max_y, max(min_y, transformed_chin + h * .04))
        else:
            y = min(h * .78, max_y)
        motion.text(frame, subtitle, (w * .5, y), face)
    return frame


def _audio(project, cfg, visual, final, root, cancel):
    duration = cfg["duration"]
    args = [_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y",
            "-filter_complex_threads", "1"] + _input(visual) + _input(cfg["source"]["local"])
    has_voice = any(s.get("codec_type") == "audio" for s in cfg["source_info"].get("streams", []))
    graph, tracks, used = [], [], []
    if has_voice:
        from .analysis import select_audio_stream
        selected = select_audio_stream(cfg["source_info"], project.get("settings", {}).get("voice_audio_stream"))
        # Keep the original source clock: a late audio stream starts with
        # silence, rather than moving its first syllable to video time zero.
        voice = f"[1:{selected['index']}]aresample=48000:first_pts=0,atrim=0:{duration:.8f}"
        options = project.get("settings", {})
        if options.get("denoise"):
            voice += ",highpass=f=70,afftdn=nf=-25"
        if options.get("normalize_voice"):
            voice += ",loudnorm=I=-16:TP=-1.5:LRA=11"
        voice += f",apad,atrim=0:{duration:.8f}[voicebase]"
        graph.append(voice)
    audio_items = []
    for item in project.get("audio", []):
        start = _number(item.get("start", 0), "Entrada de audio", 0, 7200)
        end = _number(item.get("end", duration), "Salida de audio", 0, 7200)
        if end <= start:
            raise RenderError("La pista de audio tiene duración inválida.")
        if start >= duration:
            continue
        asset = cfg["assets"].get(item.get("asset_id"))
        if not asset:
            raise RenderError("Recurso de audio inexistente.")
        info = probe_media(asset["local"], root)
        if not any(stream.get("codec_type") == "audio" for stream in info.get("streams", [])):
            raise RenderError("La pista musical/SFX no contiene audio.")
        source_in = _number(item.get("source_in", 0), "Entrada del archivo de audio", 0, 7200)
        span = min(end, duration) - start
        if source_in + span > info["duration"] + .03:
            raise RenderError("El tramo de audio excede el archivo.")
        gain = _number(item.get("gain_db", -20 if item.get("role") == "music" else -8), "Ganancia", -60, 12)
        args += _input(asset["local"])
        audio_items.append((item, start, span, source_in, gain))
        used.append({"asset_id": item["asset_id"], "role": item.get("role", "sfx"),
                     "start": start, "end": start + span, "source_in": source_in})
    music_count = sum(1 for row in audio_items if row[0].get("role") == "music")
    if has_voice:
        if music_count:
            labels = "[voice]" + "".join(f"[duck{i}]" for i in range(music_count))
            graph.append(f"[voicebase]asplit={music_count + 1}{labels}")
        else:
            graph.append("[voicebase]anull[voice]")
        tracks.append("[voice]")
    duck_index = 0
    for index, (item, start, span, source_in, gain) in enumerate(audio_items):
        fade = min(.03, span / 4)
        graph.append(f"[{index + 2}:a:0]atrim={source_in:.8f}:{source_in + span:.8f},"
                     f"asetpts=PTS-STARTPTS,aresample=48000,volume={gain:.4f}dB,"
                     f"afade=t=in:d={fade:.8f},afade=t=out:st={span - fade:.8f}:d={fade:.8f},"
                     f"adelay={round(start * 1000)}:all=1,apad,atrim=0:{duration:.8f}[a{index}]")
        if has_voice and item.get("role") == "music":
            graph.append(f"[a{index}][duck{duck_index}]sidechaincompress=threshold=0.025:"
                         f"ratio=8:attack=15:release=220[m{index}]")
            tracks.append(f"[m{index}]")
            duck_index += 1
        else:
            tracks.append(f"[a{index}]")
    if tracks:
        graph.append("".join(tracks) + f"amix=inputs={len(tracks)}:duration=longest:"
                     f"dropout_transition=0:normalize=0,alimiter=limit=0.82:level=false:latency=1,"
                     f"atrim=0:{duration:.8f}[mix]")
        args += ["-filter_complex", ";".join(graph), "-map", "0:v:0", "-map", "[mix]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
    else:
        args += ["-map", "0:v:0", "-c:v", "copy", "-an"]
    args += ["-threads", "1", "-t", f"{duration:.8f}", "-movflags", "+faststart", str(final)]
    _run(args, root, cancel)
    return has_voice, used


def _hash(path, algorithm):
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def measure_audio_levels(path: Path, root: Path, cancel=None, info=None) -> dict:
    """Measure the exported AAC input; this never asserts perceptive listening."""
    path = confined(root, path, exists=True)
    info = info or probe_media(path, root)
    fields = {"integrated_lufs": "input_i", "true_peak_dbtp": "input_tp",
              "loudness_range_lu": "input_lra", "threshold_lufs": "input_thresh"}
    result = {"available": False, "method": "FFmpeg loudnorm input measurements / EBU R128",
              "measurements": {key: None for key in fields}, "audio_listened": False,
              "true_peak_target_dbtp": -1.5, "warning_threshold_dbtp": -1., "warnings": []}
    if not any(stream.get("codec_type") == "audio" for stream in info.get("streams", [])):
        result["warnings"].append("El exportado no contiene una pista de audio.")
        return result
    _, stderr = _run([_tool("ffmpeg"), "-hide_banner", "-v", "info", "-filter_threads", "1"] + _input(path) +
                     ["-map", "0:a:0", "-vn", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                      "-threads", "1", "-f", "null", "-"], root, cancel, return_stderr=True)
    blocks = list(re.finditer(r'\{\s*"input_i"[\s\S]*?\}', stderr.decode("utf-8", "replace")))
    if not blocks:
        raise RenderError("FFmpeg no devolvió medidas de sonoridad verificables.")
    raw = json.loads(blocks[-1].group())
    for key, field in fields.items():
        try:
            value = float(raw[field])
        except (ValueError, KeyError, TypeError):
            value = float("nan")
        result["measurements"][key] = value if math.isfinite(value) else None
    result["available"] = True
    peak = result["measurements"]["true_peak_dbtp"]
    result["peak_above_target"] = peak > -1.5 if peak is not None else None
    if peak is not None and peak > -1.:
        result["warnings"].append(f"Pico real medido {peak:.2f} dBTP sobre −1 dBTP: revisar mezcla y margen del AAC.")
    if result["measurements"]["integrated_lufs"] is None:
        result["warnings"].append("No se obtuvo sonoridad integrada finita; revisar silencio o duración del tramo.")
    return result


def audit(path: Path, root: Path, scenes=None, cancel=None) -> dict:
    """Decode + sequential evidence; editorial review always remains pending."""
    path = confined(root, path, exists=True)
    info = probe_media(path, root)
    audio_levels = measure_audio_levels(path, root, cancel, info)
    _run([_tool("ffmpeg"), "-v", "error", "-xerror", "-filter_threads", "1"] +
         _input(path) + ["-map", "0:v:0", "-map", "0:a?", "-threads", "1", "-f", "null", "-"], root, cancel)
    evidence = confined(root, path.parent / (path.stem + "_audit"))
    evidence.mkdir(parents=True, exist_ok=True)
    width = 180
    video = next(s for s in info["streams"] if s.get("codec_type") == "video")
    height = round(width * int(video["height"]) / int(video["width"]))
    rate = video.get("avg_frame_rate", "30/1").split("/")
    fps = float(rate[0]) / max(1, float(rate[1])) if len(rate) == 2 else float(rate[0])
    fps = max(1, min(60, fps))
    sample_indices, metrics = [], []
    with tempfile.TemporaryDirectory(prefix="audit-", dir=confined(root, ".estado/render")) as temporary:
        raw = Path(temporary) / "evidence.rgb"
        _run([_tool("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1"] + _input(path) +
             ["-an", "-vf", f"fps={fps},scale={width}:{height},format=rgb24", "-threads", "1",
              "-f", "rawvideo", str(raw)], root, cancel)
        frame_size = width * height * 3
        count = raw.stat().st_size // frame_size
        if not count:
            raise RenderError("No hay fotogramas decodificables para la revisión.")
        sample_indices = sorted(set(min(count - 1, round(at * fps / 4))
                                    for at in range(math.ceil(info["duration"] * 4))))
        # All source frames are decoded. Sheets sample at 4 Hz; the motion
        # proxy preserves the original FPS so alternating flicker is visible.
        sheets = []
        with raw.open("rb") as handle:
            for page_start in range(0, len(sample_indices), 48):
                indices = sample_indices[page_start:page_start + 48]
                page_count = len(indices)
                sheet = Image.new("RGB", (width * 6, (height + 24) * math.ceil(page_count / 6)), (13, 16, 22))
                draw = ImageDraw.Draw(sheet)
                for index, source_index in enumerate(indices):
                    handle.seek(source_index * frame_size)
                    data = handle.read(frame_size)
                    frame = Image.frombytes("RGB", (width, height), data)
                    x, y = (index % 6) * width, (index // 6) * (height + 24)
                    sheet.paste(frame, (x, y))
                    draw.text((x + 4, y + height + 4), f"{source_index / fps:.2f} s", fill="white")
                target = evidence / f"secuencia_{page_start // 48 + 1:03d}.jpg"
                sheet.save(target, quality=88)
                sheets.append(str(target.relative_to(root)))
            # Consecutive source frames around every editorial cut, including
            # two frames on each side. These complement movement review.
            cut_indices = sorted(set(min(count - 1, max(0, round(scene["start"] * fps) + delta))
                                     for scene in scenes or [] for delta in (-2, -1, 0, 1, 2)))
            if cut_indices:
                sheet = Image.new("RGB", (width * 5, (height + 24) * math.ceil(len(cut_indices) / 5)), (13, 16, 22))
                draw = ImageDraw.Draw(sheet)
                for index, source_index in enumerate(cut_indices):
                    handle.seek(source_index * frame_size)
                    frame = Image.frombytes("RGB", (width, height), handle.read(frame_size))
                    x, y = (index % 5) * width, (index // 5) * (height + 24)
                    sheet.paste(frame, (x, y))
                    draw.text((x + 4, y + height + 4), f"{source_index / fps:.3f} s / f{source_index}", fill="white")
                target = evidence / "transiciones_consecutivas.jpg"
                sheet.save(target, quality=90)
                sheets.append(str(target.relative_to(root)))
            handle.seek(0)
            previous = None
            for source_index in range(count):
                frame = Image.frombytes("RGB", (width, height), handle.read(frame_size))
                if previous is not None:
                    delta = sum(ImageStat.Stat(ImageChops.difference(frame, previous)).mean) / 3
                    metrics.append({"frame": source_index, "time": round(source_index / fps, 6),
                                    "mean_rgb_difference": round(delta, 4)})
                previous = frame
        temporal = evidence / "diferencias_temporales.json"
        temporal.write_text(json.dumps({"interpretation": "Medición técnica; no certifica ausencia de parpadeo ni escala estable.",
                                         "fps": fps, "frames_decoded": count, "frames": metrics}, ensure_ascii=False, indent=2), encoding="utf-8")
    proxy = evidence / "revision_movimiento.mp4"
    _run([_tool("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1"] + _input(path) +
         ["-vf", "scale=360:-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
          "-c:a", "aac", "-b:a", "96k", "-threads", "1", "-movflags", "+faststart", str(proxy)], root, cancel)
    return {"decode_ok": True, "video_codec": video.get("codec_name"),
            "audio_codec": next((s.get("codec_name") for s in info["streams"] if s.get("codec_type") == "audio"), None),
            "human_review_required": True, "editorial_approved": False,
            "audio_listened": False, "contact_sheets": sheets,
            "output_audio_levels": audio_levels, "audio_warnings": audio_levels["warnings"],
            "motion_review": str(proxy.relative_to(root)), "sequential_sample_hz": 4,
            "sequential_sample_count": len(sample_indices), "consecutive_frames_decoded": count,
            "temporal_metrics": str(temporal.relative_to(root)), "scenes": scenes or []}


def render(project: dict, root: Path, output: Path, seconds: float = 10,
           progress=None, cancel=None) -> dict:
    """CPU-serial public entry point; queued workers reuse their held lease."""
    from .jobs import cpu_slot
    from .core import StudioError
    try:
        with cpu_slot(cancel=cancel):
            return _render(project,root,output,seconds,progress,cancel)
    except StudioError as error:
        if _cancelled(cancel):raise RenderCancelled('Render cancelado.') from error
        raise


def _render(project: dict, root: Path, output: Path, seconds: float = 10,
           progress=None, cancel=None) -> dict:
    """Render local source/timeline into MP4; atomic export and CPU-only.

    progress is called with ``(fraction, message)``. ``cancel`` may be an
    Event or a zero-argument predicate. Only one renderer runs in this process.
    Production font identity and review/authorization gates belong to the
    project validator; this engine requires both real, readable font files.
    """
    progress = progress or (lambda fraction, message: None)
    root = Path(root).resolve()
    output = confined(root, output)
    if output.suffix.lower() != ".mp4":
        raise RenderError("La exportación debe tener extensión MP4.")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not _RENDER_LOCK.acquire(blocking=False):
        raise RenderError("Ya hay un render local en curso; se ejecutan en serie.")
    encoder = None
    try:
        cfg = _prepare(project, root, seconds)
        if any(asset["local"] == output for asset in cfg["assets"].values()):
            raise RenderError("El destino no puede sobrescribir un original o recurso.")
        w, h, fps = cfg["width"], cfg["height"], cfg["fps"]
        used = [{"asset_id": project["source"], "role": "narration", "start": 0,
                 "end": cfg["duration"], "source_in": 0}]
        chunks = _captions(project)
        cache = confined(root, ".estado/render")
        cache.mkdir(parents=True, exist_ok=True)
        progress(.01, "Validación del proyecto y fuentes")
        with tempfile.TemporaryDirectory(prefix="job-", dir=cache) as temporary:
            temporary = Path(temporary)
            visual, candidate = temporary / "visual.mp4", temporary / "candidate.mp4"
            log = temporary / "encoder.log"
            with log.open("wb") as error_log:
                encoder = subprocess.Popen(_process_command([_tool("ffmpeg"), "-v", "error", "-y",
                    "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{w}x{h}",
                    "-framerate", f"{fps:.8f}", "-i", "pipe:0", "-an", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", str(int(project.get("settings", {}).get("crf", 18))),
                    "-pix_fmt", "yuv420p", "-threads", "1", "-movflags", "+faststart", str(visual)]),
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=error_log,
                    cwd=root, env=_environment(root), shell=False)
                sent = 0
                for scene_index, scene in enumerate(cfg["scenes"]):
                    begin = max(sent, math.ceil(scene["start"] * fps - 1e-8))
                    end = min(cfg["frames"], math.ceil(scene["end"] * fps - 1e-8))
                    count = end - begin
                    if count <= 0:
                        continue
                    kind = scene["type"]
                    lower = cfg['split_height']
                    decoded, handles = {}, {}
                    active_layers = []
                    design_layers = []
                    try:
                        if kind in {"presenter", "split"}:
                            shape = (w, h - lower) if kind == "split" else (w, h)
                            progress(.05 + .65 * sent / cfg["frames"], f"Escena {scene_index + 1}: decodificando crudo en CPU")
                            source_in = float(scene.get("source_in", scene["start"])) + begin / fps - scene["start"]
                            raw = temporary / f"source_{scene_index}.rgb"
                            _decode(cfg["source"], shape, source_in, count, fps, raw, root, scene, cancel)
                            decoded["source"] = (shape, raw)
                            used.append({"asset_id": project["source"], "role": kind, "start": begin / fps, "end": end / fps, "source_in": source_in})
                        if kind in {"broll", "split"} and scene.get("asset_id"):
                            shape = (w, lower) if kind == "split" else (w, h)
                            asset = cfg["assets"][scene["asset_id"]]
                            progress(.05 + .65 * sent / cfg["frames"], f"Escena {scene_index + 1}: decodificando recurso real en CPU")
                            source_in = float(scene.get("broll_in", 0) if kind == "split" else scene.get("source_in", 0)) + begin / fps - scene["start"]
                            raw = temporary / f"asset_{scene_index}.rgb"
                            _decode(asset, shape, source_in, count, fps, raw, root, scene, cancel)
                            decoded["asset"] = (shape, raw)
                            used.append({"asset_id": scene["asset_id"], "role": kind, "start": begin / fps, "end": end / fps, "source_in": source_in})
                        first_overlay = end
                        if scene.get("transition_asset_id"):
                            transition_start = max(scene["start"], scene["_planned_end"] - float(scene.get("transition_duration", .5)))
                            first_overlay = max(begin, math.ceil(transition_start * fps - 1e-8))
                            if first_overlay < end:
                                source_in = float(scene.get("transition_source_in", 0)) + first_overlay / fps - transition_start
                                raw = temporary / f"burn_{scene_index}.rgb"
                                asset = cfg["assets"][scene["transition_asset_id"]]
                                _decode(asset, (w, h), source_in, end - first_overlay, fps, raw, root, {}, cancel)
                                decoded["burn"] = ((w, h), raw)
                                used.append({"asset_id": asset["id"], "role": "transition", "blend": "screen",
                                             "start": first_overlay / fps, "end": end / fps, "source_in": source_in})
                        for layer_index, layer in enumerate(scene["overlays"]):
                            global_start = scene["start"] + layer["start"]
                            global_end = scene["start"] + layer["end"]
                            first = max(begin, math.ceil(global_start * fps - 1e-8))
                            last = min(end, math.ceil(global_end * fps - 1e-8))
                            if last <= first:
                                continue
                            shape = (max(1, round(w * layer["width"])), max(1, round(h * layer["height"])))
                            source_in = 0 if layer["_static_image"] else layer["source_in"] + first / fps - global_start
                            key = f"overlay_{layer_index}"
                            raw = temporary / f"layer_{scene_index}_{layer_index}.rgba"
                            progress(.05 + .65 * sent / cfg["frames"], f"Escena {scene_index + 1}: decodificando capa {layer['id']} en CPU")
                            _decode_overlay(cfg["assets"][layer["asset_id"]], shape, source_in, last - first,
                                            fps, raw, root, layer["_static_image"], cancel)
                            decoded[key] = (shape, raw)
                            active_layers.append({"layer": layer, "key": key, "first": first, "last": last,
                                                  "shape": shape, "static_frame": None})
                            used.append({"asset_id": layer["asset_id"], "role": "overlay", "layer_id": layer["id"],
                                         "scene_id": scene.get("id"), "start": first / fps, "end": last / fps,
                                         "source_in": source_in, "blend": layer["blend"], "opacity": layer["opacity"],
                                         "verification": "Composición ejecutada; aparición, pertinencia y rostro requieren revisión visual."})
                        for element_index, element in enumerate(scene.get("_design_media", [])):
                            global_start = scene["start"] + element.get("start", 0)
                            global_end = scene["start"] + element.get("end", scene["_planned_end"] - scene["start"])
                            first = max(begin, math.ceil(global_start * fps - 1e-8))
                            last = min(end, math.ceil(global_end * fps - 1e-8))
                            if last <= first:
                                continue
                            shape = (max(1, round(w * element.get("width", .25))), max(1, round(scene["_design_size"][1] * element.get("height", .25))))
                            source_in = 0 if element["_static_image"] else element.get("source_in", 0) + first / fps - global_start
                            key = f"design_{element_index}"
                            raw = temporary / f"design_{scene_index}_{element_index}.rgba"
                            _decode_overlay(cfg["assets"][element["asset_id"]], shape, source_in, last - first, fps, raw, root, element["_static_image"], cancel)
                            decoded[key] = (shape, raw)
                            design_layers.append({"element": element, "key": key, "shape": shape, "first": first, "last": last, "static_frame": None})
                            used.append({"asset_id": element["asset_id"], "role": "motion_element", "element_id": element["id"], "scene_id": scene.get("id"), "start": first / fps, "end": last / fps, "source_in": source_in})
                        for key, (_, raw) in decoded.items():
                            handles[key] = raw.open("rb")
                        for frame_index in range(begin, end):
                            if _cancelled(cancel):
                                raise RenderCancelled("Render cancelado.")
                            at = frame_index / fps
                            local = at - scene["start"]
                            media_frames = {}
                            for runtime in design_layers:
                                if runtime["first"] <= frame_index < runtime["last"]:
                                    rgba = runtime["static_frame"]
                                    if rgba is None:
                                        shape = runtime["shape"]
                                        rgba = Image.frombytes("RGBA", shape, handles[runtime["key"]].read(shape[0] * shape[1] * 4))
                                        if runtime["element"]["_static_image"]:
                                            runtime["static_frame"] = rgba
                                    media_frames[runtime["element"]["id"]] = rgba
                            if kind == "motion":
                                if scene.get("template") == "custom":
                                    from .design import draw_design
                                    frame = draw_design({**scene, "end": scene["_planned_end"]}, local, (w, h), {"primary": cfg["primary"], "accent": cfg["accent"]}, media_frames, root=root, font_assets=cfg["font_assets"]).convert("RGB")
                                else:
                                    frame = motion.compose(scene, local, scene["_planned_end"] - scene["start"],
                                                           (w, h), cfg["primary"], cfg["accent"])
                            elif kind == "presenter":
                                frame = Image.frombytes("RGB", (w, h), handles["source"].read(w * h * 3))
                            elif kind == "broll":
                                frame = Image.frombytes("RGB", (w, h), handles["asset"].read(w * h * 3))
                            else:
                                frame = Image.new("RGB", (w, h))
                                bottom = Image.frombytes("RGB", (w, h - lower), handles["source"].read(w * (h - lower) * 3))
                                if "asset" in handles:
                                    top = Image.frombytes("RGB", (w, lower), handles["asset"].read(w * lower * 3))
                                elif scene.get("template") == "custom":
                                    from .design import draw_design
                                    top = draw_design({**scene, "end": scene["_planned_end"]}, local, (w, lower), {"primary":cfg["primary"],"accent":cfg["accent"]}, media_frames, root=root, font_assets=cfg["font_assets"]).convert("RGB")
                                else:
                                    top = motion.compose(scene, local, scene["_planned_end"]-scene["start"], (w,lower),cfg["primary"],cfg["accent"])
                                frame.paste(top, (0, 0))
                                frame.paste(bottom, (0, lower))
                            effects = scene.get("effects", {})
                            brightness = _number(effects.get("brightness", 0), "brightness", -1, 1)
                            if brightness:
                                shift = round(brightness * 255)
                                frame = frame.point(lambda channel: min(255, max(0, channel + shift)))
                            for key, cls in (("contrast", ImageEnhance.Contrast),
                                             ("saturation", ImageEnhance.Color)):
                                value = _number(effects.get(key, 1), key, 0, 3)
                                if value != 1:
                                    frame = cls(frame).enhance(value)
                            frame = motion.transform(frame, motion.keyframe_state(scene.get("keyframes", []), local))
                            for runtime in active_layers:
                                if not runtime["first"] <= frame_index < runtime["last"]:
                                    continue
                                layer = runtime["layer"]
                                shape = runtime["shape"]
                                if layer["_static_image"] and runtime["static_frame"] is not None:
                                    rgba = runtime["static_frame"]
                                else:
                                    data = handles[runtime["key"]].read(shape[0] * shape[1] * 4)
                                    rgba = Image.frombytes("RGBA", shape, data)
                                    if layer["_static_image"]:
                                        runtime["static_frame"] = rgba
                                frame = _composite_overlay(frame, rgba, layer, local - layer["start"])
                            frame = _decorate(frame, project, scene, at, cfg, chunks)
                            if frame_index >= first_overlay and "burn" in handles:
                                burn = Image.frombytes("RGB", (w, h), handles["burn"].read(w * h * 3))
                                frame = ImageChops.screen(frame, burn)
                            try:
                                encoder.stdin.write(frame.tobytes())
                            except BrokenPipeError:
                                raise RenderError("FFmpeg interrumpió la codificación: " + log.read_text(errors="replace")[-2000:]) from None
                            sent += 1
                            if frame_index % max(1, round(fps)) == 0:
                                progress(.05 + .65 * sent / cfg["frames"], f"Escena {scene_index + 1}: {sent}/{cfg['frames']} fotogramas")
                    finally:
                        for handle in handles.values():
                            handle.close()
                        for _, raw in decoded.values():
                            raw.unlink(missing_ok=True)
                encoder.stdin.close()
                if encoder.wait(timeout=120) != 0:
                    raise RenderError("Falló la codificación: " + log.read_text(errors="replace")[-2000:])
                if sent != cfg["frames"]:
                    raise RenderError("El render no cubrió todos los fotogramas.")
            progress(.75, "Mezcla de voz original, música y efectos")
            has_voice, audio_used = _audio(project, cfg, visual, candidate, root, cancel)
            used.extend(audio_used)
            progress(.85, "Auditoría de decodificación y evidencias consecutivas")
            # Verify the complete candidate before replacing a previous export.
            info = probe_media(candidate, root)
            _run([_tool("ffmpeg"), "-v", "error", "-xerror", "-filter_threads", "1"] + _input(candidate) +
                 ["-threads", "1", "-f", "null", "-"], root, cancel)
            if abs(info["duration"] - cfg["duration"]) > max(.15, 2 / fps):
                raise RenderError("La duración exportada no coincide con la cronología.")
            if _cancelled(cancel):
                raise RenderCancelled("Render cancelado.")
            technical = audit(candidate, root, [{"id": s.get("id"), "start": s["start"], "end": s["end"], "type": s["type"]} for s in cfg["scenes"]], cancel)
            # All evidence is made before replacing a previous candidate.
            audit_source = temporary / "candidate_audit"
            audit_target = confined(root, output.parent / (output.stem + "_audit"))
            audit_target.mkdir(parents=True, exist_ok=True)
            for evidence_file in audit_source.iterdir():
                os.replace(evidence_file, audit_target / evidence_file.name)
            technical["contact_sheets"] = [str((audit_target / Path(path).name).relative_to(root)) for path in technical["contact_sheets"]]
            for evidence_key in ("motion_review", "temporal_metrics"):
                technical[evidence_key] = str((audit_target / Path(technical[evidence_key]).name).relative_to(root))
            os.replace(candidate, output)
        technical.update(original_voice_present=has_voice, gpu_used=False, max_ffmpeg_threads=2,
                         font_primary=Path(cfg["primary"]).relative_to(root).as_posix(),
                         font_accent=Path(cfg["accent"]).relative_to(root).as_posix())
        technical.update(overlay_count=sum(1 for item in used if item["role"] == "overlay"),
                         overlay_position_review_required=any(item["role"] == "overlay" for item in used))
        from .analysis import select_audio_stream
        technical.update(original_audio_present=has_voice, ffmpeg_niceness=10 if shutil.which("nice") else None,
                         original_audio_stream_index=select_audio_stream(cfg['source_info'], project.get('settings', {}).get('voice_audio_stream'))['index'] if has_voice else None,
                         mix_limiter={"applied": bool(has_voice or audio_used), "scope": "mixed PCM bus before AAC encoding",
                                      "limit": .82, "automatic_gain": False,
                                      "nominal_sample_ceiling_dbfs": round(20 * math.log10(.82), 3)})
        result = {"path": str(output.relative_to(root)), "size": output.stat().st_size,
                  "sha256": _hash(output, "sha256"), "md5": _hash(output, "md5"),
                  "duration": info["duration"], "width": w, "height": h, "fps": fps,
                  "used_assets": used, "technical": technical}
        receipt = output.with_suffix(".json")
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest = output.with_name("broll_manifest.csv")
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["archivo", "ruta_local", "fuente", "duracion", "contenido", "frase",
                             "tiempo_previsto", "tiempo_realmente_usado", "verificacion"])
            for entry in used:
                if entry["role"] not in {"broll", "split"} or entry["asset_id"] == project["source"]:
                    continue
                asset = cfg["assets"][entry["asset_id"]]
                scene = next(s for s in cfg["scenes"] if s.get("asset_id") == entry["asset_id"] and abs(s["start"] - entry["start"]) < 1 / fps + .001)
                writer.writerow([asset.get("name", asset["local"].name), str(asset["local"].relative_to(root)),
                                 asset.get("origin", asset.get("source", "local")), asset.get("duration", ""),
                                 asset.get("analysis", {}).get("content", "Pendiente de revisión semántica"),
                                 scene.get("subtitle", scene.get("title", "")), f"{scene['start']:.3f}–{scene['end']:.3f}",
                                 f"{entry['start']:.3f}–{entry['end']:.3f}", "Decodificado e incorporado; revisión editorial pendiente"])
        progress(1, "Candidato exportado; revisión editorial pendiente")
        return result
    finally:
        if encoder is not None and encoder.poll() is None:
            if encoder.stdin and not encoder.stdin.closed:
                try:
                    encoder.stdin.close()
                except BrokenPipeError:
                    pass
            encoder.terminate()
            try:
                encoder.wait(timeout=3)
            except subprocess.TimeoutExpired:
                encoder.kill()
                encoder.wait()
        _RENDER_LOCK.release()
