/* Tarjetas de evidencia/producto CLONE, reconstruidas por estados gráficos.
   Datos predeterminados solo describen el render de referencia, no resultados nuevos. */
(() => {
  const Clone=window.Clone;
  const group=(C,n,content,attrs='')=>`<g id="${C.id(n)}" ${attrs}>${content}</g>`;
  const rect=(x,y,w,h,r,fill,more='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" ${more}/>`;
  const reference=(a,b)=>[{source:'recursos/B2_CLONE.mp4',entry_s:a,exit_s:b,inventory:'sistema/clone/inventario_escenas.json'}];
  const origins=new WeakMap();
  const origin=(C,n,bottom=false)=>{const node=C.q(n);if(!origins.has(node)){const b=node.getBBox();const fixed={center:`${b.x+b.width/2} ${b.y+b.height/2}`,bottom:`${b.x+b.width/2} ${b.y+b.height}`};origins.set(node,fixed);gsap.set(node,{svgOrigin:fixed.center,smoothOrigin:false});}return origins.get(node)[bottom?'bottom':'center'];};
  const enter=(tl,C,n,pose,at=0,length=.1)=>{origin(C,n);return tl.fromTo(C.q(n),{...pose,opacity:at===0&&pose.opacity===0?.28:pose.opacity},{x:0,y:0,scale:1,rotation:0,opacity:1,duration:Math.max(.12,Math.min(.30,C.t(length))),ease:'power3.out'},C.t(at));};
  function paragraph(C,text,x,y,width,size=35,maxLines=5){
    const canvas=document.createElement('canvas'),m=canvas.getContext('2d');let lines=[];
    for(let fit=size;fit>=22;fit-=1){m.font=`400 ${fit}px InterUI`;lines=[];let line='';for(const word of String(text).split(/\s+/)){const next=line?line+' '+word:word;if(m.measureText(next).width>width&&line){lines.push(line);line=word;}else line=next;}if(line)lines.push(line);if(lines.length<=maxLines){return lines.map((v,i)=>C.text(x,y+i*fit*1.55,v,{size:fit,weight:400,width})).join('');}}
    throw Error('Texto About excesivo: reducir contenido o dividir la escena');
  }
  function forkIcon(x,y){return `<g transform="translate(${x} ${y})" fill="none" stroke="#667078" stroke-width="4" stroke-linecap="round"><circle cx="0" cy="0" r="4"/><circle cx="18" cy="0" r="4"/><circle cx="9" cy="25" r="4"/><path d="M0 5v6q0 7 9 7t9-7V5M9 18v3"/></g>`;}
  Clone.register('github_cards',{
    description:'Repositorio GitHub destacado por contorno trazado; el mismo panel cambia a About y recibe badge de licencia/precio.',
    source:'CLONE F99–177',reference:reference(3.3,5.933333),durationRange:[2.2,10],
    defaults:{repository:'replica-skill',owner:'Jakeschincariol',visibility:'Public',forks:149,stars:'1.1k',about:'Eleven free Claude skills that clone any app: reverse-engineer it, rebuild it, test it for bugs, then fix what its users hate. Free, MIT.',badge:'100% FREE · MIT',caption:'COMPLETELY FREE',avatar:'repo_avatar'},
    parameters:{repository:'texto≤45',owner:'texto≤45',visibility:'texto≤18',forks:'dato explícito',stars:'dato explícito',about:'texto≤350',badge:'texto≤35',caption:'texto',avatar:'asset existente'},
    build(C){const p=C.params;
      const stats=rect(67,492,246,65,13,'#f3f6f7','stroke="#d0d4d7" stroke-width="2"')+forkIcon(97,513)+C.text(135,536,'Fork',{size:29})+rect(208,503,85,42,23,'#e9eef0')+C.text(250,535,p.forks,{size:29,anchor:'middle',width:70})+
        rect(335,492,301,65,13,'#f3f6f7','stroke="#d0d4d7" stroke-width="2"')+`<path d="M373 504l7 13 15 2-11 10 3 15-14-7-14 7 3-15-11-10 15-2z" fill="none" stroke="#667078" stroke-width="3"/>`+C.text(405,536,'Star',{size:29})+rect(497,503,111,42,23,'#e9eef0')+C.text(552,535,p.stars,{size:29,anchor:'middle',width:95});
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="${C.colors.paper}"/>
        <defs><clipPath id="${C.id('about-clip')}"><rect id="${C.id('about-mask')}" x="35" y="320" width="650" height="540"/></clipPath></defs>
        ${group(C,'panel',rect(34,220,652,655,31,'white',`filter="${C.shadow}"`)+C.image('app_github',60,250,31,31)+C.text(104,274,'github.com/'+p.owner,{font:'Mono',size:21,weight:400,fill:'#626064',width:548})+
          group(C,'repo',C.image(p.avatar,74,348,66,66)+C.text(165,400,p.repository,{size:54,width:327})+rect(502,348,151,55,28,'white','stroke="#e0e0e0" stroke-width="3"')+C.text(577,386,p.visibility,{size:29,fill:'#696d70',anchor:'middle',width:125})+stats)+
          group(C,'outline',rect(153,334,340,86,13,'none',`stroke="${C.colors.clay}" stroke-width="3"`))+
          group(C,'about',C.text(69,363,'About',{size:41})+paragraph(C,p.about,69,448,577),`clip-path="url(#${C.id('about-clip')})"`))}
        ${group(C,'badge',`<g transform="rotate(-6 534 870)">${rect(411,841,246,51,25,C.colors.clay,`filter="${C.soft}"`)}${C.text(534,875,p.badge,{size:22,fill:'white',anchor:'middle',width:219})}</g>`)}
        ${group(C,'caption',C.text(360,1148,p.caption,{font:'Scholar',weight:400,size:65,fill:C.colors.ink,anchor:'middle',width:631}))}`);
      const tl=gsap.timeline({paused:true});Object.entries({repo:0,highlight:.13,about:.46,badge:.70,settled:.90}).forEach(([n,t])=>tl.addLabel(n,C.t(t)));enter(tl,C,'panel',{x:-40,y:45,scale:.88,opacity:0});
      tl.set(C.q('about'),{opacity:0},0);tl.set(C.q('badge'),{opacity:0},0);
      const outline=C.q('outline').querySelector('rect'),length=outline.getTotalLength();tl.set(outline,{strokeDasharray:length,strokeDashoffset:length},0);tl.to(outline,{strokeDashoffset:0,duration:C.t(.14),ease:'power2.out'},C.t(.13));
      tl.to(C.q('panel'),{y:-10,rotation:.6,duration:C.t(.23),ease:'power1.inOut'},C.t(.18));
      tl.to([C.q('repo'),C.q('outline')],{y:-30,opacity:0,duration:C.t(.065),ease:'power2.in'},C.t(.43));
      tl.set(C.q('about'),{opacity:1},C.t(.46));tl.fromTo(C.q('about-mask'),{scaleY:0},{scaleY:1,svgOrigin:'35 320',duration:C.t(.15),ease:'power2.out'},C.t(.46));
      tl.to(C.q('panel'),{y:0,rotation:0,duration:C.t(.13),ease:'power2.out'},C.t(.51));enter(tl,C,'badge',{x:60,y:20,scale:.72,opacity:0},.70,.10);enter(tl,C,'caption',{y:25,opacity:0},.57,.08);
      tl.to(C.q('badge'),{rotation:1.5,duration:C.t(.12),yoyo:true,repeat:1,ease:'power1.inOut'},C.t(.79));return tl;
    }
  });

  Clone.register('product_card',{
    description:'Ficha de producto con estados GET→OPEN, métricas, agentes de marca/lanzamiento/despliegue y URL LIVE.',
    source:'CLONE F989–1046',reference:reference(32.966667,34.9),durationRange:[1.6,8],
    defaults:{appName:'Slotly',description:'Booking links for small teams',icon:'app_slotly',rating:'4.9★',price:'Flat',status:'Live',domain:'slotly.app',buttonInitial:'GET',buttonFinal:'OPEN',caption:'YOU CAN SHIP',agents:['agent_brand','agent_launch','agent_deploy']},
    parameters:{appName:'texto≤35',description:'texto≤65',icon:'asset existente',rating:'dato explícito',price:'dato explícito',status:'texto≤20',domain:'texto≤55',buttonInitial:'texto≤16',buttonFinal:'texto≤16',caption:'texto',agents:'tres sprites originales'},
    build(C){const p=C.params;if(!Array.isArray(p.agents)||p.agents.length!==3)throw Error('product_card necesita tres agentes con roles marca/lanzamiento/despliegue');
      C.root.innerHTML=C.svg(`<rect width="720" height="1280" fill="#000"/>
        <defs><radialGradient id="${C.id('product-glow')}"><stop stop-color="#a55331" stop-opacity=".15"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient></defs><ellipse cx="361" cy="596" rx="323" ry="271" fill="url(#${C.id('product-glow')})"/>
        ${group(C,'card',rect(53,134,613,372,32,'#1b1b1e','stroke="#343235" stroke-width="1"')+C.image(p.icon,86,166,154,154)+C.text(268,225,p.appName,{size:49,fill:'white',width:360})+C.text(269,262,p.description,{size:23,weight:400,fill:'#929091',width:365})+
          rect(268,282,113,43,22,'#009cfa',`id="${C.id('button')}"`)+group(C,'buttonGet',C.text(324,311,p.buttonInitial,{size:22,fill:'white',anchor:'middle',width:99}))+group(C,'buttonOpen',C.text(324,311,p.buttonFinal,{size:22,fill:'#00a4ff',anchor:'middle',width:99}))+`<path d="M87 354h546" stroke="#2a282a"/>`+
          C.text(170,390,'RATING',{font:'Mono',size:12,fill:'#959191',anchor:'middle','letter-spacing':1})+C.text(360,390,'PRICE',{font:'Mono',size:12,fill:'#959191',anchor:'middle','letter-spacing':1})+C.text(543,390,'STATUS',{font:'Mono',size:12,fill:'#959191',anchor:'middle','letter-spacing':1})+
          group(C,'rating',C.text(170,433,p.rating,{size:37,fill:'white',anchor:'middle',width:146}))+group(C,'price',C.text(360,433,p.price,{size:37,fill:'white',anchor:'middle',width:146}))+group(C,'status',C.text(543,433,p.status,{size:37,fill:C.colors.green,anchor:'middle',width:146})))}
        ${group(C,'brand',C.sprite(p.agents[0],86,601,143))}${group(C,'launch',C.sprite(p.agents[1],307,624,150))}
        ${group(C,'trail',`<path d="M580 587v230" stroke="#d7a126" stroke-width="4" opacity=".7"/><path d="M593 587v187" stroke="#c57024" stroke-width="2" opacity=".45"/>`)}${group(C,'deploy',C.sprite(p.agents[2],527,436,146))}
        ${group(C,'live',rect(208,814,304,55,28,'#071b11','stroke="#318d51" stroke-width="1.3"')+`<circle cx="239" cy="841" r="7" fill="${C.colors.green}"/>`+C.text(367,850,'LIVE · '+p.domain,{size:22,font:'Mono',fill:C.colors.green,anchor:'middle',width:263}))}
        ${group(C,'caption',C.text(360,1128,p.caption,{font:'Scholar',weight:400,size:76,fill:`url(#${C.id('editorial')})`,anchor:'middle',width:631}))}`);
      const tl=gsap.timeline({paused:true});Object.entries({get:0,open:.40,deployment:.48,live:.68,settled:.90}).forEach(([n,t])=>tl.addLabel(n,C.t(t)));enter(tl,C,'card',{y:45,scale:.87,opacity:0});tl.set(C.q('buttonOpen'),{opacity:0},0);tl.set(C.q('trail'),{opacity:0},0);
      ['rating','price','status'].forEach((n,i)=>enter(tl,C,n,{y:16,opacity:0},.08+i*.035,.08));enter(tl,C,'brand',{x:-40,y:55,opacity:0},.13);enter(tl,C,'launch',{y:160,opacity:0},.21);tl.fromTo(C.q('deploy'),{y:356,opacity:0},{y:330,opacity:1,duration:C.t(.08),ease:'power2.out'},C.t(.30));
      tl.to(C.q('brand'),{y:-8,rotation:-3,duration:C.t(.12),yoyo:true,repeat:1,ease:'power1.inOut'},C.t(.28));
      tl.to(C.q('buttonGet'),{opacity:0,duration:C.t(.05)},C.t(.40));tl.to(C.q('buttonOpen'),{opacity:1,duration:C.t(.05)},C.t(.40));tl.to(C.q('button'),{fill:'#333335',duration:C.t(.06)},C.t(.40));
      tl.to(C.q('deploy'),{y:-1,duration:C.t(.28),ease:'power2.inOut'},C.t(.48));tl.fromTo(C.q('trail'),{opacity:0,scaleY:0},{opacity:1,scaleY:1,svgOrigin:'580 817',duration:C.t(.23),ease:'power2.in'},C.t(.48));
      enter(tl,C,'live',{y:18,scale:.94,opacity:0},.68);enter(tl,C,'caption',{y:25,opacity:0},.53);
      tl.to(C.q('card'),{scale:1.007,duration:C.t(.15),ease:'power1.inOut'},C.t(.80));return tl;
    }
  });
})();
