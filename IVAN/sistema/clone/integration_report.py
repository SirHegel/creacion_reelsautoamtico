"""Entregables de integración vinculados a render, inferencias y QA actuales."""
import argparse,copy,json,pathlib,sys,zipfile,hashlib
from fractions import Fraction
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import engine as e
from integration import folders

def _production_file(path,sha=None):
    file=e.w.inside(path)
    if not file.is_file() or file.is_symlink():raise ValueError('Archivo de producción ausente o no canónico: '+str(path))
    current=e.digest(file)
    if sha is not None and current!=sha:raise ValueError('Archivo de producción obsoleto: '+str(path))
    return {'path':str(file.relative_to(e.ROOT)),'sha256':current,'bytes':file.stat().st_size}

def _production_inverse(scene,mapping,value):
    """Inversa del reloj realmente ejecutado; los holds no causan división por cero."""
    for a,b in zip(mapping,mapping[1:]):
        if a['v']<=value<=b['v'] and b['v']>a['v']:
            return scene['start']+a['t']+(value-a['v'])*(b['t']-a['t'])/(b['v']-a['v'])
    if mapping and abs(value-mapping[-1]['v'])<1e-7:return scene['start']+mapping[-1]['t']
    raise ValueError('Acción fuera del reloj ejecutado: '+scene['id'])

def _production_proofs(spec,direction):
    proofs={}
    for name,path in [('scene',spec['planner']['proof']),('direction',direction['inference']['provider_proof'])]:
        record=_production_file(path);proof=e.load(e.w.inside(path))
        if proof.get('real_inference')is not True or proof.get('returncode')!=0:raise ValueError('Falta inferencia real de producción: '+name)
        # No copiar respuestas, prompts completos, credenciales ni cachés privadas.
        proofs[name]={**record,'receipt':{k:proof[k]for k in ('provider','real_inference','returncode','elapsed_s','prompt_sha256','response_sha256','schema_sha256','isolation')if k in proof}}
    return proofs

def _production_context(raw_id):
    _,folder=folders(raw_id);project=e.load(folder/'proyecto.json')
    if project.get('revision')!='production':raise ValueError('El proyecto no es una producción completa')
    spec=e.load(folder/'scene.json');direction=e.load(folder/'integration_plan.json');narr=e.load(folder/'narration.json')
    qc=e.load(folder/'integration_qc.json');browser=e.load(folder/'production_complete_browser_qc.json');visual=e.load(folder/'VISUAL_QA.json')
    fingerprint=e.source_fingerprint(folder);source=fingerprint['sha256'];mp4=folder/project['output_name'];sha=_production_file(mp4)['sha256']
    original=_production_file(project['original']['path'],project['original']['sha256'])
    media=e.w.probe(original['path']);video=next(s for s in media['streams']if s['codec_type']=='video');audio=next(s for s in media['streams']if s['codec_type']=='audio')
    frames=int(video.get('nb_frames',0));fps=float(Fraction(video['avg_frame_rate']));duration=frames/fps;voice_duration=float(audio['duration'])
    if frames!=project['frames'] or fps!=project['fps'] or abs(duration-project['duration'])>1e-6:raise ValueError('La configuración no conserva el crudo completo')
    if frames<=0 or abs(voice_duration-narr['duration'])>.001:raise ValueError('Duración de narración distinta del audio original')
    cursor=0
    for scene in spec['scenes']:
        if abs(scene['start']-cursor)>1e-6:raise ValueError('El storyboard tiene un hueco o solapamiento')
        cursor=scene['start']+scene['duration']
    if abs(cursor-duration)>1e-6:raise ValueError('El storyboard no cubre la duración completa')
    if qc.get('source_sha256')!=source or qc.get('final_mp4_sha256')!=sha:raise ValueError('Render completo obsoleto')
    if qc.get('decoded_all_frames')is not True or qc.get('frames')!=frames or qc.get('no_extension')is not True:raise ValueError('Render sin prueba de todos los fotogramas del original')
    if qc.get('hardware_gpu')is not True or qc.get('nvenc')is not True:raise ValueError('Falta la ejecución GPU/NVENC documentada para esta producción')
    if abs(qc.get('video_duration',-1)-duration)>1e-6 or abs(qc.get('audio_duration',-1)-voice_duration)>.05:raise ValueError('Render con duración modificada')
    exported=e.w.probe(mp4);export_video=next(s for s in exported['streams']if s['codec_type']=='video');export_audio=next(s for s in exported['streams']if s['codec_type']=='audio')
    if export_video.get('codec_name')!='h264' or export_audio.get('codec_name')!='aac' or (export_video.get('width'),export_video.get('height'))!=(1080,1920) or float(Fraction(export_video['avg_frame_rate']))!=fps or int(export_video.get('nb_frames',0))!=frames:raise ValueError('Export distinto de H.264/AAC 1080×1920/FPS y fotogramas originales')
    if browser.get('mode')!='all_frames' or browser.get('frame_count')!=frames or not browser.get('checks') or not all(v is True for v in browser['checks'].values()) or browser.get('errors'):raise ValueError('QA completo de producción pendiente o fallido')
    if browser.get('source_after',{}).get('sha256')!=source or browser.get('source_before',{}).get('sha256')!=source:raise ValueError('La fuente cambió durante el QA')
    export=browser.get('export_binding',{})
    if export.get('status')!='bound_to_verified_render' or export.get('sha256')!=sha or export.get('source_sha256')!=source:raise ValueError('QA no vinculado al MP4 completo actual')
    renderproof=export.get('render_receipt',{})
    _production_file(renderproof.get('path',''),renderproof.get('sha256'))
    if not browser.get('proofs'):raise ValueError('Faltan capturas verificables del QA')
    for proof in browser['proofs']:_production_file(proof['path'],proof['sha256'])
    if visual.get('mp4_sha256')!=sha or visual.get('composition_sha256')!=source:raise ValueError('Revisión visual de otro candidato completo')
    inspected=visual.get('inspection',{}).get('all_consecutive_frames',visual.get('all_consecutive_frames'))
    if inspected!=frames:raise ValueError('Falta inspección visual consecutiva del export completo')
    if 'blocking_unresolved_count'not in visual:raise ValueError('La revisión visual debe declarar bloqueos pendientes')
    for key in ('sheets','full_resolution_captures'):
        for path in visual.get('inspection',{}).get(key,[]):_production_file(path)
    for reference in visual.get('inspection',{}).get('reference_comparisons',[]):
        if reference.get('comparison'):_production_file(reference['comparison'])
        if reference.get('source'):_production_file(reference['source'],reference.get('source_sha256'))
    preservation=browser.get('preservation',{})
    if preservation.get('baseline_match')is not True or preservation.get('unchanged')is not True or preservation.get('failed'):raise ValueError('No se preservó la biblioteca protegida')
    mix=project.get('audio_mix');audio_mix=browser.get('audio_mix',{})
    if not mix or qc.get('audio_original_bit_exact')is not False or qc.get('original_voice_stem_unchanged')is not True:raise ValueError('Falta mezcla verificada con stem de voz conservado')
    _production_file(mix['path'],mix['sha256']);_production_file(mix['provenance_path'],mix['provenance_sha256'])
    if audio_mix.get('output_sha256')!=mix['sha256'] or audio_mix.get('receipt_sha256')!=mix['provenance_sha256']:raise ValueError('QA de audio de otra mezcla')
    proof=audio_mix.get('provenance',{})
    if proof.get('original_source_sha256')!=original['sha256'] or proof.get('original_voice_stem_unchanged')is not True or proof.get('voice_gain_db')!=0 or proof.get('voice_rate')!=1 or proof.get('voice_start_offset_samples')!=0:raise ValueError('El recibo no conserva la voz con ganancia/velocidad/offset originales')
    if proof.get('music_used')is not False or proof.get('audio_original_bit_exact')is not False:raise ValueError('La mezcla tiene condiciones no verificadas')
    _production_file(proof['plan_path'],proof['plan_sha256'])
    for fx in proof['sources_and_actions']:_production_file(fx['path'],fx['sha256'])
    return folder,project,spec,direction,narr,qc,browser,visual,fingerprint,original,voice_duration,sha

