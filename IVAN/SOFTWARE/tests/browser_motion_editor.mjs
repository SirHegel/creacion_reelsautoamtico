import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import crypto from 'node:crypto';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);process.env.TMPDIR='.estado/tmp';process.env.XDG_CACHE_HOME=path.join(root,'.estado/cache');process.env.XDG_CONFIG_HOME=path.join(root,'.estado/config');
for(const folder of ['.estado/tmp','.estado/browser-motion','.estado/cache','.estado/config','.estado/validacion'])await fs.mkdir(path.join(root,folder),{recursive:true});
const require=createRequire(import.meta.url),{chromium}=require(path.join(root,'..','.estado/herramientas/node_modules/playwright'));
const url=process.env.STUDIO_URL||'http://127.0.0.1:8765';
const fixture=path.join(root,'.estado/tmp/ui_free_motion_source.mp4'),image=path.join(root,'.estado/tmp/ui_free_motion_alpha.png');
try{await fs.access(fixture);}catch{execFileSync('nice',['-n','10','ffmpeg','-nostdin','-v','error','-f','lavfi','-i','color=c=0x193647:size=360x640:rate=30:duration=10','-f','lavfi','-i','sine=frequency=631:sample_rate=48000:duration=10','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest','-y',fixture],{cwd:root,env:process.env});}
try{await fs.access(image);}catch{execFileSync('python3',['-B','-c','from PIL import Image,ImageDraw;import sys;im=Image.new("RGBA",(240,160),(0,0,0,0));d=ImageDraw.Draw(im);d.rounded_rectangle((12,12,228,148),radius=18,fill=(48,73,106,255));d.ellipse((68,28,172,132),fill=(201,222,249,255));im.save(sys.argv[1])',image],{cwd:root,env:process.env});}
const results=[],errors=[],httpFailures=[],fixtureIds={projects:[],assets:[],files:[fixture,image]};
const browser=await chromium.launchPersistentContext(path.join(root,'.estado/browser-motion'),{executablePath:'/usr/bin/google-chrome',headless:true,viewport:{width:1440,height:1020},args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],env:{...process.env,TMPDIR:'.estado/tmp'}});
const page=browser.pages()[0]||await browser.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))httpFailures.push({url:r.url(),status:r.status()});});
let testId,sourceId,imageId,shapeId,labBefore,renderJob;
const labId='p_b82375e1c80d4dab';
const json=async endpoint=>{const response=await page.request.get(url+endpoint);assert.ok(response.ok(),await response.text());return response.json();};
const project=()=>json('/api/projects/'+testId);
async function until(fn,timeout=45000){const deadline=Date.now()+timeout;while(Date.now()<deadline){if(await fn())return;await page.waitForTimeout(150);}throw new Error('Timed out waiting for actual editor state.');}
async function step(name,fn){await fn();results.push({name,passed:true});console.log('PASS '+name);}
async function change(selector,value){const node=page.locator(selector);await node.fill(String(value));await node.dispatchEvent('change');}
async function save(){const pending=page.waitForResponse(r=>r.request().method()==='PUT'&&r.url()===url+'/api/projects/'+testId);await page.locator('#save-project').click();const response=await pending;assert.equal(response.status(),200,await response.text());await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));return project();}
async function scrub(t){const ruler=await page.locator('#timeline-ruler').boundingBox(),zoom=Number(await page.locator('#timeline-zoom').inputValue());await page.mouse.click(ruler.x+t*zoom,ruler.y+10);await page.waitForTimeout(75);}
async function pose(){return page.locator('#preview-canvas').evaluate(c=>JSON.parse(c.dataset.motionPose));}
async function selectElement(id){await page.locator(`[data-motion-select="${id}"]`).click();}
const editorial=p=>({source:p.source,revision:p.revision,timeline:p.timeline,assets:p.assets.map(a=>Object.fromEntries(Object.entries(a).filter(([key])=>!key.startsWith('preview_')))),review:p.review,reference_review:p.reference_review});
const sha=p=>crypto.createHash('sha256').update(JSON.stringify(p)).digest('hex');
try{
  await step('Launch with real local fonts and preserve existing laboratory',async()=>{labBefore=editorial(await json('/api/projects/'+labId));await page.goto(url);await page.waitForFunction(()=>document.querySelector('#connection-label').textContent==='Motor local');await until(()=>page.evaluate(()=>document.fonts.check('36px Sequel')&&document.fonts.check('italic 36px Scholar')));});
  await step('Create isolated canonical project and import unique synthetic media',async()=>{
    const projects=(await json('/api/projects')).projects,existing=projects.find(p=>p.name==='UI · motion libre y GSAP');
    if(existing){testId=existing.id;const p=await project();assert.equal(Boolean(p.review?.approved_preview),false);p.timeline=[];p.audio=[];p.transcript={words:[],segments:[]};p.review={};const response=await page.request.put(url+'/api/projects/'+testId,{data:p});assert.ok(response.ok(),await response.text());await page.locator('#project-select').selectOption(testId);}
    else{await page.locator('#new-project').click();await page.locator('#project-name').fill('UI · motion libre y GSAP');const created=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===url+'/api/projects');await page.locator('#create-project-form button').click();testId=(await(await created).json()).id;await until(async()=>(await page.locator('#project-select').inputValue())===testId);}
    assert.notEqual(testId,labId);fixtureIds.projects.push(testId);await page.locator('#file-input').setInputFiles(fixture);await page.waitForFunction(()=>document.querySelector('#file-input').value==='');await until(async()=>Boolean((await project()).source));sourceId=(await project()).source;
    await page.locator('#file-input').setInputFiles(image);await page.waitForFunction(()=>document.querySelector('#file-input').value==='');await until(async()=>{const a=(await project()).assets.find(a=>a.name==='ui_free_motion_alpha.png');if(a)imageId=a.id;return Boolean(a);});fixtureIds.assets.push(sourceId,imageId);
    assert.notEqual(sourceId,labBefore.source);
  });
  await step('Free composition has canonical schema and defaults to HyperFrames',async()=>{
    await page.locator('[data-tab="motion"]').click();await page.locator('#create-free-motion').click();await change('#scene-end',10);
    await change('[data-motion-field="text"]','Editor de motion libre');await change('[data-motion-field="y"]',.12);await change('[data-motion-field="height"]',.14);await change('[data-motion-field="font_size"]',92);
    const p=await save();assert.equal(p.timeline[0].type,'motion');assert.equal(p.timeline[0].template,'custom');assert.equal(p.settings.engine,'hyperframes');assert.equal(p.timeline[0].motion_design.elements.length,1);assert.equal(Boolean(p.review?.approved_preview),false);
  });
  await step('Canvas drag, resize, keyboard nudges and history edit actual geometry',async()=>{
    await page.locator('#motion-add-shape').click();await change('[data-motion-field="width"]',.36);await change('[data-motion-field="height"]',.18);await change('[data-motion-field="end"]',6);shapeId=await page.locator('#motion-elements-list .selected').getAttribute('data-motion-select');
    let bounds=await page.locator('#preview-canvas').boundingBox(),p=await pose(),startX=bounds.x+(p.x+.18)*bounds.width,startY=bounds.y+(p.y+.09)*bounds.height;
    await page.mouse.move(startX,startY);await page.mouse.down();await page.mouse.move(startX+bounds.width*.05,startY+bounds.height*.03,{steps:6});await page.mouse.up();assert.ok(Math.abs((await pose()).x-.25)<.006);assert.ok(Math.abs((await pose()).y-.43)<.006);
    const beforeWidth=Number(await page.locator('[data-motion-field="width"]').inputValue()),beforeHeight=Number(await page.locator('[data-motion-field="height"]').inputValue());p=await pose();bounds=await page.locator('#preview-canvas').boundingBox();const x=bounds.x+(p.x+beforeWidth)*bounds.width,y=bounds.y+(p.y+beforeHeight)*bounds.height;
    await page.mouse.move(x,y);await page.mouse.down();await page.mouse.move(x+bounds.width*.025,y+bounds.height*.015,{steps:5});await page.mouse.up();assert.ok(Number(await page.locator('[data-motion-field="width"]').inputValue())>beforeWidth+.025);
    const xBefore=(await pose()).x;await page.locator('#preview-canvas').focus();await page.keyboard.press('Shift+ArrowRight');assert.ok(Math.abs((await pose()).x-xBefore-10/1080)<1e-6);
    await page.locator('#undo').click();assert.ok(Math.abs((await pose()).x-xBefore)<1e-6);await page.locator('#redo').click();assert.ok(Math.abs((await pose()).x-xBefore-10/1080)<1e-6);
    await page.locator('#preview-canvas').focus();await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('#preview-canvas').dataset.motionElement);await selectElement(shapeId);
  });
  await step('Editable keyframe timing, easing and animated masks derive from seek time',async()=>{
    await scrub(0);await page.locator('#motion-add-key').click();await scrub(1.2);await page.locator('#motion-add-key').click();
    await change('[data-motion-key="1"] [data-motion-key-field="rotation"]',90);const withoutMask=await save();assert.ok(withoutMask.timeline[0].motion_design.elements.find(e=>e.id===shapeId).keyframes.every(k=>k.mask_progress===undefined));await page.locator('[data-motion-key="1"] [data-motion-key-field="ease"]').selectOption('power2.inOut');
    await page.locator('.motion-mask-details summary').click();await page.locator('#motion-mask-type').selectOption('inset');await change('[data-motion-key="1"] [data-motion-key-field="mask_progress"]',.2);await change('[data-motion-mask="left"]',.08);await change('[data-motion-mask="right"]',.1);
    await scrub(.6);let p=await pose();assert.ok(Math.abs(p.rotation-45)<1e-6);assert.ok(Math.abs(p.mask_progress-.6)<1e-6);assert.equal(await page.locator('svg.motion-curve').count(),2);
  });
  await step('Polyline path has editable points and aspect-aware constant speed',async()=>{
    await page.locator('.motion-path-details summary').click();await page.locator('#motion-path-enabled').check();
    await change('[data-motion-point="0"] [data-motion-point-field="x"]',.1);await change('[data-motion-point="0"] [data-motion-point-field="y"]',.35);await change('[data-motion-point="1"] [data-motion-point-field="x"]',.7);await change('[data-motion-point="1"] [data-motion-point-field="y"]',.35);await page.locator('#motion-add-point').click();await change('[data-motion-point="2"] [data-motion-point-field="x"]',.7);await change('[data-motion-point="2"] [data-motion-point-field="y"]',.75);
    await scrub(3);const p=await pose(),d1=.6*1080,d2=.4*1920,remaining=(d1+d2)/2-d1;assert.ok(Math.abs(p.x-.7)<1e-6);assert.ok(Math.abs(p.y-(.35+remaining/1920))<1e-6);
  });
  await step('Media element uses chosen canonical PNG and contains no raw-source copies',async()=>{
    await page.locator('#motion-add-media').click();assert.equal(await page.locator(`[data-motion-media="${sourceId}"]`).count(),0);await page.locator(`[data-motion-media="${imageId}"]`).click();await change('[data-motion-field="y"]',.77);await change('[data-motion-field="height"]',.14);await change('[data-motion-field="width"]',.65);
    assert.equal(await page.locator(`[data-motion-field="asset_id"] option[value="${sourceId}"]`).count(),0);const p=await save();assert.equal(p.timeline[0].motion_design.elements.find(e=>e.type==='media').asset_id,imageId);assert.equal(await page.locator('#motion-text-track [data-motion-element]').count(),1);assert.equal(await page.locator('#motion-shape-track [data-motion-element]').count(),1);assert.equal(await page.locator('#motion-media-track [data-motion-element]').count(),1);
    await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===1);await page.locator('#picture-track .timeline-clip').click();await selectElement(shapeId);assert.equal(await page.locator('#motion-mask-type').inputValue(),'inset');assert.equal(await page.locator('[data-motion-point]').count(),3);
  });
  await step('Split preserves nonlinear easing windows, path velocity, masks and base geometry',async()=>{
    const samples=[];for(const t of [.3,.8,1.1,2,4.2]){await scrub(t);samples.push({t,pose:await pose()});}
    const original=await project();await scrub(.65);await page.locator('#split-scene').click();assert.equal(await page.locator('#picture-track .timeline-clip').count(),2);await save();const split=await project();assert.ok(split.timeline[1].motion_design.elements.find(e=>e.id===shapeId).keyframes.some(k=>k.ease_window));
    for(const sample of samples){await page.locator('#picture-track .timeline-clip').nth(sample.t<.65?0:1).click();await selectElement(shapeId);await scrub(sample.t);const actual=await pose();for(const key of ['x','y','scale','opacity','rotation','mask_progress'])assert.ok(Math.abs(actual[key]-sample.pose[key])<1e-5,`${key} changed across split at ${sample.t}: ${actual[key]} vs ${sample.pose[key]}`);}
    for(const scene of split.timeline){const e=scene.motion_design.elements.find(e=>e.id===shapeId),before=original.timeline[0].motion_design.elements.find(e=>e.id===shapeId);assert.equal(e.x,before.x);assert.equal(e.y,before.y);assert.equal(e.width,before.width);assert.equal(e.height,before.height);}
  });
  await step('Trim preserves a partial nonlinear segment and canonical save/reload',async()=>{
    await page.locator('#picture-track .timeline-clip').nth(1).click();await selectElement(shapeId);await scrub(1.05);const before=await pose();await change('#scene-start',.9);await scrub(1.05);const after=await pose();for(const key of ['x','y','rotation','mask_progress'])assert.ok(Math.abs(before[key]-after[key])<1e-5,`${key} changed across trim`);await save();await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);assert.equal((await project()).timeline[1].start,.9);
  });
  await step('Manual reading and settings use genuine controls without editorial approval',async()=>{
    await page.locator('#picture-track .timeline-clip').nth(1).click();await change('#scene-start',.65);assert.equal((await save()).timeline[1].start,.65);
    await page.locator('[data-tab="style"]').click();await page.locator('#read-manual').click();await page.waitForFunction(()=>document.querySelectorAll('#modal-content .code-view').length===4);assert.equal(await page.locator('#modal-content .code-view').count(),4);await page.locator('#manual-read-check').check();await page.locator('#record-manual').click();await page.waitForFunction(()=>!document.querySelector('#modal').open);
    await page.locator('#open-settings').click();await page.locator('#setting-resolution').selectOption('360');await page.locator('#setting-engine').selectOption('hyperframes');await page.locator('#settings-form button[type="submit"]').click();const p=await save();assert.equal(p.settings.width,360);assert.equal(p.settings.engine,'hyperframes');assert.equal(Boolean(p.review?.approved_preview),false);assert.equal(p.approval_current,false);
  });
  if(process.env.NO_RENDER!=='1')await step('Real technical HyperFrames export completes and actual MP4 decodes',async()=>{
    await page.locator('#render-project').click();assert.equal(await page.locator('#render-kind').inputValue(),'technical');assert.equal(await page.locator('#render-engine').inputValue(),'hyperframes');const responsePromise=page.waitForResponse(r=>r.request().method()==='POST'&&r.url()===url+'/api/projects/'+testId+'/render',{timeout:30000});responsePromise.catch(()=>{});await page.locator('#start-render').click();const response=await responsePromise;assert.equal(response.status(),202,await response.text());renderJob=await response.json();await until(async()=>['completed','failed','blocked'].includes((await json('/api/jobs/'+renderJob.id)).status),240000);const finished=await json('/api/jobs/'+renderJob.id);assert.equal(finished.status,'completed',JSON.stringify(finished));
    const p=await project(),receipt=p.renders.at(-1);assert.equal(receipt.mode,'technical_library');assert.equal(receipt.production_conformant,false);assert.equal(Boolean(p.review?.approved_preview),false);assert.equal(p.approval_current,false);assert.ok(JSON.stringify(receipt).includes('hyperframes'));const output=path.resolve(root,receipt.path);assert.ok(output.startsWith(root+path.sep));execFileSync('nice',['-n','10','ffmpeg','-nostdin','-v','error','-threads','1','-i',output,'-f','null','-'],{cwd:root,env:process.env});fixtureIds.files.push(output);
    await until(()=>page.locator('#preview-render').isEnabled());await page.locator('#preview-render').click();await page.waitForFunction(()=>document.querySelector('#render-video').readyState>=2);const metadata=await page.locator('#render-video').evaluate(v=>({width:v.videoWidth,height:v.videoHeight,duration:v.duration}));assert.equal(metadata.width,360);assert.equal(metadata.height,640);assert.ok(metadata.duration>5.9&&metadata.duration<=10.05);await page.locator('#render-video').evaluate(v=>v.play());await page.waitForTimeout(600);const playback=await page.locator('#render-video').evaluate(v=>{v.pause();return v.currentTime;});assert.ok(playback>.2);results.at(-1)?.name;fixtureIds.render={job:renderJob.id,path:receipt.path,sha256:receipt.sha256,metadata,playback};
  });
  await step('Desktop/mobile free canvas is responsive and final Lab content is untouched',async()=>{
    await page.locator('#preview-timeline').click();await page.locator('#picture-track .timeline-clip').nth(1).click();await selectElement(shapeId);await scrub(2);await page.locator('[data-tab="motion"]').click();await page.screenshot({path:path.join(root,'docs/motion-editor.png')});
    await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.ok(await page.locator('#create-free-motion').isEnabled());await page.screenshot({path:path.join(root,'docs/motion-editor-mobile.png'),fullPage:true});assert.equal(sha(editorial(await json('/api/projects/'+labId))),sha(labBefore));assert.deepEqual(errors,[]);assert.deepEqual(httpFailures,[]);
  });
}catch(error){results.push({name:'Failure',passed:false,error:error.stack});console.error(error);await page.screenshot({path:path.join(root,'.estado/validacion/motion-editor-failure.png'),fullPage:true}).catch(()=>{});process.exitCode=1;}
finally{
  await fs.writeFile(path.join(root,'.estado/validacion/browser_motion_editor.json'),JSON.stringify({at:new Date().toISOString(),passed:results.filter(r=>r.passed).length,failed:results.filter(r=>!r.passed).length,results,errors,httpFailures,fixtures:fixtureIds,lab_untouched:labBefore&&sha(editorial(await json('/api/projects/'+labId)))===sha(labBefore),device:'cpu',gpu:false,editorial_approval:false,code_sha256:crypto.createHash('sha256').update(await fs.readFile(path.join(root,'web/app.js'))).digest('hex')},null,2));await browser.close();
}
