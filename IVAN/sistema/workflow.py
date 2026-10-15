#!/usr/bin/env python3
"""Workflow de Presentador. Todos los archivos propios permanecen dentro de IVAN.

La auditoría editorial la realiza el agente sobre imagen y sonido reales.
Este programa prepara material y verifica entregas; no inventa una aprobación.
"""
import argparse
import configparser
import hashlib
import html
from html.parser import HTMLParser
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.dont_write_bytecode = True
PRIVATE = ROOT / '.estado'
PRIVATE.mkdir(exist_ok=True, mode=0o700)
for key, sub in {'TMPDIR': 'tmp', 'XDG_CACHE_HOME': 'cache', 'HF_HOME': 'cache/huggingface',
                 'MPLCONFIGDIR': 'cache/matplotlib', 'NUMBA_CACHE_DIR': 'cache/numba'}.items():
    folder = PRIVATE / sub
    folder.mkdir(parents=True, exist_ok=True)
    os.environ[key] = str(folder)
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
local_ffmpeg=PRIVATE/'herramientas/ffmpeg/bin'
if local_ffmpeg.is_dir():os.environ['PATH']=str(local_ffmpeg)+os.pathsep+os.environ['PATH']
import requests


def inside(path):
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError('Ruta fuera de IVAN: ' + str(path))
    return p


def read_json(path, default=None):
    p = inside(path)
    return json.loads(p.read_text()) if p.exists() else default


