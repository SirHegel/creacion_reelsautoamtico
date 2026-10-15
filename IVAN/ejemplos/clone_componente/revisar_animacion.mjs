import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from '../../.estado/herramientas/node_modules/playwright/index.mjs';
const root=process.cwd(),folder='ejemplos/clone_componente';
if(path.basename(root)!=='IVAN') throw Error('Ejecutar dentro de IVAN');
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp`;
process.env.XDG_CACHE_HOME=path.join(root,'.estado/cache');
process.env.XDG_CONFIG_HOME=path.join(root,'.estado/config');
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY='1';
const mime={'.html':'text/html','.js':'text/javascript','.svg':'image/svg+xml','.png':'image/png'};
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+new URL(req.url,'http://localhost').pathname);
 if(!file.startsWith(root+'/')||!fs.existsSync(file)||!mime[path.extname(file)])return res.writeHead(404).end();
 res.writeHead(200,{'Content-Type':mime[path.extname(file)]});fs.createReadStream(file).pipe(res);
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
console.log('Servidor local de revisión activo.');
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,timeout:20000,
 args:['--no-sandbox','--disable-dev-shm-usage','--disable-crash-reporter','--disable-breakpad','--disable-gpu','--force-color-profile=srgb']});
try{
 console.log('Chrome de revisión iniciado.');
 const page=await browser.newPage({viewport:{width:1080,height:1920}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const response=await page.goto(`http://127.0.0.1:${server.address().port}/${folder}/index.html`,{waitUntil:'domcontentloaded',timeout:20000});
 console.log('Composición cargada HTTP'+response.status());
 await page.waitForFunction(()=>window.renderReady===true,null,{timeout:20000});
 console.log('Timeline preparada.');
 const out='.estado/tmp/clone_animacion_proof';fs.mkdirSync(out,{recursive:true});
 const states=[];
 for(let f=0;f<48;f++){
  const t=f/30;await page.evaluate(t=>{window.__timelines['clone-motion'].seek(t,false);},t);
  if(f===0)console.log('Primer seek terminado.');
  await page.screenshot({path:`${out}/frame_${String(f).padStart(3,'0')}.png`,timeout:10000});
  if(f%12===0)console.log('Fotograma',f);
  states.push(await page.evaluate(t=>({t,sourceTime:t+1.6,price:document.querySelector('#cost').textContent,
    panel:document.querySelector('#panel-camera').getBoundingClientRect().toJSON(),
    rows:Array.from(document.querySelectorAll('[id^="row-"]')).map(e=>({id:e.id,opacity:getComputedStyle(e).opacity,transform:e.getAttribute('transform')})),
    lines:Array.from(document.querySelectorAll('[id^="cancel-line-"]')).map(e=>({id:e.id,offset:getComputedStyle(e).strokeDashoffset})),
    stamp:{opacity:getComputedStyle(document.querySelector('#stamp-motion')).opacity,transform:document.querySelector('#stamp-motion').getAttribute('transform')},
    evidence:window.__cloneEvidence}),t));
 }
 const hash=x=>createHash('sha256').update(x).digest('hex');
 const seek=async t=>{await page.evaluate(t=>{window.__timelines['clone-motion'].seek(t,false);},t);return hash(await page.screenshot({timeout:10000}));};
 const first=await seek(1.5);await seek(.1);const second=await seek(1.5);
 fs.writeFileSync(folder+'/revision_timeline.json',JSON.stringify({http:response.status(),errors,seek_determinista:first===second,
  limite:'Estados técnicos y capturas; no acreditan semejanza con CLONE. La comparación visual usa el original.',states},null,2));
 if(errors.length||response.status()!==200||first!==second)throw Error('Falló estabilidad de la composición');
 console.log('48 estados inspeccionables; recursos HTTP200; seek inverso determinista.');
}finally{await browser.close();server.close();}
