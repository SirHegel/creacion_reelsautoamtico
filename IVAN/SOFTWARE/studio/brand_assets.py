"""Workspace brand files with observed scope and bounded official provenance.

A URL supplied by a user is a declaration. Only a bounded HTTPS acquisition
from an exact catalog URL proves that the canonical bytes came from that URL.
Neither operation grants trademark rights or approves an edit for publication.
"""
from __future__ import annotations

import copy
import hashlib
import io
import ipaddress
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import socket
import ssl
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from PIL import Image

from . import core, resource_review

CODE_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE = 4 * 1024 * 1024
MAX_SVG = 1024 * 1024
MAX_PIXELS = 16_000_000
MAX_REGISTRY = 2 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{64}")
ASSET = re.compile(r"a_[A-Za-z0-9_-]{1,100}")
CONTEXTS = {"private_review", "publication"}
REGISTRATION_FIELDS = {"entity", "expected_source_sha256", "expected_registry_digest", "source_url",
                       "license_label", "conditions", "reviewer", "observation", "visual_reviewed",
                       "expected_review_digest", "usage_context", "publication"}
REQUIRED_FIELDS = REGISTRATION_FIELDS - {"usage_context", "publication"}
ORIGINS = {
    "google": {"name": "Google", "page": "https://about.google/brand-resource-center/",
               "guidelines": "https://about.google/brand-resource-center/guidance/",
               "hosts": ["about.google", "www.google.com", "www.gstatic.com"],
               "conditions": "Marca propietaria; reglas de uso y ausencia de afiliación. Algunos usos requieren permiso; el archivo no concede publicación.",
               "research_status": "official_guidelines_read",
               "variants": {"wordmark": {"url": "https://www.gstatic.com/marketing-cms/assets/images/c5/3a/200414104c669203c62270f7884f/google-wordmarks-2x.webp=n-w150-h48-fcrop64=1,00000000ffffffff-rw", "format": "webp", "role": "wordmark"}}},
    "claude": {"name": "Claude", "page": "https://claude.com/", "guidelines": "https://www.anthropic.com/",
               "hosts": ["claude.com", "www.claude.com", "www.anthropic.com", "assets.claude.com", "assets.anthropic.com"],
               "conditions": "Identidad oficial de Claude/Anthropic; condiciones de redistribución del icono no confirmadas. Publicación pendiente.",
               "research_status": "official_identity_read_brand_license_unconfirmed",
               "variants": {"site_icon": {"url": "https://claude.com/icon.png", "format": "png", "role": "site_icon_not_wordmark"}}},
    "linkedin": {"name": "LinkedIn", "page": "https://brand.linkedin.com/en-us",
                 "guidelines": "https://brand.linkedin.com/linkedin-logo",
                 "hosts": ["brand.linkedin.com", "static.licdn.com", "delivery-p143253-e1476319.adobeaemcloud.com"],
                 "conditions": "El logo LinkedIn requiere una relación y licencia separada; el icono [in] tiene usos restringidos. Revisar guía y autorización para video/publicación.",
                 "research_status": "official_guidelines_read_permission_required_for_wordmark",
                 "variants": {"site_icon": {"url": "https://static.licdn.com/scds/common/u/images/logos/linkedin/logo-in-win8-tile-144_v1.png", "format": "png", "role": "in_site_icon_not_wordmark"}}},
    "youtube": {"name": "YouTube", "page": "https://brand.youtube/", "guidelines": "https://brand.youtube/",
                "hosts": ["brand.youtube", "www.youtube.com", "www.gstatic.com"],
                "conditions": "Marca propietaria. Portal oficial consultado; detalle de permisos de este recurso no confirmado. No afirmar patrocinio ni autorización pública.",
                "research_status": "official_portal_read_detailed_conditions_unconfirmed",
                "variants": {"site_icon": {"url": "https://www.gstatic.com/marketing-cms/assets/images/98/c6/59f93f6f4ac1a8e63612c5370193/favicon-1.png", "format": "png", "role": "site_icon_not_wordmark"}}},
    "instagram": {"name": "Instagram", "page": "https://about.meta.com/brand/resources/instagram/instagram-brand/",
                  "guidelines": "https://about.meta.com/brand/resources/instagram/instagram-brand/",
                  "hosts": ["about.meta.com", "www.facebook.com", "about.instagram.com", "static.cdninstagram.com"],
                  "conditions": "Marca propietaria. El portal requiere acceso en la consulta; el kit ZIP no se descarga/extracciona aquí. Importar archivo propio y documentar condiciones; publicación pendiente.",
                  "research_status": "official_portal_access_limited_no_individual_png_pinned",
                  "variants": {}},
}
RECORD_FIELDS = {"id", "entity", "asset_id", "path", "sha256", "size", "image", "origin", "license_label",
                 "conditions", "usage_context", "review", "publication", "fingerprints", "at", "previous_seal", "seal"}


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError) as error:
        raise core.StudioError("El registro de marcas requiere datos JSON finitos.") from error


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _text(value, label, low=1, high=4000):
    if (not isinstance(value, str) or len(value) > high or not low <= len(value.strip()) <= high or
            any(ord(c) < 32 and c not in "\n\t" for c in value)):
        raise core.StudioError("Texto de marca inválido: " + label)
    return value.strip()


