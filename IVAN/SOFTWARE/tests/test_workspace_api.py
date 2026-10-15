import hashlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from studio import branding,core,server


@pytest.fixture
def workspace_api(tmp_path,monkeypatch):
    root=tmp_path/"app";root.mkdir();branding.bootstrap(root,"Marca HTTP")
    monkeypatch.setattr(core,"ROOT",root);monkeypatch.setattr(core,"WORKSPACE_MODE",True)
    monkeypatch.setattr(server,"ROOT",root)
    monkeypatch.setenv("ASCENDIA_BACKEND_TOKEN","fixture-backend-token")
    core.setup()
    local=ThreadingHTTPServer(("127.0.0.1",0),server.Handler)
    thread=threading.Thread(target=local.serve_forever,daemon=True);thread.start()
    yield local,root
    local.shutdown();thread.join(timeout=5);local.server_close()


def request(local,method,path,body=None,token="fixture-backend-token"):
    connection=http.client.HTTPConnection("127.0.0.1",local.server_port,timeout=10)
    headers={"X-Ascendia-Backend":token}
    if body is not None:headers["Content-Type"]="application/json";body=json.dumps(body).encode()
    connection.request(method,path,body,headers)
    response=connection.getresponse();raw=response.read();mime=response.getheader("Content-Type","");code=response.status
    connection.close()
    return code,json.loads(raw) if mime.startswith("application/json") else raw


def test_real_worker_create_branding_apply_and_font_bytes(workspace_api):
    local,root=workspace_api
    status,project=request(local,"POST","/api/projects",{"name":"Reel HTTP"})
    assert status==201,project
    assert project["style"]["branding"]["fonts"]["primary"]["family"]=="Source Sans 3"
    value=branding.get_branding(root)
    config={k:value[k] for k in ("revision","name","colors","fonts","logo_asset_id","instructions","language")}
    config["fonts"]["primary"]="a_a4ba3a92350ebb031da0"
    branding.save_branding(root,config)
    route="/api/projects/"+project["id"]+"/branding"
    assert request(local,"POST",route,{"expected_revision":project["revision"],"extra":True})[0]==400
    status,changed=request(local,"POST",route,{"expected_revision":project["revision"]})
    assert status==200,changed
    assert changed["style"]["branding"]["fonts"]["primary"]["family"]=="Anton"
    assert request(local,"POST",route,{"expected_revision":project["revision"]})[0]==409
    status,data=request(local,"GET","/api/fonts/primary?project_id="+project["id"])
    assert status==200 and hashlib.sha256(data).hexdigest()==changed["style"]["branding"]["fonts"]["primary"]["sha256"]


def test_worker_secret_required_for_all_api_and_static_routes(workspace_api):
    local,_=workspace_api
    for path in ("/api/projects","/api/font-library","/api/fonts/primary","/app.js"):
        assert request(local,"GET",path,token="")[0]==401
        assert request(local,"GET",path,token="é")[0]==401


def test_remote_http_mcp_dispatch_not_importerror(workspace_api):
    local,_=workspace_api
    status,result=request(local,"POST","/api/mcp",{"jsonrpc":"2.0","id":1,"method":"tools/list"})
    assert status==200 and len(result["result"]["tools"])>=40
    assert {"ivan_automate","branding_get","branding_apply"}<={t["name"] for t in result["result"]["tools"]}
    status,result=request(local,"POST","/api/mcp",{"jsonrpc":"2.0","method":"notifications/initialized"})
    assert status==202 and result==b""
