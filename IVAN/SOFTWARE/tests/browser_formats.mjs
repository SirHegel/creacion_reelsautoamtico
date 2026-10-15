import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);process.env.TMPDIR='.estado/tmp';process.env.XDG_CACHE_HOME=path.join(root,'.estado','cache');process.env.XDG_CONFIG_HOME=path.join(root,'.estado','config');
const {chromium}=createRequire(import.meta.url)(path.join(root,'..','.estado','herramientas','node_modules','playwright'));
const url=process.env.STUDIO_URL||'http://127.0.0.1:8765';
const files={mov:path.join(root,'.estado/tmp/ui_alpha_movie.mov'),tiff:path.join(root,'.estado/tmp/ui_alpha_image.tiff')};
const png=path.join(root,'.estado/tmp/ui_alpha_overlay.png');
for(const folder of ['.estado/tmp','.estado/browser','.estado/cache','.estado/config'])await fs.mkdir(path.join(root,folder),{recursive:true});
try{await fs.access(files.mov);}catch(_){execFileSync('ffmpeg',['-nostdin','-v','error','-loop','1','-i',png,'-t','2','-r','30','-c:v','qtrle','-pix_fmt','argb','-threads','1','-y',files.mov],{cwd:root});}
execFileSync('python3',['-B','-c','from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2])',png,files.tiff],{cwd:root});
const report={results:[],assets:[],page_errors:[],http_failures:[]};
const browser=await chromium.launchPersistentContext(path.join(root,'.estado/browser'),{executablePath:process.env.STUDIO_BROWSER||'/usr/bin/google-chrome',headless:true,viewport:{width:1440,height:960},args:['--disable-gpu','--disable-breakpad','--disable-crash-reporter','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-extensions','--disable-dev-shm-usage','--no-sandbox'],env:{...process.env,TMPDIR:'.estado/tmp'}});
const page=browser.pages()[0]||await browser.newPage();
page.on('pageerror',e=>report.page_errors.push(e.message));
page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))report.http_failures.push({url:r.url(),status:r.status()});});
let projectId;
async function waitUntil(fn,timeout=90000){const end=Date.now()+timeout;while(Date.now()<end){if(await fn())return;await page.waitForTimeout(250);}throw new Error('Timeout waiting for actual media readiness.');}
async function project(){return(await page.request.get(url+'/api/projects/'+projectId)).json();}
async function step(name,fn){await fn();report.results.push(name);console.log('PASS '+name);}
async function pixels(){return page.locator('#preview-canvas').evaluate(canvas=>{const c=canvas.getContext('2d');return{white:[...c.getImageData(160,380,1,1).data],clear:[...c.getImageData(82,304,1,1).data]};});}
async function selectLayer(id){await page.locator('#picture-track .timeline-clip').nth(1).click();await page.locator('#overlay-section').evaluate(el=>el.open=true);await page.locator('[data-layer-field="asset_id"]').selectOption(id);await page.waitForTimeout(100);}
async function save(){await page.locator('#save-project').click();await page.waitForFunction(()=>document.querySelector('#save-state').textContent.includes('Guardado'));}
try{
  await page.goto(url);await page.locator('#connection-label').filter({hasText:'Motor local'}).waitFor();
  const list=(await(await page.request.get(url+'/api/projects')).json()).projects,fixture=list.find(p=>p.name==='UI · prueba técnica automatizada');assert.ok(fixture,'Run browser_editor.mjs first.');projectId=fixture.id;
  await page.locator('#project-select').selectOption(projectId);await page.waitForFunction(()=>document.querySelectorAll('#picture-track .timeline-clip').length===2);await page.locator('#picture-track .timeline-clip').nth(1).click();await page.waitForTimeout(300);
  const initial=await project(),source=initial.source,pngAsset=initial.assets.find(a=>a.name==='ui_alpha_overlay.png');assert.ok(pngAsset);await selectLayer(pngAsset.id);const baseline=await pixels();assert.ok(baseline.white[0]>230);assert.ok(baseline.clear[0]<100);
  await step('Chrome decodes MOV qtrle through an alpha-preserving WebM proxy',async()=>{
    await page.locator('#file-input').setInputFiles(files.mov);await waitUntil(async()=>(await project()).assets.some(a=>a.name==='ui_alpha_movie.mov'));await page.locator('#scene-asset option').filter({hasText:'ui_alpha_movie.mov'}).waitFor({state:'attached'});
    const p=await project(),asset=p.assets.find(a=>a.name==='ui_alpha_movie.mov');assert.equal(p.source,source);assert.equal(asset.sha256,createHash('sha256').update(await fs.readFile(files.mov)).digest('hex'));assert.match(asset.path,/\.mov$/);assert.equal(asset.probe.streams.find(s=>s.codec_type==='video').codec_name,'qtrle');assert.ok(asset.preview_is_derivative);assert.ok(asset.preview_preserves_alpha);assert.match(asset.preview_url,/\.webm$/);
    await selectLayer(asset.id);await waitUntil(()=>page.locator(`video[data-asset="${asset.id}"]`).evaluate(v=>v.readyState>=2));await page.waitForTimeout(200);const actual=await pixels();assert.ok(actual.white[0]>230,JSON.stringify(actual));assert.ok(Math.abs(actual.clear[0]-baseline.clear[0])<=3,JSON.stringify({baseline,actual}));
    const src=await page.locator(`video[data-asset="${asset.id}"]`).getAttribute('src');assert.equal(src,asset.preview_url);assert.equal((await project()).source,source);await save();report.assets.push({id:asset.id,name:asset.name,path:asset.path,preview_path:asset.preview_path,pixels:actual});
  });
  await step('TIFF uses a real PNG proxy with transparent pixels and unchanged original',async()=>{
    await page.locator('#file-input').setInputFiles(files.tiff);await waitUntil(async()=>(await project()).assets.some(a=>a.name==='ui_alpha_image.tiff'));await page.locator('#scene-asset option').filter({hasText:'ui_alpha_image.tiff'}).waitFor({state:'attached'});
    const p=await project(),asset=p.assets.find(a=>a.name==='ui_alpha_image.tiff');assert.equal(p.source,source);assert.equal(asset.sha256,createHash('sha256').update(await fs.readFile(files.tiff)).digest('hex'));assert.match(asset.path,/\.tiff$/);assert.equal(asset.kind,'image');assert.ok(asset.preview_is_derivative);assert.match(asset.preview_url,/\.png$/);await selectLayer(asset.id);await waitUntil(async()=>{const actual=await pixels();return actual.white[0]>230&&Math.abs(actual.clear[0]-baseline.clear[0])<=3;});const actual=await pixels();await save();report.assets.push({id:asset.id,name:asset.name,path:asset.path,preview_path:asset.preview_path,pixels:actual});
  });
  await step('Proxy playback reaches another frame while the canonical source stays unchanged',async()=>{
    const asset=report.assets[0];await selectLayer(asset.id);const ruler=await page.locator('#timeline-ruler').boundingBox();await page.mouse.click(ruler.x+1.65*70,ruler.y+10);await waitUntil(()=>page.locator(`video[data-asset="${asset.id}"]`).evaluate(v=>v.readyState>=2&&Math.abs(v.currentTime-.45)<.1));assert.equal((await project()).source,source);const actual=await pixels();assert.ok(actual.white[0]>230);assert.ok(actual.clear[0]<100);await selectLayer(pngAsset.id);await save();
  });
  assert.deepEqual(report.page_errors,[]);assert.deepEqual(report.http_failures,[]);report.project_id=projectId;
}catch(error){report.error=error.stack;throw error;}finally{await fs.writeFile(path.join(root,'.estado/browser_formats_report.json'),JSON.stringify(report,null,2));await browser.close();}
