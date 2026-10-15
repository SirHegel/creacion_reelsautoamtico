"""Observed brand rasters are explicit private references, never authored logos."""
import copy
import json
from PIL import Image, ImageChops, ImageDraw
import pytest

from studio import automation, brand_assets as brands, core, design, hyperframes, render, scene_ir
from studio import resource_review as reviews
from test_brand_assets import workspace_brand, registration
from test_resource_review import workspace, observed


def synthetic_brand_raster(path):
    """Generated test pixels, no genuine brand or privately sourced raster."""
    # Generated in this test: no real logo, private asset, download or permission.
    raster = Image.new('RGBA', (150, 48), (0, 0, 0, 0))
    painter = ImageDraw.Draw(raster)
    painter.rectangle((5, 5, 95, 42), fill='#35a78d')
    painter.ellipse((105, 8, 141, 42), fill='#182a46')
    raster.save(path)
    return core.digest(path)


@pytest.fixture
def brand_scene(workspace_brand):
    root = workspace_brand
    path = root / 'assets/images/registry_fixture.png'
    synthetic_brand_raster(path)
    logo = {'id': 'a_google_fixture', 'name': 'Synthetic registry raster fixture.png', 'kind': 'image',
            'path': 'assets/images/registry_fixture.png', 'sha256': core.digest(path), 'md5': core.digest(path, 'md5'),
            'size': path.stat().st_size, 'duration': 0., 'probe': {},
            'metadata': {'provenance': {'operation': 'uploaded_by_user'}},
            'verification': {'visual': False, 'audio': False, 'rights': 'supplied_by_user_unverified'}}
    raw = root / 'assets/video/source.mp4'
    raw.write_bytes(b'unit fixture source; not decoded, no ASR or real reel')
    source = {'id': 'a_raw_fixture', 'name': 'Unit source.mp4', 'kind': 'video', 'path': 'assets/video/source.mp4',
              'sha256': core.digest(raw), 'md5': core.digest(raw, 'md5'), 'size': raw.stat().st_size,
              'duration': 10., 'probe': {'streams': [{'codec_type': 'video', 'width': 360, 'height': 640},
                                                  {'codec_type': 'audio', 'index': 1}]}, 'metadata': {}, 'verification': {}}
    core.atomic_json('.estado/assets.json', [source, logo])
    prepared = reviews.prepare(logo['id'])
    reviews.record(logo['id'], observed(prepared,
        notes='Declaración sintética de test sobre dos formas geométricas generadas; no es un logo Google ni observación de una marca real.',
        content='Raster sintético150x48 con rectángulo y círculo sobre transparencia para probar integridad, identidad declarada y guardas.',
        rights_declaration='Fixture generado por el test, sin marca auténtica ni declaración de permisos sobre Google.'))
    logo = core.asset(logo['id'])
    record = brands.register(logo['id'], registration(logo, prepared,
        source_url='https://about.google/brand-resource-center/',
        observation='Mock de asociación de entidad para probar el registro: raster generado, no logo auténtico ni observación real de Google.'))
    project = {'id': 'p_private_brand_fixture', 'source': source['id'], 'assets': [source, logo],
               'settings': {'width': 360, 'height': 640, 'fps': 12, 'engine': 'native'},
               'style': {'name': core.POLICY['name'], 'hook_seconds': 4.5},
               'fonts': {}, 'transcript': {'words': [], 'segments': []}, 'audio': [], 'timeline': [],
               'review': {'status': 'approved'}, 'approved_export': {'path': 'historic.mp4'}, 'renders': []}
    document = {'schema': scene_ir.SCHEMA, 'representation': 'conceptual', 'duration': 2,
                'content': {'text': 'Google recibe una solicitud', 'entities': ['Google', 'solicitud']},
                'narrative_goal': 'Representar una solicitud dirigida a Google sin inventar una interfaz.',
                'family': 'problem_resolution', 'composition': {'background': '#101318'},
                'components': [{'id': 'google', 'type': 'media', 'asset_id': logo['id'], 'brand_entity': 'google',
                                'x': .1, 'y': .15, 'width': .8, 'height': .2},
                               {'id': 'packet', 'type': 'shape', 'shape': 'rect', 'x': .1, 'y': .55,
                                'width': .12, 'height': .08, 'color': '#24aa88'}],
                'actions': [{'target_id': 'google', 'time': 0, 'properties': {'x': .1}},
                            {'target_id': 'google', 'time': 2, 'properties': {'x': .15}},
                            {'target_id': 'packet', 'time': 0, 'properties': {'y': .55}},
                            {'target_id': 'packet', 'time': 2, 'properties': {'y': .4}}]}
    return root, project, document, record


