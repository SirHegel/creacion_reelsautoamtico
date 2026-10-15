/* Composición abierta por grafo y acciones: una escena nueva no requiere
   otro módulo escrito a mano. Primitivas y recursos del sistema CLONE. */
(() => {
 const Clone=window.Clone;
 const ops=new Set(['enter','transfer','type','collect','resolve','transform','camera']);
 const kinds=new Set(['message','terminal','agent','result','phone','editorial']);
 const box=(x,y,w,h,fill,rad=16,attrs='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rad}" fill="${fill}" ${attrs}/>`;
 const group=(C,id,inner,attrs='')=>`<g id="${C.id(id)}" ${attrs}>${inner}</g>`;
 function graphValidate(p,d){
  if(!['pipeline','hub','comparison'].includes(p.layout))throw Error('Layout de grafo desconocido');
  if(!Array.isArray(p.nodes)||p.nodes.length<2||p.nodes.length>6)throw Error('El grafo admite2–6nodos; dividir ideas más grandes');
  const ids=new Set();
  p.nodes.forEach(n=>{
   if(!/^[a-z][a-z0-9_-]{0,35}$/.test(n.id)||ids.has(n.id))throw Error('Nodo inválido o repetido');ids.add(n.id);
   if(!kinds.has(n.kind))throw Error('Primitiva desconocida');
   if(typeof n.label!=='string'||n.label.length>45||String(n.body||'').length>140)throw Error('Contenido excesivo para nodo');
  });
  if(!Array.isArray(p.edges)||p.edges.length>10)throw Error('El grafo admite≤10relaciones');
  p.edges.forEach(edge=>{if(!ids.has(edge.from)||!ids.has(edge.to)||edge.from===edge.to)throw Error('Relación inválida');});
  if(!Array.isArray(p.steps)||p.steps.length<4||p.steps.length>36)throw Error('Se requieren4–36acciones conectadas');
  const seen=new Set();
  p.steps.forEach(s=>{
   if(!ops.has(s.op)||!Number.isFinite(s.at)||!Number.isFinite(s.duration)||s.at<0||s.duration<=0||s.at+s.duration>d+.001)throw Error('Acción inválida/fuera de tiempo');
   if(s.op!=='camera'&&!ids.has(s.target))throw Error('Target de acción inexistente');
   if(['transfer','collect'].includes(s.op)&&(!ids.has(s.from)||!ids.has(s.to)||s.from===s.to))throw Error('Transferencia requiere dos nodos distintos');
   if(s.op==='enter')seen.add(s.target);
   if(s.op==='type'&&String(s.text||'').length>140)throw Error('Texto de acción excesivo');
   if(s.op==='camera'&&s.scale!==undefined&&(!(s.scale>=1&&s.scale<=1.12)))throw Error('Cámara fuera de límites');
  });
  if(seen.size!==ids.size)throw Error('Cada nodo necesita una entrada explícita');
  if(!p.steps.some(s=>['transfer','collect'].includes(s.op))||!p.steps.some(s=>['resolve','transform'].includes(s.op)))throw Error('Falta interacción o transformación; no aceptar diapositivas');
 }
 function locations(nodes,layout){
  if(layout==='hub'){
   const mid=nodes.findIndex(n=>['agent','terminal'].includes(n.kind));
   const ring=[[150,260],[570,260],[150,910],[570,910],[360,1080]];let index=0;
   return nodes.map((n,i)=>i===mid?{x:360,y:565}:{x:ring[index][0],y:ring[index++][1]});
  }
  if(layout==='comparison')return nodes.map((n,i)=>({x:i%2?530:190,y:310+Math.floor(i/2)*305}));
  if(nodes.length<=3)return nodes.map((n,i)=>({x:360,y:[270,565,910][i]}));
  return nodes.map((n,i)=>({x:i%2?530:190,y:265+Math.floor(i/2)*305}));
 }
 function skin(C,n,index,point){
  const compact=C.params.nodes.length>3||C.params.layout==='comparison',w=compact?285:552;
  const e=C.escape,label=C.text(0,-35,n.label,{font:'Sequel',size:32,anchor:'middle',width:w-48,id:C.id(n.id+'-label')});
  const body=C.text(0,20,n.body||'',{size:20,weight:400,anchor:'middle',width:w-48,id:C.id(n.id+'-body')});
  let inner='';let localOrigin='0 0';
  if(n.kind==='agent'){
   const role=n.role||'agent_entrepreneur';
   inner=C.sprite(role.startsWith('agent_')?role:'agent_'+role,-76,-85,152)+box(-126,87,252,36,'#fff',18,`filter="${C.soft}"`)+C.text(0,112,n.label,{font:'Mono',size:18,anchor:'middle',width:231,id:C.id(n.id+'-label')})+
    C.text(0,160,n.body||'',{size:20,anchor:'middle',width:300,id:C.id(n.id+'-body')})+group(C,n.id+'-status',`<circle cx="81" cy="-35" r="16" fill="${C.colors.green}"/><path d="M72 -35l6 7 13-14" fill="none" stroke="white" stroke-width="3"/>`);
  }else if(n.kind==='terminal'){
   inner=box(-w/2,-118,w,236,'#171712',20,`filter="${C.shadow}"`)+box(-w/2,-118,w,30,'#24241e',15)+['#ef615b','#f2c448','#3cca54'].map((c,i)=>`<circle cx="${-w/2+20+i*16}" cy="-103" r="4" fill="${c}"/>`).join('')+
    C.text(0,-99,'PROCESO',{font:'Mono',size:10,fill:'#b4ad9e',anchor:'middle','letter-spacing':2})+
    C.sprite('agent_base',-w/2+24,-78,35)+C.text(-w/2+76,-53,n.label,{size:24,font:'Mono',fill:'#eee9df',width:w-99})+box(-w/2+22,-25,w-44,65,'none',11,'stroke="#655d4b" stroke-width="1"')+
    C.text(-w/2+36,2,'>',{size:19,font:'Mono',fill:'#d77357'})+C.text(-w/2+60,2,n.body||'',{font:'Mono',size:16,weight:400,fill:'#eee9df',width:w-104,id:C.id(n.id+'-body')})+
    [0,1,2].map(i=>group(C,n.id+'-field'+i,box(-w/2+28+i*(w-55)/3,64,(w-75)/3,8,'#77736b',4))).join('')+
    group(C,n.id+'-status',C.text(0,101,'✓',{font:'Mono',size:26,fill:C.colors.green,anchor:'middle'}));
  }else if(n.kind==='phone'){
   const contents=box(14,14,272,612,'#f3f3f5',52)+C.text(150,110,n.label,{size:23,anchor:'middle',width:232})+
    box(30,154,240,104,'white',18)+C.text(150,216,n.body||'',{size:17,anchor:'middle',width:217,id:C.id(n.id+'-body')})+
    [0,1,2].map(i=>group(C,n.id+'-field'+i,box(32,290+i*64,236,44,i===0?'#faeee7':'#fff',12)+`<circle cx="51" cy="${312+i*64}" r="7" fill="#d77357"/>`+box(71,305+i*64,157,8,'#d9d8d9',4))).join('')+
    group(C,n.id+'-status',box(34,534,232,48,C.colors.green,13)+C.text(150,565,'✓',{size:24,fill:'white',anchor:'middle'}));
   inner=Clone.primitives.phoneFrame(C,n.id+'-phone',contents,{x:-104,y:-220,width:208});
  }else if(n.kind==='editorial'){
   inner=label+body+group(C,n.id+'-status',`<path d="M-95 56H95" stroke="${C.colors.clay}" stroke-width="3"/>`);
  }else{
   inner=box(-w/2,-82,w,164,'#fff',20,`filter="${C.soft}"`)+
    (n.asset?C.image(n.asset,-w/2+19,-73,21):'')+C.text(-w/2+(n.asset?48:21),-58,n.kind==='result'?'RESULTADO':'SOLICITUD',{font:'Mono',size:10,weight:400,fill:C.colors.secondary,'letter-spacing':2,id:C.id(n.id+'-meta')})+
    C.text(0,-12,n.label,{font:'Sequel',size:31,anchor:'middle',width:w-55,id:C.id(n.id+'-label')})+
    C.text(0,33,n.body||'',{size:20,weight:400,anchor:'middle',width:w-55,id:C.id(n.id+'-body')})+
    group(C,n.id+'-status',`<circle cx="${w/2-25}" cy="-61" r="11" fill="${C.colors.green}"/><path d="M${w/2-30} -61l3 4 6-8" fill="none" stroke="white" stroke-width="2"/>`)+
    (n.kind==='message'?`<path d="M${w/2-24} 56l9 9 9-9" fill="none" stroke="#d4c5bd" stroke-width="2"/>`:'');
  }
  return `<g id="${C.id(n.id+'-position')}" transform="translate(${point.x} ${point.y})">${group(C,n.id,inner)}</g>`;
 }
 Clone.register('composition_graph',{
  description:'Grafo abierto de entidades y acciones semánticas. Combina las primitivas CLONE y crea variaciones nuevas con transferencias, escritura, reacción, transformación y cámara.',
  source:'Sistema CLONE, composición nueva; no aparece literalmente en la referencia',reference:[],durationRange:[3,15],
  defaults:{title:'UN PROCESO CONECTADO',caption:'ENTRADA → ACCIÓN → RESULTADO',conceptual:true,layout:'pipeline',
   nodes:[{id:'input',kind:'message',label:'Entrada',body:'Información recibida'},{id:'system',kind:'terminal',label:'Análisis',body:'Procesar la entrada'},{id:'output',kind:'result',label:'Resultado',body:'Información transformada'}],
   edges:[{from:'input',to:'system',label:'analizar'},{from:'system',to:'output',label:'entregar'}],
   steps:[{at:0,duration:.2,op:'enter',target:'input'},{at:.2,duration:.6,op:'type',target:'input',text:'Información recibida'},{at:.8,duration:.2,op:'enter',target:'system'},{at:1,duration:.4,op:'transfer',target:'system',from:'input',to:'system'},{at:1.4,duration:.7,op:'type',target:'system',text:'Procesar la entrada'},{at:2.1,duration:.4,op:'transform',target:'system',text:'Información analizada'},{at:2.5,duration:.2,op:'enter',target:'output'},{at:2.7,duration:.4,op:'transfer',target:'output',from:'system',to:'output'},{at:3.1,duration:.7,op:'type',target:'output',text:'Información transformada'},{at:3.8,duration:.5,op:'transform',target:'output',text:'Resultado preparado'},{at:4.3,duration:.3,op:'camera',target:'output',scale:1.05},{at:4.6,duration:.4,op:'camera',target:'output',scale:1}]},
  parameters:{title:'texto≤80',caption:'texto≤100',conceptual:'etiqueta visible de representación conceptual',layout:'pipeline|hub|comparison',nodes:'2–6entidades con skins originales',edges:'hasta10 relaciones reales de significado',steps:'4–36acciones con tiempo en segundos'},
  build(C){
   const p=C.params,d=C.duration;graphValidate(p,d);
   const homes=locations(p.nodes,p.layout);
   const byId=Object.fromEntries(p.nodes.map((n,i)=>[n.id,{node:n,home:homes[i],point:{...homes[i],scale:1,alpha:1}}]));
   const compact=p.nodes.length>3||p.layout==='comparison',cardWidth=compact?285:552;
   function route(from,to){
    const a=byId[from],b=byId[to];
    const halfH=n=>n.kind==='phone'?220:n.kind==='terminal'?118:n.kind==='agent'?110:n.kind==='editorial'?42:82;
    const halfW=n=>n.kind==='phone'?104:n.kind==='agent'?92:compact?142:276;
    const dy=b.point.y-a.point.y,dx=b.point.x-a.point.x;
    const backwards=dy<-220;
    if(backwards){
     // Un retorno rodea las superficies intermedias; nunca cruza al agente.
     const x=compact?640:624;
     const aa={x:Math.min(630,a.point.x+halfW(a.node)*a.point.scale),y:a.point.y};
     const bb={x:Math.min(630,b.point.x+halfW(b.node)*b.point.scale),y:b.point.y};
     return [aa,{x,y:aa.y},{x,y:bb.y},bb];
    }
    const horizontal=Math.abs(dx)>Math.abs(dy)*.8;
    const aa=horizontal?{x:a.point.x+Math.sign(dx)*halfW(a.node)*a.point.scale,y:a.point.y}:{x:a.point.x,y:a.point.y+Math.sign(dy)*halfH(a.node)*a.point.scale};
    const bb=horizontal?{x:b.point.x-Math.sign(dx)*halfW(b.node)*b.point.scale,y:b.point.y}:{x:b.point.x,y:b.point.y-Math.sign(dy)*halfH(b.node)*b.point.scale};
    return horizontal?[aa,{x:(aa.x+bb.x)/2,y:aa.y},{x:(aa.x+bb.x)/2,y:bb.y},bb]:[aa,{x:aa.x,y:(aa.y+bb.y)/2},{x:bb.x,y:(aa.y+bb.y)/2},bb];
   }
   const cubic=(r,t)=>{const u=1-t;return {x:u**3*r[0].x+3*u*u*t*r[1].x+3*u*t*t*r[2].x+t**3*r[3].x,y:u**3*r[0].y+3*u*u*t*r[1].y+3*u*t*t*r[2].y+t**3*r[3].y};};
   const edgeState=p.edges.map(()=>({progress:0,alpha:0}));
   const edgePaths=p.edges.map((edge,i)=>group(C,'edge'+i,`<path id="${C.id('line'+i)}" fill="none" stroke="#d5c4bb" stroke-width="2"/>`)).join('');
   const packets=p.steps.map((s,i)=>{if(!['transfer','collect'].includes(s.op))return'';
    const edge=p.edges.find(e=>e.from===s.from&&e.to===s.to),label=s.text||edge?.label||byId[s.from].node.label;
    return group(C,'packet'+i,box(-80,-23,160,46,C.colors.dark,13,`filter="${C.soft}"`)+C.text(0,6,label,{size:16,font:'Mono',weight:400,fill:'#eee9df',anchor:'middle',width:138}));}).join('');
   // Los paneles reciben su detalle dentro de la misma geometría, no imágenes de relleno.
   const nodeMarkup=p.nodes.map((n,i)=>skin(C,n,i,homes[i]).replace('</g></g>',(n.kind==='message'||n.kind==='result')?'</g>'+group(C,n.id+'-details',`<path d="M-247 28H247" stroke="#514039" stroke-width="1"/>`+C.text(0,108,(p.edges.some(e=>e.to===n.id)?[...new Set(p.edges.filter(e=>e.to===n.id).map(e=>byId[e.from].node.label))].join(' + ')+' → ':'')+n.label,{font:'Mono',size:16,fill:'#d77357',anchor:'middle',width:490}))+'</g></g>':'</g></g>')).join('');
   const conceptualCaption=/^(representaci[oó]n|esquema|composici[oó]n) conceptual$/i.test(p.caption.trim());
   C.root.innerHTML=C.svg(box(0,0,720,1280,C.colors.paper,0,`id="${C.id('background')}"`)+
    `<defs><linearGradient id="${C.id('beam')}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#fff" stop-opacity=".30"/><stop offset="1" stop-color="#ffe3be" stop-opacity=".05"/></linearGradient></defs>`+
    group(C,'spotlight',`<path d="M307 0H413L630 890H90Z" fill="url(#${C.id('beam')})"/><ellipse cx="360" cy="886" rx="255" ry="62" fill="#d4bfa4" fill-opacity=".12"/>`)+
    group(C,'world',edgePaths+nodeMarkup+packets)+
    group(C,'heading',C.text(360,130,p.title,{font:'Sequel',size:42,anchor:'middle',width:640}))+
    group(C,'caption',conceptualCaption?'':C.editorial(p.caption,1178,56))+
    (p.conceptual?C.text(360,1243,'ESQUEMA CONCEPTUAL',{font:'Mono',size:12,weight:400,fill:C.colors.ink,anchor:'middle',id:C.id('conceptual-note'),'letter-spacing':2}):''));
   const tl=gsap.timeline({paused:true}),writers={},metaStates={};
   gsap.set(C.q('world'),{svgOrigin:'360 640',smoothOrigin:false});
   tl.set(C.q('spotlight'),{opacity:0},0);
   // El título solo abre la composición; desaparece antes de los cambios de escala.
   tl.to(C.q('heading'),{y:-24,opacity:0,duration:.22,ease:'power3.in'},Math.min(1.12,d*.3));
   p.nodes.forEach(n=>{
    const item=byId[n.id];
    if(C.q(n.id+'-meta')){const state={final:0};metaStates[n.id]=state;tl.set(state,{final:0},0);C.repaints.push(()=>C.q(n.id+'-meta').textContent=state.final>.5?(n.kind==='result'?'RESULTADO':'ESTADO'):(n.kind==='result'?'RESULTADO':'SOLICITUD'));}
    C.repaints.push(()=>{const t=item.point;C.q(n.id+'-position').setAttribute('transform',`translate(${t.x} ${t.y}) scale(${t.scale})`);C.q(n.id+'-position').setAttribute('opacity',t.alpha);});
    gsap.set(C.q(n.id),{svgOrigin:'0 0',smoothOrigin:false});
    tl.set(C.q(n.id),{opacity:0,y:26},0);tl.set(C.q(n.id+'-status'),{opacity:0},0);
    if(C.q(n.id+'-details'))tl.set(C.q(n.id+'-details'),{opacity:0},0);
    const node=C.q(n.id+'-body'),typing=p.steps.filter(s=>(s.op==='type'||(['resolve','transform'].includes(s.op)&&s.text))&&s.target===n.id);
    if(node&&typing.length){
     const width=n.kind==='agent'?300:n.kind==='phone'?217:cardWidth-(n.kind==='terminal'?104:55),font=n.kind==='terminal'?'Mono':'InterUI',base=n.kind==='terminal'?16:20;
     const full=[n.body||'',...typing.map(s=>s.text||n.body||'')],size=Math.min(...full.map(t=>C.fit(t,width,base,font)));
     if(size<11)throw Error('Texto de acción demasiado largo: dividir escena');node.setAttribute('font-size',size);
     const writer={value:0,index:-1},texts=typing.map(s=>Array.from(s.text||n.body||''));writers[n.id]={state:writer,texts,next:0};
     C.repaints.push(()=>{node.textContent=writer.index<0?'':texts[Math.round(writer.index)].slice(0,Math.floor(writer.value)).join('');});
     tl.set(writer,{value:0,index:-1},0);
    }
   });
   p.edges.forEach((edge,i)=>C.repaints.push(()=>{
    const r=route(edge.from,edge.to),path=C.q('line'+i),state=edgeState[i];let length=0,last=r[0];
    for(let k=1;k<=24;k++){const next=cubic(r,k/24);length+=Math.hypot(next.x-last.x,next.y-last.y);last=next;}
    path.setAttribute('d',`M${r[0].x} ${r[0].y}C${r[1].x} ${r[1].y} ${r[2].x} ${r[2].y} ${r[3].x} ${r[3].y}`);
    path.style.strokeDasharray=length;path.style.strokeDashoffset=length*(1-state.progress);C.q('edge'+i).setAttribute('opacity',state.alpha);
   }));
   p.steps.forEach((s,i)=>{if(C.q('packet'+i))tl.set(C.q('packet'+i),{opacity:0},0);});
   let focus=null,unfolded=false;const layoutAt=new Set();const first=p.steps.find(s=>s.op==='enter')?.target;
   if(p.layout==='pipeline'&&p.nodes.length<=3&&first)tl.set(byId[first].point,{y:590},0);
   function restore(at,len=.25){
    if(!focus)return;
    p.nodes.forEach(n=>{
     const item=byId[n.id];tl.to(item.point,{...item.home,scale:1,alpha:1,duration:len,ease:'power3.inOut'},at);
     if(['agent','editorial'].includes(n.kind)){
      if(n.kind==='editorial'&&C.q(n.id+'-label'))tl.to(C.q(n.id+'-label'),{attr:{fill:C.colors.ink},duration:len},at);
      tl.to(C.q(n.id+'-body'),{attr:{fill:C.colors.ink},duration:len},at);
     }else if(['message','result'].includes(n.kind)){
      const rect=C.q(n.id).querySelector('rect');tl.to(rect,{attr:{x:-cardWidth/2,y:-82,width:cardWidth,height:164,fill:'#fff',rx:20},duration:len,ease:'power3.inOut'},at);
      tl.to(C.q(n.id+'-label'),{attr:{fill:C.colors.ink,y:-12},duration:len},at);tl.to(C.q(n.id+'-body'),{attr:{fill:C.colors.ink,y:33},duration:len},at);
      if(C.q(n.id+'-meta'))tl.to(C.q(n.id+'-meta'),{attr:{y:-58,fill:C.colors.secondary},duration:len},at);
      if(C.q(n.id+'-details'))tl.to(C.q(n.id+'-details'),{opacity:0,duration:len},at);
     }
    });
    if(C.q('conceptual-note'))tl.to(C.q('conceptual-note'),{attr:{fill:C.colors.ink},duration:len},at);
    tl.to(C.q('background'),{attr:{fill:C.colors.paper},duration:len},at);tl.to(C.q('spotlight'),{opacity:0,duration:len},at);
    tl.to(C.q('world'),{scale:1,x:0,y:0,duration:len,ease:'power3.inOut'},at);focus=null;
   }
   tl.addLabel('entry',0).addLabel('result',p.steps.filter(s=>['resolve','transform'].includes(s.op)).at(-1)?.at||d*.8).addLabel('exit',d-.25);
   p.steps.forEach((s,i)=>{
    const target=C.q(s.target),at=s.at,len=s.duration;
    if(s.op==='enter'){
     if(!unfolded&&s.target!==first&&p.layout==='pipeline'&&p.nodes.length<=3){tl.to(byId[first].point,{...byId[first].home,duration:Math.min(.3,len),ease:'power3.inOut'},at);unfolded=true;}
     if(focus&&!focus.includes(s.target))restore(at,Math.min(.25,len));
     tl.to(target,{opacity:1,y:0,duration:len,ease:'power3.out'},at);
    }
    if(['transfer','collect'].includes(s.op)){
     restore(at,Math.min(.25,len*.4));
     const state={v:0},packet=C.q('packet'+i);
     C.repaints.push(()=>{const v=cubic(route(s.from,s.to),state.v);packet.setAttribute('transform',`translate(${v.x} ${v.y})`);});
     const edgeIndex=p.edges.findIndex(e=>e.from===s.from&&e.to===s.to);
     if(edgeIndex>=0){tl.to(edgeState[edgeIndex],{alpha:1,progress:1,duration:Math.min(.3,len),ease:'power2.out'},at);}
     tl.to(packet,{opacity:1,duration:.05},at);tl.fromTo(state,{v:0},{v:1,duration:len,ease:'power2.inOut',immediateRender:false},at);tl.to(packet,{opacity:0,duration:.08},at+len-.08);
     tl.to(C.q(s.from),{y:-8,scale:.97,duration:Math.min(.16,len/2),ease:'power2.inOut'},at);
     const reaction=Math.min(.16,len/2),settle=Math.min(.16,Math.max(0,d-at-len));
     tl.to(target,{y:-8,scale:1.025,duration:reaction,ease:'power2.out'},at+len-reaction);
     if(settle)tl.to(target,{y:0,scale:1,duration:settle,ease:'power2.inOut'},at+len);
     if(metaStates[s.to]&&byId[s.from].node.kind==='result')tl.set(metaStates[s.to],{final:1},at+len);
     if(s.op==='collect'){const dst=byId[s.to].home;tl.to(byId[s.from].point,{x:dst.x,y:dst.y,scale:.25,alpha:0,duration:len,ease:'power3.inOut'},at);}
    }
    if(s.op==='type'){
     const entry=writers[s.target];if(!entry)throw Error('La primitiva no admite escritura');const index=entry.next++,chars=entry.texts[index],writer=entry.state;
     tl.set(writer,{index,value:0},at);tl.fromTo(writer,{value:0},{value:chars.length,duration:len,ease:'none',immediateRender:false},at);
     [0,1,2].forEach(k=>{const field=C.q(s.target+'-field'+k);if(field){gsap.set(field,{svgOrigin:'0 0',smoothOrigin:false});tl.fromTo(field,{scaleX:.15},{scaleX:1,duration:len*.45,ease:'power2.out',immediateRender:false},at+k*len*.16);}});
    }
    if(['resolve','transform'].includes(s.op)){
     if(s.text){const entry=writers[s.target],index=entry.next++,writer=entry.state;tl.set(writer,{index,value:entry.texts[index].length},at+len*.15);tl.fromTo(C.q(s.target+'-body'),{opacity:0,y:8},{opacity:1,y:0,duration:Math.min(.25,len*.5),ease:'power3.out',immediateRender:false},at);}
     tl.to(C.q(s.target+'-status'),{opacity:1,duration:Math.min(.18,len)},at);
     if(s.op==='transform'){
      const kind=byId[s.target].node.kind;
      const together=p.steps.filter(t=>t.op==='transform'&&Math.abs(t.at-at)<.001).map(t=>t.target);
      // Acciones simultáneas comparten una sola reorganización. No timelines
      // rivales escribiendo posiciones distintas sobre el mismo elemento.
      if(!layoutAt.has(at)){
       layoutAt.add(at);
       p.nodes.forEach(n=>{
        const item=byId[n.id],selected=together.indexOf(n.id),active=selected>=0;
        const columns=Math.min(together.length,2),row=Math.floor(selected/2);
        const x=together.length===1?360:columns===2?(selected%2?540:180):360;
        const y=together.length<=2?590:390+row*390;
        const scale=active?(together.length===1?(kind==='agent'?1.8:1):n.kind==='agent'?1.05:.52):.9;
        tl.to(item.point,{x:active?x:item.home.x,y:active?y:item.home.y+(item.home.y<590?-120:120),scale,alpha:active?1:0,duration:len,ease:'power3.inOut'},at);
       });
       edgeState.forEach(e=>tl.to(e,{alpha:0,duration:len*.4},at));
       if(C.q('conceptual-note'))tl.to(C.q('conceptual-note'),{attr:{fill:'#aaa7a7'},duration:len*.7},at);
       tl.to(C.q('background'),{attr:{fill:'#000000'},duration:len*.7,ease:'power2.inOut'},at);
       tl.to(C.q('world'),{scale:1,x:0,y:0,duration:len,ease:'power3.inOut'},at);
      }
      if(kind==='agent'){
       tl.to(C.q('spotlight'),{opacity:1,duration:len},at);
       const pill=target.querySelector('rect');tl.to(pill,{attr:{x:-155,width:310,rx:22,fill:'#232322'},duration:len,ease:'power3.inOut'},at);
       tl.to(C.q(s.target+'-label'),{attr:{fill:'#fff'},duration:len*.4},at);
       tl.to(C.q(s.target+'-body'),{attr:{fill:'#fff'},duration:len*.5},at);
      }else if(['message','result'].includes(kind)){
       const rect=target.querySelector('rect');
       if(metaStates[s.target])tl.set(metaStates[s.target],{final:1},at+len*.5);
       tl.to(rect,{attr:{x:-310,y:-170,width:620,height:340,fill:'#19191b',rx:24},duration:len,ease:'power3.inOut'},at);
       tl.to(C.q(s.target+'-label'),{attr:{fill:'#fff',y:-32},duration:len,ease:'power3.inOut'},at);
       tl.to(C.q(s.target+'-body'),{attr:{fill:'#fff',y:72},duration:len,ease:'power3.inOut'},at);
       tl.to(C.q(s.target+'-meta'),{attr:{fill:'#d77357',y:-121},duration:len},at);
       if(C.q(s.target+'-details'))tl.to(C.q(s.target+'-details'),{opacity:1,duration:len*.5},at+len*.3);
      }else{tl.to(target,{scale:kind==='phone'?1.35:1.1,duration:len,ease:'power3.inOut'},at);if(C.q(s.target+'-label'))tl.to(C.q(s.target+'-label'),{attr:{fill:'#fff'},duration:len},at);tl.to(C.q(s.target+'-body'),{attr:{fill:'#fff'},duration:len},at);}
      focus=together;
     }else{
      tl.to(target,{scale:1.025,duration:len*.4,ease:'power3.out'},at);tl.to(target,{scale:1,duration:len*.6,ease:'power2.inOut'},at+len*.4);
     }
    }
    if(s.op==='camera'){
     // El foco está centrado por reflow; en diagramas el pan está limitado a24px.
     const home=byId[s.target]?.home||{x:360,y:640};
     const x=focus?0:Math.max(-24,Math.min(24,(360-home.x)*.06)),y=focus?0:Math.max(-24,Math.min(24,(640-home.y)*.06));
     tl.to(C.q('world'),{scale:s.scale||1.05,x,y,duration:len,ease:'power3.inOut'},at);
    }
   });
   return tl;
  }
 });
})();
