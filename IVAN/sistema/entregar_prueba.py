"""Publicar una prueba revisada y sus fuentes; no aprueba ni publica el completo."""
import sys,subprocess,zipfile
sys.dont_write_bytecode=True
import workflow as w

def entregar(ID):
    folder='proyectos/'+ID;p=w.read_json(folder+'/proyecto.json');a=w.read_json(folder+'/auditoria_muestra.json')
    w.require_current_instructions(p);w.require_resource_selection(p,hasta=10)
    video=folder+'/'+p['muestra_nombre']
    if not all(a['comprobaciones'].values()) or a['sha256']!=w.digest(video) or a['edicion_sha256']!=w.edit_digest(p):
        raise ValueError('La prueba y su auditoría no corresponden a la edición actual')
    w.require_sample_review(p,a)
    if w.read_json('sistema/perfil.json').get('skills_obligatorias'):
        from skills import validate
        validate(p,phase='render')
    if p.get('directiva')=='ASCENDIA V5':
        package=next((path for path in p.get('entregables_prueba',[]) if path.endswith('.zip')),None)
        if not package:raise ValueError('Preparar el paquete editable completo antes de publicar')
        with zipfile.ZipFile(w.inside(package)) as z:
            required={p['original']['archivo'],p['motor']['composicion'],p['motor']['fuente'],'sistema/motion.js','sistema/componentes_motion.js','STYLE_YO.md'}
            required.update(r['archivo'] for r in p['recursos'])
            if not required.issubset(z.namelist()) or z.testzip() or any(n.startswith('.estado/') for n in z.namelist()):
                raise ValueError('Paquete incompleto o privado; corregir antes de crear carpeta o subir entregas')
    d=w.Drive();cfg=w.read_json('sistema/perfil.json');prior=(p.get('entrega') or {}).get('archivos',{})
    rootfiles=d.children(cfg['drive_entrega'])
    parent=(p.get('entrega_prueba') or p.get('entrega') or {}).get('carpeta_id')
    if not parent:
        name=p.get('carpeta_entrega_nombre',w.inside(p['nombre_original']).stem)
        matches=[f for f in rootfiles if f['mimeType']=='application/vnd.google-apps.folder' and (f.get('appProperties',{}).get('crudo_id')==ID or f['name']==name)]
        if len(matches)>1:raise ValueError('Carpetas duplicadas en ENTREGA')
        if matches:parent=matches[0]['id']
        else:
            if not d.metadata(cfg['drive_entrega']).get('capabilities',{}).get('canAddChildren'):raise ValueError('ENTREGA sin acceso de escritura')
            parent=d.request('POST','files',params={'supportsAllDrives':'true','fields':'id'},json={'name':name,'mimeType':'application/vnd.google-apps.folder','parents':[cfg['drive_entrega']],'appProperties':{'crudo_id':ID}}).json()['id']
        p['entrega_prueba']={'carpeta_id':parent,'estado':'pendiente_aprobacion_usuario','archivos':{}}
        w.write_json(folder+'/proyecto.json',p);rootfiles=d.children(cfg['drive_entrega'])
    if not any(f['id']==parent for f in rootfiles):raise ValueError('La carpeta del proyecto no está en ENTREGA')
    if not d.metadata(parent).get('capabilities',{}).get('canAddChildren'):raise ValueError('Carpeta sin acceso de escritura')
    children=d.children(parent);receipt=p.get('entrega_prueba',{'carpeta_id':parent,'estado':'pendiente_aprobacion_usuario','archivos':{}})
    if p.get('entregables_prueba'):
        files=[(path,parent,None) for path in p['entregables_prueba']]
    else:
        files=[(video,parent,None),(folder+'/informe_ascendia_v4_prueba.pdf',parent,prior.get('informe_ascendia_v3.pdf',{}).get('id')),
               (folder+'/fuentes_prueba_ascendia_v4.zip',parent,prior.get('fuentes.zip',{}).get('id')),(folder+'/broll_manifest.csv',parent,None)]
    if video not in [x[0] for x in files]:raise ValueError('Incluir la prueba auditada en los entregables')
    if any(not w.inside(x[0]).is_file() for x in files):raise ValueError('Preparar todos los entregables antes de publicar')
    md=next((f for f in rootfiles if f['name']=='INSTRUCCIONES.md'),None)
    files.append(('INSTRUCCIONES.md',cfg['drive_entrega'],md['id'] if md else None))
    for path,destination,previous in files:
        name=w.inside(path).name;matches=[f for f in children if f['name']==name]
        if len(matches)>1:raise ValueError('Entrega duplicada: '+name)
        identifier=(receipt['archivos'].get(name) or {}).get('id') or (matches[0]['id'] if matches else previous)
        # Rclone ya instalado: limitar ritmo y reintentar cuotas compartidas sin cambiar cuenta.
        current=d.metadata(identifier) if identifier else None
        if current and int(current.get('size',0))==w.inside(path).stat().st_size and current.get('md5Checksum')==w.digest(path,'md5'):
            remote=current
        else:
            remote_name=current['name'] if current else name
            subprocess.run(['rclone','--config',str(w.inside('.estado/rclone.conf')),'--cache-dir',str(w.inside('.estado/cache')),
                'copyto',str(w.inside(path)),'gdrive:'+remote_name,'--drive-root-folder-id',destination,
                '--tpslimit','1','--transfers','1','--checkers','1','--retries','5','--low-level-retries','5','--stats','15s','--stats-one-line'],check=True)
            found=[x for x in d.children(destination) if x['name']==remote_name]
            if len(found)!=1:raise ValueError('Entrega ausente o repetida tras subir: '+remote_name)
            remote=d.metadata(found[0]['id'])
            if int(remote.get('size',0))!=w.inside(path).stat().st_size or remote.get('md5Checksum')!=w.digest(path,'md5'):
                raise ValueError('La entrega no coincide por tamaño y MD5')
        if remote['name']!=name:
            d.request('PATCH','files/'+remote['id'],params={'supportsAllDrives':'true'},json={'name':name})
        receipt['archivos'][name]={'id':remote['id'],'bytes':int(remote['size']),'md5':remote['md5Checksum'],'sha256':w.digest(path),'url':'recurso-configurado:file/d/'+remote['id']+'/view'}
        receipt['verificado_en']=w.utc();p['entrega_prueba']=receipt
        w.write_json(folder+'/proyecto.json',p)
        print('Verificado en Drive:',name,remote['id'],remote['size'],'bytes',flush=True)
    # El MP4 anterior conserva su ID y bytes; solo hay un editable y reporte vigentes.
    if p.get('entrega'):p['entrega']['archivos']={k:v for k,v in prior.items() if k== 'final_ascendia_v3.mp4'}
    p['etapa']='prueba_revisada_entregada_pendiente_aprobacion_usuario';w.write_json(folder+'/proyecto.json',p)
    state=w.read_json('ESTADO.json',{});state.update(estado=p['etapa'],proyecto_activo=ID,manual=w.manual(),prueba_sha256=w.digest(video),entrega_prueba=receipt,siguiente_accion='Revisión del usuario de la prueba de diez segundos. No producir el completo sin una nueva indicación y aprobación.')
    w.write_json('ESTADO.json',state)
    print('Prueba entregada; completo pendiente de aprobación del usuario',flush=True)

if __name__=='__main__':entregar(sys.argv[1])
