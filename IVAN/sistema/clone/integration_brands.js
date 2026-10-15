/* Recursos oficiales en superficies nativas, por instancia de integración.
   Conserva archivos, timelines, posiciones y gestos CLONE; aumenta lectura.
   No selecciona familias ni representa una interfaz real de los productos. */
window.CloneIntegrationBrands = (C,scene,native,cfg={}) => {
 const changes=[],assets=window.CLONE_ASSETS,ns='http://www.w3.org/2000/svg';
 const graphOverride=(cfg.instance_overrides||[]).find(item=>item.scene_id===scene.id&&item.kind==='graph_brand_surface');
 if(graphOverride){
  if(cfg.profile!=='production_complete'||scene.family!=='composition_graph')throw Error('Superficie gráfica de marca fuera de contrato');
  const node=scene.params.nodes.find(n=>n.id===graphOverride.node_id),asset=assets[graphOverride.asset],group=C.q(node?.id);
  const image=group?.querySelector('image'),rect=group?.querySelector('rect'),label=C.q(node?.id+'-label'),body=C.q(node?.id+'-body'),meta=C.q(node?.id+'-meta');
  if(!node||node.asset!==graphOverride.asset||!asset||asset.kind!=='brand_logo'||image?.getAttribute('href')!==asset.data||!rect||!label||!body)throw Error('Tarjeta de marca original no verificable');
  const left=Number(rect.getAttribute('x')),width=Number(rect.getAttribute('width')),size=graphOverride.painted_major_native;
  const original=[...['x','y','width','height'].map(k=>Number(image.getAttribute(k)))],alpha=asset.alpha_bbox||[0,0,asset.width,asset.height];
  const visibleMajor=Math.max(alpha[2]-alpha[0],alpha[3]-alpha[1]),viewport=size*Math.max(asset.width,asset.height)/visibleMajor,cx=left+24+size/2,cy=-8;
  const textLeft=left+24+size+24,textRight=left+width-24,textWidth=textRight-textLeft,textX=(textLeft+textRight)/2;
  if(textWidth<300)throw Error('Marca oficial deja texto sin espacio móvil suficiente');
  Object.entries({x:cx-viewport/2,y:cy-viewport/2,width:viewport,height:viewport,preserveAspectRatio:'xMidYMid meet'}).forEach(([k,v])=>image.setAttribute(k,v));image.style.filter='none';
  const plate=document.createElementNS(ns,'rect');Object.entries({x:cx-size/2-10,y:cy-size/2-10,width:size+20,height:size+20,rx:18,fill:'#fff',filter:C.soft,'data-brand-surface':graphOverride.asset}).forEach(([k,v])=>plate.setAttribute(k,v));group.insertBefore(plate,image);
  for(const text of [label,body])text.setAttribute('x',textX);if(meta)meta.setAttribute('x',textLeft);
  const fullTexts=[node.body||'',...scene.params.steps.filter(s=>s.target===node.id&&['type','resolve','transform'].includes(s.op)&&s.text).map(s=>s.text)];
  const measure=document.createElement('canvas').getContext('2d');for(const [text,values]of [[label,[node.label]],[body,fullTexts]]){
   measure.font=`${text.getAttribute('font-weight')||400} ${text.getAttribute('font-size')}px ${text.getAttribute('font-family')}`;
   if(values.some(value=>measure.measureText(value).width>textWidth))throw Error('Marca oficial colisionaría con el texto original; revisar reencuadre');
  }
  changes.push({override:'graph_brand_surface',node_id:node.id,asset:graphOverride.asset,original_image_viewport:original,painted_major_native:size,
   original_file_sha256:asset.sha256,original_bytes_unchanged:true,icon_filter:'none',icon_rotation:0,container_shadow:'native_soft',text_rail:{left:textLeft,right:textRight,center:textX,width:textWidth},
   native_clock_and_actions_unchanged:true,source_params_unchanged:true,reason:graphOverride.reason});return{receipt:changes};
 }
 if(scene.family!=='radial_research')return {receipt:changes};
 function promote(group,key,size,label){
  const asset=assets[key];if(!asset||asset.kind!=='brand_logo')return;
  const image=group?.querySelector('image');if(!image)throw Error('Slot de marca sin imagen original');
  if(image.getAttribute('href')!==asset.data)throw Error('El slot no contiene el archivo oficial declarado');
  const x=Number(image.getAttribute('x')),y=Number(image.getAttribute('y'));
  const w=Number(image.getAttribute('width')),h=Number(image.getAttribute('height'));
  const cx=x+w/2,cy=y+h/2,b=asset.alpha_bbox||[0,0,asset.width,asset.height];
  // SVG image usa meet: considerar el padding auténtico del PNG, sin recortar
  // o editar sus bytes. Todas las marcas conservan su relación de aspecto.
  const visibleMajor=Math.max(b[2]-b[0],b[3]-b[1]);
  const viewport=size*Math.max(asset.width,asset.height)/visibleMajor;
  image.setAttribute('x',cx-viewport/2);image.setAttribute('y',cy-viewport/2);
  image.setAttribute('width',viewport);image.setAttribute('height',viewport);
  image.setAttribute('preserveAspectRatio','xMidYMid meet');image.style.filter='none';
  const plate=document.createElementNS(ns,'rect');
  const radius=size+20;
  Object.entries({x:cx-radius/2,y:cy-radius/2,width:radius,height:radius,rx:20,fill:'#fff',filter:C.soft,'data-brand-surface':key}).forEach(([k,v])=>plate.setAttribute(k,v));
  group.insertBefore(plate,image); // La sombra se aplica solo a la superficie.
  if(label){
   label.setAttribute('y',cy+radius/2+32);label.setAttribute('fill','#171719');
   label.setAttribute('font-size',C.fit(label.textContent,174,32,label.getAttribute('font-family')||'InterUI'));
  }
  changes.push({asset:key,source_viewport:[x,y,w,h],viewport:[cx-viewport/2,cy-viewport/2,viewport,viewport],painted_major_native:size,
   original_file_sha256:asset.sha256,original_bytes_unchanged:true,proportions_preserved:true,icon_filter:'none',container_shadow:'native_soft',timeline_modified:false});
 }
 C.params.sources.forEach((source,i)=>{
  const group=C.q('source'+i);promote(group,source.asset,96,group?.querySelector('text'));
 });
 const target=C.q('target');promote(target,C.params.target,112,target?.querySelector('text'));
 const n=C.params.sources.length,oldSpots=[[117,240],[603,240],[117,660],[603,660]];
 const slots=n===3?[[117,240],[603,240],[360,660]]:oldSpots.slice(0,n);
 const routes=[],tweens=native.getChildren(true,true,false);
 C.params.sources.forEach((source,i)=>{
  const old=oldSpots[i],pos=slots[i],group=C.q('source'+i);
  const wrapper=document.createElementNS(ns,'g');wrapper.id=C.id('integration-brand-slot-'+i);
  wrapper.setAttribute('transform',`translate(${pos[0]-old[0]} ${pos[1]-old[1]})`);
  group.parentNode.insertBefore(wrapper,group);wrapper.appendChild(group);
  const path=C.q('line'+i),circle=C.q('data'+i),originalLength=path.getTotalLength();
  const matching=tweens.filter(t=>t.vars.progress===1&&Math.abs(t.startTime()-C.t(.24+i*.035))<1e-6)
   .flatMap(t=>t.targets()).filter(t=>t&&!t.nodeType&&Number.isFinite(t.progress));
  const points=[...new Set(matching)];if(points.length!==1)throw Error('Progreso radial no verificable');
  // Puertos fuera del texto y de la superficie oficial; mismo destino, reloj
  // y curva cuadrática. El tercer recurso se alinea al eje, no deja un hueco.
  const start=[pos[0],pos[1]+(pos[1]<482?108:-68)],control=[pos[0],490],end=[360,482];
  path.setAttribute('d',`M${start[0]} ${start[1]} Q${control[0]} ${control[1]} ${end[0]} ${end[1]}`);
  const length=path.getTotalLength(),draw=tweens.find(t=>t.targets().includes(path)&&t.vars.strokeDashoffset===0);
  if(!draw)throw Error('Reloj de dibujo nativo no verificable');
  routes.push({path,circle,state:points[0],start,control,end,originalLength,length,drawAt:draw.startTime(),drawDuration:draw.duration(),drawEase:gsap.parseEase(draw.vars.ease)});
 });
 changes.push({override:'balanced_source_ports',source_count:n,positions:slots,native_progress_preserved:true,route:'quadratic_after_labels',timeline_modified:false});
 return {receipt:changes,paint(nativeTime){
  for(const r of routes){
   const k=Math.max(0,Math.min(1,r.state.progress)),u=1-k;
   r.circle.setAttribute('cx',u*u*r.start[0]+2*u*k*r.control[0]+k*k*r.end[0]);
   r.circle.setAttribute('cy',u*u*r.start[1]+2*u*k*r.control[1]+k*k*r.end[1]);
   const progress=Math.max(0,Math.min(1,(nativeTime-r.drawAt)/r.drawDuration));
   r.path.style.strokeDasharray=String(r.length);r.path.style.strokeDashoffset=String(r.length*(1-r.drawEase(progress)));
  }
 }};
};
