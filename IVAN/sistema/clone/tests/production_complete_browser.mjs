/* QA completo: fuentes/tiempos/cámara/anclas porsegmento, tipografía, recursos reales y seeks reproducibles.
   Reutiliza compilador/inyector de HyperFrames instalado; no renderizaMP4 ni edita las fuentes. */
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
const AUDIT_V1=false; // Este harness nunca revalida pruebas históricas.
const PROJECT_ARG=process.argv.find(v=>v.startsWith('--project='))?.slice('--project='.length);
const ID=process.argv.slice(2).find(v=>!v.startsWith('--'))||'demo_produccion';
if(!/^[A-Za-z0-9_-]{12,100}$/.test(ID))throw Error('ID inválido');
const folder=PROJECT_ARG?path.resolve(ROOT,PROJECT_ARG):AUDIT_V1?path.join(ROOT,'.estado/tmp/v2/v1_frozen'):path.join(ROOT,'proyectos',ID,'integracion');
const allowedProject=folder.startsWith(path.join(ROOT,'proyectos')+'/')||(AUDIT_V1&&folder===path.join(ROOT,'.estado/tmp/v2/v1_frozen'));
if(!allowedProject||!fs.existsSync(folder)||!fs.realpathSync(folder).startsWith(ROOT+'/'))throw Error('Proyecto QA fuera de IVAN o ausente');
const TMP=path.join(ROOT,'.estado/tmp/production_complete',ID),proof=path.join(folder,'evidencia_qa/browser_completo');
fs.mkdirSync(TMP,{recursive:true});fs.mkdirSync(proof,{recursive:true});
const browserTmp=path.join(ROOT,'.estado/tmp',`pc${process.pid}`);fs.mkdirSync(browserTmp,{recursive:true});
process.env.TMPDIR=`/proc/${process.pid}/cwd/${path.relative(ROOT,browserTmp)}`;
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
const brandRegistryPath=path.join(ROOT,'sistema/clone/brand_assets.json');
const brandRegistry=fs.existsSync(brandRegistryPath)?read(brandRegistryPath):{assets:{}};
const verifiedBrandFiles=Object.fromEntries(Object.entries(brandRegistry.assets).map(([key,a])=>{const file=path.resolve(ROOT,a.path);return [key,file.startsWith(ROOT+'/')&&fs.existsSync(file)&&fs.realpathSync(file).startsWith(ROOT+'/')&&digest(file)===a.sha256];}));
const FRAME_COUNT=cfg.frames,FPS=30,project=read(path.join(folder,'proyecto.json'));
if(!Number.isInteger(FRAME_COUNT)||FRAME_COUNT<1||Math.abs(cfg.duration-FRAME_COUNT/FPS)>1e-6)throw Error('Duración/cadencia inválidas');
const expectedBrandAssets=new Set();
const collectBrandRefs=value=>{if(typeof value==='string'&&brandRegistry.assets[value])expectedBrandAssets.add(value);else if(Array.isArray(value))value.forEach(collectBrandRefs);else if(value&&typeof value==='object')Object.values(value).forEach(collectBrandRefs);};
collectBrandRefs(cfg.scenes);collectBrandRefs(dir.hook_blocks);
const expectedBrands=[...new Set([...expectedBrandAssets].map(k=>brandRegistry.assets[k].brand))];
const baseline=read(path.join(folder,'diagnostico_preservacion.json'));
const protectedPaths={...baseline.preservation_files};
const preservation=()=>Object.fromEntries(Object.keys(protectedPaths).map(p=>{
 const file=fs.realpathSync(path.join(ROOT,p));if(!file.startsWith(ROOT+'/'))throw Error('Ruta protegida externa');return[p,digest(file)];}));
