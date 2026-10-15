from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

from .core import ROOT, StudioError, confined, setup, assets, register_asset, create_project, project_list, get_project, save_project, validate_project, record_review, refresh_manual, read_json, state, attach_asset
from .jobs import list_jobs, get_job, submit, submit_media, execute, export_bundle, create_tasks, tasks, claim_task, finish_task, release_task


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))


def server_url():
    import re
    url = read_json("ESTADO.json", {}).get("server_url", "http://127.0.0.1:8765")
    if not re.fullmatch(r"http://127\.0\.0\.1:\d{4,5}", url):
        return None
    try:
        with urllib.request.urlopen(url + "/api/status", timeout=1) as r:
            info = json.load(r)
        return url if info.get("app") == "Ascendia Studio" and info.get("scope") == str(ROOT) else None
    except (OSError, ValueError):
        return None


def enqueue(project_id, action, options):
    url = server_url()
    if url:
        req = urllib.request.Request(url + f"/api/projects/{project_id}/{action}", json.dumps(options).encode(), {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            info = json.load(error)
            raise StudioError(info.get("error", "Error del servidor"), error.code, info.get("details")) from error
    job = submit(project_id, action, options)
    execute(job["id"])
    result = get_job(job["id"])
    if result["status"] != "completed":
        raise StudioError(result.get("error", result.get("message", "Trabajo fallido")), 409, result)
    return result


def enqueue_media(asset_id, operation, options=None, project_id=None):
    url = server_url()
    if url:
        req = urllib.request.Request(url + f"/api/assets/{asset_id}/process", json.dumps({"operation": operation, "options": options or {}, "project_id": project_id}).encode(), {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            info = json.load(error)
            raise StudioError(info.get("error", "Error del servidor"), error.code, info.get("details")) from error
    job = submit_media(asset_id, operation, options, project_id)
    execute(job["id"])
    result = get_job(job["id"])
    if result["status"] != "completed":
        raise StudioError(result.get("error", "Herramienta fallida"), 409, result)
    return result


def request_job_cancel(job_id):
    # Reject invalid IDs before any request. Use the live server event when present.
    get_job(job_id)
    url = server_url()
    if url:
        req = urllib.request.Request(url + f"/api/jobs/{job_id}/cancel", b"{}", {"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            info = json.load(error)
            raise StudioError(info.get("error", "Error del servidor"), error.code, info.get("details")) from error
    from .jobs import cancel_job
    return cancel_job(job_id)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ascendia Studio — edición local y automatización JSON, confinada en SOFTWARE.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("serve", help="Abrir servidor local")
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("multiservice", help="Portal con registro, marcas y espacios privados por usuario")
    p.add_argument("--port", type=int, default=8776)
    p.add_argument("--origin", help="Origen HTTPS exacto para un proxy local; no despliega ni configura servidores remotos")
    sub.add_parser("status")
    sub.add_parser("preflight", help="Comprobar capacidades de este software sin ejecutar sistema/preflight.py del padre")
    sub.add_parser("projects")
    sub.add_parser("assets")
    sub.add_parser("media-tools")
    sub.add_parser("font-library")
    sub.add_parser("text-presets")
    for command in ("job", "cancel-job"):
        p = sub.add_parser(command)
        p.add_argument("job_id")
    p = sub.add_parser("text-layout")
    p.add_argument("project_id")
    p.add_argument("element_path", help="JSON de un elemento de texto dentro de SOFTWARE")
    p.add_argument("--width", type=int, default=540)
    p.add_argument("--height", type=int, default=960)
    p.add_argument("--duration", type=float, default=5)
    p = sub.add_parser("process")
    p.add_argument("asset_id")
    p.add_argument("operation")
    p.add_argument("--options", help="JSON de parámetros dentro de SOFTWARE")
    p.add_argument("--project", help="Asociar el nuevo medio al proyecto sin reemplazar el original")
    p = sub.add_parser("open")
    p.add_argument("zip_path", help="Paquete editable ZIP dentro de SOFTWARE")
    p = sub.add_parser("import")
    p.add_argument("path", help="Archivo existente dentro de SOFTWARE")
    p.add_argument("--kind", choices=["video", "broll", "audio", "music", "sfx", "image", "font"])
    p.add_argument("--name")
    p.add_argument("--original-graphic-author", help="Declaración de autor para una imagen original; no certifica derechos")
    p = sub.add_parser("create")
    p.add_argument("--name", default="Nuevo reel")
    p.add_argument("--source")
    p.add_argument("--drive-id")
    for command in ["get", "plan", "validate", "export", "manual", "workflow", "skills"]:
        p = sub.add_parser(command)
        p.add_argument("project_id")
        if command == "validate":
            p.add_argument("--seconds", type=float, default=10)
            p.add_argument("--draft", action="store_true")
        if command == "manual":
            p.add_argument("--read-complete", action="store_true", required=True)
        if command == "skills":
            p.add_argument("--prepare", action="store_true", help="Crear registro pendiente, sin afirmar lectura ni aplicación")
    p = sub.add_parser("update")
    p.add_argument("project_id")
    p.add_argument("json_path")
    p = sub.add_parser("attach")
    p.add_argument("project_id")
    p.add_argument("asset_id")
    p.add_argument("--source", action="store_true")
    for command in ["analyze", "automate"]:
        p = sub.add_parser(command)
        p.add_argument("project_id")
        p.add_argument("--transcribe", action="store_true")
        p.add_argument("--model", default="tiny", choices=["tiny", "base", "small", "medium", "large-v3", "distil-large-v3"])
        p.add_argument("--language", default="es")
    p = sub.add_parser("render")
    p.add_argument("project_id")
    p.add_argument("--seconds", type=float, default=10)
    p.add_argument("--technical", action="store_true", help="Exportado técnico del editor, máximo 10 s y sin aprobación ASCENDIA")
    p.add_argument("--engine", choices=["native", "hyperframes"], help="Guardar la elección de motor antes de encolar")
    p = sub.add_parser("tracking")
    p.add_argument("project_id")
    p.add_argument("--options", help="Archivo JSON de opciones dentro de SOFTWARE")
    p = sub.add_parser("tracking-proposals")
    p.add_argument("project_id")
    p = sub.add_parser("design-snapshot")
    p.add_argument("project_id")
    p.add_argument("scene_id")
    p = sub.add_parser("design-review")
    p.add_argument("project_id")
    p.add_argument("json_path")
    sub.add_parser("scene-ir-schema")
    for command in ("scene-ir-preview", "scene-ir-apply"):
        p = sub.add_parser(command)
        p.add_argument("project_id")
        p.add_argument("json_path", help="SceneIR JSON dentro de SOFTWARE")
        if command == "scene-ir-apply":
            p.add_argument("--expected-revision", type=int, required=True)
    p = sub.add_parser("review")
    p.add_argument("project_id")
    p.add_argument("json_path")
    p = sub.add_parser("authorize")
    p.add_argument("project_id")
    p.add_argument("--notes", required=True)
    sub.add_parser("jobs")
    sub.add_parser("tasks")
    p = sub.add_parser("claim")
    p.add_argument("role", choices=["director", "resources", "motion", "audio", "qa"])
    p.add_argument("--agent", required=True)
    p = sub.add_parser("complete")
    p.add_argument("task_id")
    p.add_argument("--lease", required=True)
    p.add_argument("--result", required=True)
    p = sub.add_parser("release")
    p.add_argument("task_id")
    p.add_argument("--lease", required=True)
    sub.add_parser("mcp", help="Servidor MCP stdio para agentes")
    args = parser.parse_args(argv)
    setup()
    try:
        command = args.command
        if command == "multiservice":
            from .gateway import serve
            return serve(args.port, args.origin)
        if command == "serve":
            from .server import serve
            return serve(args.port)
        if command == "mcp":
            from .mcp import serve_stdio
            return serve_stdio()
        if command in ("status", "preflight"):
            from .server import status
            result = status()
            if command == "preflight":
                from PIL import ImageFont
                from .core import fonts
                result["font_checks"] = {}
                for key, path in fonts().items():
                    try:
                        result["font_checks"][key] = {"available": True, "family": ImageFont.truetype(str(confined(path, must_exist=True)), 24).getname()}
                    except (StudioError, OSError) as error:
                        result["font_checks"][key] = {"available": False, "error": str(error)}
                result["tool_usage_note"] = "Disponibilidad detectada; las pruebas y recibos de ejecución prueban uso. El preflight del reel activo no se ejecuta."
        elif command == "projects":
            result = {"projects": project_list()}
        elif command == "assets":
            result = {"assets": assets()}
        elif command == "media-tools":
            from .media_tools import catalog
            result = {"operations": catalog()}
        elif command == "font-library":
            from .fonts import catalog
            result = catalog()
        elif command == "text-presets":
            from .typography import catalog
            result = catalog()
        elif command == "text-layout":
            from .server import text_layout
            element_file = confined(args.element_path, must_exist=True)
            if element_file.stat().st_size > 32768:
                raise StudioError("El elemento tipográfico admite hasta 32 KiB de JSON.", 413)
            try:
                element = json.loads(element_file.read_text())
            except (ValueError, UnicodeError) as error:
                raise StudioError("El elemento tipográfico requiere JSON UTF-8 válido.") from error
            result = text_layout({"project_id": args.project_id, "element": element,
                                  "scene_duration": args.duration, "width": args.width, "height": args.height})
        elif command == "job":
            result = get_job(args.job_id)
        elif command == "cancel-job":
            result = request_job_cancel(args.job_id)
        elif command == "process":
            options = json.loads(confined(args.options, must_exist=True).read_text()) if args.options else {}
            result = enqueue_media(args.asset_id, args.operation, options, args.project)
        elif command == "open":
            from .bundles import import_bundle
            result = import_bundle(confined(args.zip_path, must_exist=True))
        elif command == "import":
            metadata = None
            if args.original_graphic_author is not None:
                if args.kind != "image" or not args.original_graphic_author.strip() or len(args.original_graphic_author) > 500:
                    raise StudioError("La declaración de gráfico original requiere --kind image y autor de1–500caracteres.")
                metadata = {"declaration_original": {"kind": "original_graphic", "author": args.original_graphic_author}}
            result = register_asset(confined(args.path, must_exist=True), args.name, args.kind, metadata)
        elif command == "create":
            result = create_project(args.name, args.source, args.drive_id)
        elif command == "get":
            result = get_project(args.project_id)
        elif command == "update":
            result = save_project(args.project_id, json.loads(confined(args.json_path, must_exist=True).read_text()))
        elif command == "attach":
            result = attach_asset(args.project_id, args.asset_id, args.source)
        elif command in ("analyze", "automate"):
            result = enqueue(args.project_id, command, {"transcribe": args.transcribe, "model": args.model, "language": args.language})
        elif command == "plan":
            from .analysis import propose_storyboard
            result = save_project(args.project_id, propose_storyboard(get_project(args.project_id)), action="storyboard_proposed")
        elif command == "validate":
            result = validate_project(get_project(args.project_id), seconds=args.seconds, strict=not args.draft)
        elif command == "render":
            p = get_project(args.project_id)
            if args.engine and p["settings"].get("engine", "native") != args.engine:
                p["settings"]["engine"] = args.engine
                p = save_project(p["id"], p)
            result = enqueue(args.project_id, "render", {"seconds": args.seconds, "technical": args.technical, "engine": p["settings"].get("engine", "native")})
        elif command == "tracking":
            options = json.loads(confined(args.options, must_exist=True).read_text()) if args.options else {}
            result = enqueue(args.project_id, "tracking", options)
        elif command == "tracking-proposals":
            from .tracking_actions import propose_tracking
            result = propose_tracking(get_project(args.project_id))
        elif command == "design-snapshot":
            result = enqueue(args.project_id, "design_snapshot", {"scene_id": args.scene_id})
        elif command == "design-review":
            from .design_review import record_review as review_design
            result = review_design(args.project_id, json.loads(confined(args.json_path, must_exist=True).read_text()))
        elif command == "scene-ir-schema":
            from .scene_ir import describe_schema
            result = describe_schema()
        elif command in ("scene-ir-preview", "scene-ir-apply"):
            from .scene_ir_actions import preview, apply
            document = json.loads(confined(args.json_path, must_exist=True).read_text())
            result = preview(args.project_id, document) if command == "scene-ir-preview" else apply(args.project_id, document, args.expected_revision)
        elif command == "review":
            result = record_review(args.project_id, json.loads(confined(args.json_path, must_exist=True).read_text()))
        elif command == "authorize":
            from .server import authorize_full
            result = authorize_full(args.project_id, {"authorized": True, "notes": args.notes})
        elif command == "export":
            result = export_bundle(args.project_id)
        elif command == "manual":
            result = refresh_manual(args.project_id)
        elif command == "workflow":
            result = {"tasks": create_tasks(args.project_id)}
        elif command == "skills":
            from .skills import inventory, prepare, validate_application
            p = prepare(args.project_id) if args.prepare else get_project(args.project_id)
            result = {"inventory": inventory(), "application": p.get("skills_applied"), "errors": validate_application(p)}
        elif command == "jobs":
            result = {"jobs": list_jobs()}
        elif command == "tasks":
            result = {"tasks": tasks()}
        elif command == "claim":
            result = claim_task(args.role, args.agent)
        elif command == "complete":
            result = finish_task(args.task_id, args.lease, json.loads(confined(args.result, must_exist=True).read_text()))
        elif command == "release":
            result = release_task(args.task_id, args.lease)
        else:
            raise StudioError("Comando desconocido.")
        output(result)
        return 0
    except StudioError as error:
        output({"error": str(error), "status": error.status, "details": error.details})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
