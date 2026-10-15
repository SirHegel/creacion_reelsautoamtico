"""Contrato del compositor B_V2 y fixtures CPU. Nunca renderiza MP4."""
import copy, datetime, hashlib, json, pathlib, subprocess, sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'sistema/clone'))
import engine
TMP=ROOT/'.estado/tmp/clone_bv2_qa'
OUT=ROOT/'proyectos/clone_motor/creatividad/comparacion/bv2_compositor_qc.json'
BASELINE=pathlib.Path(__file__).with_name('fixtures')/'composition_v2_preserved.json'
BROWSER=pathlib.Path(__file__).with_name('composition_v2_browser.mjs')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot():
    base=json.loads(BASELINE.read_text())
    return {f:sha(ROOT/f) for f in base['preservation_files']}

def compact_browser(data):
    """El informe público conserva evidencia útil; trazas completas quedan privadas."""
    result={'scope':data.get('scope'),'pass':data.get('pass'),'summary':data.get('summary'),'projects':{},
            'traza_privada':str((TMP/'browser.json').relative_to(ROOT)),
            'traza_sha256':sha(TMP/'browser.json')}
    for name,project in data.get('projects',{}).items():
        item={key:project.get(key) for key in ('pass','errors','checks','compare','proof_png_sha256')}
        detail=project.get('detailed',{})
        if name=='B':
            item['evidence']={'quote_lines':detail.get('quote_lines'),
                'arrival_bbox_max_delta_px':detail.get('arrival_bbox_max_delta_px'),
                'final_values':detail.get('final_values'),
                'bridge_poses':[{'t':pose['t'],**{key:{k:pose[key].get(k) for k in ('bbox','opacity')} if pose.get(key) else None
                    for key in ('bridge','source','target')}} for pose in detail.get('bridge_poses',[])]}
        else:
            item['evidence']={'reading_poses':[{'t':pose['t'],
                'active_instances':{key:{'time':value.get('time'),'layout':value.get('layout'),'primary':value.get('primary')}
                    for key,value in pose['state']['native'].items() if value.get('primary',{}).get('opacity',0)>.1}}
                for pose in detail.get('reading_poses',[])]}
        result['projects'][name]=item
    return result

