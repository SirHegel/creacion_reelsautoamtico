// Real gateway and shipped UI, dedicated empty manual project, zero model/render jobs.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';

const root=process.cwd(),origin='http://127.0.0.1:8776';
if(process.env.MODES_V06_READY!=='1')throw new Error('Run only after source freeze and owned gateway restart.');
// Relative TMPDIR keeps Chrome's Unix socket below its path limit, inside SOFTWARE.
process.env.TMPDIR='.estado/tmp';
const require=createRequire(import.meta.url),{chromium}=require(path.join(root,'../.estado/herramientas/node_modules/playwright'));
const fixture=JSON.parse(await fs.readFile(path.join(root,'.estado/validacion/multiservice_private_session.json')));
const wid=fixture.auth.workspace.id,folder=path.join(root,'.estado/validacion/modes_v06');
await fs.mkdir(folder,{recursive:true});
const results=[],errors=[],httpErrors=[],sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const preserved=[`workspaces/${wid}/projects/${fixture.project_id}/project.json`,
  `workspaces/${wid}/projects/${fixture.project_id}/technical_preview.mp4`,
  `workspaces/${wid}/exports/${fixture.project_id}_editable.zip`];
const before=await Promise.all(preserved.map(async p=>[p,sha(await fs.readFile(path.join(root,p)))]));
let browser,page,pid,auth;
async function step(name,fn){await fn();results.push({name,passed:true});console.log('PASS '+name);}
async function until(fn,ms=30000){const end=Date.now()+ms;while(Date.now()<end){if(await fn())return;await new Promise(r=>setTimeout(r,150));}throw new Error('Actual UI state did not arrive.');}
async function api(method,route,body){
  const response=await page.request.fetch(origin+'/w/'+wid+route,{method,headers:{Origin:origin,
    'X-Workspace-ID':wid,'X-CSRF-Token':auth.csrf_token,'Content-Type':'application/json'},
    ...(body===undefined?{}:{data:body})});
  assert.equal(response.status(),method==='POST'&&route==='/api/projects'?201:200,'Own fixture API failed');
  return response.json();
}
async function ready(){await until(async()=>await page.locator('#connection-label').innerText()==='Motor local');await until(async()=>(await page.locator('#save-state').innerText()).includes('rev.'));}
try{
  browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,
    args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--no-first-run',
      '--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],
    env:{...process.env,XDG_CACHE_HOME:path.join(root,'.estado/cache'),XDG_CONFIG_HOME:path.join(root,'.estado/config')}});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const separator=fixture.cookie.indexOf('=');
  await context.addCookies([{name:fixture.cookie.slice(0,separator),value:fixture.cookie.slice(separator+1).split(';')[0],
    domain:'127.0.0.1',path:'/',httpOnly:true,sameSite:'Strict'}]);
  page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400&&!r.url().endsWith('/favicon.ico'))httpErrors.push({url:r.url(),status:r.status(),method:r.request().method()});});
  await step('Authenticated home offers Automatic and Manual with own/shared project tabs',async()=>{
    await page.goto(origin+'/portal');await page.locator('#workspace-screen').waitFor({state:'visible'});
    auth=await page.request.get(origin+'/api/auth/me').then(r=>r.json());assert.equal(auth.workspace.id,wid);
    assert.ok(await page.locator('#new-automatic').isVisible());assert.ok(await page.locator('#new-manual').isVisible());
    assert.equal(await page.locator('[data-project-scope]').count(),2);
  });
  await step('Automatic opens the actual raw workflow without a model call or upload',async()=>{
    await page.locator('#new-automatic').click();await page.locator('#production-panel').waitFor({state:'visible'});
    assert.equal(await page.locator('#automation-region').isVisible(),false);
    await page.locator('#close-production').click();
  });
  await step('Manual creates its own canonical editable project without requiring a raw',async()=>{
    await page.locator('#new-manual').click();await page.locator('#manual-project-form').waitFor();
    await page.locator('#manual-project-name').fill('QA modos y proporción · proyecto vacío');
    await page.locator('#create-manual-project').click();
    await page.waitForURL(/\/editor\?.*mode=manual/);await ready();
    pid=new URL(page.url()).searchParams.get('project');assert.match(pid,/^p_[a-f0-9]{16}$/);assert.notEqual(pid,fixture.project_id);
    await fs.writeFile(path.join(folder,'project.json'),JSON.stringify({project_id:pid,workspace_id:wid},null,2)+'\n',{mode:0o600});
    const p=await api('GET','/api/projects/'+pid);assert.equal(p.settings.split_motion_ratio,.5);assert.equal(p.source,null);
  });
  await step('New source-free project settings show actual 50/50 and disabled absent audio',async()=>{
    await page.locator('#open-settings').click();await page.locator('#settings-form').waitFor();
    assert.equal(await page.locator('#setting-split-ratio').inputValue(),'0.5');
    assert.ok(await page.locator('#setting-voice-track').isDisabled());
    await page.locator('#close-modal').click();
  });
  await step('An intermediate 53/47 and nonstandard resolution/FPS survive the actual API and UI',async()=>{
    const p=await api('GET','/api/projects/'+pid);p.settings={...p.settings,width:360,height:642,fps:15,split_motion_ratio:.53};
    await api('PUT','/api/projects/'+pid,p);await page.reload();await ready();
    await page.locator('#open-settings').click();await page.locator('#settings-form').waitFor();
    assert.equal(await page.locator('#setting-split-ratio').inputValue(),'0.53');
    assert.equal(await page.locator('#setting-resolution').inputValue(),'current');
    assert.equal(await page.locator('#setting-fps').inputValue(),'15');
    await page.locator('#setting-split-ratio').selectOption('0.55');await page.locator('#apply-project-settings').click();
    const save=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/api/projects/'+pid));
    await page.locator('#save-project').click();assert.equal((await save).status(),200);
    const saved=await api('GET','/api/projects/'+pid);assert.equal(saved.settings.split_motion_ratio,.55);
    assert.equal(saved.settings.height,642);assert.equal(saved.settings.fps,15);
  });
  await step('Choosing 50/50 is saved and remains exact after a genuine page reload',async()=>{
    await page.locator('#open-settings').click();await page.locator('#setting-split-ratio').selectOption('0.5');
    await page.locator('#apply-project-settings').click();const save=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url().endsWith('/api/projects/'+pid));
    await page.locator('#save-project').click();assert.equal((await save).status(),200);await page.reload();await ready();
    await page.locator('#open-settings').click();assert.equal(await page.locator('#setting-split-ratio').inputValue(),'0.5');
    await page.locator('#close-modal').click();
    const p=await api('GET','/api/projects/'+pid);assert.equal(p.settings.width,360);assert.equal(p.settings.height,642);assert.equal(p.settings.fps,15);
  });
  await step('Production explains both full draft modes and the cloud dialog reports disconnected storage',async()=>{
    await page.locator('[data-tab=workflow]').click();
    assert.match(await page.locator('#workflow-scope-note').innerText(),/Automático o Manual/);
    await page.locator('#cloud-backup').waitFor({state:'visible'});await page.locator('#cloud-backup').click();
    await page.locator('#start-cloud-backup').waitFor();assert.ok(await page.locator('#start-cloud-backup').isDisabled());
    assert.match(await page.locator('#modal-content').innerText(),/todavía no conectó|este servidor/);
    await page.locator('#close-modal').click();
  });
  await step('Actual empty project stays unapproved and queues no ASR, provider, render or cloud job',async()=>{
    const p=await api('GET','/api/projects/'+pid);assert.ok(!p.review?.approved_preview&&!p.approved_export);
    const list=await api('GET','/api/jobs');assert.equal(list.jobs.filter(j=>j.project_id===pid).length,0);
    assert.deepEqual(errors,[]);
    assert.deepEqual(httpErrors.filter(e=>!(e.status===404&&e.method==='GET'&&/\/pipeline$/.test(e.url))),[]);
  });
}catch(error){results.push({name:'Actual browser execution',passed:false,error:error.message});process.exitCode=1;console.error(error.message);}
finally{
  if(browser)await browser.close();
  const protectedFiles=[];for(const [p,digest]of before){const after=sha(await fs.readFile(path.join(root,p)));protectedFiles.push({path:p,before:digest,after,unchanged:after===digest});if(after!==digest)process.exitCode=1;}
  const source_sha256={};for(const name of ['app.js','index.html','portal.js','portal.html'])source_sha256[name]=sha(await fs.readFile(path.join(root,'web',name)));
  const report={at:new Date().toISOString(),project_id:pid,passed:results.filter(r=>r.passed).length,
    failed:results.filter(r=>!r.passed).length,results,errors,httpErrors,protectedFiles,source_sha256,
    real_gateway:true,backend_mocked:false,browser_closed:true,gpu:false,paid_provider_calls:0,asr_jobs:0,render_jobs:0,remote_cloud_calls:0};
  await fs.writeFile(path.join(folder,'browser.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
  console.log(JSON.stringify({passed:report.passed,failed:report.failed,errors:errors.length,protected_unchanged:protectedFiles.every(f=>f.unchanged)}));
}
