"""Project-only branding for portable ZIPs; imported rights are never trusted.

This module does not edit the account branding or license registry. The caller
verifies all ZIP members before registering media and seals only a new project.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from . import branding, core, fonts

ROLES = ("primary", "accent")
COLORS = {"background", "text", "accent", "muted"}
REFERENCES = ["Sequel Sans Bold Disp", "Scholar Italic"]
SNAPSHOT_FIELDS = {"id", "revision", "name", "colors", "fonts", "logo_asset_id",
                   "instructions", "language", "base", "base_rules_sha256",
                   "font_override_explicit", "original_reference_fonts", "editorial_approved"}
FACE_FIELDS = {"asset_id", "path", "sha256", "family", "style", "license"}
LICENSE_FIELDS = {"status", "label", "source_url", "notice_path", "notice_url", "notice_sha256", "reserved_names"}
SHA = re.compile(r"[a-f0-9]{64}")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,100}")


def _fail(message, status=400):
    raise core.StudioError(message, status)


def _text(value, name, limit, *, empty=False):
    if (not isinstance(value, str) or len(value) > limit or
            (not empty and not value.strip()) or
            any(ord(c) < 32 and c not in "\n\t" for c in value)):
        _fail("Texto inválido en la marca importada: " + name)
    return value


def _font_path(value):
    if not isinstance(value, str) or "\\" in value:
        _fail("Ruta de fuente de marca inválida.", 403)
    p = PurePosixPath(value)
    if (p.is_absolute() or p.as_posix() != value or len(p.parts) < 3 or
            p.parts[:2] != ("assets", "fonts") or p.suffix.lower() not in {".ttf", ".otf"} or
            any(x in {".", "..", ".estado"} or ":" in x for x in p.parts)):
        _fail("La fuente de marca debe pertenecer al ZIP en assets/fonts.", 403)
    return value


def _license(value, item):
    if not isinstance(value, dict) or set(value) - LICENSE_FIELDS:
        _fail("La licencia tipográfica importada contiene campos incorrectos.")
    for key, val in value.items():
        if key == "reserved_names":
            if not isinstance(val, list) or len(val) > 32:
                _fail("Nombres reservados inválidos.")
            for name in val:
                _text(name, "reserved_names", 200)
        elif val is not None:
            _text(val, "license." + key, 2048)
    notice = (item.get("metadata") or {}).get("font_notice")
    if value.get("notice_path") is not None:
        if not isinstance(notice, dict) or value["notice_path"] != notice.get("path"):
            _fail("El aviso de la marca no coincide con el archivo tipográfico incluido.", 403)
    if value.get("notice_sha256") is not None:
        if not isinstance(notice, dict) or value["notice_sha256"] != notice.get("sha256"):
            _fail("El SHA del aviso de marca no coincide con el ZIP.")


def prepare(imported):
    """Validate claims without file writes; return the project-only import plan."""
    if not core.WORKSPACE_MODE:
        return None
    if not isinstance(imported.get("fonts"), dict) or set(imported["fonts"]) != set(ROLES):
        _fail("El editable requiere exactamente dos roles tipográficos.")
    style = imported.get("style", {})
    if not isinstance(style, dict):
        _fail("El estilo importado requiere un objeto.")
    profile = style.get("branding")
    if profile is None:
        # Appearance fallback is explicit; font selection stays the actual
        # Sequel/Scholar pair bundled by a legacy export.
        own = branding.snapshot(core.ROOT)
        return {"appearance": "workspace_fallback", "profile": {k: copy.deepcopy(own[k]) for k in
                ("revision", "name", "colors", "instructions", "language")},
                "roles": {"primary": "sequel", "accent": "scholar"}, "logo_asset_id": None}
    if not isinstance(profile, dict) or set(profile) - (SNAPSHOT_FIELDS | {"bundle_import"}) or not SNAPSHOT_FIELDS <= set(profile):
        _fail("La marca del editable contiene campos incorrectos.")
    if (profile["id"] != "ivan_branding" or profile["base"] != "ivan_yo_clone" or
            profile["font_override_explicit"] is not True or
            profile["original_reference_fonts"] != REFERENCES or
            type(profile["editorial_approved"]) is not bool or
            type(profile["revision"]) is not int or not 1 <= profile["revision"] <= 2147483647):
        _fail("El snapshot de marca no corresponde al contrato IVAN.")
    _text(profile["name"], "name", 120)
    _text(profile["instructions"], "instructions", 8000, empty=True)
    if not isinstance(profile["language"], str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?", profile["language"]):
        _fail("Idioma de marca inválido.")
    if (not isinstance(profile["colors"], dict) or set(profile["colors"]) != COLORS or
            any(not isinstance(c, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", c) for c in profile["colors"].values())):
        _fail("La marca requiere cuatro colores hexadecimales reales.")
    if not isinstance(profile["base_rules_sha256"], str) or not SHA.fullmatch(profile["base_rules_sha256"]):
        _fail("La marca requiere SHA completo de su perfil de origen.")
    trace = profile.get("bundle_import")
    if trace is not None:
        if (not isinstance(trace, dict) or set(trace) != {"source", "appearance", "permissions", "source_base_rules_sha256"} or
                trace.get("source") != "editable_bundle" or trace.get("appearance") not in {"bundled_snapshot", "workspace_fallback"} or
                trace.get("permissions") != "pending_reinspection" or not isinstance(trace.get("source_base_rules_sha256"), str) or
                not SHA.fullmatch(trace["source_base_rules_sha256"])):
            _fail("La procedencia de la marca importada es inválida.")
    faces = profile["fonts"]
    if not isinstance(faces, dict) or set(faces) != set(ROLES):
        _fail("La marca requiere exactamente dos roles tipográficos.")
    rows = {a.get("id"): a for a in imported.get("assets", []) if isinstance(a, dict)}
    roles = {}
    for role in ROLES:
        face = faces[role]
        if not isinstance(face, dict) or set(face) != FACE_FIELDS:
            _fail("Descriptor de fuente de marca inválido.")
        if not isinstance(face["asset_id"], str) or not IDENTIFIER.fullmatch(face["asset_id"]):
            _fail("ID de fuente de marca inválido.")
        item = rows.get(face["asset_id"])
        path = _font_path(face["path"])
        if (not item or item.get("kind") != "font" or item.get("path") != path or
                imported.get("fonts", {}).get(role) != path or item.get("sha256") != face["sha256"]):
            _fail("La fuente de la marca no coincide con el recurso incluido.")
        if not isinstance(face["sha256"], str) or not SHA.fullmatch(face["sha256"]):
            _fail("SHA de fuente de marca inválido.")
        _text(face["family"], "family", 200)
        _text(face["style"], "style", 200)
        _license(face["license"], item)
        roles[role] = copy.deepcopy(face)
    logo = profile["logo_asset_id"]
    if logo is not None and (not isinstance(logo, str) or not IDENTIFIER.fullmatch(logo) or
                             rows.get(logo, {}).get("kind") != "image"):
        _fail("El logo de marca requiere una imagen incluida en el editable.")
    return {"appearance": "bundled_snapshot", "profile": copy.deepcopy(profile), "roles": roles, "logo_asset_id": logo}


def verify_materialized(plan, specs):
    """Check SFNT identities and actual image decoding before catalog writes."""
    if plan is None:
        return
    for role, expected in plan["roles"].items():
        if isinstance(expected, str):
            continue  # The legacy role check runs in bundles._materialize.
        spec = specs.get(expected["path"], {})
        info = spec.get("font_info", {})
        if any(info.get(k) != expected[k] for k in ("sha256", "family", "style")):
            _fail("La identidad SFNT real no coincide con la fuente declarada por la marca.")
    if plan["logo_asset_id"]:
        from PIL import Image
        spec = next(s for s in specs.values() if (s.get("asset") or {}).get("id") == plan["logo_asset_id"])
        try:
            with Image.open(spec["local"]) as picture:
                picture.verify()
        except (OSError, ValueError) as error:
            raise core.StudioError("El logo de marca no es una imagen real.") from error


def _record_path(project_id):
    if not isinstance(project_id, str) or not re.fullmatch(r"p_[A-Za-z0-9_-]{1,100}", project_id):
        _fail("ID de proyecto inválido para la marca.", 403)
    root = Path(core.ROOT).resolve()
    path = root / ".estado/project_branding" / (project_id + ".json")
    if path.resolve() != path or any(p.is_symlink() for p in (root / ".estado", path.parent, path)):
        _fail("El registro de marca no admite enlaces o rutas alternativas.", 403)
    return path


def seal_and_save(project, plan, registered, imported_fonts, mapped):
    """Seal a new import under StoreLock; undo private/project bytes on failure."""
    if not core.WORKSPACE_MODE or plan is None:
        _fail("La importación de marca requiere un workspace privado.", 409)
    with core.LOCK:
        old = core.get_project(project["id"])
        if old["revision"] != 1 or len(old.get("history", [])) != 1 or old["history"][0].get("action") != "created":
            _fail("La marca de un ZIP solo puede sellarse en un proyecto nuevo.", 409)
        value = plan["profile"]
        faces = {}
        for role in ROLES:
            item = registered[imported_fonts[role]]
            canonical = core.asset(item["id"])
            info = fonts.validate_asset_font(canonical, core.ROOT)
            if canonical["sha256"] != item["sha256"]:
                _fail("La fuente canónica cambió antes de sellar la marca.", 409)
            expected = plan["roles"][role]
            if isinstance(expected, dict) and any(info[k] != expected[k] for k in ("sha256", "family", "style")):
                _fail("La fuente de marca cambió durante el registro.", 409)
            if isinstance(expected, str):
                required = ("sequel sans", "bold disp") if expected == "sequel" else ("scholar", "italic")
                if (info["family"].lower(), info["style"].lower()) != required:
                    _fail("El fallback conserva las fuentes Sequel/Scholar auténticas del editable.", 409)
            notice = canonical.get("metadata", {}).get("font_notice")
            license_value = {"status": "bundled_notice_unverified" if notice else "supplied_by_user_unverified",
                             "label": "Permisos de uso por comprobar", "source_url": None,
                             "notice_path": None, "notice_url": None}
            if notice:
                actual_notice = fonts.notice_file(canonical, core.ROOT)
                license_value.update(notice_path=actual_notice.relative_to(core.ROOT).as_posix(),
                                     notice_url="/api/files/" + actual_notice.relative_to(core.ROOT).as_posix(),
                                     notice_sha256=core.digest(actual_notice))
            faces[role] = {"asset_id": canonical["id"], "path": info["path"], "sha256": info["sha256"],
                           "family": info["family"], "style": info["style"], "license": license_value}
        logo = mapped.get(plan["logo_asset_id"]) if plan["logo_asset_id"] else None
        if logo:
            item = core.asset(logo)
            if item["kind"] != "image" or core.content_hash(item["path"]) != item["sha256"]:
                _fail("El logo canónico cambió durante la importación.", 409)
        current_base = hashlib.sha256(branding.base_rules().encode()).hexdigest()
        profile = {"id": "ivan_branding", "revision": value["revision"], "name": value["name"],
                   "colors": copy.deepcopy(value["colors"]), "fonts": faces, "logo_asset_id": logo,
                   "instructions": value["instructions"], "language": value["language"], "base": "ivan_yo_clone",
                   "base_rules_sha256": current_base, "font_override_explicit": True,
                   "original_reference_fonts": REFERENCES.copy(), "editorial_approved": False,
                   "bundle_import": {"source": "editable_bundle", "appearance": plan["appearance"],
                                     "permissions": "pending_reinspection",
                                     "source_base_rules_sha256": value.get("base_rules_sha256", current_base)}}
        record = _record_path(project["id"])
        project_path = core.project_path(project["id"])
        original_record = record.read_bytes() if record.exists() else None
        original_project = project_path.read_bytes()
        project["style"].update(branding=profile, required_fonts=[face["family"] + " " + face["style"] for face in faces.values()],
                                original_reference_fonts=REFERENCES.copy(), current_production_phase="ivan_multiservice",
                                parent_creative_scope="independent_read_only_source", parent_integration="YO_plus_CLONE_own_branding")
        project["fonts"] = {role: face["path"] for role, face in faces.items()}
        project.update(review={}, renders=[], approved_export=None)
        for key in ("full_authorization", "design_snapshots", "design_reviews", "tracking", "automation"):
            project.pop(key, None)
        from .providers import private_write
        try:
            record.parent.mkdir(parents=True, exist_ok=True)
            private_write(record, json.dumps(profile, ensure_ascii=False, sort_keys=True, allow_nan=False).encode())
            return core.save_project(project["id"], project, expected=old["revision"], action="branding_bundle_imported")
        except Exception:
            if original_record is None:
                record.unlink(missing_ok=True)
            else:
                private_write(record, original_record)
            private_write(project_path, original_project)
            raise