def _hash(value, label):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise core.StudioError("SHA completo requerido: " + label)
    return value


def _entity(value):
    if not isinstance(value, str) or value not in ORIGINS:
        raise core.StudioError("Entidad de marca desconocida.")
    return value


def _context(value):
    if not isinstance(value, str) or value not in CONTEXTS:
        raise core.StudioError("El contexto debe ser private_review o publication.")
    return value


def _scope():
    root = Path(core.ROOT).absolute()
    try:
        valid = (core.WORKSPACE_MODE and root.resolve() == root and root != CODE_ROOT and
                 root.is_relative_to(CODE_ROOT) and root.is_dir() and
                 (root / ".estado").resolve() == root / ".estado" and (root / ".estado").is_dir())
    except (OSError, RuntimeError, ValueError):
        valid = False
    if not valid:
        raise core.StudioError("El registro de marcas requiere un workspace propio canónico.", 403)
    return root


def _path(relative, *, exists=False):
    root = _scope()
    if not isinstance(relative, str) or "\\" in relative:
        raise core.StudioError("Ruta de marca inválida.", 403)
    p = PurePosixPath(relative)
    if p.is_absolute() or p.as_posix() != relative or any(x in {".", ".."} for x in p.parts):
        raise core.StudioError("Ruta de marca no canónica.", 403)
    path = root / relative
    try:
        valid = path.resolve() == path and path.is_relative_to(root)
    except (OSError, RuntimeError, ValueError):
        valid = False
    if not valid:
        raise core.StudioError("La marca no admite enlaces ni escapes de workspace.", 403)
    if exists and not path.is_file():
        raise core.StudioError("Falta el archivo propio de la marca.", 409)
    return path


def _read_file(relative, limit=MAX_FILE):
    path = _path(relative, exists=True)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 1 <= info.st_size <= limit:
        raise core.StudioError("El recurso de marca debe ser regular e individual, dentro del límite.", 413)
    before = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = path.lstat()
    if before != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or len(raw) != info.st_size:
        raise core.StudioError("El recurso de marca cambió durante la lectura.", 409)
    return raw


