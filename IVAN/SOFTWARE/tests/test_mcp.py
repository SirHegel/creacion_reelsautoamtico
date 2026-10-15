"""MCP JSON-RPC and stdio regressions, without real agents or models."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from studio import core, mcp
from test_api import api_workspace, cli_process


def rpc(method, params=None, rid=1):
    value = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        value["params"] = params
    return mcp.handle(value)


def tool(name, arguments=None):
    return rpc("tools/call", {"name": name, "arguments": arguments or {}})


def decoded_tool(response):
    return json.loads(response["result"]["content"][0]["text"])


def test_initialize_lists_actual_tools_and_notification_has_no_response(api_workspace):
    initialized = rpc("initialize", {"protocolVersion": "2024-11-05", "clientInfo": {"name": "fixture", "version": "1"}})
    assert initialized["jsonrpc"] == "2.0" and initialized["id"] == 1
    assert initialized["result"]["serverInfo"]["name"] == "ascendia-studio"
    listed = rpc("tools/list")
    names = {t["name"] for t in listed["result"]["tools"]}
    assert {"studio_status", "project_create", "project_update", "asset_import", "preview_render", "task_claim"}.issubset(names)
    assert not {"shell", "execute_shell", "publish_drive", "approve_automatically"} & names
    assert all(t["inputSchema"]["additionalProperties"] is False for t in listed["result"]["tools"])
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_tools_call_shared_project_store_and_revision_conflicts(api_workspace):
    created = tool("project_create", {"name": "MCP canonical project"})
    assert created["result"]["isError"] is False
    p = decoded_tool(created)
    assert core.get_project(p["id"])["name"] == "MCP canonical project"
    update = json.loads(json.dumps(p))
    update["name"] = "MCP edited"
    saved = tool("project_update", {"project_id": p["id"], "project": update})
    assert saved["result"]["isError"] is False
    conflict = tool("project_update", {"project_id": p["id"], "project": update})
    assert conflict["result"]["isError"] is True
    assert "cambió" in decoded_tool(conflict)["error"]
    got = decoded_tool(tool("project_get", {"project_id": p["id"]}))
    assert got["name"] == "MCP edited" and got["revision"] == p["revision"] + 1


@pytest.mark.parametrize("name,args", [
    ("execute_shell", {"command": "touch outside"}),
    ("project_get", {}),
    ("project_create", {"unexpected": True}),
    ("project_create", {"name": 12}),
    ("asset_import", {"path": "anything", "kind": "unsupported"}),
    ("project_update", {"project_id": "missing", "project": []}),
])
def test_invalid_tool_arguments_return_errors_and_do_not_create_projects(api_workspace, name, args):
    result = tool(name, args)
    assert result["result"]["isError"] is True
    assert "error" in decoded_tool(result)
    assert core.project_list() == []


def test_asset_import_rejects_paths_and_symlinks_outside_software(api_workspace):
    outside = api_workspace.parent / "outside.wav"
    outside.write_bytes(b"preserve fixture")
    (api_workspace / "escape.wav").symlink_to(outside)
    for path in ("../outside.wav", str(outside), "escape.wav"):
        result = tool("asset_import", {"path": path})
        assert result["result"]["isError"] is True
        assert "SOFTWARE" in decoded_tool(result)["error"]
    assert core.assets() == [] and outside.read_bytes() == b"preserve fixture"


@pytest.mark.parametrize("seconds", [0, -.1, 11, True, "10", float("nan"), float("inf")])
def test_number_schema_enforces_finite_preview_range(api_workspace, seconds):
    p = core.create_project("validation schema fixture")
    result = tool("project_validate", {"project_id": p["id"], "seconds": seconds})
    assert result["result"]["isError"] is True
    assert "error" in decoded_tool(result)


def test_unknown_rpc_method_and_invalid_request_shape(api_workspace):
    result = rpc("unknown/method")
    assert result["error"]["code"] == -32601
    for request in ({"jsonrpc": "1.0", "id": 1, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 1, "method": 123}):
        response = mcp.handle(request)
        assert response["error"]["code"] == -32600
    result = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []})
    assert result["error"]["code"] == -32602


def test_stdio_handles_bad_json_then_continues_valid_request(api_workspace):
    lines = "{bad json}\n" + json.dumps({"jsonrpc": "2.0", "id": "list", "method": "tools/list"}) + "\n"
    completed = cli_process(api_workspace, ["mcp"], stdin=lines)
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(responses) == 2
    assert responses[0]["error"]["code"] == -32700
    assert responses[1]["id"] == "list" and responses[1]["result"]["tools"]
    assert not list(api_workspace.rglob("__pycache__"))


def test_stdio_scope_and_preview_gate_are_json_only(api_workspace):
    p = core.create_project("unprepared MCP fixture")
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "studio_status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "preview_render", "arguments": {"project_id": p["id"]}}},
    ]
    completed = cli_process(api_workspace, ["mcp"], stdin="".join(json.dumps(row) + "\n" for row in requests))
    assert completed.returncode == 0, completed.stderr
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert decoded_tool(responses[0])["scope"] == str(api_workspace)
    assert responses[1]["result"]["isError"] is True
    assert "error" in decoded_tool(responses[1])


def test_mcp_protocol_negotiation_never_advertises_arbitrary_input():
    for value in ([],None,False,123):
        result=rpc("initialize",{"protocolVersion":value})
        assert result["error"]["code"]==-32602
    assert rpc("initialize",{"protocolVersion":"2099-future"})["result"]["protocolVersion"]=="2025-11-25"
    assert rpc("initialize",{"protocolVersion":"2025-03-26"})["result"]["protocolVersion"]=="2025-03-26"