def build_production(raw_id):
    """Entrega completa desde recibos vigentes; no promueve aprobación estética."""
    folder,project,spec,direction,narr,qc,browser,visual,fingerprint,original,voice_duration,sha=_production_context(raw_id)
    source=fingerprint['sha256'];receipt=browser['integration_receipt'];metrics=browser['metrics'];fps=project['fps']
    proofs=_production_proofs(spec,direction);e.write(folder/'planner_evidencias.json',proofs)
    assets=e.load(e.HERE/'assets.json');brand_registry=e.load(e.HERE/'brand_assets.json')['assets'];assets={**assets,**brand_registry}
    overrides=receipt.get('component_overrides',[]);families=list(dict.fromkeys(s['family']for s in spec['scenes']))
    registry={'schema_version':2,'generated':e.w.utc(),'scope':'produccion_completa','mp4_sha256':sha,'composition_sha256':source,'family_selection':'Dos inferencias reales; selección de familias conservada.','families':[],'broll_used':[],'camera':original,'voice':'Stem original con gain 0 dB, rate 1 y offset 0; mezcla AAC nueva con FX.','native_modules_modified':False,'native_preservation':browser['preservation'],'instance_overrides':project.get('instance_overrides',[]),'executed_overrides':overrides,'fonts':browser.get('fonts',{}),'brand_context':project.get('brand_context','private_review'),'social_publication_authorized_by_this_report':False}
    for scene in spec['scenes']:
        component=next((c for c in receipt['components']if c['scene_id']==scene['id']),None)
        if component is None:raise ValueError('Familia sin recibo ejecutado: '+scene['id'])
        references=list(dict.fromkeys(component.get('used_assets',[])));used=[]
        for key in references:
            if key not in assets:raise ValueError('Recurso ejecutado sin procedencia: '+key)
            asset=assets[key];_production_file(asset.get('path',asset.get('archivo')),asset['sha256']);used.append({'key':key,**asset})
        clock=next((r for r in overrides if r.get('scene_id')==scene['id']and'map'in r),None)
        if clock is None:raise ValueError('Escena sin mapa de ejecución: '+scene['id'])
        actions=[]
        for action in scene['params'].get('steps',[]):
            actions.append({**action,'executed_start':_production_inverse(scene,clock['map'],action['at']),'executed_end':_production_inverse(scene,clock['map'],action['at']+action['duration'])})
        registry['families'].append({'scene_id':scene['id'],'family':scene['family'],'start':scene['start'],'duration':scene['duration'],'objective':scene['objective'],'content':scene['content'],'semantic_reason':scene.get('semantic_reason',''),'visual_reason':scene.get('visual_reason',''),'params':scene['params'],'assets':used,'executed_actions':actions,'clock':clock})
    # El logo de hook puede ser un override YO y no figurar en el recibo nativo.
    observed_brands=metrics.get('brands',[])
    observed_brand_ids=list(dict.fromkeys(key for row in observed_brands for key in row.get('assets',[])))
    registry['brands_actually_observed']=[{'key':key,**brand_registry[key]}for key in observed_brand_ids]
    for key in observed_brand_ids:_production_file(brand_registry[key]['path'],brand_registry[key]['sha256'])
    e.write(folder/'componentes_utilizados.json',registry)
    audio=browser['audio_mix']['provenance'];issues=visual.get('issues',[])
    blockers=[i for i in issues if i.get('severity')in ('critical','major','blocking','blocker')and i.get('resolved_status')!='resolved']
    pending=[i.get('observed',i.get('description',i.get('id','')))for i in issues if i.get('resolved_status')!='resolved']
    pending+=['La revisión técnica y visual no equivale a aprobación estética del usuario ni a igualdad literal con YO/CLONE.','Las ventanas, personajes y diagramas son representaciones animadas del contenido; no son grabaciones de ejecución real de los plugins.','Las cifras y ventajas proceden del narrador; las condiciones documentales se recogen en BRAND_RESOLUTION.md, sin convertirlas en resultados probados.','Los logos auténticos se preparan en contexto private_review; la descarga y este informe no autorizan publicación social.','La música queda excluida: ninguna de las cinco pistas tiene una licencia comercial comprobada registrada.','Las fuentes internas de CLONE son aproximaciones documentadas. Sequel real se usa para el tratamiento YO; Scholar está disponible sin obligación de introducir énfasis artificial.','Los recibos de audio verifican muestras, gain, tiempos y picos; no certifican escucha ni balance sonoro perceptivo.']
    result={'schema_version':2,'generated':e.w.utc(),'status':'needs_correction'if blockers or visual['blocking_unresolved_count']or visual['status']=='necesita_correccion'else 'ready_for_user_review','aesthetic_approval':False,'scope':'production_complete','original':original,'mp4_path':str((folder/project['output_name']).relative_to(e.ROOT)),'mp4_sha256':sha,'composition_sha256':source,'duration_image_s':project['duration'],'duration_audio_s':voice_duration,'frames':project['frames'],'fps':fps,'scenes':len(spec['scenes']),'families':families,'camera_fraction':metrics['presence_fraction'],'max_visible_camera_seconds':metrics['max_continuous_frames']/fps,'camera_visible_frames':metrics['total_visible_frames'],'native_components_preserved':browser['preservation'],'native_modules_modified':False,'instance_overrides':project.get('instance_overrides',[]),'original_audio_bit_exact':False,'original_voice_stem_unchanged':True,'audio_mix':project['audio_mix'],'executed_fx':audio['sources_and_actions'],'music_used':False,'technical_checks':browser['checks'],'visual_review_status':visual['status'],'blocking_unresolved_count':max(visual['blocking_unresolved_count'],len(blockers)),'visual_issues':issues,'pending':pending,'inferences':proofs,'evidence':{'render':_production_file(folder/'integration_qc.json'),'browser':_production_file(folder/'production_complete_browser_qc.json'),'visual':_production_file(folder/'VISUAL_QA.json'),'captures':browser['proofs']},'fonts':browser.get('fonts',{}),'publication_context':'private_review'}
    e.write(folder/'INFORME_FINAL.json',result)
    _production_storyboard(folder,project,narr,direction,receipt,registry,audio,source,sha)
    camera_fraction=metrics['presence_fraction']*100;max_camera=metrics['max_continuous_frames']/fps
    lines=['# Reel Ascendia: producción completa','',f"`{project['output_name']}` conserva {project['frames']} fotogramas a {fps} FPS: {project['duration']:.3f} s de imagen y {voice_duration:.6f} s de audio. El crudo original permanece incluido en el editable.",'',f"{len(spec['scenes'])} escenas y {len(families)} familias elegidas por inferencias reales: {', '.join(families)}. Presencia medida del presentador: {camera_fraction:.2f} %, con máximo continuo de {max_camera:.3f} s, contando entradas y salidas. Las proporciones reales de split se detallan en STORYBOARD_FINAL.md.",'','## Qué se verificó','',f"QA completo de {project['frames']} fotogramas, fuente y export vinculados por SHA. {browser['preservation']['count']} archivos protegidos de la biblioteca y proyectos anteriores permanecen intactos. Los ajustes por instancia se registran en componentes_utilizados.json; no sustituyen la elección del planner.",'','Voz original sin retime, cambio de orden, gain, EQ, compresor ni limiter. Se sumaron FX selectivos a otro bus y se codificó una mezcla AAC nueva: los paquetes finales no son idénticos al AAC original. El final se cotejó con esa mezcla y su procedencia. Música excluida por falta de licencia comercial comprobada.','',f"Revisión visual del MP4: **{visual['status']}**. Estado para entrega: **{result['status']}**. Aprobación estética del usuario: pendiente.",'','## Límites y pendientes','']+['- '+p for p in pending]+['','## Editable y reproducción','','El ZIP conserva las rutas relativas a IVAN, el crudo, HTML/GSAP/CSS/JSON, componentes, fuentes, recursos realmente empleados y el recibo de mezcla. Excluye el MP4 de entrega, proxies de cámara regenerables, fotogramas/cachés, credenciales, modelos y demos anteriores. Restaurar sobre una copia de IVAN o en el IVAN actual conservando rutas; se reutiliza la instalación existente. No se instala software.','','El proxy H.264 sin pérdida y la extracción AAC original se regeneran desde original.mp4 con `prepare`; se omiten para evitar duplicar el crudo. El fingerprint corresponde al proyecto verificado instalado y el manifiesto distingue estos medios regenerables de los archivos incluidos. Después de editar, regenerar render/QA; los informes anteriores no aprueban cambios.','','```bash',f'python3 -B sistema/clone/integration.py prepare {raw_id}',f'python3 -B proyectos/{raw_id}/mezclar_sonido.py --plan proyectos/{raw_id}/audio_plan.json',f'python3 -B sistema/clone/integration.py compile {raw_id}',f'python3 -B sistema/clone/integration.py render {raw_id}',f'node sistema/clone/tests/production_complete_browser.mjs {raw_id}','```','','La mezcla ya entregada se usa sin volver a generarla; el comando de mezcla permite reconstruirla desde su plan. Revisar el nuevo MP4 antes de reconstruir informe/ZIP: VISUAL_QA.json debe corresponder a su nuevo SHA.','',f"SHA-256 MP4: `{sha}`.",f"Composición: `{source}`.",'']
    (folder/'INFORME_FINAL.md').write_text('\n'.join(lines),encoding='utf-8')
    return result

