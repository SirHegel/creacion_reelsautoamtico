/* CLONE: teléfonos con interfaz y estados independientes, nunca capturas de relleno.
   Geometría reconstruida de F382–557/F862–947; fuentes aproximadas del sistema.
   El origen/aprobación del componente CANCELLED permanece intacto. */
(() => {
  const Clone=window.Clone;
  const id = (C,n) => C.id(n);
  const group = (C,n,content,attrs='') => `<g id="${id(C,n)}" ${attrs}>${content}</g>`;
  const round = (x,y,w,h,r,fill,more='') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${more}/>`;
  function screenFrame(C,n,content,{x,y,width=300,statusColor='#171719'}) {
    const s=width/300;
    return group(C,n,`<g transform="translate(${x} ${y}) scale(${s})">
      <defs><clipPath id="${id(C,n+'-screen')}">${round(14,14,272,612,52,'white')}</clipPath></defs>
      ${round(0,0,300,640,65,'#101013',`stroke="#343438" stroke-width="3" filter="${C.shadow}"`)}
      <g clip-path="url(#${id(C,n+'-screen')})">${content}</g>
      ${round(90,25,120,35,17,'#000')}${C.text(45,48,'9:41',{size:13,fill:statusColor,id:C.id(n+'-clock')})}
      ${round(238,39,17,8,2,'none',`stroke="${statusColor}" stroke-width="1.2" id="${C.id(n+'-battery')}"`)}
      <path d="M45 625h210" stroke="#000" stroke-width="2" opacity=".2"/>
    </g>`);
  }
  function booking(C,n,{accent='#d77d5d',blueprint=false,appName='Slotly',title='Book a time',month='October 2026',times=['9:00 AM','9:30 AM','10:00 AM','11:30 AM','1:00 PM'],selected=2}) {
    const textColor=blueprint?'#eff5ff':'#18181b';
    const pale=blueprint?'#123ca5':(accent==='#2252d6'?'#e7eefc':'#faeee7');
    const slots=times.slice(0,5).map((time,i)=>group(C,n+'-slot'+i,round(35,263+i*55,230,45,12,i===selected?accent:pale,blueprint?'stroke="#a0c4fa" stroke-width="1.2"':'')+C.text(150,291+i*55,time,{size:16,weight:700,fill:blueprint?'#eff5ff':(i===selected?'white':accent),anchor:'middle',width:190})) ).join('');
    let lines='';for(let x=14;x<290;x+=20)lines+=`<path d="M${x} 14v612" stroke="#7395ce" opacity=".14"/>`;for(let y=14;y<630;y+=20)lines+=`<path d="M14 ${y}h272" stroke="#7395ce" opacity=".14"/>`;
    return round(14,14,272,612,52,blueprint?'#173b91':'#fcfcfb')+(blueprint?lines:'')+
      `<circle cx="58" cy="105" r="22" fill="${accent}"/>`+C.text(89,102,title,{size:22,fill:textColor,width:171})+
      C.text(89,126,appName+' · 30 min',{size:13,weight:400,fill:blueprint?'#a1bbdf':'#8b8786',width:173})+
      C.text(35,175,month,{size:16,fill:textColor,width:189})+C.text(254,175,'‹ ›',{size:19,fill:accent,anchor:'middle'})+
      ['M','T','W','T','F','S','S'].map((v,i)=>C.text(45+i*34,208,v,{size:10,weight:400,fill:blueprint?'#bdd0eb':'#8c8885',anchor:'middle'})).join('')+
      round(133,214,32,38,10,accent)+[12,13,14,15,16,17,18].map((v,i)=>C.text(45+i*34,240,v,{size:13,weight:400,fill:i===3?'white':textColor,anchor:'middle'})).join('')+slots+
      round(35,548,230,46,13,accent,blueprint?'stroke="#a0c4fa" stroke-width="1.2"':'')+C.text(150,576,'Confirm booking',{size:16,fill:'white',anchor:'middle',width:210})+
      (blueprint?C.text(35,153,'HEADER · SCREEN 1/18',{size:9,font:'Mono',fill:'#bad4f7'})+C.text(35,258,'SLOT PICKER · FLOW 2/7',{size:9,font:'Mono',fill:'#bad4f7'})+C.text(35,543,'CTA → CONFIRM',{size:9,font:'Mono',fill:'#bad4f7'}):'');
  }
  function bug(C,n,x,y){return group(C,n,`<circle cx="${x}" cy="${y}" r="24" fill="#fff" fill-opacity=".5" stroke="${C.colors.red}" stroke-width="2"/><path d="M${x-8} ${y-8}l16 16m-16 0l16-16M${x-11} ${y}h22M${x} ${y-11}v22" stroke="${C.colors.red}" stroke-width="4"/><circle cx="${x}" cy="${y}" r="8" fill="${C.colors.red}"/>`);}
  const reference=(a,b)=>[{source:'recursos/B2_CLONE.mp4',entry_s:a,exit_s:b,inventory:'sistema/clone/inventario_escenas.json'}];
  function finalCaption(C,value,fill){return C.text(360,1148,value,{font:'Scholar',weight:400,size:68,fill:fill||C.colors.clay,anchor:'middle',width:630});}
  const origins=new WeakMap();
  function origin(C,n,bottom=false){const node=C.q(n);if(!origins.has(node)){const b=node.getBBox();const fixed={center:`${b.x+b.width/2} ${b.y+b.height/2}`,bottom:`${b.x+b.width/2} ${b.y+b.height}`};origins.set(node,fixed);gsap.set(node,{svgOrigin:fixed.center,smoothOrigin:false});}return origins.get(node)[bottom?'bottom':'center'];}
  function init(tl,C,n,pose,at=0){origin(C,n);const start={...pose};if(at===0&&start.opacity===0)start.opacity=.28;tl.fromTo(C.q(n),start,{opacity:1,x:0,y:0,scale:1,rotation:0,duration:Math.max(.12,Math.min(.30,C.t(.1))),ease:'power3.out'},C.t(at));}
  function labels(tl,C,beats){Object.entries(beats).forEach(([name,time])=>tl.addLabel(name,C.t(time)));}
  function finish(tl,C,n,at=.92){origin(C,n);tl.to(C.q(n),{scale:1.014,duration:C.t(1-at),ease:'power1.inOut'},C.t(at));}

  Clone.register('phone_recon',{
    description:'Agente con lupa inspecciona una interfaz móvil: máscara circular, trayectoria de lectura y resultados progresivos.',
    source:'CLONE F334–381',reference:reference(11.133333,12.733333),durationRange:[1.4,8],
    defaults:{appName:'Acme Scheduling',title:'Book a time',month:'October 2026',screens:18,flows:7,result:'data model ✓',caption:'REVERSE-ENGINEERS THE APP',agent:'agent_research'},
    parameters:{screens:'entero0–999',flows:'entero0–999',result:'texto≤32',appName:'texto≤30',title:'texto≤32',caption:'texto',agent:'sprite original'},
    build(C){const p=C.params;const opts={appName:p.appName,title:p.title,month:p.month};
      const lens=booking(C,'scanui',{...opts,accent:'#2252d6',blueprint:true});
      const guide=group(C,'scan-guide',`<circle cx="150" cy="320" r="139" fill="none" stroke="#de946e" stroke-width="4"/><path d="M150 167v306M-5 320h310" stroke="#dc9980" stroke-width="1.6" opacity=".65"/>`);
      const inside=booking(C,'screen',{...opts,accent:'#2252d6'})+`<defs><clipPath id="${C.id('scan-clip')}"><circle id="${C.id('scan-mask')}" cx="150" cy="320" r="139"/></clipPath></defs><g clip-path="url(#${C.id('scan-clip')})">${lens}</g>`+guide;
      const results=[p.screens+' screens',p.flows+' flows',p.result].map((v,i)=>group(C,'result'+i,round(420,618+i*76,240,58,29,'white',`filter="${C.soft}"`)+C.text(540,655+i*76,v,{font:'Mono',weight:400,size:24,anchor:'middle',width:214}))).join('');
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="${C.colors.paper}"/>${screenFrame(C,'phone',inside,{x:56,y:135,width:322})}${group(C,'agent',C.sprite(p.agent,427,236,240))}${group(C,'role',round(412,160,272,44,22,C.colors.ink)+C.text(548,189,'/ replica-recon',{font:'Mono',size:20,fill:'white',anchor:'middle',width:248}))}${results}${group(C,'caption',finalCaption(C,p.caption))}`);
      const tl=gsap.timeline({paused:true});labels(tl,C,{inspection:0,scan:.14,results:.41,settled:.90});init(tl,C,'phone',{x:-55,y:25,opacity:0});init(tl,C,'agent',{x:60,opacity:0},.035);init(tl,C,'role',{y:8,opacity:0},.10);
      tl.fromTo(C.q('scan-guide'),{y:-154},{y:180,duration:C.t(.6),ease:'power1.inOut'},C.t(.14));
      tl.fromTo(C.q('scan-mask'),{attr:{cy:166}},{attr:{cy:500},duration:C.t(.6),ease:'power1.inOut'},C.t(.14));
      tl.to(C.q('scan-guide'),{y:104,duration:C.t(.12),ease:'power2.out'},C.t(.76));tl.to(C.q('scan-mask'),{attr:{cy:424},duration:C.t(.12),ease:'power2.out'},C.t(.76));
      [0,1,2].forEach(i=>init(tl,C,'result'+i,{x:24,y:5,opacity:0},.41+i*.13));init(tl,C,'caption',{y:18,opacity:0},.12);finish(tl,C,'phone');return tl;
    }
  });

  Clone.register('phone_rebuild',{
    description:'Mockup de reservas: blueprint azul transformado por máscara en interfaz coral, con agente constructor.',
    source:'CLONE F382–415',reference:reference(12.733333,13.866667),durationRange:[1,8],
    defaults:{appName:'Slotly',title:'Book a time',month:'October 2026',accent:'#d77d5d',fromColor:'#2252d6',times:['9:00 AM','9:30 AM','10:00 AM','11:30 AM','1:00 PM'],selected:2,caption:'REBUILDS IT',agent:'agent_build'},
    parameters:{appName:'texto≤30',title:'texto≤32',month:'texto≤30',times:'1–5 textos',selected:'índice0–4',accent:'colorCSS',fromColor:'colorCSS',caption:'texto',agent:'sprite original'},
    build(C){const p=C.params;const opts={appName:p.appName,title:p.title,month:p.month,times:p.times,selected:p.selected};
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="${C.colors.paper}"/>
        <defs><clipPath id="${C.id('build-mask')}"><rect id="${C.id('reveal')}" x="0" y="0" width="300" height="640"/></clipPath></defs>
        ${screenFrame(C,'phone',booking(C,'blue',{...opts,accent:p.fromColor,blueprint:true})+group(C,'built',booking(C,'final',{...opts,accent:p.accent}),`clip-path="url(#${C.id('build-mask')})"`),{x:190,y:112,width:340,statusColor:'white'})}
        ${group(C,'worker',C.sprite(p.agent,465,750,180))}
        ${group(C,'role',round(70,842,232,43,23,C.colors.ink,`filter="${C.soft}"`)+C.text(186,870,'/ replica-build',{font:'Mono',size:19,fill:'white',anchor:'middle',width:211}))}
        ${group(C,'caption',finalCaption(C,p.caption))}`);
      const tl=gsap.timeline({paused:true});labels(tl,C,{blueprint:0,reconstruction:.18,built:.73,settled:.90});
      init(tl,C,'phone',{y:44,scale:.87,opacity:0});init(tl,C,'worker',{x:90,y:30,opacity:0},.06);
      tl.fromTo(C.q('reveal'),{scaleY:0},{scaleY:1,svgOrigin:'0 0',duration:C.t(.55),ease:'power2.inOut'},C.t(.18));
      tl.to(C.q('phone-clock'),{fill:C.colors.ink,duration:C.t(.055)},C.t(.30));tl.to(C.q('phone-battery'),{stroke:C.colors.ink,duration:C.t(.055)},C.t(.30));
      p.times.slice(0,5).forEach((_,i)=>tl.fromTo(C.q('final-slot'+i),{x:14,opacity:.4},{x:0,opacity:1,duration:C.t(.11),ease:'power2.out'},C.t(.26+i*.08)));
      tl.fromTo(C.q('worker'),{rotation:0},{rotation:-5,y:-10,duration:C.t(.16),yoyo:true,repeat:1,ease:'power2.inOut'},C.t(.28));
      init(tl,C,'role',{y:9,opacity:0},.16);init(tl,C,'caption',{y:20,opacity:0},.32);
      finish(tl,C,'phone');return tl;
    }
  });

  Clone.register('phone_qa',{
    description:'Teléfono y agente de QA: marcadores rojos se resuelven al completar pruebas y se construye resultado verde.',
    source:'CLONE F416–460',reference:reference(13.866667,15.366667),durationRange:[1.4,8],
    defaults:{appName:'Slotly',title:'Book a time',month:'October 2026',accent:'#d77d5d',checks:['Guest books a slot','Reschedule flow','Time zones'],result:'0 bugs · all flows pass',caption:'TESTS FOR BUGS',agent:'agent_test'},
    parameters:{checks:'1–3 etiquetas',result:'texto≤55',caption:'texto',agent:'sprite original',appName:'texto≤30',title:'texto≤32',accent:'colorCSS'},
    build(C){const p=C.params,checks=p.checks.slice(0,3);const list=checks.map((text,i)=>group(C,'check'+i,`<circle cx="449" cy="${584+i*64}" r="18" fill="#ddd" id="${C.id('dot'+i)}"/>`+group(C,'tick'+i,`<path d="M440 ${584+i*64}l6 7 13-15" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>`)+C.text(481,591+i*64,text,{size:23,width:205}))).join('');
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="${C.colors.paper}"/>
        ${screenFrame(C,'phone',booking(C,'booking',{...p,times:['9:00 AM','9:30 AM','10:00 AM','11:30 AM','1:00 PM']}),{x:56,y:130,width:322})}
        ${group(C,'bugs',bug(C,'bug0',200,360)+bug(C,'bug1',270,450)+bug(C,'bug2',209,550))}
        ${group(C,'agent',C.sprite(p.agent,425,210,240))}
        ${group(C,'role',round(424,465,232,44,22,C.colors.ink)+C.text(540,494,'/ replica-test',{font:'Mono',size:18,fill:'white',anchor:'middle',width:211}))}
        ${group(C,'list',round(411,548,287,225,24,'#fff',`filter="${C.soft}"`)+list)}
        ${group(C,'result',round(67,748,340,62,31,C.colors.green,`filter="${C.soft}"`)+C.text(237,789,'✓ '+p.result,{size:23,fill:'white',anchor:'middle',width:313}))}
        ${group(C,'caption',finalCaption(C,p.caption))}`);
      const tl=gsap.timeline({paused:true});labels(tl,C,{device:0,bugs:.12,tests:.35,result:.76,settled:.90});init(tl,C,'phone',{x:-55,y:10,opacity:0});init(tl,C,'agent',{x:70,opacity:0},.04);init(tl,C,'role',{y:8,opacity:0},.11);init(tl,C,'list',{y:28,opacity:0},.18);
      checks.forEach((_,i)=>{origin(C,'bug'+i);tl.fromTo(C.q('bug'+i),{opacity:0,scale:.5},{opacity:1,scale:1,duration:C.t(.08),ease:'back.out(1.15)'},C.t(.12+i*.03));tl.set(C.q('tick'+i),{opacity:0},0);const at=C.t(.35+i*.13);tl.to(C.q('dot'+i),{fill:C.colors.green,duration:C.t(.06)},at);tl.to(C.q('tick'+i),{opacity:1,duration:C.t(.05)},at);tl.to(C.q('bug'+i),{opacity:0,scale:.7,duration:C.t(.08)},at);});
      init(tl,C,'result',{y:20,scale:.95,opacity:0},.76);init(tl,C,'caption',{y:18,opacity:0},.15);finish(tl,C,'phone');return tl;
    }
  });

  Clone.register('phone_compare',{
    description:'Dos mockups comparan original y clon; score crece y las pantallas se transforman en pares de aplicaciones.',
    source:'CLONE F461–556',reference:reference(15.366667,18.566667),durationRange:[2.2,10],
    defaults:{originalTitle:'ORIGINAL',cloneTitle:'YOUR CLONE',score:100,metricLabel:'PARITY SCORE',apps:[{name:'Airbnb',asset:'app_airbnb'},{name:'Duolingo',asset:'app_duolingo'},{name:'Notion',asset:'app_notion'},{name:'Spotify',asset:'app_spotify'},{name:'Uber',asset:'app_uber'}],caption:'A PERFECT CLONE',agent:'agent_diff'},
    parameters:{score:'número0–100',metricLabel:'texto≤40',apps:'1–5 pares{name,asset}',originalTitle:'texto≤30',cloneTitle:'texto≤30',caption:'texto',agent:'sprite original'},
    build(C){const p=C.params,apps=p.apps.slice(0,5),score=Math.max(0,Math.min(100,Number(p.score)));const appScreens=(prefix,clone)=>apps.map((app,i)=>group(C,prefix+'app'+i,round(14,14,272,612,52,'#fcfcfb')+(clone?round(98,126,105,37,18,C.colors.clay)+C.text(150,151,'CLONE ✓',{font:'Mono',size:13,fill:'white',anchor:'middle'}):'')+C.image(app.asset,76,238,148,148)+C.text(150,431,(clone?'Your ':'')+app.name,{size:26,anchor:'middle',width:225}))).join('');
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="#000"/>
        ${C.text(201,174,p.originalTitle,{size:17,font:'Mono',weight:400,fill:'#a9a7a5',anchor:'middle',width:241,'letter-spacing':3})}${C.text(520,174,p.cloneTitle,{size:17,font:'Mono',weight:400,fill:'#dfa186',anchor:'middle',width:241,'letter-spacing':3})}
        ${screenFrame(C,'leftPhone',group(C,'leftBooking',booking(C,'lbooking',{accent:'#2252d6',appName:'Acme Scheduling'}))+appScreens('l',false),{x:77,y:206,width:249})}
        ${screenFrame(C,'rightPhone',group(C,'rightBooking',booking(C,'rbooking',{appName:'Slotly'}))+appScreens('r',true),{x:394,y:206,width:249})}
        ${group(C,'equal',`<circle cx="360" cy="453" r="27" fill="#1c1c20" stroke="#343437"/>`+C.text(360,467,'=',{size:40,fill:'white',anchor:'middle'}))}
        ${group(C,'metric',C.text(360,879,'0%',{size:122,font:'Sequel',fill:`url(#${C.id('editorial')})`,anchor:'middle',id:C.id('counter')})+C.text(360,916,p.metricLabel,{font:'Mono',size:18,weight:400,fill:'#aaa7a5',anchor:'middle',width:530,'letter-spacing':3})+round(160,934,400,9,4,'#252525')+round(160,934,400,9,4,C.colors.clay,`id="${C.id('bar')}"`))}
        ${group(C,'agent',C.sprite(p.agent,26,824,118))}${group(C,'caption',finalCaption(C,p.caption,'#faf6f2'))}`);
      const tl=gsap.timeline({paused:true});labels(tl,C,{pair:0,score:.135,apps:.435,settled:.90});init(tl,C,'leftPhone',{x:-210,y:30,rotation:-11,opacity:0});init(tl,C,'rightPhone',{x:210,y:30,rotation:11,opacity:0},.03);init(tl,C,'metric',{y:18,opacity:0},.05);init(tl,C,'equal',{scale:.5,opacity:0},.1);init(tl,C,'agent',{x:-22,opacity:0},.1);init(tl,C,'caption',{y:20,opacity:0},.15);
      tl.set(C.q('bar'),{scaleX:0,svgOrigin:'160 934'},0);tl.to(C.q('bar'),{scaleX:score/100,duration:C.t(.25),ease:'power2.out'},C.t(.135));
      const state={value:0},paint=()=>C.q('counter').textContent=Math.round(state.value)+'%';tl.set(C.q('counter'),{textContent:'0%'},0);
      const stops=[[.135,0],[.198,49],[.260,83],[.323,97],[.386,100]];for(let i=1;i<stops.length;i++)tl.fromTo(state,{value:stops[i-1][1]*score/100},{value:stops[i][1]*score/100,duration:C.t(stops[i][0]-stops[i-1][0]),ease:'none',onUpdate:paint,immediateRender:false},C.t(stops[i-1][0]));
      apps.forEach((_,i)=>{['l','r'].forEach(prefix=>tl.set(C.q(prefix+'app'+i),{opacity:0,y:20},0));const at=.435+i*(.43/Math.max(1,apps.length));['l','r'].forEach(prefix=>{tl.to(C.q(prefix+'app'+i),{opacity:1,y:0,duration:C.t(.04),ease:'power2.out'},C.t(at));if(i)tl.to(C.q(prefix+'app'+(i-1)),{opacity:0,y:-16,duration:C.t(.04)},C.t(at));});});
      tl.to([C.q('leftBooking'),C.q('rightBooking')],{opacity:0,duration:C.t(.055)},C.t(.415));finish(tl,C,'rightPhone');finish(tl,C,'leftPhone');return tl;
    }
  });

  Clone.register('problem_resolution',{
    description:'Problemas detectados se convierten en funciones: etiquetas rojas, switches verdes y resultado dentro del mockup.',
    source:'CLONE F862–947',reference:reference(28.733333,31.6),durationRange:[2.4,10],
    defaults:{appName:'Slotly',appVersion:'Your app · v1.1',appIcon:'app_slotly',features:[{problem:'No SMS reminders',feature:'SMS reminders'},{problem:'Wrong time zones',feature:'Time zone check'},{problem:'Per-seat pricing',feature:'Flat pricing'},{problem:'No CSV export',feature:'CSV export'}],result:'4 problems solved',caption:'SOLVES THOSE PROBLEMS',agent:'agent_entrepreneur'},
    parameters:{features:'1–4 pares{problem,feature}',appName:'texto≤30',appVersion:'texto≤45',appIcon:'asset existente',result:'texto≤50',caption:'texto',agent:'sprite original'},
    build(C){const p=C.params,features=p.features.slice(0,4);let rows='';features.forEach((item,i)=>{const y=225+i*83;rows+=round(30,y,240,70,18,'#fff')+C.text(45,y+40,item.feature,{size:16,width:123})+round(207,y+20,52,32,16,'#dfdfe1',`id="${C.id('track'+i)}"`)+`<circle id="${C.id('thumb'+i)}" cx="224" cy="${y+36}" r="14" fill="white" stroke="#d7d7d7" stroke-width="1"/>`+group(C,'new'+i,round(175,y+28,25,17,4,'#ba5736')+C.text(187.5,y+40,'NEW',{size:8,font:'Mono',fill:'white',anchor:'middle',width:22}));});
      const inner=round(14,14,272,612,52,'#f0f0f4')+C.image(p.appIcon,34,82,45,45)+C.text(93,102,p.appName,{size:23,width:170})+C.text(93,122,p.appVersion,{size:12,weight:400,fill:'#888',width:170})+C.text(34,190,"WHAT’S NEW",{size:12,weight:400,font:'Mono',fill:'#555','letter-spacing':1})+rows;
      const problems=features.map((item,i)=>group(C,'problem'+i,round(414,154+i*79,278,58,29,'white',`stroke="#c75754" stroke-width="1.4" filter="${C.soft}"`)+C.text(553,191+i*79,item.problem,{size:23,fill:'#a6282d',anchor:'middle',width:248}))).join('');
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="${C.colors.paper}"/>${screenFrame(C,'phone',inner,{x:61,y:126,width:325})}${problems}${group(C,'agent',C.sprite(p.agent,449,553,218))}${group(C,'result',round(65,748,342,65,32,C.colors.green,`filter="${C.soft}"`)+C.text(236,791,'✓ '+p.result,{size:26,fill:'white',anchor:'middle',width:315}))}${group(C,'caption',finalCaption(C,p.caption))}`);
      const tl=gsap.timeline({paused:true});labels(tl,C,{device:0,problems:.10,solutions:.29,result:.78,settled:.90});init(tl,C,'phone',{y:36,scale:.9,opacity:0});init(tl,C,'agent',{x:60,y:20,opacity:0},.05);init(tl,C,'caption',{y:20,opacity:0},.12);
      features.forEach((_,i)=>{init(tl,C,'problem'+i,{x:40,opacity:0},.10+i*.035);tl.set(C.q('new'+i),{opacity:0},0);const at=.29+i*(.36/Math.max(1,features.length-1));tl.to(C.q('problem'+i),{x:-110,opacity:0,duration:C.t(.08),ease:'power2.in'},C.t(at));tl.to(C.q('track'+i),{fill:C.colors.green,duration:C.t(.065)},C.t(at+.035));tl.to(C.q('thumb'+i),{x:18,duration:C.t(.075),ease:'power2.out'},C.t(at+.035));tl.to(C.q('new'+i),{opacity:1,duration:C.t(.05)},C.t(at+.05));});
      init(tl,C,'result',{y:20,scale:.95,opacity:0},.78);finish(tl,C,'phone');return tl;
    }
  });
  Clone.primitives={...(Clone.primitives||{}),phoneFrame:screenFrame,bookingScreen:booking};
})();
