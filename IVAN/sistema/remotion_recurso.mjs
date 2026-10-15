import fs from 'node:fs';import path from 'node:path';import './confinar.mjs';
import {bundle} from '../.estado/herramientas/node_modules/@remotion/bundler/dist/index.js';
import {selectComposition,renderMedia} from '../.estado/herramientas/node_modules/@remotion/renderer/dist/index.js';
const root=path.resolve(import.meta.dirname,'..');process.chdir(root);process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp`;
const serveUrl=await bundle({entryPoint:path.join(root,'sistema/componentes.jsx'),outDir:path.join(root,'.estado/tmp/remotion_recurso'),enableCaching:false,publicDir:null,rootDir:path.join(root,'.estado/herramientas')});
const options={serveUrl,browserExecutable:'/usr/bin/google-chrome',chromiumOptions:{gl:'angle-egl'},logLevel:'error'};
const composition=await selectComposition({...options,id:'Circuito'});
await renderMedia({...options,composition,codec:'h264',outputLocation:path.join(root,'recursos/Circuito_analisis.mp4'),hardwareAcceleration:'required',concurrency:1,overwrite:true,videoBitrate:'14M'});
console.log('Recurso Remotion generado con NVENC: Circuito_analisis.mp4');
