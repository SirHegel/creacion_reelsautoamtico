"""Guion→inferencia→SceneIR→HyperFrames→MP4→QC. Ninguna plantilla léxica."""
import argparse,fcntl,hashlib,json,pathlib,subprocess,sys
sys.dont_write_bytecode=True
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import engine,planner
w=engine.w;ROOT=engine.ROOT
from skills import validate as validate_skills

def require_architecture(phase="lectura"):
    project=engine.load(ROOT/"proyectos/clone_motor/proyecto.json",{})
    validate_skills(project,phase)

def fingerprint(folder):
    fn=getattr(engine,'source_fingerprint',None)
    return fn(folder)['sha256'] if fn else w.digest(folder/'index.html')

def promote(folder,review_file):
    folder=w.inside(folder);qc=engine.load(folder/'qc.json',{});clock=engine.load(folder/'timeline_qc.json',{});review=engine.load(review_file,{})
    if not qc.get('decoded_all_frames') or not clock.get('ok'):raise ValueError('Falta render completo/timeline válida')
    if review.get('mp4_sha256')!=w.digest(folder/'preview.mp4') or review.get('composition_sha256')!=fingerprint(folder):raise ValueError('Revisión editorial obsoleta')
    required=('visual_consistency','motion','continuity','semantic_faithfulness','reuse')
    if not all(review.get('checks',{}).get(k) is True for k in required):raise ValueError('La composición conserva verificaciones editoriales pendientes')
    if not review.get('reference_frames') or not review.get('reviewer') or not review.get('observations'):raise ValueError('No hay comparación/observaciones reales de CLONE')
    registry=engine.load(HERE/'variantes.json',{})
    ident=engine.load(folder/'scene.json')['id']
    registry[ident]={'status':'verified_in_reviewed_scope','scene':str((folder/'scene.json').relative_to(ROOT)),
      'preview':str((folder/'preview.mp4').relative_to(ROOT)),'mp4_sha256':qc['mp4_sha256'],
      'composition_sha256':fingerprint(folder),'review':str(w.inside(review_file).relative_to(ROOT)),
      'limits':review.get('limits',[]),'updated':w.utc()}
    engine.write(HERE/'variantes.json',registry)
    return registry[ident]

def produce(folder,spec,receipt):
    require_architecture("render")
    engine.compile_spec(spec,folder)
    # Bloqueo único de GPU/NVENC para encargos del orquestador.
    with (ROOT/'.estado/clone/render.lock').open('a') as gpu:
        fcntl.flock(gpu,fcntl.LOCK_EX)
        qc=engine.render(folder)
    result=subprocess.run(['node',str(HERE/'review.mjs'),str(folder.relative_to(ROOT))],cwd=ROOT,capture_output=True,text=True)
    clock=engine.load(folder/'timeline_qc.json',{})
    if result.returncode or not clock.get('ok'):raise ValueError('Timeline no estable: '+result.stdout[-1200:])
    if receipt.get('reason'):receipt.setdefault('resolved_issues',[]).append({'issue':receipt.pop('reason'),'resolution':'Nueva compilación con revisión de timeline correcta','at':w.utc()})
    receipt.update(status='rendered_pending_editorial_review',mp4_sha256=qc['mp4_sha256'],composition_sha256=fingerprint(folder),
      rendered_frames=qc['frames'],editorial_status='pending',updated=w.utc())
    registry=engine.load(HERE/'variantes.json',{});registry[spec['id']]={'status':'pending_editorial_review',
      'scene':str((folder/'scene.json').relative_to(ROOT)),'preview':str((folder/'preview.mp4').relative_to(ROOT)),
      'mp4_sha256':qc['mp4_sha256'],'composition_sha256':fingerprint(folder),'updated':w.utc()}
    engine.write(HERE/'variantes.json',registry)
    engine.write(folder/'generation.json',receipt);return receipt

def generate(script,folder,duration=10,narration=None,plan_only=False):
    require_architecture()
    folder=w.inside(folder);folder.mkdir(parents=True,exist_ok=True)
    # Una carpeta explícita por encargo evita escribir en otra instancia de Studio.
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt={'schema_version':1,'status':'planning','updated':w.utc(),'script_sha256':planner.hash_text(script),
          'manual':w.manual(),'no_keyword_fallback':True,'audio_supplied':bool(narration)}
        engine.write(folder/'generation.json',receipt)
        try:
            spec=planner.plan(script,output=folder/'scene.json',narration=narration,duration=duration)
            receipt.update(status='planned',semantic_inference=True,scene_ir_sha256=w.digest(folder/'scene.json'))
            engine.write(folder/'generation.json',receipt)
            if plan_only:return receipt
            return produce(folder,spec,receipt)
        except Exception as exc:
            receipt.update(status='pending',reason=str(exc),updated=w.utc());engine.write(folder/'generation.json',receipt)
            spec=engine.load(folder/'scene.json',{});registry=engine.load(HERE/'variantes.json',{})
            if spec.get('id'):registry[spec['id']]={'status':'pending','scene':str((folder/'scene.json').relative_to(ROOT)),'reason':str(exc),'updated':w.utc()};engine.write(HERE/'variantes.json',registry)
            raise

def resume(folder):
    folder=w.inside(folder);spec=engine.load(folder/'scene.json',{});receipt=engine.load(folder/'generation.json',{})
    proof_path=spec.get('planner',{}).get('proof')
    if not proof_path:raise ValueError('Reanudar exige un plan con recibo de inferencia real')
    proof=engine.load(proof_path,{})
    canonical=engine.load(w.inside(proof_path).parent.parent/'scene.json',{})
    if not proof.get('real_inference') or proof.get('returncode') not in (None,0):raise ValueError('Proveedor no comprobado')
    for key in ('scenes','semantic_analysis','timing'):
        if spec.get(key)!=canonical.get(key):raise ValueError('Plan semántico editado: generar una nueva inferencia o usar compile como autoría explícita')
    if receipt.get('manual')!=w.manual():raise ValueError('El manual cambió: revisar el plan antes de reanudar')
    with (folder/'.generation.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return produce(folder,spec,receipt)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    g=sub.add_parser('create');text=g.add_mutually_exclusive_group(required=True)
    text.add_argument('--script');text.add_argument('--script-file');g.add_argument('--out',required=True)
    g.add_argument('--duration',type=float,default=10);g.add_argument('--narration');g.add_argument('--plan-only',action='store_true')
    p=sub.add_parser('promote');p.add_argument('folder');p.add_argument('--review',required=True)
    r=sub.add_parser('resume');r.add_argument('folder')
    args=parser.parse_args()
    if args.command=='promote':result=promote(args.folder,args.review)
    elif args.command=='resume':result=resume(args.folder)
    else:
        script=args.script or w.inside(args.script_file).read_text()
        narration=engine.load(args.narration) if args.narration else None
        result=generate(script,args.out,args.duration,narration,args.plan_only)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
