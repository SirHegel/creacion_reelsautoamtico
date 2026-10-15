#!/usr/bin/env python3
"""Informe de una prueba por crudo. No modifica edición ni concede aprobación.

Sin --final prepara únicamente el HTML y distingue datos previstos de resultados.
--final exige auditoría y recursos vinculados al MP4 y a la edición actuales;
entonces escribe el manifest de nueve columnas y la lista de componentes.
El PDF se exporta después desde informe.html con el navegador ya instalado.
"""
import argparse
import csv
import html
import re
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import workflow as w


def esc(value):
    return html.escape(str(value))


def segundos(value):
    return f'{float(value):.3f}'.rstrip('0').rstrip('.').replace('.', ',')


def intervalo(start, end):
    return segundos(start) + '–' + segundos(end) + ' s'


def tabla(headers, rows):
    return '<table><thead><tr>' + ''.join('<th>'+esc(h)+'</th>' for h in headers) + \
        '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+
        '</tr>' for row in rows) + '</tbody></table>'


def misma_fuente(a, b):
    return bool(a and b and w.inside(a) == w.inside(b))


def tiempos_presencia(appearances):
    merged = []
    for actor in sorted(appearances, key=lambda a: a['inicio']):
        start, end = float(actor['inicio']), float(actor['fin'])
        if end <= start:
            raise ValueError('Intervalo de presencia inválido')
        if merged and start <= merged[-1][1]+1/30:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start,end])
    return (sum(end-start for start,end in merged),
            max((end-start for start,end in merged), default=0))


def verificar_final(project, audit, video):
    """No reutilizar controles de un render anterior o de otros recursos."""
    if not video.is_file() or audit.get('sha256') != w.digest(video):
        raise ValueError('El SHA de la auditoría no corresponde al MP4 actual')
    if audit.get('edicion_sha256') != w.edit_digest(project):
        raise ValueError('La edición cambió después de la auditoría')
    checks = audit.get('comprobaciones', {})
    required = ('1080x1920','30fps','h264','aac','duracion_10s',
                '300_frames_decodificados','voz_original_alineada',
                'sin_banda_inferior_divergente','medios_reales_identificados',
                'max_presencia_3s','presencia_objetivo_20porciento')
    if any(checks.get(key) is not True for key in required) or not all(checks.values()):
        raise ValueError('La prueba no ha superado todos los controles técnicos necesarios')
    style = project.get('style_yo', {})
    if style.get('archivo') and style.get('sha256') != w.digest(style['archivo']):
        raise ValueError('El perfil YO cambió después de registrar la edición')
    for clip in project.get('broll', []):
        proof = next((r for r in audit.get('medios_reales', [])
                      if misma_fuente(r.get('archivo'), clip.get('archivo'))), None)
        if not proof or proof.get('correlacion_rgb', 0) < .88:
            raise ValueError('Falta prueba de aparición del recurso: '+clip['archivo'])
        t = float(proof['render_s'])
        if not float(clip['inicio']) <= t < float(clip['fin']):
            raise ValueError('La prueba de aparición está fuera del tramo de '+clip['archivo'])
        expected = float(clip.get('offset', 0)) + t - float(clip['inicio'])
        tolerance = float(proof.get('tolerancia_fuente_s', 1/30)) + 1e-5
        if abs(float(proof['fuente_s']) - expected) > tolerance:
            raise ValueError('La prueba pertenece a otro tiempo de fuente: '+clip['archivo'])
        declaration = next((r for r in project.get('recursos', [])
                            if misma_fuente(r.get('archivo'), clip['archivo'])), None)
        if not declaration or declaration.get('sha256') != w.digest(clip['archivo']):
            raise ValueError('El recurso cambió después de seleccionarlo: '+clip['archivo'])
    folder = video.parent
    for name in ('fotogramas_prueba.jpg', 'comparacion_YO.jpg'):
        image = folder/name
        if not image.is_file() or image.stat().st_mtime < video.stat().st_mtime:
            raise ValueError('Falta una captura actual del MP4: '+name)


