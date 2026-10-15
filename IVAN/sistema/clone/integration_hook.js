/* Dirección focalizada por instancia; no modifica los componentes CLONE.
   La frase pronunciada pertenece al stream editorial. El foco viene del planner. */
window.CloneIntegrationHook=(C,scene,native,cfg)=>{
 const receipt=[],ns='http://www.w3.org/2000/svg';
 const hide=(el,reason)=>{
  if(!el)return;const gate=document.createElementNS(ns,'g');gate.id=C.id('integration-hook-suppressed-'+receipt.length);gate.setAttribute('opacity','0');gate.dataset.hookSuppressed=reason;
  el.parentNode.insertBefore(gate,el);gate.append(el);receipt.push({target:el.id||gate.id,text:el.tagName==='text'?el.textContent:null,reason});return gate;
 };
 // Sólo el objetivo editorial de spotlight: una frase literal ya cubierta por
 // la narración/subtítulos no se repite como UI. El hook conserva su contexto.
 if(cfg.profile==='production_complete'&&scene.family==='spotlight_agent'&&scene.start>=(cfg.direction?.hook_end_frame??Infinity)/30){
  const tokens=text=>String(text||'').normalize('NFC').toLocaleLowerCase('es').match(/[\p{L}\p{N}]+/gu)||[];
  const goalTokens=tokens(scene.params.goal),words=cfg.narration?.words||[],captionBlocks=cfg.direction?.caption_blocks||[];
  if(goalTokens.length>=3){
   const sceneWords=words.map((word,index)=>({word,index,tokens:tokens(word.text)})).filter(item=>item.word.start>=scene.start-1e-7&&item.word.end<=scene.start+scene.duration+1e-7);
   const match=sceneWords.findIndex((item,offset)=>goalTokens.every((token,j)=>sceneWords[offset+j]?.tokens.length===1&&sceneWords[offset+j].tokens[0]===token&&(!j||sceneWords[offset+j].index===item.index+j)));
   if(match>=0){
    const anchors=sceneWords.slice(match,match+goalTokens.length),coverage=anchors.map(({index,word})=>({index,blocks:captionBlocks.filter(block=>block.word_start<=index&&block.word_end>=index&&block.start_frame<=Math.ceil(word.start*30)&&block.end_frame>=Math.floor(word.end*30))}));
    if(coverage.every(item=>item.blocks.length)){
     const goal=C.q('goal'),nativeText=goal&&[...goal.querySelectorAll('text')].map(text=>[...text.querySelectorAll('tspan')].length?[...text.querySelectorAll('tspan')].map(span=>span.textContent).join(' '):text.textContent).join(' ');
     if(!goal||JSON.stringify(tokens(nativeText))!==JSON.stringify(goalTokens))throw Error('Objetivo editorial literal de spotlight no verificable');
     const reason='source_caption_owns_literal_editorial_goal',gate=hide(goal,reason);
     receipt.push({override:reason,target:goal.id,gate:gate.id,phrase:scene.params.goal,normalized_literal_tokens:goalTokens,
      anchors:anchors.map(({word,index})=>({word_index:index,text:word.text,start:word.start,end:word.end})),
      caption_ids:[...new Set(coverage.flatMap(item=>item.blocks.map(block=>block.id)))],literal_consecutive_source_words:true,
      caption_word_coverage:coverage.map(item=>({word_index:item.index,caption_ids:item.blocks.map(block=>block.id)})),
      original_params_unchanged:true,native_actor_command_actions_unchanged:true,independent_opacity_gate:true,timeline_modified:false});
    }
   }
  }
 }
 const functional=(cfg.instance_overrides||[]).find(item=>item.scene_id===scene.id&&item.kind==='pixel_functional_roles');
 if(functional){
  if(cfg.profile!=='production_complete'||scene.family!=='pixel_agents'||functional.hide_count!==true)throw Error('Override pixel funcional fuera de contrato');
  const count=scene.params.roles.length,countText=[...C.q('result').querySelectorAll('text')].filter(text=>text.textContent===`${count} ROLES COORDINADOS`);
  if(!C.q('ghost')||countText.length!==1||functional.labels.length!==count)throw Error('Conteo o roles nativos no verificables');
  hide(C.q('ghost'),'functions_are_not_a_narrated_count_of_independent_agents');
  hide(countText[0],'functions_are_not_a_narrated_count_of_independent_agents');
  functional.labels.forEach((label,i)=>{
   const role=C.q('role-'+i),texts=role&&[...role.querySelectorAll('text')],pill=C.q('role-'+i+'-pill');
   if(!pill||texts?.length!==1)throw Error('Etiqueta funcional nativa no verificable: '+i);
   const text=texts[0],original=text.textContent,originalSize=Number(text.getAttribute('font-size'));
   text.textContent=label;text.setAttribute('font-size',C.fit(label,Number(pill.getAttribute('width'))-24,24,'JetBrains'));
   receipt.push({target:C.id('role-'+i),override:'functional_label_abbreviation',original_text:original,display_text:label,
    original_font_size:originalSize,display_font_size:Number(text.getAttribute('font-size')),reason:functional.reason,native_role_and_sprite_unchanged:true,timeline_modified:false});
  });
  receipt.push({override:'pixel_functional_roles',reason:functional.reason,original_params_unchanged:true,independent_opacity_gates:true});
 }
 if(cfg.revision!=='V3_hook'||scene.family!=='composition_graph')return{receipt};
 for(const node of scene.params.nodes){
  if(node.kind==='editorial')hide(C.q(node.id),'official_identity_and_spoken_phrase_owned_by_editorial_stream');
  else hide(C.q(node.id+'-body'),'spoken_words_owned_by_single_editorial_stream_not_duplicate_ui_copy');
 }
 // Una transferencia explica el proceso sin agregar otro rótulo que compita.
 for(const [i,step]of scene.params.steps.entries())if(['transfer','collect'].includes(step.op)){
  const packet=C.q('packet'+i);if(packet){
   for(const text of packet.querySelectorAll('text'))hide(text,'packet_motion_is_support_not_another_caption');
   // El paquete conserva trayectoria/reloj nativos y se lee como dato en
   // tránsito, sin una tercera tarjeta vacía que compita con sus extremos.
   const rect=packet.querySelector('rect');
   if(rect){for(const [name,value]of Object.entries({x:-9,y:-9,width:18,height:18,rx:9}))rect.setAttribute(name,String(value));rect.removeAttribute('filter');receipt.push({target:'packet'+i,override:'compact_native_transfer_particle',size_native:18,native_route_clock_and_actions_unchanged:true});}
  }
 }
 const windows=cfg.direction.focus_windows||[];
 receipt.push({focus_windows:windows,max_primary:1,max_support:1,execution:'native_pose_focus_gates',original_steps_unchanged:true});
 return{receipt};
};