def inspect_svg(raw):
    """Strict passive SVG metadata; never execute, preview or claim rasterization."""
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_SVG:
        raise core.StudioError("SVG demasiado grande o con entidades externas.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise core.StudioError("El SVG pasivo requiere UTF-8.") from error
    stripped = re.sub(r"^\s*<\?xml\s+[^?]{1,240}\?>", "", text, count=1)
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?", stripped, re.I):
        raise core.StudioError("SVG contiene entidades o instrucciones activas.")
    try:
        tree = ET.fromstring(text)
    except (ET.ParseError, ValueError) as error:
        raise core.StudioError("SVG mal formado.") from error
    tags = {"svg", "g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "defs", "symbol", "use",
            "linearGradient", "radialGradient", "stop", "clipPath", "mask", "title", "desc", "metadata"}
    attrs = {"id", "viewBox", "width", "height", "x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry",
             "d", "points", "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width", "stroke-linecap",
             "stroke-linejoin", "stroke-opacity", "opacity", "transform", "gradientUnits", "gradientTransform",
             "offset", "stop-color", "stop-opacity", "clip-path", "clip-rule", "mask", "maskUnits", "href", "version"}
    ids, refs, count = set(), [], 0
    stack = [(tree, 0)]
    while stack:
        node, depth = stack.pop();count += 1
        if count > 4096 or depth > 64:
            raise core.StudioError("SVG excede su complejidad máxima.")
        namespace, _, tag = node.tag.rpartition("}")
        if (namespace and namespace != "{http://www.w3.org/2000/svg") or tag not in tags or (count == 1 and tag != "svg"):
            raise core.StudioError("SVG contiene contenido activo, externo o no admitido.")
        for key, value in node.attrib.items():
            ns, _, name = key.rpartition("}")
            if (ns and not (ns == "{http://www.w3.org/1999/xlink" and name == "href")) or name not in attrs:
                raise core.StudioError("Atributo activo o no admitido en SVG.")
            if len(value) > 32000 or any(ord(c) < 32 for c in value):
                raise core.StudioError("Atributo SVG fuera de límites.")
            if name == "id":
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,99}", value) or value in ids:
                    raise core.StudioError("IDs SVG inválidos o repetidos.")
                ids.add(value)
            if name == "href":
                if not re.fullmatch(r"#[A-Za-z_][A-Za-z0-9_-]{0,99}", value):
                    raise core.StudioError("SVG no admite recursos externos.")
                refs.append(value[1:])
            if re.search(r"url\s*\(", value, re.I):
                match = re.fullmatch(r"url\(#[A-Za-z_][A-Za-z0-9_-]{0,99}\)", value)
                if not match:
                    raise core.StudioError("SVG no admite URLs externas o CSS.")
                refs.append(value[5:-1])
            if re.search(r"(?:https?:|file:|data:|javascript:|@import|expression\s*\()", value, re.I):
                raise core.StudioError("SVG no admite ejecución o recursos externos.")
        stack.extend((child, depth + 1) for child in node)
    if any(ref not in ids for ref in refs):
        raise core.StudioError("SVG contiene referencias internas inexistentes.")
    box = tree.get("viewBox")
    if box is not None:
        try:
            values = [float(value) for value in re.split(r"[\s,]+", box.strip())]
        except ValueError as error:
            raise core.StudioError("viewBox SVG inválido.") from error
        if len(values) != 4 or any(not math.isfinite(value) or abs(value) > 1_000_000 for value in values) or min(values[2:]) <= 0:
            raise core.StudioError("viewBox SVG fuera de límites.")
    return {"format": "SVG", "nodes": count, "safe_passive_subset": True,
            "render_ready": False, "limitation": "Solo metadata pasiva; este motor no rasteriza SVG.",
            "sha256": hashlib.sha256(raw).hexdigest()}


def _image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "WEBP"} or getattr(image, "n_frames", 1) != 1 or image.width * image.height > MAX_PIXELS:
                raise core.StudioError("Usa PNG/WebP estático real dentro del presupuesto de píxeles.")
            info = {"format": image.format, "width": image.width, "height": image.height, "render_ready": True}
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise core.StudioError("El logo no es un PNG/WebP decodificable.") from error
    return info


def _asset(asset_id):
    if not isinstance(asset_id, str) or not ASSET.fullmatch(asset_id):
        raise core.StudioError("ID canónico de marca inválido.")
    _scope()
    item = core.asset(asset_id)
    rows = core.assets()
    by_id = {row.get("id"): row for row in rows if isinstance(row, dict)}
    by_sha = {row.get("sha256"): row for row in rows if isinstance(row, dict) and row.get("sha256")}
    cursor, seen = item, set()
    for _ in range(64):
        identity = cursor.get("id") or cursor.get("sha256")
        if identity in seen or cursor.get("kind") in {"video", "broll", "audio"}:
            raise core.StudioError("Un derivado del crudo/video no acredita un logo original independiente.", 403)
        seen.add(identity)
        metadata = cursor.get("metadata") if isinstance(cursor.get("metadata"), dict) else {}
        provenance = metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
        parent_id = provenance.get("source_asset_id")
        if parent_id is None and isinstance(metadata.get("source"), str) and ASSET.fullmatch(metadata["source"]):
            parent_id = metadata["source"]
        parent_sha = provenance.get("source_sha256")
        if parent_id is None and parent_sha is None:
            break
        if (parent_id is not None and (not isinstance(parent_id, str) or not ASSET.fullmatch(parent_id))) or \
                (parent_sha is not None and (not isinstance(parent_sha, str) or not SHA.fullmatch(parent_sha))):
            raise core.StudioError("La procedencia de la imagen de marca está mal formada.", 403)
        cursor = by_id.get(parent_id) or by_sha.get(parent_sha)
        if not isinstance(cursor, dict):
            raise core.StudioError("La procedencia de la marca no puede verificarse en la biblioteca propia.", 403)
    else:
        raise core.StudioError("La cadena de procedencia de la marca excede su límite.", 403)
    path = item.get("path")
    if (item.get("kind") != "image" or not isinstance(path, str) or
            PurePosixPath(path).parts[:2] != ("assets", "images")):
        raise core.StudioError("La marca debe ser una imagen de la biblioteca propia.", 403)
    raw = _read_file(path)
    sha = hashlib.sha256(raw).hexdigest()
    if sha != _hash(item.get("sha256"), "asset") or type(item.get("size")) is not int or len(raw) != item["size"]:
        raise core.StudioError("El archivo de marca no coincide con el catálogo canónico.", 409)
    image = _image(raw)
    return item, image


