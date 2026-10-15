#!/usr/bin/env python3
"""Package reviewed public sources only; never import the running studio.

This builds a source checkout, not an installed runtime or a deployed service.
Private data are excluded by exact paths, not by guessing credential contents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

SOFTWARE = Path(__file__).resolve().parents[1]
OUTPUT = "exports/ascendia-studio-source.zip"
MANIFEST = "SOURCE_MANIFEST.json"
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
BASE = ("README.md", "AGENTS.md", "LICENSE", ".gitignore", "pyproject.toml", "requirements.txt", "requirements-asr.txt",
        "iniciar.sh", "iniciar_multiservice.sh", "instalar.sh", "instalar_asr.sh", "scripts/package_release.py",
        "profiles/ivan_base.json", "packs/public_fonts.json")
WEB = tuple("web/" + name for name in ("index.html", "app.js", "style.css", "portal.html", "portal.js", "portal.css"))
DOCS = tuple("docs/" + name + ".md" for name in ("API", "ARQUITECTURA", "AUDITORIA", "INVESTIGACION", "MULTISERVICE_ADAPTACION", "MODOS_COLABORACION_PIPELINE", "NUBE", "PROCESO_IVAN", "TIPOGRAFIA"))
WORKFLOWS = tuple("workflows/" + name for name in ("AGENTES.md", "ivan_multiservice.json", "reel_multiservice.json", "desarrollo_multiservice.json", "persona_cpu.json", "reel_v5.json", "scene_ir_component.json", "tipografia_local.json"))
SCREENS = tuple("docs/" + name + ".png" for name in ("portal", "portal-mobile", "home-desktop", "home-mobile", "shared-viewer", "typography-fonts", "typography-editor", "typography-editor-mobile"))
PUBLIC_FILES = {
    "assets/fonts/08df266400933d3178d0.otf": "08df266400933d3178d081a45f94a08814c3e55b4b7dd2e0ff69cb1329f13ab6",
    "assets/fonts/7776ddb9f3eb58683e59.otf": "7776ddb9f3eb58683e59f28d558d8896b768c2d0c80799fb3f1c56c54dfd98c9",
    "assets/fonts/a4ba3a92350ebb031da0.ttf": "a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab",
    "assets/fonts/8cc3643535edf039aa5d.ttf": "8cc3643535edf039aa5d95440a8542735e9197e4f4b8d9303e980fefbf5ab616",
    "assets/fonts/df74c0ac387baeaeb0fe.ttf": "df74c0ac387baeaeb0fe4f2324e1668e6a3ed8c09cd9796fe162c71753e19e45",
    "assets/fonts/6a3412f058c7d8dfd917.ttf": "6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46",
    "assets/fonts/licenses/89ad2c4f66dd29127527493e.txt": "89ad2c4f66dd29127527493e729c31e731f111cf10faf5774c3db9275ed0c22c",
    "assets/fonts/licenses/ee67e6ee22790b7929f1a376.txt": "ee67e6ee22790b7929f1a3769ca2801d565c64b5a9096942c1adf5596de9c9e4",
    "assets/fonts/licenses/a3e5cdd67d4571dd0a24fcc9.txt": "a3e5cdd67d4571dd0a24fcc968de0efde7ae97ef752daf0906e4767619dd7231",
    "assets/fonts/licenses/7e6b2818edbd8f6a01ae8064.txt": "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da",
}


class PackageError(ValueError):
    pass


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _root(value):
    path = Path(value).absolute()
    if path.resolve() != path or not path.is_dir() or not path.is_relative_to(SOFTWARE):
        raise PackageError("El checkout debe ser un directorio real dentro de SOFTWARE.")
    return path


def _path(root, relative):
    p = Path(relative)
    if p.is_absolute() or p.as_posix() != relative or any(part in {".", ".."} for part in p.parts):
        raise PackageError("Ruta de paquete no canónica.")
    path = root / p
    if path.resolve() != path or not path.is_relative_to(root):
        raise PackageError("Los enlaces y aliases no pertenecen al paquete público.")
    return path


def _signature(root, relative):
    info = _path(root, relative).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 1 <= info.st_size <= MAX_FILE:
        raise PackageError("El paquete admite archivos regulares individuales de hasta16MiB.")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read(root, relative, expected=None):
    signature = _signature(root, relative)
    fd = os.open(_path(root, relative), os.O_RDONLY | os.O_NOFOLLOW)
    try:
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            actual = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            if actual != signature or info.st_nlink != 1:
                raise PackageError("Un archivo cambió antes de leerse.")
            data = source.read(MAX_FILE + 1)
    except Exception:
        # fdopen owns the descriptor after its construction.
        raise
    if len(data) != signature[2] or _signature(root, relative) != signature:
        raise PackageError("Un archivo cambió mientras se verificaba.")
    sha = hashlib.sha256(data).hexdigest()
    if expected is not None and sha != expected:
        raise PackageError("El contenido público no coincide con su SHA aprobado: " + relative)
    return data, {"sha256": sha, "bytes": len(data), "signature": signature}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PackageError("Claves de manifiesto repetidas.")
        result[key] = value
    return result


def _font_manifest(root):
    raw, _ = _read(root, "packs/public_fonts.json")
    try:
        pack = json.loads(raw, object_pairs_hook=_pairs)
        fonts = pack["fonts"]
        expected = {}
        if pack.get("schema") != "ascendia.public-fonts/1" or not isinstance(fonts, list) or len(fonts) != 6:
            raise PackageError("El paquete público requiere sus seis caras OFL.")
        ids = set()
        for face in fonts:
            if (not isinstance(face, dict) or face.get("license") != "OFL-1.1" or face.get("asset_id") in ids):
                raise PackageError("Declaración de fuente pública inválida.")
            ids.add(face["asset_id"])
            if face["asset_id"] != "a_" + face.get("sha256", "")[:20]:
                raise PackageError("El ID público de fuente debe corresponder a su contenido.")
            for path, key in ((face["path"], "sha256"), (face["notice_path"], "notice_sha256")):
                if path in expected and expected[path] != face[key]:
                    raise PackageError("Avisos tipográficos contradictorios.")
                expected[path] = face[key]
        if expected != PUBLIC_FILES:
            raise PackageError("El manifiesto intenta cambiar la allowlist pública aprobada.")
    except (KeyError, TypeError, ValueError) as error:
        raise PackageError("Manifiesto público de fuentes inválido: " + str(error)[:120]) from error


def _paths(root):
    studio = _path(root, "studio")
    if not studio.is_dir():
        raise PackageError("Falta el código del editor.")
    modules = sorted("studio/" + p.name for p in studio.iterdir() if p.suffix == ".py")
    if not modules or any(not re.fullmatch(r"studio/[A-Za-z_][A-Za-z0-9_]*\.py", p) for p in modules):
        raise PackageError("Nombres de módulos públicos inválidos.")
    return sorted(set(BASE + WEB + DOCS + WORKFLOWS + SCREENS + tuple(PUBLIC_FILES) + tuple(modules)))


def plan_release(root=SOFTWARE):
    """List and hash the allowlist; no execution, copying, or installation."""
    root = _root(root)
    _font_manifest(root)
    files = {}
    for name in _paths(root):
        _, files[name] = _read(root, name, PUBLIC_FILES.get(name))
    if sum(f["bytes"] for f in files.values()) > MAX_TOTAL:
        raise PackageError("El código público supera64MiB.")
    return files


def _verify_sources(root, files):
    if _paths(root) != sorted(files):
        raise PackageError("La lista de fuentes cambió durante el empaquetado.")
    for name, expected in files.items():
        _, actual = _read(root, name, expected["sha256"])
        if actual["signature"] != expected["signature"]:
            raise PackageError("Cambió un archivo del checkout durante el empaquetado.")


def verify_zip(path, expected_files):
    """Verify exact member coverage, regular entries, CRC and actual bytes."""
    expected = {name: {"sha256": item["sha256"], "bytes": item["bytes"]} for name, item in expected_files.items()}
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [info.filename for info in entries]
        if len(names) != len(set(names)) or set(names) != set(expected) | {MANIFEST}:
            raise PackageError("El ZIP contiene miembros privados, repetidos o ausentes.")
        for info in entries:
            if info.is_dir() or stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG or info.flag_bits & 1:
                raise PackageError("El ZIP no contiene archivos regulares públicos.")
        if archive.testzip() is not None:
            raise PackageError("El ZIP no pasó su verificación CRC.")
        manifest = json.loads(archive.read(MANIFEST), object_pairs_hook=_pairs)
        if manifest.get("files") != expected or manifest.get("source_sha256") != hashlib.sha256(_json(expected)).hexdigest():
            raise PackageError("El manifiesto del ZIP no describe el checkout verificado.")
        for name, item in expected.items():
            data = archive.read(name)
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise PackageError("Un miembro del ZIP no coincide con su archivo verificado.")
    return manifest


def build_release(root=SOFTWARE, destination=None):
    root = _root(root)
    target = _path(root, OUTPUT)
    if destination is not None and Path(destination).absolute() != target:
        raise PackageError("La salida es únicamente exports/ascendia-studio-source.zip del checkout.")
    temporary_dir = _path(root, ".estado/tmp")
    files = plan_release(root)
    if target.exists():
        info = target.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PackageError("El destino existente no es un archivo regular individual.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    source_files = {name: {"sha256": item["sha256"], "bytes": item["bytes"]} for name, item in files.items()}
    source_sha = hashlib.sha256(_json(source_files)).hexdigest()
    manifest = {"schema": "ascendia.public-source/1", "files": source_files, "source_sha256": source_sha,
                "scope": "reviewable_source_checkout", "screenshots": list(SCREENS),
                "public_font_faces": 6, "public_font_notices": 4, "runtime_installed": False,
                "models_included": False, "private_data_included": False, "deployed": False,
                "commercial_ready": False, "editorial_approved": False}
    fd, temp_name = tempfile.mkstemp(prefix="source_release_", suffix=".zip", dir=temporary_dir)
    os.close(fd)
    temporary = Path(temp_name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in sorted(files):
                data, actual = _read(root, name, files[name]["sha256"])
                if actual["signature"] != files[name]["signature"]:
                    raise PackageError("El código cambió antes de guardarlo en el ZIP.")
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | (0o755 if name.endswith(".sh") else 0o644)) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
            info = zipfile.ZipInfo(MANIFEST, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3;info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, _json(manifest))
        verify_zip(temporary, files)
        _verify_sources(root, files)
        if _path(root, OUTPUT) != target or _path(root, ".estado/tmp") != temporary_dir:
            raise PackageError("Cambió el destino antes de promover el paquete.")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    raw = target.read_bytes()
    return {"path": OUTPUT, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
            "source_sha256": source_sha, "files": len(files), "verified_crc_and_sha256": True,
            "scope": "reviewable_source_checkout", "deployed": False, "commercial_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate public sources without creating the ZIP")
    args = parser.parse_args()
    try:
        result = plan_release() if args.check else build_release()
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (PackageError, OSError, zipfile.BadZipFile) as error:
        parser.exit(1, "Source package rejected: " + str(error) + "\n")


if __name__ == "__main__":
    main()