def write_json(path, data):
    p = inside(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = inside(str(p) + '.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(p)


def digest(path, algo='sha256'):
    h = hashlib.new(algo)
    with inside(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def edit_digest(project):
    """Vincula la auditoría con las decisiones, el motor y los recursos efectivos."""
    config = read_json('sistema/perfil.json')
    paths = {item['archivo'] for item in project.get('recursos', []) if item.get('archivo')}
    paths.update(config['archivos_tipografia'].values())
    actual_assets = {path: digest(path) for path in sorted(paths)}
    definition = {key: project.get(key) for key in ('escenas', 'audio', 'burns', 'motion_graphics', 'presentador', 'subtitulos', 'motor')}
    # Una decisión de revisión no modifica píxeles ni vuelve obsoleta una muestra.
    definition['escenas'] = [{key:value for key,value in scene.items() if key != 'estado'}
                            for scene in project.get('escenas', [])]
    # El render depende de código vectorial, la composición y las posiciones reales del rostro.
    source_paths = ['sistema/render.py', 'sistema/motion.js', 'sistema/confinar.mjs','sistema/seleccion.py','recursos/gsap.min.js']
    if project.get('directiva')=='ASCENDIA V5':source_paths.append('sistema/componentes_motion.js')
    if project.get('style_yo',{}).get('archivo'):
        source_paths.append(project['style_yo']['archivo'])
    selection_path='proyectos/'+project['id']+'/seleccion_recursos.json'
    if inside(selection_path).is_file():source_paths.append(selection_path)
    if project.get('motor',{}).get('fuente'):source_paths.append(project['motor']['fuente'])
    if project.get('motor', {}).get('composicion'):
        source_paths.extend([project['motor']['composicion'], 'proyectos/'+project['id']+'/rostro.json'])
    source_hashes = {path: digest(path) for path in source_paths if inside(path).is_file()}
    definition.update(manual=manual()['sha256'], instrucciones=manual()['instrucciones_sha256'], original=digest(project['original']['archivo']),
                      recursos=actual_assets, motor=source_hashes,
                      exportacion=config['exportacion'], tipografia=config['archivos_tipografia'])
    return hashlib.sha256(json.dumps(definition, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def manual():
    text = inside('PROMPT_MAESTRO.md').read_text()
    for n in range(1, 16):
        if not re.search(r'^## ' + str(n) + r'\. ', text, re.M):
            raise ValueError('El manual completo debe conservar sus 15 secciones')
    documents={}
    for name in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md'):
        content=inside(name).read_text()
        documents[name]={'sha256':hashlib.sha256(content.encode()).hexdigest(),'caracteres':len(content)}
    combined=hashlib.sha256(json.dumps(documents,sort_keys=True).encode()).hexdigest()
    return {'archivo': 'PROMPT_MAESTRO.md', 'sha256': digest('PROMPT_MAESTRO.md'),
            'secciones': 15, 'caracteres': len(text),'lectura_completa':documents,
            'instrucciones_sha256':combined}


def require_current_instructions(project):
    current=manual();previous=project.get('manual',{})
    if previous.get('sha256')!=current['sha256'] or previous.get('instrucciones_sha256')!=current['instrucciones_sha256']:
        raise ValueError('Leer e integrar el prompt completo, sus modificaciones e INSTRUCCIONES.md antes de editar')
    if project.get('directiva')=='ASCENDIA V5':
        style=project.get('style_yo',{})
        if not style.get('archivo') or not inside(style['archivo']).is_file() or style.get('sha256')!=digest(style['archivo']):
            raise ValueError('Analizar visualmente YO y registrar STYLE_YO.md vigente antes de editar V5')
        if read_json('sistema/perfil.json').get('skills_obligatorias') and project.get('motor'):
            from skills import validate
            validate(project,phase='lectura')


def require_resource_selection(project,hasta=None):
    from seleccion import validar
    validar(project,hasta=hasta)


def probe(path):
    data = subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                                   '-of', 'json', str(inside(path))], text=True)
    return json.loads(data)


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.params = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'download-form':
            self.action = a.get('action')
        if tag == 'input' and a.get('name'):
            self.params[a['name']] = a.get('value', '')


def download(file_id, destination):
    """Descarga pública legítima; no descarga HTML como si fuera un video."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
        raise ValueError('ID de Drive inválido')
    dest = inside(destination)
    if dest.exists():
        probe(dest)
        return {'archivo': str(dest.relative_to(ROOT)), 'reutilizado': True,
                'sha256': digest(dest), 'bytes': dest.stat().st_size}
    dest.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    try:
        response = session.get('https://drive.usercontent.google.com/download',
                               params={'id': file_id, 'export': 'download', 'confirm': 't'},
                               stream=True, timeout=(20, 90))
        response.raise_for_status()
        if 'text/html' in response.headers.get('Content-Type', ''):
            parser = FormParser()
            parser.feed(response.text)
            if not parser.action:
                raise RuntimeError('Drive no proporciona descarga pública para ' + file_id)
            if not parser.action.startswith('https://drive.usercontent.google.com/'):
                raise RuntimeError('Destino de confirmación de Drive inesperado')
            response = session.get(parser.action, params=parser.params, stream=True, timeout=(20, 90))
            response.raise_for_status()
        if 'text/html' in response.headers.get('Content-Type', ''):
            raise RuntimeError('Drive devolvió una página, no un archivo: ' + file_id)
    except (requests.RequestException, RuntimeError):
        # Los crudos privados necesitan el acceso autorizado de la cuenta conectada.
        response = Drive().request('GET', 'files/' + file_id,
                                  params={'alt': 'media', 'supportsAllDrives': 'true'}, stream=True)
    tmp = inside(str(dest) + '.part')
    try:
        with tmp.open('wb') as f:
            for b in response.iter_content(1024 * 1024):
                f.write(b)
        probe(tmp)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    return {'archivo': str(dest.relative_to(ROOT)), 'sha256': digest(dest),
            'bytes': dest.stat().st_size, 'id': file_id}


class Drive:
    """Usa únicamente la configuración OAuth aislada en IVAN."""
    def __init__(self):
        self.config = inside('.estado/rclone.conf')
        self.session = requests.Session()
        self.refresh_headers()
    def refresh_headers(self):
        c = configparser.ConfigParser(interpolation=None)
        c.read(self.config)
        token = json.loads(c['gdrive']['token'])['access_token']
        self.session.headers['Authorization'] = 'Bearer ' + token
    def request(self, method, endpoint, **kwargs):
        url = endpoint if endpoint.startswith('https://') else 'https://www.googleapis.com/drive/v3/' + endpoint
        if not url.startswith('https://www.googleapis.com/'):
            raise ValueError('Endpoint inesperado')
        payload=kwargs.get('data');position=payload.tell() if hasattr(payload,'tell') else None
        for attempt in range(5):
            if attempt and position is not None:payload.seek(position)
            r = self.session.request(method, url, timeout=(20, 120), **kwargs)
            if r.status_code == 401 and attempt == 0:
                # rclone renueva exclusivamente su copia local; no altera la configuración global.
                target=read_json('sistema/perfil.json')['drive_entrega']
                subprocess.run(['rclone', '--config', str(self.config), '--cache-dir', str(PRIVATE/'cache'),
                                'lsjson', 'gdrive:', '--drive-root-folder-id',target,'--max-depth', '1'], capture_output=True, check=True)
                self.refresh_headers()
                continue
            if method == 'GET' and r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            if r.status_code in (403,429):
                error=r.json().get('error',{});reasons=[e.get('reason') for e in error.get('errors',[])];message=error.get('message','')
                rate_limited=(r.status_code==429 or any(reason in ('rateLimitExceeded','userRateLimitExceeded') for reason in reasons)
                              or ('Quota exceeded' in message and ('Requests per minute' in message or "quota metric 'Queries'" in message)))
                if rate_limited:
                    write_json('.estado/tmp/drive_cuota.json',{'fecha':utc(),'metodo':method,'status':r.status_code,'mensaje':message,'motivos':reasons,'retry_after':r.headers.get('Retry-After'),'intento':attempt+1})
                    time.sleep(min(10*(attempt+1),30))
                    continue
            if not r.ok:
                message = r.json().get('error', {}).get('message', str(r.status_code))
                raise RuntimeError('Drive ' + str(r.status_code) + ': ' + message)
            return r
        raise RuntimeError('Drive no respondió después de cinco intentos')
    def metadata(self, file_id):
        return self.request('GET', 'files/' + file_id, params={'supportsAllDrives': 'true',
                            'fields': 'id,name,mimeType,size,md5Checksum,capabilities,parents,webViewLink'}).json()
    def children(self, parent):
        result, page = [], None
        while True:
            params = {'q': "'" + parent + "' in parents and trashed=false", 'pageSize': 1000,
                      'fields': 'nextPageToken,files(id,name,mimeType,size,md5Checksum,modifiedTime,appProperties)',
                      'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true'}
            if page:
                params['pageToken'] = page
            data = self.request('GET', 'files', params=params).json()
            result.extend(data.get('files', []))
            page = data.get('nextPageToken')
            if not page:
                return result
    def upload(self, path, parent, existing_id=None):
        path = inside(path)
        metadata = {'name': path.name}
        method = 'PATCH' if existing_id else 'POST'
        if not existing_id:
            metadata['parents'] = [parent]
        endpoint = 'https://www.googleapis.com/upload/drive/v3/files' + ('/' + existing_id if existing_id else '')
        content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        response = self.request(method, endpoint, params={'uploadType': 'resumable', 'supportsAllDrives': 'true'},
                                json=metadata, headers={'X-Upload-Content-Type': content_type,
                                                       'X-Upload-Content-Length': str(path.stat().st_size)})
        location = response.headers['Location']
        with path.open('rb') as f:
            result = self.request('PUT', location, data=f, headers={'Content-Type': content_type,
                                                                  'Content-Length': str(path.stat().st_size)}).json()
        remote = self.metadata(result['id'])
        if int(remote.get('size', 0)) != path.stat().st_size or remote.get('md5Checksum') != digest(path, 'md5'):
            raise RuntimeError('No coincide el archivo publicado en Drive')
        return remote


def prepare_resources(keys):
    cfg = read_json('sistema/perfil.json')
    catalog = read_json('recursos/catalogo.json', {'archivos': {}, 'bibliotecas': {}})
    items = cfg['referencias'] + cfg['sonidos']
    for item in items:
        if keys and item['key'] not in keys:
            continue
        previous = catalog['archivos'].get(item['key'], {})
        record = {**previous, **item}
        try:
            record.update(download(item['id'], item['archivo']))
            record['metadata'] = probe(item['archivo'])
            record['estado'] = previous.get('estado', 'descargado_pendiente_revision') if record.get('reutilizado') else 'descargado_pendiente_revision'
        except Exception as e:
            record.update(estado='no_disponible', error=str(e))
        record['comprobado_en'] = utc()
        catalog['archivos'][item['key']] = record
        write_json('recursos/catalogo.json', catalog)
        print(item['key'], record['estado'], flush=True)


def inspect_drive(folder):
    drive = Drive()
    info = drive.metadata(folder)
    children = drive.children(folder)
    result = {'carpeta': info, 'archivos': children, 'fecha': utc()}
    write_json('.estado/inventario_drive.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


VIDEO_EXTENSIONS={'.mp4','.mov','.mkv','.webm','.m4v'}


def classify_raw(file, projects):
    """El nombre no identifica un crudo: comparar ID y contenido real."""
    for project in projects:
        source=project.get('original',{})
        ids={project['id'],source.get('id')}
        ids.update(source.get('ids_equivalentes',[]))
        same_id=file['id'] in ids
        same_content=bool(file.get('md5Checksum') and file['md5Checksum']==source.get('md5')
                          and int(file.get('size',0))==int(source.get('bytes',-1)))
        if same_id or same_content:
            if same_id and file.get('md5Checksum') and source.get('md5') and not same_content:
                return {'estado':'original_modificado','proyecto_id':project['id'],
                        'coincidencia':'ID con contenido diferente; requiere revisión'}
            return {'estado':'entregado' if project.get('etapa')=='entregado_verificado' else 'en_proceso',
                    'proyecto_id':project['id'],'coincidencia':'ID' if same_id else 'contenido_md5'}
    return {'estado':'nuevo','proyecto_id':None,'coincidencia':None}


def local_projects():
    result=[]
    for path in sorted((ROOT/'proyectos').glob('*/proyecto.json')):
        project=read_json(path);source=project.get('original',{})
        if source.get('archivo') and inside(source['archivo']).is_file():
            source['md5']=digest(source['archivo'],'md5')
            source['bytes']=inside(source['archivo']).stat().st_size
        result.append(project)
    return result


def scan_crudos(ingest_new=False, drive=None):
    cfg=read_json('sistema/perfil.json');folder_id=cfg.get('drive_crudos')
    if not folder_id:
        raise ValueError('Falta vincular la carpeta Crudos')
    if folder_id==cfg['drive_entrega']:
        raise ValueError('Crudos y ENTREGA deben ser carpetas diferentes')
    drive=drive or Drive();info=drive.metadata(folder_id)
    if info.get('mimeType')!='application/vnd.google-apps.folder' or not info.get('capabilities',{}).get('canListChildren'):
        raise ValueError('Crudos no es una carpeta accesible para listar archivos')
    projects=local_projects();items=[]
    for file in sorted(drive.children(folder_id),key=lambda f:(f.get('modifiedTime',''),f['id'])):
        if Path(file['name']).suffix.lower() not in VIDEO_EXTENSIONS or not file.get('mimeType','').startswith('video/'):
            continue
        status=classify_raw(file,projects)
        if status['estado'] in ('entregado','en_proceso'):
            project=next(p for p in projects if p['id']==status['proyecto_id'])
            aliases=project['original'].setdefault('ids_equivalentes',[])
            if file['id']!=project['id'] and file['id'] not in aliases:aliases.append(file['id'])
            project['entrada_drive']={'carpeta_id':folder_id,'archivo_id':file['id'],
                                     'md5':file.get('md5Checksum'),'verificado_en':utc()}
            write_json('proyectos/'+project['id']+'/proyecto.json',project)
        elif status['estado']=='nuevo' and ingest_new:
            canonical_id=ingest(file['id']);projects=local_projects()
            status={**classify_raw(file,projects),'proyecto_id':canonical_id}
            project=next(p for p in projects if p['id']==canonical_id)
            project['entrada_drive']={'carpeta_id':folder_id,'archivo_id':file['id'],
                                     'md5':file.get('md5Checksum'),'verificado_en':utc()}
            write_json('proyectos/'+canonical_id+'/proyecto.json',project)
        items.append({**file,**status})
    inventory={'carpeta':{'id':folder_id,'nombre':info['name']},'fecha':utc(),'archivos':items,
               'resumen':{state:sum(x['estado']==state for x in items)
                          for state in ('nuevo','en_proceso','entregado','original_modificado')},
               'modo':'ingesta_incremental' if ingest_new else 'inventario'}
    write_json('.estado/inventario_crudos.json',inventory)
    return inventory


def bind_crudos(folder_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',folder_id):raise ValueError('ID de carpeta inválido')
    cfg=read_json('sistema/perfil.json')
    if folder_id==cfg['drive_entrega']:raise ValueError('Crudos y ENTREGA deben ser carpetas diferentes')
    drive=Drive();info=drive.metadata(folder_id)
    if info.get('mimeType')!='application/vnd.google-apps.folder' or not info.get('capabilities',{}).get('canListChildren'):
        raise ValueError('No se puede leer la carpeta Crudos indicada')
    drive.children(folder_id)  # Comprobar acceso real antes de persistir la configuración.
    cfg['drive_crudos']=folder_id
    cfg['entrada_crudos']={'nombre_verificado':info['name'],'verificado_en':utc(),
                          'seleccion':'videos_directos','deduplicacion':'ID y tamaño/MD5',
                          'comando':'python3 -B sistema/workflow.py crudos --ingestar'}
    write_json('sistema/perfil.json',cfg)
    return scan_crudos(drive=drive)


def ingest(file_id):
    folder = inside('proyectos/' + file_id)
    project_file = folder / 'proyecto.json'
    if project_file.exists():
        existing = read_json(project_file)
        original = existing.get('original', {})
        if original.get('archivo') and not inside(original['archivo']).exists():
            source_id=existing.get('entrada_drive',{}).get('archivo_id',file_id)
            restored = download(source_id, original['archivo'])
            if original.get('sha256') and restored['sha256'] != original['sha256']:
                raise ValueError('El original de Drive cambió respecto al proyecto; revisar antes de renderizar')
            print('Original restaurado sin modificar el storyboard:', file_id)
            return file_id
        print('Proyecto existente, se conserva:', file_id)
        return file_id
    info = Drive().metadata(file_id)
    status=classify_raw(info,local_projects())
    if status['estado']=='original_modificado':
        raise ValueError('El crudo asociado cambió de contenido; revisar antes de ingestar')
    if status['proyecto_id']:
        print('Contenido existente; se reutiliza el proyecto:',status['proyecto_id'])
        return status['proyecto_id']
    extension = Path(info['name']).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise ValueError('El original debe ser un video')
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / ('original' + extension)
    data = download(file_id, source)
    project = {'id': file_id, 'nombre_original': info['name'], 'manual': manual(), 'etapa': 'analisis',
               'original': data, 'metadata': probe(source), 'creado_en': utc(), 'escenas': [],
               'recursos': [], 'motion_graphics': [], 'entrega': None}
    cfg=read_json('sistema/perfil.json')
    project['requiere_aprobacion_prueba_v4']=cfg['directiva_estructural']['aprobacion_prueba_requerida']
    project['aprobacion_usuario_prueba']={'estado':'pendiente'}
    project['muestra_nombre']=cfg['directiva_estructural'].get('prueba_nombre','prueba_ascendia_v4_10s.mp4')
    project['directiva']=cfg.get('directiva_vigente')
    project['montaje_desde_cero']=bool(cfg.get('montaje_nuevo_por_crudo'))
    style=cfg.get('style_observado')
    if style and inside(style).is_file():
        project['style_yo']={'archivo':style,'sha256':digest(style),'referencia':'A3_YO'}
    write_json(project_file, project)
    print('Original preparado:', file_id)
    return file_id


def transcribe(project_id, model):
    path = inside('proyectos/' + project_id + '/proyecto.json')
    project = read_json(path)
    if not project:
        raise ValueError('Proyecto inexistente')
    folder = path.parent
    transcript = folder / 'transcripcion.json'
    if transcript.exists():
        print('Transcripción existente; se conserva para revisión.')
        return
    if model=='parakeet':
        output=PRIVATE/'tmp'/('parakeet_'+project_id+'.json')
        local_python=PRIVATE/'python/bin/python'
        subprocess.run([str(local_python) if local_python.is_file() else sys.executable,'-B',str(ROOT/'sistema/parakeet.py'),project['original']['archivo'],'--bloque','60','--salida',str(output)],check=True)
        asr=json.loads(output.read_text());segments=[];batch=[]
        for word in asr['words']:
            if batch and word['start']-batch[-1]['end']>.30:
                segments.append(batch);batch=[]
            batch.append(word)
            if word['word'].endswith(('.', '?', '!')) or len(batch)>=18:segments.append(batch);batch=[]
        if batch:segments.append(batch)
        result={'idioma':'auto','estado':'pendiente_cotejo_audio_y_nombres','modelo':asr['modelo'],'revision':asr['revision'],'dispositivo':asr['dispositivo'],'segmentos':[{'inicio':s[0]['start'],'fin':s[-1]['end'],'texto':' '.join(x['word'] for x in s),'palabras':[{'inicio':x['start'],'fin':max(x['end'],x['start']+.04),'texto':x['word']} for x in s]} for s in segments]}
        write_json(transcript,result);project['etapa']='storyboard';write_json(path,project);print('Transcripción Parakeet CUDA preparada:',project_id);return
    from faster_whisper import WhisperModel
    source = inside(project['original']['archivo'])
    engine = WhisperModel(model, device='cpu', compute_type='int8', cpu_threads=4,
                          download_root=str(PRIVATE / 'cache/modelos'))
    segments, info = engine.transcribe(str(source), language='es', word_timestamps=True,
                                      beam_size=5, vad_filter=True)
    result = {'idioma': info.language, 'estado': 'pendiente_cotejo_audio', 'modelo': model, 'segmentos': []}
    for s in segments:
        result['segmentos'].append({'inicio': s.start, 'fin': s.end, 'texto': s.text.strip(),
          'palabras': [{'inicio': w.start, 'fin': w.end, 'texto': w.word.strip(),
                        'probabilidad': w.probability} for w in s.words or []]})
    write_json(transcript, result)
    project['etapa'] = 'storyboard'
    write_json(path, project)
    print('Transcripción alineada preparada:', project_id)


def track_face(project_id):
    folder=inside('proyectos/'+project_id)
    if (folder/'rostro.json').is_file():
        print('Seguimiento facial existente; se conserva:',project_id)
        return
    project=read_json(folder/'proyecto.json')
    if not project:
        raise ValueError('Proyecto inexistente')
    proxy=PRIVATE/'tmp/rostro_base.mp4'
    subprocess.run(['ffmpeg','-v','error','-i',str(inside(project['original']['archivo'])),
        '-vf','scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2,fps=30',
        '-an','-c:v','h264_nvenc','-cq','21','-pix_fmt','yuv420p','-y',str(proxy)],check=True)
    try:
        subprocess.run(['node','sistema/browser.mjs','rostro',project_id],check=True)
    finally:
        proxy.unlink(missing_ok=True)


def plan(project_id):
    folder = inside('proyectos/' + project_id)
    project = read_json(folder / 'proyecto.json')
    if project['escenas']:
        raise ValueError('Ya hay un storyboard; editar el canónico sin duplicarlo')
    transcript = read_json(folder / 'transcripcion.json')
    for index, s in enumerate(transcript['segmentos']):
        project['escenas'].append({'id': index + 1, 'inicio': s['inicio'], 'fin': s['fin'],
          'frase': s['texto'], 'objetivo_narrativo': None, 'visual': None, 'animacion': None,
          'subtitulos': [], 'recurso': None, 'sonido': None, 'transicion': None,
          'estado': 'requiere_decision_editorial'})
    project['etapa'] = 'storyboard_pendiente'
    project['manual'] = manual()
    write_json(folder / 'proyecto.json', project)
    print('Storyboard con tiempos reales preparado. Completar las decisiones editoriales.')


def qa(project_id):
    folder = inside('proyectos/' + project_id)
    candidate = folder / 'candidato.mp4'
    project = read_json(folder / 'proyecto.json')
    require_current_instructions(project)
    require_resource_selection(project)
    data = probe(candidate)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    audio = next((s for s in data['streams'] if s['codec_type'] == 'audio'), {})
    fps = video['avg_frame_rate'].split('/')
    actual_fps = int(fps[0]) / int(fps[1])
    source_duration = float(project['metadata']['format']['duration'])
    output_duration = float(data['format']['duration'])
    checks = {'resolucion': video['width'] == 1080 and video['height'] == 1920,
              'fps': abs(actual_fps - 30) < 0.001, 'h264': video['codec_name'] == 'h264',
              'aac': audio.get('codec_name') == 'aac',
              'discurso_completo': abs(source_duration - output_duration) <= 0.15,
              'manual_vigente': project['manual']['sha256'] == manual()['sha256']}
    if project.get('motor', {}).get('nombre') == 'HyperFrames':
        checks.update(structural_checks(project))
    subprocess.run(['ffmpeg', '-v', 'error', '-threads', '2', '-i', str(candidate),
                    '-f', 'null', '-'], check=True, capture_output=True)
    from auditar_temporal import audit as temporal_audit
    temporal=temporal_audit(candidate)
    checks['continuidad_temporal']=temporal['estado']=='sin_alternancia_detectada'
    result = {'candidato_sha256': digest(candidate), 'manual_sha256': manual()['sha256'],
              'edicion_sha256': edit_digest(project),
              'tecnica': checks, 'revision_editorial': None, 'estado': 'pendiente_revision_editorial',
              'fecha': utc(), 'metadata': data,'auditoria_temporal':temporal}
    write_json(folder / 'auditoria.json', result)
    print(json.dumps(checks, ensure_ascii=False))


def structural_checks(project):
    """Unir intervalos de presencia: un split o una transición no reinicia el límite."""
    stats=presence_stats(project)
    sample = project.get('muestra') or {}
    return {'presencia_hasta_20_por_ciento': stats['proporcion'] <= .20,
            'apariciones_hasta_3_segundos': stats['max_continuo_s'] <= 3,
            'prueba_aprobada_por_usuario': not project.get('requiere_aprobacion_prueba_v4') or
                project.get('aprobacion_usuario_prueba',{}).get('estado')=='aprobada',
            'muestra_previa_vigente': sample.get('estado') == 'aprobada' and
                sample.get('edicion_sha256') == edit_digest(project)}


def presence_stats(project,duration=None):
    """Contrato común para completo y muestra: unión y recorte a duración real."""
    duration=float(duration if duration is not None else project['metadata']['format']['duration'])
    if duration<=0:raise ValueError('Duración inválida')
    merged = []
    for actor in sorted(project.get('presentador', []), key=lambda a: a['inicio']):
        a, b = float(actor['inicio']), float(actor['fin'])
        if b <= a:
            raise ValueError('Intervalo de presentador inválido')
        a,b=max(0,a),min(duration,b)
        if b<=a:continue
        if merged and a <= merged[-1][1] + 1/30:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a,b])
    visible = sum(b-a for a,b in merged)
    return {'segundos':visible,'proporcion':visible/duration,
            'max_continuo_s':max((b-a for a,b in merged),default=0),'intervalos_unidos':merged}


def require_sample_review(project,audit):
    """Una evidencia cualquiera no permite publicar una muestra con defectos."""
    review=audit.get('revision_editorial') or {};folder='proyectos/'+project['id']
    if not (review.get('revisor') or review.get('revisores')) or not review.get('evidencias'):
        raise ValueError('Falta revisión real del contenido y sus evidencias')
    cfg=read_json('sistema/perfil.json')
    if any(review.get('criterios',{}).get(key) is not True for key in cfg['auditoria_obligatoria']):
        raise ValueError('La muestra no documenta todos los criterios editoriales obligatorios')
    for evidence in review['evidencias']:
        if not inside(evidence).is_file():raise ValueError('Evidencia editorial ausente: '+evidence)
    temporal=read_json(folder+'/auditoria_temporal.json',{})
    stable=read_json(folder+'/auditoria_estabilidad.json',{})
    if temporal.get('sha256')!=audit['sha256'] or temporal.get('estado')!='sin_alternancia_detectada' or temporal.get('frames_revisados')!=300:
        raise ValueError('Falta auditoría vigente de continuidad sobre los 300 frames')
    checks=stable.get('comprobaciones',{})
    required=('mp4_inmutable_durante_inspeccion','300_frames','rostro_autentico_completo_en_frames_visibles','rostro_desaparece_en_limites','sin_candidato_aba')
    if stable.get('sha256')!=audit['sha256'] or any(checks.get(k) is not True for k in required) or not stable.get('revision_visual'):
        raise ValueError('Falta comprobación de estabilidad y revisión visual de los frames')


def approve(project_id):
    """Solo promueve el candidato cuya auditoría editorial ya documentó el agente."""
    folder = inside('proyectos/' + project_id)
    audit = read_json(folder / 'auditoria.json')
    cfg = read_json('sistema/perfil.json')
    candidate = folder / 'candidato.mp4'
    review = audit.get('revision_editorial') or {}
    if not all(audit['tecnica'].values()):
        raise ValueError('Auditoría técnica pendiente o fallida')
    if audit.get('auditoria_temporal',{}).get('estado')!='sin_alternancia_detectada':
        raise ValueError('Falta auditoría de continuidad sobre todos los frames o detectó parpadeo')
    if audit['candidato_sha256'] != digest(candidate) or audit['manual_sha256'] != manual()['sha256']:
        raise ValueError('Cambió el candidato o el manual; repetir auditoría')
    if audit.get('edicion_sha256') != edit_digest(read_json(folder / 'proyecto.json')):
        raise ValueError('Cambió la edición o uno de sus recursos después de la auditoría')
    require_current_instructions(read_json(folder/'proyecto.json'))
    require_resource_selection(read_json(folder/'proyecto.json'))
    if not review.get('revisor') or not review.get('evidencias'):
        raise ValueError('Falta revisión real del contenido y sus evidencias')
    if any(review.get('criterios', {}).get(c) is not True for c in cfg['auditoria_obligatoria']):
        raise ValueError('La auditoría editorial no cumple todos los criterios')
    if not (folder / 'cronologia.md').is_file():
        raise ValueError('Falta la cronología de decisiones')
    project = read_json(folder / 'proyecto.json')
    if project.get('motor', {}).get('nombre') == 'HyperFrames' and not all(structural_checks(project).values()):
        raise ValueError('No cumple la directiva estructural o la muestra perdió vigencia')
    if not project['escenas'] or any(s.get('estado') != 'aprobada' for s in project['escenas']):
        raise ValueError('Storyboard sin aprobar')
    target=folder/project.get('final_nombre','final.mp4')
    candidate.replace(target)
    audit.update(estado='aprobado', final_sha256=digest(target), aprobado_en=utc(),archivo_final=str(target.relative_to(ROOT)))
    write_json(folder / 'auditoria.json', audit)
    project['etapa'] = 'entrega'
    write_json(folder / 'proyecto.json', project)
    print('Único final aprobado:', project_id)


def deliver(project_id):
    folder = inside('proyectos/' + project_id)
    project = read_json(folder / 'proyecto.json')
    audit = read_json(folder / 'auditoria.json')
    final = folder / project.get('final_nombre','final.mp4')
    if audit.get('estado') != 'aprobado' or audit.get('final_sha256') != digest(final):
        raise ValueError('No se publica una versión sin auditoría vigente')
    if audit['manual_sha256'] != manual()['sha256']:
        raise ValueError('Manual modificado: repetir auditoría')
    require_current_instructions(project)
    require_resource_selection(project)
    if audit.get('edicion_sha256') != edit_digest(project):
        raise ValueError('La edición o los recursos cambiaron después de aprobar el final')
    cfg = read_json('sistema/perfil.json')
    report_name=project.get('informe_nombre','informe_ascendia_v4.pdf' if project.get('requiere_aprobacion_prueba_v4') else 'informe_ascendia_v3.pdf')
    if project.get('requiere_aprobacion_prueba_v4'):
        if not (folder/'broll_manifest.csv').is_file() or not (folder/report_name).is_file():
            raise ValueError('Faltan manifest y reporte del final V4')
        if 'prueba' in report_name:
            raise ValueError('El reporte de 10 s no sustituye la auditoría del video completo')
    drive = Drive()
    target = drive.metadata(cfg['drive_entrega'])
    if not target.get('capabilities', {}).get('canAddChildren'):
        raise ValueError('La cuenta no tiene permiso de escritura en la carpeta de entrega')
    # Una carpeta remota por crudo, reutilizada en sucesivas ejecuciones.
    folder_name = project.get('nombre_entrega', project_id)
    known_folder = (project.get('entrega') or {}).get('carpeta_id')
    root_files = drive.children(target['id'])
    existing = [f for f in root_files if f['id'] == known_folder or f['name'] == project_id or
                f.get('appProperties', {}).get('ivan_crudo_id') == project_id]
    if len(existing) > 1:
        raise ValueError('Existen carpetas duplicadas en Drive; revisar antes de publicar')
    if existing:
        if existing[0]['mimeType'] != 'application/vnd.google-apps.folder':
            raise ValueError('El nombre del proyecto está ocupado por un archivo de Drive')
        parent = existing[0]['id']
    else:
        if any(f['name'] == folder_name for f in root_files):
            folder_name += ' — ' + project_id[-6:]
        parent = drive.request('POST', 'files', params={'supportsAllDrives': 'true'},
                               json={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder',
                                     'appProperties': {'ivan_crudo_id': project_id},
                                     'parents': [target['id']]}).json()['id']
    remote_files = drive.children(parent)
    receipt = project.get('entrega') or {'carpeta_id': parent, 'archivos': {}}
    paths = [final]
    # Paquete con estructura restaurable; el original permanece en Crudos.
    package = folder / 'fuentes.zip'
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as z:
        def put(name, content):
            entry = zipfile.ZipInfo('IVAN/' + name, date_time=(2026, 10, 11, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, content)
        for name in ('proyecto.json', 'transcripcion.json', 'cronologia.md', 'auditoria.json', 'edicion.py', 'index.html', 'motion.js','rostro.json', 'auditoria_visual.jpg', 'auditoria_muestra.json','comparacion.jpg','auditoria_correcciones.json','informe.html',report_name,'brolls_revision.jpg','broll_manifest.csv','comparacion_split_v4.jpg','auditoria_recursos.json'):
            if (folder / name).is_file():
                if name == 'proyecto.json':
                    source_project = {**project, 'etapa': 'aprobado', 'entrega': None}
                    put('proyectos/' + project_id + '/' + name, json.dumps(source_project, ensure_ascii=False, indent=2))
                else:
                    put('proyectos/' + project_id + '/' + name, (folder / name).read_bytes())
        for source in (ROOT / 'sistema').glob('*'):
            if source.suffix in ('.py', '.json', '.txt', '.mjs', '.js','.jsx','.html'):
                put('sistema/' + source.name, source.read_bytes())
        put('PROMPT_MAESTRO.md', (ROOT / 'PROMPT_MAESTRO.md').read_bytes())
        put('AGENTS.md', (ROOT/'AGENTS.md').read_bytes())
        put('INSTRUCCIONES.md', (ROOT/'INSTRUCCIONES.md').read_bytes())
        if inside('recursos/inventario_drive.json').is_file():
            put('recursos/inventario_drive.json',inside('recursos/inventario_drive.json').read_bytes())
        if (folder/'seleccion_recursos.json').is_file():
            put('proyectos/'+project_id+'/seleccion_recursos.json',(folder/'seleccion_recursos.json').read_bytes())
        put('recursos/catalogo.json', inside('recursos/catalogo.json').read_bytes())
        # Recursos efectivamente usados, una sola copia de cada ruta dentro del paquete.
        resource_paths = {item['archivo'] for item in project.get('recursos', []) if item.get('archivo')}
        resource_paths.update(cfg['archivos_tipografia'].values())
        for resource_path in sorted(resource_paths):
            put(resource_path, inside(resource_path).read_bytes())
        put('RESTAURAR.txt', 'Las rutas son relativas a IVAN. Restaurar el original desde Drive ID ' + project_id +
            ' en ' + project['original']['archivo'] + '. Los recursos están identificados por ID y SHA-256 en el catálogo. '
            'Los recursos usados y las dos fuentes exactas están incluidos. Para restaurar el original sin alterar el storyboard: '
            'python3 -B sistema/workflow.py ingestar ' + project_id + '. '
            'Instalar las dependencias locales con el comando registrado en sistema/herramientas.json. '
            'El storyboard se edita en proyectos/' + project_id + '/motion.js y proyecto.json; '
            'los componentes compartidos están en sistema/motion.js y sistema/componentes.jsx. '
            'rostro.json contiene la barbilla detectada; no requiere volver a transcribir. '
            'Para comprobar cambios: python3 -B sistema/render.py ' + project_id + ' --muestra 10. '
            'Render: python3 -B sistema/render.py ' + project_id + '. '
            'El archivo generado es candidato.mp4 y requiere auditoría antes de convertirse en final.\n')
    paths.append(package)
    report = folder / report_name
    if report.is_file():
        paths.append(report)
    if (folder/'broll_manifest.csv').is_file():paths.append(folder/'broll_manifest.csv')
    for path in paths:
        matches = [f for f in remote_files if f['name'] == path.name]
        if len(matches) > 1:
            raise ValueError('Entrega duplicada en Drive: ' + path.name)
        match = matches[0] if matches else None
        if not match and path==final:
            prior_id=(receipt.get('archivos',{}).get('final.mp4') or {}).get('id')
            prior=[f for f in remote_files if f['id']==prior_id]
            if prior:match=prior[0]
        if match and match.get('md5Checksum') == digest(path, 'md5'):
            remote = drive.metadata(match['id'])
        else:
            remote = drive.upload(path, parent, match['id'] if match else None)
        if path==final and path.name!='final.mp4':receipt['archivos'].pop('final.mp4',None)
        receipt['archivos'][path.name] = {'id': remote['id'], 'md5': remote['md5Checksum'],
                                        'bytes': int(remote['size']), 'sha256': digest(path)}
        receipt['verificado_en'] = utc()
        project['entrega'] = receipt
        write_json(folder / 'proyecto.json', project)
    project['etapa'] = 'entregado_verificado'
    write_json(folder / 'proyecto.json', project)
    package.unlink()
    print('Entrega verificada:', 'recurso-configurado:drive/folders/' + parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('manual')
    p = sub.add_parser('recursos'); p.add_argument('keys', nargs='*')
    p = sub.add_parser('drive'); p.add_argument('folder')
    p = sub.add_parser('vincular-crudos'); p.add_argument('folder_id')
    p = sub.add_parser('crudos'); p.add_argument('--ingestar',action='store_true')
    p = sub.add_parser('ingestar'); p.add_argument('file_id')
    p = sub.add_parser('transcribir'); p.add_argument('project_id'); p.add_argument('--model', default='parakeet')
    for command in ('rostro', 'storyboard', 'auditar', 'aprobar', 'entregar'):
        p = sub.add_parser(command); p.add_argument('project_id')
    args = parser.parse_args()
    stamp = manual()  # El manual completo se lee antes de TODA operación.
    if args.command in ('transcribir','rostro','storyboard','auditar','aprobar','entregar'):
        from preflight import require_ready
        require_ready()
    if args.command == 'manual': print(json.dumps(stamp, ensure_ascii=False, indent=2))
    elif args.command == 'recursos': prepare_resources(args.keys)
    elif args.command == 'drive': inspect_drive(args.folder)
    elif args.command == 'vincular-crudos': print(json.dumps(bind_crudos(args.folder_id),ensure_ascii=False,indent=2))
    elif args.command == 'crudos': print(json.dumps(scan_crudos(args.ingestar),ensure_ascii=False,indent=2))
    elif args.command == 'ingestar': ingest(args.file_id)
    elif args.command == 'transcribir': transcribe(args.project_id, args.model)
    elif args.command == 'rostro': track_face(args.project_id)
    elif args.command == 'storyboard': plan(args.project_id)
    elif args.command == 'auditar': qa(args.project_id)
    elif args.command == 'aprobar': approve(args.project_id)
    elif args.command == 'entregar': deliver(args.project_id)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, requests.RequestException, subprocess.CalledProcessError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
