/* Contratos CPU de wrappers sobre builders reales, sin render/export/demos. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';

const ROOT=fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'));
if(path.basename(ROOT)!=='IVAN')throw Error('Sólo IVAN');
process.chdir(ROOT);
const TEMP=path.join(ROOT,'.estado/tmp/integration_production_contract');
fs.mkdirSync(TEMP,{recursive:true});
for(const k of ['cache','config','tmp'])fs.mkdirSync(path.join(TEMP,k),{recursive:true});
fs.mkdirSync(path.join(ROOT,'.estado/tmp/ic'),{recursive:true});
process.env.TMPDIR=`/proc/${process.pid}/cwd/.estado/tmp/ic`;process.env.XDG_CACHE_HOME=path.join(TEMP,'cache');process.env.XDG_CONFIG_HOME=path.join(TEMP,'config');
const hash=p=>createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const modules=fs.readdirSync('sistema/clone/components').filter(x=>x.endsWith('.js')).map(x=>'sistema/clone/components/'+x);
const protectedPaths=[...modules,'ejemplos/clone_componente/timeline.gsap.js','ejemplos/clone_componente/diseno.svg'];
const before=Object.fromEntries(protectedPaths.map(p=>[p,hash(p)]));
const python=spawnSync('python3',['-B','-c',"import json,sys;sys.path.insert(0,'sistema/clone');import engine;print(json.dumps(dict(fonts=engine.font_css(),assets=engine.bundled_assets('private_review'),definitions=engine.catalog(),cancelled=engine.cancelled_module())))"],
 {cwd:ROOT,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},maxBuffer:64*1024*1024});
if(python.status!==0)throw Error(python.stderr);
const payload=JSON.parse(python.stdout);
const {chromium}=await import(pathToFileURL(path.join(ROOT,'.estado/herramientas/node_modules/playwright/index.mjs')).href);
const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--disable-crash-reporter','--disable-breakpad']});
const report={scope:'CPU contract, native builders and adapter only; no pixel export or aesthetic approval',checks:[],errors:[]};
try{
 const page=await browser.newPage({viewport:{width:1080,height:1920}});
 await page.route('**/*',route=>route.abort());
 await page.setContent('<html><head><style>'+payload.fonts+'</style></head><body style="margin:0"><div id="fixture" style="width:1080px;height:1920px"></div></body></html>');
 await page.addScriptTag({content:fs.readFileSync('.estado/herramientas/node_modules/gsap/dist/gsap.min.js','utf8')});
 await page.addScriptTag({content:fs.readFileSync('sistema/clone/runtime.js','utf8')});
 for(const file of modules)await page.addScriptTag({content:fs.readFileSync(file,'utf8')});
 await page.addScriptTag({content:payload.cancelled});
 await page.addScriptTag({content:fs.readFileSync('sistema/clone/integration_layout.js','utf8')});
 await page.addScriptTag({content:fs.readFileSync('sistema/clone/integration_hook.js','utf8')});
 const checks=await page.evaluate(async payload=>{
  window.CLONE_ASSETS=payload.assets;
  await Promise.all(['700 30px Sequel','400 30px Scholar','400 30px InterUI','700 30px InterUI','400 30px Mono','700 30px Mono','400 30px JetBrains','700 30px JetBrains'].map(f=>document.fonts.load(f)));
  const result=[];
  for(const definition of payload.definitions){
   const root=document.getElementById('fixture');root.replaceChildren();
   const duration=definition.id==='composition_graph'?5:Math.max(3,definition.durationRange[0]),params=structuredClone(definition.defaults);
   if(definition.id==='composition_graph')params.steps.push(...params.nodes.map(n=>({at:4.3,duration:.4,op:'transform',target:n.id})));
   const built=Clone.build(definition.id,root,params,duration,'fixture-'+definition.id),C=built.context;
   for(const name of ['heading','caption','editorial-caption','caption-without','caption-for',...Array.from({length:5},(_,i)=>'caption'+i)])if(C.q(name))C.q(name).style.display='none';
   for(const text of root.querySelectorAll('text'))if(definition.defaults.caption&&text.textContent===definition.defaults.caption)text.style.display='none';
   const scene={id:'fixture-'+definition.id,start:0,duration,family:definition.id,params};
   let layout;
   try{const options={production:true,focus_windows:[],camera:[{state:'split',start_frame:0,end_frame:45,split_top:.5}],toNative:t=>t,split_top:.5,hook_end_frame:0,body_min_px:28,identity_min_px:72};layout=(definition.id==='composition_graph'?CloneIntegrationLayout:CloneIntegrationFamilyLayout)(C,built.tl,scene,options);}
   catch(error){
    if(/miniaturiza|demasiado pequeño/.test(error.message)){result.push({family:definition.id,status:'LEGIBILITY_REJECTED_BEFORE_RENDER',reason:error.message});continue;}
    throw error;
   }
   const sample=t=>{built.tl.seek(0,false);built.tl.seek(t,false);C.repaints.forEach(f=>f());layout.paint(t,t,1,.5);return root.querySelector('#'+CSS.escape(C.id('integration-native-frame'))).getAttribute('transform');};
   const expected=[.3,.7,1.2,2.4].map(sample),reverse=[2.4,1.2,.7,.3].map(sample).reverse(),random=[1.2,.3,2.4,.7].map(t=>[t,sample(t)]);
   if(JSON.stringify(expected)!==JSON.stringify(reverse)||random.some(([t,pose])=>pose!==expected[[.3,.7,1.2,2.4].indexOf(t)]))throw Error('Wrapper depends on seek order: '+definition.id);
   result.push({family:definition.id,status:'PASS',wrapper:layout.receipt.method,source_timeline_duration:built.tl.duration(),sample_count:layout.receipt.poses[0].samples});
  }
  {
   const root=document.getElementById('fixture');root.replaceChildren();
   const params={roles:[{role:'recon',label:'Observa tu trabajo'},{role:'architect',label:'Aprende tu estilo'},{role:'diff',label:'Mejora con el tiempo'}],count:3,result:'Mejora con el tiempo',reorganize:true};
   const original=JSON.stringify(params),built=Clone.build('pixel_agents',root,params,5.5,'observer'),C=built.context;
   const scene={id:'observer',family:'pixel_agents',params,duration:5.5,start:0};
   const helper=CloneIntegrationHook(C,scene,built.tl,{profile:'production_complete',instance_overrides:[{scene_id:'observer',kind:'pixel_functional_roles',hide_count:true,labels:['Observa','Aprende','Mejora'],reason:'Las tres funciones del plugin no se confunden con un equipo de tres agentes.'}]});
   for(const t of [0,.4,1.5,3,4.6,5.3,1.5,.4,4.6]){
    built.tl.seek(0,false);built.tl.seek(t,false);
    if(C.q('ghost').parentElement.getAttribute('opacity')!=='0')throw Error('Ghost count reappeared after native seek');
    const count=[...C.q('result').querySelectorAll('text')].find(n=>n.textContent==='3 ROLES COORDINADOS');
    if(count?.parentElement.getAttribute('opacity')!=='0')throw Error('Role count reappeared after native seek');
    ['Observa','Aprende','Mejora'].forEach((label,i)=>{const text=C.q('role-'+i).querySelector('text');if(text.textContent!==label||Number(text.getAttribute('font-size'))!==24)throw Error('Functional label not stable/readable after seek');});
   }
   if(JSON.stringify(params)!==original)throw Error('Functional override modified params');
   result.push({family:'pixel_agents',variant:'explicit_functional_instance',status:'PASS',independent_count_gates:true,original_params_unchanged:true,receipt:helper.receipt});
  }
  {
   const root=document.getElementById('fixture');root.replaceChildren();
   const params={role:'backend',title:'Claude · plugin',goal:'Capacidad descrita',caption:'Primera herramienta'},duration=196/30;
   const original=JSON.stringify(params),built=Clone.build('spotlight_agent',root,params,duration,'hook-contract'),C=built.context;
   for(const text of root.querySelectorAll('text'))if(text.textContent===params.caption)text.style.display='none';
   const scene={id:'hook',family:'spotlight_agent',params,duration,start:0},override={scene_id:'hook',kind:'spotlight_hook_identity',asset:'brand_claude_mark',painted_major_px:220,support_major_px:100,primary_until_frame:46,transform_frames:15,entrance_s:.3,
    reason:'La identidad inicial pasa a apoyo al comunicar la capacidad, sin otra copia de la marca.'};
   const cfg={profile:'production_complete',direction:{hook_end_frame:137,split_top:.5,camera_windows:[{split_top:.5}]},instance_overrides:[override]};
   const identity=CloneIntegrationSpotlightHook(C,scene,built.tl,cfg,{toNative:t=>t,toOutput:t=>t,hook_height_px:352});identity.paint(0);
   const layout=CloneIntegrationFamilyLayout(C,built.tl,scene,{production:true,camera:[{state:'split',start_frame:0,end_frame:75,split_top:.5}],toNative:t=>t,toOutput:t=>t,split_top:.5,hook_end_frame:137,body_min_px:28,identity_min_px:72,
    ...identity.layout_options,paint_instance:(_,t)=>identity.paint(t)});
   const sample=t=>{built.tl.seek(0,false);built.tl.seek(t,false);identity.paint(t);layout.paint(t,t,1,.5);const group=C.q('integration-official-hook');return{pose:group.getAttribute('transform'),alpha:group.getAttribute('opacity'),hero:C.q('integration-hook-gate-hero').getAttribute('opacity'),goal:C.q('integration-hook-gate-goal').getAttribute('opacity')};};
   const times=[0,.3,1.4,46/30,1.8,61/30,2.4,4.6,5.2],expected=times.map(sample),reverse=[...times].reverse().map(sample).reverse();
   if(JSON.stringify(expected)!==JSON.stringify(reverse))throw Error('Hook identity depends on seek order');
   if(expected[0].alpha!=='1'||expected[0].hero!=='0'||expected[0].goal!=='0')throw Error('Hook has empty/duplicate native start');
   if(expected[5].hero!=='1'||expected[5].goal!=='0')throw Error('Hook does not transform identity into support');
   const entries=identity.receipt.filter(r=>r.override==='entrance_duration_only');
   if(entries.length!==3||entries.some(r=>r.executed_native_start!==r.original_native_start||Math.abs(r.executed_output_duration-.3)>1e-7))throw Error('Hook changed phases rather than entrance durations');
   if(JSON.stringify(params)!==original)throw Error('Hook override modified params');
   const overlay=C.q('integration-official-hook');if(overlay.parentElement!==root.querySelector('svg'))throw Error('Brand is being rescaled with native body');
   if(overlay.querySelector('image').getAttribute('href')!==payload.assets.brand_claude_mark.data||overlay.querySelector('image').style.filter!=='none')throw Error('Brand bytes/filter are not authentic');
   result.push({family:'spotlight_agent',variant:'official_hook_instance',status:'PASS',seek_order_independent:true,original_params_unchanged:true,receipt:identity.receipt,layout:layout.receipt});
  }
  {
   const root=document.getElementById('fixture'),duration=3.5,params={role:'architect',title:'Claude Set Up',goal:'Módulo sintético de ejemplo',caption:'El cuarto plugin'};
   const words=['el','módulo','sintético','de','ejemplo.'].map((text,i)=>({text,start:10+i*.4,end:10+(i+1)*.4}));
   const captions=[{id:'caption_a',word_start:0,word_end:1,start_frame:300,end_frame:324},{id:'caption_b',word_start:2,word_end:4,start_frame:324,end_frame:360}];
   const variants=[{id:'literal_complete',profile:'production_complete',start:10,goal:params.goal,captions,suppress:true},
    {id:'partial_caption',profile:'production_complete',start:10,goal:params.goal,captions:captions.slice(0,1),suppress:false},
    {id:'paraphrase',profile:'production_complete',start:10,goal:'Módulo ficticio para ejemplo',captions,suppress:false},
    {id:'hook_context',profile:'production_complete',start:0,goal:params.goal,captions,suppress:false},
    {id:'legacy',profile:'legacy',start:10,goal:params.goal,captions,suppress:false}];
   for(const variant of variants){
    root.replaceChildren();const own={...params,goal:variant.goal},original=JSON.stringify(own),built=Clone.build('spotlight_agent',root,own,duration,'goal-'+variant.id),C=built.context;
    const scene={id:'goal-'+variant.id,family:'spotlight_agent',params:own,start:variant.start,duration},offset=variant.start-10;
    const ownWords=words.map(word=>({...word,start:word.start+offset,end:word.end+offset})),ownCaptions=variant.captions.map(block=>({...block,start_frame:block.start_frame+offset*30,end_frame:block.end_frame+offset*30}));
    const helper=CloneIntegrationHook(C,scene,built.tl,{profile:variant.profile,direction:{hook_end_frame:137,caption_blocks:ownCaptions},narration:{words:ownWords},instance_overrides:[]});
    const suppression=helper.receipt.find(r=>r.override==='source_caption_owns_literal_editorial_goal');
    if(!!suppression!==variant.suppress)throw Error('Goal ownership incorrectly inferred for '+variant.id);
    if(suppression&&(JSON.stringify(suppression.anchors.map(a=>a.word_index))!=='[1,2,3,4]'||suppression.caption_ids.length!==2))throw Error('Literal proof lacks actual word/caption coverage');
    for(const t of [0,.4,2.4,3.2,.4,3.2]){built.tl.seek(0,false);built.tl.seek(t,false);if(variant.suppress&&C.q('goal').parentElement.getAttribute('opacity')!=='0')throw Error('Suppressed editorial goal reappeared after native seek');}
    if(JSON.stringify(own)!==original||C.q('hero').parentElement.dataset.hookSuppressed||C.q('command').parentElement.dataset.hookSuppressed)throw Error('Goal suppression changed params/actor/command');
   }
   result.push({family:'spotlight_agent',variant:'literal_caption_goal_ownership',status:'PASS',cases:variants.map(v=>({id:v.id,suppressed:v.suppress})),only_goal_gate:true,original_params_unchanged:true,seek_order_independent:true});
  }
  {
   const definition=payload.definitions.find(d=>d.id==='composition_graph'),params=structuredClone(definition.defaults);
   // Resolver un resultado no necesariamente anima la posición de sus nodos.
   params.steps.forEach(step=>{if(step.op==='transform')step.op='resolve';});
   const root=document.getElementById('fixture');root.replaceChildren();
   const built=Clone.build('composition_graph',root,params,5,'static-contract'),C=built.context;
   const scene={id:'static-contract',family:'composition_graph',params,duration:5,start:0};
   const options={production:true,camera:[],focus_windows:[],split_top:.5,toNative:t=>t,hook_end_frame:0,body_min_px:28,identity_min_px:72};
   const layout=CloneIntegrationLayout(C,built.tl,scene,options),bindings=layout.receipt.verified_constant_native_pose_bindings;
   if(bindings.length!==2||bindings.some(r=>r.sampled_frames_and_boundaries<151||!r.changes_rejected))throw Error('Static positions were accepted without every-frame verification');
   const sample=t=>{built.tl.seek(0,false);built.tl.seek(t,false);layout.paint(t,t,0,.5);return params.nodes.map(n=>({matrix:C.q(n.id+'-position').getAttribute('transform'),alpha:C.q(n.id+'-position').getAttribute('opacity')})).concat(params.edges.map((_,i)=>({route:C.q('line'+i).getAttribute('d')})));};
   const times=[0,.7,1.4,2.7,4.5],forward=times.map(sample),reverse=[...times].reverse().map(sample).reverse();
   if(JSON.stringify(forward)!==JSON.stringify(reverse))throw Error('Verified static pose or route depends on seek order');
   root.replaceChildren();const modified=Clone.build('composition_graph',root,params,5,'invalid-static');
   modified.context.repaints.push(()=>{if(modified.tl.time()>1)modified.context.q('system-position').setAttribute('transform','translate(361 565) scale(1)');});
   let rejected=false;try{CloneIntegrationLayout(modified.context,modified.tl,{...scene,id:'invalid-static'},options);}catch(error){rejected=/pose sin target GSAP cambia/.test(error.message);}
   if(!rejected)throw Error('Unmapped changing position silently accepted as static');
   result.push({family:'composition_graph',variant:'verified_constant_native_positions',status:'PASS',every_frame_verification:true,changing_unmapped_pose_rejected:true,reverse_seeks_and_routes_stable:true,bindings});
  }
  return result;
 },payload);
 report.checks=checks;
}catch(error){report.errors.push(error.message);process.exitCode=1;}
finally{await browser.close();}
report.protected_source_unchanged=protectedPaths.every(p=>hash(p)===before[p]);
report.adapter_sha256=hash('sistema/clone/integration_layout.js');report.native_source_sha256=before;
report.status=!report.errors.length&&report.protected_source_unchanged?'PASS_CPU_CONTRACT_PENDING_ACTUAL_REEL_QA':'FAIL';
fs.writeFileSync(path.join(TEMP,'layout_checks.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
if(report.status==='FAIL')process.exitCode=1;
