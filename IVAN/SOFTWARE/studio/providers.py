"""Tenant-owned encrypted BYOK connections and bounded inference adapters."""
from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import re
import secrets
import ssl
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .core import StudioError, now

CODE_ROOT=Path(__file__).resolve().parents[1]
REGISTRY={
    "openai":{"name":"OpenAI / modelos Codex por API","protocol":"responses","endpoint":"https://api.openai.com/v1/responses","documentation":"https://developers.openai.com/api/docs/guides/text","agent_documentation":"https://developers.openai.com/codex/sdk"},
    "anthropic":{"name":"Claude / Anthropic","protocol":"anthropic","endpoint":"https://api.anthropic.com/v1/messages","documentation":"https://platform.claude.com/docs/en/api/messages/create"},
    "gemini":{"name":"Gemini / Google","protocol":"chat","endpoint":"https://generativelanguage.googleapis.com/v1beta/openai/chat/completions","documentation":"https://ai.google.dev/gemini-api/docs/openai"},
    "mistral":{"name":"Mistral","protocol":"chat","endpoint":"https://api.mistral.ai/v1/chat/completions","documentation":"https://docs.mistral.ai/resources/migration-guides"},
    "groq":{"name":"Groq","protocol":"chat","endpoint":"https://api.groq.com/openai/v1/chat/completions","documentation":"https://console.groq.com/docs/openai"},
    "xai":{"name":"Grok / xAI","protocol":"chat","endpoint":"https://api.x.ai/v1/chat/completions","documentation":"https://docs.x.ai/developers/rest-api-reference/inference"},
    "deepseek":{"name":"DeepSeek","protocol":"chat","endpoint":"https://api.deepseek.com/chat/completions","documentation":"https://api-docs.deepseek.com/"},
    "openrouter":{"name":"OpenRouter","protocol":"chat","endpoint":"https://openrouter.ai/api/v1/chat/completions","documentation":"https://openrouter.ai/docs/api/reference/overview"},
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        raise StudioError("El proveedor respondió con una redirección no admitida.",502)


def private_root(root):
    root=Path(root).resolve()
    if not root.is_relative_to(CODE_ROOT.resolve()):
        raise StudioError("Conexión fuera del espacio autorizado.",403)
    private=root/".estado"
    if private.is_symlink() or not private.resolve().is_relative_to(root):
        raise StudioError("Configuración privada inválida.",403)
    private.mkdir(parents=True,exist_ok=True,mode=0o700)
    private.chmod(0o700)
    return private


def private_write(path,data):
    if path.is_symlink():
        raise StudioError("Configuración privada inválida.",403)
    temp=path.with_name(path.name+"."+secrets.token_hex(8)+".tmp")
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


class Connections:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.private=private_root(root)
        self.path=self.private/"providers.json"
        self.key_path=self.private/"providers.key"
        self.lock_path=self.private/"providers.lock"

    def _lock(self):
        if self.lock_path.is_symlink():
            raise StudioError("Configuración privada inválida.",403)
        fd=os.open(self.lock_path,os.O_RDWR|os.O_CREAT,0o600)
        handle=os.fdopen(fd,"a+b");fcntl.flock(handle,fcntl.LOCK_EX)
        return handle

    def _key(self):
        if self.key_path.is_symlink():
            raise StudioError("Configuración privada inválida.",403)
        if not self.key_path.exists():
            private_write(self.key_path,secrets.token_bytes(32))
        key=self.key_path.read_bytes()
        if len(key)!=32:
            raise StudioError("La clave privada de conexiones es inválida.",409)
        return key

    def _read(self):
        if self.path.is_symlink():
            raise StudioError("Configuración privada inválida.",403)
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    def _save(self,value):
        private_write(self.path,json.dumps(value,ensure_ascii=False,allow_nan=False).encode())

    @staticmethod
    def public(row):
        return {k:row[k] for k in ("model","label","key_hint","updated_at","last_test") if k in row}|{"configured":True}

    def catalog(self):
        with self._lock():
            rows=self._read()
        providers=[{"id":pid,**{k:v for k,v in info.items() if k!="endpoint"},"available":True,"connection":self.public(rows[pid]) if pid in rows else {"configured":False},"authentication":"own_api_key","external_live_verified": bool((rows.get(pid,{}).get("last_test") or {}).get("ok") is True)} for pid,info in REGISTRY.items()]
        return {"providers":providers,"connections":{k:self.public(v) for k,v in rows.items() if k in REGISTRY},"agent_connection":{"transport":"streamable_http_json","endpoint":"/mcp","clients":["Codex","Claude Code","other MCP clients"],"arbitrary_server_shell":False},"oauth":{"claude_ai":"requires_prior_provider_approval; not enabled","chatgpt":"official_client_registration_required; not enabled"}}

    def put(self,pid,data):
        if pid not in REGISTRY or not isinstance(data,dict) or set(data)-{"api_key","model","label"} or not {"api_key","model"}<=set(data):
            raise StudioError("Elige un proveedor y su clave de API y modelo.")
        key,model,label=data["api_key"],data["model"],data.get("label",REGISTRY[pid]["name"])
        if not isinstance(key,str) or not re.fullmatch(r"[!-~]{8,4096}",key):
            raise StudioError("Introduce una clave de API válida, sin espacios.")
        if pid=="anthropic" and key.startswith("sk-ant-oat"):
            raise StudioError("La conexión de Claude requiere una clave de API de Console.")
        if not isinstance(model,str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,199}",model):
            raise StudioError("Introduce el ID exacto de un modelo habilitado en tu cuenta.")
        if not isinstance(label,str) or not 1<=len(label)<=120 or any(ord(c)<32 for c in label):
            raise StudioError("El nombre de conexión no es válido.")
        with self._lock():
            nonce=secrets.token_bytes(12)
            encrypted=AESGCM(self._key()).encrypt(nonce,key.encode(),pid.encode())
            rows=self._read()
            rows[pid]={"ciphertext":base64.b64encode(nonce+encrypted).decode(),"model":model,"label":label,"key_hint":"••••"+key[-4:],"updated_at":now(),"last_test":None}
            self._save(rows)
            return {"id":pid,**self.public(rows[pid])}

    def delete(self,pid):
        if pid not in REGISTRY:
            raise StudioError("Proveedor no encontrado.",404)
        with self._lock():
            rows=self._read()
            rows.pop(pid,None);self._save(rows)
        return {"id":pid,"configured":False}

    def _credential(self,pid):
        if pid not in REGISTRY:
            raise StudioError("Proveedor no encontrado.",404)
        with self._lock():
            row=self._read().get(pid)
            if not row:
                raise StudioError("Configura tu conexión de IA antes de automatizar.",409)
            try:
                payload=base64.b64decode(row["ciphertext"],validate=True)
                key=AESGCM(self._key()).decrypt(payload[:12],payload[12:],pid.encode()).decode()
            except Exception:
                raise StudioError("No se pudo abrir la conexión privada. Vuelve a configurarla.",409) from None
        return row,key

    def infer(self,pid,system,prompt,max_tokens=4096):
        if not isinstance(system,str) or not isinstance(prompt,str) or len((system+prompt).encode())>128*1024:
            raise StudioError("El contexto de inferencia es demasiado grande.",413)
        if type(max_tokens) is not int or not 16<=max_tokens<=8192:
            raise StudioError("Límite de salida inválido.")
        row,key=self._credential(pid)
        info=REGISTRY[pid]
        headers={"Content-Type":"application/json","Accept":"application/json"}
        if info["protocol"]=="anthropic":
            headers.update({"x-api-key":key,"anthropic-version":"2023-06-01"})
            body={"model":row["model"],"system":system,"messages":[{"role":"user","content":prompt}],"max_tokens":max_tokens}
        elif info["protocol"]=="responses":
            headers["Authorization"]="Bearer "+key
            body={"model":row["model"],"instructions":system,"input":prompt,"max_output_tokens":max_tokens,"store":False}
        else:
            headers["Authorization"]="Bearer "+key
            body={"model":row["model"],"messages":[{"role":"system","content":system},{"role":"user","content":prompt}],"max_tokens":max_tokens}
        request=urllib.request.Request(info["endpoint"],data=json.dumps(body,ensure_ascii=False).encode(),headers=headers,method="POST")
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        try:
            with opener.open(request,timeout=45) as response:
                raw=response.read(2*1024*1024+1)
                if len(raw)>2*1024*1024:
                    raise StudioError("La respuesta de IA excede el límite.",502)
                result=json.loads(raw)
        except urllib.error.HTTPError as exc:
            code=exc.code
            exc.close()
            raise StudioError(f"El proveedor rechazó la solicitud (HTTP {code}). Revisa clave, modelo, saldo y permisos.",502, {"provider":pid,"upstream_status":code}) from None
        except (urllib.error.URLError,TimeoutError,OSError,ValueError):
            raise StudioError("No se pudo completar la conexión con el proveedor.",502,{"provider":pid}) from None
        try:
            if info["protocol"]=="responses":
                text="".join(c["text"] for item in result["output"] if item.get("type")=="message" for c in item.get("content",[]) if c.get("type")=="output_text")
                if result.get("status") not in (None,"completed"):
                    raise ValueError("incomplete")
            elif info["protocol"]=="anthropic":
                text="".join(c["text"] for c in result["content"] if c.get("type")=="text")
                if result.get("stop_reason")=="max_tokens":
                    raise ValueError("incomplete")
            else:
                choice=result["choices"][0]
                if choice.get("finish_reason") in ("length","content_filter"):
                    raise ValueError("incomplete")
                text=choice["message"]["content"]
            if not isinstance(text,str) or not text.strip():
                raise ValueError("empty")
        except (KeyError,TypeError,ValueError,IndexError,AttributeError):
            raise StudioError("El proveedor no devolvió una respuesta completa de texto.",502) from None
        if key in text:
            raise StudioError("El proveedor devolvió contenido privado inesperado.",502)
        # The raw upstream response, request headers and key never leave this adapter.
        usage=result.get("usage",{})
        usage={k:v for k,v in usage.items() if k in {"input_tokens","output_tokens","total_tokens","prompt_tokens","completion_tokens"} and type(v) is int and v>=0} if isinstance(usage,dict) else {}
        return {"text":text,"provider":pid,"model":row["model"],"usage":usage,"at":now(),"inference_executed":True}

    def test(self,pid):
        row,_=self._credential(pid)
        try:
            result=self.infer(pid,"Responde brevemente.","Responde OK.",32)
            test={"at":now(),"ok":True,"model":result["model"],"inference_executed":True,"usage":result["usage"]}
        except StudioError as exc:
            test={"at":now(),"ok":False,"model":row["model"],"inference_executed":False,"error":str(exc)}
        with self._lock():
            rows=self._read()
            if pid in rows and rows[pid].get("updated_at")==row["updated_at"] and rows[pid].get("ciphertext")==row["ciphertext"]:
                rows[pid]["last_test"]=test;self._save(rows)
        return test
