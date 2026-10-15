"""Independent final regressions; every fixture stays in SOFTWARE/.estado/tmp."""
from __future__ import annotations

import copy
from pathlib import Path
import threading

import pytest

from studio import core, analysis, jobs, bundles, previews
from test_core import sandbox, valid_project


def fake_video_probe(unused):
    return {"format": {"duration": "2"}, "streams": [{"index": 0, "codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p"}]}


def fake_registration(monkeypatch):
    monkeypatch.setattr(analysis, "probe", fake_video_probe)
    monkeypatch.setattr(analysis, "thumbnails", lambda *args: [])
    monkeypatch.setattr(analysis, "waveform", lambda *args: [])


def test_source_change_during_import_is_conflict_and_preserves_source(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"before-probe")
    def changing_probe(path):
        source.write_bytes(b"after-probe-new-content")
        return fake_video_probe(path)
    monkeypatch.setattr(analysis, "probe", changing_probe)
    with pytest.raises(core.StudioError) as error:
        core.register_asset(source)
    assert error.value.status == 409
    assert source.read_bytes() == b"after-probe-new-content"
    assert not core.assets()


def test_existing_catalog_dedup_rejects_changed_canonical_and_keeps_upload(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"original-content")
    first = core.register_asset(source)
    canonical = sandbox / first["path"]
    canonical.write_bytes(b"changed-canonical-content")
    duplicate = sandbox / ".estado/tmp/duplicate.mp4"
    duplicate.write_bytes(b"original-content")
    with pytest.raises(core.StudioError) as error:
        core.register_asset(duplicate)
    assert error.value.status == 409
    assert duplicate.read_bytes() == b"original-content"
    assert canonical.read_bytes() == b"changed-canonical-content"


def test_unmanaged_canonical_target_is_not_overwritten(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"new-import-content")
    target = sandbox / "assets/video" / (core.digest(source)[:20] + ".mp4")
    target.write_bytes(b"existing-unmanaged-do-not-overwrite")
    with pytest.raises(core.StudioError) as error:
        core.register_asset(source)
    assert error.value.status == 409
    assert target.read_bytes() == b"existing-unmanaged-do-not-overwrite"
    assert source.read_bytes() == b"new-import-content"


def test_store_lock_path_failure_releases_thread_lock(sandbox, monkeypatch):
    lock = core.StoreLock()
    normal_confined = core.confined
    def fail_path(*args, **kwargs):
        raise core.StudioError("Fixture failed path")
    monkeypatch.setattr(core, "confined", fail_path)
    with pytest.raises(core.StudioError, match="Fixture failed path"):
        with lock:
            pytest.fail("A failed lock must not enter the transaction")
    monkeypatch.setattr(core, "confined", normal_confined)
    acquired = []
    def try_thread():
        success = lock.thread.acquire(timeout=.2)
        acquired.append(success)
        if success:
            lock.thread.release()
    thread = threading.Thread(target=try_thread, daemon=True)
    thread.start()
    thread.join(1)
    try:
        assert acquired == [True], "StoreLock leaked its RLock after path failure"
    finally:
        if acquired == [False]:
            lock.thread.release()


def test_completed_job_is_not_executed_again(sandbox, monkeypatch):
    project = valid_project(sandbox)
    job = jobs.submit(project["id"], "analyze", {"transcribe": False})
    calls = []
    def analyze(project, *unused):
        calls.append(True)
        return project
    monkeypatch.setattr(analysis, "analyze_project", analyze)
    jobs.execute(job["id"])
    assert jobs.get_job(job["id"])["status"] == "completed"
    completed = copy.deepcopy(jobs.get_job(job["id"]))
    jobs.execute(job["id"])
    assert len(calls) == 1
    assert jobs.get_job(job["id"])["status"] == completed["status"]
    assert jobs.get_job(job["id"])["result"] == completed["result"]


def test_bundle_mxf_asset_path_matches_supported_media_format():
    assert bundles._asset_path("assets/video/source.mxf") == "assets/video/source.mxf"


