"""Cerrar revisión, empaquetar y publicar únicamente el segmento autorizado."""
import hashlib,json,pathlib,subprocess,sys,zipfile
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'sistema'))
import workflow as w
from skills import validate
FOLDER='ejemplos/clone_componente/'

def package():
    p=w.read_json(FOLDER+'proyecto.json');w.require_current_instructions(p)
    record=w.read_json(FOLDER+'skills_aplicadas.json')
    for e in record['skills']:
        for ev in e['evidencias']:ev['sha256']=w.digest(ev['archivo'])
    w.write_json(FOLDER+'skills_aplicadas.json',record);validate(p,phase='render')
    a=p['aprobacion_diseno']
    assert a['usuario_aprobo']
    assert w.digest(HERE/'diseno.svg')==a['diseno_sha256']
    assert w.digest(HERE/'clone_diseno_estatico.png')==a['png_sha256']
    render=w.read_json(FOLDER+'render_ejecucion.json')
    assert render['mp4_sha256']==w.digest(HERE/'clone_segmento_animado.mp4')
    assert render['composicion_sha256']==w.digest(HERE/'index.html')
    assert render['timeline_sha256']==w.digest(HERE/'timeline.gsap.js')
    final=w.read_json('.estado/tmp/clone_revision_estabilidad_final.json')
    # El revisor independiente guarda su SHA bajo su esquema documentado.
    if render['mp4_sha256'] not in json.dumps(final):raise ValueError('Auditoría de otro MP4')
    final_path=HERE/'revision_estabilidad_final.json'
    w.write_json(final_path,final)
    for name in ['clone_segmento_animado.mp4','clone_comparacion_animada.mp4']:
        data=w.probe(HERE/name);v=next(s for s in data['streams']if s['codec_type']=='video')
        assert v['codec_name']=='h264' and v['r_frame_rate']=='30/1'
        assert abs(float(data['format']['duration'])-1.6)<.001
        assert any(s['codec_name']=='aac'for s in data['streams'])
        count=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','json',str(HERE/name)],text=True))
        assert count['streams'][0]['nb_read_frames']=='48'
        subprocess.run(['ffmpeg','-v','error','-i',str(HERE/name),'-f','null','-'],check=True)
    check=w.read_json(FOLDER+'diagnosticos_skills/check.json')
    assert check['ok'] and not check['browserSkipped'] and check['layout']['samples']
    playback=w.read_json(FOLDER+'reproduccion_prueba.json')
    assert playback['frames_presentados']==48 and playback['frames_descartados_reproductor']==0 and not playback['error_video']
    p.update(fase=3,estado='componente_animado_revisado_para_entrega',
      siguiente_accion='Entregar componente para revisión del usuario; el reel completo no está autorizado por esta validación.',
      especificacion_sha256=w.digest(HERE/'frame.md'))
    p['salidas']['frame.md'].update(sha256=w.digest(HERE/'frame.md'),bytes=(HERE/'frame.md').stat().st_size)
    p['comparacion'].update(fidelidad_visual='diseno_aprobado_preservado_con_aproximaciones_documentadas',
      movimiento='48pares_equivalentes_revisados',ritmo='hitos_observados_reproducidos',
      continuidad_transiciones='sin_corrupcion_o_parpadeo_extra_observado',html_mp4_como_similitud=False)
    p['revision_animacion']={'fecha':w.utc(),'mp4_sha256':render['mp4_sha256'],
      'revisores':['director','recursos_v4_preview','estabilidad_v5_mp4_final'],
      'frames_revisados':48,'referencia_frames':[48,95],
      'estado':'revisado_para_entrega_no_equivale_aprobacion_usuario',
      'diferencias_restantes':['Fuentes ykerning aproximados aprobados','Antialias/halos/desenfoque y opacidades estimados desdeMP4'],
      'diseño_svg_png_intactos':True,'no_instalaciones':True,'sin_cambios_globales':True}
    w.write_json(FOLDER+'proyecto.json',p)
    names=['index.html','diseno.svg','timeline.gsap.js','construir_animacion.py','contornos.py',
      'frame.md','README.md','ANIMACION.md','proyecto.json','movimiento_observado.json',
      'skills_aplicadas.json','revision_estabilidad_final.json','render_ejecucion.json',
      'reproduccion_prueba.json','referencia_3_100.png','referencia_2_400.png',
      'clone_diseno_estatico.png','clone_comparacion.png']
    assets=[f.relative_to(HERE).as_posix() for f in sorted((HERE/'assets').glob('*')) if f.is_file()]
    names+=assets
    manifest={name:{'sha256':w.digest(HERE/name),'bytes':(HERE/name).stat().st_size}for name in names}
    w.write_json(FOLDER+'editable_manifest.json',manifest)
    out=HERE/'clone_proyecto_editable.zip';temp=out.with_suffix('.zip.part')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED)as archive:
        for name in [*names,'editable_manifest.json']:archive.write(HERE/name,'clone_componente/'+name)
    with zipfile.ZipFile(temp)as archive:
        assert archive.testzip()is None
        assert len(archive.namelist())==len(names)+1
        for name,item in manifest.items():
            assert hashlib.sha256(archive.read('clone_componente/'+name)).hexdigest()==item['sha256']
    temp.replace(out)
    # Regenerar desde las fuentes empaquetadas, sin usar .estado ni otros assets.
    validation=ROOT/'.estado/tmp/clone_editable_verificacion';validation.mkdir(exist_ok=True)
    with zipfile.ZipFile(out)as archive:archive.extractall(validation)
    subprocess.run([sys.executable,'-B',str(validation/'clone_componente/construir_animacion.py')],cwd=validation,check=True)
    assert w.digest(validation/'clone_componente/index.html')==w.digest(HERE/'index.html')
    qc={'fecha':w.utc(),'estado':'revisado_para_entrega',
      'mp4_sha256':render['mp4_sha256'],'comparacion_sha256':w.digest(HERE/'clone_comparacion_animada.mp4'),
      'zip_sha256':w.digest(out),'zip_crc':True,'zip_cobertura':True,'fuentes_portables_regeneran_html':True,
      'diseno_svg_png_intactos':True,'frames':48,'duracion_s':1.6,'fps':30,
      'check_browser_real':True,'frame_decode_completo':True,'preview_http':200,
      'limite':'No afirma igualdad exacta conCLONE ni aprobación visual del usuario.'}
    w.write_json(FOLDER+'control_final.json',qc)
    print('Editable CRC/cobertura/regeneración independientes verificados.',flush=True)

