from __future__ import annotations

import importlib.util
import hashlib
import hmac
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath

from . import __version__
from .core import ROOT, StudioError, LOCK, POLICY, TEMPLATES, assets, asset, register_asset, confined, project_list, create_project, get_project, save_project, attach_asset, validate_project, record_review, refresh_manual, manual_fingerprints, fonts, uid, now, editorial_digest, setup, state, approval_is_current
from .jobs import list_jobs, get_job, submit, submit_media, cancel_job, start_worker, export_bundle, tasks, create_tasks, claim_task, finish_task, release_task


def capabilities():
    from .core import WORKSPACE_MODE
    from .tracking import capability
    from .hyperframes import availability
    from .segmentation import capability as segmentation_capability
    tracking_status = capability(ROOT)
    hf_status = availability(ROOT)
    segmentation_status = segmentation_capability(ROOT)
    from .cloud_storage import status as cloud_status
    from .runtime import CODE_ROOT
    return {"import": {"available": bool(shutil.which("ffprobe")), "formats": "Contenedores/codecs decodificables por FFmpeg local; valida cada archivo."},
            "render": {"available": bool(shutil.which("ffmpeg")), "engine": "Pillow/FFmpeg o HyperFrames/GSAP", "engines": ["native", "hyperframes"], "device": "cpu", "threads": 2, "technical_only": not hf_status.get("verified_execution"), "narrative_requires": "current_design_approval_skills_resources_and_editorial_evidence", "max_seconds": 10, "long_render": "requires_current_approved_preview_and_explicit_authorization", "no_editorial_approval": True,
                       "manual_full_draft": {"available": WORKSPACE_MODE, "max_seconds": 600, "editorial_approved": False}},
            "asr": {"available": importlib.util.find_spec("faster_whisper") is not None, "engine": "faster-whisper", "device": "cpu", "model_download": "on_request_into_SOFTWARE"},
            "timeline": {"available": True, "editable": True, "versioned_revision": True},
            "cloud_storage": {**cloud_status(CODE_ROOT), "project_backup_jobs": WORKSPACE_MODE},
            "motion": {"available": True, "templates": [t["id"] for t in TEMPLATES], "custom_design": {"editable": True, "max_elements": 64, "paths": True, "animated_masks": True, "curves": True}, "layers": {"editable": True, "max_per_scene": 8, "alpha": True, "keyframes": True, "blends": ["normal", "screen"]}},
            "browser_previews": {"available": True, "originals_preserved": True, "formats": ["H.264/AAC MP4", "VP9 alpha/Opus WebM"]},
            "audio": {"available": True, "track_selection": {"available": True, "index": "global_ffprobe_stream", "activity_is_voice_verification": False}, "features": ["waveform", "silence_analysis", "voice_preservation", "ducking", "sfx", "normalization", "integrated_lufs", "true_peak_audit"]},
            "media_tools": {"available": True, "operations": ["probe", "scene_detect", "loudness_analysis", "extract_audio", "denoise_audio", "normalize_audio", "proxy_video", "speed_video", "reverse_video", "chromakey_video", "remove_background_video"], "destructive": False},
            "editable_bundles": {"available": True, "import": True, "export": True, "checks": ["paths", "hashes", "fonts", "deduplication", "reinspection"]},
            "mcp": {"available": True, "transport": ["stdio", "authenticated_http_json"], "public_shell": False},
            "ivan_automation": {"available": True, "style": "ivan_yo_clone_own_branding", "direction": ["own_api_key", "external_mcp_agent"], "preview_seconds": 10, "editorial_approved": False, "live_provider_test_required": True},
            "reel_pipeline": {"available": True, "schema": "ascendia.pipeline/1", "max_source_seconds": 600,
                              "channels": ["api", "external"], "automatic_editorial_approval": False, "resumable": True},
            "brand_assets": {"available": True, "observations_required": True, "official_fetch": True,
                             "svg_render_supported": False, "automatic_publication_permission": False},
            "agents": {"available": True, "execution": "external_clients_claim_tasks", "auto_editorial_approval": False},
            "tracking": tracking_status, "rotoscoping": {"available": False}, "generative_fill": {"available": False},
            "segmentation": segmentation_status,
            "adobe_capcut_parity": {"available": False}, "drive_publish": {"available": False},
            "hyperframes_adapter": {**hf_status, "license_note": "GSAP conserva su licencia propia, distinta de MIT."}, "blender_adapter": {"available": False},
            "static_design": {"available": True, "explicit_approval": True, "auto_approval": False},
            "font_library": {"available": True, "formats": ["ttf", "otf"], "canonical_assets": True, "automatic_substitution": False},
            "text_typography": {"available": all(importlib.util.find_spec(name) is not None for name in ("regex", "fontTools")),
                                "scope": "custom_design", "shared_layout": True, "graphemes": True,
                                "styles": ["alignment", "line_height", "letter_spacing", "stroke", "shadow"],
                                "presets": ["none", "fade_up", "slide", "pop", "wipe", "typewriter", "word_reveal"],
                                "clone_fidelity_verified": False},
            "scene_ir": {"available": True, "schema": "ascendia.sceneir/1", "data_only": True, "editable": True,
                         "semantic_generator": False, "clone_fidelity_verified": False, "library_render": "automatic_technical_up_to_10s_qc_pending"},
            "skills_application": {"available": True, "execution": "read_only_inventory_and_per_project_evidence", "reading_not_automatic": True}}


