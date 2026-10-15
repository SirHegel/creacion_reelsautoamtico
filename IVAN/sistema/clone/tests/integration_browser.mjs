/* QA independiente CLONE+YO. CPU, sin editar fuentes ni producir MP4. */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const ROOT=fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'));
if(path.basename(ROOT)!=='IVAN')throw Error('Solo IVAN');
process.chdir(ROOT);
const QUICK=process.argv.includes('--quick');
const ID=process.argv.slice(2).find(v=>!v.startsWith('--'))||'demo_integracion';
if(!/^[A-Za-z0-9_-]{12,100}$/.test(ID))throw Error('ID inválido');
const folder=path.join(ROOT,'proyectos',ID,'integracion');
const TMP=path.join(ROOT,'.estado/tmp/integration_browser'),proof=path.join(folder,'evidencia_qa/browser');
fs.mkdirSync(TMP,{recursive:true});fs.mkdirSync(proof,{recursive:true});
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp/integration_browser`;
process.env.XDG_CACHE_HOME=path.join(TMP,'cache');process.env.XDG_CONFIG_HOME=path.join(TMP,'config');
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const digest=p=>hash(fs.readFileSync(p));
const relative=p=>path.relative(ROOT,p);
const required=['index.html','integration-config.json','integration_plan.json','scene.json','narration.json'];
for(const name of required)if(!fs.existsSync(path.join(folder,name)))throw Error('Falta composición preparada: '+name);
const cfg=read(path.join(folder,'integration-config.json')),dir=read(path.join(folder,'integration_plan.json'));
const narration=read(path.join(folder,'narration.json')),face=read(path.join(folder,'diagnostico_yo/anclas_55_45.json'));
const FRAME_COUNT=cfg.frames,FPS=30;
const baseline=read(path.join(ROOT,'sistema/clone/tests/fixtures/composition_v2_preserved.json'));
const protectedPaths={...baseline.preservation_files,
 'proyectos/clone_motor/creatividad/comparacion/B_V1.mp4':'918513396c7025c7b9d53eb80da9db9db2baaf442b36f9d60c0ec8d7dd28bcf8',
 'proyectos/clone_motor/creatividad/comparacion/preview.mp4':'ea70279dbe9defb45964a21c83b4fa1d95bf4a0258df50c169b9d3e7c8e675f0'};
const preservation=()=>Object.fromEntries(Object.keys(protectedPaths).map(p=>{
 const file=fs.realpathSync(path.join(ROOT,p));if(!file.startsWith(ROOT+'/'))throw Error('Ruta protegida externa');return[p,digest(file)];}));
const preservedBefore=preservation();
const sourceFingerprint=()=>{
 const result=spawnSync('python3',['-B','-c',
  "import sys,json;sys.path.insert(0,'sistema/clone');import engine;print(json.dumps(engine.source_fingerprint(sys.argv[1])))",relative(folder)],{cwd:ROOT,encoding:'utf8'});
 if(result.status)throw Error('No se pudo medir fuente transitiva');return JSON.parse(result.stdout);
};
const sourceBefore=sourceFingerprint();
const additionalSources=['integration_plan.json','integration-config.json','narration.json','diagnostico_yo/anclas_55_45.json'];
const auxiliary=()=>Object.fromEntries(additionalSources.map(p=>[p,digest(path.join(folder,p))]));
const auxiliaryBefore=auxiliary();
// La compilación local9.0.2 carece de encoder PNG; usar el decoder CPU ya instalado.
const ffmpeg='/usr/bin/ffmpeg';
const proxy=path.join(folder,'media/camera.mp4'),proxySha=digest(proxy),frames=path.join(TMP,'source_frames');
fs.mkdirSync(frames,{recursive:true});
const cachePath=path.join(TMP,'source_frames.json');
const cached=fs.existsSync(cachePath)?read(cachePath):{};
if(cached.proxy_sha256!==proxySha||Array.from({length:FRAME_COUNT},(_,i)=>path.join(frames,`frame_${String(i).padStart(3,'0')}.png`)).some(p=>!fs.existsSync(p))){
 const r=spawnSync(ffmpeg,['-v','error','-threads','2','-i',proxy,'-an','-fps_mode','passthrough','-threads','2','-start_number','0','-y',path.join(frames,'frame_%03d.png')],{cwd:ROOT,encoding:'utf8'});
 if(r.status)throw Error('Falló decodificación CPU del proxy: '+r.stderr.slice(-400));
 fs.writeFileSync(cachePath,JSON.stringify({proxy_sha256:proxySha,frames:FRAME_COUNT},null,2));
}
const pkg=path.join(ROOT,'.estado/herramientas/node_modules');
const {bundleToSingleHtml}=await import(pathToFileURL(path.join(pkg,'hyperframes/dist/compiler-ACCPOZMQ.js')).href);
const {injectVideoFramesBatch,syncVideoFrameVisibility}=await import(pathToFileURL(path.join(pkg,'hyperframes/dist/chunk-JF5L5SQ6.js')).href);
const stubSource=fs.readFileSync(path.join(pkg,'hyperframes/dist/chunk-3BYMCR4O.js'),'utf8');
const stub=vm.runInNewContext(stubSource.match(/var HF_EARLY_STUB_IIFE = (.*?);\nfunction getHfEarlyStub/s)[1]);
const compiled=path.join(TMP,'compiled.html');fs.writeFileSync(compiled,await bundleToSingleHtml(folder,{staticGuard:false}));
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2','.ttf':'font/ttf','.mp4':'video/mp4','.m4a':'audio/mp4'};
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://local');let file=url.pathname==='/index.html'?compiled:path.resolve(folder,'.'+decodeURIComponent(url.pathname));
 if(!file.startsWith(ROOT+'/')||!fs.existsSync(file)||!fs.realpathSync(file).startsWith(ROOT+'/')||!mime[path.extname(file)])return res.writeHead(404).end();
 res.writeHead(200,{'Content-Type':mime[path.extname(file)]});fs.createReadStream(file).pipe(res);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const {chromium}=await import(pathToFileURL(path.join(pkg,'playwright/index.mjs')).href);
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-crash-reporter','--disable-breakpad','--force-color-profile=srgb']});
const report={schema_version:1,mode:QUICK?'quick':'all_frames',frame_count:FRAME_COUNT,scope:'QA CPU de la integración; no render ni aprobación estética o sonora.',checks:{},warnings:[],errors:[],proofs:[],source_before:sourceBefore,auxiliary_before:auxiliaryBefore};
const detailed={forward:[],reverse:[],unordered:[],injected:[]};
let page;
try{
 page=await browser.newPage({viewport:{width:1080,height:1920}});
 page.on('pageerror',e=>report.errors.push(e.message));
 await page.addInitScript({content:'globalThis.__HF_RENDER_CAPTURE_MODE=true;\n'+stub});
 await page.goto(`http://127.0.0.1:${server.address().port}/index.html`,{waitUntil:'domcontentloaded',timeout:20000});
 await page.evaluate(()=>{window.__hfFlushSync?.();});
 await page.waitForFunction(()=>window.__integrationBuilt===true&&window.__playerReady===true&&window.__renderReady===true,null,{timeout:30000});
 await page.evaluate(()=>{gsap.ticker.sleep();});
 // El inyector instalado usa la firma de Puppeteer evaluate(fn,...args).
 // Adaptar el transporte a Playwright sin modificar la función del motor.
 const renderPage={evaluate:(fn,...args)=>args.length<2?page.evaluate(fn,args[0]):page.evaluate(({source,args})=>(0,eval)('('+source+')')(...args),{source:fn.toString(),args})};
 const videoId=await page.evaluate(()=>window.__hfMediaId?.(document.getElementById('integration-camera-video'))||'integration-camera-video');
 const snapshot=()=>page.evaluate(()=>{
  const alpha=node=>{let a=1;for(let p=node;p&&p.nodeType===1;p=p.parentElement){const s=getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden')return 0;a*=Number(s.opacity);}return a;};
  const box=node=>{const r=node.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};};
  const clip=node=>{const s=getComputedStyle(node),numbers=(s.clipPath.match(/[-+\d.]+%/g)||[]).map(v=>parseFloat(v)/100);return{css:s.clipPath,top:numbers[0]||0,bottom:numbers[2]??numbers[0]??0};};
  const mask=document.getElementById('integration-camera-mask'),plane=document.getElementById('integration-camera-plane'),viewport=document.getElementById('integration-motion-viewport');
  const video=document.getElementById('integration-camera-video'),image=video.nextElementSibling;
  const texts=[...document.querySelectorAll('#integration-type .integration-text')].filter(n=>alpha(n)>.001).map(n=>{
   const range=document.createRange();range.selectNodeContents(n);const b=range.getBoundingClientRect();
   const ctx=document.createElement('canvas').getContext('2d');
   const words=[...n.querySelectorAll('[data-word]')].map(s=>{const r=document.createRange();r.selectNodeContents(s);if(s.firstChild?.nodeType===3)r.setEnd(s.firstChild,s.textContent.trimEnd().length);const b=r.getBoundingClientRect(),css=getComputedStyle(s),sb=box(s);ctx.font=`${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;const m=ctx.measureText(s.textContent.trimEnd());
    // DOM Range includes the font's ascent/descent, not the painted glyphs.
    // Derive the baseline from this actual inline box and the loaded font.
    const baseline=sb.y+(sb.h+m.fontBoundingBoxAscent-m.fontBoundingBoxDescent)/2;
    const paintedInk={x:sb.x-m.actualBoundingBoxLeft,y:baseline-m.actualBoundingBoxAscent,w:m.actualBoundingBoxLeft+m.actualBoundingBoxRight,h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent};
    return{index:Number(s.dataset.word),text:s.textContent,opacity:alpha(s),bbox:sb,ink:{x:b.x,y:b.y,w:b.width,h:b.height},paintedInk,whiteSpace:css.whiteSpace};});
   const painted=words.filter(w=>w.opacity>.001).map(w=>w.paintedInk),x=Math.min(...painted.map(w=>w.x)),y=Math.min(...painted.map(w=>w.y));
   const paintedInk=painted.length?{x,y,w:Math.max(...painted.map(w=>w.x+w.w))-x,h:Math.max(...painted.map(w=>w.y+w.h))-y}:null;
   return{id:n.id,text:n.textContent,bbox:box(n),ink:{x:b.x,y:b.y,w:b.width,h:b.height},paintedInk,opacity:alpha(n),font:getComputedStyle(n).fontFamily,size:parseFloat(getComputedStyle(n).fontSize),shadow:getComputedStyle(n).textShadow,words};});
  const pausedChain=tl=>{let any=false,p=CloneTimelineReal(tl),seen=new Set();while(p&&!seen.has(p)){seen.add(p);any||=p.paused?.()===true;p=p.parent;}return any;};
  const native=[...document.querySelectorAll('svg text')].filter(n=>alpha(n)>.001).map(n=>({text:n.textContent,bbox:box(n)}));
  return{time:CloneTimelineReal(window.__timelines['clone-main']).time(),ids:[...document.querySelectorAll('[id]')].map(n=>n.id),clockPaused:pausedChain(window.__timelines['clone-main']),
   camera:{opacity:Number(getComputedStyle(mask).opacity),clip:clip(mask),mask:box(mask),plane:box(plane),video:box(video),videoTime:video.currentTime,videoSrc:video.getAttribute('src'),sourceStart:video.getAttribute('data-media-start'),playbackRate:video.getAttribute('data-playback-rate'),
    injected:image?.classList.contains('__render_frame__')?{bbox:box(image),opacity:alpha(image),src:image.getAttribute('src'),complete:image.complete,width:image.naturalWidth,height:image.naturalHeight}:null,
    filters:[mask,plane,video].map(n=>({filter:getComputedStyle(n).filter,backdrop:getComputedStyle(n).backdropFilter})),videoCount:document.querySelectorAll('video').length},
   motion:{viewport:box(viewport),clip:clip(viewport)},texts,native,receipt:window.__integrationReceipt};
 });
 const seek=async t=>{
  await page.evaluate(t=>{window.__player.renderSeek(t,{suppressEvents:false});window.__hfFlushSync?.();},t);
  const index=Math.max(0,Math.min(FRAME_COUNT-1,Math.floor(t*FPS+1e-7))),file=path.join(frames,`frame_${String(index).padStart(3,'0')}.png`),buffer=fs.readFileSync(file),uri='data:image/png;base64,'+buffer.toString('base64');
  await syncVideoFrameVisibility(renderPage,[videoId]);const injected=await injectVideoFramesBatch(renderPage,[{videoId,dataUri:uri}]);
  if(!injected.includes(videoId))throw Error('El motor no inyectó el vídeo original');
  await page.evaluate(t=>{window.__hfReseekGpu?.(t);window.__hfFlushSync?.();},t);
  const state=await snapshot();if(state.camera.injected?.src!==uri)throw Error('Frame de fuente incorrecto');
  state.camera.injected.source_sha256=hash(buffer);state.camera.injected.source_index=index;delete state.camera.injected.src;
  detailed.injected.push({t,index,sha256:hash(buffer)});return state;
 };
 const quickTimes=new Set([0,.55,1,1.4,2.6,4.5,6.4,7.55]);
 for(const w of dir.camera_windows)for(const f of [w.start_frame-1,w.start_frame,w.start_frame+1,w.start_frame+w.transition_frames-1,w.start_frame+w.transition_frames,w.end_frame-w.exit_frames-1,w.end_frame-w.exit_frames,w.end_frame-1,w.end_frame,w.end_frame+1])if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);
 for(const w of narration.words)quickTimes.add(Math.max(0,Math.min(FRAME_COUNT-1,Math.round((w.start+w.end)/2*FPS)))/FPS);
 // A midpoint may fall inside an explicit composition pause. Check every
 // native frame spoken after the hook, so the pause cannot hide a lost word.
 const plannedHookEnd=Math.max(0,...(dir.hook_blocks||[]).map(b=>b.end_frame/FPS));
 for(const w of narration.words)if(w.start>=plannedHookEnd-1e-7)for(let f=Math.ceil(w.start*FPS-1e-7);f<Math.ceil(w.end*FPS-1e-7)&&f<FRAME_COUNT;f++)quickTimes.add(f/FPS);
 const times=QUICK?[...quickTimes].sort((a,b)=>a-b):Array.from({length:FRAME_COUNT},(_,f)=>f/FPS),forward=new Map();
 for(const t of times){const state=await seek(t);detailed.forward.push({t,state});forward.set(t,state);}
 const observable=s=>JSON.stringify({time:s.time,camera:s.camera,motion:s.motion,texts:s.texts,native:s.native});
 const reverseDifferences=[];
 for(const t of [...times].reverse()){const state=await seek(t);detailed.reverse.push({t,state});if(observable(state)!==observable(forward.get(t)))reverseDifferences.push(t);}
 const unordered=[7.55,.55,4.5,1.4,6.4,1,2.6,0,7.55,2.6];
 const unorderedDifferences=[];
 for(const t of unordered){const a=await seek(t),b=await seek(0),c=await seek(t);detailed.unordered.push({t,state:a});if(observable(a)!==observable(c))unorderedDifferences.push(t);}
 const runFrames=[];let run=null;
 const cameraGeometry=[],captions=[],micWarnings=[];
 const interpolate=(pairs,t,key)=>{let i=0;while(i<pairs.length-2&&pairs[i+1].t<t)i++;const a=pairs[i],b=pairs[Math.min(i+1,pairs.length-1)],u=b.t===a.t?0:Math.min(1,Math.max(0,(t-a.t)/(b.t-a.t)));return a[key]+(b[key]-a[key])*u;};
 const chins=face.anchors.map(a=>({t:a.t,chin:a.source_normalized.smooth_chin[1]*1920}));
 const overlaps=(a,b)=>Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)&&Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y);
 const visualPath=path.join(folder,'VISUAL_QA.json');const mic=fs.existsSync(visualPath)?read(visualPath).source_microphone_bbox:null;
 const micBox=mic?.source_bbox_xyxy;
 for(const {t,state:s}of detailed.forward){
  const visible=s.camera.opacity>.001&&s.camera.clip.top<.999;
  const f=Math.round(t*FPS);if(visible&&!run)run={start_frame:f,end_frame:f+1};else if(visible)run.end_frame=f+1;else if(run){runFrames.push(run);run=null;}
  const window=dir.camera_windows.find(w=>f>=w.start_frame&&f<w.end_frame),stable=window&&f>=window.start_frame+window.transition_frames&&f<window.end_frame-6;
  if(stable&&window.state==='split')cameraGeometry.push({t,top:s.camera.clip.top,motionBottom:s.motion.clip.bottom,video:s.camera.video,plane:s.camera.plane});
  if(visible){
   const expected=interpolate(chins,Math.round(t*FPS)/FPS,'chin')+s.camera.plane.y;
   for(const text of s.texts){const block=dir.caption_blocks.find(b=>'integration-text-'+b.id===text.id);if(!block)continue;
    captions.push({t,text:text.text,center:text.ink.x+text.ink.w/2,gap:text.paintedInk.y-expected,bbox:text.paintedInk,range_bbox:text.ink,shadow:text.shadow,font:text.font,size:text.size});
    if(micBox){const [x,y,x2,y2]=micBox,rect={x,y:y+s.camera.plane.y,w:x2-x,h:y2-y};if(overlaps(text.paintedInk,rect))micWarnings.push({t,text:text.text,bbox:text.paintedInk,mic_bbox:rect});}
   }
  }
 }
 if(run)runFrames.push(run);
 const maxRun=Math.max(0,...runFrames.map(w=>w.end_frame-w.start_frame));
 const expectedFrames=new Set(dir.camera_windows.flatMap(w=>Array.from({length:w.end_frame-w.start_frame},(_,i)=>w.start_frame+i)));
 const observedFrames=new Set(runFrames.flatMap(w=>Array.from({length:w.end_frame-w.start_frame},(_,i)=>w.start_frame+i)));
 const hook=dir.hook_blocks||[],prefixes=hook.map(b=>narration.words.slice(b.word_start,b.word_end+1).map(w=>w.text).join(' '));
 const hookGroups=Object.groupBy(hook,b=>b.sequence||b.id);
 const grows=Object.values(hookGroups).every(group=>group.length>=2&&group.every((b,i)=>!i||b.word_start===group[i-1].word_start&&b.word_end>group[i-1].word_end));
 const hookPaintedStages=Object.values(hookGroups).map(group=>{const id='integration-text-'+group[0].id,stages=[];
  for(const pose of detailed.forward){const text=pose.state.texts.find(n=>n.id===id);if(text){const indices=text.words.filter(w=>w.opacity>.01).map(w=>w.index);if(indices.length&&!stages.some(s=>JSON.stringify(s)===JSON.stringify(indices)))stages.push(indices);}}
  return {sequence:group[0].sequence||group[0].id,stages};});
 const hookEnd=Math.max(0,...hook.map(b=>b.end_frame/FPS));
 const missingWords=[],documentedPauses=[];
 const pauses=detailed.forward[0].state.receipt.component_overrides.filter(r=>r.reason==='brief_type_pause_during_camera_reveal');
 for(const [i,w]of narration.words.entries())if(w.start>=hookEnd-1e-7){const poses=detailed.forward.filter(p=>p.t>=w.start-1e-7&&p.t<w.end-1e-7);
  const present=poses.filter(p=>p.state.texts.some(n=>n.words.some(x=>x.index===i&&x.opacity>.01))),absent=poses.filter(p=>!present.includes(p));
  const accounted=absent.every(p=>pauses.some(r=>r.end-r.start<=.201&&p.t>=r.start-1e-7&&p.t<=r.end+1e-7));
  if(!present.length||!accounted)missingWords.push({index:i,text:w.text,start:w.start,end:w.end,visible_frames:present.map(p=>Math.round(p.t*FPS)),unaccounted_frames:absent.filter(p=>!pauses.some(r=>r.end-r.start<=.201&&p.t>=r.start-1e-7&&p.t<=r.end+1e-7)).map(p=>Math.round(p.t*FPS))});
  else if(absent.length)documentedPauses.push({index:i,text:w.text,visible_frames:present.map(p=>Math.round(p.t*FPS)),paused_frames:absent.map(p=>Math.round(p.t*FPS)),reason:'brief_type_pause_during_camera_reveal'});
 }
 const spacing=[];
 for(const {t,state:s}of detailed.forward)for(const text of s.texts)for(let i=1;i<text.words.length;i++){const a=text.words[i-1],b=text.words[i];if(Math.abs(a.ink.y-b.ink.y)<2)spacing.push({t,text:text.text,gap:b.ink.x-(a.ink.x+a.ink.w)});}
 report.checks={runtime_ready:true,no_runtime_errors:report.errors.length===0,unique_ids:detailed.forward.every(({state:s})=>new Set(s.ids).size===s.ids.length),clock_seek_exact:detailed.forward.every(({t,state:s})=>Math.abs(Math.floor(t*FPS+1e-7)/FPS-s.time)<1e-5),clock_effectively_paused:detailed.forward.every(({state:s})=>s.clockPaused),
  source_frame_injected:detailed.forward.every(({t,state:s})=>s.camera.injected?.source_index===Math.min(FRAME_COUNT-1,Math.floor(t*FPS+1e-7))&&s.camera.injected.complete&&s.camera.injected.width===1080&&s.camera.injected.height===1920),
  source_timing_unchanged:detailed.forward.every(({state:s})=>Number(s.camera.sourceStart)===0&&(!s.camera.playbackRate||Number(s.camera.playbackRate)===1)),
  camera_continuous_limit:maxRun<=90,camera_within_declared_frames:[...detailed.forward].filter(p=>p.state.camera.opacity>.001&&p.state.camera.clip.top<.999).every(p=>expectedFrames.has(Math.round(p.t*FPS))),
  full_camera_visible:dir.camera_windows.filter(w=>w.state==='full').every(w=>detailed.forward.filter(p=>p.t>=w.start_frame/FPS&&p.t<w.end_frame/FPS).every(p=>p.state.camera.opacity>.001&&p.state.camera.clip.top<.001)),
  split_55_45_native_width:cameraGeometry.length>0&&cameraGeometry.every(s=>Math.abs(s.top-.55)<.001&&Math.abs(s.motionBottom-.45)<.001&&Math.abs(s.video.w-1080)<.01&&Math.abs(s.video.h-1920)<.01&&Math.abs(s.plane.y-711)<.01),
  no_added_blur_or_duplicated_video:detailed.forward.every(({state:s})=>s.camera.videoCount===1&&s.camera.filters.every(f=>f.filter==='none'&&f.backdrop==='none')),
  captions_centered:captions.every(c=>Math.abs(c.center-540)<2),captions_below_chin:captions.every(c=>c.gap>=0&&c.gap<120),captions_inside_frame:captions.every(c=>c.bbox.x>=0&&c.bbox.x+c.bbox.w<=1080&&c.bbox.y+c.bbox.h<=1920),
  hook_phrases_grow:grows&&hookPaintedStages.every(g=>g.stages.length>=2),text_after_hook_covered:missingWords.length===0,
  reverse_states_equal:reverseDifferences.length===0,unordered_states_equal:unorderedDifferences.length===0};
 report.metrics={sampled_poses:times.length,clock_policy:'seek real cuantizado al frame inferior a 30 FPS; tolerancia numérica 1e-5 s',caption_vertical_measurement:'Tinta mediante metrics de fuente cargada y baseline inline real; Range conserva la medición horizontal',camera_counting:QUICK?'Muestras puntuales; no recuento completo de presencia.':'Cada fotograma de la fuente.',camera_runs:QUICK?null:runFrames,max_continuous_frames:QUICK?null:maxRun,total_visible_frames:QUICK?null:observedFrames.size,declared_camera_frames:expectedFrames.size,presence_fraction:QUICK?null:observedFrames.size/FRAME_COUNT,split_samples:cameraGeometry.length,caption_samples:captions.length,caption_measurements:captions.filter((_,i)=>i%5===0),hook_prefixes:prefixes,hook_painted_stages:hookPaintedStages,missing_words:missingWords,documented_pauses:documentedPauses,reverse_differences:reverseDifferences,unordered_differences:unorderedDifferences,word_spacing_min:Math.min(...spacing.map(p=>p.gap)),mic_intersections:micWarnings.slice(0,12)};
 if(micWarnings.length)report.warnings.push({kind:'microphone_review',count:micWarnings.length,note:'Intersección con bbox conservadora medida visualmente; requiere inspección de tinta/sombra, no rechazo automático.'});
 if(!micBox)report.warnings.push({kind:'microphone_unmeasured',note:'No se certifica ausencia de cruce con micrófono sin medición verificable.'});
 if(spacing.some(p=>p.gap<1))report.warnings.push({kind:'word_spacing',note:'Posible pérdida de espacio entre spans inline-block; revisar los PNG nativos.',examples:spacing.filter(p=>p.gap<1).slice(0,8)});
 for(const t of [.55,1,1.4,2.6,4.5,6.4,7.55]){
  await seek(t);const file=path.join(proof,`t_${t.toFixed(2).replace('.','_')}.png`),buffer=await page.screenshot({timeout:15000});fs.writeFileSync(file,buffer);report.proofs.push({t,path:relative(file),sha256:hash(buffer)});
 }
 report.integration_receipt=await page.evaluate(()=>window.__integrationReceipt);
}catch(error){report.errors.push(error.message);report.exception={message:error.message,stack:error.stack?.split('\n').slice(0,5).map(s=>s.replaceAll(ROOT,'IVAN'))};}
finally{
 await browser.close();await new Promise(r=>server.close(r));
 report.source_after=sourceFingerprint();report.auxiliary_after=auxiliary();
 const preservedAfter=preservation();report.preservation={count:Object.keys(protectedPaths).length,baseline_match:JSON.stringify(preservedBefore)===JSON.stringify(protectedPaths),unchanged:JSON.stringify(preservedBefore)===JSON.stringify(preservedAfter),failed:Object.keys(protectedPaths).filter(p=>preservedAfter[p]!==protectedPaths[p])};
 report.checks.sources_stable=report.source_before.sha256===report.source_after.sha256&&JSON.stringify(report.auxiliary_before)===JSON.stringify(report.auxiliary_after);
 report.checks.preservation=report.preservation.baseline_match&&report.preservation.unchanged;
 const target=path.join(folder,'ascendia_integracion_test_10s.mp4');if(fs.existsSync(target))report.export_binding={path:relative(target),sha256:digest(target),source_sha256:report.source_after.sha256,note:'Hash comprobado; este harness no audita audio ni certifica estética del MP4.'};
 report.status=Object.values(report.checks).every(Boolean)&&report.errors.length===0?(QUICK?'PASS_QUICK_PENDING_FULL_AND_VISUAL':'PASS_CPU_PENDING_VISUAL_REVIEW'):'FAIL_OR_STALE';
 report.limits=['Recibo CPU con inyección real de frames del proxy H264 y compilador0.8.147; no reemplaza revisión del MP4.','Bbox de texto/micrófono son conservadoras; no equivalen a segmentación de tinta ni escucha.','No se afirma aprobación estética, calidad sonora ni validación de las afirmaciones narradas.'];
 const detailedPath=path.join(TMP,'detailed.json');fs.writeFileSync(detailedPath,JSON.stringify(detailed));report.private_trace={path:relative(detailedPath),sha256:digest(detailedPath)};
 fs.writeFileSync(path.join(folder,'integration_browser_qc.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({status:report.status,checks:report.checks,errors:report.errors,warnings:report.warnings,source:report.source_after.sha256,metrics:report.metrics?{camera_runs:report.metrics.camera_runs,total_visible_frames:report.metrics.total_visible_frames,caption_samples:report.metrics.caption_samples,missing_words:report.metrics.missing_words}:null},null,2));
 if(report.status==='FAIL_OR_STALE')process.exitCode=1;
}
