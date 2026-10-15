from __future__ import annotations

import copy
import csv
import io
import json
import math
import os
import fcntl
import time
import queue
import threading
import traceback
import zipfile
from contextlib import contextmanager

from .core import ROOT, LOCK, StudioError, atomic_json, confined, read_json, now, uid, get_project, save_project, state, validate_project, validate_shape, editorial_digest, relative, digest, manual_fingerprints, asset, register_asset, attach_asset, approval_is_current, engine_fingerprints
from .runtime import SHARED_CPU_LOCK, shared_cpu_lock_path, WorkspaceConfigurationError

JOB_LOCK = LOCK
QUEUE = queue.Queue()
CANCEL = {}
WORKER = None
CPU_ACTIVE = threading.local()
LOADED_ENGINE_FINGERPRINTS = engine_fingerprints()


def require_current_engine():
    if engine_fingerprints() != LOADED_ENGINE_FINGERPRINTS:
        raise StudioError("El código del editor cambió; reinicia el servidor antes de ejecutar trabajos con la nueva versión.", 409)


def _cpu_lease():
    try:
        path = shared_cpu_lock_path(SHARED_CPU_LOCK)
        path.parent.mkdir(parents=True, exist_ok=True)
        path = shared_cpu_lock_path(SHARED_CPU_LOCK)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        return os.fdopen(descriptor, "a+b")
    except (WorkspaceConfigurationError, OSError) as error:
        raise StudioError("El bloqueo CPU compartido dejó de ser un archivo local autorizado.", 403) from error


@contextmanager
def cpu_slot(cancel=None):
    """Acquire CPU before any store transaction; nested workers reuse it."""
    def cancelled():
        return cancel is not None and bool(cancel() if callable(cancel) else cancel.is_set())
    if getattr(CPU_ACTIVE, "active", False):
        if cancelled():
            raise StudioError("Cancelado antes de procesar con CPU.", 409)
        yield
        return
    if getattr(LOCK.local, "depth", 0):
        raise StudioError("El procesador debe reservarse antes de abrir una transacción del almacén.", 409)
    with _cpu_lease() as lease:
        if cancel is None:
            fcntl.flock(lease.fileno(), fcntl.LOCK_EX)
        else:
            while True:
                if cancelled():
                    raise StudioError("Cancelado mientras esperaba el procesador CPU.", 409)
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(.05)
        try:
            if cancelled():
                raise StudioError("Cancelado antes de procesar con CPU.", 409)
            CPU_ACTIVE.active = True
            yield
        finally:
            CPU_ACTIVE.active = False
            fcntl.flock(lease.fileno(), fcntl.LOCK_UN)


def list_jobs():
    return read_json(".estado/jobs.json", [])


def get_job(job_id):
    j = next((j for j in list_jobs() if j["id"] == job_id), None)
    if not j:
        raise StudioError("Trabajo no encontrado.", 404)
    return j


def update_job(job_id, **changes):
    with JOB_LOCK:
        jobs = list_jobs()
        found = next((j for j in jobs if j["id"] == job_id), None)
        if not found:
            raise StudioError("Trabajo no encontrado.", 404)
        found.update(changes, updated_at=now())
        atomic_json(".estado/jobs.json", jobs[-500:])
        return found


def check_render_authorization(p, seconds, technical=False, draft_full=False):
    if p.get("mode") == "scene_ir_component":
        if not technical or seconds > 10:
            raise StudioError("Los componentes SceneIR admiten render técnico de hasta diez segundos con QC pendiente, sin aprobación de reel.", 409)
        return
    if draft_full:
        from .core import WORKSPACE_MODE
        if not WORKSPACE_MODE or technical is not True or seconds > 600:
            raise StudioError("El borrador completo requiere un espacio SaaS, modo técnico y hasta 600 segundos.", 409)
        if not p.get('source') or not p.get('timeline'):
            raise StudioError("El borrador completo requiere crudo y cronología.", 409)
        tolerance = 1 / float(p['settings']['fps'])
        source = asset(p['source'])
        planned = max(float(scene['end']) for scene in p['timeline'])
        if seconds > planned + tolerance or seconds > float(source.get('duration', 0)) + tolerance:
            raise StudioError("El borrador solicitado supera el crudo o la cronología.", 409)
        return
    if technical and seconds > 10 and p.get('pipeline'):
        from .pipeline import validate_pipeline_receipt
        receipt = validate_pipeline_receipt(p)
        if seconds > receipt['scope_seconds'] + 1 / float(p['settings']['fps']):
            raise StudioError("El render supera el alcance del pipeline.", 409)
        return
    if seconds <= 10:
        return
    if technical:
        raise StudioError("La exportación técnica del editor admite como máximo diez segundos y no autoriza un completo.", 409)
    if not p.get('source') or not p.get('timeline'):
        raise StudioError('El completo requiere un crudo canónico y una cronología que cubra la duración solicitada.',409)
    tolerance=1/float(p.get('settings',{}).get('fps',30))
    planned=max((float(s.get('end',0)) for s in p.get('timeline',[])),default=0)
    source=asset(p.get('source'))
    if seconds>planned+tolerance or seconds>float(source.get('duration',0))+tolerance:
        raise StudioError('El completo solicitado supera la cronología o el crudo disponible; amplía el plan y usa el crudo completo antes de autorizarlo.',409)
    auth = p.get("full_authorization", {})
    if not auth.get("authorized") or auth.get("editorial_digest") != editorial_digest(p) or not approval_is_current(p):
        raise StudioError("El completo requiere prueba vigente aprobada y autorización explícita posterior.", 409)


