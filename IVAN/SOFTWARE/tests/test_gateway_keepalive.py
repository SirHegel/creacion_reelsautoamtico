"""Regression for the real browser failure '{}GET' after logout on keepalive."""
import http.client
import json

from test_gateway_security import portal,session,request
from studio import gateway
import pytest


def headers_for(portal,session):
    return {"Host":f"127.0.0.1:{portal['server'].server_port}","Cookie":f"{gateway.COOKIE}={session['session']}",
            "X-CSRF-Token":session["principal"]["csrf_token"],"X-Workspace-ID":session["principal"]["workspace"]["id"],"Content-Type":"application/json"}


def test_logout_consumes_json_before_next_get_on_same_connection(portal,session):
    connection=http.client.HTTPConnection("127.0.0.1",portal["server"].server_port,timeout=5)
    try:
        connection.request("POST","/api/auth/logout",b"{}",headers_for(portal,session))
        response=connection.getresponse();assert response.status==200;response.read()
        original_socket=connection.sock
        connection.request("GET","/api/auth/me",headers=headers_for(portal,session))
        response=connection.getresponse()
        assert response.status==200 and json.loads(response.read())=={"authenticated":False}
        assert connection.sock is original_socket
    finally:connection.close()


def test_provider_delete_consumes_body_and_preserves_http_alignment(portal,session):
    connection=http.client.HTTPConnection("127.0.0.1",portal["server"].server_port,timeout=5)
    try:
        connection.request("DELETE","/api/providers/openai",b"{}",headers_for(portal,session))
        response=connection.getresponse();assert response.status==200;response.read()
        connection.request("GET","/api/auth/me",headers=headers_for(portal,session))
        response=connection.getresponse();assert response.status==200 and json.loads(response.read())["authenticated"]
    finally:connection.close()


def test_revocation_consumes_body_and_preserves_http_alignment(portal,session):
    value=portal["store"].create_token(session["principal"],{"name":"Regression token"})
    connection=http.client.HTTPConnection("127.0.0.1",portal["server"].server_port,timeout=5)
    try:
        connection.request("DELETE","/api/agent-tokens/"+value["id"],b"{}",headers_for(portal,session))
        response=connection.getresponse();assert response.status==200;response.read()
        connection.request("GET","/api/auth/me",headers=headers_for(portal,session))
        response=connection.getresponse();assert response.status==200 and json.loads(response.read())["authenticated"]
    finally:connection.close()


def test_get_body_rejected_and_socket_closed(portal,session):
    status,_,data=request(portal,"GET","/api/auth/me",body=b"{}",session=session)
    assert status==400 and "cuerpo" in data["error"]


def test_scoped_editor_alias_is_rejected_before_loading_legacy_client(portal,session):
    path="/w/"+session["principal"]["workspace"]["id"]+"/editor"
    status,_,data=request(portal,"GET",path,session=session)
    assert status==404 and "/editor" in data["error"]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_review_evidence_cookie_requires_explicit_workspace_path(portal,session,method):
    """Transport fixture proves the guard, without claiming media decoding."""
    before=len(portal["transport"].requests)
    route="/api/assets/a_private/review-files/frame_00.png"
    status,_,data=request(portal,method,route,session=session)
    assert status==409
    if method=="GET":assert "espacio" in data["error"]
    assert len(portal["transport"].requests)==before


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_review_evidence_foreign_workspace_rejected_before_backend(portal,session,method):
    foreign=portal["principals"][1]["workspace"]["id"]
    before=len(portal["transport"].requests)
    status,_,_=request(portal,method,"/w/"+foreign+"/api/assets/a_private/review-files/frame_00.png",session=session)
    assert status==409 and len(portal["transport"].requests)==before


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_review_evidence_own_workspace_routes_to_authenticated_owner(portal,session,method):
    wid=session["principal"]["workspace"]["id"]
    route="/api/assets/a_private/review-files/frame_00.png"
    status,headers,_=request(portal,method,"/w/"+wid+route,session=session)
    assert status==200 and "no-store" in headers["Cache-Control"]
    transported=portal["transport"].requests[-1]
    assert transported["owner"]==wid and transported["path"]==route and transported["method"]==method


def test_review_evidence_header_workspace_mismatch_even_with_own_path(portal,session):
    wid=session["principal"]["workspace"]["id"]
    other=portal["principals"][1]["workspace"]["id"]
    before=len(portal["transport"].requests)
    status,_,_=request(portal,"GET","/w/"+wid+"/api/assets/a_private/review-files/frame_00.png",session=session,headers={"X-Workspace-ID":other})
    assert status==409 and len(portal["transport"].requests)==before
