"""Browser proxies for local editing formats, with immutable original media.

VP9 alpha uses libvpx and yuva420p (FFmpeg/libavcodec/libvpxenc.c).
Browser playback still depends on the installed browser and codec support;
these low-resolution previews are not delivery exports or editorial approvals.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
from urllib.parse import quote

from PIL import Image

from .analysis import FORMATS
from .core import StudioError
from .media_tools import ROOT, INPUT_EXTENSIONS, _inside, _hash, _run, _probe, _base

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_PICTURES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
_HDR = {"smpte2084", "arib-std-b67"}


def _destination(root: Path, relative: str) -> Path:
    """Our own derived outputs never follow a symlink, even within SOFTWARE."""
    raw = root / relative
    resolved = _inside(root, relative)
    if raw.absolute() != resolved or raw.is_symlink():
        raise StudioError("La ruta de vista previa no puede sustituir enlaces ni originales.", 403)
    return raw


@contextmanager
def _preview_lock(root: Path, key: str):
    label = str(root / key)
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(label, threading.RLock())
    with lock:
        path = _destination(root, f".estado/previews/{key}.lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _videos(info):
    return [s for s in info.get("streams", []) if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]


def _alpha(video, suffix):
    pixel = str(video.get("pix_fmt", "")).lower()
    return (pixel.startswith(("rgba", "bgra", "argb", "abgr", "yuva", "gbrap", "ya"))
            or video.get("codec_name") == "qtrle"
            or (video.get("codec_name") == "png" and suffix == ".mov")
            or str(video.get("tags", {}).get("alpha_mode", "0")) == "1")


def _browser_compatible(info, suffix):
    videos = _videos(info)
    if not videos:
        return True
    video = videos[0]
    audios = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if video.get("color_transfer") in _HDR:
        return False
    if suffix in {".mp4", ".m4v"}:
        return (video.get("codec_name") == "h264" and video.get("pix_fmt", "yuv420p") in {"yuv420p", "yuvj420p"}
                and all(s.get("codec_name") in {"aac", "mp3"} for s in audios))
    if suffix == ".webm":
        return (video.get("codec_name") in {"vp8", "vp9", "av1"}
                and all(s.get("codec_name") in {"opus", "vorbis"} for s in audios))
    return False


def _duration(info):
    durations = [info.get("format", {}).get("duration")]
    durations += [s.get("duration") for s in info.get("streams", [])]
    valid = []
    for duration in durations:
        try:
            number = float(duration)
            if math.isfinite(number) and number > 0:
                valid.append(number)
        except (TypeError, ValueError):
            pass
    if not valid:
        raise StudioError("No hay duración verificable para generar una vista previa completa.")
    return max(valid)


def _local_url(path):
    return "/api/files/" + quote(path, safe="/")


def _original(asset, path, reason, pending=False):
    asset.update(preview_path=path, preview_url=_local_url(path), preview_is_derivative=False, preview_reason=reason)
    if pending:
        asset["preview_pending"] = True
    return asset


def _with_receipt(asset, receipt, reused):
    asset.update(preview_path=receipt["path"], preview_url=_local_url(receipt["path"]),
                 preview_probe=receipt["probe"], preview_is_derivative=True,
                 preview_provenance=receipt["provenance"], preview_reused=reused,
                 preview_preserves_alpha=receipt["alpha"], preview_sha256=receipt["sha256"])
    return asset


def _tiff_preview(asset, source, relative_source, source_sha, root):
    """Decode only the first TIFF page into a browser-readable RGBA PNG."""
    key = source_sha[:20]
    output_path = f"assets/previews/{key}.png"
    with _preview_lock(root, key):
        output = _destination(root, output_path)
        receipt_path = _destination(root, f".estado/previews/{key}.json")
        if output == source:
            raise StudioError("La vista previa nunca reemplaza el original.", 403)
        if output.exists():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
            if not receipt or receipt.get("path") != output_path or receipt.get("source_sha256") != source_sha or receipt.get("sha256") != _hash(output):
                raise StudioError("La vista previa existente cambió o carece de recibo; no se sobrescribe.", 409)
            if _hash(source) != source_sha:
                raise StudioError("El original cambió durante la consulta de la vista previa.", 409)
            return _with_receipt(asset, receipt, True)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_root = _destination(root, ".estado/tmp")
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="browser-preview-", dir=temporary_root) as temporary:
            candidate = _destination(root, str(Path(temporary).relative_to(root) / "candidate.png"))
            with Image.open(source) as picture:
                if picture.format != "TIFF":
                    raise StudioError("La extensión TIFF no corresponde a una imagen TIFF real.")
                source_dimensions = list(picture.size)
                pages = picture.n_frames
                picture.seek(0)
                alpha = "A" in picture.getbands() or "transparency" in picture.info
                rgba = picture.convert("RGBA")
                rgba.thumbnail((540, 960), Image.Resampling.LANCZOS)
                dimensions = list(rgba.size)
                rgba.save(candidate, format="PNG")
            with Image.open(candidate) as decoded:
                decoded.load()
                if decoded.format != "PNG" or decoded.mode != "RGBA" or list(decoded.size) != dimensions:
                    raise StudioError("La vista previa TIFF perdió su formato o canales RGBA.")
            measured = _probe(candidate, root)
            videos = _videos(measured)
            if len(videos) != 1 or videos[0].get("codec_name") != "png" or [videos[0].get("width"), videos[0].get("height")] != dimensions:
                raise StudioError("No se pudo verificar la vista previa PNG.")
            if _hash(source) != source_sha:
                raise StudioError("El original cambió durante la conversión; la vista previa no se promueve.", 409)
            receipt = {"path": output_path, "probe": measured, "source_sha256": source_sha, "sha256": _hash(candidate), "alpha": alpha,
                       "provenance": {"operation": "browser_preview", "source_asset_id": asset.get("id"), "source_path": relative_source,
                                      "source_sha256": source_sha, "processor_sha256": _hash(__file__),
                                      "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "profile": "PNG RGBA · TIFF first page",
                                      "max_dimensions": [540, 960], "source_dimensions": source_dimensions, "preview_dimensions": dimensions,
                                      "source_pages": pages, "preview_page": 0, "decoder": "Pillow", "gpu_used": False,
                                      "decode_ok": True, "audio_listened": False, "visual_reviewed": False, "approved_for_ascendia": False,
                                      "limitations": ["Vista estática de la primera página; usar el TIFF original para editar y exportar.",
                                                      "No constituye aprobación del contenido ni conversión de color para mastering."]}}
            candidate_receipt = Path(temporary) / "receipt.json"
            candidate_receipt.write_text(json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
            # The hard link atomically refuses an output created by an external
            # process during conversion, even if it does not honor our lock.
            try:
                os.link(candidate, output)
            except FileExistsError as error:
                raise StudioError("La vista previa apareció durante la conversión; no se sobrescribe.", 409) from error
            os.replace(candidate_receipt, receipt_path)
            return _with_receipt(asset, receipt, False)


def ensure_preview(asset: dict, root: Path = ROOT) -> dict:
    """Return original asset metadata plus optional, canonical browser preview.

    Errors are reported as preview_error and do not reject an otherwise valid
    original import. No CPU-global/store lock is acquired here: callers serialize
    CPU workloads. The per-hash file lock prevents duplicate simultaneous work.
    """
    if not isinstance(asset, dict):
        return {"preview_error": "La vista previa requiere un recurso local.", "preview_is_derivative": False}
    result = copy.deepcopy(asset)
    # Reset existing preview fields explicitly: callers merge these keys into a
    # catalog, so omission would leave a stale derivative/error after failure.
    for field in list(result):
        if field.startswith("preview_"):
            result[field] = False if field in {"preview_is_derivative", "preview_preserves_alpha", "preview_pending", "preview_reused"} else None
    try:
        root = _inside(root, ".")
        if not isinstance(asset.get("path"), str):
            raise StudioError("La vista previa requiere una ruta local.")
        source = _inside(root, asset["path"], True)
        relative_source = source.relative_to(root).as_posix()
        suffix = source.suffix.lower()
        source_sha = _hash(source)
        if asset.get("sha256") and asset["sha256"] != source_sha:
            raise StudioError("El recurso cambió respecto a su hash canónico.", 409)
        if asset.get("kind") == "font":
            return _original(result, relative_source, "Fuente tipográfica: usa el original.")
        if suffix not in INPUT_EXTENSIONS | _PICTURES:
            raise StudioError("Formato no admitido para vistas previas locales.")
        info = asset.get("probe")
        if suffix in {".tif", ".tiff"}:
            return _tiff_preview(result, source, relative_source, source_sha, root)
        if suffix in _PICTURES or asset.get("kind") in {"image", "font"}:
            return _original(result, relative_source, "Imagen estática: usa el original.")
        if isinstance(info, dict):
            videos = _videos(info)
            if not videos:
                return _original(result, relative_source, "Sin pista de video: usa el original.")
            if not videos[0].get("codec_name"):
                return _original(result, relative_source, "Códec pendiente de inspección; no se genera proxy con metadata incompleta.", True)
            if _browser_compatible(info, suffix):
                return _original(result, relative_source, "Perfil de reproducción web compatible.")
        info = _probe(source, root)
        videos = _videos(info)
        if not videos:
            return _original(result, relative_source, "Sin pista de video: usa el original.")
        if _browser_compatible(info, suffix):
            return _original(result, relative_source, "Perfil de reproducción web compatible.")
        video = videos[0]
        alpha = _alpha(video, suffix)
        hdr = video.get("color_transfer") in _HDR
        if hdr and alpha:
            raise StudioError("HDR con transparencia requiere una conversión de color dedicada; el original sigue disponible.")
        duration = _duration(info)
        if duration > 4 * 3600:
            raise StudioError("La vista previa automática admite hasta cuatro horas; el original sigue disponible.")
        key = source_sha[:20]
        extension = ".webm" if alpha else ".mp4"
        output_path = f"assets/previews/{key}{extension}"
        processor_sha = _hash(__file__)
        with _preview_lock(root, key):
            output = _destination(root, output_path)
            receipt_path = _destination(root, f".estado/previews/{key}.json")
            if output == source:
                raise StudioError("La vista previa nunca reemplaza el original.", 403)
            if output.exists():
                receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
                if not receipt or receipt.get("path") != output_path or receipt.get("source_sha256") != source_sha or receipt.get("sha256") != _hash(output):
                    raise StudioError("La vista previa existente cambió o carece de recibo; no se sobrescribe.", 409)
                if _hash(source) != source_sha:
                    raise StudioError("El original cambió durante la consulta de la vista previa.", 409)
                return _with_receipt(result, receipt, True)
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary_root = _destination(root, ".estado/tmp")
            temporary_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="browser-preview-", dir=temporary_root) as temporary:
                candidate = _destination(root, str(Path(temporary).relative_to(root) / ("candidate" + extension)))
                scale = "scale=w='min(540,iw)':h='min(960,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1"
                filter = scale + ",fps=30,setsar=1"
                if hdr:
                    filter = "zscale=t=linear:npl=100,format=gbrpf32le,tonemap=tonemap=hable:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=tv," + filter
                filter += ",format=" + ("yuva420p" if alpha else "yuv420p")
                args = _base() + ["-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-threads", "2", "-i", str(source),
                                 "-map", f"0:{video['index']}", "-map", "0:a:0?", "-sn", "-dn", "-vf", filter, "-map_metadata", "-1"]
                if alpha:
                    args += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0", "-b:v", "0", "-crf", "32",
                             "-deadline", "good", "-cpu-used", "4", "-c:a", "libopus", "-b:a", "128k", "-ar", "48000"]
                else:
                    args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                             "-ar", "48000", "-movflags", "+faststart"]
                args += ["-threads", "2", "-y", str(candidate)]
                timeout = max(60, min(3600, duration * 30 + 30))
                _run("ffmpeg", args, root, timeout)
                measured = _probe(candidate, root)
                derived_videos = _videos(measured)
                source_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
                derivative_audio = any(s.get("codec_type") == "audio" for s in measured.get("streams", []))
                if not derived_videos or (source_audio and not derivative_audio):
                    raise StudioError("La vista previa perdió una pista requerida.")
                if abs(_duration(measured) - duration) > max(.15, duration * .002):
                    raise StudioError("La duración de la vista previa no conserva el tramo completo.")
                verify = _base() + ["-xerror", "-protocol_whitelist", "file,pipe", "-format_whitelist", FORMATS, "-threads", "2"]
                if alpha:
                    verify += ["-c:v", "libvpx-vp9"]
                _run("ffmpeg", verify + ["-i", str(candidate), "-threads", "2", "-f", "null", "-"], root, timeout)
                if _hash(source) != source_sha:
                    raise StudioError("El original cambió durante la conversión; la vista previa no se promueve.", 409)
                receipt = {"path": output_path, "probe": measured, "source_sha256": source_sha, "sha256": _hash(candidate), "alpha": alpha,
                           "provenance": {"operation": "browser_preview", "source_asset_id": asset.get("id"), "source_path": relative_source,
                                          "source_sha256": source_sha, "processor_sha256": processor_sha, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                          "profile": "VP9/Opus alpha WebM" if alpha else "H.264/AAC MP4 SDR", "max_dimensions": [540, 960], "fps": 30,
                                          "source_duration": duration, "preview_duration": _duration(measured), "gpu_used": False, "max_ffmpeg_threads": 2,
                                          "decode_ok": True, "audio_listened": False, "visual_reviewed": False, "approved_for_ascendia": False,
                                          "alpha_decoder": "libvpx-vp9" if alpha else None, "hdr_tonemap": "hable" if hdr else None,
                                          "limitations": ["Vista previa comprimida; usar el original para render final.", "La compatibilidad depende del navegador.", "No constituye mastering HDR ni aprobación del montaje."]}}
                candidate_receipt = Path(temporary) / "receipt.json"
                candidate_receipt.write_text(json.dumps(receipt, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
                os.replace(candidate, output)
                os.replace(candidate_receipt, receipt_path)
                return _with_receipt(result, receipt, False)
    except Exception as error:
        result.update(preview_error=str(error), preview_is_derivative=False)
        return result
