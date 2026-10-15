// Pure tests of the shipped portal selectors. No browser, workspace writes or inference.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const source=await fs.readFile(path.join(root,'web/portal.js'),'utf8');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
function extract(name){
  const start=source.indexOf('  function '+name+'(');assert.ok(start>=0,name+' missing');
  const next=/\n  (?:async )?function /g;next.lastIndex=start+3;
  const end=next.exec(source)?.index??source.length;
  return source.slice(start,end);
}
const nodes=Object.fromEntries(['start-automation','automation-mode','apply-current-brand','api-provider-field','mcp-direction-help','agent-preparation','automation-state','copy-agent-brief'].map(id=>[id,{value:id==='automation-mode'?'mcp':'',disabled:false,textContent:'',hidden:false,dataset:{}}]));
const state={selectedProject:{id:'own',source:'a_test_source'},status:null,pipelines:new Map(),providers:[],jobs:[],submittedAuto:new Map(),automationBusy:false,brandBusy:false};
const context={state,$:id=>nodes[id],paintPreparation:()=>{},paintPipeline:()=>{}};
vm.createContext(context);vm.runInContext(['activeProduction','pipelineAvailable','pipelineOpen','preparationFor','productionFor','updateAutomationControls'].map(extract).join('\n')+'\nglobalThis.run=updateAutomationControls;',context);
const results=[];
function job(id,action,status='completed',result,project='own'){return {id,project_id:project,action,status,result};}
function check(name,jobs,assertion){
  state.jobs=jobs;state.submittedAuto.clear();state.automationBusy=false;
  for(const node of Object.values(nodes)){node.disabled=false;node.textContent='';node.dataset={};}
  context.run();assertion();results.push({name,passed:true});console.log('PASS '+name);
}
try{
  check('External MCP plan and completed preview survive an empty reload cache',[job('apply','ivan_apply_plan','completed',{preview_job_id:'render'}),job('render','render')],()=>{assert.match(nodes['automation-state'].textContent,/Prueba técnica generada/);assert.equal(nodes['start-automation'].disabled,false);});
  check('A newer foreign workspace project cannot replace the selected production status',[job('api','auto_ivan','completed',{preview_job_id:'render'}),job('render','render'),job('foreign','ivan_apply_plan','failed',null,'other')],()=>assert.match(nodes['automation-state'].textContent,/Prueba técnica generada/));
  check('A newer own API run supersedes an earlier failed direction',[job('old','ivan_apply_plan','failed'),job('api','auto_ivan','completed',{preview_job_id:'new-render'}),job('new-render','render')],()=>assert.match(nodes['automation-state'].textContent,/Prueba técnica generada/));
  check('A new preparation is shown as pending direction rather than an old finished preview',[job('old','ivan_apply_plan','completed',{preview_job_id:'render'}),job('render','render'),job('prepare','ivan_prepare','completed',{preparation_id:'real-context'})],()=>{assert.match(nodes['automation-state'].textContent,/Contexto preparado/);assert.doesNotMatch(nodes['automation-state'].textContent,/generada/);});
  check('An actual running preview locks duplicate production and copying',[job('apply','ivan_apply_plan','completed',{preview_job_id:'render'}),{...job('render','render','running'),message:'Componiendo escenas'}],()=>{assert.equal(nodes['start-automation'].disabled,true);assert.equal(nodes['copy-agent-brief'].disabled,true);assert.match(nodes['automation-state'].textContent,/Componiendo escenas · running/);});
  check('A failed preview exposes its actual error without a success claim',[job('apply','ivan_apply_plan','completed',{preview_job_id:'render'}),{...job('render','render','failed'),error:'No se pudo validar el recurso'}],()=>{assert.match(nodes['automation-state'].textContent,/No se pudo validar el recurso · failed/);assert.doesNotMatch(nodes['automation-state'].textContent,/generada/);});
  check('A linked preview missing from the poll remains explicitly pending',[job('apply','ivan_apply_plan','completed',{preview_job_id:'not-polled'})],()=>{assert.match(nodes['automation-state'].textContent,/Esperando el estado.*not-polled/);assert.doesNotMatch(nodes['automation-state'].textContent,/generada/);});
  check('A latest failed agent application preserves the failure instead of promoting an old render',[job('old','auto_ivan','completed',{preview_job_id:'render'}),job('render','render'),{...job('new','ivan_apply_plan','failed'),error:'La preparación dejó de estar vigente'}],()=>{assert.match(nodes['automation-state'].textContent,/La preparación dejó de estar vigente · failed/);assert.doesNotMatch(nodes['automation-state'].textContent,/generada/);});
}catch(error){results.push({name:'Production state regression',passed:false,error:error.message});process.exitCode=1;}
const report={at:new Date().toISOString(),kind:'pure shipped frontend selectors; test data only',passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length,results,source_sha256:hash(source),browser:false,model_calls:0,workspace_mutations:0,approval:false};
await fs.mkdir(path.join(root,'.estado/validacion'),{recursive:true});
await fs.writeFile(path.join(root,'.estado/validacion/frontend_multiservice_production.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,failed:report.failed}));
