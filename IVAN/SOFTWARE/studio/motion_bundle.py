"""Portable HTML sources from a verified HyperFrames execution receipt."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import uuid
import zipfile

from .core import StudioError
from . import hyperframes as hf

MAX_BYTES = 4 * 1024 ** 3
MAX_FILES = 5000
MEDIA = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".mxf", ".mpeg", ".mpg",
         ".m4v", ".mts", ".m2ts", ".ts", ".3gp", ".3g2", ".gif", ".flv", ".wmv", ".ogv",
         ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def _allowed(relative):
    parts = relative.parts
    if len(parts) == 1:
        return parts[0] in {"index.html", "hyperframes.json"}
    if len(parts) != 2:
        return False
    parent, name = parts
    if parent == "fonts":
        return name in {"primary.ttf", "accent.ttf", "font_manifest.json"} or bool(re.fullmatch(r"[0-9a-f]{20}\.(ttf|otf)|license_[0-9a-f]{20}\.txt", name))
    if parent == "runtime":
        return name in {"gsap.min.js", "MotionPathPlugin.min.js", "third_party.json"}
    if parent == "compositions":
        return bool(re.fullmatch(r"scene_[0-9]+\.html", name))
    if parent == "captions":
        return bool(re.fullmatch(r"scene_[0-9]+_[0-9]+\.png", name))
    if parent == "media":
        return name == "native_baseline.mp4" or (bool(re.fullmatch(r"[0-9a-f]{64}\.[a-z0-9]+", name)) and relative.suffix.lower() in MEDIA)
    return False


def write_bundle(receipt, root, destination):
    """Write a new ZIP, preserving portable URLs and actual runtime bytes.

    Only generated visual sources are included: no private receipt, profile,
    cache, browser, CLI executable or installer. Voice remains in the parent
    canonical project and is mixed separately by its existing audio engine.
    """
    root = Path(root).resolve()
    destination = hf._target(root, destination)
    temporary_scope = hf._inside(root, ".estado/tmp")
    if not destination.is_relative_to(temporary_scope) or destination.suffix.lower() != ".zip":
        raise StudioError("El paquete de motion debe crearse como ZIP nuevo en .estado/tmp de SOFTWARE.")
    if destination.exists():
        raise StudioError("El paquete no reemplaza archivos existentes.", 409)
    if not hf.verify_receipt(receipt, root):
        raise StudioError("El editable requiere evidencia HyperFrames actual y archivos verificados.", 409)
    adapter = receipt["technical"]["hyperframes"]
    build_path = hf._inside(root, adapter["build_path"], True)
    try:
        manifest = json.loads(build_path.read_text())
    except (OSError, ValueError) as error:
        raise StudioError("El manifiesto editable no es válido.") from error
    directory = hf._inside(root, manifest.get("directory", ""))
    if build_path.parent != directory:
        raise StudioError("El manifiesto no pertenece a su composición.")
    files = manifest.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        raise StudioError("El editable supera el número seguro de archivos.")
    entries, names, total = [], set(), 0
    proof_files = {entry["path"]: entry["sha256"] for entry in adapter.get("proof_files", [])}
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise StudioError("Entrada inválida en el manifiesto editable.")
        source = hf._inside(root, item["path"], True)
        if not source.is_relative_to(directory):
            raise StudioError("El editable no incluye archivos ajenos a su composición.")
        relative = source.relative_to(directory)
        unresolved = root / item["path"]
        if unresolved.is_symlink() or unresolved.absolute() != source or not _allowed(relative):
            raise StudioError("El editable contiene rutas privadas, enlaces o archivos no permitidos.")
        name = relative.as_posix()
        if name in names:
            raise StudioError("El editable contiene miembros repetidos.")
        names.add(name)
        digest = hf._sha(source)
        if digest != item.get("sha256") or proof_files.get(item["path"]) != digest:
            raise StudioError("Un archivo editable no coincide con la ejecución verificada.", 409)
        total += source.stat().st_size
        if total > MAX_BYTES:
            raise StudioError("El editable supera el límite local de 4 GiB.")
        entries.append((name, source, digest))
    required = {"index.html", "hyperframes.json", "runtime/gsap.min.js",
                "runtime/MotionPathPlugin.min.js", "runtime/third_party.json"}
    if not required.issubset(names) or not any(name.startswith("compositions/") for name in names):
        raise StudioError("Al editable le faltan HTML, subcomposiciones, fuentes o runtime local.")
    extra_fonts = {name for name in names if re.fullmatch(r"fonts/[0-9a-f]{20}\.(ttf|otf)", name)}
    extra_notices = {name for name in names if re.fullmatch(r"fonts/license_[0-9a-f]{20}\.txt", name)}
    if extra_fonts or extra_notices or "fonts/font_manifest.json" in names:
        if "fonts/font_manifest.json" not in names:
            raise StudioError("El manifiesto tipográfico debe estar incluido y cubierto por la ejecución verificada.", 409)
        try:
            font_manifest = json.loads((directory / "fonts/font_manifest.json").read_text())
            records = font_manifest["fonts"]
            if not isinstance(records, list) or not records or len(records) > 64:
                raise ValueError()
            declared_fonts, declared_notices = set(), set()
            entry_hashes = {name: digest for name, _, digest in entries}
            for record in records:
                name, digest = record["file"], record["sha256"]
                if name not in extra_fonts or not re.fullmatch(r"[0-9a-f]{64}", digest) or entry_hashes[name] != digest or name.split("/")[1].split(".")[0] != digest[:20]:
                    raise ValueError()
                if name in declared_fonts or record.get("synthetic_style") is not False:
                    raise ValueError()
                declared_fonts.add(name)
                license = record.get("license", {})
                notice = license.get("bundled_notice")
                if notice:
                    notice_digest = license.get("notice_sha256")
                    if notice not in extra_notices or not isinstance(notice_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", notice_digest) or entry_hashes[notice] != notice_digest or notice != "fonts/license_" + notice_digest[:20] + ".txt":
                        raise ValueError()
                    declared_notices.add(notice)
            roles = font_manifest.get("roles", {})
            if roles:
                if not isinstance(roles, dict) or set(roles) != {"primary", "accent"}:
                    raise ValueError()
                by_id = {record["asset_id"]: record for record in records}
                if len(by_id) != len(records):
                    raise ValueError()
                for role in roles.values():
                    if not isinstance(role, dict) or set(role) != {"asset_id", "file", "sha256"}:
                        raise ValueError()
                    record = by_id[role["asset_id"]]
                    if any(role[key] != record[key] for key in ("file", "sha256")):
                        raise ValueError()
            elif not {"fonts/primary.ttf", "fonts/accent.ttf"}.issubset(names):
                raise ValueError()
            if declared_fonts != extra_fonts or declared_notices != extra_notices:
                raise ValueError()
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            raise StudioError("El manifiesto de fuentes y sus avisos no cubre los bytes editables verificados.", 409) from error
    elif not {"fonts/primary.ttf", "fonts/accent.ttf"}.issubset(names):
        raise StudioError("Al editable le faltan los dos roles tipográficos.", 409)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = hf._target(root, destination.parent / ("motion_" + uuid.uuid4().hex + ".tmp"))
    report = {"schema": 1, "engine": "HyperFrames + GSAP", "cli_version": adapter["cli_version"],
              "gsap_version": adapter["gsap_version"], "render_sha256": receipt["sha256"],
              "static_only": bool(adapter.get("static_only")), "editorial_approved": False,
              "files": [{"path": name, "sha256": digest} for name, _, digest in entries]}
    readme = """# Composición visual editable

