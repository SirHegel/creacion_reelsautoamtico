"""Entrega V2 vinculada al MP4, inferencias y mediciones reales; conserva V1."""
import argparse,csv,hashlib,json,pathlib,sys,zipfile
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import engine as e
from integration import folders

def build(raw_id):
    _,folder=folders(raw_id);project=e.load(folder/'proyecto.json')
    spec=e.load(folder/'scene.json');direction=e.load(folder/'integration_plan.json')
    browser=e.load(folder/'integration_v2_browser_qc.json');qc=e.load(folder/'integration_qc.json')
    rhythm=e.load(folder/'ritmo_v2.json');visual=e.load(folder/'VISUAL_QA.json')
    source=e.source_fingerprint(folder)['sha256'];mp4=folder/project['output_name'];sha=e.digest(mp4)
    if project.get('revision')!='V2':raise ValueError('Informe exclusivo de corrección V2')
    e.w.require_current_instructions(project)
    if qc['source_sha256']!=source or qc['final_mp4_sha256']!=sha or not qc['audio_original_bit_exact'] or not qc['decoded_all_frames']:raise ValueError('Render/audio obsoleto')
    if browser['mode']!='all_frames' or browser['frame_count']!=project['frames'] or not all(browser['checks'].values()) or browser.get('errors'):raise ValueError('QA incompleto o fallido')
    if browser['source_after']['sha256']!=source or browser['export_binding']['sha256']!=sha:raise ValueError('QA de otro candidato')
    if rhythm['source_sha256']!=source or rhythm['export_binding']['sha256']!=sha:raise ValueError('Permanencias de otro candidato')
    if visual['mp4_sha256']!=sha or visual['composition_sha256']!=source or visual.get('blocking_unresolved_count',1):raise ValueError('Revisión visual pendiente/rechazada')
    old=project['previous_version'];v1=folder/old['output_name']
    if e.digest(v1)!=old['sha256']:raise ValueError('V1 modificada')
    marks=e.load(e.HERE/'brand_assets.json')['assets'];receipt=browser['integration_receipt']
    rows=[]
    for brand in rhythm['brands']:
        if not brand['original_bytes_match'] or not brand['actual_visible_frames']:raise ValueError('Marca no incorporada auténticamente: '+brand['brand'])
        for key in brand['assets']:
            asset=marks[key]
            rows.append({'Marca':asset['entity_label'],'Asset':key,'Archivo':asset['path'],'SHA256':asset['sha256'],'Fuente oficial':asset['source_page'],'Descarga original':asset['download_url'],'Condiciones':asset['conditions_url'],'Primer frame visible':min(brand['actual_visible_frames']),'Último frame visible':max(brand['actual_visible_frames']),'Permanencia legible máxima s':round(brand['readable_dwell']['max'],3),'Permanencia legible total s':round(brand['readable_dwell']['total'],3),'Contexto':'private_review','Publicación autorizada':False})
    with (folder/'brand_assets_utilizados.csv').open('w',newline='',encoding='utf-8')as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    families=[]
    for scene in spec['scenes']:
        executed=next(x for x in rhythm['families']if x['scene_id']==scene['id'])
        families.append({'scene_id':scene['id'],'family':scene['family'],'start':scene['start'],'duration':scene['duration'],'semantic_reason':scene['semantic_reason'],'visual_reason':scene['visual_reason'],'alternatives':scene.get('alternatives_considered',[]),'actual_execution':executed,'rhythm_request':scene.get('rhythm'),'assets':next(x['used_assets']for x in receipt['components']if x['scene_id']==scene['id'])})
    proofs={}
    for key,path in [('scene',spec['planner']['proof']),('direction',direction['inference']['provider_proof'])]:
        proof=e.load(path)
        if not proof.get('real_inference')or proof.get('returncode')!=0:raise ValueError('Falta inferencia real')
        proofs[key]={'path':path,'sha256':e.digest(path),'provider':proof.get('provider'),'real_inference':True,'prompt_sha256':proof['prompt_sha256'],'response_sha256':proof['response_sha256']}
    registry={'schema_version':2,'generated':e.w.utc(),'mp4_sha256':sha,'composition_sha256':source,'families':families,'logos':rows,'hook_assets':receipt.get('hook_assets_used',[]),'inferences':proofs,'stock_or_broll':[],'native_components_modified':False,'source_audio':'AAC original, paquetes idénticos','publication_authorized':False}
    e.write(folder/'componentes_utilizados_v2.json',registry)
    storyboard=['# Storyboard automático V2','',f"{project['duration']} s de imagen; {project['frames']} fotogramas a 30 FPS. Audio original sin cambio de velocidad.",'','## Familias y decisiones','']
    for family in families:
        storyboard.extend([f"**{family['scene_id']} · {family['family']} · {family['start']:.3f}–{family['start']+family['duration']:.3f} s**",family['semantic_reason'],'',family['visual_reason'],''])
        for alternative in family['alternatives']:storyboard.append(f"- Alternativa {alternative['family']}: {alternative['reason']}")
        storyboard.append('')
    storyboard.extend(['## Cámara original','','| Inicio–fin s | Estado | Motivo |','|---|---|---|'])
    for window in direction['camera_windows']:storyboard.append(f"| {window['start_frame']/30:.3f}–{window['end_frame']/30:.3f} | {window['state']} | {window['reason']} |")
    storyboard.extend(['','Presencia orientativa adaptada al hook: '+direction['camera_budget_reason'],'','## Texto realmente compuesto','','| Inicio–fin s | Frase | Fuente |','|---|---|---|'])
    for block in receipt['text_blocks']:storyboard.append(f"| {block['start_frame']/30:.3f}–{block['end_frame']/30:.3f} | {block['text']} | {block['font']} · {block['font_size']:.0f}px |")
    storyboard.extend(['','## Relojes ejecutados',''])
    for operation in receipt['component_overrides']:
        if 'map'in operation:storyboard.extend([f"**{operation['scene_id']}** · {operation['execution']} · {operation.get('rhythm_mode','word_cues')}",'', '```json',json.dumps(operation['map'],ensure_ascii=False,indent=2),'```',''])
    (folder/'auto_storyboard_v2.md').write_text('\n'.join(storyboard))
    result={'schema_version':2,'generated':e.w.utc(),'status':'lista_para_revision_usuario','aesthetic_approval':False,'mp4_sha256':sha,'composition_sha256':source,'v1_sha256':old['sha256'],'image_duration':project['duration'],'audio_duration':qc['audio_duration'],'frames':project['frames'],'source_audio_bit_exact':True,'families':[x['family']for x in families],'camera':rhythm['camera'],'logos':rows,'technical_checks':browser['checks'],'visual_review':visual,'rhythm':rhythm,'inferences':proofs,'native_preservation':browser['preservation'],'publication_context':'private_review','publication_authorized':False}
    e.write(folder/'INFORME_INTEGRACION_V2.json',result)
    lines=['# Ascendia + CLONE — integración V2','',f"`{mp4.name}` conserva {project['duration']} s de imagen / {project['frames']} fotogramas y {qc['audio_duration']:.6f} s de AAC original. V1 permanece intacta. Esta entrega es una prueba para revisión; no una aprobación estética ni una autorización de publicación de marcas.",'','## Qué cambió','', 'El planner evalúa cada bloque narrativo y las capacidades visuales reales. Los logos auténticos se resuelven por identidad y procedencia. Los recursos de una enumeración pueden permanecer juntos para ser reconocidos; la sincronización no exige un cambio gráfico por palabra. Las notas internas se mantienen en el informe. Los módulos aprobados, CANCELLED y las demostraciones anteriores se conservan.','',f"Familias seleccionadas mediante inferencia real: **{', '.join(result['families'])}**. Consultar `auto_storyboard_v2.md` y `componentes_utilizados_v2.json` para las alternativas y sus motivos.",'','## Logos incorporados','', '| Marca | Archivo | Fuente oficial | Lectura continua máxima |','|---|---|---|---|']
    for row in rows:lines.append(f"| {row['Marca']} | `{row['Archivo']}` | [{row['Marca']}]({row['Fuente oficial']}) | {row['Permanencia legible máxima s']:.3f} s |")
    lines.extend(['','Los archivos conservan sus bytes y colores. `brand_assets_utilizados.csv` registra SHA, descarga, condiciones y tiempos medidos. `LOGOS_FUENTES_V2.md` y `BRAND_ASSETS.md` documentan los permisos pendientes; `BRAND_VISUAL_QA_V2.json` registra la revisión de archivos y apariencia del export. Preparar este mockup no concede permisos de publicación.','', '## Ritmo y permanencia','', '| Protagonista | Lectura continua máxima | Lectura total | Entrada hasta lectura | Movimiento durante lectura |','|---|---|---|---|---|'])
    for subject in rhythm['protagonists']:
        entry=subject['entry_until_first_readable_seconds'];label=subject['label'].replace('|','/')
        if subject['kind']=='official_hook_brand':label+=' (logo del hook)'
        elif subject['label']=='Google' and subject['family']=='composition_graph':label+=' (reacción auxiliar)'
        elif subject['kind']=='pixel_agent':label='Investigador pixelado'
        lines.append(f"| {label} | {subject['legible_presence']['max']:.3f} s | {subject['legible_presence']['total']:.3f} s | {'—'if entry is None else f'{entry:.3f} s'} | {subject['in_motion_while_readable_seconds']:.3f} s |")
    lines.extend(['','La referencia de 0,7–1,3 s corresponde a una idea legible. Una fuente puede permanecer más tiempo mientras se nombra otra; no es una duración máxima ni una orden para congelar el movimiento. La columna de movimiento mide el desplazamiento de la superficie, no la animación interna de rutas, texto o datos. El nodo auxiliar de Google no es el protagonista: su identidad ya se presenta mediante el wordmark legible del hook. `ritmo_v2.json` contiene los intervalos y los umbrales; un bbox visible no prueba por sí solo lectura móvil o fidelidad con CLONE.','', '## Validación','',f"Se decodificaron los {project['frames']} fotogramas; AAC coincide por paquetes con el original. El navegador recorrió todos los estados, en orden directo, inverso y con búsquedas desordenadas. Las marcas se identificaron por bytes realmente montados y visibles. Familias y movimientos se comprobaron en instancias reales. Fuentes Sequel/Scholar locales, split 55/45 y cámara original sin blur.",'','En esta V2 el rostro aparece durante el hook editorial. Los subtítulos tradicionales posteriores no coinciden con cámara visible: la colocación convencional bajo barbilla es un contrato disponible, pero no se declara ejercitada por esta muestra.', '', f"Presencia de rostro observada: {rhythm['camera']['presence_fraction']*100:.2f} %. Máximo continuo: {rhythm['camera']['max_continuous_frames']/30:.3f} s. Motivo del presupuesto: {direction['camera_budget_reason']}",'','`VISUAL_QA.json` registra la inspección de fotogramas consecutivos y comparación con YO/CLONE; `comparacion_integracion_v1_v2.mp4` compara los renders en tiempos equivalentes. La comparación no mide igualdad estética automáticamente.','', '## Límites y pendientes',''])
    for issue in visual.get('issues',[]):
        if issue.get('resolved_status')!='resolved':lines.append('- '+issue['observed'])
    lines.extend(['- La aprobación estética corresponde al usuario. Las reconstrucciones originales y el modelo no sustituyen su revisión.', '- Las afirmaciones sobre scraping de todas las plataformas y gratuidad se conservan de la narración; el gráfico no demuestra ejecución real ni acceso autorizado.', '- La prueba conserva exclusivamente AAC original; no se afirma mezcla adicional de música/FX ni escucha perceptiva.', '- El registro reconoce las marcas catalogadas. Nuevas marcas requieren una fuente oficial, sus condiciones y verificación antes de incorporarse.', '- Para otros crudos, completar transcripción y anclas de rostro verificadas antes del adaptador. No generalizar el crop de esta fuente.','', '## Editable y reproducción','', '`index.html` es la composición modular editable; el ZIP conserva SceneIR, dirección, timelines, fuentes y medios locales. Para render CLI reutiliza la instalación existente de IVAN; no contiene herramientas, credenciales ni modelos.','',f'```bash\npython3 -B sistema/clone/integration.py compile {raw_id}\npython3 -B sistema/clone/integration.py render {raw_id}\nnode sistema/clone/tests/integration_v2_browser.mjs {raw_id}\npython3 -B sistema/clone/integration_v2_report.py report {raw_id}\n```','',f"SHA-256 V2: `{sha}`. Composición: `{source}`."])
    (folder/'INFORME_INTEGRACION_V2.md').write_text('\n'.join(lines)+'\n');return result

