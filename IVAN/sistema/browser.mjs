import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import { chromium } from '../.estado/herramientas/node_modules/playwright/index.mjs';

const root = process.cwd();
if (path.basename(root) !== 'IVAN') throw Error('Ejecutar exclusivamente desde IVAN');
process.env.TMPDIR = `/proc/${process.pid}/cwd/.estado/tmp`;
process.env.XDG_CACHE_HOME = path.join(root,'.estado/cache');
process.env.XDG_CONFIG_HOME = path.join(root,'.estado/config');
const mime={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.json':'application/json','.wasm':'application/wasm','.task':'application/octet-stream','.mp4':'video/mp4','.ttf':'font/ttf','.svg':'image/svg+xml','.png':'image/png','.jpg':'image/jpeg'};
const server=http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');
 const rel=decodeURIComponent(url.pathname).replace(/^\//,'');
 if(rel==='__prueba__'){
  const target=process.argv[3];if(process.argv[2]!=='reproducir'||!/^proyectos\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+\.mp4$/.test(target)){res.writeHead(404).end();return;}
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});res.end(`<html><body style="margin:0;background:#191b1e"><video id="preview" src="/${target}" controls style="width:1080px;height:1920px"></video></body></html>`);return;
 }
 const file=path.resolve(root,rel);
 const allowed=rel.startsWith('assets/') || rel.startsWith('recursos/') || rel.startsWith('proyectos/') || rel.startsWith('sistema/') || rel.startsWith('.estado/herramientas/node_modules/') || ['.estado/cache/modelos/face_landmarker.task','.estado/tmp/rostro_base.mp4','.estado/tmp/face.html'].includes(rel);
 if(!allowed || !file.startsWith(root+path.sep) || !mime[path.extname(file)] || !fs.existsSync(file)){res.writeHead(404).end();return;}
 const stat=fs.statSync(file); const range=req.headers.range;
 res.setHeader('Content-Type',mime[path.extname(file)]);
 if(range){const m=range.match(/bytes=(\d+)-(\d*)/);let start=Number(m[1]),end=m[2]?Number(m[2]):stat.size-1;end=Math.min(end,stat.size-1);res.writeHead(206,{'Content-Range':`bytes ${start}-${end}/${stat.size}`,'Accept-Ranges':'bytes','Content-Length':end-start+1});fs.createReadStream(file,{start,end}).pipe(res);}
 else {res.writeHead(200,{'Content-Length':stat.size,'Accept-Ranges':'bytes'});fs.createReadStream(file).pipe(res);}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-crash-reporter','--disable-breakpad','--disable-gpu','--autoplay-policy=no-user-gesture-required',...(process.argv[2]==='estatico'?['--force-color-profile=srgb']:[])]});
