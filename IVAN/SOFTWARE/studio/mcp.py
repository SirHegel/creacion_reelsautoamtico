"""MCP JSON-RPC stdio access to the same confined editor, with no shell tool."""
from __future__ import annotations
import json
import math
import sys

from . import __version__

from .core import StudioError, create_project, project_list, get_project, save_project, validate_project, assets, register_asset, confined, attach_asset, record_review
from .jobs import list_jobs, export_bundle, create_tasks, tasks, claim_task, finish_task, release_task


def spec(name, description, properties=None, required=None, read_only=False, open_world=False):
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": read_only, "destructiveHint": False, "openWorldHint": open_world}}


S = {"type": "string"}
P = {"project_id": S}
TOOLS = [
    spec("studio_status", "Capacidades reales, limitaciones y manual vigente.", read_only=True),
    spec("cloud_storage_status", "Estado de la base de respaldo remoto del administrador. Por defecto local, sin conexión verificada ni sincronización automática.", read_only=True),
    spec("cloud_backup_get", "Estado y recibo del respaldo propio; pendiente hasta confirmar integridad, sin heredar aprobación del montaje.", P, ["project_id"], True),
    spec("cloud_backup_start", "Respaldar el proyecto propio y recursos en el almacenamiento configurado por el administrador. Requiere revisiones y verificación remota antes de declararlo sincronizado.",
         {**P, "expected_revision": {"type": "integer", "minimum": 1},
          "expected_outbox_revision": {"type": "integer", "minimum": 0}, "expected_etag": S,
          "include_outputs": {"type": "boolean"}}, ["project_id", "expected_revision"], open_world=True),
    spec("ivan_automation_catalog", "Contrato de dirección y capacidades reales de las familias IVAN adaptadas.", read_only=True),
    spec("branding_get", "Perfil IVAN y configuración privada de marca, sin claves de IA.", read_only=True),
    spec("pipeline_start", "Iniciar el reel completo por etapas con API propia confirmada o agente externo; ASR/cámara reales y borrador técnico sin aprobación automática.", {**P, "options": {"type": "object"}}, ["project_id", "options"]),
    spec("pipeline_get", "Consultar generación, etapas y encargos de dirección por tramo para reanudar el reel; sin ejecutar IA ni aprobar.", {**P, "include_context": {"type": "boolean"}}, ["project_id"], True),
    spec("pipeline_plan", "Entregar un plan cerrado de un tramo externo con generación/revisión vigentes; nunca ejecutar código ni certificar el modelo declarado.", {**P, "generation": {"type": "integer", "minimum": 1}, "chunk_id": S,
         "expected_revision": {"type": "integer", "minimum": 1}, "document": {"type": "object"}, "agent": {"type": "object"}},
         ["project_id", "generation", "chunk_id", "expected_revision", "document", "agent"]),
    spec("pipeline_resume", "Reanudar la generación vigente, reutilizando etapas verificadas, hasta el render y editable técnicos.", {**P, "generation": {"type": "integer", "minimum": 1}}, ["project_id", "generation"]),
    spec("pipeline_restart", "Reiniciar explícitamente una generación cancelada u obsoleta con entradas/opciones actuales; conserva historia y análisis que aún sean válidos.", {**P, "generation": {"type": "integer", "minimum": 1}, "options": {"type": "object"}}, ["project_id", "generation", "options"]),
    spec("pipeline_cancel", "Cancelar solo la generación propia, conservando fuente y evidencias registradas.", {**P, "generation": {"type": "integer", "minimum": 1}}, ["project_id", "generation"]),
    spec("audio_tracks", "Medir pistas de audio reales y sugerir por actividad; actividad/tonos no verifican voz ni sustituyen escuchar.", {"asset_id": S, "options": {"type": "object"}}, ["asset_id"]),
    spec("brand_assets_catalog", "Registro privado de gráficos de marca y observaciones vigentes; sin permisos públicos automáticos.", {"context": {"enum": ["private_review", "publication"]}}, read_only=True),
    spec("brand_assets_origins", "Fuentes oficiales fijadas y límites de importación; no descarga ni certifica uso.", read_only=True),
    spec("brand_assets_register", "Registrar una observación propia con evidencia y procedencia declarada; no concede derechos.", {"asset_id": S, "options": {"type": "object"}}, ["asset_id", "options"]),
    spec("brand_assets_fetch", "Importar por HTTPS un gráfico de una fuente oficial fija; queda pendiente de observación y permisos aplicables.", {"entity": S, "options": {"type": "object"}}, ["entity"]),
    spec("brand_assets_resolve", "Resolver entidades contra registros observados actuales; sin logo inventado como alternativa.", {"entities": {"type": "array", "items": S}, "context": {"enum": ["private_review", "publication"]}}, ["entities"], True),
    spec("draft_render", "Exportar un borrador manual completo de hasta600s en el espacio SaaS. Es técnico, conserva audio original y no hereda aprobación editorial.", {**P, "seconds": {"type": "number", "minimum": .1, "maximum": 600}, "engine": {"enum": ["native", "hyperframes"]}}, ["project_id", "seconds"]),
    spec("ivan_prepare", "Preparar narración alineada, mediciones de cámara y contexto IVAN para tu agente externo; CPU local, sin consumo de API ni aplicar una edición.", {**P,"options":{"type":"object","properties":{"instructions":S,"seconds":{"type":"number","minimum":.1,"maximum":10},"language":S,"asr_model":{"enum":["tiny","base","small"]}},"additionalProperties":False}}, ["project_id"]),
    spec("ivan_apply_plan", "Aplicar el plan declarado de tu agente a la preparación vigente, con revisión optimista; compila motion editable y prueba técnica sin aprobación automática.", {**P,"preparation_id":S,"expected_revision":{"type":"integer","minimum":1},"document":{"type":"object"},"agent":{"type":"object","properties":{"name":S,"model":S,"notes":S},"required":["name"],"additionalProperties":False}}, ["project_id","preparation_id","expected_revision","document","agent"]),
    spec("resource_review_prepare", "Decodificar muestras y opcionalmente una secuencia muda de un recurso privado. Preparar evidencia no equivale a verla.", {"asset_id":S,"options":{"type":"object","properties":{"start":{"type":"number","minimum":0},"duration":{"type":"number","minimum":.01,"maximum":30},"samples":{"type":"integer","minimum":1,"maximum":12},"max_width":{"type":"integer","minimum":160,"maximum":1080},"max_height":{"type":"integer","minimum":160,"maximum":1920},"sequence":{"type":"boolean"}},"additionalProperties":False}}, ["asset_id"]),
    spec("resource_review_get", "Consultar integridad, alcance y tramo de la observación actual; sin promover licencia o aprobación editorial.", {"asset_id":S}, ["asset_id"], True),
    spec("resource_review_record", "Registrar contenido observado y evidencia propia con CAS de fuente/recibo/observación; muestras aisladas no acreditan una secuencia completa.", {"asset_id":S,"review":{"type":"object"}}, ["asset_id","review"]),
    spec("branding_apply", "Aplicar explícitamente la marca actual a este proyecto, con revisión optimista de proyecto y marca; revisión editorial invalidada.", {**P,"expected_revision":{"type":"integer","minimum":1},"expected_branding_revision":{"type":"integer","minimum":1}}, ["project_id","expected_revision"]),
    spec("ivan_automate", "Transcribir con CPU, inferir con tu proveedor y generar storyboard/motion editable y prueba; consume tu API sólo con confirmed=true, sin aprobación automática.",
         {**P,"options":{"type":"object","properties":{"provider":{"type":"string"},"confirmed":{"const":True},"instructions":S,"seconds":{"type":"number","minimum":.1,"maximum":10},"language":S,"asr_model":{"enum":["tiny","base","small"]},"plan_only":{"type":"boolean"},"max_tokens":{"type":"integer","minimum":1024,"maximum":8192}},"required":["provider","confirmed"],"additionalProperties":False}},["project_id","options"]),
    spec("project_list", "Listar proyectos canónicos.", read_only=True),
    spec("project_get", "Leer proyecto editable y revisión optimista.", P, ["project_id"], True),
    spec("project_create", "Crear o reutilizar proyecto por fuente/ID Drive; no descarga de Drive.", {"name": S, "source": S, "drive_id": S}),
    spec("project_update", "Guardar proyecto completo con revision; invalida aprobaciones si cambió edición.", {**P, "project": {"type": "object"}}, ["project_id", "project"]),
    spec("asset_list", "Listar recursos importados; nombres no certifican pertinencia.", read_only=True),
    spec("asset_import", "Importar medio dentro de SOFTWARE, deduplicado. original_graphic_author es declaración para imagen propia, no certifica derechos.", {"path": S, "kind": {"enum": ["video", "broll", "audio", "music", "sfx", "image", "font"]}, "original_graphic_author": S}, ["path"]),
    spec("asset_attach", "Asociar recurso importado al proyecto.", {**P, "asset_id": S, "source": {"type": "boolean"}}, ["project_id", "asset_id"]),
    spec("media_tools", "Catálogo real de herramientas multimedia y parámetros.", read_only=True),
    spec("font_library", "Fuentes locales TTF/OTF con familia, variante, hashes y avisos de licencia; sin sustitución automática.", read_only=True),
    spec("text_presets", "Estilos y presets originales de texto determinista; no certifican CLONE ni una suite comercial.", read_only=True),
    spec("text_layout", "Medir un borrador de texto con fuente canónica, sin guardar ni aprobar.", {**P, "element": {"type": "object"},
         "scene_duration": {"type": "number", "minimum": .01, "maximum": 7200}, "width": {"type": "integer", "minimum": 64, "maximum": 1080},
         "height": {"type": "integer", "minimum": 64, "maximum": 1920}}, ["project_id", "element", "scene_duration", "width", "height"], True),
    spec("media_process", "Procesar derivado FFmpeg CPU; sin sobrescribir original, revisión pendiente.", {"asset_id": S, "operation": S, "options": {"type": "object"}, "project_id": S}, ["asset_id", "operation"]),
    spec("editable_open", "Reabrir ZIP dentro de SOFTWARE, validar hashes y reutilizar originales; no importa aprobaciones.", {"path": S}, ["path"]),
    spec("project_analyze", "Analizar pistas; transcripción CPU solo si transcribe=true. Modelo/cache locales.", {**P, "transcribe": {"type": "boolean", "default": False}, "model": {"enum": ["tiny", "base", "small"]}, "language": S}, ["project_id"]),
    spec("storyboard_propose", "Propuesta heurística por narración; requiere dirección y evidencia, no aprobación automática.", P, ["project_id"]),
    spec("project_validate", "Comprobar tiempos, fuentes, evidencias y requisitos V5 antes del candidato; technical omite aprobación editorial.", {**P, "seconds": {"type": "number", "minimum": .1, "maximum": 10}, "technical": {"type": "boolean"}}, ["project_id"], True),
    spec("preview_render", "Renderizar primeros 10s con el motor guardado. technical=true nunca aprueba ASCENDIA.", {**P, "technical": {"type": "boolean"}, "engine": {"enum": ["native", "hyperframes"]}}, ["project_id"]),
    spec("face_tracking", "Medir rostro/barbilla con MediaPipe CPU. Conserva evidencia; no cambia escenas ni aprueba.", {**P, "options": {"type": "object"}}, ["project_id"]),
    spec("tracking_proposals", "Transformar medidas verificadas a crop/split actual; propuestas para revisión sin aplicar ni aprobar.", P, ["project_id"], True),
    spec("design_snapshot", "Capturar PNG del diseño base vigente sin animación; pendiente de revisión explícita.", {**P, "scene_id": S}, ["project_id", "scene_id"]),
    spec("design_review", "Registrar observaciones o aprobación explícita del diseño actual; requiere SHA, referencia y evidencias comparativas.", {**P, "review": {"type": "object"}}, ["project_id", "review"]),
    spec("scene_ir_schema", "Contrato de escenas estructuradas; datos cerrados, sin generador semántico interno.", read_only=True),
    spec("scene_ir_preview", "Compilar propuesta SceneIR sin guardar; muestra sustitución de cronología y controles técnicos.", {**P, "document": {"type": "object"}}, ["project_id", "document"], True),
    spec("scene_ir_apply", "Aplicar SceneIR como componente editable con QC pendiente; reemplaza cronología con revisión optimista.", {**P, "document": {"type": "object"}, "expected_revision": {"type": "number", "minimum": 1}}, ["project_id", "document", "expected_revision"]),
    spec("job_list", "Ver progreso o fallos de tareas locales.", read_only=True),
    spec("job_get", "Consultar un trabajo local por ID, sin iniciar procesos.", {"job_id": S}, ["job_id"], True),
    spec("job_cancel", "Cancelar un trabajo local en punto seguro; conserva originales y resultados ya registrados.", {"job_id": S}, ["job_id"]),
    spec("editable_export", "Empaquetar proyecto, assets y manifest; conserva derechos originales.", P, ["project_id"]),
    spec("workflow_create", "Crear DAG director/recursos/motion/audio/QA con leases y salidas separadas.", P, ["project_id"]),
    spec("skills_inventory", "Leer guías locales e inventario de hashes; no acredita comprensión ni aplicación.", P, ["project_id"], True),
    spec("skills_prepare", "Crear registro pendiente de las doce guías por proyecto; conserva un registro existente.", P, ["project_id"]),
    spec("task_list", "Leer tareas y dependencias; no equivale a desplegar modelos.", read_only=True),
    spec("task_claim", "Reclamar una tarea disponible. La evidencia debe quedar dentro de SOFTWARE.", {"role": {"enum": ["director", "resources", "motion", "audio", "qa"]}, "agent": S}, ["role", "agent"]),
    spec("task_complete", "Completar con observaciones/evidencia local; rechaza resultados de proyecto/manual desactualizados.", {"task_id": S, "lease": S, "result": {"type": "object"}}, ["task_id", "lease", "result"]),
    spec("task_release", "Liberar una tarea reclamada para reanudarla con otro agente; requiere su lease.", {"task_id": S, "lease": S}, ["task_id", "lease"]),
]


