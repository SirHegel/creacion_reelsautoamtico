"""Paquete curado editable. Excluye autenticación, cachés, logs y dependencias."""
import json,pathlib,sys,zipfile,hashlib
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import engine
w=engine.w;ROOT=engine.ROOT

def build():
    report=engine.load('proyectos/clone_motor/registro_componentes.json');counts=report['counts']
    if counts['total']!=18 or counts['technical_current']!=18 or counts['visual_review_current']!=18 or counts['registered_current_variants']!=2:raise ValueError('La galería no tiene los18previews actuales ylas2variantes verificadas')
    # La biblioteca histórica conserva su registro; las tres pruebas nuevas
    # tienen un gate separado y no se promocionan por pasar controles técnicos.
    if engine.load('proyectos/clone_motor/creatividad/comparacion/scene.json').get('editorial_revision',{}).get('version')=='B_V2':
        import b_v2
        creative=b_v2.report();creative_counts={'technical':1,'reviewed':1,'version':'B_V2'}
    else:
        import creative_report
        creative=creative_report.build();creative_counts={'technical':creative['counts']['technical_current'],'reviewed':creative['counts']['visual_agent_current'],'version':'A_B_C'}
    allowed=set()
    def add_tree(relative,suffixes=None):
        for file in w.inside(relative).rglob('*'):
            if file.is_file() and not file.is_symlink() and (suffixes is None or file.suffix in suffixes):allowed.add(file)
    add_tree('sistema/clone',{'.py','.mjs','.js','.json','.md'})
    add_tree('recursos/clone')
    add_tree('.agents/skills')
    add_tree('proyectos/clone_motor',{'.mp4','.png','.jpg','.svg','.html','.js','.css','.json','.md'})
    for name in ('AGENTS.md','PROMPT_MAESTRO.md','INSTRUCCIONES.md','ESTADO.json',
      'sistema/workflow.py','sistema/skills.py','sistema/skills_entorno.mjs','sistema/skills_instaladas.json','sistema/perfil.json',
      'recursos/Sequel_Sans_Bold_Disp.ttf','recursos/Scholar_Italic.ttf','recursos/gsap.min.js',
      'ejemplos/clone_componente/index.html','ejemplos/clone_componente/diseno.svg','ejemplos/clone_componente/timeline.gsap.js','ejemplos/clone_componente/proyecto.json','ejemplos/clone_componente/frame.md'):
        allowed.add(w.inside(name))
    # Recursos pequeños del componente aprobado, si no están ya embebidos.
    paths=engine.load('sistema/clone/assets.json')
    for record in paths.values():
        if isinstance(record,dict) and record.get('archivo'):allowed.add(w.inside(record['archivo']))
    exclusions={'entrega.json','entrega_creativa.json','paquete_manifest.json'}
    files=[p for p in sorted(allowed) if p.exists() and '.estado'not in p.relative_to(ROOT).parts and 'node_modules'not in p.relative_to(ROOT).parts and p.name not in exclusions and not p.name.endswith('.part.mp4')]
    records=[{'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':w.digest(p)}for p in files]
    manifest={'schema_version':1,'generated':w.utc(),'files':records,'exclusions':['.estado','credenciales','node_modules','modelos','logs','video_fuente_CLONE_canonico_ya_local'],
      'requirements':'Reutilizar la instalación actual dentro deIVAN; el ZIPno instala software niincluye autenticación. Galería/HTMLs se pueden abrir sin el CLI.',
      'creative_tests':{**creative_counts,'aesthetic_approval':False,'aesthetic_status':'pending_user_review'}}
    path=ROOT/'proyectos/clone_motor/paquete_manifest.json';w.write_json(path,manifest)
    output=ROOT/'proyectos/clone_motor/clone_motor_editable.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as archive:
        for p in files:archive.write(p,str(p.relative_to(ROOT)))
        archive.write(path,str(path.relative_to(ROOT)))
    with zipfile.ZipFile(output)as archive:
        if archive.testzip()is not None:raise ValueError('ZIPcorrupto')
        names=archive.namelist()
        if len(names)!=len(set(names)) or any('/.estado/'in n or n.startswith('.estado/')or '/node_modules/'in n for n in names):raise ValueError('Ruta privada/repetida enpaquete')
        for record in records:
            if hashlib.sha256(archive.read(record['file'])).hexdigest()!=record['sha256']:raise ValueError('ContenidoZIPno coincide')
    return {'file':str(output.relative_to(ROOT)),'bytes':output.stat().st_size,'sha256':w.digest(output),'members':len(files)+1,'verified':True}
if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
