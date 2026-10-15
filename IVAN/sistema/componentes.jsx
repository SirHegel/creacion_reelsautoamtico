import React from '../.estado/herramientas/node_modules/react';
import {AbsoluteFill,Composition,registerRoot,useCurrentFrame,interpolate,Easing} from '../.estado/herramientas/node_modules/remotion';
// Fondo explicativo reutilizable: fuentes se agrupan, el dato viaja y se convierte en un documento.
const Circuito=()=>{
 const f=useCurrentFrame(),phase=interpolate(f,[0,20,55,80,105],[0,.2,.6,.85,1],{extrapolateRight:'clamp',easing:Easing.inOut(Easing.cubic)});
 const coords=[[215,540],[805,570],[240,1230],[825,1200]];
 return <AbsoluteFill style={{background:'#101820',overflow:'hidden'}}>
  <svg width="1080" height="1920" viewBox="0 0 1080 1920"><defs><radialGradient id="glow"><stop stopColor="#456b82" stopOpacity=".5"/><stop offset="1" stopColor="#101820" stopOpacity="0"/></radialGradient><pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M 48 0 H 0 V 48" fill="none" stroke="#ffffff" strokeOpacity=".045"/></pattern></defs><rect width="1080" height="1920" fill="url(#grid)"/><ellipse cx={540+Math.sin(f/40)*80} cy="900" rx="800" ry="880" fill="url(#glow)"/>
   {coords.map(([x,y],i)=>{const t=(phase+i*.13)%1,cx=x+(540-x)*t,cy=y+(900-y)*t;return <g key={i}><path d={`M ${x} ${y} Q 540 ${y} 540 900`} fill="none" stroke="#89a8bd" strokeOpacity=".35" strokeWidth="3"/><rect x={x-62} y={y-46} width="124" height="92" rx="17" fill="#263744" stroke="#8cabb9" strokeOpacity=".4"/><path d={`M ${x-36} ${y-13} h 72 M ${x-36} ${y+8} h 46`} stroke="#d1dfe4" strokeWidth="7"/><circle cx={cx} cy={cy} r="11" fill="#eaf1f1"/></g>})}
   <g transform={`translate(540 900) rotate(${Math.sin(f/20)*3}) scale(${.9+phase*.13})`}><rect x="-175" y="-125" width="350" height="250" rx="35" fill="#eaf0f1"/><path d="M -110 -54 h 220 M -110 -13 h 146 M -110 28 h 188 M -110 69 h 116" stroke="#314957" strokeWidth="14" strokeLinecap="round"/></g>
  </svg>
 </AbsoluteFill>
};
registerRoot(()=> <Composition id="Circuito" component={Circuito} durationInFrames={108} fps={30} width={1080} height={1920}/>);