def call_tool(name, args):
    definitions = {t["name"]: t for t in TOOLS}
    if name not in definitions or not isinstance(args, dict):
        raise StudioError("Herramienta o argumentos desconocidos.")
    schema = definitions[name]["inputSchema"]
    if set(args) - set(schema["properties"]) or any(k not in args for k in schema["required"]):
        raise StudioError("Argumentos extra o requeridos ausentes.")
    for k, value in args.items():
        field = schema["properties"][k]
        if "enum" in field and value not in field["enum"]:
            raise StudioError("Valor fuera del esquema de la herramienta.")
        if field.get("type") == "string" and not isinstance(value, str):
            raise StudioError(f"{k} debe ser texto.")
        if field.get("type") == "boolean" and not isinstance(value, bool):
            raise StudioError(f"{k} debe ser booleano.")
        if field.get("type") == "object" and not isinstance(value, dict):
            raise StudioError(f"{k} debe ser un objeto.")
        if field.get("type") == "array" and not isinstance(value, list):
            raise StudioError(f"{k} debe ser una lista.")
        if field.get("type") in ("number", "integer"):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < field.get("minimum", -math.inf) or value > field.get("maximum", math.inf):
                raise StudioError(f"{k} debe ser un número dentro del rango admitido.")
            if field["type"] == "integer" and type(value) is not int:
                raise StudioError(f"{k} requiere un número entero.")
    if name == 'cloud_storage_status':
        from .cloud_storage import status
        from .runtime import CODE_ROOT
        return status(CODE_ROOT)
    if name == 'cloud_backup_get':
        from .jobs import cloud_backup_status
        return cloud_backup_status(args['project_id'])
    if name == 'cloud_backup_start':
        from .jobs import submit, start_worker
        start_worker()
        return submit(args['project_id'], 'cloud_backup', {k: v for k, v in args.items() if k != 'project_id'})
    if name == 'pipeline_get':
        from .pipeline import status
        return status(args['project_id'], args.get('include_context', True))
    if name in ('pipeline_start', 'pipeline_resume', 'pipeline_restart'):
        from .jobs import submit, start_worker
        start_worker()
        options = args['options'] if name == 'pipeline_start' else {'generation': args['generation'],
                  **({'options': args['options']} if name == 'pipeline_restart' else {})}
        action = 'pipeline' if name == 'pipeline_start' else 'pipeline_restart' if name == 'pipeline_restart' else 'pipeline_resume'
        return submit(args['project_id'], action, options)
    if name == 'pipeline_plan':
        from .pipeline import submit_external_plan
        return submit_external_plan(args['project_id'], {key: value for key, value in args.items() if key != 'project_id'})
    if name == 'pipeline_cancel':
        from .pipeline import cancel
        return cancel(args['project_id'], args['generation'])
    if name == 'audio_tracks':
        from .jobs import submit_audio_tracks, start_worker
        start_worker()
        return submit_audio_tracks(args['asset_id'], args.get('options'))
    if name in ('brand_assets_catalog', 'brand_assets_origins', 'brand_assets_register', 'brand_assets_resolve'):
        from . import brand_assets
        if name == 'brand_assets_catalog': return brand_assets.catalog(args.get('context', 'private_review'))
        if name == 'brand_assets_origins': return brand_assets.origin_catalog()
        if name == 'brand_assets_register': return brand_assets.register(args['asset_id'], args['options'])
        return brand_assets.resolve(args['entities'], args.get('context', 'private_review'))
    if name == 'brand_assets_fetch':
        from .jobs import submit_brand_fetch, start_worker
        start_worker()
        return submit_brand_fetch(args['entity'], args.get('options'))
    if name == 'draft_render':
        from .cli import enqueue
        return enqueue(args['project_id'], 'render', {'seconds': args['seconds'], 'technical': True,
                       'draft_full': True, **({'engine': args['engine']} if 'engine' in args else {})})
    if name == "ivan_automation_catalog":
        from .automation import catalog
        return catalog()
    if name == "ivan_automate":
        from .jobs import submit, start_worker
        start_worker()
        return submit(args["project_id"], "auto_ivan", args["options"])
    if name in ("ivan_prepare", "ivan_apply_plan"):
        from .jobs import submit, start_worker
        start_worker()
        options = args.get("options", {}) if name == "ivan_prepare" else {key: args[key] for key in ("preparation_id", "expected_revision", "document", "agent")}
        return submit(args["project_id"], name, options)
    if name == "resource_review_prepare":
        from .jobs import submit_resource_review, start_worker
        start_worker()
        return submit_resource_review(args["asset_id"], args.get("options", {}))
    if name == "resource_review_get":
        from .resource_review import current_review
        return current_review(args["asset_id"])
    if name == "resource_review_record":
        from .resource_review import record
        return record(args["asset_id"], args["review"])
    if name == "branding_get":
        from .branding import get_branding
        from .core import ROOT
        return get_branding(ROOT)
    if name == "branding_apply":
        from .branding import apply_project_branding
        return apply_project_branding(args["project_id"], args["expected_revision"], args.get("expected_branding_revision"))
    if name == "studio_status":
        from .server import status
        return status()
    if name == "project_list": return {"projects": project_list()}
    if name == "project_get": return get_project(args["project_id"])
    if name == "project_create": return create_project(args.get("name", "Nuevo reel"), args.get("source"), args.get("drive_id"))
    if name == "project_update": return save_project(args["project_id"], args["project"])
    if name == "asset_list": return {"assets": assets()}
    if name == "asset_import":
        author = args.get("original_graphic_author")
        if author is not None and (args.get("kind") != "image" or not author.strip() or len(author) > 500):
            raise StudioError("La declaración de gráfico original requiere kind:image y autor de1–500caracteres.")
        metadata = {"declaration_original": {"kind": "original_graphic", "author": author}} if author is not None else None
        return register_asset(confined(args["path"], must_exist=True), kind=args.get("kind"), metadata=metadata)
    if name == "asset_attach": return attach_asset(args["project_id"], args["asset_id"], args.get("source", False))
    if name == "media_tools":
        from .media_tools import catalog
        return {"operations": catalog()}
    if name == "font_library":
        from .fonts import catalog
        return catalog()
    if name == "text_presets":
        from .typography import catalog
        return catalog()
    if name == "text_layout":
        from .server import text_layout
        return text_layout(args)
    if name == "job_get":
        from .jobs import get_job
        return get_job(args["job_id"])
    if name == "job_cancel":
        from .cli import request_job_cancel
        return request_job_cancel(args["job_id"])
    if name == "media_process":
        from .cli import enqueue_media
        return enqueue_media(args["asset_id"], args["operation"], args.get("options", {}), args.get("project_id"))
    if name == "editable_open":
        from .bundles import import_bundle
        return import_bundle(confined(args["path"], must_exist=True))
    if name == "project_analyze":
        from .cli import enqueue
        return enqueue(args["project_id"], "analyze", {"transcribe": args.get("transcribe", False), "model": args.get("model", "tiny"), "language": args.get("language", "es")})
    if name == "storyboard_propose":
        from .analysis import propose_storyboard
        p = propose_storyboard(get_project(args["project_id"]))
        return save_project(p["id"], p, action="storyboard_proposed")
    if name == "project_validate": return validate_project(get_project(args["project_id"]), args.get("seconds", 10), strict=not args.get("technical", False))
    if name == "preview_render":
        from .cli import enqueue
        options = {"seconds": 10, "technical": args.get("technical", False)}
        if "engine" in args:
            options["engine"] = args["engine"]
        return enqueue(args["project_id"], "render", options)
    if name == "face_tracking":
        from .cli import enqueue
        return enqueue(args["project_id"], "tracking", args.get("options", {}))
    if name == "tracking_proposals":
        from .tracking_actions import propose_tracking
        return propose_tracking(get_project(args["project_id"]))
    if name == "design_snapshot":
        from .cli import enqueue
        return enqueue(args["project_id"], "design_snapshot", {"scene_id": args["scene_id"]})
    if name == "design_review":
        from .design_review import record_review as review_design
        return review_design(args["project_id"], args["review"])
    if name == "scene_ir_schema":
        from .scene_ir import describe_schema
        return describe_schema()
    if name in ("scene_ir_preview", "scene_ir_apply"):
        from .scene_ir_actions import preview, apply
        return preview(args["project_id"], args["document"]) if name == "scene_ir_preview" else apply(args["project_id"], args["document"], args["expected_revision"])
    if name == "job_list": return {"jobs": list_jobs()}
    if name == "editable_export": return export_bundle(args["project_id"])
    if name == "workflow_create": return {"tasks": create_tasks(args["project_id"])}
    if name in ("skills_inventory", "skills_prepare"):
        from .skills import inventory, prepare, validate_application
        p = prepare(args["project_id"]) if name == "skills_prepare" else get_project(args["project_id"])
        return {"inventory": inventory(), "application": p.get("skills_applied"), "errors": validate_application(p)}
    if name == "task_list": return {"tasks": tasks()}
    if name == "task_claim": return claim_task(args["role"], args["agent"])
    if name == "task_complete": return finish_task(args["task_id"], args["lease"], args["result"])
    if name == "task_release": return release_task(args["task_id"], args["lease"])
    raise StudioError("Herramienta no implementada.")


