"""Actual ZIP brands reopen editable; portable claims cannot enable rendering."""
import copy
import json
import shutil

from PIL import Image
import pytest

from studio import branding, bundles, core, hyperframes, jobs, render, scene_ir
from studio import brand_assets as brands, resource_review as reviews
from test_api import api_workspace, fixture_media
from test_brand_bundles import workspaces, rewrite, incoming
from test_brand_assets import registration
from test_resource_review import observed
from test_scene_ir_brand_assets import synthetic_brand_raster


def observe_logo(asset_id):
    prepared = reviews.prepare(asset_id)
    reviews.record(asset_id, observed(prepared,
        notes='Declaración mock sobre raster generado para probar registro portable; no es un logo Google ni observación de marca real.',
        content='Dos formas geométricas generadas150x48 sobre transparencia, usadas exclusivamente como fixture de integridad.'))
    item = core.asset(asset_id)
    return brands.register(asset_id, registration(item, prepared,
        observation='Asociación de entidad declarada por fixture sintético para probar controles; no afirma logo auténtico o derechos comerciales.'))


@pytest.fixture
def portable_brand(workspaces, fixture_media):
    original = workspaces('original')
    raw = original / '.estado/tmp/raw.mp4'; shutil.copyfile(fixture_media, raw)
    source = core.register_asset(raw)
    logo_file = original / '.estado/tmp/registry_fixture.png'
    synthetic_brand_raster(logo_file)
    logo = core.register_asset(logo_file, kind='image')
    observe_logo(logo['id'])
    project = core.create_project('Isolated portable observed brand fixture', source['id'])
    project['settings'].update(width=360, height=640, fps=12)
    project['assets'].append(logo)
    document = {'schema':scene_ir.SCHEMA,'representation':'conceptual','family':'problem_resolution','duration':2,
        'narrative_goal':'La solicitud se dirige a Google explícito; no recrea una interfaz ni afirma resultados.',
        'content':{'text':'Solicitud dirigida a Google'},'composition':{'background':'#101318'},
        'components':[{'id':'logo','type':'media','asset_id':logo['id'],'brand_entity':'google',
                       'x':.1,'y':.15,'width':.8,'height':.2},
                      {'id':'input','type':'shape','x':.1,'y':.5,'width':.1,'height':.1}],
        'actions':[{'target_id':'logo','time':2,'properties':{'x':.15}}]}
    project = scene_ir.compile_scene_ir(project, document)
    project = core.save_project(project['id'], project, action='scene_ir_compiled')
    zipped = original / jobs.export_bundle(project['id'])['path']
    return workspaces, original, project, zipped


def reopen(value, *, change=None):
    activate, old_root, old, zipped = value
    if change:
        zipped = rewrite(old_root, zipped, change)
    new = activate('reopened')
    result = bundles.import_bundle(incoming(new, zipped))
    return new, result['project'], result


def test_brand_zip_roundtrip_is_editable_with_pending_local_observation(portable_brand):
    root, project, result = reopen(portable_brand)
    assert result['reused'] is False and project['pending_brand_references']['status'] == 'pending_local_observation'
    assert project['brand_references_state']['local_observation_pending'] is True
    element = project['timeline'][0]['motion_design']['elements'][0]
    assert element['brand_entity'] == 'google' and element['asset_id'] in {a['id'] for a in core.assets()}
    assert project['scene_ir']['document']['components'][0]['asset_id'] == element['asset_id']
    assert core.asset(element['asset_id'])['sha256'] == next(a['sha256'] for a in project['assets'] if a['id'] == element['asset_id'])
    assert 'declaration_original' not in core.asset(element['asset_id'])['metadata']
    assert brands.catalog()['records'] == []
    assert not project['review'] and not project.get('approved_export') and not project.get('full_authorization')
    assert project['pending_brand_references']['publication_approved'] is False
    assert scene_ir.validate_editable_component(project) is None and core.validate_shape(project) is None
    assert core.validate_project(project)['valid'] is False
    with pytest.raises(core.StudioError):scene_ir.compile_scene_ir(project, project['scene_ir']['document'])
    with pytest.raises(render.RenderError):render._prepare(project, root, 2)
    with pytest.raises(render.RenderError):hyperframes.build(project, root, root/'.estado/hyperframes/blocked', seconds=2)
    with pytest.raises(core.StudioError):jobs.submit(project['id'], 'render', {'seconds':2, 'technical':True})
    editable = copy.deepcopy(project);editable['timeline'][0]['motion_design']['elements'][1]['x'] = .25
    saved = core.save_project(project['id'], editable, expected=project['revision'])
    assert saved['timeline'][0]['motion_design']['elements'][1]['x'] == .25
    assert saved['pending_brand_references'] == project['pending_brand_references']
    # Re-export/reopen a pending draft retains media and creates its own proof,
    # rather than accepting the prior workspace's pending marker as authority.
    pending_zip = root / jobs.export_bundle(saved['id'])['path']
    third = portable_brand[0]('third')
    third_result = bundles.import_bundle(incoming(third, pending_zip))['project']
    assert third_result['pending_brand_references']['record_sha256'] != project['pending_brand_references']['record_sha256']
    assert not core.validate_project(third_result)['valid'] and brands.catalog()['records'] == []