def package(raw_id):
    report=build(raw_id);_,folder=folders(raw_id);allowed=set()
    def add(path,suffixes=None):
        path=e.w.inside(path)
        for file in ([path]if path.is_file()else path.rglob('*')):
            if file.is_file()and not file.is_symlink()and(suffixes is None or file.suffix in suffixes):allowed.add(file)
    # Un paquete vigente, sin auditorías históricas o exports intermedios.
    names=['index.html','scene.json','integration_plan.json','integration-config.json','integration_compile.json','mounts.json','proyecto.json','narration.json','skills_aplicadas.json','skills_lectura.json','catalogo_skills.json','source_manifest.json','integration_qc.json','integration_v2_browser_qc.json','ritmo_v2.json','VISUAL_QA.json','VISUAL_QA.md','INFORME_INTEGRACION_V2.md','INFORME_INTEGRACION_V2.json','componentes_utilizados_v2.json','auto_storyboard_v2.md','brand_assets_utilizados.csv','LOGOS_FUENTES_V2.md','BRAND_VISUAL_QA_V2.json','BRAND_VISUAL_QA_V2.md','ascendia_integracion_test_10s_v2.mp4','comparacion_integracion_v1_v2.mp4']
    for name in names:
        if not(folder/name).is_file():raise ValueError('Entregable pendiente: '+name)
        add(folder/name)
    for name in ('compositions','shared','media','diagnostico_yo','evidencia_qa/browser_v2','evidencia_qa/visual_v2'):add(folder/name,{'.html','.js','.css','.json','.md','.png','.jpg','.m4a','.mp4'})
    add(folder.parent/'original.mp4');add('sistema/clone',{'.py','.js','.mjs','.json','.md'});add('.agents/skills');add('recursos/clone');add('recursos/brands')
    for path in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md','STYLE_YO.md','sistema/workflow.py','sistema/skills.py','sistema/skills_entorno.mjs','sistema/skills_instaladas.json','sistema/perfil.json','recursos/Sequel_Sans_Bold_Disp.ttf','recursos/Scholar_Italic.ttf','recursos/gsap.min.js','ejemplos/clone_componente/index.html','ejemplos/clone_componente/diseno.svg','ejemplos/clone_componente/timeline.gsap.js','ejemplos/clone_componente/proyecto.json'):add(path)
    for path in e.source_fingerprint(folder)['files']:add(path)
    files=[p for p in sorted(allowed)if '.estado'not in p.relative_to(e.ROOT).parts and 'node_modules'not in p.relative_to(e.ROOT).parts]
    records=[{'path':str(p.relative_to(e.ROOT)),'sha256':e.digest(p),'bytes':p.stat().st_size}for p in files]
    manifest=folder/'paquete_v2_manifest.json';e.write(manifest,{'schema_version':2,'mp4_sha256':report['mp4_sha256'],'files':records,'excluded':['credenciales','.estado','instalaciones','modelos','exports históricos e intermedios'],'context':'private_review'})
    target=folder/'ascendia_integracion_v2_editable.zip';part=target.with_suffix('.part.zip')
    with zipfile.ZipFile(part,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
        for file in files:archive.write(file,str(file.relative_to(e.ROOT)))
        archive.write(manifest,str(manifest.relative_to(e.ROOT)))
    with zipfile.ZipFile(part)as archive:
        if archive.testzip()or len(archive.namelist())!=len(set(archive.namelist())):raise ValueError('Paquete corrupto/repetido')
        for item in records:
            if hashlib.sha256(archive.read(item['path'])).hexdigest()!=item['sha256']:raise ValueError('SHA de paquete divergente')
    part.replace(target);return {'path':str(target.relative_to(e.ROOT)),'sha256':e.digest(target),'bytes':target.stat().st_size,'verified_members':len(records)+1}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['report','package']);parser.add_argument('raw_id');args=parser.parse_args()
    result=(build if args.stage=='report'else package)(args.raw_id)
    print(json.dumps({k:result[k]for k in ('status','mp4_sha256','families','path','sha256','bytes','verified_members')if k in result},ensure_ascii=False,indent=2))
