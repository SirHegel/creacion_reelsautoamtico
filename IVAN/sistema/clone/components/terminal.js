/* CLONE_017, 34.900–38.966667 s: comando → instalación → agentes → Ready.
   La ventana conserva la geometría interna observada a720×1280. `upper`
   conserva el emplazamiento del split; `full` la sitúa en el lienzo completo.
   Es una representación conceptual editable, nunca una instalación ejecutada.
   Los sprites son los recursos originales extraídos, no imágenes sustitutas. */
(() => {
  const roles=['recon','architect','design','build','backend','test','diff','entrepreneur','brand','launch','deploy'];
  const boundedText=(value,name,max=160)=>{
    if(typeof value!=='string')throw Error(name+' debe ser texto');
    if(value.length>max||/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value))throw Error(name+' excede el límite o contiene controles');
    return value;
  };
  function selectedRoles(value){
    if(!Array.isArray(value)||value.length<1||value.length>11)throw Error('roles requiere1–11 agentes');
    const out=value.map(item=>typeof item==='string'?{role:item,label:'/'+item}:{...item});
    const seen=new Set();
    out.forEach(item=>{
      if(!roles.includes(item.role))throw Error('Rol original desconocido: '+item.role);
      if(seen.has(item.role))throw Error('Rol repetido: '+item.role);
      seen.add(item.role);item.label=boundedText(item.label??'/'+item.role,'label',40);
    });
    return out;
  }
  function tween(tl,node,from,to,at){tl.fromTo(node,from,{...to,immediateRender:false},at);}
  const group=(C,name,content,extra='')=>`<g id="${C.id(name)}" ${extra}>${content}</g>`;

  Clone.register('terminal_install',{
    description:'Terminal CLONE: escritura, transferencia de datos, activación por rol, checks y resultado. UI conceptual; no ejecuta comandos.',
    durationRange:[2.8,14],
    source:{path:'recursos/B2_CLONE.mp4',start:34.9,end:38.966667},
    reference:[{file:'.estado/tmp/clone_inventario/frame_1056.png',time:35.2},{file:'.estado/tmp/clone_inventario/frame_1164.png',time:38.8}],
    defaults:{
      title:'Claude Code',workspace:'~/projects/my-clone',windowTitle:'claude',
      command:'https://github.com/Jakeschinariol/replica-skill',instruction:'install skill',
      roles,progressLabel:'Installing',packageLabel:'Replica skills',
      result:'Ready · try /replica-recon <app url>',caption:'INSTALA Y ACTIVA',
      placement:'full',showRoleLabels:false,exit:'lift'
    },
    parameters:{
      title:'cabecera,1–40caracteres',workspace:'ruta descriptiva,0–70caracteres',windowTitle:'nombre de ventana,0–30caracteres',
      command:'texto de comando,1–160caracteres; se escribe y distribuye en líneas sin recortar',
      instruction:'instrucción,0–90caracteres',roles:'1–11roles originales únicos, strings u objetos{role,label}',
      progressLabel:'acción del proceso,1–20caracteres',packageLabel:'objeto del proceso,0–30caracteres',
      result:'resultado proporcionado,1–90caracteres; representación conceptual',caption:'texto editorial opcional',
      placement:'full|upper: misma geometría interna, diferente posición vertical',showRoleLabels:'mostrar etiquetas cortas en variantes',exit:'lift|slide: salida preparada para enlazar otra composición'
    },
    build(C){
      const p=C.params,d=C.duration,list=selectedRoles(p.roles),n=list.length;
      for(const [name,max]of [['title',40],['workspace',70],['windowTitle',30],['command',160],['instruction',90],['progressLabel',20],['packageLabel',30],['result',90]]){
        boundedText(p[name],name,max);
        if(!['command','instruction'].includes(name)&&/[\r\n]/.test(p[name]))throw Error(name+' debe ocupar una sola línea');
      }
      if(!p.title.trim()||!p.command.trim()||!p.result.trim())throw Error('title,command,result no pueden estar vacíos');
      if(!['full','upper'].includes(p.placement))throw Error('placement debe ser full o upper');
      if(!['lift','slide'].includes(p.exit))throw Error('exit debe ser lift o slide');

      // Las líneas se fijan al construir: sin cambios de layout durante seek.
      // El punto de corte conserva exactamente el comando, también sus espacios.
      const fieldWidth=560,commandSize=17,mono='JetBrains';
      // hmtx del JetBrainsMono-400.woff2 local:600unidades/1000em.
      // Medir una fuente todavía no solicitada usaría el fallback del navegador.
      // El avance fijo mantiene el layout aunque el primer worker arranque en frío.
      const monoWidth=(value,size=commandSize)=>Array.from(value).reduce((width,char)=>width+(/\p{Mark}/u.test(char)?0:size*.6),0);
      const monoFit=(value,width,size)=>Math.min(size,size*width/Math.max(1,monoWidth(value,size)));
      const monoText=(x,y,value,options={})=>{
        const {width,size=17,...rest}=options;
        return C.text(x,y,value,{...rest,size:width?monoFit(value,width,size):size,font:mono});
      };
      const wrap=value=>{
        const out=[];let line='';
        for(const char of Array.from(value)){
          if(char==='\n'){out.push(line);line='';continue;}
          if(line&&monoWidth(line+char)>fieldWidth){out.push(line);line=char;}else line+=char;
        }
        out.push(line);return out;
      };
      const commandLines=wrap(p.command),instructionLines=p.instruction?wrap(p.instruction):[];
      const lines=[...commandLines,...instructionLines];
      if(lines.length>5)throw Error('Comando demasiado largo: dividir la instrucción en otra escena');
      const commandHeight=Math.max(75,27+lines.length*22);
      const overflow=commandHeight-75;
      const labelSpace=p.showRoleLabels?56:0;
      const panelY=p.placement==='upper'?80:308,panelHeight=480+overflow+labelSpace;
      const gridTop=319+overflow,gridBottom=399+overflow+(p.showRoleLabels?28:0);
      const topCount=n<=6?n:6,bottomCount=n-topCount;
      const spots=[];
      [topCount,bottomCount].forEach((count,row)=>{
        if(!count)return;
        const pitch=count===1?0:Math.min(104,520/(count-1));
        for(let col=0;col<count;col++)spots.push({x:360+(col-(count-1)/2)*pitch,y:row===0?gridTop:gridBottom});
      });
      const sourceTint='#d78b73',terminal='#171712',text='#e9e9df',muted='#96968c';
      const fieldY=154,installY=264+overflow,resultY=455+overflow+labelSpace;
      if(monoFit(p.result,576,20)<15)throw Error('Resultado demasiado extenso para una línea legible: resumir o dividir escena');
      const countX=71+monoWidth(p.progressLabel)+16;
      const packageX=countX+monoWidth(n+'/'+n)+16;
      const packageWidth=651-packageX;
      if(p.packageLabel&&monoFit(p.packageLabel,packageWidth,17)<15)throw Error('Etiquetas de proceso demasiado largas: resumir');
      let html=`<defs><clipPath id="${C.id('panel-clip')}"><rect x="27" y="0" width="666" height="${panelHeight}" rx="22"/></clipPath><clipPath id="${C.id('command-clip')}"><rect x="60" y="${fieldY+8}" width="592" height="${commandHeight-12}" rx="5"/></clipPath></defs><rect width="720" height="1280" fill="${C.colors.paper}"/>`;
      let inside=`<rect x="27" y="0" width="666" height="${panelHeight}" rx="22" fill="${terminal}" filter="${C.shadow}"/><g clip-path="url(#${C.id('panel-clip')})"><rect x="27" y="0" width="666" height="35" fill="#22221c"/><path d="M27 35H693" stroke="#2b2b25"/>`;
      [['#ef615b',46],['#f2c448',62],['#3cca54',78]].forEach(([fill,x])=>{inside+=`<circle cx="${x}" cy="17" r="5" fill="${fill}"/>`;});
      inside+=monoText(360,22,p.windowTitle,{size:12,weight:400,fill:muted,anchor:'middle','letter-spacing':1});
      inside+=`<rect x="49" y="57" width="622" height="79" rx="13" fill="none" stroke="${sourceTint}" stroke-width="1.5"/>${C.sprite('agent_base',81,96,39)}${monoText(150,93,p.title,{size:21,weight:700,fill:text,width:486})}${monoText(150,117,p.workspace,{size:14,weight:400,fill:muted,width:486})}`;
      inside+=`<rect id="${C.id('command-border')}" x="49" y="${fieldY}" width="622" height="${commandHeight}" rx="12" fill="none" stroke="#47483e" stroke-width="1.5"/>`;
      inside+=group(C,'field',`<g clip-path="url(#${C.id('command-clip')})">${monoText(64,fieldY+30,'>',{size:17,weight:400,fill:muted})}<rect id="${C.id('selection')}" x="84" y="${fieldY+12}" width="${Math.min(580,monoWidth(commandLines[0])+10)}" height="23" rx="4" fill="${sourceTint}" opacity=".25"/>${lines.map((line,i)=>monoText(i===0?87:64,fieldY+30+i*22,'',{size:commandSize,weight:400,fill:text,id:C.id('typed-'+i)})).join('')}<rect id="${C.id('cursor')}" x="87" y="${fieldY+14}" width="8" height="20" fill="${text}"/></g>`);
      inside+=group(C,'install',`<circle cx="56" cy="${installY-5}" r="4.5" fill="${sourceTint}"/>${monoText(71,installY,p.progressLabel,{size:17,weight:400,fill:text})}${monoText(countX,installY,'0/'+n,{size:17,weight:400,fill:text,id:C.id('count')})}${monoText(packageX,installY,p.packageLabel,{size:17,weight:400,fill:text,width:packageWidth})}<path d="M71 ${installY+10}H651" stroke="#33352c" stroke-width="2"/><path id="${C.id('rail')}" d="M71 ${installY+10}H651" stroke="${sourceTint}" stroke-width="2"/>`);
      list.forEach((item,i)=>{
        const point=spots[i],width=75,asset='agent_'+item.role;
        const metadata=window.CLONE_ASSETS[asset],spriteHeight=width*metadata.height/metadata.width;
        inside+=`<g transform="translate(${point.x} ${point.y})"><g id="${C.id('agent-'+i)}" opacity=".2"><title>${C.escape(item.label)}</title>${C.sprite(asset,-width/2,28-spriteHeight,width)}</g>`;
        inside+=group(C,'check-'+i,`<circle cx="37" cy="-28" r="10" fill="${C.colors.green}"/><path id="${C.id('tick-'+i)}" d="M33 -28l3 3 5-6" fill="none" stroke="#123c1d" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`);
        if(p.showRoleLabels)inside+=group(C,'role-'+i,monoText(0,56,item.label,{size:12,weight:400,fill:text,anchor:'middle',width:90}));
        inside+='</g>';
        const startX=93+(i%6)*93,startY=fieldY+commandHeight+5;
        const route=`M${startX} ${startY}C${startX} ${startY+23} ${point.x} ${point.y-69} ${point.x} ${point.y-31}`;
        inside+=`<path id="${C.id('flow-path-'+i)}" d="${route}" fill="none" stroke="none"/><rect id="${C.id('packet-'+i)}" x="-2.5" y="-2.5" width="5" height="5" rx="1" fill="${sourceTint}" opacity="0"/>`;
      });
      inside+=group(C,'ready',`<path id="${C.id('ready-tick')}" d="M51 ${resultY-6}l3 3 7-10" fill="none" stroke="${C.colors.green}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>${monoText(74,resultY,p.result,{size:20,weight:700,fill:C.colors.green,width:576})}`);
      inside+='</g>';
      html+=`<g transform="translate(0 ${panelY})">${group(C,'window',inside)}</g>`;
      // Clay ligeramente más oscuro para superar3:1 en el lienzo claro medido.
      if(p.caption)html+=group(C,'caption',C.text(360,1150,String(p.caption),{size:64,font:'Scholar',weight:400,fill:'#d16f54',anchor:'middle',width:620}));
      C.root.innerHTML=C.svg(html);

      const tl=gsap.timeline({paused:true});
      const phases={entry:0,command:d*.12,action:d*.52,reaction:d*.59,result:d*.81,exit:d*.94};
      Object.entries(phases).forEach(([name,time])=>tl.addLabel(name,time));
      tl.addLabel('typed',d*.49).addLabel('all_active',d*.80);
      tl.set(C.q('install'),{opacity:0,y:6},0);
      tl.set(C.q('rail'),{scaleX:0,svgOrigin:`71 ${installY+10}`},0);
      tl.set(C.q('selection'),{opacity:0},0);
      tl.set(C.q('ready'),{opacity:0,y:5},0);
      tween(tl,C.q('window'),{scale:.965,y:40,opacity:0,svgOrigin:`360 ${panelHeight/2}`},{scale:1,y:0,opacity:1,duration:Math.min(.3,d*.1),ease:'power3.out'},0);
      if(p.caption)tween(tl,C.q('caption'),{y:30,opacity:0},{y:0,opacity:1,duration:Math.min(.26,d*.08),ease:'power3.out'},d*.09);

      // Escritor: mismo texto y cursor para seeks adelante, atrás o discontinuos.
      const chars=lines.map(line=>Array.from(line)),offsets=[];let total=0;
      chars.forEach(line=>{offsets.push(total);total+=line.length;});
      const writer={value:0};
      const paintCommand=()=>{
        const typed=Math.max(0,Math.min(total,Math.floor(writer.value+1e-6)));
        let activeLine=0,visible=0;
        chars.forEach((line,i)=>{
          const count=Math.max(0,Math.min(line.length,typed-offsets[i]));
          C.q('typed-'+i).textContent=line.slice(0,count).join('');
          if(typed>=offsets[i]){activeLine=i;visible=count;}
        });
        const cursor=C.q('cursor');
        const partial=chars[activeLine].slice(0,visible).join('');
        cursor.setAttribute('x',(activeLine===0?87:64)+monoWidth(partial)+2);
        cursor.setAttribute('y',fieldY+14+activeLine*22);
      };
      paintCommand();C.repaints.push(paintCommand);
      tl.fromTo(writer,{value:0},{value:total,duration:d*.37,ease:'none',immediateRender:false,onUpdate:paintCommand,onComplete:paintCommand,onReverseComplete:paintCommand},phases.command);
      const blinkCount=Math.max(1,Math.floor(d*.37/.3)-1);
      tl.fromTo(C.q('cursor'),{opacity:1},{opacity:.15,duration:.15,ease:'none',repeat:blinkCount,yoyo:true,immediateRender:false},phases.command);
      tl.to(C.q('cursor'),{opacity:0,duration:.08,ease:'none'},d*.49);
      tl.to(C.q('selection'),{opacity:.25,duration:.12,ease:'none'},d*.49);
      tl.to(C.q('command-border'),{attr:{stroke:sourceTint},duration:.14,ease:'power2.out'},d*.49);
      tl.to(C.q('install'),{opacity:1,y:0,duration:.18,ease:'power2.out'},phases.action);

      // El contador sigue únicamente los agentes realmente activados de esta lista.
      const counter={value:0},paintCounter=()=>{C.q('count').textContent=Math.max(0,Math.min(n,Math.floor(counter.value+1e-6)))+'/'+n;};
      paintCounter();C.repaints.push(paintCounter);
      list.forEach((item,i)=>{
        const at=d*.59+(i/Math.max(1,n-1))*d*.16;
        const travelDuration=Math.min(.28,d*.085),packet=C.q('packet-'+i),travel={value:0};
        const sx=93+(i%6)*93,sy=fieldY+commandHeight+5,point=spots[i];
        const paintPacket=()=>{
          const a=1-travel.value,b=travel.value;
          const x=a*a*a*sx+3*a*a*b*sx+3*a*b*b*point.x+b*b*b*point.x;
          const y=a*a*a*sy+3*a*a*b*(sy+23)+3*a*b*b*(point.y-69)+b*b*b*(point.y-31);
          packet.setAttribute('transform',`translate(${x} ${y})`);
        };
        paintPacket();C.repaints.push(paintPacket);
        tl.set(packet,{opacity:.8},at-travelDuration);
        tl.fromTo(travel,{value:0},{value:1,duration:travelDuration,ease:'none',immediateRender:false,onUpdate:paintPacket,onComplete:paintPacket,onReverseComplete:paintPacket},at-travelDuration);
        tl.to(packet,{opacity:0,duration:.08,ease:'power2.out'},at);
        tween(tl,C.q('agent-'+i),{opacity:.2,y:6,scale:.96,svgOrigin:'0 8'},{opacity:1,y:-5,scale:1.025,duration:.13,ease:'power3.out'},at);
        tl.to(C.q('agent-'+i),{y:0,scale:1,duration:.16,ease:'sine.inOut'},at+.13);
        const countDuration=Math.min(.07,d*.16/Math.max(1,n-1)*.8);
        tl.fromTo(counter,{value:i},{value:i+1,duration:countDuration,ease:'none',immediateRender:false,onUpdate:paintCounter,onComplete:paintCounter,onReverseComplete:paintCounter},at);
        tl.set(C.q('check-'+i),{scale:0,opacity:0,svgOrigin:'37 -28'},0);
        tl.to(C.q('check-'+i),{scale:1,opacity:1,duration:.12,ease:'power3.out'},at+.01);
        C.draw(tl,'tick-'+i,at+.04,.09);
        if(p.showRoleLabels){tl.set(C.q('role-'+i),{opacity:.2},0);tl.to(C.q('role-'+i),{opacity:1,duration:.12},at);}
      });
      tl.to(C.q('rail'),{scaleX:1,duration:d*.2,ease:'none'},d*.58);
      tl.to(C.q('ready'),{opacity:1,y:0,duration:.2,ease:'power3.out'},phases.result);
      C.draw(tl,'ready-tick',phases.result+.04,.13);
      tl.to(C.q('command-border'),{attr:{stroke:'#656a51'},duration:.17,ease:'power2.out'},d*.82);
      // Conserva Ready legible en la cola: salida de movimiento, sin frame negro.
      tl.to(C.q('window'),{y:p.exit==='slide'?-110:-34,scale:p.exit==='slide'?.98:1.018,duration:d*.06,ease:'power2.inOut'},phases.exit);
      if(p.caption)tl.to(C.q('caption'),{y:-12,duration:d*.06,ease:'power2.inOut'},phases.exit);
      return tl;
    }
  });
})();
