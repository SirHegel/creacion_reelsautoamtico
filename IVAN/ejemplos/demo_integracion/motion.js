/* Dirección V5 original. Medios auténticos + proceso conceptual por componentes. */
(async()=>{
 const A=await crearAscendiaRuntime(document.querySelector('#root'));
 const {ROOT,P,tl,$,el,group,text,windowAt,move,reveal,svg,morph,travel,draw,finish}=A;
 const INK='#0d121b',WHITE='#fafaf8',RED='#ee2335';
 const stage=$('stage');
 // Los recursos reales tienen ventanas temporales y envolturas propias.
 P.broll.forEach(b=>windowAt($(b.id+'Clip'),b.inicio,b.fin));
 windowAt($('burn'),79/30,3.20);
 move($('claudeClip'),1.10,{height:1920},.20);
 move($('claudePlane'),1.10,{width:3413,height:1920,left:-1166,top:0},.20);
 move($('claudePlane'),2.12,{scale:1.08},.20);

 // Hook YO: frase acumulada, dos niveles; el nombre no recibe rojo.
 const hook=windowAt(group(ROOT,{zIndex:65}),0,1.20);
 const hook1=text(hook,'Herramienta A',90,804,114,{width:'900px',textAlign:'center',color:'#191b1e',letterSpacing:'-4px'});
 const hook2=text(hook,'activa',90,913,142,{width:'900px',textAlign:'center',color:RED,letterSpacing:'-5px',textShadow:'2px 4px 5px rgba(0,0,0,.85)'});
 // No set oculto en t=0: evitar perder el primer texto en la captura determinista.
 hook1.style.clipPath='inset(0 0 0% 0)';
 tl.fromTo(hook1,{y:24},{y:0,duration:.15,ease:'power3.out'},.03);
 windowAt(hook2,.55,1.20);reveal(hook2,.55,.17,{y:32});
 move(hook,1.04,{y:-24,opacity:0},.14);
 const claudeLabel=windowAt(text(ROOT,'Claude',90,853,102,{width:'900px',textAlign:'center',zIndex:65,textShadow:'2px 4px 5px rgba(0,0,0,.85)'}),1.20,2.40);
 reveal(claudeLabel,1.20,.18,{y:30});move(claudeLabel,1.30,{y:470,scale:1.08},.26);move(claudeLabel,2.18,{y:480,opacity:0},.2);

 // Lectura auténtica, muy breve y ampliada; mantener URL real, nunca sustituirla.
 const fetchLabel=windowAt(text(ROOT,'lee la web',70,230,108,{width:'940px',textAlign:'center',zIndex:65,textShadow:'2px 4px 5px rgba(0,0,0,.85)'}),2.40,86/30);
 reveal(fetchLabel,2.40,.16,{y:26});
 const selection=windowAt(el('div',ROOT,'',{left:'135px',top:'887px',width:'804px',height:'67px',border:'3px solid #fff',background:'rgba(255,255,255,.10)',zIndex:62}),2.47,86/30);
 tl.fromTo(selection,{scaleX:0,transformOrigin:'left center'},{scaleX:1,duration:.20,ease:'power3.out'},2.47);
 move(selection,2.73,{y:-110,x:10,rotation:-4,width:760},.24);
 move($('fetchClip'),2.82,{x:-220,y:130,scale:.92,skewX:3,transformOrigin:'center'},.22);

 // Un mismo mundo evoluciona de web curva a fuentes, extracción y salida.
 const world=windowAt(group(stage,{zIndex:50,perspective:'1500px',transformStyle:'flat'}),86/30,10);
 world.dataset.audit='world';
 const backdrop=group(world,{background:INK});
 svg(backdrop,`<defs><pattern id="fineGrid" width="90" height="90" patternUnits="userSpaceOnUse"><path d="M90 0H0V90" fill="none" stroke="#fff" stroke-opacity=".035"/></pattern><radialGradient id="halo"><stop stop-color="#fff" stop-opacity=".07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient></defs><rect width="1080" height="1920" fill="url(#fineGrid)"/><ellipse cx="540" cy="970" rx="530" ry="600" fill="url(#halo)"/>`);
 const concept=text(world,'Esquema del proceso',88,214,35,{color:'#9ca3af',letterSpacing:'1px'});
 const globe=group(world,{transformOrigin:'540px 1020px',transformStyle:'flat'});
 const mesh=svg(globe,`<g transform="translate(540 1040)"><circle r="365" stroke="#cdd3db" stroke-width="2" fill="none"/><ellipse rx="125" ry="365" stroke="#fff" stroke-opacity=".7" fill="none"/><ellipse rx="255" ry="365" stroke="#fff" stroke-opacity=".35" fill="none"/><ellipse rx="365" ry="85" stroke="#fff" stroke-opacity=".75" fill="none"/><ellipse rx="365" ry="235" stroke="#fff" stroke-opacity=".35" fill="none"/><path d="M-365 0H365M0-365V365" stroke="#fff" stroke-opacity=".2"/></g>`);
 const titleA=text(globe,'todo',75,465,132,{width:'930px',textAlign:'center',letterSpacing:'-5px'});
 const titleB=text(globe,'internet',60,596,172,{width:'960px',textAlign:'center',fontFamily:'Scholar',letterSpacing:'-3px'});
 reveal(titleA,2.95,.20,{y:65});reveal(titleB,3.18,.22,{y:75});
 tl.fromTo(mesh,{skewX:-8,rotationZ:-18,scale:.65},{skewX:0,rotationZ:8,scale:1,duration:.58,ease:'power3.out'},2.85);
 const packet=el('div',globe,'',{left:0,top:0,width:'115px',height:'26px',background:WHITE,borderRadius:'3px',boxShadow:'0 3px 0 rgba(0,0,0,.2)'});
 travel(packet,'M100 980 C200 620 910 770 865 1150 C810 1470 250 1320 240 990',2.86,.84,22);
 const orbit=svg(globe,`<path id="orbit" d="M110 1010C250 450 1180 950 860 1360C620 1640 140 1340 110 1010" stroke="#fff" stroke-opacity=".7" stroke-width="3" fill="none"/>`);
 draw(orbit.querySelector('path'),2.95,.64);
 move(globe,3.50,{scale:1.65,skewX:12,rotationZ:15,x:-410,y:-250,opacity:0},.20);
 const pages=windowAt(text(world,'fuentes como',100,450,96,{width:'880px',textAlign:'center'}),3.70,4.24);reveal(pages,3.70,.17,{y:30});move(pages,4.04,{y:-25,opacity:0},.18);

 // Las fuentes son símbolos editoriales identificados, no interfaces falsificadas.
 const sources=windowAt(group(world,{transformStyle:'flat',transformOrigin:'540px 900px'}),3.65,6.38);
 const linkedin=`<rect width="90" height="90" rx="10" fill="#0a66c2"/><text x="13" y="71" font-family="Arial" font-weight="bold" font-size="70" fill="white">in</text>`;
 const youtube=`<rect x="0" y="12" width="96" height="67" rx="18" fill="#ff0033"/><path d="M39 29L39 63L68 46Z" fill="white"/>`;
 const instagram=`<defs><linearGradient id="ig" x1="0" x2="1" y1="1" y2="0"><stop stop-color="#feda75"/><stop offset=".4" stop-color="#fa7e1e"/><stop offset=".7" stop-color="#d62976"/><stop offset="1" stop-color="#962fbf"/></linearGradient></defs><rect x="4" y="4" width="82" height="82" rx="22" fill="none" stroke="url(#ig)" stroke-width="10"/><circle cx="45" cy="45" r="19" stroke="url(#ig)" stroke-width="8" fill="none"/><circle cx="69" cy="21" r="5" fill="#962fbf"/>`;
 const definitions=[{name:'LinkedIn',logo:linkedin,time:4.24,entryTime:3.60,x:140,y:610,angle:-13},
 {name:'YouTube',logo:youtube,time:4.96,x:240,y:720,angle:12},
 {name:'Instagram',logo:instagram,time:5.36,x:160,y:850,angle:-9}];
 const {fragments}=crearFuentesDinamicas(A,sources,definitions);
 move(sources,5.68,{scale:.82,y:-280,skewX:-4},.4);

 // Une surface unique se construit avec les fragments; morphing continu.
 const output=windowAt(group(world,{transformOrigin:'540px 1190px',transformStyle:'flat'}),5.62,10);
 output.dataset.audit='output';
 const surface=svg(output,`<defs><linearGradient id="paper" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ffffff"/><stop offset="1" stop-color="#c8cdd5"/></linearGradient></defs><path id="sheet" d="M340 1100 C470 1030 610 1220 740 1100 C730 1180 760 1430 720 1510 C580 1440 480 1630 350 1530 C340 1420 320 1200 340 1100Z" fill="url(#paper)"/><path id="fold" d="M340 1100C470 1030 610 1220 740 1100" stroke="#fff" stroke-width="3" fill="none"/>`);
 surface.dataset.audit='surface';
 morph(surface.querySelector('#sheet'),5.96,'M295 890 C458 890 622 890 785 890 C785 1100 785 1340 785 1550 C622 1550 458 1550 295 1550 C295 1340 295 1100 295 890Z',.46);
 tl.fromTo(output,{rotationZ:-8,y:80},{rotationZ:0,y:0,duration:.42,ease:'power3.out'},5.65);
 const outputLines=[];
 for(let j=0;j<6;j++){
   const l=el('div',output,'',{left:'355px',top:(985+j*55)+'px',width:(340-j%3*45)+'px',height:j===0?'17px':'10px',background:j===0?'#1f2530':'#87909c',borderRadius:'3px',transformOrigin:'left center'});outputLines.push(l);
  tl.fromTo(l,{scaleX:0,x:100},{scaleX:1,x:0,duration:.25,ease:'power3.out'},5.83+j*.10);
 }
 move(output,6.42,{scale:.60,x:-120,y:-40,rotationZ:7},.3);

 // Obstacle de coût API et trajet alternatif, pas de compteur inventé.
 const bypass=windowAt(group(world,{transformStyle:'flat'}),5.84,9.15);
 const api=el('div',bypass,'API',{left:'715px',top:'1140px',width:'225px',height:'185px',background:'#181e29',border:'3px solid #7c3540',borderRadius:'18px',display:'flex',justifyContent:'center',alignItems:'center',fontSize:'76px',color:WHITE});
 reveal(api,5.84,.20,{x:100});
 const route=svg(bypass,`<path id="direct" d="M365 1280H845" stroke="#6c7789" stroke-width="4" fill="none"/><path id="detour" d="M365 1280 C365 1520 850 1570 860 1390 C880 1070 760 905 590 865" stroke="#fff" stroke-width="6" fill="none"/><path id="cross" d="M735 1160L920 1305M920 1160L735 1305" stroke="${RED}" stroke-width="7" stroke-linecap="round" fill="none"/>`);
 draw(route.querySelector('#direct'),5.88,.28);draw(route.querySelector('#detour'),6.37,.55);draw(route.querySelector('#cross'),6.72,.22);
 const pulse=el('div',bypass,'',{left:0,top:0,width:'34px',height:'24px',borderRadius:'5px',background:WHITE});windowAt(pulse,6.40,7.36);travel(pulse,'M365 1280 C365 1520 850 1570 860 1390 C880 1070 760 905 590 865',6.40,.88,0);
 move(api,6.86,{skewX:8,x:210,scaleX:.1,opacity:0},.32);
 move(bypass,7.54,{scale:1.35,x:70,y:-120,opacity:0},.32);

 // Split bref récurrent: la source humaine reste native, jamais dupliquée en blur.
 move(world,182/30,{scale:.95,y:-450,transformOrigin:'540px 700px'},.20);
 move(world,200/30,{scale:1,y:0,transformOrigin:'540px 700px'},.26);
 const subs=windowAt(group(ROOT,{zIndex:82}),6.68,7.80);
 const sub1=windowAt(text(subs,'de payer',130,1450,72,{width:'820px',textAlign:'center',textShadow:'2px 4px 5px rgba(0,0,0,.85)'}),6.68,7.04);
 sub1.textContent='de datos';
 const sub2=windowAt(text(subs,'de ejemplo',130,1450,72,{width:'820px',textAlign:'center',textShadow:'2px 4px 5px rgba(0,0,0,.85)'}),7.04,7.80);
 reveal(sub1,6.68,.12,{y:12});reveal(sub2,7.04,.14,{y:14});

 // Résolution sans nouvelle voix: le papier se plie, se révèle et ferme le mouvement.
 move(output,7.57,{scale:1.05,x:0,y:-30,rotationZ:0,rotationY:0},.40);
 morph(surface.querySelector('#sheet'),7.62,'M270 845 C450 845 630 845 810 845 C810 1060 810 1290 810 1540 C630 1540 450 1540 270 1540 C270 1290 270 1060 270 845Z',.42);
 outputLines.forEach((l,j)=>move(l,7.75+j*.045,{y:30,x:0},.28));
 const end=windowAt(group(world),7.83,10);
 const end1=text(end,'con datos',75,475,113,{width:'930px',textAlign:'center',letterSpacing:'-4px'});
 const end2=text(end,'un ejemplo',75,585,145,{width:'930px',textAlign:'center',fontFamily:'Scholar',letterSpacing:'-4px'});
 reveal(end1,7.83,.22,{y:40});reveal(end2,8.02,.24,{y:50});
 const seal=text(output,'contenido',320,1380,60,{width:'440px',textAlign:'center',color:'#202734',fontFamily:'Scholar'});windowAt(seal,8.05,10);reveal(seal,8.05,.22,{y:30});
 ['LinkedIn','YouTube','Instagram'].forEach((name,i)=>{
  const row=text(output,name,340,930+i*112,43,{color:'#202734',letterSpacing:'-1px'});windowAt(row,7.98+i*.16,10);reveal(row,7.98+i*.16,.2,{x:40});
 });
 const closing=svg(output,`<path id="envelopeFold" d="M270 1030C450 1030 630 1030 810 1030" fill="none" stroke="#7f8791" stroke-width="3"/>`);windowAt(closing,8.62,10);
 outputLines.forEach((line,j)=>move(line,8.45+j*.045,{x:70,y:90,scaleX:.4,opacity:0},.22));
 Array.from(output.children).filter(n=>n.textContent==='LinkedIn'||n.textContent==='YouTube'||n.textContent==='Instagram').forEach((row,i)=>move(row,8.46+i*.10,{y:70,opacity:0},.22));
 morph(surface.querySelector('#sheet'),8.66,'M270 1010 C450 960 630 960 810 1010 C810 1160 810 1390 810 1540 C630 1540 450 1540 270 1540 C270 1390 270 1160 270 1010Z',.27);
 morph(closing.querySelector('path'),8.80,'M270 1010C450 1310 630 1310 810 1010',.27);
 move(surface.querySelector('#fold'),8.60,{opacity:0},.16);
 move(output,9.08,{rotationZ:0,scale:1.18,y:-80},.22);
 move(output,9.60,{scale:1.12,y:-55},.22);
 move(end,9.30,{y:-12},.48);
 finish();
})();
