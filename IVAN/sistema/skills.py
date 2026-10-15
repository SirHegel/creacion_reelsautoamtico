"""Skills oficiales de IVAN: actualizar, inventariar y exigir aplicación documentada.

Instalar o imprimir una guía no demuestra que el agente la entendió/aplicó.
La plantilla conserva pendientes hasta que el revisor documenta decisiones reales.
"""
import argparse, hashlib, json, os, subprocess, sys
sys.dont_write_bytecode=True
import workflow as w

REQUIRED=('hyperframes','general-video','hyperframes-core','hyperframes-creative',
 'hyperframes-animation','hyperframes-keyframes','hyperframes-audio','hyperframes-cli',
 'hyperframes-registry','hyperframes-studio','media-use','motion-graphics')
REFERENCES=('hyperframes-animation/adapters/gsap.md',
 'hyperframes-core/references/determinism-rules.md',
 'hyperframes-creative/references/house-style.md',
 'hyperframes-creative/references/video-composition.md',
 'hyperframes-creative/references/motion-principles.md')
STORE='.agents/skills/'

def inventory():
    records=[]
    for name in REQUIRED:
        directory=w.inside(STORE+name);file=directory/'SKILL.md'
        if not file.is_file():raise ValueError('Skill obligatoria ausente: '+name)
        tree=hashlib.sha256()
        for item in sorted(directory.rglob('*')):
            if item.is_file():
                w.inside(item);tree.update(str(item.relative_to(directory)).encode()+b'\0'+item.read_bytes()+b'\0')
        records.append({'nombre':name,'archivo':STORE+name+'/SKILL.md',
          'sha256':w.digest(file),'arbol_sha256':tree.hexdigest(),
          'fuente':'https://github.com/heygen-com/hyperframes/tree/main/skills/'+name})
    return records

def cli(args):
    env=os.environ.copy();env['NODE_OPTIONS']='--import '+str(w.inside('sistema/skills_entorno.mjs'))
    return subprocess.run(['node',str(w.inside('.estado/herramientas/node_modules/hyperframes/bin/hyperframes.mjs')),*args],
      cwd=w.ROOT,env=env,capture_output=True,text=True)

def update():
    result=cli(['skills','update','general-video','motion-graphics','--json'])
    w.inside('.estado/tmp/skills_actualizacion.log').write_text(result.stdout+'\n'+result.stderr)
    if result.returncode:raise RuntimeError('Actualización de skills fallida; consultar .estado/tmp/skills_actualizacion.log')
    check=cli(['skills','check','--json'])
    w.inside('.estado/tmp/skills_check.json').write_text(check.stdout)
    if check.returncode:raise RuntimeError('Skills incompletas o desactualizadas; consultar .estado/tmp/skills_check.json')
    data={'fecha':w.utc(),'directorio_canonico':STORE,'estado':'instaladas_y_actualizadas',
      'lectura_y_aplicacion':'Se acreditan por proyecto; la instalación no las demuestra.',
      'skills':inventory(),'comprobacion_cli':json.loads(check.stdout),
      'gsap_solicitada':{'comando':'npx skills add heygen-com/hyperframes --skill gsap',
       'resultado_comprobado':'No matching skills found for: gsap',
       'guia_oficial_actual':'hyperframes-keyframes',
       'referencia_gsap':STORE+'hyperframes-animation/adapters/gsap.md'},
      'confinamiento':str(w.ROOT),'motor_conservado':'HyperFrames 0.8.147; no actualizado por instalar guías'}
    w.write_json('sistema/skills_instaladas.json',data)
    print('12 skills oficiales actualizadas, incluida la guía actual GSAP; todo en IVAN.')

def template(ID):
    folder=w.inside('proyectos/'+ID)
    if not (folder/'proyecto.json').is_file():raise ValueError('Proyecto inexistente')
    path=folder/'skills_aplicadas.json'
    if path.exists():raise ValueError('Conservar el registro existente; revisar solo sus pendientes')
    entries=[]
    for entry in inventory():entries.append(dict(entry,lectura='pendiente',revisor=None,aplicacion=None,evidencias=[]))
    w.write_json(path,{'version':1,'estado':'pendiente_lectura_y_aplicacion','manual':w.manual(),
      'skills':entries,'referencias':[{'archivo':STORE+r,'sha256':w.digest(STORE+r),
         'lectura':'pendiente','revisor':None} for r in REFERENCES],
      'busqueda_catalogo':{'consulta':None,'archivo':None,'sha256':None,'decision':None}})
    print('Registro pendiente creado:',path.relative_to(w.ROOT),'; completar tras leer y aplicar las guías.')

