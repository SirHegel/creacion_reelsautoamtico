"""Design approval regressions. Fixtures never approve a real client design."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from PIL import Image

from studio import core, design, design_review, jobs
from test_core import sandbox, valid_project


@pytest.fixture
def static_project(sandbox, monkeypatch):
    # Freeze the engine identity inside this test only; don't edit real modules
    # to test staleness while other agents are implementing their own modules.
    code = ["a" * 64]
    monkeypatch.setattr(core, "engine_fingerprints", lambda: {"fixture_engine.py": code[0]})
    p = valid_project(sandbox)
    p["settings"].update(width=160, height=284, engine="native")
    scene = p["timeline"][1]
    scene.update(template="custom", motion_design={"canvas": {"background": "#102030"}, "elements": [
        {"id": "shape", "type": "shape", "shape": "rect", "x": .1, "y": .1, "width": .5, "height": .3,
         "color": "#405060", "mask": {"type": "none"}, "keyframes": []}]})
    path = sandbox / "assets/images/fixture_reference.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "#806040").save(path)
    reference = {"id": "a_reference", "name": "Own fixture reference, not CLONE.png", "path": core.relative(path),
                 "kind": "image", "sha256": core.digest(path), "md5": core.digest(path, "md5"),
                 "size": path.stat().st_size, "duration": 0, "probe": {"streams": [{"codec_type": "video"}]},
                 "metadata": {}, "verification": {"visual": False}}
    catalog = core.assets(); catalog.append(reference); core.atomic_json(".estado/assets.json", catalog)
    p["assets"].append(reference)
    p = core.save_project(p["id"], p)
    return p, sandbox, code


def capture(p):
    with jobs.cpu_slot():
        snapshot = design_review.make_snapshot(p, {"scene_id": "s_motion"})
    p = copy.deepcopy(p)
    p.setdefault("design_snapshots", {})["s_motion"] = snapshot
    return core.save_project(p["id"], p, action="design_captured"), snapshot


def payload(snapshot, approved=True):
    return {"scene_id": "s_motion", "approve_design": approved, "expected_sha256": snapshot["sha256"],
            "reviewer": "Fixture reviewer only", "notes": "Fixture inspection, not a real client approval",
            "approval_text": "Explicit fixture authorization; never approval of the client's CLONE component",
            "reference_asset_id": "a_reference", "reference_name": "CLONE", "reference_time": 3.1,
            "checks": {key: True for key in ("composition", "typography", "spacing", "color", "depth")}}


def test_native_snapshot_is_real_png_and_never_autoapproves(static_project):
    p, root, _ = static_project
    before = copy.deepcopy(p)
    with jobs.cpu_slot():
        snapshot = design_review.make_snapshot(p, {"scene_id": "s_motion"})
    assert p == before
    assert snapshot["approved"] is False and snapshot["technical"]["editorial_approved"] is False
    assert snapshot["technical"]["static"] is True
    path = root / snapshot["path"]
    assert core.digest(path) == snapshot["sha256"]
    with Image.open(path) as image:
        assert image.size == (160, 284)
        assert image.convert("RGB").getpixel((0, 0)) == (16, 32, 48)
        assert image.convert("RGB").getpixel((25, 40)) == (64, 80, 96)
    assert not core.get_project(p["id"]).get("design_reviews")


@pytest.mark.parametrize("effects,background,shape", [
    ({"brightness": .2}, (67, 83, 99), (115, 131, 147)),
    ({"saturation": 0}, (29, 29, 29), (77, 77, 77)),
    ({"brightness": .2, "saturation": 0}, (80, 80, 80), (128, 128, 128)),
])
def test_native_snapshot_pixels_include_current_grading(static_project, effects, background, shape):
    p, root, _ = static_project
    p["timeline"][1]["effects"] = effects
    with jobs.cpu_slot():
        snapshot = design_review.make_snapshot(p, {"scene_id": "s_motion"})
    with Image.open(root / snapshot["path"]) as image:
        assert image.convert("RGB").getpixel((0, 0)) == background
        assert image.convert("RGB").getpixel((25, 40)) == shape
    assert snapshot["approved"] is False
    assert snapshot["design_digest"] == design.design_digest(p["timeline"][1], p)


def test_explicit_neutral_effect_defaults_preserve_static_digest(static_project):
    p, _, _ = static_project
    scene = p["timeline"][1]
    scene.pop("effects", None)
    original = design.design_digest(scene, p)
    scene["effects"] = {"brightness": 0, "contrast": 1, "saturation": 1}
    assert design.design_digest(scene, p) == original


def test_comments_only_remain_unapproved_and_do_not_create_approved_png(static_project):
    p, root, _ = static_project
    p, snapshot = capture(p)
    data = payload(snapshot, False)
    for field in ("approval_text", "reference_asset_id", "reference_name", "reference_time", "checks"):
        data.pop(field)
    result = design_review.record_review(p["id"], data)
    assert result["design_reviews"]["s_motion"]["approved"] is False
    assert not (root / f"projects/{p['id']}/designs/s_motion_approved.png").exists()
    assert design_review.production_errors(result)


def test_explicit_fixture_approval_is_tied_to_current_png_and_reference(static_project):
    p, root, _ = static_project
    p, snapshot = capture(p)
    result = design_review.record_review(p["id"], payload(snapshot))
    review = result["design_reviews"]["s_motion"]
    assert review["approved"] is True and review["snapshot_sha256"] == snapshot["sha256"]
    assert core.digest(root / review["approved_path"]) == snapshot["sha256"]
    assert not result["review"] and not result.get("full_authorization")
    assert design_review.production_errors(result) == []


@pytest.mark.parametrize("changes", [
    {"approve_design": "false"}, {"approve_design": 1}, {"expected_sha256": "0" * 64},
    {"approval_text": " "}, {"reviewer": ""}, {"notes": " "}, {"reference_asset_id": "missing"},
    {"reference_asset_id": "a_source"}, {"reference_name": ""}, {"reference_time": -1},
    {"reference_time": float("nan")}, {"checks": {}}, {"checks": {"composition": "true"}},
])
def test_incomplete_or_forged_assertions_cannot_approve(static_project, changes):
    p, root, _ = static_project
    p, snapshot = capture(p)
    data = payload(snapshot); data.update(changes)
    old = core.read_json(core.project_path(p["id"]))
    with pytest.raises(core.StudioError):
        design_review.record_review(p["id"], data)
    assert core.read_json(core.project_path(p["id"])) == old
    assert not (root / f"projects/{p['id']}/designs/s_motion_approved.png").exists()


@pytest.mark.parametrize("mutation", ["manual", "engine", "engine_mode", "brightness", "contrast", "saturation", "design", "font", "snapshot"])
def test_snapshot_invalidations_before_review(static_project, mutation):
    p, root, code = static_project
    p, snapshot = capture(p)
    if mutation == "manual":
        (root.parent / "INSTRUCCIONES.md").write_text("Changed fixture manual")
    elif mutation == "engine":
        code[0] = "b" * 64
    elif mutation == "font":
        (root / p["fonts"]["primary"]).write_bytes(b"changed fixture font")
    elif mutation == "snapshot":
        (root / snapshot["path"]).write_bytes(b"changed fixture snapshot")
    elif mutation == "engine_mode":
        p["settings"]["engine"] = "hyperframes"
        p = core.save_project(p["id"], p)
    elif mutation in ("brightness", "contrast", "saturation"):
        p["timeline"][1].setdefault("effects", {})[mutation] = {"brightness": .2, "contrast": 1.5, "saturation": 0}[mutation]
        p = core.save_project(p["id"], p)
    else:
        p["timeline"][1]["motion_design"]["elements"][0]["color"] = "#506070"
        p = core.save_project(p["id"], p)
    with pytest.raises(core.StudioError) as error:
        design_review.record_review(p["id"], payload(snapshot))
    assert error.value.status == 409
    assert not core.get_project(p["id"]).get("design_reviews")


@pytest.mark.parametrize("mutation", ["manual", "engine", "engine_mode", "brightness", "contrast", "saturation", "design", "font", "snapshot", "approved", "reference"])
def test_previously_approved_design_becomes_stale(static_project, mutation):
    p, root, code = static_project
    p, snapshot = capture(p)
    p = design_review.record_review(p["id"], payload(snapshot))
    if mutation == "manual":
        (root.parent / "PROMPT_MAESTRO.md").write_text("Changed fixture manual")
    elif mutation == "engine":
        code[0] = "c" * 64
    elif mutation == "engine_mode":
        p["settings"]["engine"] = "hyperframes"
    elif mutation in ("brightness", "contrast", "saturation"):
        p["timeline"][1].setdefault("effects", {})[mutation] = {"brightness": .2, "contrast": 1.5, "saturation": 0}[mutation]
    elif mutation == "design":
        p["timeline"][1]["motion_design"]["elements"][0]["width"] = .45
    elif mutation == "font":
        (root / p["fonts"]["accent"]).write_bytes(b"new fixture font bytes")
    elif mutation == "snapshot":
        (root / snapshot["path"]).write_bytes(b"changed fixture snapshot")
    elif mutation == "approved":
        (root / p["design_reviews"]["s_motion"]["approved_path"]).write_bytes(b"changed fixture approved PNG")
    else:
        reference = next(a for a in p["assets"] if a["id"] == "a_reference")
        (root / reference["path"]).write_bytes(b"changed fixture reference")
    assert design_review.production_errors(p)


def test_reference_change_before_approval_is_rejected(static_project):
    p, root, _ = static_project
    p, snapshot = capture(p)
    reference = next(a for a in p["assets"] if a["id"] == "a_reference")
    (root / reference["path"]).write_bytes(b"Changed reference fixture")
    with pytest.raises(core.StudioError) as error:
        design_review.record_review(p["id"], payload(snapshot))
    assert error.value.status == 409


def test_incoming_project_cannot_inject_design_or_tracking_receipts(static_project):
    p, _, _ = static_project
    forged = copy.deepcopy(p)
    forged.update(design_snapshots={"s_motion": {"approved": True}}, design_reviews={"s_motion": {"approved": True}},
                  tracking={"reviewed": True, "editorial_approved": True, "apply_automatically": True})
    saved = core.save_project(p["id"], forged)
    assert not saved.get("design_snapshots") and not saved.get("design_reviews") and not saved.get("tracking")


def test_edit_preserves_existing_server_owned_receipts_and_tracking(static_project):
    p, _, _ = static_project
    p, _ = capture(p)
    p["tracking"] = {"reviewed": False, "source_sha256": p["assets"][0]["sha256"]}
    p = core.save_project(p["id"], p, action="tracking_measured")
    original_snapshots = copy.deepcopy(p["design_snapshots"])
    original_tracking = copy.deepcopy(p["tracking"])
    incoming = copy.deepcopy(p)
    incoming["design_snapshots"] = {"s_motion": {"approved": True, "sha256": "forged"}}
    incoming["tracking"] = {"reviewed": True}
    incoming["name"] = "Ordinary fixture edit"
    result = core.save_project(p["id"], incoming)
    assert result["design_snapshots"] == original_snapshots
    assert result["tracking"] == original_tracking


def test_source_related_uses_canonical_lineage_despite_forged_project_metadata():
    source = {"id": "source", "sha256": "raw_hash"}
    derived = {"id": "derived", "sha256": "derived_hash", "metadata": {"provenance": {"source_asset_id": "source", "source_sha256": "raw_hash"}}}
    candidate = {**derived, "metadata": {}}
    assert core.source_related(candidate, source, [source, derived]) is True


def test_source_related_handles_hash_alias_transitive_ancestors_and_cycles():
    source = {"id": "source", "sha256": "raw_hash"}
    first = {"id": "first", "sha256": "first_hash", "metadata": {"source": "source"}}
    second = {"id": "second", "sha256": "second_hash", "metadata": {"provenance": {"source_sha256": "first_hash"}}}
    alias = {"id": "alias", "sha256": "raw_hash"}
    cycle_a = {"id": "ca", "sha256": "ca_hash", "metadata": {"source": "cb"}}
    cycle_b = {"id": "cb", "sha256": "cb_hash", "metadata": {"source": "ca"}}
    catalog = [source, first, second, alias, cycle_a, cycle_b]
    assert core.source_related(second, source, catalog)
    assert core.source_related(alias, source, catalog)
    assert core.source_related(cycle_a, source, catalog)  # ambiguity rejects use
    assert not core.source_related({"id": "independent", "sha256": "other"}, source, catalog)
    assert not core.source_related(first, None, catalog)


def test_native_static_capture_cannot_hide_source_derivative(static_project):
    p, _, _ = static_project
    reference = next(a for a in p["assets"] if a["id"] == "a_reference")
    reference["metadata"] = {"provenance": {"source_asset_id": p["source"], "source_sha256": p["assets"][0]["sha256"]}}
    p["timeline"][1]["motion_design"]["elements"] = [{"id": "media", "type": "media", "asset_id": reference["id"], "x": .1, "y": .1, "width": .5, "height": .3}]
    with jobs.cpu_slot(), pytest.raises(core.StudioError, match="distinto del crudo"):
        design_review.make_snapshot(p, {"scene_id": "s_motion"})


def test_unsafe_scene_id_cannot_write_outside_its_design_directory(static_project):
    p, root, _ = static_project
    scene = p["timeline"][1]
    scene["id"] = "../../../assets/images/victim"
    sentinel = root / "assets/images/victim_candidate.png"
    sentinel.write_bytes(b"own fixture sentinel; preserve")
    with jobs.cpu_slot(), pytest.raises(core.StudioError):
        design_review.make_snapshot(p, {"scene_id": scene["id"]})
    assert sentinel.read_bytes() == b"own fixture sentinel; preserve"


def test_reference_change_during_copy_cannot_be_promoted(static_project, monkeypatch):
    p, root, _ = static_project
    p, snapshot = capture(p)
    reference = next(a for a in p["assets"] if a["id"] == "a_reference")
    original_copy = design_review.shutil.copyfile
    def changing_copy(source, target, *args, **kwargs):
        answer = original_copy(source, target, *args, **kwargs)
        (root / reference["path"]).write_bytes(b"reference changed while approving")
        return answer
    monkeypatch.setattr(design_review.shutil, "copyfile", changing_copy)
    with pytest.raises(core.StudioError) as error:
        design_review.record_review(p["id"], payload(snapshot))
    assert error.value.status == 409
    assert not core.get_project(p["id"]).get("design_reviews")


def test_failed_save_preserves_previously_approved_bytes(static_project, monkeypatch):
    p, root, _ = static_project
    p, snapshot = capture(p)
    p = design_review.record_review(p["id"], payload(snapshot))
    approved = root / p["design_reviews"]["s_motion"]["approved_path"]
    original_bytes = approved.read_bytes()
    p["timeline"][1]["motion_design"]["elements"][0]["color"] = "#607080"
    p = core.save_project(p["id"], p)
    p, newer_snapshot = capture(p)
    def save_failure(*args, **kwargs):
        raise core.StudioError("Fixture commit failure", 409)
    monkeypatch.setattr(core, "save_project", save_failure)
    with pytest.raises(core.StudioError, match="Fixture commit failure"):
        design_review.record_review(p["id"], payload(newer_snapshot))
    assert approved.read_bytes() == original_bytes


@pytest.mark.parametrize("mutation", ["manual", "engine", "reference", "approved_bytes"])
def test_post_commit_race_rolls_back_project_and_approved_png(static_project, monkeypatch, mutation):
    p, root, code = static_project
    p, snapshot = capture(p)
    p = design_review.record_review(p["id"], payload(snapshot))
    approved = root / p["design_reviews"]["s_motion"]["approved_path"]
    approved_before = approved.read_bytes()
    p["timeline"][1]["motion_design"]["elements"][0]["color"] = "#8090a0"
    p = core.save_project(p["id"], p)
    p, new_snapshot = capture(p)
    canonical_before = core.project_path(p["id"]).read_bytes()
    reference = next(a for a in p["assets"] if a["id"] == "a_reference")
    original_save = core.save_project
    def save_then_change(*args, **kwargs):
        answer = original_save(*args, **kwargs)
        if mutation == "manual":
            (root.parent / "INSTRUCCIONES.md").write_text("Fixture manual changed after JSON commit")
        elif mutation == "engine":
            code[0] = "d" * 64
        elif mutation == "reference":
            (root / reference["path"]).write_bytes(b"Fixture reference changed after JSON commit")
        else:
            approved.write_bytes(b"Fixture approved PNG changed after JSON commit")
        return answer
    monkeypatch.setattr(core, "save_project", save_then_change)
    with pytest.raises(core.StudioError) as error:
        design_review.record_review(p["id"], payload(new_snapshot))
    assert error.value.status == 409
    assert core.project_path(p["id"]).read_bytes() == canonical_before
    assert approved.read_bytes() == approved_before


def test_post_commit_failure_without_prior_approval_removes_only_own_approved_png(static_project, monkeypatch):
    p, root, _ = static_project
    p, snapshot = capture(p)
    canonical_before = core.project_path(p["id"]).read_bytes()
    reference = next(a for a in p["assets"] if a["id"] == "a_reference")
    source_before = (root / p["assets"][0]["path"]).read_bytes()
    original_save = core.save_project
    def save_then_change(*args, **kwargs):
        answer = original_save(*args, **kwargs)
        (root / reference["path"]).write_bytes(b"Fixture reference changed after first approval")
        return answer
    monkeypatch.setattr(core, "save_project", save_then_change)
    with pytest.raises(core.StudioError):
        design_review.record_review(p["id"], payload(snapshot))
    assert core.project_path(p["id"]).read_bytes() == canonical_before
    assert not (root / f"projects/{p['id']}/designs/s_motion_approved.png").exists()
    assert (root / p["assets"][0]["path"]).read_bytes() == source_before


def test_split_static_digest_binds_region_source_crop_and_pose(static_project):
    p,root,_=static_project
    scene=p["timeline"][1]
    motion=design.design_digest(scene,p)
    scene["type"]="split"
    split=design.design_digest(scene,p)
    assert split!=motion
    for key,value in (("source_in",1.),("focus_x",.2),("focus_y",.8)):
        edited=copy.deepcopy(scene);edited[key]=value
        assert design.design_digest(edited,p)!=split
    anchored=copy.deepcopy(scene);anchored["camera_anchors"]=[{"time":0,"focus_x":.1,"focus_y":.2,"chin_y":.7}]
    assert design.design_digest(anchored,p)!=split
    # Later camera movement does not change the static pose being reviewed.
    first=design.design_digest(anchored,p)
    anchored["camera_anchors"].append({"time":1,"focus_x":.9,"focus_y":.8,"chin_y":.6})
    assert design.design_digest(anchored,p)==first
    assert design_review.production_errors(p)


def test_native_split_static_snapshot_contains_authentic_camera_in_lower_region(static_project):
    import subprocess
    from studio.render import split_height
    p,root,_=static_project
    source=next(a for a in p["assets"] if a["id"]==p["source"])
    scene=p["timeline"][1];scene.update(type="split",source_in=0)
    with jobs.cpu_slot():
        subprocess.run(["ffmpeg","-v","error","-y","-filter_threads","1","-f","lavfi","-i","color=c=red:s=160x284:r=1:d=1","-an","-c:v","libx264","-threads","1",str(root/source["path"])],check=True)
        source["sha256"]=core.digest(root/source["path"])
        snapshot=design_review.make_snapshot(p,{"scene_id":scene["id"]})
    with Image.open(root/snapshot["path"]) as picture:
        assert picture.size==(160,284)
        upper=split_height(284)
        assert picture.getpixel((0,upper-1))==(16,32,48)
        r,g,b=picture.getpixel((0,upper));assert r>240 and g<8 and b<8
    assert snapshot["approved"] is False
