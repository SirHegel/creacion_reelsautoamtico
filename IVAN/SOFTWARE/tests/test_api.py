"""Real HTTP and CLI integration, isolated in SOFTWARE/.estado/tmp."""
from __future__ import annotations

import copy
import http.client
import hashlib
import io
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest

from studio import analysis, cli, core, jobs, mcp, server

REAL_ROOT = Path(__file__).resolve().parents[1]

BOOTSTRAP = """
import sys
from pathlib import Path
from studio import analysis, cli, core, jobs, mcp, server
workspace = Path(sys.argv[1]).resolve()
original_confined = core.confined
def local_confined(path, root_override=None, must_exist=False, **kwargs):
    return original_confined(path, root=kwargs.get('root', root_override) or workspace, must_exist=must_exist)
for module in (core, analysis, jobs, cli, mcp, server):
    if hasattr(module, 'ROOT'): module.ROOT = workspace
    if hasattr(module, 'confined'): module.confined = local_confined
core.MANUAL_ROOT = workspace.parent
jobs.SHARED_CPU_LOCK = workspace / '.estado/cpu_worker.lock'
if hasattr(server, 'MANUAL_ROOT'): server.MANUAL_ROOT = workspace.parent
cli.server_url = lambda: None
"""


@pytest.fixture
def api_workspace(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to((REAL_ROOT / ".estado/tmp").resolve()), "Run pytest with --basetemp=SOFTWARE/.estado/tmp/pytest_audit"
    root = tmp_path / "SOFTWARE"
    root.mkdir()
    original = core.confined
    def local_confined(path, root_override=None, must_exist=False, **kwargs):
        return original(path, root=kwargs.get("root", root_override) or root, must_exist=must_exist)
    for module in (core, analysis, jobs, cli, mcp, server):
        if hasattr(module, "ROOT"):
            monkeypatch.setattr(module, "ROOT", root)
        if hasattr(module, "confined"):
            monkeypatch.setattr(module, "confined", local_confined)
    monkeypatch.setattr(core, "MANUAL_ROOT", root.parent)
    monkeypatch.setattr(jobs, "SHARED_CPU_LOCK", root / ".estado/cpu_worker.lock")
    if hasattr(server, "MANUAL_ROOT"):
        monkeypatch.setattr(server, "MANUAL_ROOT", root.parent)
    for key in ("TMPDIR", "XDG_CACHE_HOME", "HF_HOME", "HUGGINGFACE_HUB_CACHE", "TORCH_HOME", "MPLCONFIGDIR", "NUMBA_CACHE_DIR", "TOKENIZERS_PARALLELISM", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "CUDA_VISIBLE_DEVICES"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    monkeypatch.setattr(core, "HASH_CACHE", {})
    monkeypatch.setattr(jobs, "QUEUE", queue.Queue())
    monkeypatch.setattr(jobs, "CANCEL", {})
    monkeypatch.setattr(jobs, "WORKER", None)
    # Never discover or talk to a separately running production/demo server.
    monkeypatch.setattr(cli, "server_url", lambda: None)
    core.setup()
    for name in core.DOCUMENTS:
        (root.parent / name).write_text("Synthetic fixture manual; not a client instruction.\n" + name, encoding="utf-8")
    for name in ("Sequel_Sans_Bold_Disp.ttf", "Scholar_Italic.ttf"):
        origin = REAL_ROOT / "assets/fonts" / name
        if not origin.is_file():
            pytest.skip("Exact fonts needed for isolated integration fixture")
        shutil.copyfile(origin, root / "assets/fonts" / name)
    return root


@pytest.fixture
def fixture_media(api_workspace):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg needed for actual media upload fixture")
    path = api_workspace / "synthetic.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-y", "-filter_threads", "1",
                    "-f", "lavfi", "-i", "color=c=blue:s=160x284:r=10:d=12",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
                    "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
                    "-threads", "1", "-shortest", str(path)], check=True,
                   cwd=api_workspace, env={**os.environ, "TMPDIR": str(api_workspace / ".estado/tmp")})
    return path


