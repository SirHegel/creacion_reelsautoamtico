// Entorno exclusivo de las skills: npm, clones y escrituras permanecen en IVAN.
import './confinar.mjs';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {syncBuiltinESMExports} from 'node:module';
const root=path.resolve(import.meta.dirname,'..');
const inside=p=>p===root||p.startsWith(root+path.sep);
function guard(value,removeLink=false){
  if(typeof value==='number')return; // Descriptores ya abiertos, incluido stdout.
  let p=path.resolve(value instanceof URL?fileURLToPath(value):String(value));
  // Borrar/renombrar un enlace propio no escribe en su destino.
  if(removeLink){try{if(fs.lstatSync(p).isSymbolicLink())p=path.dirname(p);}catch{}}
  let ancestor=p;
  while(!fs.existsSync(ancestor))ancestor=path.dirname(ancestor);
  const canonical=path.join(fs.realpathSync(ancestor),path.relative(ancestor,p));
  if(!inside(canonical))throw new Error('Escritura de skills fuera de IVAN bloqueada: '+p);
}
const index={mkdir:0,mkdirSync:0,rm:0,rmSync:0,rmdir:0,rmdirSync:0,unlink:0,unlinkSync:0,
  writeFile:0,writeFileSync:0,appendFile:0,appendFileSync:0,truncate:0,truncateSync:0,
  chmod:0,chmodSync:0,chown:0,chownSync:0,utimes:0,utimesSync:0,
  copyFile:1,copyFileSync:1,cp:1,cpSync:1,symlink:1,symlinkSync:1,link:1,linkSync:1};
for(const [name,i] of Object.entries(index)){
  const original=fs[name];if(!original)continue;
  fs[name]=function(...args){guard(args[i],/^(rm|rmdir|unlink)/.test(name));return original.apply(this,args);};
}
for(const name of ['rename','renameSync']){
  const original=fs[name];fs[name]=function(...args){guard(args[0],true);guard(args[1],true);return original.apply(this,args);};
}
const writes=flags=>typeof flags==='number'?(flags&3)!==0||Boolean(flags&fs.constants.O_CREAT):/[wa+]/.test(flags??'r');
for(const name of ['open','openSync']){
  const original=fs[name];fs[name]=function(...args){if(writes(args[1]))guard(args[0]);return original.apply(this,args);};
}
const stream=fs.createWriteStream;fs.createWriteStream=function(...args){guard(args[0]);return stream.apply(this,args);};
for(const [name,i] of Object.entries(index).filter(([name])=>!name.endsWith('Sync'))){
  const original=fs.promises[name];if(!original)continue;
  fs.promises[name]=async function(...args){guard(args[i],/^(rm|rmdir|unlink)/.test(name));return original.apply(this,args);};
}
const rename=fs.promises.rename;fs.promises.rename=async function(...args){guard(args[0],true);guard(args[1],true);return rename.apply(this,args);};
const open=fs.promises.open;fs.promises.open=async function(...args){if(writes(args[1]))guard(args[0]);return open.apply(this,args);};
syncBuiltinESMExports();
for(const [key,relative] of Object.entries({TMPDIR:'.estado/tmp',npm_config_cache:'.estado/cache/npm',
  npm_config_userconfig:'.estado/config/npmrc',CLAUDE_CONFIG_DIR:'.estado/hyperframes/.claude',
  XDG_STATE_HOME:'.estado/hyperframes',GIT_CONFIG_GLOBAL:'.estado/config/git'})){
  process.env[key]=path.join(root,relative);
}
// Los instaladores lanzan otro proceso Node: también debe cargar este aislamiento.
process.env.NODE_OPTIONS='--import '+fileURLToPath(import.meta.url);
// Chrome usa sockets Unix de longitud limitada; este alias apunta al mismo TMPDIR.
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp`;
