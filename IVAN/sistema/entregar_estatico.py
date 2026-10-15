"""Entrega autorizada del diseño para revisión; no aprueba ni anima el componente."""
import sys
sys.dont_write_bytecode=True
import workflow as w
from PIL import Image

FOLDER='ejemplos/clone_componente'

def run():
    p=w.read_json(FOLDER+'/proyecto.json')
    w.require_current_instructions(p)
    if p['fase']!=1 or p['animacion_implementada'] or p['aprobacion_diseno']['usuario_aprobo']:
        raise ValueError('Este comando entrega solo la FASE1 pendiente de revisión')
    for name,item in p['salidas'].items():
        if w.digest(item['archivo'])!=item['sha256']:
            raise ValueError('Diseño cambió después de la revisión estática: '+name)
    for name,size in [('clone_diseno_estatico.png',(1080,1920)),('clone_comparacion.png',(2162,2016))]:
        with Image.open(w.inside(FOLDER+'/'+name)) as im:
            if im.format!='PNG' or im.size!=size:
                raise ValueError('Imagen de entrega inválida')
            im.verify()
    d=w.Drive();root=w.read_json('sistema/perfil.json')['drive_entrega']
    receipt=p.get('entrega_estatica',{});parent=receipt.get('carpeta_id')
    if not parent:
        matches=[x for x in d.children(root) if x['name']=='CLONE — Diseño estático']
        if len(matches)>1:raise ValueError('Carpeta de diseño duplicada')
        parent=matches[0]['id'] if matches else d.request('POST','files',params={'supportsAllDrives':'true','fields':'id'},json={
            'name':'CLONE — Diseño estático','mimeType':'application/vnd.google-apps.folder','parents':[root],
            'appProperties':{'proyecto':'clone_componente','fase':'diseno_estatico_pendiente_aprobacion'}}).json()['id']
        receipt={'carpeta_id':parent,'archivos':{}}
        p['entrega_estatica']=receipt;w.write_json(FOLDER+'/proyecto.json',p)
    if not d.metadata(parent).get('capabilities',{}).get('canAddChildren'):
        raise ValueError('Carpeta de entrega sin permiso de escritura')
    remote_files=d.children(parent)
    for name in ['clone_diseno_estatico.png','clone_comparacion.png','diseno.svg','frame.md']:
        file=FOLDER+'/'+name
        matches=[x for x in remote_files if x['name']==name]
        if len(matches)>1:raise ValueError('Archivo de entrega duplicado: '+name)
        old=matches[0] if matches else None
        if old and old.get('md5Checksum')==w.digest(file,'md5') and int(old.get('size',0))==w.inside(file).stat().st_size:
            remote=d.metadata(old['id'])
        else:
            remote=d.upload(file,parent,existing_id=old['id'] if old else None)
        if int(remote['size'])!=w.inside(file).stat().st_size or remote['md5Checksum']!=w.digest(file,'md5'):
            raise ValueError('PNG/fuente diferente en Drive: '+name)
        receipt['archivos'][name]={'id':remote['id'],'bytes':int(remote['size']),
            'md5':remote['md5Checksum'],'sha256':w.digest(file),
            'url':'recurso-configurado:file/d/'+remote['id']+'/view'}
        receipt['verificado_en']=w.utc()
        p['entrega_estatica']=receipt;w.write_json(FOLDER+'/proyecto.json',p)
        print('Entrega para revisión verificada:',name,remote['id'],flush=True)
    state=w.read_json('ESTADO.json',{})
    state.update(actualizado_en=w.utc(),estado=p['estado'],entrega_estatica=receipt)
    w.write_json('ESTADO.json',state)
    print('Diseño pendiente de aprobación: recurso-configurado:drive/folders/'+parent,flush=True)

if __name__=='__main__':run()