@pytest.fixture
def http_server(api_workspace):
    listener = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    listener.daemon_threads = True
    thread = threading.Thread(target=listener.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
    thread.start()
    yield listener
    listener.shutdown()
    listener.server_close()
    thread.join(timeout=3)


def request(listener, method, path, value=None, *, raw=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", listener.server_port, timeout=15)
    payload = raw if raw is not None else json.dumps(value).encode() if value is not None else None
    request_headers = {"Content-Type": "application/json"} if value is not None else {}
    request_headers.update(headers or {})
    try:
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        result = json.loads(data) if data and response.getheader("Content-Type", "").startswith("application/json") else data
        return response.status, dict(response.getheaders()), result
    finally:
        connection.close()


def real_project(root, media):
    asset = core.register_asset(media, metadata={"content": "Synthetic blue fixture with test tone", "source": "generated fixture"})
    asset["verification"]["visual"] = True
    catalog = core.assets()
    catalog[0] = asset
    core.atomic_json(".estado/assets.json", catalog)
    p = core.create_project("Synthetic isolated reel", asset["id"])
    p["settings"].update(width=160, height=284, fps=10)
    evidence = root / ".estado/tmp/observations.txt"
    evidence.write_text("Synthetic fixture evidence; no assertion of YO review.", encoding="utf-8")
    decision = {"search": "Synthetic fixture library", "reason": "Tests conceptual workflow renderer", "evidence": [".estado/tmp/observations.txt"]}
    p["timeline"] = [
        {"id": "hook", "start": 0., "end": 1.5, "type": "split", "template": "workflow", "title": "Una idea conecta", "chin_y": .65, "chin_reviewed": True, "decision": copy.deepcopy(decision)},
        {"id": "process", "start": 1.5, "end": 12., "type": "motion", "template": "workflow", "title": "Entrada y resultado", "decision": copy.deepcopy(decision)},
    ]
    p["transcript"] = {"status": "imported", "words": [{"start": 6., "end": 6.5, "word": "resultado"}], "segments": [{"start": 0., "end": 12., "text": "Una idea conecta entrada y resultado"}]}
    p["reference_review"] = {"identity_observations": "Synthetic test observations; not a production approval", "evidence": [".estado/tmp/observations.txt"]}
    p["audio"] = [{"asset_id": asset["id"], "start": 0., "end": 3., "source_in": 0., "gain_db": -25, "role": "sfx", "is_riser": True, "impact_at": 3., "visual_event": "Synthetic transfer"}]
    return core.save_project(p["id"], p)


def test_raw_upload_decodes_and_deduplicates_actual_content(http_server, fixture_media, api_workspace):
    data = fixture_media.read_bytes()
    status, headers, a = request(http_server, "POST", "/api/assets", raw=data,
                                 headers={"X-File-Name": "../../fixture.mp4", "X-Asset-Kind": "video"})
    assert status == 201
    assert a["name"] == "fixture.mp4"
    assert a["duration"] == pytest.approx(12., abs=.1)
    assert {s["codec_type"] for s in a["probe"]["streams"]} == {"video", "audio"}
    assert a["waveform"]["seconds"] == pytest.approx(12., abs=.2)
    assert a["thumbnails"] and all((api_workspace / p).is_file() for p in a["thumbnails"])
    status, _, b = request(http_server, "POST", "/api/assets", raw=data,
                          headers={"X-File-Name": "another.mov", "X-Asset-Kind": "video"})
    assert status == 201 and a["id"] == b["id"]
    assert len(core.assets()) == 1
    assert (api_workspace / a["path"]).read_bytes() == data
    assert not list((api_workspace / ".estado/tmp").glob("upload_*"))


def test_manual_response_hashes_the_same_bytes_it_displays(http_server, api_workspace, monkeypatch):
    # Simulate a manual changed between the initial inventory and its read.
    monkeypatch.setattr(server, "manual_fingerprints", lambda: {name: {"sha256": "stale"} for name in core.DOCUMENTS})
    code, _, result = request(http_server, "GET", "/api/manual")
    assert code == 200
    for doc in result["documents"]:
        assert doc["sha256"] == hashlib.sha256(doc["content"].encode()).hexdigest()
    p = core.create_project("Manual read fixture")
    expected = {doc["name"]: doc["sha256"] for doc in result["documents"]}
    before = core.project_path(p["id"]).read_bytes()
    (api_workspace.parent / "PROMPT_MAESTRO.md").write_text("A later fixture change", encoding="utf-8")
    code, _, error = request(http_server, "POST", f"/api/projects/{p['id']}/manual",
                             {"read_complete": True, "expected_fingerprints": expected})
    assert code == 409 and "manual cambió" in error["error"]
    assert core.project_path(p["id"]).read_bytes() == before


def test_range_head_suffix_and_invalid_range(http_server, api_workspace):
    path = api_workspace / "exports/test.mp4"
    content = b"0123456789abcdefghij"
    path.write_bytes(content)
    code, headers, data = request(http_server, "GET", "/api/files/exports/test.mp4", headers={"Range": "bytes=3-8"})
    assert code == 206 and data == content[3:9]
    assert headers["Content-Range"] == "bytes 3-8/20"
    code, _, data = request(http_server, "GET", "/api/files/exports/test.mp4", headers={"Range": "bytes=-4"})
    assert code == 206 and data == content[-4:]
    code, headers, data = request(http_server, "HEAD", "/api/files/exports/test.mp4")
    assert code == 200 and data == b"" and headers["Content-Length"] == "20"
    code, headers, data = request(http_server, "GET", "/api/files/exports/test.mp4", headers={"Range": "bytes=200-300"})
    assert code == 416 and headers["Content-Range"] == "bytes */20"


@pytest.mark.parametrize("headers", [{"Origin": "https://attacker.example"}, {"Origin": "null"}, {"Host": "attacker.example"}])
def test_reject_cross_origin_and_dns_rebinding_before_mutation(http_server, headers):
    code, _, result = request(http_server, "POST", "/api/projects", {"name": "blocked"}, headers=headers)
    assert code == 403 and "error" in result
    assert core.project_list() == []


def test_private_path_traversal_and_symlink_do_not_publish(http_server, api_workspace):
    secret = api_workspace / ".estado/tmp/secret.wav"
    secret.write_bytes(b"private fixture")
    outside = api_workspace.parent / "outside.wav"
    outside.write_bytes(b"fixture outside the isolated application root")
    (api_workspace / "exports/escape.wav").symlink_to(outside)
    for path in ("/api/files/.estado/tmp/secret.wav", "/api/files/../outside.wav", "/api/files/exports/escape.wav"):
        code, _, result = request(http_server, "GET", path)
        assert code == 403 and "error" in result
    assert secret.read_bytes() == b"private fixture"


def test_http_optimistic_revision_allows_one_concurrent_writer(http_server):
    code, _, p = request(http_server, "POST", "/api/projects", {"name": "first"})
    assert code == 201
    barrier = threading.Barrier(2)
    def edit(label):
        update = copy.deepcopy(p)
        update["name"] = label
        barrier.wait(timeout=5)
        return request(http_server, "PUT", "/api/projects/" + p["id"], update)[0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(edit, ["writer A", "writer B"]))
    assert sorted(codes) == [200, 409]
    saved = core.get_project(p["id"])
    assert saved["revision"] == p["revision"] + 1


def test_preview_and_full_render_gates_are_enforced_before_queueing(http_server):
    code, _, p = request(http_server, "POST", "/api/projects", {"name": "unprepared"})
    for seconds in (10, 12):
        code, _, result = request(http_server, "POST", "/api/projects/" + p["id"] + "/render", {"seconds": seconds})
        assert code == 409 and "error" in result
    assert jobs.list_jobs() == []
    code, _, result = request(http_server, "POST", "/api/projects/" + p["id"] + "/authorize", {"authorized": True, "notes": "Premature approval"})
    assert code == 409


def test_malformed_json_and_wrong_body_type_return_client_errors(http_server):
    for raw in (b"{broken", b"[]", b"null"):
        code, _, result = request(http_server, "POST", "/api/projects", raw=raw, headers={"Content-Type": "application/json"})
        assert code == 400 and "error" in result
    assert core.project_list() == []


def test_render_receipt_survives_jobs_and_editable_export(api_workspace, fixture_media):
    p = real_project(api_workspace, fixture_media)
    check = core.validate_project(p, strict=False)
    assert check["valid"], check
    narrative = core.validate_project(p, strict=True)
    assert not narrative["valid"] and any("HyperFrames/GSAP" in error for error in narrative["errors"])
    queued = jobs.submit(p["id"], "render", {"seconds": 10, "technical": True})
    jobs.execute(queued["id"])
    finished = jobs.get_job(queued["id"])
    assert finished["status"] == "completed", finished
    receipt = finished["result"]
    assert receipt["duration"] == pytest.approx(10., abs=.15)
    assert receipt["technical"]["original_voice_present"] is True
    assert receipt["technical"]["editorial_approved"] is False
    assert receipt["mode"] == "technical_library" and receipt["production_conformant"] is False
    assert {row["role"] for row in receipt["used_assets"]} >= {"narration", "split", "sfx"}
    persisted = core.get_project(p["id"])
    assert persisted["renders"][-1]["sha256"] == receipt["sha256"]
    assert persisted["review"] == {}
    bundle = jobs.export_bundle(p["id"])
    with zipfile.ZipFile(api_workspace / bundle["path"]) as archive:
        names = set(archive.namelist())
        assert {a["path"] for a in persisted["assets"]}.issubset(names)
        assert set(persisted["fonts"].values()).issubset(names)
        assert {"project.json", "transcript.srt", "transcript.vtt", "broll_manifest.csv"}.issubset(names)
        assert "approved_preview.mp4" not in names
        assert all(not n.startswith(".estado/") and "../" not in n for n in names)
        editable = json.loads(archive.read("project.json"))
        assert editable["id"] == persisted["id"] and editable["timeline"] == persisted["timeline"]
        for asset in persisted["assets"]:
            assert archive.read(asset["path"]) == (api_workspace / asset["path"]).read_bytes()


def cli_process(root, args, *, stdin=None):
    script = BOOTSTRAP + "\nraise SystemExit(cli.main(sys.argv[2:]))\n"
    return subprocess.run([sys.executable, "-B", "-c", script, str(root), *args], cwd=REAL_ROOT,
                          input=stdin, text=True, capture_output=True, timeout=30,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "TMPDIR": str(root / ".estado/tmp")})


def test_cli_status_returns_one_json_document_with_correct_scope(api_workspace):
    result = cli_process(api_workspace, ["status"])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["app"] == "Ascendia Studio"
    assert data["scope"] == str(api_workspace)
    assert data["capabilities"]["render"]["device"] == "cpu"
    assert data["capabilities"]["adobe_capcut_parity"]["available"] is False
    assert not list(api_workspace.rglob("__pycache__"))


def test_editable_bundle_normalizes_internal_font_path_aliases(api_workspace):
    p = core.create_project("Portable path fixture")
    p["fonts"]["primary"] = "../SOFTWARE/assets/fonts/Sequel_Sans_Bold_Disp.ttf"
    p["fonts"]["accent"] = str(api_workspace / "assets/fonts/Scholar_Italic.ttf")
    p = core.save_project(p["id"], p)
    result = jobs.export_bundle(p["id"])
    with zipfile.ZipFile(api_workspace / result["path"]) as archive:
        names = archive.namelist()
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)
        editable = json.loads(archive.read("project.json"))
        for font_path in editable["fonts"].values():
            assert not Path(font_path).is_absolute() and ".." not in Path(font_path).parts
            assert font_path in names


def test_cli_update_serializes_canonical_store_in_separate_processes(api_workspace):
    p = core.create_project("canonical concurrency")
    candidates = []
    for label in ("A", "B"):
        candidate = copy.deepcopy(p)
        candidate["name"] = "writer " + label
        path = api_workspace / f".estado/tmp/edit_{label}.json"
        path.write_text(json.dumps(candidate), encoding="utf-8")
        candidates.append(str(path.relative_to(api_workspace)))
    script = BOOTSTRAP + "\nraise SystemExit(cli.main(sys.argv[2:]))\n"
    processes = [subprocess.Popen([sys.executable, "-B", "-c", script, str(api_workspace), "update", p["id"], path],
                                  cwd=REAL_ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  env={**os.environ, "TMPDIR": str(api_workspace / ".estado/tmp")}) for path in candidates]
    outcomes = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=15)
        assert not stderr, stderr
        outcomes.append((process.returncode, json.loads(stdout)))
    assert sorted(code for code, _ in outcomes) == [0, 1]
    assert [data["status"] for code, data in outcomes if code] == [409]
    assert core.get_project(p["id"])["revision"] == p["revision"] + 1
    assert (api_workspace / ".estado/store.lock").is_file()