def test_preview_import_inside_cpu_slot_does_not_reacquire_it(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"cpu-slot-owned-fixture")
    observed = []
    def ensure(asset, root):
        observed.append((root, getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return {**asset, "preview_pending": True}
    monkeypatch.setattr(previews, "ensure_preview", ensure)
    jobs.CPU_ACTIVE.active = True
    try:
        item = core.register_asset(source)
    finally:
        jobs.CPU_ACTIVE.active = False
    assert item["preview_pending"]
    assert observed == [(sandbox, True, 0)]


def test_bundle_outer_store_lock_defers_preview_work(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"bundle-outer-lock-fixture")
    monkeypatch.setattr(previews, "ensure_preview", lambda *args: pytest.fail("Store-locked registration must defer preview CPU work"))
    with jobs.cpu_slot():
        with core.LOCK:
            item = core.register_asset(source)
    assert item["sha256"] == core.digest(sandbox / item["path"])


def test_public_import_rejects_store_then_cpu_lock_order(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"lock-order-fixture")
    with core.LOCK:
        with pytest.raises(core.StudioError) as error:
            core.register_asset(source)
    assert error.value.status == 409 and source.exists()
    assert not core.assets()


def test_public_execute_rejects_store_then_cpu_lock_order(sandbox, monkeypatch):
    project = valid_project(sandbox)
    job = jobs.submit(project["id"], "analyze", {"transcribe": False})
    monkeypatch.setattr(analysis, "analyze_project", lambda project, *unused: project)
    with core.LOCK:
        with pytest.raises(core.StudioError) as error:
            jobs.execute(job["id"])
    assert error.value.status == 409
    assert jobs.get_job(job["id"])["status"] == "queued"


def test_import_analysis_and_preview_own_cpu_before_store(sandbox, monkeypatch):
    fake_registration(monkeypatch)
    source = sandbox / ".estado/tmp/input.mp4"
    source.write_bytes(b"cpu-ingest-fixture")
    observations = []
    def recording_probe(path):
        observations.append(("probe", getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return fake_video_probe(path)
    def recording_thumbnails(*unused):
        observations.append(("thumbnails", getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return []
    def recording_preview(asset, root):
        observations.append(("preview", getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return asset
    monkeypatch.setattr(analysis, "probe", recording_probe)
    monkeypatch.setattr(analysis, "thumbnails", recording_thumbnails)
    monkeypatch.setattr(previews, "ensure_preview", recording_preview)
    core.register_asset(source)
    assert all(active for unused, active, depth in observations)
    assert [stage for stage, active, depth in observations] == ["probe", "thumbnails", "preview"]
    assert observations[-1][2] == 0
    assert not getattr(jobs.CPU_ACTIVE, "active", False)


def test_cpu_slot_nested_reuses_one_lease_and_resets_on_failure(sandbox):
    with pytest.raises(RuntimeError, match="fixture"):
        with jobs.cpu_slot():
            assert jobs.CPU_ACTIVE.active
            with jobs.cpu_slot():
                assert jobs.CPU_ACTIVE.active
            assert jobs.CPU_ACTIVE.active
            raise RuntimeError("fixture")
    assert jobs.CPU_ACTIVE.active is False


def test_cpu_slot_rejects_store_lock_inversion(sandbox):
    with core.LOCK:
        with pytest.raises(core.StudioError) as error:
            with jobs.cpu_slot():
                pytest.fail("Inverted lock order must not enter CPU slot")
    assert error.value.status == 409


def test_get_project_hydrates_preview_without_editorial_changes(sandbox):
    project = valid_project(sandbox)
    before_digest = core.editorial_digest(project)
    catalog = core.assets()
    catalog[0].update(preview_url="/api/files/assets/previews/fixture.mp4", preview_probe={"streams": []}, preview_is_derivative=True)
    core.atomic_json(".estado/assets.json", catalog)
    loaded = core.get_project(project["id"])
    assert loaded["assets"][0]["preview_url"] == catalog[0]["preview_url"]
    assert loaded["revision"] == project["revision"]
    assert loaded["assets"][0]["verification"] == project["assets"][0]["verification"]
    assert core.editorial_digest(loaded) == before_digest


def test_bundle_preview_wrapper_runs_after_outer_transaction(sandbox, monkeypatch):
    project = valid_project(sandbox)
    monkeypatch.setattr(bundles, "_import_bundle", lambda unused: {"project": project, "reused": False})
    called = []
    def registration(path, *args, **kwargs):
        called.append(getattr(core.LOCK.local, "depth", 0))
        return project["assets"][0]
    monkeypatch.setattr(core, "register_asset", registration)
    result = bundles.import_bundle(Path("ignored_by_mock.zip"))
    assert called == [0] and result["project"]["id"] == project["id"]


def test_bundle_materialize_and_preview_reuse_same_cpu_slot(sandbox, monkeypatch):
    project = valid_project(sandbox)
    called = []
    def import_stage(unused):
        called.append(("materialize", getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return {"project": project, "reused": False}
    def registration(path, *args, **kwargs):
        called.append(("preview", getattr(jobs.CPU_ACTIVE, "active", False), getattr(core.LOCK.local, "depth", 0)))
        return project["assets"][0]
    monkeypatch.setattr(bundles, "_import_bundle", import_stage)
    monkeypatch.setattr(core, "register_asset", registration)
    bundles.import_bundle(Path("ignored.zip"))
    assert called == [("materialize", True, 0), ("preview", True, 0)]