def handle(request):
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
        return {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None, "error": {"code": -32600, "message": "Solicitud JSON-RPC inválida."}}
    if not isinstance(request.get("params", {}), dict):
        return {"jsonrpc": "2.0", "id": request.get("id"), "error": {"code": -32602, "message": "Estos métodos requieren parámetros con nombres."}}
    rid = request.get("id")
    method, params = request.get("method"), request.get("params", {})
    if rid is None:
        return None
    response = {"jsonrpc": "2.0", "id": rid}
    if method == "initialize":
        version = params.get("protocolVersion", "2025-11-25")
        if not isinstance(version, str):
            response["error"] = {"code": -32602, "message": "protocolVersion requiere una versión literal."}
            return response
        supported = {"2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05", "2024-10-07"}
        response["result"] = {"protocolVersion": version if version in supported else "2025-11-25", "capabilities": {"tools": {}},
                              "serverInfo": {"name": "ascendia-studio", "version": __version__}, "instructions": "Editor local en SOFTWARE; leer manual completo y usar evidencia real. Componentes SceneIR: render técnico hasta10s sin aprobación por pieza, QC pendiente. Reel completo requiere prueba aprobada y autorización posterior. No heredar aprobaciones ni modificar producción padre."}
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            value = call_tool(params.get("name"), params.get("arguments", {}))
            response["result"] = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, allow_nan=False)}], "isError": False}
        except Exception as error:
            response["result"] = {"content": [{"type": "text", "text": json.dumps({"error": str(error), "details": getattr(error, "details", None)}, ensure_ascii=False)}], "isError": True}
    else:
        response["error"] = {"code": -32601, "message": "Método desconocido."}
    return response


def serve_stdio():
    for line in sys.stdin:
        try:
            if len(line) > 10 * 1024 * 1024:
                raise ValueError("Mensaje demasiado grande.")
            request = json.loads(line)
            result = handle(request)
        except (ValueError, TypeError, AttributeError):
            result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON-RPC inválido."}}
        if result is not None:
            sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
            sys.stdout.flush()
