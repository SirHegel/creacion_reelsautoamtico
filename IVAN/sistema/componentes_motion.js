/* Fuentes conceptuales que leen, extraen y se transforman. Parámetros por narración. */
window.crearFuentesDinamicas=(A,sources,definitions)=>{
 const {el,text,windowAt,tl,move,travel}=A;const WHITE='#fafaf8';
 const fragments=[],panels=[];
 definitions.forEach((d,i)=>{
  const entry=d.entryTime??d.time-.15;
  const panel=el('div',sources,'',{left:d.x+'px',top:d.y+'px',width:'660px',height:'440px',background:'#f8f8f6',borderRadius:'15px',overflow:'hidden',color:'#181b21',zIndex:20+i,transformStyle:'flat',boxShadow:'0px 22px 36px rgba(0,0,0,.36)',border:'2px solid #fff'});
  panels.push(panel);
  const logo=el('div',panel,`<svg width="90" height="90" viewBox="0 0 96 96">${d.logo}</svg>`,{left:'40px',top:'35px'});
  const name=text(panel,d.name,155,54,72,{letterSpacing:'-2px'});
  if(d.entryTime!==undefined){windowAt(logo,d.time,6.38);windowAt(name,d.time,6.38);}
  const lines=[];
  for(let j=0;j<5;j++){
   const l=el('div',panel,'',{left:'43px',top:(160+j*41)+'px',width:(450-(j%3)*80)+'px',height:'11px',background:j===0?'#303641':'#b4b8bd',borderRadius:'2px',transformOrigin:'left center'});lines.push(l);
  }
  if(i===1){
   lines.slice(0,3).forEach(l=>l.style.visibility='hidden');
   const video=el('div',panel,'<svg width="74" height="74" viewBox="0 0 74 74"><path d="M21 13L21 61L59 37Z" fill="white"/></svg>',{left:'43px',top:'151px',width:'500px',height:'146px',background:'#303741',display:'flex',alignItems:'center',justifyContent:'center'});
   tl.fromTo(video,{clipPath:'inset(0% 100% 0% 0%)'},{clipPath:'inset(0% 0% 0% 0%)',duration:.18,ease:'power3.out'},d.time-.04);
   move(video,d.time+.24,{x:180,scaleY:.15,opacity:0},.3);
  }
  if(i===2){
   lines.slice(0,4).forEach(l=>l.style.visibility='hidden');
   for(let j=0;j<3;j++){
    const tile=el('div',panel,`<svg width="145" height="140" viewBox="0 0 145 140"><rect width="145" height="140" fill="${['#d9dce0','#c3c8ce','#aeb7c1'][j]}"/><circle cx="104" cy="36" r="12" fill="#f5f5f3"/><path d="M0 135L49 60L89 112L117 82L145 135Z" fill="#88929f"/></svg>`,{left:(43+j*177)+'px',top:'155px',width:'145px',height:'140px'});
    move(tile,d.time+.22+j*.05,{x:160+j*12,y:170,scale:.18,opacity:0},.35);
   }
  }
  const sweep=el('div',panel,'',{left:'0',top:'137px',width:'100%',height:'90px',background:'linear-gradient(0deg,rgba(20,27,40,.13),rgba(20,27,40,0))',borderBottom:'3px solid #18202a'});
  windowAt(panel,entry,6.38);
  tl.fromTo(panel,{x:650,y:130,skewX:-5,rotationZ:d.angle,scale:.74},{x:0,y:0,skewX:0,rotationZ:d.angle*.35,scale:1,duration:.28,ease:'power3.out'},entry);
  move(sweep,d.time,{y:230},.38);
  move(panel,d.time+.33,{x:-90,skewX:3,rotationZ:-d.angle,scale:.87},.30);
  move(panel,d.time+.60,{width:170,height:126,x:-160,y:-170,skewX:5,rotationZ:0,scale:.74},.28);
  lines.forEach((l,j)=>move(l,d.time+.18+j*.045,{x:180+j*20,opacity:0,scaleX:.65},.32));
  // Fragments quittent vraiment la source et alimentent le document final.
  for(let j=0;j<3;j++){
   const f=el('div',sources,'',{left:0,top:0,width:(160+j*45)+'px',height:'16px',background:WHITE,borderRadius:'3px',boxShadow:'0 3px 7px rgba(0,0,0,.2)'});
   const begin=d.time+.28+j*.10;windowAt(f,begin,6.45);travel(f,`M${d.x+100} ${d.y+180+j*40} C980 ${d.y+50} 900 1500 530 ${1300+j*30}`,begin,.66,32);fragments.push(f);
  }
 });
 return {panels,fragments};
};