def submit(project_id, action, options=None):
    require_current_engine()
    if action not in ("analyze", "automate", "render", "tracking", "design_snapshot", "auto_ivan", "ivan_prepare", "ivan_apply_plan", "pipeline", "pipeline_resume", "pipeline_restart", "cloud_backup"):
        raise StudioError("Acción de trabajo desconocida.")
    p = get_project(project_id)
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise StudioError("Las opciones del trabajo requieren un objeto JSON.")
    cloud_config_revision = None
    if action == 'cloud_backup':
        from .core import WORKSPACE_MODE
        from .runtime import CODE_ROOT
        from .cloud_storage import ETAG, status as cloud_status
        if not WORKSPACE_MODE:
            raise StudioError('El respaldo remoto pertenece a un espacio SaaS privado.', 403)
        if set(options) - {'expected_revision', 'expected_outbox_revision', 'expected_etag', 'include_outputs'} or 'expected_revision' not in options:
            raise StudioError('El respaldo requiere la revisión del proyecto y opciones cerradas.')
        revision = options['expected_revision']
        outbox_revision = options.get('expected_outbox_revision', 0)
        if type(revision) is not int or revision < 1 or type(outbox_revision) is not int or outbox_revision < 0:
            raise StudioError('Las revisiones del respaldo deben ser enteros válidos.')
        if revision != p['revision']:
            raise StudioError('El proyecto cambió antes de solicitar el respaldo.', 409)
        etag = options.get('expected_etag')
        if etag is not None and (not isinstance(etag, str) or not ETAG.fullmatch(etag)):
            raise StudioError('La revisión remota debe ser un ETag válido.')
        if type(options.get('include_outputs', True)) is not bool:
            raise StudioError('include_outputs debe ser booleano.')
        cloud = cloud_status(CODE_ROOT)
        if cloud.get('configured') is not True or cloud.get('enabled') is not True:
            raise StudioError('El administrador debe configurar el almacenamiento remoto antes de respaldar.', 409)
        cloud_config_revision = cloud['revision']
        options = {'expected_revision': revision, 'expected_outbox_revision': outbox_revision,
                   'expected_etag': etag, 'include_outputs': options.get('include_outputs', True)}
    if action == "pipeline":
        from .pipeline import validate_options
        options = validate_options(options)
        if not p.get('source') or p.get('mode') == 'scene_ir_component':
            raise StudioError("El pipeline requiere un reel con crudo canónico.", 409)
    if action in ("pipeline_resume", "pipeline_restart"):
        from .pipeline import status, validate_options
        fields = {'generation', 'options'} if action == 'pipeline_restart' else {'generation'}
        if set(options) != fields or type(options['generation']) is not int:
            raise StudioError("Reanudar o reiniciar requiere la generación entera vigente y sus campos exactos.")
        current = status(project_id)
        if options['generation'] != current['generation']:
            raise StudioError("La generación del pipeline cambió.", 409)
        if action == 'pipeline_restart':
            options = {'generation': options['generation'], 'options': validate_options(options['options'])}
    if action in ("analyze", "automate"):
        from .analysis import validate_analysis_options
        validate_analysis_options(options)
    if action == "auto_ivan":
        from .automation import validate_options
        options=validate_options(options)
        if not p.get('source'):
            raise StudioError('Carga un crudo antes de automatizar IVAN.')
        if p.get('mode')=='scene_ir_component':
            raise StudioError('Auto IVAN requiere un reel con fuente, no un componente aislado.',409)
    if action in ('ivan_prepare','ivan_apply_plan'):
        from .automation import validate_prepare_options,validate_apply_options
        options=(validate_prepare_options(options) if action=='ivan_prepare' else validate_apply_options(options))
        if not p.get('source') or p.get('mode')=='scene_ir_component':raise StudioError('La dirección IVAN requiere un reel canónico con fuente.',409)
        if action=='ivan_apply_plan' and options['expected_revision']!=p['revision']:
            raise StudioError('El proyecto cambió desde la preparación externa.',409)
    if action == "tracking":
        from .tracking import validate_options
        options = validate_options(options)
    if action == "design_snapshot":
        if set(options) != {"scene_id"} or not isinstance(options["scene_id"], str):
            raise StudioError("La captura estática requiere scene_id.")
        from .design import validate_design
        scene = next((s for s in p["timeline"] if s["id"] == options["scene_id"]), None)
        if not scene or scene.get("template") != "custom":
            raise StudioError("Elige una escena de composición libre para capturar.")
        validate_design(scene, (p["settings"]["width"], p["settings"]["height"]))
        if p["manual"] != manual_fingerprints():
            raise StudioError("Relee y actualiza el manual antes de capturar el diseño.", 409)
    if action == "render":
        if "technical" in options and not isinstance(options["technical"], bool):
            raise StudioError("technical debe ser booleano.")
        if 'draft_full' in options and type(options['draft_full']) is not bool:
            raise StudioError("draft_full debe ser booleano.")
        technical = options.get("technical", False)
        if 'ivan_draft' in options:
            from .automation import validate_draft_receipt
            if options['ivan_draft'] is not True or technical is not True:
                raise StudioError('La prueba IVAN requiere un plan inferido vigente y modo técnico.',409)
            validate_draft_receipt(p)
        engine = options.get("engine", p.get("settings", {}).get("engine", "native"))
        if engine not in ("native", "hyperframes") or engine != p.get("settings", {}).get("engine", "native"):
            raise StudioError("El motor solicitado debe coincidir con el motor guardado en ajustes del proyecto.", 409)
        options = {**options, "engine": engine}
        try:
            raw_seconds = options.get("seconds", 10)
            if isinstance(raw_seconds, bool):
                raise StudioError("Duración de render inválida.")
            seconds = float(raw_seconds)
        except (ValueError, TypeError):
            raise StudioError("Duración de render inválida.") from None
        if not math.isfinite(seconds) or seconds <= 0 or seconds > 7200:
            raise StudioError("Duración de render inválida.")
        if p.get("mode") == "scene_ir_component":
            if seconds > 10:
                raise StudioError("Un componente SceneIR admite como máximo diez segundos.", 409)
            from .scene_ir import validate_compiled_project
            validate_compiled_project(p)
            seconds = min(seconds, p["timeline"][0]["end"])
            technical = True
            options.update(seconds=seconds, technical=True, component_qc="pending")
        check_render_authorization(p, seconds, technical, options.get('draft_full', False))
        check = validate_project(p, seconds=seconds, strict=not technical)
        if not check["valid"]:
            raise StudioError("La prueba todavía no cumple sus requisitos previos.", 409, check)
    with JOB_LOCK:
        for j in list_jobs():
            if j["project_id"] == project_id and j["status"] in ("queued", "running"):
                raise StudioError("Ya hay un trabajo pendiente para este proyecto.", 409)
        job = {"id": uid("j_"), "project_id": project_id, "action": action, "options": options,
               "revision": p["revision"], "status": "queued", "progress": 0, "owner_pid": os.getpid(),
               "message": "En cola CPU, sin utilizar GPU ni procesos externos.", "created_at": now(), "updated_at": now()}
        if cloud_config_revision is not None:
            job.update(cloud_config_revision=cloud_config_revision,
                       processor_fingerprints=engine_fingerprints(),
                       message='Respaldo privado en cola; sincronización pendiente de recibo remoto.')
        jobs = list_jobs() + [job]
        atomic_json(".estado/jobs.json", jobs[-500:])
        CANCEL[job["id"]] = threading.Event()
        QUEUE.put(job["id"])
        return job