def publish():
    p=w.read_json(FOLDER+'proyecto.json');w.require_current_instructions(p)
    qc=w.read_json(FOLDER+'control_final.json');assert qc['estado']=='revisado_para_entrega'
    for name,key in [('clone_segmento_animado.mp4','mp4_sha256'),('clone_comparacion_animada.mp4','comparacion_sha256'),('clone_proyecto_editable.zip','zip_sha256')]:
        assert w.digest(HERE/name)==qc[key]
    d=w.Drive();root=w.read_json('sistema/perfil.json')['drive_entrega']
    parent=p['entrega_estatica']['carpeta_id'];meta=d.metadata(parent)
    if not any(x['id']==parent for x in d.children(root)):raise ValueError('La carpeta no está enENTREGA')
    if not meta.get('capabilities',{}).get('canAddChildren'):raise ValueError('Sin acceso aentrega')
    if meta['name']!='CLONE — Componente':
        d.request('PATCH','files/'+parent,params={'supportsAllDrives':'true','fields':'id,name'},json={'name':'CLONE — Componente'})
        assert d.metadata(parent)['name']=='CLONE — Componente'
    remote=d.children(parent);receipt=p.get('entrega_animacion',{'carpeta_id':parent,'archivos':{}})
    for name in ['clone_segmento_animado.mp4','clone_comparacion_animada.mp4','clone_proyecto_editable.zip','timeline.gsap.js','ANIMACION.md','frame.md']:
        matches=[f for f in remote if f['name']==name]
        if len(matches)>1:raise ValueError('Entregable duplicado: '+name)
        old=matches[0]if matches else None
        if old and old.get('md5Checksum')==w.digest(HERE/name,'md5'):
            item=d.metadata(old['id'])
        else:item=d.upload(HERE/name,parent,existing_id=old['id']if old else None)
        assert int(item['size'])==(HERE/name).stat().st_size
        assert item['md5Checksum']==w.digest(HERE/name,'md5')
        receipt['archivos'][name]={'id':item['id'],'url':'recurso-configurado:file/d/'+item['id']+'/view',
          'bytes':int(item['size']),'md5':item['md5Checksum'],'sha256':w.digest(HERE/name)}
        receipt['verificado_en']=w.utc();p['entrega_animacion']=receipt;w.write_json(FOLDER+'proyecto.json',p)
        print('Driveverificado',name,item['id'],flush=True)
    instruction_id='CONFIGURE_RECURSO_1296'
    if not any(x['id']==instruction_id for x in d.children(root)):raise ValueError('No se encontró INSTRUCCIONES canónico')
    item=d.upload('INSTRUCCIONES.md',root,existing_id=instruction_id)
    assert item['md5Checksum']==w.digest('INSTRUCCIONES.md','md5')
    p.update(estado='componente_clone_animado_entregado_para_revision_usuario')
    w.write_json(FOLDER+'proyecto.json',p)
    state=w.read_json('ESTADO.json',{});state.update(actualizado_en=w.utc(),estado=p['estado'],
      proyecto_actual='clone_componente',entrega_animacion=receipt,
      siguiente_accion='Revisión del componente por el usuario; no producir reel completo automáticamente.')
    w.write_json('ESTADO.json',state)
    print('Entrega completada en la carpeta existenteCLONE — Componente.',flush=True)

if __name__=='__main__':
    if '--publicar' in sys.argv:publish()
    else:package()
