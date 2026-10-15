import copy
import json
from pathlib import Path

import pytest

from studio import branding,core
from studio.core import StudioError


@pytest.fixture
def brand(tmp_path,monkeypatch):
    root=tmp_path/"app"
    root.mkdir()
    branding.bootstrap(root,"Marca propia")
    monkeypatch.setattr(core,"ROOT",root)
    monkeypatch.setattr(core,"WORKSPACE_MODE",True)
    core.setup()
    return root


def editable_config(root):
    value=branding.get_branding(root)
    return {k:value[k] for k in ("revision","name","colors","fonts","logo_asset_id","instructions","language")}


def test_only_verified_public_fonts_seeded_without_private_ivan_material(brand):
    rows=json.loads((brand/".estado/assets.json").read_text())
    assert {a["id"] for a in rows}==branding.SEED_FONT_IDS
    assert all(a["kind"]=="font" for a in rows)
    assert not (brand/"assets/fonts/Sequel_Sans_Bold_Disp.ttf").exists()
    assert not (brand/"assets/fonts/Scholar_Italic.ttf").exists()
    current=branding.get_branding(brand)
    assert current["style_base"]=="ivan_yo_clone"
    assert current["snapshot"]["font_override_explicit"] is True
    assert current["snapshot"]["fonts"]["primary"]["family"]=="Source Sans 3"
    assert all(a["license"]["status"]=="source_verified" for a in current["fonts_library"]["fonts"])


def test_seed_is_idempotent_preserves_new_branding_and_assets(brand):
    value=editable_config(brand);value["name"]="Azul propio";value["colors"]["accent"]="#3366ff"
    saved=branding.save_branding(brand,value)
    before=(brand/".estado/assets.json").read_bytes()
    branding.bootstrap(brand,"Overwritten name")
    assert branding.get_branding(brand)["name"]==saved["name"]
    assert (brand/".estado/assets.json").read_bytes()==before


def test_brand_revision_compare_and_cross_workspace_font_rejected(brand):
    original=editable_config(brand)
    branding.save_branding(brand,copy.deepcopy(original))
    with pytest.raises(StudioError) as error:branding.save_branding(brand,original)
    assert error.value.status==409
    current=editable_config(brand);current["fonts"]["primary"]="a_other_user_font"
    with pytest.raises(StudioError):branding.save_branding(brand,current)


def test_project_has_immutable_explicit_branding_and_can_apply_new_revision(brand):
    project=core.create_project("Mi reel")
    before=copy.deepcopy(project["style"]["branding"])
    assert project["fonts"]["primary"].endswith("7776ddb9f3eb58683e59.otf")
    assert project["style"]["parent_integration"]=="YO_plus_CLONE_own_branding"
    value=editable_config(brand);value["fonts"]["primary"]="a_a4ba3a92350ebb031da0";value["colors"]["accent"]="#3366ff"
    branding.save_branding(brand,value)
    assert core.get_project(project["id"])["style"]["branding"]==before
    forged=copy.deepcopy(project);forged["style"]["branding"]["fonts"]["primary"]["family"]="Invented"
    saved=core.save_project(project["id"],forged)
    assert saved["style"]["branding"]==before
    applied=branding.apply_project_branding(project["id"],saved["revision"])
    assert applied["style"]["branding"]["fonts"]["primary"]["family"]=="Anton"
    assert applied["history"][-1]["action"]=="branding_applied"
    assert not applied.get("review",{}).get("approved_preview")
    assert branding.validate_project_binding(applied,brand)


def test_project_snapshot_bytes_and_paths_cannot_be_forged(brand):
    project=core.create_project("Prueba")
    project["style"]["branding"]["fonts"]["primary"]["sha256"]="0"*64
    with pytest.raises(StudioError):branding.validate_project_binding(project,brand)


def test_actual_font_tampering_rejected(brand):
    project=core.create_project("Prueba")
    path=brand/project["fonts"]["primary"]
    path.write_bytes(b"forged font")
    with pytest.raises(StudioError):branding.validate_project_binding(project,brand)


def test_current_software_profile_acknowledgement_hashes_agree(brand):
    project=core.create_project("Prueba")
    document=branding.profile_document()
    assert core.manual_fingerprints()[document["name"]]["sha256"]==document["sha256"]
    refreshed=core.refresh_manual(project["id"],{document["name"]:document["sha256"]})
    assert refreshed["style"]["parent_integration"]=="YO_plus_CLONE_own_branding"
    assert "1KV8OF_" not in document["content"]
    with pytest.raises(StudioError):core.refresh_manual(project["id"],{document["name"]:"0"*64})


@pytest.mark.parametrize("field,value",[("colors",{"accent":"red"}),("fonts",{"primary":"../../private","accent":"anything"}),("logo_asset_id","a_foreign"),("revision",True),("language","../../xx"),("instructions",123)])
def test_branding_closed_parameters(brand,field,value):
    data=editable_config(brand);data[field]=value
    with pytest.raises(StudioError):branding.save_branding(brand,data)


def test_bootstrap_symlink_leaves_target_untouched(tmp_path):
    root=tmp_path/"root";root.mkdir();target=tmp_path/"other";target.mkdir()
    (root/".estado").symlink_to(target,target_is_directory=True)
    with pytest.raises(StudioError):branding.bootstrap(root)
    assert not list(target.iterdir())


def test_bootstrap_works_from_public_pack_without_private_global_catalog(tmp_path, monkeypatch):
    import shutil
    code=tmp_path/"public_source";code.mkdir()
    (code/"packs").mkdir()
    (code/"profiles").mkdir()
    shutil.copyfile(branding.CODE_ROOT/"profiles/ivan_base.json", code/"profiles/ivan_base.json")
    shutil.copyfile(branding.CODE_ROOT/"packs/public_fonts.json", code/"packs/public_fonts.json")
    manifest=json.loads((code/"packs/public_fonts.json").read_text())
    for relative in {row[key] for row in manifest["fonts"] for key in ("path","notice_path")}:
        target=code/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(branding.CODE_ROOT/relative,target)
    assert not (code/".estado").exists()
    monkeypatch.setattr(branding,"CODE_ROOT",code)
    user=tmp_path/"fresh_user";user.mkdir()
    branding.bootstrap(user)
    assert {row["id"] for row in json.loads((user/".estado/assets.json").read_text())}==branding.SEED_FONT_IDS
    assert branding.get_branding(user)["snapshot"]["fonts"]["primary"]["family"]=="Source Sans 3"
    assert not (code/".estado").exists()


def test_project_update_cannot_forge_resource_observations_or_rights(brand):
    project=core.create_project("Reel protegido")
    original=copy.deepcopy(project["assets"])
    for item in project["assets"]:
        item["verification"]={"visual":True,"rights":"source_verified"}
        item["metadata"]["resource_review"]={"status":"observed","content":"Fabricated"}
    saved=core.save_project(project["id"],project)
    assert saved["assets"]==original


def test_apply_branding_rejects_other_tab_change_since_confirmation(brand):
    project=core.create_project("Reel CAS doble")
    before=core.project_path(project["id"]).read_bytes()
    old=editable_config(brand)
    value=copy.deepcopy(old);value["name"]="Nueva marca desde otra pestaña"
    saved=branding.save_branding(brand,value)
    with pytest.raises(StudioError) as conflict:
        branding.apply_project_branding(project["id"],project["revision"],old["revision"])
    assert conflict.value.status==409
    assert core.project_path(project["id"]).read_bytes()==before
    applied=branding.apply_project_branding(project["id"],project["revision"],saved["revision"])
    assert applied["style"]["branding"]["name"]==saved["name"]
