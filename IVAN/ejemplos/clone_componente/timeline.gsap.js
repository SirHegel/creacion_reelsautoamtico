/* CLONE 1.600–3.200 s. Diseño SVG revisión2 aprobado e inmutable.
 * Tiempo local = tiempo original −1.600; 30fps, 48frames.
 * Valores y poses medidos en el video, no una plantilla de motion.
 */
document.fonts.ready.then(() => {
  if (!window.gsap) throw Error('GSAP local no disponible');
  const tl = gsap.timeline({paused:true, defaults:{ease:'none'}});
  const F = n => (n - 48) / 30;
  const names = ['notion','spotify','canva','duolingo','calendly','headspace'];
  const prices = [29,45,60,74,87,100,112,123,134,144,153,162,170,178,
    184,190,196,200,204,207,210,212,213,214];
  tl.addLabel('acumulacion',0).addLabel('cambio-frase',F(66))
    .addLabel('importe-completo',F(71)).addLabel('tachados',F(72))
    .addLabel('impacto',F(86)).addLabel('cancelled',F(88))
    .addLabel('asentamiento',F(90));

  // El mismo panel crece lentamente; la sacudida va en otra capa.
  tl.fromTo('#panel-camera',{scale:600/618,y:3,svgOrigin:'360 543.5'},
    {scale:1,y:0,duration:F(84),ease:'none'},0);
  tl.set('#subscriptions',{opacity:1},0);
  gsap.set('#stamp-motion',{opacity:0,scale:1,rotation:0,svgOrigin:'359.6 449.5'});
  gsap.set('#editorial-caption',{opacity:0,y:0});
  gsap.set('#caption-for',{opacity:0,y:22});
  tl.set('#caption-without',{opacity:1,y:0},0);
  tl.set('#panel-shake',{x:0,y:0},0);
  names.slice(1).forEach(name=>tl.set('#row-'+name,{opacity:0,y:30},0));
  names.slice(1).forEach((name,i)=>{
    // El frame previo es invisible, los cuatro siguientes suben y se fijan.
    const start=49+3*i;
    const poses=[{opacity:0,y:30},{opacity:.22,y:20},{opacity:.64,y:8},
      {opacity:.89,y:2},{opacity:.99,y:0},{opacity:1,y:0}];
    poses.slice(1).forEach((pose,j)=>tl.fromTo('#row-'+name,poses[j],
      {...pose,duration:1/30,immediateRender:false},F(start-1+j)));
  });

  // Contador continuo de los valores realmente leídos, con anchura óptica.
  const cost=document.querySelector('#cost');
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
  ctx.font='700 49px InterUI';
  const calibration=196/ctx.measureText('$214/mo').width;
  const widths=Object.fromEntries(prices.map(n=>[n,ctx.measureText('$'+n+'/mo').width*calibration]));
  const counter={value:29};
  const paintPrice=()=>{
    const n=Math.round(counter.value);
    cost.textContent='$'+n+'/mo';
    const width=widths[n]??ctx.measureText('$'+n+'/mo').width*calibration;
    cost.setAttribute('textLength',n===214?'196':width.toFixed(3));
  };
  paintPrice();
  prices.slice(1).forEach((value,i)=>tl.fromTo(counter,{value:prices[i]},
    {value,duration:1/30,onUpdate:paintPrice,immediateRender:false},i/30));
  // onUpdate de la timeline asegura también el contador en seeks inversos.
  tl.eventCallback('onUpdate',paintPrice);
  tl.set(cost,{attr:{fill:'#f5f5f6'}},0);
  tl.to(cost,{attr:{fill:'#ff4140'},duration:1/30},F(86));

  // Cambio tipográfico por desplazamiento/desenfoque local, como la fuente.
  tl.to('#caption-without',{opacity:0,y:-16,duration:1/30,ease:'power2.in'},F(64));
  tl.fromTo('#caption-for',{opacity:0,y:22,filter:'blur(3px)'},
    {opacity:1,y:0,filter:'blur(0px)',duration:3/30,ease:'power1.inOut',immediateRender:false},F(65));

  // Barridos medidos: los trazos recorren cada fila, no conectan logos.
  const ends = [
    [0,279,546,623,628,630],
    [0,351,573,627,630],
    [0,415,594,630],
    [0,469,609,630],
    [0,191,513,619,630],
    [0,279,547,625,630]
  ];
  const starts=[72,74,76,78,79,81];
  ends.forEach((values,i)=>{
    const line=document.querySelector('#cancel-line-'+i);
    const length=line.getTotalLength();
    tl.set(line,{strokeDasharray:length,strokeDashoffset:length,attr:{'stroke-opacity':1}},0);
    const offsets=values.map(end=>end===0?length:Math.max(0,630-Math.max(90,end)));
    offsets.slice(1).forEach((strokeDashoffset,j)=>tl.fromTo(line,
      {strokeDashoffset:offsets[j]},
      {strokeDashoffset,duration:1/30,immediateRender:false},F(starts[i]+j)));
    tl.to(line,{attr:{'stroke-opacity':.50},duration:3/30},F(86));
  });
  const dim=[1,.99,.96,.84,.75,.60,.51,.49,.50];
  dim.slice(1).forEach((opacity,j)=>tl.fromTo('#subscriptions',{opacity:dim[j]},
    {opacity,duration:1/30,immediateRender:false},F(82+j)));

  // Impacto real: traslaciones alternantes y flash medido de tres frames.
  const shakes=[{x:0,y:0},{x:14,y:-9},{x:-13,y:11},{x:7,y:-5},{x:-4,y:4},{x:0,y:0}];
  shakes.slice(1).forEach((pose,j)=>tl.fromTo('#panel-shake',shakes[j],
    {...pose,duration:1/30,immediateRender:false},F(85+j)));
  const flashes=[0,87/255,35/255,9/255,0];
  flashes.slice(1).forEach((opacity,j)=>tl.fromTo('#impact-flash',{opacity:flashes[j]},
    {opacity,duration:1/30,immediateRender:false},F(85+j)));
  tl.to('#caption-for',{opacity:0,y:-13,duration:1/30,ease:'power2.in'},F(86));
  const againPoses=[{opacity:0,y:22,filter:'blur(24px)'},
    {opacity:.12,y:16,filter:'blur(12px)'},
    {opacity:.75,y:4,filter:'blur(6px)'},
    {opacity:1,y:0,filter:'blur(1.5px)'},
    {opacity:1,y:0,filter:'blur(0px)'}];
  againPoses.slice(1).forEach((pose,j)=>tl.fromTo('#editorial-caption',againPoses[j],
    {...pose,duration:1/30,immediateRender:false},F(86+j)));

  // Sello: impacto desde primer plano, inclinación y asentamiento sin cambiar
  // el lettering, la caja, la posición o la rotación final aprobados.
  tl.set('#stamp-motion',{scale:2.1,rotation:5.67,opacity:0},F(87));
  tl.to('#stamp-motion',{scale:2,rotation:5.67,opacity:.30,duration:1/30},F(87));
  tl.to('#stamp-motion',{scale:1,rotation:0,opacity:1,duration:1/30,ease:'power3.out'},F(88));
  tl.to('#stamp-motion',{scale:1,rotation:0,opacity:1,duration:1/30,ease:'power2.out'},F(89));

  window.__timelines=window.__timelines||{};
  window.__timelines['clone-motion']=tl;
  window.__cloneEvidence={gsap:gsap.version,duration:1.6,sourceStart:1.6,
    designRevision:2,labels:tl.labels,tweens:tl.getChildren(true,true,false).length,
    motion:['reveal-filas','contador','barrido-tachados','sacudida-impacto','sello','cambio-tipografico']};
  tl.seek(0,false);
  window.renderReady=true;
});
