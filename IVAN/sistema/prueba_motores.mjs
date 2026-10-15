// Calibración sintética. No modifica la edición del cliente.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import './confinar.mjs';
const root=path.resolve(import.meta.dirname,'..');process.chdir(root);
const temp=path.join(root,'.estado/tmp');fs.mkdirSync(temp,{recursive:true});
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp`;
process.env.PATH=path.join(root,'.estado/herramientas/ffmpeg/bin')+':'+process.env.PATH;
process.env.NODE_OPTIONS='--import '+path.join(root,'sistema/confinar.mjs');
const mode=process.argv[2]||'hyperframes';
const markers='<i style="position:absolute;left:0;top:0;width:54px;height:54px;background:#00ff00"></i><i style="position:absolute;right:0;top:0;width:54px;height:54px;background:#0000ff"></i><i style="position:absolute;left:0;bottom:0;width:54px;height:54px;background:#ffff00"></i><i style="position:absolute;right:0;bottom:0;width:54px;height:54px;background:#00ffff"></i>';
if(mode==='hyperframes'){
 const html=`<!DOCTYPE html><html><head><style>*{box-sizing:border-box}html,body{margin:0;width:1080px;height:1920px;overflow:hidden}#root{position:absolute;inset:0;background:#f5f3ee}#tile{position:absolute;left:210px;top:480px;width:660px;height:880px;border-radius:50px;background:#171b21;box-shadow:0 24px 40px #0004;color:white;font:80px sans-serif;display:grid;place-items:center}</style><script src="/recursos/gsap.min.js"></script></head><body><div id="root" data-composition-id="calibracion" data-start="0" data-duration="2" data-width="1080" data-height="1920" data-fps="30">${markers}<div id="tile">CALIBRACIÓN</div></div><script>const tl=gsap.timeline({paused:true});tl.fromTo('#tile',{x:-150,scale:.6,opacity:0},{x:0,scale:1,opacity:1,duration:.3,ease:'power3.out'}).to('#tile',{rotation:6,duration:.3},.7).to('#tile',{rotation:0,x:100,y:100,duration:.3},1.2).to('#tile',{scale:1.08,duration:.2},1.6);window.__timelines={calibracion:tl};</script></body></html>`;
 fs.writeFileSync(path.join(temp,'calibracion_hyperframes.html'),html);
 const workers=process.argv[3]||'1';const file=`hyperframes_${workers}_prueba.mp4`;
 const log=fs.openSync(path.join(temp,`hyperframes_${workers}_prueba.log`),'w');
 const started=Date.now();
 const r=spawnSync(process.execPath,[path.join(root,'.estado/herramientas/node_modules/hyperframes/bin/hyperframes.mjs'),'render',root,'--composition','.estado/tmp/calibracion_hyperframes.html','--output',path.join(temp,file),'--fps','30','--workers',workers,'--browser-gpu','--gpu','--sdr','--no-best-effort','--experimental-fast-capture=false'],{env:process.env,stdio:['ignore',log,log]});
 fs.closeSync(log);if(r.status!==0)throw Error('Falló HyperFrames; revisar '+file.replace('.mp4','.log'));
 console.log(JSON.stringify({herramienta:'HyperFrames',version:'0.8.147',workers:+workers,render_s:(Date.now()-started)/1000,archivo:'.estado/tmp/'+file}));
}else if(mode==='remotion'){
 const entry=path.join(temp,'calibracion_remotion.jsx');
 // Resolución explícita dentro de IVAN: el bundler no necesita instalaciones en otros directorios.
 const react=path.join(root,'.estado/herramientas/node_modules/react');
 const remotion=path.join(root,'.estado/herramientas/node_modules/remotion');
 fs.writeFileSync(entry,`import React from ${JSON.stringify(react)};import {registerRoot,Composition,AbsoluteFill,useCurrentFrame,interpolate,Easing} from ${JSON.stringify(remotion)};const Graphic=()=>{const f=useCurrentFrame();const p=interpolate(f,[0,9],[0,1],{extrapolateRight:'clamp',easing:Easing.out(Easing.cubic)});return <AbsoluteFill style={{background:'#f5f3ee'}}><div style={{position:'absolute',left:210,top:480,width:660,height:880,borderRadius:50,background:'#171b21',boxShadow:'0 24px 40px #0004',color:'white',font:'80px sans-serif',display:'grid',placeItems:'center',transform:\`translateX(\${-150*(1-p)}px) scale(\${.6+.4*p}) rotate(\${Math.sin(f/12)*6}deg)\`}}>CALIBRACIÓN</div>{[[0,0,'#00ff00'],['auto',0,'#0000ff'],[0,'auto','#ffff00'],['auto','auto','#00ffff']].map(([x,y,c],i)=><i key={i} style={{position:'absolute',left:x,top:y,right:x==='auto'?0:'auto',bottom:y==='auto'?0:'auto',width:54,height:54,background:c}}/>)}</AbsoluteFill>};registerRoot(()=> <Composition id="Calibracion" component={Graphic} durationInFrames={60} fps={30} width={1080} height={1920}/>);`);
 const {bundle}=await import('../.estado/herramientas/node_modules/@remotion/bundler/dist/index.js');
 const {selectComposition,renderMedia}=await import('../.estado/herramientas/node_modules/@remotion/renderer/dist/index.js');
 const started=Date.now();
 const serveUrl=await bundle({entryPoint:entry,outDir:path.join(temp,'remotion_bundle'),enableCaching:false,publicDir:null,rootDir:path.join(root,'.estado/herramientas')});
 const opts={serveUrl,id:'Calibracion',browserExecutable:'/usr/bin/google-chrome',chromiumOptions:{gl:'angle-egl'},logLevel:'verbose'};
 const composition=await selectComposition(opts);
 await renderMedia({...opts,composition,codec:'h264',outputLocation:path.join(temp,'remotion_prueba.mp4'),hardwareAcceleration:'required',concurrency:1,overwrite:true,videoBitrate:'12M'});
 const proof={herramienta:'Remotion',version:'4.0.534',estado:'operativo',hardwareAcceleration:'required',render_s:(Date.now()-started)/1000,archivo:'.estado/tmp/remotion_prueba.mp4'};
 fs.writeFileSync(path.join(temp,'remotion_prueba.json'),JSON.stringify(proof,null,2));console.log(JSON.stringify(proof));
}else throw Error('Motor desconocido');
