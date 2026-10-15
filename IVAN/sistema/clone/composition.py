"""Capacidades del compositor. No altera las 15 definiciones reconstruidas."""
import math

ACTORS = {
    'spotlight_agent': {'group': 'hero', 'asset': {'param': 'role', 'prefix': 'agent_'}},
    'feedback_bars': {'group': 'agent', 'asset': {'param': 'agent'}},
    'radial_research': {'group': 'agent', 'asset': {'param': 'agent'}},
    'phone_recon': {'group': 'agent', 'asset': {'param': 'agent'}},
    'phone_rebuild': {'group': 'worker', 'asset': {'param': 'agent'}},
    'phone_qa': {'group': 'agent', 'asset': {'param': 'agent'}},
    'problem_resolution': {'group': 'agent', 'asset': {'param': 'agent'}},
}
DEVICES = {'phone_recon', 'phone_rebuild', 'phone_qa', 'problem_resolution'}
LAYOUTS = {'feedback_bars': ['compact_stack'], 'spotlight_agent': ['centered_actor'],
           'phone_rebuild': ['centered_primary'], 'terminal_install': ['centered_primary']}

def capabilities(family):
    ports = []
    accepts = []
    if family in ACTORS:
        ports.append({'id': 'actor', 'kind': 'actor', 'asset': ACTORS[family]['asset'], 'identity_param': None})
        accepts += [{'kind': 'actor_pose_match', 'source_family': source, 'source_port': 'actor', 'target_port': 'actor',
                     'wrapper_kinds': ['cut', 'mask'], 'duration_range': [.2, .6], 'requires_same_framing': True}
                    for source in ACTORS]
    if family in DEVICES:
        ports.append({'id': 'device', 'kind': 'device', 'asset': {'literal': 'native:calendar_phone'}, 'identity_param': 'appName'})
        accepts += [{'kind': 'device_pose_match', 'source_family': source, 'source_port': 'device', 'target_port': 'device',
                     'wrapper_kinds': ['cut'], 'duration_range': [.2, .6], 'requires_same_framing': True}
                    for source in sorted(DEVICES)]
    return {'ports': ports, 'accepts': accepts}

def effective_asset(scene, port, definitions):
    family = definitions[scene['family']]
    params = {**family.get('defaults', {}), **scene.get('params', {})}
    rule = next((p for p in family.get('continuity', {}).get('ports', []) if p['id'] == port), None)
    if not rule:
        raise ValueError('Puerto de continuidad no disponible: ' + scene['family'] + '/' + port)
    asset = rule['asset']
    return asset.get('literal') or asset.get('prefix', '') + str(params.get(asset['param'], ''))

def validate_continuity(spec, definitions):
    scenes = spec['scenes']
    entities = {e['id'] for e in spec.get('semantic_analysis', {}).get('entities', [])}
    for index, scene in enumerate(scenes):
        continuity = scene.get('continuity')
        if continuity is None:
            continue
        if not index or not isinstance(continuity, dict) or set(continuity) != {'from_scene', 'reason', 'operations'}:
            raise ValueError('Continuidad requiere frontera anterior, motivo y operaciones')
        source = scenes[index - 1]
        if continuity['from_scene'] != source['id'] or not isinstance(continuity['reason'], str) or not continuity['reason'].strip():
            raise ValueError('Continuidad sin origen adyacente o motivo semántico')
        if abs(source['start'] + source['duration'] - scene['start']) > .001:
            raise ValueError('Continuidad exige escenas contiguas')
        operations = continuity['operations']
        if not isinstance(operations, list) or not 1 <= len(operations) <= 2:
            raise ValueError('Continuidad admite una o dos operaciones')
        ports_used = set()
        for op in operations:
            if not isinstance(op, dict) or set(op) != {'kind', 'source_port', 'target_port', 'asset', 'entity_ids', 'duration'}:
                raise ValueError('Operación de continuidad no tipada')
            duration = op['duration']
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or not .2 <= duration <= .6 or abs(duration * 30 - round(duration * 30)) > .001:
                raise ValueError('Continuidad debe durar0,2–0,6s alineados a30FPS')
            if duration > min(source['duration'], scene['duration']) / 3:
                raise ValueError('Continuidad no cabe en ambas escenas')
            pair = (op['source_port'], op['target_port'])
            if pair in ports_used:
                raise ValueError('Puerto animado dos veces en la frontera')
            ports_used.add(pair)
            ids = op['entity_ids']
            shared = scene.get('handoff', {}).get('shared_entity_ids', [])
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in entities or i not in shared for i in ids) or len(ids) != len(set(ids)):
                raise ValueError('Continuidad exige entidades reales compartidas por la narración')
            candidates = definitions[scene['family']].get('continuity', {}).get('accepts', [])
            allowed = next((a for a in candidates if a['kind'] == op['kind'] and a['source_family'] == source['family'] and a['source_port'] == op['source_port'] and a['target_port'] == op['target_port'] and scene['transition_in']['kind'] in a['wrapper_kinds']), None)
            if not allowed:
                raise ValueError('Par de continuidad no implementado: ' + source['family'] + '→' + scene['family'])
            if source.get('framing') != scene.get('framing'):
                raise ValueError('Continuidad requiere framing compatible')
            if op['asset'] != effective_asset(source, op['source_port'], definitions) or op['asset'] != effective_asset(scene, op['target_port'], definitions):
                raise ValueError('Recurso de continuidad no existe en ambas escenas')
            if op['kind'] == 'device_pose_match':
                if source.get('layout') or scene.get('layout') or source['params'].get('appName') != scene['params'].get('appName'):
                    raise ValueError('Device pose requiere identidad igual y coordenadas nativas sin layout')
    return spec