def cancel_job(job_id):
    j = get_job(job_id)
    if j["status"] not in ("queued", "running"):
        return j
    CANCEL.setdefault(job_id, threading.Event()).set()
    return update_job(job_id, cancel_requested=True, message="Cancelación solicitada; esperando un punto seguro.")


def submit_media(asset_id, operation, options=None, project_id=None):
    require_current_engine()
    from .media_tools import validate_options
    a = asset(asset_id)
    normalized = validate_options(operation, options)
    project = get_project(project_id) if project_id else None
    processor_identity = None
    if operation == "remove_background_video":
        from .segmentation import capability
        available = capability(ROOT)
        if not available.get("available") or not available.get("fingerprint"):
            raise StudioError(available.get("reason", "El modelo local de segmentación está pendiente."), 409)
        processor_identity = available["fingerprint"]
    with JOB_LOCK:
        if project and get_project(project_id)["revision"] != project["revision"]:
            raise StudioError("El proyecto cambió durante la preparación; vuelve a solicitar la herramienta.", 409)
        if any(j.get("asset_id") == asset_id and j["status"] in ("queued", "running") for j in list_jobs()):
            raise StudioError("Ya hay una operación pendiente para este recurso.", 409)
        job = {"id": uid("j_"), "action": "media_process", "project_id": project_id, "asset_id": asset_id,
               "project_revision": project["revision"] if project else None,
               "source_sha256": a["sha256"], "operation": operation, "options": normalized, "status": "queued",
               "processor_fingerprints": engine_fingerprints(), "segmentation_fingerprint": processor_identity,
               "owner_pid": os.getpid(),
               "progress": 0, "message": "Herramienta local en cola CPU.", "created_at": now(), "updated_at": now()}
        atomic_json(".estado/jobs.json", (list_jobs() + [job])[-500:])
        CANCEL[job["id"]] = threading.Event()
        QUEUE.put(job["id"])
        return job


def submit_resource_review(asset_id, options=None):
    """Decode private observations in the same globally serialized worker."""
    require_current_engine()
    from .resource_review import validate_options,_directory
    _directory(asset_id)
    a=asset(asset_id);normalized=validate_options(a,options)
    if a.get('kind')=='image':normalized['duration']=None
    with JOB_LOCK:
        if any(j.get('asset_id')==asset_id and j['status'] in ('queued','running') for j in list_jobs()):
            raise StudioError('Ya hay una operación pendiente para este recurso.',409)
        job={'id':uid('j_'),'action':'asset_review_prepare','project_id':None,'asset_id':asset_id,
             'source_sha256':a['sha256'],'options':normalized,'status':'queued','owner_pid':os.getpid(),
             'processor_fingerprints':engine_fingerprints(),'progress':0,
             'message':'Preparación de muestras y secuencia en cola CPU; no implica observación.',
             'created_at':now(),'updated_at':now()}
        atomic_json('.estado/jobs.json',(list_jobs()+[job])[-500:]);CANCEL[job['id']]=threading.Event();QUEUE.put(job['id'])
        return job


def _enqueue_auxiliary(action, options, *, asset_id=None, entity=None):
    """Owner-scoped tasks use the same durable queue and global CPU lease."""
    require_current_engine()
    source = asset(asset_id) if asset_id else None
    with JOB_LOCK:
        if any(j.get('action') == action and j.get('asset_id') == asset_id and
               j.get('entity') == entity and j['status'] in ('queued', 'running') for j in list_jobs()):
            raise StudioError("Ya hay un trabajo pendiente para este recurso.", 409)
        job = {'id': uid('j_'), 'action': action, 'project_id': None, 'asset_id': asset_id,
               'entity': entity, 'options': options, 'source_sha256': source['sha256'] if source else None,
               'processor_fingerprints': engine_fingerprints(), 'status': 'queued', 'progress': 0,
               'owner_pid': os.getpid(), 'created_at': now(), 'updated_at': now(),
               'message': 'En cola privada; no modifica la edición ni aprueba recursos.'}
        atomic_json('.estado/jobs.json', (list_jobs() + [job])[-500:])
        CANCEL[job['id']] = threading.Event()
        QUEUE.put(job['id'])
        return job


def submit_audio_tracks(asset_id, options=None):
    from . import analysis, core
    value = {} if options is None else options
    if not isinstance(value, dict) or set(value) - {'start', 'duration', 'selected_index'}:
        raise StudioError("Opciones de pistas de audio desconocidas.")
    start = core.finite_number(value.get('start', 0), 'inicio de audio', 0, 7200)
    duration = core.finite_number(value.get('duration', 30), 'alcance de audio', .01, 30)
    selected = value.get('selected_index')
    if selected is not None:
        analysis.validate_audio_stream_index(selected)
    return _enqueue_auxiliary('audio_tracks', {'start': start, 'duration': duration,
                                             'selected_index': selected}, asset_id=asset_id)


def submit_brand_fetch(entity, options=None):
    import re
    from .brand_assets import ORIGINS
    value = {} if options is None else options
    if not isinstance(entity, str) or entity not in ORIGINS or not isinstance(value, dict) or set(value) - {'variant', 'expected_registry_digest'}:
        raise StudioError("Fuente o opciones de marca desconocidas.")
    variants = ORIGINS[entity]['variants']
    variant = value.get('variant', next(iter(variants), None))
    if not isinstance(variant, str) or variant not in variants:
        raise StudioError("Esta marca requiere importar un archivo propio.", 409)
    expected = value.get('expected_registry_digest')
    if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected)):
        raise StudioError("La revisión del registro requiere su SHA256.")
    return _enqueue_auxiliary('brand_fetch', {**value, 'variant': variant}, entity=entity)


def execute_auxiliary(job_id, job, event):
    try:
        if job.get('processor_fingerprints') != engine_fingerprints():
            raise StudioError("Cambió el motor desde la solicitud del trabajo.", 409)
        def progress(value, message=''):
            if get_job(job_id).get('cancel_requested'):
                event.set()
            if event.is_set():
                raise StudioError("Trabajo cancelado.", 409)
            update_job(job_id, progress=max(0, min(.99, float(value))), message=message)
        progress(.01, 'Procesando el recurso privado.')
        if job['action'] == 'audio_tracks':
            from .analysis import audio_tracks
            source = asset(job['asset_id'])
            path = confined(source['path'], must_exist=True)
            if digest(path) != job['source_sha256']:
                raise StudioError("El medio cambió desde la solicitud.", 409)
            result = audio_tracks(path, **job['options'], progress=progress, cancel=event)
        else:
            from .brand_assets import fetch
            result = fetch(job['entity'], job['options'])
        progress(.99, 'Resultado guardado sin aprobación editorial.')
        return update_job(job_id, status='completed', progress=1, result=result, finished_at=now())
    except Exception as error:
        return update_job(job_id, status='cancelled' if event.is_set() else 'failed',
                          error=str(error), message=str(error), finished_at=now())


