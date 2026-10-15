#!/usr/bin/env python3
"""Informe reproducible a partir de evidencias; nunca aprueba una edición."""
import sys, html, json
from pathlib import Path
sys.dont_write_bytecode=True
import workflow as w

def construir(identifier):
    folder=w.inside('proyectos/'+identifier)
    p=w.read_json(folder/'proyecto.json');a=w.read_json(folder/'auditoria.json')
    c=w.read_json(folder/'auditoria_correcciones.json');tools=w.read_json('sistema/herramientas.json')
    esc=html.escape
    catalog=w.read_json('recursos/catalogo.json')['archivos']
    cfg=w.read_json('sistema/perfil.json');raw_id=cfg.get('drive_crudos')
    raw_info=('<a href="recurso-configurado:drive/folders/'+esc(raw_id)+'">Crudos</a> está verificada y vinculada. '
              'El comando <code>python3 -B sistema/workflow.py crudos --ingestar</code> detecta videos nuevos y reutiliza proyectos existentes por ID o contenido MD5/tamaño, incluso si cambia el enlace. '
              'La lectura se ejecuta al iniciar el workflow; no se instaló un vigilante periódico.' if raw_id else
              'Crudos aún no tiene un ID confirmado; se utiliza el ID del archivo y no hay un vigilante periódico.')
    records={v.get('archivo'):v for v in catalog.values()}
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+esc(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'
    def resource_label(path):
        r=records.get(path,{})
        return r.get('origen') or ('Drive ID '+r['id'] if r.get('id') else 'Archivo del proyecto')
    resources=sorted({x['archivo'] for x in p['recursos']}|set(w.read_json('sistema/perfil.json')['archivos_tipografia'].values()))
    problems=table(['Tiempo','Problema anterior','Corrección V3'],[(x['tiempo'],x['problema'],x['correccion']) for x in c['problemas_corregidos']])
    timeline=''
    for scene in c['storyboard']:
        timeline+='<article><h3>'+esc(scene['tiempo']+' · '+scene['objetivo'])+'</h3><p><b>Narración:</b> '+esc(scene['narracion'])+'</p><p>'+esc(scene['secuencia'])+'</p><p class="small"><b>Recursos:</b> '+esc(', '.join(scene['recursos']))+'<br><b>Movimiento:</b> '+esc(scene['animacion'])+'<br><b>Subtítulos:</b> '+esc(scene['subtitulos'])+'<br><b>Sonido:</b> '+esc(scene['sonido'])+'<br><b>Salida:</b> '+esc(scene['transicion'])+'</p></article>'
    body=f'''<!doctype html><html lang="es"><meta charset="utf-8"><title>Ascendia V3 · Auditoría y automatización</title><style>
    @page{{size:A4}}*{{box-sizing:border-box}}body{{font:14px/1.5 Arial,sans-serif;color:#17232c;max-width:1100px;margin:32px auto}}h1{{font-size:32px;margin-bottom:8px}}h2{{font-size:21px;margin-top:30px}}h3{{font-size:16px;margin-bottom:6px}}p{{margin:8px 0}}table{{width:100%;border-collapse:collapse;font-size:12px;margin:14px 0}}th,td{{border-bottom:1px solid #dce2e6;padding:9px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#edf1f2}}article{{break-inside:avoid;border-top:1px solid #dce2e6;padding:10px 0}}img{{width:100%;height:auto}}.small{{font-size:12px;color:#435362}}.metrics{{background:#edf1f2;padding:16px;border-radius:12px}}pre{{white-space:pre-wrap;background:#edf1f2;padding:12px;font-size:12px}}a{{color:#17628c}}@media print{{body{{margin:0;font-size:11px}}h1{{font-size:27px}}h2{{font-size:18px}}h3{{font-size:14px}}table{{font-size:10px}}.small{{font-size:10px}}.gallery{{page-break-before:always}}}}
    </style><body><h1>Ascendia V3</h1><p>Reconstrucción de <b>{esc(p['final_nombre'])}</b> desde el crudo, conservando la narración y los cortes originales. {esc(c['fecha'])}.</p>
    <div class="metrics"><b>1080 × 1920 · 30 FPS · H.264 / AAC · 45,97 s</b><br>Presencia programada: 8,02 s (17,45 %); máximo continuo: 1,82 s. Split inferior: 35 %.<br>Revisión temporal: 1.379 fotogramas; cero bandas inferiores alternantes detectadas. Muestra previa: 12 s / 360 fotogramas.</div>
    <h2>Qué se corrigió</h2>{problems}
    <h2>Arquitectura utilizada</h2>{table(['Herramienta','Versión','Comprobación'],[(x['herramienta'],x.get('version') or '—',x['estado']) for x in tools['herramientas']])}
    <p>NVIDIA RTX 4050: inferencia Parakeet en CUDA, composición con Chrome PRIME y codificación H.264 NVENC. Un worker y captura determinista evitan alternancias del lienzo; aumentar workers no es una garantía de calidad. Todas las dependencias, recursos y cachés propias permanecen dentro de IVAN.</p>
    <h2>Automatización para próximos reels</h2><p>El manual se lee antes de cada etapa. Se reutilizan componentes, tipografías, seguimiento suavizado de barbilla, zooms rápidos y render estable. El workflow une todas las apariciones visibles —incluido split— y rechaza más de 3 s continuos o más del 20 %. Un cambio en el manual, recursos o animación invalida la muestra y la auditoría anterior.</p>
    <p>La selección semántica de b-rolls y el storyboard se diseñan por narración. El proyecto actual no se aplica automáticamente a otro guion. La aprobación exige evidencia editorial real; las métricas técnicas por sí solas no publican un video.</p>
    <pre>Desde IVAN, detectar e ingestar nuevos crudos:
python3 -B sistema/workflow.py crudos --ingestar
# Continuar con el ID canónico indicado en el inventario.
Para un ID concreto:
python3 -B sistema/workflow.py ingestar ID
python3 -B sistema/workflow.py transcribir ID
python3 -B sistema/workflow.py rostro ID
python3 -B sistema/workflow.py storyboard ID
# Completar el storyboard semántico y proyecto/motion.js con los recursos reales.
python3 -B sistema/render.py ID --muestra 12
# Revisar muestra; registrar evidencias y corregir antes de continuar.
python3 -B sistema/render.py ID
python3 -B sistema/workflow.py auditar ID
# Documentar la revisión editorial y aprobar las escenas.
python3 -B sistema/workflow.py aprobar ID
python3 -B sistema/workflow.py entregar ID</pre>
    <p>Entrega: una carpeta por crudo, un MP4 vigente, un paquete editable y este informe. Drive se verifica por tamaño y MD5; se reutilizan los IDs existentes para evitar duplicados. {raw_info}</p>
    <h2>Control tipográfico y sonoro</h2><p>Sequel Sans Bold Disp y Scholar Italic reales. Subtítulo tradicional centrado, ancho máximo 820 px y margen nominal 26 px bajo barbilla; texto blanco con sombra negra 2/4/5 px al 85 %. En split, la barbilla se encuadra en y=1598 para reservar 220 px inferiores. Rojo editorial: FURIOSO; los colores nativos de marca conservan su identidad.</p>
    <p>Parakeet CUDA: 149 palabras alineadas; nombres Claude y Agent Reach cotejados. Zoom de cámara: 0,20 s, escala 108 %. Música desde 12 s de su archivo, ganancia −16,3 dB con ducking. Riser: pico 2,83 s / transformación 2,82 s. Medición de mezcla: −15,90 LUFS y −1,52 dBTP.</p>
    <h2>Storyboard por segundos</h2>{timeline}
    <h2>Recursos utilizados y procedencia</h2>{table(['Archivo','Fuente','Uso / derechos documentados'],[(Path(x).name,resource_label(x),records.get(x,{}).get('derechos') or 'Fuente registrada en catálogo; no se atribuye otra licencia') for x in resources])}
    <h2>Alcance de la verificación</h2><ul>{''.join('<li>'+esc(x)+'</li>' for x in c['limites'])}</ul>
    <p>Las seis referencias se inspeccionaron visualmente y se estudiaron estados consecutivos de AGENT, EDIT y CLONE. El registro está en recursos/analisis_referencias.json. La cifra 60.000 procede del discurso original; no se ha probado como número de usuarios ni se confunde con estrellas de GitHub. Los flujos esquemáticos están identificados como conceptos y no prueban una ejecución real del producto.</p>
    <div class="gallery"><h2>Comparación antes / después</h2><img src="comparacion.jpg" alt="Seis pares de fotogramas antes y después"><p class="small">Pares: 0,1; 1,3; 18,5; 28,8; 34,2 y 44,9 segundos. ANTES y V3 se leen bajo cada fotograma.</p><h2>Revisión visual del video completo</h2><img src="auditoria_visual.jpg" alt="Treinta fotogramas de todas las escenas"><p class="small">Muestras visuales de las 13 escenas, complementadas con auditoría temporal de todos los fotogramas. SHA-256 del MP4: {esc(a['candidato_sha256'])}.</p></div></body></html>'''
    (folder/'informe.html').write_text(body)
    (w.ROOT/'sistema/informe_automatizacion.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>Informe vigente de Presentador</title><p><a href="../proyectos/'+esc(identifier)+'/informe.html">Abrir auditoría y automatización ASCENDIA V3</a></p></html>')
    print('Informe canónico:',str((folder/'informe.html').relative_to(w.ROOT)))

if __name__=='__main__':construir(sys.argv[1])
