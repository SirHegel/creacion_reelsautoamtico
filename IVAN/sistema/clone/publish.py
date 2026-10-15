"""Entrega autorizada, idempotente y verificada en ENTREGA/CLONE—Motor."""
import json,pathlib,sys
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import engine
w=engine.w;ROOT=engine.ROOT;PARENT='CONFIGURE_RECURSO_0521'

def publish():
    import importlib.util
    spec=importlib.util.spec_from_file_location('clone_package',HERE/'package.py');package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
    archive=package.build();drive=w.Drive();parent=drive.metadata(PARENT)
    if parent.get('mimeType')!='application/vnd.google-apps.folder' or parent.get('name')!='ENTREGA':raise ValueError('Destino no coincide con la entrega autorizada')
    children=drive.children(PARENT);matches=[x for x in children if x['name']=='CLONE — Motor' and x['mimeType']=='application/vnd.google-apps.folder']
    if len(matches)>1:raise ValueError('Más deuna carpeta canónica; resolver sin eliminar archivos ajenos')
    if matches:folder=drive.metadata(matches[0]['id'])
    else:
        created=drive.request('POST','files',params={'supportsAllDrives':'true','fields':'id'},json={'name':'CLONE — Motor','mimeType':'application/vnd.google-apps.folder','parents':[PARENT]}).json()
        folder=drive.metadata(created['id'])
    records=drive.children(folder['id']);receipt={'parent':PARENT,'folder':folder,'archive':archive,'files':{},'verified':False}
    target='proyectos/clone_motor/entrega.json';w.write_json(target,receipt)
    jobs=[('proyectos/clone_motor/demo_nueva/preview.mp4','demo_claude_10s.mp4'),('proyectos/clone_motor/demo_equipo/preview.mp4','demo_equipo_6s.mp4'),
      ('proyectos/clone_motor/clone_motor_editable.zip',None),('proyectos/clone_motor/INFORME_FINAL.md',None),('proyectos/clone_motor/registro_componentes.json',None),('sistema/clone/README.md',None)]
    is_b_v2=engine.load('proyectos/clone_motor/creatividad/comparacion/scene.json').get('editorial_revision',{}).get('version')=='B_V2'
    jobs += [('proyectos/clone_motor/creatividad/app/preview.mp4','A_herramienta_a_app_9s.mp4'),
      ('proyectos/clone_motor/creatividad/comparacion/'+('B_V1.mp4' if is_b_v2 else 'preview.mp4'),'B_ia_compara_9s.mp4'),
      ('proyectos/clone_motor/creatividad/agente/preview.mp4','C_agente_resultado_9s.mp4'),
      ('proyectos/clone_motor/creatividad/app/comparacion_clone.png','A_comparacion_CLONE.png'),
      ('proyectos/clone_motor/creatividad/comparacion/comparacion_clone.png','B_comparacion_CLONE.png'),
      ('proyectos/clone_motor/creatividad/agente/comparacion_clone.png','C_comparacion_CLONE.png'),
      ('proyectos/clone_motor/creatividad/INFORME_FINAL.md','INFORME_CREATIVO.md')]
    if is_b_v2:
        jobs[-1]=('proyectos/clone_motor/creatividad/comparacion/B_V2_INFORME.md','INFORME_CREATIVO.md')
        jobs += [('proyectos/clone_motor/creatividad/comparacion/preview.mp4','B_V2.mp4'),
          ('proyectos/clone_motor/creatividad/comparacion/B_V1_vs_B_V2.mp4','B_V1_vs_B_V2.mp4'),
          ('proyectos/clone_motor/creatividad/comparacion/B_V1_vs_B_V2.png','B_V1_vs_B_V2.png')]
    for source,name in jobs:
        file=w.inside(source);remote_name=name or file.name
        match=[r for r in records if r['name']==remote_name]
        if len(match)>1:raise ValueError('Nombre duplicado en destino: '+remote_name)
        previous=match[0]if match else None
        if previous and previous.get('md5Checksum')==w.digest(file,'md5'):remote=drive.metadata(previous['id'])
        else:
            # upload preserva sharing y verifica MD5/tamaño tras escritura.
            remote=drive.upload(file,folder['id'],previous['id']if previous else None)
            if remote_name!=file.name:
                drive.request('PATCH','files/'+remote['id'],params={'supportsAllDrives':'true'},json={'name':remote_name})
                remote=drive.metadata(remote['id'])
        if remote.get('md5Checksum')!=w.digest(file,'md5') or int(remote.get('size',0))!=file.stat().st_size:raise ValueError('Readback no coincide: '+remote_name)
        receipt['files'][remote_name]={'id':remote['id'],'url':remote.get('webViewLink'),'local':source,'bytes':file.stat().st_size,'md5':remote['md5Checksum'],'sha256':w.digest(file)}
        w.write_json(target,receipt);print(remote_name,'VERIFICADO',flush=True)
    # Actualizar instrucciones compactas vigentes conservando su ID y carpeta.
    ident='CONFIGURE_RECURSO_1296';meta=drive.metadata(ident)
    if meta.get('name')!='INSTRUCCIONES.md':raise ValueError('No coincide el documento canónico de instrucciones')
    latest=drive.upload('INSTRUCCIONES.md',PARENT,ident)
    receipt['instructions']={'id':ident,'url':latest.get('webViewLink'),'md5':latest.get('md5Checksum'),'sha256':w.digest('INSTRUCCIONES.md')}
    final_children=drive.children(folder['id']);ids={x['id']for x in final_children}
    if not all(record['id']in ids for record in receipt['files'].values()):raise ValueError('Entrega no localizada bajo el padre esperado')
    receipt.update(verified=True,verified_at=w.utc());w.write_json(target,receipt)
    state=w.read_json('ESTADO.json',{});state['entrega_motor']={'archivo':target,'folder_id':folder['id'],'url':folder.get('webViewLink'),'verified':True,'date':w.utc()};w.write_json('ESTADO.json',state)
    return receipt
if __name__=='__main__':
    r=publish();print(json.dumps({'verified':r['verified'],'folder':r['folder']['webViewLink'],'files':{k:v['url']for k,v in r['files'].items()}},ensure_ascii=False))