/* Etiquetas de función sobre celdas originales: dos líneas, sin mover sprites
   ni cambiar sus gestos. Se comprueba el espacio horizontal con fuentes reales. */
window.CloneIntegrationReadableLabels=(C,scene,cfg)=>{
 const receipt=[];if(cfg.profile!=='production_complete'||scene.family!=='terminal_install'||!scene.params.showRoleLabels)return{receipt};
 const ns='http://www.w3.org/2000/svg',canvas=document.createElement('canvas').getContext('2d'),windowGroup=C.q('window'),rows=new Map();
 if(!windowGroup)throw Error('Terminal sin ventana original verificable');
 const base=windowGroup.getScreenCTM();if(!base)throw Error('Terminal sin matriz original verificable');
 scene.params.roles.forEach((_,i)=>{
  const group=C.q('role-'+i),text=group?.querySelector('text');if(!text)throw Error('Etiqueta terminal original ausente');
  const original=text.textContent,parts=original.trim().split(/\s+/),size=Number(text.getAttribute('font-size')),family=text.getAttribute('font-family'),weight=text.getAttribute('font-weight')||400;
  if(!Number.isFinite(size)||size<=0)throw Error('Fuente terminal no medible');canvas.font=`${weight} ${size}px ${family}`;
  let lines=[original],width=canvas.measureText(original).width;
  if(parts.length>1){let best=null;for(let split=1;split<parts.length;split++){const pair=[parts.slice(0,split).join(' '),parts.slice(split).join(' ')],w=Math.max(...pair.map(line=>canvas.measureText(line).width));if(!best||w<best.width)best={lines:pair,width:w};}lines=best.lines;width=best.width;}
  const matrix=base.inverse().multiply(group.getScreenCTM()),rowKey=Math.round(matrix.f),item={group,text,original,lines,width,size,x:matrix.e,y:Number(text.getAttribute('y'))};
  if(!rows.has(rowKey))rows.set(rowKey,[]);rows.get(rowKey).push(item);
 });
 for(const row of rows.values()){
  row.sort((a,b)=>a.x-b.x);const gap=24,total=row.reduce((v,item)=>v+item.width,0)+gap*(row.length-1),center=row.reduce((v,item)=>v+item.x,0)/row.length;
  if(total>570)throw Error('Etiquetas terminal no caben en dos líneas conservando fuente; revisar contenido original');
  let left=Math.max(63,Math.min(657-total,center-total/2));
  for(const item of row){
   const offset=left+item.width/2-item.x;item.text.replaceChildren();
   item.lines.forEach((line,index)=>{const span=document.createElementNS(ns,'tspan');span.setAttribute('x',offset);span.setAttribute('y',item.y+index*item.size*1.15);span.textContent=line;item.text.append(span);});
   receipt.push({target:item.group.id,override:'two_line_native_role_label',original_text:item.original,lines:item.lines,font_size:item.size,font_size_unchanged:true,
    label_offset_x_native:offset,max_line_width_native:item.width,minimum_horizontal_gap_native:gap,original_cell_sprite_and_gestures_unchanged:true});left+=item.width+gap;
  }
 }
 return{receipt};
};

