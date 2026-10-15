// Prueba de GSAP real y reproducibilidad de la misma timeline usada por HyperFrames.
import './skills_entorno.mjs';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {chromium} from '../.estado/herramientas/node_modules/playwright-core/index.mjs';
const root=path.resolve(import.meta.dirname,'..'),folder=path.join(root,'ejemplos/arquitectura_motion_3s');
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const server=http.createServer((req,res)=>{
  try{
    const requested=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
    const file=path.resolve(folder,'.'+(requested==='/'?'/index.html':requested));
    if(!file.startsWith(folder+path.sep)||!fs.existsSync(file)||!fs.realpathSync(file).startsWith(root+path.sep)){res.writeHead(404);res.end();return;}
    const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.ttf':'font/ttf'})[ext]||'application/octet-stream');res.end(fs.readFileSync(file));
  }catch{res.writeHead(500);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
process.stdout.write('Servidor de poses preparado.\n');
// El render ya usa NVIDIA. Para el observador independiente, compositor software.
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,timeout:30000,args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
process.stdout.write('Navegador de poses iniciado.\n');
try{
  const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});const errors=[];
  page.on('pageerror',e=>{errors.push(e.message);process.stdout.write('Error en página: '+e.message+'\n');});
  const response=await page.goto('http://127.0.0.1:'+server.address().port,{timeout:30000});await page.waitForFunction(()=>window.renderReady===true,{timeout:15000});
  process.stdout.write('GSAP registrado; capturando poses.\n');
  const loaded=await page.evaluate(()=>({...window.__gsapEvidence,paused:window.__timelines['arquitectura-gsap'].paused()}));
  process.stdout.write('Biblioteca y plugins confirmados: '+JSON.stringify(loaded)+'\n');
  const states=[];const evidence=path.join(folder,'evidencias');fs.mkdirSync(evidence,{recursive:true});
  async function seek(t){
    // No devolver la timeline: contiene un grafo cíclico muy grande de plugins/DOM.
    await page.evaluate(t=>{window.__timelines['arquitectura-gsap'].seek(t,false);},t);
    // GSAP escribe sus canales sincrónicamente; screenshot fuerza el paint.
    // No depender de RAF cuando Chrome deja inactivo el ticker de una timeline pausada.
    return page.evaluate(t=>({t,time:window.__timelines['arquitectura-gsap'].time(),duracion_timeline:window.__timelines['arquitectura-gsap'].duration(),
      source:getComputedStyle(document.querySelector('#source-a')).transform,
      mask:getComputedStyle(document.querySelector('.source-data')).clipPath,
      packet:getComputedStyle(document.querySelector('#packet-a')).transform,
      silhouette:document.querySelector('#processor').getAttribute('d'),
      world:getComputedStyle(document.querySelector('#world')).transform}),t);
  }
  for(const t of [0,.2,.3,.5,.8,1,1.2,1.5,1.8,2.1,2.4,2.8,2.966667]){
    process.stdout.write('Pose '+t+'\n');
    states.push(await seek(t));await page.screenshot({path:path.join(evidence,'html_'+t.toFixed(3)+'.png')});
  }
  await seek(1.2);const first=sha(await page.screenshot());await seek(.3);await seek(1.2);const second=sha(await page.screenshot());
  const varied=key=>new Set(states.map(s=>s[key])).size>2;
  const checks={gsap_315_cargado:loaded.version==='3.15.0',plugins_reales:loaded.motionPath&&loaded.morphSVG,
    timeline_pausada:loaded.paused,timeline_sincronizada:states.every(s=>Math.abs(s.time-Math.min(s.t,s.duracion_timeline))<.00001),
    posicion:varied('source'),escala_y_camara:varied('world'),mascaras:varied('mask'),trayectorias:varied('packet'),
    morphing:varied('silhouette'),seek_reproducible:first===second,sin_errores_runtime:errors.length===0,preview_http_200:response.status()===200};
  const report={fecha:new Date().toISOString(),carga_real:loaded,comprobaciones:checks,estados:states,
    errores:errors,determinismo_sha256:first,timeline_sha256:sha(fs.readFileSync(path.join(folder,'timeline.gsap.js'))),
    html_sha256:sha(fs.readFileSync(path.join(folder,'index.html'))),limite:'Se verifica biblioteca/timeline y poses. La prueba final compara estos píxeles con el MP4 real de HyperFrames.'};
  fs.writeFileSync(path.join(folder,'verificacion_gsap.json'),JSON.stringify(report,null,2)+'\n');
  process.stdout.write(JSON.stringify({carga_real:loaded,comprobaciones:checks})+'\n');
  if(!Object.values(checks).every(Boolean))process.exitCode=1;
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