const preservedBefore=preservation();
const sourceFingerprint=()=>{
 const result=spawnSync('python3',['-B','-c',
  "import sys,json;sys.path.insert(0,'sistema/clone');import engine;print(json.dumps(engine.source_fingerprint(sys.argv[1])))",relative(folder)],{cwd:ROOT,encoding:'utf8'});
 if(result.status)throw Error('No se pudo medir fuente transitiva');return JSON.parse(result.stdout);
};
const sourceBefore=sourceFingerprint();
const qaHistory=[];
for(const name of ['production_complete_browser_qc.json','ritmo_completo.json']){
 const old=path.join(folder,name);if(!fs.existsSync(old))continue;
 const bytes=fs.readFileSync(old),save=path.join(TMP,'history',hash(bytes).slice(0,16)+'_'+name);fs.mkdirSync(path.dirname(save),{recursive:true});if(!fs.existsSync(save))fs.writeFileSync(save,bytes);
 qaHistory.push({file:name,previous_sha256:hash(bytes),private_archive:relative(save)});
}
const additionalSources=['scene.json','integration_plan.json','integration-config.json','narration.json','diagnostico_yo/anclas_55_45.json'];
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
const rawSource=path.resolve(ROOT,narration.source.path);
if(!fs.realpathSync(rawSource).startsWith(ROOT+'/'))throw Error('Fuente fuera de IVAN');
const rawSourceSha=digest(rawSource),pixelCache=path.join(TMP,'source_pixel_binding.json');
let sourcePixels=fs.existsSync(pixelCache)?read(pixelCache):{};
if(sourcePixels.raw_sha256!==rawSourceSha||sourcePixels.proxy_sha256!==proxySha){
 const decoded=file=>{const r=spawnSync(ffmpeg,['-v','error','-threads','2','-i',file,'-map','0:v:0','-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','framemd5','-'],{cwd:ROOT,encoding:'utf8',maxBuffer:8*1024*1024});if(r.status)throw Error('Falló prueba píxeles fuente: '+r.stderr.slice(-300));return r.stdout.split('\n').filter(v=>v&&!v.startsWith('#')).map(v=>{const q=v.split(',').map(x=>x.trim());return{pts:Number(q[2]),duration:Number(q[3]),bytes:Number(q[4]),hash:q[5]};});};
 const rawFrames=decoded(rawSource),proxyFrames=decoded(proxy);sourcePixels={raw_sha256:rawSourceSha,proxy_sha256:proxySha,raw_count:rawFrames.length,proxy_count:proxyFrames.length,decoded_rgb_exact:JSON.stringify(rawFrames)===JSON.stringify(proxyFrames),mismatches:rawFrames.flatMap((r,i)=>JSON.stringify(r)===JSON.stringify(proxyFrames[i])?[]:[i]).slice(0,30),method:'Todos los fotogramas RGB24 decodificados por el mismo FFmpeg CPU, tiempo y hash; sin comparación del MP4 compuesto.'};fs.writeFileSync(pixelCache,JSON.stringify(sourcePixels,null,2)+'\n');
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
const report={schema_version:2,mode:QUICK?'quick':'all_frames',frame_count:FRAME_COUNT,project:relative(folder),scope:'QA CPU del nuevo reel completo; no render ni aprobación estética o escucha perceptiva.',checks:{},warnings:[],errors:[],proofs:[],source_before:sourceBefore,auxiliary_before:auxiliaryBefore,previous_receipts_archived:qaHistory};
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
 report.fonts=await page.evaluate(()=>{const faces=[...document.fonts].map(f=>({family:f.family.replaceAll('"',''),weight:f.weight,style:f.style,status:f.status})),c=document.createElement('canvas').getContext('2d');c.font='700 72px Sequel';const sequel=c.measureText('sin necesidad').width;c.font='700 72px sans-serif';const fallback=c.measureText('sin necesidad').width;return{faces,sequel_test_width:sequel,fallback_test_width:fallback,font_faces_ready:document.fonts.status==='loaded',sequel_loaded:faces.some(f=>f.family==='Sequel'&&f.status==='loaded'),scholar_loaded:faces.some(f=>f.family==='Scholar'&&f.status==='loaded'),sequel_metric_distinct_from_fallback:Math.abs(sequel-fallback)>1};});

 // El inyector instalado usa la firma de Puppeteer evaluate(fn,...args).
 // Adaptar el transporte a Playwright sin modificar la función del motor.
 const renderPage={evaluate:(fn,...args)=>args.length<2?page.evaluate(fn,args[0]):page.evaluate(({source,args})=>(0,eval)('('+source+')')(...args),{source:fn.toString(),args})};
 const videoId=await page.evaluate(()=>window.__hfMediaId?.(document.getElementById('integration-camera-video'))||'integration-camera-video');
 // Targets come from actual mounted instances. A receipt naming a family or
 // resource is never sufficient proof of visibility or legible permanence.
 const assets=await page.evaluate(()=>Object.fromEntries(Object.entries(window.CLONE_ASSETS||{}).map(([k,{data,...meta}])=>[k,meta])));
 const mountedImages=await page.evaluate(()=>[...document.querySelectorAll('svg image,img[data-brand-asset]')].map((el,i)=>({ordinal:i,href:el.getAttribute('href')||el.getAttribute('xlink:href')||el.getAttribute('src')})));
 const imageAssets={};
 for(const item of mountedImages){
  let sha=null;if(item.href?.startsWith('data:')){const comma=item.href.indexOf(','),head=item.href.slice(0,comma),payload=item.href.slice(comma+1);sha=hash(head.endsWith(';base64')?Buffer.from(payload,'base64'):Buffer.from(decodeURIComponent(payload)));}
  imageAssets[item.ordinal]={sha256:sha,keys:sha?Object.keys(assets).filter(k=>assets[k].sha256===sha):[]};
 }
 await page.evaluate(imageAssets=>{
  window.__qaV2ImageAssets=imageAssets;
  // SVG geometry can remain in DOM while a later scene's opaque canvas hides
  // it. Honour actual paint order and clipping rather than certifying a ghost.
  window.__qaBackgrounds=()=>{
   const boxes=new WeakMap(),csses=new WeakMap(),cssOf=el=>{if(!csses.has(el))csses.set(el,getComputedStyle(el));return csses.get(el);};
   const rect=el=>{if(!boxes.has(el)){const b=el.getBoundingClientRect();boxes.set(el,{x:b.x,y:b.y,w:b.width,h:b.height});}return boxes.get(el);};
   const alpha=el=>{let a=1;for(let p=el;p&&p.nodeType===1;p=p.parentElement){const c=cssOf(p);if(c.display==='none'||c.visibility==='hidden')return 0;a*=Number(c.opacity);}return a;};
   const coord=(v,size)=>v.endsWith('%')?parseFloat(v)*size/100:parseFloat(v);
   const inside=(el,x,y)=>{const b=rect(el);if(x<b.x||x>b.x+b.w||y<b.y||y>b.y+b.h)return false;
    for(let p=el.parentElement;p;p=p.parentElement){const css=cssOf(p),b=rect(p);if(['hidden','clip'].includes(css.overflow)&&(x<b.x||x>b.x+b.w||y<b.y||y>b.y+b.h))return false;
     if(css.clipPath==='none')continue;
     if(css.clipPath.startsWith('inset(')){const a=(css.clipPath.match(/[-+\d.]+(?:%|px)/g)||[]);if(!a.length)return false;const top=coord(a[0],b.h),right=coord(a[1]??a[0],b.w),bottom=coord(a[2]??a[0],b.h),left=coord(a[3]??a[1]??a[0],b.w);if(x<b.x+left||x>b.x+b.w-right||y<b.y+top||y>b.y+b.h-bottom)return false;}
     else if(css.clipPath.startsWith('circle(')){const q=css.clipPath.match(/^circle\(([-+\d.]+(?:%|px)) at ([-+\d.]+(?:%|px)) ([-+\d.]+(?:%|px))\)$/);if(!q)return false;const r=coord(q[1],Math.hypot(b.w,b.h)/Math.SQRT2),cx=b.x+coord(q[2],b.w),cy=b.y+coord(q[3],b.h);if(Math.hypot(x-cx,y-cy)>r)return false;}
     else return false; // Unknown clipping never establishes opaque coverage.
    }return true;};
   const items=[...document.querySelectorAll('#integration-motion-viewport svg rect')].filter(el=>!el.closest('defs')&&Number(el.getAttribute('width'))>=710&&Number(el.getAttribute('height'))>=1270&&alpha(el)>=.999).flatMap(el=>{const colour=cssOf(el).fill,m=/^rgba?\(([^)]+)\)$/.exec(colour);if(!m)return[];const q=m[1].split(/[, ]+/).filter(Boolean).map(Number);if(q.length===4&&q[3]<.999)return[];return[{el,colour,bbox:rect(el)}];});
   const later=(el,bg)=>{if(el===bg||el.contains(bg)||!(el.compareDocumentPosition(bg)&Node.DOCUMENT_POSITION_FOLLOWING))return false;const a=el.closest('[id^="__clone-host-"]'),b=bg.closest('[id^="__clone-host-"]');return !a||!b||a===b||(+cssOf(b).zIndex||0)>=(+cssOf(a).zIndex||0);};
   const surfaceAt=(x,y)=>{const item=items.filter(o=>inside(o.el,x,y)).at(-1);return item?{colour:item.colour,scene_id:item.el.closest('[id^="__clone-host-"]')?.id.replace('__clone-host-','')||null}: {colour:getComputedStyle(document.getElementById('__clone-film')).backgroundColor,scene_id:null};};
   return{at:(x,y)=>surfaceAt(x,y).colour,surfaceAt,
    covered:(el,b)=>items.some(o=>later(el,o.el)&&[[b.x,b.y],[b.x+b.w,b.y],[b.x,b.y+b.h],[b.x+b.w,b.y+b.h]].every(([x,y])=>inside(o.el,x,y))),
    candidates:items.map(({el,...v})=>({id:el.id,scene_id:el.closest('[id^="__clone-host-"]')?.id,...v}))};
  };
  const descriptors=[];
  for(const scene of window.CLONE_INTEGRATION.scenes){
   const C=window.__cloneBuilt[scene.id]?.context;if(!C)throw Error('Familia declarada sin instancia real: '+scene.id);
   if(scene.family==='composition_graph')for(const node of scene.params.nodes)descriptors.push({key:scene.id+':'+node.id,scene_id:scene.id,family:scene.family,node_id:node.id,label:node.label,body_id:C.id(node.id),label_id:C.id(node.id+'-label'),kind:node.kind});
   else{
    const seen=new Set();
    for(const image of C.root.querySelectorAll('svg image')){let group=image.parentElement;while(group&&group!==C.root&&!group.id)group=group.parentElement;if(!group?.id||seen.has(group.id))continue;seen.add(group.id);descriptors.push({key:scene.id+':'+group.id,scene_id:scene.id,family:scene.family,node_id:group.id,label:group.querySelector('text')?.textContent||group.id,body_id:group.id,label_id:null,kind:'original_asset_group'});}
    if(!seen.size)descriptors.push({key:scene.id+':surface',scene_id:scene.id,family:scene.family,node_id:'surface',label:scene.family,body_id:C.root.id||null,body_scene_root:true,label_id:null,kind:'family_surface'});
   }
  }
  for(const [ordinal,image]of [...document.querySelectorAll('svg image,img[data-brand-asset]')].entries())if(image.matches('img[data-brand-asset]'))descriptors.push({key:'hook:'+image.dataset.brandAsset+':'+ordinal,scene_id:'clone-main',family:'YO_hook',node_id:image.dataset.brandEntity||image.alt,label:image.alt,body_id:null,image_ordinal:ordinal,label_id:null,kind:'official_hook_brand',brand_asset:image.dataset.brandAsset,brand_entity:image.dataset.brandEntity});
  window.__qaV2Subjects=descriptors;
  window.__qaV2Measure=()=>{
   const rect=el=>{const b=el.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height};};
   const alpha=el=>{let a=1;for(let p=el;p&&p.nodeType===1;p=p.parentElement){const c=getComputedStyle(p);if(c.display==='none'||c.visibility==='hidden')return 0;a*=Number(c.opacity);if(p instanceof SVGElement&&p.hasAttribute('opacity'))a*=1; }return a;};
   const intersect=(a,b)=>{const x=Math.max(a.x,b.x),y=Math.max(a.y,b.y);return{x,y,w:Math.max(0,Math.min(a.x+a.w,b.x+b.w)-x),h:Math.max(0,Math.min(a.y+a.h,b.y+b.h)-y)};};
   const paintBackgrounds=window.__qaBackgrounds();
   const clipped=(el,b)=>{let out=intersect(b,{x:0,y:0,w:1080,h:1920});for(let p=el.parentElement;p;p=p.parentElement){const css=getComputedStyle(p),pb=rect(p);if(css.overflow==='hidden'||css.overflow==='clip')out=intersect(out,pb);if(css.clipPath.startsWith('inset(')){const values=(css.clipPath.match(/[-+\d.]+%/g)||[]).map(Number.parseFloat);if(values.length){const top=values[0],right=values[1]??top,bottom=values[2]??top,left=values[3]??right;out=intersect(out,{x:pb.x+pb.w*left/100,y:pb.y+pb.h*top/100,w:pb.w*(1-(left+right)/100),h:pb.h*(1-(top+bottom)/100)});}}}
    // The camera is above the motion layer. DOM visibility alone would count
    // a completely covered protagonist under the initial full-screen photo.
    if(el.closest('#integration-motion-viewport')){const m=document.getElementById('integration-camera-mask'),css=getComputedStyle(m);if(Number(css.opacity)>.95){const top=parseFloat(css.clipPath.match(/[\d.]+%/)?.[0]||'0')/100*1920;out=intersect(out,{x:0,y:0,w:1080,h:top});}}
    if(out.w&&out.h&&paintBackgrounds.covered(el,out))out={...out,w:0,h:0};
    return{box:out,fraction:b.w*b.h?out.w*out.h/(b.w*b.h):0};};
   const rgb=s=>{if(/^#[0-9a-f]{6}$/i.test(s))return [1,3,5].map(i=>parseInt(s.slice(i,i+2),16));const m=/^rgba?\(([^)]+)\)$/.exec(s);return m?m[1].split(/[, ]+/).slice(0,3).map(Number):null;};
   const luminance=c=>{const v=c.map(n=>{const x=n/255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;});return .2126*v[0]+.7152*v[1]+.0722*v[2];};
   const contrast=(a,b)=>a&&b?(Math.max(luminance(a),luminance(b))+.05)/(Math.min(luminance(a),luminance(b))+.05):null;
   const imageList=[...document.querySelectorAll('svg image,img[data-brand-asset]')];
   const forbidden=/esquema conceptual|ejemplo conceptual|condicion del guion|enfado atribuido|pagina mencionada|segun el guion|sceneir|composition_graph|\bnode_id\b/i;
   window.__qaV2InternalNotes=[...document.querySelectorAll('svg text,#integration-type .integration-text')].filter(el=>!el.closest('defs')&&alpha(el)>.1).map(el=>({text:el.textContent,bbox:rect(el),visible_fraction:clipped(el,rect(el)).fraction})).filter(el=>el.visible_fraction>.15&&forbidden.test(el.text.normalize('NFD').replace(/\p{Diacritic}/gu,'')));
   window.__qaV2RouteCrossings=[];
   for(const scene of window.CLONE_INTEGRATION.scenes.filter(s=>s.family==='radial_research')){
    const C=window.__cloneBuilt[scene.id]?.context;if(!C)continue;
    const labels=(scene.params.sources||[]).flatMap((_,i)=>[...(C.q('source'+i)?.querySelectorAll('text')||[])].filter(el=>alpha(el)>=.85&&clipped(el,rect(el)).fraction>.9));
    for(let i=0;i<(scene.params.sources||[]).length;i++){const curve=C.q('line'+i);if(!curve||alpha(curve)<.25)continue;const css=getComputedStyle(curve),length=curve.getTotalLength(),matrix=curve.getScreenCTM(),dash=parseFloat(css.strokeDasharray),offset=Math.max(0,parseFloat(css.strokeDashoffset)||0),progress=Number.isFinite(dash)&&dash>0?Math.max(0,Math.min(1,1-offset/dash)):1;
     if(!matrix||progress<=0)continue;
     for(const label of labels){const b=rect(label);let hit=null;for(let k=0;k<=60;k++){const point=curve.getPointAtLength(length*progress*k/60),painted=new DOMPoint(point.x,point.y).matrixTransform(matrix);if(painted.x>b.x+1&&painted.x<b.x+b.w-1&&painted.y>b.y+1&&painted.y<b.y+b.h-1){hit={x:painted.x,y:painted.y};break;}}
      if(hit)window.__qaV2RouteCrossings.push({scene_id:scene.id,line_id:curve.id,label:label.textContent,label_bbox:b,point:hit,visible_progress:progress,method:'60 samples of the currently drawn SVG route; conservative label bbox, not glyph segmentation'});
     }
    }
   }
   for(const scene of window.CLONE_INTEGRATION.scenes.filter(s=>s.family==='composition_graph')){
    const C=window.__cloneBuilt[scene.id]?.context;if(!C)continue;
    const labels=[...C.root.querySelectorAll('text')].filter(el=>!el.closest('defs')&&!scene.params.steps.some((step,i)=>['transfer','collect'].includes(step.op)&&el.closest('#'+CSS.escape(C.id('packet'+i))))&&alpha(el)>=.85&&clipped(el,rect(el)).fraction>.9);
    for(let i=0;i<(scene.params.edges||[]).length;i++){
     const curve=C.q('line'+i);if(!curve||alpha(curve)<.25)continue;
     const css=getComputedStyle(curve),length=curve.getTotalLength(),matrix=curve.getScreenCTM(),dash=parseFloat(css.strokeDasharray),offset=Math.max(0,parseFloat(css.strokeDashoffset)||0),progress=Number.isFinite(dash)&&dash>0?Math.max(0,Math.min(1,1-offset/dash)):1;
     if(!matrix||length<=0||progress<=0)continue;
     for(const label of labels){const b=rect(label);let hit=null;for(let k=0;k<=60;k++){const point=curve.getPointAtLength(length*progress*k/60),painted=new DOMPoint(point.x,point.y).matrixTransform(matrix);if(painted.x>b.x+1&&painted.x<b.x+b.w-1&&painted.y>b.y+1&&painted.y<b.y+b.h-1){hit={x:painted.x,y:painted.y};break;}}
      if(hit)window.__qaV2RouteCrossings.push({scene_id:scene.id,line_id:curve.id,label:label.textContent,label_bbox:b,point:hit,visible_progress:progress,method:'60 samples of currently drawn SVG route over visible text bbox; conservative, not glyph segmentation'});
     }
    }
   }
   return window.__qaV2Subjects.map(d=>{
    const body=d.image_ordinal!==undefined?imageList[d.image_ordinal]:d.body_scene_root?window.__cloneBuilt[d.scene_id]?.context.root:document.getElementById(d.body_id);if(!body)return {...d,missing:true};
    const allLeaves=[...(body.matches('text,image,img,rect,path,circle,ellipse,line')?[body]:[]),...body.querySelectorAll('text,image,img[data-brand-asset],rect,path,circle,ellipse,line')].filter(el=>!el.closest('defs'));
    const leaves=allLeaves.filter(el=>alpha(el)>.001);
    const b=rect(body),clip=clipped(body,b),label=d.label_id?document.getElementById(d.label_id):null;
    const texts=leaves.filter(el=>el.tagName==='text').map(el=>{
     const box=rect(el),m=el.getScreenCTM(),css=getComputedStyle(el),size=parseFloat(css.fontSize)*Math.hypot(m?.c??0,m?.d??1),painted=clipped(el,box);
     const cx=box.x+box.w/2,cy=box.y+box.h/2,svg=el.ownerSVGElement;
     const surfaces=[...svg.querySelectorAll('rect')].filter(r=>!r.closest('defs')&&alpha(r)>.85&&(r.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)).filter(r=>{const q=rect(r);return cx>=q.x&&cx<=q.x+q.w&&cy>=q.y&&cy<=q.y+q.h;});
     const surface=surfaces.at(-1),bg=surface?getComputedStyle(surface).fill:getComputedStyle(document.getElementById('__clone-film')).backgroundColor;
     const foreground=rgb(css.fill),background=rgb(bg),a=alpha(el),blended=foreground&&background?foreground.map((v,i)=>v*a+background[i]*(1-a)):null;
     return{id:el.id,text:el.textContent,bbox:box,visible_fraction:painted.fraction,opacity:a,font_px_1080:size,font_px_360:size/3,fill:css.fill,background:bg,nominal_contrast:contrast(blended,background),is_identity:el===label};
    });
    const images=leaves.filter(el=>el.matches('image,img[data-brand-asset]')).map(el=>{
     const box=rect(el),i=imageList.indexOf(el),identified=window.__qaV2ImageAssets[i],meta=window.CLONE_ASSETS?.[identified?.keys?.[0]];
     let painted=box,method='element_bbox_no_alpha_metadata';
     if(meta?.width&&meta?.height){const nw=meta.width,nh=meta.height,svg=el instanceof SVGElement,fit=getComputedStyle(el).objectFit;
      const contain=svg&&!/none/.test(el.getAttribute('preserveAspectRatio')||'')||!svg&&fit==='contain';
      const sx=box.w/nw,sy=box.h/nh,scale=contain?Math.min(sx,sy):null,x=contain?box.x+(box.w-nw*scale)/2:box.x,y=contain?box.y+(box.h-nh*scale)/2:box.y;
      const ab=meta.alpha_bbox||[0,0,nw,nh];painted={x:x+ab[0]*(scale??sx),y:y+ab[1]*(scale??sy),w:(ab[2]-ab[0])*(scale??sx),h:(ab[3]-ab[1])*(scale??sy)};method=meta.alpha_bbox?'painted_alpha_bbox_with_original_aspect':'original_viewbox_conservative';
     }
     const m=el.getScreenCTM?.(),css=getComputedStyle(el),cssm=!m&&css.transform!=='none'?new DOMMatrix(css.transform):null;
     return{ordinal:i,bbox:box,painted_bbox:painted,measurement:method,visible_fraction:clipped(el,painted).fraction,opacity:alpha(el),alt:el.alt||null,complete:el instanceof HTMLImageElement?el.complete&&el.naturalWidth>0:true,brand_asset:el.dataset.brandAsset||null,brand_entity:el.dataset.brandEntity||null,angle_degrees:m?Math.atan2(m.b,m.a)*180/Math.PI:cssm?Math.atan2(cssm.b,cssm.a)*180/Math.PI:0,filter:css.filter,...identified};});
    return {...d,bbox:b,visible_fraction:clip.fraction,opacity:alpha(body),visible_leaf_count:leaves.length,texts,images,
     pose_state:allLeaves.map(el=>({tag:el.tagName,id:el.id,transform:el.getAttribute('transform'),d:el.tagName==='path'?el.getAttribute('d'):null,text:el.tagName==='text'?el.textContent:null,bbox:rect(el),fill:getComputedStyle(el).fill})),
     scene_clock_exists:!!window.__timelines[d.scene_id]};
   });
  };
 },imageAssets);
 const snapshot=()=>page.evaluate(()=>{
  const alpha=node=>{let a=1;for(let p=node;p&&p.nodeType===1;p=p.parentElement){const s=getComputedStyle(p);if(s.display==='none'||s.visibility==='hidden')return 0;a*=Number(s.opacity);}return a;};
  const box=node=>{const r=node.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height};};
  const clip=node=>{const s=getComputedStyle(node),numbers=(s.clipPath.match(/[-+\d.]+%/g)||[]).map(v=>parseFloat(v)/100);return{css:s.clipPath,top:numbers[0]||0,bottom:numbers[2]??numbers[0]??0};};
  const mask=document.getElementById('integration-camera-mask'),plane=document.getElementById('integration-camera-plane'),viewport=document.getElementById('integration-motion-viewport');
  const video=document.getElementById('integration-camera-video'),image=video.nextElementSibling;
  const backgrounds=window.__qaBackgrounds();
  const revealPauses=(window.__integrationReceipt?.component_overrides||[]).filter(r=>r.reason==='brief_type_pause_during_scene_reveal'),renderTime=CloneTimelineReal(window.__timelines['clone-main']).time();
  const revealPausePoses=revealPauses.filter(r=>renderTime>=r.start-1/30-1e-7&&renderTime<=r.end+1/30+1e-7).map(r=>{
   const n=document.getElementById('integration-text-'+r.text);if(!n)return{...r,missing:true};
   const ctx=document.createElement('canvas').getContext('2d'),bounds=[...n.querySelectorAll('[data-word]')].map(span=>{const range=document.createRange();range.selectNodeContents(span);if(span.firstChild?.nodeType===3)range.setEnd(span.firstChild,span.textContent.trimEnd().length);const b=range.getBoundingClientRect(),css=getComputedStyle(span),sb=box(span);ctx.font=`${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;ctx.letterSpacing=css.letterSpacing==='normal'?'0px':css.letterSpacing;ctx.wordSpacing=css.wordSpacing==='normal'?'0px':css.wordSpacing;const m=ctx.measureText(span.textContent.trimEnd()),base=sb.y+(sb.h+m.fontBoundingBoxAscent-m.fontBoundingBoxDescent)/2;return{index:Number(span.dataset.word),text:span.textContent,foreground:css.color,x:b.x-m.actualBoundingBoxLeft,y:base-m.actualBoundingBoxAscent,w:m.actualBoundingBoxLeft+m.actualBoundingBoxRight,h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent};}).filter(b=>b.w>0&&b.h>0);
   if(!bounds.length)return{...r,missing:true};const x=Math.min(...bounds.map(b=>b.x)),y=Math.min(...bounds.map(b=>b.y)),ink={x,y,w:Math.max(...bounds.map(b=>b.x+b.w))-x,h:Math.max(...bounds.map(b=>b.y+b.h))-y};
   const rgb=css=>{const m=/^rgba?\(([^)]+)\)$/.exec(css);return m?m[1].split(/[, ]+/).filter(Boolean).slice(0,3).map(Number):null;},luma=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   const samples=bounds.flatMap(b=>[0,.5,1].flatMap(fx=>[0,.5,1].map(fy=>{const point={x:b.x+b.w*fx,y:b.y+b.h*fy},surface=backgrounds.surfaceAt(point.x,point.y),fg=rgb(b.foreground),bg=rgb(surface.colour),contrast=fg&&bg?(Math.max(luma(fg),luma(bg))+.05)/(Math.min(luma(fg),luma(bg))+.05):null;return{...point,...surface,word_index:b.index,word:b.text,foreground:b.foreground,contrast};})));
   return{...r,opacity:alpha(n),ink,surfaces:samples,incoming_coverage:samples.filter(s=>s.scene_id===r.scene_id).length/samples.length,composited_surface_legible:samples.every(s=>s.contrast!==null&&s.contrast>=4.5)};
  });
  const texts=[...document.querySelectorAll('#integration-type .integration-text')].filter(n=>alpha(n)>.001).map(n=>{
   const range=document.createRange();range.selectNodeContents(n);const b=range.getBoundingClientRect();
   const ctx=document.createElement('canvas').getContext('2d');
   const words=[...n.querySelectorAll('[data-word]')].map(s=>{const r=document.createRange();r.selectNodeContents(s);if(s.firstChild?.nodeType===3)r.setEnd(s.firstChild,s.textContent.trimEnd().length);const b=r.getBoundingClientRect(),css=getComputedStyle(s),sb=box(s);ctx.font=`${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;ctx.letterSpacing=css.letterSpacing==='normal'?'0px':css.letterSpacing;ctx.wordSpacing=css.wordSpacing==='normal'?'0px':css.wordSpacing;const m=ctx.measureText(s.textContent.trimEnd());
    // DOM Range includes the font's ascent/descent, not the painted glyphs.
    // Derive the baseline from this actual inline box and the loaded font.
    const baseline=sb.y+(sb.h+m.fontBoundingBoxAscent-m.fontBoundingBoxDescent)/2;
    const brand=s.querySelector('img[data-brand-asset]'),brandBox=brand?box(brand):null;
    let paintedInk=brandBox||{x:b.x-m.actualBoundingBoxLeft,y:baseline-m.actualBoundingBoxAscent,w:m.actualBoundingBoxLeft+m.actualBoundingBoxRight,h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent};
    if(brand&&s.textContent.trim()){
     const boxes=[brandBox],walker=document.createTreeWalker(s,NodeFilter.SHOW_TEXT);let node;
     while(node=walker.nextNode())if(node.textContent.trim()){const q=document.createRange();q.selectNodeContents(node);q.setEnd(node,node.textContent.trimEnd().length);const tb=q.getBoundingClientRect(),v=ctx.measureText(node.textContent.trimEnd()),base=tb.y+(tb.height+v.fontBoundingBoxAscent-v.fontBoundingBoxDescent)/2;boxes.push({x:tb.x-v.actualBoundingBoxLeft,y:base-v.actualBoundingBoxAscent,w:v.actualBoundingBoxLeft+v.actualBoundingBoxRight,h:v.actualBoundingBoxAscent+v.actualBoundingBoxDescent});}
     const left=Math.min(...boxes.map(v=>v.x)),top=Math.min(...boxes.map(v=>v.y));paintedInk={x:left,y:top,w:Math.max(...boxes.map(v=>v.x+v.w))-left,h:Math.max(...boxes.map(v=>v.y+v.h))-top};
    }
    const surfaceColour=css.backgroundColor,hasPlate=surfaceColour!=='transparent'&&surfaceColour!=='rgba(0, 0, 0, 0)';
    const semantic=brand&&s.textContent.trim()&&s.textContent.toLowerCase().includes(brand.alt.toLowerCase())?s.textContent:(brand?.alt||'')+s.textContent;
    return{index:Number(s.dataset.word),text:semantic,color:getComputedStyle(s).color,background:backgrounds.at(paintedInk.x+paintedInk.w/2,paintedInk.y+paintedInk.h/2),opacity:alpha(s),bbox:sb,ink:brandBox||{x:b.x,y:b.y,w:b.width,h:b.height},paintedInk,brand_asset:brand?.dataset.brandAsset||null,brand_surface_bbox:brand&&hasPlate?sb:null,brand_complete:brand?brand.complete&&brand.naturalWidth>0:null,whiteSpace:css.whiteSpace};});
   const painted=words.filter(w=>w.opacity>.001).map(w=>w.paintedInk),x=Math.min(...painted.map(w=>w.x)),y=Math.min(...painted.map(w=>w.y));
   const paintedInk=painted.length?{x,y,w:Math.max(...painted.map(w=>w.x+w.w))-x,h:Math.max(...painted.map(w=>w.y+w.h))-y}:null;
   return{id:n.id,text:n.textContent,bbox:box(n),ink:{x:b.x,y:b.y,w:b.width,h:b.height},paintedInk,opacity:alpha(n),font:getComputedStyle(n).fontFamily,size:parseFloat(getComputedStyle(n).fontSize),shadow:getComputedStyle(n).textShadow,color:getComputedStyle(n).color,words};});
  const pausedChain=tl=>{let any=false,p=CloneTimelineReal(tl),seen=new Set();while(p&&!seen.has(p)){seen.add(p);any||=p.paused?.()===true;p=p.parent;}return any;};
  const native=[...document.querySelectorAll('svg text')].filter(n=>alpha(n)>.001).map(n=>({text:n.textContent,bbox:box(n)}));
  const obstacles=[];
  for(const scene of window.CLONE_INTEGRATION.scenes){const C=window.__cloneBuilt[scene.id]?.context;if(!C)continue;for(const el of C.root.querySelectorAll('svg rect,svg image,svg text')){
   if(el.closest('defs')||alpha(el)<.85)continue;
   if(el.tagName==='rect'&&Number(el.getAttribute('width'))>=710&&Number(el.getAttribute('height'))>=1270)continue;
   const b=box(el);if(b.w<12||b.h<12)continue;
   const vp=box(viewport),vc=clip(viewport),out={x:Math.max(b.x,0,vp.x),y:Math.max(b.y,0,vp.y+vp.h*vc.top),right:Math.min(b.x+b.w,1080,vp.x+vp.w),bottom:Math.min(b.y+b.h,1920,vp.y+vp.h*(1-vc.bottom))};
   if(el.closest('#integration-motion-viewport')&&Number(getComputedStyle(mask).opacity)>.95)out.bottom=Math.min(out.bottom,box(mask).y+box(mask).h*clip(mask).top);
   if(out.right<=out.x||out.bottom<=out.y||backgrounds.covered(el,{x:out.x,y:out.y,w:out.right-out.x,h:out.bottom-out.y}))continue;
   const obstacleBox={x:out.x,y:out.y,w:out.right-out.x,h:out.bottom-out.y},occluded_words=[];
   for(const text of texts)for(const word of text.words.filter(w=>w.opacity>=.85&&w.paintedInk?.w>0)){const b=word.paintedInk,x=Math.max(b.x,obstacleBox.x),y=Math.max(b.y,obstacleBox.y),right=Math.min(b.x+b.w,obstacleBox.x+obstacleBox.w),bottom=Math.min(b.y+b.h,obstacleBox.y+obstacleBox.h);if(right>x&&bottom>y&&backgrounds.covered(el,{x,y,w:right-x,h:bottom-y}))occluded_words.push(text.id+':'+word.index);}
   obstacles.push({id:el.id||null,scene_id:scene.id,tag:el.tagName,bbox:obstacleBox,occluded_words,fill:getComputedStyle(el).fill,text:el.tagName==='text'?el.textContent:null});
  }}
  return{time:CloneTimelineReal(window.__timelines['clone-main']).time(),ids:[...document.querySelectorAll('[id]')].map(n=>n.id),clockPaused:pausedChain(window.__timelines['clone-main']),
   camera:{opacity:Number(getComputedStyle(mask).opacity),clip:clip(mask),mask:box(mask),plane:box(plane),video:box(video),videoTime:video.currentTime,videoSrc:video.getAttribute('src'),sourceStart:video.getAttribute('data-media-start'),playbackRate:video.getAttribute('data-playback-rate'),
    injected:image?.classList.contains('__render_frame__')?{bbox:box(image),opacity:alpha(image),src:image.getAttribute('src'),complete:image.complete,width:image.naturalWidth,height:image.naturalHeight}:null,
    filters:[mask,plane,video].map(n=>({filter:getComputedStyle(n).filter,backdrop:getComputedStyle(n).backdropFilter})),videoCount:document.querySelectorAll('video').length},
   motion:{viewport:box(viewport),clip:clip(viewport),background:getComputedStyle(document.getElementById('__clone-film')).backgroundColor,effective_solid_background_at_center:backgrounds.surfaceAt(540,960),solid_surfaces:backgrounds.candidates},texts,native,obstacles,subjects:window.__qaV2Measure(),internal_notes:window.__qaV2InternalNotes,route_label_crossings:window.__qaV2RouteCrossings,
   editorial_suppression:[...document.querySelectorAll('g[data-hook-suppressed="source_caption_owns_literal_editorial_goal"]')].map(g=>({id:g.id,opacity:alpha(g),child_ids:[...g.children].map(child=>child.id),text:[...g.querySelectorAll('text')].map(text=>[...text.querySelectorAll('tspan')].length?[...text.querySelectorAll('tspan')].map(span=>span.textContent).join(' '):text.textContent).join(' ')})),scene_reveal_pause_poses:revealPausePoses,receipt:window.__integrationReceipt};
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
 const proofTimes=[...new Set([0,.5,1,2,3,3.5,6.7,11.8,14.8,18.4,21,25.6,29,31.6,36.5,40.8,45.9,49.7,FRAME_COUNT/FPS-1/FPS,...dir.camera_windows.map(w=>(w.start_frame+w.end_frame)/2/FPS)])].filter(t=>t>=0&&t<FRAME_COUNT/FPS);
 const quickTimes=new Set([0,...proofTimes]);
 for(const scene of cfg.scenes)for(const boundary of [Math.round(scene.start*FPS),Math.round((scene.start+scene.duration)*FPS)])for(let delta=-3;delta<=3;delta++){const f=boundary+delta;if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);}
 for(let frame=0;frame<=Math.min(FRAME_COUNT-1,75);frame++)quickTimes.add(frame/FPS);
 for(const window of dir.focus_windows||[])for(const f of Array.from({length:10},(_,i)=>window.start_frame-1+i))if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);
 for(const block of dir.hook_blocks||[])for(const f of Array.from({length:9},(_,i)=>block.start_frame-1+i))if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);
 for(const w of dir.camera_windows)for(const f of [w.start_frame-1,w.start_frame,w.start_frame+1,w.start_frame+w.transition_frames-1,w.start_frame+w.transition_frames,w.end_frame-w.exit_frames-1,w.end_frame-w.exit_frames,w.end_frame-1,w.end_frame,w.end_frame+1])if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);
 for(const w of narration.words)quickTimes.add(Math.max(0,Math.min(FRAME_COUNT-1,Math.round((w.start+w.end)/2*FPS)))/FPS);
 const declaredRevealPauses=await page.evaluate(()=>(window.__integrationReceipt?.component_overrides||[]).filter(r=>r.reason==='brief_type_pause_during_scene_reveal'));
 for(const pause of declaredRevealPauses)for(let f=Math.floor(pause.start*FPS)-1;f<=Math.ceil(pause.end*FPS)+1;f++)if(f>=0&&f<FRAME_COUNT)quickTimes.add(f/FPS);
 for(const pause of declaredRevealPauses)for(const t of [pause.start,pause.end])if(t>=0&&t<FRAME_COUNT/FPS&&!proofTimes.includes(t))proofTimes.push(t);
 // A midpoint may fall inside an explicit composition pause. Check every
 // native frame spoken after the hook, so the pause cannot hide a lost word.
 const plannedHookEnd=Math.max(0,...(dir.hook_blocks||[]).map(b=>b.end_frame/FPS));
 // Quick checks boundaries/midpoints; only the final run covers every frame.
 if(!QUICK)for(const w of narration.words)if(w.end>plannedHookEnd+1e-7)for(let f=Math.ceil(Math.max(w.start,plannedHookEnd)*FPS-1e-7);f<Math.ceil(w.end*FPS-1e-7)&&f<FRAME_COUNT;f++)quickTimes.add(f/FPS);
 const times=QUICK?[...quickTimes].sort((a,b)=>a-b):Array.from({length:FRAME_COUNT},(_,f)=>f/FPS),forward=new Map();
 for(const t of times){const state=await seek(t);detailed.forward.push({t,state});forward.set(t,state);}
 const observable=s=>JSON.stringify({time:s.time,camera:s.camera,motion:s.motion,texts:s.texts,native:s.native,subjects:s.subjects});
 const reverseDifferences=[];
 for(const t of [...times].reverse()){const state=await seek(t);detailed.reverse.push({t,state});if(observable(state)!==observable(forward.get(t)))reverseDifferences.push(t);}
 const unordered=[FRAME_COUNT/FPS-1/FPS,.5,25.6,14.8,45.9,1,31.6,0,21,6.7].filter(t=>t<FRAME_COUNT/FPS);
 const unorderedDifferences=[];
 for(const t of unordered){const a=await seek(t),b=await seek(0),c=await seek(t);detailed.unordered.push({t,state:a});if(observable(a)!==observable(c))unorderedDifferences.push(t);}
 const runFrames=[];let run=null;
 const cameraGeometry=[],captions=[],micWarnings=[],stableFaceGeometry=[];
 const interpolate=(pairs,t,key)=>{let i=0;while(i<pairs.length-2&&pairs[i+1].t<t)i++;const a=pairs[i],b=pairs[Math.min(i+1,pairs.length-1)];if(a.segment_id!==b.segment_id)return t<b.t?a[key]:b[key];const u=b.t===a.t?0:Math.min(1,Math.max(0,(t-a.t)/(b.t-a.t)));return a[key]+(b[key]-a[key])*u;};
 const chins=face.anchors.filter(a=>!a.missing).map(a=>({t:a.t,segment_id:a.segment_id,chin:a.source_normalized.smooth_chin[1]*1920}));
 const faceBoxAnchors=face.anchors.filter(a=>!a.missing).map(a=>{const [x,y,right,bottom]=a.source_normalized.bbox;return{t:a.t,segment_id:a.segment_id,x:x*1080,y:y*1920,w:(right-x)*1080,h:(bottom-y)*1920};});
 // A camera body can remain visible after its face has left the mask. Apply
 // the face-relative caption contract only to the actual clipped face region.
 // Keep the stricter full body/transition budget for presenter presence.
 const visibleFace=(s,t)=>{const scale=s.camera.video.w/1080,raw={x:interpolate(faceBoxAnchors,t,'x')*scale+s.camera.video.x,y:interpolate(faceBoxAnchors,t,'y')*scale+s.camera.video.y,w:interpolate(faceBoxAnchors,t,'w')*scale,h:interpolate(faceBoxAnchors,t,'h')*scale},m=s.camera.mask,x=Math.max(0,raw.x,m.x),y=Math.max(0,raw.y,m.y+m.h*s.camera.clip.top),right=Math.min(1080,raw.x+raw.w,m.x+m.w),bottom=Math.min(1920,raw.y+raw.h,m.y+m.h*(1-s.camera.clip.bottom));return{x,y,w:Math.max(0,right-x),h:Math.max(0,bottom-y),opacity:s.camera.opacity};};
 const overlaps=(a,b)=>Math.min(a.x+a.w,b.x+b.w)>Math.max(a.x,b.x)&&Math.min(a.y+a.h,b.y+b.h)>Math.max(a.y,b.y);
 const visualPath=path.join(folder,'VISUAL_QA.json');const mic=(fs.existsSync(visualPath)?read(visualPath).source_microphone_bbox:null)||face.source_microphone_bbox;
 const micBox=mic?.source_bbox_xyxy;
 for(const {t,state:s}of detailed.forward){
  const visible=s.camera.opacity>.001&&s.camera.clip.top<.999;
  const f=Math.round(t*FPS);if(visible&&!run)run={start_frame:f,end_frame:f+1};else if(visible)run.end_frame=f+1;else if(run){runFrames.push(run);run=null;}
  const window=dir.camera_windows.find(w=>f>=w.start_frame&&f<w.end_frame),stable=window&&f>=window.start_frame+window.transition_frames&&f<window.end_frame-window.exit_frames;
  if(stable&&window.state==='split')cameraGeometry.push({t,top:s.camera.clip.top,motionBottom:s.motion.clip.bottom,video:s.camera.video,plane:s.camera.plane,expectedTop:window.split_top??dir.split_top??cfg.split.upper});
  const faceRegion=visibleFace(s,t);
  if(stable&&s.camera.opacity>.99){const scale=s.camera.video.w/1080,full={x:interpolate(faceBoxAnchors,t,'x')*scale+s.camera.video.x,y:interpolate(faceBoxAnchors,t,'y')*scale+s.camera.video.y,w:interpolate(faceBoxAnchors,t,'w')*scale,h:interpolate(faceBoxAnchors,t,'h')*scale};stableFaceGeometry.push({frame:f,mode:window.state,source_face_bbox:full,visible_face_bbox:faceRegion,visible_fraction:full.w*full.h?faceRegion.w*faceRegion.h/(full.w*full.h):0});}
  if(visible&&faceRegion.w>0&&faceRegion.h>0){
   const videoScale=s.camera.video.w/1080;const expected=interpolate(chins,Math.round(t*FPS)/FPS,'chin')*videoScale+s.camera.video.y;
   for(const text of s.texts){const block=dir.caption_blocks.find(b=>'integration-text-'+b.id===text.id);if(!block)continue;
    if(!text.paintedInk)continue;captions.push({t,text:text.text,expected_font:block.font||'Sequel',center:text.ink.x+text.ink.w/2,ink_center:text.paintedInk.x+text.paintedInk.w/2,all_words_visible:text.words.every(w=>w.opacity>.001),centering_basis:'avance tipográfico del bloque tradicional completo realmente visible; bearings de cursiva registrados por separado',gap:text.paintedInk.y-expected,bbox:text.paintedInk,range_bbox:text.ink,shadow:text.shadow,font:text.font,size:text.size,expected_chin_y:expected,camera_scale:videoScale,camera_mode:window?.state||'transition'});
    if(micBox){const [x,y,x2,y2]=micBox,rect={x:s.camera.video.x+x*videoScale,y:s.camera.video.y+y*videoScale,w:(x2-x)*videoScale,h:(y2-y)*videoScale};if(overlaps(text.paintedInk,rect))micWarnings.push({t,text:text.text,bbox:text.paintedInk,mic_bbox:rect});}
   }
  }
 }
 if(run)runFrames.push(run);
 const maxRun=Math.max(0,...runFrames.map(w=>w.end_frame-w.start_frame));
 const expectedFrames=new Set(dir.camera_windows.flatMap(w=>Array.from({length:w.end_frame-w.start_frame},(_,i)=>w.start_frame+i)));
 const observedFrames=new Set(runFrames.flatMap(w=>Array.from({length:w.end_frame-w.start_frame},(_,i)=>w.start_frame+i)));
 const hook=dir.hook_blocks||[],prefixes=hook.map(b=>narration.words.slice(b.word_start,b.word_end+1).map(w=>w.text).join(' '));
 const hookGroups=Object.groupBy(hook,b=>b.sequence||b.id);
 const grows=Object.values(hookGroups).every(group=>group[0].word_end>group[0].word_start||group.length>=2&&group.every((b,i)=>!i||b.word_start===group[i-1].word_start&&b.word_end>group[i-1].word_end));
 const hookPaintedStages=Object.values(hookGroups).map(group=>{const id='integration-text-'+group[0].id,stages=[];
  for(const pose of detailed.forward){const text=pose.state.texts.find(n=>n.id===id);if(text){const indices=text.words.filter(w=>w.opacity>.01).map(w=>w.index);if(indices.length&&!stages.some(s=>JSON.stringify(s)===JSON.stringify(indices)))stages.push(indices);}}
  return {sequence:group[0].sequence||group[0].id,stages};});
 const hookIds=new Set(Object.values(hookGroups).map(g=>'integration-text-'+g[0].id));
 const hookCenters=detailed.forward.flatMap(({t,state:s})=>s.texts.filter(n=>hookIds.has(n.id)&&n.paintedInk&&n.opacity>.85).map(n=>({frame:Math.floor(t*FPS+1e-7),id:n.id,visible_word_indices:n.words.filter(w=>w.opacity>.85).map(w=>w.index),ink_center_x:n.paintedInk.x+n.paintedInk.w/2,ink_bbox:n.paintedInk})));
 const hookEnd=Math.max(0,...hook.map(b=>b.end_frame/FPS));
 const missingWords=[],documentedPauses=[];
 const pauses=(detailed.forward[0].state.receipt.component_overrides||[]).filter(r=>['brief_type_pause_during_camera_reveal','brief_type_pause_during_scene_reveal'].includes(r.reason));
 const wordPause=(pause,index,t)=>pause.end-pause.start<=.201&&t>=pause.start-1e-7&&t<=pause.end+1e-7&&dir.caption_blocks.some(block=>block.id===pause.text&&index>=block.word_start&&index<=block.word_end);
 for(const [i,w]of narration.words.entries())if(w.end>hookEnd+1e-7){const poses=detailed.forward.filter(p=>p.t>=Math.max(w.start,hookEnd)-1e-7&&p.t<w.end-1e-7);
  const present=poses.filter(p=>p.state.texts.some(n=>n.words.some(x=>x.index===i&&x.opacity>.01))),absent=poses.filter(p=>!present.includes(p));
  const accounted=absent.every(p=>pauses.some(r=>wordPause(r,i,p.t)));
  if(!present.length||!accounted)missingWords.push({index:i,text:w.text,start:w.start,end:w.end,visible_frames:present.map(p=>Math.round(p.t*FPS)),unaccounted_frames:absent.filter(p=>!pauses.some(r=>wordPause(r,i,p.t))).map(p=>Math.round(p.t*FPS))});
  else if(absent.length)documentedPauses.push({index:i,text:w.text,visible_frames:present.map(p=>Math.round(p.t*FPS)),paused_frames:absent.map(p=>Math.round(p.t*FPS)),reasons:[...new Set(absent.flatMap(p=>pauses.filter(r=>wordPause(r,i,p.t)).map(r=>r.reason)))]});
 }
 const spacing=[];
 for(const {t,state:s}of detailed.forward)for(const text of s.texts)for(let i=1;i<text.words.length;i++){const a=text.words[i-1],b=text.words[i];if(a.opacity>.85&&b.opacity>.85&&a.ink.w>0&&b.ink.w>0&&Math.abs(a.ink.y-b.ink.y)<2)spacing.push({t,text:text.text,gap:b.ink.x-(a.ink.x+a.ink.w)});}
 report.checks={runtime_ready:true,no_runtime_errors:report.errors.length===0,unique_ids:detailed.forward.every(({state:s})=>new Set(s.ids).size===s.ids.length),clock_seek_exact:detailed.forward.every(({t,state:s})=>Math.abs(Math.floor(t*FPS+1e-7)/FPS-s.time)<1e-5),clock_effectively_paused:detailed.forward.every(({state:s})=>s.clockPaused),
  source_frame_injected:detailed.forward.every(({t,state:s})=>s.camera.injected?.source_index===Math.min(FRAME_COUNT-1,Math.floor(t*FPS+1e-7))&&s.camera.injected.complete&&s.camera.injected.width===1080&&s.camera.injected.height===1920),
  source_timing_unchanged:detailed.forward.every(({state:s})=>Number(s.camera.sourceStart)===0&&(!s.camera.playbackRate||Number(s.camera.playbackRate)===1)),
  camera_continuous_limit:maxRun<=90,camera_within_declared_frames:[...detailed.forward].filter(p=>p.state.camera.opacity>.001&&p.state.camera.clip.top<.999).every(p=>expectedFrames.has(Math.round(p.t*FPS))),
  full_camera_stable_pose:dir.camera_windows.filter(w=>w.state==='full').every(w=>detailed.forward.filter(p=>p.t>=(w.start_frame+w.transition_frames)/FPS&&p.t<(w.end_frame-w.exit_frames)/FPS).every(p=>p.state.camera.opacity>.001&&p.state.camera.clip.top<.001)),
  split_ratio_native_aspect:cameraGeometry.length>0&&cameraGeometry.every(s=>Math.abs(s.top-s.expectedTop)<.001&&Math.abs(s.motionBottom-(1-s.expectedTop))<.001&&Math.abs(s.video.w/s.video.h-1080/1920)<1e-6&&s.video.w>=1080-.01),
  no_added_blur_or_duplicated_video:detailed.forward.every(({state:s})=>s.camera.videoCount===1&&s.camera.filters.every(f=>f.filter==='none'&&f.backdrop==='none')),
  captions_centered:captions.every(c=>c.all_words_visible&&Math.abs(c.center-540)<2),captions_below_chin:captions.every(c=>c.gap>=0&&c.gap<120),captions_inside_frame:captions.every(c=>c.bbox.x>=0&&c.bbox.x+c.bbox.w<=1080&&c.bbox.y+c.bbox.h<=1920),
  hook_phrases_grow:grows&&hookPaintedStages.every(g=>g.stages.length>=2&&g.stages.every((stage,i)=>!i||stage.length>=g.stages[i-1].length&&g.stages[i-1].every((word,j)=>stage[j]===word))),text_after_hook_covered:missingWords.length===0,
  reverse_states_equal:reverseDifferences.length===0,unordered_states_equal:unorderedDifferences.length===0};
 report.metrics={source_pixel_binding:sourcePixels,expected_brand_assets:[...expectedBrandAssets],tracking_segments:face.segments||[],tracking_resets:face.tracking_resets||[],camera_modes_exercised:Object.fromEntries(['full','split'].map(mode=>[mode,dir.camera_windows.filter(w=>w.state===mode).length])),sampled_poses:times.length,clock_policy:'seek real cuantizado al frame inferior a 30 FPS; tolerancia numérica 1e-5 s',caption_horizontal_measurement:'Centro del avance tipográfico de todos los spans visibles; tolerancia2px. Se conserva el centro de tinta y sus bearings, sin tratar la cursiva Scholar como fuente equivocada.',caption_vertical_measurement:'Tinta mediante metrics de fuente cargada y baseline inline real; Range conserva la medición horizontal. El contrato bajo barbilla se mide solo mientras el bbox facial está dentro de la máscara real, no durante una cola de cámara con cuerpo sin rostro.',camera_counting:QUICK?'Muestras puntuales; no recuento completo de presencia.':'Cada fotograma de la fuente.',camera_runs:QUICK?null:runFrames,max_continuous_frames:QUICK?null:maxRun,total_visible_frames:QUICK?null:observedFrames.size,declared_camera_frames:expectedFrames.size,presence_fraction:QUICK?null:observedFrames.size/FRAME_COUNT,split_samples:cameraGeometry.length,caption_samples:captions.length,caption_measurements:captions.filter((_,i)=>i%5===0),hook_prefixes:prefixes,hook_painted_stages:hookPaintedStages,hook_visible_ink_centers:hookCenters.filter((_,i)=>i%4===0),traditional_captions_with_presenter_exercised:captions.length>0,missing_words:missingWords,documented_pauses:documentedPauses,reverse_differences:reverseDifferences,unordered_differences:unorderedDifferences,word_spacing_min:Math.min(...spacing.map(p=>p.gap)),mic_intersections:micWarnings.slice(0,12)};
 // An editorial duplicate may be suppressed only when the actual spoken
 // phrase and mounted captions own it. A plan entry alone is not visibility.
 const literalTokens=text=>String(text||'').normalize('NFC').toLocaleLowerCase('es').match(/[\p{L}\p{N}]+/gu)||[];
 const dedupRecords=(detailed.forward[0].state.receipt.component_overrides||[]).flatMap(parent=>(parent.changes||[]).filter(change=>change.override==='source_caption_owns_literal_editorial_goal').map(change=>({scene_id:parent.scene_id,...change})));
 const dedupRows=dedupRecords.map(record=>{
  const scene=cfg.scenes.find(s=>s.id===record.scene_id),anchors=record.anchors||[],tokens=literalTokens(record.phrase);
  const words=anchors.map(anchor=>{const source=narration.words[anchor.word_index],poses=detailed.forward.filter(p=>p.t>=source?.start-1e-7&&p.t<source?.end-1e-7),present=poses.filter(p=>p.state.texts.some(text=>text.words.some(word=>word.index===anchor.word_index&&word.opacity>.01&&word.paintedInk?.w>0)));return{...anchor,source_matches:!!source&&source.text===anchor.text&&source.start===anchor.start&&source.end===anchor.end,caption_mounted_visible_frames:present.map(p=>Math.round(p.t*FPS)),checked_spoken_frames:poses.length};});
  const gates=detailed.forward.map(p=>p.state.editorial_suppression.find(g=>g.id===record.gate));
  const hidden_only_original_goal=gates.every(g=>g&&g.opacity===0&&g.child_ids.length===1&&g.child_ids[0]===record.target&&JSON.stringify(literalTokens(g.text))===JSON.stringify(tokens));
  const confined=!!scene&&cfg.profile==='production_complete'&&scene.family==='spotlight_agent'&&scene.start>=dir.hook_end_frame/FPS&&tokens.length>=3&&JSON.stringify(literalTokens(scene.params.goal))===JSON.stringify(tokens);
  const consecutive_literal=anchors.length===tokens.length&&anchors.every((anchor,i)=>!i||anchor.word_index===anchors[i-1].word_index+1)&&JSON.stringify(anchors.flatMap(a=>literalTokens(a.text)))===JSON.stringify(tokens);
  const actual_caption_coverage=words.every(word=>word.source_matches&&word.checked_spoken_frames>0&&word.caption_mounted_visible_frames.length>0&&!missingWords.some(w=>w.index===word.word_index));
  return{scene_id:record.scene_id,phrase:record.phrase,target:record.target,gate:record.gate,confined,consecutive_literal,hidden_only_original_goal,actual_caption_coverage,words};
 });
 const gatesCount=detailed.forward[0].state.editorial_suppression.length;
 report.metrics.literal_editorial_deduplication={scope:'Sólo objetivo editorial literal de Spotlight después del hook; se comprueban fuente, gate exclusivo y presencia real de sus palabras. No aplica a comandos, campos ni resultados de interfaces.',instances:dedupRows};
 report.checks.editorial_deduplication_preserves_spoken_words=gatesCount===dedupRecords.length&&dedupRows.every(row=>row.confined&&row.consecutive_literal&&row.hidden_only_original_goal&&row.actual_caption_coverage);
 const revealPauseRows=declaredRevealPauses.map(record=>{
  const scene=cfg.scenes.find(s=>s.id===record.scene_id),block=dir.caption_blocks.find(b=>b.id===record.text);
  const poses=detailed.forward.flatMap(p=>p.state.scene_reveal_pause_poses.filter(r=>r.text===record.text&&r.scene_id===record.scene_id).map(r=>({frame:Math.round(p.t*FPS),t:p.t,...r})));
  const within=poses.filter(p=>p.t>=record.start-1e-7&&p.t<record.end-1e-7),restored=poses.find(p=>p.t>=record.end-1e-7&&p.opacity>=.85);
  const affected=narration.words.flatMap((word,index)=>word.start<record.end&&word.end>record.start?[{index,text:word.text,start:word.start,end:word.end}]:[]).map(word=>({...word,legible_frames:detailed.forward.filter(p=>p.t>=word.start-1e-7&&p.t<word.end-1e-7&&p.state.texts.some(text=>text.words.some(w=>w.index===word.index&&w.opacity>=.85&&w.paintedInk?.w>0))).map(p=>Math.round(p.t*FPS))}));
  const temporal_contract=!!scene&&!!block&&record.end>record.start&&record.end-record.start<=.201&&record.start>=scene.start-1e-7&&record.start<=scene.start+1/FPS+1e-7&&record.end<block.end_frame/FPS&&record.end<=scene.start+.201+1e-7;
  const actual_reveal=within.length>0&&within.some(p=>!p.composited_surface_legible)&&!!restored&&restored.composited_surface_legible===true;
  const hidden_during_unsafe_interval=within.every(p=>!p.missing&&p.opacity<=.001);
  const no_spoken_word_lost=affected.length>0&&affected.every(word=>word.legible_frames.length>0&&!missingWords.some(w=>w.index===word.index));
  const earliestCovered=poses.find(p=>p.t>=record.start-1e-7&&p.composited_surface_legible===true);
  return{scene_id:record.scene_id,text:record.text,start:record.start,end:record.end,temporal_contract,actual_reveal,hidden_during_unsafe_interval,no_spoken_word_lost,first_measured_legible_surface_frame:earliestCovered?.frame??null,restored_frame:restored?.frame??null,legible_but_still_paused_frames:within.filter(p=>p.composited_surface_legible).map(p=>p.frame),affected_words:affected,poses,method:'9 puntos por bbox de tinta de cada palabra con fuentes cargadas y fondos SVG opacos realmente pintados, clips/transformaciones actuales; el film real es superficie válida donde no lo cubre un fondo opaco. Contraste >=4,5 en cada punto al restaurarse. No segmenta glifos ni aprueba estética.'};
 });
 report.metrics.scene_reveal_type_pauses=revealPauseRows;
 report.checks.scene_reveal_pauses_bounded_and_words_preserved=revealPauseRows.every(row=>row.temporal_contract&&row.actual_reveal&&row.hidden_during_unsafe_interval&&row.no_spoken_word_lost);
 const series=new Map();
 for(const {t,state:s}of detailed.forward)for(const subject of s.subjects){if(!series.has(subject.key))series.set(subject.key,[]);series.get(subject.key).push({frame:Math.floor(t*FPS+1e-7),t,subject});}
 const runs=(rows,predicate)=>{const out=[];for(const row of rows){if(!predicate(row))continue;const f=row.frame;if(out.length&&out.at(-1).end_frame===f)out.at(-1).end_frame=f+1;else out.push({start_frame:f,end_frame:f+1});}return out.map(r=>({...r,start:r.start_frame/FPS,end:r.end_frame/FPS,duration:(r.end_frame-r.start_frame)/FPS}));};
 const durations=r=>({total:r.reduce((a,b)=>a+b.duration,0),max:Math.max(0,...r.map(v=>v.duration)),runs:r});
 const subjects=[],brandObservations=[],familyObservations={};
 for(const [key,rows]of series){
  const descriptor=rows[0].subject;let previous=null;
  for(const row of rows){const s=row.subject,b=s.bbox,prev=previous;
   row.present=!s.missing&&s.opacity>.01&&s.visible_fraction>.15&&s.visible_leaf_count>0;
   row.speed_frame_width_per_second=prev?.subject.bbox&&b&&row.frame===prev.frame+1?Math.hypot(b.x+b.w/2-prev.subject.bbox.x-prev.subject.bbox.w/2,b.y+b.h/2-prev.subject.bbox.y-prev.subject.bbox.h/2)*FPS/1080:null;
   row.identity_texts=s.texts?.filter(v=>(v.is_identity||!s.label_id||v.text.trim().toLocaleLowerCase()===s.label?.trim().toLocaleLowerCase())&&v.opacity>=.85&&v.visible_fraction>=.9)||[];
   const readableText=row.identity_texts.some(v=>v.font_px_1080>=32&&v.nominal_contrast!==null&&v.nominal_contrast>=4.5);
   const readableImage=(s.images||[]).some(v=>v.complete&&v.opacity>=.85&&v.visible_fraction>=.9&&v.painted_bbox.w>=72&&v.painted_bbox.h>=36&&v.sha256&&v.keys.length);
   row.readable=row.present&&s.opacity>=.85&&(readableText||readableImage);
   row.settled_readable=row.readable&&(row.speed_frame_width_per_second===null||row.speed_frame_width_per_second<=.2);
   previous=row;
   for(const image of s.images||[])if(image.opacity>.01&&image.visible_fraction>.15)for(const assetKey of image.keys){const asset=brandRegistry.assets[assetKey];if(asset)brandObservations.push({frame:row.frame,subject:key,asset:assetKey,brand:asset.brand,sha256:image.sha256,complete:image.complete,opacity:image.opacity,visible_fraction:image.visible_fraction,painted_bbox:image.painted_bbox,angle_degrees:image.angle_degrees,filter:image.filter,readable:image.opacity>=.85&&image.visible_fraction>=.9&&image.painted_bbox.w>=72&&image.painted_bbox.h>=36});}
  }
  const present=durations(runs(rows,r=>r.present)),readable=durations(runs(rows,r=>r.readable)),settled=durations(runs(rows,r=>r.settled_readable));
  const firstReadable=rows.find(r=>r.readable)?.frame,lastReadable=rows.findLast(r=>r.readable)?.frame,firstPresent=rows.find(r=>r.present)?.frame,lastPresent=rows.findLast(r=>r.present)?.frame;
  const texts=rows.flatMap(r=>r.identity_texts),ratios=texts.map(v=>v.nominal_contrast).filter(Number.isFinite),sizes=texts.map(v=>v.font_px_1080);
  const named=(descriptor.label||'').toLowerCase(),spoken=narration.words.filter(w=>named.includes(w.text.toLowerCase().replace(/[,.;:]/g,''))&&w.text.length>2),spokenDuration=spoken.reduce((a,w)=>a+w.end-w.start,0);
  const dwellAssessment=QUICK?'pending_all_frames':readable.max>=.7?'within_or_above_orientative_hold':readable.total>=.7?'accumulated_visibility_review':spokenDuration>0&&spokenDuration<.7&&readable.max>=Math.max(.2,spokenDuration-.1)?'short_voice_hit_requires_semantic_retention_review':'insufficient_readable_hold_review';
  const appearances=present.runs.map(run=>{const part=rows.filter(r=>r.frame>=run.start_frame&&r.frame<run.end_frame),readPart=durations(runs(part,r=>r.readable)),settledPart=durations(runs(part,r=>r.settled_readable)),first=part.find(r=>r.readable)?.frame,last=part.findLast(r=>r.readable)?.frame;return{...run,entry_until_readable:first===undefined?null:(first-run.start_frame)/FPS,readable:readPart,settled_readable:settledPart,transform_while_readable_seconds:Math.max(0,readPart.total-settledPart.total),exit_after_readable:last===undefined?null:(run.end_frame-1-last)/FPS};});
  subjects.push({key,appearances,family:descriptor.family,scene_id:descriptor.scene_id,label:descriptor.label,kind:descriptor.kind,presence:present,legible_presence:readable,settled_legible_presence:settled,entry_until_first_readable_seconds:firstReadable!==undefined&&firstPresent!==undefined?(firstReadable-firstPresent)/FPS:null,exit_after_last_readable_seconds:lastReadable!==undefined&&lastPresent!==undefined?(lastPresent-lastReadable)/FPS:null,in_motion_while_readable_seconds:Math.max(0,readable.total-settled.total),identity_font_px_1080:sizes.length?{min:Math.min(...sizes),max:Math.max(...sizes)}:null,identity_font_px_360:sizes.length?{min:Math.min(...sizes)/3,max:Math.max(...sizes)/3}:null,nominal_text_contrast:ratios.length?{min:Math.min(...ratios),max:Math.max(...ratios)}:null,dwell_assessment:dwellAssessment,spoken_duration:spokenDuration,reading_time_is_orientative:true});
  if(descriptor.family!=='YO_hook'){const f=familyObservations[descriptor.scene_id]||={family:descriptor.family,visible_frames:new Set(),pose_states:new Set(),registered:true};for(const r of rows){f.registered&&=r.subject.scene_clock_exists;if(r.present){f.visible_frames.add(r.frame);f.pose_states.add(hash(JSON.stringify(r.subject.pose_state)));}}}
 }
 const brandRows=expectedBrands.map(brand=>{const observed=brandObservations.filter(o=>o.brand===brand),visibleFrames=new Set(observed.map(o=>o.frame)),readableFrames=new Set(observed.filter(o=>o.readable).map(o=>o.frame));const rowList=[...readableFrames].sort((a,b)=>a-b).map(frame=>({frame}));return {brand,actual_visible_frames:[...visibleFrames].sort((a,b)=>a-b),actual_readable_frames:[...readableFrames].sort((a,b)=>a-b),readable_dwell:durations(runs(rowList,()=>true)),assets:[...new Set(observed.map(o=>o.asset))],original_bytes_match:observed.length>0&&observed.every(o=>verifiedBrandFiles[o.asset]&&o.sha256===brandRegistry.assets[o.asset].sha256),authentic_private_preparation:observed.length>0&&observed.every(o=>{const a=brandRegistry.assets[o.asset];return a.status==='authentic_verified'&&a.visual_verified&&a.contexts.private_review.user_authorized_preparation===true&&a.publication_authorized===false;}),decode_complete:observed.every(o=>o.complete),painted_bounds_examples:observed.filter((_,i)=>i%20===0).slice(0,8).map(o=>({frame:o.frame,asset:o.asset,painted_bbox:o.painted_bbox})),contrast:'Multicolor mark: visual review required; no scalar WCAG text certificate.'};});
 const familyRows=Object.entries(familyObservations).map(([id,f])=>({scene_id:id,family:f.family,registered:f.registered,actual_visible_frames:f.visible_frames.size,distinct_non_opacity_pose_states:f.pose_states.size,execution_verified:f.registered&&f.visible_frames.size>0&&f.pose_states.size>1}));
 report.metrics.protagonists=subjects;report.metrics.brands=brandRows;report.metrics.families=familyRows;
 const hookCollisions=detailed.forward.flatMap(({t,state:s})=>s.texts.filter(text=>hookIds.has(text.id)&&text.opacity>=.85).flatMap(text=>text.words.filter(w=>w.opacity>=.85&&w.paintedInk?.w>0).flatMap(word=>s.obstacles.filter(o=>overlaps(word.paintedInk,o.bbox)&&!o.occluded_words.includes(text.id+':'+word.index)).map(o=>({frame:Math.floor(t*FPS+1e-7),text_id:text.id,word:word.text,ink:word.paintedInk,object:o})))));
 report.metrics.hook_foreground_collisions=hookCollisions.slice(0,30);
 report.checks.hook_outside_graph_foreground=hookCollisions.length===0;
 const brandWordIntersections=[];
 for(const{t,state:pose}of detailed.forward)for(const text of pose.texts)for(const mark of text.words.filter(w=>w.brand_asset&&w.opacity>=.1&&w.paintedInk?.w>0))for(const word of text.words.filter(w=>w!==mark&&w.opacity>=.1&&w.paintedInk?.w>0)){const markHit=overlaps(mark.paintedInk,word.paintedInk),plateHit=mark.brand_surface_bbox&&overlaps(mark.brand_surface_bbox,word.paintedInk);if(markHit||plateHit)brandWordIntersections.push({frame:Math.round(t*FPS),brand:mark.brand_asset,word:word.text,word_alpha:word.opacity,mark_bbox:mark.paintedInk,surface_bbox:mark.brand_surface_bbox,word_ink:word.paintedInk,mark_overlap:markHit,plate_overlap:!!plateHit});}
 report.metrics.brand_word_clearance={alpha_threshold:.1,intersections:brandWordIntersections};
 report.checks.visible_words_outside_official_mark_and_plate=brandWordIntersections.length===0;

 const captionGraphicCollisions=detailed.forward.flatMap(({t,state:s})=>s.texts.filter(text=>!hookIds.has(text.id)&&text.opacity>=.85).flatMap(text=>text.words.filter(w=>w.opacity>=.85&&w.paintedInk?.w>0).flatMap(word=>s.obstacles.filter(o=>overlaps(word.paintedInk,o.bbox)&&!o.occluded_words.includes(text.id+':'+word.index)).map(o=>({frame:Math.floor(t*FPS+1e-7),text_id:text.id,word:word.text,ink:word.paintedInk,object:o})))));
 report.metrics.caption_graphic_collisions=captionGraphicCollisions.slice(0,30);
 report.checks.captions_outside_graph_foreground=captionGraphicCollisions.length===0;

 const faceCollisions=detailed.forward.flatMap(({t,state:s})=>{if(s.camera.opacity<.25)return[];const visible=visibleFace(s,t);if(!visible.w||!visible.h)return[];return s.texts.flatMap(text=>text.words.filter(w=>w.opacity>=.85&&w.paintedInk?.w>0&&overlaps(w.paintedInk,visible)).map(word=>({frame:Math.floor(t*FPS+1e-7),text_id:text.id,word:word.text,ink:word.paintedInk,visible_face_bbox:visible,method:'MediaPipe bbox interpolada y recortada por máscara real, no segmentación de glifos'})));});
 report.metrics.text_face_collisions=faceCollisions.slice(0,30);
 report.checks.legible_text_outside_visible_face=faceCollisions.length===0;
 const backgroundRuns=[];for(const {t,state:s}of detailed.forward){const frame=Math.floor(t*FPS+1e-7),colour=s.motion.background;const last=backgroundRuns.at(-1);if(last&&last.end_frame===frame&&last.colour===colour)last.end_frame=frame+1;else backgroundRuns.push({start_frame:frame,end_frame:frame+1,colour});}
 const colourVector=colour=>(colour?.match(/[\d.]+/g)||[]).slice(0,3).map(Number),colourDistance=(a,b)=>{const x=colourVector(a),y=colourVector(b);return x.length===3&&y.length===3?Math.hypot(...x.map((v,i)=>v-y[i])):0;};
 const briefFlashes=QUICK?[]:backgroundRuns.filter((run,i)=>i>0&&i<backgroundRuns.length-1&&run.end_frame-run.start_frame<=6&&backgroundRuns[i-1].colour===backgroundRuns[i+1].colour&&colourDistance(run.colour,backgroundRuns[i-1].colour)>180);
 report.metrics.background_runs=backgroundRuns;report.metrics.brief_background_flashes=briefFlashes;
 report.checks.no_undeclared_brief_background_flash=briefFlashes.length===0;
 const emptyBoundaryFrames=detailed.forward.filter(({state:s})=>!(s.camera.opacity>.001&&s.camera.clip.top<.999)&&!s.texts.some(text=>text.opacity>.1&&text.words.some(word=>word.opacity>.1&&word.paintedInk?.w>0))&&!s.subjects.some(subject=>!subject.missing&&subject.opacity>.1&&subject.visible_fraction>.15&&subject.visible_leaf_count>0)).map(({t,state:s})=>({frame:Math.round(t*FPS),t,background:s.motion.effective_solid_background_at_center,scene_start:cfg.scenes.filter(scene=>scene.start<=t+1e-7).at(-1)?.start??null}));
 const emptyRuns=[];for(const pose of emptyBoundaryFrames){const previous=emptyRuns.at(-1);if(previous?.end_frame===pose.frame)previous.end_frame=pose.frame+1;else emptyRuns.push({start_frame:pose.frame,end_frame:pose.frame+1});}
 report.metrics.empty_composition_boundary_candidates={frames:emptyBoundaryFrames,runs:emptyRuns,scope:QUICK?'Candidatos de muestras puntuales, pendientes de inspección de continuidad.':'Todos los fotogramas; candidatos geométricos, pendientes de inspección de continuidad.',classification:'Un cuadro de inicio de un reveal puede estar vacío sin ser corrupción; no constituye aprobación del ritmo ni del negro transitorio.'};
 report.checks.no_prolonged_empty_composition=QUICK||emptyRuns.every(run=>run.end_frame-run.start_frame<=6);
 if(emptyBoundaryFrames.length)report.warnings.push({kind:'empty_transition_review',frames:emptyBoundaryFrames.map(p=>p.frame),note:'Revisar la transición codificada en movimiento. No se clasifica automáticamente como corrupción ni se aprueba por el recibo; más de6fotogramas vacíos consecutivos bloquearán el QA final.'});


 report.metrics.internal_note_findings=detailed.forward.flatMap(({t,state:s})=>s.internal_notes.map(note=>({frame:Math.floor(t*FPS+1e-7),...note}))).slice(0,24);
 report.metrics.route_label_crossings=detailed.forward.flatMap(({t,state:s})=>s.route_label_crossings.map(note=>({frame:Math.floor(t*FPS+1e-7),...note}))).slice(0,24);
 report.metrics.dwell_policy={min_orientative:.7,max_orientative:1.3,alpha_readable:.85,visible_fraction_readable:.9,min_identity_font_px_1080:32,min_text_contrast:4.5,settled_speed_limit_frame_width_per_second:.2,source:'Legibility is measured;0.7–1.3 is editorial guidance, not a universal hard cut. Short voice hits/accumulation are flagged for explicit review.'};
 report.checks.original_source_sha_bound=rawSourceSha===narration.source.sha256&&rawSourceSha===face.original.sha256;
 report.checks.source_picture_and_cadence_preserved=sourcePixels.decoded_rgb_exact&&sourcePixels.raw_count===FRAME_COUNT&&sourcePixels.proxy_count===FRAME_COUNT;
 report.metrics.stable_presenter_face_geometry={method:'BBox facial MediaPipe del mismo crudo, interpolación solo dentro del segmento y transformación real del vídeo; máscara/canvas actuales. Excluye entradas y salidas deliberadas y no certifica el contorno del cabello.',samples:stableFaceGeometry.length,min_visible_fraction:Math.min(...stableFaceGeometry.map(p=>p.visible_fraction)),failures:stableFaceGeometry.filter(p=>p.visible_fraction<.999).slice(0,24)};
 report.checks.stable_presenter_face_not_cropped=stableFaceGeometry.length>0&&stableFaceGeometry.every(p=>p.visible_fraction>=.999);
 report.metrics.traditional_captions_by_pose=Object.fromEntries(['full','split','transition'].map(mode=>[mode,captions.filter(c=>c.camera_mode===mode).length]));
 report.checks.source_face_anchors_same_crudo=face.tracking.model_rerun===true&&face.tracking.count===face.anchors.length&&face.tracking.missing===0&&face.anchors.every(a=>!a.missing&&a.source_normalized.bbox.every(v=>v>=0&&v<=1)&&a.source_normalized.chin.every(v=>v>=0&&v<=1));
 report.checks.caption_style_matches_YO_contract=captions.every(c=>['Sequel','Scholar'].includes(c.expected_font)&&c.font.includes(c.expected_font)&&c.shadow!=='none'&&c.shadow.includes('0, 0, 0'));
 report.checks.caption_control_exercised=QUICK||captions.length>0;
 report.checks.actual_fonts_loaded=report.fonts.font_faces_ready&&report.fonts.sequel_loaded&&report.fonts.scholar_loaded&&report.fonts.sequel_metric_distinct_from_fallback;
 const toRGB=css=>{const m=/^rgba?\(([^)]+)\)$/.exec(css||'');return m?m[1].split(/[, ]+/).filter(Boolean).slice(0,3).map(Number):null;};
 const luma=c=>{const q=c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;});return q[0]*.2126+q[1]*.7152+q[2]*.0722;};
 const textContrast=[],photoStyles=[];
 for(const{t,state:pose}of detailed.forward)for(const text of pose.texts)for(const word of text.words.filter(w=>w.opacity>=.85&&w.paintedInk?.w>0&&!w.brand_asset)){
  const ink=word.paintedInk,m=pose.camera.mask,photo={x:m.x,y:m.y+m.h*pose.camera.clip.top,w:m.w,h:m.h*(1-pose.camera.clip.top-pose.camera.clip.bottom)},overPhoto=pose.camera.opacity>.01&&overlaps(ink,photo);
  if(overPhoto){const block=[...(dir.hook_blocks||[]),...(dir.caption_blocks||[])].find(b=>text.id==='integration-text-'+b.id),rgb=toRGB(word.color),white=rgb?.every(v=>v>=250),semanticRed=block?.color==='red'&&!!block.red_reason;
   photoStyles.push({frame:Math.round(t*FPS),id:text.id,word:word.text,color:word.color,font:text.font,shadow:text.shadow,white_or_semantic_red:!!white||!!semanticRed,black_compact_shadow:text.shadow.includes('0, 0, 0')&&text.shadow!=='none'});continue;
  }
  const fg=toRGB(word.color),bg=toRGB(word.background),blended=fg&&bg?fg.map((v,i)=>v*word.opacity+bg[i]*(1-word.opacity)):null,contrast=blended?(Math.max(luma(blended),luma(bg))+.05)/(Math.min(luma(blended),luma(bg))+.05):null;
  textContrast.push({frame:Math.round(t*FPS),id:text.id,word:word.text,foreground:word.color,background:word.background,opacity:word.opacity,contrast,pass:contrast!==null&&contrast>=4.5});
 }
 report.metrics.motion_text_contrast={method:'Color CSS calculado real sobre fondo SVG sólido y película real normalizados por navegador; alpha visible>=.85. No calcula WCAG sobre fotos.',samples:textContrast.length,min:Math.min(...textContrast.map(x=>x.contrast).filter(Number.isFinite)),failures:textContrast.filter(v=>!v.pass).slice(0,40)};
 report.metrics.photo_text_style={samples:photoStyles.length,failures:photoStyles.filter(v=>!v.white_or_semantic_red||!v.black_compact_shadow).slice(0,30),method:'Letras blancas o rojo editorial justificado y sombra negra; no promedio fotográfico ni certificado WCAG.'};
 report.checks.motion_words_contrast_real_background=textContrast.length>0&&textContrast.every(v=>v.pass);
 report.checks.photo_words_white_with_compact_black_shadow=photoStyles.every(v=>v.white_or_semantic_red&&v.black_compact_shadow);
 report.checks.families_actually_executed=cfg.scenes.every(s=>familyRows.some(f=>f.scene_id===s.id&&f.execution_verified));
 report.checks.selected_authentic_brands_actually_visible=brandRows.every(r=>r.actual_visible_frames.length&&r.original_bytes_match&&r.authentic_private_preparation&&r.decode_complete);
 report.checks.selected_authentic_brands_legible=brandRows.every(r=>r.actual_readable_frames.length>0);
 const firstPose=detailed.forward.find(p=>Math.abs(p.t)<1e-8)?.state,firstWindow=dir.camera_windows.find(w=>w.start_frame===0),firstBrand=(dir.hook_blocks||[]).find(b=>b.start_frame===0)?.brand_asset;
 report.metrics.first_frame={camera_opacity:firstPose?.camera.opacity,camera_top:firstPose?.camera.clip.top,present_subjects:(firstPose?.subjects||[]).filter(s=>!s.missing&&s.opacity>.01&&s.visible_fraction>.15&&s.visible_leaf_count>0).map(s=>({key:s.key,label:s.label,family:s.family,opacity:s.opacity,visible_fraction:s.visible_fraction})),words:(firstPose?.texts||[]).flatMap(t=>t.words.filter(w=>w.opacity>.01).map(w=>({text:w.text,alpha:w.opacity,brand_asset:w.brand_asset}))),requested_initial_brand:firstBrand||null};
 report.checks.first_frame_contains_semantic_protagonist=!!firstPose&&(report.metrics.first_frame.present_subjects.length>0||report.metrics.first_frame.words.length>0);
 if(dir.camera_mode==='split_first')report.checks.first_frame_split_executed=!!firstWindow&&firstWindow.state==='split'&&firstPose.camera.opacity>.99&&Math.abs(firstPose.camera.clip.top-(firstWindow.split_top??dir.split_top??cfg.split.upper))<.001;
 if(firstBrand)report.checks.requested_initial_brand_visible_from_frame0=brandObservations.some(o=>o.frame===0&&o.asset===firstBrand&&o.opacity>.85&&o.visible_fraction>.9);
 report.metrics.official_mark_style_review=brandObservations.filter(o=>o.opacity>.1&&(Math.abs(o.angle_degrees)>.01||o.filter!=='none')).slice(0,30);
 report.checks.official_hook_marks_not_rotated_or_filtered=report.metrics.official_mark_style_review.filter(o=>o.subject.startsWith('hook:')).length===0;
 report.checks.routes_outside_source_labels=report.metrics.route_label_crossings.length===0;
 report.checks.internal_notes_not_editorial=report.metrics.internal_note_findings.length===0;
 if(subjects.some(s=>s.dwell_assessment==='insufficient_readable_hold_review'))report.warnings.push({kind:'readable_dwell_review',subjects:subjects.filter(s=>s.dwell_assessment==='insufficient_readable_hold_review').map(s=>({key:s.key,label:s.label,readable_max:s.legible_presence.max,readable_total:s.legible_presence.total})),note:'Does not force0.7s per spoken word; review geometry, contrast and purposeful retention.'});
 if(micWarnings.length)report.warnings.push({kind:'microphone_review',count:micWarnings.length,note:'Intersección con bbox conservadora medida visualmente; requiere inspección de tinta/sombra, no rechazo automático.'});
 if(!micBox)report.warnings.push({kind:'microphone_unmeasured',note:'No se certifica ausencia de cruce con micrófono sin medición verificable.'});
 if(spacing.some(p=>p.gap<1))report.warnings.push({kind:'word_spacing',note:'Posible pérdida de espacio entre spans inline-block; revisar los PNG nativos.',examples:spacing.filter(p=>p.gap<1).slice(0,8)});
 for(const t of proofTimes){
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
 if(AUDIT_V1)report.original_v1_binding={source_sha256:baseline.source_v1_sha256,mp4_sha256:baseline.mp4_v1_sha256,snapshot:baseline.snapshot,snapshot_files_match_preservation:report.preservation.baseline_match&&report.preservation.unchanged,note:'El fingerprint técnico del snapshot cambia por la ruta; las copias preservadas se vinculan con los SHA originales.'};
 const target=path.join(folder,project.output_name||'ascendia_reel_final.mp4');
 const renderReceiptPath=path.join(folder,'integration_qc.json'),renderReceipt=fs.existsSync(renderReceiptPath)?read(renderReceiptPath):null;
 const targetSha=fs.existsSync(target)?digest(target):AUDIT_V1?baseline.mp4_v1_sha256:null;
 const receiptCurrent=!!targetSha&&renderReceipt?.source_sha256===report.source_after.sha256&&(renderReceipt.final_mp4_sha256||renderReceipt.mp4_sha256)===targetSha;
 report.export_binding={status:receiptCurrent?'bound_to_verified_render':'pending_current_render_receipt',path:relative(target),sha256:targetSha,source_sha256:report.source_after.sha256,render_receipt:receiptCurrent?{path:relative(renderReceiptPath),sha256:digest(renderReceiptPath)}:null};
 report.render_media=receiptCurrent?{decoded_all_frames:renderReceipt.decoded_all_frames===true,frames:renderReceipt.frames,video_duration:renderReceipt.video_duration??renderReceipt.duration,audio_duration:renderReceipt.audio_duration,container_duration:renderReceipt.container_duration,audio_original_bit_exact:renderReceipt.audio_original_bit_exact===true,original_audio_packet_hash:renderReceipt.original_audio_packet_hash,no_extension:renderReceipt.no_extension===true,hardware_gpu:renderReceipt.hardware_gpu===true,nvenc:renderReceipt.nvenc===true,note:'Valores del recibo de render verificado, vinculado por SHA de fuente y MP4. Este harness no vuelve a renderizar ni escucha el audio.'}:{status:'pending_verified_export'};
 const packetHash=file=>{const r=spawnSync(ffmpeg,['-v','error','-i',file,'-map','0:a:0','-c:a','copy','-f','hash','-hash','sha256','-'],{cwd:ROOT,encoding:'utf8'});if(r.status)throw Error('No se pudo verificar AAC original: '+r.stderr.slice(-300));return r.stdout.trim();};
 const raw=path.join(ROOT,'proyectos',ID,'original.mp4'),voice=path.join(folder,'media/voice_original.m4a');
 report.input_audio={raw_path:relative(raw),raw_sha256:digest(raw),voice_path:relative(voice),voice_sha256:digest(voice),raw_aac_packet_hash:packetHash(raw),voice_aac_packet_hash:packetHash(voice),no_processing_claim:'Identidad de paquetes AAC, sin escucha ni inferencias sobre mezcla.'};
 report.checks.input_audio_original=report.input_audio.raw_aac_packet_hash===report.input_audio.voice_aac_packet_hash;
 const mixProofPath=path.join(ROOT,'proyectos',ID,'recursos/sonido/mezcla_provenance.json'),mixContractPath=path.join(ROOT,'proyectos',ID,'recursos/sonido/audio_mix.json');
 if(fs.existsSync(mixProofPath)&&fs.existsSync(mixContractPath)){
  const mixProof=read(mixProofPath),mixContract=read(mixContractPath),resolveOwned=p=>{const q=path.resolve(ROOT,p);if(!fs.existsSync(q)||!fs.realpathSync(q).startsWith(ROOT+'/'))throw Error('Recurso de audio no disponible dentro de IVAN: '+p);return q;};
  const mixedFile=resolveOwned(mixProof.output_path),planFile=resolveOwned(mixProof.plan_path),mixedSha=digest(mixedFile),mixPacket=packetHash(mixedFile);
  const decoded=spawnSync(ffmpeg,['-v','error','-i',raw,'-map','0:a:0','-f','f32le','-acodec','pcm_f32le','-'],{cwd:ROOT,maxBuffer:64*1024*1024});
  if(decoded.status)throw Error('No se pudo cotejar el stem de voz original');
  const rawPCMHash=hash(decoded.stdout),pcmFrames=decoded.stdout.length/4/mixProof.channels;
  const fxSources=(mixProof.sources_and_actions||[]).map(cue=>({resource_id:cue.resource_id,path:cue.path,sha256:cue.sha256,current_sha256:digest(resolveOwned(cue.path)),start_sample:cue.start_sample,mixed_samples:cue.mixed_samples,visual_action:cue.visual_action,reason:cue.reason,fade_applied_to_fx_only:cue.fade_applied_to_fx_only}));
  report.audio_mix={receipt_path:relative(mixProofPath),receipt_sha256:digest(mixProofPath),contract_path:relative(mixContractPath),contract_sha256:digest(mixContractPath),output_path:relative(mixedFile),output_sha256:mixedSha,output_aac_packet_hash:mixPacket,original_pcm_sha256:rawPCMHash,original_pcm_frames:pcmFrames,provenance:mixProof,fx_sources:fxSources,final_packet_hash:receiptCurrent?packetHash(target):null,scope:'Cotejo de hashes, identidad del stem y tiempos declarados con archivos actuales; no escucha ni aprobación del balance.'};
  report.checks.audio_mix_bound_to_original_source=mixProof.original_source_sha256===rawSourceSha&&mixProof.voice_source_sha256===report.input_audio.raw_aac_packet_hash.split('=',2)[1]&&mixProof.voice_decoded_f32le_sha256===rawPCMHash&&mixProof.original_decoded_samples===pcmFrames;
  report.checks.voice_stem_unchanged_in_mix=mixProof.original_voice_stem_unchanged===true&&mixProof.voice_gain_db===0&&mixProof.voice_speed===1&&mixProof.voice_rate===1&&mixProof.voice_start_offset_samples===0;
  report.checks.audio_mix_assets_and_plan_current=mixedSha===mixProof.output_sha256&&mixedSha===mixContract.sha256&&digest(planFile)===mixProof.plan_sha256&&digest(mixProofPath)===mixContract.provenance_sha256&&fxSources.length>0&&fxSources.every(c=>c.sha256===c.current_sha256&&c.visual_action&&c.reason&&c.start_sample>=0&&c.mixed_samples>0&&c.start_sample+c.mixed_samples<=pcmFrames&&c.fade_applied_to_fx_only===true);
  const soundPlan=read(planFile),clockBinding=soundPlan.action_clock_binding,clockMaps=(report.integration_receipt?.component_overrides||[]).filter(r=>Array.isArray(r.map)).map(r=>({scene_id:r.scene_id,map:r.map})).sort((a,b)=>a.scene_id.localeCompare(b.scene_id));
  const canon=spawnSync('python3',['-B','-c',"import json,sys,hashlib;v=json.load(sys.stdin);print(hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest())"],{cwd:ROOT,input:JSON.stringify(clockMaps),encoding:'utf8'});
  if(canon.status)throw Error('No se pudo medir el mapa temporal de sonido');
  const recordedCanon=spawnSync('python3',['-B','-c',"import json,sys,hashlib;v=json.load(sys.stdin);print(hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest())"],{cwd:ROOT,input:JSON.stringify(clockBinding?.clock_maps||[]),encoding:'utf8'});
  if(recordedCanon.status)throw Error('No se pudo medir el mapa temporal declarado');
  report.audio_mix.action_clock_binding={recorded:clockBinding||null,actual_maps:clockMaps,actual_maps_sha256:canon.stdout.trim(),note:'basis_composition_sha256 es procedencia anterior al audio; se compara el reloj ejecutado, SceneIR/dirección y cues, no se obliga a conservar el fingerprint previo a embebido del mix.'};
  report.checks.audio_mix_action_clock_bound=!!clockBinding&&clockMaps.length>0&&digest(resolveOwned(clockBinding.scene_ir_path))===clockBinding.scene_ir_sha256&&digest(resolveOwned(clockBinding.direction_path))===clockBinding.direction_sha256&&clockBinding.clock_maps_sha256===canon.stdout.trim()&&recordedCanon.stdout.trim()===canon.stdout.trim();
  const basisReceiptFile=clockBinding?.basis_runtime_receipt_path?resolveOwned(clockBinding.basis_runtime_receipt_path):null,basisReceipt=basisReceiptFile?read(basisReceiptFile):null;
  report.audio_mix.action_clock_binding.immutable_basis_receipt=basisReceiptFile?{path:relative(basisReceiptFile),sha256:digest(basisReceiptFile),status:basisReceipt.quick_status,composition_sha256:basisReceipt.composition_sha256,tested_poses:basisReceipt.tested_poses,scope:'Recibo inmutable del quick anterior a embebido del audio; no sustituye QA final ni escucha.'}:null;
  report.checks.audio_mix_immutable_clock_receipt=!!basisReceipt&&digest(basisReceiptFile)===clockBinding.basis_runtime_receipt_sha256&&basisReceipt.quick_status==='PASS_QUICK_PENDING_FULL_AND_VISUAL'&&basisReceipt.mode==='quick'&&basisReceipt.tested_poses>0&&Object.values(basisReceipt.checks||{}).length>0&&Object.values(basisReceipt.checks||{}).every(Boolean)&&basisReceipt.composition_sha256===clockBinding.basis_composition_sha256&&basisReceipt.original_sha256===rawSourceSha&&basisReceipt.scene_ir_sha256===clockBinding.scene_ir_sha256&&basisReceipt.direction_sha256===clockBinding.direction_sha256&&basisReceipt.clock_maps_sha256===canon.stdout.trim();
  report.checks.audio_mix_timing_and_sample_headroom=mixProof.sample_rate===44100&&mixProof.channels===2&&Math.abs(mixProof.original_audio_duration-narration.duration)<.001&&Math.abs(mixProof.output_audio_duration-narration.duration)<.05&&mixProof.samples_abs_gt1===0&&Number.isFinite(mixProof.decoded_aac_sample_peak_dbfs)&&mixProof.decoded_aac_sample_peak_dbfs<0&&mixProof.music_used===false;
  if(receiptCurrent)report.checks.final_audio_matches_verified_mix=packetHash(target)===mixPacket;
 }else{
  report.audio_mix={status:'pending_verified_mix',no_unexecuted_claim:true};
  if(receiptCurrent&&!report.render_media.audio_original_bit_exact)report.checks.audio_mix_bound_to_original_source=false;
 }
 if(receiptCurrent){report.checks.export_frame_count_unchanged=report.render_media.decoded_all_frames&&report.render_media.frames===FRAME_COUNT&&Math.abs(report.render_media.video_duration-FRAME_COUNT/FPS)<1e-6;report.checks.export_audio_voice_timing_preserved=report.render_media.no_extension&&Math.abs(report.render_media.audio_duration-narration.duration)<.05;report.render_media.audio_mix_status=report.render_media.audio_original_bit_exact?'AACoriginal exacto':'AACmezclado; auditar fuente/gain/offset/rate/FX mediante recibo real, no exigir identidad debytes delmix.';}
 report.status=Object.values(report.checks).every(Boolean)&&report.errors.length===0?(QUICK?'PASS_QUICK_PENDING_FULL_AND_VISUAL':'PASS_CPU_PENDING_VISUAL_REVIEW'):'FAIL_OR_STALE';
 report.limits=['Recibo CPU con inyección real de frames del proxy H264 y compilador0.8.147; no reemplaza revisión del MP4.','Bbox de texto/micrófono son conservadoras; no equivalen a segmentación de tinta ni escucha.','No se afirma aprobación estética, calidad sonora ni validación de las afirmaciones narradas.'];
 const detailedPath=path.join(TMP,'detailed.json');fs.writeFileSync(detailedPath,JSON.stringify(detailed));report.private_trace={path:relative(detailedPath),sha256:digest(detailedPath)};
 fs.writeFileSync(path.join(folder,'production_complete_browser_qc.json'),JSON.stringify(report,null,2)+'\n');
 const rhythm={schema_version:1,status:report.status,mode:report.mode,frame_count:FRAME_COUNT,fps:FPS,source_sha256:report.source_after.sha256,export_binding:report.export_binding,render_media:report.render_media,input_audio:report.input_audio,audio_mix:report.audio_mix,fonts:report.fonts,protagonists:report.metrics?.protagonists||[],brands:report.metrics?.brands||[],families:report.metrics?.families||[],dwell_policy:report.metrics?.dwell_policy,camera:{runs:report.metrics?.camera_runs,visible_frames:report.metrics?.total_visible_frames,presence_fraction:report.metrics?.presence_fraction,max_continuous_frames:report.metrics?.max_continuous_frames},limits:report.limits};fs.writeFileSync(path.join(folder,'ritmo_completo.json'),JSON.stringify(rhythm,null,2)+'\n');

 console.log(JSON.stringify({status:report.status,checks:report.checks,errors:report.errors,warnings:report.warnings,source:report.source_after.sha256,metrics:report.metrics?{camera_runs:report.metrics.camera_runs,total_visible_frames:report.metrics.total_visible_frames,caption_samples:report.metrics.caption_samples,missing_words:report.metrics.missing_words}:null},null,2));
 if(report.status==='FAIL_OR_STALE'&&!AUDIT_V1)process.exitCode=1;
}