def validate(project,phase='lectura'):
    path='proyectos/'+project['id']+'/skills_aplicadas.json';record=w.read_json(path,{})
    if record.get('estado')!='revisado_aplicado' or record.get('manual')!=w.manual():
        raise ValueError('Leer y aplicar las skills del proyecto; falta registro vigente skills_aplicadas.json')
    actual={x['nombre']:x for x in inventory()};entries={x['nombre']:x for x in record.get('skills',[])}
    for name,now in actual.items():
        entry=entries.get(name,{})
        if any(entry.get(key)!=now[key] for key in ('archivo','sha256','arbol_sha256')):
            raise ValueError('Skill modificada o no registrada: '+name)
        if entry.get('lectura')!='leido_por_agente' or not entry.get('revisor') or not entry.get('aplicacion'):
            raise ValueError('Falta lectura y decisión concreta para skill: '+name)
        if phase=='render':
            if not entry.get('evidencias'):raise ValueError('Falta evidencia de aplicación: '+name)
            for evidence in entry['evidencias']:
                file=evidence.get('archivo');expected=evidence.get('sha256')
                if not file or not w.inside(file).is_file() or expected!=w.digest(file):
                    raise ValueError('Evidencia ausente o modificada para skill: '+name)
    refs={r['archivo']:r for r in record.get('referencias',[])}
    for relative in REFERENCES:
        file=STORE+relative;entry=refs.get(file,{})
        if entry.get('sha256')!=w.digest(file) or entry.get('lectura')!='leido_por_agente' or not entry.get('revisor'):
            raise ValueError('Leer referencia de skills obligatoria: '+file)
    if phase=='render':
        search=record.get('busqueda_catalogo',{});file=search.get('archivo')
        if not search.get('consulta') or not search.get('decision') or not file or not w.inside(file).is_file() or search.get('sha256')!=w.digest(file):
            raise ValueError('Buscar el catálogo y documentar reutilización o construcción propia antes de motion')
    return record

def check_composition(project):
    """Gate real previo al motor; una guía leída no sustituye check ni keyframes."""
    folder='proyectos/'+project['id']+'/diagnosticos_skills';composition=project['motor']['composicion']
    # CLI 0.8.147: check admite un directorio; keyframes admite el HTML.
    # El servidor debe resolver los recursos absolutos de la raíz IVAN.
    if project['motor'].get('recursos_relativos'):
        view=w.inside(composition).parent
    else:
        view=w.inside('.estado/tmp/skills_check_project');view.mkdir(exist_ok=True)
        # El ensamblador 0.8.147 puede excluir un index symlink cuyo destino
        # tiene otro basename. Copia de revisión privada, nunca otra fuente.
        index=view/'index.html';index.unlink(missing_ok=True)
        index.write_text(w.inside(composition).read_text())
        for name in ['recursos','assets','sistema','proyectos']:
            link=view/name
            if not link.exists():link.symlink_to(w.inside(name),target_is_directory=True)
    for operation in ['check','keyframes']:
        arguments=[operation,str(view) if operation=='check' else str(w.inside(composition)),'--json']
        if operation=='check':arguments+=['--browser-gpu','--at-transitions','--max-transition-samples','60']
        result=cli(arguments)
        w.inside(folder).mkdir(exist_ok=True)
        output=folder+'/'+operation+'.json';w.inside(output).write_text(result.stdout)
        w.inside(folder+'/'+operation+'.log').write_text(result.stderr)
        w.write_json(folder+'/'+operation+'_ejecucion.json',{'fecha':w.utc(),
          'comando':['hyperframes',*arguments],
          'returncode':result.returncode,'composicion_sha256':w.digest(composition),'salida':output})
        if result.returncode:raise ValueError('Falló el control HyperFrames '+operation+'; corregir antes de renderizar')
        if operation=='check':
            report=json.loads(result.stdout)
            if not report.get('ok') or report.get('browserSkipped') or not report.get('layout',{}).get('samples'):
                raise ValueError('HyperFrames check no ejecutó el navegador y las muestras; no aprobar por ceros vacíos')
    return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('accion',choices=['actualizar','inventario','preparar','validar'])
    parser.add_argument('ID',nargs='?');args=parser.parse_args()
    if args.accion=='actualizar':update()
    elif args.accion=='inventario':print(json.dumps(inventory(),ensure_ascii=False,indent=2))
    elif not args.ID:parser.error('Falta ID del proyecto')
    elif args.accion=='preparar':template(args.ID)
    else:validate(w.read_json('proyectos/'+args.ID+'/proyecto.json'),phase='render');print('Registro de skills vigente y evidencias comprobadas.')
if __name__=='__main__':main()