def validate_composition(scene):
    layout = scene.get('layout')
    if layout is not None:
        allowed = {'profile', 'gap_px', 'anchor_x', 'anchor_y', 'margin_px', 'body_px', 'secondary_px'}
        if not isinstance(layout, dict) or set(layout) - allowed or layout.get('profile') not in LAYOUTS.get(scene['family'], []):
            raise ValueError('Perfil/clave de composición no implementado')
        ranges = {'gap_px': (36, 144), 'anchor_x': (.33, .67), 'anchor_y': (.33, .67), 'margin_px': (72, 180), 'body_px': (48, 60), 'secondary_px': (30, 42)}
        for key, (lo, hi) in ranges.items():
            value = layout.get(key)
            if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not lo <= value <= hi):
                raise ValueError('Valor de composición fuera de límites: ' + key)
        if scene['family'] == 'feedback_bars' and len(scene['params'].get('reviews', [])) > 4:
            raise ValueError('Stack compacto admite hasta4observaciones; conservar carrusel para más')
    closing = scene.get('closing')
    if closing is not None:
        if scene['family'] != 'feedback_bars' or not isinstance(closing, dict) or set(closing) != {'kind', 'at', 'headline'} or closing['kind'] != 'coverage_conclusion':
            raise ValueError('Conclusión no implementada')
        at = closing['at']
        if not isinstance(at, (int, float)) or isinstance(at, bool) or not math.isfinite(at) or at < scene['duration'] * .6 or at > scene['duration'] - 1.2 or abs(at * 30 - round(at * 30)) > .001:
            raise ValueError('Conclusión requiere clasificación previa y1,2s de lectura')
        if closing['headline'] != 'Cobertura de respuestas' or 'calidad' not in scene['params'].get('caption', '').lower():
            raise ValueError('Conclusión de cobertura exige el límite semántico suministrado')
        if not layout or layout['profile'] != 'compact_stack':
            raise ValueError('Conclusión requiere distribución compacta verificada')

def bridges(scenes):
    result = []
    for index, incoming in enumerate(scenes):
        for op in (incoming.get('continuity') or {}).get('operations', []):
            if op['kind'] != 'actor_pose_match':
                continue
            outgoing = scenes[index - 1]
            half = op['duration'] / 2
            result.append({**op, 'id': incoming['id'] + '-actor-bridge', 'source_scene': outgoing['id'], 'target_scene': incoming['id'],
                           'source_group': ACTORS[outgoing['family']]['group'], 'target_group': ACTORS[incoming['family']]['group'],
                           'start': incoming['start'] - half, 'duration': op['duration'],
                           'source_local': outgoing['duration'] - half, 'target_local': half})
    return result
