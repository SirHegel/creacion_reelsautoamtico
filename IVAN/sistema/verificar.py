#!/usr/bin/env python3
"""Regresiones de las restricciones del workflow; no aprueba calidad editorial."""
import sys,json,unittest,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode=True
import workflow as w

class WorkflowTests(unittest.TestCase):
 def test_presencia_muestra_une_adyacentes_y_recorta_al_segmento(self):
  p={'presentador':[{'inicio':0,'fin':2},{'inicio':2,'fin':4},{'inicio':9.5,'fin':12}]}
  stats=w.presence_stats(p,duration=10)
  self.assertEqual(stats['max_continuo_s'],4);self.assertEqual(stats['segundos'],4.5)
 def test_presencia_muestra_no_duplica_solapamientos(self):
  p={'presentador':[{'inicio':0,'fin':2},{'inicio':1,'fin':3}]}
  self.assertEqual(w.presence_stats(p,duration=10)['segundos'],3)
 def test_skills_instaladas_no_sustituyen_registro_de_aplicacion(self):
  import skills
  with patch.object(w,'read_json',return_value={}):
   with self.assertRaisesRegex(ValueError,'skills_aplicadas'):skills.validate({'id':'reel'})
 def test_render_concurrente_no_pisa_temporales(self):
  import fcntl,render
  with w.inside('.estado/render.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with patch.object(render,'_render') as engine:
    with self.assertRaisesRegex(ValueError,'render de IVAN activo'):render.render('reel',sample=10)
    engine.assert_not_called()
   fcntl.flock(lock,fcntl.LOCK_UN)
 def test_gsap_real_forma_parte_de_huella_de_edicion(self):
  original=w.digest;p={'id':'reel','recursos':[],'original':{'archivo':'recursos/gsap.min.js'}}
  def modified(path,algo='sha256'):
   return 'gsap_modificado' if str(path)=='recursos/gsap.min.js' else original(path,algo)
  first=w.edit_digest(p)
  # Mantener original fijo para demostrar cambio exclusivo del runtime incluido.
  p['original']['archivo']='recursos/Sequel_Sans_Bold_Disp.ttf';first=w.edit_digest(p)
  with patch.object(w,'digest',side_effect=modified):second=w.edit_digest(p)
  self.assertNotEqual(first,second)
 def test_muestra_no_publica_solo_por_evidencia_cualquiera(self):
  audit={'revision_editorial':{'revisor':'agente','evidencias':['STYLE_YO.md']},'sha256':'x'}
  with self.assertRaisesRegex(ValueError,'criterios editoriales'):w.require_sample_review({'id':'reel'},audit)
 def test_skills_bloquean_escritura_fuera_de_ivan_y_protegen_hijos(self):
  import subprocess
  result=subprocess.run(['node','--import',str(w.inside('sistema/skills_entorno.mjs')),'--input-type=module','-e',
   'import fs from "node:fs"; import {spawnSync} from "node:child_process"; let blocked=false; try {fs.writeFileSync("/tmp/ivan_prohibido.txt","x");} catch(e) {blocked=e.message.includes("bloqueada");} const child=spawnSync(process.execPath,["--input-type=module","-e", "import os from \'node:os\'; process.stdout.write(os.homedir());"],{env:process.env,encoding:"utf8"}); if(!blocked||!child.stdout.includes("/IVAN/.estado/hyperframes"))process.exit(1);'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_confinamiento(self):
  for p in ('../fuera','/tmp/video.mp4'):
   with self.assertRaises(ValueError):w.inside(p)
 def test_split_no_reinicia_presencia(self):
  p={'metadata':{'format':{'duration':'40'}},'presentador':[{'inicio':0,'fin':2},{'inicio':2,'fin':4}]}
  with patch.object(w,'edit_digest',return_value='x'):
   self.assertFalse(w.structural_checks(p)['apariciones_hasta_3_segundos'])
 def test_union_no_duplica_presencia(self):
  p={'metadata':{'format':{'duration':'20'}},'presentador':[{'inicio':0,'fin':2},{'inicio':1,'fin':3}]}
  with patch.object(w,'edit_digest',return_value='x'):
   c=w.structural_checks(p);self.assertTrue(c['presencia_hasta_20_por_ciento']);self.assertTrue(c['apariciones_hasta_3_segundos'])
 def test_muestra_caduca_si_cambia_edicion(self):
  p={'metadata':{'format':{'duration':'20'}},'presentador':[],'muestra':{'estado':'aprobada','edicion_sha256':'anterior'}}
  with patch.object(w,'edit_digest',return_value='actual'):
   self.assertFalse(w.structural_checks(p)['muestra_previa_vigente'])
 def test_copia_drive_reutiliza_contenido_entregado(self):
  p={'id':'original','etapa':'entregado_verificado','original':{'md5':'abc','bytes':100}}
  f={'id':'copia_con_otro_id','md5Checksum':'abc','size':'100'}
  c=w.classify_raw(f,[p]);self.assertEqual(c['estado'],'entregado');self.assertEqual(c['proyecto_id'],'original')
 def test_id_con_contenido_cambiado_no_se_omite(self):
  p={'id':'original','etapa':'entregado_verificado','original':{'md5':'abc','bytes':100}}
  f={'id':'original','md5Checksum':'distinto','size':'100'}
  self.assertEqual(w.classify_raw(f,[p])['estado'],'original_modificado')
 def test_instrucciones_modificadas_bloquean_edicion(self):
  p={'manual':{'sha256':'prompt','instrucciones_sha256':'anteriores'}}
  with patch.object(w,'manual',return_value={'sha256':'prompt','instrucciones_sha256':'nuevas'}):
   with self.assertRaisesRegex(ValueError,'Leer e integrar'):w.require_current_instructions(p)
 def test_no_admite_seleccion_solo_por_metadatos(self):
  from seleccion import validar
  with patch.object(w,'read_json',return_value={'estado':'pendiente_seleccion_contextual'}):
   with self.assertRaisesRegex(ValueError,'selección contextual'):validar({'id':'reel'})
 def test_no_descarga_toda_biblioteca_como_preseleccion(self):
  from seleccion import descargar
  selection={'bloques':[{'candidatos':[{'drive_id':str(i),'descargar':True} for i in range(13)]}]}
  with patch.object(w,'read_json',side_effect=[selection,{'elementos':{}}]),patch.object(w,'download') as download:
   with self.assertRaisesRegex(ValueError,'máximo 12'):descargar('reel')
   download.assert_not_called()
 def test_render_no_inicia_motor_sin_revision_contextual(self):
  import render
  p={'id':'reel','manual':w.manual()}
  with patch('preflight.require_ready'),patch.object(w,'read_json',side_effect=[p,{}]),patch.object(render.subprocess,'run') as engine:
   with self.assertRaisesRegex(ValueError,'selección contextual'):render.render('reel',sample=12)
   engine.assert_not_called()
 def test_v4_no_inicia_completo_sin_aprobacion_del_usuario(self):
  import render
  p={'id':'reel','manual':w.manual(),'requiere_aprobacion_prueba_v4':True,'aprobacion_usuario_prueba':{'estado':'pendiente'}}
  with patch('preflight.require_ready'),patch.object(w,'read_json',return_value=p),patch.object(render.subprocess,'run') as engine:
   with self.assertRaisesRegex(ValueError,'aprobación explícita'):render.render('reel')
   engine.assert_not_called()
 def test_v4_rechaza_prueba_que_no_cubre_el_segmento(self):
  from seleccion import validar
  selection={'estado':'revisada_para_prueba','alcance_hasta_s':8}
  with patch.object(w,'read_json',return_value=selection):
   with self.assertRaisesRegex(ValueError,'no cubre'):validar({'id':'reel'},hasta=10)
 def test_seleccion_de_prueba_no_autoriza_reel_completo(self):
  from seleccion import validar
  with patch.object(w,'read_json',return_value={'estado':'revisada_para_prueba','alcance_hasta_s':10}):
   with self.assertRaisesRegex(ValueError,'selección contextual'):validar({'id':'reel'})
 def test_v4_no_inicia_completo_con_resto_sin_reconstruir(self):
  import render
  p={'id':'reel','manual':w.manual(),'metadata':{'format':{'duration':'45'}},'requiere_aprobacion_prueba_v4':True,'aprobacion_usuario_prueba':{'estado':'aprobada'},'motor':{'alcance_hasta_s':10}}
  with patch('preflight.require_ready'),patch.object(w,'read_json',return_value=p),patch.object(render.subprocess,'run') as engine:
   with self.assertRaisesRegex(ValueError,'escenas pendientes'):render.render('reel')
   engine.assert_not_called()
 def test_no_basta_declarar_plan_revisado_sin_ver_clip(self):
  from seleccion import validar,BIBLIOTECAS
  p={'id':'reel','escenas':[{'id':'s0','inicio':0,'fin':1}],'recursos':[]}
  selection={'estado':'revisada_contextualmente','manual':w.manual(),'inventario_sha256':'x','bibliotecas_consultadas':list(BIBLIOTECAS),'bloques':[{'escena_id':'s0','inicio':0,'fin':1,'narracion':'Investiga clientes','intencion':'Demostrar investigación','carpetas_consultadas':['carpeta'],'candidatos':[{'drive_id':'clip','motivo_contextual':'Investigar','analisis_visual':{'estado':'solo_metadata'}}],'decision':{'tipo':'broll','drive_id':'clip','motivo_contextual':'Demostrar investigación'}}]}
  with patch.object(w,'read_json',side_effect=[selection,{'elementos':{'carpeta':{},'clip':{'rol':'broll_dinamico'}}}]),patch.object(w,'digest',return_value='x'):
   with self.assertRaisesRegex(ValueError,'sin ver su contenido'):validar(p)
 def test_no_publica_rechazo(self):
  identifier='_verificacion_'+uuid.uuid4().hex;folder=w.inside('proyectos/'+identifier);folder.mkdir()
  try:
   (folder/'final.mp4').write_bytes(b'rechazado');w.write_json(folder/'proyecto.json',{'id':identifier});w.write_json(folder/'auditoria.json',{'estado':'rechazada_por_usuario'})
   with patch.object(w,'Drive') as drive:
    with self.assertRaisesRegex(ValueError,'sin auditoría'):w.deliver(identifier)
    drive.assert_not_called()
  finally:
   for p in folder.iterdir():p.unlink()
   folder.rmdir()
 def test_cuota_reintenta_subida_rechazada_con_cuerpo_completo(self):
  import io
  from unittest.mock import Mock
  body=io.BytesIO(b'archivo completo');client=object.__new__(w.Drive);client.session=Mock()
  rejected=Mock(status_code=403,ok=False,headers={});rejected.json.return_value={'error':{'message':"Quota exceeded for quota metric 'Queries' and limit 'Previous quota: Requests per minute'",'errors':[{'reason':'quotaExceeded'}]}}
  accepted=Mock(status_code=200,ok=True,headers={})
  seen=[]
  def send(method,url,**kwargs):
   seen.append(kwargs['data'].read());return rejected if len(seen)==1 else accepted
  client.session.request.side_effect=send
  with patch.object(w.time,'sleep'):
   self.assertIs(client.request('PUT','files/recurso',data=body),accepted)
  self.assertEqual(seen,[b'archivo completo',b'archivo completo'])

if __name__=='__main__':unittest.main(verbosity=2)
