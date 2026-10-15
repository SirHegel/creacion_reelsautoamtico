import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';

// Read-only restart check: no processing, export, import or project writes.
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);process.env.TMPDIR='.estado/tmp';
const require=createRequire(import.meta.url);
const {chromium}=require(path.join(root,'../.estado/herramientas/node_modules/playwright'));
const base=process.env.STUDIO_URL||'http://127.0.0.1:8765';
const id='p_910174bf60f74b75',sourceId='a_a489c41844014c91c2fd',derivedId='a_28b569e2f8d71c0ccabe';
const protectedIds=[id,'p_b82375e1c80d4dab','p_13aa3f878757456e','p_19bf3e6884734446'];
const sha=value=>crypto.createHash('sha256').update(value).digest('hex');
const snapshots={};for(const pid of protectedIds)snapshots[pid]=sha(await fs.readFile(path.join(root,'projects',pid,'project.json')));
const results=[],errors=[],httpErrors=[],writes=[],evidence={};let project,catalog,jobsBefore;
const browser=await chromium.launchPersistentContext(path.join(root,'.estado/browser-segmentation-reopen'),{
  executablePath:'/usr/bin/google-chrome',headless:true,viewport:{width:1440,height:1020},
  args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--no-first-run','--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],
  env:{...process.env,TMPDIR:'.estado/tmp',XDG_CACHE_HOME:path.join(root,'.estado/cache'),XDG_CONFIG_HOME:path.join(root,'.estado/config')}
});
const page=browser.pages()[0]||await browser.newPage();
page.on('pageerror',error=>errors.push(error.message));
page.on('response',response=>{if(response.status()>=400&&!response.url().includes('favicon'))httpErrors.push({url:response.url(),status:response.status()});});
page.on('request',request=>{if(['POST','PUT','PATCH','DELETE'].includes(request.method()))writes.push({method:request.method(),url:request.url()});});
const get=async route=>{const response=await page.request.get(base+route);assert.ok(response.ok(),await response.text());return response.json();};
async function step(name,fn){await fn();results.push({name,passed:true});console.log('PASS '+name);}
try{
  await step('Restart serves the current engine, persisted jobs and verified segmentation proof',async()=>{
    const status=await get('/api/status');assert.equal(status.version,'0.3.0');assert.equal(status.restart_required,false);assert.equal(status.capabilities.segmentation.verified_execution,true);
    assert.equal(status.capabilities.segmentation.gpu_used,false);const ops=(await get('/api/media-tools')).operations;assert.equal(ops.length,11);assert.equal(ops.find(op=>op.id==='remove_background_video').available,true);
    jobsBefore=(await get('/api/jobs')).jobs.map(job=>job.id);assert.ok((await get('/api/jobs')).jobs.every(job=>!['queued','running'].includes(job.status)));
    evidence.engine={version:status.version,fingerprint:status.capabilities.segmentation.fingerprint,verified_execution:true,restart_required:false};
  });
  await step('Canonical source, alpha MOV and observations survive the restart unapproved',async()=>{
    project=await get('/api/projects/'+id);catalog=(await get('/api/assets')).assets;assert.equal(project.source,sourceId);assert.equal(project.approval_current,false);
    const source=catalog.find(asset=>asset.id===sourceId),derived=catalog.find(asset=>asset.id===derivedId);assert.ok(source&&derived);assert.equal(sha(await fs.readFile(path.join(root,source.path))),source.sha256);assert.equal(sha(await fs.readFile(path.join(root,derived.path))),derived.sha256);
    assert.equal(derived.metadata.source,sourceId);assert.equal(derived.preview_preserves_alpha,true);assert.equal(derived.verification.visual,false);assert.equal(derived.verification.audio,false);
    const attached=project.assets.find(asset=>asset.id===derivedId);assert.match(attached.metadata.origin_observed,/Origen observado/);assert.equal(attached.metadata.provenance.approved_for_ascendia,false);
    evidence.resources={source:sourceId,derived:derivedId,mov_sha256:derived.sha256,original_sha256:source.sha256,project_revision:project.revision,approved:false};
  });
  await step('Fresh browser loads the persisted project and real transparent proxy',async()=>{
    await page.goto(base);await page.waitForFunction(()=>document.querySelector('#connection-label').textContent==='Motor local');await page.locator('#project-select').selectOption(id);
    await page.waitForFunction(pid=>document.querySelector('#project-select').value===pid&&!document.querySelector('#save-state').textContent.includes('Cargando'),id);
    await page.locator('[data-tab="library"]').click();await page.locator(`[data-view="${derivedId}"]`).click();await page.waitForFunction(()=>{const video=document.querySelector('#asset-review-media');return video?.readyState>=2&&video.videoWidth===360;});
    assert.equal(await page.locator('#asset-verified').isChecked(),false);await page.locator('#media-operation').waitFor({state:'attached'});
    const playback=await page.locator('#asset-review-media').evaluate(async video=>{video.muted=true;await video.play();await new Promise(resolve=>setTimeout(resolve,180));video.pause();return{width:video.videoWidth,height:video.videoHeight,duration:video.duration,time:video.currentTime,error:video.error?.code??null};});
    assert.equal(playback.height,640);assert.ok(playback.time>.05);assert.equal(playback.error,null);evidence.playback={...playback,muted:true,audio_listening:false};
  });
  await step('Browser-decoded alpha and downloadable canonical bytes remain distinct',async()=>{
    const alpha=await page.locator('#asset-review-media').evaluate(video=>{const canvas=document.createElement('canvas');canvas.width=video.videoWidth;canvas.height=video.videoHeight;const context=canvas.getContext('2d');context.drawImage(video,0,0);const bytes=context.getImageData(0,0,canvas.width,canvas.height).data;let clear=0,opaque=0,soft=0;for(let i=3;i<bytes.length;i+=4){if(bytes[i]===0)clear++;else if(bytes[i]===255)opaque++;else soft++;}return{clear,opaque,soft};});assert.ok(alpha.clear>1000&&alpha.opaque>1000&&alpha.soft>0);
    await page.locator('#asset-preview-background').selectOption('light');assert.equal(await page.locator('#asset-preview-frame').getAttribute('data-background'),'light');
    const href=await page.locator('#modal-content a[download]').getAttribute('href');const response=await page.request.get(new URL(href,base).href);assert.ok(response.ok());assert.equal(sha(await response.body()),evidence.resources.mov_sha256);evidence.alpha=alpha;evidence.canonical_download_sha_valid=true;
  });
  await step('Mobile inspection remains readable and project observations stay pending',async()=>{
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await page.locator('#asset-verified').isChecked(),false);
    assert.equal(await page.locator('#asset-review-form button[type="submit"]').isDisabled(),false);await page.locator('#close-modal').click();evidence.mobile_overflow=false;
  });
  await step('Reopening makes no writes, jobs or changes to any protected project',async()=>{
    for(const pid of protectedIds)assert.equal(sha(await fs.readFile(path.join(root,'projects',pid,'project.json'))),snapshots[pid]);
    assert.deepEqual((await get('/api/jobs')).jobs.map(job=>job.id),jobsBefore);assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);assert.deepEqual(httpErrors,[]);evidence.project_sha256=snapshots;
  });
}catch(error){results.push({name:'Failure',passed:false,error:error.stack});console.error(error);process.exitCode=1;}
finally{
  const code={};for(const filename of ['web/app.js','web/index.html','web/style.css'])code[filename]=sha(await fs.readFile(path.join(root,filename)));
  await fs.writeFile(path.join(root,'.estado/validacion/browser_segmentation_reopen_v03.json'),JSON.stringify({at:new Date().toISOString(),passed:results.filter(result=>result.passed).length,failed:results.filter(result=>!result.passed).length,results,errors,httpErrors,writes,evidence,code_sha256:code,read_only:true,gpu:false,editorial_approval:false},null,2)+'\n');await browser.close();
}