def test_registered_observed_logo_compiles_without_false_original_author(brand_scene):
    root, project, document, record = brand_scene
    original = copy.deepcopy(project)
    files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = scene_ir.compile_scene_ir(project, document)
    assert project == original and files == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert result['timeline'][0]['motion_design']['elements'][0]['brand_entity'] == 'google'
    assert result['scene_ir']['document']['components'][0]['brand_entity'] == 'google'
    assert 'declaration_original' not in core.asset('a_google_fixture')['metadata']
    assert result['scene_ir']['rights_verified'] is False and result['scene_ir']['status'] == 'pending_qc'
    assert not result['review'] and 'approved_export' not in result
    assert record['current']['eligible_for_context'] is True and record['publication_approved'] is False
    assert brands.resolve(['google'], 'publication')['resolved'] == []


def test_compiled_brand_preserves_registered_fixture_pixels_and_seek_geometry(brand_scene):
    root, project, document, _ = brand_scene
    scene = scene_ir.compile_scene_ir(project, document)['timeline'][0]
    with Image.open(root / project['assets'][1]['path']) as original:
        original = original.convert('RGBA')
    frame = design.draw_design(scene, 0, (360, 640), {}, {project['assets'][1]['id']: original}, root=root)
    expected = Image.new('RGBA', frame.size, '#101318')
    tile = Image.new('RGBA', (288, 128)); resized = original.copy(); resized.thumbnail(tile.size)
    tile.alpha_composite(resized, ((tile.width-resized.width)//2, (tile.height-resized.height)//2))
    expected.alpha_composite(tile, (36, 96))
    assert ImageChops.difference(frame.crop((36, 96, 324, 224)), expected.crop((36, 96, 324, 224))).convert('RGB').getbbox() is None
    assert ImageChops.difference(frame.crop((36, 96, 324, 224)).convert('RGB'), Image.new('RGB', (288,128), '#101318')).getbbox()
    frame.save(root / '.estado/static_brand_fixture.png')
    later = design.draw_design(scene, 2-1e-6, (360, 640), {}, {project['assets'][1]['id']: original}, root=root)
    assert frame.tobytes() != later.tobytes()
    assert frame.tobytes() == design.draw_design(scene, 0, (360, 640), {}, {project['assets'][1]['id']: original}, root=root).tobytes()


@pytest.mark.parametrize('value', [None, True, {}, [], 'Google', 'unknown', '../google', 'https://google.com', ''])
def test_brand_entity_is_closed_literal_not_a_metadata_bypass(brand_scene, value):
    _, project, document, _ = brand_scene
    document['components'][0]['brand_entity'] = value
    with pytest.raises(core.StudioError):scene_ir.compile_scene_ir(project, document)


def test_planner_receives_actual_eligible_and_ineligible_brand_records(brand_scene):
    _, project, _, record = brand_scene
    context = automation.direction_context(project, {'words': [], 'segments': []}, {'samples': []}, 2, '', require_camera=False)
    registry = context['prompt']['brand_registry']
    assert registry['context'] == 'private_review' and registry['publication_approved'] is False
    row = next(a for a in context['prompt']['assets'] if a['id'] == 'a_google_fixture')
    assert row['brand_references'][0]['entity'] == 'google'
    assert row['brand_references'][0]['eligible_for_context'] is True
    assert row['brand_references'][0]['sha256'] == record['sha256']
    assert row['brand_references'][0]['source_verified'] is False
    assert row['brand_references'][0]['publication_approved'] is False


@pytest.mark.parametrize('field,value', [('brand_entity', 'claude'), ('asset_id', 'a_raw_fixture'),
    ('brand_entity', None), ('brand_entity', True)])
def test_runtime_manual_edits_cannot_change_brand_identity(brand_scene, field, value):
    root, project, document, _ = brand_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled['timeline'][0]['motion_design']['elements'][0][field] = value
    with pytest.raises(core.StudioError):core.validate_shape(compiled)
    with pytest.raises(render.RenderError):render._prepare(compiled, root, 2)


def test_registered_logo_cannot_remove_brand_field_even_with_author_claim(brand_scene):
    root, project, document, _ = brand_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    compiled['timeline'][0]['motion_design']['elements'][0].pop('brand_entity')
    item = core.asset('a_google_fixture')
    item['metadata']['declaration_original'] = {'kind': 'original_graphic', 'author': 'Not a verified author claim'}
    core.atomic_json('.estado/assets.json', [core.asset(project['source']), item])
    compiled['assets'][1] = item
    with pytest.raises(core.StudioError, match='brand_entity'):core.validate_shape(compiled)
    with pytest.raises(render.RenderError, match='brand_entity'):render._prepare(compiled, root, 2)
    document['components'][0].pop('brand_entity')
    project['assets'][1] = item
    with pytest.raises(core.StudioError, match='brand_entity'):scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize('mutation', ['source_bytes', 'review', 'registry', 'manual', 'cycle', 'source_lineage'])
def test_current_brand_proof_is_rechecked_before_save_and_native_hf_prepare(brand_scene, monkeypatch, mutation):
    root, project, document, _ = brand_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    assert core.validate_shape(compiled) is None
    if mutation == 'source_bytes':
        (root / project['assets'][1]['path']).write_bytes(b'changed source bytes')
    elif mutation == 'review':
        item = core.asset('a_google_fixture'); item['metadata']['resource_review']['notes'] = 'Changed after the sealed registry observation.'
        core.atomic_json('.estado/assets.json', [core.asset(project['source']), item]); compiled['assets'][1] = item
    elif mutation == 'registry':
        registry = core.read_json('.estado/brand_assets/registry.json', {})
        next(iter(registry['records'].values()))['sha256'] = '0' * 64
        core.atomic_json('.estado/brand_assets/registry.json', registry)
    elif mutation == 'manual':
        stamp = brands._fingerprints()
        monkeypatch.setattr(brands, '_fingerprints', lambda: {**stamp, 'manual': {'changed': True}})
    else:
        item = core.asset('a_google_fixture')
        item['metadata']['provenance'] = {'source_asset_id': item['id'] if mutation == 'cycle' else project['source']}
        core.atomic_json('.estado/assets.json', [core.asset(project['source']), item]); compiled['assets'][1] = item
    with pytest.raises(core.StudioError):core.validate_shape(compiled)
    with pytest.raises(render.RenderError):render._prepare(compiled, root, 2)


def test_unreviewed_registry_entry_is_in_context_with_omission_reason(brand_scene, monkeypatch):
    _, project, _, _ = brand_scene
    stamp = brands._fingerprints()
    monkeypatch.setattr(brands, '_fingerprints', lambda: {**stamp, 'manual': {'new_revision': 1}})
    context = automation.direction_context(project, {'words': [], 'segments': []}, {'samples': []}, 2, '', require_camera=False)
    row = next(a for a in context['prompt']['assets'] if a['id'] == 'a_google_fixture')['brand_references'][0]
    assert row['eligible_for_context'] is False and row['omission_reason']
    assert row['publication_approved'] is False
    assert 'brand_entity' in context['prompt']['contract']['brand_graphics']


def test_registry_update_invalidates_director_context_identity_without_mutating_asset_catalog(brand_scene):
    root, project, _, _ = brand_scene
    before = automation._library_identity()
    catalog_bytes = (root / '.estado/assets.json').read_bytes()
    item = core.asset('a_google_fixture')
    brands.register(item['id'], registration(item, None,
        observation='Second explicitly recorded private observation of the same Google multicolor wordmark.'))
    assert (root / '.estado/assets.json').read_bytes() == catalog_bytes
    assert automation._library_identity() != before


def test_imported_registry_claim_is_not_a_local_observation_or_usage_authority(brand_scene, monkeypatch):
    root, project, document, record = brand_scene
    compiled = scene_ir.compile_scene_ir(project, document)
    catalog = copy.deepcopy(core.assets())
    for item in catalog:
        if item['id'] == 'a_google_fixture':
            item['metadata'].update(brand_asset=copy.deepcopy(record), publication_approved=True, visual_reviewed=True)
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    monkeypatch.setattr(core, 'assets', lambda: pytest.fail('Pure import consulted global catalog'))
    assert scene_ir.validate_import_project(compiled, catalog) is None
    assert before == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('field,value', [('brand_record', {'current': {'eligible_for_context': True}}),
    ('source_verified', True), ('publication_approved', True), ('declaration_original', {'author': 'Google'})])
def test_sceneir_cannot_supply_registry_authority_or_rights_claim(brand_scene, field, value):
    _, project, document, _ = brand_scene
    document['components'][0][field] = value
    with pytest.raises(core.StudioError):scene_ir.compile_scene_ir(project, document)


@pytest.mark.parametrize('kind,suffix', [('video', '.mp4'), ('image', '.svg')])
def test_brand_reference_never_allows_video_or_svg_without_renderer(brand_scene, kind, suffix):
    _, project, document, _ = brand_scene
    item = core.asset('a_google_fixture'); item['kind'] = kind; item['path'] = 'assets/images/altered'+suffix
    core.atomic_json('.estado/assets.json', [core.asset(project['source']), item]); project['assets'][1] = item
    with pytest.raises(core.StudioError, match='raster'):scene_ir.compile_scene_ir(project, document)


def test_original_nonbrand_graphic_rule_is_retained(brand_scene):
    root, project, document, _ = brand_scene
    path = root / 'assets/images/original.png'; Image.new('RGBA', (24, 24), '#35a78d').save(path)
    item = {'id': 'a_original_fixture', 'name': 'Own original shape.png', 'path': 'assets/images/original.png',
            'kind': 'image', 'sha256': core.digest(path), 'md5': core.digest(path, 'md5'), 'size': path.stat().st_size,
            'duration': 0., 'probe': {}, 'metadata': {}, 'verification': {}}
    core.atomic_json('.estado/assets.json', core.assets()+[item]);project['assets'].append(copy.deepcopy(item))
    document['components'][0].update(asset_id=item['id']); document['components'][0].pop('brand_entity')
    with pytest.raises(core.StudioError, match='gráfico original'):scene_ir.compile_scene_ir(project, document)
    item['metadata']['declaration_original'] = {'kind': 'original_graphic', 'author': 'Fixture author declaration only'}
    core.atomic_json('.estado/assets.json', [a if a['id'] != item['id'] else item for a in core.assets()]);project['assets'][-1] = item
    result = scene_ir.compile_scene_ir(project, document)
    assert result['scene_ir']['rights_verified'] is False
    assert result['timeline'][0]['motion_design']['elements'][0]['asset_id'] == item['id']


def test_multiscene_director_can_select_registry_logo_without_author_forgery(brand_scene):
    _, project, document, _ = brand_scene
    document['actions'].append({'target_id': 'packet', 'time': 1, 'properties': {'y': .45}})
    row = {'id': 's_brand', 'start': 0, 'end': 2, 'type': 'motion', 'narration': 'Google recibe una solicitud',
           'reason': 'El logo representa a Google explícitamente mencionado, no una interfaz o resultado inventado.',
           'family': 'problem_resolution', 'fact_ids': [], 'scene_ir': document,
           'alternatives': [{'family': 'composition_graph', 'reason': 'No hacen falta relaciones adicionales.'}],
           'phases': {'entry': 'entra solicitud', 'action': 'va hacia Google', 'reaction': 'se recibe',
                      'transformation': 'cambia su posición', 'exit': 'termina la transferencia'}}
    plan = {'schema': automation.SCHEMA, 'narrative_goal': row['reason'], 'summary': row['reason'], 'facts': [], 'scenes': [row]}
    transcript = {'words': [], 'segments': [{'start': 0, 'end': 2, 'text': row['narration']}]}
    result = automation.validate_chunk_plan(project, plan, transcript, 2)
    assert result['timeline'][0]['motion_design']['elements'][0]['brand_entity'] == 'google'
    assert result['timeline'][0]['scene_ir_origin']['document']['components'][0]['brand_entity'] == 'google'
    assert 'declaration_original' not in result['assets'][1]['metadata']
    assert not result['review']


def test_native_and_hyperframes_reject_revoked_registry_before_pixels_or_processes(brand_scene, monkeypatch):
    root, project, document, _ = brand_scene
    result = scene_ir.compile_scene_ir(project, document)
    stamp = brands._fingerprints()
    monkeypatch.setattr(brands, '_fingerprints', lambda: {**stamp, 'manual': {'changed': True}})
    monkeypatch.setattr(render, 'probe_media', lambda *a, **k: pytest.fail('Decoded after brand revocation'))
    target = root / '.estado/hyperframes/revoked'
    with pytest.raises(render.RenderError):hyperframes.build(result, root, target, seconds=2)
    assert not target.exists()


@pytest.mark.parametrize('channel', ['overlay', 'scene', 'transition'])
def test_registered_brand_cannot_evade_guard_through_secondary_scene_channel(brand_scene, channel):
    _, project, document, _ = brand_scene
    result = scene_ir.compile_scene_ir(project, document)
    scene = result['timeline'][0]
    scene['motion_design']['elements'] = [scene['motion_design']['elements'][1]]
    if channel == 'overlay':
        scene['overlays'] = [{'id': 'bypass', 'asset_id': 'a_google_fixture', 'start': 0, 'end': 2}]
    else:
        scene['asset_id' if channel == 'scene' else 'transition_asset_id'] = 'a_google_fixture'
    with pytest.raises(core.StudioError, match='marca registrada'):scene_ir.validate_brand_media(result)


def test_unattached_and_forged_asset_hash_cannot_acquire_brand_eligibility(brand_scene):
    _, project, document, _ = brand_scene
    result = scene_ir.compile_scene_ir(project, document)
    result['assets'][1]['sha256'] = '0' * 64
    with pytest.raises(core.StudioError, match='registro canónico'):scene_ir.validate_brand_media(result)
    result['assets'].pop()
    with pytest.raises(core.StudioError, match='adjunto'):scene_ir.validate_brand_media(result)


def test_same_brand_asset_requires_entity_on_each_visual_reference(brand_scene):
    _, project, document, _ = brand_scene
    duplicate = copy.deepcopy(document['components'][0]);duplicate['id'] = 'duplicate';duplicate.pop('brand_entity')
    document['components'].append(duplicate)
    with pytest.raises(core.StudioError, match='brand_entity'):scene_ir.compile_scene_ir(project, document)


def test_schema_announces_brand_enum_and_private_permission_boundary():
    schema = scene_ir.describe_schema()
    media = next(v for v in schema['properties']['components']['items']['oneOf'] if v['properties']['type']['const'] == 'media')
    assert set(media['properties']['brand_entity']['enum']) == set(brands.ORIGINS)
    assert 'private_review' in media['properties']['brand_entity']['description']
    assert 'publication' in media['properties']['brand_entity']['description']
    assert media['additionalProperties'] is False


@pytest.mark.parametrize('asset_id',['a_still.png','lámina.área 01.webp','imagen_🔎.png'])
@pytest.mark.parametrize('channel',['overlay','scene','transition'])
def test_brand_guard_preserves_canonical_nonbrand_legacy_ids_with_dots_and_unicode(brand_scene,asset_id,channel):
    root, project, document, _ = brand_scene
    result = scene_ir.compile_scene_ir(project,document)
    path = root/'assets/images/legacy.png';Image.new('RGBA',(16,24),'green').save(path)
    item={'id':asset_id,'kind':'image','name':'Legacy nonbrand.png','path':'assets/images/legacy.png',
          'sha256':core.digest(path),'md5':core.digest(path,'md5'),'size':path.stat().st_size,
          'duration':0,'probe':{},'metadata':{},'verification':{}}
    core.atomic_json('.estado/assets.json',core.assets()+[item]);result['assets'].append(item)
    scene=result['timeline'][0]
    if channel=='overlay':scene['overlays']=[{'id':'legacy','asset_id':asset_id,'start':0,'end':2}]
    else:scene['asset_id' if channel=='scene' else 'transition_asset_id']=asset_id
    assert scene_ir.validate_brand_media(result) is None


@pytest.mark.parametrize('value',[True,17,{},[]])
def test_brand_guard_nonbrand_secondary_ids_still_require_strings(brand_scene,value):
    _,project,document,_=brand_scene
    result=scene_ir.compile_scene_ir(project,document)
    result['timeline'][0]['overlays']=[{'id':'invalid','asset_id':value}]
    if value in ({},[]):
        # Empty/unset references are delegated to the renderer's media checks.
        assert scene_ir.validate_brand_media(result) is None
    else:
        with pytest.raises(core.StudioError):scene_ir.validate_brand_media(result)

