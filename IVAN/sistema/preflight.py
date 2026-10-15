#!/usr/bin/env python3
"""Verifica las ocho herramientas; no inicia edición ni usa Tella sin autenticación."""
import os,sys,json,subprocess,hashlib,csv
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.dont_write_bytecode=True;os.chdir(ROOT)
os.environ['PATH']=str(ROOT/'.estado/herramientas/ffmpeg/bin')+':'+os.environ['PATH']
os.environ['TMPDIR']=str(ROOT/'.estado/tmp')
def read(rel):
    p=ROOT/rel
    return json.loads(p.read_text()) if p.is_file() else {}
def command(args):return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip()
def package(name):return read('.estado/herramientas/node_modules/'+name+'/package.json').get('version')
def collect():
    entries=[]
    for name,pkg,expected,proof in [
      ('HyperFrames','hyperframes','0.8.147','.estado/tmp/hyperframes_2_auditoria.json'),
      ('Playwright MCP','@playwright/mcp','0.0.83','.estado/tmp/playwright_mcp_prueba.json'),
      ('Remotion','remotion','4.0.534','.estado/tmp/remotion_auditoria.json')]:
        p=read(proof); passed=p.get('estado') in ['aprobado','operativo']
        if name=='HyperFrames':passed=passed and 'NVIDIA' in (ROOT/'.estado/tmp/hyperframes_2_prueba.log').read_text()
        entries.append({'herramienta':name,'version':package(pkg),'version_solicitada':expected,
          'estado':'operativo' if package(pkg)==expected and passed else 'pendiente_prueba','evidencia':proof})
    node=command(['node','--version']).lstrip('v');codex=command(['codex','--version']).split()[-1]
    ffmpeg=command([str(ROOT/'.estado/herramientas/ffmpeg/bin/ffmpeg'),'-version']).splitlines()[0].split()[2]
    for n,v,ok,e in [('Node.js',node,node.startswith('24.'),'Ejecución de scripts locales'),('Codex CLI',codex,codex=='0.162.1','CLI consultada y orquestación del entorno'),('FFmpeg',ffmpeg,ffmpeg=='9.0.2' and bool(read('.estado/tmp/ffmpeg_prueba.json')),'Render H.264 NVENC + AAC y decodificación completa')]:
        entries.append({'herramienta':n,'version':v,'estado':'operativo' if ok else 'pendiente_prueba','evidencia':e})
    p=read('.estado/tmp/parakeet_prueba.json')
    entries.append({'herramienta':'NVIDIA Parakeet TDT 0.6B v3','version':'v3','estado':'operativo' if p.get('estado')=='operativo' and p.get('words') and p.get('cuda') else 'pendiente_prueba_cuda','evidencia':'.estado/tmp/parakeet_prueba.json'})
    excluded=read('sistema/perfil.json').get('herramientas_excluidas',[])
    t=read('.estado/tella/validacion.json')
    entries.append({'herramienta':'Tella MCP','version':None,'estado':'operativo' if t.get('estado')=='operativo' and t.get('prueba_lectura') else t.get('estado','pendiente_autenticacion'),'evidencia':'.estado/tella/validacion.json','endpoint':'https://api.tella.com/mcp'})
    for entry in entries:
        if entry['herramienta'] in excluded:entry.update(estado='excluida_por_usuario',evidencia='Instrucción explícita: no uses Tella, hazlo ya')
    gpu=command(['nvidia-smi','--query-gpu=name,memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits']).split(', ')
    ram={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        k,v=line.split(':',1)
        if k in ['MemTotal','MemAvailable']:ram[k+'_mib']=round(int(v.split()[0])/1024)
    report={'fecha':datetime.now(timezone.utc).isoformat(),'directiva':read('sistema/perfil.json').get('directiva_vigente','ASCENDIA V4.0'),
      'manual_sha256':hashlib.sha256((ROOT/'PROMPT_MAESTRO.md').read_bytes()).hexdigest(),
      'herramientas':entries,'todas_operativas':all(e['estado'] in ['operativo','excluida_por_usuario'] for e in entries),
      'gpu':{'modelo':gpu[0],'total_mib':int(gpu[1]),'usado_mib':int(gpu[2]),'utilizacion_por_ciento':int(gpu[3]),'ruta':'CUDA + NVENC + Chrome PRIME NVIDIA'},
      'ram':ram,'confinamiento':str(ROOT),
      'siguiente_accion':'Workflow disponible' if all(e['estado'] in ['operativo','excluida_por_usuario'] for e in entries) else 'Completar herramientas pendientes antes de modificar la edición',
      'fuentes_primarias':['https://github.com/heygen-com/hyperframes','https://github.com/microsoft/playwright-mcp','https://www.tella.com/docs/mcp-server','https://ffmpeg.org/download.html','https://www.remotion.dev/docs/renderer/render-media','https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3']}
    if read('sistema/perfil.json').get('skills_obligatorias'):
        from skills import inventory
        try:
            skills=inventory();report['skills']={'estado':'disponibles','cantidad':len(skills),'directorio':'.agents/skills','lectura_y_aplicacion':'Se exige registro por proyecto antes de diseño/render'}
        except ValueError as error:report['skills']={'estado':'pendiente','motivo':str(error)}
    (ROOT/'sistema/herramientas.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report
def require_ready():
    # El comprobante anterior no sustituye una conexión autenticada vigente.
    if 'Tella MCP' not in read('sistema/perfil.json').get('herramientas_excluidas',[]) and (ROOT/'.estado/tella/validacion.json').is_file():
        check=subprocess.run(['node',str(ROOT/'sistema/tella.mjs'),'--comprobar'],cwd=ROOT,timeout=40,capture_output=True,text=True)
        if check.returncode:raise RuntimeError('Tella MCP no pudo comprobar la conexión autenticada vigente')
    report=collect()
    pending=[e['herramienta'] for e in report['herramientas'] if e['estado'] not in ['operativo','excluida_por_usuario']]
    if report.get('skills',{}).get('estado')=='pendiente':pending.append('skills locales')
    if pending:raise RuntimeError('No se puede iniciar edición: falta verificar '+', '.join(pending))
    return report
if __name__=='__main__':
    r=collect();print(json.dumps(r,ensure_ascii=False,indent=2));sys.exit(0 if r['todas_operativas'] else 2)
