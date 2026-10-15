"""Guardas CPU de producción completa; fixtures, sin inferencia ni render."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import integration_planner as ip
import integration as adapter
from test_integration_planner import fixture,SPEC,NARR

CONSTRAINTS={'profile':'production_complete','camera_mode':'split_first','split_top':.5}

def production_fixture():
    raw=fixture();raw.update(profile='production_complete',camera_mode='split_first',split_top=.5,
        camera_budget_reason='Identidad reconocible durante el inicio y condición, con apariciones breves según el significado.')
    raw['camera_windows']=[{'start_frame':0,'end_frame':60,'state':'split','transition_frames':0,'exit_frames':12,'anchor_indices':list(range(7)),
        'reason':'El rostro aparece en split desde cero con espacio para la explicación superior.'},
        {'start_frame':175,'end_frame':212,'state':'full','transition_frames':12,'exit_frames':12,'anchor_indices':[17,18,19,20,21],
        'reason':'La condición económica requiere confianza personal y salida suave dentro de su aparición.'}]
    raw['caption_blocks'][2]['placement']='under_chin'
    return raw

class ProductionIntegrationContracts(unittest.TestCase):
    def test_complete_profile_smooth_transitions_do_not_modify_scene_or_voice(self):
        raw=production_fixture();before=copy.deepcopy((raw,SPEC,NARR));protected=ip.protected_sources()
        result=ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        self.assertEqual((raw,SPEC,NARR),before);self.assertEqual(ip.protected_sources(),protected)
        self.assertEqual(result['frames'],237);self.assertEqual(result['profile'],'production_complete')
        self.assertEqual(result['camera_windows'][1]['transition_frames'],12)
        self.assertFalse(result['execution_verified']);self.assertEqual(ip.validate_plan(result,SPEC,NARR)['frames'],237)
    def test_legacy_still_rejects_production_transition_length(self):
        raw=fixture();raw['camera_windows'][1]['transition_frames']=12
        with self.assertRaisesRegex(ip.IntegrationError,'legacy'):ip.normalize(raw,SPEC,NARR)
    def test_per_window_ratio_changes_require_real_framing_reason(self):
        raw=production_fixture();raw['camera_windows'][1].update(state='split',split_top=.55)
        with self.assertRaisesRegex(ip.IntegrationError,'motivo concreto'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        raw['camera_windows'][1]['split_ratio_reason']='La altura superior conserva la interfaz mientras la cámara mantiene frente y barbilla visibles.'
        result=ip.normalize(raw,SPEC,NARR,CONSTRAINTS);self.assertEqual(result['camera_windows'][1]['split_top'],.55)
        raw['camera_windows'][1]['state']='full'
        with self.assertRaisesRegex(ip.IntegrationError,'sólo corresponde'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
    def test_no_extra_face_time_by_long_exit_or_pose_reset(self):
        raw=production_fixture();raw['camera_windows'][0]['end_frame']=91
        with self.assertRaisesRegex(ip.IntegrationError,'3s continuos'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        raw=production_fixture();raw['camera_windows'][1]['exit_frames']=19
        with self.assertRaises(ip.IntegrationError):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        raw=production_fixture();raw['camera_windows'][1]['transition_frames']=8
        with self.assertRaisesRegex(ip.IntegrationError,'9–18'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
    def test_initial_spoken_identity_has_no_empty_graphical_delay(self):
        raw=production_fixture();raw['hook_blocks'][0]['start_frame']=1
        with self.assertRaisesRegex(ip.IntegrationError,'frame0'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
    def test_profile_is_explicit_no_prefix_and_no_paid_fallback(self):
        for c in ({'profile':'unknown'},{'profile':[]},{'profile':'production_complete','scope_end_frame':108}):
            with self.subTest(c=c),self.assertRaises(ip.IntegrationError):ip.constraint_contract(c)
        raw=production_fixture();raw['profile']='legacy'
        with self.assertRaisesRegex(ip.IntegrationError,'perfil explícito'):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        prompt=ip.make_prompt(SPEC,NARR,'STYLE_YO',constraints=CONSTRAINTS)
        self.assertIn('transición9–18frames',prompt);self.assertNotIn('transición4–10frames',prompt)
        self.assertIn('no imponer variedad',prompt);self.assertIn('family_layout_capabilities',prompt)
    def test_camera_schema_allows24_without_a_quota_and_provider_remains_strict(self):
        schema=ip.p.strict_provider_schema(ip.SCHEMA)
        self.assertEqual(schema['properties']['camera_windows']['maxItems'],24)
        window=schema['properties']['camera_windows']['items']
        self.assertEqual(set(window['properties']),set(window['required']))
        self.assertEqual(ip.normalize(fixture(),SPEC,NARR)['profile'],'legacy')
    def test_impossible_clock_is_rejected_before_gpu(self):
        raw=production_fixture();raw['phase_cues'][0]['anchor_index']=1
        # Holding native0 until a later word is legitimate and monotonic.
        ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
        raw['phase_cues'][1]['anchor_index']=1
        with self.assertRaises(ip.IntegrationError):ip.normalize(raw,SPEC,NARR,CONSTRAINTS)
    def test_crop_uses_source_anatomy_and_uniform_scale(self):
        face={'original':{'width':1080,'height':1920},'anchors':[{'t':t,'source_normalized':{'bbox':[.35,.30,.65,.50],'chin':[.5,.5]}}for t in (0,.1,.2,1,2)]}
        direction={'split_top':.5,'camera_windows':[{'state':'split','start_frame':0,'end_frame':60}]}
        first=adapter.production_camera_poses(face,direction,1533)[0]
        self.assertEqual(first['scale'],1);self.assertNotEqual(first['crop_source'][1],315)
        self.assertLessEqual(first['crop_source'][1],.30*1920-48)
        self.assertGreaterEqual(first['crop_source'][1]+first['crop_source'][3],.5*1920+120)
        face['anchors'][0]['source_normalized']['bbox'][1]=-.1
        with self.assertRaisesRegex(ValueError,'normalizados'):adapter.production_camera_poses(face,direction,1533)
    def test_missing_bbox_and_distorted_source_do_not_get_fixed_old_crop(self):
        face={'original':{'width':1920,'height':1080},'anchors':[{'t':0}]}
        direction={'split_top':.5,'camera_windows':[{'state':'split','start_frame':0,'end_frame':60}]}
        with self.assertRaisesRegex(ValueError,'no deformar'):adapter.production_camera_poses(face,direction,1533)
        face['original'].update(width=1080,height=1920)
        with self.assertRaisesRegex(ValueError,'BBox'):adapter.production_camera_poses(face,direction,1533)
    def test_optional_camera_framing_is_uniform_bounded_and_centers_measured_face(self):
        face={'original':{'width':1080,'height':1920},'anchors':[{'t':t,'source_normalized':{'bbox':[.42,.32,.62,.50],'chin':[.52,.5]}}for t in (0,.1,.2,1,2)]}
        direction={'split_top':.5,'camera_windows':[{'state':'split','start_frame':0,'end_frame':60}]}
        config={'target_face_width_px':300,'max_scale':1.5,'reason':'Identidad centrada y visible sobre el rostro medido del crudo.'}
        before=copy.deepcopy((face,direction,config))
        pose=adapter.production_camera_poses(face,direction,1533,config)[0]
        self.assertEqual((face,direction,config),before)
        self.assertAlmostEqual(pose['scale'],300/216);self.assertEqual(pose['displayed_face_width_px'],300)
        self.assertAlmostEqual(((.42+.62)/2)*1080*pose['scale']+pose['x'],540)
        self.assertAlmostEqual(pose['crop_source'][2]*pose['scale'],1080)
        self.assertAlmostEqual(pose['crop_source'][3]*pose['scale'],960)
        self.assertLessEqual(pose['crop_source'][1],.32*1920-48/pose['scale'])
        self.assertGreaterEqual(pose['crop_source'][1]+pose['crop_source'][3],.5*1920+120/pose['scale'])
        config['max_scale']=1.2
        self.assertAlmostEqual(adapter.production_camera_poses(face,direction,1533,config)[0]['scale'],1.2)
        config['max_scale']=True
        with self.assertRaisesRegex(ValueError,'escala segura'):adapter.production_camera_poses(face,direction,1533,config)
    def test_functional_pixel_override_preserves_native_plan_and_rejects_new_roles(self):
        spec={'scenes':[{'id':'observer','family':'pixel_agents','params':{'roles':[{'role':'recon','label':'Observa tu trabajo'},{'role':'architect','label':'Aprende tu estilo'},{'role':'diff','label':'Mejora con el tiempo'}]}}]}
        item={'scene_id':'observer','kind':'pixel_functional_roles','hide_count':True,'labels':['Observa','Aprende','Mejora'],
            'reason':'Son funciones narradas de un único plugin, no tres agentes independientes.'}
        project={'revision':'production','instance_overrides':[item]};before=copy.deepcopy((project,spec))
        result=adapter.validated_instance_overrides(project,spec,NARR)
        self.assertEqual(result,[item]);self.assertEqual((project,spec),before)
        result[0]['labels'][0]='Changed';self.assertEqual(project['instance_overrides'][0]['labels'][0],'Observa')
        item['labels'][0]='Genera ingresos'
        with self.assertRaisesRegex(ValueError,'no sustentado'):adapter.validated_instance_overrides(project,spec,NARR)
        item['labels'][0]='Observa';project['revision']='V2'
        with self.assertRaisesRegex(ValueError,'legacy'):adapter.validated_instance_overrides(project,spec,NARR)
        project['revision']='production';spec['scenes'][0]['family']='spotlight_agent'
        with self.assertRaisesRegex(ValueError,'pixel_agents'):adapter.validated_instance_overrides(project,spec,NARR)
        self.assertEqual(adapter.validated_instance_overrides({},SPEC,NARR),[])
    def test_official_hook_instance_requires_existing_direction_brand_and_closed_timing(self):
        spec={'scenes':[{'id':'hook','family':'spotlight_agent','start':0,'params':{}}]}
        item={'scene_id':'hook','kind':'spotlight_hook_identity','asset':'brand_claude_mark','painted_major_px':220,'support_major_px':100,
            'primary_until_frame':46,'transform_frames':15,'entrance_s':.3,'reason':'Una identidad oficial inicial se transforma en apoyo al aparecer la capacidad narrada.'}
        direction={'hook_end_frame':137,'hook_blocks':[{'brand_asset':'brand_claude_mark','word_start':0}]}
        project={'revision':'production','brand_context':'private_review','instance_overrides':[item]};before=copy.deepcopy((project,spec,direction))
        with patch('brand_registry.assets_for_engine',return_value={'brand_claude_mark':{'kind':'brand_logo'}}):
            self.assertEqual(adapter.validated_instance_overrides(project,spec,NARR,direction),[item])
            self.assertEqual((project,spec,direction),before)
            item['transform_frames']=150
            with self.assertRaisesRegex(ValueError,'rango seguro'):adapter.validated_instance_overrides(project,spec,NARR,direction)
            item['transform_frames']=15;item['primary_until_frame']=130
            with self.assertRaisesRegex(ValueError,'fuera del hook'):adapter.validated_instance_overrides(project,spec,NARR,direction)
            item['primary_until_frame']=46;direction['hook_blocks'][0]['brand_asset']='brand_google_wordmark'
            with self.assertRaisesRegex(ValueError,'identidad inferida'):adapter.validated_instance_overrides(project,spec,NARR,direction)
    def test_mixed_audio_proof_is_bound_to_actual_file_and_original_packets(self):
        with tempfile.TemporaryDirectory(dir=adapter.ROOT/'.estado/tmp')as name:
            folder=pathlib.Path(name);source=folder/'source.mp4';audio=folder/'mix.m4a';proof_file=folder/'proof.json'
            source.write_bytes(b'UNIT SOURCE; decoder mocked');audio.write_bytes(b'UNIT MIX; no real audio generated')
            source_sha=adapter.w.digest(source);audio_sha=adapter.w.digest(audio);voice_sha='1'*64
            proof={'original_source_sha256':source_sha,'original_voice_stem_unchanged':True,'voice_source_sha256':voice_sha,'output_sha256':audio_sha}
            proof_file.write_text(json.dumps(proof));contract={'path':str(audio.relative_to(adapter.ROOT)),'sha256':audio_sha,
                'provenance_path':str(proof_file.relative_to(adapter.ROOT)),'provenance_sha256':adapter.w.digest(proof_file),'voice_source_sha256':voice_sha}
            project={'original':{'path':str(source.relative_to(adapter.ROOT)),'sha256':source_sha},'audio_mix':contract}
            media=folder/'media';media.mkdir();voice=media/'voice_original.m4a';voice.write_bytes(b'UNIT VOICE; decoder mocked')
            with patch.object(adapter,'run',return_value='SHA256='+voice_sha):
                self.assertEqual(adapter.validated_audio_mix(project,source_sha)['audio'],audio)
                playback=adapter.browser_audio(project,folder)
                self.assertEqual(playback['kind'],'verified_mix');self.assertEqual(playback['audible_tracks'],1)
                self.assertTrue((folder/playback['src']).is_symlink());self.assertEqual((folder/playback['src']).resolve(),audio.resolve())
                self.assertEqual(adapter.browser_audio(project,folder)['sha256'],audio_sha)
                self.assertEqual(voice.read_bytes(),b'UNIT VOICE; decoder mocked')
                del project['audio_mix'];self.assertEqual(adapter.browser_audio(project,folder)['src'],'media/voice_original.m4a');project['audio_mix']=contract
            with patch.object(adapter,'run',return_value='SHA256='+'2'*64):
                with self.assertRaisesRegex(ValueError,'Stem o salida'):adapter.validated_audio_mix(project,source_sha)
            audio.write_bytes(b'MODIFIED MIX')
            with self.assertRaisesRegex(ValueError,'SHA actual'):adapter.validated_audio_mix(project,source_sha)
    def test_audio_mix_cannot_claim_unchanged_voice_without_complete_receipt(self):
        with self.assertRaisesRegex(ValueError,'contrato completo'):adapter.validated_audio_mix({'audio_mix':{'path':'recursos/missing.m4a'}},'0'*64)
        self.assertIsNone(adapter.validated_audio_mix({},'0'*64))
    def test_graph_brand_override_requires_the_original_node_and_authentic_asset(self):
        spec={'scenes':[{'id':'omni','family':'composition_graph','params':{'nodes':[{'id':'route','kind':'message','asset':'brand_omniroute_mark'}]}}]}
        item={'kind':'graph_brand_surface','scene_id':'omni','node_id':'route','asset':'brand_omniroute_mark','painted_major_native':96,
            'reason':'El icono auxiliar medido no era legible; se reserva una superficie para la misma marca auténtica.'}
        project={'revision':'production','brand_context':'private_review','instance_overrides':[item]};before=copy.deepcopy((project,spec))
        with patch('brand_registry.assets_for_engine',return_value={'brand_omniroute_mark':{'kind':'brand_logo'}}):
            self.assertEqual(adapter.validated_instance_overrides(project,spec,NARR),[item]);self.assertEqual((project,spec),before)
            item['node_id']='another'
            with self.assertRaisesRegex(ValueError,'no coincide'):adapter.validated_instance_overrides(project,spec,NARR)
            item['node_id']='route';item['painted_major_native']=400
            with self.assertRaisesRegex(ValueError,'rango seguro'):adapter.validated_instance_overrides(project,spec,NARR)

if __name__=='__main__':unittest.main(verbosity=2)
