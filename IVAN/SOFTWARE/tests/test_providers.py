import json
import urllib.error

import pytest

from studio import providers
from studio.core import StudioError

KEY="fixture-only-key-12345678"


@pytest.fixture
def connections(tmp_path):
    return providers.Connections(tmp_path)


def configured(connections,pid="openai"):
    connections.put(pid,{"api_key":KEY,"model":"my-exact-model","label":"Propia"})


def mock_response(monkeypatch,payload,observed):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,maximum):return json.dumps(payload).encode()
    class Opener:
        def open(self,request,timeout):
            observed.append(request)
            assert timeout==45
            return Response()
    monkeypatch.setattr(providers.urllib.request,"build_opener",lambda *args:Opener())


def test_byok_ciphertext_private_and_metadata_redacted(connections):
    configured(connections)
    assert KEY not in connections.path.read_text()
    assert KEY not in json.dumps(connections.catalog())
    assert connections.path.stat().st_mode & 0o777==0o600
    assert connections.key_path.stat().st_mode & 0o777==0o600
    assert connections.catalog()["connections"]["openai"]["last_test"] is None
    assert connections.delete("openai")=={"id":"openai","configured":False}


def test_connection_cannot_be_decrypted_in_another_workspace(connections,tmp_path):
    configured(connections)
    other=providers.Connections(tmp_path/"other")
    configured(other)
    other.path.write_bytes(connections.path.read_bytes())
    with pytest.raises(StudioError) as error:other._credential("openai")
    assert error.value.status==409


@pytest.mark.parametrize("pid,protocol",[(pid,info["protocol"]) for pid,info in providers.REGISTRY.items()])
def test_each_official_wire_protocol_and_usage_redaction(connections,monkeypatch,pid,protocol):
    configured(connections,pid);requests=[]
    payload={"output":[{"type":"message","content":[{"type":"output_text","text":"OK"}]}],"status":"completed"} if protocol=="responses" else {"content":[{"type":"text","text":"OK"}],"stop_reason":"end_turn"} if protocol=="anthropic" else {"choices":[{"message":{"content":"OK"},"finish_reason":"stop"}]}
    payload["usage"]={"total_tokens":3,"private_unknown":KEY,"output_tokens":-1}
    mock_response(monkeypatch,payload,requests)
    result=connections.infer(pid,"System","Narración",32)
    assert result["text"]=="OK" and result["usage"]=={"total_tokens":3}
    assert result["inference_executed"] and KEY not in json.dumps(result)
    request=requests[0];body=json.loads(request.data)
    assert request.full_url==providers.REGISTRY[pid]["endpoint"]
    assert body["model"]=="my-exact-model"
    if protocol=="responses":assert body["store"] is False and body["max_output_tokens"]==32
    elif protocol=="anthropic":assert request.get_header("X-api-key")==KEY
    else:assert body["messages"][1]["content"]=="Narración"


@pytest.mark.parametrize("payload",[None,{}, {"output":[None]}, {"output":[{"type":"message","content":[1]}]}, {"output":[],"status":"incomplete"}])
def test_malformed_upstream_is_bounded_error(connections,monkeypatch,payload):
    configured(connections);mock_response(monkeypatch,payload,[])
    with pytest.raises(StudioError) as error:connections.infer("openai","s","p",32)
    assert error.value.status==502


def test_upstream_error_cannot_echo_secret(connections,monkeypatch):
    configured(connections)
    class Opener:
        def open(self,*args,**kwargs):raise urllib.error.HTTPError("https://api.openai.com",401,KEY,{},None)
    monkeypatch.setattr(providers.urllib.request,"build_opener",lambda *args:Opener())
    with pytest.raises(StudioError) as error:connections.infer("openai","s","p",32)
    assert KEY not in str(error.value) and error.value.details["upstream_status"]==401


def test_private_text_echo_and_redirect_fail_closed(connections,monkeypatch):
    configured(connections)
    mock_response(monkeypatch,{"output":[{"type":"message","content":[{"type":"output_text","text":KEY}]}]},[])
    with pytest.raises(StudioError):connections.infer("openai","s","p",32)
    with pytest.raises(StudioError):providers.NoRedirect().redirect_request(None,None,302,"",{},"http://127.0.0.1/private")


@pytest.mark.parametrize("data",[{"api_key":KEY,"model":"model","endpoint":"http://127.0.0.1"},{"api_key":KEY,"model":"../../bad"},{"api_key":"sk-ant-oat-subscription","model":"model"},{"api_key":KEY+"\n","model":"model"}])
def test_client_cannot_select_endpoint_or_subscription_auth(connections,data):
    with pytest.raises(StudioError):connections.put("anthropic",data)


def test_symlink_guard_precedes_private_directory_creation(tmp_path):
    root=tmp_path/"root";target=tmp_path/"outside";root.mkdir();target.mkdir()
    (root/".estado").symlink_to(target,target_is_directory=True)
    with pytest.raises(StudioError):providers.Connections(root)
    assert not list(target.iterdir())


def test_connection_test_records_executed_success_and_no_key(connections,monkeypatch):
    configured(connections)
    mock_response(monkeypatch,{"output":[{"type":"message","content":[{"type":"output_text","text":"OK"}]}],"status":"completed"},[])
    result=connections.test("openai")
    assert result["ok"] and result["inference_executed"]
    assert connections.catalog()["connections"]["openai"]["last_test"]["ok"]