def fichas(project, selection, audit, final):
    candidates = [c for block in selection.get('bloques', [])
                  for c in block.get('candidatos', [])]
    extra = w.read_json('proyectos/'+project['id']+'/auditoria_recursos.json', {})
    if extra.get('crudo_id') == project['id']:
        candidates += extra.get('candidatos', [])
    candidates += list(w.read_json('recursos/catalogo.json', {}).get('archivos', {}).values())
    result = []
    for clip in project.get('broll', []):
        path = clip['archivo']
        record = next((c for c in candidates if misma_fuente(c.get('archivo'), path)), {})
        visual = record.get('analisis_visual', {})
        source_id = record.get('drive_id') or record.get('id')
        source = record.get('enlace') or record.get('origen')
        if source_id:
            source = 'recurso-configurado:file/d/'+source_id+'/view'
        content = visual.get('contenido_observado') or record.get('contenido_observado') or \
                  'Contenido descrito en la selección de recursos del proyecto.'
        scene = next((s for s in project['escenas'] if s.get('id') == clip.get('id')), None)
        if not scene:
            scene = next((s for s in project['escenas']
                          if s['inicio'] <= clip['inicio'] < s['fin']), {})
        proof = next((r for r in audit.get('medios_reales', [])
                      if misma_fuente(r.get('archivo'), path)), {}) if final else {}
        metadata = w.probe(path)
        stream = next(s for s in metadata['streams'] if s['codec_type'] == 'video')
        start, end = float(clip['inicio']), float(clip['fin'])
        offset = float(clip.get('offset', 0))
        result.append({
            'archivo': Path(path).name, 'ruta': path, 'fuente': source or 'Fuente pendiente de documentar',
            'drive_id': source_id, 'duracion_s': float(metadata['format']['duration']),
            'resolucion': str(stream['width'])+'×'+str(stream['height']),
            'contenido': content, 'frase': scene.get('frase', ''),
            'previsto': intervalo(start, end), 'real': intervalo(start, end) if final else 'Pendiente',
            'fuente_tramo': intervalo(offset, offset+end-start),
            'estado': ('Identificado en MP4; correlación RGB '+f"{proof['correlacion_rgb']:.3f}"
                       if final else 'Candidato visto; aparición final pendiente'),
            'sha256': w.digest(path), 'derechos': record.get('derechos') or
                'Biblioteca proporcionada por el cliente; licencia comercial independiente no comprobada.',
            'limite': record.get('limite') or visual.get('limite') or record.get('motivo_contextual', ''),
        })
    return result


