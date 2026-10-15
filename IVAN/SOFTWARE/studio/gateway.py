"""Authenticated local SaaS gateway. Each tenant has an immutable worker root."""
from __future__ import annotations

import hmac
import copy
import http.client
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie, CookieError
from http.server import ThreadingHTTPServer
from pathlib import Path

from .accounts import Accounts, SESSION_SECONDS
from .core import StudioError
from .providers import Connections
from .server import Handler
from .sharing import Sharing

CODE_ROOT=Path(__file__).resolve().parents[1]
COOKIE="ascendia_session"
MAX_PROXY_BYTES=4*1024**3


class Backends:
    def __init__(self,accounts):
        self.accounts=accounts
        self.lock=threading.RLock()
        self.workers={}

    def get(self,principal):
        wid=principal["workspace"]["id"]
        with self.lock:
            current=self.workers.get(wid)
            if current and current["process"].poll() is None:
                return current
            if len([x for x in self.workers.values() if x["process"].poll() is None])>=12:
                raise StudioError("Los espacios activos alcanzaron la capacidad local. Intenta más tarde.",429)
            root=self.accounts.workspace_path(principal)
            from .branding import bootstrap
            bootstrap(root,principal["workspace"]["name"])
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
            secret=secrets.token_urlsafe(48)
            env={key:os.environ[key] for key in ("PATH","LANG","LC_ALL","LD_LIBRARY_PATH") if key in os.environ}
            env.update(PYTHONPATH=str(CODE_ROOT),PYTHONDONTWRITEBYTECODE="1",ASCENDIA_WORKSPACE=str(root),ASCENDIA_BACKEND_TOKEN=secret,
                       TMPDIR=str(root/".estado/tmp"),CUDA_VISIBLE_DEVICES="",OMP_NUM_THREADS="2",OPENBLAS_NUM_THREADS="2")
            log=root/".estado/logs/backend.log"
            if log.parent.is_symlink() or log.is_symlink() or not log.resolve().is_relative_to(root):
                raise StudioError("Registro privado inválido.",403)
            log.parent.mkdir(parents=True,exist_ok=True)
            fd=os.open(log,os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
            with os.fdopen(fd,"ab") as output:
                process=subprocess.Popen(["nice","-n","10",sys.executable,"-B","-m","studio","serve","--port",str(port)],cwd=root,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True)
            current={"port":port,"secret":secret,"process":process,"root":root}
            self.workers[wid]=current
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                if process.poll() is not None:
                    break
                try:
                    connection=http.client.HTTPConnection("127.0.0.1",port,timeout=.8)
                    connection.request("GET","/api/projects",headers={"X-Ascendia-Backend":secret})
                    response=connection.getresponse();response.read();connection.close()
                    if response.status==200:
                        return current
                except (OSError,http.client.HTTPException):
                    pass
                time.sleep(.1)
            raise StudioError("No se pudo iniciar el espacio privado. Consulta su registro local.",503)

    def close(self):
        # Only processes created by this object; never discover/kill parent processes.
        with self.lock:
            processes=[x["process"] for x in self.workers.values()]
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill();process.wait(timeout=3)


URL_FIELDS={"url","preview_url","notice_url","thumbnail_url","waveform_url","poster_url","download_url","bundle_url"}
SEMANTIC_FIELDS={"document","scene_ir","parameters","params","provenance","metadata","style","motion_design","plan","transcript","reference_review","library_searches","instructions","decision","motion","data"}


def scoped_urls(value,wid,field=None):
    if field in SEMANTIC_FIELDS:
        return value
    if isinstance(value,dict):
        return {k:scoped_urls(v,wid,k) for k,v in value.items()}
    if isinstance(value,list):
        return [scoped_urls(v,wid,field) for v in value]
    if field in URL_FIELDS and isinstance(value,str) and value.startswith("/api/"):
        return "/w/"+wid+value
    return value


def shared_urls(value, owner, project_id, actor, field=None):
    """Transport URLs carry the project and actor; narration stays literal."""
    if field in SEMANTIC_FIELDS:
        return value
    if isinstance(value,dict):
        return {key:shared_urls(item,owner,project_id,actor,key) for key,item in value.items()}
    if isinstance(value,list):
        return [shared_urls(item,owner,project_id,actor,field) for item in value]
    if field in URL_FIELDS and isinstance(value,str) and value.startswith("/api/"):
        parsed=urllib.parse.urlsplit(value)
        query=urllib.parse.parse_qs(parsed.query)
        query.update(project_id=[project_id],actor_workspace_id=[actor])
        return "/w/"+owner+parsed.path+"?"+urllib.parse.urlencode(query,doseq=True)
    return value


class GatewayHandler(Handler):
    server_version="AscendiaPortal"

    def common_headers(self,mime):
        super().common_headers(mime)
        self.send_header("Cache-Control","no-store")
        self.send_header("Vary","Cookie, Authorization, X-Workspace-ID")
        if self.server.public_origin.startswith("https://"):
            self.send_header("Strict-Transport-Security","max-age=31536000")

    def guard(self):
        if self.headers.get("Host") not in self.server.allowed_hosts:
            raise StudioError("Host no autorizado.",403)
        origin=self.headers.get("Origin")
        if origin and origin!=self.server.public_origin:
            raise StudioError("Origen no autorizado.",403)
        if self.headers.get("Sec-Fetch-Site")=="cross-site":
            raise StudioError("Origen no autorizado.",403)
        if self.headers.get("Transfer-Encoding"):
            raise StudioError("Transfer-Encoding no admitido.")
        lengths=self.headers.get_all("Content-Length",[])
        if len(lengths)>1:
            raise StudioError("Content-Length duplicado.")
        if self.command in ("GET","HEAD") and self.headers.get("Content-Length","0")!="0":
            raise StudioError("Esta consulta no admite un cuerpo.")

    def principal(self):
        authorization=self.headers.get("Authorization")
        if authorization:
            if not authorization.startswith("Bearer "):
                raise StudioError("Conexión de agente no válida.",401)
            return self.server.accounts.authenticate(authorization[7:],agent=True)
        cookie=SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie",""))
            value=cookie.get(COOKIE)
        except CookieError:
            return None
        return self.server.accounts.authenticate(value.value) if value else None

    def need_principal(self,path,mutation=False):
        principal=self.principal()
        if not principal:
            raise StudioError("Inicia sesión para acceder a tu espacio.",401)
        requested=self.headers.get("X-Workspace-ID")
        match=re.match(r"/w/(w_[0-9a-f]{32})(/.*)$",path)
        query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        actor_hint=query.get("actor_workspace_id")
        if actor_hint and (len(actor_hint)!=1 or actor_hint[0]!=principal["workspace"]["id"]):
            raise StudioError("La cuenta cambió. Vuelve al portal antes de continuar.",409)
        if match:
            path=match[2]
        if requested and requested!=principal["workspace"]["id"]:
            raise StudioError("La cuenta cambió. Vuelve al portal antes de continuar.",409)
        if match and match[1]!=principal["workspace"]["id"]:
            project=re.fullmatch(r"/api/projects/(p_[0-9a-f]{16})(?:/[a-z_-]+)?",path)
            selected=query.get("project_id",[])
            if project:
                pid=project[1]
                if selected and selected!=[pid]:
                    raise StudioError("El proyecto compartido no coincide con la solicitud.",403)
            elif len(selected)==1:
                pid=selected[0]
            else:
                raise StudioError("La cuenta cambió. Abre el proyecto compartido desde el portal.",409)
            access=self.server.sharing.access(principal,match[1],pid)
            self.shared_scope={"owner":self.server.sharing.owner(match[1]),"access":access}
        if mutation and principal["kind"]=="session":
            if not hmac.compare_digest(self.headers.get("X-CSRF-Token","").encode("utf-8"),principal["csrf_token"].encode("ascii")):
                raise StudioError("Sesión desactualizada. Vuelve a iniciar sesión.",403)
            if path!="/api/auth/logout" and not requested and not match:
                raise StudioError("La solicitud requiere el espacio actual.",409)
        return principal,path,bool(match)

    def backend_json(self,principal,path,method="GET",body=None):
        worker=self.server.backends.get(principal)
        raw=None if body is None else json.dumps(body,ensure_ascii=False).encode()
        headers={"X-Ascendia-Backend":worker["secret"]}
        if raw is not None:
            headers["Content-Type"]="application/json"
        connection=http.client.HTTPConnection("127.0.0.1",worker["port"],timeout=180)
        try:
            connection.request(method,path,raw,headers)
            response=connection.getresponse()
            raw=response.read(16*1024*1024+1)
            if len(raw)>16*1024*1024:
                raise StudioError("La respuesta del proyecto excede el límite.",502)
            value=json.loads(raw)
            if response.status>=400:
                raise StudioError(value.get("error","No se pudo abrir el proyecto."),response.status,value.get("details"))
            return value
        finally:
            connection.close()

    def shared_context(self,actor):
        scope=self.shared_scope;owner=scope["owner"];access=scope["access"]
        pid=access["project_id"];wid=access["owner_workspace_id"]
        self.server.sharing.project(wid,pid)
        project=self.backend_json(owner,"/api/projects/"+pid)
        assets=self.server.sharing.assets(wid,project)
        status=self.backend_json(owner,"/api/status")
        # The current global branding can contain unrelated future brand changes.
        status={key:status[key] for key in ("app","version","capabilities","restart_required","limitations","manual") if key in status}
        status.update(scope=wid,active_external=[],policy=copy.deepcopy(project.get("style",{})))
        library=self.backend_json(owner,"/api/font-library")
        ids={item['id'] for item in assets}
        library['fonts']=[item for item in library.get('fonts',[]) if item.get('asset_id',item.get('id')) in ids]
        # Do not expose the owner's global font roles, which can differ from this project.
        roles=project.get('style',{}).get('branding',{}).get('fonts',{})
        library['roles']=[{**value,'role':role,'name':str(value.get('family',''))+' '+str(value.get('style','')),
                           'url':'/api/fonts/'+role+'?project_id='+pid} for role,value in roles.items() if isinstance(value,dict)]
        context={'project':project,'access':access,'assets':assets,'status':status,'font_library':library,
                 'templates':self.backend_json(owner,'/api/templates'),
                 'text_presets':self.backend_json(owner,'/api/text-presets'),
                 'manual':self.backend_json(owner,'/api/manual'),
                 'jobs':self.server.sharing.jobs(wid,pid)}
        return shared_urls(context,wid,pid,actor['workspace']['id'])

    def shared_dispatch(self,actor,route,query,method,head):
        scope=self.shared_scope;owner=scope['owner'];access=scope['access']
        wid=access['owner_workspace_id'];pid=access['project_id']
        project=self.server.sharing.project(wid,pid)
        render_url='/api/projects/'+pid
        def respond(value,status=200):
            return self.json(shared_urls(value,wid,pid,actor['workspace']['id']),status,head)
        if method=='GET' and route==render_url+'/editor-context':
            return self.json(self.shared_context(actor),head=head)
        if method=='GET' and route==render_url:
            return respond(self.backend_json(owner,route))
        if method=='PUT' and route==render_url:
            self.server.sharing.access(actor,wid,pid,write=True)
            incoming=self.body()
            with self.server.sharing.admitted(actor,wid,pid,write=True):
                current=self.server.sharing.project(wid,pid)
                self.server.sharing.validate_edit(current,incoming)
                value=self.backend_json(owner,route,'PUT',incoming)
            return respond(value)
        if method=='GET' and route.startswith(render_url+'/') and route.rsplit('/',1)[-1] in ('validate','tracking','tracking_proposals','designs'):
            return respond(self.backend_json(owner,urllib.parse.quote(route,safe='/:-_.')+('?' + query if query else '')))
        if method=='POST' and route==render_url+'/export':
            if self.body(4096):raise StudioError('Exportar requiere un cuerpo vacío.')
            with self.server.sharing.admitted(actor,wid,pid):
                value=self.backend_json(owner,route,'POST',{})
            return respond(value)
        if method=='POST' and route in (render_url+'/render',render_url+'/design_snapshot'):
            self.server.sharing.access(actor,wid,pid,write=True)
            options=self.body()
            if route.endswith('/render') and options.get('technical') is not True:
                raise StudioError('La colaboración permite render técnico, sin aprobación narrativa.',403)
            with self.server.sharing.admitted(actor,wid,pid,write=True):
                value=self.backend_json(owner,route,'POST',options)
            return respond(value,202)
        if method=='POST' and route=='/api/text-layout':
            value=self.body(32768)
            if value.get('project_id')!=pid:
                raise StudioError('El layout debe pertenecer al proyecto compartido.',403)
            reference=value.get('element',{}).get('font_asset_id') if isinstance(value.get('element'),dict) else None
            if reference is not None and reference not in {item['id'] for item in self.server.sharing.assets(wid,project)}:
                raise StudioError('El layout requiere una fuente adjunta al proyecto.',403)
            with self.server.sharing.admitted(actor,wid,pid):
                value=self.backend_json(owner,route,'POST',value)
            return respond(value)
        if method=='GET' and route=='/api/jobs':
            return respond({'jobs':self.server.sharing.jobs(wid,pid)})
        job=re.fullmatch(r'/api/jobs/(j_[0-9a-f]{16})(?:/(cancel))?',route)
        if job:
            allowed={item['id']:item for item in self.server.sharing.jobs(wid,pid)}
            if job[1] not in allowed:raise StudioError('Tarea no disponible en el proyecto compartido.',403)
            if method=='GET' and not job[2]:return respond(allowed[job[1]])
            # A collaborator never cancels a job submitted by the owner or another user.
            raise StudioError('La cancelación corresponde al propietario.',403)
        if method=='GET' and route=='/api/typography-client.js':
            return self.proxy(owner,route,head)
        notice=re.fullmatch(r'/api/font-notices/(a_[A-Za-z0-9_-]+)',route)
        if notice and method=='GET':
            if notice[1] not in {item['id'] for item in self.server.sharing.assets(wid,project) if item.get('kind')=='font'}:
                raise StudioError('Aviso no adjunto al proyecto compartido.',403)
            return self.proxy(owner,route,head)
        media=re.fullmatch(r'/api/media/(a_[A-Za-z0-9_-]+)',route)
        if media and method=='GET':
            item=next((item for item in self.server.sharing.assets(wid,project) if item['id']==media[1]),None)
            if not item:
                raise StudioError('Medio no adjunto al proyecto compartido.',403)
            if not self.server.sharing.file_allowed(wid,project,item.get('path')):
                raise StudioError('El medio canónico no admite alias ni enlaces.',403)
            return self.proxy(owner,route,head)
        if method=='GET' and route.startswith('/api/fonts/'):
            if route not in ('/api/fonts/primary','/api/fonts/accent'):
                raise StudioError('Fuente no disponible en este proyecto.',403)
            return self.proxy(owner,route+'?project_id='+pid,head)
        if method=='GET' and route.startswith('/api/files/'):
            relative=route[len('/api/files/'):]
            if not self.server.sharing.file_allowed(wid,project,relative):
                raise StudioError('Archivo no disponible en el proyecto compartido.',403)
            return self.proxy(owner,urllib.parse.quote(route,safe='/:-_.'),head)
        raise StudioError('Esta función pertenece al propietario del proyecto.',403)

    def session_json(self,result):
        data=json.dumps(self.public_principal(result["principal"]),ensure_ascii=False).encode()
        self.send_response(200);self.common_headers("application/json; charset=utf-8")
        secure="; Secure" if self.server.public_origin.startswith("https://") else ""
        self.send_header("Set-Cookie",f"{COOKIE}={result['session']}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_SECONDS}"+secure)
        self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)

    @staticmethod
    def public_principal(principal):
        return {"authenticated":True,"user":principal["user"],"workspace":principal["workspace"],"csrf_token":principal["csrf_token"],"kind":principal["kind"]}

    def proxy(self,principal,path,head=False):
        worker=self.server.backends.get(principal)
        try:
            length=int(self.headers.get("Content-Length","0"))
        except ValueError:
            raise StudioError("Content-Length inválido.") from None
        if not 0<=length<=MAX_PROXY_BYTES:
            raise StudioError("Carga demasiado grande.",413)
        headers={"X-Ascendia-Backend":worker["secret"],"Host":f"127.0.0.1:{worker['port']}","Content-Length":str(length)}
        for name in ("Content-Type","Range","X-File-Name","X-Asset-Kind"):
            if value:=self.headers.get(name):
                headers[name]=value
        connection=http.client.HTTPConnection("127.0.0.1",worker["port"],timeout=180)
        try:
            connection.putrequest(self.command,path,skip_host=True,skip_accept_encoding=True)
            for key,value in headers.items():connection.putheader(key,value)
            connection.endheaders()
            remaining=length
            while remaining:
                chunk=self.rfile.read(min(1024*1024,remaining))
                if not chunk:raise StudioError("La carga llegó incompleta.")
                connection.send(chunk);remaining-=len(chunk)
            response=connection.getresponse()
            content_type=response.getheader("Content-Type","")
            if content_type.startswith("application/json") and not head:
                raw=response.read(16*1024*1024+1)
                if len(raw)>16*1024*1024:
                    raise StudioError("La respuesta del espacio excede el límite.",502)
                value=json.loads(raw)
                if path.split("?")[0]=="/api/status" and isinstance(value,dict):
                    value["scope"]=principal["workspace"]["id"];value["active_external"]=[]
                return self.json(scoped_urls(value,principal["workspace"]["id"]),response.status)
            self.send_response(response.status);self.common_headers(content_type or "application/octet-stream")
            for key in ("Content-Length","Content-Range","Accept-Ranges","Content-Disposition"):
                if value:=response.getheader(key):self.send_header(key,value)
            self.end_headers()
            if not head:
                while chunk:=response.read(1024*1024):self.wfile.write(chunk)
        finally:
            connection.close()

    def dispatch(self,head=False):
        self.shared_scope=None
        try:
            self.guard()
            parsed=urllib.parse.urlsplit(self.path)
            path=urllib.parse.unquote(parsed.path)
            method="GET" if head else self.command
            if path in ("/","/portal","/portal.html","/portal.js","/portal.css","/app.js","/style.css") and method=="GET":
                filename="portal.html" if path in ("/","/portal") else path[1:]
                return self.file(CODE_ROOT/"web"/filename,head,root=CODE_ROOT)
            if method=="GET" and path=="/api/auth/me":
                principal=self.principal()
                return self.json(self.public_principal(principal) if principal else {"authenticated":False},head=head)
            if method=="POST" and path in ("/api/auth/register","/api/auth/login"):
                if self.headers.get_content_type()!="application/json":
                    raise StudioError("El acceso requiere JSON.",415)
                data=self.body(16384)
                fn=self.server.accounts.register if path.endswith("register") else self.server.accounts.login
                return self.session_json(fn(data,self.client_address[0]))
            principal,route,scoped=self.need_principal(path,mutation=method not in ("GET","HEAD"))
            if method=="GET" and route=="/editor":
                if scoped:
                    raise StudioError("Abre el editor desde /editor con el espacio indicado.",404)
                target=urllib.parse.parse_qs(parsed.query).get("workspace",[principal["workspace"]["id"]])[0]
                typography='/w/'+target+'/api/typography-client.js'
                if target!=principal['workspace']['id']:
                    pid=urllib.parse.parse_qs(parsed.query).get('project',[None])[0]
                    try:self.server.sharing.access(principal,target,pid)
                    except StudioError as error:raise StudioError('La cuenta cambió o el proyecto ya no está compartido.',409) from error
                    typography+='?project_id='+pid+'&actor_workspace_id='+principal['workspace']['id']
                raw=(CODE_ROOT/"web/index.html").read_text().replace('src="/api/typography-client.js"','src="'+typography+'"').encode()
                self.send_response(200);self.common_headers("text/html; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers()
                if not head:self.wfile.write(raw)
                return
            if self.shared_scope:
                return self.shared_dispatch(principal,route,parsed.query,method,head)
            if route=='/api/shared/projects' and method=='GET':
                return self.json(self.server.sharing.received(principal),head=head)
            sharing=re.fullmatch(r'/api/projects/(p_[0-9a-f]{16})/shares(?:/(sh_[0-9a-f]{32}))?',route)
            if sharing:
                if method=='GET' and not sharing[2]:return self.json(self.server.sharing.members(principal,sharing[1]),head=head)
                if method=='POST' and not sharing[2]:return self.json(self.server.sharing.grant(principal,sharing[1],self.body(16384)),201)
                if method=='DELETE' and sharing[2]:
                    value=self.body(4096)
                    if set(value)!={'expected_revision'}:raise StudioError('Revocar requiere expected_revision.')
                    return self.json(self.server.sharing.revoke(principal,sharing[1],sharing[2],value['expected_revision']))
                raise StudioError('Método de colaboración no admitido.',405)
            if route=='/api/storage' and method=='GET':
                catalog=self.backend_json(principal,'/api/assets').get('assets',[])
                projects=self.backend_json(principal,'/api/projects').get('projects',[])
                from .cloud_storage import status as cloud_status
                return self.json({'provider':'local','remote':False,'cloud_storage':cloud_status(self.server.accounts.root),'used_bytes':sum(item.get('size',0) for item in catalog if type(item.get('size')) is int),'asset_count':len(catalog),'project_count':len(projects),'quota_bytes':None,'measurement':'Canonical asset bytes, excluding derived caches and runtimes.'},head=head)
            if method=="POST" and route=="/api/auth/logout":
                if self.body(4096):raise StudioError("Salir de la cuenta requiere un cuerpo vacío.")
                if principal["kind"]!="session":raise StudioError("Esta conexión requiere sesión de usuario.",403)
                self.server.accounts.logout(principal)
                raw=b'{"authenticated":false}'
                self.send_response(200);self.common_headers("application/json")
                self.send_header("Set-Cookie",f"{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
                self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw);return
            if route.startswith("/api/providers") or route.startswith("/api/agent-tokens"):
                if principal["kind"]!="session":raise StudioError("Gestiona las conexiones desde tu cuenta.",403)
                root=self.server.accounts.workspace_path(principal)
                connections=Connections(root)
                if route=="/api/providers" and method=="GET":return self.json(connections.catalog(),head=head)
                match=re.fullmatch(r"/api/providers/([a-z]+)(/test)?",route)
                if match:
                    if method=="PUT" and not match[2]:return self.json(connections.put(match[1],self.body(16384)))
                    if method=="DELETE" and not match[2]:
                        if self.body(4096):raise StudioError("Eliminar una conexión requiere un cuerpo vacío.")
                        return self.json(connections.delete(match[1]))
                    if method=="POST" and match[2]:
                        if self.body(16384).get("confirmed") is not True:raise StudioError("Confirma la prueba de conexión, que consume tu API.")
                        return self.json(connections.test(match[1]))
                if route=="/api/agent-tokens":
                    if method=="GET":return self.json({"tokens":self.server.accounts.tokens(principal)},head=head)
                    if method=="POST":
                        value=self.server.accounts.create_token(principal,self.body(4096))
                        value["mcp_config"]={"url":self.server.public_origin+"/mcp","headers":{"Authorization":"Bearer "+value["token"]}}
                        return self.json(value,201)
                match=re.fullmatch(r"/api/agent-tokens/(at_[0-9a-f]{32})",route)
                if match and method=="DELETE":
                    if self.body(4096):raise StudioError("Revocar una conexión requiere un cuerpo vacío.")
                    return self.json(self.server.accounts.revoke_token(principal,match[1]))
                raise StudioError("Ruta no encontrada.",404)
            if route=="/api/branding":
                from .branding import get_branding,save_branding,bootstrap
                root=self.server.accounts.workspace_path(principal);bootstrap(root,principal["workspace"]["name"])
                if method=="GET":return self.json(scoped_urls(get_branding(root),principal["workspace"]["id"]),head=head)
                if method=="PUT" and principal["kind"]=="session":return self.json(scoped_urls(save_branding(root,self.body(32768)),principal["workspace"]["id"]))
                raise StudioError("Gestiona la marca desde tu cuenta.",403)
            if route=="/api/manual" and method=="GET":
                from .branding import profile_document
                return self.json({"documents":[profile_document()],"policy":{"name":"IVAN YO + CLONE","split":[55,45],"max_presenter_continuous":3},"scope":"software_profile; no claim of reading parent manuals"},head=head)
            if route=="/mcp":
                if principal["kind"]!="agent":raise StudioError("Conecta tu agente con un token de su espacio.",401)
                if method=="GET":raise StudioError("El transporte MCP usa POST JSON-RPC sin SSE.",405)
                if method!="POST":raise StudioError("Método MCP no admitido.",405)
                return self.proxy(principal,"/api/mcp",head)
            if not route.startswith("/api/"):raise StudioError("Ruta no encontrada.",404)
            evidence_media = bool(re.fullmatch(r"/api/assets/a_[A-Za-z0-9_-]+/review-files/[^/]+", route))
            if principal["kind"]=="session" and (route.startswith(("/api/media/","/api/files/","/api/fonts/","/api/font-notices/")) or evidence_media) and not scoped:
                raise StudioError("Abre el recurso desde su espacio privado.",409)
            # Every backend endpoint and every media range stays behind ownership checks.
            return self.proxy(principal,urllib.parse.quote(route,safe="/:-_.")+("?"+parsed.query if parsed.query else ""),head)
        except StudioError as exc:
            self.close_connection=True;self.json({"error":str(exc),"details":exc.details},exc.status,head)
        except (BrokenPipeError,ConnectionResetError):pass
        except (OSError,http.client.HTTPException,ValueError,TypeError,KeyError):
            self.close_connection=True;self.json({"error":"No se pudo completar la solicitud del espacio."},502,head)
        except Exception:
            self.close_connection=True;self.json({"error":"Error interno del portal."},500,head)


def make_server(port=8776,origin=None,accounts=None):
    if type(port) is not int or not 1024<=port<=65535:
        raise StudioError("Puerto local inválido.")
    origin=origin or f"http://127.0.0.1:{port}"
    parsed=urllib.parse.urlsplit(origin)
    if parsed.scheme not in ("https","http") or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise StudioError("Origen público inválido.")
    if parsed.scheme=="http" and parsed.hostname not in ("127.0.0.1","localhost"):
        raise StudioError("Un origen público requiere HTTPS.")
    server=ThreadingHTTPServer(("127.0.0.1",port),GatewayHandler)
    server.daemon_threads=True
    server.public_origin=origin
    server.allowed_hosts={parsed.netloc}
    server.accounts=accounts or Accounts()
    server.sharing=Sharing(server.accounts)
    server.backends=Backends(server.accounts)
    return server


def serve(port=8776,origin=None):
    server=make_server(port,origin)
    print("Ascendia multiservicio — "+server.public_origin+"/portal",flush=True)
    try:server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:pass
    finally:
        server.server_close();server.backends.close()
