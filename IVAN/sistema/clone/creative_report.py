"""Informe verificable del lote creativo; nunca aprueba estética ni renderiza."""
import json, sys
sys.dont_write_bytecode = True
import engine as e
import creative_gallery

BASE = e.ROOT / 'proyectos/clone_motor/creatividad'

def build():
    creative_gallery.generate()
    summary = e.load(BASE / 'resumen.json')
    records = summary['records']
    if len(records) != 3 or not all(r['technical_current'] and r['visual_review_current'] and r['comparison_current'] for r in records):
        raise ValueError('Faltan renders, comparaciones o revisiones actuales del lote A/B/C')
    presentation = e.load(BASE / 'presentation_qc.json')
    zero = e.load(BASE / 'runtime_zero_qc.json')
    if not presentation.get('pass') or zero.get('status') not in ('PASS', 'PASS_CPU_CURRENT_SOURCES') or not zero.get('checks', {}).get('all_runtime_checks_pass'):
        raise ValueError('La adaptación editorial o el transporte HyperFrames siguen pendientes')
    for relative, digest in presentation['source_files'].items():
        if e.digest(relative) != digest:
            raise ValueError('Auditoría de presentación obsoleta: ' + relative)
    for record in records:
        evidence = zero['projects'][record['folder'].split('/')[-1]]
        if evidence['source_after']['declared_fingerprint'] != record['current_sha']['composition_sha256'] or not evidence['source_unchanged']:
            raise ValueError('Control de entrada obsoleto: ' + record['id'])
    families = list(dict.fromkeys(f for r in records for f in r['selected_families']))
    result = {'schema_version': 1, 'generated': e.w.utc(), 'status': 'delivered_for_aesthetic_review',
              'aesthetic_approval': False, 'aesthetic_status': 'pending_user_review',
              'library_rebuilt': False, 'installed_tools': False, 'integrated_YO': False,
              'families_used': families, 'counts': summary['counts'],
              'checks': {'presentation': 'PASS', 'hyperframes_entry_transport': 'PASS',
                         'full_frame_decode': True, 'reference_comparisons_current': True},
              'demos': [{'id': r['id'], 'title': r['title'], 'folder': r['folder'],
                        'duration': r['duration_s'], 'frames': r['frames'],
                        'families': r['selected_families'], 'sha': r['current_sha'],
                        'remaining': r['visual_review']['observations']['pending']} for r in records],
              'limits': ['Pruebas conceptuales mudas; ninguna ejecución auténtica de software.',
                         'B usa cifras ficticias de la misma unidad, declaradas; no benchmark ni ganador.',
                         'Comparativas con CLONE por fase aproximada; no prueba de equivalencia literal de movimiento.',
                         'Las fuentes exactas de CLONE siguen sin identificar.',
                         'No se promocionan estas tres variantes por aprobar el QC técnico.']}
    e.write(BASE / 'INFORME_FINAL.json', result)
    lines = ['# CLONE · mejora del generador creativo', '',
             'Tres pruebas de nueve segundos, con seis familias existentes seleccionadas por significado. '
             'Se conserva la biblioteca de 15 familias y CANCELLED. Sin nuevas instalaciones. '
             '**Aprobación estética pendiente del usuario.**', '',
             '| Prueba | Escenas | Archivo |', '|---|---|---|']
    for r in records:
        folder = r['folder'].split('/')[-1]
        scenes = ', '.join(f"{s['start_s']:.1f}–{s['end_s']:.1f}s: {s['family']}" for s in r['scenes'])
        lines.append(f"| {r['id']} · {r['title']} | {scenes} | [MP4]({folder}/preview.mp4) · [Plan]({folder}/PLAN_ESCENAS.md) · [CLONE]({folder}/comparacion_clone.png) |")
    lines += ['', '## Cambios aplicados', '',
              '- Planner: eliminada la prioridad general de composition_graph. Evalúa capacidad narrativa, razón visual y alternativas reales. No impone cuotas de familias.',
              '- Contratos tipados y fases descriptivas de las 15 familias; solo los pasos del compositor abierto son instrucciones nuevas ejecutables.',
              '- Adaptaciones opt-in: rótulos traducidos, tipografía breve ajustada al ancho real, omisión explícita de métricas no aportadas y reencuadre limitado.',
              '- A: transformación mediante máscara, selección real del horario en la representación y continuación geométrica del teléfono entre escenas.',
              '- B: personaje bajo foco, entradas contextualizadas y comparación de barras/contadores con la misma unidad. Una sola transición oscuro→claro.',
              '- C: solicitud escrita en aproximadamente un segundo, paquetes entre roles ampliados, reloj remapeado y resultado que cambia de estado.',
              '- Transporte: resolución del proxy doble de GSAP y estados iniciales ocultos antes de construir tweens de duración cero. Se verifican dentro del bundler/early stub real de HyperFrames.',
              '', '## Validación y alcance', '',
              'Los tres MP4 tienen 1080×1920, H.264, 30 FPS y 270 fotogramas decodificados por archivo. '
              'Captura GPU y NVENC verificados. Timeline directa/inversa, fuentes estables y publicación local atómica. '
              '23 regresiones del planner, 25 contratos inválidos y cuatro positivos; prueba de navegador real de tipografía, colisiones y seek. '
              'El control independiente comprueba las entradas exactas y revelaciones posteriores con HyperFrames.', '',
              'Revisión visual separada: 90 fotogramas a 10 Hz por prueba, diez consecutivos a 30 FPS por empalme y cuatro pares CLONE por prueba. '
              'La comparación por fase evalúa lenguaje y mecanismos; no afirma igualdad literal ni usa correlación HTML/MP4 como similitud estética.', '',
              'Cada carpeta incluye SceneIR, subcomposiciones y bundle editable, guion, plan, recursos incorporados, comparación y recibos vinculados por SHA. '
              'La auditoría de las dos demos anteriores se conserva en [AUDITORIA_VISUAL_INICIAL.md](AUDITORIA_VISUAL_INICIAL.md).', '',
              '## Diferencias pendientes', '']
    for r in records:
        lines += ['**' + r['id'] + '**', ''] + ['- ' + s for s in r['visual_review']['observations']['pending']] + ['']
    lines += ['Las tipografías de CLONE son aproximaciones documentadas. Estas pruebas son conceptuales, sin voz ni ejecución real; '
              'YO, talking head, split 55/45 y sonido esperan la aprobación de las tres pruebas. '
              'No se declara una aprobación estética a partir de los checks técnicos.', '',
              '## Reutilizar el proceso', '', 'Desde IVAN:', '', '```bash',
              'python3 -B sistema/clone/creativity.py plan',
              'python3 -B sistema/clone/creativity.py render',
              'python3 -B sistema/clone/creative_compare.py proyectos/clone_motor/creatividad/app proyectos/clone_motor/creatividad/comparacion proyectos/clone_motor/creatividad/agente',
              '# Después de inspeccionar los renders actuales y guardar visual_review.json:',
              'python3 -B sistema/clone/creative_report.py', '```', '',
              'El informe rechaza revisiones/controles obsoletos. No reconstruye familias, no renderiza y no promociona variantes.', '']
    (BASE / 'INFORME_FINAL.md').write_text('\n'.join(lines))
    return result

if __name__ == '__main__':
    r = build()
    print(json.dumps({'status': r['status'], 'counts': r['counts'], 'families': r['families_used']}, ensure_ascii=False))