def canonical_media_path(item):
    """Expose canonical asset bytes, never an alias into the private store."""
    from .core import content_hash
    relative = item.get('path') if isinstance(item, dict) else None
    if not isinstance(relative, str) or '\\' in relative or '%' in relative or any(part in ('', '.', '..') for part in relative.split('/')):
        raise StudioError('Ruta de medio canónico no válida.', 403)
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.parts[0] != 'assets':
        raise StudioError('El medio debe pertenecer a la biblioteca canónica.', 403)
    lexical = ROOT / relative
    for candidate in [lexical, *lexical.parents]:
        if candidate == ROOT.parent:
            break
        if candidate.is_symlink():
            raise StudioError('El medio canónico no admite enlaces.', 403)
    path = confined(relative, must_exist=True)
    if path != lexical or not path.is_file() or path.stat().st_nlink != 1:
        raise StudioError('El medio canónico no admite alias ni enlaces.', 403)
    if content_hash(path) != item.get('sha256'):
        raise StudioError('El medio cambió; revisa su integridad antes de compartirlo.', 409)
    return path


def text_layout(data):
    """Read-only layout of one draft text element, using local canonical fonts."""
    from . import core, design, typography
    from .fonts import validate_asset_font
    from .jobs import cpu_slot
    if not isinstance(data, dict) or set(data) != {"project_id", "element", "scene_duration", "width", "height"}:
        raise StudioError("El layout requiere proyecto, elemento, duración y tamaño de vista.")
    if not isinstance(data["project_id"], str):
        raise StudioError("El proyecto del layout requiere un ID literal.")
    width = core.finite_number(data["width"], "ancho de vista tipográfica", 64, 1080)
    height = core.finite_number(data["height"], "alto de vista tipográfica", 64, 1920)
    if int(width) != width or int(height) != height:
        raise StudioError("El tamaño de vista requiere píxeles enteros.")
    duration = core.finite_number(data["scene_duration"], "duración de vista tipográfica", .01, 7200)
    element = data["element"]
    if not isinstance(element, dict) or element.get("type") != "text":
        raise StudioError("El layout admite un único elemento de texto.")
    project = get_project(data["project_id"])
    scene = {"id": "typography_preview", "type": "motion", "template": "custom", "start": 0, "end": duration,
             "motion_design": {"elements": [element]}}
    design.validate_design(scene, (width, height))
    selected = {}
    with cpu_slot():
        reference = element.get("font_asset_id")
        if reference is not None:
            registered = asset(reference)
            validated = validate_asset_font(registered)
            selected[reference] = {**registered, "path": validated["path"]}
        layout = typography.layout_element(element, (int(width), int(height)), project["fonts"], selected, root=ROOT)
        resolved = typography.resolve_font(element, project["fonts"], selected, root=ROOT)
        # The public response contains measured data, never an executable font path.
        from .fonts import inspect_font
        metadata = inspect_font(resolved["path"])
    return {"layout": layout, "font": {k: metadata[k] for k in ("family", "style", "sha256")},
            "project_revision": project["revision"], "persisted": False, "approved": False}


