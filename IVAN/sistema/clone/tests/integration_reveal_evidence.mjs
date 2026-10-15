/* Regresión de las fronteras observadas en el reel completo. Comprueba la
   evidencia Chromium real vinculada al código congelado; no crea una demo. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=fs.realpathSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../../..'));
assert.equal(path.basename(root),'IVAN');
const inside=p=>{const file=fs.realpathSync(path.resolve(root,p));assert.ok(file.startsWith(root+'/'));return file;};
const read=p=>JSON.parse(fs.readFileSync(inside(p),'utf8'));
const digest=p=>createHash('sha256').update(fs.readFileSync(inside(p))).digest('hex');
const freeze=read(process.argv[2]||'.estado/tmp/production_runtime_freeze.json');
for(const [file,sha]of Object.entries(freeze.source_sha256))assert.equal(digest(file),sha,'Fuente distinta del freeze: '+file);
const proof=freeze.real_complete_index_boot;
assert.equal(digest(proof.receipt),proof.receipt_sha256,'Evidencia de otra ejecución');
const report=read(proof.receipt),frames=new Map(report.critical_frames.map(frame=>[frame.frame,frame]));
assert.equal(report.built,true);assert.deepEqual(report.errors,[]);assert.equal(report.mounted.length,10);
assert.equal(report.real_first_frames.status,'PASS');assert.deepEqual(report.real_first_frames.reverse_mismatches,[]);
assert.deepEqual(report.critical_reverse_mismatches,[],'La frontera depende del orden de seek');
const source=read('ejemplos/demo_produccion/integracion/scene.json');
const direction=read('ejemplos/demo_produccion/integracion/integration_plan.json');
const pauses=report.receipt.component_overrides.filter(item=>item.reason==='brief_type_pause_during_scene_reveal');
for(const id of ['c095','c131'])assert.ok(pauses.some(pause=>pause.text===id),'Sin corrección del fallo observado: '+id);
for(const pause of pauses){
 const scene=source.scenes.find(scene=>scene.id===pause.scene_id),block=direction.caption_blocks.find(block=>block.id===pause.text);
 assert.ok(scene&&block);assert.equal(pause.start_frame,Math.max(Math.round(scene.start*30),block.start_frame));
 assert.ok(pause.duration_s>0&&pause.duration_s<=.201);assert.ok(pause.end_frame_exclusive-pause.start_frame<=6);
 assert.equal(pause.source_words_and_P2_times_unchanged,true);
 assert.ok(pause.checked_frames.length>=2);assert.equal(pause.checked_frames.at(-1).covered,true);
 for(const sample of pause.checked_frames){assert.equal(sample.composited_surface_samples.length,9);
  assert.equal(sample.covered,sample.composited_surface_samples.every(point=>point.matches_incoming_luminance_class));}
 for(const word of pause.word_presence_after_pause)assert.ok(word.first_visible_frame<word.end_frame_exclusive,'Palabra omitida: '+word.text);
 for(let frame=pause.start_frame;frame<pause.end_frame_exclusive;frame++){
  assert.ok(frames.has(frame),'Falta captura de frontera: '+frame);
  assert.ok(!frames.get(frame).texts.some(text=>text.id==='integration-text-'+pause.text),'Texto sobre reveal incompleto: '+frame);
 }
 const restored=frames.get(pause.end_frame_exclusive);assert.ok(restored,'Falta restauración capturada');
 const caption=restored.texts.find(text=>text.id==='integration-text-'+pause.text);assert.ok(caption,'Caption sin restauración');
 assert.equal(caption.words.length,block.word_end-block.word_start+1,'Una palabra no volvió');
}
for(const frame of [828,830,831,1150,1151])assert.ok(frames.has(frame),'Falta fotograma observado: '+frame);
console.log(JSON.stringify({status:'PASS',scope:'Regresión de evidencia Chromium CPU del montaje real; no aprobación estética ni MP4',
 pauses:pauses.map(pause=>({text:pause.text,scene_id:pause.scene_id,frames:[pause.start_frame,pause.end_frame_exclusive],duration_s:pause.duration_s,words_preserved:pause.word_presence_after_pause.length}))},null,2));
