/* Navegador real: estabilidad de seek, textos/targets y estados de cada preview.
   No confundir este control funcional con la comparación visual a CLONE. */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {chromium} from '../../.estado/herramientas/node_modules/playwright/index.mjs';
const ROOT=process.cwd();
if(path.basename(ROOT)!=='IVAN')throw Error('Ejecutar dentro de IVAN');
// Alias corto al mismo directorio IVAN: sockets Unix de Chrome tienen límite.
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp`;
process.env.XDG_CACHE_HOME=path.join(ROOT,'.estado/cache');
process.env.XDG_CONFIG_HOME=path.join(ROOT,'.estado/config');
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.mp4':'video/mp4'};
const server=http.createServer((req,res)=>{
 const file=path.resolve(ROOT,'.'+new URL(req.url,'http://local').pathname);
 if(!file.startsWith(ROOT+'/')||!fs.existsSync(file)||!mime[path.extname(file)])return res.writeHead(404).end();
 res.writeHead(200,{'Content-Type':mime[path.extname(file)]});fs.createReadStream(file).pipe(res);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,
 args:['--no-sandbox','--disable-dev-shm-usage','--disable-crash-reporter','--disable-breakpad','--disable-gpu','--force-color-profile=srgb']});
const input=process.argv.slice(2),folders=input.length?input:fs.readdirSync('proyectos/clone_motor/previews').map(x=>'proyectos/clone_motor/previews/'+x);
const results=[];
try{
 for(const folder of folders){
  if(!path.resolve(folder).startsWith(ROOT+'/'))throw Error('Fuera de IVAN');
  if(!fs.existsSync(folder+'/index.html'))continue;
  const page=await browser.newPage({viewport:{width:720,height:1280}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
   const spec=JSON.parse(fs.readFileSync(folder+'/scene.json','utf8'));
   const modular=spec.scenes.length>1;
   if(modular)await page.setViewportSize({width:1080,height:1920});
   const response=await page.goto(`http://127.0.0.1:${server.address().port}/${folder}/index.html`,{waitUntil:'domcontentloaded',timeout:20000});
   if(modular){
    // Mismo loader/transport0.8.147 instalado que utiliza el render. No montar
    // templates ni anidar timelines a mano en el diagnóstico del compilador.
    await page.addScriptTag({url:`http://127.0.0.1:${server.address().port}/.estado/herramientas/node_modules/hyperframes/dist/hyperframe-runtime.js`});
    await page.waitForFunction(()=>window.__renderReady===true&&window.__playerReady===true,null,{timeout:30000});
   }
   await page.waitForFunction(()=>window.renderReady===true,null,{timeout:20000});
   const metadata=await page.evaluate(()=>({instances:window.__cloneInstances,gsap:gsap.version,
    ids:[...document.querySelectorAll('[id]')].map(n=>n.id),images:[...document.querySelectorAll('svg image')].map(n=>n.getAttribute('href')),
    clocks:{intervals:0,raf:0},timelineDurations:Object.fromEntries(Object.entries(window.__timelines).map(([id,tl])=>[id,tl.duration()]))}));
   const hash=b=>createHash('sha256').update(b).digest('hex');
   let lastBuffer;
   const seek=async t=>{await page.evaluate(({t,modular})=>{
     if(modular)window.__player.renderSeek(t,{suppressEvents:false});
     else window.__timelines['clone-main'].seek(t,false);
    },{t,modular});
    await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(()=>r()))));
    lastBuffer=await page.screenshot({timeout:15000});return hash(lastBuffer);};
   let times=[.03,.25,.52,.79,.97].map(f=>Math.max(0,Math.min(spec.duration-1/30,spec.duration*f)));
   if(modular){
    const boundaries=spec.scenes.slice(1).flatMap(s=>[...new Set([-2,-1,0,1,2,9,Math.round((s.transition_in?.duration||0)*15),Math.round((s.transition_in?.duration||0)*30)])].map(f=>s.start+f/30));
    times=[...new Set([...times,...boundaries].map(t=>Math.round(Math.max(0,Math.min(spec.duration-1/30,t))*30)/30))].sort((a,b)=>a-b);
   }
   const snapshot=()=>page.evaluate(()=>[...document.querySelectorAll('svg [id]')].map(n=>({id:n.id,text:n.tagName==='text'?n.textContent:null,transform:n.getAttribute('transform'),style:n.getAttribute('style'),fill:n.getAttribute('fill')})));
   const before=[],beforeDOM=[],beforeBuffers=[];for(const t of times){before.push(await seek(t));beforeBuffers.push(lastBuffer);beforeDOM.push(await snapshot());}
   const after=[],afterDOM=[],afterBuffers=[];for(const t of [...times].reverse()){after.push(await seek(t));afterBuffers.push(lastBuffer);afterDOM.push(await snapshot());}
   const seekExact=before.every((x,i)=>x===after[after.length-1-i]);let raster=[];
   if(!seekExact){const dir='.estado/tmp/clone_seek/'+path.basename(folder);fs.mkdirSync(dir,{recursive:true});
    for(const old of fs.readdirSync(dir))if(/^(before|after)_\d+\.png$/.test(old))fs.unlinkSync(dir+'/'+old);
    before.forEach((b,i)=>{if(b!==after[after.length-1-i]){fs.writeFileSync(dir+'/before_'+i+'.png',beforeBuffers[i]);fs.writeFileSync(dir+'/after_'+i+'.png',afterBuffers[after.length-1-i]);}});
    raster=JSON.parse(execFileSync('python3',['-B','-c',`import pathlib,numpy as np,json,sys
from PIL import Image
out=[]
for p in pathlib.Path(sys.argv[1]).glob('before_*.png'):
 a=np.asarray(Image.open(p).convert('RGB'),dtype=np.int16);b=np.asarray(Image.open(p.with_name(p.name.replace('before','after'))).convert('RGB'),dtype=np.int16);e=np.abs(a-b)
 out.append({'pair':p.name,'mad':float(e.mean()),'max':int(e.max()),'changed_fraction':float((e.max(2)>0).mean()),'above8_fraction':float((e.max(2)>8).mean())})
print(json.dumps(out))`,dir],{encoding:'utf8'}));
   }
   // Umbral de antialias estricto: <0.001/255 de MAD y <0.005% de píxeles
   // con diferencia>8. Un salto de geometría/texto nunca pasa este control.
   const seekOK=seekExact||raster.every(r=>r.mad<.001&&r.above8_fraction<.00005&&r.max<=32);
   const states=[];
   for(const t of times){await seek(t);states.push(await page.evaluate(({t,modular})=>({t,texts:[...document.querySelectorAll('svg text')].filter(n=>getComputedStyle(n).opacity!=='0').map(n=>({id:n.id,text:n.textContent,size:parseFloat(getComputedStyle(n).fontSize)})),visible:[...document.querySelectorAll(modular?'[data-composition-src]':'.scene-host')].filter(n=>getComputedStyle(n).visibility==='visible').map(n=>n.id),
     clocks:modular?Object.fromEntries(Object.entries(window.__timelines).map(([id,tl])=>[id,{time:tl.time(),paused:tl.paused()}])):undefined,
     wrappers:modular?Object.fromEntries([...document.querySelectorAll('[id^="__clone-surface-"]')].map(n=>[n.id.replace('__clone-surface-',''),{clip:getComputedStyle(n).clipPath,transform:getComputedStyle(n).transform}])):undefined}),{t,modular}));}
   const clockOK=!modular||states.every(s=>spec.scenes.every(scene=>{
    const clock=s.clocks[scene.id],expected=Math.max(0,Math.min(metadata.timelineDurations[scene.id],s.t-scene.start));
    return clock?.paused===true&&Math.abs(clock.time-expected)<.00001;
   }));
   const coverageOK=!modular||states.every(s=>s.visible.length>0);
   const transitionChecks=modular?spec.scenes.slice(1).filter(s=>s.transition_in.kind!=='cut'&&s.transition_in.duration>0).map(scene=>{
    const at=offset=>states.find(s=>Math.abs(s.t-(scene.start+offset))<.00001)?.wrappers[scene.id];
    const initial=at(0),middle=at(Math.round(scene.transition_in.duration*15)/30),end=at(Math.round(scene.transition_in.duration*30)/30);
    return {id:scene.id,kind:scene.transition_in.kind,initial,middle,end,progresses:!!initial&&!!middle&&!!end&&JSON.stringify(initial)!==JSON.stringify(middle)&&JSON.stringify(middle)!==JSON.stringify(end)};
   }):[];
   const transitionsOK=transitionChecks.every(s=>s.progresses);
   const sources=modular?JSON.parse(execFileSync('python3',['-B','-c',`import sys,json;sys.path.insert(0,'sistema/clone');import engine;print(json.dumps(engine.source_fingerprint(sys.argv[1])))`,folder],{encoding:'utf8'})):null;
   const record={ok:!errors.length&&response.status()===200&&seekOK&&new Set(metadata.ids).size===metadata.ids.length&&clockOK&&coverageOK&&transitionsOK,
    html_sha256:hash(fs.readFileSync(folder+'/index.html')),
    ...(sources?{source_sha256:sources.sha256,source_files:sources.files,architecture:'hyperframes_subcompositions'}:{}),
    http:response.status(),errors,seek_determinista:seekOK,seek_exact_bytes:seekExact,raster_tolerance:{mad:.001,above8_fraction:.00005,max:32,measured:raster},unique_ids:new Set(metadata.ids).size===metadata.ids.length,
    states_distinct:new Set(before).size,images:metadata.images.length,instances:metadata.instances,gsap:metadata.gsap,states,
    ...(modular?{local_clocks_ok:clockOK,host_coverage_ok:coverageOK,transitions_progress:transitionsOK,transition_checks:transitionChecks}:{}),
    differences:beforeDOM.flatMap((list,i)=>list.map((n,j)=>JSON.stringify(n)===JSON.stringify(afterDOM[afterDOM.length-1-i][j])?null:{t:times[i],before:n,after:afterDOM[afterDOM.length-1-i][j]}).filter(Boolean)),
    limit:'Control funcional y de reloj; no acredita semejanza con CLONE.'};
   fs.writeFileSync(folder+'/timeline_qc.json',JSON.stringify(record,null,2));
   results.push({folder,...record});console.log(folder,record.ok?'PASS':'FAIL');
  }catch(e){const record={folder,ok:false,error:String(e),errors};results.push(record);fs.writeFileSync(folder+'/timeline_qc.json',JSON.stringify(record,null,2));console.log(folder,'FAIL',String(e));}
  await page.close();
 }
 const report=folders.every(f=>f.startsWith('.estado/tmp/clone_variants/'))?'revision_variantes_timelines.json':folders.every(f=>f.startsWith('proyectos/clone_motor/previews/'))?'revision_timelines.json':'revision_especifica_timelines.json';
 fs.writeFileSync('proyectos/clone_motor/'+report,JSON.stringify(results,null,2));
 if(results.some(r=>!r.ok))process.exitCode=1;
}finally{await browser.close();server.close();}
