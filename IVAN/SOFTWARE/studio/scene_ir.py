"""Explicit SceneIR data to an editable scene; no generator, execution or store.

The caller authors the semantics and geometry. Family names are annotations,
not an assertion that a CLONE component was reconstructed or reviewed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re

from . import core, design
from .core import StudioError, finite_number

SCHEMA = "ascendia.sceneir/1"
MAX_ACTIONS = 8192
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
IDENTIFIER = r"[a-zA-Z0-9_-]{1,100}"
PARAMETER = r"[a-zA-Z][a-zA-Z0-9_]{0,63}"
PICTURES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ROOT_FIELDS = {"schema", "scene_id", "content", "narrative_goal", "family", "representation",
               "duration", "composition", "parameters", "components", "actions"}
COMMON_ELEMENT = {"id", "type", "x", "y", "width", "height", "start", "end", "opacity", "rotation",
                  "z", "color", "color_reason", "radius", "mask", "keyframes", "path"}
TYPE_FIELDS = {"text": {"text", "font", "font_size", "font_asset_id", "text_style", "text_animation"}, "shape": {"shape"}, "media": {"asset_id", "source_in", "brand_entity"}}
KEY_FIELDS = {"time", "ease", "ease_window", *design.CHANNELS}
ACTION_FIELDS = {"target_id", "time", "properties", "ease", "ease_window"}


def _object(value, fields, label, required=()):
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise StudioError(f"{label} requiere un objeto de datos.")
    unknown = set(value) - set(fields)
    missing = set(required) - set(value)
    if unknown or missing:
        raise StudioError(f"Campos inválidos en {label}: " + ", ".join(sorted(unknown | missing)) + ".")
    return value


def _text(value, label, limit, empty=False):
    if not isinstance(value, str) or len(value) > limit or (not empty and not value.strip()):
        raise StudioError(f"{label} requiere texto de hasta {limit} caracteres.")
    if any((ord(c) < 32 and c not in "\n\t") or 0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise StudioError(f"{label} contiene caracteres de control no admitidos.")
    return value


def _identifier(value, label, pattern=IDENTIFIER):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise StudioError(f"{label} requiere un identificador literal.")
    return value


def _data_document(document):
    # Bound recursion and work before serializing/deepcopying adversarial input.
    count = 0

    def visit(value, depth):
        nonlocal count
        count += 1
        if count > 100000 or depth > 16:
            raise StudioError("SceneIR supera el límite de estructura local.")
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            finite_number(value, "número SceneIR", -1e15, 1e15)
        elif isinstance(value, str):
            _text(value, "cadena SceneIR", 20000, empty=True)
        elif isinstance(value, list):
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, dict) and all(isinstance(key, str) for key in value):
            for key, item in value.items():
                visit(key, depth + 1)
                visit(item, depth + 1)
        else:
            raise StudioError("SceneIR solo admite datos JSON, nunca objetos ejecutables.")

    visit(document, 0)
    encoded = json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_DOCUMENT_BYTES:
        raise StudioError("SceneIR supera el límite local de 2 MiB.")
    return encoded


def document_digest(document):
    """Hash bounded literal JSON consistently after portable asset-ID remaps."""
    return hashlib.sha256(_data_document(document)).hexdigest()


def _parameters(value):
    _object(value, value.keys() if isinstance(value, dict) else (), "parámetros")
    if len(value) > 64:
        raise StudioError("SceneIR admite hasta 64 parámetros literales.")
    result = {}
    for name, item in value.items():
        _identifier(name, "nombre del parámetro", PARAMETER)
        if isinstance(item, str):
            result[name] = _text(item, "valor del parámetro", 2000, empty=True)
        else:
            finite_number(item, "valor del parámetro", -1e12, 1e12)
            result[name] = str(item)
    return result


def _substitute(text, parameters, label, limit):
    _text(text, label, limit, empty=True)
    pattern = re.compile(r"\{\{(" + PARAMETER + r")\}\}")
    # Validate the input tokens, then replace once. Inserted values stay literal.
    remaining = pattern.sub("", text)
    if "{{" in remaining or "}}" in remaining:
        raise StudioError(f"Marcador de parámetro inválido en {label}.")

    def literal(match):
        name = match[1]
        if name not in parameters:
            raise StudioError(f"Parámetro no declarado: {name}.")
        return parameters[name]

    return _text(pattern.sub(literal, text), label, limit, empty=True)


def _closed_element(element):
    _object(element, COMMON_ELEMENT | set().union(*TYPE_FIELDS.values()), "componente", ("id", "type"))
    kind = element["type"]
    if not isinstance(kind, str) or kind not in TYPE_FIELDS:
        raise StudioError("El componente requiere text, shape o media.")
    _object(element, COMMON_ELEMENT | TYPE_FIELDS[kind], "componente " + kind)
    _identifier(element["id"], "ID componente")
    if "color_reason" in element:
        _text(element["color_reason"], "razón editorial del color", 2000, empty=True)
    if kind == "media":
        _identifier(element.get("asset_id"), "ID recurso gráfico")
        finite_number(element.get("source_in", 0), "entrada gráfico estático", 0, 0)
        if "brand_entity" in element:
            _brand_entity(element["brand_entity"])
    keys = element.get("keyframes", [])
    if not isinstance(keys, list) or len(keys) > 128:
        raise StudioError("Cada componente admite hasta 128 keyframes.")
    for key in keys:
        _object(key, KEY_FIELDS, "keyframe", ("time",))
        if not set(key).intersection(design.CHANNELS):
            raise StudioError("Un keyframe debe declarar una propiedad animada.")
    mask = element.get("mask", {"type": "none"})
    _object(mask, {"type", "inset"}, "máscara")
    if "inset" in mask:
        if mask.get("type") != "inset":
            raise StudioError("Las coordenadas inset requieren máscara inset.")
        _object(mask["inset"], {"top", "right", "bottom", "left"}, "coordenadas inset")
    if "path" in element:
        _object(element["path"], {"points", "orient"}, "trayectoria", ("points",))
        points = element["path"]["points"]
        if not isinstance(points, list):
            raise StudioError("La trayectoria requiere una lista de puntos.")
        for point in points:
            _object(point, {"x", "y"}, "punto trayectoria", ("x", "y"))


def _merge_key(existing, incoming):
    for key, value in incoming.items():
        if key in existing and existing[key] != value:
            raise StudioError("Dos acciones/keyframes contradicen una propiedad o curva en el mismo instante.")
        existing[key] = value


def _validate_key(frame, duration, element):
    t = finite_number(frame.get("time"), "tiempo keyframe SceneIR", 0, duration)
    if frame.get("ease", "linear") not in design.EASES:
        raise StudioError("Curva de animación SceneIR no admitida.")
    window = frame.get("ease_window", [0, 1])
    if not isinstance(window, list) or len(window) != 2:
        raise StudioError("La ventana de easing requiere dos números.")
    lo = finite_number(window[0], "inicio ventana easing", 0, 1)
    hi = finite_number(window[1], "fin ventana easing", 0, 1)
    if hi - lo < 1e-6:
        raise StudioError("La ventana de easing debe tener extensión positiva.")
    for key, lo, hi in (("x", -2, 2), ("y", -2, 2), ("scale", .01, 8), ("opacity", 0, 1),
                        ("rotation", -3600, 3600), ("mask_progress", 0, 1)):
        if key in frame:
            finite_number(frame[key], "keyframe " + key, lo, hi)
            if key == "mask_progress" and element.get("mask", {}).get("type", "none") == "none":
                raise StudioError("La revelación requiere una máscara circle o inset.")
    return t


def _merge_actions(elements, actions, duration):
    if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
        raise StudioError("SceneIR admite hasta 8192 acciones explícitas.")
    by_id = {el["id"]: el for el in elements}
    poses = {}
    for el in elements:
        poses[el["id"]] = {}
        for frame in el.get("keyframes", []):
            t = _validate_key(frame, duration, el)
            if t in poses[el["id"]]:
                raise StudioError("Los keyframes del componente requieren tiempos únicos.")
            poses[el["id"]][t] = copy.deepcopy(frame)
    for action in actions:
        _object(action, ACTION_FIELDS, "acción", ("target_id", "time", "properties"))
        target = _identifier(action["target_id"], "destino acción")
        if target not in by_id:
            raise StudioError("La acción apunta a un componente inexistente.")
        t = finite_number(action["time"], "tiempo acción", 0, duration)
        props = _object(action["properties"], set(design.CHANNELS), "propiedades acción")
        if not props:
            raise StudioError("Una acción debe declarar una propiedad animada.")
        incoming = {"time": t, **copy.deepcopy(props)}
        for key in ("ease", "ease_window"):
            if key in action:
                incoming[key] = copy.deepcopy(action[key])
        _validate_key(incoming, duration, by_id[target])
        _merge_key(poses[target].setdefault(t, {"time": t}), incoming)
    for el in elements:
        el["keyframes"] = [poses[el["id"]][t] for t in sorted(poses[el["id"]])]


def _brand_entity(value):
    from .brand_assets import ORIGINS
    if not isinstance(value, str) or value not in ORIGINS:
        raise StudioError("brand_entity requiere una entidad literal del registro de marcas.")
    return value


def _graphic_brand(registered, source, catalog):
    """Pure lineage/raster checks shared by staging and runtime; no approval."""
    if core.source_related(registered, source, catalog):
        raise StudioError("El crudo o sus derivados no pueden ocultarse como una marca.", 403)
    if (registered.get("kind") != "image" or
            Path(registered.get("path", "")).suffix.lower() not in PICTURES):
        raise StudioError("La marca requiere un raster canónico decodificable; no SVG ni video.")
    from PIL import Image
    raw = Path(core.ROOT) / registered['path']
    path = core.confined(raw, must_exist=True)
    from .brand_assets import MAX_FILE
    if path.stat().st_size > MAX_FILE:
        raise StudioError("El raster de marca supera el límite de4MiB.", 413)
    if path != raw.absolute() or raw.is_symlink() or core.digest(path) != registered['sha256']:
        raise StudioError("La marca requiere bytes canónicos íntegros y sin alias.", 409)
    try:
        with Image.open(path) as image:
            if image.width * image.height > 16_000_000 or getattr(image, 'n_frames', 1) != 1:
                raise StudioError("La marca requiere una imagen estática de hasta16 millones de píxeles.")
            image.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as error:
        raise StudioError("El raster de marca no es decodificable.") from error
    by_sha = {a.get("sha256"): a for a in catalog.values()}
    cursor, seen = registered, set()
    for _ in range(64):
        if cursor.get("id") in seen or cursor.get("kind") != "image":
            raise StudioError("La marca no permite procedencia circular ni derivados de video/audio.", 403)
        seen.add(cursor.get("id"))
        metadata = cursor.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        provenance = metadata.get("provenance", {})
        if not isinstance(provenance, dict):
            raise StudioError("La procedencia gráfica debe ser un objeto.")
        parent_id, parent_sha = provenance.get("source_asset_id"), provenance.get("source_sha256")
        if parent_id is None and isinstance(metadata.get("source"), str) and metadata["source"] in catalog:
            parent_id = metadata["source"]
        if parent_id is None and parent_sha is None:
            break
        if parent_id is not None:
            _identifier(parent_id, "ID origen gráfico")
        if parent_sha is not None and (not isinstance(parent_sha, str) or not re.fullmatch(r"[a-f0-9]{64}", parent_sha)):
            raise StudioError("La marca requiere un SHA de procedencia válido.", 403)
        parent = catalog.get(parent_id) or by_sha.get(parent_sha)
        if not parent or (parent_id is not None and parent.get("id") != parent_id) or (parent_sha is not None and parent.get("sha256") != parent_sha):
            raise StudioError("La procedencia de la marca no puede verificarse.", 403)
        cursor = parent
    else:
        raise StudioError("La procedencia gráfica excede 64 recursos.", 403)


def _pending_path(project_id):
    _identifier(project_id, "ID proyecto de marca pendiente")
    raw = Path(core.ROOT) / '.estado/brand_assets/imports' / (project_id + '.json')
    resolved = core.confined(raw)
    if resolved != raw.absolute() or raw.is_symlink():
        raise StudioError("El comprobante de marca pendiente no admite alias.", 403)
    return resolved


def _pending_references(project):
    """Authenticate editable-only import state; JSON alone never grants it."""
    field = project.get('pending_brand_references')
    if field is None:
        return {}
    _object(field, {'schema','record_sha256','status','editorial_approved','publication_approved'}, 'marcas pendientes',
            ('schema','record_sha256','status','editorial_approved','publication_approved'))
    if (field['schema'] != 'ascendia.pending-brand-import/1' or field['status'] != 'pending_local_observation' or
            field['editorial_approved'] is not False or field['publication_approved'] is not False or
            not isinstance(field['record_sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', field['record_sha256'])):
        raise StudioError("Las marcas pendientes no confieren autorización ni aprobación.", 403)
    path = _pending_path(project.get('id'))
    if not path.is_file() or path.stat().st_size > MAX_DOCUMENT_BYTES or core.digest(path) != field['record_sha256']:
        raise StudioError("Falta el comprobante privado de importación de marcas.", 409)
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, RecursionError) as error:
        raise StudioError("Comprobante de marcas pendientes mal formado.", 409) from error
    _object(record, {'schema','project_id','source_sha256','references','editable_only','editorial_approved','publication_approved'},
            'comprobante de marcas', ('schema','project_id','source_sha256','references','editable_only','editorial_approved','publication_approved'))
    if (record['schema'] != field['schema'] or record['project_id'] != project.get('id') or
            record['editable_only'] is not True or record['editorial_approved'] is not False or record['publication_approved'] is not False):
        raise StudioError("El comprobante pertenece a otra autorización de datos.", 403)
    source = core.asset(project.get('source'))
    if source['sha256'] != record['source_sha256'] or core.content_hash(source['path']) != source['sha256']:
        raise StudioError("El crudo no coincide con el borrador importado.", 409)
    refs = record['references']
    if not isinstance(refs, list) or not 1 <= len(refs) <= 5000:
        raise StudioError("La importación requiere referencias de marca acotadas.")
    result = {}
    for ref in refs:
        _object(ref, {'asset_id','sha256','entity'}, 'referencia de marca pendiente', ('asset_id','sha256','entity'))
        _identifier(ref['asset_id'], 'ID marca pendiente');_brand_entity(ref['entity'])
        canonical = core.asset(ref['asset_id'])
        if canonical['sha256'] != ref['sha256']:
            raise StudioError("La marca pendiente cambió de contenido canónico.", 409)
        key = (ref['asset_id'], ref['entity'])
        if key in result:
            raise StudioError("Referencia de marca pendiente repetida.")
        result[key] = ref['sha256']
    return result


def seal_imported_brands(project):
    """Importer-only: seal raster references for editing, never for execution."""
    project.pop('pending_brand_references', None)
    references = {}
    catalog = {a['id']: a for a in core.assets()}
    source = catalog.get(project.get('source'))
    for scene in project.get('timeline', []):
        for element in (scene.get('motion_design') or {}).get('elements', []):
            if 'brand_entity' not in element:
                continue
            _closed_element(element)
            _graphic_brand(catalog[element['asset_id']], source, catalog)
            entity = _brand_entity(element['brand_entity'])
            references[(element['asset_id'],entity)] = catalog[element['asset_id']]['sha256']
    if not references:
        return None
    if not source or source.get('kind') != 'video':
        raise StudioError("El borrador de marca conserva un crudo de video canónico.")
    if not core.WORKSPACE_MODE:
        raise StudioError("Las marcas importadas pertenecen a un workspace privado.", 403)
    old = core.get_project(project['id'])
    if old.get('revision') != 1 or old.get('history', [{}])[-1].get('action') != 'created' or old.get('source') != project.get('source'):
        raise StudioError("El importador sella marcas solo en un proyecto nuevo.", 409)
    path = _pending_path(project['id'])
    if path.exists():
        raise StudioError("El comprobante pendiente ya existe; no se sobrescribe.", 409)
    record = {'schema':'ascendia.pending-brand-import/1','project_id':project['id'],'source_sha256':source['sha256'],
              'references':[{'asset_id':aid,'entity':entity,'sha256':sha} for (aid,entity),sha in sorted(references.items())],
              'editable_only':True,'editorial_approved':False,'publication_approved':False}
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as output:
        output.write(_data_document(record))
    project['pending_brand_references']={'schema':record['schema'],'record_sha256':core.digest(path),
        'status':'pending_local_observation','editorial_approved':False,'publication_approved':False}
    return path


def _observed_brand(registered, entity, source, catalog):
    """Use the private registry, never imported/client metadata as authority."""
    from .brand_assets import current_record
    _brand_entity(entity)
    _graphic_brand(registered, source, catalog)
    record = current_record(registered["id"], entity, "private_review")
    current = record.get("current", {})
    if (record.get("asset_id") != registered["id"] or record.get("sha256") != registered.get("sha256") or
            record.get("path") != registered.get("path") or current.get("valid") is not True or
            current.get("visual_reviewed") is not True or current.get("render_ready") is not True or
            current.get("eligible_for_context") is not True):
        raise StudioError("La marca perdió su observación, hash o disponibilidad para revisión privada.", 409)
    return record


def validate_brand_media(project, root=None, *, editable_only=False):
    """Read-only runtime guard for brand references in every editable scene.

    A private observed record permits technical use only. This helper grants
    neither original authorship, publishing permission nor editorial approval.
    All execution paths also call it after ordinary manual edits.
    """
    if not isinstance(project, dict):
        raise StudioError("Las referencias de marca requieren un proyecto.")
    if not isinstance(project.get("timeline", []), list):
        raise StudioError("Las referencias de marca requieren una cronología de datos.")
    pending = _pending_references(project)
    references = []
    media = []
    secondary = []
    for scene in project.get("timeline", []):
        if not isinstance(scene, dict):
            continue
        if "brand_entity" in scene:
            raise StudioError("brand_entity pertenece a un componente media del diseño, no a la escena.")
        for key in ("asset_id", "transition_asset_id"):
            if scene.get(key):
                if not isinstance(scene[key], str):
                    raise StudioError("El ID del recurso secundario requiere texto.")
                secondary.append(scene[key])
        overlays = scene.get("overlays", [])
        if not isinstance(overlays, list):
            raise StudioError("Las capas de marca requieren una lista de datos.")
        for layer in overlays:
            if isinstance(layer, dict):
                if "brand_entity" in layer:
                    raise StudioError("Las marcas se integran como componentes media del diseño, no como overlays sin contrato de marca.")
                if layer.get("asset_id"):
                    if not isinstance(layer['asset_id'], str):
                        raise StudioError("El ID del recurso de capa requiere texto.")
                    secondary.append(layer['asset_id'])
        if not isinstance(scene.get("motion_design"), dict):
            continue
        elements = scene["motion_design"].get("elements", [])
        if not isinstance(elements, list):
            raise StudioError("Los componentes de marca requieren una lista de datos.")
        for element in elements:
            if isinstance(element, dict) and element.get("type") == "media":
                media.append(element)
            if isinstance(element, dict) and "brand_entity" in element:
                if element.get("type") != "media":
                    raise StudioError("brand_entity pertenece solo a un componente media.")
                _closed_element(element)
                references.append(element)
    if (media or secondary) and core.WORKSPACE_MODE:
        from .brand_assets import catalog
        registered_ids = {row["asset_id"] for row in catalog("private_review")["records"] if row.get("asset_id")} | {key[0] for key in pending}
        if any(el.get("asset_id") in registered_ids and "brand_entity" not in el for el in media):
            raise StudioError("Un recurso registrado como marca conserva brand_entity explícito; quitarlo no evita su revisión vigente.", 409)
        if any(aid in registered_ids for aid in secondary):
            raise StudioError("Una marca registrada se integra como media con brand_entity, no como footage, transición ni overlay sin revisión de marca.", 409)
    if not references:
        return None
    if root is not None and Path(root).resolve() != Path(core.ROOT).resolve():
        raise StudioError("La marca debe validarse en su workspace canónico de ejecución.", 403)
    attached = project.get("assets", [])
    if not isinstance(attached, list) or any(not isinstance(a, dict) for a in attached):
        raise StudioError("Las marcas requieren recursos canónicos adjuntos.")
    records = core.assets()
    canonical = {a["id"]: a for a in records}
    source_id = _identifier(project.get("source"), "ID crudo de la marca")
    source = canonical.get(source_id)
    source_attached = next((a for a in attached if a.get("id") == source_id), None)
    if not source or source.get("kind") != "video" or not source_attached:
        raise StudioError("La marca no sustituye el crudo canónico del proyecto.")
    for key in ("path", "sha256", "kind", "probe"):
        if source_attached.get(key) != source.get(key):
            raise StudioError("El crudo declarado difiere de su registro canónico.", 403)
    for element in references:
        item = canonical.get(element["asset_id"])
        local = next((a for a in attached if a.get("id") == element["asset_id"]), None)
        if not item or not local:
            raise StudioError("La marca requiere un recurso canónico ya adjunto al proyecto.")
        for key in ("path", "sha256", "kind", "probe"):
            if item.get(key) != local.get(key):
                raise StudioError("La marca declarada difiere de su registro canónico.", 403)
        _graphic_brand(item, source, canonical)
        try:
            _observed_brand(item, element["brand_entity"], source, canonical)
        except StudioError:
            if not editable_only or pending.get((item['id'], element['brand_entity'])) != item['sha256']:
                raise
    return None


def imported_brand_status(project):
    """Computed GET status; the import marker records origin, not live approval."""
    if not project.get('pending_brand_references'):
        return None
    try:
        validate_brand_media(project)
        return {'status':'available_for_private_use','local_observation_pending':False,
                'editorial_approved':False,'publication_approved':False,'rights_authority':False}
    except StudioError as error:
        return {'status':'pending_local_observation','local_observation_pending':True,'reason':str(error),
                'editorial_approved':False,'publication_approved':False,'rights_authority':False}


def _canonical_assets(project, elements, catalog=None, *, pending=None, staging_brands=False):
    explicit_catalog = catalog is not None
    attached = project.get("assets", [])
    if not isinstance(attached, list) or any(not isinstance(a, dict) for a in attached):
        raise StudioError("SceneIR requiere los recursos canónicos del proyecto.")
    attached_ids = [a.get("id") for a in attached]
    if any(not isinstance(aid, str) or not aid for aid in attached_ids) or len(set(attached_ids)) != len(attached_ids):
        raise StudioError("Los recursos del proyecto requieren IDs únicos.")
    records = core.assets() if catalog is None else catalog
    if isinstance(records, dict):
        if any(not isinstance(value, dict) or key != value.get("id") for key, value in records.items()):
            raise StudioError("El catálogo de validación requiere IDs coherentes.")
        records = list(records.values())
    if not isinstance(records, list) or any(not isinstance(a, dict) for a in records):
        raise StudioError("El catálogo de validación requiere recursos de datos.")
    ids = [a.get("id") for a in records]
    if any(not isinstance(aid, str) or not re.fullmatch(IDENTIFIER, aid) for aid in ids) or len(set(ids)) != len(ids):
        raise StudioError("El catálogo de validación requiere IDs únicos y literales.")
    for record in records:
        if not isinstance(record.get("path"), str) or not record["path"]:
            raise StudioError("El catálogo de validación requiere rutas de datos.")
        core.confined(record["path"])
        sha = record.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise StudioError("El catálogo de validación requiere SHA256 reales.")
        probe = record.get("probe", {})
        if not isinstance(probe, dict) or not isinstance(probe.get("streams", []), list) or any(
                not isinstance(stream, dict) or not isinstance(stream.get("disposition", {}), dict)
                for stream in probe.get("streams", [])):
            raise StudioError("El catálogo requiere pistas inspeccionadas con estructura válida.")
    catalog = {a["id"]: a for a in records}
    source_id = project.get("source")
    source = catalog.get(source_id) if isinstance(source_id, str) else None
    if source is None or source_id not in attached_ids or source.get("kind") != "video" or not any(
            stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic")
            for stream in source.get("probe", {}).get("streams", [])):
        raise StudioError("SceneIR conserva un crudo canónico con pista de video real; así mantiene la narración existente.")
    visual_ids = {el["asset_id"] for el in elements if el["type"] == "media"}
    font_ids = {el["font_asset_id"] for el in elements if el["type"] == "text" and el.get("font_asset_id")}
    if visual_ids & font_ids:
        raise StudioError("Un recurso tipográfico no puede usarse simultáneamente como gráfico SceneIR.")
    if source_id in visual_ids:
        raise StudioError("El crudo no puede ocultarse como gráfico SceneIR.")
    if visual_ids and not explicit_catalog and core.WORKSPACE_MODE:
        from .brand_assets import catalog as brand_catalog
        known_brands = {row["asset_id"] for row in brand_catalog("private_review")["records"] if row.get("asset_id")}
        if any(el["type"] == "media" and el["asset_id"] in known_brands and "brand_entity" not in el for el in elements):
            raise StudioError("Un recurso registrado como marca requiere brand_entity explícito, también al compilar.", 409)
    used = {source_id} | visual_ids | font_ids
    for aid in used:
        if aid not in catalog or aid not in attached_ids:
            raise StudioError("El componente requiere un recurso canónico ya adjunto al proyecto.")
        local = next(a for a in attached if a["id"] == aid)
        registered = catalog[aid]
        for key in ("path", "sha256", "kind", "probe"):
            if local.get(key) != registered.get(key):
                raise StudioError("El recurso declarado difiere de su registro canónico.", 403)
        if aid == source_id:
            continue
        if aid in font_ids:
            from .fonts import validate_asset_font, inspect_font
            if registered.get("kind") != "font":
                raise StudioError("SceneIR requiere fuentes reales registradas; un medio no es tipografía.")
            if not explicit_catalog:
                validate_asset_font(registered)
            else:
                actual = inspect_font(registered["path"])
                if actual["sha256"] != registered["sha256"]:
                    raise StudioError("La fuente de la importación cambió.", 409)
            continue
        if core.source_related(registered, source, catalog):
            raise StudioError("Un derivado del crudo no puede ocultarse como gráfico SceneIR.")
        media = [el for el in elements if el["type"] == "media" and el["asset_id"] == aid]
        for element in media:
            if "brand_entity" in element:
                if explicit_catalog:
                    if not staging_brands:
                        raise StudioError("La importación de marca no acredita una observación local.", 409)
                    _graphic_brand(registered, source, catalog)
                else:
                    _graphic_brand(registered, source, catalog)
                    try:
                        _observed_brand(registered, element["brand_entity"], source, catalog)
                    except StudioError:
                        if (pending or {}).get((aid, element['brand_entity'])) != registered['sha256']:
                            raise
        if all("brand_entity" in element for element in media):
            continue
        metadata = registered.get("metadata", {})
        declaration = metadata.get("declaration_original", {}) if isinstance(metadata, dict) else {}
        if (registered.get("kind") != "image" or Path(registered.get("path", "")).suffix.lower() not in PICTURES
                or not isinstance(declaration, dict) or declaration.get("kind") != "original_graphic"
                or not isinstance(declaration.get("author"), str) or not declaration["author"].strip()):
            raise StudioError("SceneIR requiere un gráfico original declarado o brand_entity con registro observado vigente; no stock ni video.")


def _compile(project, document, catalog=None, *, pending=None, staging_brands=False):
    """Return a project copy containing one explicit, editable motion scene.

    No files, processes, timestamps or approvals are generated here. The caller
    owns canonical save/revision checks, render scheduling and individual QC.
    """
    if not isinstance(project, dict):
        raise StudioError("SceneIR requiere un proyecto existente.")
    encoded = _data_document(document)
    _object(document, ROOT_FIELDS, "SceneIR", ("schema", "content", "narrative_goal", "family", "representation",
                                             "duration", "composition", "components"))
    if document["schema"] != SCHEMA or document["representation"] != "conceptual":
        raise StudioError("SceneIR requiere ascendia.sceneir/1 y representación conceptual explícita.")
    _text(document["narrative_goal"], "objetivo narrativo", 2000)
    _identifier(document["family"], "familia declarada")
    duration = finite_number(document["duration"], "duración SceneIR", .1, 10)
    content = _object(document["content"], {"text", "entities", "actions", "results", "relations"}, "contenido", ("text",))
    _text(content["text"], "contenido textual", 10000)
    for field in ("entities", "actions", "results", "relations"):
        if field in content:
            if not isinstance(content[field], list) or len(content[field]) > 64:
                raise StudioError(f"contenido.{field} requiere hasta 64 declaraciones textuales.")
            for item in content[field]:
                _text(item, "declaración " + field, 500)
    parameters = _parameters(document.get("parameters", {}))
    composition = _object(document["composition"], {"background", "width", "height"}, "composición", ("background",))
    design.color(composition["background"], "fondo SceneIR")
    settings = project.get("settings")
    if not isinstance(settings, dict):
        raise StudioError("El proyecto requiere un lienzo existente.")
    size = []
    for key in ("width", "height"):
        value = finite_number(settings.get(key), "lienzo " + key, 160, 3840)
        if value % 2 or int(value) != value:
            raise StudioError("El lienzo del proyecto requiere dimensiones enteras y pares.")
        size.append(int(value))
        if key in composition and finite_number(composition[key], "composición " + key, 160, 3840) != value:
            raise StudioError("SceneIR no cambia el lienzo canónico: width/height deben coincidir con el proyecto.")
    components = document["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= 64:
        raise StudioError("SceneIR admite entre uno y 64 componentes.")
    elements = copy.deepcopy(components)
    for element in elements:
        _closed_element(element)
        if element["type"] == "text":
            element["text"] = _substitute(element.get("text"), parameters, "texto componente", 2000)
    if len({el["id"] for el in elements}) != len(elements):
        raise StudioError("Los componentes requieren IDs únicos.")
    _merge_actions(elements, document.get("actions", []), duration)
    digest = hashlib.sha256(encoded).hexdigest()
    scene_id = _identifier(document.get("scene_id", "sceneir_" + digest[:16]), "ID escena SceneIR")
    scene = {"id": scene_id, "start": 0, "end": duration, "type": "motion", "template": "custom",
             "motion_design": {"canvas": {"background": composition["background"]}, "elements": elements},
             "decision": {"status": "draft", "search": "SceneIR explícito; sin stock ni b-roll.",
                          "reason": document["narrative_goal"], "evidence": []}}
    design.validate_design(scene, tuple(size))
    _canonical_assets(project, elements, catalog, pending=pending, staging_brands=staging_brands)
    result = copy.deepcopy(project)
    _substitute(content["text"], parameters, "contenido textual", 10000)
    result.update(timeline=[scene], mode="scene_ir_component", stage="storyboard", review={}, renders=[],
                  design_snapshots={}, design_reviews={}, gates={}, approval_current=False)
    result.pop("approved_export", None)
    result.pop("full_authorization", None)
    result["scene_ir"] = {"schema": SCHEMA, "duration": duration, "document_sha256": digest,
                          "document": json.loads(encoded),
                          "representation": "conceptual", "semantic_origin": "author_declared", "status": "pending_qc",
                          "clone_fidelity": "not_reviewed", "rights_verified": False,
                          "timing": "explicit_scene_local; narration retained without invented alignment"}
    return result


def compile_scene_ir(project, document):
    """Compile against the real canonical catalog; never accept a caller catalog."""
    return _compile(project, document)


def _validate_compiled(project, catalog=None, *, editable_only=False, staging_brands=False):
    """Validate the protected origin and the current, freely edited component.

    Geometry/text/keys may evolve after compilation. The origin remains an
    honest immutable declaration, rather than a claim about the edited image.
    """
    if not isinstance(project, dict) or project.get("mode") != "scene_ir_component":
        raise StudioError("El proyecto requiere modo scene_ir_component.")
    fields = {"schema", "duration", "document_sha256", "document", "representation", "semantic_origin",
              "status", "clone_fidelity", "rights_verified", "timing"}
    origin = _object(project.get("scene_ir"), fields, "origen SceneIR", fields)
    pending = _pending_references(project) if editable_only else None
    expected = _compile(project, origin["document"], catalog, pending=pending, staging_brands=staging_brands)["scene_ir"]
    if origin != expected:
        raise StudioError("El origen SceneIR fue alterado: esquema, duración, huella y declaraciones deben coincidir.", 409)
    timeline = project.get("timeline")
    if not isinstance(timeline, list) or len(timeline) != 1 or not isinstance(timeline[0], dict):
        raise StudioError("SceneIR contiene un componente editable único.")
    scene = timeline[0]
    if scene.get("type") != "motion" or scene.get("template") != "custom" or scene.get("start") != 0:
        raise StudioError("SceneIR requiere una escena motion/custom desde cero.")
    finite_number(scene.get("start"), "inicio componente SceneIR", 0, 0)
    finite_number(scene.get("end"), "duración componente SceneIR", .1, 10)
    # A caller cannot add footage through secondary native scene channels.
    if any(scene.get(key) for key in ("asset_id", "transition_asset_id", "overlays", "source_in", "broll_in")):
        raise StudioError("SceneIR solo usa medios gráficos en sus componentes; no capas de stock ni footage.")
    elements = scene.get("motion_design", {}).get("elements") if isinstance(scene.get("motion_design"), dict) else None
    if not isinstance(elements, list):
        raise StudioError("SceneIR requiere componentes de diseño editables.")
    for element in elements:
        _closed_element(element)
    settings = project.get("settings", {})
    design.validate_design(scene, (settings["width"], settings["height"]))
    _canonical_assets(project, elements, catalog, pending=pending, staging_brands=staging_brands)


def validate_compiled_project(project):
    """Check protected origin/current component against the real catalog."""
    return _validate_compiled(project)


def validate_editable_component(project):
    """Save-only validation; pending imports require their private proof."""
    return _validate_compiled(project, editable_only=True)


def validate_import_project(project, catalog):
    """Pure preflight against explicit, already decoded ZIP staging records.

    The importer is responsible for staging confinement, hashes and decoding.
    This function never registers those records or asserts they are canonical.
    Normal compilation/validation always reads the actual local catalog.
    """
    if not isinstance(catalog, (dict, list)):
        raise StudioError("El preflight de importación requiere un catálogo explícito.")
    return _validate_compiled(project, catalog, staging_brands=True)


def validate_import_brand_media(project, catalog):
    """Pure closed brand/raster preflight for a multis-scene editable import."""
    elements = []
    for scene in project.get('timeline', []):
        if 'brand_entity' in scene:
            raise StudioError("La entidad de marca pertenece a un componente media.")
        for layer in scene.get('overlays', []):
            if 'brand_entity' in layer:
                raise StudioError("Las marcas importadas usan componentes media, no overlays.")
        for element in (scene.get('motion_design') or {}).get('elements', []):
            if 'brand_entity' in element:
                _closed_element(element)
                elements.append(element)
    if elements:
        _canonical_assets(project, elements, catalog, staging_brands=True)
    return None


def describe_schema():
    """Return a closed JSON Schema and an executable-shape example."""
    from .brand_assets import ORIGINS
    number = lambda lo, hi: {"type": "number", "minimum": lo, "maximum": hi}
    identifier = {"type": "string", "pattern": "^" + IDENTIFIER + "$"}
    color = {"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"}
    window = {"type": "array", "minItems": 2, "maxItems": 2, "items": number(0, 1),
              "description": "lo < hi; hi - lo >= 0.000001"}
    channels = {key: number(lo, hi) for key, lo, hi in (("x", -2, 2), ("y", -2, 2), ("scale", .01, 8),
                ("opacity", 0, 1), ("rotation", -3600, 3600), ("mask_progress", 0, 1))}
    closed = lambda props, required=(): {"type": "object", "additionalProperties": False,
                                        "properties": props, "required": list(required)}
    text = lambda n: {"type": "string", "maxLength": n}
    key = closed({"time": number(0, 10), **channels, "ease": {"enum": list(design.EASES)}, "ease_window": window}, ("time",))
    point = closed({"x": number(-2, 2), "y": number(-2, 2)}, ("x", "y"))
    mask = closed({"type": {"enum": ["none", "circle", "inset"]},
                   "inset": closed({side: number(0, 1) for side in ("top", "right", "bottom", "left")})})
    text_style = closed({"align": {"enum": ["left", "center", "right"]},
        "vertical_align": {"enum": ["top", "middle", "bottom"]},
        "letter_spacing": number(-16, 80), "line_height": number(.8, 3),
        "stroke": closed({"width": number(0, 16), "color": color}),
        "shadow": closed({"enabled": {"type": "boolean"}, "x": number(-40, 40),
            "y": number(-40, 40), "blur": number(0, 20), "color": color, "opacity": number(0, 1)})})
    text_animation = closed({"preset": {"enum": ["none", "fade_up", "slide", "pop", "wipe", "typewriter", "word_reveal"]},
        "duration": number(.01, 10), "exit": {"enum": ["none", "fade", "slide"]},
        "exit_duration": number(.01, 10), "clock_start": number(-86400, 86400),
        "clock_offset": number(0, 86400), "clock_duration": {"type": "number", "exclusiveMinimum": 0, "maximum": 86400}})
    common = {"id": identifier, "type": {"enum": ["text", "shape", "media"]},
              **{key: number(0, 1) for key in ("x", "y", "opacity")},
              **{key: number(.005, 1) for key in ("width", "height")},
              "start": number(0, 10), "end": number(0, 10), "rotation": channels["rotation"],
              "z": number(-1000, 1000), "radius": number(0, 540), "color": color, "color_reason": text(2000), "mask": mask,
              "keyframes": {"type": "array", "maxItems": 128, "items": key},
              "path": closed({"orient": {"const": False}, "points": {"type": "array", "minItems": 2,
                       "maxItems": 64, "items": point}}, ("points",))}
    variants = []
    for kind, extra, required in (("text", {"text": text(2000), "font": {"enum": ["primary", "accent"]},
                                  "font_size": {**number(8, 400), "description": "Pixels at REFERENCE canvas width1080, not output pixels. At output width360:120 ->40px,42 ->14px. Element/preset scale changes effective size. Narrated scenes that declare text need a main visible block >=48px reference (=16px at360) sustained for min(0.7s,scene duration); small secondary labels remain allowed. This is geometric QC, not proof of human reading."}, "font_asset_id": identifier,
                                  "text_style": text_style, "text_animation": text_animation}, ("text",)),
                                 ("shape", {"shape": {"enum": ["rect", "ellipse"]}}, ()),
                                 ("media", {"asset_id": identifier, "source_in": {"const": 0},
                                            "brand_entity": {"enum": list(ORIGINS),
                                                "description": "Optional explicit brand; requires a current observed local raster record for private_review, never original-author or publication approval."}}, ("asset_id",))):
        variants.append(closed({**common, "type": {"const": kind}, **extra}, ("id", "type", *required)))
    content = closed({"text": text(10000), **{field: {"type": "array", "maxItems": 64, "items": text(500)}
                      for field in ("entities", "actions", "results", "relations")}}, ("text",))
    action = closed({"target_id": identifier, "time": number(0, 10),
                     "properties": {**closed(channels), "minProperties": 1},
                     "ease": {"enum": list(design.EASES)}, "ease_window": window}, ("target_id", "time", "properties"))
    result = closed({"schema": {"const": SCHEMA}, "scene_id": identifier, "content": content,
                     "narrative_goal": text(2000), "family": identifier, "representation": {"const": "conceptual"},
                     "duration": number(.1, 10), "composition": closed({"background": color,
                     "width": {"type": "integer", "minimum": 160, "maximum": 3840, "multipleOf": 2},
                     "height": {"type": "integer", "minimum": 160, "maximum": 3840, "multipleOf": 2}}, ("background",)),
                     "parameters": {"type": "object", "maxProperties": 64, "propertyNames": {"pattern": "^" + PARAMETER + "$"},
                     "additionalProperties": {"oneOf": [text(2000), number(-1e12, 1e12)]}},
                     "components": {"type": "array", "minItems": 1, "maxItems": 64, "items": {"oneOf": variants}},
                     "actions": {"type": "array", "maxItems": MAX_ACTIONS, "items": action}},
                    ("schema", "content", "narrative_goal", "family", "representation", "duration", "composition", "components"))
    result.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "ASCENDIA SceneIR 1",
                   "description": "Datos explícitos a una escena motion/custom. Familia declarada, QC pendiente; sin generación semántica ni aprobación automática.",
                   "x-constraints": {"action_time": "local scene seconds, <= duration", "coordinates": "normalized canvas top-left",
                   "font_size_radius": "pixels at reference width 1080", "path": "canvas pixel-distance linear travel; overrides x/y",
                   "parameters": "single literal substitution only content.text/components[].text; inserted values are never evaluated",
                   "assets": "attached canonical fonts for font_asset_id; media requires canonical original_graphic image and author OR explicit brand_entity with current locally observed private_review registry/hash; no raw-source lineage, stock, video or unrendered SVG; imported registry claims do not grant usage",
                   "typography": "actual TTF/OTF face, measured grapheme layout; no substitution or synthetic styles; text-animation clock survives trim/split",
                   "source": "existing canonical real-video source retained with its original audio",
                   "timeline": "replace timeline of returned copy only, scene starts at 0; no store/render"}})
    return result