def cloud_backup_status(project_id):
    from .core import WORKSPACE_MODE
    from .runtime import CODE_ROOT
    from .cloud_storage import CloudStorage
    if not WORKSPACE_MODE:
        raise StudioError('El respaldo remoto pertenece a un espacio SaaS privado.', 403)
    get_project(project_id)
    return CloudStorage(CODE_ROOT).outbox_status(ROOT.name, project_id)


def execute_cloud_backup(job_id, job, event):
    """Back up only this process's fixed workspace; never accept an owner ID."""
    try:
        from .runtime import CODE_ROOT
        from .cloud_storage import CloudStorage, status as cloud_status
        if job.get('processor_fingerprints') != engine_fingerprints():
            raise StudioError('El código cambió mientras esperaba el respaldo.', 409)
        if cloud_status(CODE_ROOT).get('revision') != job['cloud_config_revision']:
            raise StudioError('La configuración de nube cambió; vuelve a solicitar el respaldo.', 409)
        def progress(value, message=''):
            if get_job(job_id).get('cancel_requested'):
                event.set()
            if event.is_set():
                raise StudioError('Respaldo cancelado.', 409)
            update_job(job_id, progress=max(0, min(.99, float(value))), message=message)
        progress(.01, 'Preparando una copia íntegra del proyecto y sus recursos.')
        storage = CloudStorage(CODE_ROOT)
        options = job['options']
        staged = storage.enqueue_project(ROOT.name, job['project_id'], options['expected_revision'],
            expected_revision=options['expected_outbox_revision'], expected_etag=options['expected_etag'],
            include_outputs=options['include_outputs'],
            progress=lambda value, message='': progress(.05 + .35 * value, message), cancel=event)
        progress(.4, 'Enviando y verificando cada archivo antes de publicar el manifiesto.')
        result = storage.run_outbox(ROOT.name, job['project_id'], staged['revision'],
            progress=lambda value, message='': progress(.4 + .59 * value, message), cancel=event)
        if result.get('integrity_verified') is not True or result.get('pending') is not False:
            raise StudioError('El almacenamiento no confirmó la integridad del respaldo.', 409)
        live = result.get('live_remote_execution_verified') is True
        return update_job(job_id, status='completed', progress=1, result=result, finished_at=now(),
            message='Respaldo remoto verificado.' if live else 'Contrato de respaldo verificado con transporte de prueba; sin conexión remota acreditada.')
    except Exception as error:
        return update_job(job_id, status='cancelled' if event.is_set() else 'failed',
                          error=str(error), message=str(error), finished_at=now())


def execute_resource_review(job_id, job, event):
    try:
        from .resource_review import prepare
        if job.get('processor_fingerprints')!=engine_fingerprints():raise StudioError('El código de muestras cambió mientras esperaba.',409)
        a=asset(job['asset_id'])
        if digest(confined(a['path'],must_exist=True))!=job['source_sha256']:raise StudioError('El recurso cambió antes de preparar las muestras.',409)
        def progress(value,message=''):
            if get_job(job_id).get('cancel_requested'):event.set()
            if event.is_set():raise StudioError('Trabajo cancelado.',409)
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise StudioError('Progreso de muestras inválido.')
            update_job(job_id,progress=max(0,min(.99,value)),message=message)
        result=prepare(job['asset_id'],job['options'],progress=progress,cancel=event)
        if event.is_set() or get_job(job_id).get('cancel_requested'):
            return update_job(job_id,status='cancelled',message='Cancelado sin aprobar observación.',finished_at=now())
        return update_job(job_id,status='completed',progress=1,result=result,message='Muestras preparadas; observación y derechos pendientes.',finished_at=now())
    except Exception as error:
        return update_job(job_id,status='cancelled' if event.is_set() else 'failed',error=str(error),message=str(error),finished_at=now())


def execute_media(job_id, job, event):
    try:
        from .media_tools import process
        if job.get("processor_fingerprints") and job["processor_fingerprints"] != engine_fingerprints():
            raise StudioError("El código de la herramienta cambió mientras esperaba; vuelve a encolar el trabajo.", 409)
        if job["operation"] == "remove_background_video":
            from .segmentation import capability
            current = capability(ROOT)
            if not current.get("available") or current.get("fingerprint") != job.get("segmentation_fingerprint"):
                raise StudioError("El modelo/runtime de segmentación cambió mientras esperaba; vuelve a solicitarlo.", 409)
        a = asset(job["asset_id"])
        if digest(confined(a["path"], must_exist=True)) != job["source_sha256"]:
            raise StudioError("El recurso original cambió antes del procesamiento.", 409)
        update_job(job_id, progress=.1, message="Procesando con FFmpeg CPU; no se reemplaza el original.")
        def progress(value, message=""):
            if get_job(job_id).get("cancel_requested"):
                event.set()
            if event.is_set():
                raise StudioError("Trabajo cancelado.", 409)
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise StudioError("El procesador devolvió un progreso inválido.")
            update_job(job_id, progress=max(.1, min(.95, .1 + .85 * float(value))), message=message or "Procesando medio local…")
        result = (process(a, job["operation"], job["options"], ROOT, progress=progress, cancel=event)
                  if job["operation"] == "remove_background_video" else
                  process(a, job["operation"], job["options"], ROOT))
        if event.is_set() or get_job(job_id).get("cancel_requested"):
            return update_job(job_id, status="cancelled", message="Cancelado sin promover el derivado.", finished_at=now())
        if digest(confined(a["path"], must_exist=True)) != job["source_sha256"]:
            raise StudioError("El recurso cambió durante el procesamiento; resultado descartado.", 409)
        if result.get("path"):
            from pathlib import Path
            extension = Path(result["path"]).suffix
            derived = register_asset(confined(result["path"], must_exist=True), name=f"{job['operation']} · {Path(a['name']).stem}{extension}", metadata={"source": a["id"], "provenance": result.get("provenance", {}), "content": "Derivado técnico; inspección contextual pendiente."})
            result["asset"] = derived
            from .media_tools import bind_canonical
            result = bind_canonical(result, derived, ROOT)
            result["asset"] = derived
            if event.is_set() or get_job(job_id).get("cancel_requested"):
                return update_job(job_id, status="cancelled", result=result,
                                  message="Cancelado; el recurso técnico ya registrado se conserva sin aplicar a escenas.", finished_at=now())
            if job.get("project_id"):
                with LOCK:
                    live = get_project(job["project_id"])
                    if job.get("project_revision") is not None and live["revision"] != job["project_revision"]:
                        result["project_attachment"] = {"attached": False, "reason": "project_changed", "revision": live["revision"]}
                    else:
                        attach_asset(job["project_id"], derived["id"])
                        result["project_attachment"] = {"attached": True, "project_id": job["project_id"]}
        update_job(job_id, status="completed", progress=1, result=result, message="Operación completada; revisión de recurso pendiente.", finished_at=now())
    except Exception as error:
        cancelled = event.is_set() or get_job(job_id).get("cancel_requested")
        update_job(job_id, status="cancelled" if cancelled else "failed", error=None if cancelled else str(error),
                   details=getattr(error, "details", None), message="Cancelado sin aplicar el derivado." if cancelled else str(error), finished_at=now())


