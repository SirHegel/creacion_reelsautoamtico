from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import threading
import tempfile
import fcntl
import time
import uuid
from pathlib import Path
from .runtime import CODE_ROOT, DATA_ROOT, MANUAL_ROOT, validate_workspace, WorkspaceConfigurationError

ROOT = DATA_ROOT
WORKSPACE_MODE = DATA_ROOT != CODE_ROOT
class StoreLock:
    """Reentrant thread + POSIX process lock shared by UI, CLI and MCP."""
    def __init__(self):
        self.thread = threading.RLock()
        self.local = threading.local()

    def __enter__(self):
        self.thread.acquire()
        depth = getattr(self.local, "depth", 0)
        if depth == 0:
            handle = None
            try:
                target = confined(".estado/store.lock")
                target.parent.mkdir(parents=True, exist_ok=True)
                handle = target.open("a+b")
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                self.local.file = handle
            except Exception:
                if handle is not None:
                    handle.close()
                self.thread.release()
                raise
        self.local.depth = depth + 1
        return self

    def __exit__(self, *args):
        self.local.depth -= 1
        if self.local.depth == 0:
            fcntl.flock(self.local.file.fileno(), fcntl.LOCK_UN)
            self.local.file.close()
        self.thread.release()


LOCK = StoreLock()
HASH_CACHE = {}
DOCUMENTS = ("AGENTS.md", "PROMPT_MAESTRO.md", "INSTRUCCIONES.md", "STYLE_YO.md")
POLICY = {"name": "ASCENDIA V5", "preview_seconds": 10, "split": [55, 45],
          "max_presenter_continuous": 3, "hook_seconds": 4.5,
          "identity": "YO", "motion_references": ["CLONE"],
          "technical_preview_seconds": 3,
          "current_production_phase": "clone_creative_B_v2",
          "parent_creative_scope": "B_v2_preserve_B_structure_fifteen_families_CANCELLED_and_B_v1_comparison",
          "parent_integration": "no_additional_A_B_C_demos_no_YO_integration_B_v2_user_review_pending",
          "library_render": "automatic_components_up_to_10s_with_pending_qc",
          "library_semantics": "author_declared_scene_ir_no_internal_semantic_generator",
          "clone_design_interval": [1.6, 3.2], "design_before_animation": True,
          "clone_static_reference_time": 3.10, "clone_static_iteration": 2,
          "parent_static_design_approval": "declared_in_manual_not_inherited_by_software_projects",
          "parent_architecture": "declared_verified_in_canonical_manual_do_not_repeat",
          "required_fonts": ["Sequel Sans Bold Disp", "Scholar Italic"],
          "tella": "excluded", "full_render": "requires_explicit_authorization",
          "publication": "not_enabled"}
TEMPLATES = [
    {"id": "workflow", "name": "Transferencia de datos", "description": "Entrada, transferencia, reacción y convergencia en resultado conceptual.", "phases": ["entrada", "acción", "reacción", "transformación", "salida"], "kind": "conceptual", "implemented": True},
    {"id": "compare", "name": "Comparación que se resuelve", "description": "Dos conceptos se enfrentan y se transforman en una conclusión del guion.", "phases": ["comparación", "separación", "resolución", "salida"], "kind": "conceptual", "implemented": True},
    {"id": "kinetic", "name": "Frase editorial", "description": "Jerarquía y revelación tipográfica integrada, sin transcripción automática del hook.", "phases": ["revelación", "énfasis", "transformación", "salida"], "kind": "conceptual", "implemented": True},
    {"id": "counter", "name": "Dato del guion", "description": "Representa exclusivamente una cifra suministrada por el guion.", "phases": ["entrada", "conteo", "resultado", "salida"], "kind": "conceptual", "implemented": True},
    {"id": "custom", "name": "Composición libre", "description": "Elementos editables, máscaras, trayectorias y curvas; requiere dirección específica por narración.", "phases": ["diseño", "acción", "reacción", "transformación", "salida"], "kind": "conceptual", "implemented": True},
]


class StudioError(Exception):
    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.status, self.details = status, details


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def uid(prefix=""):
    return prefix + uuid.uuid4().hex[:16]


def confined(path, root=None, must_exist=False):
    root = ROOT if root is None else root
    if root == DATA_ROOT and DATA_ROOT != CODE_ROOT:
        try:
            validate_workspace(DATA_ROOT)
        except WorkspaceConfigurationError as error:
            raise StudioError("El workspace dejó de ser un directorio real autorizado.", 403) from error
    path = Path(path)
    result = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not result.is_relative_to(root.resolve()):
        raise StudioError("La ruta debe permanecer dentro de SOFTWARE.", 403)
    if must_exist and not result.is_file():
        raise StudioError("Archivo local inexistente.", 404)
    return result


def relative(path):
    return confined(path).relative_to(ROOT).as_posix()