def _production_storyboard(folder,project,narr,direction,receipt,registry,audio,source,sha):
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    fps=project['fps'];words=narr.get('words',[])
    lines=['# Storyboard final Ascendia','',f"{project['frames']} fotogramas, {project['duration']:.3f} s, {fps} FPS. Derivado de SceneIR, dirección YO y recibo ejecutado; no es un plan alternativo escrito a mano.",'','## Escenas y narración','']
    for scene in registry['families']:
        start=scene['start'];end=start+scene['duration'];spoken=' '.join(w.get('word',w.get('text',''))for w in words if start-.001<=w['start']<end-.001)
        lines.extend([f"### {scene['scene_id']} · {start:.3f}–{end:.3f} s · {scene['family']}",'',f"Narración alineada: {spoken or scene['content']}",'',f"Objetivo: {scene['objective']}",'',f"Elección semántica: {scene['semantic_reason']}",'',f"Composición: {scene['visual_reason']}",''])
        if scene['assets']:lines.extend(['Recursos nativos: '+', '.join(a['key']for a in scene['assets'])+'.',''])
        if scene['executed_actions']:
            lines.extend(['| Tiempo final | Acción | Componentes | Texto/valor declarado |','|---|---|---|---|'])
            for a in scene['executed_actions']:lines.append(f"| {a['executed_start']:.3f}–{a['executed_end']:.3f} s | {cell(a['op'])} | {cell(a.get('from',''))} → {cell(a.get('to',a.get('target','')))} | {cell(a.get('text',a.get('value','')))} |")
            lines.append('')
        else:
            lines.extend(['La familia ejecuta su timeline nativa. El reloj monótono y los cues aplicados constan en componentes_utilizados.json; no se inventan pasos discretos que el componente no declara.',''])
        cues=[k for k in scene['clock']['map']if 'cue_id'in k]
        if cues:
            lines.extend(['| Cue de voz ejecutado | Tiempo final | Tiempo nativo | Ancla narrada |','|---|---|---|---|'])
            for cue in cues:
                anchor=words[cue['word']]if isinstance(cue.get('word'),int)and 0<=cue['word']<len(words)else{}
                lines.append(f"| {cell(cue['cue_id'])} · {cell(cue['kind'])} | {scene['start']+cue['t']:.3f} s | {cue['v']:.3f} s | {cell(anchor.get('text',anchor.get('word','')))} |")
            lines.append('')
    lines.extend(['## Cámara auténtica','','| Tiempo | Composición | Motivo |','|---|---|---|'])
    for c in direction['camera_windows']:
        split=c.get('split_top',direction.get('split_top',.5));composition=c['state']+(f" {split*100:.0f}/{(1-split)*100:.0f}"if c['state']=='split'else'')
        lines.append(f"| {c['start_frame']/fps:.3f}–{c['end_frame']/fps:.3f} s | {composition} | {cell(c['reason'])} |")
    lines.extend(['','Las ventanas incluyen transiciones. La presencia y los intervalos contiguos se miden sobre la composición ejecutada, no se cuentan solo planos de cámara completa.','','## Textos ejecutados','','| Tiempo | Texto | Tratamiento/tamaño |','|---|---|---|'])
    for t in receipt.get('text_blocks',[]):lines.append(f"| {t['start_frame']/fps:.3f}–{t['end_frame']/fps:.3f} s | {cell(t['text'])} | {cell(t.get('font',''))} · {cell(t.get('placement','narration'))} · {t.get('font_size',0):.0f} px |")
    lines.extend(['','Fuente real y pose/sombra/legibilidad comprobadas por QA y revisión visual. Las excepciones dinámicas y la información del hook permanecen en integration_plan.json y el recibo.','','## Diseño sonoro ejecutado','','| Culmen | Recurso | Gain solicitado | Acción visual |','|---|---|---|'])
    for fx in audio['sources_and_actions']:lines.append(f"| {fx['impact_time']:.3f} s | {fx['resource_id']} | {fx['requested_gain_db']:.1f} dB | {cell(fx['visual_action'])} |")
    lines.extend(['',f"Bus FX: atenuación adicional {audio['fx_bus_extra_gain_db']:.1f} dB; voz a gain 0 dB, rate 1 y offset 0. Sin música. El culmen se vincula a una acción real del reloj; la verificación de muestras no implica escucha perceptiva.",'',f"MP4: `{sha}`. Composición: `{source}`.",''])
    (folder/'STORYBOARD_FINAL.md').write_text('\n'.join(lines),encoding='utf-8')

