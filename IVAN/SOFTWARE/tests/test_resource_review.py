"""Private resource samples, honest scope, optimistic writes and stale guards."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

import pytest
from PIL import Image

from studio import analysis, core, jobs, resource_review as reviews

SOFTWARE = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((SOFTWARE / ".estado/tmp").resolve())
    root = tmp_path / "private_user"
    root.mkdir()
    original = core.confined
    def local(path, root_override=None, must_exist=False, **kwargs):
        return original(path, root=kwargs.get("root", root_override) or root, must_exist=must_exist)
    for module in (core, jobs, analysis):
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module, "confined", local)
    monkeypatch.setattr(core, "WORKSPACE_MODE", True)
    monkeypatch.setattr(core, "HASH_CACHE", {})
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
    core.setup()
    core.atomic_json(".estado/assets.json", [])
    # The source engine fingerprints are checked in dedicated stale tests;
    # unrelated concurrently written modules are outside this unit's contract.
    monkeypatch.setattr(reviews, "_engine", lambda: {"code": "resource_fixture_1", "manual": "profile_fixture_1"})
    return root


def canonical_image(root, color="red"):
    path = root / "assets/images/owned.png"
    Image.new("RGBA", (80, 120), color).save(path)
    row = {"id": "a_private_image", "path": "assets/images/owned.png", "name": "Un nombre no prueba contenido.png",
           "kind": "image", "sha256": core.digest(path), "md5": core.digest(path, "md5"), "size": path.stat().st_size,
           "duration": 0., "probe": {}, "metadata": {"provenance": {"operation": "uploaded_by_user"}},
           "verification": {"visual": False, "audio": False, "rights": "supplied_by_user_unverified"}}
    core.atomic_json(".estado/assets.json", [row])
    return row


def observed(prepared, **changes):
    return {"expected_source_sha256": prepared["source_sha256"], "expected_review_digest": prepared["expected_review_digest"],
            "receipt_sha256": prepared["receipt_sha256"], "reviewer": "Operador de prueba privada",
            "notes": "He observado la muestra local: fondo rojo uniforme y ningún rostro, texto ni interfaz.",
            "content": "Imagen sintética de prueba con un fondo rojo plano; no representa una función de software.",
            "interval": copy.deepcopy(prepared["interval"]), "scope": "observed_samples",
            "evidence": [{k: prepared["frames"][0][k] for k in ("path", "sha256")}],
            "visual_reviewed": True, "rights_declaration": "Soy el usuario que suministra este archivo de prueba; no es una autoridad de licencia.",
            **changes}


def test_actual_image_samples_pending_and_reused_without_observation(workspace):
    item = canonical_image(workspace)
    before = (workspace / item["path"]).read_bytes()
    result = reviews.prepare(item["id"])
    assert result["status"] == "pending" and result["visual_reviewed"] is False
    assert result["audio_listened"] is False and result["reel_approved"] is False
    assert result["proposal_model_vision"] == "deferred_not_executed"
    assert result["safe_zones"]["face_detected"] is False
    assert result["frames"][0]["time"] == 0 and result["sequence"] is None
    assert core.digest(workspace / result["frames"][0]["path"]) == result["frames"][0]["sha256"]
    with Image.open(workspace / result["frames"][0]["path"]) as pic:
        assert pic.size == (80, 120) and pic.getpixel((40, 60)) == (255, 0, 0, 255)
    repeated = reviews.prepare(item["id"])
    assert repeated["reused"] is True and repeated["receipt_sha256"] == result["receipt_sha256"]
    assert (workspace / item["path"]).read_bytes() == before
    assert reviews.current_review(item)["valid"] is False
    assert core.asset(item["id"])["verification"]["visual"] is False


def test_explicit_observation_updates_only_own_asset_and_keeps_rights_pending(workspace):
    item = canonical_image(workspace)
    other = {**copy.deepcopy(item), "id": "a_other", "name": "Otro recurso"}
    core.atomic_json(".estado/assets.json", [item, other])
    original = (workspace / item["path"]).read_bytes()
    prepared = reviews.prepare(item["id"])
    result = reviews.record(item["id"], observed(prepared))
    row = result["asset"]
    assert row["metadata"]["content"].startswith("Imagen sintética")
    assert row["verification"]["visual"] is True and row["verification"]["audio"] is False
    assert row["verification"]["rights"] == "supplied_by_user_unverified"
    assert result["editorial_approved"] is False and result["review"]["rights_authority"] is False
    assert reviews.current_review(row)["valid"] is True
    assert reviews.current_review(row)["coverage"] == "points_only"
    assert core.asset("a_other") == other
    assert (workspace / item["path"]).read_bytes() == original
    assert core.project_list() == []
    assert len(row["metadata"]["resource_review_history"]) == 1
    with pytest.raises(core.StudioError) as error:
        reviews.record(item["id"], observed(prepared))
    assert error.value.status == 409


@pytest.mark.parametrize("field,value", [("unknown", 1), ("samples", True), ("samples", 0), ("samples", 13),
    ("samples", 3.0), ("duration", float("nan")), ("duration", True), ("duration", 31), ("start", -1),
    ("start", float("inf")), ("max_width", False), ("max_width", 159), ("max_height", 1921),
    ("sequence", 1), ("sequence", "yes")])
def test_invalid_options_do_not_create_review_files(workspace, field, value):
    item = canonical_image(workspace)
    catalog = (workspace / ".estado/assets.json").read_bytes()
    with pytest.raises(core.StudioError):
        reviews.prepare(item["id"], {field: value})
    assert not (workspace / ".estado/resource_reviews").exists()
    assert (workspace / ".estado/assets.json").read_bytes() == catalog


@pytest.mark.parametrize("field,value", [("visual_reviewed", False), ("visual_reviewed", 1), ("sequence_viewed", "true"),
    ("reviewer", ""), ("notes", "filename looks nice"), ("content", "a logo"), ("rights_declaration", True),
    ("scope", "all_video"), ("scope", {}), ("expected_source_sha256", "0"), ("receipt_sha256", True),
    ("interval", {"start": True, "end": 0}), ("interval", {"start": 0, "end": float("nan")}),
    ("evidence", []), ("approved", True)])
def test_invalid_review_payload_no_catalog_or_private_seal_write(workspace, field, value):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    catalog = (workspace / ".estado/assets.json").read_bytes()
    data = observed(prepared)
    data[field] = value
    with pytest.raises(core.StudioError):
        reviews.record(item["id"], data)
    assert (workspace / ".estado/assets.json").read_bytes() == catalog
    assert not (workspace / ".estado/resource_reviews" / item["id"] / "review.json").exists()


@pytest.mark.parametrize("mutation", ["source", "frame", "manual", "code", "provenance", "content", "private_review", "claim", "symlink"])
def test_changed_original_evidence_code_or_claim_invalidates_review(workspace, monkeypatch, mutation):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    row = reviews.record(item["id"], observed(prepared))["asset"]
    assert reviews.current_review(row)["valid"]
    if mutation == "source":
        (workspace / item["path"]).write_bytes(b"changed source bytes")
    elif mutation == "frame":
        (workspace / prepared["frames"][0]["path"]).write_bytes(b"changed evidence")
    elif mutation in {"manual", "code"}:
        monkeypatch.setattr(reviews, "_engine", lambda: {"code": "changed" if mutation == "code" else "resource_fixture_1", "manual": "changed"})
    elif mutation in {"provenance", "content", "claim"}:
        catalog = core.assets()
        if mutation == "provenance":
            catalog[0]["metadata"]["provenance"]["operation"] = "forged"
        elif mutation == "content":
            catalog[0]["metadata"]["content"] = "Forjado: demo auténtica de Claude"
        else:
            catalog[0]["metadata"]["resource_review"]["reel_approved"] = True
        core.atomic_json(".estado/assets.json", catalog)
    elif mutation == "private_review":
        private = workspace / ".estado/resource_reviews" / item["id"] / "review.json"
        private.write_text("{}")
    else:
        path = workspace / prepared["frames"][0]["path"]
        moved = workspace / ".estado/tmp/samebytes.png"
        moved.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(moved)
    assert reviews.current_review(row)["valid"] is False


def test_forged_verified_catalog_without_private_observation_is_invalid(workspace):
    item = canonical_image(workspace)
    item["verification"]["visual"] = True
    item["metadata"].update(content="Nombre y logo no constituyen revisión", resource_review={"status": "observed", "visual_reviewed": True})
    core.atomic_json(".estado/assets.json", [item])
    assert reviews.current_review(item)["valid"] is False


def test_sequence_claim_cannot_be_created_from_isolated_image(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    with pytest.raises(core.StudioError, match="secuencia"):
        reviews.record(item["id"], observed(prepared, scope="sequence", sequence_viewed=True))


def test_evidence_outside_current_receipt_is_rejected(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    evidence = workspace / ".estado/tmp/unrelated.txt"
    evidence.write_text("Una observación ajena no prueba este recurso.")
    with pytest.raises(core.StudioError) as error:
        reviews.record(item["id"], observed(prepared, evidence=[{"path": core.relative(evidence), "sha256": core.digest(evidence)}]))
    assert error.value.status == 403


def test_private_scope_rejects_parent_global_store_and_path_aliases(workspace, monkeypatch):
    item = canonical_image(workspace)
    target = workspace / item["path"]
    alias = target.with_name("alias.png")
    alias.symlink_to(target)
    item["path"] = core.relative(alias.parent) + "/alias.png"
    core.atomic_json(".estado/assets.json", [item])
    with pytest.raises(core.StudioError) as error:
        reviews.prepare(item["id"])
    assert error.value.status == 403
    monkeypatch.setattr(core, "WORKSPACE_MODE", False)
    with pytest.raises(core.StudioError):
        reviews.prepare(item["id"])


def test_record_failure_after_catalog_commit_rolls_back_catalog_and_private_seal(workspace, monkeypatch):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    catalog = (workspace / ".estado/assets.json").read_bytes()
    original = core.atomic_json
    def fail_after(path, value):
        original(path, value)
        if path == ".estado/assets.json" and value[0].get("metadata", {}).get("resource_review", {}).get("status") == "observed":
            raise core.StudioError("fixture commit failure", 409)
    monkeypatch.setattr(core, "atomic_json", fail_after)
    with pytest.raises(core.StudioError, match="fixture commit"):
        reviews.record(item["id"], observed(prepared))
    assert (workspace / ".estado/assets.json").read_bytes() == catalog
    assert not (workspace / ".estado/resource_reviews" / item["id"] / "review.json").exists()


def test_new_preparation_invalidates_observation_without_duplicate_folders(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    row = reviews.record(item["id"], observed(prepared))["asset"]
    assert reviews.current_review(row)["valid"]
    updated = reviews.prepare(item["id"], {"max_width": 320})
    assert updated["reused"] is False and updated["status"] == "pending"
    assert core.asset(item["id"])["verification"]["visual"] is False
    assert reviews.current_review(item)["valid"] is False
    assert core.asset(item["id"])["metadata"]["visual_reviewed"] is False
    assert [p.name for p in (workspace / ".estado/resource_reviews").iterdir()] == [item["id"]]
    assert len(core.asset(item["id"])["metadata"]["resource_review_history"]) == 1


def test_source_mutated_during_sample_generation_never_commits_catalog(workspace, monkeypatch):
    item = canonical_image(workspace)
    original = reviews._sheet
    catalog = (workspace / ".estado/assets.json").read_bytes()
    def changed(*args):
        output = original(*args)
        (workspace / item["path"]).write_bytes(b"changed by independent fixture actor")
        return output
    monkeypatch.setattr(reviews, "_sheet", changed)
    with pytest.raises(core.StudioError) as error:
        reviews.prepare(item["id"])
    assert error.value.status == 409
    assert (workspace / ".estado/assets.json").read_bytes() == catalog
    assert not (workspace / ".estado/resource_reviews" / item["id"] / "receipt.json").exists()


def test_catalog_changed_during_preparation_is_a_review_cas_conflict(workspace, monkeypatch):
    item = canonical_image(workspace)
    original = reviews._sheet
    def changed(*args):
        output = original(*args)
        catalog = core.assets()
        catalog[0]["metadata"]["resource_review"] = {"status": "pending", "independent_change": True}
        core.atomic_json(".estado/assets.json", catalog)
        return output
    monkeypatch.setattr(reviews, "_sheet", changed)
    with pytest.raises(core.StudioError) as error:
        reviews.prepare(item["id"])
    assert error.value.status == 409
    assert core.asset(item["id"])["metadata"]["resource_review"]["independent_change"] is True


def test_prepare_commit_failure_restores_previous_evidence_and_observation(workspace, monkeypatch):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    row = reviews.record(item["id"], observed(prepared))["asset"]
    directory = workspace / ".estado/resource_reviews" / item["id"]
    files = {p.name: p.read_bytes() for p in directory.iterdir()}
    catalog = (workspace / ".estado/assets.json").read_bytes()
    original = core.atomic_json
    def fail(path, data):
        original(path, data)
        if path == ".estado/assets.json" and data[0]["metadata"]["resource_review"]["status"] == "pending":
            raise core.StudioError("fixture preparation commit failure", 409)
    monkeypatch.setattr(core, "atomic_json", fail)
    with pytest.raises(core.StudioError):
        reviews.prepare(item["id"], {"max_width": 320})
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == files
    assert (workspace / ".estado/assets.json").read_bytes() == catalog
    assert reviews.current_review(row)["valid"]


def test_second_explicit_observation_keeps_hash_chain_and_reuses_samples(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    first = reviews.record(item["id"], observed(prepared))
    again = reviews.prepare(item["id"])
    assert again["reused"] is True and reviews.current_review(first["asset"])["valid"]
    second = reviews.record(item["id"], observed(again, reviewer="Segundo revisor explícito"))
    history = second["asset"]["metadata"]["resource_review_history"]
    assert len(history) == 2 and history[1]["previous_sha256"] == history[0]["sha256"]
    assert second["review"]["previous_review_digest"] == first["review_digest"]
    assert reviews.current_review(second["asset"])["valid"]


@pytest.mark.parametrize("bad_path", ["assets", "/outside/image.png", "assets/images/../owned.png", ".estado/receipt.json"])
def test_malformed_source_paths_have_stable_errors(workspace, bad_path):
    item = canonical_image(workspace)
    item["path"] = bad_path
    core.atomic_json(".estado/assets.json", [item])
    with pytest.raises(core.StudioError):
        reviews.prepare(item["id"])


def test_preparation_refuses_store_then_cpu_lock_inversion(workspace):
    item = canonical_image(workspace)
    with core.LOCK:
        with pytest.raises(core.StudioError, match="reservarse"):
            reviews.prepare(item["id"])


def test_malformed_private_receipt_cannot_create_a_verified_record(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    path = workspace / prepared["receipt_path"]
    receipt = json.loads(path.read_text())
    receipt["visual_reviewed"] = True
    path.write_text(json.dumps(receipt))
    data = observed(prepared, receipt_sha256=core.digest(path))
    with pytest.raises(core.StudioError, match="afirmaciones"):
        reviews.record(item["id"], data)
    assert core.asset(item["id"])["verification"]["visual"] is False


def test_evidence_resolver_serves_only_current_samples_not_private_records(workspace):
    item = canonical_image(workspace)
    prepared = reviews.prepare(item["id"])
    assert reviews.evidence_file(item["id"], "frame_00.png") == workspace / prepared["frames"][0]["path"]
    assert reviews.evidence_file(item["id"], "contact_sheet.png").is_file()
    for name in ("receipt.json", "review.json", "../frame_00.png", "/frame_00.png", "unknown.png", []):
        with pytest.raises(core.StudioError):
            reviews.evidence_file(item["id"], name)
    frame = workspace / prepared["frames"][0]["path"]
    frame.write_bytes(b"tampered")
    with pytest.raises(core.StudioError):
        reviews.evidence_file(item["id"], "frame_00.png")


def test_cancel_before_preparation_preserves_asset_and_creates_no_evidence(workspace):
    item = canonical_image(workspace)
    before = (workspace / ".estado/assets.json").read_bytes()
    event = threading.Event();event.set()
    with pytest.raises(core.StudioError, match="Cancelado"):
        reviews.prepare(item["id"], cancel=event)
    assert (workspace / ".estado/assets.json").read_bytes() == before
    assert not (workspace / ".estado/resource_reviews").exists()


def test_cancel_from_final_progress_rolls_back_catalog_and_files(workspace):
    item = canonical_image(workspace)
    before = (workspace / ".estado/assets.json").read_bytes()
    event = threading.Event()
    progress = []
    def stop(value, message):
        progress.append((value, message));event.set()
    with pytest.raises(core.StudioError, match="Cancelado"):
        reviews.prepare(item["id"], progress=stop, cancel=event)
    assert progress and progress[-1][0] == 1
    assert (workspace / ".estado/assets.json").read_bytes() == before
    directory = workspace / ".estado/resource_reviews" / item["id"]
    assert not list(directory.iterdir())


def test_cancel_stops_only_own_child_promptly_without_files_or_catalog_write(workspace, monkeypatch):
    # Real private child process exercises cancellation, not a render or an
    # existing worker. No parent PID, credentials, or production files touched.
    event = threading.Event()
    children = []
    original = reviews.subprocess.Popen
    def capture(*args, **kwargs):
        p = original(*args, **kwargs);children.append(p);return p
    monkeypatch.setattr(reviews.subprocess, "Popen", capture)
    timer = threading.Timer(.15, event.set);timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(core.StudioError, match="Cancelado"):
            reviews._run([sys.executable, "-B", "-c", "import time;time.sleep(5)"], cancel=event)
    finally:
        timer.cancel();timer.join()
    assert time.monotonic() - started < 2
    assert len(children) == 1 and children[0].poll() is not None
    assert core.assets() == []


def test_actual_two_second_video_sample_pts_muted_sequence_and_explicit_scope(workspace):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg required for local CPU media fixture")
    path = workspace / "assets/broll/own_video.mp4"
    with jobs.cpu_slot():
        subprocess.run(["nice", "-n", "10", "ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x284:rate=10:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-threads", "2", "-filter_threads", "1", "-shortest", "-y", str(path)], cwd=workspace, check=True,
            env={**os.environ, "TMPDIR": str(workspace / ".estado/tmp"), "CUDA_VISIBLE_DEVICES": ""})
        probe = analysis.probe(path)
    item = {"id": "a_own_video", "path": core.relative(path), "kind": "broll", "name": "CPU test source.mp4",
            "sha256": core.digest(path), "md5": core.digest(path, "md5"), "size": path.stat().st_size,
            "duration": float(probe["format"]["duration"]), "probe": probe, "metadata": {}, "verification": {"visual": False}}
    core.atomic_json(".estado/assets.json", [item])
    original = path.read_bytes()
    prepared = reviews.prepare(item["id"], {"start": .2, "duration": 1., "samples": 3, "sequence": True})
    assert [round(f["time"], 1) for f in prepared["frames"]] == [.2, .7, 1.1]
    assert prepared["sequence"]["audio_included"] is False and .95 <= prepared["sequence"]["duration"] <= 1.1
    seen = observed(prepared, scope="sequence", sequence_viewed=True,
                    evidence=[{k: prepared["sequence"][k] for k in ("path", "sha256")}])
    seen["notes"] = "Afirmación de prueba del protocolo: la secuencia sintética fue suministrada para verificar el alcance continuo declarado."
    seen["content"] = "Patrón de prueba sintético de FFmpeg; no es b-roll semántico ni una observación editorial real."
    result = reviews.record(item["id"], seen)
    assert reviews.current_review(result["asset"])["coverage"] == "continuous_declared"
    assert reviews.current_review(result["asset"])["interval"] == {"start": .2, "end": 1.2}
    assert result["review"]["audio_listened"] is False and result["editorial_approved"] is False
    assert path.read_bytes() == original
    reused = reviews.prepare(item["id"], {"start": .2, "duration": 1., "samples": 3, "sequence": True})
    assert reused["reused"] is True and reused["receipt_sha256"] == prepared["receipt_sha256"]
