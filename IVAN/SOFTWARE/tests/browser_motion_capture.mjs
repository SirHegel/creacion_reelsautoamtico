import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import crypto from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');process.chdir(root);process.env.TMPDIR='.estado/tmp';
const require=createRequire(import.meta.url),{chromium}=require(path.join(root,'../.estado/herramientas/node_modules/playwright'));
const url='http://127.0.0.1:8765',id='p_13aa3f878757456e',lab='p_b82375e1c80d4dab',errors=[],mutations=[];
const context=await chromium.launchPersistentContext(path.join(root,'.estado/browser-motion-capture'),{executablePath:'/usr/bin/google-chrome',headless:true,viewport:{width:1440,height:1020},args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],env:{...process.env,TMPDIR:'.estado/tmp',XDG_CACHE_HOME:path.join(root,'.estado/cache'),XDG_CONFIG_HOME:path.join(root,'.estado/config')}});
const page=context.pages()[0]||await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(['POST','PUT','PATCH','DELETE'].includes(r.method()))mutations.push(r.url());});
const get=async endpoint=>{const response=await page.request.get(url+endpoint);assert.ok(response.ok());return response.json();};
const content=p=>JSON.stringify({source:p.source,timeline:p.timeline,assets:p.assets,review:p.review,reference_review:p.reference_review,revision:p.revision});const sha=v=>crypto.createHash('sha256').update(v).digest('hex');let report;
try{
 const labCurrent=await get('/api/projects/'+lab),rawLab=JSON.parse(await fs.readFile(path.join(root,'projects',lab,'project.json'),'utf8'));
 const changes=[];const reconstructed=structuredClone(labCurrent);
 for(const asset of reconstructed.assets){const raw=rawLab.assets.find(a=>a.id===asset.id);for(const key of Object.keys(asset))if(key.startsWith('preview_')&&!(key in raw)){changes.push({asset_id:asset.id,field:key});delete asset[key];}}
 // This exact checkpoint was captured before import_bundle hydrated the shared b-roll preview.
 assert.equal(sha(content(reconstructed)),'213bd0705758ae2f9fec3b14c16e8805b66556e8675eaebba147c5e815d75be1');
 assert.deepEqual(changes.map(c=>c.asset_id),Array(changes.length).fill('a_77cbab0f1020de5d8f6b'));assert.equal(labCurrent.revision,10);assert.equal(labCurrent.timeline.length,4);
 const before=await get('/api/projects/'+id);await page.goto(url);await page.waitForFunction(()=>document.querySelector('#connection-label').textContent==='Motor local');await page.locator('#project-select').selectOption(id);await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);await page.waitForFunction(()=>document.fonts.check('36px Sequel')&&document.fonts.check('italic 36px Scholar'));
 await page.locator('#preview-timeline').click();await page.locator('#picture-track .timeline-clip').nth(1).click();const shape=before.timeline[1].motion_design.elements.find(e=>e.type==='shape');await page.locator(`[data-motion-select="${shape.id}"]`).click();const ruler=await page.locator('#timeline-ruler').boundingBox(),zoom=Number(await page.locator('#timeline-zoom').inputValue());await page.mouse.click(ruler.x+2*zoom,ruler.y+10);await page.locator('[data-tab="motion"]').click();await page.waitForTimeout(300);await page.screenshot({path:path.join(root,'docs/motion-editor.png')});await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(root,'docs/motion-editor-mobile.png'),fullPage:true});assert.equal(content(await get('/api/projects/'+id)),content(before));assert.equal(content(await get('/api/projects/'+lab)),content(labCurrent));assert.deepEqual(mutations,[]);assert.deepEqual(errors,[]);
 report={passed:1,failed:0,at:new Date().toISOString(),read_only:true,mutations,errors,lab_editorial_unchanged:true,lab_revision:10,preview_only_hydration:changes,previous_full_hash:'213bd0705758ae2f9fec3b14c16e8805b66556e8675eaebba147c5e815d75be1',reconstructed_previous_hash:sha(content(reconstructed)),gpu:false,captures:['docs/motion-editor.png','docs/motion-editor-mobile.png'],code_sha256:sha(await fs.readFile(path.join(root,'web/app.js')))};console.log('PASS clean desktop/mobile, zero mutations, exact original Lab content except preview hydration');
}catch(error){report={passed:0,failed:1,error:error.stack,errors,mutations};console.error(error);process.exitCode=1;}
finally{await fs.writeFile(path.join(root,'.estado/validacion/browser_motion_capture.json'),JSON.stringify(report,null,2));await context.close();}
