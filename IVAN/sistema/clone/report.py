"""Galería única y registro de QC vinculados a los archivos actuales de IVAN.

generate() no renderiza, no promueve variantes y no modifica componentes.
La revisión visual solo se conserva cuando coinciden los SHA auditados.
"""
from __future__ import annotations

import collections
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
PROJECT = ROOT / 'proyectos/clone_motor'


def _load(path, default=None):
    if not path.is_file():
        return {} if default is None else default
    return json.loads(path.read_text())


def _sha(path):
    if not path.is_file():
        return None
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _relative(path):
    return str(path.resolve().relative_to(ROOT))


def _link(path):
    return quote(os.path.relpath(path, PROJECT), safe='/._-') if path.is_file() else None


def _engine():
    # engine.gallery() puede cargar este módulo bajo otro nombre. Importarlo
    # aquí no llama gallery ni cambia las fuentes: solo necesitamos su hash.
    loaded = sys.modules.get('engine')
    if loaded and pathlib.Path(loaded.__file__).resolve() == HERE / 'engine.py':
        return loaded
    spec = importlib.util.spec_from_file_location('clone_report_engine', HERE / 'engine.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reviews():
    records = []
    for name in ('qc_dispositivos', 'qc_agentes', 'qc_cancelled', 'qc_core',
                 'qc_graph', 'qc_demo', 'qc_equipo'):
        path = PROJECT / (name + '.json')
        data = _load(path)
        if not data:
            continue
        rows = data.get('records', data.get('components', [data]))
        for row in rows:
            ident = row.get('family', row.get('id', row.get('render', {}).get('id')))
            if ident == 'cancelled_adapter':
                ident = 'cancelled'
            if name == 'qc_demo':
                ident = 'demo_nueva'
            elif name == 'qc_equipo':
                ident = 'demo_equipo'
            elif name == 'qc_graph':
                ident = 'composition_graph'
            render = row.get('render', {})
            records.append({
                'id': ident,
                'file': _relative(path),
                'mp4_sha256': row.get('mp4_sha256', row.get('mp4_auditado_sha256', render.get('sha256'))),
                'html_sha256': row.get('html_sha256', row.get('html_auditado_sha256', render.get('html_sha256'))),
                'composition_sha256': row.get('composition_sha256', render.get('composition_sha256')),
                'record': row,
            })
    return records


def _record(folder, review_rows, engine, catalog):
    ident = folder.name
    spec = _load(folder / 'scene.json')
    qc = _load(folder / 'qc.json')
    timeline = _load(folder / 'timeline_qc.json')
    fingerprint_error = None
    try:
        fingerprint = engine.source_fingerprint(folder)['sha256']
    except (ValueError, OSError) as exc:
        fingerprint, fingerprint_error = None, str(exc)
    actual = {'mp4_sha256': _sha(folder / 'preview.mp4'),
              'html_sha256': _sha(folder / 'index.html'),
              'scene_sha256': _sha(folder / 'scene.json'),
              'composition_sha256': fingerprint}
    render_current = bool(actual['mp4_sha256'] and qc.get('mp4_sha256') == actual['mp4_sha256']
                          and qc.get('html_sha256') == actual['html_sha256'])
    if qc.get('source_sha256'):
        render_current = render_current and qc['source_sha256'] == fingerprint
    if qc.get('scene_sha256'):
        render_current = render_current and qc['scene_sha256'] == actual['scene_sha256']
    timeline_current = bool(timeline.get('ok') and timeline.get('html_sha256') == actual['html_sha256'])
    if timeline.get('source_sha256'):
        timeline_current = timeline_current and timeline['source_sha256'] == fingerprint
    technical = bool(render_current and timeline_current and qc.get('decoded_all_frames'))

    bound, obsolete = [], []
    for review in review_rows:
        if review['id'] != ident:
            continue
        valid = bool(review['mp4_sha256'] and review['mp4_sha256'] == actual['mp4_sha256'])
        if review['html_sha256']:
            valid = valid and review['html_sha256'] == actual['html_sha256']
        if review['composition_sha256']:
            valid = valid and review['composition_sha256'] == fingerprint
        (bound if valid else obsolete).append(review)

    style = _load(folder / 'style_review.json')
    style_current = bool(style and style.get('mp4_sha256') == actual['mp4_sha256']
                         and style.get('composition_sha256') == fingerprint)
    required = ('visual_consistency', 'motion', 'continuity', 'semantic_faithfulness', 'reuse')
    style_pass = bool(style_current and all(style.get('checks', {}).get(key) is True for key in required))
    visual = 'revision_visual_pendiente'
    if bound:
        row = bound[-1]['record']
        visual = row.get('status', row.get('estado', 'revisado_como_variante'))
    if style_pass:
        visual = 'variante_verificada_en_alcance'
    elif not bound and obsolete:
        visual = 'revision_visual_obsoleta'

    definition = catalog.get(ident, {})
    registered = _load(HERE / 'variantes.json').get(spec.get('id'), {})
    registry_current = bool(registered and registered.get('mp4_sha256') == actual['mp4_sha256']
                            and registered.get('composition_sha256') == fingerprint)
    comparison = _load(folder / 'comparison.json')
    comparison_current = bool(comparison and comparison.get('render_sha256') == actual['mp4_sha256']
                              and comparison.get('source_sha256') == _sha(ROOT / 'recursos/B2_CLONE.mp4'))
    links = {}
    for name, path in [('video', folder / 'preview.mp4'), ('poster', folder / 'poster.png'),
                       ('scene', folder / 'scene.json'), ('composition', folder / 'index.html'),
                       ('technical_qc', folder / 'qc.json'), ('timeline_qc', folder / 'timeline_qc.json'),
                       ('comparison', folder / 'comparison.png'), ('comparison_data', folder / 'comparison.json'),
                       ('style_review', folder / 'style_review.json')]:
        value = _link(path)
        if value:
            links[name] = value
    return {
        'id': ident, 'group': 'demo' if folder.parent == PROJECT else 'api' if ident == 'composition_graph' else 'library',
        'title': spec.get('scenes', [{}])[0].get('objective', definition.get('description', ident)),
        'folder': _relative(folder), 'current_sha': actual,
        'duration_s': qc.get('duration', spec.get('duration')), 'frames': qc.get('frames'), 'fps': qc.get('fps'),
        'technical': {'status': 'verificado_archivo_actual' if technical else 'pendiente_o_obsoleto',
                      'pass': technical, 'render_receipt_current': render_current,
                      'timeline_current': timeline_current, 'decoded_all_frames': bool(qc.get('decoded_all_frames')),
                      'hardware_gpu': bool(qc.get('hardware_gpu')), 'nvenc': bool(qc.get('nvenc')),
                      'source_fingerprint_error': fingerprint_error},
        'visual': {'status': visual, 'reviews_current': bound, 'reviews_obsolete': obsolete,
                   'style_review_current': style_current, 'style_checks_pass': style_pass,
                   'user_aesthetic_approval_claimed': False},
        'reference': definition.get('reference', []), 'parameters': definition.get('parameters', {}),
        'comparison_current': comparison_current,
        'variant_registry': {'current': registry_current, 'entry': registered,
                             'status': registered.get('status') if registry_current else 'ausente_o_obsoleto'},
        'links': links,
        'font_limit': 'Fuentes originales CLONE no identificadas; Inter, Sequel, Scholar y JetBrains son aproximaciones declaradas.',
        'style_review': style if style_current else None,
        'scene': spec,
    }


def _card(record):
    esc = html.escape
    ident, links = record['id'], record['links']
    video = ''
    if links.get('video'):
        poster = ' poster="' + esc(links['poster'], quote=True) + '"' if links.get('poster') else ''
        video = '<video controls loop playsinline preload="none"' + poster + ' src="' + esc(links['video'], quote=True) + '"></video>'
    names = {'video': 'MP4', 'poster': 'Fotograma nativo', 'scene': 'SceneIR editable',
             'composition': 'Composición', 'comparison': 'Comparación con CLONE',
             'technical_qc': 'QC técnico', 'timeline_qc': 'Timeline', 'style_review': 'Revisión editorial'}
    anchors = ' · '.join('<a href="' + esc(url, quote=True) + '">' + esc(names.get(key, key)) + '</a>'
                         for key, url in links.items() if key in names)
    review_links = ' · '.join('<a href="' + esc(_link(ROOT / item['file']), quote=True) + '">Informe visual</a>'
                              for item in record['visual']['reviews_current'])
    quality = 'Técnica: verificada' if record['technical']['pass'] else 'Técnica: pendiente'
    visual = record['visual']['status'].replace('_', ' ')
    raw = {'reference': record['reference'], 'parameters': record['parameters'],
           'visual': record['visual'], 'style_review': record['style_review'],
           'variant_registry': record['variant_registry'], 'comparison_current': record['comparison_current']}
    return ('<article data-group="' + record['group'] + '" data-pending="' + str(not record['visual']['reviews_current']).lower() + '">'
            '<h3>' + esc(ident.replace('_', ' ')) + '</h3><p class="objective">' + esc(record['title']) + '</p>'
            + video + '<p class="status">' + esc(quality) + ' · ' + esc(visual) + '</p>'
            '<p>' + esc(str(record['duration_s'])) + ' s · ' + esc(str(record['frames'])) + ' fotogramas</p>'
            '<p class="links">' + anchors + '</p><p>' + review_links + '</p>'
            '<details><summary>Evidencia, límites y parámetros</summary><p>' + esc(record['font_limit']) + '</p><pre>'
            + esc(json.dumps(raw, ensure_ascii=False, indent=2)) + '</pre></details>'
            '<p class="hash">MP4 ' + esc((record['current_sha']['mp4_sha256'] or 'ausente')[:16]) + '…</p></article>')


def generate():
    """Genera galería/registro únicos; devuelve rutas y conteos, sin renderizar."""
    engine = _engine()
    catalog = {item['id']: item for item in engine.catalog()}
    reviews = _reviews()
    folders = sorted(path.parent for path in (PROJECT / 'previews').glob('*/scene.json'))
    folders += sorted(path.parent for path in PROJECT.glob('demo*/scene.json'))
    records = [_record(folder, reviews, engine, catalog) for folder in folders]
    counts = {'total': len(records), 'library': sum(r['group'] == 'library' for r in records),
              'api': sum(r['group'] == 'api' for r in records), 'demos': sum(r['group'] == 'demo' for r in records),
              'technical_current': sum(r['technical']['pass'] for r in records),
              'visual_review_current': sum(bool(r['visual']['reviews_current']) for r in records),
              'style_verified_variants': sum(r['visual']['style_checks_pass'] for r in records),
              'registered_current_variants': sum(r['variant_registry']['current'] and r['variant_registry']['status'] == 'verified_in_reviewed_scope' for r in records),
              'obsolete_visual_reviews': sum(len(r['visual']['reviews_obsolete']) for r in records)}
    data = {'schema_version': 1, 'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope': '15 familias CLONE, API de composiciones y demostraciones nuevas. No es un reel ni aprobación estética del usuario.',
            'policy': 'SHA de MP4/HTML y composición cuando existe. Una revisión obsoleta no aprueba el archivo actual.',
            'counts': counts, 'font_approximations': _load(HERE / 'design-system.json').get('typography', {}),
            'records': records}
    PROJECT.mkdir(parents=True, exist_ok=True)
    (PROJECT / 'registro_componentes.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    sections = []
    for group, label in [('library', 'Biblioteca CLONE'), ('api', 'API de composiciones'), ('demo', 'Demostraciones con guion nuevo')]:
        rows = [r for r in records if r['group'] == group]
        sections.append('<section><h2>' + label + '</h2><main>' + ''.join(_card(row) for row in rows) + '</main></section>')
    content = '''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CLONE · Biblioteca y revisión</title>
<style>body{font:16px system-ui,sans-serif;background:#f3f3f5;color:#19191b;margin:28px;line-height:1.45}h1{font-size:32px}h2{margin-top:36px}h3{font-size:21px;margin:0}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:22px}article{background:white;border:1px solid #dfdfe2;border-radius:16px;padding:18px;min-width:0}video{width:100%;max-height:520px;background:#19191b;border-radius:12px}.status{font-weight:650}.objective{min-height:3em;font-size:14px}a{color:#74412e}.links{font-size:14px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:450px;overflow:auto;font:12px ui-monospace,monospace}.hash{color:#666;font:11px ui-monospace,monospace}button{padding:10px 16px;margin:4px;border:1px solid #777;border-radius:8px;background:white;cursor:pointer}nav{position:sticky;top:0;background:#f3f3f5ee;padding:8px 0;z-index:1}article[hidden]{display:none}.intro{max-width:1000px}.counts{font-weight:650}</style>
<body><h1>CLONE · Biblioteca de motion graphics</h1><p class="intro">Previews reales y composiciones editables. La validación técnica y la revisión visual se muestran por separado. Las familias adaptan el original a pantalla completa; las demostraciones aplican su lenguaje a nuevos conceptos. La fidelidad literal y la aprobación estética del usuario no se presuponen.</p>
<p class="counts">''' + html.escape(f"{counts['library']} familias · {counts['api']} API · {counts['demos']} demostraciones · {counts['technical_current']} QC técnicos vigentes · {counts['visual_review_current']} revisiones visuales vigentes") + '''</p><p><a href="registro_componentes.json">Registro completo y hashes</a> · <a href="../../sistema/clone/DESIGN_SYSTEM.md">Sistema de diseño y fuentes aproximadas</a> · <a href="../../sistema/clone/INVENTARIO_CLONE.md">Inventario de referencia</a></p>
<nav><button data-filter="all">Todo</button><button data-filter="library">Biblioteca</button><button data-filter="api">API</button><button data-filter="demo">Demostraciones</button><button id="play">Reproducir visibles</button><button id="pause">Pausar</button></nav>''' + ''.join(sections) + '''
<script>document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{document.querySelectorAll('article').forEach(a=>{a.hidden=b.dataset.filter!=='all'&&a.dataset.group!==b.dataset.filter;if(a.hidden)a.querySelector('video')?.pause()})});document.getElementById('play').onclick=()=>document.querySelectorAll('article:not([hidden]) video').forEach(v=>{v.muted=true;v.play().catch(()=>{})});document.getElementById('pause').onclick=()=>document.querySelectorAll('video').forEach(v=>v.pause());</script></body></html>'''
    (PROJECT / 'galeria.html').write_text(content)
    return {'gallery': _relative(PROJECT / 'galeria.html'),
            'registry': _relative(PROJECT / 'registro_componentes.json'), 'counts': counts}


if __name__ == '__main__':
    print(json.dumps(generate(), ensure_ascii=False, indent=2))
