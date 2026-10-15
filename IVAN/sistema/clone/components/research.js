/* Fuente: CLONE F0–43, F648–861. Recursos originales; geometría editable. */
(() => {
  const ref=(a,b)=>[{source:'recursos/B2_CLONE.mp4',entry_s:a,exit_s:b}];
  const g=(C,n,inside)=>`<g id="${C.id(n)}">${inside}</g>`;
  const r=(x,y,w,h,fill,rad=14,extra='')=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${rad}" fill="${fill}" ${extra}/>`;
  Clone.register('apps_clone_orbit',{
    description:'Una aplicación se duplica en un clon; aplicaciones satélite se reorganizan alrededor del agente pixel art.',
    reference:ref(0,1.466667),source:'CLONE F0–43',durationRange:[1.2,7],
    defaults:{main:'app_airbnb',satellites:['app_notion','app_spotify','app_duolingo','app_uber'],badge:'CLONE',caption:'ANY APP',agent:'agent_base'},
    parameters:{main:'asset existente',satellites:'1–5 assets existentes',badge:'texto≤20',caption:'texto',agent:'sprite existente'},
    build(C){const p=C.params,spots=[[154,247],[224,175],[442,187],[568,431],[526,549]];
      C.root.innerHTML=C.svg(r(0,0,720,1280,C.colors.paper,0)+g(C,'world',
        g(C,'main',C.image(p.main,190,344,158))+g(C,'copy',C.image(p.main,397,344,158)+r(483,326,72,22,'#df9a81',11)+C.text(519,342,p.badge,{size:11,fill:'white',anchor:'middle',width:66}))+
        p.satellites.slice(0,5).map((key,i)=>g(C,'sat'+i,C.image(key,...spots[i],78))).join('')+
        g(C,'agent',C.sprite(p.agent,315,612,101))+g(C,'caption',C.editorial(p.caption,973,80))));
      const tl=gsap.timeline({paused:true});
      tl.fromTo(C.q('main'),{y:60,rotation:-7,opacity:0},{y:0,rotation:0,opacity:1,duration:C.t(.09),ease:'power3.out'},0);
      tl.fromTo(C.q('copy'),{x:-207,rotation:-7,opacity:0},{x:0,rotation:0,opacity:1,duration:C.t(.19),ease:'power3.inOut'},C.t(.16));
      p.satellites.slice(0,5).forEach((_,i)=>{
        tl.fromTo(C.q('sat'+i),{x:360-spots[i][0],y:430-spots[i][1],scale:.8,opacity:0},{x:0,y:0,scale:1,opacity:1,duration:C.t(.14),ease:'power3.out',transformOrigin:'center center'},C.t(.21+i*.045));
        tl.to(C.q('sat'+i),{y:i%2?-10:10,rotation:i%2?4:-4,duration:C.t(.2),ease:'sine.inOut'},C.t(.57));
      });
      tl.fromTo(C.q('agent'),{x:-25,y:30,opacity:0},{x:0,y:0,opacity:1,duration:C.t(.11)},C.t(.34));
      tl.fromTo(C.q('caption'),{y:18,opacity:0},{y:0,opacity:1,duration:C.t(.1)},C.t(.42));
      tl.to(C.q('world'),{y:-24,scale:1.045,transformOrigin:'50% 35%',duration:C.t(.14),ease:'power2.inOut'},C.t(.86));
      return tl;
    }
  });
  Clone.register('radial_research',{
    description:'Fuentes de reseñas convergen en el agente: datos recorren rutas curvas y el contador registra la investigación.',
    reference:ref(21.6,24.2),source:'CLONE F648–725',durationRange:[2,9],
    defaults:{sources:[{asset:'app_store',label:'App Store'},{asset:'app_g2',label:'G2'},{asset:'app_reddit',label:'Reddit'},{asset:'app_trustpilot',label:'Trustpilot'}],count:140,metric:'reviews read',target:'calendar_blue',agent:'agent_entrepreneur',caption:'ON THE APP YOU CLONED'},
    parameters:{sources:'1–4 pares{asset,label}',count:'número0–9999 con fuente',metric:'texto≤35',target:'asset existente',agent:'sprite existente',caption:'texto'},
    build(C){const p=C.params,spots=[[117,240],[603,240],[117,660],[603,660]];
      const routes=p.sources.slice(0,4).map((source,i)=>{
        const [x,y]=spots[i],path=`M${x} ${y+20} Q${x} 490 360 482`;
        return g(C,'route'+i,`<path id="${C.id('line'+i)}" d="${path}" fill="none" stroke="#d5c4bb" stroke-width="2" stroke-dasharray="5 4"/>`+
          `<circle id="${C.id('data'+i)}" cx="${x}" cy="${y+20}" r="5" fill="${C.colors.clay}"/>`)+g(C,'source'+i,C.image(source.asset,x-36,y-36,72)+C.text(x,y+65,source.label,{size:19,weight:400,anchor:'middle',width:174}));
      }).join('');
      C.root.innerHTML=C.svg(r(0,0,720,1280,C.colors.paper,0)+g(C,'world',routes+
        g(C,'target',C.image(p.target,322,151,76)+C.text(360,255,'THE APP YOU CLONED',{font:'Mono',size:14,weight:400,fill:'#8c8584',anchor:'middle','letter-spacing':2,width:294}))+
        g(C,'agent',C.sprite(p.agent,290,385,145))+
        g(C,'counter-group',C.text(313,623,'0',{size:54,anchor:'end',id:C.id('counter')})+C.text(333,620,p.metric,{size:23,weight:400,width:290}))+
        g(C,'caption',C.editorial(p.caption,1040,72))));
      const tl=gsap.timeline({paused:true});
      tl.fromTo(C.q('agent'),{y:25,opacity:0},{y:0,opacity:1,duration:C.t(.09)},0);
      p.sources.slice(0,4).forEach((_,i)=>{
        const [x,y]=spots[i],start=.08+i*.025;
        tl.fromTo(C.q('source'+i),{x:(360-x)*.3,y:(482-y)*.3,opacity:0},{x:0,y:0,opacity:1,duration:C.t(.10),ease:'power3.out'},C.t(start));
        C.draw(tl,'line'+i,C.t(start+.06),C.t(.13));
        tl.set(C.q('data'+i),{opacity:0},0);
        const proxy={progress:0},paint=()=>{const k=proxy.progress,u=1-k;C.q('data'+i).setAttribute('cx',u*u*x+2*u*k*x+k*k*360);C.q('data'+i).setAttribute('cy',u*u*(y+20)+2*u*k*490+k*k*482);};
        tl.fromTo(proxy,{progress:0},{progress:1,duration:C.t(.34),ease:'none',onUpdate:paint},C.t(.24+i*.035));
        tl.to(C.q('data'+i),{opacity:1,duration:.03},C.t(.24+i*.035));
        tl.to(C.q('data'+i),{opacity:0,duration:.04},C.t(.58+i*.035));
      });
      const reading={value:0},paintReading=()=>C.q('counter').textContent=Math.round(reading.value);C.repaints.push(paintReading);
      const samples=[[.2,0],[.45,.3],[.7,121/140],[.94,1]];
      for(let i=1;i<samples.length;i++)tl.fromTo(reading,{value:samples[i-1][1]*Number(p.count)},{value:samples[i][1]*Number(p.count),duration:C.t(samples[i][0]-samples[i-1][0]),ease:'none',immediateRender:false},C.t(samples[i-1][0]));
      tl.fromTo(C.q('target'),{y:-44,opacity:0},{y:0,opacity:1,duration:C.t(.12),ease:'power3.out'},C.t(.53));
      tl.fromTo(C.q('caption'),{y:18,opacity:0},{y:0,opacity:1,duration:C.t(.08)},C.t(.12));
      tl.to(C.q('world'),{scale:1.035,y:-20,duration:C.t(.13),transformOrigin:'50% 35%',ease:'power2.inOut'},C.t(.87));return tl;
    }
  });
  Clone.register('feedback_bars',{
    description:'Reseñas se ordenan; evidencia se convierte en tres categorías y barras dinámicas con cifras declaradas.',
    reference:ref(24.2,28.733333),source:'CLONE F726–861',durationRange:[2.8,12],
    defaults:{reviews:[{asset:'app_store',text:'No SMS reminders? My clients keep no-showing.',tag:'MISSING FEATURE'},{asset:'app_g2',text:'Per-seat pricing doubled our bill overnight.',tag:'PRICING'},{asset:'app_reddit',text:'Guests keep booking in the wrong time zone.',tag:'UNSOLVED PROBLEM'},{asset:'app_trustpilot',text:'Still can’t export my bookings to CSV.',tag:'MISSING FEATURE'},{asset:'app_store',text:'Rescheduling breaks the calendar sync. Again.',tag:'UNSOLVED PROBLEM'},{asset:'app_g2',text:'Paying more every year for the same app.',tag:'THINGS PEOPLE HATE'}],categories:[{label:'Missing features',value:38,color:'#d77357'},{label:'Unsolved problems',value:27,color:'#e99b22'},{label:'Things people hate',value:51,color:'#ff3529'}],caption:'READS USER FEEDBACK',agent:'agent_entrepreneur'},
    parameters:{reviews:'1–8 pares{asset,text,tag}',categories:'1–3 pares{label,value,color} con fuente',caption:'texto',agent:'sprite existente'},
    build(C){const p=C.params,reviews=p.reviews.slice(0,8),cats=p.categories.slice(0,3),max=Math.max(1,...cats.map(c=>Number(c.value)));
      const categoryKey=s=>String(s).toUpperCase().replace(/S\b/g,'').replace(/[^A-Z0-9]/g,'');
      const tagColor=row=>cats.find(c=>categoryKey(c.label)===categoryKey(row.tag))?.color||C.colors.clay;
      const cards=reviews.map((row,i)=>g(C,'review'+i,r(78,139+i*103,564,84,'#fff',12,`filter="${C.soft}"`)+C.image(row.asset,94,166+i*103,35)+C.text(143,183+i*103,'“'+row.text+'”',{size:18,weight:400,width:476})+r(475,145+i*103,156,20,tagColor(row),5)+C.text(553,159+i*103,row.tag,{size:9,font:'Mono',fill:'white',anchor:'middle',width:147}))).join('');
      const bars=cats.map((cat,i)=>g(C,'row'+i,C.text(111,660+i*89,cat.label,{size:18,weight:400,fill:'white',width:205})+r(328,645+i*89,229,9,'#333236',4)+r(328,645+i*89,229*Number(cat.value)/max,9,cat.color,4,`id="${C.id('bar'+i)}"`)+C.text(605,664+i*89,'0',{size:25,fill:cat.color,anchor:'end',id:C.id('count'+i)}))).join('');
      const headlines=[p.caption,...cats.map(cat=>String(cat.label).toUpperCase())];
      const editorial=headlines.map((value,i)=>g(C,'caption'+i,C.editorial(value,1100,69))).join('');
      C.root.innerHTML=C.svg(`<defs><clipPath id="${C.id('deck-mask')}"><rect x="62" y="126" width="598" height="420"/></clipPath></defs>`+r(0,0,720,1280,C.colors.paper,0)+g(C,'world',`<g clip-path="url(#${C.id('deck-mask')})">${g(C,'deck',cards).replace('<g id=', '<g data-layout-allow-overflow="true" id=')}</g>`+
        g(C,'panel',r(72,561,576,325,C.colors.dark,22,`filter="${C.shadow}"`)+C.text(111,601,'WHAT USERS WANT FIXED',{font:'Mono',size:11,fill:'#aaa7a7',weight:400,'letter-spacing':2})+bars)+
        g(C,'agent',C.sprite(p.agent,550,526,94))+editorial));
      const tl=gsap.timeline({paused:true});
      reviews.forEach((_,i)=>tl.fromTo(C.q('review'+i),{y:180-Math.min(i,3)*25,x:i%2?24:-24,opacity:0},{x:0,y:0,opacity:1,duration:C.t(.085),ease:'power3.out'},C.t(.015+Math.min(i,3)*.05)));
      // Como en CLONE, nueva evidencia reemplaza la fila superior y alimenta
      // la categoría siguiente; no mantener cuatro tarjetas inmóviles.
      const extra=Math.max(0,reviews.length-4);
      for(let i=0;i<extra;i++)tl.to(C.q('deck'),{y:-103*(i+1),duration:Math.min(.3,C.t(.08)),ease:'power3.inOut'},C.t(.42+i*(.35/Math.max(1,extra-1))));
      tl.fromTo(C.q('panel'),{y:55,opacity:0},{y:0,opacity:1,duration:C.t(.10)},C.t(.20));
      tl.fromTo(C.q('agent'),{x:40,y:18,opacity:0},{x:0,y:0,opacity:1,duration:C.t(.10)},C.t(.21));
      cats.forEach((cat,i)=>{tl.fromTo(C.q('bar'+i),{scaleX:0},{scaleX:1,svgOrigin:`328 ${645+i*89}`,duration:C.t(.19),ease:'power2.out'},C.t(.32+i*.13));C.counter(tl,'count'+i,0,Number(cat.value),C.t(.32+i*.13),C.t(.19));
        if(reviews[i])tl.to(C.q('review'+i),{x:12,rotation:.6,duration:C.t(.12),yoyo:true,repeat:1,transformOrigin:'center center'},C.t(.29+i*.13));});
      headlines.forEach((_,i)=>{tl.set(C.q('caption'+i),{opacity:0,y:17},0);const at=i===0?.15:.32+(i-1)*.13;
        tl.to(C.q('caption'+i),{opacity:1,y:0,duration:Math.min(.25,C.t(.06)),ease:'power3.out'},C.t(at));
        if(i){const fade=Math.min(.12,C.t(.025));tl.to(C.q('caption'+(i-1)),{opacity:0,y:-17,duration:fade,ease:'power2.in'},C.t(at)-fade);}});
      tl.to(C.q('world'),{y:-20,scale:1.025,duration:C.t(.12),transformOrigin:'50% 40%',ease:'power2.inOut'},C.t(.88));return tl;
    }
  });
})();
