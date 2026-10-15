// Conexión OAuth de Tella, aislada en IVAN. Nunca imprime tokens ni abre otro perfil.
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {Client} from '../.estado/herramientas/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import {StreamableHTTPClientTransport} from '../.estado/herramientas/node_modules/@modelcontextprotocol/sdk/dist/esm/client/streamableHttp.js';
const root=path.resolve(import.meta.dirname,'..'), file=path.join(root,'.estado/tella/oauth.json');
fs.mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
let state=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{};
const save=()=>fs.writeFileSync(file,JSON.stringify(state,null,2),{mode:0o600});
const post=async(url,data)=>{const res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(data)});const obj=await res.json();return {status:res.status,data:obj};};
const metadata=await (await fetch('https://authkit.tella.tv/.well-known/oauth-authorization-server')).json();
if(!state.client){
 const response=await fetch(metadata.registration_endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_name:'Codex — IVAN local',redirect_uris:['http://127.0.0.1:17477/oauth/callback'],grant_types:['authorization_code','refresh_token','urn:ietf:params:oauth:grant-type:device_code'],response_types:['code'],token_endpoint_auth_method:'none'})});
 const client=await response.json();if(!response.ok)throw Error('No se pudo registrar el cliente OAuth: '+response.status+' '+client.error);state.client=client;save();
}
async function renew(force=false){
 state=fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):state;
