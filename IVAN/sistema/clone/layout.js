/* Layout del compositor en píxeles de salida1080×1920, geometría original720×1280.
   Las capas nuevas contienen los nodos originales: sus tweens siguen aislados. */
window.CloneLayout = (built, scene) => {
  const p=scene.layout;if(!p)return null;
  const C=built.context,svg=C.root.querySelector('svg'),ns='http://www.w3.org/2000/svg';
  const unit=2/3,axis=(p.anchor_x??.5)*720,focus=(p.anchor_y??.5)*1280;
  const margin=(p.margin_px??96)*unit,width=Math.min(576,720-2*margin),gap=(p.gap_px??96)*unit;
  const placed=[];
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  function put(name,nodes,source,target){
    const group=document.createElementNS(ns,'g');group.id=C.id('layout-'+name);
    const first=nodes[0];first.parentNode.insertBefore(group,first);nodes.forEach(n=>group.appendChild(n));
    const scale=target[2]/source[2],tx=target[0]-source[0]*scale,ty=target[1]-source[1]*scale;
    const matrix=[scale,0,0,scale,tx,ty];group.setAttribute('transform','matrix('+matrix.join(' ')+')');
    placed.push({name,source,target,matrix});return group;
  }
  function textSize(node,size,maxWidth){
    node.setAttribute('font-size',size);
    const canvas=document.createElement('canvas').getContext('2d');
    canvas.font=(node.getAttribute('font-weight')||'400')+' '+size+'px '+node.getAttribute('font-family');
    if(canvas.measureText(node.textContent).width>maxWidth)throw Error('Texto de composición no cabe en móvil: '+node.textContent);
  }
  if(p.profile==='compact_stack'){
    const n=C.params.reviews.length;
    C.params.reviews.forEach((row,i)=>{
      const node=C.q('review'+i),texts=node.querySelectorAll('text'),rects=node.querySelectorAll('rect');
      rects[0].setAttribute('height',92);
      const body=texts[0],size=(p.body_px??54)*unit;
      body.setAttribute('font-size',size);
      const measure=document.createElement('canvas').getContext('2d');measure.font='400 '+size+'px InterUI';
      const words=body.textContent.split(/\s+/),lines=[''];
      for(const word of words){const i=lines.length-1,next=lines[i]?lines[i]+' '+word:word;
        if(lines[i]&&measure.measureText(next).width>(i===0?300:476)){lines.push(word);}else lines[i]=next;}
      if(lines.length>2||lines.some((s,i)=>measure.measureText(s).width>(i===0?300:476)))throw Error('Observación demasiado larga para tarjeta móvil');
      body.replaceChildren();lines.forEach((line,j)=>{const span=document.createElementNS(ns,'tspan');span.setAttribute('x',143);span.setAttribute('y',181+i*103+j*35);span.textContent=line;body.appendChild(span);});
      // La clasificación usa las etiquetas existentes; el aviso ficticio se
      // conserva aparte. No reinterpreta otros tags ni añade métricas.
      const cat=C.params.categories[i];
      if(cat&&row.tag.toLowerCase().startsWith(cat.label.toLowerCase()+' ·')){
        texts[1].textContent=cat.label;texts[1].setAttribute('x',553);texts[1].setAttribute('y',167+i*103);
        textSize(texts[1],(p.secondary_px??36)*unit,147);rects[1].setAttribute('height',30);
      }
    });
    C.params.categories.forEach((_,i)=>{const texts=C.q('row'+i).querySelectorAll('text');textSize(texts[0],(p.body_px??54)*unit,205);C.q('count'+i).setAttribute('font-size',44);});
    const header=C.q('panel').querySelector('text');header.setAttribute('letter-spacing',1);textSize(header,24,470);
    const captionGroups=[...svg.querySelectorAll('g[id]')].filter(n=>/^caption\d+$/.test(n.id.slice(C.prefix.length+1)));
    const box=C.q('caption0').getBBox();
    const evidence=[78,139,564,Math.min(n,4)*103-11],panel=[72,561,576,325],caption=[box.x,box.y,box.width,box.height];
    const evidenceScale=width/evidence[2],heights=[evidence[3]*evidenceScale,panel[3]*width/panel[2],caption[3]];
    const total=heights.reduce((a,b)=>a+b,0)+2*gap,top=clamp(focus-total/2,80,1160-total);
    const x=clamp(axis-width/2,margin,720-margin-width);
    const viewport=C.q('deck').parentNode;
    put('evidence',[viewport],evidence,[x,top,width,heights[0]]);
    const panelTop=top+heights[0]+gap;
    put('dashboard',[C.q('panel'),C.q('agent')],panel,[x,panelTop,width,heights[1]]);
    const captionTop=panelTop+heights[1]+gap;
    // Tipografía centrada a tamaño propio, sin deformarla al ancho del panel.
    put('editorial',captionGroups,caption,[axis-caption[2]/2,captionTop,caption[2],caption[3]]);
  }else if(p.profile==='centered_actor'){
    // Mueve el padre geométrico del personaje, manteniendo su trayectoria local.
    const node=C.q('hero').parentNode;put('actor',[node],[250,441,300,180],[axis-150,441,300,180]);
    textSize(C.q('command').querySelector('text'),24,306);
  }else if(p.profile==='centered_primary'){
    const node=C.q(scene.family==='phone_rebuild'?'phone':'window');
    if(!node)throw Error('Puerto primario de layout no disponible');
    const box=node.getBBox(),targetWidth=Math.min(box.width,720-2*margin),targetX=clamp(axis-targetWidth/2,margin,720-margin-targetWidth);
    put('primary',[node],[box.x,box.y,box.width,box.height],[targetX,box.y,targetWidth,box.height*targetWidth/box.width]);
  }else throw Error('Perfil de composición no disponible');
  built.layout={canvas:[1080,1920],native_canvas:[720,1280],axis_x:axis*1.5,thirds:{x:[360,720],y:[640,1280]},focus_y:focus*1.5,
    guides_are_preferences:true,gap_px:gap*1.5,placements:placed,profile:p.profile};
  [...svg.querySelectorAll('text')].filter(n=>n.textContent==='EJEMPLO CONCEPTUAL').forEach(n=>n.setAttribute('font-size',24));
  return built.layout;
};