try{
 const mode=process.argv[2];
 const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
 page.on('pageerror',e=>console.error('BROWSER',e.message));
 if(mode==='rostro' || mode==='medir'){
  const source=mode==='rostro'?'/.estado/tmp/rostro_base.mp4':'/'+process.argv[3];
  fs.writeFileSync('.estado/tmp/face.html',`<html><body><video id="v" src="${source}" muted></video><script type="module">
  import {FaceLandmarker,FilesetResolver} from '/.estado/herramientas/node_modules/@mediapipe/tasks-vision/vision_bundle.mjs';
  const files=await FilesetResolver.forVisionTasks('/.estado/herramientas/node_modules/@mediapipe/tasks-vision/wasm');
  const model=await FaceLandmarker.createFromOptions(files,{baseOptions:{modelAssetPath:'/.estado/cache/modelos/face_landmarker.task',delegate:'CPU'},runningMode:'IMAGE',numFaces:1,minFaceDetectionConfidence:0.6,minFacePresenceConfidence:0.6});
  const v=document.querySelector('#v');await new Promise(r=>v.readyState>=2?r():v.addEventListener('loadeddata',r,{once:true}));
  const out=[];for(let t=0;t<v.duration-.04;t+=.1){v.currentTime=t;await new Promise(r=>v.addEventListener('seeked',r,{once:true}));const result=model.detect(v);const pts=result.faceLandmarks[0];if(pts){const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);out.push({t:+t.toFixed(3),chin:[pts[152].x,pts[152].y],top:[pts[10].x,pts[10].y],bbox:[Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)]});}else out.push({t:+t.toFixed(3),missing:true});}window.result=out;model.close();
  </script></body></html>`);
  await page.goto(base+'/.estado/tmp/face.html');
  await page.waitForFunction(()=>window.result,null,{timeout:180000});
  const points=await page.evaluate(()=>window.result);
  let prev;for(const p of points){if(p.missing)continue;const smooth=prev?p.chin.map((v,i)=>prev[i]*.65+v*.35):p.chin;p.smooth_chin=smooth;prev=smooth;}
  const identifier=process.argv[3]||'demo_montaje_v4';
  const target=mode==='rostro'?'proyectos/'+identifier+'/rostro.json':'.estado/tmp/presencia.json';
  if(!path.resolve(root,target).startsWith(root+path.sep))throw Error('Ruta fuera de IVAN');
  fs.writeFileSync(target,JSON.stringify({modelo:'MediaPipe FaceLandmarker',landmark_barbilla:152,intervalo_s:.1,suavizado_alpha:.35,fuente:mode==='rostro'?'Proxy del original, análisis 540 × 960':process.argv[3]+', análisis del render completo',detecciones:points},null,2));
  console.log(JSON.stringify({mode,frames:points.length,missing:points.filter(p=>p.missing).length,first:points[0]}));
 } else if(mode==='estatico'){
  const project=process.argv[3];
  if(!/^proyectos\/[A-Za-z0-9_-]+$/.test(project))throw Error('Proyecto estático inválido');
  await page.goto(`${base}/${project}/index.html`,{waitUntil:'networkidle'});
  await page.evaluate(()=>document.fonts.ready);
  await page.screenshot({path:`${project}/clone_diseno_estatico.png`});
  console.log('PNG estático 1080×1920, fuentes cargadas; sin timeline ni reproducción.');
 } else if(mode==='informe'){
  const project=process.argv[3];
  if(!/^proyectos\/[A-Za-z0-9_-]+$/.test(project))throw Error('Proyecto inválido');
  await page.goto(`${base}/${project}/informe.html`,{waitUntil:'networkidle'});
  const reportName=process.argv[4]||'informe_ascendia_v3.pdf';
  if(!/^[A-Za-z0-9_-]+\.pdf$/.test(reportName))throw Error('Nombre de informe inválido');
  await page.pdf({path:`${project}/${reportName}`,format:'A4',printBackground:true,preferCSSPageSize:true,margin:{top:'14mm',bottom:'14mm',left:'13mm',right:'13mm'}});
  console.log('Informe PDF generado dentro de IVAN');
 } else if(mode==='fotogramas'){
  const project=process.argv[3],times=process.argv[4].split(',').map(Number);
  // Conservar peticiones Range: fulfill del archivo completo impedía buscar
  // correctamente el fotograma del presentador y dejaba currentTime en cero.
  await page.route('**/original.mp4',route=>route.continue({url:base+'/.estado/tmp/rostro_base.mp4'}));
  await page.goto(`${base}/${project}/index.html`);await page.waitForFunction(()=>window.renderReady===true);
  const geometry=[];
  for(const t of times){await page.evaluate(t=>window.seekForReview(t),t);await page.screenshot({path:`.estado/tmp/review_${t.toFixed(3)}.png`});
   geometry.push(await page.evaluate(t=>({t,fonts:[document.fonts.check('72px Sequel'),document.fonts.check('100px Scholar')],videos:Array.from(document.querySelectorAll('video')).map(v=>({id:v.id,currentTime:v.currentTime,start:v.dataset.start,offset:v.dataset.mediaStart,duration:v.dataset.duration,rect:v.getBoundingClientRect().toJSON()})),sheet:document.querySelector('#sheet')?.getAttribute('d'),transforms:Array.from(document.querySelectorAll('[data-audit]')).map(n=>({name:n.dataset.audit,rect:n.getBoundingClientRect().toJSON(),transform:getComputedStyle(n).transform})),texts:Array.from(document.querySelectorAll('div')).filter(n=>n.childNodes.length===1&&n.firstChild.nodeType===3&&getComputedStyle(n).visibility!=='hidden').map(n=>({text:n.textContent,rect:n.getBoundingClientRect().toJSON(),font:getComputedStyle(n).fontFamily,shadow:getComputedStyle(n).textShadow}))}),t));
  }
  fs.writeFileSync('.estado/tmp/review_geometry.json',JSON.stringify(geometry,null,2));
  console.log('Fotogramas '+times.join(','));
 } else if(mode==='oficial'){
  await page.setViewportSize({width:1300,height:1400});
  await page.goto('https://github.com/Panniantong/Agent-Reach',{waitUntil:'domcontentloaded',timeout:60000});
  await page.locator('article').waitFor({timeout:60000});
  const article=page.locator('article');await article.scrollIntoViewIfNeeded();
  await page.evaluate(()=>window.scrollBy(0,-80));
  const initial=await page.evaluate(()=>window.scrollY);
  const encoder=spawn('ffmpeg',['-v','error','-f','image2pipe','-framerate','12','-vcodec','mjpeg','-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-y','recursos/Agent_Reach_navegacion.mp4'],{stdio:['pipe','inherit','inherit']});
  for(let i=0;i<84;i++){const p=Math.max(0,Math.min(1,(i-12)/60));const ease=p*p*(3-2*p);await page.evaluate(y=>window.scrollTo(0,y),initial+ease*920);const frame=await page.screenshot({type:'jpeg',quality:92});if(!encoder.stdin.write(frame))await new Promise(r=>encoder.stdin.once('drain',r));}
  encoder.stdin.end();await new Promise((resolve,reject)=>encoder.on('close',c=>c===0?resolve():reject(Error('FFmpeg '+c))));
  console.log('Grabación real del repositorio oficial: 7 segundos, 84 estados de navegación');
 }else if(mode==='reproducir'){
  const target=process.argv[3];if(!/^proyectos\/[A-Za-z0-9_-]+\/[A-Za-z0-9_-]+\.mp4$/.test(target))throw Error('Solo el MP4 del proyecto dentro de IVAN');
  await page.goto(base+'/__prueba__',{waitUntil:'domcontentloaded'});
  const result=await page.evaluate(async()=>{
   const v=document.querySelector('video');await new Promise((r,j)=>{if(v.readyState>=2)return r();v.addEventListener('loadeddata',r,{once:true});v.addEventListener('error',()=>j(Error('Error de decodificación')), {once:true});});
   const Audio=window.AudioContext||window.webkitAudioContext,context=new Audio(),source=context.createMediaElementSource(v),meter=context.createAnalyser();source.connect(meter);meter.connect(context.destination);await context.resume();
   let peak=0;const data=new Uint8Array(meter.fftSize);const timer=setInterval(()=>{meter.getByteTimeDomainData(data);for(const x of data)peak=Math.max(peak,Math.abs(x-128)/128);},20);
   const ended=new Promise((r,j)=>{v.addEventListener('ended',r,{once:true});v.addEventListener('error',()=>j(Error('Reproducción interrumpida')),{once:true});});await v.play();await ended;clearInterval(timer);
   const q=v.getVideoPlaybackQuality();await context.close();return {estado:'reproducido_hasta_el_final',duracion_s:v.duration,tiempo_final_s:v.currentTime,frames_presentados:q.totalVideoFrames,frames_descartados_reproductor:q.droppedVideoFrames,error_video:v.error,audio_detectado:peak>0,pico_audio_navegador:peak,limite:'Reproducción técnica en navegador; no equivale a audición humana ni aprobación editorial del usuario'};
  });
  fs.writeFileSync(path.join(root,path.dirname(target),'reproduccion_prueba.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }else throw Error('Modo desconocido');
}finally{await browser.close();server.close();}