def _fingerprints():
    return {"code": {name: core.digest(Path(__file__).with_name(name)) for name in ("brand_assets.py", "resource_review.py")},
            "manual": core.manual_fingerprints()}


def _pairs(rows):
    result = {}
    for key, value in rows:
        if key in result:
            raise core.StudioError("Claves duplicadas en el registro privado.", 409)
        result[key] = value
    return result


def _load():
    path = _path(".estado/brand_assets/registry.json")
    if not path.exists():
        return {"schema": "ascendia.brand-assets/1", "revision": 0, "records": {}}
    try:
        data = json.loads(_read_file(".estado/brand_assets/registry.json", MAX_REGISTRY), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if (not isinstance(data, dict) or set(data) != {"schema", "revision", "records"} or
                data["schema"] != "ascendia.brand-assets/1" or type(data["revision"]) is not int or
                not 0 <= data["revision"] <= 2147483647 or not isinstance(data["records"], dict) or len(data["records"]) > 256):
            raise ValueError("shape")
        for key, row in data["records"].items():
            if (not isinstance(row, dict) or set(row) != RECORD_FIELDS or not re.fullmatch(r"ba_[a-f0-9]{24}", key) or
                    row["id"] != key or row["seal"] != _digest({k: v for k, v in row.items() if k != "seal"})):
                raise ValueError("seal")
    except (ValueError, TypeError, KeyError) as error:
        raise core.StudioError("El registro privado de marcas está mal formado o alterado.", 409) from error
    return data


def _save(data):
    from .providers import private_write
    if (not isinstance(data, dict) or not isinstance(data.get("records"), dict) or len(data["records"]) > 256 or
            type(data.get("revision")) is not int or not 0 <= data["revision"] <= 2147483647):
        raise core.StudioError("El registro de marcas excede su límite de entradas o revisión.", 413)
    raw = _json(data)
    if len(raw) > MAX_REGISTRY:
        raise core.StudioError("El registro de marcas supera su presupuesto.", 413)
    path = _path(".estado/brand_assets/registry.json")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_write(path, raw)


def _official_url(entity, value):
    value = _text(value, "source_url", high=2048)
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in ORIGINS[entity]["hosts"] or parsed.username or
                parsed.password or parsed.port not in {None, 443} or parsed.query or parsed.fragment or "\\" in value):
            raise ValueError("origin")
    except ValueError as error:
        raise core.StudioError("La procedencia debe ser una URL HTTPS del origen oficial conocido, sin credenciales.") from error
    return value


