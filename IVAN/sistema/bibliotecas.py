#!/usr/bin/env python3
"""Inventario canónico de las bibliotecas autorizadas de Presentador, sin descargar medios.

Los nombres y metadatos orientan una preselección; no certifican el contenido.
Recorre todas las páginas, conserva una entrada por ID, no sigue accesos directos
a destinos fuera del ámbito y preserva análisis visuales solo si el medio no cambió.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import threading
import unicodedata

from workflow import Drive, inside, manual, read_json, utc, write_json

FOLDER = 'application/vnd.google-apps.folder'
SHORTCUT = 'application/vnd.google-apps.shortcut'
ARCHIVO = 'recursos/inventario_drive.json'
RAIZ = 'CONFIGURE_RECURSO_1066'
SOFTWARE = 'CONFIGURE_RECURSO_1351'
RAICES_AUTORIZADAS = (RAIZ, SOFTWARE)
ROLES = {
    RAIZ: ('raiz_edicion', 'Árbol de edición y recursos del cliente.'),
    SOFTWARE: ('broll_software', 'Demostraciones de herramientas; biblioteca adicional autorizada.'),
    'CONFIGURE_RECURSO_1792': ('broll_dinamico', 'Clips cinematográficos, dopamina y luxury; escoger por la narración.'),
    'CONFIGURE_RECURSO_1469': ('crudos', 'Entrada: narración y cortes originales, nunca recurso genérico.'),
    'CONFIGURE_RECURSO_0521': ('entregas', 'Salida final; no usar exportados como b-roll.'),
    'CONFIGURE_RECURSO_1536': ('musica', 'Escuchar candidatos desde 10–15 s del archivo; comprobar derechos.'),
    'CONFIGURE_RECURSO_1305': ('transiciones', 'Burn en Screen y otras transiciones selectivas.'),
    'CONFIGURE_RECURSO_0027': ('sonidos', 'Efectos: revisar carácter, pico de energía y sincronización.'),
    'CONFIGURE_RECURSO_0766': ('prompt_drive', 'Documento de instrucciones original; leer junto al manual y modificaciones.'),
    'CONFIGURE_RECURSO_0355': ('referencia_A1', 'Identidad: INTERNACIONAL.'),
    'CONFIGURE_RECURSO_1593': ('referencia_A2', 'Identidad: CLASE.'),
    'CONFIGURE_RECURSO_0493': ('referencia_A3', 'Identidad: YO.'),
    'CONFIGURE_RECURSO_1613': ('referencia_B1', 'Motion: EDIT.'),
    'CONFIGURE_RECURSO_1679': ('referencia_B2', 'Motion: CLONE.'),
    'CONFIGURE_RECURSO_1671': ('referencia_B3', 'Motion prioritario: AGENT.'),
    'CONFIGURE_RECURSO_0595': ('riser_principal', 'Culminación entre 2 y 6 s del vídeo, en una transformación importante.'),
    'CONFIGURE_RECURSO_1590': ('riser_alternativo', 'Utilizar cuando carácter y duración encajen.'),
    'CONFIGURE_RECURSO_0547': ('woosh', 'Movimientos relevantes, nunca saturar cada aparición.'),
}
FIELDS = ','.join((
    'id', 'name', 'mimeType', 'size', 'md5Checksum', 'modifiedTime', 'parents',
    'webViewLink', 'capabilities', 'shared', 'permissions(type,role,allowFileDiscovery)',
    'shortcutDetails(targetId,targetMimeType)',
    'videoMediaMetadata(width,height,durationMillis)',
    'imageMediaMetadata(width,height)',
))
_local = threading.local()


def cliente():
    if not hasattr(_local, 'drive'):
        _local.drive = Drive()
    return _local.drive


def metadata(file_id):
    return cliente().request('GET', 'files/' + file_id, params={
        'supportsAllDrives': 'true', 'fields': FIELDS,
    }).json()


def listar(parent):
    files, pages, page = [], 0, None
    while True:
        params = {
            'q': "'" + parent + "' in parents and trashed=false", 'pageSize': 1000,
            'fields': 'nextPageToken,incompleteSearch,files(' + FIELDS + ')',
            'supportsAllDrives': 'true', 'includeItemsFromAllDrives': 'true',
        }
        if page:
            params['pageToken'] = page
        data = cliente().request('GET', 'files', params=params).json()
        if data.get('incompleteSearch'):
            raise RuntimeError('Drive devolvió una búsqueda incompleta para ' + parent)
        files.extend(data.get('files', []))
        pages += 1
        page = data.get('nextPageToken')
        if not page:
            return files, pages


def normalizar(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower())
                   if not unicodedata.combining(c))


def orientacion(nombre, role):
    """Provisional por nombre/categoría; jamás cuenta como revisión visual."""
    name = normalizar(nombre)
    if role == 'broll_software':
        return 'Preselección de herramienta por nombre; verificar función y acción reales en el clip.'
    if 'luxury' in name:
        return 'Categoría nombrada luxury: usar solo si la historia requiere ese contexto; no ilustrar ingresos genéricamente.'
    if 'cinematic' in name:
        return 'Categoría cinematográfica: investigar acción/entorno y escoger una metáfora pertinente.'
    if 'dopamina' in name:
        return 'Categoría de impacto: comprobar tema real, legibilidad y pertinencia; no insertar por atractivo solamente.'
    return ROLES.get(next((i for i, r in ROLES.items() if r[0] == role), ''), ('',
        'Contenido pendiente de inspección; el nombre no acredita una función o escena.'))[1]


def convertir(meta, raiz, parent, path, role, anterior):
    file_id = meta['id']
    selected_role = ROLES.get(file_id, (role, ''))[0]
    previous = anterior.get(file_id, {})
    same = bool(previous and meta.get('md5Checksum') and
                previous.get('md5') == meta.get('md5Checksum'))
    if meta['mimeType'] == FOLDER:
        content = {'estado': 'estructura_inventariada', 'inspeccion_visual': False}
    else:
        content = previous.get('contenido', {}) if same else {}
        if not content:
            content = {'estado': 'pendiente_inspeccion', 'inspeccion_visual': False,
                       'observaciones': [], 'evidencias': [],
                       'limitacion': 'Solo metadatos; descargar candidatos según el reel y visualizar su secuencia.'}
    return {
        'id': file_id, 'nombre': meta['name'], 'ruta': path, 'rutas': [path],
        'raiz_autorizada': raiz, 'padre_recorrido': parent,
        'padres_drive': meta.get('parents', []), 'mime': meta['mimeType'],
        'bytes': int(meta['size']) if meta.get('size') is not None else None,
        'md5': meta.get('md5Checksum'), 'modificado_en': meta.get('modifiedTime'),
        'enlace': meta.get('webViewLink') or ('recurso-configurado:' +
            ('drive/folders/' if meta['mimeType'] == FOLDER else 'file/d/') + file_id),
        'rol': selected_role, 'orientacion_provisional': orientacion(meta['name'], selected_role),
        'base_orientacion': 'ID autorizado y categoría/nombre; no análisis audiovisual',
        'acceso': {'metadatos_comprobados': True, 'listado_comprobado': False,
                   'descarga_binaria_comprobada': bool(same and previous.get('acceso', {}).get('descarga_binaria_comprobada')),
                   'capacidades_cuenta': meta.get('capabilities', {}),
                   'permisos_drive': meta.get('permissions', []), 'compartido': meta.get('shared'),
                   'derechos_uso': 'Recursos proporcionados por el cliente; licencia comercial no comprobada por metadatos.',
                   'comprobado_en': utc()},
        'metadata_video': meta.get('videoMediaMetadata'),
        'metadata_imagen': meta.get('imageMediaMetadata'),
        'acceso_directo': meta.get('shortcutDetails'), 'contenido': content,
        'subcarpetas': [], 'archivos': [], 'errores': [],
    }


def resumen(data):
    items = data['elementos']
    kinds = Counter(item['mime'] for item in items.values())
    roots = {root: {'carpetas': 0, 'archivos': 0, 'bytes_remotos': 0}
             for root in RAICES_AUTORIZADAS}
    roles = defaultdict(lambda: {'carpetas': 0, 'archivos': 0, 'bytes_remotos': 0})
    for item in items.values():
        kind = 'carpetas' if item['mime'] == FOLDER else 'archivos'
        roots[item['raiz_autorizada']][kind] += 1
        roots[item['raiz_autorizada']]['bytes_remotos'] += item.get('bytes') or 0
        roles[item['rol']][kind] += 1
        roles[item['rol']]['bytes_remotos'] += item.get('bytes') or 0
    return {'elementos': len(items), 'carpetas': kinds[FOLDER],
            'archivos': len(items) - kinds[FOLDER], 'videos': sum(n for k,n in kinds.items() if k.startswith('video/')),
            'audios': sum(n for k,n in kinds.items() if k.startswith('audio/')),
            'bytes_remotos': sum(item.get('bytes') or 0 for item in items.values()),
            'descargas_medios_en_este_recorrido': 0,
            'errores': len(data['errores']), 'por_raiz': roots, 'por_rol': dict(roles),
            'por_mime': dict(sorted(kinds.items()))}


def actualizar(workers=3):
    previous = read_json(ARCHIVO, {}).get('elementos', {})
    data = {'version': 1, 'actualizado_en': utc(), 'manual': manual(),
            'raices_autorizadas': list(RAICES_AUTORIZADAS),
            'alcance': 'Todos los descendientes de las dos raíces autorizadas. Referencias externas solo por IDs del manual.',
            'metodo': 'Drive API v3 OAuth local, metadatos y paginación completa, sin descarga de vídeos.',
            'elementos': {}, 'accesos_conocidos': {}, 'errores': []}
    pending, seen = [], set()
    # Leer secuencialmente las raíces también renueva el OAuth antes de las peticiones paralelas.
    for root in RAICES_AUTORIZADAS:
        try:
            meta = metadata(root)
            if meta['mimeType'] != FOLDER:
                raise RuntimeError('La raíz autorizada no es una carpeta')
            data['elementos'][root] = convertir(meta, root, None, meta['name'], ROLES[root][0], previous)
            pending.append(root)
        except Exception as exc:
            data['errores'].append({'id': root, 'operacion': 'raiz', 'error': str(exc)})
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 4))) as executor:
        while pending:
            batch = [i for i in pending if i not in seen]
            pending = []
            seen.update(batch)
            futures = {executor.submit(listar, file_id): file_id for file_id in batch}
            for future in as_completed(futures):
                file_id = futures[future]
                folder = data['elementos'][file_id]
                try:
                    children, pages = future.result()
                    folder['acceso'].update(listado_comprobado=True, paginas_listado=pages)
                    for child in sorted(children, key=lambda x: (x['name'].casefold(), x['id'])):
                        path = folder['ruta'] + '/' + child['name'].replace('/', '／')
                        child_id = child['id']
                        item = convertir(child, folder['raiz_autorizada'], file_id, path, folder['rol'], previous)
                        if child_id in data['elementos']:
                            existing = data['elementos'][child_id]
                            if path not in existing['rutas']:
                                existing['rutas'].append(path)
                        else:
                            data['elementos'][child_id] = item
                        if child['mimeType'] == FOLDER:
                            folder['subcarpetas'].append(child_id)
                            pending.append(child_id)
                        else:
                            folder['archivos'].append(child_id)
                            if child['mimeType'] == SHORTCUT:
                                data['elementos'][child_id]['contenido']['limitacion'] = 'Acceso directo inventariado; destino no recorrido sin autorización explícita.'
                except Exception as exc:
                    problem = {'id': file_id, 'ruta': folder['ruta'], 'operacion': 'listar', 'error': str(exc)}
                    data['errores'].append(problem)
                    folder['errores'].append(problem)
            print('Inventario:', len(data['elementos']), 'elementos;', len(seen),
                  'carpetas recorridas;', len(pending), 'pendientes', flush=True)
    # Ubicación real de los enlaces conocidos; no asumir que pertenecen a la raíz.
    for file_id, (role, _) in ROLES.items():
        if file_id in data['elementos']:
            item = data['elementos'][file_id]
            data['accesos_conocidos'][role] = {
                'id': file_id, 'nombre': item['nombre'], 'ruta': item['ruta'],
                'enlace': item['enlace'], 'dentro_raiz_principal': item['raiz_autorizada'] == RAIZ,
                'raiz_autorizada': item['raiz_autorizada'], 'acceso': item['acceso'],
            }
        else:
            try:
                meta = metadata(file_id)
                data['accesos_conocidos'][role] = {
                    'id': file_id, 'nombre': meta['name'], 'enlace': meta.get('webViewLink'),
                    'dentro_raiz_principal': False, 'raiz_autorizada': None,
                    'ubicacion': 'Enlace adicional autorizado por el manual; no encontrado en el árbol principal.',
                    'acceso': {'metadatos_comprobados': True, 'capacidades_cuenta': meta.get('capabilities', {}),
                               'permisos_drive': meta.get('permissions', []), 'comprobado_en': utc()},
                    'contenido': {'estado': 'pendiente_inspeccion', 'inspeccion_visual': False},
                }
            except Exception as exc:
                data['accesos_conocidos'][role] = {'id': file_id, 'acceso': {'metadatos_comprobados': False}, 'error': str(exc)}
                data['errores'].append({'id': file_id, 'operacion': 'acceso_conocido', 'error': str(exc)})
    groups = defaultdict(list)
    for file_id, item in data['elementos'].items():
        if item['md5']:
            groups[(item['md5'], item['bytes'])].append(file_id)
    data['coincidencias_contenido'] = [{'md5': key[0], 'bytes': key[1], 'ids': ids}
                                     for key, ids in sorted(groups.items()) if len(ids) > 1]
    data['resumen'] = resumen(data)
    data['recorrido_completo'] = not any(e['operacion'] in ('raiz','listar') for e in data['errores'])
    write_json(ARCHIVO, data)
    return data


def buscar(consulta, limite=20, rol=None):
    """Devuelve candidatos por metadatos; la decisión editorial requiere ver el clip."""
    data = read_json(ARCHIVO)
    if not data:
        raise RuntimeError('Falta inventario; ejecutar bibliotecas.py actualizar')
    terms = set(re.findall(r'\w+', normalizar(consulta)))
    candidates = []
    for item in data['elementos'].values():
        if item['mime'] == FOLDER or item['rol'] not in ('broll_dinamico', 'broll_software'):
            continue
        if rol and item['rol'] != rol:
            continue
        haystack = normalizar(item['ruta'])
        if item.get('contenido',{}).get('inspeccion_visual'):
            haystack+=' '+normalizar(' '.join(item['contenido'].get('observaciones',[])))
        score = sum(1 for term in terms if term in haystack)
        if score:
            candidates.append({'id': item['id'], 'nombre': item['nombre'], 'ruta': item['ruta'],
                               'bytes': item['bytes'], 'md5': item['md5'], 'enlace': item['enlace'],
                               'coincidencias_nombre': score, 'contenido': item['contenido'],
                               'limitacion': 'Coincidencia de metadatos, no prueba de pertinencia semántica.'})
    return sorted(candidates, key=lambda x: (-x['coincidencias_nombre'], x['ruta']))[:limite]


def mapa():
    data = read_json(ARCHIVO)
    if not data:
        raise RuntimeError('Falta inventario; ejecutar bibliotecas.py actualizar')
    return [{'id': item['id'], 'ruta': item['ruta'], 'rol': item['rol'],
             'archivos_directos': len(item['archivos']), 'subcarpetas_directas': len(item['subcarpetas']),
             'orientacion_provisional': item['orientacion_provisional'],
             'acceso_listado': item['acceso']['listado_comprobado']}
            for item in sorted(data['elementos'].values(), key=lambda x: x['ruta']) if item['mime'] == FOLDER]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    update = sub.add_parser('actualizar'); update.add_argument('--workers', type=int, default=3)
    search = sub.add_parser('buscar'); search.add_argument('consulta'); search.add_argument('--limite', type=int, default=20)
    search.add_argument('--rol', choices=['broll_dinamico','broll_software'])
    sub.add_parser('mapa')
    args = parser.parse_args()
    manual()
    if args.command == 'actualizar':
        data = actualizar(args.workers)
        print(json.dumps(data['resumen'], ensure_ascii=False, indent=2))
        if not data['recorrido_completo']:
            raise SystemExit(1)
    elif args.command == 'buscar':
        print(json.dumps(buscar(args.consulta, args.limite, args.rol), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(mapa(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
