/* Agent Reach: primeros 10 s. Acciones ligadas al audio; resto todavía pendiente. */
(async()=>{
const {ROOT,P,tl,INK,PAPER,RED,$,el,group,text,windowAt,move,reveal,svg,morph,travel,draw,finish}=await window.crearAscendiaRuntime(document.getElementById('root'));
const stage=$('stage');
// Material real a ancho completo. El rostro ajeno del b-roll queda fuera del recorte.
for(const b of P.broll)windowAt($(b.id+'Clip'),b.inicio,b.fin);
windowAt($('burn'),2.65,3.20);
tl.fromTo($('webHookClip'),{y:-1152},{y:0,duration:.24,ease:'power3.inOut'},.62);
move($('webHookPlane'),1.86,{x:-36,y:-30,scale:1.05},.22);
move($('webHookClip'),1.86,{height:1290},.22);
move($('webHookPlane'),2.35,{x:10,y:-98,scale:1.10},.20);
tl.fromTo($('workClip'),{clipPath:'inset(0 0 100% 0)'},{clipPath:'inset(0 0 0% 0)',duration:.2,ease:'power3.out'},2.84);
// Hook: dos titulares editoriales; ninguna transcripción convencional automática.
const personal=group(ROOT,{zIndex:60,opacity:1});tl.to(personal,{opacity:0,duration:.08,ease:'power2.in'},.54);
const skill=text(personal,'UNA SKILL',130,1056,130,{width:'820px',textAlign:'center',letterSpacing:'-5px',textShadow:'2px 4px 5px rgba(0,0,0,.85)'});reveal(skill,.06,.18,{y:55});
const slash=el('div',personal,'',{left:'115px',top:'1214px',width:'825px',height:'7px',background:'#f4f1e9',transformOrigin:'0 50%'});tl.fromTo(slash,{scaleX:0},{scaleX:1,duration:.18,ease:'power3.out'},.21);
const hook=group(ROOT,{zIndex:55});windowAt(hook,.62,2.84);
const claude=text(hook,'Claude',82,60,106,{letterSpacing:'-3px',textShadow:'2px 4px 5px rgba(0,0,0,.85)'});reveal(claude,.62,.18,{y:-40});
const todo=text(hook,'TODO',77,1365,148,{letterSpacing:'-5px'}),internet=text(hook,'INTERNET',72,1521,156,{letterSpacing:'-7px'});windowAt(todo,1.86,2.84);windowAt(internet,1.86,2.84);reveal(todo,1.86,.20,{x:-95});reveal(internet,2.22,.20,{y:70});
const sweep=el('div',hook,'',{left:'28px',top:'1030px',width:'1024px',height:'3px',background:'#f4f1e9',boxShadow:'0 1px 6px #fff6'});windowAt(sweep,1.01,2.4);move(sweep,1.01,{y:-760},.64);move(sweep,1.70,{y:-400},.4);
// El monitor se convierte en una fuente editorial. Fondo sólido deliberado, sin blur.
const flow=group(ROOT,{zIndex:25,color:INK,perspective:'1800px'});windowAt(flow,3.94,8.8);
const paper=group(flow,{background:PAPER});tl.fromTo(paper,{clipPath:'inset(30% 21% 44% 21%)'},{clipPath:'inset(0% 0% 0% 0%)',duration:.31,ease:'power3.inOut'},3.94);
const texture=group(flow,{opacity:.35,backgroundImage:'linear-gradient(#292c3012 1px,transparent 1px),linear-gradient(90deg,#292c3012 1px,transparent 1px)',backgroundSize:'64px 64px'});
const headline=text(flow,'La web,',78,219,111,{letterSpacing:'-4px'});reveal(headline,4.07,.19,{y:40});
const subhead=text(flow,'en un flujo.',78,334,121,{fontFamily:'Scholar',letterSpacing:'-5px'});reveal(subhead,4.14,.22,{x:80});
const label=text(flow,'FUENTES PÚBLICAS · ESQUEMA',83,491,29,{letterSpacing:'2px',color:'#666762'});reveal(label,4.19,.16,{y:15});
const world=group(flow,{transformOrigin:'540px 975px',transformStyle:'preserve-3d'});
const back=svg(world,'<path d="M 160 614 C160 614 968 614 968 614 C968 614 968 1280 968 1280 C968 1280 160 1280 160 1280 C160 1280 160 614 160 614 Z" fill="#dedbd2"/>');
const outline=svg(world,'<path d="M 100 560 C100 560 980 560 980 560 C980 560 980 1215 980 1215 C980 1215 100 1215 100 1215 C100 1215 100 560 100 560 Z" fill="#fffdf8" stroke="#282b2e" stroke-width="3"/>');
outline.style.filter='drop-shadow(14px 20px 18px #191b1e15)';const frame=outline.querySelector('path');
tl.fromTo(world,{x:115,y:155,rotationY:-16,rotation:-7,scale:.66},{x:0,y:0,rotationY:0,rotation:-3,scale:1,duration:.30,ease:'power3.out'},3.94);
const topRule=svg(world,'<path d="M100 669 L980 669" stroke="#282b2e" stroke-width="2"/><circle cx="137" cy="614" r="9" fill="#292c30"/><circle cx="170" cy="614" r="9" fill="#a4a29a"/><circle cx="203" cy="614" r="9" fill="#d4d0c7"/>');
const sourceName=text(world,'LinkedIn',277,577,74,{letterSpacing:'-3px'});
const figure=svg(world,'<path d="M 218 717 C 218 667 362 667 362 717 C362 747 349 770 327 777 C377 789 399 810 399 859 C399 859 181 859 181 859 C181 810 203 789 253 777 C231 770 218 747 218 717 Z" fill="#191b1e"/>');const figurePath=figure.querySelector('path');
const caption=text(world,'Perfiles',439,742,68,{letterSpacing:'-2px'});
const rowLines=svg(world,'<path d="M 164 935 L 914 935 M 164 1007 L 801 1007 M 164 1079 L 864 1079" stroke="#b8b6ad" stroke-width="15" stroke-linecap="round"/>');
const scanner=el('div',world,'',{left:'128px',top:'882px',width:'824px',height:'5px',background:INK,transformOrigin:'0 50%'});windowAt(scanner,4.37,6.16);
tl.fromTo(scanner,{scaleX:0},{scaleX:1,duration:.12},4.37);move(scanner,4.41,{y:240},.29);
// El barrido extrae campos; el mismo soporte se reformatea en video, retrato y mensaje.
const paths=['M 210 895 C 800 955 800 1330 614 1380','M 210 969 C 820 1030 610 1465 265 1410','M 210 1037 C 764 1120 700 1510 480 1475'];
const arrivals=[];
function extract(labels,t){labels.forEach((word,i)=>{
 const token=text(world,word,0,0,44,{padding:'13px 22px',background:INK,color:PAPER,borderRadius:'8px',letterSpacing:'-1px',whiteSpace:'nowrap',zIndex:6});windowAt(token,t+i*.07,Math.min(6.39,t+i*.07+.69));
 travel(token,paths[i],t+i*.07,.40,16-i*12);move(token,t+.47+i*.04,{scale:.78},.20);arrivals.push(token);
});}
extract(['perfil','empresa','sector'],4.40);
tl.set(sourceName,{textContent:'YouTube'},4.72);tl.set(caption,{textContent:'Videos'},4.72);
morph(figurePath,4.69,'M 204 715 C204 695 376 695 376 715 C376 715 398 715 398 746 C398 746 398 847 376 847 C376 847 204 847 204 847 C182 847 182 746 182 746 C182 715 204 715 204 715 Z',.23);
const play=svg(world,'<path d="M276 729 L276 820 L344 774 Z" fill="#fffdf8"/>');windowAt(play,4.82,5.23);reveal(play,4.82,.12,{y:0});
move(world,4.72,{rotation:3,x:-16,y:-33,rotationY:7},.22);move(scanner,4.76,{y:0},.12);move(scanner,4.88,{y:240},.25);extract(['tema','formato','video'],4.88);
tl.set(sourceName,{textContent:'Instagram'},5.20);tl.set(caption,{textContent:'Contenido'},5.20);
morph(frame,5.18,'M 245 532 C245 532 861 532 861 532 C861 532 861 1290 861 1290 C861 1290 245 1290 245 1290 C245 1290 245 532 245 532 Z',.25);
morph(figurePath,5.20,'M 297 711 C297 699 358 699 358 711 C358 711 358 738 358 738 C358 738 358 868 346 868 C346 868 285 868 285 868 C285 868 285 726 285 726 C285 711 297 711 297 711 Z',.23);
move(figure,5.20,{x:35},.22);move(caption,5.20,{x:-29,fontSize:57},.22);move(sourceName,5.20,{x:14,fontSize:66},.22);move(topRule,5.20,{scaleX:.69,x:82},.22);move(rowLines,5.20,{scaleX:.66,x:95},.22);
move(world,5.20,{rotation:-3,x:-55,y:15,rotationY:-5},.23);move(scanner,5.23,{y:0,scaleX:.7,x:116},.12);move(scanner,5.36,{y:240},.23);extract(['publicación','contenido','formato'],5.37);
tl.set(sourceName,{textContent:'Twitter / X'},5.84);tl.set(caption,{textContent:'Publicaciones'},5.84);
morph(frame,5.78,'M 104 583 C104 583 980 583 980 583 C980 583 980 1175 980 1175 C980 1175 104 1175 104 1175 C104 1175 104 583 104 583 Z',.24);
morph(figurePath,5.80,'M 194 720 C194 709 370 709 370 720 C370 720 394 720 394 754 C394 754 394 829 370 829 C370 829 231 829 231 829 C231 829 190 860 190 860 C190 860 190 745 194 720 Z',.25);
move(figure,5.8,{x:0},.22);move(caption,5.8,{x:-4,fontSize:53},.22);move(sourceName,5.8,{x:0,fontSize:69},.22);move(topRule,5.8,{scaleX:1,x:0},.22);move(rowLines,5.8,{scaleX:1,x:0},.22);
move(world,5.83,{rotation:0,x:0,y:-10,rotationY:0},.25);move(scanner,5.89,{scaleX:1,x:0,y:0},.12);move(scanner,6.02,{y:150},.16);
// Los fragmentos reaccionan a la lectura y convergen. La página se convierte en resultado.
const funnel=svg(flow,'<path d="M 151 1330 C 150 1570 925 1570 930 1330" stroke="#85867e" stroke-width="3" fill="none"/>');windowAt(funnel,4.58,6.65);draw(funnel.querySelector('path'),4.58,.34);
move(world,6.15,{scale:.28,x:8,y:360,rotation:10},.26);
arrivals.forEach((n,i)=>move(n,6.17+i*.008,{scale:.08,y:120},.26));
const cost=group(flow);windowAt(cost,6.32,8.08);
const zeroShape=svg(cost,'<path d="M 324 774 C324 724 756 724 756 774 C756 774 756 1086 756 1086 C756 1086 324 1086 324 1086 C324 1086 324 774 324 774 Z" fill="none" stroke="#191b1e" stroke-width="32"/>');const zp=zeroShape.querySelector('path');
tl.fromTo(zeroShape,{y:380,scale:.66},{y:0,scale:1,duration:.34,ease:'power3.inOut'},6.32);
morph(zp,6.32,'M 432 673 C432 578 734 578 734 771 C734 771 734 1181 583 1181 C583 1181 432 1181 432 988 C432 988 432 673 432 673 Z',.31);
move(world,6.43,{y:320,scale:.01},.13);windowAt(world,3.94,6.61);
const money=text(cost,'$0',0,676,480,{width:'1080px',textAlign:'center',letterSpacing:'-20px'});reveal(money,6.58,.18,{y:90});move(zeroShape,6.49,{opacity:0},.12);
const free=text(cost,'procesando',0,1295,117,{width:'1080px',textAlign:'center',fontFamily:'Scholar',letterSpacing:'-4px'});reveal(free,6.66,.21,{y:55});
move(zeroShape,7.13,{scale:1.055,x:8,y:-22},.20);move(money,7.13,{x:18,y:-22,scale:1.055},.20);
const noDollar=text(cost,'un ejemplo',0,1473,63,{width:'1080px',textAlign:'center',letterSpacing:'-1px'});windowAt(noDollar,7.12,7.93);reveal(noDollar,7.12,.12,{y:30});tl.set(noDollar,{textContent:'dólar'},7.68);
// El cero se reforma en lente: transición construida, sin tarjeta independiente.
move(money,7.78,{x:-135,clipPath:'inset(0 100% 0 0)'},.22);move(free,7.78,{y:185},.22);move(noDollar,7.92,{y:230},.12);move(zeroShape,7.77,{opacity:1},.22);
morph(zp,7.77,'M 245 793 C245 661 667 661 667 870 C667 870 667 1099 456 1099 C456 1099 245 1099 245 940 C245 940 245 793 245 793 Z',.27);
const tail=svg(cost,'<path d="M 616 1070 L 858 1312" stroke="#191b1e" stroke-width="37" stroke-linecap="round"/>');windowAt(tail,7.79,8.08);draw(tail.querySelector('path'),7.79,.25);
move(headline,6.35,{y:-15},.2);move(subhead,6.35,{y:-15},.2);
// La provocación narrada permanece separada de la demostración auténtica.
const contrast=group(ROOT,{zIndex:30});windowAt(contrast,8.08,10);
const dark=group(contrast,{background:INK});tl.fromTo(dark,{clipPath:'circle(6% at 45% 49%)'},{clipPath:'circle(115% at 45% 49%)',duration:.26,ease:'power3.inOut'},8.08);
const google=text(contrast,'Herramienta A',97,466,109,{letterSpacing:'-4px'});reveal(google,8.08,.20,{y:55});
const angry=text(contrast,'FURIOSO',77,607,149,{letterSpacing:'-6px',color:RED});windowAt(angry,8.64,9.18);reveal(angry,8.64,.16,{x:-88});
const ring=svg(contrast,'<path d="M 222 995 C222 786 858 786 858 995 C858 995 858 1216 540 1216 C540 1216 222 1216 222 1087 C222 1087 222 995 222 995 Z" fill="none" stroke="#f4f1e9" stroke-width="14"/>');const rp=ring.querySelector('path');windowAt(ring,8.08,8.8);
morph(rp,8.48,'M 40 769 C40 769 1040 769 1040 769 C1040 769 1040 1510 1040 1510 C1040 1510 40 1510 40 1510 C40 1510 40 769 40 769 Z',.28);
// La captura real entra por el marco surgido de la transformación anterior.
ROOT.insertBefore($('webFinalClip'),contrast);$('webFinalClip').style.zIndex='34';
tl.fromTo($('webFinalClip'),{clipPath:'inset(50% 46% 50% 46%)'},{clipPath:'inset(0% 0% 0% 0%)',duration:.25,ease:'power3.out'},8.8);
move(google,8.8,{y:-247,scale:.78,x:55},.23);move(angry,8.8,{y:-268,scale:.85,x:41},.23);
move($('webFinalPlane'),9.20,{x:-18,y:-44,scale:1.06},.22);
const finalTitle=group(ROOT,{zIndex:56});windowAt(finalTitle,9.18,10);
const finalClaude=text(finalTitle,'Claude',85,229,137,{letterSpacing:'-4px'}),finalRead=text(finalTitle,'lee la web.',87,379,96,{fontFamily:'Scholar',letterSpacing:'-3px'});reveal(finalClaude,9.18,.20,{x:-70});reveal(finalRead,9.28,.20,{y:40});
move(google,9.12,{y:-650},.18);
finish();
})();
