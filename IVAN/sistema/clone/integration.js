/* Adaptador YO: un reloj de HyperFrames, instancias CLONE intactas.
   Las decisiones de narración/cámara vienen de dos inferencias registradas.
   Geometría y muestreo se calculan una sola vez, nunca en un tween de layout. */
window.CloneIntegrationSetup = async () => {
 if(window.__integrationBuilt||window.__integrationBuilding)return;
 window.__integrationBuilding=true;
 const cfg=window.CLONE_INTEGRATION,dir=cfg.direction,words=cfg.narration.words;
 const ns='http://www.w3.org/2000/svg',fps=30,d=cfg.duration,production=dir.profile==='production_complete';
 const splitTop=cfg.split.upper,dividerY=1920*splitTop,splitY=dividerY-cfg.camera_crop[1],hookV3=cfg.revision==='V3_hook';
 const main=gsap.timeline({paused:true}),type=document.getElementById('integration-type');
 const mask=document.getElementById('integration-camera-mask'),plane=document.getElementById('integration-camera-plane');
 const viewport=document.getElementById('integration-motion-viewport'),world=document.getElementById('integration-motion-world'),film=document.getElementById('__clone-film');
 const norm=s=>s.normalize('NFD').replace(/\p{Diacritic}/gu,'').replace(/[^\p{L}\p{N} ]/gu,'').toLowerCase().trim();
 const nativeText=el=>{const lines=[...el.children].filter(n=>n.tagName==='tspan');return lines.length?lines.map(n=>n.textContent).join(' '):el.textContent;};
 const receipts=[],textNodes=[],duplicates=[],hookAssets=[];
 const camera=dir.camera_windows.map((p,index)=>({...p,index,start:p.start_frame/fps,end:p.end_frame/fps,pose:production?cfg.camera_poses[index]:null,split_top:p.split_top??splitTop}));
 if(production&&camera.some(w=>!w.pose||w.pose.start_frame!==w.start_frame||w.pose.end_frame!==w.end_frame))throw Error('Poses de cámara no corresponden a dirección actual');
 const atCamera=t=>camera.find(p=>t>=p.start&&t<p.end);
 const splitAt=t=>{
  const index=camera.findIndex(w=>t>=w.start&&t<w.end),w=camera[index];
  if(!w)return 0;
  const ease=gsap.parseEase('power3.inOut'),incoming=w.transition_frames/fps;
  const previous=camera[index-1],next=camera[index+1],exit=next?.start_frame===w.end_frame?0:production?w.exit_frames/fps:Math.min((w.exit_frames||6)/fps,(w.end-w.start)/3);
  if(w.state!=='split')return production&&previous?.state==='split'&&previous.end_frame===w.start_frame&&incoming&&t<w.start+incoming?1-ease((t-w.start)/incoming):0;
  if(production&&previous?.state==='split'&&previous.end_frame===w.start_frame){if(exit&&t>w.end-exit)return 1-ease((t-w.end+exit)/exit);return 1;}
  if(incoming&&t<w.start+incoming)return ease((t-w.start)/incoming);
  if(exit&&t>w.end-exit)return 1-ease((t-w.end+exit)/exit);
  return 1;
 };
 const splitRatioAt=t=>{const w=atCamera(t);if(!w)return splitTop;const previous=camera[w.index-1],incoming=w.transition_frames/fps;
  if(w.state==='full')return previous?.state==='split'?previous.split_top:splitTop;
  if(previous?.state==='split'&&previous.end_frame===w.start_frame&&incoming&&t<w.start+incoming)return previous.split_top+(w.split_top-previous.split_top)*gsap.parseEase('power3.inOut')((t-w.start)/incoming);
  return w.split_top;};
 const interpolate=(pairs,t,key)=>{
  let i=0;while(i<pairs.length-2&&pairs[i+1].t<t)i++;
  const a=pairs[i],b=pairs[Math.min(i+1,pairs.length-1)],f=b.t===a.t?0:Math.max(0,Math.min(1,(t-a.t)/(b.t-a.t)));
  return a[key]+(b[key]-a[key])*f;
 };
 const sourceHeight=production?cfg.source_geometry.height:1920;
 const anchors=cfg.face.anchors.map(a=>({t:a.t,segment:a.segment_id??0,chin:a.source_normalized.smooth_chin[1]*sourceHeight}));
 if(!anchors.length)throw Error('No hay barbillas comprobadas');
 const chin=Array.from({length:cfg.frames},(_,f)=>{const t=f/fps;if(!production)return interpolate(anchors,t,'chin');
  let i=0;while(i<anchors.length-2&&anchors[i+1].t<t)i++;const a=anchors[i],b=anchors[Math.min(i+1,anchors.length-1)];
  return a.segment!==b.segment?(t>=b.t?b.chin:a.chin):interpolate([a,b],t,'chin');});
 const colors=Array(cfg.frames).fill('rgb(244, 244, 243)'),nativeRecords=[],backgroundFills=new Map();
 const hookFootprint=scene=>{
  const groups=new Map(),canvas=document.createElement('canvas').getContext('2d');
  for(const block of dir.hook_blocks||[]){const key=block.sequence||block.id,old=groups.get(key);if(old){old.word_end=Math.max(old.word_end,block.word_end);old.emphasis_word_indices=[...new Set([...(old.emphasis_word_indices||[]),...(block.emphasis_word_indices||[])])];}else groups.set(key,{...block});}
  let height=0;const samples=[];
  for(const block of groups.values()){
   const probe=document.createElement('div');probe.className='integration-text';probe.style.visibility='hidden';probe.style.opacity='0';
   const font=block.font||'Sequel',range=words.slice(block.word_start,block.word_end+1);canvas.font=`${font==='Sequel'?700:400} 114px ${font}`;
   const fit=Math.min(114,920/Math.max(1,...range.map(w=>canvas.measureText(w.text).width))*114);
   probe.style.fontFamily=font;probe.style.fontWeight=font==='Sequel'?'700':'400';probe.style.fontSize=fit+'px';
   range.forEach((word,i)=>{const span=document.createElement('span');span.className='integration-glyph';span.textContent=word.text+(i<range.length-1?' ':'');
    if((block.emphasis_word_indices||[]).includes(block.word_start+i)){span.style.display='block';canvas.font=`${font==='Sequel'?700:400} 142px ${font}`;span.style.fontSize=Math.min(142,920/Math.max(1,canvas.measureText(word.text).width)*142)+'px';}probe.append(span);});
   type.append(probe);const spans=[...probe.children],styles=spans.map(n=>n.style.display||'inline-block'),prefixHeights=[];
   for(let count=1;count<=spans.length;count++){spans.forEach((n,i)=>n.style.display=i<count?styles[i]:'none');prefixHeights.push(probe.offsetHeight);}
   for(const window of camera.filter(w=>w.state==='split')){
    const first=Math.max(window.start_frame,block.start_frame,Math.round(scene.start*fps)),last=Math.min(window.end_frame,block.end_frame,Math.round((scene.start+scene.duration)*fps));
    for(let frame=first;frame<last;frame++){
     const count=range.filter((word,i)=>(block.word_start+i===0?0:Math.round(word.start*fps))<=frame).length;
     if(count){const visibleHeight=prefixHeights[count-1];height=Math.max(height,visibleHeight);samples.push({frame,block_id:block.id,visible_words:count,height_px:visibleHeight});}
    }
   }
   probe.remove();
  }
  if(height<=0)throw Error('Hook sin tipografía real medible durante el split');
  receipts.push({scene_id:scene.id,override:'temporal_spoken_hook_footprint',max_visible_height_px:height,samples,
   measurement:'loaded fonts; spoken prefixes only inside actual split intersection; no future words or later full-frame phrases'});return height;
 };
 // La representación textual externa reemplaza los títulos de narración, no
 // los elementos que explican la acción dentro de una interfaz o diagrama.
 for(const scene of cfg.scenes){
  const built=window.__cloneBuilt[scene.id];if(!built)throw Error('Instancia no montada: '+scene.id);
  const C=built.context,svg=C.root.querySelector('svg'),native=CloneTimelineReal(window.__timelines[scene.id]);
  // Avisos de verificación pertenecen al informe, no al montaje narrado.
  const internal=/^(?:EJEMPLO CONCEPTUAL|Esquema conceptual|Condición del guion|.*según el guion|No mide calidad ni declara ganador)$/i;
  const defaultChrome=/^(?:SOLICITUD|ESTADO|RESULTADO|PROCESO)$/i;
  for(const note of svg.querySelectorAll('text'))if(internal.test(nativeText(note).trim())||(defaultChrome.test(nativeText(note).trim())&&!words.some(w=>norm(w.text)===norm(nativeText(note))))) {
   const wrapper=document.createElementNS(ns,'g');wrapper.setAttribute('opacity','0');
   wrapper.id=C.id('integration-internal-'+receipts.length);
   note.parentNode.insertBefore(wrapper,note);wrapper.appendChild(note);
   receipts.push({scene_id:scene.id,override:'internal_note_report_only',text:nativeText(note),reason:'verification_is_not_spoken_editorial_content',family_source_changed:false});
  }
  for(const name of ['heading','caption']){const el=C.q(name);if(el){const wrapper=document.createElementNS(ns,'g');wrapper.id='integration-editorial-'+scene.id+'-'+name;wrapper.setAttribute('opacity','0');el.parentNode.insertBefore(wrapper,el);wrapper.appendChild(el);receipts.push({scene_id:scene.id,override:name,reason:'narration_type_layer_owns_editorial_text',family_source_changed:false});}}
  if(production){
   const captionNames=scene.family==='feedback_bars'?['caption0',...scene.params.categories.map((_,i)=>'caption'+(i+1))]:scene.family==='cancelled'?['editorial-caption','caption-without','caption-for']:[];
   for(const name of captionNames){const el=C.q(name);if(!el)continue;const wrapper=document.createElementNS(ns,'g');wrapper.id=C.id('integration-caption-'+name);wrapper.setAttribute('opacity','0');el.parentNode.insertBefore(wrapper,el);wrapper.appendChild(el);receipts.push({scene_id:scene.id,override:name,reason:'external source-word captions replace existing editorial captions',family_source_changed:false});}
   for(const text of svg.querySelectorAll('text'))if(scene.params.caption&&norm(nativeText(text))===norm(scene.params.caption)&&!text.closest('[id*="integration-editorial"]')&&!text.closest('[id*="integration-caption"]')){const wrapper=document.createElementNS(ns,'g');wrapper.setAttribute('opacity','0');text.parentNode.insertBefore(wrapper,text);wrapper.appendChild(text);receipts.push({scene_id:scene.id,override:'native_caption_text',original_text:nativeText(text),reason:'unwrapped native editorial caption replaced by original source words',family_source_changed:false});}
  }
  // No tocar parámetros ni añadir otro skin: sólo envolturas independientes
  // para impedir el texto duplicado durante un titular narrativo equivalente.
  for(const text of svg.querySelectorAll('text')){
   if(text.closest('defs')||text.closest('#'+CSS.escape(C.id('heading')))||text.closest('#'+CSS.escape(C.id('caption'))))continue;
   const value=norm(nativeText(text));
   const editorial=scene.family==='composition_graph'&&(scene.params.nodes||[]).some(n=>n.kind==='editorial'&&text.id===C.id(n.id+'-label'));
   if(editorial&&value&&words.some(w=>norm(w.text)===value)){
    const wrapper=document.createElementNS(ns,'g');wrapper.id='integration-dupe-'+duplicates.length;
    text.parentNode.insertBefore(wrapper,text);wrapper.appendChild(text);duplicates.push({wrapper,value});
   }
  }
  const hookLayout=CloneIntegrationHook(C,scene,native,cfg);
  if(hookLayout.receipt.length)receipts.push({scene_id:scene.id,override:'hook_visual_hierarchy',changes:hookLayout.receipt,family_source_changed:false});
  const readableLabels=CloneIntegrationReadableLabels(C,scene,cfg);
  if(readableLabels.receipt.length)receipts.push({scene_id:scene.id,override:'native_role_label_readability',changes:readableLabels.receipt,family_source_changed:false});
  const brandLayout=CloneIntegrationBrands(C,scene,native,cfg);
  if(brandLayout.receipt.length)receipts.push({scene_id:scene.id,override:'official_brand_prominence',changes:brandLayout.receipt,family_source_changed:false});
  // Cues anclados pueden retimar el reloj de la instancia sin editar su módulo.
  const cues=(dir.phase_cues||[]).filter(c=>c.scene_id===scene.id);
  let knots=[{t:0,v:0,kind:'endpoint'}];
  for(const cue of cues){
   let nativeAt,labelSource;
   if(cue.cue_id.startsWith('step:')){nativeAt=scene.params.steps[Number(cue.cue_id.slice(5))]?.at;labelSource='executable_graph_step';}
   else {const ident=cue.cue_id.slice(6),action=scene.actions.find(a=>a.phase_id===ident);nativeAt=Number.isFinite(cue.native_at)?cue.native_at:(native.labels[ident]??action?.at);labelSource=Number.isFinite(cue.native_at)?cue.timing_basis:(native.labels[ident]!==undefined?'native_label':'derived_phase_window');}
   const target=Math.round((words[cue.anchor_index].start-scene.start)*fps)/fps;
   if(!Number.isFinite(nativeAt)||target<0||target>scene.duration)throw Error('Cue no ejecutable');
   knots.push({t:target,v:nativeAt,kind:labelSource,cue_id:cue.cue_id,word:cue.anchor_index});
  }
  if(scene.rhythm?.mode==='phase_clock'){
   for(const point of scene.rhythm.points){
    const step=point.cue_id.startsWith('step:')?scene.params.steps[Number(point.cue_id.slice(5))]:null;
    const action=step||scene.actions.find(a=>a.phase_id===point.cue_id.slice(6));
    if(!action)throw Error('Ritmo sin acción nativa: '+point.cue_id);
    const expected=Math.round((action.at+action.duration*point.native_progress)*fps)/fps;
    const value=Number.isFinite(point.native_at)?point.native_at:expected;
    if(Math.abs(expected-value)>1e-5)throw Error('Ritmo altera la fase nativa');
    knots.push({t:point.at,v:value,kind:'phase_clock',cue_id:point.cue_id,progress:point.native_progress,reason:point.reason});
    if(point.hold_s>0)knots.push({t:Math.round((point.at+point.hold_s)*fps)/fps,v:value,kind:'readable_hold',cue_id:point.cue_id,reason:point.reason});
   }
  }
  knots.push({t:scene.duration,v:scene.duration,kind:'endpoint'});
  knots.sort((a,b)=>a.t-b.t||a.v-b.v);
  const unique=knots.filter((p,i)=>!i||Math.abs(p.t-knots[i-1].t)>1e-7||Math.abs(p.v-knots[i-1].v)>1e-7);
  const monotonic=unique.every((p,i)=>!i||(p.t>unique[i-1].t&&p.v>=unique[i-1].v));
  const rates=unique.slice(1).map((p,i)=>(p.v-unique[i].v)/(p.t-unique[i].t));
  const phaseClock=scene.rhythm?.mode==='phase_clock';
  const canWarp=monotonic&&rates.every(r=>(phaseClock||production)?r>=0&&r<=6:r>=.25&&r<=4);
  if((phaseClock||production)&&!canWarp)throw Error('Reloj solicitado no ejecutable; no afirmar sincronización ni conservarlo silenciosamente');
  const needsWarp=unique.some(p=>Math.abs(p.t-p.v)>1/fps);
  const actualMap=canWarp?unique:[{t:0,v:0},{t:scene.duration,v:scene.duration}];
  const toNative=t=>interpolate(actualMap.map(p=>({t:p.t,v:p.v})),t,'v');
  const toOutput=v=>interpolate(actualMap.map(p=>({t:p.v,v:p.t})),v,'v');
  const identityRequested=(cfg.instance_overrides||[]).some(v=>v.scene_id===scene.id&&v.kind==='spotlight_hook_identity');
  const hookIdentity=CloneIntegrationSpotlightHook(C,scene,native,cfg,{toNative,toOutput,hook_height_px:identityRequested?hookFootprint(scene):0});
  hookIdentity.paint?.(0);
  if(hookIdentity.receipt.length)receipts.push({scene_id:scene.id,override:'spotlight_official_hook_instance',changes:hookIdentity.receipt,family_source_changed:false});
  if(scene.family==='radial_research'&&!production){
   // Entradas rápidas sin comprimir los flujos de investigación ni los holds.
   // La instancia conserva sus tweens, objetivos y posiciones originales.
   const entryTargets=[C.q('agent'),C.q('target'),...scene.params.sources.map((_,i)=>C.q('source'+i))];
   for(const tween of native.getChildren(true,true,false)){
    if(tween.vars.opacity!==1||!tween.targets().some(t=>entryTargets.includes(t)))continue;
    const nativeStart=tween.startTime(),oldDuration=tween.duration(),outStart=toOutput(nativeStart),oldOutput=toOutput(nativeStart+oldDuration)-outStart;
    const newDuration=toNative(Math.min(scene.duration,outStart+.26))-nativeStart;
    if(oldOutput>.30&&newDuration>0&&newDuration<oldDuration){tween.duration(newDuration);receipts.push({scene_id:scene.id,override:'entry_duration_only',element:tween.targets()[0].id,original_native_duration:oldDuration,new_native_duration:newDuration,output_duration:.26,movement_flows_unchanged:true,family_source_changed:false});}
   }
  }
  // La acción transforma el objeto; el fondo oscuro incidental de salida
  // no aporta una idea ni enlaza con el siguiente papel claro.
  if(scene.family==='composition_graph'&&scene.transition_out?.kind==='cut'){
   const background=C.q('background');
   const fills=native.getChildren(true,true,false).filter(t=>t.targets().includes(background)&&t.vars.attr?.fill==='#000000');
   fills.forEach(t=>t.kill());
   if(fills.length){background.setAttribute('fill',C.colors.paper);receipts.push({scene_id:scene.id,override:'continuous_paper_surface',reason:'avoid_unmotivated_dark_flash_before_next_paper_scene',removed_instance_background_tweens:fills.length,family_source_changed:false});}
  }
  const layout=scene.family==='composition_graph'?CloneIntegrationLayout(C,native,scene,(hookV3||production)?{focus_windows:dir.focus_windows,split_top:splitTop,production,camera,toNative,hook_end_frame:dir.hook_end_frame,...cfg.layout_contract}:undefined):
    production?CloneIntegrationFamilyLayout(C,native,scene,{camera,toNative,toOutput,split_top:splitTop,hook_end_frame:dir.hook_end_frame,...cfg.layout_contract,...hookIdentity.layout_options,
      paint_instance:(nativeTime,outputTime)=>{brandLayout.paint?.(nativeTime);hookIdentity.paint?.(outputTime);}}):null;
  if(layout)receipts.push({scene_id:scene.id,override:'instance_semantic_reflow',...layout.receipt});
  let clock=native;
  if((canWarp&&needsWarp)||layout||brandLayout.paint||hookIdentity.paint){
   // Partir del estado0 evita heredar reacciones de un seek anterior. El
   // adaptador recompone el mismo reloj nativo, sin editar sus keyframes.
   const state={time:0},retimed=gsap.timeline({paused:true}),paint=()=>{native.seek(0,false);native.seek(state.time,false);brandLayout.paint?.(state.time);hookIdentity.paint?.(retimed.time());layout?.paint(Math.min(scene.duration,state.time),retimed.time(),splitAt(scene.start+retimed.time()),splitRatioAt(scene.start+retimed.time()));hookLayout.paint?.(retimed.time());};
   const appliedMap=actualMap;
   const nativeEnd=native.duration();
   if(nativeEnd>scene.duration+1e-7)appliedMap.push({t:nativeEnd,v:nativeEnd,kind:'native_transition_tail'});
   for(let i=1;i<appliedMap.length;i++)retimed.fromTo(state,{time:appliedMap[i-1].v},{time:appliedMap[i].v,duration:appliedMap[i].t-appliedMap[i-1].t,ease:'none',immediateRender:false,onUpdate:paint},appliedMap[i-1].t);
   retimed.eventCallback('onUpdate',paint);clock=retimed;window.__timelines[scene.id]=retimed;
  }
  const sampleScene=outputTime=>{
   const time=toNative(outputTime);native.seek(0,false);native.seek(time,false);
   brandLayout.paint?.(time);hookIdentity.paint?.(outputTime);layout?.paint(Math.min(scene.duration,time),outputTime,splitAt(scene.start+outputTime),splitRatioAt(scene.start+outputTime));hookLayout.paint?.(outputTime);
  };
  const mounted=window.__cloneInstances.find(record=>record.id===scene.id),visibleDuration=mounted?.visible_duration??scene.duration;
  if(!Number.isFinite(visibleDuration)||visibleDuration<scene.duration)throw Error('Duración visible de la instancia no verificable');
  const record={scene_id:scene.id,family:scene.family,clock,context:C,svg,layout,sample:sampleScene,start:scene.start,duration:scene.duration,visibleDuration};nativeRecords.push(record);
  receipts.push({scene_id:scene.id,phase_cues:cues,map:actualMap,requested_map:unique,word_cues_applied:canWarp,rhythm_mode:phaseClock?'phase_clock':'word_cues',retimed:clock!==native,rate_guard:canWarp,execution:clock!==native?'monotonic_timewarp':'original_timeline',limit:!canWarp&&needsWarp?'Se conserva el reloj original: el mapa solicitado produciría velocidades o fases inválidas.':null});
  const bg=C.q('background')||[...svg.querySelectorAll('rect')].find(el=>!el.closest('defs')&&Number(el.getAttribute('x')||0)===0&&Number(el.getAttribute('y')||0)===0&&Number(el.getAttribute('width'))===720&&Number(el.getAttribute('height'))===1280);
  record.background=bg;
  for(let f=Math.round(scene.start*fps);f<Math.min(cfg.frames,Math.round((scene.start+scene.duration)*fps));f++){
   sampleScene(f/fps-scene.start);
   if(bg){const cssFill=getComputedStyle(bg).fill;if(!/^rgba?\(/.test(cssFill))throw Error('Fondo sólido sin color CSS normalizado: '+scene.id+' '+cssFill);
    colors[f]=cssFill;const key=scene.id+'|'+bg.getAttribute('fill')+'|'+cssFill;const item=backgroundFills.get(key);
    if(item)item.end_frame=f+1;else backgroundFills.set(key,{scene_id:scene.id,original_fill:bg.getAttribute('fill'),executed_css_fill:cssFill,start_frame:f,end_frame:f+1});}
  }
  sampleScene(0);
 }
 // Medir los focos realmente visibles durante cada split. Se consideran los
 // estados transformados, no la caja total del SVG ni el fondo de pantalla.
 function focusPose(window){
  let bounds=null;
  for(let f=window.start_frame;f<window.end_frame;f+=Math.max(1,Math.floor((window.end_frame-window.start_frame)/5))){
   const t=f/fps,record=nativeRecords.find(r=>{const s=cfg.scenes.find(s=>s.id===r.scene_id);return t>=s.start&&t<s.start+s.duration;});
   if(!record)continue;const scene=cfg.scenes.find(s=>s.id===record.scene_id);record.sample?record.sample(t-scene.start):record.clock.seek(t-scene.start,false);
   const hostBox=record.svg.getBoundingClientRect();
   for(const node of record.svg.querySelectorAll('image,rect,text,path,circle,ellipse,line')){
    if(node.closest('defs')||node.id.endsWith('-background')||node.closest('#'+CSS.escape(record.context.id('heading')))||node.closest('#'+CSS.escape(record.context.id('caption')))||node.id.endsWith('-conceptual-note'))continue;
    let hidden=false;
    for(let p=node;p&&p!==record.svg;p=p.parentElement){if(Number(getComputedStyle(p).opacity)<.1||getComputedStyle(p).display==='none'){hidden=true;break;}}
    if(hidden)continue;const b=node.getBoundingClientRect();
    if(b.width<=0||b.height<=0||b.width>hostBox.width*.98||b.height>hostBox.height*.98)continue;
    const q={x:(b.left-hostBox.left)*1080/hostBox.width,y:(b.top-hostBox.top)*1920/hostBox.height,w:b.width*1080/hostBox.width,h:b.height*1920/hostBox.height};
    if(!bounds)bounds=q;else{const x=Math.min(bounds.x,q.x),y=Math.min(bounds.y,q.y);bounds={x,y,w:Math.max(bounds.x+bounds.w,q.x+q.w)-x,h:Math.max(bounds.y+bounds.h,q.y+q.h)-y};}
   }
  }
  nativeRecords.forEach(r=>r.sample?r.sample(0):r.clock.seek(0,false));
  if(!bounds)bounds={x:120,y:250,w:840,h:840};
  const scale=Math.min(1.25,960/Math.max(1,bounds.w),800/Math.max(1,bounds.h));
  return {scale,x:540-scale*(bounds.x+bounds.w/2),y:570-scale*(bounds.y+bounds.h/2),bounds};
 }
 const splitPoses=camera.filter(w=>w.state==='split').map(w=>({window:w,pose:production||cfg.scenes.every(s=>s.family==='composition_graph')?{scale:1,x:0,y:0,geometry:production?'individual_native_scene_wrappers':'semantic_instance_reflow'}:focusPose(w)}));
 // El estabilizador de HyperFrames revierte SETs exactos de tiempo0. La pose
 // anterior a esos SETs también debe ser el full inicial solicitado.
 const initialSplit=camera[0]?.state==='split'&&camera[0].start_frame===0;
 const firstPose=production?camera[0].pose:{x:0,y:initialSplit?splitY:0,scale:1,split_top:splitTop};
 const cameraState={maskFraction:initialSplit?firstPose.split_top:0,x:firstPose.x,y:firstPose.y,scale:firstPose.scale,alpha:1},motionState={scale:1,x:0,y:0,coverageFraction:initialSplit?firstPose.split_top:1};
 main.set(cameraState,{maskFraction:initialSplit?firstPose.split_top:0,x:firstPose.x,y:firstPose.y,scale:firstPose.scale,alpha:1},0);
 main.set(motionState,{scale:1,x:0,y:0,coverageFraction:initialSplit?firstPose.split_top:1},0);
 for(const [index,window]of camera.entries()){
  const previous=camera[index-1],contiguous=previous&&previous.end_frame===window.start_frame;
  const duration=window.transition_frames/fps,split=window.state==='split';
  const pose=split?splitPoses.find(p=>p.window===window).pose:{scale:1,x:0,y:0};
  const photo=production?window.pose:{x:0,y:split?splitY:0,scale:1,split_top:splitTop};
  const initial=contiguous?undefined:{maskFraction:duration?1:(split?photo.split_top:0),x:photo.x,y:split?(duration?photo.y+(production?96:313):photo.y):0,scale:photo.scale,alpha:1};
  if(initial)main.set(cameraState,initial,window.start);
  main.to(cameraState,{maskFraction:split?photo.split_top:0,x:photo.x,y:photo.y,scale:photo.scale,alpha:1,duration,ease:'power3.inOut'},window.start);
  if(production&&!duration)main.set(motionState,{scale:pose.scale,x:pose.x,y:pose.y,coverageFraction:split?photo.split_top:1},window.start);
  else main.to(motionState,{scale:pose.scale,x:pose.x,y:pose.y,coverageFraction:split?photo.split_top:1,duration:duration||.2,ease:'power3.inOut'},window.start);
  main.addLabel('camera_'+window.state+'_'+index,window.start);
  if(!camera[index+1]||camera[index+1].start_frame!==window.end_frame){
   const exit=production?window.exit_frames/fps:Math.min((window.exit_frames||6)/fps,(window.end-window.start)/3);
   main.to(cameraState,{maskFraction:1,y:production?photo.y:splitY,alpha:1,duration:exit,ease:'power3.inOut'},window.end-exit);
   main.to(motionState,{scale:1,x:0,y:0,coverageFraction:1,duration:exit,ease:'power3.inOut'},window.end-exit);
   main.set(cameraState,{alpha:0},window.end);main.addLabel('camera_exit_'+index,window.end);
  }
 }
 const sequenceGroups=new Map();
 for(const block of dir.hook_blocks||[]){
  const key=block.sequence||block.id,old=sequenceGroups.get(key);
  if(!old)sequenceGroups.set(key,{...block,placement:'hook',members:[block.id],word_fonts:Object.fromEntries(Array.from({length:block.word_end-block.word_start+1},(_,i)=>[block.word_start+i,block.font||'Sequel']))});
  else{for(let i=old.word_end+1;i<=block.word_end;i++)old.word_fonts[i]=block.font||'Sequel';if(block.brand_asset&&!old.brand_asset){old.brand_asset=block.brand_asset;old.brand_entity_id=block.brand_entity_id;old.brand_reason=block.brand_reason;}old.word_end=Math.max(old.word_end,block.word_end);old.end_frame=Math.max(old.end_frame,block.end_frame);old.members.push(block.id);if(block.color==='red'){old.color='red';old.red_reason=block.red_reason;old.emphasis_word_indices=[...new Set([...old.emphasis_word_indices,...block.emphasis_word_indices])];}}
 }
 const all=[...sequenceGroups.values(),...(dir.caption_blocks||[])];
 const canvas=document.createElement('canvas').getContext('2d');
 function opaqueBackground(record,frame){
  const bg=record.background;if(!bg)return null;const fill=getComputedStyle(bg).fill,rgba=fill.match(/[\d.]+/g)?.map(Number);
  if(!rgba||rgba.length>3&&rgba[3]<.999)return null;
  const shapes=[],host=document.getElementById('__clone-host-'+record.scene_id);
  const box=el=>{const b=el.getBoundingClientRect();return{x:b.x,y:b.y,w:b.width,h:b.height};};
  for(let p=bg;p&&p!==host;p=p.parentElement){
   const css=getComputedStyle(p);if(Number(css.opacity)<.999||css.display==='none'||p.style.visibility==='hidden'||p.getAttribute('visibility')==='hidden')return null;
   if(css.overflow==='hidden'||css.overflow==='clip')shapes.push({kind:'rect',...box(p)});
   if(css.clipPath&&css.clipPath!=='none'){
    const b=box(p),circle=/^circle\(([\d.]+)(%|px) at ([\d.]+)(%|px) ([\d.]+)(%|px)\)$/.exec(css.clipPath);
    if(circle)shapes.push({kind:'circle',x:b.x+Number(circle[3])*(circle[4]==='%'?b.w/100:1),y:b.y+Number(circle[5])*(circle[6]==='%'?b.h/100:1),r:Number(circle[1])*(circle[2]==='%'?Math.hypot(b.w,b.h)/Math.SQRT2/100:1)});
    else if(css.clipPath.startsWith('inset(')){
     const parts=css.clipPath.slice(6,-1).split(/\s+/);if(parts.some(v=>!/^[-\d.]+(?:%|px)$/.test(v)))return null;
     const p4=parts.length===1?[parts[0],parts[0],parts[0],parts[0]]:parts.length===2?[parts[0],parts[1],parts[0],parts[1]]:parts.length===3?[parts[0],parts[1],parts[2],parts[1]]:parts;
     if(p4.length!==4)return null;const values=p4.map((v,i)=>parseFloat(v)*(v.endsWith('%')?(i%2?b.w:b.h)/100:1));
     shapes.push({kind:'rect',x:b.x+values[3],y:b.y+values[0],w:b.w-values[1]-values[3],h:b.h-values[0]-values[2]});
    }else return null; // Una máscara desconocida nunca acredita oclusión.
   }
  }
  shapes.push({kind:'rect',...box(bg)});
  // Obstáculos y clips comparten coordenadas del lienzo, incluso en Studio
  // cuando el viewport escala la composición durante una medición.
  const sx=1080/frame.width,sy=1920/frame.height;
  return shapes.map(shape=>shape.kind==='circle'?{...shape,x:(shape.x-frame.left)*sx,y:(shape.y-frame.top)*sy,r:shape.r*sx}:
   {...shape,x:(shape.x-frame.left)*sx,y:(shape.y-frame.top)*sy,w:shape.w*sx,h:shape.h*sy});
 }
 const covered=(box,shapes)=>[[box.x,box.y],[box.x+box.w,box.y],[box.x,box.y+box.h],[box.x+box.w,box.y+box.h]].every(([x,y])=>shapes.every(s=>s.kind==='circle'?Math.hypot(x-s.x,y-s.y)<=s.r:x>=s.x&&x<=s.x+s.w&&y>=s.y&&y<=s.y+s.h));
 function compositionTextY(start,end,height){
  const occupied=[],contributors=new Set(),tails=new Set();
  for(let f=Math.max(0,Math.floor(start*fps));f<Math.min(cfg.frames,Math.ceil(end*fps));f++){
   const t=f/fps;
   const active=nativeRecords.filter(r=>t>=r.start&&t<r.start+r.visibleDuration);
   active.forEach(r=>r.sample(t-r.start));const frame=film.getBoundingClientRect(),occluders=active.map(r=>opaqueBackground(r,frame));
   for(const [index,record]of active.entries()){
    contributors.add(record.scene_id);if(t>=record.start+record.duration)tails.add(record.scene_id);
    for(const node of record.svg.querySelectorAll('text,image,rect')){
    if(node.closest('defs')||node.id.endsWith('-background')||node.id.endsWith('-conceptual-note'))continue;
    let hidden=false;for(let p=node;p&&p!==record.svg;p=p.parentElement){if(Number(getComputedStyle(p).opacity)<.15||getComputedStyle(p).display==='none'){hidden=true;break;}}
    if(hidden)continue;const b=node.getBoundingClientRect();if(b.width<=0||b.height<=0||b.width>frame.width*.98||b.height>frame.height*.98)continue;
     occupied.push({x:(b.left-frame.left)*1080/frame.width,y:(b.top-frame.top)*1920/frame.height,w:b.width*1080/frame.width,h:b.height*1920/frame.height,
      occluders:occluders.slice(index+1).filter(Boolean),scene_id:record.scene_id,frame:f});
    }
   }
  }
  nativeRecords.forEach(r=>r.sample(0));
  const nearBelow=occupied.length?Math.round(Math.max(...occupied.map(b=>b.y+b.h))+48):1130;
  const preferred=[nearBelow,1130,1280,1490,1040,400,210,1640,800,600];
  const candidates=[...preferred,...Array.from({length:31},(_,i)=>180+i*50)].filter(y=>y+height<=1750);
  const free=y=>!occupied.some(b=>{
   const x=Math.max(60,b.x),top=Math.max(y-20,b.y),right=Math.min(1020,b.x+b.w),bottom=Math.min(y+height+20,b.y+b.h);
   if(right<=x||bottom<=top)return false;
   return !b.occluders.some(shapes=>covered({x,y:top,w:right-x,h:bottom-top},shapes));
  });
  const y=candidates.find(free);
  if(y===undefined)throw Error('No hay zona textual libre: revisar composición, no superponer caption');
  receipts.push({text_anchor:'automatic_free_zone',start,end,y,height,obstacle_samples:occupied.length,active_scene_ids:[...contributors],outgoing_tail_scene_ids:[...tails],
   sampling:'explicit native time-map + instance repaint; actual canvas coordinates',occlusion:'Only opaque higher scene background with supported rect/circle clips can remove an obstacle intersection; unsupported masks stay conservative.'});return y;
 }
 for(const block of all){
  let visibleHeightAt=null;
  const group=document.createElement('div');group.id='integration-text-'+block.id;group.className='integration-text';
  const range=words.slice(block.word_start,block.word_end+1),isHook=block.placement==='hook';
  const text=range.map(w=>w.text).join(' '),font=block.font||'Sequel';
  const size=isHook?114:64;canvas.font=`${font==='Sequel'?700:400} ${size}px ${font}`;
  const major=(block.emphasis_word_indices||[]).length&&isHook;
  const ordinary=range.filter((_,i)=>!major||!block.emphasis_word_indices.includes(block.word_start+i)).map(w=>w.text).join(' ');
  const measured=isHook?Math.max(...range.map(w=>canvas.measureText(w.text).width)):canvas.measureText(text).width;
  const fit=Math.min(size,920/Math.max(1,measured)*size);
  group.style.fontFamily=font;group.style.fontWeight=font==='Sequel'?'700':'400';group.style.fontSize=fit+'px';
  // Hooks construyen una frase; los spans siguen formando una composición.
  range.forEach((word,i)=>{const span=document.createElement('span'),wordFont=block.word_fonts?.[block.word_start+i]||font;span.className='integration-glyph';span.textContent=word.text+(i<range.length-1?' ':'');span.dataset.word=String(block.word_start+i);span.style.fontFamily=wordFont;span.style.fontWeight=wordFont==='Sequel'?'700':'400';if(major&&block.emphasis_word_indices.includes(block.word_start+i)){span.style.display='block';canvas.font=`${wordFont==='Sequel'?700:400} 142px ${wordFont}`;span.style.fontSize=Math.min(142,920/Math.max(1,canvas.measureText(word.text).width)*142)+'px';}group.appendChild(span);});
  const separateIdentity=isHook&&block.brand_asset&&(cfg.instance_overrides||[]).find(v=>v.kind==='spotlight_hook_identity'&&v.asset===block.brand_asset&&cfg.scenes.some(s=>s.id===v.scene_id&&block.start_frame>=s.start*fps&&block.start_frame<(s.start+s.duration)*fps));
  if(separateIdentity)receipts.push({text:block.id,override:'inline_logo_replaced_by_official_protagonist_instance',asset:block.brand_asset,reason:separateIdentity.reason,spoken_text_unchanged:true});
  if(isHook&&block.brand_asset&&!separateIdentity){
   const asset=window.CLONE_ASSETS[block.brand_asset];
   if(!asset||asset.kind!=='brand_logo'||!asset.data)throw Error('Logo de hook no resuelto auténticamente');
   const identity=cfg.narration.text&&asset.aliases.find(a=>range.some(w=>norm(w.text)===norm(a)));
   const span=[...group.children].find(el=>identity&&norm(words[Number(el.dataset.word)].text)===norm(identity));
   if(!span)throw Error('Logo de hook sin palabra/identidad correspondiente');
   const img=document.createElement('img');img.src=asset.data;img.alt=identity;
   img.dataset.brandAsset=block.brand_asset;img.dataset.brandEntity=block.brand_entity_id;
   const wordmark=block.brand_asset.includes('wordmark');
   const imageHeight=hookV3&&wordmark?140:wordmark?fit*.78:fit*.70;
   img.style.cssText=`display:inline-block;height:${imageHeight}px;width:${imageHeight*asset.width/asset.height}px;vertical-align:-.07em;object-fit:contain;filter:none;`;
   if(wordmark){if(hookV3){const surface=document.createElement('span');surface.className='integration-brand-surface';surface.style.cssText='display:inline-block;background:#fff;padding:24px;border-radius:22px;vertical-align:middle;filter:none;box-shadow:none';surface.append(img);img.style.verticalAlign='middle';span.replaceChildren(surface);}else span.replaceChildren(img);span.append(' ');}
   else{span.prepend(img);img.style.marginRight='.15em';}
   hookAssets.push({asset:block.brand_asset,entity_id:block.brand_entity_id,word_index:Number(span.dataset.word),reason:block.brand_reason,official_file_sha256:asset.sha256});
  }
  type.appendChild(group);
  const requestedStart=block.start_frame/fps;
  // Una identidad ya pronunciada no espera al siguiente prefijo textual.
  // El foco inicial lo decide el planner; los demás glifos conservan su voz.
  const initialIdentity=isHook&&block.word_start===0&&words[0].start===0&&(production||(hookV3&&block.brand_asset&&dir.focus_windows?.[0]?.start_frame===0&&dir.focus_windows[0].primary_target===block.brand_entity_id));
  const nextSequence=hookV3&&isHook?all.filter(b=>b.placement==='hook'&&b.start_frame>block.start_frame).sort((a,b)=>a.start_frame-b.start_frame)[0]:null;
  const carryIdentity=initialIdentity&&nextSequence&&nextSequence.start_frame>block.end_frame&&nextSequence.start_frame-block.end_frame<=9;
  const start=initialIdentity?0:requestedStart,end=(carryIdentity?nextSequence.start_frame:block.end_frame)/fps;
  if(initialIdentity&&requestedStart!==0)receipts.push({text:block.id,override:'initial_spoken_identity',requested_start:requestedStart,executed_start:0,reason:'planner initial focus + authentic identity at source word 0; subsequent words retain narration times'});
  if(carryIdentity)receipts.push({text:block.id,override:'identity_hold_until_next_focus',requested_end:block.end_frame/fps,executed_end:end,reason:'hold the last pronounced state through a short inter-phrase gap; no new words or actor'});
  if((hookV3||production)&&isHook&&start===0)group.style.opacity='1';
  main.set(group,{opacity:1},start);main.set(group,{opacity:0},end);
  const compositionY=compositionTextY(start,end,Math.max(76,group.offsetHeight));
  const cameraAtStart=atCamera(start),textDivider=production&&cameraAtStart?.state==='split'?1920*cameraAtStart.split_top:dividerY;
  const hookPose={y:cameraAtStart?.state==='full'?chin[Math.round(start*fps)]*(cameraAtStart.pose?.scale??1)+(cameraAtStart.pose?.y??0)+10:cameraAtStart?.state==='split'?(hookV3&&block.brand_asset?.includes('wordmark')?240:textDivider-Math.max(76,group.offsetHeight)-56):compositionY};
  if(isHook){
   // Durante el reencuadre inicial no colocar el título sobre el rostro
   // que todavía ocupa el lienzo; la frase se mantiene al completar el split.
   if(cameraAtStart?.state==='split'&&start<cameraAtStart.start+cameraAtStart.transition_frames/fps){
    const ready=cameraAtStart.start+cameraAtStart.transition_frames/fps;
    main.set(group,{opacity:0},start);if(ready<end)main.set(group,{opacity:1},ready);
    receipts.push({text:block.id,reason:'typography_pause_until_split_region_is_clear',start,end:Math.min(ready,end)});
   }
   for(const span of group.children){const word=words[Number(span.dataset.word)],at=Math.max(start,Math.round(word.start*fps)/fps);if((hookV3||production)&&Number(span.dataset.word)===0){gsap.set(span,{opacity:1});continue;}gsap.set(span,{opacity:0});main.fromTo(span,{opacity:0},{opacity:1,duration:Math.min(production?.2:.14,end-at),ease:'power3.out',immediateRender:false},at);}
   if(cameraAtStart?.state==='full'){
    const next=camera.find(c=>c.start>=start&&c.state==='split'&&c.start<end);
    if(next){const move=next.transition_frames/fps;main.to(hookPose,{y:(production?1920*next.split_top:dividerY)-Math.max(76,group.offsetHeight)-56,duration:move,ease:'power3.inOut'},next.start);main.to(group,{opacity:0,duration:1/fps,ease:'none'},next.start-1/fps);main.fromTo(group,{opacity:0},{opacity:1,duration:1/fps,ease:'none',immediateRender:false},next.start+move);}
   }
  }else{
   for(const window of camera){
    // Pausa tipográfica breve durante el reveal: evita que el subtítulo
    // atraviese el rostro. Sus palabras ya se leen en el bloque persistente.
    if(window.start>start&&window.start<end&&window.transition_frames&&window.start_frame>0){const before=camera.find(c=>c.end_frame===window.start_frame);if(!before){main.to(group,{opacity:0,duration:2/fps,ease:'power2.in'},window.start-2/fps);const restored=window.start+window.transition_frames/fps;if(restored<end)main.fromTo(group,{opacity:0},{opacity:1,duration:1/fps,ease:'none',immediateRender:false},restored);receipts.push({text:block.id,reason:'brief_type_pause_during_camera_reveal',start:window.start-2/fps,end:Math.min(end,restored)});}}
   }
  }
  if(isHook){
   // Medir cada prefijo con fuentes reales una sola vez. Los futuros glifos
   // no reservan huecos visibles ni desplazan la frase a un lado del plano.
   const spans=[...group.children],display=spans.map(s=>s.style.display||'inline-block');
   const allHeight=group.offsetHeight,origin=group.getBoundingClientRect();
   const layouts=[];
   for(let count=1;count<=spans.length;count++){
    spans.forEach((span,i)=>span.style.display=i<count?display[i]:'none');
    layouts.push(spans.map((span,i)=>{if(i>=count)return null;const b=span.getBoundingClientRect();return {x:b.left-origin.left,y:b.top-origin.top,w:b.width};}));
   }
   const full=layouts.at(-1);
   layouts.forEach(layout=>layout.forEach((v,i)=>{if(!v)layout[i]=full[i];}));
   spans.forEach((span,i)=>{span.style.display=display[i];span.style.position='absolute';span.style.left='0px';span.style.top='0px';span.style.width=full[i].w+'px';});
   const rowHeights=spans.map(span=>span.offsetHeight);
   group.style.height=allHeight+'px';
   const mix=(a,b,f)=>a.map((p,i)=>({x:p.x+(b[i].x-p.x)*f,y:p.y+(b[i].y-p.y)*f,w:p.w}));
   const prefixDuration=production?.3:.18;
   const events=[],ease=gsap.parseEase('power3.out'),poseAt=t=>{let e=events[0];for(const event of events){if(event.at>t)break;e=event;}return e?mix(e.from,e.to,ease(Math.max(0,Math.min(1,(t-e.at)/prefixDuration)))):layouts[0];};
   for(let count=1;count<=spans.length;count++){
    const at=Math.max(start,Math.round(words[block.word_start+count-1].start*fps)/fps),to=layouts[count-1];
    const from=poseAt(at).map(p=>({...p}));
    // El glifo nuevo acompaña el desplazamiento de la línea anterior,
    // conservando su separación mientras se centra el prefijo completo.
    // Un logo y una palabra pueden compartir línea con alturas distintas:
    // comparar intervalos verticales, no sus bordes superiores.
    let peer=-1;for(let i=0;i<count-1;i++)if(Math.max(to[i].y,to[count-1].y)<Math.min(to[i].y+rowHeights[i],to[count-1].y+rowHeights[count-1])-2)peer=i;
    from[count-1]={...to[count-1],x:to[count-1].x+(peer>=0?from[peer].x-to[peer].x:0),y:to[count-1].y+(hookV3&&count===1&&block.word_start===0?0:16)};
    events.push({at,from,to,count});
    spans.forEach((span,i)=>main.fromTo(span,{x:from[i].x,y:from[i].y},{x:to[i].x,y:to[i].y,duration:prefixDuration,ease:'power3.out',immediateRender:false},at));
   }
   receipts.push({text:block.id,override:'measured_prefix_layout',prefix_count:layouts.length,measurement:'loaded-font DOM once during setup',interpolation_seconds:prefixDuration,family_source_changed:false});
   visibleHeightAt=t=>{const event=events.filter(e=>e.at<=t+1e-7).at(-1);if(!event)return rowHeights[0];const poses=poseAt(t);return Math.max(...poses.slice(0,event.count).map((p,i)=>p.y+rowHeights[i]));};
  }
  main.addLabel('text_'+block.id,start);
  canvas.font=`${font==='Sequel'?700:400} ${fit}px ${font}`;const metrics=canvas.measureText(text),lineHeight=fit*1.03;
  const inkOffset=(lineHeight+(metrics.fontBoundingBoxAscent-metrics.fontBoundingBoxDescent))/2-metrics.actualBoundingBoxAscent;
  textNodes.push({block,group,text,isHook,start,end,fit,hookPose,compositionY,height:group.offsetHeight,visibleHeightAt,inkOffset:Number.isFinite(inkOffset)?inkOffset:0});
 }
 const luminance=color=>{
  const rgb=/^#[0-9a-f]{6}$/i.test(color)?[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)):/^rgba?\(/.test(color)?color.match(/[\d.]+/g).slice(0,3).map(Number):[244,244,243];
  const a=rgb.map(v=>{const s=v/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4;});
  return .2126*a[0]+.7152*a[1]+.0722*a[2];
 };
 // Pausa editorial sólo en la frontera medida entre superficies opuestas.
 // El color de una escena lógica no acredita que su reveal cubra el texto.
 if(production)for(const n of textNodes.filter(node=>!node.isHook)){
  const filmBox=film.getBoundingClientRect(),horizontal=[...n.group.children].map(span=>span.getBoundingClientRect());
  const left=Math.min(...horizontal.map(box=>box.left)),right=Math.max(...horizontal.map(box=>box.right));
  const textX=(left-filmBox.left)*1080/filmBox.width,textW=(right-left)*1080/filmBox.width;
  const yAt=t=>{const last=camera.filter(c=>c.end<=t&&t<c.end+.35).at(-1);if(!last)return n.compositionY;
   const f=Math.max(0,Math.min(1,(t-last.end)/.35)),prior=chin[Math.min(cfg.frames-1,Math.round(last.end*fps))]*last.pose.scale+last.pose.y+12-n.inkOffset;
   return prior+(n.compositionY-prior)*gsap.parseEase('power3.out')(f);};
  for(let index=1;index<nativeRecords.length;index++){
   const incoming=nativeRecords[index],outgoing=nativeRecords[index-1],scene=cfg.scenes.find(item=>item.id===incoming.scene_id),tin=scene.transition_in;
   if(tin.kind==='cut'||tin.duration<=0||incoming.start>=n.end||incoming.start+.201<=n.start)continue;
   const first=Math.max(Math.round(incoming.start*fps),Math.round(n.start*fps)),limit=Math.min(first+6,Math.round(n.end*fps)-1),samples=[];
   if(atCamera(first/fps))continue; // Bajo barbilla sigue la superficie de cámara.
   incoming.sample(first/fps-incoming.start);outgoing.sample(first/fps-outgoing.start);
   const incomingFill=getComputedStyle(incoming.background).fill,outgoingFill=getComputedStyle(outgoing.background).fill;
   if((luminance(incomingFill)<.179)===(luminance(outgoingFill)<.179))continue;
   let ready=null;
   for(let frame=first;frame<=limit;frame++){
    const t=frame/fps;if(atCamera(t))throw Error('Pausa de superficie alcanza una aparición de cámara; revisar frontera');
    const active=nativeRecords.filter(record=>t>=record.start&&t<record.start+record.visibleDuration);active.forEach(record=>record.sample(t-record.start));
    const box={x:textX,y:yAt(t),w:textW,h:n.height},layers=active.map(record=>({scene_id:record.scene_id,fill:getComputedStyle(record.background).fill,shapes:opaqueBackground(record,filmBox)}));
    const points=[0,.5,1].flatMap(x=>[0,.5,1].map(y=>{const px=box.x+box.w*x,py=box.y+box.h*y;
     const layer=[...layers].reverse().find(layer=>layer.shapes&&covered({x:px,y:py,w:0,h:0},layer.shapes));
     const fill=layer?.fill||colors[frame];return{x:px,y:py,scene_id:layer?.scene_id||'film',fill,matches_incoming_luminance_class:(luminance(fill)<.179)===(luminance(incomingFill)<.179)};}));
    const incomingShapes=layers.find(layer=>layer.scene_id===incoming.scene_id)?.shapes;
    // El film puede cubrir el hueco entre dos superficies que se desplazan.
    // Una máscara desconocida sólo admite prueba de cobertura total entrante.
    const clear=layers.every(layer=>layer.shapes)?points.every(point=>point.matches_incoming_luminance_class):!!incomingShapes&&covered(box,incomingShapes);
    samples.push({frame,caption_bbox:box,composited_background_layers:layers,composited_surface_samples:points,covered:clear});
    if(clear){ready=frame;break;}
   }
   if(ready===first)continue;
   if(ready===null)throw Error('Reveal no libera caption en ≤0,201 s: '+n.block.id+' / '+incoming.scene_id);
   const coverage=words.slice(n.block.word_start,n.block.word_end+1).map((word,i)=>({word_index:n.block.word_start+i,text:word.text,
    first_visible_frame:Math.max(ready,Math.ceil(word.start*fps),n.block.start_frame),end_frame_exclusive:Math.min(n.block.end_frame,Math.ceil(word.end*fps))}));
   if(coverage.some(word=>word.first_visible_frame>=word.end_frame_exclusive))throw Error('Pausa de reveal omitiría una palabra completa: '+n.block.id);
   main.set(n.group,{opacity:0},first/fps);main.set(n.group,{opacity:1},ready/fps);
   receipts.push({text:n.block.id,scene_id:incoming.scene_id,outgoing_scene_id:outgoing.scene_id,reason:'brief_type_pause_during_scene_reveal',
    start:first/fps,end:ready/fps,start_frame:first,end_frame_exclusive:ready,duration_s:(ready-first)/fps,maximum_s:.201,
    incoming_fill:incomingFill,outgoing_fill:outgoingFill,transition_kind:tin.kind,measurement:'real native clock + instance repaint + outgoing/incoming opaque clips and film; nine caption surface samples',
    checked_frames:samples,word_presence_after_pause:coverage,source_words_and_P2_times_unchanged:true});
  }
 }
 nativeRecords.forEach(record=>record.sample(0));
 const paint=()=>{
  const t=main.time(),frame=Math.max(0,Math.min(cfg.frames-1,Math.round(t*fps))),cam=atCamera(t),dark=luminance(colors[frame])<.179;
  // El fondo gráfico sigue el color nativo a tamaño completo; sólo los
  // objetos cambian de encuadre. Nunca se duplica ni rellena la grabación.
  film.style.backgroundColor=colors[frame];
  mask.style.clipPath=`inset(${cameraState.maskFraction*100}% 0% 0% 0%)`;mask.style.opacity=String(cameraState.alpha);
  plane.style.transform=production?`translate(${cameraState.x}px,${cameraState.y}px) scale(${cameraState.scale})`:`translateY(${cameraState.y}px)`;
  viewport.style.clipPath=`inset(0% 0% ${(1-motionState.coverageFraction)*100}% 0%)`;
  world.style.transform=`translate(${motionState.x}px,${motionState.y}px) scale(${motionState.scale})`;
  const active=textNodes.filter(n=>t>=n.start&&t<n.end);
  const tokens=new Set(active.flatMap(n=>words.slice(n.block.word_start,n.block.word_end+1).map(w=>norm(w.text))));
  duplicates.forEach(p=>p.wrapper.style.opacity=tokens.has(p.value)?'0':'1');
  for(const n of textNodes){
   const under=!n.isHook&&!!cam;
   let y=under?chin[frame]*(production?cameraState.scale:1)+cameraState.y+12-n.inkOffset:n.isHook?n.hookPose.y:n.compositionY;
   if(n.isHook&&cam){
    const height=production&&cam.state==='split'&&n.visibleHeightAt?n.visibleHeightAt(t):n.height;
    const initialY=production&&cam.state==='split'?1920*cam.split_top-height-56:n.hookPose.y;
    y=initialY;
    const index=camera.indexOf(cam),next=camera[index+1];
    const exit=next?.start_frame===cam.end_frame?0:production?cam.exit_frames/fps:Math.min((cam.exit_frames||6)/fps,(cam.end-cam.start)/3);
    if(exit&&t>=cam.end-exit&&cam.end<n.end){
     const f=Math.max(0,Math.min(1,(t-cam.end+exit)/exit));
     y=initialY+(n.compositionY-initialY)*gsap.parseEase('power3.inOut')(f);
     // Permanecer encima de la máscara mientras aún hay cámara debajo.
     y=Math.min(y,cameraState.maskFraction*1920-height-48);
    }
   }
   if(n.isHook&&!cam){
    const last=camera.filter(c=>c.end<=t&&c.end>n.start).at(-1);
    if(last)y=n.compositionY;
   }
   if(!n.isHook&&!cam){const returnTime=production?.35:.16,last=camera.filter(c=>c.end<=t&&t<c.end+returnTime).at(-1);if(last){const f=Math.max(0,Math.min(1,(t-last.end)/returnTime)),prior=chin[Math.min(cfg.frames-1,Math.round(last.end*fps))]*(production?last.pose.scale:1)+(production?last.pose.y:last.state==='split'?splitY:0)+12-n.inkOffset;y=prior+(n.compositionY-prior)*gsap.parseEase('power3.out')(f);}}
   n.group.style.transform=`translateY(${y}px)`;
   // La ventana lógica puede seguir abierta mientras su máscara ya retiró
   // la foto debajo del texto. El contraste sigue la superficie visible.
   const textInkTop=y+n.inkOffset,photoBelowText=cameraState.alpha>.01&&textInkTop>=cameraState.maskFraction*1920&&textInkTop<1920;
   const white=photoBelowText||dark;
   n.group.style.color=white?'#fff':'#171719';n.group.style.textShadow=white?cfg.shadow:'none';
   for(const span of n.group.children){const emphasis=n.block.color==='red'&&(n.block.emphasis_word_indices||[]).includes(Number(span.dataset.word));span.style.color=emphasis?(white?'#ff4140':'#b71925'):'inherit';}
  }
 };
 main.eventCallback('onUpdate',paint);
 const real=CloneTimelineReal(main);real.seek(Math.max(0,d-1/fps),false);real.seek(0,false);paint();
 window.__timelines['clone-main']=main;
 window.__integrationReceipt={version:production?3:2,profile:production?'production_complete':'legacy',camera_windows:camera,camera_poses:cfg.camera_poses||null,face_tracking_sha256:cfg.face_tracking_sha256||null,visible_frames:camera.reduce((sum,w)=>sum+w.end_frame-w.start_frame,0),split_poses:splitPoses.map(p=>({start_frame:p.window.start_frame,end_frame:p.window.end_frame,...p.pose})),hook_assets_used:hookAssets,background_fill_normalization:[...backgroundFills.values()],components:nativeRecords.map(r=>({scene_id:r.scene_id,family:r.family,used_assets:[...r.context.usedAssets]})),text_blocks:textNodes.map(n=>({...n.block,text:n.text,font_size:n.fit})),component_overrides:receipts,audio_playback:cfg.audio_playback||null,source_audio:cfg.audio_mix?'original_voice_stem_with_verified_mix':'original_unchanged',scope:'geometría calculada de antemano; no certifica fidelidad visual',render_clock:'HyperFrames',autonomous_timers:false};
 const actualAssetKeys=new Set([...nativeRecords.flatMap(r=>[...r.context.usedAssets]),...hookAssets.map(a=>a.asset)]);
 await Promise.all([...actualAssetKeys].map(key=>{const img=new Image();img.src=window.CLONE_ASSETS[key].data;return img.decode();}));
 await Promise.all([...type.querySelectorAll('img')].map(img=>img.decode()));
 window.__integrationBuilt=true;window.renderReady=true;
 window.dispatchEvent(new Event('hf-timelines-built'));
};
