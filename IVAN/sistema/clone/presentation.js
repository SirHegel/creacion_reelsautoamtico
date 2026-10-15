/* Adaptación de nuevas instancias. Ningún módulo reconstruido se modifica.
   Las claves autorizadas provienen del contrato local validado por Python. */
window.CloneTimelineReal = timeline => {
  const seen=new Set();
  while(timeline?.__hfReal){
    if(seen.has(timeline))throw Error('Ciclo en el proxy de timeline HyperFrames');
    seen.add(timeline);timeline=timeline.__hfReal;
  }
  if(typeof timeline?.seek!=='function'||typeof timeline?.duration!=='function')throw Error('Timeline real no disponible');
  return timeline;
};
window.CloneBuildCreative = (scene,root) => {
  if(!scene.choreography)return Clone.build(scene.family,root,scene.params,scene.duration,scene.id);
  const definition=Clone.definitions.get(scene.family),original=definition.build;
  // Los SETs de duración0 son revertidos en exact0 por el estabilizador de
  // HyperFrames. Su valor anterior también debe ser el estado inicial correcto.
  // Inyectarlo antes de crear tweens corrige el transporte directo e inverso,
  // sin editar las reconstrucciones ni hacer un parche después del render.
  definition.build=C=>{
    const names=[];
    if(scene.family==='feedback_bars')for(let i=0;i<=C.params.categories.length;i++)names.push('caption'+i);
    if(scene.family==='problem_resolution')C.params.features.forEach((_,i)=>names.push('new'+i));
    if(scene.family==='phone_qa')C.params.checks.forEach((_,i)=>names.push('tick'+i));
    if(scene.family==='product_card')names.push('buttonOpen','trail');
    if(scene.family==='terminal_install')names.push('install','selection','ready');
    if(scene.family==='spotlight_agent'&&C.params.goal)names.push('goal');
    const svg=C.svg;
    C.svg=content=>{
      let markup=svg(content);
      names.forEach(name=>{const match='<g id="'+C.id(name)+'"';markup=markup.replace(match,'<g opacity="0" id="'+C.id(name)+'"');});
      return markup;
    };
    return original(C);
  };
  try{return Clone.build(scene.family,root,scene.params,scene.duration,scene.id);}
  finally{definition.build=original;}
};
window.ClonePresent = (built, scene) => {
  const C=built.context, svg=C.root.querySelector('svg');
  const motion_labels=[],zero_poses=[];
  const p=scene.presentation;
  const contract=window.CLONE_PRESENTATION?.families?.[scene.family];
  const measure=document.createElement('canvas').getContext('2d');
  function fit(node,size,width) {
    const font=node.getAttribute('font-family')||'InterUI';
    const weight=node.getAttribute('font-weight')||'700';
    measure.font=`${weight} ${size}px ${font}`;
    const actual=Math.min(size,size*width/Math.max(1,measure.measureText(node.textContent).width));
    node.setAttribute('font-size',actual);
    return actual;
  }
  function editorial(node){
    const text=node.textContent,desired=62,width=620;
    measure.font=`400 ${desired}px Scholar`;
    const lines=[];
    for(const paragraph of text.split(/\n/)){
      let line='';
      for(const word of paragraph.split(/\s+/).filter(Boolean)){
        const next=line?line+' '+word:word;
        if(line&&measure.measureText(next).width>width){lines.push(line);line=word;}else line=next;
      }
      if(line)lines.push(line);
    }
    if(lines.length>4)throw Error('Texto editorial demasiado largo para móvil; abreviar o dividir la idea');
    const y=Number(node.getAttribute('y')),size=lines.length>3?52:desired,lineHeight=size*1.03;
    // Un bloque inferior conserva el límite de lectura y no invade la interfaz.
    // Para cuatro líneas bajar ligeramente el baseline, sin salir del lienzo.
    const baseline=lines.length>3?Math.max(y,1160):y;
    node.setAttribute('font-size',size);node.setAttribute('y',baseline-(lines.length-1)*lineHeight);
    node.replaceChildren();
    lines.forEach((value,i)=>{const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');span.setAttribute('x',node.getAttribute('x'));span.setAttribute('dy',i===0?0:lineHeight);span.textContent=value;node.appendChild(span);});
  }
  if(scene.choreography)[...svg.querySelectorAll('text[font-family="Scholar"]')].forEach(editorial);
  if(scene.choreography&&scene.family==='spotlight_agent'&&C.params.goal.includes('\n')){
    const node=C.q('goal')?.querySelector('text'),lines=C.params.goal.split('\n');
    if(node&&lines.length<=3){
      node.setAttribute('font-size',32);node.setAttribute('y',976-(lines.length-1)*38);node.replaceChildren();
      lines.forEach((value,i)=>{const span=document.createElementNS('http://www.w3.org/2000/svg','tspan');span.setAttribute('x',360);span.setAttribute('dy',i===0?0:38);span.textContent=value;node.appendChild(span);});
    }
  }
  if(p&&contract){
    Object.entries(p.labels||{}).forEach(([key,value])=>{
      const r=contract.labels[key];
      const nodes=[...svg.querySelectorAll('text')].filter(n=>n.textContent===r.original);
      if(!nodes.length)throw Error('Etiqueta de presentación no localizada: '+key);
      nodes.forEach(node=>{node.textContent=value;fit(node,r.size,r.width);});
    });
    (p.omit||[]).forEach(key=>{
      const r=contract.omit[key];
      (r.groups||[]).forEach(group=>{const node=C.q(group);if(!node)throw Error('Área ausente: '+group);node.style.display='none';});
      (r.texts||[]).forEach(value=>[...svg.querySelectorAll('text')].filter(n=>n.textContent===value).forEach(n=>n.style.display='none'));
    });
    // Solo instancias que optan por el contrato editorial: no alterar previews
    // o poses aprobadas. El ancho se calcula una vez, antes de renderizar.
    if(scene.family==='feedback_bars'){
      C.params.reviews.forEach((_,i)=>{const texts=C.q('review'+i)?.querySelectorAll('text');if(texts?.[0]){fit(texts[0],30,470);texts[0].setAttribute('y',203+i*103);}});
      C.params.categories.forEach((_,i)=>{const texts=C.q('row'+i)?.querySelectorAll('text');if(texts?.[0])fit(texts[0],28,205);const count=C.q('count'+i);if(count)count.setAttribute('font-size',36);});
    }
    if(scene.family==='radial_research'){
      C.params.sources.forEach((_,i)=>{const node=C.q('source'+i)?.querySelector('text');if(node)fit(node,28,174);});
      const group=C.q('counter-group'),nodes=group?.querySelectorAll('text');if(nodes?.[1])fit(nodes[1],30,280);
    }
    if(scene.family==='product_card'&&p.omit?.includes('rating')&&p.omit?.includes('price')){
      // Una sola propiedad suministrada ocupa la fila central: no conservar
      // dos columnas vacías como si hubiese métricas ocultas por completar.
      C.q('status').querySelector('text').setAttribute('x',360);
      [...svg.querySelectorAll('text')].filter(n=>n.textContent==='STATUS').forEach(n=>n.setAttribute('x',360));
    }
    if(scene.family==='problem_resolution'){
      // Textos de funciones se ajustan al área real, sin pisar toggle/NEW.
      [...C.q('phone').querySelectorAll('text')].filter(n=>C.params.features.some(f=>f.feature===n.textContent)).forEach(n=>fit(n,22,123));
    }
    if(scene.family==='phone_rebuild'){
      // Mostrar uso tras construir. La réplica canónica queda intacta; esta
      // interacción de instancia aprovecha los slots reales del componente.
      const ns='http://www.w3.org/2000/svg',d=scene.duration,i=C.params.selected;
      const final=C.q('built'),tl=built.tl;
      C.params.times.forEach((_,j)=>{
        const b=C.q('blue-slot'+j),f=C.q('final-slot'+j);
        tl.set(b.querySelector('rect'),{attr:{fill:'#123ca5'}},0);
        tl.set(f.querySelector('rect'),{attr:{fill:'#faeee7'}},0);
        tl.set(f.querySelector('text'),{attr:{fill:C.params.accent}},0);
      });
      const pointer=document.createElementNS(ns,'g');pointer.id=C.id('selection-cursor');
      pointer.innerHTML='<path d="M0 0L0 26L6 20L12 31L17 29L11 18L21 17Z" fill="#fff" stroke="#171719" stroke-width="1.6" stroke-linejoin="round"/>';
      final.appendChild(pointer);
      const proof=document.createElementNS(ns,'g');proof.id=C.id('selection-proof');
      proof.innerHTML='<circle cx="237" cy="571" r="9" fill="#42b95c"/><path d="M232 571l3 3 6-7" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/>';
      final.appendChild(proof);
      const at=d*.74,selected=C.q('final-slot'+i),length=Math.min(.16,d*.035),factor=Math.min(1,d/4.5);
      tl.set(pointer,{x:255,y:510,opacity:0},0);tl.set(proof,{opacity:0},0);
      tl.fromTo(pointer,{x:255,y:510,opacity:0},{x:174,y:282+i*55,opacity:1,duration:length,ease:'power3.out',immediateRender:false},at);
      tl.to(selected.querySelector('rect'),{attr:{fill:C.params.accent},duration:.10*factor,ease:'power2.out'},at+length);
      tl.to(selected.querySelector('text'),{attr:{fill:'#fff'},duration:.10*factor},at+length);
      tl.to(pointer,{x:200,y:559,duration:length,ease:'power3.inOut'},at+length+.12*factor);
      tl.to(proof,{opacity:1,duration:.10*factor},at+2*length+.14*factor);
      tl.to(pointer,{opacity:0,duration:.10*factor},at+2*length+.28*factor);
      tl.addLabel('interaction_select',at);tl.addLabel('selection_feedback',at+2*length+.14*factor);
      motion_labels.push('interaction_select','selection_feedback');
    }
  }
  if(scene.choreography&&scene.family==='terminal_install'){
    const n=C.params.roles.length,tl=built.tl;
    // Una solicitud breve necesita lectura rápida. La lógica original sigue
    // siendo la fuente; el compositor usa un reloj remapeado determinista.
    if(C.params.command.length<=28&&!C.params.instruction){
      const typed=C.q('typed-0');typed.setAttribute('font-size',28);typed.setAttribute('y',192);
      const selection=C.q('selection');selection.setAttribute('width',C.params.command.length*28*.6+10);selection.setAttribute('height',34);selection.setAttribute('y',162);
      const cursor=C.q('cursor');cursor.setAttribute('height',28);
      C.repaints.push(()=>{cursor.setAttribute('x',87+Array.from(typed.textContent).length*28*.6+2);cursor.setAttribute('y',169);});
      const heading=[...C.q('window').querySelectorAll('text')].find(x=>x.textContent===C.params.title);if(heading)fit(heading,28,486);
    }
    if(n<=3&&C.params.showRoleLabels){
      const points=C.params.roles.map((_,i)=>({oldX:360+(i-(n-1)/2)*104,newX:360+(i-(n-1)/2)*180}));
      points.forEach((point,i)=>{
        const agent=C.q('agent-'+i),parent=agent.parentNode,image=agent.querySelector('image');
        parent.setAttribute('transform',`translate(${point.newX} 379)`);
        const height=Number(image.getAttribute('height'))*110/75;
        image.setAttribute('x',-55);image.setAttribute('y',28-height);image.setAttribute('width',110);image.setAttribute('height',height);
        const role=C.q('role-'+i).querySelector('text');fit(role,22,170);
      });
      C.repaints.push(()=>points.forEach((point,i)=>{
        const packet=C.q('packet-'+i),values=packet.getAttribute('transform')?.match(/translate\(([-\d.e]+)[ ,]+([-\d.e]+)\)/);
        if(!values)return;
        const sx=93+(i%6)*93,x=Number(values[1]),y=Number(values[2]),blend=(x-sx)/(point.oldX-sx);
        packet.setAttribute('transform',`translate(${sx+blend*(point.newX-sx)} ${y+blend*60})`);
      }));
    }
    const d=scene.duration;
    const beats=[[0,0],[.04,.12],[.19,.49],[.23,.52],[.275,.59],[.683333,.80],[.716667,.81],[.95,.94],[1,1]];
    const native=CloneTimelineReal(tl);
    const state={time:0},paint=()=>native.seek(state.time,false),retimed=gsap.timeline({paused:true});
    for(let i=1;i<beats.length;i++)retimed.fromTo(state,{time:beats[i-1][1]*d},{time:beats[i][1]*d,duration:(beats[i][0]-beats[i-1][0])*d,ease:'none',immediateRender:false,onUpdate:paint},beats[i-1][0]*d);
    const invert=t=>{const f=t/d;for(let i=1;i<beats.length;i++)if(f<=beats[i][1])return (beats[i-1][0]+(f-beats[i-1][1])/(beats[i][1]-beats[i-1][1])*(beats[i][0]-beats[i-1][0]))*d;return d;};
    if(!native.labels||typeof native.labels!=='object')throw Error('El componente no expone las etiquetas de su timeline real');
    Object.entries(native.labels).forEach(([key,time])=>retimed.addLabel(key,invert(time)));
    retimed.eventCallback('onUpdate',paint);built.renderTl=retimed;
    motion_labels.push('semantic_clock_remap');if(n<=3&&C.params.showRoleLabels)motion_labels.push('large_role_instances');
  }
  const handoffs=Array.isArray(scene.render_handoff)?scene.render_handoff:(scene.render_handoff?[scene.render_handoff]:[]);
  for(const handoff of handoffs){
    const phone=C.q('phone'),tl=built.tl;
    if(phone&&handoff.direction==='out'){
      const wrapper=document.createElementNS('http://www.w3.org/2000/svg','g');
      wrapper.id=C.id('device-handoff');phone.parentNode.insertBefore(wrapper,phone);wrapper.appendChild(phone);
      tl.set(wrapper,{svgOrigin:handoff.source[0]+' '+handoff.source[1],smoothOrigin:false,x:0,y:0,scale:1},0);
      tl.to(wrapper,{x:handoff.target[0]-handoff.source[0],y:handoff.target[1]-handoff.source[1],scale:handoff.target[2]/handoff.source[2]/1.014,duration:handoff.duration,ease:'power3.inOut'},scene.duration-handoff.duration);
      tl.addLabel('device_handoff',scene.duration-handoff.duration);motion_labels.push('device_handoff');
    }
    if(phone&&handoff.direction==='in'){
      // Suprimir solo la entrada de dispositivo: ya viene de un encuadre
      // coincidente. Las transformaciones internas y los demás actores siguen.
      tl.getChildren(true,true,false).filter(t=>t.startTime()<scene.duration*.12&&t.targets().includes(phone)).forEach(t=>t.kill());
      tl.set(phone,{x:0,y:0,rotation:0,scale:1,opacity:1},0);
      zero_poses.push({node:phone,vars:{x:0,y:0,rotation:0,scale:1,opacity:1}});
      motion_labels.push('device_pose_continued');
    }
    if(handoff.actor){
      const actor=C.q(handoff.actor.group),tl=built.tl;
      if(actor&&handoff.direction==='out'){
        const wrapper=document.createElementNS('http://www.w3.org/2000/svg','g'),a=handoff.actor;
        actor.parentNode.insertBefore(wrapper,actor);wrapper.appendChild(actor);
        tl.set(wrapper,{svgOrigin:a.source[0]+' '+a.source[1],smoothOrigin:false,x:0,y:0,scale:1},0);
        tl.to(wrapper,{x:a.target[0]-a.source[0],y:a.target[1]-a.source[1],scale:a.target[2]/a.source[2],duration:handoff.duration,ease:'power3.inOut'},scene.duration-handoff.duration);
      }
      if(actor&&handoff.direction==='in'){
        tl.getChildren(true,true,false).filter(t=>t.startTime()<scene.duration*.12&&t.targets().includes(actor)).forEach(t=>t.kill());
        tl.set(actor,{x:0,y:0,rotation:0,scale:1,opacity:1},0);
        zero_poses.push({node:actor,vars:{x:0,y:0,rotation:0,scale:1,opacity:1}});
      }
    }
  }
  if(zero_poses.length){
    C.presentZero=()=>zero_poses.forEach(p=>gsap.set(p.node,p.vars));
    const prior=built.tl.eventCallback('onUpdate');
    built.tl.eventCallback('onUpdate',()=>{if(prior)prior();if(built.tl.time()===0)C.presentZero();});
  }
  if(scene.framing?.view_box)svg.setAttribute('viewBox',scene.framing.view_box.join(' '));
  // Estado semántico declarado, no prueba de funcionamiento real de la UI.
  if(scene.illustrative_fields?.length||scene.conceptual===true||window.CLONE_PLAN?.semantic_analysis?.conceptual===true){
    const note=document.createElementNS('http://www.w3.org/2000/svg','text');
    const view=(svg.getAttribute('viewBox')||'0 0 720 1280').split(/\s+/).map(Number);
    note.setAttribute('x',view[0]+view[2]/2);note.setAttribute('y',view[1]+view[3]-35);
    note.setAttribute('text-anchor','middle');note.setAttribute('font-family','Mono');
    note.setAttribute('font-weight','400');note.setAttribute('font-size','19');
    note.setAttribute('fill',['phone_compare','product_card','spotlight_agent'].includes(scene.family)?'#c4bbb6':'#625a56');
    note.textContent='EJEMPLO CONCEPTUAL';svg.appendChild(note);
  }
  return {framing:scene.framing||null,presentation:p||null,motion_labels,render_handoff:handoffs};
};
