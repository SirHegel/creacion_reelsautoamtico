"""Portable free designs remap foreign media IDs and preserve source lineage."""
import json
import zipfile

import pytest
from PIL import Image

from studio import bundles, core, jobs
from test_api import api_workspace, fixture_media, real_project
from test_bundles import new_workspace, rewrite


@pytest.mark.parametrize("derivative", [False, True])
def test_free_design_roundtrip_remaps_ids_and_cannot_erase_derivative_lineage(api_workspace, fixture_media, monkeypatch, derivative):
    p = real_project(api_workspace, fixture_media)
    image = api_workspace / ".estado/tmp/free_alpha.png"
    Image.new("RGBA", (32, 32), (100, 200, 50, 128)).save(image)
    metadata = {"source": p["source"]} if derivative else {"content": "Synthetic alpha graphic"}
    graphic = core.register_asset(image, kind="image", metadata=metadata)
    p["assets"].append(graphic)
    p["timeline"] = [{"id": "free", "type": "motion", "template": "custom", "start": 0, "end": 12,
                      "motion_design": {"elements": [{"id": "graphic", "type": "media", "asset_id": graphic["id"],
                        "x": .1, "y": .2, "width": .3, "height": .3, "mask": {"type": "circle"},
                        "keyframes": [{"time": 0, "mask_progress": 0}, {"time": 2, "mask_progress": 1}]}]}}]
    p = core.save_project(p["id"], p)
    archive = api_workspace / jobs.export_bundle(p["id"])["path"]
    def foreign_ids(value):
        next(a for a in value["assets"] if a["id"] == graphic["id"])["id"] = "foreign_graphic"
        value["timeline"][0]["motion_design"]["elements"][0]["asset_id"] = "foreign_graphic"
        value.update(tracking={"forged": True}, design_reviews={"free": {"approved": True}}, design_snapshots={"forged": True})
    changed = rewrite(api_workspace, archive, update=foreign_ids)
    root, incoming = new_workspace(api_workspace, changed, monkeypatch)
    restored = bundles.import_bundle(incoming)["project"]
    element = restored["timeline"][0]["motion_design"]["elements"][0]
    assert element["asset_id"] == graphic["id"] != "foreign_graphic"
    assert element["mask"] == {"type": "circle"}
    assert element["keyframes"][1]["mask_progress"] == 1
    assert not restored.get("tracking") and not restored.get("design_reviews") and not restored.get("design_snapshots")
    actual = core.asset(element["asset_id"])
    assert core.source_related(actual, core.asset(restored["source"]), core.assets()) is derivative
    if derivative:
        assert actual["metadata"]["provenance"]["source_sha256"] == core.asset(restored["source"])["sha256"]
        assert any("presencia del presentador en motion" in error for error in core.validate_project(restored)["errors"])


def test_missing_custom_media_is_rejected_before_registering_any_file(api_workspace, fixture_media, monkeypatch):
    p = real_project(api_workspace, fixture_media)
    archive = api_workspace / jobs.export_bundle(p["id"])["path"]
    def invalid_media(value):
        value["timeline"] = [{"id": "free", "type": "motion", "template": "custom", "start": 0, "end": 12,
            "motion_design": {"elements": [{"id": "missing", "type": "media", "asset_id": "unbundled"}]}}]
    changed = rewrite(api_workspace, archive, update=invalid_media)
    root, incoming = new_workspace(api_workspace, changed, monkeypatch)
    with pytest.raises(core.StudioError, match="motion"):
        bundles.import_bundle(incoming)
    assert core.assets() == [] and core.project_list() == []
