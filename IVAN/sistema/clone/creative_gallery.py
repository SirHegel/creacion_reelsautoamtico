"""Galería A/B/C de planes, renders y revisiones, sin producir ni aprobar.

generate() tolera entradas ausentes durante el lote. Toda salida permanece en
IVAN. La estética conserva estado pendiente_usuario aun con QC correcto.
"""
from __future__ import annotations

import datetime
import hashlib
import html
import importlib.util
import json
import os
import pathlib
import sys
from urllib.parse import quote

sys.dont_write_bytecode = True
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / 'proyectos/clone_motor/creatividad'
DEFAULT_JOBS = [
    {'id': 'A', 'title': 'Herramienta → aplicación', 'folder': str((BASE / 'app').relative_to(ROOT))},
    {'id': 'B', 'title': 'IA compara resultados', 'folder': str((BASE / 'comparacion').relative_to(ROOT))},
    {'id': 'C', 'title': 'Solicitud → proceso → resultado', 'folder': str((BASE / 'agente').relative_to(ROOT))},
]


def _read(path, warnings):
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        warnings.append({'file': str(path.relative_to(ROOT)), 'status': 'archivo_pendiente_de_lectura',
                         'reason': type(exc).__name__})
        return {}


def _sha(path):
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _inside(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError('Ruta fuera de IVAN')
    return resolved


def _href(path):
    path = _inside(path)
    if not path.is_file():
        return None
    return quote(os.path.relpath(path, BASE), safe='/._-')


def _fingerprint(folder, warnings):
    if not (folder / 'index.html').is_file():
        return None
    # Función de lectura de dependencias; no se llama compile/render/catalog.
    try:
        spec = importlib.util.spec_from_file_location('creative_gallery_engine', HERE / 'engine.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.source_fingerprint(folder)['sha256']
    except (OSError, ValueError) as exc:
        warnings.append({'file': str(folder.relative_to(ROOT)), 'status': 'fuentes_pendientes',
                         'reason': type(exc).__name__})
        return None


def _record(job, warnings):
    folder = _inside(ROOT / job['folder'])
    spec = _read(folder / 'scene.json', warnings)
    generation = _read(folder / 'generation.json', warnings)
    review = _read(folder / 'visual_review.json', warnings)
    qc = _read(folder / 'qc.json', warnings)
    timeline = _read(folder / 'timeline_qc.json', warnings)
    hashes = {'mp4_sha256': _sha(folder / 'preview.mp4'),
              'html_sha256': _sha(folder / 'index.html'),
              'scene_sha256': _sha(folder / 'scene.json'),
              'composition_sha256': _fingerprint(folder, warnings)}
    render_current = bool(hashes['mp4_sha256'] and qc.get('mp4_sha256') == hashes['mp4_sha256']
                          and qc.get('html_sha256') == hashes['html_sha256'])
    if qc.get('source_sha256'):
        render_current = render_current and qc['source_sha256'] == hashes['composition_sha256']
    if qc.get('scene_sha256'):
        render_current = render_current and qc['scene_sha256'] == hashes['scene_sha256']
    clock_current = bool(timeline.get('ok') and timeline.get('html_sha256') == hashes['html_sha256'])
    if timeline.get('source_sha256'):
        clock_current = clock_current and timeline['source_sha256'] == hashes['composition_sha256']
    technical_pass = bool(render_current and clock_current and qc.get('decoded_all_frames'))
    technical_status = ('sin_render' if not hashes['mp4_sha256'] else 'verificado' if technical_pass
                        else 'pendiente_o_desactualizado')
    visual_current = bool(review and hashes['mp4_sha256'] and
                          review.get('mp4_sha256') == hashes['mp4_sha256'] and
                          review.get('composition_sha256') == hashes['composition_sha256'])
    if review.get('scene_sha256'):
        visual_current = visual_current and review['scene_sha256'] == hashes['scene_sha256']
    agent_status = review.get('status', review.get('estado', 'revisado_por_agente')) if visual_current else (
        'revision_obsoleta' if review else 'pendiente_revision_agente')
    observed_families = review.get('families_observed', []) if visual_current else []
    if not isinstance(observed_families, list):
        observed_families = []
    scenes = []
    for scene in spec.get('scenes', []):
        start, duration = scene.get('start'), scene.get('duration')
        end = start + duration if isinstance(start, (int, float)) and isinstance(duration, (int, float)) else None
        scenes.append({'id': scene.get('id'), 'start_s': start, 'end_s': end,
                       'duration_s': duration, 'family': scene.get('family'),
                       'content': scene.get('content', ''), 'objective': scene.get('objective', ''),
                       'semantic_reason': scene.get('semantic_reason', ''),
                       'visual_reason': scene.get('visual_reason', scene.get('semantic_reason', '')),
                       'alternatives': scene.get('alternatives', scene.get('alternatives_rejected', [])),
                       'actions': scene.get('actions', []),
                       'presentation': scene.get('presentation'),
                       'transition_in': scene.get('transition_in'), 'transition_out': scene.get('transition_out'),
                       'family_appearance_reviewed': scene.get('family') in observed_families})
    families = list(dict.fromkeys(s['family'] for s in scenes if s['family']))
    links = {}
    for label, name in [('video', 'preview.mp4'), ('poster', 'poster.png'), ('plan', 'PLAN_ESCENAS.md'),
                        ('comparison', 'comparacion_clone.png'), ('comparison_data', 'comparacion_clone.json'),
                        ('scene_ir', 'scene.json'), ('composition', 'index.html'), ('generation', 'generation.json'),
                        ('visual_review', 'visual_review.json'), ('qc', 'qc.json'), ('timeline', 'timeline_qc.json')]:
        href = _href(folder / name)
        if href:
            links[label] = href
    sources = [{'file': str(path.relative_to(ROOT)), 'href': _href(path), 'sha256': _sha(path)}
               for path in sorted(folder.rglob('*'))
               if path.is_file() and path.suffix in ('.html', '.js', '.css', '.svg')]
    comparison = _read(folder / 'comparacion_clone.json', warnings)
    comparison_current = bool(comparison and comparison.get('mp4_sha256') == hashes['mp4_sha256']
                              and comparison.get('source_fingerprint') == hashes['composition_sha256'])
    return {'id': job['id'], 'title': job.get('title', job['id']), 'script': job.get('script', ''),
            'folder': str(folder.relative_to(ROOT)), 'aesthetic_status': 'pendiente_usuario',
            'generation_status': generation.get('status', 'pendiente_plan'),
            'generation_reason': generation.get('reason'),
            'technical_status': technical_status, 'technical_current': technical_pass,
            'visual_agent_status': agent_status, 'visual_review_current': visual_current,
            'visual_review': review if visual_current else None,
            'comparison_current': comparison_current,
            'selected_families': families, 'families_observed_in_review': observed_families,
            'scenes': scenes, 'duration_s': qc.get('duration', spec.get('duration')),
            'frames': qc.get('frames'), 'current_sha': hashes,
            'links': links, 'editable_sources': sources,
            'limits': ['El QC técnico no aprueba estética.',
                       'Familias seleccionadas en SceneIR no equivalen a aparición visual verificada.',
                       'Comparaciones CLONE por fase son orientativas, sin equivalencia temporal literal.',
                       'Prueba conceptual sin talking head, narración original ni ejecución real de software.']}


def _card(record):
    esc = html.escape
    links = record['links']
    video = '<div class="placeholder">Render pendiente</div>'
    if 'video' in links:
        poster = ' poster="' + esc(links['poster'], quote=True) + '"' if 'poster' in links else ''
        video = '<video controls loop playsinline preload="none"' + poster + ' src="' + esc(links['video'], quote=True) + '"></video>'
    table = []
    for scene in record['scenes']:
        interval = f"{scene['start_s']:.2f}–{scene['end_s']:.2f}s" if scene['end_s'] is not None else 'pendiente'
        table.append('<tr><td>' + esc(interval) + '</td><td>' + esc(str(scene['family'])) + '</td><td>'
                     + esc(scene['objective']) + '</td><td>' + esc(scene['semantic_reason']) + '</td><td>'
                     + esc(scene['visual_reason']) + '</td></tr>')
    plan = ('<div class="table"><table><thead><tr><th>Tiempo</th><th>Familia</th><th>Objetivo</th>'
            '<th>Razón semántica</th><th>Razón visual</th></tr></thead><tbody>' + ''.join(table) + '</tbody></table></div>'
            if table else '<p>Plan de escenas pendiente.</p>')
    labels = {'video': 'MP4', 'poster': 'Fotograma nativo', 'plan': 'Plan de escenas',
              'comparison': 'Comparación con CLONE', 'scene_ir': 'SceneIR editable', 'composition': 'Composición editable',
              'generation': 'Registro de generación', 'visual_review': 'Revisión visual',
              'qc': 'QC técnico', 'timeline': 'Timeline'}
    anchors = ' · '.join('<a href="' + esc(href, quote=True) + '">' + labels[key] + '</a>'
                         for key, href in links.items() if key in labels)
    sources = ''.join('<li><a href="' + esc(item['href'], quote=True) + '">' + esc(item['file']) + '</a></li>'
                      for item in record['editable_sources'])
    return ('<article id="' + esc(record['id']) + '"><h2>' + esc(record['id'] + ' · ' + record['title'])
            + '</h2><p class="approval">Aprobación estética: pendiente del usuario</p>' + video
            + '<p><strong>Guion conceptual:</strong> ' + esc(record['script']) + '</p>'
            + '<p>Producción: ' + esc(record['generation_status']) + ' · Técnica: ' + esc(record['technical_status'])
            + ' · Revisión agente: ' + esc(record['visual_agent_status']) + '</p>'
            + '<p><strong>Familias del SceneIR:</strong> ' + esc(', '.join(record['selected_families']) or 'pendientes')
            + '</p><p><strong>Aparición verificada por agente:</strong> '
            + esc(', '.join(record['families_observed_in_review']) or 'pendiente') + '</p>'
            + '<p class="links">' + anchors + '</p><details><summary>Escenas y decisiones</summary>' + plan
            + '</details><details><summary>Fuentes editables</summary><ul>' + sources + '</ul></details>'
            + '<details><summary>Revisión, hashes y límites</summary><pre>'
            + esc(json.dumps({'sha': record['current_sha'], 'visual_review_current': record['visual_review_current'],
                             'visual_review': record['visual_review'], 'comparison_current': record['comparison_current'],
                             'limits': record['limits']}, ensure_ascii=False, indent=2)) + '</pre></details></article>')


def _atomic_write(path, content):
    temporary = path.with_name('.' + path.name + '.tmp')
    temporary.write_text(content)
    os.replace(temporary, path)


def generate():
    """Escribe galeria.html y resumen.json; ninguna producción ni promoción."""
    warnings = []
    brief = _read(BASE / 'briefs.json', warnings)
    supplied = {job.get('id'): job for job in brief.get('jobs', [])}
    jobs = [{**default, **supplied.get(default['id'], {})} for default in DEFAULT_JOBS]
    records = []
    for job in jobs:
        try:
            records.append(_record(job, warnings))
        except ValueError as exc:
            # Configuración incompleta: mostrar el fixture canónico sin abrir
            # rutas externas ni interrumpir los otros dos planes del lote.
            warnings.append({'job': job['id'], 'status': 'ruta_pendiente', 'reason': str(exc)})
            records.append(_record(next(j for j in DEFAULT_JOBS if j['id'] == job['id']), warnings))
    counts = {'jobs': len(records), 'renders_present': sum(bool(r['current_sha']['mp4_sha256']) for r in records),
              'technical_current': sum(r['technical_current'] for r in records),
              'visual_agent_current': sum(r['visual_review_current'] for r in records),
              'aesthetic_pending_user': len(records)}
    summary = {'schema_version': 1, 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope': brief.get('scope', 'Tres pruebas conceptuales del generador CLONE sin talking head.'),
               'aesthetic_status': 'pendiente_usuario', 'counts': counts, 'records': records, 'warnings': warnings}
    BASE.mkdir(parents=True, exist_ok=True)
    _atomic_write(BASE / 'resumen.json', json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    brief_link = ' · <a href="briefs.json">Guiones de las tres pruebas</a>' if (BASE / 'briefs.json').is_file() else ''
    page = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CLONE · Tres pruebas creativas</title>
<style>body{margin:28px;background:#f3f3f5;color:#19191b;font:16px system-ui,sans-serif;line-height:1.45}h1{font-size:32px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}article{background:white;border:1px solid #dedee1;border-radius:16px;padding:20px;min-width:0}h2{font-size:23px;margin:0}video,.placeholder{width:100%;max-height:560px;background:#19191b;border-radius:12px}.placeholder{height:360px;display:grid;place-items:center;color:white}a{color:#74412e}.approval{font-weight:650;color:#8a4b19}.links{font-size:14px}details{margin:16px 0}pre{font:12px ui-monospace,monospace;white-space:pre-wrap;overflow-wrap:anywhere;max-height:480px;overflow:auto}.table{overflow:auto}table{border-collapse:collapse;font-size:13px;min-width:800px}th,td{border:1px solid #ddd;padding:9px;text-align:left;vertical-align:top}button{padding:10px 16px;border:1px solid #777;border-radius:8px;background:white;margin:5px;cursor:pointer}.intro{max-width:1050px}ul{padding-left:20px;overflow-wrap:anywhere}@media(max-width:420px){body{margin:12px}main{grid-template-columns:1fr}}</style>
<body><h1>CLONE · Tres pruebas del generador creativo</h1><p class="intro">''' + html.escape(summary['scope']) + '''</p>
<p class="intro">Esta galería separa producción, QC técnico y revisión visual del agente. La aprobación estética de las tres pruebas permanece pendiente del usuario. Los archivos ausentes y las revisiones desactualizadas se muestran como pendientes.</p>
<p><a href="resumen.json">Resumen y hashes actuales</a>''' + brief_link + '''</p>
<p><button id="play">Reproducir las tres</button><button id="pause">Pausar</button></p><main>''' + ''.join(_card(r) for r in records) + '''</main>
<script>document.getElementById('play').onclick=()=>document.querySelectorAll('video').forEach(v=>{v.muted=true;v.play().catch(()=>{})});document.getElementById('pause').onclick=()=>document.querySelectorAll('video').forEach(v=>v.pause());</script></body></html>'''
    _atomic_write(BASE / 'galeria.html', page)
    return {'gallery': str((BASE / 'galeria.html').relative_to(ROOT)),
            'summary': str((BASE / 'resumen.json').relative_to(ROOT)), 'counts': counts, 'warnings': warnings}


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