def atomic_json(path, data):
    path = confined(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path, default=None):
    path = confined(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else copy.deepcopy(default)


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def content_hash(path):
    """Cache hashes against inode, mtime AND ctime; changes invalidate approvals."""
    p = confined(path, must_exist=True)
    st = p.stat()
    key = (str(p), st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    if key not in HASH_CACHE:
        value = digest(p)
        after = p.stat()
        after_key = (str(p), after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if after_key != key:
            raise StudioError("Un recurso cambió mientras se verificaba su contenido.", 409)
        HASH_CACHE[key] = value
    return HASH_CACHE[key]


def setup():
    for folder in ("projects", "exports", "assets/broll", "assets/fonts", "assets/audio", "assets/video", "assets/images", ".estado/tmp", ".estado/cache", ".estado/models", ".estado/logs"):
        confined(folder).mkdir(parents=True, exist_ok=True)
    for name, folder in {"TMPDIR": "tmp", "XDG_CACHE_HOME": "cache", "XDG_CONFIG_HOME": "config", "HF_HOME": "models/huggingface", "HF_HUB_CACHE": "models/huggingface/hub", "HUGGINGFACE_HUB_CACHE": "models/huggingface/hub", "HF_XET_CACHE": "models/huggingface/xet", "HF_ASSETS_CACHE": "models/huggingface/assets", "TORCH_HOME": "models/torch", "MPLCONFIGDIR": "cache/matplotlib", "NUMBA_CACHE_DIR": "cache/numba"}.items():
        target = confined(".estado/" + folder)
        target.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(target)
    os.environ["HF_TOKEN_PATH"] = str(confined(".estado/config/hf_token"))
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    for token in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_HUB_TOKEN", "HF_API_TOKEN"):
        os.environ.pop(token, None)
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["OMP_NUM_THREADS"] = "2"
    os.environ["OPENBLAS_NUM_THREADS"] = "2"
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import tempfile
    tempfile.tempdir = str(confined(".estado/tmp"))


def manual_fingerprints():
    if WORKSPACE_MODE:
        from .branding import profile_document
        document = profile_document()
        return {document["name"]: {"source": "profiles/ivan_base.json", "sha256": document["sha256"], "bytes": document["bytes"]}}
    # Canonical manuals are read-only. Never duplicate or mutate the active workflow.
    result = {}
    for name in DOCUMENTS:
        p = MANUAL_ROOT / name
        if p.is_file():
            content = p.read_bytes()
            result[name] = {"source": "../" + name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
        else:
            result[name] = {"missing": True}
    return result


def fonts():
    if WORKSPACE_MODE:
        from .branding import font_paths
        return font_paths(ROOT)
    return {"primary": "assets/fonts/Sequel_Sans_Bold_Disp.ttf", "accent": "assets/fonts/Scholar_Italic.ttf"}


def font_path(path):
    resolved = confined(path)
    if not resolved.is_relative_to(ROOT / "assets/fonts"):
        raise StudioError("Las fuentes del proyecto deben estar en assets/fonts; los archivos privados no se exportan.", 403)
    return resolved


def state(**changes):
    with LOCK:
        value = read_json("ESTADO.json", {"app": "Ascendia Studio", "scope": "SOFTWARE", "active_parent_untouched": True})
        value.update(changes, updated_at=now())
        atomic_json("ESTADO.json", value)


def assets():
    return read_json(".estado/assets.json", [])


def asset(asset_id):
    found = next((a for a in assets() if a["id"] == asset_id), None)
    if not found:
        raise StudioError("Recurso no encontrado.", 404)
    return found


def source_related(candidate, source, catalog):
    """Recognize declared source derivatives; this is lineage, not face identity."""
    if not isinstance(candidate, dict) or not isinstance(source, dict):
        return False
    values = list(catalog.values()) if isinstance(catalog, dict) else catalog
    by_id = {a.get("id"): a for a in values if isinstance(a, dict)}
    by_sha = {a.get("sha256"): a for a in values if isinstance(a, dict) and a.get("sha256")}
    item, seen = by_id.get(candidate.get("id"), candidate), set()
    for _ in range(64):
        if item.get("id") == source.get("id") or (source.get("sha256") and item.get("sha256") == source["sha256"]):
            return True
        identity = item.get("id") or item.get("sha256")
        if identity in seen:
            return True  # ambiguous circular lineage is unsuitable as b-roll
        seen.add(identity)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        provenance = metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
        parent_id = provenance.get("source_asset_id") or metadata.get("source")
        parent_sha = provenance.get("source_sha256")
        parent_id = parent_id if isinstance(parent_id, str) else None
        parent_sha = parent_sha if isinstance(parent_sha, str) else None
        if parent_id == source.get("id") or (parent_sha and parent_sha == source.get("sha256")):
            return True
        parent = by_id.get(parent_id) or by_sha.get(parent_sha)
        if parent is None:
            return False
        item = parent
    return True


def source_background_removed(candidate, catalog):
    """Recognize declared removal in a source chain; never infer it visually."""
    rows = list(catalog.values()) if isinstance(catalog, dict) else catalog
    rows = [a for a in rows if isinstance(a, dict)]
    by_id = {a.get("id"): a for a in rows}
    by_sha = {a.get("sha256"): a for a in rows if a.get("sha256")}
    item, seen = candidate, set()
    for _ in range(64):
        if not isinstance(item, dict):
            return False
        identity = item.get("id") or item.get("sha256")
        if not isinstance(identity, str) or identity in seen:
            return False
        seen.add(identity)
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        provenance = metadata.get("provenance") if isinstance(metadata.get("provenance"), dict) else {}
        if provenance.get("operation") in ("remove_background_video", "chromakey_video"):
            return True
        parent_id = provenance.get("source_asset_id") or metadata.get("source")
        parent_sha = provenance.get("source_sha256")
        item = by_id.get(parent_id) if isinstance(parent_id, str) else None
        if item is None and isinstance(parent_sha, str):
            item = by_sha.get(parent_sha)
    return False


def register_asset(path, name=None, kind=None, metadata=None):
    from .jobs import CPU_ACTIVE, cpu_slot
    # Batch staging already owns CPU before taking its store transaction.
    # Browser proxies are deferred until that transaction is released.
    if getattr(LOCK.local, "depth", 0):
        if not getattr(CPU_ACTIVE, "active", False):
            raise StudioError("La importación debe reservar el procesador antes de abrir el almacén.", 409)
        return _register_asset(path, name, kind, metadata)
    with cpu_slot():
        item = _register_asset(path, name, kind, metadata)
        return _register_preview(item)


def _register_preview(item):
    try:
        from .previews import ensure_preview
        updated = ensure_preview(item, ROOT)
    except (ImportError, StudioError, OSError) as error:
        updated = {**item, "preview_error": str(error)}
    extras = {k: v for k, v in updated.items() if k.startswith("preview_")}
    if extras:
        with LOCK:
            catalog = assets()
            stored = next(a for a in catalog if a["id"] == item["id"])
            stored.update(extras)
            atomic_json(".estado/assets.json", catalog)
        return {**item, **extras}
    return item


def _register_asset(path, name=None, kind=None, metadata=None):
    p = confined(path, must_exist=True)
    name = Path(name or p.name).name
    with LOCK:
        sha = digest(p)
        catalog = assets()
        existing = next((a for a in catalog if a["sha256"] == sha), None)
        if existing:
            if digest(confined(existing["path"], must_exist=True)) != sha or digest(p) != sha:
                raise StudioError("El original canónico cambió; no se reutiliza ni reemplaza automáticamente.", 409)
            return existing
        with tempfile.TemporaryDirectory(prefix="import_", dir=confined(".estado/tmp")) as staging:
            snapshot = Path(staging) / ("source" + Path(name).suffix.lower())
            shutil.copy2(p, snapshot)
            if digest(snapshot) != sha or digest(p) != sha:
                raise StudioError("El original cambió durante su importación; vuelve a cargarlo cuando esté estable.", 409)
            return _register_snapshot(p, snapshot, name, kind, metadata, sha, catalog)


def _register_snapshot(original, p, name, kind, metadata, sha, catalog):
    from .analysis import probe, thumbnails, waveform
    with LOCK:
        suffix = Path(name).suffix.lower()
        is_font = suffix in (".ttf", ".otf")
        info = {} if is_font else probe(p)
        streams = info.get("streams", [])
        video = any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in streams)
        audio = any(s.get("codec_type") == "audio" for s in streams)
        image = suffix in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
        if image:
            from PIL import Image
            try:
                with Image.open(p) as picture:
                    picture.verify()
            except (OSError, ValueError) as error:
                raise StudioError("El archivo no es una imagen válida para su extensión.") from error
        if not (is_font or video or audio):
            raise StudioError("Formato sin pista de video, imagen o audio decodificable.")
        inferred = "font" if is_font else "image" if image else "video" if video else "audio"
        kind = kind if kind in ("broll", "video", "audio", "music", "sfx", "image", "font") else inferred
        if kind == "font" and not is_font:
            raise StudioError("El recurso no es un archivo tipográfico.")
        if kind == "image" and not image:
            raise StudioError("El recurso no es una imagen estática admitida.")
        if kind in ("audio", "music", "sfx") and not audio:
            raise StudioError("Este recurso no contiene una pista de audio.")
        if kind in ("video", "broll") and (not video or image):
            raise StudioError("Este recurso no es un clip de video.")
        folder = "fonts" if is_font else "images" if image else "audio" if not video else "broll" if kind == "broll" else "video"
        target = confined(f"assets/{folder}/{sha[:20]}{suffix}")
        if is_font:
            from .fonts import inspect_font
            font_info = inspect_font(p)
            from PIL import ImageFont
            try:
                ImageFont.truetype(str(p), 24)
            except OSError as error:
                raise StudioError("Archivo tipográfico inválido.") from error
            for canonical in fonts().values():
                f = confined(canonical)
                if f.is_file() and digest(f) == sha:
                    target = f
                    break
        if digest(p) != sha or digest(original) != sha:
            raise StudioError("El original cambió durante su inspección; no se registra una copia inconsistente.", 409)
        if target.exists():
            if digest(target) != sha:
                raise StudioError("La ruta canónica contiene otro contenido; no se sobrescribe.", 409)
        else:
            os.replace(p, target)
        duration = float(info.get("format", {}).get("duration", 0) or 0)
        item = {"id": "a_" + sha[:20], "name": name, "path": relative(target), "kind": kind,
                "sha256": sha, "md5": digest(target, "md5"), "size": target.stat().st_size,
                "duration": duration, "probe": info, "created_at": now(),
                "url": "/api/media/a_" + sha[:20], "metadata": metadata or {},
                "verification": {"visual": False, "audio": False, "rights": "supplied_by_user_unverified"}}
        if is_font:
            item["font_info"] = font_info
        if video:
            try:
                thumbs = thumbnails(target, sha[:20], duration)
                item["thumbnail"] = "/api/files/" + thumbs[0] if thumbs else None
                item["thumbnails"] = thumbs
            except StudioError as error:
                item["thumbnail_error"] = str(error)
        if audio:
            try:
                item["waveform"] = waveform(target)
            except StudioError as error:
                item["waveform_error"] = str(error)
        if digest(target) != sha:
            raise StudioError("El recurso canónico cambió antes de registrarse.", 409)
        catalog.append(item)
        atomic_json(".estado/assets.json", catalog)
        return item


def project_path(project_id):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", project_id):
        raise StudioError("ID de proyecto inválido.")
    return confined(f"projects/{project_id}/project.json")


def get_project(project_id):
    p = read_json(project_path(project_id))
    if p is None:
        raise StudioError("Proyecto no encontrado.", 404)
    # Refresh browser derivatives without replacing editorial observations or
    # incrementing the editable revision. Originals remain canonical.
    catalog = {a["id"]: a for a in assets()}
    for item in p.get("assets", []):
        canonical = catalog.get(item.get("id"))
        if canonical and canonical.get("sha256") == item.get("sha256"):
            item.update({k: v for k, v in canonical.items() if k.startswith("preview_")})
    p["approval_current"] = approval_is_current(p)
    from .scene_ir import imported_brand_status
    imported_brands = imported_brand_status(p)
    if imported_brands is not None:
        p['brand_references_state'] = imported_brands
    else:
        p.pop('brand_references_state', None)
    return p


def project_list():
    result = []
    for path in sorted(confined("projects").glob("*/project.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        p = read_json(path)
        result.append({k: p.get(k) for k in ("id", "name", "revision", "updated_at", "source", "stage", "drive_id")})
    return result


def source_project(source, excluding=None, drive_id=None):
    if source or drive_id:
        for item in project_list():
            if item["id"] != excluding and ((source and item.get("source") == source) or (drive_id and item.get("drive_id") == drive_id)):
                return get_project(item["id"])
    return None


def create_project(name="Nuevo reel", source=None, drive_id=None):
    with LOCK:
        if drive_id:
            for item in project_list():
                old = get_project(item["id"])
                if old.get("drive_id") == drive_id:
                    if source and old.get("source") and old["source"] != source:
                        raise StudioError("El ID de Drive ya está asociado a otro contenido; revisa el crudo antes de reemplazarlo.", 409,
                                          {"project_id": old["id"], "source": old["source"]})
                    if source and not old.get("source"):
                        return attach_asset(old["id"], source, source=True)
                    return old
        if source:
            a = asset(source)
            if a.get("kind") == "image" or not any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in a.get("probe", {}).get("streams", [])):
                raise StudioError("El crudo requiere una pista de video real, distinta de una portada de audio.")
            for item in project_list():
                old = get_project(item["id"])
                if old.get("source") == source:
                    return old
        p = {"id": uid("p_"), "name": str(name)[:200], "revision": 1, "created_at": now(), "updated_at": now(),
             "stage": "import", "source": source, "drive_id": drive_id,
             "settings": {"width": 1080, "height": 1920, "fps": 30, "engine": "native"}, "style": copy.deepcopy(POLICY),
             "fonts": fonts(), "manual": manual_fingerprints(), "assets": [a] if source else [],
             "transcript": {"words": [], "segments": [], "status": "pending"}, "timeline": [], "audio": [],
             "review": {}, "renders": [], "reference_review": {}, "library_searches": [],
             "history": [{"at": now(), "action": "created"}], "gates": {}}
        if WORKSPACE_MODE:
            p['settings']['split_motion_ratio'] = .5
            from .branding import bind_project
            bind_project(p, ROOT)
            p["style"].update(current_production_phase="ivan_multiservice", parent_creative_scope="independent_read_only_source", parent_integration="YO_plus_CLONE_own_branding")
        atomic_json(project_path(p["id"]), p)
        state(last_project=p["id"], stage="editor_ready")
        return p


def finite_number(value, field, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < lo or value > hi:
        raise StudioError(f"Valor inválido para {field} ({lo}–{hi}).")
    return value


def validate_shape(p):
    if not isinstance(p, dict):
        raise StudioError("El proyecto requiere un objeto JSON.")
    for key in ("style", "settings", "fonts", "transcript", "reference_review", "review"):
        if key in p and not isinstance(p[key], dict):
            raise StudioError(f"{key} requiere un objeto JSON.")
    for key in ("timeline", "audio", "assets"):
        if not isinstance(p.get(key, []), list) or any(not isinstance(item, dict) for item in p.get(key, [])):
            raise StudioError(f"{key} requiere una lista de objetos.")
    for key in ("source", "drive_id"):
        if p.get(key) is not None and not isinstance(p[key], str):
            raise StudioError(f"{key} requiere un ID de texto.")
    if p.get("mode", "reel") not in ("reel", "scene_ir_component"):
        raise StudioError("Modo de proyecto no admitido.")
    if p.get("mode") == "scene_ir_component" and not isinstance(p.get("scene_ir"), dict):
        raise StudioError("El componente requiere su origen SceneIR.")
    style = p.get("style", {})
    if style.get("name") != POLICY["name"]:
        raise StudioError("Este proyecto utiliza el preset ASCENDIA V5.")
    finite_number(style.get("hook_seconds", 4.5), "duración hook", 4, 6)
    settings = p.get("settings", {})
    if settings.get("engine", "native") not in ("native", "hyperframes"):
        raise StudioError("Motor de render no admitido.")
    if 'split_motion_ratio' in settings:
        finite_number(settings['split_motion_ratio'], 'proporción superior del split', .5, .55)
    for key, lo, hi in (("width", 160, 3840), ("height", 160, 3840), ("fps", 10, 60)):
        finite_number(settings.get(key), key, lo, hi)
        if int(settings[key]) != settings[key] or (key != "fps" and settings[key] % 2):
            raise StudioError(f"{key} debe ser entero" + (" y par." if key != "fps" else "."))
    if settings.get("voice_audio_stream") is not None:
        from .analysis import select_audio_stream, validate_audio_stream_index
        index = validate_audio_stream_index(settings["voice_audio_stream"])
        if not p.get("source"):
            raise StudioError("Selecciona una pista de voz de un crudo canónico.")
        selected_source = asset(p["source"])
        select_audio_stream(selected_source.get("probe", {}), index)
    if len(p.get("timeline", [])) > 500 or len(p.get("audio", [])) > 100:
        raise StudioError("Demasiadas capas en un proyecto.")
    scene_ids = set()
    for scene in p.get("timeline", []):
        if not isinstance(scene.get("id"), str) or not scene["id"] or scene["id"] in scene_ids:
            raise StudioError("Las escenas requieren IDs únicos.")
        scene_ids.add(scene["id"])
        if scene.get("type") not in ("presenter", "split", "broll", "motion"):
            raise StudioError("Tipo de escena no admitido.")
        start = finite_number(scene.get("start"), "inicio", 0, 24 * 3600)
        end = finite_number(scene.get("end"), "fin", 0, 24 * 3600)
        if end <= start:
            raise StudioError("El fin de la escena debe ser posterior al inicio.")
        if "camera_anchors" in scene:
            anchors = scene["camera_anchors"]
            if scene["type"] not in ("presenter", "split") or not isinstance(anchors, list) or not 1 <= len(anchors) <= 300:
                raise StudioError("Las anclas de cámara requieren una escena con presentador y hasta 300 muestras.")
            previous_anchor = -1.0
            for anchor in anchors:
                if not isinstance(anchor, dict) or set(anchor) != {"time", "focus_x", "focus_y", "chin_y"}:
                    raise StudioError("Cada ancla requiere tiempo, foco y barbilla normalizados.")
                at = finite_number(anchor["time"], "tiempo de ancla", 0, end-start)
                if at - previous_anchor < 1e-6:
                    raise StudioError("Las anclas requieren una separación mínima de un microsegundo.")
                previous_anchor = at
                for coordinate in ("focus_x", "focus_y", "chin_y"):
                    finite_number(anchor[coordinate], coordinate, 0, 1)
        if len(str(scene.get("title", ""))) > 500 or len(str(scene.get("subtitle", ""))) > 1000:
            raise StudioError("Texto de escena demasiado largo.")
        finite_number(scene.get("source_in", start if scene["type"] in ("presenter", "split") else 0), "entrada del medio", 0, 24 * 3600)
        finite_number(scene.get("broll_in", 0), "entrada b-roll superior", 0, 24 * 3600)
        finite_number(scene.get("chin_y", .65), "barbilla normalizada", 0, 1)
        if not isinstance(scene.get("template", "workflow"), str) or scene.get("template", "workflow") not in {t["id"] for t in TEMPLATES}:
            raise StudioError("Plantilla no admitida.")
        from .design import validate_design
        validate_design(scene, (settings["width"], settings["height"]))
        if scene.get("font", "primary") not in ("primary", "accent"):
            raise StudioError("Elige Sequel principal o Scholar de énfasis.")
        color = scene.get("text_color", "white")
        if not isinstance(color, str) or (color not in ("white", "black") and not re.fullmatch(r"#[0-9a-fA-F]{6}", color)):
            raise StudioError("El color de texto debe ser #RRGGBB, white o black.")
        motion = scene.get("motion", {})
        if not isinstance(motion, dict):
            raise StudioError("Los parámetros motion requieren un objeto.")
        for key in ("value", "from"):
            if key in motion:
                finite_number(motion[key], f"dato motion {key}", -1e12, 1e12)
        if "decimals" in motion:
            finite_number(motion["decimals"], "decimales del contador", 0, 4)
            if int(motion["decimals"]) != motion["decimals"]:
                raise StudioError("Los decimales del contador deben ser enteros.")
        if not isinstance(scene.get("effects", {}), dict):
            raise StudioError("Los efectos de escena requieren un objeto.")
        for key, (lo, hi) in {"brightness": (-1, 1), "contrast": (.1, 3), "saturation": (0, 3)}.items():
            if key in scene.get("effects", {}):
                finite_number(scene["effects"][key], key, lo, hi)
        for key in ("keyframes", "overlays"):
            if not isinstance(scene.get(key, []), list) or any(not isinstance(item, dict) for item in scene.get(key, [])):
                raise StudioError(f"{key} requiere una lista de objetos.")
        if not isinstance(scene.get("decision", {}), dict):
            raise StudioError("La decisión de escena requiere un objeto.")
        if not isinstance(scene.get("decision", {}).get("evidence", []), list):
            raise StudioError("La evidencia de escena requiere una lista de rutas.")
        for frame in scene.get("keyframes", []):
            for key, lo, hi in (("time", 0, end - start), ("x", -1, 1), ("y", -1, 1), ("scale", .25, 3), ("opacity", 0, 1)):
                if key in frame:
                    finite_number(frame[key], key, lo, hi)
            if scene["type"] in ("presenter", "split"):
                scale = frame.get("scale", 1)
                margin = max(0, (scale - 1) / 2)
                if scale < 1 or abs(frame.get("x", 0)) > margin + .0001 or abs(frame.get("y", 0)) > margin + .0001 or frame.get("opacity", 1) < 1:
                    raise StudioError("Los keyframes del presentador no pueden revelar relleno artificial ni reducir su opacidad.")
        if scene.get("transition_asset_id"):
            finite_number(scene.get("transition_duration", .5), "duración burn", .3, 1)
            finite_number(scene.get("transition_source_in", 0), "entrada burn", 0, 86400)
        overlays = scene.get("overlays", [])
        if not isinstance(overlays, list) or len(overlays) > 8:
            raise StudioError("Cada escena admite hasta ocho capas visuales.")
        ids = set()
        for layer in overlays:
            if not isinstance(layer, dict) or not isinstance(layer.get("id"), str) or not layer["id"] or layer["id"] in ids:
                raise StudioError("Las capas requieren objetos con IDs únicos.")
            ids.add(layer["id"])
            layer_start = finite_number(layer.get("start", 0), "inicio de capa", 0, end - start)
            layer_end = finite_number(layer.get("end", end - start), "fin de capa", 0, end - start)
            if layer_end <= layer_start:
                raise StudioError("El fin de capa debe ser posterior al inicio.")
            finite_number(layer.get("source_in", 0), "entrada de recurso capa", 0, 86400)
            for key in ("x", "y"):
                finite_number(layer.get(key, 0), f"posición {key} capa", 0, 1)
            for key in ("width", "height"):
                finite_number(layer.get(key, .5), f"tamaño {key} capa", .01, 1)
            if layer.get("x", 0) + layer.get("width", .5) > 1.00001 or layer.get("y", 0) + layer.get("height", .5) > 1.00001:
                raise StudioError("La caja base de una capa debe quedar dentro del lienzo; anima salidas mediante keyframes.")
            finite_number(layer.get("opacity", 1), "opacidad capa", 0, 1)
            if layer.get("blend", "normal") not in ("normal", "screen"):
                raise StudioError("Modo de mezcla de capa no admitido.")
            if not isinstance(layer.get("decision", {}), dict) or not isinstance(layer.get("keyframes", []), list) or any(not isinstance(k, dict) for k in layer.get("keyframes", [])):
                raise StudioError("Las decisiones y keyframes de capa requieren objetos.")
            if not isinstance(layer.get("decision", {}).get("evidence", []), list):
                raise StudioError("La evidencia de capa requiere una lista de rutas.")
            for keyframe in layer.get("keyframes", []):
                for key, lo, hi in (("time", 0, layer_end - layer_start), ("x", -1, 1), ("y", -1, 1), ("scale", .25, 3), ("opacity", 0, 1)):
                    if key in keyframe:
                        finite_number(keyframe[key], f"{key} de keyframe capa", lo, hi)
    for track in p.get("audio", []):
        finite_number(track.get("start", 0), "inicio audio", 0, 86400)
        finite_number(track.get("end", 10), "fin audio", 0, 86400)
        finite_number(track.get("source_in", 0), "entrada audio", 0, 86400)
        finite_number(track.get("gain_db", -18), "ganancia audio", -60, 12)
        if track.get("end", 10) <= track.get("start", 0):
            raise StudioError("El fin del audio debe ser posterior al inicio.")
        if not isinstance(track.get("asset_id"), str) or track.get("role") not in ("music", "sfx"):
            raise StudioError("Rol de audio no admitido.")
        if track.get("is_riser"):
            finite_number(track.get("impact_at"), "culminación del riser", 2, 6)
    for a in p.get("assets", []):
        if not isinstance(a.get("id"), str):
            raise StudioError("Cada recurso requiere un ID de texto.")
        if not isinstance(a.get("metadata", {}), dict) or not isinstance(a.get("verification", {}), dict):
            raise StudioError("Metadata y verificación de recursos requieren objetos.")
        registered = asset(a.get("id"))
        for key in ("path", "sha256", "md5", "size", "duration", "probe", "kind", "font_info"):
            if a.get(key) != registered.get(key):
                raise StudioError("Los datos técnicos canónicos de un recurso no se pueden alterar.", 403)
        for key in ("source", "provenance", "declaration_original", "font_notice"):
            if registered.get("metadata", {}).get(key) != a.get("metadata", {}).get(key):
                raise StudioError("La procedencia canónica de un recurso no se puede alterar.", 403)
    from .fonts import font_assets
    font_assets(p)
    transcript = p.get("transcript", {})
    for key in ("words", "segments"):
        items = transcript.get(key, [])
        if not isinstance(items, list) or len(items) > 100000:
            raise StudioError("Transcripción inválida o demasiado larga.")
        for item in items:
            if not isinstance(item, dict):
                raise StudioError("Cada unidad de transcripción requiere un objeto.")
            start = finite_number(item.get("start"), "inicio de transcripción", 0, 86400)
            end = finite_number(item.get("end"), "fin de transcripción", 0, 86400)
            if end <= start:
                raise StudioError("El fin de transcripción debe ser posterior al inicio.")
            if not isinstance(item.get("word" if key == "words" else "text"), str):
                raise StudioError("La transcripción requiere texto real.")
    for path in p.get("fonts", {}).values():
        if path:
            if not isinstance(path, str):
                raise StudioError("Las rutas de fuentes requieren texto.")
            font_path(path)
    from .scene_ir import validate_brand_media
    validate_brand_media(p, editable_only=True)


def engine_fingerprints():
    # Read our source directly; runtime/project JSON cannot forge these hashes.
    return {path.name: digest(path) for path in sorted(Path(__file__).resolve().parent.glob("*.py"))}


def editorial_digest(p):
    selected = {key: p.get(key) for key in ("source", "settings", "style", "fonts", "timeline", "transcript", "audio", "manual", "reference_review", "library_searches", "skills_applied", "mode", "scene_ir", "pending_brand_references")}
    selected["engine_code"] = engine_fingerprints()
    selected["manual_live"] = manual_fingerprints()
    if isinstance(p.get("skills_applied"), dict):
        from .skills import inventory
        source = inventory()
        selected["skill_sources_live"] = {
            "skills": [{key: item.get(key) for key in ("name", "path", "sha256", "tree_sha256", "available")} for item in source["skills"]],
            "references": [{key: item.get(key) for key in ("path", "sha256", "available")} for item in source["references"]],
        }
    selected["assets"] = [{"id": a["id"], "sha256": content_hash(a["path"]), "verification": a.get("verification"), "metadata": a.get("metadata")} for a in p.get("assets", [])]
    selected["font_content"] = {key: content_hash(path) if path and confined(path).is_file() else "missing" for key, path in p.get("fonts", {}).items()}
    return hashlib.sha256(json.dumps(selected, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def save_project(project_id, incoming, expected=None, action="edited"):
    with LOCK:
        if not isinstance(incoming, dict):
            raise StudioError("El proyecto requiere un objeto JSON.")
        old = get_project(project_id)
        expected = incoming.get("revision") if expected is None else expected
        if expected != old["revision"]:
            raise StudioError("El proyecto cambió en otra ventana o tarea. Recarga antes de guardar.", 409, {"revision": old["revision"]})
        p = copy.deepcopy(incoming)
        p.pop("approval_current", None)
        p.pop('brand_references_state', None)
        p.update(id=old["id"], created_at=old["created_at"], revision=old["revision"] + 1, updated_at=now())
        if WORKSPACE_MODE and action not in ("branding_applied", "branding_bundle_imported"):
            p.setdefault("style", {})["branding"] = copy.deepcopy(old.get("style", {}).get("branding"))
            p["fonts"] = copy.deepcopy(old["fonts"])
        if WORKSPACE_MODE:
            canonical = {a["id"]: a for a in assets()}
            attached = p.get("assets", [])
            if not isinstance(attached, list) or any(not isinstance(a, dict) or a.get("id") not in canonical for a in attached):
                raise StudioError("Adjunta únicamente recursos canónicos de tu espacio privado.", 403)
            if len({a["id"] for a in attached}) != len(attached):
                raise StudioError("Los recursos adjuntos requieren IDs únicos.")
            p["assets"] = [copy.deepcopy(canonical[a["id"]]) for a in attached]
            from .branding import validate_project_binding
            validate_project_binding(p, ROOT)
        # Review and render receipts only change through their dedicated endpoints.
        if action == "edited":
            p["renders"] = old.get("renders", [])
            p["review"] = old.get("review", {})
            p["approved_export"] = old.get("approved_export")
            for protected in ("design_snapshots", "design_reviews", "tracking", "mode", "scene_ir", "automation", "pipeline", "pending_brand_references"):
                if protected in old:
                    p[protected] = copy.deepcopy(old[protected])
                else:
                    p.pop(protected, None)
            p.pop("full_authorization", None)
        validate_shape(p)
        if p.get("mode") == "scene_ir_component":
            from .scene_ir import validate_editable_component
            validate_editable_component(p)
        duplicate = source_project(p.get("source"), excluding=project_id, drive_id=p.get("drive_id"))
        if duplicate:
            raise StudioError("Este crudo ya tiene un proyecto canónico; abre su editable existente.", 409,
                              {"project_id": duplicate["id"], "name": duplicate["name"]})
        p["fonts"] = {k: relative(confined(v)) for k, v in p.get("fonts", {}).items() if v}
        if editorial_digest(p) != editorial_digest(old) and action not in ("reviewed", "authorized"):
            p["review"] = {}
            p.pop("full_authorization", None)
        p["history"] = (old.get("history", []) + [{"at": now(), "action": action}])[-200:]
        p["gates"] = validate_project(p)
        atomic_json(project_path(project_id), p)
        return get_project(project_id)


def attach_asset(project_id, asset_id, source=False):
    with LOCK:
        p = get_project(project_id)
        a = asset(asset_id)
        if a["id"] not in {item["id"] for item in p["assets"]}:
            p["assets"].append(a)
        if source:
            if a.get("kind") == "image" or not any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in a.get("probe", {}).get("streams", [])):
                raise StudioError("El crudo requiere una pista de video.")
            duplicate = source_project(asset_id, excluding=project_id)
            if duplicate:
                if not p.get("source") and not p.get("timeline") and not p.get("audio") and not p.get("transcript", {}).get("words") and not p.get("transcript", {}).get("segments"):
                    return duplicate
                raise StudioError("Este crudo ya tiene un proyecto canónico; se conservan tus cambios y el editable existente.", 409,
                                  {"project_id": duplicate["id"], "name": duplicate["name"]})
            if p.get("source") != asset_id:
                p.update(source=asset_id, timeline=[], transcript={"words": [], "segments": [], "status": "pending"}, reference_review={})
                p.pop("pending_brand_references", None)
        return save_project(project_id, p, action="asset_attached")


def production_motion_errors(p):
    errors = []
    for scene in p.get("timeline", []):
        if scene.get("type") == "split" and not scene.get("asset_id") and not scene.get("motion_design"):
            errors.append(f"{scene.get('id')}: el split de producción requiere un recurso superior real inspeccionado; su relleno raster solo está disponible como prueba técnica.")
    if p.get("settings", {}).get("engine", "native") != "hyperframes":
        errors.append("La producción ASCENDIA requiere HyperFrames/GSAP verificado; Pillow/FFmpeg permite exportación técnica sin equivalencia editorial. La arquitectura del padre ya está comprobada: no repetirla.")
    else:
        from .hyperframes import availability
        if not availability(ROOT).get("verified_execution"):
            errors.append("Falta comprobación vigente de ejecución real del adaptador HyperFrames/GSAP propio.")
    from .design_review import production_errors
    errors.extend(production_errors(p))
    return errors


def approval_is_current(p):
    """Read-only status for every client; cannot be asserted by editable JSON."""
    if p.get("mode") == "scene_ir_component":
        return False
    review = p.get("review", {})
    preview = {**p, "timeline": [s for s in p.get("timeline", []) if s.get("start", 0) < 10]}
    if not isinstance(review, dict) or review.get("approved_preview") is not True or production_motion_errors(preview):
        return False
    try:
        receipt = p.get("renders", [])[-1] if p.get("renders") else {}
        if receipt.get("mode") in ("technical_library", "ivan_draft_preview") or receipt.get("technical_demo") is True:
            return False
        if review.get("manual") != manual_fingerprints() or review.get("editorial_digest") != editorial_digest(p):
            return False
        if receipt.get("sha256") != review.get("render_sha256") or content_hash(receipt.get("path", "")) != review.get("render_sha256"):
            return False
        approved = p.get("approved_export", {})
        if not approved or content_hash(approved.get("path", "")) != review.get("render_sha256"):
            return False
        return validate_project(p, strict=True)["valid"]
    except (StudioError, OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def validate_project(p, seconds=10, strict=False):
    finite_number(seconds, "duración de validación", .05, 7200)
    errors, warnings = [], []
    from .scene_ir import validate_brand_media
    try:
        validate_brand_media(p)
    except StudioError as error:
        errors.append(str(error))
    component = p.get("mode") == "scene_ir_component"
    if component:
        from .scene_ir import validate_compiled_project
        try:
            validate_compiled_project(p)
        except StudioError as error:
            errors.append(str(error))
        if strict:
            errors.append("SceneIR es un componente de biblioteca con QC pendiente; usa render técnico, sin promoción a reel aprobado.")
        warnings.append("SceneIR representa instrucciones declaradas; no acredita generación semántica, fidelidad CLONE ni derechos de recursos.")
    media = {a["id"]: a for a in p.get("assets", [])}
    source = media.get(p.get("source"))
    canonical_catalog = {**media, **{a["id"]: a for a in assets()}}
    if strict and source and source_background_removed(canonical_catalog.get(source["id"], source), canonical_catalog):
        errors.append("La producción ASCENDIA requiere el fondo auténtico del crudo; un derivado con fondo eliminado no puede promoverse como su cámara original.")
    if not source:
        errors.append("Carga y asigna el crudo original.")
    elif source.get("kind") == "image" or not any(s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic") for s in source.get("probe", {}).get("streams", [])):
        errors.append("El crudo requiere una pista de video real; una portada no cuenta como video.")
    if p.get("manual") != manual_fingerprints():
        errors.append("Las instrucciones cambiaron: vuelve a leerlas y actualizar sus huellas antes de renderizar.")
    if any(v.get("missing") for v in manual_fingerprints().values()):
        errors.append("Falta uno de los documentos canónicos obligatorios del manual.")
    for a in media.values():
        try:
            if content_hash(a["path"]) != a["sha256"]:
                errors.append(f"{a['name']}: su contenido cambió; importa el archivo actualizado y repite la revisión.")
        except StudioError as error:
            errors.append(str(error))
    for key, label in (("primary", "Sequel Sans Bold Disp"), ("accent", "Scholar Italic")):
        try:
            path = confined(p.get("fonts", {}).get(key, ""), must_exist=True)
            from PIL import ImageFont
            family = ImageFont.truetype(str(path), 24).getname()
            valid_font = family[0].lower() == "sequel sans" and family[1].lower() == "bold disp" if key == "primary" else family[0].lower() == "scholar" and family[1].lower() == "italic"
            if WORKSPACE_MODE:
                from .branding import validate_project_binding
                profile = validate_project_binding(p, ROOT)
                face = profile["fonts"][key]
                from .fonts import inspect_font
                actual = inspect_font(path, ROOT)
                valid_font = actual["sha256"] == face["sha256"] and actual["family"] == face["family"] and actual["style"] == face["style"]
                label = face["family"] + " " + face["style"]
            if not valid_font:
                errors.append(f"El archivo de {label} no corresponde a la familia obligatoria.")
        except (StudioError, OSError):
            errors.append(f"Falta la fuente auténtica {label}.")
    scenes = sorted((s for s in p.get("timeline", []) if s.get("start", 0) < seconds), key=lambda s: s["start"])
    limit = min(seconds, float(source.get("duration", seconds))) if source else seconds
    if component and p.get("timeline"):
        limit = min(limit, float(p["timeline"][-1]["end"]))
    last, run_start, max_run, presenter_total = 0, None, 0, 0
    for s in scenes:
        start, end = s["start"], min(s["end"], limit)
        if start > last + .035:
            errors.append(f"Hueco en cronología: {last:.2f}–{start:.2f} s.")
        if start < last - .035:
            errors.append(f"Escenas solapadas en {start:.2f} s.")
        last = max(last, end)
        visible = s["type"] in ("presenter", "split")
        if visible:
            if run_start is None:
                run_start = start
            presenter_total += max(0, end - start)
            max_run = max(max_run, end - run_start)
        else:
            run_start = None
        if s["type"] == "broll" or (s["type"] == "split" and s.get("asset_id")):
            a = media.get(s.get("asset_id"))
            if source_related(a, source, canonical_catalog):
                errors.append(f"{s['id']}: el crudo del presentador no puede ocultarse como b-roll ni duplicarse en split.")
            if not a:
                errors.append(f"{s['id']}: falta el recurso seleccionado.")
            else:
                entry = s.get("broll_in", 0) if s["type"] == "split" else s.get("source_in", 0)
                if entry + end - start > a.get("duration", 0) + .05:
                    errors.append(f"{s['id']}: el tramo supera la duración del recurso.")
                if strict and (not a.get("verification", {}).get("visual") or not a.get("metadata", {}).get("content")):
                    errors.append(f"{s['id']}: recurso sin inspección visual documentada.")
            timed_text = any(w.get("start", 0) < end and w.get("end", 0) > max(start, POLICY["hook_seconds"]) for w in p.get("transcript", {}).get("words", []))
            if not s.get("subtitle") and not s.get("title") and not s.get("text_pause_reason") and not timed_text:
                errors.append(f"{s['id']}: b-roll sin representación textual ni pausa justificada.")
        if start < POLICY["hook_seconds"] and s.get("automatic_hook_captions"):
            errors.append("El hook no admite transcripción automática palabra por palabra.")
        if visible and not s.get("chin_reviewed"):
            warnings.append(f"{s['id']}: ajusta y revisa barbilla/rostro en el encuadre real.")
        color = s.get("text_color", "").lower()
        red_color = color in ("red", "#ff0000", "#ef4444", "#ff4d58", "#ff4757", "#e53935", "#b91c1c")
        if re.fullmatch(r"#[0-9a-f]{6}", color):
            r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
            red_color = r > 80 and r > g * 1.4 and r > b * 1.4
        if (s.get("semantic_red") or red_color) and not (s.get("red_reason") or s.get("color_reason")):
            errors.append(f"{s['id']}: rojo sin intención semántica documentada.")
        if strict:
            decision = s.get("decision", {})
            if not decision.get("search") or not decision.get("reason"):
                errors.append(f"{s['id']}: falta búsqueda contextual y motivo de selección.")
            if not decision.get("evidence"):
                errors.append(f"{s['id']}: falta evidencia de selección o descarte de recursos.")
            else:
                for evidence in decision["evidence"]:
                    try:
                        confined(evidence, must_exist=True)
                    except (StudioError, TypeError):
                        errors.append(f"{s['id']}: evidencia inexistente o fuera de SOFTWARE.")
        if s.get("transition_asset_id"):
            transition = media.get(s["transition_asset_id"])
            if not transition:
                errors.append(f"{s['id']}: transición sin recurso auténtico.")
            elif source_related(transition, source, canonical_catalog):
                errors.append(f"{s['id']}: el crudo o sus derivados no pueden ocultarse en una transición.")
            elif strict and (not transition.get("verification", {}).get("visual") or not transition.get("metadata", {}).get("content")):
                errors.append(f"{s['id']}: transición sin revisión visual documentada.")
            elif s.get("transition_source_in", 0) + s.get("transition_duration", .5) > transition.get("duration", 0) + .05:
                errors.append(f"{s['id']}: tramo burn supera el recurso.")
        for layer in s.get("overlays", []):
            span = min(layer.get("end", s["end"] - s["start"]), end - s["start"]) - layer.get("start", 0)
            if span <= 0:
                continue
            a = media.get(layer.get("asset_id"))
            if not a:
                errors.append(f"{s['id']}: una capa referencia un recurso inexistente.")
            elif source_related(a, source, canonical_catalog):
                errors.append(f"{s['id']}: no se puede ocultar presencia del presentador en una capa.")
            else:
                if a.get("kind") != "image" and span > 0 and layer.get("source_in", 0) + span > a.get("duration", 0) + .05:
                    errors.append(f"{s['id']}: capa solicita un tramo superior a la duración del recurso.")
                if a.get("kind") == "image" and layer.get("source_in", 0) != 0:
                    errors.append(f"{s['id']}: una imagen estática requiere entrada de recurso cero.")
                if strict and (not a.get("verification", {}).get("visual") or not a.get("metadata", {}).get("content")):
                    errors.append(f"{s['id']}: capa sin recurso visto y contenido observado.")
            if strict:
                decision = layer.get("decision", {})
                if not decision.get("search") or not decision.get("reason") or not decision.get("evidence"):
                    errors.append(f"{s['id']}: capa sin búsqueda, motivo y evidencia contextual.")
                for evidence in decision.get("evidence", []):
                    try:
                        confined(evidence, must_exist=True)
                    except (StudioError, TypeError):
                        errors.append(f"{s['id']}: evidencia de capa inválida.")
        for el in (s.get("motion_design") or {}).get("elements", []):
            if strict and not component and el.get("font_asset_id"):
                selected_font = media.get(el["font_asset_id"])
                expected = {content_hash(path) for role in ("primary", "accent")
                            if (path := p.get("fonts", {}).get(role)) and confined(path).is_file()}
                if not selected_font or selected_font.get("sha256") not in expected:
                    errors.append(f"{s['id']}/{el['id']}: ASCENDIA conserva Sequel/Scholar; fuentes adicionales disponibles para composición técnica.")
            colors = [el.get("color", "#ffffff")]
            if el.get("type") == "text":
                text_style = el.get("text_style", {})
                stroke, shadow = text_style.get("stroke", {}), text_style.get("shadow", {})
                if stroke.get("width", 0) > 0:
                    colors.append(stroke.get("color", "#000000"))
                if shadow.get("enabled", True) and shadow.get("opacity", .85) > 0:
                    colors.append(shadow.get("color", "#000000"))
            for color in colors:
                if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                    continue
                r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
                if r > 80 and r > g * 1.4 and r > b * 1.4 and not (el.get("color_reason") or s.get("red_reason") or s.get("color_reason")):
                    errors.append(f"{s['id']}/{el['id']}: rojo sin intención semántica documentada.")
                    break
            if el.get("type") != "media":
                continue
            a = media.get(el.get("asset_id"))
            if not a or a.get("kind") not in ("video", "broll", "image"):
                errors.append(f"{s['id']}/{el['id']}: el elemento requiere imagen o video registrado.")
                continue
            if source_related(a, source, canonical_catalog):
                errors.append(f"{s['id']}/{el['id']}: no se puede ocultar presencia del presentador en motion.")
            span = el.get("end", s["end"] - s["start"]) - el.get("start", 0)
            if a.get("kind") == "image" and el.get("source_in", 0) != 0:
                errors.append(f"{s['id']}/{el['id']}: una imagen requiere entrada cero.")
            elif a.get("kind") != "image" and el.get("source_in", 0) + span > a.get("duration", 0) + .05:
                errors.append(f"{s['id']}/{el['id']}: tramo del elemento supera el medio.")
            if strict and (not a.get("verification", {}).get("visual") or not a.get("metadata", {}).get("content")):
                errors.append(f"{s['id']}/{el['id']}: recurso sin inspección visual y contenido observado.")
    if last < limit - .035:
        errors.append(f"Faltan escenas hasta {limit:.2f} s.")
    if max_run > 3.035:
        errors.append(f"Presencia continua {max_run:.2f} s: supera el máximo de 3 s incluyendo split.")
    if strict and not component:
        errors.extend(production_motion_errors({**p, "timeline": scenes}))
        from .skills import validate_application
        errors.extend(validate_application(p))
        rr = p.get("reference_review", {})
        if p.get("style", {}).get("identity") != "YO" or p.get("style", {}).get("motion_references") != ["CLONE"]:
            errors.append("La política vigente exige YO para identidad y CLONE como referencia exclusiva de motion; relee y actualiza el manual del proyecto.")
        if not rr.get("identity_observations") or not rr.get("evidence"):
            errors.append("Falta análisis visual secuencial de YO y sus evidencias para este encargo.")
        for evidence in rr.get("evidence", []):
            try:
                confined(evidence, must_exist=True)
            except (StudioError, TypeError):
                errors.append("Evidencia de YO inexistente o fuera de SOFTWARE.")
        if rr.get("motion_reference") != "CLONE" or not rr.get("motion_observations") or not rr.get("motion_evidence"):
            errors.append("Falta análisis visual secuencial de CLONE y sus evidencias; AGENT/EDIT son referencias históricas.")
        for evidence in rr.get("motion_evidence", []):
            try:
                confined(evidence, must_exist=True)
            except (StudioError, TypeError):
                errors.append("Evidencia de CLONE inexistente o fuera de SOFTWARE.")
        if not p.get("transcript", {}).get("segments"):
            errors.append("Falta transcripción alineada: importa tiempos reales o ejecuta ASR.")
        if not any(s["type"] == "motion" or (s["type"] == "split" and not s.get("asset_id")) for s in scenes):
            errors.append("La prueba V5 requiere una escena de motion con transformación.")
        risers = [t for t in p.get("audio", []) if t.get("role") == "sfx" and t.get("is_riser")]
        if not any(2 <= t.get("impact_at", -1) <= 6 and t.get("start", 0) <= t.get("impact_at", -1) <= t.get("end", 10) and t.get("visual_event") for t in risers):
            errors.append("Falta riser con culminación 2–6 s y transformación visual documentada.")
        for track in p.get("audio", []):
            a = media.get(track.get("asset_id"))
            if not a or not any(s.get("codec_type") == "audio" for s in a.get("probe", {}).get("streams", [])):
                errors.append("Una capa sonora no contiene audio registrado.")
            elif track.get("source_in", 0) + track.get("end", 10) - track.get("start", 0) > a.get("duration", 0) + .05:
                errors.append("El tramo de una capa sonora supera la duración del recurso.")
    pct = 100 * presenter_total / limit if limit > 0 else 0
    if pct > 20:
        warnings.append(f"Presencia total {pct:.1f} %; V5 prioriza pertinencia, justificar frente al objetivo orientativo.")
    warnings.append("La auditoría técnica no aprueba identidad, pertinencia, movimiento ni escucha perceptiva.")
    return {"valid": not errors, "errors": list(dict.fromkeys(errors)), "warnings": list(dict.fromkeys(warnings)),
            "metrics": {"presenter_seconds": round(presenter_total, 3), "presenter_percent": round(pct, 2), "max_presenter_continuous": round(max_run, 3), "duration": limit}, "strict": strict}


def refresh_manual(project_id, expected_fingerprints=None):
    with LOCK:
        current = manual_fingerprints()
        if expected_fingerprints is not None:
            hashes = {name: info.get("sha256") for name, info in current.items()}
            if expected_fingerprints != hashes:
                raise StudioError("El manual cambió desde que lo abriste; vuelve a leer los documentos vigentes.", 409)
        p = get_project(project_id)
        p["manual"] = current
        p["style"].update(identity=POLICY["identity"], motion_references=copy.deepcopy(POLICY["motion_references"]),
                          technical_preview_seconds=POLICY["technical_preview_seconds"],
                          current_production_phase=POLICY["current_production_phase"],
                          parent_creative_scope=POLICY["parent_creative_scope"], parent_integration=POLICY["parent_integration"],
                          library_render=POLICY["library_render"], library_semantics=POLICY["library_semantics"],
                          clone_design_interval=copy.deepcopy(POLICY["clone_design_interval"]),
                          clone_static_reference_time=POLICY["clone_static_reference_time"],
                          clone_static_iteration=POLICY["clone_static_iteration"],
                          parent_static_design_approval=POLICY["parent_static_design_approval"],
                          design_before_animation=True, parent_architecture=POLICY["parent_architecture"])
        if WORKSPACE_MODE:
            p["style"].update(current_production_phase="ivan_multiservice", parent_creative_scope="independent_read_only_source", parent_integration="YO_plus_CLONE_own_branding")
        result = save_project(project_id, p, action="manual_refreshed_after_reading")
        if manual_fingerprints() != current:
            raise StudioError("El manual cambió durante la lectura; vuelve a abrirlo y registrar la revisión.", 409)
        return result


def record_review(project_id, data):
    with LOCK:
        p = get_project(project_id)
        receipt = p.get("renders", [])[-1] if p.get("renders") else None
        if not receipt or receipt.get("editorial_digest") != editorial_digest(p):
            raise StudioError("Renderiza la cronología vigente antes de revisar.", 409)
        path = confined(receipt.get("path", ""), must_exist=True)
        technical = receipt.get("mode") in ("technical_library", "ivan_draft_preview") or receipt.get("technical_demo") is True
        if data.get("approve_preview") and technical:
            raise StudioError("Un exportado técnico del editor no puede aprobarse como prueba narrativa ASCENDIA.", 409)
        if content_hash(path) != receipt.get("sha256"):
            raise StudioError("El exportado cambió: renderiza y revisa de nuevo.", 409)
        source = next((a for a in p["assets"] if a["id"] == p["source"]), {})
        minimum_duration = .05 if technical else min(10, source.get("duration", 10)) - .05
        if receipt.get("duration", 0) < minimum_duration or receipt.get("duration", 0) > 10.05:
            raise StudioError("La aprobación inicial corresponde a la prueba de los primeros diez segundos.", 409)
        check = validate_project(p, strict=True)
        if data.get("approve_preview") and not check["valid"]:
            raise StudioError("La prueba no cumple los controles previos vigentes.", 409, check)
        checks = ["visual", "audio", "sync", "spelling", "resources", "movement", "identity", "safe_zones"]
        if data.get("approve_preview") and (not all(data.get(c) is True for c in checks) or not str(data.get("reviewer", "")).strip() or not str(data.get("notes", "")).strip()):
            raise StudioError("La aprobación requiere revisión visual, audio escuchado, sincronía, ortografía, recursos, movimiento, identidad YO, revisor y notas.")
        review = {c: data.get(c) is True for c in checks}
        review.update(at=now(), reviewer=str(data.get("reviewer", ""))[:200], notes=str(data.get("notes", ""))[:10000],
                      approved_preview=data.get("approve_preview") is True, render_sha256=receipt["sha256"], editorial_digest=editorial_digest(p), manual=manual_fingerprints())
        p["review"] = review
        p.pop("full_authorization", None)
        if review["approved_preview"]:
            approved = confined(f"projects/{project_id}/approved_preview.mp4")
            if path != approved:
                temp = confined(f".estado/tmp/{uid('approved_')}.mp4")
                try:
                    shutil.copy2(path, temp)
                    if digest(temp) != receipt["sha256"]:
                        raise StudioError("El exportado cambió durante la aprobación; vuelve a revisarlo.", 409)
                    os.replace(temp, approved)
                finally:
                    temp.unlink(missing_ok=True)
            p["approved_export"] = {**receipt, "path": relative(approved), "url": "/api/files/" + relative(approved), "approved": True, "review": review}
        return save_project(project_id, p, action="reviewed")
