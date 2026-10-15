"""Read-only canonical skill inventory and explicit project application records.

Nothing imports or executes IVAN's workflow/skill updater. A hash establishes
file identity; reading and applying a guide remain explicit agent declarations
with local evidence. These records do not approve an edit or install a renderer.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re

from . import core
from .runtime import MANUAL_ROOT

REQUIRED = ("hyperframes", "general-video", "hyperframes-core", "hyperframes-creative",
            "hyperframes-animation", "hyperframes-keyframes", "hyperframes-audio", "hyperframes-cli",
            "hyperframes-registry", "hyperframes-studio", "media-use", "motion-graphics")
REFERENCES = ("hyperframes-animation/adapters/gsap.md", "hyperframes-core/references/determinism-rules.md",
              "hyperframes-creative/references/house-style.md", "hyperframes-creative/references/video-composition.md",
              "hyperframes-creative/references/motion-principles.md")
SOURCE_PREFIX = "../.agents/skills/"


def _source(path):
    if not isinstance(path, str) or not path.startswith(SOURCE_PREFIX):
        raise core.StudioError("La guía debe pertenecer a la fuente canónica ../.agents/skills.", 403)
    parent = MANUAL_ROOT.resolve()
    allowed = (parent / ".agents/skills").resolve()
    if not allowed.is_relative_to(parent):
        raise core.StudioError("La fuente de skills salió del workspace IVAN.", 403)
    source = (allowed / path[len(SOURCE_PREFIX):]).resolve()
    if not source.is_relative_to(allowed):
        raise core.StudioError("La guía apunta fuera de la fuente canónica .agents/skills.", 403)
    return source


def _signature(path):
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_hash(path, digest=None):
    before = _signature(path)
    hasher = digest if digest is not None else hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    if before != _signature(path):
        raise core.StudioError("La guía cambió durante la lectura; vuelve a inventariarla.", 409)
    return hasher.hexdigest()


def _tree_hash(name):
    directory = _source(SOURCE_PREFIX + name)
    if not directory.is_dir():
        raise FileNotFoundError("Directorio de skill ausente")
    def manifest():
        return {p.relative_to(directory).as_posix(): (str(_source(SOURCE_PREFIX + name + "/" + p.relative_to(directory).as_posix())),
                                                    _signature(_source(SOURCE_PREFIX + name + "/" + p.relative_to(directory).as_posix())))
                for p in sorted(directory.rglob("*")) if p.is_file()}
    before = manifest()
    h = hashlib.sha256()
    for relative in before:
        safe = _source(SOURCE_PREFIX + name + "/" + relative)
        h.update(relative.encode("utf-8") + b"\0")
        _read_hash(safe, h)
        h.update(b"\0")
    if before != manifest():
        raise core.StudioError("El árbol de la skill cambió durante el inventario.", 409)
    return h.hexdigest()


def inventory() -> dict:
    """Return twelve guide hashes/tree hashes and five reference hashes.

    Missing, unreadable or escaping files are reported as unavailable, never as
    a successful read/application. This function creates no folders or caches.
    """
    skills, references = [], []
    for name in REQUIRED:
        path = SOURCE_PREFIX + name + "/SKILL.md"
        item = {"name": name, "path": path, "source": "https://github.com/heygen-com/hyperframes/tree/main/skills/" + name,
                "sha256": None, "tree_sha256": None, "available": False}
        try:
            source = _source(path)
            signature = _signature(source)
            sha, tree = _read_hash(source), _tree_hash(name)
            if signature != _signature(_source(path)):
                raise core.StudioError("El SKILL.md cambió entre su hash y el inventario del árbol.", 409)
            item.update(sha256=sha, tree_sha256=tree, available=True)
        except (OSError, ValueError, RuntimeError, core.StudioError) as error:
            item["error"] = str(error)
        skills.append(item)
    for name in REFERENCES:
        path = SOURCE_PREFIX + name
        item = {"path": path, "sha256": None, "available": False}
        try:
            item.update(sha256=_read_hash(_source(path)), available=True)
        except (OSError, ValueError, RuntimeError, core.StudioError) as error:
            item["error"] = str(error)
        references.append(item)
    return {"canonical_root": SOURCE_PREFIX.rstrip("/"), "required_count": len(REQUIRED),
            "skills": skills, "references": references, "reading_verified": False, "application_verified": False}


def prepare(project_id: str) -> dict:
    """Create a pending record once; preserve an existing record verbatim."""
    with core.LOCK:
        project = core.get_project(project_id)
        if "skills_applied" in project:
            return project
        source = inventory()
        entries = [{**copy.deepcopy(item), "reading": "pending", "reviewer": None, "decision": None, "evidence": []}
                   for item in source["skills"]]
        references = [{**copy.deepcopy(item), "reading": "pending", "reviewer": None} for item in source["references"]]
        project["skills_applied"] = {"version": 1, "status": "pending_reading_and_application", "at": core.now(),
                                     "manual": core.manual_fingerprints(), "entries": entries, "references": references,
                                     "catalog_query": {"query": None, "language": "en", "decision": None, "evidence": []}}
        return core.save_project(project_id, project, expected=project["revision"], action="skills_prepared")


def _text(value, maximum=20000):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def _proof(value, label, errors):
    if not isinstance(value, list) or not value:
        errors.append(label + ": falta evidencia local con SHA256.")
        return
    if len(value) > 100:
        errors.append(label + ": demasiadas evidencias.")
        return
    for proof in value:
        if not isinstance(proof, dict) or not _text(proof.get("path"), 4096):
            errors.append(label + ": la evidencia requiere path y sha256.")
            continue
        sha = proof.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            errors.append(label + ": SHA256 de evidencia inválido.")
            continue
        try:
            path = core.confined(proof["path"], must_exist=True)
            if path.stat().st_size == 0 or _read_hash(path) != sha.lower():
                errors.append(label + ": la evidencia está vacía o cambió de contenido.")
        except (OSError, ValueError, TypeError, RuntimeError, core.StudioError):
            errors.append(label + ": evidencia inexistente o fuera de SOFTWARE.")


def _reading(entry, label, errors, decision=True):
    if entry.get("reading") != "read_by_agent" or not _text(entry.get("reviewer"), 200):
        errors.append(label + ": registra lectura real y revisor.")
    if decision and not _text(entry.get("decision")):
        errors.append(label + ": falta una decisión concreta de aplicación.")


def validate_application(project) -> list[str]:
    """Validate attestations against current sources and SOFTWARE evidence.

    Return stable validation errors for malformed JSON shapes, never infer a
    read from hashing and never mutate project, skills, approval or filesystem.
    """
    if not isinstance(project, dict):
        return ["El registro de skills requiere un objeto de proyecto."]
    record = project.get("skills_applied")
    if not isinstance(record, dict):
        return ["Falta el registro propio skills_applied; prepara y documenta lectura/aplicación."]
    errors = []
    current = inventory()
    manual = core.manual_fingerprints()
    if any(value.get("missing") for value in manual.values()):
        errors.append("Falta un documento del manual canónico para registrar lectura/aplicación.")
    if record.get("manual") != manual or project.get("manual") != manual:
        errors.append("El manual del registro de skills no está vigente; vuelve a leerlo.")
    if record.get("status") != "reviewed_applied":
        errors.append("El registro de skills sigue pendiente de lectura y aplicación explícitas.")
    entries = record.get("entries")
    indexed = {}
    if not isinstance(entries, list) or len(entries) > 100:
        errors.append("Las entradas de skills deben ser una lista acotada.")
        entries = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or entry["name"] not in REQUIRED:
            errors.append("Entrada de skill desconocida o inválida.")
            continue
        if entry["name"] in indexed:
            errors.append("Skill repetida: " + entry["name"] + ".")
        indexed[entry["name"]] = entry
    for item in current["skills"]:
        name = item["name"]
        if not item["available"]:
            errors.append("Skill canónica no disponible: " + name + ".")
            continue
        entry = indexed.get(name)
        if not entry:
            errors.append("Falta registrar la skill: " + name + ".")
            continue
        if any(entry.get(key) != item[key] for key in ("path", "sha256", "tree_sha256")):
            errors.append("Skill modificada o con huellas inválidas: " + name + ".")
        _reading(entry, name, errors)
        _proof(entry.get("evidence"), name, errors)
    refs = record.get("references")
    indexed_refs = {}
    if not isinstance(refs, list) or len(refs) > 200:
        errors.append("Las referencias de skills deben ser una lista acotada.")
        refs = []
    for reference in refs:
        if not isinstance(reference, dict) or not isinstance(reference.get("path"), str):
            errors.append("Referencia de skill inválida.")
            continue
        path = reference["path"]
        if path in indexed_refs:
            errors.append("Referencia de skill repetida: " + path + ".")
        indexed_refs[path] = reference
        try:
            actual = _read_hash(_source(path))
            if reference.get("sha256") != actual:
                errors.append("Referencia de skill modificada o sin huella vigente: " + path + ".")
            _reading(reference, path, errors, decision=False)
        except (OSError, ValueError, RuntimeError, core.StudioError):
            errors.append("Referencia de skill no disponible o fuera de su fuente canónica.")
    for item in current["references"]:
        if not item["available"]:
            errors.append("Referencia canónica no disponible: " + item["path"] + ".")
        if item["path"] not in indexed_refs:
            errors.append("Falta registrar referencia obligatoria: " + item["path"] + ".")
    catalog = record.get("catalog_query")
    if not isinstance(catalog, dict):
        errors.append("Falta registrar la consulta y decisión del catálogo.")
    else:
        query = catalog.get("query")
        # Language is an explicit attestation; no invented language detector.
        if not _text(query, 2000) or catalog.get("language") != "en" or not re.search(r"[A-Za-z]{2,}", query):
            errors.append("Consulta el catálogo con una frase en inglés y registra language: en.")
        if not _text(catalog.get("decision")):
            errors.append("Falta la decisión de reutilizar o construir tras consultar el catálogo.")
        _proof(catalog.get("evidence"), "Catálogo", errors)
    return errors
