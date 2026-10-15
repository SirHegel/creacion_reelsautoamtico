#!/usr/bin/env python3
"""Preselección contextual y descarga selectiva. La decisión visual la registra el agente."""
import argparse,sys
from pathlib import Path
sys.dont_write_bytecode=True
import workflow as w

INVENTARIO='recursos/inventario_drive.json'
BIBLIOTECAS=('CONFIGURE_RECURSO_1792','CONFIGURE_RECURSO_1351')

def ruta(project_id):return 'proyectos/'+project_id+'/seleccion_recursos.json'

def crear(project_id):
    target=w.inside(ruta(project_id))
    if target.is_file():raise ValueError('La selección canónica ya existe; completar sin duplicarla')
    p=w.read_json('proyectos/'+project_id+'/proyecto.json')
    inventory=w.read_json(INVENTARIO)
    if not p or not inventory or not inventory.get('recorrido_completo'):
        raise ValueError('Preparar el proyecto e inventariar las bibliotecas completas primero')
    transcript=w.read_json('proyectos/'+project_id+'/transcripcion.json',{})
    words=[x for s in transcript.get('segmentos',[]) for x in s.get('palabras',[])]
    blocks=[]
    for s in p.get('escenas',[]):
        spoken=s.get('frase') or ' '.join(x['texto'] for x in words if s['inicio']<=x['inicio']<s['fin'])
        blocks.append({'escena_id':str(s['id']),'inicio':s['inicio'],'fin':s['fin'],
            'narracion':spoken,'intencion':None,'carpetas_consultadas':[],
            'candidatos':[],'decision':None})
    w.write_json(target,{'proyecto_id':project_id,'estado':'pendiente_seleccion_contextual',
        'manual':w.manual(),'inventario_sha256':w.digest(INVENTARIO),
        'bibliotecas_consultadas':[],'bloques':blocks})
    print('Completar narración, intención y candidatos:',ruta(project_id))

def descargar(project_id):
    selection=w.read_json(ruta(project_id));inventory=w.read_json(INVENTARIO)
    if not selection or not inventory:raise ValueError('Falta preselección o inventario')
    active={c.get('drive_id') for b in selection['bloques'] for c in b.get('candidatos',[]) if c.get('descargar') is True}
    if len(active)>12:raise ValueError('Preseleccionar pocos candidatos; máximo 12 por pasada, revisarlos antes de ampliar la búsqueda')
    catalog=w.read_json('recursos/catalogo.json');downloads=0
    for block in selection['bloques']:
        for candidate in block['candidatos']:
            if candidate.get('descargar') is not True:continue
            if not block.get('narracion') or not block.get('intencion') or not candidate.get('motivo_contextual'):
                raise ValueError('Preseleccionar por narración e intención antes de descargar')
            item=inventory['elementos'].get(candidate['drive_id'],{})
            if item.get('rol') not in ('broll_dinamico','broll_software') or not item.get('mime','').startswith('video/'):
                raise ValueError('El candidato no es un video de las bibliotecas de b-roll autorizadas')
            existing=next((v for v in catalog['archivos'].values()
                if (v.get('id')==item['id'] or (item.get('md5') and v.get('md5_origen')==item['md5']))
                and v.get('archivo') and w.inside(v['archivo']).is_file()
                and v.get('sha256')==w.digest(v['archivo'])),None)
            if existing:
                candidate.update(archivo=existing['archivo'],sha256=existing['sha256'],reutilizado=True,descargar=False)
                item['acceso']['descarga_binaria_comprobada']=True
                continue
            extension=Path(item['nombre']).suffix.lower()
            if extension not in w.VIDEO_EXTENSIONS and extension not in ('.mpeg','.mpg'):
                raise ValueError('Formato de clip no reconocido: '+extension)
            destination='assets/broll/broll_'+(item.get('md5') or item['id'])+extension
            record=w.download(item['id'],destination)
            if item.get('md5') and w.digest(destination,'md5')!=item['md5']:
                raise ValueError('El recurso cambió desde el inventario; actualizar y revisar')
            record.update(md5_origen=item.get('md5'),origen=item['enlace'],
                carpeta_id=item['padre_recorrido'],rol=item['rol'],metadata=w.probe(destination),
                derechos='Recurso del cliente autorizado para esta edición; no se atribuye otra licencia',
                estado='descargado_pendiente_inspeccion_visual',analisis_visual=None)
            catalog['archivos']['BROLL_'+(item.get('md5') or item['id'])]=record
            candidate.update(archivo=destination,sha256=record['sha256'],reutilizado=False,descargar=False)
            item['acceso']['descarga_binaria_comprobada']=True
            downloads+=1
    w.write_json('recursos/catalogo.json',catalog)
    w.write_json(INVENTARIO,inventory)
    selection['inventario_sha256']=w.digest(INVENTARIO)
    w.write_json(ruta(project_id),selection)
    print('Descargas nuevas:',downloads,'; inspeccionar antes de integrar')