/* Protagonismo de marca oficial opt-in: una misma superficie pasa de identidad
   a apoyo. Todos los tiempos vienen del contrato de instancia, no de un timer. */
window.CloneIntegrationSpotlightHook=(C,scene,native,cfg,options)=>{
 const item=(cfg.instance_overrides||[]).find(v=>v.scene_id===scene.id&&v.kind==='spotlight_hook_identity');
 if(!item)return{receipt:[],layout_options:{}};
 if(cfg.profile!=='production_complete'||scene.family!=='spotlight_agent'||scene.start!==0)throw Error('Identidad spotlight fuera de contrato');
 const ns='http://www.w3.org/2000/svg',svg=C.root.querySelector('svg'),asset=window.CLONE_ASSETS[item.asset],receipt=[];
 if(!asset||asset.kind!=='brand_logo'||!asset.data)throw Error('Identidad hook no resuelta oficialmente');
 const fps=30,ratio=cfg.direction.camera_windows[0].split_top??cfg.direction.split_top;
 const reserve=(options.hook_height_px+96)/1.5,upper=1280*ratio;
 const primary={x:360,y:(44+upper-reserve)/2,scale:1},support={x:94,y:78,scale:item.support_major_px/item.painted_major_px};
 const size=item.painted_major_px/1.5,b=asset.alpha_bbox||[0,0,asset.width,asset.height],major=Math.max(b[2]-b[0],b[3]-b[1]);
 const viewport=size*Math.max(asset.width,asset.height)/major,pad=18;
 if(primary.y-size/2-pad<30||primary.y+size/2+pad>upper-reserve)throw Error('Identidad hook no cabe sobre el titular medido');
 const group=document.createElementNS(ns,'g');group.id=C.id('integration-official-hook');group.dataset.integrationFixedOverlay='true';
 group.innerHTML=`<rect x="${-size/2-pad}" y="${-size/2-pad}" width="${size+2*pad}" height="${size+2*pad}" rx="24" fill="${C.colors.paper}" filter="${C.soft}"/>${C.image(item.asset,-viewport/2,-viewport/2,viewport,viewport)}`;
 const image=group.querySelector('image');image.setAttribute('preserveAspectRatio','xMidYMid meet');image.style.filter='none';
 svg.appendChild(group);
 const gate=(name)=>{
  const el=C.q(name);if(!el)throw Error('Objeto spotlight nativo no verificable: '+name);
  const wrap=document.createElementNS(ns,'g');wrap.id=C.id('integration-hook-gate-'+name);el.parentNode.insertBefore(wrap,el);wrap.appendChild(el);return wrap;
 };
 const heroGate=gate('hero'),goalGate=C.q('goal')?gate('goal'):null;
 // El identificador de herramienta es secundario. Su posición original
 // bajo el actor divide el espacio reservado al titular grande de capacidad.
 // Reencuadrar la misma superficie, no quitarla ni crear otra etiqueta.
 const command=C.q('command'),commandBox=command.getBBox(),commandScale=Math.min(1,280/commandBox.width);
 if(!Number.isFinite(commandBox.width)||commandBox.width<=0||commandScale<.6)throw Error('Identificador spotlight no puede conservar lectura móvil');
 const commandPose={scale:commandScale,x:42-commandBox.x*commandScale,y:support.y+96-commandBox.y*commandScale};
 const commandWrapper=document.createElementNS(ns,'g');commandWrapper.id=C.id('integration-hook-command-support');
 commandWrapper.setAttribute('transform',`translate(${commandPose.x} ${commandPose.y}) scale(${commandPose.scale})`);
 command.parentNode.insertBefore(commandWrapper,command);commandWrapper.appendChild(command);
 receipt.push({target:command.id,override:'native_identifier_support_reframe',source_bbox:{x:commandBox.x,y:commandBox.y,w:commandBox.width,h:commandBox.height},pose:commandPose,
  source_text_preserved:true,native_timeline_and_gestures_preserved:true,reason:'Original tool identifier becomes secondary beside official identity; lower area remains free for large source-aligned capability sentence.'});
 const tweens=native.getChildren(true,true,false);
 for(const name of ['light','hero','command']){
  const target=C.q(name),entries=tweens.filter(t=>t.vars.opacity===1&&t.targets().includes(target));
  if(entries.length!==1)throw Error('Tween de entrada spotlight no verificable: '+name);
  const tween=entries[0],at=tween.startTime(),old=tween.duration(),outAt=options.toOutput(at),newNative=options.toNative(outAt+item.entrance_s)-at;
  if(newNative<=0||outAt+item.entrance_s>scene.duration)throw Error('Entrada spotlight no ejecutable dentro de su escena');
  const actualOutput=options.toOutput(at+newNative)-outAt;
  if(Math.abs(actualOutput-item.entrance_s)>1/fps)throw Error('La pausa del phase clock impide medir la entrada solicitada');
  tween.duration(newNative);
  receipt.push({target:C.id(name),override:'entrance_duration_only',original_native_start:at,executed_native_start:tween.startTime(),original_native_duration:old,
   executed_native_duration:newNative,executed_output_start:outAt,requested_output_duration:item.entrance_s,executed_output_duration:actualOutput,other_gestures_and_actions_unchanged:true});
 }
 const begin=item.primary_until_frame/fps,end=(item.primary_until_frame+item.transform_frames)/fps,hookEnd=cfg.direction.hook_end_frame/fps;
 const ease=gsap.parseEase('power2.inOut'),goalEntry=gsap.parseEase('power3.out');
 receipt.push({override:'authentic_hook_identity_to_support',asset:item.asset,original_file_sha256:asset.sha256,original_bytes_unchanged:true,primary_pose:primary,support_pose:support,
  painted_major_px:item.painted_major_px,support_major_px:item.support_major_px,primary_interval:[0,begin],transform_interval:[begin,end],transform_ease:'power2.inOut',
  reason:item.reason,original_actor_revealed_after_identity:true,inline_duplicate_suppressed:true,goal_suppressed_until:hookEnd,
  hook_text_height_px:options.hook_height_px,hook_bottom_reserved_native:reserve,icon_rotation:0,icon_shadow:false,container_shadow:'native_soft',native_source_modified:false});
 return{receipt,layout_options:{hook_bottom_reserved_native:reserve,exclude_bounds_ids:[C.id('light')]},paint(outputTime){
  const k=ease(Math.max(0,Math.min(1,(outputTime-begin)/(end-begin)))),pose={x:primary.x+(support.x-primary.x)*k,y:primary.y+(support.y-primary.y)*k,scale:1+(support.scale-1)*k};
  group.setAttribute('transform',`translate(${pose.x} ${pose.y}) scale(${pose.scale})`);
  group.setAttribute('opacity',outputTime<scene.duration?'1':'0');
  // Gate independiente: GSAP conserva su propia opacidad/gesto interior.
  heroGate.setAttribute('opacity',String(k));
  goalGate?.setAttribute('opacity',String(goalEntry(Math.max(0,Math.min(1,(outputTime-hookEnd)/.35)))));
 }};
};