def generar(identifier, final=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', identifier):
        raise ValueError('ID de proyecto inválido')
    folder = w.inside('proyectos/'+identifier)
    project = w.read_json(folder/'proyecto.json')
    if not project:
        raise ValueError('No existe proyecto para el crudo indicado')
    audit = w.read_json(folder/'auditoria_muestra.json', {})
    selection = w.read_json(folder/'seleccion_recursos.json', {})
    video = folder/project.get('muestra_nombre', 'ascendia_test_v5_10s.mp4')
    if final:
        verificar_final(project, audit, video)
    records = fichas(project, selection, audit, final)
    raw_duration = float(project['metadata']['format']['duration'])
    visual_end = float(project.get('motor', {}).get('alcance_hasta_s', 10))
    tail = max(0, visual_end-raw_duration)
    appearances = project.get('presentador', [])
    face_seconds, longest = tiempos_presencia(appearances)
    status = ('Prueba exportada y controles técnicos vigentes; revisión de Presentador pendiente.' if final else
              'Informe en preparación. Los datos de montaje son previstos; el render final aún no está certificado.')
    clip_rows = [(r['archivo'], r['resolucion']+' · '+segundos(r['duracion_s'])+' s',
                  r['fuente_tramo'], r['real'] if final else r['previsto'], r['estado']) for r in records]
    scenes = [(intervalo(s['inicio'],s['fin']), s['frase'], s['objetivo'],
               s.get('composicion','').replace('_',' ')) for s in project['escenas']
              if s['inicio'] < visual_end]
    source_cards = ''.join('<article><h3>'+esc(r['archivo'])+'</h3><p>'+esc(r['contenido'])+
                          '</p><p class="small"><b>Fuente:</b> <a href="'+esc(r['fuente'])+'">'+
                          esc(r['fuente'])+'</a><br><b>Derechos:</b> '+esc(r['derechos'])+
                          '<br><b>Límite:</b> '+esc(r['limite'])+'<br><b>SHA-256:</b> <code>'+r['sha256']+
                          '</code></p></article>' for r in records)
    frames = audit.get('frames_inspeccion_temporal', 0) if final else 0
    original_corr = audit.get('audio', {}).get('correlacion_voz_original') if final else None
    correlation_text = f'{original_corr:.3f}' if original_corr is not None else 'pendiente'
    technical_rows = [(key.replace('_',' '), 'Correcto' if value is True else 'Pendiente / fallo')
                      for key,value in audit.get('comprobaciones', {}).items()] if final else \
                     [('Controles del MP4 actual', 'Pendientes de la auditoría del nuevo render')]
    def imagen(name, caption):
        path = folder/name
        if final and path.is_file():
            return '<figure><img src="'+esc(name)+'" alt="'+esc(caption)+'"><figcaption>'+esc(caption)+'</figcaption></figure>'
        return '<p class="pending">Captura actual pendiente: '+esc(name)+'</p>'
    components = project.get('motion_graphics', [])
    component_list = '<ul>'+''.join('<li>'+esc(c.replace('_',' '))+'</li>' for c in components)+'</ul>'
    stamp = w.utc()
    html_text = '''<!doctype html><html lang="es"><head><meta charset="utf-8"><title>ASCENDIA V5 · Prueba de 10 segundos</title>
<style>@page{size:A4;margin:14mm}*{box-sizing:border-box}body{font:13px/1.55 Arial,sans-serif;color:#20242b;max-width:1060px;margin:32px auto;padding:0 12px}h1{font-size:30px;line-height:1.15;margin:0 0 10px}h2{font-size:20px;margin:26px 0 10px}h3{font-size:15px;margin:12px 0 6px}p{margin:7px 0}a{color:#1d526d}code{font-size:10px;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;margin:14px 0;font-size:11px}th,td{padding:8px 7px;border-bottom:1px solid #d8dce1;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f0f2f4}article{break-inside:avoid;border-top:1px solid #ddd;padding:10px 0}.box{background:#edf1f4;padding:14px 16px;margin:14px 0;border-left:3px solid #243846}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.metric{padding:13px;background:#f2f3f5}.metric b{display:block;font-size:21px}.small,figcaption{font-size:11px;color:#505c68}figure{margin:14px 0}img{display:block;width:100%;height:auto}figcaption{margin-top:7px}.page{break-before:page}.pending{background:#fff0d2;padding:10px}ul{padding-left:19px}@media print{body{margin:0;padding:0;font-size:10.5px}h1{font-size:27px}h2{font-size:17px}h3{font-size:13px}table{font-size:9px}.small,figcaption{font-size:9px}.metrics{gap:8px}.metric b{font-size:18px}a{color:#1d526d;text-decoration:none}}</style></head><body>'''
    html_text += '<h1>ASCENDIA V5</h1><p>Prueba de diez segundos · '+esc(stamp)+'</p><div class="box">'+esc(status)+'</div>'
    html_text += '<div class="metrics"><div class="metric"><b>1080 × 1920</b>30 FPS · H.264 / AAC</div><div class="metric"><b>'+segundos(face_seconds)+' s</b>Presencia programada · '+f'{face_seconds/visual_end*100:.1f}'.replace('.',',')+' %</div><div class="metric"><b>'+str(frames if final else 'Pendiente')+'</b>Fotogramas auditados del render actual</div></div>'
    html_text += '<h2>Alcance de esta entrega</h2><p>Montaje nuevo desde el crudo <b>'+esc(project['nombre_original'])+'</b>. La narración original dura '+segundos(raw_duration)+' s; se conserva sin cambio de velocidad. La prueba dura '+segundos(visual_end)+' s y añade únicamente '+segundos(tail)+' s de resolución visual, sin voz, oferta, CTA ni afirmación nueva.</p>'
    html_text += '<p>YO define la identidad, el lenguaje del hook, la jerarquía tipográfica y el encuadre humano. AGENT, EDIT y CLONE orientan la ambición del movimiento. El proyecto anterior no se reutiliza como montaje de este crudo.</p>'
    html_text += '<h2>Identidad observada y adaptación</h2><p>En YO, el hook construye una frase sobre b-roll real y presentador, con énfasis mayor en «furioso». El split original se aproxima a 50/50; la prueba adopta el 55/45 solicitado para V5. Una sola grabación original conserva iluminación y fondo. No hay relleno duplicado, blur añadido ni fondo artificial.</p>'
    html_text += '<p>El perfil <a href="../../STYLE_YO.md">STYLE_YO.md</a> distingue medidas observadas de estimaciones. Los tamaños, el CSS exacto y las curvas de movimiento del MP4 original no pueden recuperarse con certeza. Sequel Sans Bold Disp y Scholar Italic son archivos auténticos; la sombra corta negra se compara visualmente con YO. La captura específica «porque ahora» no está disponible.</p>'
    html_text += imagen('comparacion_YO.jpg','Fotogramas reales de YO y de la prueba vigente. Comparación de composición, titular, rostro y texto; adaptación 55/45, sin atribuir CSS exacto al original.')
    html_text += '<h2>Storyboard del montaje vigente</h2>'+tabla(['Tiempo','Narración / objetivo','Acción visual','Composición'],scenes)
    html_text += '<p>Presencias programadas: '+esc('; '.join(intervalo(a['inicio'],a['fin']) for a in appearances))+'. Máximo continuo: '+segundos(longest)+' s. La presencia en split cuenta para el límite de tres segundos; texto tradicional centrado bajo barbilla y tipografía editorial integrada en el hook y los recursos.</p>'
    html_text += '<div class="page"></div><h2>B-rolls incorporados'+(' y comprobados' if final else ' — uso previsto')+'</h2>'+tabla(['Archivo','Calidad de fuente','Tramo original','Ventana en prueba','Verificación'],clip_rows)
    html_text += '<p class="small">'+('La identidad de cada medio se cotejó con píxeles de su fuente en el MP4 vigente (correlación RGB ≥0,88). Los intervalos son las ventanas del compositor, incluyendo entradas, salidas y superposiciones; no implican visibilidad íntegra de toda la imagen original.' if final else 'No se declara uso real mientras el render final y sus pruebas de procedencia estén pendientes.')+'</p>'+source_cards
    html_text += '<h2>Representaciones y credibilidad</h2><p>El spot de Workspace identifica a Google; no acredita una reacción oficial de enfado. Claude Agent View muestra ejecución de tareas, no la skill concreta del narrador. Web Fetch muestra lectura auténtica de Calendly; no prueba extracción de LinkedIn, YouTube o Instagram ni el coste de sus APIs.</p>'
    html_text += '<p>El recorrido de plataformas, extracción, convergencia y ruta alternativa se presenta como esquema conceptual. No se fabrican resultados, perfiles ni cifras. «Google está furioso» y la ausencia de pago pertenecen al discurso original; no se convierten en afirmaciones verificadas por esta edición.</p>'
    html_text += '<p>Se consultó el <a href="https://github.com/Panniantong/Agent-Reach">repositorio de Agent Reach</a> para contexto técnico: contempla integración con Claude Code y distintos canales de acceso, algunos con autenticación o dependencias. El crudo nuevo no nombra Agent Reach; el video no añade ese nombre ni afirma acceso universal.</p>'
    html_text += '<div class="page"></div><h2>Revisión técnica del MP4</h2>'+tabla(['Control','Resultado'],technical_rows)
    html_text += '<p>Correlación de la voz original con la mezcla: '+correlation_text+'. Se verifica alineación y conservación mediante señales y ASR. No se afirma audición perceptiva del audio por los agentes. La revisión técnica no sustituye el juicio estético ni la aprobación de Presentador.</p>'
    html_text += '<p>La inspección temporal cubre todos los fotogramas; la revisión visual incluye escenas y transiciones consecutivas. Se comparan las zonas inferiores con el encuadre original, sin confundir una validación de codec con una auditoría de parpadeo.</p>'
    html_text += imagen('fotogramas_prueba.jpg','Muestras del MP4 vigente complementadas por la auditoría temporal de los 300 fotogramas y las secuencias contiguas de transición.')
    html_text += '<h2>Movimiento y componentes editables</h2><p>Los componentes declarados se combinan en secuencias de acción, reacción, transformación y salida. Trayectorias, máscaras, parallax y cambios de superficie explican la extracción y ensamblaje; los fades y escalas son auxiliares. La aprobación de su calidad se apoya en el render, no solo en esta lista.</p>'+component_list
    html_text += '<h2>Sonido y herramientas</h2><p>Se conserva la voz original. Música y efectos proceden de las bibliotecas del cliente; la entrada musical se toma dentro del archivo, sin retrasar su inicio en el video. Riser y burn se sincronizan con la transformación del hook; wooshes son selectivos. No se atribuyen licencias adicionales a los recursos proporcionados.</p>'
    html_text += '<p>HyperFrames, Node y FFmpeg/NVENC producen la prueba; NVIDIA también está disponible para Parakeet. Playwright sirve para inspección y reproducción. Se reutilizan las dependencias verificadas, sin instalaciones nuevas. Remotion y Codex CLI permanecen verificados en el entorno; no se afirma un componente Remotion incorporado a esta prueba si no figura en los recursos. Tella sigue excluido por el usuario.</p>'
    html_text += '<h2>Entrega y continuidad</h2><p>La prueba contiene el MP4, proyecto editable, STYLE_YO.md, storyboard, manifest de nueve columnas, fuentes, componentes, comparativas y esta auditoría. El PDF se llama <code>informe_ascendia_test_v5.pdf</code>. La entrega en Drive se verifica por tamaño y MD5; este generador no publica ni autoriza el render de otros videos.</p>'
    html_text += '<p>Para otro crudo: leer todas las instrucciones vigentes, analizar el discurso, consultar ambas bibliotecas, descargar pocos candidatos, verlos, escoger tramos y construir un storyboard nuevo. La identidad y los componentes se reutilizan; los recursos y el montaje se deciden por contenido. La aprobación de la prueba de Presentador sigue pendiente.</p>'
    if final:
        html_text += '<p class="small"><b>MP4 SHA-256:</b> <code>'+esc(audit['sha256'])+'</code><br><b>Edición SHA-256:</b> <code>'+esc(audit['edicion_sha256'])+'</code></p>'
    html_text += '</body></html>'
    (folder/'informe.html').write_text(html_text, encoding='utf-8')
    if final:
        with (folder/'broll_manifest.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Archivo','Ruta local','Fuente original','Duración','Contenido visual',
                             'Frase a la que corresponde','Tiempo previsto de utilización',
                             'Tiempo realmente utilizado','Estado de verificación'])
            for r in records:
                writer.writerow([r['archivo'],r['ruta'],r['fuente'],segundos(r['duracion_s'])+' s',
                                 r['contenido'],r['frase'],r['previsto'],r['real'],r['estado']])
        md = ['# Componentes de la prueba', '',
              'Proyecto: `'+identifier+'`. Fuente editable: `'+project['motor']['fuente']+'`.', '',
              'Declarados en el proyecto y revisables en el render; esta lista no sustituye la inspección del movimiento.', '']
        md.extend('- '+c.replace('_',' ') for c in components)
        md += ['', 'Cada nuevo crudo requiere storyboard y selección propios. No se reutiliza automáticamente este montaje.', '',
               'MP4 SHA-256: `'+audit['sha256']+'`.']
        (folder/'componentes_prueba.md').write_text('\n'.join(md)+'\n', encoding='utf-8')
    print('Informe '+('final vinculado a QA' if final else 'provisional')+': '+str((folder/'informe.html').relative_to(w.ROOT)))
    return {'informe': str((folder/'informe.html').relative_to(w.ROOT)), 'final': final,
            'manifest': str((folder/'broll_manifest.csv').relative_to(w.ROOT)) if final else None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('id')
    parser.add_argument('--final', action='store_true', help='Exigir QA actual y escribir uso real en CSV')
    args = parser.parse_args()
    generar(args.id, final=args.final)