def execute(job_id):
    """Serialize CPU work across HTTP, standalone CLI and MCP processes."""
    current = get_job(job_id)
    if current["status"] != "queued":
        return current
    if getattr(LOCK.local, "depth", 0) or getattr(CPU_ACTIVE, "active", False):
        raise StudioError("Ejecuta el trabajo fuera de transacciones y de otro trabajo activo del procesador.", 409)
    event = CANCEL.setdefault(job_id, threading.Event())
    with _cpu_lease() as lease:
        while True:
            current = get_job(job_id)
            if current["status"] != "queued":
                return current
            if current.get("cancel_requested"):
                event.set()
            if event.is_set():
                return update_job(job_id, status="cancelled", message="Cancelado antes de ocupar el worker CPU.")
            try:
                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.05)
        try:
            # A second worker may have waited for the same queued job. Never
            # overwrite completed/failed results or execute a job twice.
            current = get_job(job_id)
            if current["status"] != "queued":
                return current
            CPU_ACTIVE.active = True
            return _execute(job_id)
        finally:
            CPU_ACTIVE.active = False
            fcntl.flock(lease.fileno(), fcntl.LOCK_UN)


def execute_pipeline(job_id, job, event, progress):
    from . import pipeline
    project_id = job['project_id']
    if job['action'] == 'pipeline':
        pipeline.create(project_id, job['options'])
    else:
        current = pipeline.status(project_id)
        if current['generation'] != job['options']['generation']:
            raise StudioError("La generación cambió mientras el trabajo esperaba.", 409)
        if job['action'] == 'pipeline_restart':
            pipeline.create(project_id, job['options']['options'], restart=True)
    expected_generation = pipeline.status(project_id)['generation']

    def commit(draft, expected_revision):
        if event.is_set():
            raise StudioError("Pipeline cancelado antes de guardar.", 409)
        return save_project(project_id, draft, expected=expected_revision, action='pipeline_compiled')

    def render_draft(project, seconds, report, cancelled):
        baseline = editorial_digest(project)
        pipeline.validate_pipeline_receipt(project)
        check_render_authorization(project, seconds, True)
        check = validate_project(project, seconds=seconds, strict=False)
        if not check['valid']:
            raise StudioError("El completo técnico no supera sus requisitos actuales.", 409, check)
        if project['settings'].get('engine', 'native') == 'hyperframes':
            from .hyperframes import render
        else:
            from .render import render
        generation = project['pipeline']['generation']
        output = confined(f"projects/{project_id}/pipeline_{generation}_draft.mp4")
        receipt = render(project, ROOT, output, seconds=seconds, progress=report, cancel=cancelled)
        if cancelled.is_set():
            raise StudioError("Cancelado después del render; sin promover el archivo.", 409)
        receipt.update(path=relative(output), url='/api/files/' + relative(output), at=now(),
                       editorial_digest=baseline, approved=False, production_conformant=False,
                       mode='pipeline_full_technical_draft')
        with LOCK:
            live = get_project(project_id)
            if live['revision'] != project['revision'] or editorial_digest(live) != baseline:
                raise StudioError("La edición cambió durante el completo; el archivo queda sin aplicar.", 409)
            live['renders'] = (live.get('renders', []) + [receipt])[-10:]
            live['review'] = {}
            live.pop('full_authorization', None)
            live['stage'] = 'technical_export_unapproved'
            saved = save_project(project_id, live, expected=project['revision'], action='rendered')
            write_manifest(saved, receipt)
            receipt['project_revision'] = saved['revision']
        return receipt

    def export_draft(project, receipt):
        live = get_project(project_id)
        if live['revision'] != receipt.get('project_revision') or editorial_digest(live) != receipt['editorial_digest']:
            raise StudioError("El proyecto cambió antes de empaquetar el editable.", 409)
        result = export_bundle(project_id)
        return {**result, 'project_id': project_id, 'project_revision': live['revision'],
                'approved': False, 'production_conformant': False}

    try:
        result = pipeline.resume(project_id, commit=commit, render=render_draft, export=export_draft,
                                 progress=progress, cancel=event)
    except Exception:
        # A persistent cancellation can originate from pipeline_cancel while
        # the queue's Event is still unset. Preserve its real classification.
        try:
            interrupted = pipeline.status(project_id)
            if interrupted['generation'] == expected_generation and interrupted['status'] == 'cancelled':
                event.set()
        except Exception:
            pass
        raise
    waiting = result['status'].startswith('waiting_')
    return update_job(job_id, status='completed', progress=1, result=result, finished_at=now(),
                      message='Pipeline preparado; esperando dirección externa real.' if waiting else
                              'Borrador completo y editable verificados; revisión editorial pendiente.')