def package_production(raw_id):
    """Un ZIP de fuentes y medios necesarios; sin proxies, renders ni cachés."""
    _,folder=folders(raw_id);report=build_production(raw_id)
    if report['status']!='ready_for_user_review' or report['blocking_unresolved_count']!=0:raise ValueError('No empaquetar una producción con defectos visuales bloqueantes')
    project=e.load(folder/'proyecto.json');fingerprint=e.source_fingerprint(folder);allowed=set();regenerable=[]
    def add(path,optional=False):
        file=e.w.inside(path)
        if not file.is_file():
            if optional:return
            raise ValueError('Dependencia del editable ausente: '+str(path))
        if file.is_symlink():raise ValueError('Dependencia no canónica en editable: '+str(path))
        if '.estado'in file.relative_to(e.ROOT).parts or 'node_modules'in file.relative_to(e.ROOT).parts:raise ValueError('No incluir cachés o credenciales en el editable')
        allowed.add(file)
    # HTML/JS/CSS/JSON canónicos, informes y recibos; no incluir imágenes de QA.
    for file in folder.iterdir():
        if file.is_file()and file.suffix in ('.html','.css','.js','.mjs','.json','.md')and not any(tag in file.name for tag in ('failure','_failure','entrega_','paquete_manifest')):add(file)
    for file in (folder/'diagnostico_yo').glob('*'):
        if file.is_file()and file.suffix in ('.json','.md'):add(file)
    add(folder/'media/provenance.json')
    for comparison in e.load(folder/'VISUAL_QA.json').get('inspection',{}).get('reference_comparisons',[]):
        if comparison.get('comparison'):add(comparison['comparison'])
    for relative in fingerprint['files']:
        file=e.w.inside(relative)
        if file.is_relative_to(folder/'media')and file.name in ('camera.mp4','voice_original.m4a'):
            regenerable.append(_production_file(file,fingerprint['files'][relative]));continue
        add(file)
    add(project['original']['path'])
    for name in ('mezclar_sonido.py','comparar_referencias.py','audio_plan.json','REFERENCIAS_PRODUCCION.md','REFERENCIAS_PRODUCCION.json','BRAND_RESOLUTION.md','brand_resolution.json'):add(folder.parent/name)
    mix=e.load(e.w.inside(project['audio_mix']['provenance_path']));add(project['audio_mix']['path']);add(project['audio_mix']['provenance_path']);add(folder.parent/'recursos/sonido/audio_mix.json')
    # El quick se sustituye por el QA final; el plan conserva un recibo de reloj
    # inmutable dentro del proyecto, para verificar los cues sin una caché privada.
    sound_plan=e.load(e.w.inside(mix['plan_path']))
    clock_receipt=sound_plan.get('action_clock_binding',{}).get('basis_runtime_receipt_path')
    if clock_receipt:add(clock_receipt)
    for fx in mix['sources_and_actions']:add(fx['path'])
    registry=e.load(folder/'componentes_utilizados.json')
    for scene in registry['families']:
        for asset in scene['assets']:add(asset.get('path',asset.get('archivo')))
    for asset in registry['brands_actually_observed']:add(asset['path'])
    # Catálogos/compiladores editables son pequeños; nada de galerías, renders o demos.
    for file in e.HERE.iterdir():
        if file.is_file()and file.suffix in ('.py','.js','.mjs','.json','.md'):add(file)
    for file in (e.HERE/'components').glob('*.js'):add(file)
    add(e.HERE/'tests/production_complete_browser.mjs')
    for name in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md','STYLE_YO.md','INTEGRACION_YO.md','sistema/workflow.py','sistema/skills.py','sistema/skills_entorno.mjs','sistema/skills_instaladas.json','sistema/perfil.json','recursos/gsap.min.js'):add(name)
    for definition in e.load(e.HERE/'assets.json').values():add(definition['path'])
    # El catálogo registra CANCELLED aun si no lo elige este reel. Se necesitan
    # sus fuentes aprobadas para recompilar el catálogo; no se incluyen sus MP4.
    for name in ('index.html','diseno.svg','timeline.gsap.js','proyecto.json'):add(e.ROOT/'ejemplos/clone_componente'/name)
    for file in (e.ROOT/'ejemplos/clone_componente/assets').glob('*'):
        if file.is_file()and file.suffix in ('.png','.svg','.ttf','.woff2'):add(file)
    for file in (e.ROOT/'.agents/skills').rglob('*'):
        if file.is_file()and(file.suffix in ('.md','.json','.py','.js','.mjs','.yaml','.yml','.woff2','.ttf','.otf')or file.name.lower().startswith(('ofl','license','licence','notice','copyright'))):add(file)
    # Son las fuentes locales que usa font_css(), incluyendo pesos reales.
    for name in ('recursos/Sequel_Sans_Bold_Disp.ttf','recursos/Scholar_Italic.ttf','recursos/Inter-Regular.ttf','recursos/Inter-Bold.ttf','recursos/JetBrainsMono-Regular.ttf','recursos/JetBrainsMono-Bold.ttf'):add(name,optional=True)
    font_files=[]
    for file in (e.ROOT/'recursos').rglob('*'):
        if file.is_file()and file.suffix in ('.ttf','.woff2','.otf'):font_files.append(file)
    for file in font_files:add(file)
    # Recompilar requiere los bytes auténticos del registro, no logos sustitutivos.
    for asset in e.load(e.HERE/'brand_assets.json')['assets'].values():add(asset['path'])
    files=sorted(allowed);records=[_production_file(file)for file in files]
    if sum(r['path']==project['original']['path']for r in records)!=1:raise ValueError('Crudo ausente o duplicado en el editable')
    omitted_media={str((folder/'media'/name).relative_to(e.ROOT))for name in ('camera.mp4','voice_original.m4a')}
    if any(r['path']in omitted_media or r['path'].endswith(project['output_name'])for r in records):raise ValueError('Un proxy/render se duplicaría en el editable')
    manifest=folder/'paquete_manifest.json';e.write(manifest,{'schema_version':2,'generated':e.w.utc(),'scope':'production_complete','mp4_sha256':report['mp4_sha256'],'composition_sha256':report['composition_sha256'],'files':records,'regenerable_media_omitted':regenerable,'regeneration_command':f'python3 -B sistema/clone/integration.py prepare {raw_id}','excluded':['MP4 de entrega y renders','proxy lossless de cámara','extracción AAC original regenerable','fotogramas y cachés','.estado y credenciales','node_modules, modelos y herramientas','demos anteriores'],'requirements':'Restaurar rutas relativas en IVAN; reutilizar instalación local existente. prepare reconstruye proxy/extracción desde el crudo incluido. compile/render invalidan QA anterior.'})
    target=folder/'ascendia_reel_editable.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
        for file in files:archive.write(file,str(file.relative_to(e.ROOT)))
        archive.write(manifest,str(manifest.relative_to(e.ROOT)))
    with zipfile.ZipFile(target)as archive:
        if archive.testzip():raise ValueError('ZIP corrupto')
        if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Rutas repetidas en el ZIP')
        for record in records:
            if hashlib.sha256(archive.read(record['path'])).hexdigest()!=record['sha256']:raise ValueError('Miembro del ZIP alterado')
    return {'path':str(target.relative_to(e.ROOT)),'bytes':target.stat().st_size,'sha256':e.digest(target),'verified_members':len(records)+1,'original_included_once':True,'camera_proxy_omitted':True,'aesthetic_approval':False}

