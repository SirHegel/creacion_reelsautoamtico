/* Avatares originales de CLONE, recuperados en assets.json.
   Cada familia construye estados y movimiento finito sobre una timeline GSAP.
   Las variantes son composiciones nuevas: no se atribuyen como copia exacta. */
(() => {
  const allRoles=['recon','architect','design','build','backend','test','diff','entrepreneur','brand','launch','deploy'];
  function rolesOf(params){
    const value=params.roles??allRoles;
    if(!Array.isArray(value)||value.length<1||value.length>11)throw Error('roles debe contener entre 1 y 11 agentes');
    const values=value.map((v,i)=>typeof v==='string'?{role:v,label:'/'+v}:{...v});
    for(const v of values){
      if(!v||!allRoles.includes(v.role))throw Error('Rol original de CLONE desconocido: '+v?.role);
      v.label=String(v.label??'/'+v.role);v.asset='agent_'+v.role;
    }
    return values.slice(0,Math.max(1,Math.min(11,Number(params.count)||values.length)));
  }
  function avatar(C,name,role,x,y,width,label=true){
    const item=typeof role==='string'?{role,label:'/'+role,asset:'agent_'+role}:role;
    const marquee=name.startsWith('march-');
    const pillWidth=Math.min(160,Math.max(66,item.label.length*10.8+24));
    return `<g transform="translate(${x} ${y})"><g id="${C.id(name)}"${marquee?' data-layout-allow-overflow="true"':''}>
      ${C.sprite(item.asset,-width/2,-100,width)}
      ${label?`<rect id="${C.id(name+'-pill')}" x="${-pillWidth/2}" y="40" width="${pillWidth}" height="36" rx="18" fill="#fff" filter="${C.soft}"/>${C.text(0,65,item.label,{font:'JetBrains',weight:400,size:18,anchor:'middle',width:pillWidth-24,...(marquee?{'data-layout-allow-overflow':'true'}:{})})}`:''}
    </g></g>`;
  }
  function setup(C,content){C.root.innerHTML=C.svg(content);return gsap.timeline({paused:true});}
  function tween(tl,target,from,to,at){
    // Estado real desde t=0, también cuando la entrada empieza más tarde.
    // Sin este set aparece el DOM final antes del tween y después parpadea.
    // El origen SVG se resuelve una vez sobre la geometría en reposo. Repetir
    // svgOrigin después del desplazamiento inicial altera la compensación XY.
    const {svgOrigin,transformOrigin,...pose}=from;
    if(svgOrigin!==undefined)tl.set(target,{svgOrigin,smoothOrigin:false},0);
    if(transformOrigin!==undefined)tl.set(target,{transformOrigin},0);
    tl.set(target,pose,0);
    tl.fromTo(target,pose,{...to,immediateRender:false},at);
  }

  Clone.register('pixel_agents',{
    description:'Equipo de sprites originales por rol; activación de funciones y reorganización coordinada hacia un resultado.',
    reference:[{source:'recursos/B2_CLONE.mp4',entry_s:7.933333,exit_s:11.133333,inventory:'sistema/clone/inventario_escenas.json'}],
    durationRange:[2.3,12],
    defaults:{roles:allRoles,count:11,caption:'CADA AGENTE, UNA FUNCIÓN',result:'EQUIPO LISTO',reorganize:true},
    parameters:{roles:'roles originales/labels propios',count:'1–11',result:'resultado suministrado',reorganize:'true permite resolución visual'},
    source:{path:'recursos/B2_CLONE.mp4',start:7.933333,end:11.133333},
    build(C){
      const roles=rolesOf(C.params),n=roles.length;
      const rows=n<=4?1:n<=8?2:3,rowCounts=rows===1?[n]:rows===2?[Math.ceil(n/2),Math.floor(n/2)]:[4,4,n-8];
      const spots=[];let k=0;
      rowCounts.forEach((count,row)=>{for(let col=0;col<count;col++)spots.push({x:360+(col-(count-1)/2)*158,y:rows===1?580:rows===2?400+row*290:260+row*275,i:k++});});
      const ghost=C.text(360,870,n,{font:'Sequel',size:740,fill:C.colors.clay,anchor:'middle',opacity:.16});
      let html=`<rect width="720" height="1280" fill="${C.colors.paper}"/><g id="${C.id('camera')}"><g id="${C.id('ghost')}">${ghost}</g>`;
      spots.forEach((p,i)=>{html+=avatar(C,'role-'+i,roles[i],p.x,p.y,104);});
      html+=`</g><g id="${C.id('progress')}"><rect x="158" y="952" width="404" height="44" rx="22" fill="#fff" filter="${C.soft}"/>${C.text(360,982,'FUNCIONES EN ACCIÓN',{font:'JetBrains',weight:400,size:18,anchor:'middle'})}<rect id="${C.id('rail')}" x="180" y="1010" width="360" height="5" rx="2.5" fill="${C.colors.clay}"/></g>`;
      html+=`<g id="${C.id('result')}"><rect x="95" y="468" width="530" height="205" rx="30" fill="#fff" filter="${C.shadow}"/>${C.text(360,530,C.params.result,{font:'Sequel',size:42,anchor:'middle',width:480})}${C.text(360,592,n+' ROLES COORDINADOS',{font:'JetBrains',weight:400,size:22,anchor:'middle',width:455})}<g id="${C.id('check')}"><circle cx="360" cy="642" r="24" fill="${C.colors.green}"/><path d="M348 642l8 8 16-17" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></g></g>${C.caption()}`;
      const tl=setup(C,html),d=C.duration;
      tl.addLabel('entry',0).addLabel('action',d*.26).addLabel('reaction',d*.52).addLabel('result',d*.76).addLabel('exit',d*.92);
      tl.set(C.q('result'),{opacity:0},0);tl.set(C.q('check'),{scale:0,svgOrigin:'360 642'},0);
      tween(tl,C.q('ghost'),{scale:.92,opacity:.05,svgOrigin:'360 600'},{scale:1,opacity:1,duration:Math.min(.42,d*.15),ease:'sine.out'},.03);
      spots.forEach((p,i)=>{
        const entry=i*.025;
        tween(tl,C.q('role-'+i),{x:(i%2?1:-1)*135,y:100,scale:.78,opacity:0,svgOrigin:p.x+' '+p.y},{x:0,y:0,scale:1,opacity:1,duration:Math.min(.32,d*.12),ease:i%3===0?'expo.out':i%3===1?'power3.out':'back.out(1.1)'},.09+entry);
        const at=d*.27+(i/n)*d*.33;
        tl.to(C.q('role-'+i),{y:-18,rotation:i%2?-3:3,duration:Math.min(.16,d*.055),ease:'power2.out'},at);
        tl.to(C.q('role-'+i+'-pill'),{attr:{fill:C.colors.clay},duration:.10,ease:'none'},at);
        tl.to(C.q('role-'+i),{y:0,rotation:0,duration:Math.min(.22,d*.07),ease:'sine.inOut'},at+Math.min(.16,d*.055));
        tl.to(C.q('role-'+i+'-pill'),{attr:{fill:'#fff'},duration:.12,ease:'sine.inOut'},at+Math.min(.25,d*.09));
      });
      tween(tl,C.q('progress'),{y:36,opacity:0},{y:0,opacity:1,duration:.25,ease:'power3.out'},d*.22);
      tween(tl,C.q('rail'),{scaleX:0,svgOrigin:'180 1010'},{scaleX:1,duration:d*.4,ease:'none'},d*.25);
      if(C.params.reorganize!==false){
        const resolve=d*.69;
        spots.forEach((p,i)=>{tl.to(C.q('role-'+i),{x:360-p.x,y:490-p.y,scale:.34,opacity:0,duration:Math.min(.40,d*.14),ease:'power3.inOut'},resolve+i*.013);});
        tl.to(C.q('ghost'),{opacity:0,scale:1.06,duration:.26,ease:'power2.in'},resolve);
        tl.to(C.q('progress'),{y:80,opacity:0,duration:.22,ease:'power2.in'},resolve);
        tween(tl,C.q('result'),{scale:.88,y:42,opacity:0,svgOrigin:'360 570'},{scale:1,y:0,opacity:1,duration:.3,ease:'power3.out'},d*.78);
        tl.to(C.q('check'),{scale:1,duration:.18,ease:'back.out(1.2)'},d*.85);
        tl.to(C.q('result'),{scale:1.025,duration:Math.min(.15,d*.02),ease:'power2.out'},d*.90);
        tl.to(C.q('result'),{scale:1,y:-26,opacity:0,duration:Math.min(.23,d*.07),ease:'power2.in'},d*.93);
      }else{
        tl.to(C.q('camera'),{x:-52,scale:1.07,svgOrigin:'360 550',duration:d*.22,ease:'sine.inOut'},d*.68);
        tl.to(C.q('camera'),{y:-70,opacity:0,duration:d*.08,ease:'power2.in'},d*.91);
        tl.to(C.q('progress'),{opacity:0,duration:d*.08,ease:'power2.in'},d*.91);
      }
      return tl;
    }
  });

  Clone.register('spotlight_agent',{
    description:'Un agente original entra en un foco oscuro, actúa, revela su propósito y entrega la acción a la siguiente composición.',
    reference:[{source:'recursos/B2_CLONE.mp4',entry_s:20.333333,exit_s:21.6,inventory:'sistema/clone/inventario_escenas.json'}],
    durationRange:[1.2,8],
    defaults:{role:'entrepreneur',title:'/ replica-entrepreneur',goal:'',caption:'THE ENTREPRENEUR'},
    parameters:{role:'uno de los11roles',title:'título',goal:'objetivo real',caption:'énfasis editorial'},
    source:{path:'recursos/B2_CLONE.mp4',start:20.333333,end:21.6},
    build(C){
      const role=rolesOf({roles:[C.params.role]})[0],d=C.duration;
      const localDefs=`<defs><radialGradient id="${C.id('pool-grad')}"><stop stop-color="#b8a493" stop-opacity=".70"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient><linearGradient id="${C.id('cone-grad')}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#d7c6b3" stop-opacity=".45"/><stop offset="1" stop-color="#7e6248" stop-opacity=".15"/></linearGradient></defs>`;
      let html=`${localDefs}<rect width="720" height="1280" fill="#000"/><g id="${C.id('scene')}"><g id="${C.id('light')}"><path d="M306 -30L116 786Q360 825 604 786L414 -30Z" fill="url(#${C.id('cone-grad')})"/><ellipse cx="360" cy="772" rx="220" ry="52" fill="url(#${C.id('pool-grad')})"/></g>${avatar(C,'hero',role,400,541,300,false)}`;
      for(let i=0;i<7;i++)html+=`<rect id="${C.id('spark-'+i)}" x="${279+i*27}" y="${461+(i%3)*24}" width="7" height="7" fill="${i%2?'#eab431':C.colors.clay}"/>`;
      html+=`<g id="${C.id('command')}"><rect x="191" y="847" width="338" height="49" rx="24" fill="#19191b" stroke="#353236" stroke-width="1"/>${C.text(360,879,C.params.title,{font:'JetBrains',size:20,fill:'#e9e5e3',weight:400,anchor:'middle',width:306})}</g>`;
      if(C.params.goal)html+=`<g id="${C.id('goal')}">${C.text(360,976,C.params.goal,{font:'Sequel',size:32,fill:'#fff',anchor:'middle',width:600})}<path id="${C.id('goal-underline')}" d="M230 999H490" stroke="${C.colors.clay}" stroke-width="4" stroke-linecap="round"/></g>`;
      html+=`</g>${C.caption()}`;
      const tl=setup(C,html);
      tl.addLabel('entry',0).addLabel('action',d*.3).addLabel('reaction',d*.45).addLabel('result',d*.65).addLabel('exit',d*.91);
      tween(tl,C.q('light'),{scaleY:.5,opacity:0,svgOrigin:'360 0'},{scaleY:1,opacity:1,duration:d*.23,ease:'sine.out'},.02);
      tween(tl,C.q('hero'),{y:75,scale:.74,opacity:0,svgOrigin:'400 541'},{y:0,scale:1,opacity:1,duration:d*.24,ease:'power3.out'},d*.07);
      tl.to(C.q('hero'),{y:-14,rotation:-3,duration:d*.12,ease:'power2.out'},d*.32);
      tl.to(C.q('hero'),{y:0,rotation:0,duration:d*.14,ease:'sine.inOut'},d*.44);
      for(let i=0;i<7;i++){
        tween(tl,C.q('spark-'+i),{opacity:0,x:360-(279+i*27),y:76},{opacity:1,x:0,y:-28,duration:d*.19,ease:i%2?'power3.out':'sine.out'},d*.31+i*.018);
        tl.to(C.q('spark-'+i),{y:-55,opacity:0,duration:d*.12,ease:'power2.in'},d*.57+i*.018);
      }
      tween(tl,C.q('command'),{y:26,scaleX:.8,opacity:0,svgOrigin:'360 872'},{y:0,scaleX:1,opacity:1,duration:d*.18,ease:'expo.out'},d*.38);
      if(C.params.goal){
        tween(tl,C.q('goal'),{y:24,opacity:0},{y:0,opacity:1,duration:d*.16,ease:'power3.out'},d*.60);
        tween(tl,C.q('goal-underline'),{scaleX:0,svgOrigin:'230 999'},{scaleX:1,duration:d*.16,ease:'sine.inOut'},d*.65);
      }
      tl.to(C.q('scene'),{scale:1.075,svgOrigin:'360 640',duration:d*.15,ease:'power2.inOut'},d*.72);
      tl.to(C.q('scene'),{x:-100,y:-38,opacity:0,duration:d*.09,ease:'power3.in'},d*.91);
      return tl;
    }
  });

  Clone.register('agent_marquee',{
    description:'Desfile finito de agentes originales con movimiento interno, selección de rol y CTA contextual opcional.',
    reference:[{source:'recursos/B2_CLONE.mp4',entry_s:38.966667,exit_s:42.3,inventory:'sistema/clone/inventario_escenas.json'}],
    durationRange:[2,12],
    defaults:{roles:allRoles,title:'UN EQUIPO ESPECIALIZADO',caption:'CADA ROL APORTA',direction:'left',cta:'',highlight:'build'},
    parameters:{roles:'lista de roles originales',direction:'left/right',title:'mensaje',cta:'CTA suministrada, opcional',highlight:'rol relevante'},
    source:{path:'recursos/B2_CLONE.mp4',start:38.966667,end:42.3},
    build(C){
      const roles=rolesOf(C.params),d=C.duration,n=roles.length,spacing=155,total=n*spacing;
      const dir=C.params.direction==='right'?1:-1;
      const found=roles.findIndex(r=>r.role===C.params.highlight),heroIndex=found<0?0:found;
      let html=`<defs><clipPath id="${C.id('viewport')}"><rect x="0" y="326" width="720" height="344"/></clipPath></defs><rect width="720" height="1280" fill="${C.colors.paper}"/>${C.text(360,244,C.params.title,{font:'Sequel',size:42,anchor:'middle',width:630})}<path d="M46 665H674" stroke="#dcdce1" stroke-width="2"/><g id="${C.id('marquee-viewport')}" clip-path="url(#${C.id('viewport')})" data-layout-allow-overflow="true"><g id="${C.id('procession')}" data-layout-allow-overflow="true">`;
      roles.forEach((r,i)=>{html+=avatar(C,'march-'+i,r,i*spacing,507,113,true);});
      html+=`</g></g><g id="${C.id('focus')}"><rect x="171" y="728" width="378" height="196" rx="28" fill="#fff" filter="${C.shadow}"/>${avatar(C,'focus-agent',roles[heroIndex],360,826,114,false)}${C.text(360,906,roles[heroIndex].label,{font:'JetBrains',weight:400,size:22,anchor:'middle',width:342})}</g>`;
      if(C.params.cta)html+=`<g id="${C.id('cta')}"><rect x="92" y="1001" width="536" height="62" rx="24" fill="${C.colors.dark}"/>${C.text(360,1041,C.params.cta,{font:'Sequel',size:28,fill:'#fff',anchor:'middle',width:486})}</g>`;
      html+=C.caption();
      const tl=setup(C,html),startX=dir===-1?850:-total-150,endX=dir===-1?-total-150:850;
      tl.addLabel('entry',0).addLabel('action',d*.15).addLabel('reaction',d*.48).addLabel('result',d*.7).addLabel('exit',d*.92);
      tween(tl,C.q('procession'),{x:startX},{x:endX,duration:d*.86,ease:'none'},d*.05);
      roles.forEach((r,i)=>{
        const at=d*.13+(i/n)*d*.48;
        tl.to(C.q('march-'+i),{y:-12,rotation:i%2?-2:2,duration:.13,ease:'sine.out'},at);
        tl.to(C.q('march-'+i),{y:0,rotation:0,duration:.18,ease:'sine.inOut'},at+.13);
      });
      tween(tl,C.q('focus'),{scale:.82,y:52,opacity:0,svgOrigin:'360 825'},{scale:1,y:0,opacity:1,duration:Math.min(.36,d*.15),ease:'power3.out'},d*.49);
      tl.to(C.q('focus-agent'),{y:-16,duration:.16,ease:'power2.out'},d*.66);
      tl.to(C.q('focus-agent'),{y:0,duration:.2,ease:'sine.inOut'},d*.66+.16);
      if(C.params.cta)tween(tl,C.q('cta'),{scaleX:.74,y:28,opacity:0,svgOrigin:'360 1032'},{scaleX:1,y:0,opacity:1,duration:Math.min(.26,d*.12),ease:'expo.out'},d*.73);
      tl.to(C.q('focus'),{y:-48,scale:1.035,opacity:0,duration:d*.08,ease:'power3.in'},d*.92);
      if(C.params.cta)tl.to(C.q('cta'),{y:-40,opacity:0,duration:d*.08,ease:'power2.in'},d*.92);
      return tl;
    }
  });
})();
