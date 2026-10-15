"""Canonical local font inspection; no system font lookup or remote downloads."""
from __future__ import annotations

import copy
import hashlib
import io
import re
import struct
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from . import core

MAX_FONT_BYTES = 16 * 1024 * 1024
FORMATS = {".ttf", ".otf"}
LICENSE_REGISTRY = ".estado/fonts/licensed.json"


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _clean(value):
    return "".join(c for c in value if ord(c) >= 32 or c in "\n\t")[:2000]


def _tables(data):
    if len(data) < 12 or data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise core.StudioError("Solo fuentes TTF/OTF individuales; WOFF y colecciones TTC no se admiten.")
    count = struct.unpack_from(">H", data, 4)[0]
    if not 1 <= count <= 256 or 12 + count * 16 > len(data):
        raise core.StudioError("Directorio tipográfico inválido.")
    tables = {}
    for index in range(count):
        tag, _, offset, size = struct.unpack_from(">4sIII", data, 12 + index * 16)
        if tag in tables or offset < 12 + count * 16 or offset + size > len(data):
            raise core.StudioError("Tabla tipográfica fuera de límites o repetida.")
        tables[tag] = data[offset:offset + size]
    return tables


def _names(data):
    if len(data) < 6:
        return {}
    _, count, strings = struct.unpack_from(">HHH", data)
    if count > 2048 or 6 + count * 12 > len(data) or strings > len(data):
        raise core.StudioError("Tabla de nombres tipográficos inválida.")
    records = {}
    priority = {}
    for index in range(count):
        platform, _, language, name_id, length, offset = struct.unpack_from(">6H", data, 6 + index * 12)
        low, high = strings + offset, strings + offset + length
        if high > len(data):
            raise core.StudioError("Un nombre tipográfico supera su tabla.")
        if name_id not in (0, 1, 2, 4, 5, 6, 13, 14, 16, 17):
            continue
        encoding = "utf-16-be" if platform in (0, 3) else "mac_roman"
        value = _clean(data[low:high].decode(encoding, errors="replace"))
        rank = (platform in (0, 3), language in (0, 0x409))
        if name_id not in records or rank > priority[name_id]:
            records[name_id], priority[name_id] = value, rank
    return records


@lru_cache(maxsize=128)
def _inspect(path_string, signature):
    path = Path(path_string)
    if not 1 <= signature[2] <= MAX_FONT_BYTES:
        raise core.StudioError("La fuente supera 16 MiB o está vacía.", 413)
    data = path.read_bytes()
    if len(data) != signature[2] or _signature(path) != signature:
        raise core.StudioError("La fuente cambió durante su inspección.", 409)
    tables = _tables(data)
    names = _names(tables.get(b"name", b""))
    try:
        from fontTools.ttLib import TTFont
        with TTFont(io.BytesIO(data), lazy=False) as parsed:
            if not parsed.getBestCmap():
                raise ValueError("missing unicode cmap")
    except Exception as error:
        raise core.StudioError("La tabla Unicode de la fuente TTF/OTF es inválida.") from error
    try:
        face = ImageFont.truetype(str(path), 24)
        family, style = face.getname()
        face.getbbox("Áéñ¿€ Aa 0123")
    except (OSError, ValueError) as error:
        raise core.StudioError("El archivo no es una fuente TTF/OTF decodificable.") from error
    os2 = tables.get(b"OS/2", b"")
    fs_type = struct.unpack_from(">H", os2, 8)[0] if len(os2) >= 10 else None
    if _signature(path) != signature or path.read_bytes() != data:
        raise core.StudioError("La fuente cambió durante su carga.", 409)
    return {"family": _clean(family), "style": _clean(style), "full_name": names.get(4, family),
            "postscript_name": names.get(6), "version": names.get(5), "copyright": names.get(0),
            "embedded_license_text": names.get(13), "embedded_license_url": names.get(14),
            "embedding_flags": fs_type, "variable_axes_present": b"fvar" in tables,
            "format": path.suffix.lstrip("."), "sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "synthetic_style": False,
            "glyph_sample": "Áéñ¿€ Aa 0123", "glyph_coverage_verified": False}


def inspect_font(path, root=None):
    root = core.ROOT if root is None else Path(root).resolve()
    path = core.confined(path, root=root, must_exist=True)
    if path.suffix.lower() not in FORMATS:
        raise core.StudioError("Las fuentes locales admiten TTF y OTF.")
    signature = _signature(path)
    metadata = _inspect(str(path), signature)
    if _signature(path) != signature:
        raise core.StudioError("La fuente cambió durante su inspección.", 409)
    return copy.deepcopy(metadata)


def validate_asset_font(item, root=None):
    root = core.ROOT if root is None else Path(root).resolve()
    if not isinstance(item, dict) or item.get("kind") != "font":
        raise core.StudioError("El texto requiere una fuente canónica registrada.")
    path = core.confined(item.get("path", ""), root=root, must_exist=True)
    if not path.is_relative_to(root / "assets/fonts"):
        raise core.StudioError("La fuente del texto debe quedar en assets/fonts.", 403)
    expected = item.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise core.StudioError("La fuente necesita su SHA-256 canónico.")
    metadata = inspect_font(path, root)
    if metadata["sha256"] != expected:
        raise core.StudioError("La fuente canónica cambió; vuelve a comprobar su archivo.", 409)
    return {**metadata, "path": path.relative_to(root).as_posix()}


