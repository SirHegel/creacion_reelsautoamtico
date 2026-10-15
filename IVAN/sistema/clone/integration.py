"""Adaptador de crudos: plan CLONE intacto + dirección YO + medios originales.

No selecciona familias, no instala y no modifica componentes aprobados.
La dirección tipada procede de integration_planner; el adaptador aplica geometría.
"""
import argparse,copy,fcntl,json,math,pathlib,re,shutil,statistics,subprocess,sys
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import engine
w=engine.w;ROOT=engine.ROOT
FFMPEG=ROOT/'.estado/herramientas/ffmpeg/bin/ffmpeg'

def run(args):
    return subprocess.check_output([str(x) for x in args],cwd=ROOT,text=True,stderr=subprocess.PIPE)

def folders(raw_id,component=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{12,100}',raw_id):raise ValueError('ID de crudo inválido')
    if component not in (None,'hook'):raise ValueError('Componente de integración desconocido')
    return w.inside('proyectos/'+raw_id),w.inside('proyectos/'+raw_id+'/integracion'+('/hook'if component else''))

def production_camera_poses(face,direction,frames,framing=None):
    """Crop medido sobre anclas del nuevo original; jamás crop heredado."""
    original=face.get('original',{});sw=original.get('width');sh=original.get('height')
    if not all(isinstance(v,(int,float))and not isinstance(v,bool)and math.isfinite(v)and v>0 for v in (sw,sh)):
        raise ValueError('Dimensiones comprobadas de la fuente facial requeridas')
    if abs(sw/sh-9/16)>.001 or original.get('rotation',0)not in (0,360):
        raise ValueError('Camera requiere fuente vertical con orientación normalizada comprobada; no deformar vídeo')
    anchors=face.get('anchors',[])
    if not anchors or any(a.get('missing')for a in anchors):raise ValueError('Anclas incompletas: revisar antes de encuadrar')
    framing=copy.deepcopy(framing)if framing else None
    if framing:
        if not isinstance(framing,dict)or set(framing)!={'target_face_width_px','max_scale','reason'}:raise ValueError('Contrato camera_framing desconocido')
        for key,lo,hi in (('target_face_width_px',220,360),('max_scale',1,1.5)):
            value=framing[key]
            if not isinstance(value,(int,float))or isinstance(value,bool)or not math.isfinite(value)or not lo<=value<=hi:raise ValueError('Camera framing fuera de escala segura: '+key)
        if not isinstance(framing['reason'],str)or len(framing['reason'].strip())<20:raise ValueError('Camera framing requiere motivo de composición')
    poses=[];base_scale=1080/sw
    for index,window in enumerate(direction['camera_windows']):
        ratio=window.get('split_top')or direction.get('split_top',.5)
        selected=[a for a in anchors if window['start_frame']/30-.1<=a['t']<=min(frames/30,window['end_frame']/30+.1)]
        if not selected:raise ValueError('Aparición sin anclas del mismo intervalo')
        boxes=[]
        for a in selected:
            normalized=a.get('source_normalized',{});bbox=normalized.get('bbox');chin=normalized.get('chin',normalized.get('smooth_chin'))
            if not isinstance(bbox,list)or len(bbox)!=4 or not isinstance(chin,list)or len(chin)!=2 or not all(isinstance(v,(int,float))and not isinstance(v,bool)and math.isfinite(v)and 0<=v<=1 for v in bbox+chin):raise ValueError('BBox/barbilla no normalizados o finitos')
            if bbox[0]>=bbox[2]or bbox[1]>=bbox[3]:raise ValueError('BBox facial vacío')
            boxes.append((bbox[0]*sw,bbox[1]*sh,bbox[2]*sw,max(bbox[3],chin[1])*sh))
        left=min(x[0]for x in boxes);top=min(x[1]for x in boxes);right=max(x[2]for x in boxes);bottom=max(x[3]for x in boxes)
        median_width=statistics.median(x[2]-x[0]for x in boxes)
        scale=max(base_scale,min(base_scale*framing['max_scale'],framing['target_face_width_px']/median_width))if framing else base_scale
        crop_width=1080/scale;crop_height=(1920*(1-ratio)if window['state']=='split'else 1920)/scale
        low=max(0,bottom+120/scale-crop_height);high=min(sh-crop_height,top-48/scale)
        if high<low:raise ValueError('Split no conserva frente, barbilla y espacio de caption: revisar proporción/encuadre')
        crop_y=min(high,max(low,(top+bottom)/2-crop_height*.38))if window['state']=='split'or framing else 0
        min_x=max(0,right+48/scale-crop_width);max_x=min(sw-crop_width,left-48/scale)
        if min_x>max_x:raise ValueError('Framing no conserva el rostro horizontal completo')
        center=statistics.median((x[0]+x[2])/2 for x in boxes)
        crop_x=min(max_x,max(min_x,center-crop_width/2))if framing else 0
        x=-crop_x*scale;y=(1920*ratio if window['state']=='split'else 0)-crop_y*scale
        poses.append({'index':index,'start_frame':window['start_frame'],'end_frame':window['end_frame'],'state':window['state'],
            'split_top':ratio,'x':x,'y':y,'scale':scale,'crop_source':[crop_x,crop_y,crop_width,crop_height],
            'target_rect':[0,1920*ratio if window['state']=='split'else 0,1080,1920*(1-ratio)if window['state']=='split'else 1920],
            'measurement':'face bbox union in actual camera window; original background and uniform pixel scale',
            'anchor_count':len(selected),'source_face_top':top,'source_face_bottom':bottom,'no_artificial_fill':True,
            'framing':framing,'median_source_face_width':median_width,'displayed_face_width_px':median_width*scale,
            'baseline_composition_not_animated_zoom':True})
    return poses

def validated_instance_overrides(project,spec,narration,direction=None):
    """Correcciones explícitas de lectura; nunca reescribir el plan inferido."""
    overrides=project.get('instance_overrides')or[]
    if not isinstance(overrides,list)or len(overrides)>len(spec['scenes']):raise ValueError('Overrides instanciales fuera de contrato')
    if overrides and project.get('revision')!='production':raise ValueError('Overrides de producción opt-in; legacy permanece intacto')
    scenes={scene['id']:scene for scene in spec['scenes']};seen=set();result=[]
    normalize=lambda s:re.sub(r'[^\w ]','',str(s).lower()).split()
    for item in overrides:
        if not isinstance(item,dict)or 'scene_id'not in item:raise ValueError('Override instancial desconocido')
        scene=scenes.get(item['scene_id'])
        if not scene:raise ValueError('Override sin escena original existente')
        if scene['id']in seen:raise ValueError('Override repetido para la misma escena')
        if not isinstance(item.get('reason'),str)or len(item['reason'].strip())<30:raise ValueError('Override requiere razón semántica registrada')
        if item.get('kind')=='graph_brand_surface':
            keys={'scene_id','kind','node_id','asset','painted_major_native','reason'}
            if set(item)!=keys or scene['family']!='composition_graph':raise ValueError('Superficie de marca sólo admite un nodo de grafo original')
            node=next((n for n in scene['params']['nodes']if n['id']==item['node_id']),None)
            if not node or node.get('asset')!=item['asset']or node['kind']not in ('message','result'):raise ValueError('Marca no coincide con la tarjeta original del plan')
            size=item['painted_major_native']
            if not isinstance(size,(int,float))or isinstance(size,bool)or not math.isfinite(size)or not 72<=size<=104:raise ValueError('Tamaño de marca gráfica fuera de rango seguro')
            from brand_registry import assets_for_engine
            asset=assets_for_engine(context=project.get('brand_context','editorial_reel'),data_uri=False).get(item['asset'])
            if not asset or asset['kind']!='brand_logo':raise ValueError('Marca gráfica sin bytes oficiales verificados')
            seen.add(scene['id']);result.append(copy.deepcopy(item));continue
        if item.get('kind')=='spotlight_hook_identity':
            keys={'scene_id','kind','asset','painted_major_px','support_major_px','primary_until_frame','transform_frames','entrance_s','reason'}
            if set(item)!=keys or scene['family']!='spotlight_agent'or scene['start']!=0:raise ValueError('Identidad de hook sólo admite spotlight inicial y contrato cerrado')
            if not direction or not any(block.get('brand_asset')==item['asset']and block['word_start']==0 for block in direction.get('hook_blocks',[])):raise ValueError('Marca de hook no corresponde a la identidad inferida inicial')
            for key,lo,hi in (('painted_major_px',200,240),('support_major_px',90,110),('entrance_s',.2,.4),('transform_frames',9,21)):
                value=item[key]
                if not isinstance(value,(int,float))or isinstance(value,bool)or not math.isfinite(value)or not lo<=value<=hi:raise ValueError('Identidad de hook fuera del rango seguro: '+key)
            for key in ('primary_until_frame','transform_frames'):
                if not isinstance(item[key],int)or isinstance(item[key],bool):raise ValueError('Identidad hook requiere fotogramas enteros')
            if not 1<=item['primary_until_frame']<item['primary_until_frame']+item['transform_frames']<=direction['hook_end_frame']:raise ValueError('Transformación de identidad fuera del hook inferido')
            from brand_registry import assets_for_engine
            asset=assets_for_engine(context=project.get('brand_context','editorial_reel'),data_uri=False).get(item['asset'])
            if not asset or asset['kind']!='brand_logo':raise ValueError('Identidad hook no tiene bytes oficiales verificados en el contexto declarado')
            seen.add(scene['id']);result.append(copy.deepcopy(item));continue
        if set(item)!={'scene_id','kind','hide_count','labels','reason'}or item.get('kind')!='pixel_functional_roles':raise ValueError('Override instancial desconocido')
        if scene['family']!='pixel_agents':raise ValueError('Pixel functional sólo admite una instancia pixel_agents existente')
        if item['hide_count']is not True:raise ValueError('Conteo funcional requiere ocultar el número de agentes no narrado')
        roles=scene['params']['roles'];labels=item['labels']
        if not isinstance(labels,list)or len(labels)!=len(roles):raise ValueError('Etiquetas no corresponden a los roles originales')
        for label,role in zip(labels,roles):
            original=role.get('label','')if isinstance(role,dict)else role
            if not isinstance(label,str)or not 1<=len(label)<=20 or not normalize(label)or any(token not in normalize(original)for token in normalize(label)):raise ValueError('Etiqueta funcional introduce texto no sustentado por el rol original')
        seen.add(scene['id']);result.append(copy.deepcopy(item))
    return result

def validated_audio_mix(project,original_sha):
    contract=project.get('audio_mix')
    if not contract:return None
    required={'path','sha256','provenance_path','provenance_sha256','voice_source_sha256'}
    if not isinstance(contract,dict)or not required<=set(contract):raise ValueError('Mezcla sin contrato completo de medios/procedencia')
    audio=w.inside(contract['path']);proof_path=w.inside(contract['provenance_path'])
    if not audio.is_file()or not proof_path.is_file()or w.digest(audio)!=contract['sha256']or w.digest(proof_path)!=contract['provenance_sha256']:raise ValueError('Mezcla o recibo no corresponden al SHA actual')
    proof=engine.load(proof_path)
    if proof.get('original_source_sha256')!=original_sha or proof.get('original_voice_stem_unchanged')is not True or proof.get('voice_source_sha256')!=contract['voice_source_sha256']:
        raise ValueError('No está comprobada la conservación del stem original en la mezcla')
    source=w.inside(project['original']['path'])
    if w.digest(source)!=original_sha:raise ValueError('Fuente original cambió antes de la mezcla')
    packet_hash=run([FFMPEG,'-v','error','-i',source,'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).strip().split('=',1)[-1]
    if packet_hash!=contract['voice_source_sha256']or proof.get('output_sha256')!=contract['sha256']:raise ValueError('Stem o salida de la mezcla no corresponden a los bytes originales comprobados')
    return {'audio':audio,'proof':proof,'contract':copy.deepcopy(contract)}

def browser_audio(project,folder):
    """Una sola pista audible: mezcla verificada o voz local conservada."""
    mix=validated_audio_mix(project,project['original']['sha256'])
    if not mix:
        audio=folder/'media/voice_original.m4a'
        if not audio.is_file():raise ValueError('Voz original preparada ausente')
        return {'src':'media/voice_original.m4a','kind':'voice_original','sha256':w.digest(audio),'voice_processing':'none','audible_tracks':1}
    suffix=mix['audio'].suffix.lower()
    if suffix not in ('.m4a','.mp4','.aac','.wav','.mp3'):raise ValueError('Formato de mezcla no reproducible en el editable')
    target=folder/'media'/('audio_mix'+suffix)
    if target.exists()and target.resolve()==mix['audio'].resolve():pass
    else:
        if target.is_symlink():target.unlink()
        elif target.exists():raise ValueError('No sobrescribir un binario local ajeno al selector de mezcla')
        target.symlink_to(mix['audio'])
    return {'src':str(target.relative_to(folder)),'kind':'verified_mix','sha256':mix['contract']['sha256'],'source_path':mix['contract']['path'],
        'provenance_path':mix['contract']['provenance_path'],'provenance_sha256':mix['contract']['provenance_sha256'],'original_voice_stem_unchanged':True,
        'voice_processing':'none; mixed track replaces original playback, not added on top','audible_tracks':1}

def plan(raw_id):
    """Inferencia real del planner vigente y dirección YO; reutiliza pruebas válidas."""
    _,folder=folders(raw_id)
    project=engine.load(folder/'proyecto.json');w.require_current_instructions(project)
    from skills import validate
    validate(project,'render')
    narration=engine.load(folder/'narration.json');source=w.inside(project['original']['path'])
    if w.digest(source)!=narration['source']['sha256']:raise ValueError('Transcripción de otro crudo')
    import planner
    from integration_planner import plan_for,validate_plan
    scene_path=folder/'scene.json';direction_path=folder/'integration_plan.json'
    reused=scene_path.exists() and direction_path.exists()
    if reused:
        spec=engine.load(scene_path);direction=engine.load(direction_path)
        proof=engine.load(w.inside(spec['planner']['proof']),{})
        if not proof.get('real_inference') or proof.get('returncode')!=0:raise ValueError('Plan sin inferencia comprobada')
        if direction['scene_ir_sha256']!=w.digest(scene_path) or direction['narration_sha256']!=w.digest(folder/'narration.json'):raise ValueError('Plan obsoleto; no sustituirlo silenciosamente')
        validate_plan(direction,spec,narration)
    else:
        if scene_path.exists() or direction_path.exists():raise ValueError('Plan incompleto; revisar el intento existente')
        requirements=copy.deepcopy(project.get('visual_requirements')or{})
        if project.get('revision')=='production':requirements['motion_profile']='production_complete'
        spec=planner.plan(narration['text'],output=scene_path,narration=narration,duration=project['duration'],brand_context=project.get('brand_context','editorial_reel'),visual_requirements=requirements or None)
        constraints={'profile':'production_complete','camera_mode':'split_first','split_top':.5}if project.get('revision')=='production'else None
        direction=plan_for(scene_path,folder/'narration.json',source,direction_path,constraints=constraints)
    return {'real_inference':True,'reused_verified_plan':reused,'families':[s['family']for s in spec['scenes']],'scene_ir_sha256':w.digest(scene_path),'integration_plan_sha256':w.digest(direction_path)}

def prepare(raw_id):
    source_folder,folder=folders(raw_id)
    project=engine.load(folder/'proyecto.json');source=w.inside(project['original']['path'])
    if w.digest(source)!=project['original']['sha256']:raise ValueError('El crudo cambió')
    media=folder/'media';media.mkdir(exist_ok=True)
    previous=engine.load(media/'provenance.json',{})
    proxy=media/'camera.mp4';audio=media/'voice_original.m4a'
    if previous.get('source_sha256')==w.digest(source) and all(p.exists() and w.digest(p)==previous.get(p.name,{}).get('sha256') for p in (proxy,audio)):return previous
    with (ROOT/'.estado/clone/render.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run([FFMPEG,'-v','error','-i',source,'-map','0:v:0','-an','-c:v','h264_nvenc','-preset','p4','-tune','lossless','-rc','constqp','-qp','0','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709','-fps_mode','passthrough','-movflags','+faststart','-y',proxy])
    run([FFMPEG,'-v','error','-i',source,'-vn','-map','0:a:0','-c:a','copy','-movflags','+faststart','-y',audio])
    probe=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',proxy]))
    video=next(s for s in probe['streams']if s['codec_type']=='video')
    if int(video['nb_read_frames'])!=project['frames']:raise ValueError('Proxy altera número de fotogramas')
    # Comparación de muestras YUV decodificadas: proxy técnico, sin tratamiento.
    hashes=[run(['/usr/bin/ffmpeg','-v','error','-i',p,'-map','0:v:0','-pix_fmt','yuv420p','-f','hash','-hash','sha256','-']).strip() for p in (source,proxy)]
    if hashes[0]!=hashes[1]:raise ValueError('El proxy cambia los píxeles originales')
    receipt={'source_sha256':w.digest(source),'source':str(source.relative_to(ROOT)),'camera_pixels_identical':True,'decoded_yuv_sha256':hashes[0],'frames':project['frames'],'duration':project['duration'],'original_audio_processing':'stream_copy','proxy_reason':'HEVC original → H264 lossless para preview/navegador; sin crop/color/retime','updated':w.utc()}
    for p in (proxy,audio):receipt[p.name]={'path':str(p.relative_to(ROOT)),'sha256':w.digest(p),'bytes':p.stat().st_size}
    engine.write(media/'provenance.json',receipt)
    return receipt

def compile_integration(raw_id,component=None):
    _,folder=folders(raw_id,component)
    from skills import validate
    project=engine.load(folder/'proyecto.json');w.require_current_instructions(project);validate(project,'render')
    spec=engine.load(folder/'scene.json');direction=engine.load(folder/'integration_plan.json');narration=engine.load(folder/'narration.json')
    from integration_planner import validate_plan
    validate_plan(direction,spec,narration)
    if component is None:prepare(raw_id)
    elif not all((folder/'media'/n).is_file()for n in ('camera.mp4','voice_original.m4a')):raise ValueError('Medios del hook no preparados')
    face=engine.load(folder/'diagnostico_yo/anclas_55_45.json',{})
    if not face:raise ValueError('Faltan anclas verificadas de rostro')
    if face.get('original',{}).get('sha256')!=narration['source']['sha256']:raise ValueError('Rostro de otro crudo')
    # Snapshot semántico: compile sólo puede normalizar forma técnica del mismo plan.
    protected={key:copy.deepcopy(spec.get(key)) for key in ('scenes','semantic_analysis','timing')}
    engine.compile_multiscene(engine.validate_spec(copy.deepcopy(spec)),folder)
    current=engine.load(folder/'scene.json')
    if any(current.get(k)!=v for k,v in protected.items()):raise ValueError('El adaptador alteró decisiones del planner')
    bootstrap=folder/'shared/clone-bundle.js'
    code=bootstrap.read_text();old="if(window.renderReady)window.dispatchEvent(new Event('hf-timelines-built'));"
    if code.count(old)!=1:raise ValueError('Contrato de montaje cambió; no aplicar reemplazo heurístico')
    bootstrap.write_text(code.replace(old,"if(window.renderReady){window.renderReady=false;window.CloneIntegrationSetup();}"))
    html=(folder/'index.html').read_text()
    root_open=f'<div id="__clone-film" data-composition-id="clone-main" data-width="1080" data-height="1920" data-duration="{spec["duration"]}">'
    if html.count(root_open)!=1:raise ValueError('Root modular ausente')
    html=html.replace("<script>window.__timelines['clone-main']=gsap.timeline({paused:true});</script>",'')
    html=html.replace(root_open,root_open+'<div id="integration-motion-viewport"><div id="integration-motion-world">')
    tail='</div></body></html>'
    if not html.endswith(tail):raise ValueError('Transporte modular no reconocido')
    playback=browser_audio(project,folder)
    media='<div id="integration-camera-mask"><div id="integration-camera-plane"><video id="integration-camera-video" class="clip" src="media/camera.mp4" muted playsinline preload="auto" data-start="0" data-duration="'+str(spec['duration'])+'" data-media-start="0" data-track-index="3"></video></div></div><div id="integration-type"></div><audio id="integration-voice" src="'+playback['src']+'" data-start="0" data-duration="'+str(spec['duration'])+'" data-volume="1" data-track-index="4"></audio>'
    production=direction.get('profile')=='production_complete'
    split_top=direction.get('split_top',.55);crop_y=315 if split_top==.5 else 345
    config={'schema_version':1,'revision':project.get('revision','V1'),'brand_context':spec.get('planner',{}).get('asset_resolution',{}).get('context','editorial_reel'),'duration':spec['duration'],'frames':project['frames'],'scenes':spec['scenes'],'direction':direction,'narration':narration,'face':face,'split':{'upper':split_top,'lower':1-split_top},'camera_crop':[0,crop_y,1080,round((1-split_top)*1920)],'fonts':{'principal':'Sequel','editorial':'Scholar'},'shadow':'2px 4px 5px rgba(0,0,0,.85)','original_family_source_edited':False,'audio_playback':playback}
    if production:
        config.update(profile='production_complete',source_geometry={k:face['original'].get(k,0 if k=='rotation'else None)for k in ('width','height','fps','rotation')},
            camera_poses=production_camera_poses(face,direction,project['frames'],project.get('camera_framing')),face_tracking_sha256=w.digest(folder/'diagnostico_yo/anclas_55_45.json'),
            layout_contract={'method':'native_surface_measured','body_min_px':28,'identity_min_px':72,'secondary_min_px':18,'motion_transition_s':.4},
            audio_mix=copy.deepcopy(project.get('audio_mix')),instance_overrides=validated_instance_overrides(project,spec,narration,direction))
        config['camera_crop']=config['camera_poses'][0]['crop_source']
    engine.write(folder/'integration-config.json',config)
    css='<style>'+engine.font_css()+'''
#integration-motion-viewport{position:absolute;inset:0;overflow:hidden}
#integration-motion-world{position:absolute;inset:0;transform-origin:0 0}
#integration-camera-mask{position:absolute;inset:0;z-index:200;overflow:hidden}
#integration-camera-plane{position:absolute;inset:0;transform-origin:0 0}
#integration-camera-video{display:block;width:100%;height:100%;object-fit:fill}
#integration-type{position:absolute;inset:0;z-index:220;pointer-events:none;font-family:Sequel}
.integration-text{position:absolute;left:60px;top:0;width:960px;text-align:center;line-height:1.03;letter-spacing:-.015em;color:#fff;text-shadow:2px 4px 5px rgba(0,0,0,.85);overflow:visible;opacity:0}
.integration-line{display:block;white-space:pre-wrap}
.integration-glyph{display:inline-block;white-space:pre}
</style>'''
    if production:
        geometry=config['source_geometry'];css=css.replace('#integration-camera-video{display:block;width:100%;height:100%;object-fit:fill}',
            '#integration-camera-video{display:block;width:'+str(geometry['width'])+'px;height:'+str(geometry['height'])+'px;max-width:none;object-fit:contain}')
    adapter=(HERE/'integration_layout.js').read_text()+'\n'+(HERE/'integration_brands.js').read_text()+'\n'+(HERE/'integration_hook.js').read_text()+'\n'+(HERE/'integration.js').read_text()
    html=html[:-len(tail)]+'</div></div>'+media+'</div>'+css+'<script>window.CLONE_INTEGRATION='+json.dumps(config,ensure_ascii=False).replace('</','<\\/')+';</script><script>'+adapter.replace('</','<\\/')+'</script></body></html>'
    (folder/'index.html').write_text(html)
    # La timeline real se publica inline: lint/check inspeccionan su registro,
    # sin una declaración ficticia ni una segunda timeline vacía.
    (folder/'integration.js').unlink(missing_ok=True)
    sources=engine.source_fingerprint(folder);engine.write(folder/'source_manifest.json',sources)
    engine.write(folder/'integration_compile.json',{'updated':w.utc(),'manual':w.manual(),'plan_decisions_preserved':True,'selected_families':[s['family']for s in spec['scenes']],'integration_plan_sha256':w.digest(folder/'integration_plan.json'),'narration_sha256':w.digest(folder/'narration.json'),'sources':sources,'native_components_modified':False})
    project.update(stage='composicion_lista',motor={'composicion':str((folder/'index.html').relative_to(ROOT)),'recursos_relativos':True},integration_plan_sha256=w.digest(folder/'integration_plan.json'))
    engine.write(folder/'proyecto.json',project)
    return {'compiled':True,'source_sha256':sources['sha256'],'family_selection':'original_planner_unchanged'}

def render(raw_id,component=None):
    _,folder=folders(raw_id,component);project=engine.load(folder/'proyecto.json')
    from skills import validate
    w.require_current_instructions(project);validate(project,'render')
    with (ROOT/'.estado/clone/render.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);qc=engine.render(folder)
    target=folder/project['output_name'];part=target.with_suffix('.part.mp4');source=folder/'media/voice_original.m4a'if component else w.inside(project['original']['path'])
    mix=validated_audio_mix(project,project['original']['sha256'])
    # Restaurar los paquetes AAC exactos del original. No apad, retime ni DSP.
    audio_source=mix['audio']if mix else source
    audio_probe=json.loads(run(['ffprobe','-v','error','-show_streams','-of','json',audio_source]));audio_stream=next(s for s in audio_probe['streams']if s['codec_type']=='audio')
    if mix and abs(float(audio_stream['duration'])-project.get('original_audio_duration',project['duration']))>.05:raise ValueError('La mezcla cambia duración de la pista original')
    encoding=['-c:a','copy']if audio_stream['codec_name']=='aac'else['-c:a','aac','-b:a','256k']
    run([FFMPEG,'-v','error','-i',folder/'preview.mp4','-i',audio_source,'-map','0:v:0','-map','1:a:0','-c:v','copy',*encoding,'-movflags','+faststart','-y',part])
    probe=json.loads(run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',part]));video=next(x for x in probe['streams']if x['codec_type']=='video');audio=next(x for x in probe['streams']if x['codec_type']=='audio')
    if int(video['nb_read_frames'])!=project['frames']:raise ValueError('Duración visual cambiada')
    audiohashes=[run([FFMPEG,'-v','error','-i',p,'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).strip()for p in (source,part)]
    if not mix and audiohashes[0]!=audiohashes[1]:raise ValueError('Audio original modificado')
    run(['/usr/bin/ffmpeg','-v','error','-xerror','-err_detect','explode','-i',part,'-f','null','-'])
    if engine.source_fingerprint(folder)['sha256']!=qc['source_sha256']:raise ValueError('Composición cambió durante mux; no promover un render obsoleto')
    if mix and(w.digest(mix['audio'])!=mix['contract']['sha256']or w.digest(w.inside(mix['contract']['provenance_path']))!=mix['contract']['provenance_sha256']):raise ValueError('Mezcla cambió durante mux; no promover')
    part.replace(target)
    receipt={**qc,'final_mp4_sha256':w.digest(target),'original_audio_packet_hash':audiohashes[0],'audio_original_bit_exact':not bool(mix),'original_voice_stem_unchanged':True if mix else None,'audio_mix':mix['contract']if mix else None,'source_sha256':engine.source_fingerprint(folder)['sha256'],'video_duration':float(video['duration']),'audio_duration':float(audio['duration']),'container_duration':float(probe['format']['duration']),'output_name':target.name,'no_extension':int(video['nb_read_frames'])==project['frames'],'review':'pending_visual_review'}
    engine.write(folder/'integration_qc.json',receipt)
    project.update(stage='render_pendiente_revision',final_mp4_sha256=receipt['final_mp4_sha256']);engine.write(folder/'proyecto.json',project)
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['plan','prepare','compile','render']);p.add_argument('raw_id');p.add_argument('--component',choices=['hook']);a=p.parse_args()
    if a.component and a.stage not in ('compile','render'):p.error('El hook se deriva del plan conservado; no plan/prepare completos')
    result={'plan':plan,'prepare':prepare,'compile':compile_integration,'render':render}[a.stage](a.raw_id,**({'component':a.component}if a.component else{}))
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