def main():
    TMP.mkdir(parents=True,exist_ok=True)
    raw=json.loads((ROOT/'proyectos/clone_motor/creatividad/comparacion/scene.json').read_text())
    before=snapshot();source_before=engine.source_fingerprint(ROOT/'proyectos/clone_motor/creatividad/comparacion')
    export_path=OUT.with_name('preview.mp4');export_before=sha(export_path)
    codepaths=['composition.py','layout.js','continuity.js','presentation.js','engine.py']
    code_before={f:sha(ROOT/'sistema/clone'/f) for f in codepaths}
    cases=[]
    def case(name,mutate,valid=False):
        spec=copy.deepcopy(raw);mutate(spec)
        try:engine.validate_spec(spec);accepted=True;error=None
        except Exception as e:accepted=False;error={'type':type(e).__name__,'message':str(e)}
        cases.append({'id':name,'expected_valid':valid,'accepted':accepted,'error':error,'pass':accepted==valid and (accepted or error['type']=='ValueError')})
    case('B_V2_actual',lambda s:None,True)
    def layout(key,value):return lambda s:s['scenes'][1]['layout'].__setitem__(key,value)
    for key,v in [('gap_px',-1),('gap_px',float('nan')),('body_px',True),('body_px',47),('secondary_px',43),('anchor_x',.9),('anchor_y',float('inf')),('margin_px',-1),('profile','unimplemented'),('unknown',1)]:case('invalid_layout_'+key+'_'+str(v),layout(key,v))
    case('invalid_layout_family',lambda s:s['scenes'][0].__setitem__('layout',{'profile':'compact_stack'}))
    for k,v in [('at',float('nan')),('at',True),('at',.5),('at',6.5),('headline','La mejor herramienta'),('kind','winner')]:
        case('invalid_closing_'+k+'_'+str(v),lambda s,k=k,v=v:s['scenes'][1]['closing'].__setitem__(k,v))
    case('closing_without_layout',lambda s:s['scenes'][1].pop('layout'))
    case('closing_without_semantic_limit',lambda s:s['scenes'][1]['params'].__setitem__('caption','Ganador'))
    def op(k,v):return lambda s:s['scenes'][1]['continuity']['operations'][0].__setitem__(k,v)
    for k,v in [('kind','teleport'),('source_port','missing'),('target_port','missing'),('asset','agent_build'),('duration',.1),('duration',.25),('duration',True),('duration',float('inf')),('entity_ids',[]),('entity_ids',['unknown'])]:case('invalid_bridge_'+k+'_'+str(v),op(k,v))
    case('bridge_unsupported_wrapper',lambda s:s['scenes'][1]['transition_in'].__setitem__('kind','push'))
    case('bridge_nonadjacent_origin',lambda s:s['scenes'][1]['continuity'].__setitem__('from_scene','unknown'))
    case('bridge_duplicate_port',lambda s:s['scenes'][1]['continuity']['operations'].append(copy.deepcopy(s['scenes'][1]['continuity']['operations'][0])))
    case('duplicate_namespaces',lambda s:s['scenes'][1].__setitem__('id',s['scenes'][0]['id']))
    for k,v in [('gap_px',36),('gap_px',144),('body_px',48),('body_px',60),('anchor_x',.33),('anchor_x',.67)]:case('valid_boundary_'+k+'_'+str(v),layout(k,v),True)
    fixtures=[]
    for family in ['phone_rebuild','terminal_install']:
        scenes=[]
        for i in range(2):
            params={'caption':'Prueba CPU de reutilización'}
            if family=='terminal_install':params.update(command='crea una agenda',instruction='',roles=[{'role':'design','label':'Diseño'},{'role':'build','label':'Construcción'}])
            scenes.append({'id':family+'_'+str(i),'family':family,'start':4*i,'duration':4,'content':'Fixture técnica, sin demo ni ejecución real.','objective':'Verificar aislamiento y geometría del compositor.','params':params,'layout':{'profile':'centered_primary','anchor_x':.45 if i==0 else .55},'choreography':{'mode':'family_phases'},'transition_in':{'kind':'cut','duration':0},'transition_out':{'kind':'cut','duration':0}})
        spec={'schema_version':1,'duration':8,'scenes':scenes};directory=TMP/family
        engine.compile_spec(spec,directory)
        fixtures.append({'family':family,'folder':str(directory.relative_to(ROOT)),'scope':'Dos instancias CPU; no MP4 ni nueva demo.'})
    browser=subprocess.run(['node',str(BROWSER)],cwd=ROOT,capture_output=True,text=True,timeout=100)
    (TMP/'browser.log').write_text(browser.stdout+'\n'+browser.stderr)
    b=json.loads((TMP/'browser.json').read_text()) if (TMP/'browser.json').exists() else {'error':'Sin reporte de navegador'}
    after=snapshot();base=json.loads(BASELINE.read_text())
    source_after=engine.source_fingerprint(ROOT/'proyectos/clone_motor/creatividad/comparacion')
    code_after={f:sha(ROOT/'sistema/clone'/f) for f in codepaths}
    report={'scope':'B_V2 CPU y contrato; no render ni aprobación estética.','contracts':cases,'fixtures':fixtures,'browser':compact_browser(b),'source_before':source_before,'source_after':source_after,'compositor_before':code_before,'compositor_after':code_after,'preservation':{'files':len(before),'baseline_match':before==base['preservation_files'],'unchanged':before==after,'changed':[f for f,v in before.items() if after[f]!=v]},'checks':{'contracts_pass':all(c['pass'] for c in cases),'browser_returncode_zero':browser.returncode==0,'browser_pass':b.get('pass') is True,'source_unchanged':source_before==source_after,'compositor_unchanged_during_test':code_before==code_after,'preservation_pass':before==after==base['preservation_files']}}
    export_after=sha(export_path);render=json.loads(OUT.with_name('qc.json').read_text())
    report['checks'].update(export_unchanged=export_before==export_after,
        cpu_matches_render_sources=source_after['sha256']==render.get('source_sha256'),
        export_matches_render_receipt=export_after==render.get('mp4_sha256'))
    report['final_export_binding']={'fecha_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'archivo':str(export_path.relative_to(ROOT)),'mp4_sha256':export_after,'source_sha256':source_after['sha256'],
        'cpu_matches_render_sources':report['checks']['cpu_matches_render_sources'],
        'render_receipt_summary':{key:render.get(key) for key in ('duration','frames','fps','decoded_all_frames','sources_stable','hardware_gpu','nvenc')},
        'note':'SHA deMP4comprobado; decodificación/GPU/NVENC constan en el recibo del motor de root. Esta prueba CPU no renderiza ni aprueba estética.'}
    report['test_sha256']=sha(pathlib.Path(__file__))
    report['portable_test_sources']={'browser':{'archivo':str(BROWSER.relative_to(ROOT)),'sha256':sha(BROWSER)},
        'baseline':{'archivo':str(BASELINE.relative_to(ROOT)),'sha256':sha(BASELINE)},
        'dependencies':'HyperFrames0.8.147+Playwright ya instalados en IVAN/.estado/herramientas y Chrome del sistema; no instala ni copia binarios.'}
    report['limits']=['Prueba CPU con compilador y early stub reales0.8.147; no sustituye revisión en movimiento del MP4.',
        'Layout comprobado enspotlight_agent,feedback_bars,phone_rebuild,terminal_install; no cobertura funcional de todas las15familias.',
        'No voz,música,talkinghead,YO,stock ni b-roll enB_V2.',
        'Continuidad medida para el actor compartido deB; no prueba todos los puertos declarados.',
        'La aprobación estética del usuario sigue pendiente; B_V1 permanece histórico.']
    report['status']='PASS_CPU_B_V2' if all(report['checks'].values()) else 'FAIL_OR_STALE'
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'checks':report['checks'],'bad_contracts':[c for c in cases if not c['pass']],'browser_summary':b.get('summary')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