def _execute(job_id):
    job = get_job(job_id)
    event = CANCEL.setdefault(job_id, threading.Event())
    if event.is_set():
        return update_job(job_id, status="cancelled", message="Cancelado antes de iniciar.")
    try:
        require_current_engine()
    except StudioError as error:
        return update_job(job_id, status="failed", error=str(error), message=str(error), finished_at=now())
    update_job(job_id, status="running", owner_pid=os.getpid(), started_at=now(), progress=.01)
    if job["action"] == "media_process":
        return execute_media(job_id, job, event)
    if job['action']=='asset_review_prepare':
        return execute_resource_review(job_id,job,event)
    if job['action'] in ('audio_tracks', 'brand_fetch'):
        return execute_auxiliary(job_id, job, event)
    if job['action'] == 'cloud_backup':
        return execute_cloud_backup(job_id, job, event)
    p = get_project(job["project_id"])
    baseline_digest = editorial_digest(p)
    base_revision = p["revision"]
    if job["revision"] != base_revision:
        return update_job(job_id, status="failed", error="La cronología cambió mientras esperaba. Vuelve a lanzar la tarea.")
    def progress(value, message=""):
        if get_job(job_id).get("cancel_requested"):
            event.set()
        update_job(job_id, progress=max(0, min(1, float(value))), message=message)
        if event.is_set():
            raise StudioError("Trabajo cancelado.", 409)
    try:
        if job['action'] in ('pipeline', 'pipeline_resume', 'pipeline_restart'):
            return execute_pipeline(job_id, job, event, progress)
        elif job['action']=='ivan_prepare':
            from .automation import ivan_prepare
            result=ivan_prepare(p,job['options'],progress,event)
            return update_job(job_id,status='completed',progress=1,result=result,finished_at=now(),message='Contexto ASR/tracking real preparado para dirección externa; sin llamada API ni aprobación.')
        elif job['action'] in ('auto_ivan','ivan_apply_plan'):
            from .automation import run,ivan_apply_plan
            computed=(run(p,job['options'],progress,event) if job['action']=='auto_ivan' else ivan_apply_plan(p,job['options'],progress,event))
            if event.is_set():raise StudioError('Automatización cancelada.',409)
            with LOCK:
                live=get_project(p['id'])
                if live['revision']!=base_revision or editorial_digest(live)!=baseline_digest:
                    raise StudioError('El proyecto cambió durante la inferencia; no se aplica el plan.',409)
                saved=save_project(p['id'],computed['project'],expected=base_revision,action=job['action'])
            result={'project_id':saved['id'],'revision':saved['revision'],'stage':saved['stage'],'automation':computed['automation'],'approved':False,'preview_job_id':None}
            # Complete this job before enqueueing the next: submit forbids two
            # active jobs per project, and the worker releases CPU before it
            # dequeues the render. Never execute a nested renderer here.
            update_job(job_id,status='completed',progress=1,result=result,finished_at=now(),message='Plan IVAN editable guardado; preparando prueba técnica sin aprobación.')
            if not computed['plan_only'] and not event.is_set():
                try:
                    preview=submit(saved['id'],'render',{'seconds':computed['seconds'],'engine':'hyperframes','technical':True,'ivan_draft':True})
                    result['preview_job_id']=preview['id']
                except StudioError as error:
                    result['preview_pending_reason']=str(error)
            return update_job(job_id,result=result)
        elif job["action"] in ("analyze", "automate"):
            from .analysis import analyze_project, propose_storyboard
            p = analyze_project(p, job["options"], progress, event)
            if job["action"] == "automate":
                progress(.96, "Creando propuesta de storyboard; pendiente de dirección contextual.")
                p = propose_storyboard(p)
            if editorial_digest(get_project(p["id"])) != baseline_digest:
                raise StudioError("El proyecto o sus medios cambiaron durante el análisis; relanza desde entradas vigentes.", 409)
            saved = save_project(p["id"], p, expected=base_revision, action=job["action"])
            result = {"project_id": saved["id"], "revision": saved["revision"], "stage": saved["stage"]}
        elif job["action"] == "tracking":
            from .tracking import analyze_tracking
            result = analyze_tracking(p, job["options"], progress, event)
            with LOCK:
                live = get_project(p["id"])
                if live["revision"] != base_revision or editorial_digest(live) != baseline_digest:
                    raise StudioError("La edición cambió durante el tracking; se conservan medidas sin aplicarlas.", 409)
                live["tracking"] = result
                live["stage"] = "tracking_review_pending"
                save_project(p["id"], live, action="tracking_measured")
        elif job["action"] == "design_snapshot":
            from .design_review import make_snapshot
            result = make_snapshot(p, job["options"], progress, event)
            with LOCK:
                live = get_project(p["id"])
                if live["revision"] != base_revision or editorial_digest(live) != baseline_digest:
                    raise StudioError("El diseño cambió durante su captura; relanza desde la revisión vigente.", 409)
                live.setdefault("design_snapshots", {})[job["options"]["scene_id"]] = result
                save_project(p["id"], live, action="design_captured")
        else:
            if job["options"].get("engine", p.get("settings", {}).get("engine", "native")) == "hyperframes":
                from .hyperframes import render
            else:
                from .render import render
            seconds = float(job["options"].get("seconds", 10))
            technical = job["options"].get("technical", False) is True
            if job['options'].get('ivan_draft') is True:
                from .automation import validate_draft_receipt
                validate_draft_receipt(p)
            check_render_authorization(p, seconds, technical, job['options'].get('draft_full', False))
            check = validate_project(p, seconds=seconds, strict=not technical)
            if not check["valid"]:
                raise StudioError("Cambió un requisito previo antes de ejecutar el render.", 409, check)
            output = confined(f"projects/{p['id']}/technical_preview.mp4" if technical else
                              f"projects/{p['id']}/ascendia_test_v5_10s.mp4" if seconds <= 10 else f"projects/{p['id']}/candidate.mp4")
            # An approved preview must never be overwritten during a new candidate render.
            if output.exists() and any(r.get("sha256") == p.get("review", {}).get("render_sha256") for r in p.get("renders", [])):
                output = confined(f"projects/{p['id']}/candidate_preview.mp4")
            result = render(p, ROOT, output, seconds=seconds, progress=progress, cancel=event)
            result.update(path=relative(output), url="/api/files/" + relative(output), at=now(), editorial_digest=baseline_digest, approved=False)
            result.update(mode="manual_full_technical_draft" if technical and job['options'].get('draft_full') is True else "ivan_draft_preview" if technical and job['options'].get('ivan_draft') is True else "technical_library" if technical else "ascendia_narrative", production_conformant=False)
            with LOCK:
                live = get_project(p["id"])
                if editorial_digest(live) != baseline_digest:
                    result["stale"] = True
                    raise StudioError("El montaje cambió durante el render. El candidato se conserva sin promover.", 409, result)
                live["renders"] = (live.get("renders", []) + [result])[-10:]
                live["review"] = {}
                live.pop("full_authorization", None)
                live["stage"] = "technical_export_unapproved" if technical else "preview_review_pending"
                save_project(p["id"], live, action="rendered")
                write_manifest(live, result)
        update_job(job_id, status="completed", progress=1, message="Completado; revisión editorial pendiente cuando corresponde.", result=result, finished_at=now())
        state(last_job=job_id, stage="review_pending" if job["action"] in ("render", "tracking", "design_snapshot") else "storyboard_pending")
    except Exception as error:
        status = "cancelled" if event.is_set() else "failed"
        details = getattr(error, "details", None)
        update_job(job_id, status=status, error=str(error), details=details, message=str(error), finished_at=now())
        log = confined(f".estado/logs/{job_id}.log")
        log.write_text(traceback.format_exc(), encoding="utf-8")