def build(raw_id):
    _,folder=folders(raw_id);project=e.load(folder/'proyecto.json')
    if project.get('revision')=='production':return build_production(raw_id)
    spec=e.load(folder/'scene.json');direction=e.load(folder/'integration_plan.json');narr=e.load(folder/'narration.json')
    qc=e.load(folder/'integration_qc.json');browser=e.load(folder/'integration_browser_qc.json');visual=e.load(folder/'VISUAL_QA.json')
    source=e.source_fingerprint(folder)['sha256'];mp4=folder/project['output_name'];sha=e.digest(mp4)
    if qc['source_sha256']!=source or qc['final_mp4_sha256']!=sha:raise ValueError('Render obsoleto')
    if browser['mode']!='all_frames' or browser.get('frame_count')!=project['frames'] or not all(browser['checks'].values()) or browser['source_after']['sha256']!=source or browser['export_binding']['sha256']!=sha:raise ValueError('QA de navegador incompleto u obsoleto')
    if visual['mp4_sha256']!=sha or visual['composition_sha256']!=source:raise ValueError('Revisión visual de otro candidato')
    receipt=browser['integration_receipt'];metrics=browser['metrics'];families=list(dict.fromkeys(s['family']for s in spec['scenes']))
    proofs={}
    for name,path in [('scene',spec['planner']['proof']),('direction',direction['inference']['provider_proof'])]:
        proof=e.load(e.w.inside(path));
        if not proof.get('real_inference')or proof.get('returncode')!=0:raise ValueError('Falta inferencia real')
        proofs[name]={'path':path,'sha256':e.digest(e.w.inside(path)),'receipt':{k:proof[k]for k in ('provider','real_inference','returncode','elapsed_s','prompt_sha256','response_sha256','schema_sha256','isolation')if k in proof}}
    e.write(folder/'planner_evidencias.json',proofs)
    registry={'schema_version':1,'mp4_sha256':sha,'composition_sha256':source,'family_selection':'planner vigente, inferencia real; adaptador sin sustitución de escenas','families':[], 'broll_used':[], 'voice':'AAC original, paquetes idénticos', 'camera':project['original'],'text_font':'Sequel Sans Bold Disp','emphasis_font_used':False,'native_modules_modified':False}
    assets=e.load(e.HERE/'assets.json')
    for scene in spec['scenes']:
        references=next(c['used_assets']for c in receipt['components']if c['scene_id']==scene['id'])
        registry['families'].append({'scene_id':scene['id'],'family':scene['family'],'start':scene['start'],'duration':scene['duration'],'reason':scene['semantic_reason'],'visual_reason':scene['visual_reason'],'actions':scene['params'].get('steps',scene.get('actions',[])),'assets':[{'key':key,**assets[key]}for key in dict.fromkeys(references)]})
    e.write(folder/'componentes_utilizados.json',registry)
    lines=['# Storyboard automático CLONE + YO','',f"Fuente original: `{raw_id}`. Imagen: {project['duration']} s/{project['frames']} fotogramas; audio: {project['source_audio_duration']} s. Sin ampliación.",'','Las familias y las ventanas/textos proceden de dos inferencias reales. La geometría se adapta a las acciones existentes. Este documento se genera desde sus JSON y el recibo ejecutado.','', '## Familia y objetivo','']
    for scene in spec['scenes']:
        lines.extend([f"**{scene['id']} · {scene['family']} · {scene['start']:.3f}–{scene['start']+scene['duration']:.3f} s.**",scene['semantic_reason'],'',scene['visual_reason'],''])
    lines.extend(['## Cámara original','','| Inicio–fin | Composición | Motivo del director automático |','|---|---|---|'])
    for c in direction['camera_windows']:lines.append(f"| {c['start_frame']/30:.3f}–{c['end_frame']/30:.3f} s | {c['state']} | {c['reason']} |")
    lines.extend(['','La presencia cuenta juntas las ventanas contiguas, incluyendo entradas y salidas. El split estable tiene división y1056: 55 % motion/45 % cámara auténtica.','', '## Texto ejecutado','','| Inicio–fin | Texto | Tratamiento |','|---|---|---|'])
    for t in receipt['text_blocks']:lines.append(f"| {t['start_frame']/30:.3f}–{t['end_frame']/30:.3f} s | {t['text']} | {'Hook de frase acumulativa'if t.get('placement')=='hook'else 'Subtítulo de narración'} · {t['font_size']:.0f}px |")
    lines.extend(['','Rojo exclusivamente en «furioso», por provocación atribuida en la narración. Sequel real; Scholar está disponible pero este director no la eligió.','', '## Acciones sincronizadas','','| Intervalo de voz | Acción ejecutable | Entidades |','|---|---|---|'])
    for s in spec['scenes']:
        rec=next(x for x in receipt['component_overrides']if x.get('scene_id')==s['id']and'map'in x);mapping=rec['map']
        def inverse(value):
            for a,b in zip(mapping,mapping[1:]):
                if a['v']<=value<=b['v']:return s['start']+a['t']+(value-a['v'])*(b['t']-a['t'])/(b['v']-a['v'])
            raise ValueError('Acción fuera del mapa')
        for a in s['params'].get('steps',[]):lines.append(f"| {inverse(a['at']):.3f}–{inverse(a['at']+a['duration']):.3f} s | {a['op']} | {a.get('from','')} → {a.get('to',a.get('target',''))} |")
    lines.extend(['','El remapeo es monótono, con límites de velocidad comprobados. Las transiciones de cámara, reflujo y texto se ejecutan en el reloj, no solo como metadata. Audio: pista original, sin mezcla adicional en este test.',''])
    (folder/'auto_storyboard.md').write_text('\n'.join(lines))
    pending=[i['observed']for i in visual.get('issues',[])if i.get('severity')=='minor'and i.get('resolved_status')!='resolved']+['La aprobación estética corresponde al usuario; un PASS técnico no equivale a fidelidad perfecta con CLONE o YO.',
      'Este caso seleccionó una sola familia; todavía no demuestra integración con cámara de las quince familias ni continuidad entre familias distintas.',
      'Las fuentes de CLONE siguen siendo aproximaciones documentadas. Sequel del texto YO es la fuente original disponible.',
      'El director no eligió Scholar en esta secuencia. No se añade por obligación.',
      'El gráfico representa conceptualmente las afirmaciones originales; no demuestra scraping real, enfado de Google ni gratuidad de acceso a todas las plataformas.',
      'La ASR reconoció Cloud; se normalizó a Claude por contexto previo. No se afirma verificación por escucha.',
      'Sin música/riser/FX añadidos: se conserva AAC bit a bit. El diseño sonoro adicional sigue pendiente.',
      'Para nuevos crudos falta conectar ingestión y detección facial al adaptador; en esta prueba se usaron anclas del mismo crudo comprobadas sobre fotogramas.']
    result={'schema_version':1,'generated':e.w.utc(),'status':'delivered_for_user_review','aesthetic_approval':False,'source_sha256':project['original']['sha256'],'mp4_sha256':sha,'composition_sha256':source,'duration_image_s':project['duration'],'duration_audio_s':project['source_audio_duration'],'frames':project['frames'],'family_selection':families,'original_audio_bit_exact':qc['audio_original_bit_exact'],'max_visible_camera_seconds':metrics['max_continuous_frames']/30,'camera_fraction':metrics['presence_fraction'],'native_components_preserved':browser['preservation'],'technical_checks':browser['checks'],'compatibility_notices':browser.get('compatibility_notices',[]),'font_loading_verified':browser.get('font_loading_verified',{}),'visual_review_status':visual['status'],'visual_issues':visual.get('issues',[]),'pending':pending,'inferences':proofs}
    e.write(folder/'INFORME_INTEGRACION.json',result)
    description=['# Primera integración CLONE + YO','',f"El archivo `{mp4.name}` conserva {project['frames']} fotogramas, {project['duration']} s de imagen y {project['source_audio_duration']} s de audio. El sufijo 10s no amplía el crudo.",'',f"Planner real: {', '.join(families)}. No se cambiaron sus familias a mano. Dirección YO automática: hook por frases, cámara completa breve y dos apariciones split 55/45; presencia observada {metrics['presence_fraction']*100:.2f} %, máxima continua {metrics['max_continuous_frames']/30:.3f} s.",'','## Validación técnica','', 'Todos los fotogramas decodificados; timeline directa/inversa y seeks desordenados; fuente de cámara correcta por frame; máscara 55/45; texto centrado y anclado a barbilla; palabras cubiertas con pausas tipográficas registradas. H.264/AAC a 1080×1920/30 FPS. Captura GPU y NVENC utilizados. Paquetes AAC idénticos al original. Sin blur de relleno, vídeo duplicado, stock ni clips externos.','',f"{browser['preservation']['count']} archivos de biblioteca/demos protegidos: {browser['preservation']['unchanged']}. Los módulos originales permanecen intactos.",'','## Revisión visual','',f"Estado de la revisión independiente: **{visual['status']}**. Consultar `VISUAL_QA.json`, fotogramas consecutivos y comparaciones. La revisión técnica no certifica igualdad estética con las referencias.",'','## Problemas corregidos','']+['- '+i['observed']for i in visual.get('issues',[])if i.get('resolved_status')=='resolved']+['','## Mejoras y límites pendientes','']+['- '+p for p in pending]+['','## Proyecto y reproducción','','`index.html` contiene la timeline GSAP editable. `scene.json` es el plan original y `integration_plan.json` su dirección YO; `auto_storyboard.md`, `componentes_utilizados.json` y `planner_evidencias.json` documentan decisiones y ejecución. El ZIP conserva las rutas relativas a IVAN y todos los medios del test, sin credenciales, modelos o herramientas nuevas. El HTML/GSAP es editable y usa sus dependencias incluidas; la reproducción por CLI reutiliza la instalación y los estados de validación existentes en este IVAN. No se incluye la caché privada de inferencias.','', 'Desde IVAN:','',f'```bash\npython3 -B sistema/clone/integration.py plan {raw_id}\npython3 -B sistema/clone/integration.py compile {raw_id}\npython3 -B sistema/clone/integration.py render {raw_id}\nnode sistema/clone/tests/integration_browser.mjs {raw_id}\n```','',f"SHA-256 del MP4: `{sha}`. Composición: `{source}`.",'']
    (folder/'INFORME_INTEGRACION.md').write_text('\n'.join(description));return result

