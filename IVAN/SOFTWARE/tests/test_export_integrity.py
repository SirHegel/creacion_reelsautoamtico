"""Editable commits preserve previous ZIPs when any input changes in flight."""
import copy
import zipfile

import pytest

from studio import core, jobs
from test_api import api_workspace, fixture_media, real_project


def test_changed_asset_before_packaging_preserves_existing_editable(api_workspace, fixture_media):
    p = real_project(api_workspace, fixture_media)
    exported = jobs.export_bundle(p["id"])
    archive = api_workspace / exported["path"]
    before = archive.read_bytes()
    core.confined(p["assets"][0]["path"]).write_bytes(b"changed actual bytes")
    with pytest.raises(core.StudioError, match="hashes inválidos"):
        jobs.export_bundle(p["id"])
    assert archive.read_bytes() == before


@pytest.mark.parametrize("changed", ["asset", "manual", "approved"])
def test_changed_inputs_during_zip_write_never_replace_previous_archive(api_workspace, fixture_media, monkeypatch, changed):
    p = real_project(api_workspace, fixture_media)
    exported = jobs.export_bundle(p["id"])
    archive = api_workspace / exported["path"]
    before = archive.read_bytes()
    approved = api_workspace / "projects" / p["id"] / "approved_preview.mp4"
    if changed == "approved":
        # Explicit unit fixture bypasses the unrelated editorial gate, without
        # claiming this fake byte file or synthetic reel received an approval.
        approved.write_bytes(b"fixture only; no customer approval")
        p["approved_export"] = {"path": core.relative(approved), "sha256": core.digest(approved)}
        core.atomic_json(core.project_path(p["id"]), p)
        monkeypatch.setattr(jobs, "approval_is_current", lambda project: True)
    original = zipfile.ZipFile.write
    did_change = []
    def changing_write(self, filename, arcname=None, *args, **kwargs):
        result = original(self, filename, arcname, *args, **kwargs)
        trigger = arcname == "approved_preview.mp4" if changed == "approved" else arcname == p["assets"][0]["path"]
        if trigger and not did_change:
            did_change.append(True)
            if changed == "manual":
                (api_workspace.parent / "PROMPT_MAESTRO.md").write_text("changed fixture manual during export")
            else:
                core.confined(filename).write_bytes(b"modified after successful ZIP CRC data write")
        return result
    monkeypatch.setattr(zipfile.ZipFile, "write", changing_write)
    with pytest.raises(core.StudioError, match="cambió"):
        jobs.export_bundle(p["id"])
    assert did_change and archive.read_bytes() == before
    assert not list((api_workspace / ".estado/tmp").glob("export_*.zip"))
    assert not list((api_workspace / ".estado/tmp").glob("motion_export_*.zip"))


def test_stale_approved_export_is_not_distributed_as_current(api_workspace, fixture_media):
    p = real_project(api_workspace, fixture_media)
    output = api_workspace / "projects" / p["id"] / "approved_preview.mp4"
    output.write_bytes(b"historical fixture bytes; no current approval")
    p["approved_export"] = {"path": core.relative(output), "sha256": core.digest(output)}
    core.atomic_json(core.project_path(p["id"]), p)
    result = jobs.export_bundle(p["id"])
    assert result["verified_crc_and_sha256"] is True
    with zipfile.ZipFile(api_workspace / result["path"]) as archive:
        assert "approved_preview.mp4" not in archive.namelist()
    assert output.read_bytes() == b"historical fixture bytes; no current approval"
