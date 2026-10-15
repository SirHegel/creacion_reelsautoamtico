// Actual SDK, own isolated account and complete technical draft. No paid inference.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const root=process.cwd(),origin='http://127.0.0.1:8776';
const folder=path.join(root,'.estado/validacion/pipeline_full');
const sdk=path.join(root,'../.estado/herramientas/node_modules/@modelcontextprotocol/sdk');
const {Client}=await import(pathToFileURL(path.join(sdk,'dist/esm/client/index.js')));
const {StreamableHTTPClientTransport}=await import(pathToFileURL(path.join(sdk,'dist/esm/client/streamableHttp.js')));
const fixture=JSON.parse(await fs.readFile(path.join(root,'.estado/validacion/multiservice_private_session.json')));
const input=JSON.parse(await fs.readFile(path.join(folder,'project.json')));
const plans=JSON.parse(await fs.readFile(path.join(folder,'plans_candidate.json')));
const wid=fixture.auth.workspace.id,pid=input.project_id;
assert.match(wid,/^w_[a-f0-9]{32}$/);assert.match(pid,/^p_[a-f0-9]{16}$/);
assert.notEqual(pid,fixture.project_id,'Preserve the historical eight-second project');
const report={at:new Date().toISOString(),SDK:JSON.parse(await fs.readFile(path.join(sdk,'package.json'))).version,
  project_id:pid,results:[],paid_provider_calls:0,external_agent:'Root Codex',
  external_model_provider_verified:false,technical_only:true,editorial_approved:false,audio_listened:false};
let created,client;
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const preservedPaths=[`workspaces/${wid}/projects/${fixture.project_id}/project.json`,
  `workspaces/${wid}/projects/${fixture.project_id}/technical_preview.mp4`,
  `workspaces/${wid}/exports/${fixture.project_id}_editable.zip`];
