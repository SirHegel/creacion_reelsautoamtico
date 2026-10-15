"""Reopen a portable editable ZIP into the confined canonical project store.

ZIP paths are names, never filesystem destinations. Sources are verified by
content before registration. Imported observations remain drafts and confer
neither an editorial approval nor publication permission.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

from PIL import ImageFont

from . import core

MAX_MEMBERS = 5000
MAX_BYTES = 4 * 1024 ** 3
MAX_PROJECT_BYTES = 10 * 1024 ** 2
MAX_COMPRESSION_RATIO = 250
MEDIA_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg", ".mxf",
                  ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".gif", ".flv", ".wmv", ".ogv",
                  ".wav", ".mp3", ".flac", ".aac", ".m4a", ".ogg", ".opus", ".aif", ".aiff",
                  ".amr", ".ac3", ".eac3", ".au", ".ape", ".mp2", ".png", ".jpg", ".jpeg",
                  ".webp", ".bmp", ".tif", ".tiff", ".ttf", ".otf"}
FONT_SUFFIXES = {".ttf", ".otf"}
EXTRAS = {"README.txt", "transcript.srt", "transcript.vtt", "broll_manifest.csv", "approved_preview.mp4", "hyperframes_editable.zip"}
KINDS = {"video", "broll", "audio", "music", "sfx", "image", "font"}


def _error(message, status=400):
    return core.StudioError(message, status)


def _member_name(value):
    if (not isinstance(value, str) or not value or len(value) > 1024 or
            "\\" in value or "\x00" in value or any(ord(c) < 32 for c in value)):
        raise _error("Nombre de miembro ZIP inválido.")
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or
            any(part in {".", "..", ".estado"} or ":" in part for part in path.parts)):
        raise _error("El ZIP contiene una ruta privada, absoluta o no canónica.", 403)
    return value


def _asset_path(value):
    value = _member_name(value)
    path = PurePosixPath(value)
    if (len(path.parts) < 3 or path.parts[0] != "assets" or
            path.parts[1] not in {"video", "broll", "audio", "images", "fonts"} or
            path.suffix.lower() not in MEDIA_SUFFIXES):
        raise _error("Un recurso del editable tiene una ruta o formato no admitidos.")
    return value


def _inspect(archive):
    entries = archive.infolist()
    if not entries or len(entries) > MAX_MEMBERS:
        raise _error("El ZIP está vacío o excede el límite de miembros.", 413)
    index, compressed, expanded = {}, 0, 0
    for info in entries:
        name = _member_name(info.filename)
        mode = info.external_attr >> 16
        if info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG}):
            raise _error("El ZIP solo admite archivos regulares; no enlaces ni carpetas.", 403)
        if name in index:
            raise _error("El ZIP contiene miembros repetidos.")
        if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
            raise _error("El ZIP cifrado o con compresión no admitida no puede reabrirse.")
        compressed += info.compress_size
        expanded += info.file_size
        if info.file_size < 0 or info.compress_size < 0 or compressed + expanded > MAX_BYTES:
            raise _error("El contenido comprimido y expandido excede 4 GiB.", 413)
        if info.file_size > 1024 ** 2 and info.file_size / max(1, info.compress_size) > MAX_COMPRESSION_RATIO:
            raise _error("El ZIP excede la relación de compresión permitida.", 413)
        index[name] = info
    if "project.json" not in index or index["project.json"].file_size > MAX_PROJECT_BYTES:
        raise _error("Falta project.json o excede el tamaño permitido.")
    return index


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Claves JSON repetidas")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("Número JSON no finito")


def _read_project(archive):
    try:
        project = json.loads(archive.read("project.json"), object_pairs_hook=_object_pairs,
                             parse_constant=_invalid_number)
    except (ValueError, UnicodeDecodeError) as error:
        raise _error("project.json no contiene un JSON válido y acotado.") from error
    if not isinstance(project, dict):
        raise _error("project.json debe contener un objeto de proyecto.")
    for field, expected in (("assets", list), ("settings", dict), ("timeline", list),
                            ("audio", list), ("transcript", dict), ("fonts", dict)):
        if not isinstance(project.get(field), expected):
            raise _error(f"El editable requiere {field} con el formato correcto.")
    if len(project["assets"]) > MAX_MEMBERS - 1:
        raise _error("Demasiados recursos en el editable.", 413)
    return project


def _references(project, index, brand_plan=None):
    specs, ids, paths = {}, set(), set()
    for item in project["assets"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
            raise _error("Los recursos exportados requieren IDs únicos.")
        if item["id"] in ids:
            raise _error("Un ID de recurso se repite en project.json.")
        path = _asset_path(item.get("path"))
        if path in paths:
            raise _error("Un recurso exportado se repite por ruta.")
        digest = item.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise _error("Cada recurso requiere su SHA256 original verificable.")
        if item.get("kind") not in KINDS:
            raise _error("Tipo de recurso exportado no admitido.")
        if path not in index:
            raise _error("Falta un recurso referenciado por project.json.")
        if item.get("size") is not None and item["size"] != index[path].file_size:
            raise _error("El tamaño exportado no coincide con el miembro ZIP.")
        specs[path] = {"asset": item, "sha256": digest.lower()}
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            raise _error("La metadata del recurso requiere un objeto.")
        notice = metadata.get("font_notice")
        if notice is not None:
            if item.get("kind") != "font" or not isinstance(notice, dict):
                raise _error("Los avisos tipográficos pertenecen únicamente a fuentes.")
            notice_sha = notice.get("sha256")
            if not isinstance(notice_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", notice_sha):
                raise _error("El aviso de fuente requiere SHA-256 completo.")
            notice_path = "assets/fonts/licenses/" + notice_sha[:24] + ".txt"
            if notice.get("path") != notice_path or notice_path not in index:
                raise _error("Falta el aviso tipográfico canónico por contenido.")
            if not 1 <= index[notice_path].file_size <= 65536:
                raise _error("El aviso tipográfico supera su límite.", 413)
            specs.setdefault(notice_path, {"asset": None, "sha256": notice_sha, "special": "font_notice"})
        ids.add(item["id"])
        paths.add(path)
    source = project.get("source")
    if source is not None and (not isinstance(source, str) or source not in ids):
        raise _error("El original del editable no está incluido entre sus recursos.")
    if core.WORKSPACE_MODE and brand_plan is None:
        from .brand_bundles import prepare
        brand_plan = prepare(project)
    for key, expected in (("primary", "sequel"), ("accent", "scholar")):
        if brand_plan is not None:
            expected = brand_plan["roles"][key]
        path = _asset_path(project["fonts"].get(key))
        if PurePosixPath(path).suffix.lower() not in FONT_SUFFIXES or path not in index:
            raise _error("Falta una fuente real referenciada por el editable.")
        specs.setdefault(path, {"asset": None, "sha256": None})
        specs[path].setdefault("font_roles", []).append((key, expected))
    allowed = set(specs) | EXTRAS | {"project.json"}
    if set(index) - allowed:
        raise _error("El ZIP contiene archivos ajenos al proyecto editable.", 403)
    for scene in project["timeline"]:
        if not isinstance(scene, dict):
            raise _error("Cada escena del editable requiere un objeto.")
        for key in ("asset_id", "transition_asset_id"):
            if scene.get(key) is not None and (not isinstance(scene[key], str) or scene[key] not in ids):
                raise _error("Una escena referencia un recurso no incluido.")
        for layer in scene.get("overlays", []):
            if not isinstance(layer, dict) or layer.get("asset_id") not in ids:
                raise _error("Una capa referencia un recurso no incluido.")
        design = scene.get("motion_design")
        if design is not None:
            if not isinstance(design, dict) or not isinstance(design.get("elements"), list):
                raise _error("La composición libre requiere elementos válidos.")
            for element in design["elements"]:
                if not isinstance(element, dict) or (element.get("type") == "media" and element.get("asset_id") not in ids):
                    raise _error("Un elemento de motion referencia un recurso no incluido.")
                if 'brand_entity' in element:
                    from .scene_ir import _closed_element
                    _closed_element(element)
                    member = next(a['path'] for a in project['assets'] if a['id'] == element['asset_id'])
                    specs[member]['brand_reference'] = True
                if element.get("font_asset_id") is not None:
                    reference = element["font_asset_id"]
                    registered = next((a for a in project["assets"] if a["id"] == reference), None)
                    if element.get("type") != "text" or not registered or registered.get("kind") != "font":
                        raise _error("Un elemento de texto referencia una fuente no incluida.")
    for track in project["audio"]:
        if not isinstance(track, dict) or not isinstance(track.get("asset_id"), str) or track["asset_id"] not in ids:
            raise _error("Una pista sonora referencia un recurso no incluido.")
    return specs


def _materialize(archive, specs, temporary):
    from .analysis import probe
    for number, (name, spec) in enumerate(specs.items()):
        target = temporary / f"resource_{number:05d}{PurePosixPath(name).suffix.lower()}"
        digest = hashlib.sha256()
        actual_size = 0
        with archive.open(name) as source, target.open("wb") as output:
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                actual_size += len(block)
                if actual_size > MAX_BYTES:
                    raise _error("Un miembro excedió el límite al expandirse.", 413)
                digest.update(block)
                output.write(block)
        actual_hash = digest.hexdigest()
        if spec["sha256"] and actual_hash != spec["sha256"]:
            raise _error("El contenido de un recurso no coincide con su SHA256 exportado.")
        spec.update(local=target, actual_hash=actual_hash)
        if spec.get("special") == "font_notice":
            try:
                target.read_text(encoding="utf-8")
            except UnicodeDecodeError as error:
                raise _error("El aviso de licencia debe ser texto UTF-8.") from error
            continue
        if target.suffix.lower() in FONT_SUFFIXES:
            from .fonts import inspect_font
            spec["font_info"] = inspect_font(target)
            try:
                names = ImageFont.truetype(str(target), 24).getname()
            except OSError as error:
                raise _error("Una fuente del editable no es un archivo tipográfico válido.") from error
            for _, expected in spec.get("font_roles", []):
                if isinstance(expected, dict):
                    if any(spec["font_info"].get(k) != expected[k] for k in ("sha256", "family", "style")):
                        raise _error("La identidad SFNT real no coincide con la fuente declarada por la marca.")
                    continue
                valid = names[0].lower() == "sequel sans" and names[1].lower() == "bold disp" if expected == "sequel" else names[0].lower() == "scholar" and names[1].lower() == "italic"
                if not valid:
                    raise _error("La fuente importada no corresponde a Sequel/Scholar obligatorias.")
        elif spec.get("font_roles"):
            raise _error("Una fuente declarada no tiene un formato tipográfico válido.")
        else:
            if target.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
                from PIL import Image
                try:
                    with Image.open(target) as picture:
                        picture.verify()
                except (OSError, ValueError) as error:
                    raise _error("Una imagen importada no es válida para su extensión.") from error
            if (spec.get("asset") or {}).get("kind") == "font":
                raise _error("Un recurso declarado como fuente no tiene formato tipográfico.")
            spec["probe"] = probe(target)
            streams = spec["probe"].get("streams", [])
            video = any(s.get("codec_type") == "video" for s in streams)
            audio = any(s.get("codec_type") == "audio" for s in streams)
            kind = (spec.get("asset") or {}).get("kind")
            if not video and not audio:
                raise _error("Un recurso importado no contiene medios decodificables.")
            if kind in {"audio", "music", "sfx"} and not audio:
                raise _error("Un recurso sonoro importado no contiene una pista real de audio.")
            if kind in {"video", "broll"} and not video:
                raise _error("Un clip importado no contiene una pista real de video.")


def _draft(imported):
    timeline = copy.deepcopy(imported["timeline"])
    for scene in timeline:
        scene.update(status="draft", chin_reviewed=False)
        decision = scene.get("decision") if isinstance(scene.get("decision"), dict) else {}
        decision.update(evidence=[], verification="pending_reinspection",
                        import_note="Las observaciones se conservan; revisa recursos y registra nueva evidencia local.")
        scene["decision"] = decision
        for layer in scene.get("overlays", []):
            decision = layer.get("decision") if isinstance(layer.get("decision"), dict) else {}
            decision.update(evidence=[], verification="pending_reinspection")
            layer["decision"] = decision
    transcript = copy.deepcopy(imported["transcript"])
    transcript.update(reviewed=False, status="imported_pending_review")
    reference = imported.get("reference_review", {})
    observations = reference.get("identity_observations", "") if isinstance(reference, dict) else ""
    style = copy.deepcopy(core.POLICY)
    if core.WORKSPACE_MODE:
        style.update(current_production_phase="ivan_multiservice", parent_creative_scope="independent_read_only_source",
                     parent_integration="YO_plus_CLONE_own_branding")
    if isinstance(imported.get("style"), dict) and "hook_seconds" in imported["style"]:
        style["hook_seconds"] = imported["style"]["hook_seconds"]
    draft = {"style": style, "settings": copy.deepcopy(imported["settings"]), "timeline": timeline,
            "transcript": transcript, "audio": copy.deepcopy(imported["audio"]),
            "review": {}, "renders": [], "approved_export": None, "library_searches": [],
            "reference_review": {"identity_observations": observations, "evidence": [], "status": "pending_reinspection"},
            "stage": "imported_review_pending"}
    if imported.get("mode") == "scene_ir_component":
        if not isinstance(imported.get("scene_ir"), dict):
            raise _error("El componente no contiene su registro SceneIR.")
        draft.update(mode="scene_ir_component", scene_ir=copy.deepcopy(imported["scene_ir"]))
    elif imported.get("mode", "reel") != "reel":
        raise _error("Modo de editable no admitido.")
    return draft


def _metadata(spec, source_hashes=None):
    supplied = (spec.get("asset") or {}).get("metadata", {})
    values = {}
    if isinstance(supplied, dict):
        notice = supplied.get("font_notice")
        if isinstance(notice, dict):
            values["font_notice"] = {"path": notice["path"], "sha256": notice["sha256"],
                                     "license": str(notice.get("license", "supplied_notice"))[:100],
                                     "source_status": "bundled_notice_unverified"}
        declaration = supplied.get("declaration_original")
        if not spec.get('brand_reference') and isinstance(declaration, dict) and declaration.get("kind") == "original_graphic" and isinstance(declaration.get("author"), str) and declaration["author"].strip():
            values["declaration_original"] = {"kind": "original_graphic", "author": declaration["author"][:500]}
        for key in ("source", "content", "rights", "license", "url", "observations"):
            if isinstance(supplied.get(key), str):
                values[key] = supplied[key][:20000]
        provenance = supplied.get("provenance", {})
        provenance = provenance if isinstance(provenance, dict) else {}
        parent_id = provenance.get("source_asset_id") or supplied.get("source")
        parent_hash = (source_hashes or {}).get(parent_id) if isinstance(parent_id, str) else None
        parent_hash = parent_hash or provenance.get("source_sha256")
        if isinstance(parent_hash, str) and re.fullmatch(r"[a-fA-F0-9]{64}", parent_hash):
            values["provenance"] = {"source_sha256": parent_hash.lower(), "imported_source_asset_id": parent_id,
                                    "operation": str(provenance.get("operation", "imported_derivative"))[:200]}
    values.update(imported_from="editable_bundle", review_status="pending_reinspection")
    return values


def _display_name(member, spec):
    supplied = (spec.get("asset") or {}).get("name")
    if (isinstance(supplied, str) and 0 < len(supplied) <= 240 and
            not any(ord(c) < 32 for c in supplied) and
            PurePosixPath(supplied).suffix.lower() == spec["local"].suffix.lower()):
        return PurePosixPath(supplied).name
    return PurePosixPath(member).name


def _existing_project(imported, specs):
    source_id = imported.get("source")
    source_spec = next((s for s in specs.values() if (s.get("asset") or {}).get("id") == source_id), None) if source_id is not None else None
    source_hash = source_spec["actual_hash"] if source_spec else None
    catalog = {a["id"]: a for a in core.assets()}
    drive_id = imported.get("drive_id")
    if drive_id is not None and (not isinstance(drive_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,200}", drive_id)):
        raise _error("El ID de Drive importado no es válido.")
    for summary in core.project_list():
        candidate = core.get_project(summary["id"])
        original = catalog.get(candidate.get("source"))
        same_hash = original and source_hash and original.get("sha256") == source_hash
        same_drive = drive_id and candidate.get("drive_id") == drive_id
        if same_hash:
            if core.content_hash(original["path"]) != source_hash:
                raise _error("El original canónico cambió en disco; revisa su integridad antes de reabrir.", 409)
            return candidate
        if same_drive:
            if source_hash or original:
                raise _error("El ID de Drive ya tiene otro original canónico; no se sobrescribe.", 409)
            return candidate
    return None


def import_bundle(path: Path) -> dict:
    from .jobs import cpu_slot
    with cpu_slot():
        return _import_and_preview(path)


def _import_and_preview(path: Path) -> dict:
    result = _import_bundle(path)
    # Batch staging never waits for the CPU slot while holding the store lock.
    # Prepare browser derivatives afterward from canonical originals.
    warnings = []
    for item in result["project"].get("assets", []):
        if item.get("kind") not in {"video", "broll"}:
            continue
        if core.content_hash(item["path"]) != item["sha256"]:
            warnings.append("Un original cambió después de reabrir; no se genera su vista previa.")
            continue
        current = core.register_asset(core.confined(item["path"], must_exist=True))
        if current.get("preview_error"):
            warnings.append(current["preview_error"])
    result["project"] = core.get_project(result["project"]["id"])
    if warnings:
        result["preview_warnings"] = warnings
    return result


def _import_bundle(path: Path) -> dict:
    """Return {project, reused, asset_count}; never approve imported evidence."""
    path = core.confined(path, must_exist=True)
    if path.suffix.lower() != ".zip" or path.stat().st_size > MAX_BYTES:
        raise _error("Selecciona un editable ZIP local de hasta 4 GiB.", 413)
    base = core.confined(".estado/tmp")
    base.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="bundle_", dir=base) as temporary:
            temporary = Path(temporary)
            with zipfile.ZipFile(path) as archive:
                index = _inspect(archive)
                if archive.testzip() is not None:
                    raise _error("El editable no superó la verificación CRC.")
                imported = _read_project(archive)
                from .brand_bundles import prepare, verify_materialized, seal_and_save
                brand_plan = prepare(imported)
                specs = _references(imported, index, brand_plan)
                _materialize(archive, specs, temporary)
                verify_materialized(brand_plan, specs)
                if imported.get("source"):
                    source_spec = next(spec for spec in specs.values() if (spec.get("asset") or {}).get("id") == imported["source"])
                    if not any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in source_spec.get("probe", {}).get("streams", [])):
                        raise _error("El original importado no contiene una pista real de video.")
            draft = _draft(imported)
            # Validate schema before catalog writes. Asset identity is checked
            # after registration; the preflight deliberately has no asset rows.
            # Actual bundled fonts have already been verified by _materialize.
            # Temporary staging paths must never become exportable font paths.
            shape = {**draft, "assets": [], "fonts": core.fonts()}
            shape = copy.deepcopy(shape)
            for scene in shape.get("timeline", []):
                for number,element in enumerate((scene.get("motion_design") or {}).get("elements", [])):
                    # IDs/kind/bytes are independently checked in references/materialize.
                    element.pop("font_asset_id", None)
                    element.pop("brand_entity", None)
                    if element.get('type') == 'media':
                        element['asset_id'] = 'staged_graphic_' + str(number)
            core.validate_shape(shape)
            has_brands = any('brand_entity' in element for scene in draft['timeline']
                             for element in (scene.get('motion_design') or {}).get('elements', []))
            if draft.get("mode") == "scene_ir_component" or has_brands:
                from .scene_ir import validate_import_project, validate_import_brand_media
                source_hashes = {(spec.get("asset") or {}).get("id"): spec["actual_hash"] for spec in specs.values() if spec.get("asset")}
                staging = []
                for spec in specs.values():
                    item = spec.get("asset")
                    if not item:
                        continue
                    actual_probe = spec.get("probe", {})
                    row = copy.deepcopy(item)
                    row.update(path=core.relative(spec["local"]), sha256=spec["actual_hash"],
                               size=spec["local"].stat().st_size, probe=actual_probe,
                               duration=float(actual_probe.get("format", {}).get("duration", 0)),
                               metadata=_metadata(spec, source_hashes))
                    staging.append(row)
                shadow = {**draft, "source": imported.get("source"), "assets": staging}
                if draft.get('mode') == 'scene_ir_component':
                    validate_import_project(shadow, staging)
                else:
                    validate_import_brand_media(shadow, staging)
            with core.LOCK:
                existing = _existing_project(imported, specs)
                if existing:
                    return {"project": existing, "reused": True, "asset_count": len(existing.get("assets", []))}
                catalog_by_hash = {a["sha256"]: a for a in core.assets()}
                # A dedup hit must also match the real local bytes.
                for spec in specs.values():
                    old = catalog_by_hash.get(spec["actual_hash"])
                    if old and core.content_hash(old["path"]) != spec["actual_hash"]:
                        raise _error("Un recurso canónico cambió en disco; no se reemplaza automáticamente.", 409)
                registered, mapped = {}, {}
                source_hashes = {(spec.get("asset") or {}).get("id"): spec["actual_hash"] for spec in specs.values() if spec.get("asset")}
                for name, spec in specs.items():
                    if spec.get("special") == "font_notice":
                        destination = core.confined(name)
                        if not destination.is_relative_to(core.ROOT / "assets/fonts/licenses"):
                            raise _error("El aviso tipográfico no puede escribir fuera de su biblioteca.", 403)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        if destination.exists():
                            if core.digest(destination) != spec["actual_hash"]:
                                raise _error("El aviso canónico contiene otros bytes; se conserva.", 409)
                        else:
                            shutil.copyfile(spec["local"], destination)
                        continue
                    item = spec.get("asset") or {}
                    asset = core.register_asset(spec["local"], name=_display_name(name, spec),
                                                kind="font" if spec["local"].suffix in FONT_SUFFIXES else item.get("kind"),
                                                metadata=_metadata(spec, source_hashes))
                    if asset["sha256"] != spec["actual_hash"]:
                        raise _error("El recurso cambió durante su registro.", 409)
                    registered[name] = asset
                    if spec.get("asset"):
                        mapped[item["id"]] = asset["id"]
                unique = {asset["id"]: asset for asset in registered.values()}
                source = mapped.get(imported.get("source"))
                if source and not any(s.get("codec_type") == "video" for s in unique[source].get("probe", {}).get("streams", [])):
                    raise _error("El original importado no contiene una pista real de video.")
                p = core.create_project(str(imported.get("name", "Editable importado"))[:200], source,
                                        imported.get("drive_id"))
                p.update(draft, assets=list(unique.values()),
                         fonts={key: registered[imported["fonts"][key]]["path"] for key in ("primary", "accent")},
                         manual=core.manual_fingerprints(),
                         import_info={"at": core.now(), "format": "ascendia_editable_zip", "original_project_id": str(imported.get("id", ""))[:100],
                                      "sha256": core.digest(path), "review_status": "pending_reinspection"})
                p.pop("full_authorization", None)
                for scene in p["timeline"]:
                    for key in ("asset_id", "transition_asset_id"):
                        if scene.get(key):
                            scene[key] = mapped[scene[key]]
                    for layer in scene.get("overlays", []):
                        layer["asset_id"] = mapped[layer["asset_id"]]
                    for element in (scene.get("motion_design") or {}).get("elements", []):
                        if element.get("type") == "media":
                            element["asset_id"] = mapped[element["asset_id"]]
                        if element.get("font_asset_id"):
                            element["font_asset_id"] = mapped[element["font_asset_id"]]
                    origin = scene.get('scene_ir_origin')
                    if isinstance(origin, dict) and isinstance(origin.get('document'), dict):
                        from .scene_ir import document_digest
                        for element in origin['document'].get('components', []):
                            for key in ('asset_id', 'font_asset_id'):
                                if element.get(key):
                                    if element[key] not in mapped:
                                        raise _error('El origen SceneIR referencia un recurso no incluido.')
                                    element[key] = mapped[element[key]]
                        origin.update(document_sha256=document_digest(origin['document']), status='pending_qc', clone_fidelity='not_reviewed')
                for track in p["audio"]:
                    track["asset_id"] = mapped[track["asset_id"]]
                if p.get("mode") == "scene_ir_component":
                    from .scene_ir import document_digest
                    for element in p["scene_ir"]["document"]["components"]:
                        if element.get("type") == "media":
                            element["asset_id"] = mapped[element["asset_id"]]
                        if element.get("font_asset_id"):
                            element["font_asset_id"] = mapped[element["font_asset_id"]]
                    p["scene_ir"]["document_sha256"] = document_digest(p["scene_ir"]["document"])
                    p["scene_ir"].update(status="pending_qc", clone_fidelity="not_reviewed", rights_verified=False)
                from .scene_ir import seal_imported_brands
                pending_proof = seal_imported_brands(p)
                try:
                    result = (seal_and_save(p, brand_plan, registered, imported["fonts"], mapped)
                              if brand_plan is not None else core.save_project(p["id"], p, action="bundle_imported"))
                except Exception:
                    if pending_proof:
                        pending_proof.unlink(missing_ok=True)
                    raise
                return {"project": result, "reused": False, "asset_count": len(unique)}
    except core.StudioError:
        raise
    except (zipfile.BadZipFile, RuntimeError, OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise _error("No se pudo reabrir el editable: " + str(error)[:300]) from error