def _publication(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {"declaration", "evidence"}:
        raise core.StudioError("La declaración de publicación requiere declaración y evidencia propias.")
    declaration = _text(value["declaration"], "publication.declaration", 16, 4000)
    evidence = value["evidence"]
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 8:
        raise core.StudioError("La publicación requiere documentos propios con SHA.")
    result, seen = [], set()
    for row in evidence:
        if not isinstance(row, dict) or set(row) != {"asset_id", "sha256"}:
            raise core.StudioError("Evidencia de publicación mal formada.")
        item, _ = _asset(row["asset_id"])
        if item["id"] in seen or item["sha256"] != _hash(row["sha256"], "publication.evidence"):
            raise core.StudioError("Documento de autorización duplicado u obsoleto.", 409)
        seen.add(item["id"])
        result.append({"asset_id": item["id"], "sha256": item["sha256"], "path": item["path"]})
    return {"declaration": declaration, "evidence": result, "status": "user_declared_with_hashed_evidence",
            "rights_authority": False, "publication_approved": False}


def _permission_current(value):
    if value is None:
        return False
    if (not isinstance(value, dict) or set(value) != {"declaration", "evidence", "status", "rights_authority", "publication_approved"} or
            value["status"] != "user_declared_with_hashed_evidence" or value["rights_authority"] is not False or
            value["publication_approved"] is not False):
        raise core.StudioError("Declaración de publicación privada inválida.", 409)
    for row in value["evidence"]:
        item, _ = _asset(row["asset_id"])
        if item["sha256"] != row["sha256"] or item["path"] != row["path"]:
            raise core.StudioError("La evidencia de publicación cambió.", 409)
    return True


def _origin_current(row):
    origin = row["origin"]
    entity = _entity(row["entity"])
    if (not isinstance(origin, dict) or type(origin.get("verified")) is not bool or
            type(origin.get("fetched")) is not bool or origin.get("content_sha256") != row["sha256"] or
            origin.get("guidelines_url") != ORIGINS[entity]["guidelines"]):
        raise core.StudioError("El origen privado de la marca es inválido.", 409)
    _official_url(entity, origin.get("source_url"))
    if origin["verified"]:
        variant = ORIGINS[entity]["variants"].get(origin.get("variant"))
        if (origin.get("status") != "fetched_official_https" or origin["fetched"] is not True or not variant or
                variant["url"] != origin["source_url"] or origin.get("tls_verified") is not True or
                origin.get("cookies_sent") is not False or origin.get("proxy_used") is not False or
                origin.get("method") != "exact_fixed_catalog_url_no_redirect"):
            raise core.StudioError("El sello de adquisición oficial no coincide con el catálogo.", 409)
    elif origin.get("status") != "user_declared_official_url" or origin["fetched"] is not False:
        raise core.StudioError("El origen declarado no acredita una descarga oficial.", 409)
    return origin


def _current(row, context):
    try:
        if row["fingerprints"] != _fingerprints():
            raise core.StudioError("Cambió el manual o código del registro.", 409)
        _origin_current(row)
        if row["asset_id"] is None:
            if row["path"] != "assets/brand_vectors/" + _hash(row["sha256"], "vector") + ".svg":
                raise core.StudioError("El SVG debe usar su ruta vectorial canónica por SHA.", 403)
            raw = _read_file(row["path"], MAX_SVG)
            inspect_svg(raw)
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise core.StudioError("El SVG original cambió.", 409)
            return {"valid": True, "status": "pending_svg_metadata_only", "render_ready": False,
                    "eligible_for_context": False, "source_verified": row["origin"]["verified"],
                    "visual_reviewed": False, "publication_approved": False, "rights_authority": False}
        item, image = _asset(row["asset_id"])
        if item["path"] != row["path"] or item["sha256"] != row["sha256"] or item["size"] != row["size"] or image != row["image"]:
            raise core.StudioError("La marca canónica cambió.", 409)
        review = row["review"]
        observed = False
        if review is not None:
            live = resource_review.current_review(item)
            if not live["valid"] or live["review_digest"] != review["review_digest"] or live["receipt_sha256"] != review["receipt_sha256"]:
                raise core.StudioError("La observación de la marca está ausente u obsoleta.", 409)
            observed = review.get("visual_reviewed") is True
        permission = _permission_current(row["publication"])
        return {"valid": True, "status": "observed" if observed else "pending_observation", "render_ready": True,
                "eligible_for_context": observed and (context == "private_review" or permission),
                "source_verified": row["origin"]["verified"], "visual_reviewed": observed,
                "publication_declaration_current": permission, "publication_approved": False, "rights_authority": False}
    except (core.StudioError, KeyError, IndexError, TypeError, AttributeError, OSError, ValueError) as error:
        return {"valid": False, "status": "stale_or_missing", "eligible_for_context": False,
                "reason": str(error)[:500], "publication_approved": False, "rights_authority": False}


def origin_catalog():
    """Public source guidance, not a license or proof that any file was fetched."""
    return {"schema": "ascendia.brand-origins/1", "entities": [{"entity": entity, **copy.deepcopy(row)} for entity, row in ORIGINS.items()],
            "download_is_optional": True, "downloads_executed": False,
            "svg_render_supported": False, "private_review_is_publication_permission": False,
            "limits": {"download_bytes": MAX_FILE, "svg_bytes": MAX_SVG, "pixels": MAX_PIXELS, "deadline_seconds": 20}}


def catalog(context="private_review"):
    context = _context(context)
    with core.LOCK:
        data = _load()
        rows = [{**copy.deepcopy(row), "current": _current(row, context)} for row in data["records"].values()]
        return {"schema": data["schema"], "revision": data["revision"], "digest": _digest(data), "records": rows,
                "context": context, "rights_authority": False, "editorial_approved": False, "publication_approved": False}


def register(asset_id, options):
    """Seal an explicit current observation of a canonical user image."""
    if not isinstance(options, dict) or set(options) - REGISTRATION_FIELDS or not REQUIRED_FIELDS <= set(options):
        raise core.StudioError("Registro de marca incompleto o con campos desconocidos.")
    entity = _entity(options["entity"])
    context = _context(options.get("usage_context", "private_review"))
    for key in ("expected_source_sha256", "expected_registry_digest", "expected_review_digest"):
        _hash(options[key], key)
    url = _official_url(entity, options["source_url"])
    if options["visual_reviewed"] is not True:
        raise core.StudioError("La marca requiere observación visual explícita.")
    values = {key: _text(options[key], key, 24 if key == "observation" else 1, 120 if key == "reviewer" else 4000)
              for key in ("license_label", "conditions", "reviewer", "observation")}
    with core.LOCK:
        data = _load()
        if _digest(data) != options["expected_registry_digest"]:
            raise core.StudioError("El registro de marcas cambió; recarga antes de guardar.", 409)
        item, image = _asset(asset_id)
        if item["sha256"] != options["expected_source_sha256"]:
            raise core.StudioError("La marca cambió desde su selección.", 409)
        observation = resource_review.current_review(item)
        if not observation["valid"] or observation["review_digest"] != options["expected_review_digest"]:
            raise core.StudioError("Observa primero la imagen y registra evidencia vigente de su contenido.", 409)
        publication = _publication(options.get("publication"))
        if context == "publication" and publication is None:
            raise core.StudioError("La revisión privada no autoriza publicación; añade declaración y documento propios.", 409)
        key = "ba_" + _digest({"entity": entity, "sha256": item["sha256"]})[:24]
        old = data["records"].get(key)
        origin = {"status": "user_declared_official_url", "source_url": url, "guidelines_url": ORIGINS[entity]["guidelines"],
                  "verified": False, "fetched": False, "content_sha256": item["sha256"], "variant": None}
        if (old and old["origin"].get("fetched") is True and old["origin"].get("source_url") == url and
                old["fingerprints"] == _fingerprints() and old["asset_id"] == item["id"] and
                old["path"] == item["path"] and old["sha256"] == item["sha256"] and old["image"] == image):
            origin = copy.deepcopy(_origin_current(old))
        row = {"id": key, "entity": entity, "asset_id": item["id"], "path": item["path"], "sha256": item["sha256"],
               "size": item["size"], "image": image, "origin": origin, **values, "usage_context": context,
               "review": {"review_digest": observation["review_digest"], "receipt_sha256": observation["receipt_sha256"],
                          "reviewer": values["reviewer"], "observation": values["observation"], "visual_reviewed": True},
               "publication": publication, "fingerprints": _fingerprints(), "at": core.now(), "previous_seal": old["seal"] if old else None}
        row.pop("reviewer");row.pop("observation")
        row["seal"] = _digest(row)
        before = copy.deepcopy(data)
        data["records"][key] = row;data["revision"] += 1
        try:
            _save(data)
            current = _current(row, context)
            if not current["valid"]:
                raise core.StudioError("La marca cambió antes de confirmar su registro.", 409)
        except Exception:
            _save(before)
            raise
        return {**copy.deepcopy(row), "current": current, "rights_authority": False,
                "editorial_approved": False, "publication_approved": False}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise core.StudioError("La fuente oficial redirigió; no se sigue una URL no fijada.", 502)


def _request(url, deadline):
    fixed_urls = {variant["url"] for origin in ORIGINS.values() for variant in origin["variants"].values()}
    if not isinstance(url, str) or url not in fixed_urls:
        raise core.StudioError("La descarga solo admite URLs exactas fijadas en el catálogo.", 403)
    host = urllib.parse.urlsplit(url).hostname
    if time.monotonic() >= deadline:
        raise core.StudioError("La descarga oficial excedió su tiempo máximo.", 504)
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise core.StudioError("No se pudo resolver la fuente oficial.", 502) from error
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global or
                            ipaddress.ip_address(row[4][0]).is_multicast for row in addresses):
        raise core.StudioError("La fuente oficial resolvió una dirección privada o reservada.", 403)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise core.StudioError("La descarga oficial excedió su tiempo máximo.", 504)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(),
                                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    request = urllib.request.Request(url, headers={"User-Agent": "AscendiaStudio/0.6 public-brand-resource", "Accept": "image/png,image/webp,image/svg+xml"})
    try:
        with opener.open(request, timeout=min(5, remaining)) as response:
            if response.geturl() != url or response.status != 200:
                raise core.StudioError("Respuesta oficial no canónica.", 502)
            length = response.headers.get("Content-Length")
            if length is not None and (not length.isdigit() or not 1 <= int(length) <= MAX_FILE):
                raise core.StudioError("La fuente excede el presupuesto de descarga.", 413)
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise core.StudioError("La descarga oficial excedió su tiempo máximo.", 504)
                chunk = response.read(min(64 * 1024, MAX_FILE + 1 - size))
                if time.monotonic() >= deadline:
                    raise core.StudioError("La descarga oficial excedió su tiempo máximo.", 504)
                if not chunk:
                    break
                chunks.append(chunk);size += len(chunk)
                if size > MAX_FILE:
                    raise core.StudioError("La fuente excede el presupuesto de descarga.", 413)
            raw = b"".join(chunks)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise core.StudioError("Falló la descarga pública oficial: " + type(error).__name__, 502) from error
    if not raw:
        raise core.StudioError("La fuente oficial devolvió un archivo vacío.", 502)
    return raw