if(state.tokens && (force||Date.now()>state.expires_at-30000) && state.tokens.refresh_token){
 const r=await post(metadata.token_endpoint,{grant_type:'refresh_token',refresh_token:state.tokens.refresh_token,client_id:state.client.client_id});
 if(r.status===200){state.tokens={...state.tokens,...r.data};state.expires_at=Date.now()+r.data.expires_in*1000;save();}else delete state.tokens;
}
}
await renew();
async function authenticate(){
 const result=await post(metadata.device_authorization_endpoint,{client_id:state.client.client_id,scope:'openid profile email offline_access'});
 if(result.status!==200)throw Error('Tella no inició la conexión: '+result.status+' '+result.data.error);
 const grant=result.data;state.pending={verification_uri:grant.verification_uri_complete||grant.verification_uri,user_code:grant.user_code,expires_at:Date.now()+grant.expires_in*1000};save();
 console.log(JSON.stringify({estado:'requiere_inicio_de_sesion',enlace:state.pending.verification_uri,codigo:grant.user_code,expira_en_s:grant.expires_in}));
 let interval=grant.interval||5;
 while(Date.now()<state.pending.expires_at){
  await new Promise(r=>setTimeout(r,interval*1000));
  const token=await post(metadata.token_endpoint,{grant_type:'urn:ietf:params:oauth:grant-type:device_code',device_code:grant.device_code,client_id:state.client.client_id});
  if(token.status===200){state.tokens=token.data;state.expires_at=Date.now()+token.data.expires_in*1000;delete state.pending;save();break;}
  if(token.data.error==='slow_down')interval+=5;
  else if(token.data.error==='expired_token')break;
  else if(token.data.error!=='authorization_pending')throw Error('La conexión no se completó: '+token.data.error);
 }
 if(!state.tokens){state.pending.estado='caducado';save();throw Error('El código temporal caducó; iniciar una nueva conexión.');}
}
async function verify(){
await renew(true);
const client=new Client({name:'Codex IVAN',version:'0.162.1'});
try{
await client.connect(new StreamableHTTPClientTransport(new URL('https://api.tella.com/mcp'),{requestInit:{headers:{Authorization:'Bearer '+state.tokens.access_token,'User-Agent':'Codex/0.162.1'}}}));
 const result=await client.listTools();
 const wanted=['list_videos','get_video_frame','get_storyboard','add_zoom','export_video'];
 const available=result.tools.map(t=>t.name);
 const list=result.tools.find(t=>t.name==='list_videos');let checked=false;
 if(list){const r=await client.callTool({name:list.name,arguments:{}});checked=!r.isError;}
 const proof={herramienta:'Tella MCP',estado:checked?'operativo':'conectado_pendiente_verificar_lectura',fecha:new Date().toISOString(),endpoint:'https://api.tella.com/mcp',cantidad_herramientas:available.length,capacidades:wanted.map(n=>({nombre:n,disponible:available.includes(n)})),prueba_lectura:checked};
 fs.writeFileSync(path.join(root,'.estado/tella/validacion.json'),JSON.stringify(proof,null,2));console.log(JSON.stringify(proof));
}catch(e){
 let claims={};try{claims=JSON.parse(Buffer.from(state.tokens.access_token.split('.')[1],'base64url'));}catch{}
 const proof={herramienta:'Tella MCP',estado:e.code===401&&!claims.tella_user_id?'autorizado_sin_cuenta_tella_vinculada':'conexion_rechazada',fecha:new Date().toISOString(),http:e.code,usuario_tella_asociado:!!claims.tella_user_id,workspace_tella_asociado:!!claims.tella_org_id,prueba_lectura:false};
 fs.writeFileSync(path.join(root,'.estado/tella/validacion.json'),JSON.stringify(proof,null,2));
 if(proof.estado==='autorizado_sin_cuenta_tella_vinculada')throw Error('OAuth recibido, pero el usuario de Tella no está asociado. Entrar en https://www.tella.tv/api/login con la misma cuenta hasta ver la biblioteca y volver a comprobar.');
 throw e;
}finally{await client.close();}
}
if(process.argv.includes('--servidor')){
 let running=false, error=null;
 const page=body=>`<!DOCTYPE html><html lang="es"><meta charset="utf-8"><title>Tella — IVAN</title><body style="font:20px system-ui;max-width:740px;margin:60px auto;padding:24px"><h1>Conectar Tella a IVAN</h1>${body}<p>Las credenciales se guardan únicamente en IVAN/.estado/tella. No se publican videos desde esta página.</p></body></html>`;
 const server=http.createServer(async(req,res)=>{
  res.setHeader('Content-Type','text/html; charset=utf-8');res.setHeader('Cache-Control','no-store');
  if((req.url==='/conectar'||req.url==='/comprobar')&&!running){
   running=true;error=null;
   (async()=>{try{if(!state.tokens)await authenticate();await verify();}catch(e){error=e.message;}finally{running=false;}})();
   res.writeHead(303,{Location:'/'});res.end();return;
  }
  let body;
  const proofPath=path.join(root,'.estado/tella/validacion.json');const proof=fs.existsSync(proofPath)?JSON.parse(fs.readFileSync(proofPath)):{};
  if(proof.estado==='operativo')body='<p>Conexión verificada. Tella MCP está disponible.</p>';
  else if(!running&&proof.estado==='autorizado_sin_cuenta_tella_vinculada')body='<p>La autorización llegó, pero aún falta asociar la cuenta de Tella.</p><p><a href="https://www.tella.tv/api/login" target="_blank" rel="noopener">Entrar en Tella con la misma cuenta</a> hasta ver la biblioteca.</p><p><a href="/comprobar">Comprobar conexión después de entrar</a></p>';
  else if(running&&state.pending&&state.pending.expires_at>Date.now())body=`<p>Inicia sesión en Tella y autoriza esta conexión.</p><p><a href="${state.pending.verification_uri}" target="_blank" rel="noopener">Abrir autorización oficial de Tella</a></p><p>Código: <strong>${state.pending.user_code}</strong></p><p><a href="/">Comprobar estado</a></p>`;
  else if(running)body='<p>Preparando conexión…</p><script>setTimeout(()=>location.reload(),1500)</script>';
  else body=`${error?'<p>'+error+'</p>':''}<p><a href="/conectar">Iniciar conexión con Tella</a></p>`;
  res.end(page(body));
 });
 server.listen(17477,'127.0.0.1',()=>console.log('Tella: conexión local preparada en http://127.0.0.1:17477'));
}else{
 if(!state.tokens&&process.argv.includes('--comprobar')){console.log('Tella MCP pendiente de autenticación.');process.exit(2);}
 if(!state.tokens)await authenticate();await verify();
}
