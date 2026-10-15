"""Paquete editable completo y atómico; nunca publica un ZIP parcial ni privados."""
import sys,zipfile,json
sys.dont_write_bytecode=True
import workflow as w

def empaquetar(ID):
    folder='proyectos/'+ID;p=w.read_json(folder+'/proyecto.json');a=w.read_json(folder+'/auditoria_muestra.json')
    w.require_current_instructions(p);w.require_resource_selection(p,hasta=10)
    if a['sha256']!=w.digest(folder+'/'+p['muestra_nombre']) or a['edicion_sha256']!=w.edit_digest(p) or not a.get('revision_editorial'):
        raise ValueError('Revisar el MP4 y sus fuentes actuales antes de empaquetar')
    paths={'AGENTS.md','INSTRUCCIONES.md','PROMPT_MAESTRO.md','STYLE_YO.md','sistema/perfil.json','sistema/herramientas.json','recursos/inventario_drive.json','recursos/gsap.min.js','recursos/Sequel_Sans_Bold_Disp.ttf','recursos/Scholar_Italic.ttf',p['original']['archivo']}
    paths.update(r['archivo'] for r in p['recursos'])
    modules=['workflow.py','seleccion.py','preflight.py','render.py','motion.js','componentes_motion.js','confinar.mjs','browser.mjs','auditar_prueba.py','auditar_temporal.py','verificar_estabilidad_v5.py','informe_prueba.py','entregar_prueba.py','bibliotecas.py','parakeet.py','verificar.py','empaquetar_prueba.py']
    paths.update('sistema/'+name for name in modules)
    for file in w.inside(folder).rglob('*'):
        if file.is_file() and file.suffix in ('.json','.md','.js','.html','.py','.jpg','.csv','.pdf') and not file.name.startswith('qa_nativo_'):
            paths.add(str(file.relative_to(w.ROOT)))
    for block in w.read_json(folder+'/seleccion_recursos.json')['bloques']:
        for candidate in block['candidatos']:paths.update(candidate.get('analisis_visual',{}).get('evidencias',[]))
    paths.update(str(x.relative_to(w.ROOT)) for x in w.inside('assets/referencias/YO').glob('*') if x.is_file())
    for path in paths:
        if path.startswith('.estado/') or not w.inside(path).is_file():raise ValueError('Paquete contiene referencia privada o ausente: '+path)
    out=w.inside(folder+'/fuentes_ascendia_test_v5.zip');tmp=w.inside(str(out)+'.part')
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for path in sorted(paths):
                if path==folder+'/proyecto.json':
                    # El archivo no puede contener su propio recibo final de ZIP.
                    snapshot=dict(p);snapshot.pop('entrega_prueba',None);snapshot.pop('entrega',None)
                    snapshot['etapa']='prueba_v5_revisada';z.writestr(path,json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
                else:z.write(w.inside(path),arcname=path)
        with zipfile.ZipFile(tmp) as z:
            if z.testzip() or set(z.namelist())!=paths:raise ValueError('Paquete corrupto o incompleto')
        tmp.replace(out)
    finally:tmp.unlink(missing_ok=True)
    print('Editable completo verificado:',len(paths),'archivos;',out.stat().st_size,'bytes')

if __name__=='__main__':empaquetar(sys.argv[1])
