// QA CPU reproducible; temporales únicamente dentro de IVAN/.estado.
import fs from 'node:fs';import path from 'node:path';import http from 'node:http';import vm from 'node:vm';import {pathToFileURL,fileURLToPath} from 'node:url';import {createHash} from 'node:crypto';
const ROOT=fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'));
if(path.basename(ROOT)!=='IVAN')throw Error('Solo IVAN');
process.chdir(ROOT);
const TMP=path.join(ROOT,'.estado/tmp/clone_bv2_qa');
fs.mkdirSync(TMP,{recursive:true});
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp/clone_bv2_qa`;process.env.XDG_CACHE_HOME=path.join(TMP,'cache');process.env.XDG_CONFIG_HOME=path.join(TMP,'config');process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
const hash=b=>createHash('sha256').update(b).digest('hex');
const {bundleToSingleHtml}=await import(pathToFileURL(path.join(ROOT,'.estado/herramientas/node_modules/hyperframes/dist/compiler-ACCPOZMQ.js')).href);
const stubSource=fs.readFileSync('.estado/herramientas/node_modules/hyperframes/dist/chunk-3BYMCR4O.js','utf8');const stub=vm.runInNewContext(stubSource.match(/var HF_EARLY_STUB_IIFE = (.*?);\nfunction getHfEarlyStub/s)[1]);
const folders={B:'proyectos/clone_motor/creatividad/comparacion',phone_rebuild:'.estado/tmp/clone_bv2_qa/phone_rebuild',terminal_install:'.estado/tmp/clone_bv2_qa/terminal_install'};
for(const [key,folder] of Object.entries(folders))fs.writeFileSync(path.join(TMP,key+'_compiled.html'),await bundleToSingleHtml(path.join(ROOT,folder),{staticGuard:false}));
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png','.woff2':'font/woff2'};
const server=http.createServer((req,res)=>{const url=new URL(req.url,'http://local'),key=url.pathname.split('/')[1];let file;
 if(url.pathname===`/${key}/index.html`&&folders[key])file=path.join(TMP,key+'_compiled.html');else if(folders[key])file=path.resolve(ROOT,folders[key],'.'+url.pathname.slice(key.length+1));
 if(!file?.startsWith(ROOT+'/')||!fs.existsSync(file)||!fs.realpathSync(file).startsWith(ROOT+'/')||!mime[path.extname(file)])return res.writeHead(404).end();res.writeHead(200,{'Content-Type':mime[path.extname(file)]});fs.createReadStream(file).pipe(res);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const {chromium}=await import(pathToFileURL(path.join(ROOT,'.estado/herramientas/node_modules/playwright/index.mjs')).href);
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-crash-reporter','--disable-breakpad','--disable-gpu','--force-color-profile=srgb']});
const report={scope:'CPU, compilador y early stub reales0.8.147; no MP4.',projects:{},pass:false};
try{
 for(const [key,folder] of Object.entries(folders)){
  const page=await browser.newPage({viewport:{width:1080,height:1920}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript({content:'globalThis.__HF_RENDER_CAPTURE_MODE=true;\n'+stub});
  await page.goto(`http://127.0.0.1:${server.address().port}/${key}/index.html`,{waitUntil:'domcontentloaded',timeout:20000});await page.evaluate(()=>{window.__hfFlushSync?.();});
  try{await page.waitForFunction(()=>window.renderReady===true&&window.__renderReady===true&&window.__playerReady===true,null,{timeout:16000});}
  catch(e){report.projects[key]={errors,wait_error:e.message,pass:false};await page.close();continue;}
  await page.evaluate(()=>{window.__hfFlushSync?.();gsap.ticker.sleep();});
  const spec=JSON.parse(fs.readFileSync(path.join(ROOT,folder,'scene.json'),'utf8'));
  const snap=()=>page.evaluate(()=>{
   const alpha=n=>{let a=1;for(let p=n;p&&p.nodeType===1;p=p.parentElement){const s=getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden')return 0;a*=parseFloat(s.opacity);}return a;};
   const bounds=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
   const px=n=>{const m=n.getScreenCTM(),size=parseFloat(getComputedStyle(n).fontSize);return size*Math.hypot(m.c,m.d);};
   const texts=[];for(const n of document.querySelectorAll('svg text'))if(alpha(n)>0&&n.textContent.trim())texts.push({text:n.textContent,opacity:alpha(n),bbox:bounds(n),font_px:px(n)});
   const native=Object.fromEntries(Object.entries(window.__cloneBuilt||{}).map(([id,b])=>{
    const C=b.context,img=C.q('hero')?.querySelector('image')||C.q('agent')?.querySelector('image');
    const prim=C.q('layout-primary');return [id,{time:CloneTimelineReal(b.renderTl||b.tl).time(),layout:b.layout,closing:b.closing,
     actor:img?{bbox:bounds(img),opacity:alpha(img)}:null,primary:prim?{bbox:bounds(prim),opacity:alpha(prim)}:null,
     counts:[0,1,2].map(i=>C.q('count'+i)?.textContent).filter(x=>x!==undefined),
     quote_lines:[0,1,2].flatMap(i=>{const q=C.q('review'+i);if(!q)return [];const body=q.querySelector('text'),tag=q.querySelectorAll('text')[1];return [...body.querySelectorAll('tspan')].map(n=>({bbox:bounds(n),font_px:px(body),tag_bbox:bounds(tag)}));}),
     conclusion:C.q('closing-conclusion')?{opacity:alpha(C.q('closing-conclusion')),bbox:bounds(C.q('closing-conclusion'))}:null}];}));
   const bridge=document.querySelector('[id$="-actor-bridge-sprite"]');
   const receipt=window.__cloneInstances.find(x=>x.family==='compositor_actor_bridge');
   return {texts,native,bridge:bridge?{bbox:bounds(bridge),opacity:alpha(bridge),receipt:receipt?.continuity}:null,ids:[...document.querySelectorAll('[id]')].map(n=>n.id),timelines:Object.keys(window.__timelines),instances:window.__cloneInstances.map(n=>({id:n.id,family:n.family,duration:n.duration}))};
  });
  const seek=async t=>{await page.evaluate(t=>{window.__player.renderSeek(t,{suppressEvents:false});window.__hfFlushSync?.();},t);await page.waitForTimeout(25);return snap();};
  const times=key==='B'?[0,.6,1.6,...Array.from({length:23},(_,i)=>(61+i)/30),5.3,6.8666666667,6.9,7.1,7.3,7.5,8,8.9666666667]:[0,.6,2.8,3.9666666667,4,4.0333333333,4.6,6.8,7.9666666667];
  const forward=[],reverse=[];
  for(const t of times)forward.push({t,state:await seek(t)});
  for(const t of [...times].reverse())reverse.push({t,state:await seek(t)});
  const compare=forward.map((f,i)=>{const r=reverse[reverse.length-1-i];return {t:f.t,visible_state_equal:JSON.stringify({texts:f.state.texts,native:f.state.native,bridge:f.state.bridge})===JSON.stringify({texts:r.state.texts,native:r.state.native,bridge:r.state.bridge})};});
  const checks={no_runtime_errors:errors.length===0,registered_all_hosts:forward.every(f=>f.state.timelines.length===(key==='B'?4:3)),unique_ids:forward.every(f=>new Set(f.state.ids).size===f.state.ids.length),reverse_visible_states:compare.every(c=>c.visible_state_equal)};
  let detailed={};
  if(key==='B'){
   const proof=forward.find(f=>f.t===5.3).state,final=forward[forward.length-1].state;
   const lines=proof.native.cobertura.quote_lines,overlap=(a,b)=>Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)+1&&Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y)+1;
   checks.quote_font_mobile=lines.length===6&&lines.every(n=>n.font_px>=48);
   checks.no_quote_tag_collision=lines.every(n=>!overlap(n.bbox,n.tag_bbox));
   checks.conclusion_values_unchanged=JSON.stringify(final.native.cobertura.counts)==='["2","1","3"]';
   checks.conclusion_visible=final.native.cobertura.conclusion.opacity===1;
   checks.conclusion_within_frame=Object.values(final.native.cobertura.conclusion.bbox).every(Number.isFinite)&&final.native.cobertura.conclusion.bbox.y+final.native.cobertura.conclusion.bbox.h<1824;
   const bridgePoses=forward.filter(f=>f.t>=2.1&&f.t<=2.7).map(f=>({t:f.t,bridge:f.state.bridge,source:f.state.native.planteamiento.actor,target:f.state.native.cobertura.actor}));
   checks.bridge_really_moves=bridgePoses.length>=18&&new Set(bridgePoses.map(s=>JSON.stringify(s.bridge.bbox))).size>12;
   checks.actor_never_disappears=bridgePoses.every(s=>s.bridge.opacity>0||s.source.opacity>0||s.target.opacity>0);
   const last=bridgePoses[bridgePoses.length-1],delta=Math.max(...['x','y','w','h'].map(k=>Math.abs(last.bridge.bbox[k]-last.target.bbox[k])));
   checks.bridge_arrives_at_native_pose=delta<1;
   checks.native_actor_visible_at_arrival=last.target.opacity===1;
   checks.no_caption_conclusion_overlap=forward.filter(f=>f.t>=6.9).every(f=>{const c=f.state.native.cobertura.conclusion;if(!(c?.opacity>0))return true;return !f.state.texts.some(n=>n.text==='TERCERA'&&n.opacity>0);});
   detailed={quote_lines:lines,bridge_poses:bridgePoses,arrival_bbox_max_delta_px:delta,final_values:final.native.cobertura.counts};
  }else{
   const poses=forward.filter(f=>[2.8,6.8].includes(f.t));
   checks.layout_in_two_instances=poses.every(f=>Object.values(f.state.native).every(n=>n.layout?.profile==='centered_primary'));
   checks.primary_fits_canvas=poses.every(f=>Object.values(f.state.native).filter(n=>n.primary?.opacity>0).every(n=>n.primary.bbox.x>=0&&n.primary.bbox.x+n.primary.bbox.w<=1080.01));
   checks.two_namespaces=Object.keys(forward[0].state.native).length===2;
   detailed={reading_poses:poses};
  }
  await seek(key==='B'?7.5:2.8);const screen=await page.screenshot({timeout:15000});fs.writeFileSync(path.join(TMP,key+'_proof.png'),screen);
  report.projects[key]={errors,checks,compare,detailed,proof_png_sha256:hash(screen),pass:Object.values(checks).every(Boolean),forward,reverse};await page.close();
 }
 report.pass=Object.values(report.projects).every(p=>p.pass);
}catch(e){report.error={message:e.message,stack:e.stack?.split('\n').slice(0,4)};}
finally{await browser.close();await new Promise(r=>server.close(r));report.summary=Object.fromEntries(Object.entries(report.projects).map(([k,p])=>[k,{pass:p.pass,errors:p.errors,failed_checks:Object.entries(p.checks||{}).filter(([,v])=>!v).map(([k])=>k)}]));fs.writeFileSync(path.join(TMP,'browser.json'),JSON.stringify(report,null,2));}
console.log(JSON.stringify({pass:report.pass,summary:report.summary,error:report.error},null,2));if(!report.pass)process.exitCode=1;