def package(raw_id):
    _,production_folder=folders(raw_id)
    if e.load(production_folder/'proyecto.json').get('revision')=='production':return package_production(raw_id)
    _,folder=folders(raw_id);report=build(raw_id)
    if report['visual_review_status']=='necesita_correccion' or e.load(folder/'VISUAL_QA.json').get('blocking_unresolved_count',1)!=0:raise ValueError('No empaquetar candidato rechazado visualmente')
    allowed=set()
    def add(path,suffixes=None):
        path=e.w.inside(path)
        for file in ([path]if path.is_file()else path.rglob('*')):
            if file.is_file()and not file.is_symlink()and(suffixes is None or file.suffix in suffixes):allowed.add(file)
    add(folder,{'.html','.js','.css','.json','.md','.png','.jpg','.m4a','.mp4'})
    allowed.discard(folder/'preview.mp4') # El único MP4 de entrega es el mux con AAC original.
    add(folder.parent/'original.mp4');add('sistema/clone',{'.py','.mjs','.js','.json','.md'})
    add('.agents/skills');add('recursos/clone')
    for file in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md','STYLE_YO.md','sistema/workflow.py','sistema/skills.py','sistema/skills_entorno.mjs','sistema/skills_instaladas.json','sistema/perfil.json','recursos/Sequel_Sans_Bold_Disp.ttf','recursos/Scholar_Italic.ttf','recursos/gsap.min.js','ejemplos/clone_componente/index.html','ejemplos/clone_componente/diseno.svg','ejemplos/clone_componente/timeline.gsap.js','ejemplos/clone_componente/proyecto.json'):
        add(file)
    for relative in e.source_fingerprint(folder)['files']:add(relative)
    exclusions={'entrega_integracion.json','paquete_manifest.json'}
    files=[p for p in sorted(allowed)if '.estado'not in p.relative_to(e.ROOT).parts and 'node_modules'not in p.relative_to(e.ROOT).parts and p.name not in exclusions]
    records=[{'path':str(p.relative_to(e.ROOT)),'sha256':e.digest(p),'bytes':p.stat().st_size}for p in files]
    manifest=folder/'paquete_manifest.json';e.write(manifest,{'schema_version':1,'generated':e.w.utc(),'mp4_sha256':report['mp4_sha256'],'files':records,'excluded':['credenciales','.estado','node_modules','modelos','preview_intermedio'],'requirements':'Reutiliza la instalación existente en IVAN. Restaurar rutas relativas; HTML y medios independientes del render CLI.'})
    target=folder/'ascendia_integracion_editable.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
        for p in files:archive.write(p,str(p.relative_to(e.ROOT)))
        archive.write(manifest,str(manifest.relative_to(e.ROOT)))
    with zipfile.ZipFile(target)as archive:
        if archive.testzip():raise ValueError('ZIP corrupto')
        if len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Rutas repetidas')
        for record in records:
            if hashlib.sha256(archive.read(record['path'])).hexdigest()!=record['sha256']:raise ValueError('Miembro ZIP alterado')
    return {'path':str(target.relative_to(e.ROOT)),'bytes':target.stat().st_size,'sha256':e.digest(target),'verified_members':len(records)+1}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['report','package']);parser.add_argument('raw_id');args=parser.parse_args();result=(build if args.stage=='report'else package)(args.raw_id)
    print(json.dumps(result,ensure_ascii=False,indent=2))