def fetch(entity, options=None):
    """Optional exact-URL HTTPS import, always pending visual/rights review."""
    entity = _entity(entity)
    options = {} if options is None else options
    if not isinstance(options, dict) or set(options) - {"variant", "expected_registry_digest"}:
        raise core.StudioError("Opciones de descarga oficial desconocidas.")
    variants = ORIGINS[entity]["variants"]
    variant = options.get("variant", next(iter(variants), None))
    if not isinstance(variant, str) or variant not in variants:
        raise core.StudioError("No existe un recurso individual fijado para esa marca/variante; importa uno propio.", 409)
    expected = options.get("expected_registry_digest")
    if expected is not None:
        _hash(expected, "expected_registry_digest")
    with core.LOCK:
        initial = _load();initial_digest = _digest(initial)
        if expected is not None and initial_digest != expected:
            raise core.StudioError("El registro cambió antes de descargar.", 409)
        for previous in initial["records"].values():
            if (previous["entity"] == entity and previous["origin"].get("variant") == variant and
                    previous["origin"].get("verified") is True):
                current = _current(previous, "private_review")
                if current["valid"]:
                    return {**copy.deepcopy(previous), "current": current, "reused": True,
                            "editorial_approved": False, "publication_approved": False}
    root = _scope()
    fingerprints = _fingerprints()
    source = variants[variant];url = _official_url(entity, source["url"])
    raw = _request(url, time.monotonic() + 20)
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_FILE:
        raise core.StudioError("Respuesta oficial inválida o demasiado grande.", 413)
    image = inspect_svg(raw) if source["format"] == "svg" else _image(raw)
    sha = hashlib.sha256(raw).hexdigest()
    from .jobs import cpu_slot
    with cpu_slot(), core.LOCK:
        data = _load()
        if _digest(data) != initial_digest or _fingerprints() != fingerprints:
            raise core.StudioError("El registro/manual/código cambió durante la descarga.", 409)
        key = "ba_" + _digest({"entity": entity, "sha256": sha})[:24]
        previous = data["records"].get(key)
        if previous and previous["origin"].get("source_url") == url and previous["origin"].get("verified") is True:
            current = _current(previous, "private_review")
            if current["valid"]:
                return {**copy.deepcopy(previous), "current": current, "reused": True,
                        "editorial_approved": False, "publication_approved": False}
        asset_id = None
        if source["format"] == "svg":
            path = "assets/brand_vectors/" + sha + ".svg"
            target = _path(path);target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if _read_file(path, MAX_SVG) != raw:
                    raise core.StudioError("La ruta canónica vectorial está ocupada por otro contenido.", 409)
            else:
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw);stream.flush();os.fsync(stream.fileno())
        else:
            temp_dir = _path(".estado/tmp");temp_dir.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix="brand_fetch_", suffix="." + image["format"].lower(), dir=temp_dir)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw);stream.flush();os.fsync(stream.fileno())
                item = core.register_asset(temp, name=ORIGINS[entity]["name"] + "_" + variant + "." + image["format"].lower(), kind="image",
                                           metadata={"source_url": url, "provenance": {"operation": "official_brand_download", "entity": entity}})
                item, actual_image = _asset(item["id"])
                if item["sha256"] != sha or actual_image != image:
                    raise core.StudioError("La copia canónica no coincide con la respuesta oficial.", 409)
                asset_id, path = item["id"], item["path"]
            finally:
                Path(temp).unlink(missing_ok=True)
        origin = {"status": "fetched_official_https", "source_url": url, "guidelines_url": ORIGINS[entity]["guidelines"],
                  "verified": True, "fetched": True, "content_sha256": sha, "variant": variant,
                  "role": source["role"], "tls_verified": True, "cookies_sent": False, "proxy_used": False,
                  "at": core.now(), "method": "exact_fixed_catalog_url_no_redirect"}
        row = {"id": key, "entity": entity, "asset_id": asset_id, "path": path, "sha256": sha, "size": len(raw), "image": image,
               "origin": origin, "license_label": "proprietary_trademark_conditions_apply", "conditions": ORIGINS[entity]["conditions"],
               "usage_context": "private_review", "review": None, "publication": None, "fingerprints": fingerprints,
               "at": core.now(), "previous_seal": previous["seal"] if previous else None}
        row["seal"] = _digest(row)
        before = copy.deepcopy(data);data["records"][key] = row;data["revision"] += 1
        try:
            _save(data)
            current = _current(row, "private_review")
            if not current["valid"]:
                raise core.StudioError("La copia descargada cambió antes de confirmar.", 409)
        except Exception:
            _save(before)
            raise
        return {**copy.deepcopy(row), "current": current, "reused": False,
                "editorial_approved": False, "publication_approved": False}