const preservedBefore=await Promise.all(preservedPaths.map(async p=>[p,sha(await fs.readFile(path.join(root,p)))]));
async function api(method,route,body){
  const response=await fetch(origin+route,{method,headers:{Origin:origin,Cookie:fixture.cookie,
    'X-Workspace-ID':wid,'X-CSRF-Token':fixture.auth.csrf_token,'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body)});
  const result=await response.json();
  assert.equal(response.status,method==='POST'&&route==='/api/agent-tokens'?201:200,'Own account API failed');return result;
}
async function call(name,args){
  const result=await client.callTool({name,arguments:args});
  assert.equal(result.isError,false,`Tool ${name} failed`);
  return JSON.parse(result.content[0].text);
}
async function deny(name,args){
  let rejected=false;
  try{const result=await client.callTool({name,arguments:args});rejected=result.isError===true;}catch{rejected=true;}
  assert.ok(rejected,`Tool ${name} accepted invalid arguments`);
}
try{
  created=await api('POST','/api/agent-tokens',{name:'Pipeline v06 SDK QA own workspace'});
  client=new Client({name:'ascendia-pipeline-qa',version:'0.6.0'},{capabilities:{}});
  await client.connect(new StreamableHTTPClientTransport(new URL(origin+'/mcp'),{
    requestInit:{headers:{Authorization:'Bearer '+created.token}}}));
  report.results.push({name:'Official SDK authenticates current workspace',passed:true});
  const listed=await client.listTools();report.tools=listed.tools.map(t=>t.name);
  for(const name of ['pipeline_get','pipeline_plan','pipeline_resume','pipeline_restart','draft_render','cloud_storage_status']){
    const tool=listed.tools.find(t=>t.name===name);assert.ok(tool);assert.equal(tool.inputSchema.additionalProperties,false);
  }
  report.results.push({name:'Current closed tool schemas include both draft modes and pipeline',passed:true,count:report.tools.length});
  const project=await call('project_get',{project_id:pid});
  assert.equal(project.id,pid);assert.equal(project.settings.split_motion_ratio,.5);
  assert.equal(project.style.branding.base,'ivan_yo_clone');
  const state=await call('pipeline_get',{project_id:pid});
  assert.equal(state.status,'waiting_external');assert.equal(state.chunks.length,Object.keys(plans).length);
  assert.ok(state.chunks.every(c=>c.context));assert.equal(state.scope_seconds,12);
  report.generation=state.generation;report.initial_revision=state.project_revision;
  report.results.push({name:'Agent receives actual aligned whole-source context',passed:true,
    duration:state.scope_seconds,chunks:state.chunks.length,generation:state.generation});
  const denied=await fetch(origin+'/api/providers',{headers:{Authorization:'Bearer '+created.token}});
  assert.equal(denied.status,403);
  const cloud=await call('cloud_storage_status',{});
  assert.equal(cloud.remote,false);assert.equal(cloud.configured,false);
  report.results.push({name:'Agent cannot manage account keys; cloud is accurately disconnected',passed:true});
  await deny('pipeline_get',{project_id:pid,shell:'arbitrary command'});
  const chunk=state.chunks[0];
  await deny('pipeline_plan',{project_id:pid,generation:state.generation-1,chunk_id:chunk.id,
    expected_revision:state.project_revision,document:plans[chunk.id],agent:{name:'Root Codex'}});
  const unchanged=await call('pipeline_get',{project_id:pid});
  assert.equal(unchanged.project_revision,state.project_revision);
  assert.ok(unchanged.chunks.every(c=>!c.plan));
  report.results.push({name:'Extra fields and stale generation reject without mutation',passed:true});
  for(const chunk of state.chunks){
    assert.ok(plans[chunk.id]);
    const submitted=await call('pipeline_plan',{project_id:pid,generation:state.generation,
      chunk_id:chunk.id,expected_revision:state.project_revision,document:plans[chunk.id],
      agent:{name:'Root Codex',notes:'Actual root agent authored closed conceptual test data. No model API attestation or editorial approval.'}});
    assert.ok(submitted.chunks.find(c=>c.id===chunk.id).plan);
  }
  const directed=await call('pipeline_get',{project_id:pid});
  assert.ok(directed.chunks.every(c=>c.current_plan?.schema==='ascendia.ivan-plan/1'));
  report.results.push({name:'Actual SDK submits both validated plans and reads current plan evidence',passed:true});
  const job=await call('pipeline_resume',{project_id:pid,generation:state.generation});report.job_id=job.id;
  const deadline=Date.now()+15*60*1000;
  let current;
  do{
    await new Promise(resolve=>setTimeout(resolve,3000));
    current=await call('job_get',{job_id:job.id});
    if(Date.now()>deadline)throw new Error('Technical pipeline exceeded the observation deadline');
  }while(['queued','running'].includes(current.status));
  await fs.writeFile(path.join(folder,'render_job.json'),JSON.stringify(current,null,2)+'\n',{mode:0o600});
  assert.equal(current.status,'completed','Full pipeline job did not complete');
  const final=await call('pipeline_get',{project_id:pid});
  assert.equal(final.status,'completed');assert.equal(final.editorial_approved,false);
  assert.equal(final.audio_listened,false);assert.equal(final.qc.ok,true);
  assert.ok(final.chunks.every(c=>c.current_plan));
  await fs.writeFile(path.join(folder,'pipeline_result.json'),JSON.stringify(final,null,2)+'\n',{mode:0o600});
  report.results.push({name:'Actual full technical pipeline renders and exports without approving content',passed:true,
    status:final.status,generation:final.generation,stages:Object.keys(final.stages)});
  await api('DELETE','/api/agent-tokens/'+created.id,{});report.revoked=true;
  let rejected=false;try{await client.listTools();}catch{rejected=true;}assert.ok(rejected);
  report.results.push({name:'Revocation rejects the next SDK request',passed:true});
}catch(error){
  report.failed=true;report.error=String(error.message).slice(0,500);process.exitCode=1;
}finally{
  if(created&&!report.revoked){try{await api('DELETE','/api/agent-tokens/'+created.id,{});report.revoked=true;}catch{report.cleanup_failed=true;}}
  if(client)await client.close();
  report.source_sha256=sha(await fs.readFile(path.join(root,'tests/mcp_pipeline_v06.mjs')));
  report.protected_projects=[];
  for(const [p,before] of preservedBefore){const after=sha(await fs.readFile(path.join(root,p)));report.protected_projects.push({path:p,before,after,unchanged:before===after});if(before!==after){report.failed=true;process.exitCode=1;}}
  await fs.writeFile(path.join(folder,'mcp_sdk.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  console.log(JSON.stringify({passed:report.results.length,failed:report.failed===true,revoked:report.revoked,
    SDK:report.SDK,tools:report.tools?.length,job_id:report.job_id,error:report.error,
    protected_unchanged:report.protected_projects.every(p=>p.unchanged)}));
}
