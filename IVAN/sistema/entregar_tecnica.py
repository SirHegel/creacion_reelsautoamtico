"""Empaquetar/publicar solo la prueba de arquitectura realmente revisada."""
import sys,subprocess,zipfile
sys.dont_write_bytecode=True
import workflow as w
from skills import validate
FOLDER='ejemplos/arquitectura_motion_3s'
def run():
    p=w.read_json(FOLDER+'/proyecto.json');a=w.read_json(FOLDER+'/auditoria_arquitectura.json')
    w.require_current_instructions(p);validate(p,phase='render')
    if a.get('estado')!='revisada_para_entrega_tecnica' or not a.get('revision_visual') or not all(a['comprobaciones'].values()):
        raise ValueError('Prueba técnica sin revisión completa')
    for file,key in [('prueba_gsap_3s.mp4','sha256'),('timeline.gsap.js','timeline_sha256'),('index.html','html_sha256')]:
        if w.digest(FOLDER+'/'+file)!=a[key]:raise ValueError('Prueba o fuentes cambiaron después de revisar')
    for name,sha in p['dependencias'].items():
        if w.digest(FOLDER+'/lib/'+name)!=sha:raise ValueError('Dependencia GSAP modificada tras revisión')
    docs=['AGENTS.md','INSTRUCCIONES.md','PROMPT_MAESTRO.md','STYLE_YO.md',
      'sistema/AUDITORIA_WORKFLOW.md','sistema/skills.py','sistema/skills_entorno.mjs','sistema/confinar.mjs',
      'sistema/skills_instaladas.json','sistema/auditoria_skills_globales.json','sistema/perfil.json',
      'sistema/workflow.py','sistema/render.py','sistema/preflight.py','sistema/seleccion.py',
      'sistema/prueba_tecnica.py','sistema/verificar_gsap.mjs','sistema/auditar_gsap.py','sistema/auditar_temporal.py',
      'sistema/verificar.py','sistema/entregar_tecnica.py','sistema/entregar_prueba.py',
      'sistema/auditar_prueba.py','sistema/herramientas.json']
    files=[w.inside(x) for x in docs]
    files += [f for f in w.inside('.agents/skills').rglob('*') if f.is_file()]
    files += [f for f in w.inside(FOLDER).rglob('*') if f.is_file() and f.suffix not in ['.mp4','.zip','.part'] and f.name!='render.log']
    package=FOLDER+'/editable_gsap_3s.zip';temp=w.inside(package+'.part')
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for file in sorted(set(files)):
                name=str(file.relative_to(w.ROOT))
                if name.startswith('.estado/'):raise ValueError('Archivo privado en editable')
                if name==FOLDER+'/proyecto.json':
                    snapshot=dict(p);snapshot.pop('entrega_tecnica',None);z.writestr(name,__import__('json').dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
                else:z.write(file,name)
        with zipfile.ZipFile(temp) as z:
            required={FOLDER+'/index.html',FOLDER+'/timeline.gsap.js',FOLDER+'/lib/gsap.min.js',FOLDER+'/lib/MotionPathPlugin.min.js',FOLDER+'/lib/MorphSVGPlugin.min.js'}
            if not required.issubset(z.namelist()) or z.testzip():raise ValueError('Paquete incompleto o corrupto')
        temp.replace(w.inside(package))
    finally:temp.unlink(missing_ok=True)
    print('Editable íntegro:',w.inside(package).stat().st_size,'bytes',flush=True)
    d=w.Drive();cfg=w.read_json('sistema/perfil.json');root=cfg['drive_entrega'];receipt=p.get('entrega_tecnica') or {};parent=receipt.get('carpeta_id')
    roots=d.children(root);name='Prueba GSAP 3s'
    if not parent:
        matches=[f for f in roots if f['name']==name]
        if len(matches)>1:raise ValueError('Carpetas técnicas repetidas')
        parent=matches[0]['id'] if matches else d.request('POST','files',params={'supportsAllDrives':'true','fields':'id'},json={'name':name,'mimeType':'application/vnd.google-apps.folder','parents':[root],'appProperties':{'tipo':'arquitectura_gsap_3s'}}).json()['id']
        receipt={'carpeta_id':parent,'archivos':{}};p['entrega_tecnica']=receipt;w.write_json(FOLDER+'/proyecto.json',p)
    if not d.metadata(parent).get('capabilities',{}).get('canAddChildren'):raise ValueError('Carpeta técnica sin acceso de escritura')
    deliverables=[FOLDER+'/prueba_gsap_3s.mp4',FOLDER+'/timeline.gsap.js',package,FOLDER+'/README.md',FOLDER+'/fotogramas_gsap.jpg','sistema/AUDITORIA_WORKFLOW.md']
    for file in [*deliverables,'INSTRUCCIONES.md']:
        destination=root if file=='INSTRUCCIONES.md' else parent;filename=w.inside(file).name
        matches=[x for x in d.children(destination) if x['name']==filename]
        if len(matches)>1:raise ValueError('Entrega repetida: '+filename)
        remote=d.metadata(matches[0]['id']) if matches else None
        if not remote or int(remote.get('size',0))!=w.inside(file).stat().st_size or remote.get('md5Checksum')!=w.digest(file,'md5'):
            subprocess.run(['rclone','--config',str(w.inside('.estado/rclone.conf')),'--cache-dir',str(w.inside('.estado/cache')),
              'copyto',str(w.inside(file)),'gdrive:'+filename,'--drive-root-folder-id',destination,
              '--tpslimit','1','--transfers','1','--checkers','1','--retries','5','--low-level-retries','5'],check=True)
            matches=[x for x in d.children(destination) if x['name']==filename]
            if len(matches)!=1:raise ValueError('Archivo ausente/repetido después de subir')
            remote=d.metadata(matches[0]['id'])
        if int(remote.get('size',0))!=w.inside(file).stat().st_size or remote.get('md5Checksum')!=w.digest(file,'md5'):
            raise ValueError('Tamaño o MD5 diferente en Drive: '+filename)
        receipt['archivos'][filename]={'id':remote['id'],'bytes':int(remote['size']),'md5':remote['md5Checksum'],'sha256':w.digest(file),'url':'recurso-configurado:file/d/'+remote['id']+'/view'}
        receipt['verificado_en']=w.utc();p['entrega_tecnica']=receipt;w.write_json(FOLDER+'/proyecto.json',p)
        print('Verificado en Drive:',filename,remote['id'],remote['size'],'bytes',flush=True)
    p['estado']='arquitectura_verificada_y_entregada';w.write_json(FOLDER+'/proyecto.json',p)
    state=w.read_json('ESTADO.json',{});state.update(actualizado_en=w.utc(),estado=p['estado'],proyecto_activo=p['id'],ultimo_proyecto=FOLDER+'/proyecto.json',manual=w.manual(),
      alcance_actual='Prueba técnica de 3 s, sin edición completa',referencias_vigentes={'motion':'CLONE exclusivo','identidad':'YO'},entrega_tecnica=receipt,
      arquitectura={'gsap':'3.15.0','hyperframes':'0.8.147','skills_locales':12,'tweens':32,'frames':90,'regresiones_aprobadas':24,'mp4_sha256':a['sha256'],'informe':'sistema/AUDITORIA_WORKFLOW.md'},
      siguiente_accion='Revisión del usuario de la prueba técnica. El siguiente reel debe releer prompt/skills y crear storyboard contextual con CLONE para motion y YO para identidad; no producir completo sin indicación y muestra aprobada.')
    w.write_json('ESTADO.json',state)
    print('Carpeta final: recurso-configurado:drive/folders/'+parent,flush=True)
if __name__=='__main__':run()