def test_observation_in_new_workspace_unlocks_real_prepare_without_publication_permission(portable_brand):
    root, project, _ = reopen(portable_brand)
    aid = project['timeline'][0]['motion_design']['elements'][0]['asset_id']
    registration_result = observe_logo(aid)
    assert scene_ir.validate_brand_media(project) is None
    assert scene_ir.validate_compiled_project(project) is None
    live = core.get_project(project['id'])
    assert live['brand_references_state']['local_observation_pending'] is False
    assert live['brand_references_state']['publication_approved'] is False
    cfg = render._prepare(project, root, 2)
    assert cfg['source']['id'] == project['source'] and cfg['duration'] == 2
    media = cfg['scenes'][0]['_design_media'][0]
    assert media['_static_image'] is True and cfg['assets'][media['asset_id']]['sha256'] == next(a['sha256'] for a in project['assets'] if a['id'] == aid)
    assert registration_result['publication_approved'] is False and registration_result['rights_authority'] is False
    assert brands.resolve(['google'],'publication')['resolved'] == []
    assert not project['review']


@pytest.mark.parametrize('change', ['fake_registry','fake_author','fake_pending','mode_reel'])
def test_zip_claims_never_enable_render_even_when_import_succeeds(portable_brand, change):
    def mutate(p):
        media = p['timeline'][0]['motion_design']['elements'][0]
        item = next(a for a in p['assets'] if a['id'] == media['asset_id'])
        if change == 'fake_registry':
            item['metadata']['brand_asset'] = {'entity':'google','current':{'eligible_for_context':True},'publication_approved':True}
            item['verification']['visual'] = True
        elif change == 'fake_author':
            item['metadata']['declaration_original'] = {'kind':'original_graphic','author':'Google imaginary author'}
        elif change == 'fake_pending':
            p['pending_brand_references'] = {'schema':'ascendia.pending-brand-import/1','record_sha256':'0'*64,
                'status':'approved','publication_approved':True,'editorial_approved':True}
        else:
            p['mode'] = 'reel';p.pop('scene_ir')
    root, project, _ = reopen(portable_brand, change=mutate)
    assert project['pending_brand_references']['status'] == 'pending_local_observation'
    assert project['pending_brand_references']['publication_approved'] is False
    with pytest.raises(render.RenderError):render._prepare(project, root, 2)
    assert brands.catalog()['records'] == []
    assert 'declaration_original' not in core.asset(project['timeline'][0]['motion_design']['elements'][0]['asset_id'])['metadata']


