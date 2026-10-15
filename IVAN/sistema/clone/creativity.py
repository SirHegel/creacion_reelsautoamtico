"""Workflow de fixtures creativos: inferencia real independiente, GPU serial y QC.

No selecciona familias ni aprueba estética. La variedad debe resultar de la
interpretación semántica y queda expuesta en el informe para revisión.
"""
import argparse,concurrent.futures,fcntl,json,pathlib,sys
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import engine as e,generate

BRIEFS='proyectos/clone_motor/creatividad/briefs.json'
ROOT_REPORT='proyectos/clone_motor/creatividad/workflow.json'

def run(stage,selected=None):
    generate.require_architecture('render' if stage=='render' else 'lectura')
    brief=e.load(BRIEFS);jobs=[j for j in brief['jobs'] if not selected or j['id'] in selected]
    record=e.load(ROOT_REPORT,{'schema_version':1,'jobs':{}})
    record.update(updated=e.w.utc(),manual=e.w.manual(),scope=brief['scope'],stage=stage,
                  aesthetic_approval='pending_user_review',no_family_prescription=True)
    def work(job):
        folder=e.w.inside(job['folder']);folder.mkdir(parents=True,exist_ok=True)
        (folder/'guion.md').write_text(job['script']+'\n\n'+brief['scope']+'\n')
        try:
            if stage=='plan':receipt=generate.generate(job['script'],folder,duration=brief['duration_s'],plan_only=True)
            else:receipt=generate.resume(folder)
            spec=e.load(folder/'scene.json',{})
            result={'status':receipt['status'],'folder':job['folder'],'families':[s['family'] for s in spec.get('scenes',[])],
                    'duration':spec.get('duration'),'semantic_provider':spec.get('planner',{}),'updated':e.w.utc()}
            return job['id'],result
        except Exception as exc:return job['id'],{'status':'pending','reason':str(exc),'folder':job['folder'],'updated':e.w.utc()}
    # Proveedor remoto concurrente y directorios privados separados. No paralelizar
    # el navegador/GPU: generate mantiene además flock como contrato global.
    workers=3 if stage=='plan' else 1
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(work,j) for j in jobs]):
            ident,result=future.result()
            # Otro proceso puede renderizarA mientras todavía se planificaC.
            # Un progreso nuevo no debe ser borrado por una copia vieja del lote.
            with (e.ROOT/'.estado/clone/creative_workflow.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                latest=e.load(ROOT_REPORT,{'schema_version':1,'jobs':{}})
                latest.update({k:v for k,v in record.items() if k!='jobs'})
                latest['jobs'][ident]=result;e.write(ROOT_REPORT,latest);record=latest
            print(json.dumps({'demo':ident,**result},ensure_ascii=False),flush=True)
    return e.load(ROOT_REPORT,record)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['plan','render']);p.add_argument('--only',nargs='+',choices=['A','B','C']);a=p.parse_args()
    result=run(a.stage,a.only)
    sys.exit(1 if any(j['status']=='pending' for key,j in result['jobs'].items() if not a.only or key in a.only) else 0)
