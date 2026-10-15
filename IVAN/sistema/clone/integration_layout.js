/* Reencuadre semántico POR INSTANCIA. No modifica el módulo, el SceneIR,
   el reloj ni los objetos originales de GSAP. Todas las mediciones ocurren
   durante setup; paint sólo interpola poses y repinta rutas nativas. */
window.CloneIntegrationLayout = (C,native,scene,options) => {
 'use strict';
 options=options||{};
 const fail=message=>{throw Error('Reencuadre '+scene.id+': '+message);};
 if(scene.family!=='composition_graph')fail('familia sin contrato de puntos');
 if(!native?.getChildren||!native?.seek||!Array.isArray(C.repaints))fail('timeline/contexto nativo no verificable');
 const nodes=scene.params.nodes,steps=scene.params.steps,edges=scene.params.edges;
 const duration=scene.duration,fps=30,epsilon=1e-5,visibleFloor=.015;
 if(!Array.isArray(nodes)||nodes.length<2||nodes.length>6||!Array.isArray(steps)||!Number.isFinite(duration)||duration<=0)fail('contrato de grafo inválido');
 const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const ease=gsap.parseEase('power3.inOut');
 const repaint=()=>C.repaints.forEach(fn=>fn());
 const originalTime=native.time();
 const records=new Map(),enters=new Map(),events=[];
 const transforms=()=>native.getChildren(true,true,false).flatMap(t=>t.targets?.()||[]);
 const candidates=[...new Set(transforms())].filter(p=>p&&typeof p==='object'&&!p.nodeType&&['x','y','scale','alpha'].every(k=>Number.isFinite(p[k])));
 const keys=['x','y','scale','alpha'];
 const clone=p=>Object.fromEntries(keys.map(k=>[k,p[k]]));
 const matches=(p,q)=>keys.every(k=>Math.abs(p[k]-q[k])<epsilon);
 const readPose=element=>{
  const matrix=element.transform?.baseVal?.consolidate()?.matrix;
  if(!matrix||Math.abs(matrix.b)>epsilon||Math.abs(matrix.c)>epsilon||Math.abs(matrix.a-matrix.d)>epsilon)fail('pose original no es una traslación/escala uniforme');
  return {x:matrix.e,y:matrix.f,scale:matrix.a,alpha:Number(element.getAttribute('opacity')??1)};
 };
 const reset=t=>{native.seek(0,false);native.seek(t,false);repaint();};
 try{
  reset(0);
  for(const n of nodes){
   const position=C.q(n.id+'-position'),body=C.q(n.id);
   if(!position||!body)fail('nodo sin superficie original: '+n.id);
   const initial=readPose(position),found=candidates.filter(p=>matches(p,initial));
   if(found.length>1)fail('punto GSAP ambiguo para '+n.id+' ('+found.length+')');
   if(found.length&&[...records.values()].some(r=>r.point===found[0]))fail('dos nodos comparten un punto GSAP');
   // Algunos nodos nunca animan su posición: sus acciones son escritura,
   // entradas y transferencia. El builder conserva ese punto en un cierre,
   // fuera de targets GSAP. Admitirlo requiere probar la matriz local constante
   // en TODOS los frames y límites; nunca inferir una pose móvil desde DOM.
   records.set(n.id,{node:n,point:found[0]||clone(initial),staticBinding:found.length===0,staticPoseSamples:0,position,body,initial,footprint:null,
    leaves:[...body.querySelectorAll('text,image,rect,path,circle,ellipse,line,polygon,polyline')].filter(el=>!el.closest('defs'))});
  }
  for(const [i,s]of steps.entries()){
   if(!Number.isFinite(s.at)||!Number.isFinite(s.duration)||s.at<0||s.duration<=0||s.at+s.duration>duration+.001)fail('acción fuera de reloj: '+i);
   if(s.op==='enter')enters.set(s.target,Math.min(enters.get(s.target)??Infinity,s.at));
  }
  for(const n of nodes)if(!enters.has(n.id))fail('no hay permiso de entrada para '+n.id);
  // Medición local: se omite únicamente la opacidad del contenedor de entrada.
  // Las superficies ocultas (status/details) no agrandan el encuadre hasta que
  // realmente aparecen. CTM relativo elimina cámara/posición/escala externas.
  const visibleLeaf=(el,body)=>{
   for(let p=el;p&&p!==body;p=p.parentElement){
    // La visibility heredada del host futuro corresponde al reloj global0
    // durante setup; no oculta una superficie muestreada con su reloj local.
    // Sí se respetan gates/opacity CSS efectiva y visibility local explícita.
    const css=getComputedStyle(p);if(Number(css.opacity)<.001||css.display==='none'||p.style.visibility==='hidden'||p.getAttribute('visibility')==='hidden')return false;
   }
   return true;
  };
  const merge=(a,b)=>!a?b:{x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),right:Math.max(a.right,b.right),bottom:Math.max(a.bottom,b.bottom)};
  const sampleTimes=[...new Set([0,duration,...Array.from({length:Math.ceil(duration*fps)},(_,i)=>i/fps),...steps.flatMap(s=>[s.at,s.at+s.duration])])].sort((a,b)=>a-b);
  for(const t of sampleTimes){
   reset(t);
   for(const r of records.values()){
    if(r.staticBinding){
     const pose=readPose(r.position);
     if(!matches(pose,r.initial))fail('pose sin target GSAP cambia durante el reloj nativo: '+r.node.id+' @'+t.toFixed(5));
     r.staticPoseSamples++;
    }
    const base=r.position.getCTM();if(!base)fail('CTM original no disponible');
    const inverse=base.inverse();
    for(const el of r.leaves){
     if(!visibleLeaf(el,r.body))continue;
     const b=el.getBBox(),ctm=el.getCTM();
     if(!ctm||!Number.isFinite(b.x+b.y+b.width+b.height)||b.width<=0||b.height<=0)continue;
     const m=inverse.multiply(ctm);
     const corners=[[b.x,b.y],[b.x+b.width,b.y],[b.x,b.y+b.height],[b.x+b.width,b.y+b.height]].map(([x,y])=>({x:m.a*x+m.c*y+m.e,y:m.b*x+m.d*y+m.f}));
     r.footprint=merge(r.footprint,{x:Math.min(...corners.map(p=>p.x)),y:Math.min(...corners.map(p=>p.y)),right:Math.max(...corners.map(p=>p.x)),bottom:Math.max(...corners.map(p=>p.y))});
    }
   }
  }
  for(const r of records.values()){
   if(!r.footprint||r.footprint.right-r.footprint.x<1||r.footprint.bottom-r.footprint.y<1)fail('superficie no medible: '+r.node.id);
   const b=r.footprint;r.footprint={x:b.x-10,y:b.y-10,w:b.right-b.x+20,h:b.bottom-b.y+20};
  }
 }finally{reset(originalTime);}
 // Una acción existente determina qué entidad o pareja explica la idea.
 // No se introducen acciones, conexiones, textos ni entradas nuevas.
 const grouped=new Map();
 steps.forEach((s,i)=>{
  let ids=['transfer','collect'].includes(s.op)?[s.from,s.to]:[s.target],layoutIds=null;
  // Una cámara existente puede preparar los puertos de una transferencia
  // inminente sin hacer visible su interlocutor todavía. Esto evita mover
  // el actor a través del destino mientras ya está circulando el paquete.
  if(s.op==='camera'){
   const next=steps.find(a=>a.at>s.at&&a.at-s.at<=.6&&['transfer','collect'].includes(a.op)&&[a.from,a.to].includes(s.target));
   if(next&&[next.from,next.to].every(id=>enters.get(id)<=s.at+epsilon))layoutIds=[next.from,next.to];
  }
  // La entrada de una fuente conserva su interlocutor ya existente si la
  // siguiente transferencia REAL de ese nodo lo necesita. Editorial abre
  // ideas por sí solo; no se añade una pareja decorativa.
  if(s.op==='enter'&&records.get(s.target)?.node.kind!=='editorial'){
   const next=steps.find(a=>a.at>=s.at&&['transfer','collect'].includes(a.op)&&[a.from,a.to].includes(s.target));
   if(next){const peer=next.from===s.target?next.to:next.from;
    if(enters.get(peer)<=s.at+epsilon&&records.get(peer)?.node.kind!=='editorial')ids=[next.from,next.to];
   }
  }
  if(ids.some(id=>!records.has(id)))fail('foco no resoluble: acción '+i);
  const key=s.at.toFixed(7),prior=grouped.get(key);
  if(prior){
   if(s.op==='transform'&&prior.ops.every(op=>op==='transform'))prior.ids=[...new Set([...prior.ids,...ids])];
   else {prior.ids=ids;prior.ops=[s.op];prior.layoutIds=layoutIds;}
   prior.indices.push(i);prior.length=Math.max(prior.length,s.duration);
  }else grouped.set(key,{at:s.at,length:s.duration,ids,layoutIds,ops:[s.op],indices:[i]});
 });
 for(const e of [...grouped.values()].sort((a,b)=>a.at-b.at)){
  e.ids=e.ids.filter(id=>enters.get(id)<=e.at+epsilon);
  if(!e.ids.length)fail('acción enfoca un nodo antes de su entrada: '+e.indices.join(','));
  if(e.ids.length>2){
   if(options.production&&!(options.focus_windows||[]).some(w=>w.scene_id===scene.id)){
    const original=CloneIntegrationFamilyLayout(C,native,scene,options);
    original.receipt.parallel_graph_policy='Preserve the original parallel native composition; no universal two-node quota or re-authored steps.';
    return original;
   }
   fail('foco simultáneo de más de dos nodos; revisar plan');
  }
 e.length=clamp(e.length,options.production?.35:.2,options.production?.7:.3);events.push(e);
 }
 const lerp=(a,b,u)=>Object.fromEntries(keys.map(k=>[k,a[k]+(b[k]-a[k])*u]));
 const empty=()=>Object.fromEntries([...records].map(([id,r])=>[id,{...r.initial,alpha:0}]));
 // Se reserva margen para la cámara original (zoom<=1.12) y sombras suaves.
 // El SVG no se comprime: cada skin mantiene su propia geometría interna.
 const regions={full:{x:50,y:180,w:620,h:720},split:{x:50,y:80,w:620,h:options.split_top===.5?456:520}};
 if(options.production){regions.split={x:50,y:80,w:620,h:456};regions.split55={x:50,y:80,w:620,h:520};}
 function poseFor(ids,region){
  const result=empty(),selected=ids.map(id=>records.get(id));
  const gap=ids.length===2?96:0,safety=1.12;
  const scales=selected.map(r=>Math.min(r.node.kind==='agent'||r.node.kind==='editorial'?2.05:1.8,(region.w-36)/(r.footprint.w*safety)));
  const total=selected.reduce((h,r,i)=>h+r.footprint.h*scales[i],0);
  const fit=Math.min(1,(region.h-36-gap)/(total*safety));
  const final=scales.map(s=>s*fit),height=selected.reduce((h,r,i)=>h+r.footprint.h*final[i],0)+gap;
  let top=region.y+(region.h-height)/2;
  selected.forEach((r,i)=>{
   const b=r.footprint,s=final[i];
   result[r.node.id]={x:region.x+region.w/2-(b.x+b.w/2)*s,y:top-b.y*s,scale:s,alpha:1};
   top+=b.h*s+gap;
  });
  return result;
 }
 function fromEvents(t,prepared){
  let e=null;for(const event of prepared){if(event.at>t+epsilon)break;e=event;}
  if(!e)return empty();
  const progress=clamp((t-e.at)/e.length,0,1),u=ease(progress);
  return Object.fromEntries([...records.keys()].map(id=>{
   const pose=lerp(e.from[id],e.to[id],u),a=e.from[id].alpha,b=e.to[id].alpha;
   if(e.twoStage&&e.exiting.includes(id))pose.alpha=a*(1-ease(clamp(progress*2,0,1)));
   else if(e.twoStage&&e.entering.includes(id))pose.alpha=b*ease(clamp(progress*2-(e.lead===id?0:1),0,1));
   else if(a>0&&b===0)pose.alpha=a*(1-ease(clamp((t-e.at)/Math.min(.12,e.length),0,1)));
   return [id,pose];
  }));
 }
 const prepared={};
 for(const [mode,region]of Object.entries(regions)){
  const list=[];
  for(const e of events){
   const from=fromEvents(e.at,list),to=poseFor(e.layoutIds||e.ids,region);
   for(const id of records.keys()){
    if(!e.ids.includes(id))to[id]={...from[id],alpha:0};
    if(from[id].alpha<epsilon&&to[id].alpha>epsilon)from[id]={...to[id],alpha:0};
   }
   const outgoing=[...records.keys()].filter(id=>from[id].alpha>.001&&!e.ids.includes(id));
   const incoming=e.ids.filter(id=>from[id].alpha<.001);
   const shared=e.ids.filter(id=>from[id].alpha>.001);
   const union=[...new Set([...e.ids,...outgoing])];
   const twoStage=union.length>2;let lead=null;
   if(twoStage&&!shared.length){
    // Sin vecino común, sólo un saliente permanece hasta que la primera
    // entrada puede tomar el relevo. Su compañero llega en la segunda fase.
    for(const id of outgoing.slice(0,-1)){from[id].alpha=0;to[id].alpha=0;}
    if(incoming.length===2)lead=incoming[0];
   }
   list.push({...e,from,to,twoStage,lead,exiting:outgoing,entering:incoming});
  }
  prepared[mode]=list;
 }

 // Ventanas de foco declaradas por el director: una entidad principal y
 // como máximo otra de apoyo. Posiciones preparadas una vez, sin timers.
 const focusPrepared=[];
 for(const window of (options.focus_windows||[]).filter(w=>w.scene_id===scene.id)){
  const ids=[window.primary_target,...(window.support_target?[window.support_target]:[])];
  if(ids.some(id=>!records.has(id)))fail('Foco declarado sin superficie nativa');
  const states={};
  for(const mode of Object.keys(regions)){
   const region=regions[mode],target=empty(),mainRecord=records.get(ids[0]),b=mainRecord.footprint;
   const mainScale=Math.min(1.8,(region.w-36)/(b.w*1.12),(region.h-(ids.length>1?190:36))/(b.h*1.12));
   target[ids[0]]={x:region.x+region.w/2-(b.x+b.w/2)*mainScale,y:region.y+region.h*.53-(b.y+b.h/2)*mainScale,scale:mainScale,alpha:1};
   if(ids.length>1){const support=records.get(ids[1]),sb=support.footprint,ss=Math.min(mainScale*.55,(region.w*.55)/(sb.w*1.12),145/(sb.h*1.12));
    target[ids[1]]={x:region.x+region.w/2-(sb.x+sb.w/2)*ss,y:region.y+40-sb.y*ss,scale:ss,alpha:1};
   }
   states[mode]=target;
  }
  focusPrepared.push({window,states});
 }
 const focusedPose=(t,id,fraction,ratio)=>{
  const globalTime=t+scene.start,index=focusPrepared.findIndex(p=>globalTime*30>=p.window.start_frame&&globalTime*30<p.window.end_frame);
  if(index<0)return null;const current=focusPrepared[index],previous=focusPrepared[index-1],duration=index===0?0:(options.production?.4:.2);
  const f=duration?ease(clamp((globalTime-current.window.start_frame/30)/duration,0,1)):1;
  const splitState=s=>options.production?lerp(s.split[id],s.split55[id],clamp((ratio-.5)/.05,0,1)):s.split[id];
  const to=lerp(current.states.full[id],splitState(current.states),fraction);
  if(!previous)return to;
  const from=lerp(previous.states.full[id],splitState(previous.states),fraction);
  // No conservar un tercer actor de salida si el siguiente foco usa dos.
  if(![current.window.primary_target,current.window.support_target].includes(id))return {...to,alpha:0};
  // Un actor antes invisible entra en su zona preparada; no atraviesa la
  // tipografía desde una posición histórica que nunca estuvo en pantalla.
  if(![previous.window.primary_target,previous.window.support_target].includes(id))return {...to,alpha:to.alpha*f};
  return lerp(from,to,f);
 };
 // Pose tables have no dependency on previous seeks or DOM layout.
 const table=Object.fromEntries(Object.entries(prepared).map(([mode,list])=>[mode,Array.from({length:Math.ceil(duration*fps)+1},(_,i)=>fromEvents(Math.min(duration,i/fps),list))]));
 const tableAt=(mode,t)=>{
  const f=clamp(t*fps,0,table[mode].length-1),a=Math.floor(f),b=Math.min(a+1,table[mode].length-1);
  return Object.fromEntries([...records.keys()].map(id=>[id,lerp(table[mode][a][id],table[mode][b][id],f-a)]));
 };
 const ns='http://www.w3.org/2000/svg';
 const gate=(element,name)=>{
  if(!element)fail('superficie nativa no disponible: '+name);
  const wrapper=document.createElementNS(ns,'g');wrapper.id=C.id('integration-layout-gate-'+name);
  element.parentNode.insertBefore(wrapper,element);wrapper.appendChild(element);return wrapper;
 };
 for(const [id,r]of records)r.gate=gate(r.position,id);
 const packetRecords=steps.flatMap((s,i)=>['transfer','collect'].includes(s.op)?[{element:C.q('packet'+i),from:s.from,to:s.to,step:s,index:i}]:[]);
 const edgeRecords=edges.map((e,i)=>({element:C.q('edge'+i),from:e.from,to:e.to}));
 for(const [i,r]of [...edgeRecords,...packetRecords].entries())r.gate=gate(r.element,'route-'+i);
 // Leer el objeto original de progreso (no reconstruir el estado del dibujo).
 // El tween de progress=1 identifica la primera transferencia de esta arista.
 const childTweens=native.getChildren(true,true,false);
 for(const r of edgeRecords){
  r.path=C.q('line'+edgeRecords.indexOf(r));
  const action=steps.find(s=>['transfer','collect'].includes(s.op)&&s.from===r.from&&s.to===r.to);
  if(!action)continue;
  const matching=childTweens.filter(t=>t.vars?.progress===1&&Math.abs(t.startTime()-action.at)<epsilon)
   .flatMap(t=>t.targets()).filter(p=>p&&!p.nodeType&&Number.isFinite(p.progress)&&Number.isFinite(p.alpha));
  const unique=[...new Set(matching)];
  if(unique.length!==1)fail('progreso de arista ambiguo o ausente: '+r.from+'→'+r.to);
  r.state=unique[0];
 }
 const motionEase=gsap.parseEase('power2.inOut');
 const route=(poses,from,to)=>{
  const a=records.get(from),b=records.get(to),pa=poses[from],pb=poses[to];
  const aa=a.footprint,bb=b.footprint,down=pb.y+bb.y*pb.scale>=pa.y+aa.y*pa.scale,pad=25;
  const start={x:pa.x+(aa.x+aa.w/2)*pa.scale,y:pa.y+(down?aa.y+aa.h:aa.y)*pa.scale+(down?pad:-pad)};
  const end={x:pb.x+(bb.x+bb.w/2)*pb.scale,y:pb.y+(down?bb.y:bb.y+bb.h)*pb.scale+(down?-pad:pad)};
  return [start,{x:start.x,y:(start.y+end.y)/2},{x:end.x,y:(start.y+end.y)/2},end];
 };
 const cubic=(r,t)=>{const u=1-t;return{x:u**3*r[0].x+3*u*u*t*r[1].x+3*u*t*t*r[2].x+t**3*r[3].x,y:u**3*r[0].y+3*u*u*t*r[1].y+3*u*t*t*r[2].y+t**3*r[3].y};};
 const receipt={version:1,method:'semantic_action_native_point_reflow',family_source_changed:false,scene_ir_changed:false,
  measurement:'visible native surfaces sampled once; relative CTM, 30 FPS and action boundaries',sampled_source_frames:table.full.length,
  region_native_units:regions,split_fraction:'normalized 0 full → 1 split55%',max_focus_nodes:2,
  enter_pair_policy:'Use next existing transfer endpoints only when the peer already entered; editorial peer excluded.',
  routing_approach:'Existing camera may prepare positions for a transfer within 0.6s; peer remains hidden until its actual focus action.',
  visibility_gates:'Independent SVG wrappers; native CSS opacity is preserved; sub-1.5% tails are gated to prevent lingering ghosts.',
  native_point_mapping:[...records].filter(([,r])=>!r.staticBinding).map(([id,r])=>({id,source_pose:r.initial,footprint:r.footprint,binding:'native_gsap_object'})),
  verified_constant_native_pose_bindings:[...records].filter(([,r])=>r.staticBinding).map(([id,r])=>({id,source_pose:r.initial,binding:'verified_constant_native_pose',
   sampled_frames_and_boundaries:r.staticPoseSamples,footprint:r.footprint,changes_rejected:true,paint:'matrix after native repaint; routes and packets recalculated from same existing clock'})),
  semantic_events:events.map(e=>({at:e.at,duration:e.length,node_ids:e.ids,layout_node_ids:e.layoutIds||e.ids,step_indices:e.indices,ops:e.ops})),
  visibility_policy:'Only nodes with an existing enter; camera may restore its already-entered target after native focus hid it.',
  routes:'Native repaints with temporary adapted points; measured surface ports replace overlapping native half-height ports; original edge progress and numeric GSAP state preserved.',
  geometry_routing_override:{gap_native:96,packet_boundary_clearance:25,path:'Cubic between measured source/target surfaces; existing packet clock/ease and text.',native_actions_changed:false},autonomous_timers:false};
 return {receipt,paint(nativeTime,outputLocalTime,splitFraction=0,splitRatio=options.split_top||.55){
  if(!Number.isFinite(nativeTime)||!Number.isFinite(outputLocalTime)||!Number.isFinite(splitFraction))fail('reloj o fracción no finita');
  if(nativeTime<-.001||nativeTime>duration+.001||splitFraction<-.001||splitFraction>1.001)fail('reloj o fracción fuera del contrato');
  const t=clamp(nativeTime,0,duration),fraction=clamp(splitFraction,0,1),full=tableAt('full',t),split=tableAt('split',t);
  if(options.production){const upper=tableAt('split55',t),ratio=clamp((splitRatio-.5)/.05,0,1);for(const id of records.keys())split[id]=lerp(split[id],upper[id],ratio);}
  const saved=new Map(),poses={};
 const focus=(options.focus_windows||[]).find(w=>w.scene_id===scene.id&&(outputLocalTime+scene.start)*30>=w.start_frame&&(outputLocalTime+scene.start)*30<w.end_frame);
  try{
   for(const [id,r]of records){
    saved.set(id,clone(r.point));const pose=focusedPose(outputLocalTime,id,fraction,splitRatio)||lerp(full[id],split[id],fraction);
    if(focus&&id!==focus.primary_target&&id!==focus.support_target)pose.alpha=0;
    if(t<enters.get(id)-epsilon)pose.alpha=0;
    if(!keys.every(k=>Number.isFinite(pose[k]))||pose.scale<=0)fail('pose calculada inválida: '+id);
    poses[id]=pose;Object.assign(r.point,pose);
    r.gate.setAttribute('opacity',pose.alpha<visibleFloor?'0':'1');
   }
   repaint();
   for(const [id,r]of records)if(r.staticBinding){const p=poses[id];r.position.setAttribute('transform',`translate(${p.x} ${p.y}) scale(${p.scale})`);r.position.setAttribute('opacity',p.alpha);}
   for(const r of edgeRecords){
    const path=route(poses,r.from,r.to);let length=0,last=path[0];
    for(let i=1;i<=24;i++){const next=cubic(path,i/24);length+=Math.hypot(next.x-last.x,next.y-last.y);last=next;}
    r.path.setAttribute('d',`M${path[0].x} ${path[0].y}C${path[1].x} ${path[1].y} ${path[2].x} ${path[2].y} ${path[3].x} ${path[3].y}`);
    r.path.style.strokeDasharray=length;r.path.style.strokeDashoffset=length*(1-(r.state?.progress||0));
    r.gate.setAttribute('opacity',poses[r.from].alpha<visibleFloor||poses[r.to].alpha<visibleFloor?'0':'1');
   }
   for(const r of packetRecords){
    const progress=motionEase(clamp((t-r.step.at)/r.step.duration,0,1)),position=cubic(route(poses,r.from,r.to),progress);
    r.element.setAttribute('transform',`translate(${position.x} ${position.y})`);
    r.gate.setAttribute('opacity',poses[r.from].alpha<visibleFloor||poses[r.to].alpha<visibleFloor?'0':'1');
   }
  }finally{for(const [id,values]of saved)Object.assign(records.get(id).point,values);}
 }};
};

