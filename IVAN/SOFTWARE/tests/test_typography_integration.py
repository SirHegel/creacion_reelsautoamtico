"""HTTP/CLI/MCP typography contracts against an isolated SOFTWARE fixture."""
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil

import pytest

from studio import cli, core, fonts, jobs, mcp, scene_ir, typography
from test_api import api_workspace, http_server, request, cli_process

SOFTWARE = Path(__file__).resolve().parents[1]


def element(**extra):
    return {"id": "heading", "type": "text", "text": "Árbol y acción", "font": "primary",
            "font_size": 84, "x": .1, "y": .2, "width": .8, "height": .5, **extra}


@pytest.fixture
def selected_font(api_workspace):
    incoming = api_workspace / ".estado/tmp/Anton.ttf"
    shutil.copyfile(SOFTWARE / "assets/fonts/a4ba3a92350ebb031da0.ttf", incoming)
    return core.register_asset(incoming)


def test_http_font_upload_is_real_face_deduplicated_and_cannot_claim_licensed(http_server, api_workspace):
    data = (SOFTWARE / "assets/fonts/08df266400933d3178d0.otf").read_bytes()
    code, _, first = request(http_server, "POST", "/api/assets", raw=data,
        headers={"X-File-Name": "SourceSans3-Regular.otf", "X-Asset-Kind": "font"})
    assert code == 201 and first["kind"] == "font"
    assert first["font_info"]["family"] == "Source Sans 3" and first["font_info"]["style"] == "Regular"
    assert first["sha256"] == hashlib.sha256(data).hexdigest()
    code, _, second = request(http_server, "POST", "/api/assets", raw=data,
        headers={"X-File-Name": "Renamed.otf", "X-Asset-Kind": "font"})
    assert code == 201 and second["id"] == first["id"] and len(core.assets()) == 1
    code, _, library = request(http_server, "GET", "/api/font-library")
    assert code == 200 and library["fonts"][0]["available"]
    assert library["fonts"][0]["license"]["status"] == "supplied_by_user_unverified"
    assert library["automatic_substitution"] is False and library["synthetic_weights"] is False


@pytest.mark.parametrize("name,kind", [("TooBig.ttf", "font"), ("TooBig.otf", "image"), ("Opaque.bin", "font")])
def test_http_font_cap_rejects_before_reading_body_or_creating_upload(http_server, api_workspace, name, kind):
    before = list((api_workspace / ".estado/tmp").iterdir())
    code, _, result = request(http_server, "POST", "/api/assets", raw=b"",
        headers={"X-File-Name": name, "X-Asset-Kind": kind, "Content-Length": str(fonts.MAX_FONT_BYTES + 1)})
    assert code == 413 and "16 MiB" in result["error"]
    assert list((api_workspace / ".estado/tmp").iterdir()) == before and core.assets() == []


def test_http_layout_measures_unattached_catalog_font_without_saving_or_approval(http_server, api_workspace, selected_font):
    p = core.create_project("Local draft")
    before = core.project_path(p["id"]).read_bytes()
    body = {"project_id": p["id"], "element": element(font_asset_id=selected_font["id"],
        text_style={"align": "center", "letter_spacing": 2}, text_animation={"preset": "typewriter"}),
        "scene_duration": 2, "width": 360, "height": 640}
    code, _, result = request(http_server, "POST", "/api/text-layout", body)
    assert code == 200 and result["font"]["family"] == "Anton"
    assert result["font"]["sha256"] == selected_font["sha256"]
    assert result["persisted"] is False and result["approved"] is False
    assert core.project_path(p["id"]).read_bytes() == before
    assert core.get_project(p["id"])["assets"] == []
    assert str(api_workspace) not in json.dumps(result)
    code, headers, data = request(http_server, "GET", "/api/typography-client.js")
    assert code == 200 and "javascript" in headers["Content-Type"] and data.decode() == typography.CLIENT_JS


def test_http_layout_body_cap_is_json_error_without_store_change(http_server, api_workspace):
    p = core.create_project("Read-only draft")
    before = core.project_path(p["id"]).read_bytes()
    code, _, response = request(http_server, "POST", "/api/text-layout", raw=b" " * 32769)
    assert code == 413 and "error" in response
    assert core.project_path(p["id"]).read_bytes() == before