@pytest.mark.parametrize('change', ['remove','forged','mode','remove_entity','unregistered_entity'])
def test_put_cannot_forge_or_remove_import_authority(portable_brand, change):
    root, project, _ = reopen(portable_brand)
    proposed = copy.deepcopy(project)
    if change == 'remove':proposed.pop('pending_brand_references')
    elif change == 'forged':proposed['pending_brand_references']['record_sha256'] = '0'*64
    elif change == 'mode':proposed['mode'] = 'reel'
    elif change == 'remove_entity':proposed['timeline'][0]['motion_design']['elements'][0].pop('brand_entity')
    else:proposed['timeline'][0]['motion_design']['elements'][0]['brand_entity'] = 'claude'
    if change in {'remove_entity','unregistered_entity'}:
        with pytest.raises(core.StudioError):core.save_project(project['id'], proposed, expected=project['revision'])
        saved = core.get_project(project['id'])
    else:
        saved = core.save_project(project['id'], proposed, expected=project['revision'])
    assert saved['pending_brand_references'] == project['pending_brand_references']
    assert saved['mode'] == 'scene_ir_component'
    with pytest.raises(render.RenderError):render._prepare(saved, root, 2)


@pytest.mark.parametrize('mutation', ['missing','bytes','symlink'])
def test_private_pending_proof_is_required_for_editing_and_never_overwritten(portable_brand, mutation):
    root, project, _ = reopen(portable_brand)
    path = scene_ir._pending_path(project['id']);original = path.read_bytes()
    if mutation == 'missing':path.unlink()
    elif mutation == 'bytes':path.write_bytes(b'{}')
    else:
        target = path.with_name('target.json');target.write_bytes(original);path.unlink();path.symlink_to(target)
    with pytest.raises(core.StudioError):core.validate_shape(project)
    with pytest.raises(render.RenderError):render._prepare(project, root, 2)
    if mutation == 'symlink':assert target.read_bytes() == original


def test_pure_zip_brand_validation_rejects_source_derivative_before_registration(portable_brand, monkeypatch):
    def mutate(p):
        aid = p['timeline'][0]['motion_design']['elements'][0]['asset_id']
        item = next(a for a in p['assets'] if a['id'] == aid)
        item['metadata']['provenance'] = {'source_asset_id':p['source']}
    activate, old_root, _, zipped = portable_brand
    bad = rewrite(old_root, zipped, mutate)
    new = activate('rejected')
    before = core.assets()
    monkeypatch.setattr(core,'register_asset',lambda *a,**k:pytest.fail('Unsafe staging reached registration'))
    with pytest.raises(core.StudioError,match='derivad'):bundles.import_bundle(incoming(new,bad))
    assert core.assets() == before and not core.project_list()


def test_same_source_reopen_preserves_user_edits_and_private_pending_proof(portable_brand):
    root, project, _ = reopen(portable_brand)
    editable = copy.deepcopy(project);editable['timeline'][0]['motion_design']['elements'][1]['x'] = .3
    saved = core.save_project(project['id'],editable,expected=project['revision'])
    proof = scene_ir._pending_path(project['id']);proof_bytes = proof.read_bytes()
    bundle = root/jobs.export_bundle(saved['id'])['path']
    second = bundles.import_bundle(bundle)
    assert second['reused'] is True and second['project'] == saved
    assert proof.read_bytes() == proof_bytes


def test_client_computed_status_is_ignored_and_recomputed(portable_brand):
    _, project, _ = reopen(portable_brand)
    project['brand_references_state'] = {'local_observation_pending':False,'publication_approved':True}
    saved = core.save_project(project['id'],project,expected=project['revision'])
    assert saved['brand_references_state']['local_observation_pending'] is True
    assert saved['brand_references_state']['publication_approved'] is False


@pytest.mark.parametrize('after_save',[False,True])
def test_failed_import_removes_own_pending_proof_and_restores_empty_new_project(portable_brand,monkeypatch,after_save):
    activate, _, _, zipped = portable_brand
    root = activate('failed_import');original_save = core.save_project;captured = {}
    def fail(pid,value,**kwargs):
        if kwargs.get('action') == 'branding_bundle_imported':
            captured['id'] = pid
            if after_save:original_save(pid,value,**kwargs)
            raise core.StudioError('Private import CAS failure',409)
        return original_save(pid,value,**kwargs)
    monkeypatch.setattr(core,'save_project',fail)
    with pytest.raises(core.StudioError,match='CAS failure'):bundles.import_bundle(incoming(root,zipped))
    assert not scene_ir._pending_path(captured['id']).exists()
    assert not core.get_project(captured['id']).get('pending_brand_references')