Abra esta carpeta con una CLI local compatible de HyperFrames. El punto de
entrada es index.html; sus subcomposiciones, medios, fuentes y scripts usan
rutas relativas. El ZIP conserva los bytes de la ejecución verificada.
No incluye navegador, instaladores, cachés, acceso privado ni credenciales.

La composición HTML contiene la imagen. La narración original, la música y
los efectos se mezclan después con FFmpeg desde el proyecto canónico principal;
este paquete visual no sustituye ese proyecto ni su cronología de audio.

GSAP y MotionPathPlugin conservan sus cabeceras y su licencia separada
Standard 'no charge'; consulte runtime/third_party.json y https://gsap.com/standard-license.
Las fuentes conservan sus familias y variantes reales. Cuando existe,
fonts/font_manifest.json identifica sus roles, hashes y avisos de licencia.
Este paquete no asigna permisos nuevos para redistribuir fuentes o medios.

La evidencia técnica no aprueba el diseño, la animación, el estilo ni una
entrega. La aprobación explícita y revisión humana siguen pendientes.
"""
    try:
        with zipfile.ZipFile(staging, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for name, source, digest in entries:
                current = hashlib.sha256()
                with source.open("rb") as incoming, archive.open(name, "w", force_zip64=True) as outgoing:
                    while chunk := incoming.read(1024 * 1024):
                        current.update(chunk)
                        outgoing.write(chunk)
                if current.hexdigest() != digest or hf._sha(source) != digest:
                    raise StudioError("El recurso cambió mientras se empaquetaba; no se entrega el ZIP.", 409)
            archive.writestr("README.md", readme)
            archive.writestr("bundle_manifest.json", json.dumps(report, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(staging) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(entries) + 2:
                raise StudioError("El paquete editable no pasó la comprobación CRC/cobertura.")
        if not hf.verify_receipt(receipt, root):
            raise StudioError("La evidencia dejó de ser actual durante el empaquetado.", 409)
        try:
            os.link(staging, destination)
        except FileExistsError as error:
            raise StudioError("El destino apareció durante el empaquetado; no se reemplaza.", 409) from error
    finally:
        staging.unlink(missing_ok=True)
    return {"path": str(destination.relative_to(root)), "size": destination.stat().st_size,
            "sha256": hf._sha(destination), "file_count": len(entries) + 2,
            "uncompressed_bytes": total, "editorial_approved": False, "render_sha256": receipt["sha256"]}