def validar(project,hasta=None):
    selection=w.read_json(ruta(project['id']),{})
    current=w.manual()
    permitted=('revisada_contextualmente','revisada_para_prueba') if hasta is not None else ('revisada_contextualmente',)
    if selection.get('estado') not in permitted:
        raise ValueError('Falta selección contextual de b-rolls revisada por el agente')
    if hasta is not None and float(selection.get('alcance_hasta_s',0))<hasta:
        raise ValueError('La selección no cubre toda la prueba solicitada')
    if selection.get('manual',{}).get('instrucciones_sha256')!=current['instrucciones_sha256']:
        raise ValueError('La selección no integra las instrucciones y modificaciones vigentes')
    if selection.get('inventario_sha256')!=w.digest(INVENTARIO):
        raise ValueError('El inventario cambió; revisar la preselección contextual')
    if not set(BIBLIOTECAS).issubset(selection.get('bibliotecas_consultadas',[])):
        raise ValueError('Consultar tanto b-roll dinámico como software antes de diseñar')
    inventory=w.read_json(INVENTARIO)['elementos']
    blocks=[b for b in selection.get('bloques',[]) if hasta is None or b['inicio']<hasta]
    expected={str(s['id']) for s in project['escenas'] if hasta is None or s['inicio']<hasta}
    if {str(b['escena_id']) for b in blocks}!=expected or len(blocks)!=len(expected):
        raise ValueError('Documentar una decisión de recursos por cada bloque del reel')
    assets={r['archivo'] for r in project.get('recursos',[]) if r.get('archivo')}
    for block in blocks:
        decision=block.get('decision') or {}
        if not block.get('narracion') or not block.get('intencion') or not decision.get('motivo_contextual'):
            raise ValueError('Falta comprender y justificar la representación de una frase')
        if not block.get('carpetas_consultadas') or any(folder not in inventory for folder in block['carpetas_consultadas']):
            raise ValueError('Registrar carpetas reales consultadas para cada bloque')
        scene=next(s for s in project['escenas'] if str(s['id'])==str(block['escena_id']))
        if abs(block['inicio']-scene['inicio'])>.01 or abs(block['fin']-scene['fin'])>.01:
            raise ValueError('La selección no corresponde a los tiempos actuales del storyboard')
        for candidate in block.get('candidatos',[]):
            internal=candidate.get('drive_id') in inventory
            external=(candidate.get('fuente_tipo')=='oficial' and candidate.get('fuente_url','').startswith('https://')
                      and candidate.get('derechos') and candidate.get('registro_captura')
                      and w.inside(candidate['registro_captura']).is_file())
            if not (internal or external) or not candidate.get('motivo_contextual'):
                raise ValueError('Candidato sin procedencia o motivo semántico')
        if decision.get('tipo') in ('broll','demo_externa'):
            if decision['tipo']=='broll':
                chosen=next((c for c in block['candidatos'] if c.get('drive_id')==decision.get('drive_id')),None)
                if inventory.get(decision.get('drive_id'),{}).get('rol') not in ('broll_dinamico','broll_software'):
                    raise ValueError('El recurso elegido no pertenece a una biblioteca de b-roll')
            else:
                chosen=next((c for c in block['candidatos'] if c.get('fuente_url')==decision.get('fuente_url')),None)
                if not decision.get('resultado_busqueda'):
                    raise ValueError('Consultar primero las bibliotecas antes de recurrir a una demostración externa')
                if not chosen or chosen.get('fuente_tipo')!='oficial' or not chosen.get('derechos') or not chosen.get('registro_captura'):
                    raise ValueError('La demostración externa requiere fuente oficial, permisos y registro de captura')
            analysis=(chosen or {}).get('analisis_visual') or {}
            if not chosen or analysis.get('estado')!='revisado' or not analysis.get('contenido_observado') or not analysis.get('evidencias'):
                raise ValueError('No usar un b-roll sin ver su contenido y secuencia real')
            path=chosen.get('archivo')
            if not path or path not in assets or chosen.get('sha256')!=w.digest(path):
                raise ValueError('El clip elegido no está íntegro ni registrado entre los recursos del render')
            if any(not w.inside(e).is_file() for e in analysis['evidencias']):
                raise ValueError('Falta la evidencia visual del clip elegido')
            cut=decision.get('tramo_s',[])
            duration=float(w.probe(path)['format']['duration'])
            if len(cut)!=2 or not 0<=cut[0]<cut[1]<=duration+.05:
                raise ValueError('El tramo de b-roll es inválido')
        elif decision.get('tipo') in ('motion','presentador','tipografia'):
            if not decision.get('resultado_busqueda'):
                raise ValueError('Justificar con la búsqueda por qué se prioriza otra representación')
        else:raise ValueError('Tipo de decisión visual no reconocido')
    if project.get('directiva')=='ASCENDIA V5':
        selected={c.get('archivo') for b in blocks for c in b.get('candidatos',[]) if c.get('analisis_visual',{}).get('estado')=='revisado'}
        actual={b['archivo'] for b in project.get('broll',[]) if hasta is None or b['inicio']<hasta}
        if not actual.issubset(selected):
            raise ValueError('Cada b-roll incorporado requiere candidato revisado y correspondencia narrativa; no omitir el recurso del hook')
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('accion',choices=['crear','descargar','validar']);parser.add_argument('project_id');parser.add_argument('--hasta',type=float);args=parser.parse_args()
    w.manual()
    if args.accion=='crear':crear(args.project_id)
    elif args.accion=='descargar':descargar(args.project_id)
    else:
        validar(w.read_json('proyectos/'+args.project_id+'/proyecto.json'),hasta=args.hasta);print('Selección contextual verificada')

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as error:print(str(error),file=sys.stderr);sys.exit(1)