def worker():
    while True:
        job_id = QUEUE.get()
        try:
            execute(job_id)
        except Exception as error:
            try:
                update_job(job_id, status="failed", error=str(error))
            except Exception:
                pass
        finally:
            QUEUE.task_done()


def start_worker():
    global WORKER
    with JOB_LOCK:
        if WORKER and WORKER.is_alive():
            return
        for j in list_jobs():
            if j["status"] in ("queued", "running"):
                alive = False
                if j.get("owner_pid") and j["owner_pid"] != os.getpid():
                    try:
                        os.kill(j["owner_pid"], 0)
                        alive = True
                    except (OSError, ValueError):
                        pass
                if not alive:
                    update_job(j["id"], status="interrupted", message="El proceso anterior se detuvo. Relanza la tarea; no se repite automáticamente.")
        WORKER = threading.Thread(target=worker, name="studio-cpu-serial", daemon=True)
        WORKER.start()


def write_manifest(p, receipt=None):
    assets = {a["id"]: a for a in p["assets"]}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["archivo", "ruta_local", "fuente", "duracion", "contenido", "frase", "tiempo_previsto", "tiempo_realmente_usado", "verificacion"])
    used = (receipt or {}).get("used_assets", [])
    for s in p["timeline"]:
        a = assets.get(s.get("asset_id"))
        if not a:
            continue
        intervals = []
        for u in used:
            if not isinstance(u, dict) or u.get("asset_id", u.get("id")) != a["id"] or u.get("role") not in ("broll", "split"):
                continue
            lo, hi = max(s["start"], u.get("start", 0)), min(s["end"], u.get("end", 0), (receipt or {}).get("duration", 0))
            if hi > lo:
                intervals.append(f"{lo}–{hi}")
        actual = "; ".join(intervals) if intervals else "0; pendiente de evidencia del render"
        writer.writerow([a["name"], a["path"], a.get("metadata", {}).get("source", "local_supplied"), a["duration"], a.get("metadata", {}).get("content", "pending"), s.get("narration", s.get("title", "")), f"{s['start']}–{s['end']}", actual, "Decodificado e incorporado; verificar pertinencia visual" if intervals else "sin verificación de aparición"])
    path = confined(f"projects/{p['id']}/broll_manifest.csv")
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return path


def export_bundle(project_id):
    with LOCK:
        return _export_bundle(project_id)


def _export_bundle(project_id):
    from .analysis import subtitles
    p = get_project(project_id)
    validate_shape(p)
    p["fonts"] = {k: relative(confined(v)) for k, v in p.get("fonts", {}).items() if v}
    path = confined(f"exports/{project_id}_editable.zip")
    temp = confined(f".estado/tmp/{uid('export_')}.zip")
    files = {a["path"] for a in p["assets"]} | {v for v in p.get("fonts", {}).values() if v}
    for item in p["assets"]:
        notice = item.get("metadata", {}).get("font_notice")
        if item.get("kind") == "font" and notice:
            from .fonts import notice_file
            files.add(notice_file(item).relative_to(ROOT).as_posix())
    for item in p["assets"]:
        if digest(confined(item["path"], must_exist=True)) != item["sha256"]:
            raise StudioError("Un medio cambió; no se exporta un editable con hashes inválidos.", 409)
    file_hashes = {rel: (rel, digest(confined(rel, must_exist=True))) for rel in files}
    baseline = editorial_digest(p)
    manifest = write_manifest(p, p.get("renders", [])[-1] if p.get("renders") else None)
    motion_temp = confined(f".estado/tmp/{uid('motion_export_')}.zip")
    motion_sources = "not_rendered"
    packaged_approved = False
    try:
        receipt = p.get("renders", [])[-1] if p.get("renders") else {}
        if receipt.get("technical", {}).get("hyperframes"):
            from .hyperframes import verify_receipt
            if receipt.get("editorial_digest") == baseline and verify_receipt(receipt, ROOT):
                from .motion_bundle import write_bundle
                motion = write_bundle(receipt, ROOT, motion_temp)
                file_hashes["hyperframes_editable.zip"] = (relative(motion_temp), motion["sha256"])
                motion_sources = "included_verified_html_gsap"
            else:
                motion_sources = "render_not_current_regenerate_from_project"
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=2) as z:
            z.writestr("project.json", json.dumps(p, ensure_ascii=False, indent=2))
            z.writestr("transcript.srt", subtitles(p["transcript"]))
            z.writestr("transcript.vtt", subtitles(p["transcript"], "vtt"))
            z.write(manifest, "broll_manifest.csv")
            z.writestr("README.txt", "Proyecto editable Ascendia Studio. Conserva assets en sus rutas relativas. Código del editor: SOFTWARE/studio y SOFTWARE/web. Si existe hyperframes_editable.zip contiene HTML/GSAP de una ejecución vigente; sus licencias y fuentes permanecen separadas. Reabrir recupera el JSON; no ejecuta HTML importado ni hereda aprobaciones. Medios/fuentes conservan sus derechos originales; no reciben MIT. Manual canónico no duplicado. Revisión en movimiento y escucha siguen necesarias.\n")
            for rel in sorted(files):
                f = confined(rel, must_exist=True)
                z.write(f, relative(f))
            if motion_temp.is_file():
                z.write(motion_temp, "hyperframes_editable.zip")
            approved = p.get("approved_export")
            if approved and approval_is_current(p) and digest(confined(approved["path"], must_exist=True)) == approved["sha256"]:
                z.write(confined(approved["path"], must_exist=True), "approved_preview.mp4")
                file_hashes["approved_preview.mp4"] = (approved["path"], approved["sha256"])
                packaged_approved = True
        with zipfile.ZipFile(temp) as verification:
            from .bundles import _inspect
            _inspect(verification)
            if verification.testzip() is not None:
                raise StudioError("El editable no superó su verificación CRC.", 409)
            for rel, (live_path, expected_hash) in file_hashes.items():
                import hashlib
                computed = hashlib.sha256()
                with verification.open(rel) as entry:
                    for block in iter(lambda: entry.read(1024 * 1024), b""):
                        computed.update(block)
                if computed.hexdigest() != expected_hash or digest(confined(live_path, must_exist=True)) != expected_hash:
                    raise StudioError("Un recurso cambió durante el empaquetado; el editable anterior se conserva.", 409)
        if editorial_digest(p) != baseline or (packaged_approved and not approval_is_current(p)):
            raise StudioError("El proyecto, manual o aprobación cambió durante el empaquetado; el editable anterior se conserva.", 409)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
        motion_temp.unlink(missing_ok=True)
    return {"path": relative(path), "url": "/api/files/" + relative(path), "size": path.stat().st_size, "sha256": digest(path), "motion_sources": motion_sources, "verified_crc_and_sha256": True}