def font_assets(project, root=None):
    """Validate referenced, attached font assets, without a global catalog lookup."""
    root = core.ROOT if root is None else Path(root).resolve()
    ids = set()
    try:
        for scene in project.get("timeline", []):
            for el in (scene.get("motion_design") or {}).get("elements", []):
                reference = el.get("font_asset_id")
                if reference is not None:
                    if el.get("type") != "text" or not isinstance(reference, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", reference):
                        raise core.StudioError("La fuente de un elemento de texto requiere un ID literal.")
                    ids.add(reference)
        attached = {item["id"]: item for item in project.get("assets", [])}
    except (AttributeError, TypeError, KeyError) as error:
        raise core.StudioError("Proyecto o referencias de fuente inválidos.") from error
    result = {}
    for asset_id in ids:
        if asset_id not in attached:
            raise core.StudioError("La fuente seleccionada debe estar adjunta al proyecto.")
        item = attached[asset_id]
        validated = validate_asset_font(item, root)
        result[asset_id] = {**item, "path": validated["path"]}
    return result


def license_info(item, root=None):
    root = core.ROOT if root is None else Path(root).resolve()
    unknown = {"status": "supplied_by_user_unverified", "label": "Permisos de uso por comprobar",
               "source_url": None, "notice_path": None, "notice_url": None}
    if not isinstance(item, dict):
        return unknown
    path = core.confined(LICENSE_REGISTRY, root=root)
    if not path.exists():
        return _supplied_notice(item, root, unknown)
    try:
        import json
        registry = json.loads(path.read_text())
        records = registry.get("fonts", [])
        if not isinstance(records, list) or len(records) > 256:
            return _supplied_notice(item, root, unknown)
        record = next((record for record in records if record.get("sha256") == item.get("sha256")), None)
        if not record or record.get("license") != "OFL-1.1":
            return _supplied_notice(item, root, unknown)
        notice = core.confined(record["notice_path"], root=root, must_exist=True)
        if not notice.is_relative_to(root / "assets/fonts/licenses"):
            return unknown
        if not 1 <= notice.stat().st_size <= 65536 or _sha(notice) != record["notice_sha256"]:
            return unknown
        if not isinstance(record.get("source_url"), str) or not record["source_url"].startswith("https://raw.githubusercontent.com/"):
            return unknown
        return {"status": "source_verified", "label": "SIL Open Font License 1.1",
                "source_url": record["source_url"], "notice_path": notice.relative_to(root).as_posix(),
                "notice_url": "/api/font-notices/" + item['id'] if item.get('id') else None,
                "notice_sha256": record["notice_sha256"], "reserved_names": record.get("reserved_names", [])}
    except (core.StudioError, OSError, ValueError, KeyError, TypeError, AttributeError):
        return unknown


def notice_file(item, root=None):
    root = core.ROOT if root is None else Path(root).resolve()
    metadata = item.get("metadata") if isinstance(item, dict) else None
    notice = metadata.get("font_notice") if isinstance(metadata, dict) else None
    if not isinstance(item, dict) or item.get("kind") != "font" or not isinstance(notice, dict):
        raise core.StudioError("No hay un aviso de licencia tipográfica asociado.")
    expected = notice.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        raise core.StudioError("El aviso requiere SHA-256 completo.")
    relative = "assets/fonts/licenses/" + expected[:24] + ".txt"
    if notice.get("path") != relative:
        raise core.StudioError("El aviso debe usar su ruta canónica por contenido.", 403)
    path = core.confined(relative, root=root, must_exist=True)
    if not path.is_relative_to(root / "assets/fonts/licenses"):
        raise core.StudioError("Aviso fuera de la biblioteca de fuentes.", 403)
    if not 1 <= path.stat().st_size <= 65536 or _sha(path) != expected:
        raise core.StudioError("El aviso tipográfico cambió o supera su límite.", 409)
    return path


def _supplied_notice(item, root, unknown):
    metadata = item.get("metadata") if isinstance(item, dict) else None
    if not isinstance(metadata, dict) or not metadata.get("font_notice"):
        return unknown
    try:
        path = notice_file(item, root)
        return {"status": "bundled_notice_unverified", "label": "Aviso aportado; permisos por comprobar",
                "notice_path": path.relative_to(root).as_posix(), "notice_url": "/api/font-notices/" + item['id'] if item.get('id') else None,
                "notice_sha256": _sha(path), "source_url": None}
    except (core.StudioError, TypeError, AttributeError):
        return unknown


def catalog():
    roles, imported = [], []
    for role, path in core.fonts().items():
        entry = {"id": None, "asset_id": None, "role": role, "path": path,
                 "name": "Sequel Sans Bold Disp" if role == "primary" else "Scholar Italic"}
        try:
            entry.update(inspect_font(path), available=True, url="/api/files/" + path,
                         license=license_info({"sha256": core.content_hash(path)}))
        except (core.StudioError, OSError) as error:
            entry.update(available=False, unavailable_reason=str(error), license=license_info({}))
        roles.append(entry)
    for item in core.assets():
        if item.get("kind") != "font":
            continue
        entry = {"id": item["id"], "asset_id": item["id"], "role": None, "name": item["name"],
                 "url": item.get("url", "/api/media/" + item["id"])}
        try:
            entry.update(validate_asset_font(item), available=True, license=license_info(item))
        except (core.StudioError, OSError) as error:
            entry.update(available=False, unavailable_reason=str(error), license=license_info({}))
        imported.append(entry)
    return {"roles": roles, "fonts": imported, "formats": ["ttf", "otf"],
            "max_upload_bytes": MAX_FONT_BYTES, "automatic_substitution": False,
            "synthetic_weights": False, "network_downloads": False}
