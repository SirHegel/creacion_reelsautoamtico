"""Independent real HTTP gateway audit with fixture-only transport backends.

These tests exercise authentication, routing and byte ranges. They do not
decode media, call an inference provider, seed production or start a renderer.
All accounts, databases and fixture files live under SOFTWARE/.estado/tmp.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from studio import accounts, core, gateway, mcp, providers, server


class TransportFixtureHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_args):
        pass

    def do_HEAD(self):
        self.reply(True)

    def do_GET(self):
        self.reply()

    def do_POST(self):
        self.reply()

    def do_PUT(self):
        self.reply()

    def do_DELETE(self):
        self.reply()

    def reply(self, head=False):
        owner = self.server.owners.get(self.headers.get("X-Ascendia-Backend"))
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b""
        self.server.requests.append({"owner": owner, "path": self.path,
                                     "method": self.command, "body": body,
                                     "headers": dict(self.headers)})
        if owner is None:
            return self.send_bytes(b"unauthenticated fixture", 401, head=head)
        if self.path.startswith("/api/media/"):
            if self.path != "/api/media/a_shared_fixture":
                return self.send_json({"error": "Fixture asset not found"}, 404, head)
            # Same asset ID for both users; different private transport bytes.
            raw = ("PRIVATE:" + owner).encode()
            range_header = self.headers.get("Range")
            if range_header == "bytes=0-7":
                return self.send_bytes(raw[:8], 206, "video/mp4", head,
                                       {"Content-Range": f"bytes 0-7/{len(raw)}",
                                        "Accept-Ranges": "bytes"})
            return self.send_bytes(raw, 200, "video/mp4", head)
        if self.path == "/api/mcp":
            # Real MCP dispatch; only read-only fixture status is requested.
            value = mcp.handle(json.loads(body))
            if value is None:
                return self.send_bytes(b"", 202, head=head)
            return self.send_json(value, head=head)
        if self.path == "/api/assets" and self.command == "POST":
            return self.send_json({"id": "a_shared_fixture", "owner": owner,
                                   "url": "/api/media/a_shared_fixture",
                                   "received_sha256": hashlib.sha256(body).hexdigest()}, 201)
        return self.send_json({"owner": owner, "name": "/api/users",
                               "url": "/api/media/a_shared_fixture",
                               "projects": [{"id": "p_shared_fixture",
                                             "name": "/api/users", "owner": owner}]}, head=head)

    def send_json(self, value, status=200, head=False):
        self.send_bytes(json.dumps(value, allow_nan=False).encode(), status,
                        "application/json", head)

    def send_bytes(self, raw, status=200, mime="application/octet-stream", head=False, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(raw)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not head:
            self.wfile.write(raw)


class FixtureBackends:
    def __init__(self, store, transport):
        self.store, self.transport = store, transport
        self.calls = []

    def get(self, principal):
        wid = principal["workspace"]["id"]
        self.calls.append(wid)
        secret = "fixture-internal-" + wid
        self.transport.owners[secret] = wid
        return {"root": self.store.workspace_path(principal),
                "port": self.transport.server_port, "secret": secret}


@contextmanager
def listening(server_object):
    server_object.daemon_threads = True
    thread = threading.Thread(target=server_object.serve_forever,
                              kwargs={"poll_interval": .02}, daemon=True)
    thread.start()
    try:
        yield server_object
    finally:
        server_object.shutdown()
        server_object.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


@pytest.fixture(scope="module")
def portal(tmp_path_factory):
    root = tmp_path_factory.mktemp("independent_gateway")
    assert root.resolve().is_relative_to(accounts.CODE_ROOT / ".estado/tmp")
    store = accounts.Accounts(root)
    registered = [store.register({"email": name + "@fixture.invalid", "name": name,
                                  "password": "Fixture-only-password-123!"})
                  for name in ("Alice", "Bob")]
    transport = ThreadingHTTPServer(("127.0.0.1", 0), TransportFixtureHandler)
    transport.owners, transport.requests = {}, []
    public = ThreadingHTTPServer(("127.0.0.1", 0), gateway.GatewayHandler)
    public.public_origin = f"http://127.0.0.1:{public.server_port}"
    public.allowed_hosts = {f"127.0.0.1:{public.server_port}"}
    public.accounts = store
    public.backends = FixtureBackends(store, transport)
    with listening(transport), listening(public):
        yield {"root": root, "store": store, "server": public, "transport": transport,
               "principals": [item["principal"] for item in registered]}


@pytest.fixture
def session(portal):
    # New fixture sessions avoid revocation/expiry bleeding between tests.
    return portal["store"].new_session(portal["principals"][0]["user"]["id"])


def request(portal, method, path, body=None, session=None, bearer=None, headers=None):
    scope = session["principal"] if session else None
    values = {}
    if session:
        values.update(Cookie=f"{gateway.COOKIE}={session['session']}",
                      **{"X-CSRF-Token": scope["csrf_token"],
                         "X-Workspace-ID": scope["workspace"]["id"]})
    if bearer:
        values["Authorization"] = "Bearer " + bearer
    values.update(headers or {})
    if body is not None:
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
            values.setdefault("Content-Type", "application/json")
        values["Content-Length"] = str(len(body))
    connection = http.client.HTTPConnection("127.0.0.1", portal["server"].server_port, timeout=5)
    try:
        connection.request(method, path, body=body, headers=values)
        response = connection.getresponse()
        raw = response.read()
        result = json.loads(raw) if raw and "json" in response.getheader("Content-Type", "") else raw
        return response.status, dict(response.getheaders()), result
    finally:
        connection.close()


def own_path(session, path):
    return "/w/" + session["principal"]["workspace"]["id"] + path


@pytest.mark.parametrize("method,path", [("GET", "/api/projects"), ("GET", "/api/providers"),
                                         ("HEAD", "/api/media/a_shared_fixture"),
                                         ("POST", "/mcp")])
def test_anonymous_private_routes_never_reach_backend(portal, method, path):
    before = len(portal["server"].backends.calls)
    status, headers, result = request(portal, method, path, {} if method == "POST" else None)
    assert status == 401 and "no-store" in headers["Cache-Control"]
    assert len(portal["server"].backends.calls) == before


@pytest.mark.parametrize("headers", [{"Origin": "https://attacker.invalid"},
                                    {"Sec-Fetch-Site": "cross-site"},
                                    {"Host": "attacker.invalid"}])
def test_login_origin_and_host_rejected_before_account_creation(portal, headers):
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, "POST", "/api/auth/register",
                           {"email": "blocked@fixture.invalid", "name": "Blocked",
                            "password": "Fixture-only-password-123!"}, headers=headers)
    assert status == 403 and len(portal["server"].backends.calls) == before
    with portal["store"].connect() as db:
        assert not db.execute("SELECT id FROM users WHERE email=?", ("blocked@fixture.invalid",)).fetchone()


def test_real_login_cookie_and_public_principal_do_not_echo_credentials(portal):
    status, headers, value = request(portal, "POST", "/api/auth/login",
                                    {"email": "Alice@fixture.invalid", "password": "Fixture-only-password-123!"})
    assert status == 200 and value["authenticated"] is True
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and "Max-Age=" in cookie
    assert "session" not in value and "credential_hash" not in value and "password" not in value
    assert value["workspace"]["id"] == portal["principals"][0]["workspace"]["id"]


@pytest.mark.parametrize("header", [{"X-CSRF-Token": ""}, {"X-CSRF-Token": "incorrect"},
                                     {"X-CSRF-Token": "é"}])
def test_mutation_csrf_failure_never_proxies(portal, session, header):
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, "POST", own_path(session, "/api/projects"), {}, session, headers=header)
    assert status == 403 and len(portal["server"].backends.calls) == before


def test_unscoped_mutation_requires_explicit_current_workspace(portal, session):
    status, _, _ = request(portal, "POST", "/api/projects", {}, session,
                           headers={"X-Workspace-ID": ""})
    assert status == 409


def test_unknown_bearer_never_falls_back_to_valid_session_cookie(portal, session):
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, "GET", own_path(session, "/api/projects"),
                           session=session, bearer="invalid-fixture-agent-token")
    assert status == 401 and len(portal["server"].backends.calls) == before


def test_chunked_request_rejected_before_proxy(portal, session):
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, "POST", own_path(session, "/api/projects"), {},
                           session, headers={"Transfer-Encoding": "chunked"})
    assert status == 400 and len(portal["server"].backends.calls) == before


@pytest.mark.parametrize("path_kind", ["uri", "header"])
@pytest.mark.parametrize("method", ["GET", "HEAD", "POST"])
def test_other_workspace_selector_denied_before_proxy(portal, session, path_kind, method):
    other = portal["principals"][1]["workspace"]["id"]
    path, values = own_path(session, "/api/projects"), {}
    if path_kind == "uri":
        path = "/w/" + other + "/api/projects"
    else:
        values["X-Workspace-ID"] = other
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, method, path, {} if method == "POST" else None,
                           session, headers=values)
    assert status == 409 and len(portal["server"].backends.calls) == before


def test_two_accounts_same_asset_id_receive_only_their_bytes_and_range(portal, session):
    other = portal["store"].new_session(portal["principals"][1]["user"]["id"])
    results = []
    for login in (session, other):
        status, headers, raw = request(portal, "GET", own_path(login, "/api/media/a_shared_fixture"), session=login)
        assert status == 200 and raw == ("PRIVATE:" + login["principal"]["workspace"]["id"]).encode()
        assert "no-store" in headers["Cache-Control"]
        results.append(raw)
        status, headers, partial = request(portal, "GET", own_path(login, "/api/media/a_shared_fixture"),
                                           session=login, headers={"Range": "bytes=0-7"})
        assert status == 206 and partial == raw[:8] and headers["Content-Range"].startswith("bytes 0-7/")
        status, headers, empty = request(portal, "HEAD", own_path(login, "/api/media/a_shared_fixture"), session=login)
        assert status == 200 and empty == b"" and int(headers["Content-Length"]) == len(raw)
    assert results[0] != results[1]


def test_unscoped_session_media_denied_even_with_correct_header(portal, session):
    status, _, _ = request(portal, "GET", "/api/media/a_shared_fixture", session=session)
    assert status == 409


def test_scope_urls_preserves_narration_and_proxy_upload_drops_sensitive_headers(portal, session):
    status, _, value = request(portal, "GET", own_path(session, "/api/projects"), session=session)
    assert status == 200 and value["name"] == value["projects"][0]["name"] == "/api/users"
    assert value["url"] == own_path(session, "/api/media/a_shared_fixture")
    data = b"Fixture-only-upload-not-real-media"
    status, _, value = request(portal, "POST", own_path(session, "/api/assets"), data, session,
                               headers={"X-File-Name": "fixture.mp4", "X-Asset-Kind": "video",
                                        "X-Ascendia-Backend": "attacker-chosen-internal", "X-Leak": "not-forwarded"})
    assert status == 201 and value["received_sha256"] == hashlib.sha256(data).hexdigest()
    forwarded = portal["transport"].requests[-1]["headers"]
    assert forwarded["X-Ascendia-Backend"] == "fixture-internal-" + session["principal"]["workspace"]["id"]
    assert not any(name in forwarded for name in ("Cookie", "Authorization", "X-CSRF-Token", "X-Leak"))


def test_url_named_semantic_parameter_and_provenance_are_not_transport_addresses():
    """SceneIR parameters are literal data, including an author-chosen 'url'."""
    wid = "w_" + "a" * 32
    document = {"url": "/api/media/a_fixture", "preview_url": "/api/files/assets/previews/a.mp4",
                "text": "/api/users",
                "scene_ir": {"document": {"parameters": {"url": "/api/users"}}},
                "provenance": {"url": "/api/users", "observed_content": "/api/users"}}
    scoped = gateway.scoped_urls(document, wid)
    assert scoped["url"] == "/w/" + wid + document["url"]
    assert scoped["preview_url"] == "/w/" + wid + document["preview_url"]
    assert scoped["text"] == document["text"]
    assert scoped["scene_ir"] == document["scene_ir"]
    assert scoped["provenance"] == document["provenance"]


def test_expiry_and_logout_revoke_future_media_ranges(portal, session):
    principal = session["principal"]
    with portal["store"].connect() as db:
        db.execute("UPDATE sessions SET expires=? WHERE hash=?", (int(time.time()) - 1, principal["credential_hash"]))
    status, _, _ = request(portal, "GET", own_path(session, "/api/media/a_shared_fixture"), session=session)
    assert status == 401
    login = portal["store"].new_session(principal["user"]["id"])
    status, headers, value = request(portal, "POST", "/api/auth/logout", {}, login)
    assert status == 200 and value == {"authenticated": False} and "Max-Age=0" in headers["Set-Cookie"]
    assert request(portal, "GET", own_path(login, "/api/projects"), session=login)[0] == 401


def test_token_one_time_display_owner_and_revocation(portal, session):
    status, _, token = request(portal, "POST", "/api/agent-tokens", {"name": "Audit fixture agent"}, session)
    assert status == 201 and token["workspace_id"] == session["principal"]["workspace"]["id"]
    status, _, listed = request(portal, "GET", "/api/agent-tokens", session=session)
    assert status == 200 and token["id"] in {row["id"] for row in listed["tokens"]}
    assert token["token"] not in json.dumps(listed)
    other = portal["store"].new_session(portal["principals"][1]["user"]["id"])
    assert request(portal, "DELETE", "/api/agent-tokens/" + token["id"], session=other)[0] == 404
    status, _, value = request(portal, "GET", "/api/projects", bearer=token["token"])
    assert status == 200 and value["owner"] == session["principal"]["workspace"]["id"]
    assert request(portal, "DELETE", "/api/agent-tokens/" + token["id"], session=session)[0] == 200
    assert request(portal, "GET", "/api/projects", bearer=token["token"])[0] == 401


@pytest.mark.parametrize("method,path", [("GET", "/api/providers"), ("PUT", "/api/providers/openai"),
                                         ("POST", "/api/providers/openai/test"),
                                         ("POST", "/api/agent-tokens")])
def test_agent_credentials_cannot_manage_provider_keys_or_mint_credentials(portal, session, method, path):
    created = portal["store"].create_token(session["principal"], {"name": "Permission fixture"})
    before = len(portal["server"].backends.calls)
    status, _, _ = request(portal, method, path, {} if method != "GET" else None, bearer=created["token"])
    assert status == 403 and len(portal["server"].backends.calls) == before


def test_provider_storage_is_encrypted_scoped_and_not_arbitrary_endpoint(portal, session):
    fixture_key = "fixture-only-not-valid-api-secret"
    status, _, _ = request(portal, "PUT", "/api/providers/openai",
                           {"api_key": fixture_key, "model": "fixture-model", "endpoint": "http://127.0.0.1"}, session)
    assert status == 400
    status, _, saved = request(portal, "PUT", "/api/providers/openai",
                               {"api_key": fixture_key, "model": "fixture-model"}, session)
    assert status == 200 and saved["configured"] is True and "ciphertext" not in saved
    private = portal["store"].workspace_path(session["principal"]) / ".estado/providers.json"
    assert fixture_key.encode() not in private.read_bytes() and private.stat().st_mode & 0o777 == 0o600
    other = portal["store"].new_session(portal["principals"][1]["user"]["id"])
    status, _, catalog = request(portal, "GET", "/api/providers", session=other)
    assert status == 200 and catalog["connections"] == {}
    assert request(portal, "POST", "/api/providers/openai/test", {"confirmed": False}, session)[0] == 400


def test_http_mcp_status_does_not_scan_other_workspaces(portal, session, monkeypatch):
    from studio import branding
    token = portal["store"].create_token(session["principal"], {"name": "Read-only MCP fixture"})
    monkeypatch.setattr(core, "WORKSPACE_MODE", True)
    monkeypatch.setattr(server, "ROOT", portal["store"].workspace_path(session["principal"]))
    monkeypatch.setattr(server, "capabilities", lambda: {})
    # The transport fixture has no seeded font/project data. Stub only its
    # branding descriptor, not the /proc isolation or actual MCP dispatch.
    monkeypatch.setattr(branding, "get_branding", lambda _root: {"snapshot": {
        "base": "ivan_yo_clone", "name": "Fixture profile", "editorial_approved": False}})
    original = Path.iterdir
    def no_proc(path):
        if path == Path("/proc"):
            pytest.fail("A private workspace must not enumerate another process")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", no_proc)
    rpc = {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "studio_status", "arguments": {}}}
    status, _, response = request(portal, "POST", "/mcp", rpc, bearer=token["token"])
    assert status == 200 and response["id"] == 7 and response["result"]["isError"] is False
    value = json.loads(response["result"]["content"][0]["text"])
    assert value["active_external"] == []
    assert request(portal, "POST", "/mcp", rpc, session=session)[0] == 401
    invalid = {"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": []}
    status, _, response = request(portal, "POST", "/mcp", invalid, bearer=token["token"])
    assert status == 200 and response["error"]["code"] == -32602


def test_account_symlink_guard_rejects_before_external_fixture_mkdir(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(accounts.CODE_ROOT / ".estado/tmp")
    scope, outside = tmp_path / "scope", tmp_path / "outside_scope"
    scope.mkdir(); outside.mkdir()
    (scope / ".estado").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(accounts, "CODE_ROOT", scope)
    with pytest.raises(core.StudioError) as error:
        accounts.Accounts(scope)
    assert error.value.status == 403 and list(outside.iterdir()) == []


def test_workspace_alias_cannot_select_sibling_fixture(portal, session):
    root = portal["root"]
    wid = session["principal"]["workspace"]["id"]
    path = root / "workspaces" / wid
    target = portal["store"].workspace_path(session["principal"])
    # No deleting a user workspace: test a unique account-owned alias path.
    principal = {**session["principal"], "workspace": {"id": "w_" + "f" * 32, "name": "Alias fixture"}}
    alias = root / "workspaces" / principal["workspace"]["id"]
    assert alias != path and not alias.exists()
    alias.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(core.StudioError) as error:
            portal["store"].workspace_path(principal)
        assert error.value.status == 403
    finally:
        alias.unlink()


@pytest.mark.parametrize("provider,reply", [
    ("openai", {"status": "completed", "output": [None]}),
    ("openai", {"status": "completed", "output": [{"type": "message", "content": [1]}]}),
    ("openai", {"status": "incomplete", "output": [{"type": "message", "content": [{"type": "output_text", "text": "partial"}]}]}),
    ("anthropic", {"content": [None]}),
    ("anthropic", {"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens"}),
    ("gemini", {"choices": [None]}),
    ("gemini", {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}),
])
def test_malformed_upstream_data_has_no_phantom_success(tmp_path, monkeypatch, provider, reply):
    assert tmp_path.resolve().is_relative_to(accounts.CODE_ROOT / ".estado/tmp")
    connection = providers.Connections(tmp_path)
    connection.put(provider, {"api_key": "fixture-only-no-valid-provider-key", "model": "fixture-model"})
    raw = json.dumps(reply).encode()
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def read(self, _limit): return raw
    class Opener:
        def open(self, request_value, timeout):
            assert request_value.full_url == providers.REGISTRY[provider]["endpoint"] and timeout == 45
            return Response()
    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *_args: Opener())
    with pytest.raises(core.StudioError) as error:
        connection.infer(provider, "Fixture system", "Fixture prompt")
    assert error.value.status == 502
    assert "fixture-only-no-valid-provider-key" not in str(error.value)
    assert connection.catalog()["connections"][provider]["last_test"] is None