def resolve(entities, context="private_review"):
    """Resolve explicit entity requests; does not infer semantics or invent logos."""
    context = _context(context)
    if not isinstance(entities, list) or not 1 <= len(entities) <= 32:
        raise core.StudioError("Solicita entre una y treinta y dos entidades explícitas.")
    requests, seen = [], set()
    for value in entities:
        if isinstance(value, str):
            entity, reason = _entity(value), None
        elif isinstance(value, dict) and set(value) == {"entity", "reason"}:
            entity, reason = _entity(value["entity"]), _text(value["reason"], "reason", 8, 2000)
        else:
            raise core.StudioError("Solicitud de entidad mal formada.")
        if entity in seen:
            raise core.StudioError("Entidades repetidas en la selección.")
        seen.add(entity);requests.append((entity, reason))
    result = catalog(context)
    resolved, unresolved = [], []
    for entity, reason in requests:
        candidates = [row for row in result["records"] if row["entity"] == entity and row["current"].get("eligible_for_context")]
        candidates.sort(key=lambda row: (row["current"].get("source_verified") is True, row["at"], row["id"]), reverse=True)
        if candidates:
            chosen = candidates[0]
            resolved.append({"entity": entity, "reason": reason, "record": chosen, "selection_origin": "caller_declared_context",
                             "semantic_match_confirmed": False, "editorial_approved": False, "publication_approved": False})
        else:
            unresolved.append({"entity": entity, "reason": reason, "status": "missing_observed_current_resource",
                               "guidelines_url": ORIGINS[entity]["guidelines"], "text_substitution_applied": False})
    return {"context": context, "registry_digest": result["digest"], "resolved": resolved, "unresolved": unresolved,
            "inference_executed": False, "parent_assets_inherited": False, "editorial_approved": False, "publication_approved": False}


def current_record(asset_id, entity, context="private_review"):
    """Canonical sealed lookup for downstream save/render guards; no writes."""
    _entity(entity);_context(context)
    _asset(asset_id)
    values = [row for row in catalog(context)["records"] if row["entity"] == entity and row["asset_id"] == asset_id]
    row = next((row for row in values if row["current"].get("eligible_for_context")), None)
    if row is None:
        raise core.StudioError("La marca no tiene un registro observado vigente para este contexto.", 409)
    return row
