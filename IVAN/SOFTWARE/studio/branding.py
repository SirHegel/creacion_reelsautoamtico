"""Shared IVAN editorial rules with private, explicit branding overrides."""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import re
from pathlib import Path

from .core import StudioError, now
from .providers import CODE_ROOT, private_root, private_write

def profile_document():
    path=CODE_ROOT/"profiles/ivan_base.json"
    if path.is_symlink() or not path.resolve().is_relative_to(CODE_ROOT.resolve()):
        raise StudioError("Perfil de automatización inválido.",403)
    raw=path.read_bytes()
    value=json.loads(raw)
    if value.get("schema")!="ascendia.ivan-style/1" or not isinstance(value.get("rules"),str):
        raise StudioError("Perfil de automatización inválido.",409)
    return {"name":"IVAN_STYLE_BASE","sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"content":raw.decode("utf-8")}


def base_rules():
    return json.loads(profile_document()["content"])["rules"]


# Compatibility for callers; the canonical rule text resides only in profiles/.
BASE_RULES=base_rules()

DEFAULT={"revision":1,"name":"Mi marca","colors":{"background":"#f8f7f3","text":"#15171b","accent":"#d71920","muted":"#72757d"},
         "fonts":{"primary":"a_7776ddb9f3eb58683e59","accent":"a_df74c0ac387baeaeb0fe"},
         "logo_asset_id":None,"instructions":"","language":"es"}
SEED_FONT_IDS={"a_08df266400933d3178d0","a_7776ddb9f3eb58683e59","a_a4ba3a92350ebb031da0","a_8cc3643535edf039aa5d","a_df74c0ac387baeaeb0fe","a_6a3412f058c7d8dfd917"}


def _path(root,relative,must=False):
    root=Path(root).resolve();path=root/relative
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise StudioError("La marca debe permanecer en su espacio privado.",403)
    if must and not path.is_file():raise StudioError("Falta un recurso de la marca.",404)
    return path


def _read(root):
    path=_path(root,".estado/branding.json")
    if not path.exists():raise StudioError("Configura la marca de este espacio.",409)
    return json.loads(path.read_text())


def _lock(root):
    private_root(root)
    path=_path(root,".estado/branding.lock")
    path.touch(mode=0o600,exist_ok=True)
    handle=path.open("a+b");fcntl.flock(handle,fcntl.LOCK_EX)
    return handle


def _catalog(root):
    path=_path(root,".estado/assets.json")
    return json.loads(path.read_text()) if path.exists() else []


def bootstrap(root,name="Mi marca"):
    """Only verified public OFL fonts are seeded. No private IVAN media or accounts."""
    root=Path(root).resolve()
    with _lock(root):
        if _path(root,".estado/branding.json").exists():return
        registry=json.loads(_path(CODE_ROOT,"packs/public_fonts.json",True).read_text())
        if registry.get("schema")!="ascendia.public-fonts/1":
            raise StudioError("El manifiesto de fuentes públicas no es válido.",409)
        approved=[r for r in registry["fonts"] if r.get("asset_id") in SEED_FONT_IDS and r.get("license")=="OFL-1.1"]
        if {r["asset_id"] for r in approved}!=SEED_FONT_IDS:
            raise StudioError("El paquete de fuentes públicas está incompleto.",409)
        copied=[]
        for record in approved:
            if record["path"] != "assets/fonts/"+record["sha256"][:20]+Path(record["path"]).suffix or record["asset_id"]!="a_"+record["sha256"][:20] or record["notice_path"]!="assets/fonts/licenses/"+record["notice_sha256"][:24]+".txt":
                raise StudioError("Cambió una fuente pública del paquete.",409)
            for relative,expected in ((record["path"],record["sha256"]),(record["notice_path"],record["notice_sha256"])):
                source=_path(CODE_ROOT,relative,True);data=source.read_bytes()
                if hashlib.sha256(data).hexdigest()!=expected:raise StudioError("Cambió el paquete público de fuentes.",409)
                target=_path(root,relative);target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():
                    if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise StudioError("Un recurso de la marca cambió; no se sobrescribe.",409)
                else:private_write(target,data)
            from .fonts import inspect_font
            path=_path(root,record["path"],True)
            info=inspect_font(path,root)
            if info["sha256"]!=record["sha256"] or any(info[k]!=record[k] for k in ("family","style")):
                raise StudioError("La variante real no coincide con el paquete público.",409)
            copied.append({"id":record["asset_id"],"name":record["family"]+" · "+record["style"]+path.suffix,
                           "path":record["path"],"kind":"font","sha256":record["sha256"],
                           "md5":hashlib.md5(path.read_bytes()).hexdigest(),"size":path.stat().st_size,
                           "duration":0.0,"probe":{},"created_at":now(),"url":"/api/media/"+record["asset_id"],
                           "metadata":{"provenance":{"operation":"public_font_import","source_url":record["source_url"],"commit":record["commit"],"license":"OFL-1.1","font_bytes_modified":False},
                                       "font_notice":{"path":record["notice_path"],"sha256":record["notice_sha256"],"license":"OFL-1.1","source_url":record["notice_source_url"]},
                                       "content":"Fuente pública canónica, variante original sin estilo sintético."},
                           "verification":{"visual":False,"audio":False,"rights":"supplied_by_user_unverified"},
                           "font_info":info,"preview_path":record["path"],"preview_url":"/api/files/"+record["path"],
                           "preview_is_derivative":False,"preview_reason":"Fuente tipográfica: usa el original."})
        existing=_catalog(root)
        by_id={a["id"]:a for a in existing}
        for item in copied:
            if item["id"] in by_id and by_id[item["id"]].get("sha256")!=item["sha256"]:
                raise StudioError("Identidad de recurso incompatible.",409)
            by_id.setdefault(item["id"],item)
        private_write(_path(root,".estado/assets.json"),json.dumps(list(by_id.values()),ensure_ascii=False).encode())
        licenses=_path(root,".estado/fonts/licensed.json");licenses.parent.mkdir(parents=True,exist_ok=True)
        private_write(licenses,json.dumps({"fonts":approved,"seed":"public_OFL_fonts_only"},ensure_ascii=False).encode())
        config=copy.deepcopy(DEFAULT);config["name"]=str(name)[:120];config["updated_at"]=now()
        private_write(_path(root,".estado/branding.json"),json.dumps(config,ensure_ascii=False).encode())
        for folder in (".estado/tmp",".estado/logs",".estado/cache","projects","exports"):
            _path(root,folder).mkdir(parents=True,exist_ok=True)


def snapshot(root,config=None):
    from .fonts import inspect_font,validate_asset_font,license_info
    config=_read(root) if config is None else config
    catalog={a["id"]:a for a in _catalog(root)}
    roles={}
    for role in ("primary","accent"):
        aid=config["fonts"][role];item=catalog.get(aid)
        if not item:raise StudioError("Selecciona una fuente de tu espacio.",404)
        validated=validate_asset_font(item,root)
        info=inspect_font(_path(root,validated["path"],True),root)
        roles[role]={"asset_id":aid,"path":validated["path"],"sha256":info["sha256"],"family":info["family"],"style":info["style"],"license":license_info(item,root)}
    return {"id":"ivan_branding","revision":config["revision"],"name":config["name"],"colors":copy.deepcopy(config["colors"]),"fonts":roles,
            "logo_asset_id":config["logo_asset_id"],"instructions":config["instructions"],"language":config["language"],"base":"ivan_yo_clone",
            "base_rules_sha256":hashlib.sha256(base_rules().encode()).hexdigest(),"font_override_explicit":True,
            "original_reference_fonts":["Sequel Sans Bold Disp","Scholar Italic"],"editorial_approved":False}


def get_branding(root):
    config=_read(root)
    fonts=[]
    from .fonts import validate_asset_font,license_info
    for item in _catalog(root):
        if item.get("kind")=="font":
            try:
                face=validate_asset_font(item,root)
                fonts.append({"asset_id":item["id"],"id":item["id"],"name":item["name"],"family":face["family"],"style":face["style"],"available":True,"url":"/api/media/"+item["id"],"license":license_info(item,root)})
            except StudioError:
                fonts.append({"asset_id":item["id"],"name":item["name"],"available":False})
    return {**config,"style_base":"ivan_yo_clone","fonts_library":{"fonts":fonts},"snapshot":snapshot(root,config),"base_rules":base_rules(),"shared_private_ivan_assets":False}


def save_branding(root,data):
    fields={"revision","name","colors","fonts","logo_asset_id","instructions","language"}
    if not isinstance(data,dict) or set(data)!=fields:raise StudioError("La configuración de marca contiene campos incorrectos.")
    if type(data["revision"]) is not int or data["revision"]<1:raise StudioError("Revisión de marca inválida.")
    if not isinstance(data["name"],str) or not 1<=len(data["name"].strip())<=120:raise StudioError("Nombre de marca inválido.")
    if not isinstance(data["colors"],dict) or set(data["colors"])!={"background","text","accent","muted"} or any(not isinstance(v,str) or not re.fullmatch(r"#[0-9a-fA-F]{6}",v) for v in data["colors"].values()):
        raise StudioError("Los colores requieren valores hexadecimales de seis dígitos.")
    if not isinstance(data["fonts"],dict) or set(data["fonts"])!={"primary","accent"} or any(not isinstance(v,str) or not re.fullmatch(r"a_[A-Za-z0-9_-]{1,100}",v) for v in data["fonts"].values()):raise StudioError("Selecciona las dos fuentes reales de tu espacio.")
    if not isinstance(data["instructions"],str) or len(data["instructions"])>8000:raise StudioError("Las indicaciones de marca admiten hasta 8000 caracteres.")
    if not isinstance(data["language"],str) or not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?",data["language"]):raise StudioError("Idioma inválido.")
    logo=data["logo_asset_id"]
    if logo is not None:
        item=next((a for a in _catalog(root) if a["id"]==logo and a.get("kind")=="image"),None)
        if not item or hashlib.sha256(_path(root,item["path"],True).read_bytes()).hexdigest()!=item["sha256"]:raise StudioError("El logo debe ser una imagen canónica de tu espacio.")
    with _lock(root):
        current=_read(root)
        if current["revision"]!=data["revision"]:raise StudioError("La marca cambió en otra pestaña. Recarga antes de guardar.",409)
        snapshot(root,data)
        value=copy.deepcopy(data);value.update(revision=data["revision"]+1,updated_at=now());value["name"]=value["name"].strip()
        private_write(_path(root,".estado/branding.json"),json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
    return get_branding(root)


def font_paths(root):
    return {role:face["path"] for role,face in snapshot(root)["fonts"].items()}


def bind_project(project,root):
    """Capture a server-owned snapshot; later branding edits don't rewrite a reel."""
    profile=snapshot(root)
    path=_path(root,".estado/project_branding/"+project["id"]+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    private_write(path,json.dumps(profile,ensure_ascii=False,sort_keys=True).encode())
    project["style"]["branding"]=profile
    project["style"]["required_fonts"]=[face["family"]+" "+face["style"] for face in profile["fonts"].values()]
    project["style"]["original_reference_fonts"]=profile["original_reference_fonts"]
    project["fonts"]={role:face["path"] for role,face in profile["fonts"].items()}
    wanted={face["asset_id"] for face in profile["fonts"].values()}
    if profile["logo_asset_id"]:wanted.add(profile["logo_asset_id"])
    existing={a["id"]:a for a in project.get("assets",[])}
    for item in _catalog(root):
        if item["id"] in wanted:existing.setdefault(item["id"],copy.deepcopy(item))
    project["assets"]=list(existing.values())
    return project


def validate_project_binding(project,root):
    profile=project.get("style",{}).get("branding")
    path=_path(root,".estado/project_branding/"+project["id"]+".json",True)
    authoritative=json.loads(path.read_text())
    if not isinstance(profile,dict) or profile!=authoritative:
        raise StudioError("La marca del proyecto requiere una aplicación explícita desde su configuración.",409)
    from .fonts import validate_asset_font
    by_id={a["id"]:a for a in project.get("assets",[])}
    for role,face in profile["fonts"].items():
        if project.get("fonts",{}).get(role)!=face["path"]:
            raise StudioError("La fuente del proyecto cambió sin actualizar su marca.",409)
        item=by_id.get(face["asset_id"])
        validated=validate_asset_font(item,root)
        if any(validated.get(key)!=face.get(key) for key in ("path","sha256","family","style")):
            raise StudioError("La fuente de la marca cambió; vuelve a comprobarla.",409)
    return profile


def apply_project_branding(project_id,expected_revision,expected_branding_revision=None):
    from . import core
    if not core.WORKSPACE_MODE:
        raise StudioError("La personalización de marca requiere un espacio privado.",409)
    with core.LOCK, _lock(core.ROOT):
        project=core.get_project(project_id)
        if type(expected_revision) is not int or expected_revision!=project["revision"]:
            raise StudioError("El proyecto cambió. Recarga antes de aplicar la marca.",409)
        current=_read(core.ROOT)
        if expected_branding_revision is not None and (type(expected_branding_revision) is not int or expected_branding_revision!=current["revision"]):
            raise StudioError("La marca cambió desde la confirmación. Revisa su nueva configuración.",409)
        record=_path(core.ROOT,".estado/project_branding/"+project_id+".json",True)
        original=record.read_bytes()
        old_roles=copy.deepcopy(project["style"]["branding"]["fonts"])
        try:
            bind_project(project,core.ROOT)
            new_roles=project["style"]["branding"]["fonts"]
            for scene in project.get("timeline",[]):
                for element in (scene.get("motion_design") or {}).get("elements",[]):
                    for role in ("primary","accent"):
                        if element.get("font_asset_id")==old_roles[role]["asset_id"]:
                            element["font_asset_id"]=new_roles[role]["asset_id"]
            return core.save_project(project_id,project,expected=expected_revision,action="branding_applied")
        except Exception:
            private_write(record,original)
            raise
