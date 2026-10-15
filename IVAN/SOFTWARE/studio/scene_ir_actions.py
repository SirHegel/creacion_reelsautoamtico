"""Transactional entry points for data-only SceneIR proposals."""
from __future__ import annotations

from . import core


def preview(project_id, document):
    from .scene_ir import compile_scene_ir
    with core.LOCK:
        project = compile_scene_ir(core.get_project(project_id), document)
        core.validate_shape(project)
        validation = core.validate_project(project, seconds=project["timeline"][0]["end"], strict=False)
        return {"project": project, "validation": validation, "can_apply": True,
                "warnings": ["Aplicar reemplaza la cronología por una composición libre editable.",
                             "El origen semántico es declarado; fidelidad CLONE, derechos y revisión perceptiva siguen pendientes.",
                             "El render de este componente es técnico y no aprueba un reel."]}


def apply(project_id, document, expected_revision):
    from .scene_ir import compile_scene_ir
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
        raise core.StudioError("expected_revision debe ser la revisión entera vigente.")
    with core.LOCK:
        old = core.get_project(project_id)
        if old["revision"] != expected_revision:
            raise core.StudioError("El proyecto cambió desde la propuesta SceneIR; vuelve a previsualizar.", 409)
        project = compile_scene_ir(old, document)
        project["renders"] = old.get("renders", [])
        project["stage"] = "scene_ir_component_qc_pending"
        return core.save_project(project_id, project, expected=expected_revision, action="scene_ir_applied")