window.CloneClosing = (built,scene) => {
  const p=scene.closing;if(!p)return null;
  const C=built.context,native=CloneTimelineReal(built.renderTl||built.tl),d=scene.duration;
  const finish=(.32+(C.params.categories.length-1)*.13+.19)*d;
  const state={time:0},tl=gsap.timeline({paused:true}),paint=()=>native.seek(state.time,false);
  tl.fromTo(state,{time:0},{time:finish,duration:p.at,ease:'none',immediateRender:false,onUpdate:paint},0);
  tl.eventCallback('onUpdate',paint);
  const svg=C.root.querySelector('svg'),editorial=C.q('layout-editorial'),ns='http://www.w3.org/2000/svg';
  const layer=document.createElementNS(ns,'g');layer.id=C.id('closing-editorial-exit');editorial.parentNode.insertBefore(layer,editorial);layer.appendChild(editorial);
  const block=document.createElementNS(ns,'g');block.id=C.id('closing-conclusion');block.setAttribute('opacity','0');
  const headline=document.createElementNS(ns,'text');
  Object.entries({x:360,y:1004,'text-anchor':'middle','font-family':'Scholar','font-size':58,'font-weight':400,fill:C.colors.clay}).forEach(([k,v])=>headline.setAttribute(k,v));
  headline.textContent=p.headline;
  const subline=document.createElementNS(ns,'text');
  Object.entries({x:360,y:1075,'text-anchor':'middle','font-family':'InterUI','font-size':30,'font-weight':700,fill:C.colors.ink}).forEach(([k,v])=>subline.setAttribute(k,v));
  subline.textContent='No mide calidad ni declara ganador';
  const underline=document.createElementNS(ns,'path');underline.setAttribute('d','M145 1099H575');underline.setAttribute('stroke',C.colors.clay);underline.setAttribute('stroke-width','3');
  block.append(headline,subline,underline);svg.appendChild(block);
  tl.fromTo(layer,{opacity:1,y:0},{opacity:0,y:-18,duration:.16,ease:'power2.in',immediateRender:false},p.at);
  tl.fromTo(block,{opacity:0,y:20},{opacity:1,y:0,duration:.3,ease:'power3.out',immediateRender:false},p.at+.18);
  const len=underline.getTotalLength();underline.style.strokeDasharray=len;underline.style.strokeDashoffset=len;
  tl.fromTo(underline,{strokeDashoffset:len},{strokeDashoffset:0,duration:.4,ease:'power2.out',immediateRender:false},p.at+.35);
  // Los tres resultados viajan juntos hacia la conclusión, conservando2/1/3.
  const dashboard=C.q('layout-dashboard'),evidence=C.q('layout-evidence');
  const matrix=node=>node.getAttribute('transform').match(/[-+\d.e]+/g).map(Number);
  for(const [node,name,delta] of [[dashboard,'dashboard',24],[evidence,'evidence',24]]){
    const values=matrix(node),target=values.slice();target[5]+=delta;
    tl.fromTo(node,{attr:{transform:'matrix('+values.join(' ')+')'}},{attr:{transform:'matrix('+target.join(' ')+')'},duration:.4,ease:'power3.inOut',immediateRender:false},p.at+.18);
  }
  tl.addLabel('coverage_complete',p.at).addLabel('conclusion_reveal',p.at+.18).addLabel('conclusion_settled',p.at+.75);
  built.renderTl=tl;built.closing={kind:p.kind,at:p.at,classification_finished_at:p.at,source_finish:finish,
    final_values:C.params.categories.map(c=>c.value),values_unchanged:true,headline:p.headline,subline:subline.textContent};
  return built.closing;
};
