// Real SDK transport and private account; no provider inference or shell exposed.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const root=process.cwd(), origin='http://127.0.0.1:8776';
const sdk=path.join(root,'../.estado/herramientas/node_modules/@modelcontextprotocol/sdk');
const {Client}=await import(pathToFileURL(path.join(sdk,'dist/esm/client/index.js')));
const {StreamableHTTPClientTransport}=await import(pathToFileURL(path.join(sdk,'dist/esm/client/streamableHttp.js')));
const fixture=JSON.parse(await fs.readFile(path.join(root,'.estado/validacion/multiservice_private_session.json')));
const wid=fixture.auth.workspace.id, report={at:new Date().toISOString(),SDK:JSON.parse(await fs.readFile(path.join(sdk,'package.json'))).version,results:[],provider_calls:0,inference_executed:false};
async function api(method,route,body){
 const response=await fetch(origin+route,{method,headers:{Origin:origin,Cookie:fixture.cookie,'X-Workspace-ID':wid,'X-CSRF-Token':fixture.auth.csrf_token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const result=await response.json();assert.equal(response.status,method==='POST'&&route==='/api/agent-tokens'?201:200,'Own account API failed');return result;
}
let created,client;
try{
 created=await api('POST','/api/agent-tokens',{name:'SDK QA own workspace'});
 client=new Client({name:'ascendia-qa',version:'0.5.0'},{capabilities:{}});
 const transport=new StreamableHTTPClientTransport(new URL(origin+'/mcp'),{requestInit:{headers:{Authorization:'Bearer '+created.token}}});
 await client.connect(transport);report.results.push({name:'Official MCP SDK initializes authenticated HTTP',passed:true});
 const tools=await client.listTools();assert.ok(tools.tools.length>=40);report.tools=tools.tools.map(t=>t.name);report.results.push({name:'SDK receives actual tool schemas',passed:true,count:report.tools.length});
 const result=await client.callTool({name:'project_get',arguments:{project_id:fixture.project_id}});assert.equal(result.isError,false);const project=JSON.parse(result.content[0].text);assert.equal(project.id,fixture.project_id);assert.equal(project.style.branding.base,'ivan_yo_clone');report.results.push({name:'Agent reads its canonical project and own branding',passed:true});
 const denied=await fetch(origin+'/api/providers',{headers:{Authorization:'Bearer '+created.token}});assert.equal(denied.status,403);report.results.push({name:'Agent cannot manage account API credentials',passed:true});
 await api('DELETE','/api/agent-tokens/'+created.id,{});report.revoked=true;
 let rejected=false;try{await client.listTools();}catch{rejected=true;}assert.ok(rejected);report.results.push({name:'Revocation rejects next SDK request',passed:true});
}catch{report.failed=true;process.exitCode=1;}finally{
 if(created&&!report.revoked){try{await api('DELETE','/api/agent-tokens/'+created.id,{});report.revoked=true;}catch{}}
 if(client)await client.close();
 report.source_sha256=crypto.createHash('sha256').update(await fs.readFile(path.join(root,'tests/mcp_multiservice.mjs'))).digest('hex');
 await fs.writeFile(path.join(root,'.estado/validacion/mcp_multiservice_sdk.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
 console.log(JSON.stringify({passed:report.results.length,failed:report.failed===true,revoked:report.revoked,SDK:report.SDK,tools:report.tools?.length}));
}