def external_activity():
    from .core import WORKSPACE_MODE
    if WORKSPACE_MODE:
        return []
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cwd = Path(os.readlink(entry / "cwd"))
            if not cwd.is_relative_to(ROOT.parent) or cwd.is_relative_to(ROOT):
                continue
            command = (entry / "comm").read_text().strip()
            if command in ("codex", "ffmpeg", "python3", "node"):
                found.append({"pid": int(entry.name), "process": command, "workspace": "IVAN (solo lectura)", "interference": False})
        except (OSError, ValueError):
            pass
    return found


def status():
    from .jobs import engine_fingerprints, LOADED_ENGINE_FINGERPRINTS
    from .core import WORKSPACE_MODE
    effective_policy = dict(POLICY)
    if WORKSPACE_MODE:
        from .branding import get_branding
        branding_snapshot = get_branding(ROOT)["snapshot"]
        effective_policy.update(current_production_phase="ivan_multiservice", parent_creative_scope="independent_read_only_source", parent_integration="YO_plus_CLONE_own_branding",
                                branding=branding_snapshot, manual_scope="complete_software_style_profile",
                                required_fonts=[face["family"]+" "+face["style"] for face in branding_snapshot.get("fonts",{}).values()],
                                original_reference_fonts=branding_snapshot.get("original_reference_fonts",["Sequel Sans Bold Disp","Scholar Italic"]))
    return {"app": "Ascendia Studio", "version": __version__, "scope": str(ROOT), "capabilities": capabilities(),
            "restart_required": engine_fingerprints() != LOADED_ENGINE_FINGERPRINTS,
            "policy": effective_policy, "manual": manual_fingerprints(), "active_external": external_activity(),
            "limitations": ["No equivale a toda la suite Adobe/CapCut Pro.", "La disponibilidad de un motor no aprueba fidelidad CLONE/YO; se exige diseño vigente aprobado, skills y revisión perceptiva.", "Los borradores automáticos requieren dirección contextual y revisión explícita.", "La producción activa de IVAN permanece independiente."]}


def authorize_full(project_id, data):
    with LOCK:
        p = get_project(project_id)
        review = p.get("review", {})
        if data.get("authorized") is not True or not str(data.get("notes", "")).strip():
            raise StudioError("La autorización posterior debe ser explícita e incluir la indicación del usuario.")
        if not review.get("approved_preview") or review.get("editorial_digest") != editorial_digest(p) or review.get("manual") != manual_fingerprints():
            raise StudioError("Primero aprueba la prueba vigente tras revisión completa.", 409)
        approved = p.get("approved_export")
        from .core import content_hash
        if not approved or content_hash(approved["path"]) != review.get("render_sha256"):
            raise StudioError("La prueba aprobada falta o cambió; debe revisarse de nuevo.", 409)
        if not approval_is_current(p):
            raise StudioError("Primero aprueba la prueba vigente tras revisión completa.", 409)
        p["full_authorization"] = {"authorized": True, "at": now(), "notes": str(data["notes"])[:10000], "editorial_digest": editorial_digest(p)}
        return save_project(project_id, p, action="authorized")


