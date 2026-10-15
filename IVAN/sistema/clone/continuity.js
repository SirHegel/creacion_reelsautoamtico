/* Puentes reales del compositor: el mismo sprite vectorizado entre puertos.
   Sin reloj autónomo; geometría medida una vez y timeline pausada por host. */
window.__cloneBuilt=window.__cloneBuilt||{};
window.__cloneWaiting=window.__cloneWaiting||{};
window.CloneNativeReady=id=>window.__cloneBuilt[id]?Promise.resolve(window.__cloneBuilt[id]):new Promise(resolve=>(window.__cloneWaiting[id]??=[]).push(resolve));
window.CloneRegisterNative=(id,built)=>{window.__cloneBuilt[id]=built;(window.__cloneWaiting[id]||[]).forEach(resolve=>resolve(built));delete window.__cloneWaiting[id];};
window.CloneActorMask=(built,scene)=>{
  const C=built.context,tl=built.renderTl||built.tl,native=CloneTimelineReal(built.tl),ns='http://www.w3.org/2000/svg';
  const operations=scene.render_actor_bridges||[];
  for(const op of operations){
    const isSource=op.source_scene===scene.id,group=C.q(isSource?op.source_group:op.target_group);
    if(!group)throw Error('Puerto real de actor ausente');
    const wrapper=document.createElementNS(ns,'g');wrapper.id=C.id('continuity-'+(isSource?'out':'in'));
    wrapper.setAttribute('opacity',isSource?'1':'0');group.parentNode.insertBefore(wrapper,group);wrapper.appendChild(group);
    if(isSource){
      tl.fromTo(wrapper,{opacity:1},{opacity:0,duration:1/30,ease:'none',immediateRender:false},op.source_local-1/30);
    }else{
      // Un actor compartido no vuelve a aparecer mediante la entrada nativa.
      native.getChildren(true,true,false).filter(t=>t.startTime()<scene.duration*.4&&t.targets().includes(group)).forEach(t=>t.kill());
      gsap.set(group,{opacity:1,x:0,y:0,scale:1,rotation:0});
      tl.fromTo(wrapper,{opacity:0},{opacity:1,duration:1/30,ease:'none',immediateRender:false},op.target_local-1/30);
      if(scene.family==='feedback_bars'){
        const panel=C.q('panel');
        native.getChildren(true,true,false).filter(t=>t.startTime()<scene.duration*.4&&t.targets().includes(panel)).forEach(t=>t.kill());
        native.fromTo(panel,{opacity:0,y:40},{opacity:1,y:0,duration:.26,ease:'power3.out',immediateRender:false},0);
      }
    }
  }
  return operations;
};
window.CloneActorBridge = async (op,surface) => {
  const source=await CloneNativeReady(op.source_scene),target=await CloneNativeReady(op.target_scene);
  const stage=document.getElementById('__clone-film');
  const measure=(built,group,at)=>{
    const clock=CloneTimelineReal(built.renderTl||built.tl),restore=clock.time();clock.seek(at,false);
    const node=built.context.q(group).querySelector('image');if(!node)throw Error('Actor sin sprite original');
    const bounds=node.getBoundingClientRect(),canvas=stage.getBoundingClientRect();
    const pose={x:(bounds.left-canvas.left)*1080/canvas.width,y:(bounds.top-canvas.top)*1920/canvas.height,
      width:bounds.width*1080/canvas.width,height:bounds.height*1920/canvas.height,href:node.getAttribute('href')};
    clock.seek(restore,false);return pose;
  };
  const a=measure(source,op.source_group,op.source_local),b=measure(target,op.target_group,op.target_local);
  if(a.href!==b.href)throw Error('Puente intentó cambiar de recurso gráfico');
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.setAttribute('viewBox','0 0 1080 1920');svg.setAttribute('width','100%');svg.setAttribute('height','100%');
  const group=document.createElementNS(ns,'g');group.id=op.id+'-sprite';
  const image=document.createElementNS(ns,'image');image.setAttribute('href',a.href);
  image.setAttribute('x',0);image.setAttribute('y',0);image.setAttribute('width',a.width);image.setAttribute('height',a.height);image.style.imageRendering='pixelated';
  group.appendChild(image);svg.appendChild(group);surface.appendChild(svg);
  const tl=gsap.timeline({paused:true}),state={p:0},ease=gsap.parseEase('power3.inOut');
  const paint=()=>{
    const t=ease(state.p),u=1-t,control={x:(a.x+b.x)/2+85,y:Math.min(a.y,b.y)-90};
    const x=u*u*a.x+2*u*t*control.x+t*t*b.x,y=u*u*a.y+2*u*t*control.y+t*t*b.y;
    const scale=1+t*(b.width/a.width-1);group.setAttribute('transform',`translate(${x} ${y}) scale(${scale})`);
  };
  tl.fromTo(state,{p:0},{p:1,duration:op.duration,ease:'none',immediateRender:false,onUpdate:paint},0);tl.eventCallback('onUpdate',paint);
  tl.addLabel('shared_actor_depart',0).addLabel('shared_actor_arrive',op.duration);
  const real=CloneTimelineReal(tl);real.seek(op.duration,false);real.seek(0,false);paint();
  window.__timelines[op.id]=tl;
  const receipt={id:op.id,family:'compositor_actor_bridge',start:op.start,duration:op.duration,visible_duration:op.duration,
    labels:CloneTimelineReal(tl).labels,tweens:1,used_assets:[op.asset],local_clock:true,
    continuity:{kind:op.kind,source_scene:op.source_scene,target_scene:op.target_scene,source_port:op.source_port,target_port:op.target_port,
      asset:op.asset,source_pose:(({href,...pose})=>pose)(a),target_pose:(({href,...pose})=>pose)(b),trajectory:'quadratic_curve',execution:'gsap_timeline',execution_verified:false}};
  window.CloneMountReady(receipt);return receipt;
};
