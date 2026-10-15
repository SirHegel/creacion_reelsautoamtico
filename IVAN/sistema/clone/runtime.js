/* Runtime CLONE: instancias aisladas, coordenadas nativas720×1280.
   Fuente visual única; GSAP recibe el tiempo de HyperFrames, nunca un reloj. */
window.Clone = (() => {
  const definitions=new Map();
  const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function register(id,definition){
    if(definitions.has(id))throw Error('Componente duplicado: '+id);
    if(typeof definition.build!=='function')throw Error('Falta build: '+id);
    definitions.set(id,definition);
  }
  function context(root,params,duration,prefix){
    const repaints=[],usedAssets=new Set();
    const assets=window.CLONE_ASSETS||{},design=window.CLONE_DESIGN||{};
    const canvas=document.createElement('canvas'),measure=canvas.getContext('2d');
    const colors={paper:'#f4f4f3',ink:'#171719',secondary:'#737174',clay:'#db8a72',red:'#ff4140',green:'#42b95c',dark:'#1a191c',line:'#dfddda',...(design.runtime_colors||{})};
    const id=name=>prefix+'-'+name;
    const q=name=>root.querySelector('#'+CSS.escape(id(name)));
    const fit=(text,width,size=30,font='InterUI')=>{measure.font=`700 ${size}px ${font}`;return Math.min(size,size*width/Math.max(1,measure.measureText(String(text)).width));};
    const attr=o=>Object.entries(o).map(([k,v])=>`${k}="${escape(v)}"`).join(' ');
    const text=(x,y,value,options={})=>{
      const {size=30,font='InterUI',weight=700,fill=colors.ink,anchor='start',width,...more}=options;
      return `<text x="${x}" y="${y}" font-family="${font}" font-size="${width?fit(value,width,size,font):size}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}" ${attr(more)}>${escape(value)}</text>`;
    };
    const image=(key,x,y,width,height=width)=>{
      const a=assets[key];if(!a)throw Error('Recurso gráfico no disponible: '+key);usedAssets.add(key);
      return `<image x="${x}" y="${y}" width="${width}" height="${height}" href="${a.data}"/>`;
    };
    const sprite=(key,x,y,width=75)=>{const a=assets[key];if(!a)throw Error('Sprite original ausente: '+key);usedAssets.add(key);return `<image x="${x}" y="${y}" width="${width}" height="${width*a.height/a.width}" href="${a.data}" style="image-rendering:pixelated"/>`;};
    const defs=`<defs><filter id="${id('shadow')}" x="-30%" y="-40%" width="160%" height="190%" color-interpolation-filters="sRGB"><feDropShadow dx="0" dy="10" stdDeviation="13" flood-color="#000" flood-opacity=".16"/></filter><filter id="${id('soft')}" x="-30%" y="-40%" width="160%" height="190%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000" flood-opacity=".12"/></filter><linearGradient id="${id('editorial')}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f3dfd6"/><stop offset="1" stop-color="${colors.clay}"/></linearGradient></defs>`;
    const svg=inner=>`<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" viewBox="0 0 720 1280" color-interpolation-filters="sRGB">${defs}${inner}</svg>`;
    const editorial=(value,y=1150,size=64)=>text(360,y,value,{size,font:'Scholar',weight:400,fill:colors.clay,anchor:'middle',width:620});
    const counter=(tl,name,start,end,at,length,suffix='')=>{
      const node=q(name),state={value:start};if(!node)throw Error('Counter ausente '+name);
      const paint=()=>node.textContent=Math.round(state.value)+suffix;paint();repaints.push(paint);
      tl.fromTo(state,{value:start},{value:end,duration:length,ease:'power2.out',onUpdate:paint},at);
      return state;
    };
    const draw=(tl,name,at,length)=>{const node=q(name),len=node.getTotalLength();node.style.strokeDasharray=len;node.style.strokeDashoffset=len;tl.fromTo(node,{strokeDashoffset:len},{strokeDashoffset:0,duration:length,ease:'power2.out'},at);};
    const caption=()=>params.caption?editorial(params.caption):'';
    return {root,params,duration,prefix,id,q,text,image,sprite,svg,defs,editorial,counter,draw,caption,escape,colors,design,fit,repaints,usedAssets,shadow:`url(#${id('shadow')})`,soft:`url(#${id('soft')})`,t:n=>n*duration};
  }
  function build(family,root,params={},duration=4,prefix='component'){
    const definition=definitions.get(family);if(!definition)throw Error('Familia desconocida: '+family);
    const [lo,hi]=definition.durationRange||[1,15];if(duration<lo||duration>hi)throw Error('Duración fuera de límites: '+family);
    const input={...(definition.defaults||{}),...params};
    const ctx=context(root,input,duration,prefix);
    const tl=definition.build(ctx);
    if(!tl||typeof tl.seek!=='function')throw Error('Timeline inexistente: '+family);
    if(ctx.repaints.length){const prior=tl.eventCallback('onUpdate');tl.eventCallback('onUpdate',()=>{if(prior)prior();ctx.repaints.forEach(p=>p());});}
    // Inicializar cachés SVG/CSS de todos los tweens antes del primer frame.
    // Evita que una búsqueda inversa agregue por primera vez matrices/estilos
    // que modifican la rasterización de filtros respecto al arranque en frío.
    tl.seek(tl.duration(),false);tl.seek(0,false);
    return {tl,definition,context:ctx};
  }
  return {register,build,context,definitions,escape};
})();