ROLES = {
    "director": {"depends": [], "purpose": "Leer manual completo; CLONE motion exclusivo, YO cámara/subs/split. El padre construye su biblioteca generativa CLONE; no ejecutar esa tarea independiente ni heredar aprobaciones. Para futuros crudos comprender narración y dirigir storyboard por frase."},
    "resources": {"depends": ["director"], "purpose": "Consultar bibliotecas dinámica/software; preseleccionar, ver clips y registrar selección/descarte con fuente, tramo, hash y evidencia."},
    "motion": {"depends": ["director", "resources"], "purpose": "CLONE motion exclusivo; diseño estático y comparación primero. Animar solo tras aprobación propia vigente, sin alterar geometría/fuentes/colores/elementos. Validar fidelidad visual, movimiento, ritmo y continuidad por separado. Registrar skills/catálogo/evidencia y recibos HyperFrames/GSAP actuales. No repetir prueba del padre, heredar su aprobación ni afirmar paridad por plantillas Pillow."},
    "audio": {"depends": ["director"], "purpose": "Preservar voz; elegir música, ducking y riser con culminación 2–6 s; escuchar y registrar evidencia real."},
    "qa": {"depends": ["resources", "motion", "audio"], "purpose": "Revisar render en movimiento, identidad, rostro/barbilla, texto, ortografía, recursos, sincronía y escuchar audio. No aprobar automáticamente."},
}
COMPONENT_ROLES = {
    "director": {"depends": [], "purpose": "Leer manual actual y SceneIR; comprobar entidades, acción, resultado y relación declarados contra el contenido. Registrar lo pendiente; el adaptador no genera ni verifica semántica por sí solo."},
    "resources": {"depends": ["director"], "purpose": "Usar tipografía/formas originales o gráficos declarados del catálogo. Sin b-roll, stock, videos, AGENT/EDIT ni fuente duplicada. Una declaración de autor no certifica derechos."},
    "motion": {"depends": ["director", "resources"], "purpose": "Editar el componente y sus acciones conectadas con HyperFrames/GSAP. Render técnico automático de hasta10s, sin pedir aprobación por componente. Conservar controles de datos y registrar fidelidad CLONE como pendiente hasta comparación real."},
    "audio": {"depends": ["director"], "purpose": "Conservar narración y audio existentes. Revisar sincronía real sin inventar alineación con SceneIR; métricas no equivalen a audición."},
    "qa": {"depends": ["resources", "motion", "audio"], "purpose": "Revisar componente en movimiento y comparar referencias autorizadas. Registrar geometría, tipografía, ritmo, continuidad y escucha con evidencia; conservar fallos/pendientes y no aprobar un reel."},
}


def tasks():
    return read_json(".estado/tasks.json", [])


def create_tasks(project_id):
    p = get_project(project_id)
    with JOB_LOCK:
        existing = tasks()
        current_digest = editorial_digest(p)
        active = [t for t in existing if t["project_id"] == project_id and t["status"] in ("pending", "claimed")]
        if active and all(t.get("editorial_digest") == current_digest and t.get("manual") == manual_fingerprints() for t in active):
            return active
        for t in active:
            t.update(status="stale", invalidated_at=now())
        batch = uid("w_")
        component = p.get("mode") == "scene_ir_component"
        roles = COMPONENT_ROLES if component else ROLES
        new = [{"id": uid("t_"), "workflow_id": batch, "project_id": project_id, "role": role, "depends": spec["depends"],
                "purpose": spec["purpose"], "status": "pending", "artifact": f"projects/{project_id}/agents/{role}.json",
                "created_at": now(), "editorial_digest": editorial_digest(p), "manual": manual_fingerprints(), "constraints": {"scope": str(ROOT), "gpu": False, "preview_seconds": 10, "human_approval": not component, "mode": "scene_ir_component" if component else "reel", "qc": "pending", "auto_editorial_approval": False}}
               for role, spec in roles.items()]
        atomic_json(".estado/tasks.json", existing + new)
        return new


def claim_task(role, agent):
    if role not in ROLES or not str(agent).strip():
        raise StudioError("Rol o agente inválido.")
    with JOB_LOCK:
        all_tasks = tasks()
        for t in all_tasks:
            if t["role"] != role or t["status"] != "pending":
                continue
            completed = {x["role"] for x in all_tasks if x["workflow_id"] == t["workflow_id"] and x["status"] == "done"}
            if not set(t["depends"]).issubset(completed):
                continue
            t.update(status="claimed", agent=str(agent)[:200], lease=uid("lease_"), claimed_at=now())
            atomic_json(".estado/tasks.json", all_tasks)
            return t
    return {"task": None, "message": "No hay tareas disponibles de este rol; revisa dependencias."}


def finish_task(task_id, lease, result):
    with JOB_LOCK:
        all_tasks = tasks()
        t = next((x for x in all_tasks if x["id"] == task_id), None)
        if not t or t.get("lease") != lease or t["status"] != "claimed":
            raise StudioError("Lease de tarea inválido o tarea no reclamada.", 409)
        if t.get("editorial_digest") != editorial_digest(get_project(t["project_id"])) or t.get("manual") != manual_fingerprints():
            raise StudioError("El proyecto o el manual cambió desde la asignación: renueva el workflow.", 409)
        if not isinstance(result, dict) or not result.get("observations") or not result.get("evidence"):
            raise StudioError("La tarea requiere observaciones y evidencia; no basta un estado aprobado.")
        for evidence in result["evidence"]:
            if not isinstance(evidence, str):
                raise StudioError("Cada evidencia debe ser una ruta local a un archivo existente.")
            confined(evidence, must_exist=True)
        atomic_json(t["artifact"], {"task_id": task_id, "agent": t["agent"], "role": t["role"], "at": now(), "result": result})
        t.update(status="done", finished_at=now(), result_path=t["artifact"])
        atomic_json(".estado/tasks.json", all_tasks)
        return t


def release_task(task_id, lease):
    with JOB_LOCK:
        all_tasks = tasks()
        t = next((x for x in all_tasks if x["id"] == task_id), None)
        if not t or t.get("lease") != lease or t["status"] != "claimed":
            raise StudioError("Lease de tarea inválido o tarea no reclamada.", 409)
        t.update(status="pending", released_at=now())
        t.pop("lease", None)
        t.pop("agent", None)
        atomic_json(".estado/tasks.json", all_tasks)
        return t