class Handler(BaseHTTPRequestHandler):
    server_version = "AscendiaStudio/" + __version__
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, BrokenPipeError, TimeoutError):
            # Browsers cancel earlier Range requests during a normal seek.
            pass

    def log_message(self, fmt, *args):
        # No raw bodies, uploaded paths, credentials, or request headers in logs.
        pass

    def do_HEAD(self):
        self.dispatch(head=True)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_PUT(self):
        self.dispatch()

    def do_DELETE(self):
        self.dispatch()

    def guard(self):
        internal_token = os.environ.get("ASCENDIA_BACKEND_TOKEN")
        if internal_token and not hmac.compare_digest(self.headers.get("X-Ascendia-Backend", "").encode("utf-8"), internal_token.encode("ascii")):
            raise StudioError("Este espacio requiere acceso autenticado desde el portal.", 401)
        host = self.headers.get("Host", "")
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in allowed_hosts:
            raise StudioError("Host local inválido.", 403)
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + h for h in allowed_hosts}:
            raise StudioError("Origen no autorizado para el editor local.", 403)
        if self.headers.get("Transfer-Encoding"):
            raise StudioError("Transfer-Encoding no admitido; usa Content-Length.", 400)

    def body(self, maximum=10 * 1024 * 1024):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise StudioError("Content-Length inválido.") from None
        if length < 0 or length > maximum:
            raise StudioError("Carga demasiado grande.", 413)
        if not length:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise StudioError("El cuerpo JSON debe ser un objeto.")
            return value
        except (ValueError, UnicodeDecodeError):
            raise StudioError("JSON inválido.") from None

    def json(self, value, code=200, head=False):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.common_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not head:
            self.wfile.write(data)

    def common_headers(self, mime):
        self.send_header("Content-Type", mime)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'")

    def file(self, path, head=False, root=None):
        path = confined(path, root=root, must_exist=True)
        size = path.stat().st_size
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        low, high, code = 0, max(0, size - 1), 200
        header = self.headers.get("Range")
        if header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
            if not match or not any(match.groups()):
                raise StudioError("Range no admitido.", 416)
            start, end = match.groups()
            if not start:
                low = max(0, size - int(end))
            else:
                low = int(start)
            high = min(size - 1, int(end)) if start and end else size - 1
            if low >= size or high < low:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        length = max(0, high - low + 1) if size else 0
        self.send_response(code)
        self.common_headers(mime)
        if path.suffix.lower() in (".zip", ".csv", ".srt", ".vtt") or path.name.endswith("_pending.json"):
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(path.name, safe=""))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {low}-{high}/{size}")
        self.end_headers()
        if not head:
            with path.open("rb") as f:
                f.seek(low)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    def upload(self, bundle=False):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise StudioError("Content-Length inválido.") from None
        if not 0 < length <= 4 * 1024 ** 3:
            raise StudioError("Carga vacía o mayor de 4 GiB.", 413)
        name = Path(urllib.parse.unquote(self.headers.get("X-File-Name", "clip.mp4"))).name
        if len(name) > 240 or "\x00" in name:
            raise StudioError("Nombre de archivo inválido.")
        if not bundle and (Path(name).suffix.lower() in (".ttf", ".otf") or self.headers.get("X-Asset-Kind") == "font"):
            from .fonts import MAX_FONT_BYTES
            if length > MAX_FONT_BYTES:
                raise StudioError("La carga de una fuente admite hasta 16 MiB.", 413)
        temp = confined(".estado/tmp/" + uid("upload_") + Path(name).suffix.lower())
        try:
            with temp.open("wb") as f:
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise StudioError("Carga incompleta.")
                    f.write(chunk)
                    remaining -= len(chunk)
            if bundle:
                from .bundles import import_bundle
                return import_bundle(temp)
            return register_asset(temp, name=name, kind=self.headers.get("X-Asset-Kind"))
        finally:
            temp.unlink(missing_ok=True)

    def dispatch(self, head=False):
        try:
            self.guard()
            parsed = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(parsed.path)
            query = urllib.parse.parse_qs(parsed.query)
            method = "GET" if head else self.command
            if method == "POST" and path == "/api/mcp":
                if not os.environ.get("ASCENDIA_BACKEND_TOKEN"):
                    raise StudioError("El transporte HTTP de agentes requiere un espacio privado autenticado.", 403)
                from .mcp import handle
                value = handle(self.body())
                if value is None:
                    self.send_response(202)
                    self.common_headers("application/octet-stream")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self.json(value)
            if method == "GET" and path == "/api/status":
                return self.json(status(), head=head)
            if method == 'GET' and path == '/api/cloud-storage':
                from .cloud_storage import status as cloud_status
                from .runtime import CODE_ROOT
                from .core import WORKSPACE_MODE
                return self.json({**cloud_status(CODE_ROOT), 'project_backup_jobs': WORKSPACE_MODE}, head=head)
            if method == "GET" and path == "/api/manual":
                from .core import WORKSPACE_MODE
                if WORKSPACE_MODE:
                    from .branding import profile_document
                    return self.json({"documents": [profile_document()], "policy": {"name": "IVAN + branding propio", "style_base": "ivan_yo_clone"}}, head=head)
                fps = manual_fingerprints()
                docs = []
                for name in fps:
                    from .runtime import MANUAL_ROOT
                    source = MANUAL_ROOT / name
                    content = source.read_bytes() if source.is_file() else None
                    docs.append({"name": name, "sha256": hashlib.sha256(content).hexdigest() if content is not None else None,
                                 "content": content.decode("utf-8") if content is not None else "Falta el manual canónico."})
                return self.json({"documents": docs, "policy": POLICY}, head=head)
            if method == "GET" and path == "/api/templates":
                return self.json({"templates": TEMPLATES}, head=head)
            if method == "GET" and path == "/api/automation":
                from .automation import catalog
                return self.json(catalog(), head=head)
            if method == 'GET' and path in ('/api/brand-assets', '/api/brand-assets/origins'):
                from .brand_assets import catalog, origin_catalog
                return self.json(origin_catalog() if path.endswith('/origins') else
                                 catalog(query.get('context', ['private_review'])[0]), head=head)
            if method == 'POST' and path in ('/api/brand-assets/register', '/api/brand-assets/fetch', '/api/brand-assets/resolve'):
                b = self.body(maximum=65536)
                from .brand_assets import register, resolve
                if path.endswith('/register'):
                    if set(b) != {'asset_id', 'options'}:
                        raise StudioError('El registro requiere asset_id y options.')
                    return self.json(register(b['asset_id'], b['options']))
                if path.endswith('/fetch'):
                    if set(b) - {'entity', 'options'} or 'entity' not in b:
                        raise StudioError('La descarga requiere entity y options opcionales.')
                    from .jobs import submit_brand_fetch
                    return self.json(submit_brand_fetch(b['entity'], b.get('options')), 202)
                if set(b) - {'entities', 'context'} or 'entities' not in b:
                    raise StudioError('Resolver requiere entities y context opcional.')
                return self.json(resolve(b['entities'], b.get('context', 'private_review')))
            if method == "GET" and path == "/api/font-library":
                from .fonts import catalog
                return self.json(catalog(), head=head)
            if method == "GET" and path == "/api/text-presets":
                from .typography import catalog
                return self.json(catalog(), head=head)
            if method == "GET" and path == "/api/typography-client.js":
                from .typography import CLIENT_JS
                content = CLIENT_JS.encode("utf-8")
                self.send_response(200)
                self.common_headers("application/javascript; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                if not head:
                    self.wfile.write(content)
                return
            if method == "POST" and path == "/api/text-layout":
                return self.json(text_layout(self.body(maximum=32768)))
            if method == "GET" and path == "/api/scene-ir/schema":
                from .scene_ir import describe_schema
                return self.json(describe_schema(), head=head)
            if method == "POST" and path == "/api/backups":
                b = self.body()
                p = b.get("project")
                if not isinstance(p, dict) or not p.get("id"):
                    raise StudioError("El respaldo requiere un proyecto existente.")
                get_project(p["id"])
                from .core import atomic_json
                rel = f"exports/{p['id']}_pending.json"
                atomic_json(rel, p)
                return self.json({"path": rel, "url": "/api/files/" + rel, "applied": False, "approved": False}, 201)
            if method == "GET" and path == "/api/media-tools":
                from .media_tools import catalog
                return self.json({"operations": catalog()}, head=head)
            if method == "POST" and path == "/api/bundles":
                return self.json(self.upload(bundle=True), 201)
            match = re.fullmatch(r"/api/assets/([a-zA-Z0-9_-]+)/process", path)
            if match and method == "POST":
                b = self.body()
                return self.json(submit_media(match[1], b["operation"], b.get("options", {}), b.get("project_id")), 202)
            match = re.fullmatch(r'/api/assets/(a_[a-zA-Z0-9_-]+)/audio-tracks', path)
            if match and method == 'POST':
                from .jobs import submit_audio_tracks
                return self.json(submit_audio_tracks(match[1], self.body(maximum=8192)), 202)
            match = re.fullmatch(r"/api/assets/(a_[a-zA-Z0-9_-]+)/(review|review-prepare|review-files/[^/]+)", path)
            if match:
                aid, operation = match.groups()
                from .resource_review import current_review, record, evidence_file
                if method == "GET" and operation == "review":
                    return self.json(current_review(asset(aid)), head=head)
                if method == "GET" and operation.startswith("review-files/"):
                    return self.file(evidence_file(aid, operation.split("/", 1)[1]), head=head)
                if method == "POST" and operation == "review":
                    return self.json(record(aid, self.body(maximum=65536)))
                if method == "POST" and operation == "review-prepare":
                    from .jobs import submit_resource_review
                    return self.json(submit_resource_review(aid, self.body(maximum=8192)), 202)
            if path == "/api/assets":
                if method == "GET":
                    return self.json({"assets": assets()}, head=head)
                if method == "POST":
                    return self.json(self.upload(), 201)
            if path == "/api/projects":
                if method == "GET":
                    return self.json({"projects": project_list()}, head=head)
                if method == "POST":
                    b = self.body()
                    return self.json(create_project(b.get("name", "Nuevo reel"), b.get("source"), b.get("drive_id")), 201)
            match = re.fullmatch(r"/api/projects/([a-zA-Z0-9_-]+)(?:/([a-z_-]+))?", path)
            if match:
                pid, operation = match.groups()
                if not operation:
                    if method == "GET":
                        return self.json(get_project(pid), head=head)
                    if method == "PUT":
                        return self.json(save_project(pid, self.body()))
                if method == "GET" and operation == "validate":
                    return self.json(validate_project(get_project(pid), seconds=float(query.get("seconds", [10])[0]), strict=query.get("strict", ["true"])[0] == "true"), head=head)
                if method == 'GET' and operation == 'pipeline':
                    from .pipeline import status as pipeline_status
                    context = query.get('include_context', ['false'])
                    if len(context) != 1 or context[0] not in ('true', 'false'):
                        raise StudioError('include_context requiere true o false.')
                    return self.json(pipeline_status(pid, include_context=context[0] == 'true'), head=head)
                if method == 'GET' and operation == 'cloud-backup':
                    from .jobs import cloud_backup_status
                    return self.json(cloud_backup_status(pid), head=head)
                if method == "GET" and operation == "skills":
                    from .skills import inventory, validate_application
                    p = get_project(pid)
                    return self.json({"inventory": inventory(), "application": p.get("skills_applied"), "errors": validate_application(p)}, head=head)
                if method == "GET" and operation == "tracking":
                    return self.json({"tracking": get_project(pid).get("tracking"), "automatic_application": False}, head=head)
                if method == "GET" and operation == "tracking_proposals":
                    from .tracking_actions import propose_tracking
                    return self.json(propose_tracking(get_project(pid)), head=head)
                if method == "GET" and operation == "designs":
                    p = get_project(pid)
                    from .design_review import production_errors
                    return self.json({"snapshots": p.get("design_snapshots", {}), "reviews": p.get("design_reviews", {}), "errors": production_errors(p)}, head=head)
                if method == "POST":
                    b = self.body()
                    if operation == 'cloud-backup':
                        return self.json(submit(pid, 'cloud_backup', b), 202)
                    if operation in ('pipeline', 'pipeline-resume', 'pipeline-restart'):
                        return self.json(submit(pid, operation.replace('-', '_'), b), 202)
                    if operation == 'pipeline-plan':
                        from .pipeline import submit_external_plan
                        return self.json(submit_external_plan(pid, b))
                    if operation == 'pipeline-cancel':
                        from .pipeline import cancel as cancel_pipeline
                        if set(b) != {'generation'}:
                            raise StudioError('Cancelar requiere generation.')
                        return self.json(cancel_pipeline(pid, b['generation']))
                    if operation == "branding":
                        if not {"expected_revision"} <= set(b) or set(b) - {"expected_revision", "expected_branding_revision"}:
                            raise StudioError("Aplicar la marca requiere expected_revision.")
                        from .branding import apply_project_branding
                        return self.json(apply_project_branding(pid, b["expected_revision"], b.get("expected_branding_revision")))
                    if operation in ("scene_ir_preview", "scene_ir"):
                        allowed = {"document"} if operation == "scene_ir_preview" else {"document", "expected_revision"}
                        if set(b) != allowed:
                            raise StudioError("SceneIR requiere document y, para aplicar, expected_revision, sin campos adicionales.")
                        from .scene_ir_actions import preview, apply
                        return self.json(preview(pid, b["document"]) if operation == "scene_ir_preview" else
                                         apply(pid, b["document"], b["expected_revision"]))
                    if operation == "assets":
                        return self.json(attach_asset(pid, b["asset_id"], b.get("source", False)))
                    if operation in ("analyze", "automate", "auto_ivan", "ivan_prepare", "ivan_apply_plan", "render", "tracking", "design_snapshot"):
                        return self.json(submit(pid, operation, b), 202)
                    if operation == "plan":
                        from .analysis import propose_storyboard
                        p = propose_storyboard(get_project(pid))
                        return self.json(save_project(pid, p, action="storyboard_proposed"))
                    if operation == "review":
                        return self.json(record_review(pid, b))
                    if operation == "design_review":
                        from .design_review import record_review as review_design
                        return self.json(review_design(pid, b))
                    if operation == "authorize":
                        return self.json(authorize_full(pid, b))
                    if operation == "manual":
                        if b.get("read_complete") is not True:
                            raise StudioError("Confirma la lectura completa de los documentos antes de actualizar huellas.")
                        return self.json(refresh_manual(pid, b.get("expected_fingerprints")))
                    if operation == "export":
                        return self.json(export_bundle(pid))
                    if operation == "skills":
                        from .skills import prepare
                        return self.json(prepare(pid))
            if method == "GET" and path == "/api/jobs":
                return self.json({"jobs": list_jobs()}, head=head)
            match = re.fullmatch(r"/api/jobs/([a-zA-Z0-9_-]+)(?:/(cancel))?", path)
            if match:
                jid, op = match.groups()
                if method == "GET" and not op:
                    return self.json(get_job(jid), head=head)
                if method == "POST" and op:
                    self.body()
                    return self.json(cancel_job(jid))
            if path == "/api/workflows" and method == "POST":
                return self.json({"tasks": create_tasks(self.body()["project_id"])}, 201)
            if path == "/api/tasks" and method == "GET":
                return self.json({"tasks": tasks()}, head=head)
            if path == "/api/tasks/claim" and method == "POST":
                b = self.body()
                return self.json(claim_task(b["role"], b["agent"]))
            match = re.fullmatch(r"/api/tasks/([a-zA-Z0-9_-]+)/complete", path)
            if match and method == "POST":
                b = self.body()
                return self.json(finish_task(match[1], b["lease"], b["result"]))
            match = re.fullmatch(r"/api/tasks/([a-zA-Z0-9_-]+)/release", path)
            if match and method == "POST":
                b = self.body()
                return self.json(release_task(match[1], b["lease"]))
            if method == "GET" and path.startswith("/api/media/"):
                return self.file(canonical_media_path(asset(path[len("/api/media/"):])), head)
            match = re.fullmatch(r'/api/font-notices/(a_[A-Za-zA-Z0-9_-]+)', path)
            if match and method == 'GET':
                from .fonts import license_info
                item = asset(match[1])
                if item.get('kind') != 'font':
                    raise StudioError('El aviso requiere una fuente canónica.', 404)
                info = license_info(item)
                if not info.get('notice_path') or not info.get('notice_sha256'):
                    raise StudioError('No hay un aviso tipográfico verificado para este archivo.', 404)
                notice = confined(info['notice_path'], must_exist=True)
                from .core import digest
                if digest(notice) != info['notice_sha256'] or not 1 <= notice.stat().st_size <= 65536:
                    raise StudioError('El aviso tipográfico cambió.', 409)
                return self.file(notice, head)
            if method == "GET" and path.startswith("/api/fonts/"):
                which = path.split("/")[-1]
                if which not in fonts():
                    raise StudioError("Fuente no encontrada.", 404)
                pid = query.get("project_id", [None])[0]
                return self.file(get_project(pid)["fonts"][which] if pid else fonts()[which], head)
            if method == "GET" and path.startswith("/api/files/"):
                rel = path[len("/api/files/"):]
                target = confined(rel, must_exist=True)
                allowed_roots = [confined("assets"), confined("exports"), confined("projects")]
                pending_json = target.is_relative_to(confined("exports")) and target.name.endswith("_pending.json")
                if not any(target.is_relative_to(r) for r in allowed_roots) or (not pending_json and target.suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp", ".zip", ".csv", ".srt", ".vtt"}):
                    raise StudioError("Este archivo no es un entregable público del editor.", 403)
                return self.file(target, head)
            if method == "GET" and path in ("/", "/index.html", "/app.js", "/style.css"):
                from .runtime import CODE_ROOT
                return self.file("web/" + ("index.html" if path == "/" else path[1:]), head, root=CODE_ROOT)
            raise StudioError("Ruta no encontrada.", 404)
        except StudioError as error:
            self.close_connection = True
            self.json({"error": str(error), "details": error.details}, error.status, head)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except (KeyError, ValueError, TypeError, OSError) as error:
            self.close_connection = True
            self.json({"error": str(error)}, 400, head)
        except Exception as error:
            self.close_connection = True
            self.json({"error": "Error interno del editor.", "type": type(error).__name__}, 500, head)


def serve(port=8765):
    if not 1024 <= int(port) <= 65535:
        raise StudioError("Puerto local inválido.")
    setup()
    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    server.daemon_threads = True
    start_worker()
    state(server_url=f"http://127.0.0.1:{port}", server_pid=os.getpid(), stage="editor_ready", limitations=status()["limitations"])
    print(f"Ascendia Studio {__version__} — http://127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
