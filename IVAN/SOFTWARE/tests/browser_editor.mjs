import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);process.env.TMPDIR='.estado/tmp';process.env.XDG_CACHE_HOME=path.join(root,'.estado','cache');process.env.XDG_CONFIG_HOME=path.join(root,'.estado','config');
const require=createRequire(import.meta.url);
const {chromium}=require(path.join(root,'..','.estado','herramientas','node_modules','playwright'));
const url=process.env.STUDIO_URL||'http://127.0.0.1:8765';
const input=path.join(root,'.estado','tmp','ui_smoke_source.mp4');
const overlayInput=path.join(root,'.estado','tmp','ui_alpha_overlay.png');
const captionInput=path.join(root,'.estado','tmp','ui_caption_source.mp4');
const screenshotDir=path.join(root,'docs');
for(const folder of ['.estado/tmp','.estado/browser','.estado/cache','.estado/config'])await fs.mkdir(path.join(root,folder),{recursive:true});
try{await fs.access(input);}catch(_){execFileSync('ffmpeg',['-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=360x640:rate=30:duration=4','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest','-y',input],{cwd:root,env:{...process.env,TMPDIR:'.estado/tmp'}});}
try{await fs.access(overlayInput);}catch(_){execFileSync('python3',['-B','-c','from PIL import Image,ImageDraw; import sys; im=Image.new("RGBA",(120,120),(0,0,0,0)); ImageDraw.Draw(im).rectangle((30,30,90,90),fill=(255,255,255,255)); im.save(sys.argv[1])',overlayInput],{cwd:root,env:{...process.env,TMPDIR:'.estado/tmp'}});}
try{await fs.access(captionInput);}catch(_){execFileSync('ffmpeg',['-nostdin','-v','error','-f','lavfi','-i','color=c=0xccaa88:size=360x640:rate=30:duration=10','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-y',captionInput],{cwd:root,env:{...process.env,TMPDIR:'.estado/tmp'}});}
const errors=[],failures=[],results=[];
let expectedConflict=false;
const browser=await chromium.launchPersistentContext(path.join(root,'.estado','browser'),{
  executablePath:process.env.STUDIO_BROWSER||'/usr/bin/google-chrome',headless:true,
  viewport:{width:1440,height:960},acceptDownloads:true,
  downloadsPath:path.join(root,'.estado','tmp'),
  args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],
  // A relative temp path stays in SOFTWARE and fits Chrome's Unix socket limit.
  env:{...process.env,TMPDIR:'.estado/tmp',XDG_CACHE_HOME:path.join(root,'.estado','cache'),XDG_CONFIG_HOME:path.join(root,'.estado','config')},
});
const page=browser.pages()[0]||await browser.newPage();
page.on('pageerror',error=>errors.push(error.message));
page.on('response',response=>{if(response.status()>=400&&!response.url().includes('favicon')&&!(expectedConflict&&response.status()===409))failures.push({url:response.url(),status:response.status()});});
async function step(name,fn){await fn();results.push(name);console.log('PASS '+name);}
async function project(){const id=await page.locator('#project-select').inputValue();return (await page.request.get(url+'/api/projects/'+id)).json();}
async function waitUntil(predicate,timeout=60000){const deadline=Date.now()+timeout;while(Date.now()<deadline){if(await predicate())return;await page.waitForTimeout(250);}throw new Error('Timed out waiting for actual asynchronous API result.');}
let testProject;
try {
  await step('Editor starts with local capabilities and real media',async()=>{
    await page.goto(url);await page.locator('#connection-label').filter({hasText:'Motor local'}).waitFor();
    await page.waitForFunction(()=>document.querySelectorAll('#assets-grid .asset-card').length>=4);
    assert.match(await page.locator('.brand').innerText(),/ASCENDIA\s+STUDIO/);
  });
  await step('Create isolated project and upload real MP4',async()=>{
    const all=(await(await page.request.get(url+'/api/projects')).json()).projects,existing=all.find(p=>p.name==='UI · prueba técnica automatizada');
    if(existing){
      const p=await(await page.request.get(url+'/api/projects/'+existing.id)).json();p.source=null;p.assets=[];p.timeline=[];p.audio=[];p.transcript={words:[],segments:[]};p.reference_review={};
      const reset=await page.request.put(url+'/api/projects/'+p.id,{data:p});assert.equal(reset.ok(),true);await page.reload();await page.locator('#project-select').selectOption(p.id);await page.waitForFunction(()=>document.querySelector('#add-scene').disabled===false&&document.querySelector('#render-project').disabled===true&&document.querySelector('#save-state').textContent.includes('Guardado'));
    }else{await page.locator('#new-project').click();await page.locator('#project-name').fill('UI · prueba técnica automatizada');await page.locator('#create-project-form button[type="submit"]').click();}
    await page.locator('#file-input').setInputFiles(input);
    await waitUntil(async()=>Boolean((await project()).assets.find(a=>a.name==='ui_smoke_source.mp4')));
    testProject=await project();assert.ok(testProject.source);assert.ok(testProject.assets.some(a=>a.name==='ui_smoke_source.mp4'));assert.ok(testProject.assets.find(a=>a.id===testProject.source).waveform.peaks.length);
    await page.waitForFunction(()=>document.querySelector('#source-video').readyState>=2);
    await page.locator('#file-input').setInputFiles(captionInput);await waitUntil(async()=>Boolean((await project()).assets.find(a=>a.name==='ui_caption_source.mp4')));await page.waitForFunction(()=>document.querySelector('#file-input').value==='');assert.equal((await project()).source,testProject.source);
  });
  await step('Edit scene, additive brightness, and save',async()=>{
    await page.locator('#add-scene').click();await page.locator('#scene-type').selectOption('presenter');
    await page.locator('#scene-title').fill('Prueba técnica de interfaz');await page.locator('#scene-start').click();
    await page.locator('#scene-brightness').evaluate(el=>{el.value='1.2';el.dispatchEvent(new Event('change'));});
    await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));
    const p=await project();assert.equal(p.timeline.length,1);assert.equal(p.timeline[0].title,'Prueba técnica de interfaz');assert.ok(Math.abs(p.timeline[0].effects.brightness-.2)<1e-9);
  });
  await step('Edits made during an actual delayed PUT remain pending and save correctly',async()=>{
    const p=await project();await page.locator('#scene-title').fill('Revisión enviada al servidor');await page.locator('#scene-start').click();let release,held=false;const delay=new Promise(resolve=>release=resolve);
    const handler=async route=>{if(route.request().method()==='PUT'){held=true;await delay;}await route.continue();};await page.route(url+'/api/projects/'+p.id,handler);
    await page.locator('#save-project').click();await waitUntil(()=>held,5000);await page.locator('#scene-title').fill('Edición durante el guardado');await page.locator('#scene-start').click();release();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Nuevos cambios'));
    assert.equal(await page.locator('#scene-title').inputValue(),'Edición durante el guardado');assert.equal((await project()).timeline[0].title,'Revisión enviada al servidor');await page.unroute(url+'/api/projects/'+p.id,handler);
    await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));assert.equal((await project()).timeline[0].title,'Edición durante el guardado');
  });
  await step('Timeline scrub, split, undo and redo persist',async()=>{
    const ruler=await page.locator('#timeline-ruler').boundingBox();await page.mouse.click(ruler.x+84,ruler.y+10);await page.locator('#split-scene').click();assert.equal(await page.locator('#picture-track .timeline-clip').count(),2);
    await page.locator('#undo').click();assert.equal(await page.locator('#picture-track .timeline-clip').count(),1);await page.locator('#redo').click();assert.equal(await page.locator('#picture-track .timeline-clip').count(),2);
    await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));assert.equal((await project()).timeline.length,2);
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);
  });
  await step('Counter accepts an explicit script value and context evidence',async()=>{
    await page.locator('#picture-track .timeline-clip').nth(1).click();await page.locator('#scene-type').selectOption('motion');await page.locator('#scene-template').selectOption('counter');
    await page.locator('#motion-data-section summary').click();await page.locator('#scene-value').fill('42');await page.locator('#scene-value-from').click();
    const details=page.locator('#scene-search').locator('..').locator('..');await details.locator('summary').click();
    await page.locator('#scene-search').fill('Prueba técnica sobre recurso sintético; no corresponde a narración de Iván.');await page.locator('#scene-reason').fill('Comprobar persistencia del inspector.');await page.locator('#scene-search').click();
    await page.locator('#choose-scene-evidence').click();await page.locator('#modal-content [data-evidence]').first().click();
    await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));
    const p=await project(),scene=p.timeline[1];assert.equal(scene.motion.value,42);assert.ok(scene.decision.evidence[0]);assert.ok(!scene.decision.evidence[0].startsWith('/api/'));
  });
  await step('Independent image layer preserves transparency and editable keyframes',async()=>{
    await page.locator('#file-input').setInputFiles(overlayInput);await page.locator('#scene-asset option').filter({hasText:'ui_alpha_overlay.png'}).waitFor({state:'attached'});
    const p=await project(),image=p.assets.find(a=>a.name==='ui_alpha_overlay.png');assert.ok(image);await page.locator('#picture-track .timeline-clip').nth(1).click();await page.locator('#overlay-section summary').click();await page.locator('#add-overlay').click();await page.locator('[data-layer-field="asset_id"]').selectOption(image.id);
    await page.locator('[data-layer-field="x"]').fill('.15');await page.locator('[data-layer-field="y"]').click();
    await page.locator('#overlay-list details summary').first().click();await page.locator('[data-layer-add-key]').click();await page.locator('[data-layer-key-field="scale"]').fill('1.2');await page.locator('[data-layer-key-field="time"]').click();
    await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));const edited=await project();assert.equal(edited.timeline[1].overlays[0].asset_id,image.id);assert.equal(edited.timeline[1].overlays[0].keyframes[0].scale,1.2);assert.equal(edited.source,p.source);
    await page.waitForTimeout(120);const pixels=await page.locator('#preview-canvas').evaluate(canvas=>{const c=canvas.getContext('2d');return{white:[...c.getImageData(160,380,1,1).data],clear:[...c.getImageData(82,304,1,1).data]};});assert.ok(pixels.white[0]>230);assert.ok(pixels.clear[0]<100);assert.equal(await page.locator('#overlay-track .overlay-clip').count(),1);
  });
  await step('Splitting and trimming a PNG layer keeps its static source entry at zero',async()=>{
    const original=await project();await page.locator('#picture-track .timeline-clip').nth(1).click();const ruler=await page.locator('#timeline-ruler').boundingBox();await page.mouse.click(ruler.x+1.85*70,ruler.y+10);await page.locator('#split-scene').click();await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));
    let p=await project();assert.equal(p.timeline.length,3);assert.equal(p.timeline[1].overlays[0].source_in,0);assert.equal(p.timeline[2].overlays[0].source_in,0);
    await page.locator('#picture-track .timeline-clip').nth(2).click();await page.locator('#overlay-section').evaluate(el=>el.open=true);await page.locator('[data-layer-field="start"]').fill('.1');await page.locator('[data-layer-field="end"]').click();await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));p=await project();assert.equal(p.timeline[2].overlays[0].source_in,0);
    original.revision=p.revision;assert.equal((await page.request.put(url+'/api/projects/'+p.id,{data:original})).ok(),true);await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);
  });
  await step('Playback moves the playhead with original audio',async()=>{
    await page.locator('#jump-start').click();await page.locator('#play-button').click();await page.waitForTimeout(450);await page.locator('#play-button').click();
    const time=await page.locator('#source-video').evaluate(video=>video.currentTime);assert.ok(time>.2);
  });
  await step('Canvas obeys the 55/45 split and timed three-word captions',async()=>{
    const original=await project(),fixture=structuredClone(original);fixture.source=fixture.assets.find(a=>a.name==='ui_caption_source.mp4'&&a.duration>=10).id;fixture.timeline=[{id:'ui_split_fixture',start:0,end:2,type:'split',template:'workflow',source_in:0,chin_y:.65,subtitle:'No debe aparecer en hook',nodes:['Entrada','Acción','Resultado'],effects:{brightness:0,contrast:1,saturation:1}},{id:'ui_caption_fixture',start:2,end:10,type:'motion',template:'kinetic',title:'',chin_y:.65}];fixture.transcript={segments:[{start:0,end:10,text:'Datos sintéticos para probar temporización.'}],words:[{start:.1,end:.4,word:'HOOK'},{start:4.6,end:4.85,word:'texto'},{start:4.85,end:5.1,word:'de'},{start:5.1,end:5.4,word:'prueba'}]};
    assert.equal((await page.request.put(url+'/api/projects/'+fixture.id,{data:fixture})).ok(),true);await page.reload();await page.waitForFunction(()=>document.querySelector('#presenter-video').readyState>=2);
    const ruler=await page.locator('#timeline-ruler').boundingBox();await page.mouse.click(ruler.x+35,ruler.y+10);await page.waitForTimeout(200);
    assert.ok(!(await page.locator('#preview-canvas').getAttribute('aria-label')).includes('Texto activo'));
    const boundary=await page.locator('#preview-canvas').evaluate(canvas=>{const c=canvas.getContext('2d');return {top:[...c.getImageData(15,527,1,1).data],bottom:[...c.getImageData(15,529,1,1).data]};});assert.ok(boundary.top[0]<40);assert.ok(boundary.bottom[0]>70);
    await page.mouse.click(ruler.x+350,ruler.y+10);await page.waitForTimeout(100);assert.match(await page.locator('#preview-canvas').getAttribute('aria-label'),/Texto activo: texto de prueba/);
    const transformed=await project();transformed.timeline[1].type='presenter';transformed.timeline[1].source_in=2;transformed.timeline[1].keyframes=[{time:0,x:0,y:-.06,scale:1.15,opacity:1}];assert.equal((await page.request.put(url+'/api/projects/'+transformed.id,{data:transformed})).ok(),true);await page.reload();await page.waitForFunction(()=>document.querySelector('#presenter-video').readyState>=2);const secondRuler=await page.locator('#timeline-ruler').boundingBox();await page.mouse.click(secondRuler.x+350,secondRuler.y+10);await page.waitForTimeout(100);const captionY=Number(await page.locator('#preview-canvas').getAttribute('data-caption-y')),expectedY=480+(960*.65-480)*1.15-.06*960+960*.04;assert.ok(Math.abs(captionY-expectedY)<1,`captionY=${captionY}, expected=${expectedY}`);
    const live=await project();original.revision=live.revision;assert.equal((await page.request.put(url+'/api/projects/'+original.id,{data:original})).ok(),true);await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);
  });
  await step('A concurrent save preserves remote edits and offers local recovery',async()=>{
    const before=await project();await page.locator('#picture-track .timeline-clip').nth(1).click();await page.locator('#scene-title').fill('Cambio local para conflicto');await page.locator('#scene-start').click();
    const external=structuredClone(before);external.transcript.segments=[{start:0,end:1,text:'Edición concurrente de prueba técnica.'}];assert.equal((await page.request.put(url+'/api/projects/'+external.id,{data:external})).ok(),true);
    expectedConflict=true;await page.locator('#save-project').click();await page.locator('#reload-conflict').waitFor();assert.match(await page.locator('#modal-content').innerText(),/Tus cambios siguen/);assert.notEqual((await project()).timeline[1].title,'Cambio local para conflicto');
    await page.locator('#backup-conflict').click();await page.locator('#conflict-backup-link').waitFor();const backupUrl=await page.locator('#conflict-backup-link').getAttribute('href'),backup=await page.request.get(url+backupUrl);assert.equal(backup.ok(),true);assert.equal((await backup.json()).timeline[1].title,'Cambio local para conflicto');
    await page.locator('#reload-conflict').click();await page.waitForFunction(()=>document.querySelector('#modal').open===false);expectedConflict=false;
  });
  await step('Strict validation exposes missing production evidence',async()=>{
    await page.locator('[data-tab="workflow"]').click();await page.locator('#validate-project').click();await page.waitForFunction(()=>document.querySelector('#validation-results').textContent.includes('necesita ajustes'));
    assert.ok((await page.locator('#validation-results').innerText()).includes('YO'));
  });
  await step('Agent workflow creates five dependent roles without approving',async()=>{
    await page.locator('#agent-workflow').click();await page.locator('#modal').waitFor({state:'visible'});assert.ok(await page.locator('#modal-content .job-card').count()>=5);assert.ok(!(await project()).review.approved_preview);await page.locator('#close-modal').click();
  });
  await step('FFmpeg tool extracts real audio without replacing original',async()=>{
    const p=await project(),original=p.source;await page.locator('[data-tab="library"]').click();await page.locator(`[data-view="${p.source}"]`).click();
    await page.locator('#media-tools-panel details summary').click();await page.locator('#media-operation').selectOption('extract_audio');await page.locator('#media-process-form button[type="submit"]').click();
    await page.waitForFunction(()=>document.querySelector('#modal').open===false);await waitUntil(async()=>{const response=await page.request.get(url+'/api/jobs'),data=await response.json(),last=data.jobs.filter(j=>j.action==='media_process').at(-1);if(last?.status==='failed')throw new Error(last.error);return last?.status==='completed';});
    const updated=await project();assert.equal(updated.source,original);assert.ok(updated.assets.some(a=>a.id!==original&&a.probe.streams.some(s=>s.codec_type==='audio')));
  });
  await step('Editable archive is generated with a working download URL',async()=>{
    await page.locator('#export-project').click();await page.locator('#download-editable-link').waitFor();const href=await page.locator('#download-editable-link').getAttribute('href'),response=await page.request.get(url+href);assert.equal(response.ok(),true);const bytes=await response.body();assert.equal(bytes.subarray(0,2).toString(),'PK');await fs.writeFile(path.join(root,'.estado','tmp','browser_editable.zip'),bytes);assert.ok(bytes.length>0);await page.locator('#close-modal').click();
  });
  await step('Editable ZIP reopens its canonical project',async()=>{
    const p=await project();await page.locator('[data-tab="library"]').click();await page.locator('#bundle-input').setInputFiles(path.join(root,'.estado','tmp','browser_editable.zip'));
    await page.waitForFunction(()=>document.querySelector('#job-message').textContent==='Editable abierto');const reopened=await project();assert.equal(reopened.id,p.id);assert.equal(reopened.timeline.length,p.timeline.length);
  });
  await step('Importing the same raw file into an empty draft reopens its canonical project',async()=>{
    const canonical=await project(),all=(await(await page.request.get(url+'/api/projects')).json()).projects,draft=all.find(p=>p.name==='UI · borrador de reutilización técnica');
    if(draft){await page.locator('#project-select').selectOption(draft.id);await page.waitForFunction(()=>document.querySelector('#add-scene').disabled===false&&document.querySelectorAll('#picture-track .timeline-clip').length===0);}
    else{await page.locator('#new-project').click();await page.locator('#project-name').fill('UI · borrador de reutilización técnica');await page.locator('#create-project-form button[type="submit"]').click();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===0&&document.querySelector('#project-select').selectedOptions[0]?.textContent==='UI · borrador de reutilización técnica');}
    await page.locator('#file-input').setInputFiles(input);await page.waitForFunction(()=>document.querySelector('#file-input').value==='');assert.equal(await page.locator('#project-select').inputValue(),canonical.id);await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);const reopened=await project();assert.equal(reopened.revision,canonical.revision);assert.deepEqual(reopened.timeline,canonical.timeline);assert.equal(reopened.source,canonical.source);assert.equal(await page.evaluate(()=>localStorage.getItem('ascendia.project')),canonical.id);
  });
  await step('Manual presents full canonical documents without automatic approval',async()=>{
    await page.locator('[data-tab="style"]').click();await page.locator('#read-manual').click();await page.locator('#modal-title').filter({hasText:'Manual completo'}).waitFor();assert.equal(await page.locator('#modal-content details').count(),4);assert.equal(await page.locator('#record-manual').isDisabled(),true);await page.locator('#close-modal').click();
  });
  await step('Changed displayed manual fingerprints cannot attest a newer unseen version',async()=>{
    const manual=await(await page.request.get(url+'/api/manual')).json(),mock=structuredClone(manual),p=await project();mock.documents[0].sha256='obsolete_test_fingerprint';let served=false,posted=0;
    const getHandler=async route=>{if(!served){served=true;await route.fulfill({json:mock});}else await route.continue();};const postHandler=async route=>{if(route.request().method()==='POST')posted++;await route.continue();};await page.route(url+'/api/manual',getHandler);await page.route(url+'/api/projects/'+p.id+'/manual',postHandler);
    await page.locator('#read-manual').click();await page.locator('#modal-title').filter({hasText:'Manual completo'}).waitFor();await page.locator('#manual-read-check').check();await page.locator('#record-manual').click();await page.waitForFunction(()=>document.querySelector('#manual-read-check').checked===false&&document.querySelector('#record-manual').disabled===true);assert.equal(posted,0);await page.locator('#close-modal').click();await page.unroute(url+'/api/manual',getHandler);await page.unroute(url+'/api/projects/'+p.id+'/manual',postHandler);
  });
  await step('Switching from a rendered project clears the previous movie',async()=>{
    const current=await project(),demo=(await(await page.request.get(url+'/api/projects')).json()).projects.find(p=>p.name.includes('Laboratorio'));assert.ok(demo);await page.locator('#project-select').selectOption(demo.id);await page.waitForFunction(()=>document.querySelector('#preview-render').disabled===false);await page.locator('#preview-render').click();assert.equal(await page.locator('#render-video').isVisible(),true);
    await page.locator('#project-select').selectOption(current.id);await page.waitForFunction(()=>document.querySelector('#preview-timeline').classList.contains('active')&&document.querySelector('#render-video').hidden===true);assert.equal(await page.locator('#render-video').getAttribute('src'),null);
  });
  await step('Desktop and mobile layout render without horizontal overflow',async()=>{
    const p=(await (await page.request.get(url+'/api/projects')).json()).projects.find(p=>p.name.includes('Laboratorio'));
    if(p){await page.locator('#project-select').selectOption(p.id);await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===4);}
    await page.locator('[data-tab="library"]').click();await page.locator('#picture-track .timeline-clip').first().click();await page.waitForTimeout(350);await page.locator('.inspector-panel').evaluate(panel=>panel.scrollTop=0);await page.locator('.tab-view.active').evaluate(panel=>panel.scrollTop=0);await page.locator('#toast-region').evaluate(region=>region.innerHTML='');
    await fs.mkdir(screenshotDir,{recursive:true});await page.screenshot({path:path.join(screenshotDir,'editor.png')});
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(150);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);await page.screenshot({path:path.join(screenshotDir,'editor-mobile.png'),fullPage:true});
  });
  assert.deepEqual(errors,[]);assert.deepEqual(failures,[]);
} finally {
  const report={at:new Date().toISOString(),project_id:testProject?.id,passed:results,page_errors:errors,http_failures:failures,scope:'SOFTWARE only; technical test; no editorial approval'};
  await fs.writeFile(path.join(root,'.estado','browser_report.json'),JSON.stringify(report,null,2));
  await browser.close();
}
