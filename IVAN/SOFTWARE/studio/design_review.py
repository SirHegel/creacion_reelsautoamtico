"""Static design evidence and explicit approval tied to current bytes."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageEnhance

from . import core, design


def _scene(project, scene_id):
    scene = next((s for s in project.get("timeline", []) if s.get("id") == scene_id), None)
    if not scene or scene.get("template") != "custom":
        raise core.StudioError("Elige una escena de composición libre.")
    design.validate_design(scene, (project["settings"]["width"], project["settings"]["height"]))
    return scene


def make_snapshot(project, options, progress=None, cancel=None):
    scene = _scene(project, options["scene_id"])
    before = core.editorial_digest(project)
    base_hash = design.design_digest(scene, project)
    output = core.confined(f"projects/{project['id']}/designs/{scene['id']}_candidate.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if project["settings"].get("engine", "native") == "hyperframes":
        from .hyperframes import snapshot_design
        result = snapshot_design(project, scene["id"], core.ROOT, output, progress, cancel)
    else:
        from .render import _run, _tool, _input, RenderCancelled, _cancelled, _decode, split_height
        frames = {}
        media = {a["id"]: a for a in project.get("assets", [])}
        with tempfile.TemporaryDirectory(prefix="static_", dir=core.confined(".estado/tmp")) as temporary:
            for i, el in enumerate(scene["motion_design"]["elements"]):
                if el["type"] != "media":
                    continue
                item = media.get(el["asset_id"])
                source = media.get(project.get("source"))
                catalog = {a["id"]: a for a in core.assets()} if core.ROOT == Path(__file__).resolve().parents[1] else media
                if not item or core.source_related(item, source, catalog):
                    raise core.StudioError("El diseño requiere un medio registrado distinto del crudo.")
                path = core.confined(item["path"], must_exist=True)
                if core.content_hash(path) != item["sha256"]:
                    raise core.StudioError("Un recurso del diseño cambió.", 409)
                if item.get("kind") == "image":
                    with Image.open(path) as image:
                        frames[el["id"]] = image.convert("RGBA").copy()
                elif item.get("kind") in ("video", "broll"):
                    target = Path(temporary) / f"media_{i}.png"
                    _run([_tool("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1", "-ss", str(el.get("source_in", 0))] + _input(path) + ["-frames:v", "1", "-threads", "1", str(target)], core.ROOT, cancel)
                    with Image.open(target) as image:
                        frames[el["id"]] = image.convert("RGBA").copy()
                else:
                    raise core.StudioError("El elemento estático requiere una imagen o un video.")
            from .fonts import font_assets
            width, height = project["settings"]["width"], project["settings"]["height"]
            upper = split_height(height, project['settings'].get('split_motion_ratio', .55)) if scene.get("type") == "split" else height
            picture = design.draw_design(scene, 0, (width, upper), project["fonts"], frames, animate=False, root=core.ROOT, font_assets=font_assets(project))
            if scene.get("type") == "split":
                source = media.get(project.get("source"))
                if not source or core.content_hash(source["path"]) != source["sha256"]:
                    raise core.StudioError("El crudo del split falta o cambió.", 409)
                target = Path(temporary) / "camera.rgb"
                _decode({**source, "local": core.confined(source["path"], must_exist=True)},
                        (width, height-upper), scene.get("source_in", scene["start"]), 1,
                        project["settings"]["fps"], target, core.ROOT, scene, cancel)
                lower = Image.frombytes("RGB", (width, height-upper), target.read_bytes())
                canvas = Image.new("RGB", (width, height))
                canvas.paste(picture.convert("RGB"), (0, 0))
                canvas.paste(lower, (0, upper))
                picture = canvas
            # Match native grading of the base before its animation/overlays.
            picture = picture.convert("RGB")
            effects = scene.get("effects", {})
            brightness = core.finite_number(effects.get("brightness", 0), "brillo", -1, 1)
            if brightness:
                shift = round(brightness * 255)
                picture = picture.point(lambda channel: min(255, max(0, channel + shift)))
            for key, enhancer in (("contrast", ImageEnhance.Contrast), ("saturation", ImageEnhance.Color)):
                factor = core.finite_number(effects.get(key, 1), key, 0, 3)
                if factor != 1:
                    picture = enhancer(picture).enhance(factor)
            if _cancelled(cancel):
                raise RenderCancelled("Captura estática cancelada.")
            temp = Path(temporary) / "candidate.png"
            picture.save(temp)
            if core.editorial_digest(project) != before:
                raise core.StudioError("Una entrada cambió durante la captura del diseño.", 409)
            os.replace(temp, output)
        result = {"path": core.relative(output), "size": output.stat().st_size, "sha256": core.content_hash(output), "width": picture.width, "height": picture.height,
                  "technical": {"engine": "Pillow static design", "static": True, "editorial_approved": False}}
    if core.editorial_digest(project) != before:
        raise core.StudioError("Una entrada cambió durante la captura del diseño.", 409)
    result.update(scene_id=scene["id"], design_digest=base_hash, at=core.now(), manual=core.manual_fingerprints(), engine_code=core.engine_fingerprints(), approved=False,
                  url="/api/files/" + result["path"])
    return result


def current_snapshot(project, scene):
    snapshot = project.get("design_snapshots", {}).get(scene["id"])
    if not isinstance(snapshot, dict) or snapshot.get("design_digest") != design.design_digest(scene, project):
        raise core.StudioError("Genera una captura del diseño vigente antes de revisarlo.", 409)
    if snapshot.get("manual") != core.manual_fingerprints() or snapshot.get("engine_code") != core.engine_fingerprints():
        raise core.StudioError("Manual o código cambiaron desde la captura; vuelve a generarla.", 409)
    if core.content_hash(snapshot["path"]) != snapshot.get("sha256"):
        raise core.StudioError("La captura estática cambió.", 409)
    return snapshot


def record_review(project_id, data):
    if not isinstance(data, dict) or not isinstance(data.get("approve_design"), bool):
        raise core.StudioError("La revisión requiere approve_design booleano explícito.")
    with core.LOCK:
        project = core.get_project(project_id)
        scene = _scene(project, data.get("scene_id"))
        snapshot = current_snapshot(project, scene)
        if data.get("expected_sha256") != snapshot["sha256"]:
            raise core.StudioError("La revisión debe identificar el SHA de la captura vista.", 409)
        reviewer, notes = data.get("reviewer"), data.get("notes")
        if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(notes, str) or not notes.strip():
            raise core.StudioError("Registra revisor y observaciones concretas del diseño.")
        review = {"at": core.now(), "reviewer": reviewer[:200], "notes": notes[:10000], "approved": False,
                  "design_digest": snapshot["design_digest"], "snapshot_sha256": snapshot["sha256"], "manual": snapshot["manual"], "engine_code": snapshot["engine_code"]}
        if data["approve_design"]:
            text = data.get("approval_text")
            if not isinstance(text, str) or not text.strip():
                raise core.StudioError("Incluye la indicación explícita de aprobación del usuario; comentarios técnicos no aprueban el diseño.")
            reference = next((a for a in project["assets"] if a["id"] == data.get("reference_asset_id")), None)
            if not reference or reference.get("kind") != "image":
                raise core.StudioError("La aprobación necesita un fotograma de referencia importado como imagen.")
            ref_time = core.finite_number(data.get("reference_time"), "tiempo de referencia", 0, 86400)
            name = data.get("reference_name")
            if not isinstance(name, str) or not name.strip():
                raise core.StudioError("Identifica la referencia comparada.")
            dimensions = ("composition", "typography", "spacing", "color", "depth")
            checks = data.get("checks")
            if not isinstance(checks, dict) or not all(checks.get(key) is True for key in dimensions):
                raise core.StudioError("La aprobación requiere comparación de composición, tipografía, espaciado, color y profundidad.")
            reference_hash = core.content_hash(reference["path"])
            if reference_hash != reference["sha256"]:
                raise core.StudioError("La referencia cambió.", 409)
            approved = core.confined(f"projects/{project_id}/designs/{scene['id']}_approved.png")
            with tempfile.TemporaryDirectory(prefix="design_approval_", dir=core.confined(".estado/tmp")) as temporary:
                candidate = Path(temporary) / "approved.png"
                previous_image = Path(temporary) / "previous.png"
                previous_project = Path(temporary) / "project.json"
                had_previous_image = approved.is_file()
                if had_previous_image:
                    shutil.copyfile(approved, previous_image)
                shutil.copyfile(core.project_path(project_id), previous_project)
                shutil.copyfile(core.confined(snapshot["path"], must_exist=True), candidate)
                if core.digest(candidate) != snapshot["sha256"]:
                    raise core.StudioError("La captura cambió mientras se registraba su aprobación.", 409)
                current_snapshot(project, scene)
                if core.content_hash(reference["path"]) != reference_hash:
                    raise core.StudioError("La referencia cambió durante la revisión.", 409)
                review.update(approved=True, approval_text=text[:10000], reference_name=name[:200], reference_time=ref_time,
                              reference_asset_id=reference["id"], reference_sha256=reference_hash, approved_path=core.relative(approved),
                              dimensions={key: True for key in dimensions})
                project.setdefault("design_reviews", {})[scene["id"]] = review
                project["review"] = {}
                project.pop("full_authorization", None)
                try:
                    os.replace(candidate, approved)
                    saved = core.save_project(project_id, project, action="design_reviewed")
                    current_snapshot(saved, _scene(saved, scene["id"]))
                    if core.content_hash(approved) != snapshot["sha256"]:
                        raise core.StudioError("El PNG aprobado cambió durante el guardado.", 409)
                    if core.content_hash(reference["path"]) != reference_hash:
                        raise core.StudioError("La referencia cambió durante la revisión.", 409)
                    return saved
                except BaseException:
                    if had_previous_image:
                        os.replace(previous_image, approved)
                    elif approved.exists():
                        approved.unlink()
                    os.replace(previous_project, core.project_path(project_id))
                    raise
        project.setdefault("design_reviews", {})[scene["id"]] = review
        project["review"] = {}
        project.pop("full_authorization", None)
        return core.save_project(project_id, project, action="design_reviewed")


def production_errors(project):
    errors = []
    for scene in project.get("timeline", []):
        if scene.get("type") != "motion" and not (scene.get("type") == "split" and scene.get("template") == "custom"):
            continue
        if scene.get("template") != "custom":
            errors.append(f"{scene['id']}: las plantillas raster no acreditan motion ASCENDIA; diseña una composición libre.")
            continue
        review = project.get("design_reviews", {}).get(scene["id"], {})
        try:
            snapshot = current_snapshot(project, scene)
            if not review.get("approved") or review.get("design_digest") != snapshot["design_digest"] or review.get("snapshot_sha256") != snapshot["sha256"]:
                raise core.StudioError("diseño vigente sin aprobación explícita")
            if review.get("manual") != snapshot["manual"] or review.get("engine_code") != snapshot["engine_code"]:
                raise core.StudioError("la aprobación anterior no autoriza esta revisión")
            if review.get("reference_name") != "CLONE" or abs(review.get("reference_time", -1) - core.POLICY["clone_static_reference_time"]) > .01:
                raise core.StudioError("falta comparación con el fotograma CLONE vigente")
            reference = next(a for a in project["assets"] if a["id"] == review["reference_asset_id"])
            if core.content_hash(reference["path"]) != review.get("reference_sha256") or core.content_hash(review["approved_path"]) != snapshot["sha256"]:
                raise core.StudioError("cambió el diseño aprobado o su referencia")
        except (core.StudioError, KeyError, TypeError, StopIteration, OSError) as error:
            errors.append(f"{scene['id']}: {error}.")
    return errors
