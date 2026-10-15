/* Componentes Ascendia V4. Lienzo fijo; una cámara original, sin relleno artificial. */
window.crearAscendiaRuntime=async ROOT=>{
 const P=await (await fetch('/'+ROOT.dataset.project+'/proyecto.json')).json();
 const F=await (await fetch('/'+ROOT.dataset.project+'/rostro.json')).json();
 await Promise.all([document.fonts.load('100px Sequel'),document.fonts.load('100px Scholar')]);
 const tl=gsap.timeline({paused:true}),INK='#191b1e',PAPER='#f4f1e9',RED='#f23848';
 const $=id=>document.getElementById(id);let uid=0;
 function el(tag,parent,content='',style={}){const n=document.createElement(tag);n.id='v4_'+(++uid);n.innerHTML=content;Object.assign(n.style,{position:'absolute',...style});parent.appendChild(n);return n;}
 function group(parent,style={}){return el('div',parent,'',{inset:'0',...style});}
 function text(parent,content,x,y,size=80,style={}){return el('div',parent,content,{left:x+'px',top:y+'px',fontSize:size+'px',lineHeight:'1',whiteSpace:'nowrap',letterSpacing:'-2px',...style});}
 function windowAt(n,a,b){if(a===0){n.style.visibility='visible';}else{tl.set(n,{visibility:'hidden'},0);tl.set(n,{visibility:'visible'},a);}tl.set(n,{visibility:'hidden'},b);return n;}
 function move(n,t,properties,d=.24){tl.to(n,{...properties,duration:d,ease:'power3.inOut'},t);return n;}
 function reveal(n,t,d=.22,from={y:45}){tl.fromTo(n,{clipPath:'inset(0 0 100% 0)',...from},{clipPath:'inset(0 0 0% 0)',x:0,y:0,duration:d,ease:'power3.out'},t);return n;}
 function svg(parent,content,style={}){return el('div',parent,`<svg viewBox="0 0 1080 1920" width="1080" height="1920" xmlns="http://www.w3.org/2000/svg">${content}</svg>`,{inset:0,pointerEvents:'none',...style});}
 function morph(path,t,destination,d=.28){tl.to(path,{attr:{d:destination},duration:d,ease:'power3.inOut'},t);}
 function travel(n,curve,t,d=.42,rotation=0){const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',curve);const len=path.getTotalLength(),state={p:0};tl.fromTo(state,{p:0},{p:1,duration:d,ease:'power2.inOut',onUpdate:()=>{const a=path.getPointAtLength(state.p*len);gsap.set(n,{x:a.x,y:a.y,rotation:rotation*Math.sin(state.p*Math.PI)});}},t);return n;}
 function draw(path,t,d=.35){const len=path.getTotalLength();tl.fromTo(path,{strokeDasharray:len,strokeDashoffset:len},{strokeDashoffset:0,duration:d,ease:'power2.out'},t);}
 const faceFrames=F.detecciones.filter(f=>f.smooth_chin);
 function faceAt(t){if(!faceFrames.length)throw Error('No hay detección facial válida');let index=0;while(index<faceFrames.length-2&&faceFrames[index+1].t<=t)index++;const a=faceFrames[index],b=faceFrames[index+1]||a,k=a===b?0:Math.max(0,Math.min(1,(t-a.t)/(b.t-a.t)));return a.smooth_chin.map((v,i)=>v+(b.smooth_chin[i]-v)*k);}
 function presenter(){
  const poses=(P.presentador||[]).map((p,i)=>{
   const suffix=i?String(i):'',wrapper=$('actor'+suffix),plane=$('actorPlane'+suffix);
   if(!wrapper||!plane)throw Error('Falta la capa original para la presencia '+i);
   const state={blend:p.modo==='split'?1:0,zoom:1};windowAt(wrapper,p.inicio,p.fin);
   if(p.zoom!==undefined)tl.to(state,{zoom:p.zoom_escala||1.08,duration:p.zoom_duracion||.2,ease:'power3.out'},p.zoom);
   if(p.split_desde!==undefined)tl.to(state,{blend:1,zoom:1,duration:.24,ease:'power3.inOut'},p.split_desde);
   const withCaption=P.subtitulos.some(c=>c.inicio<p.fin&&c.fin>p.inicio);
   // Con textos tradicionales, reservar espacio bajo barbilla dentro de la zona segura.
   return {p,wrapper,plane,state,top:p.split_proporcion_superior??(withCaption?.5:.6),chin:p.barbilla_destino_px??(withCaption?1600:1742),fit:p.escala_split??1.15};
  });
  const caption=el('div',ROOT,'',{left:'130px',width:'820px',fontSize:'72px',textAlign:'center',whiteSpace:'nowrap',lineHeight:'1.05',color:'white',textShadow:'2px 4px 5px rgba(0,0,0,.85)',zIndex:80});
  const diagnostic=ROOT.dataset.debugGeometry==='true'?el('pre',ROOT,'',{left:'30px',top:'1420px',fontSize:'28px',background:'#fff',color:'#000',zIndex:9999}):null;
  function update(){window.scrollTo(0,0);const t=tl.time(),chin=faceAt(t);let active;
   if(diagnostic){const rect=ROOT.getBoundingClientRect(),cs=getComputedStyle(ROOT),bs=getComputedStyle(document.body);diagnostic.textContent=JSON.stringify({t,rect:[rect.x,rect.y,rect.width,rect.height],client:[ROOT.clientWidth,ROOT.clientHeight],rootTransform:cs.transform,bodyTransform:bs.transform,bodyZoom:bs.zoom,inner:[innerWidth,innerHeight],scroll:[scrollX,scrollY],scrollH:document.documentElement.scrollHeight},null,2);}
   for(const pose of poses){const {p,state,wrapper,plane}=pose,blend=state.blend;
   const scale=state.zoom*(1-blend)+pose.fit*blend;
   const tx=(1080-1080*scale)/2*(1-blend)+(540-chin[0]*1080*scale)*blend;
   const ty=(900-900*scale)*(1-blend)+(pose.chin-chin[1]*1920*scale)*blend;
   wrapper.style.clipPath=`inset(${pose.top*1920*blend}px 0 0 0)`;
   plane.style.transform=`matrix(${scale},0,0,${scale},${tx},${ty})`;
   if(t>=p.inicio&&t<p.fin)active={scale,ty};}
   const sub=P.subtitulos.find(c=>t>=c.inicio&&t<c.fin);
   caption.textContent=sub?.texto||'';if(active)caption.style.top=(chin[1]*1920*active.scale+active.ty+26)+'px';
   caption.style.visibility=active&&sub?'visible':'hidden';
  }
  tl.eventCallback('onUpdate',update);return update;
 }
 function finish(){
  const update=presenter();tl.set({}, {},P.motor.alcance_hasta_s);
  window.__timelines={ivan:tl};
  window.seekForReview=async t=>{
   tl.seek(t,false);update();
   const activeVideos=Array.from(document.querySelectorAll('video')).filter(v=>t>=Number(v.dataset.start)&&t<Number(v.dataset.start)+Number(v.dataset.duration));
   await Promise.all(activeVideos.map(async v=>{
    await new Promise((resolve,reject)=>{if(v.readyState>=2)return resolve();v.addEventListener('loadeddata',resolve,{once:true});v.addEventListener('error',()=>reject(Error('No se puede decodificar '+v.id)),{once:true});});
    const target=Number(v.dataset.mediaStart||0)+t-Number(v.dataset.start);
    if(Math.abs(v.currentTime-target)>.005)await new Promise(resolve=>{v.addEventListener('seeked',resolve,{once:true});v.currentTime=target;});
   }));
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  };
  update();window.renderReady=true;
 }
 return {ROOT,P,F,tl,INK,PAPER,RED,$,el,group,text,windowAt,move,reveal,svg,morph,travel,draw,finish};
};