/* Las familias fijas mantienen sus objetos, repaints y timeline originales.
   Este wrapper sólo encuadra su superficie visible, una vez por aparición.
   No crea skins, no elige familias y no reemplaza acciones por zoom estático. */
window.CloneIntegrationFamilyLayout = (C,native,scene,options) => {
 'use strict';
 const svg=C.root.querySelector('svg'),ns='http://www.w3.org/2000/svg',fps=30;
 if(!svg||!native?.seek)throw Error('Superficie nativa no medible: '+scene.id);
 const view=svg.getAttribute('viewBox').trim().split(/\s+/).map(Number);
 if(view.length!==4||view.some(v=>!Number.isFinite(v))||view[2]<=0||view[3]<=0||Math.abs(view[2]/view[3]-9/16)>.001)throw Error('Familia sin viewport vertical verificable: '+scene.id);
 const originalTime=native.time(),leaves=[...svg.querySelectorAll('text,image,rect,path,circle,ellipse,line,polygon,polyline')].filter(n=>!n.closest('defs')&&!n.closest('[data-integration-fixed-overlay]'));
 const visible=n=>{for(let p=n;p&&p!==svg;p=p.parentElement){if(Number(getComputedStyle(p).opacity)<.10||getComputedStyle(p).display==='none')return false;}return true;};
 const isBackground=n=>n.tagName==='rect'&&Number(n.getAttribute('x')||0)===0&&Number(n.getAttribute('y')||0)===0&&Number(n.getAttribute('width'))===720&&Number(n.getAttribute('height'))===1280;
 const excludedBounds=[...(options.exclude_bounds_ids||[]),...(scene.family==='spotlight_agent'?[C.id('light')]:[])];
 const poses=[];
 try{
  for(const [index,window]of options.camera.entries()){
   if(window.state!=='split')continue;
   const first=Math.max(window.start_frame,Math.round(scene.start*fps)),last=Math.min(window.end_frame,Math.round((scene.start+scene.duration)*fps));
   if(first>=last)continue;
   let bounds=null,largestText=0,majorImage=0,samples=0;
   for(let f=first;f<last;f++){
    const outputTime=f/fps-scene.start,nativeTime=options.toNative(outputTime);
    native.seek(0,false);native.seek(nativeTime,false);C.repaints.forEach(fn=>fn());options.paint_instance?.(nativeTime,outputTime);
    const host=svg.getBoundingClientRect();if(!host.width||!host.height)throw Error('SVG sin dimensiones de medición: '+scene.id);
    for(const n of leaves){
     if(isBackground(n)||!visible(n)||excludedBounds.some(id=>n.closest('#'+CSS.escape(id))))continue;
     const font=Number(n.getAttribute('font-size')||0);if(n.tagName==='text'&&font>160)continue;
     const box=n.getBoundingClientRect();if(!box.width||!box.height)continue;
     let b={x:(box.x-host.x)*720/host.width,y:(box.y-host.y)*1280/host.height,w:box.width*720/host.width,h:box.height*1280/host.height};
     const intersect=(b,c)=>{const x=Math.max(b.x,c.x),y=Math.max(b.y,c.y),right=Math.min(b.x+b.w,c.x+c.w),bottom=Math.min(b.y+b.h,c.y+c.h);return right>x&&bottom>y?{x,y,w:right-x,h:bottom-y}:null;};
     b=intersect(b,{x:0,y:0,w:720,h:1280});if(!b)continue;
     for(let parent=n.parentElement;parent&&parent!==svg&&b;parent=parent.parentElement){
      const key=/^url\(#([^)]*)\)$/.exec(parent.getAttribute('clip-path')||'');if(!key)continue;
      const clip=C.root.querySelector('#'+CSS.escape(key[1])),matrix=parent.getScreenCTM();if(!clip||!matrix)throw Error('Máscara nativa no medible: '+scene.id);
      const shapes=[...clip.children].filter(n=>typeof n.getBBox==='function').map(n=>n.getBBox());if(!shapes.length)throw Error('Máscara sin geometría verificable: '+scene.id);
      const q={x:Math.min(...shapes.map(b=>b.x)),y:Math.min(...shapes.map(b=>b.y))};q.width=Math.max(...shapes.map(b=>b.x+b.width))-q.x;q.height=Math.max(...shapes.map(b=>b.y+b.height))-q.y;
      const points=[[q.x,q.y],[q.x+q.width,q.y],[q.x,q.y+q.height],[q.x+q.width,q.y+q.height]].map(([x,y])=>new DOMPoint(x,y).matrixTransform(matrix)),xs=points.map(p=>(p.x-host.x)*720/host.width),ys=points.map(p=>(p.y-host.y)*1280/host.height);
      b=intersect(b,{x:Math.min(...xs),y:Math.min(...ys),w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys)});
     }if(!b)continue;
     if(b.w>=719||b.h>=1279)continue;
     if(!bounds)bounds=b;else{const x=Math.min(bounds.x,b.x),y=Math.min(bounds.y,b.y);bounds={x,y,w:Math.max(bounds.x+bounds.w,b.x+b.w)-x,h:Math.max(bounds.y+bounds.h,b.y+b.h)-y};}
     if(n.tagName==='text'&&font>=28)largestText=Math.max(largestText,font);
     if(n.tagName==='image')majorImage=Math.max(majorImage,Math.min(b.w,b.h));
    }samples++;
   }
   if(!bounds)throw Error('Split sin objetos nativos visibles en su intervalo: '+scene.id);
   const ratio=window.split_top??options.split_top,hook=first<options.hook_end_frame;
   const reserved=hook?options.hook_bottom_reserved_native||0:0,top=reserved?44:hook?160:44;
   const region={x:42,y:top,w:636,h:1280*ratio-top-36-reserved};
   const scale=Math.min(1.35,region.w/(bounds.w+24),region.h/(bounds.h+24));
   if(!Number.isFinite(scale)||scale<.48)throw Error('Split miniaturiza la familia '+scene.family+': revisar aparición/encuadre; escala='+scale.toFixed(3));
   if(largestText&&largestText*scale*1.5<options.body_min_px)throw Error('Texto principal demasiado pequeño en split: '+scene.id);
   if(!largestText&&majorImage&&majorImage*scale*1.5<options.identity_min_px)throw Error('Objeto principal demasiado pequeño en split: '+scene.id);
   poses.push({index,start_frame:first,end_frame:last,split_top:ratio,bounds,region,scale,
    x:region.x+region.w/2-scale*(bounds.x+bounds.w/2),y:region.y+region.h/2-scale*(bounds.y+bounds.h/2),samples,
    measured_primary_text_px:largestText?largestText*scale*1.5:null,measured_major_image_px:majorImage?majorImage*scale*1.5:null});
  }
 }finally{native.seek(0,false);native.seek(originalTime,false);C.repaints.forEach(fn=>fn());options.paint_instance?.(originalTime,options.toOutput?options.toOutput(originalTime):originalTime);}
 const content=document.createElementNS(ns,'g');content.id=C.id('integration-native-frame');
 for(const child of [...svg.children])if(child.tagName!=='defs'&&!isBackground(child)&&!child.dataset.integrationFixedOverlay)content.append(child);
 svg.append(content);
 for(const overlay of [...svg.children].filter(child=>child.dataset.integrationFixedOverlay))svg.append(overlay);
 return {receipt:{method:'per_scene_native_surface_wrapper',poses,ambient_background_excluded_from_focus_bounds:scene.family==='spotlight_agent'?[C.id('light')]:[],native_source_changed:false,native_actions_preserved:true,
   measurements:'all frames of actual split intersections; setup only',legibility:'main text/object thresholds; secondary detail still needs mobile visual review'},
  paint(nativeTime,outputLocalTime,splitFraction=0,splitRatio=options.split_top){
   const frame=Math.round((scene.start+outputLocalTime)*fps),pose=poses.find(p=>frame>=p.start_frame&&frame<p.end_frame),f=Math.max(0,Math.min(1,splitFraction));
   if(!Number.isFinite(nativeTime)||!Number.isFinite(outputLocalTime)||!Number.isFinite(f))throw Error('Reloj de encuadre no finito');
   const previous=pose&&poses.find(p=>p.index===pose.index-1&&p.end_frame===pose.start_frame),ratioBlend=previous&&previous.split_top!==pose.split_top?Math.max(0,Math.min(1,(splitRatio-previous.split_top)/(pose.split_top-previous.split_top))):1;
   const blend=key=>previous?previous[key]+(pose[key]-previous[key])*ratioBlend:pose[key];
   const scale=pose?1+(blend('scale')-1)*f:1,x=pose?blend('x')*f:0,y=pose?blend('y')*f:0;
   content.setAttribute('transform',`translate(${view[0]*(1-scale)+x*view[2]/720} ${view[1]*(1-scale)+y*view[3]/1280}) scale(${scale})`);
  }};
};