def test_cli_and_mcp_presets_font_layout_match_http_contract(api_workspace, selected_font):
    p = core.create_project("Private CLI contract")
    before = core.project_path(p["id"]).read_bytes()
    path = api_workspace / ".estado/tmp/text-element.json"
    path.write_text(json.dumps(element(font_asset_id=selected_font["id"])), encoding="utf-8")
    result = cli_process(api_workspace, ["text-layout", p["id"], str(path), "--duration", "2", "--width", "360", "--height", "640"])
    assert result.returncode == 0, result.stdout + result.stderr
    measured = json.loads(result.stdout)
    assert measured["font"]["sha256"] == selected_font["sha256"] and not measured["persisted"]
    for command in ("font-library", "text-presets"):
        completed = cli_process(api_workspace, [command])
        assert completed.returncode == 0 and isinstance(json.loads(completed.stdout), dict)
    tools = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
    assert len(tools) >= 45
    assert len(tools) == len({tool['name'] for tool in tools})
    assert {"font_library", "text_layout", "text_presets", "job_get", "job_cancel"}.issubset({t["name"] for t in tools})
    response = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
        "name": "text_layout", "arguments": {"project_id": p["id"], "element": element(font_asset_id=selected_font["id"]),
        "scene_duration": 2, "width": 360, "height": 640}}})
    assert not response["result"].get("isError")
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["font"] == measured["font"] and payload["layout"] == measured["layout"]
    assert core.project_path(p["id"]).read_bytes() == before


@pytest.mark.parametrize("body,expected", [(b"{broken", 400), (b"x" * 32769, 413), (b"\xff", 400)])
def test_cli_invalid_text_json_returns_protocol_error(api_workspace, body, expected):
    path = api_workspace / ".estado/tmp/invalid-element.json"
    path.write_bytes(body)
    result = cli_process(api_workspace, ["text-layout", "not_used", str(path)])
    assert result.returncode == 1 and not result.stderr
    assert json.loads(result.stdout)["status"] == expected


def test_cli_cancel_uses_owned_server_endpoint_and_validates_id_first(api_workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "get_job", lambda job_id: calls.append(("validate", job_id)) or {"id": job_id})
    monkeypatch.setattr(cli, "server_url", lambda: "http://127.0.0.1:9999")
    def live(request, timeout):
        calls.append(("request", request.full_url, request.data))
        return io.BytesIO(b'{"status":"cancel_requested"}')
    monkeypatch.setattr(cli.urllib.request, "urlopen", live)
    monkeypatch.setattr(jobs, "cancel_job", lambda job_id: pytest.fail("Live cancellation bypassed worker event"))
    assert cli.request_job_cancel("j_owned")["status"] == "cancel_requested"
    assert calls == [("validate", "j_owned"), ("request", "http://127.0.0.1:9999/api/jobs/j_owned/cancel", b"{}")]


def test_scene_ir_schema_carries_closed_typography_and_trim_clock():
    variants = scene_ir.describe_schema()["properties"]["components"]["items"]["oneOf"]
    props = next(v for v in variants if v["properties"]["type"].get("const") == "text")["properties"]
    assert props["font_asset_id"]["pattern"]
    assert props["text_style"]["additionalProperties"] is False
    assert props["text_style"]["properties"]["shadow"]["additionalProperties"] is False
    anim = props["text_animation"]
    assert anim["additionalProperties"] is False and set(anim["properties"]["preset"]["enum"]) == set(typography.PRESETS)
    assert {"clock_start", "clock_offset", "clock_duration"}.issubset(anim["properties"])


@pytest.mark.parametrize("channel,visible", [("stroke", True), ("shadow", True), ("stroke", False), ("shadow", False)])
def test_red_typographic_effect_requires_semantic_reason_only_when_visible(api_workspace, channel, visible):
    p = core.create_project("Semantic color fixture")
    style = {channel: {"color": "#ff0000", **({"width": 2 if visible else 0} if channel == "stroke" else {"enabled": visible})}}
    p["timeline"] = [{"id": "design", "start": 0, "end": 2, "type": "motion", "template": "custom",
                      "motion_design": {"elements": [element(text_style=style)]}}]
    errors = core.validate_project(p, strict=False)["errors"]
    assert any("rojo sin intención" in err for err in errors) is visible
    p["timeline"][0]["motion_design"]["elements"][0]["color_reason"] = "Advertencia explícita"
    assert not any("rojo sin intención" in err for err in core.validate_project(p, strict=False)["errors"])
