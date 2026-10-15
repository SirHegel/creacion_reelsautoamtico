"""Guardas de integración; fixtures de tests, nunca fallback de producción."""
import copy,json,pathlib,sys,unittest
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import integration_planner as ip
FIXTURES=pathlib.Path(__file__).resolve().parent/'fixtures'
SPEC=json.loads((FIXTURES/'integration_scene_v1.json').read_text());NARR=json.loads((FIXTURES/'integration_narration_v1.json').read_text())
SPEC_V2=json.loads((FIXTURES/'integration_scene_v2.json').read_text())
HOOK_CONSTRAINTS={'camera_mode':'split_first','split_top':.5,'scope_end_frame':108,'max_primary':1,'max_support':1}

def block(ident,a,b,x,y,sequence='',placement='composition'):
    return {'id':ident,'start_frame':a,'end_frame':b,'word_start':x,'word_end':y,'sequence':sequence,'font':'Sequel','color':'white','emphasis_word_indices':[],'red_reason':'','placement':placement}

def fixture():
    return {'schema_version':1,'conceptual':True,'camera_budget_reason':'','camera_windows':[
        {'start_frame':0,'end_frame':6,'state':'full','transition_frames':0,'exit_frames':0,'anchor_indices':[0],'reason':'Introducir la identidad del narrador al pronunciar la provocación.'},
        {'start_frame':6,'end_frame':21,'state':'split','transition_frames':6,'exit_frames':0,'anchor_indices':[0,1,2],'reason':'Reencuadrar mientras evoluciona la explicación visual superior.'},
        {'start_frame':175,'end_frame':198,'state':'full','transition_frames':0,'exit_frames':6,'anchor_indices':[17,18,19],'reason':'Aclarar brevemente la condición económica con la identidad del narrador.'}],
        'hook_end_frame':127,
        'hook_blocks':[block('hook_a',0,17,0,1,'provocacion','hook'),block('hook_b',17,28,0,2,'provocacion','hook'),block('hook_c',29,69,3,7,'causa','hook'),block('hook_d',70,108,8,11,'accion','hook'),block('hook_e',110,127,12,13,'fuentes','hook')],
        'caption_blocks':[block('cap_a',127,175,14,16),block('cap_b',175,198,17,19,placement='under_chin'),block('cap_c',198,212,20,21),block('cap_d',212,237,22,23)],
        'phase_cues':[{'scene_id':SPEC['scenes'][0]['id'],'cue_id':'step:0','anchor_index':0,'reason':'La aparición del nodo coincide con la primera palabra pronunciada.'},
                      {'scene_id':SPEC['scenes'][0]['id'],'cue_id':'step:7','anchor_index':14,'reason':'La fuente entra cuando se menciona la plataforma correspondiente.'}],
        'omissions':[]}

def hook_fixture():
    scene,narration,_=ip.scoped_inputs(SPEC_V2,NARR,HOOK_CONSTRAINTS);ident=scene['scenes'][0]['id']
    raw={'schema_version':1,'conceptual':True,'camera_mode':'split_first','split_top':.5,'split_ratio_reason':'',
         'camera_budget_reason':'Presencia inicial breve para reconocer al narrador en esta muestra compuesta únicamente por el hook.',
         'camera_windows':[{'start_frame':0,'end_frame':60,'state':'split','transition_frames':0,'exit_frames':6,
             'anchor_indices':list(range(7)),'reason':'El presentador aparece debajo de la explicación desde el primer fotograma, sin un full previo.'}],
         'hook_end_frame':108,'hook_blocks':[block('h_a',0,17,0,1,'google','hook'),block('h_b',17,29,0,2,'google','hook'),
             block('h_c',29,51,3,4,'claude','hook'),block('h_d',51,69,3,7,'claude','hook'),
             block('h_e',70,92,8,9,'scraping','hook'),block('h_f',92,108,8,11,'scraping','hook')],
         'caption_blocks':[],'omissions':[],
         'phase_cues':[{'scene_id':ident,'cue_id':'step:0','anchor_index':0,'reason':'La aparición inicial conserva el primer endpoint y la primera palabra del hook.'}],
         'focus_windows':[{'scene_id':ident,'start_frame':0,'end_frame':36,'primary_target':'google','support_target':None,
                          'reason':'La reacción inicial se organiza alrededor de Google como único protagonista.'},
                         {'scene_id':ident,'start_frame':36,'end_frame':70,'primary_target':'claude','support_target':None,
                          'reason':'Claude toma el foco cuando la voz introduce su identidad y su skill.'},
                         {'scene_id':ident,'start_frame':70,'end_frame':108,'primary_target':'claude','support_target':'internet',
                          'reason':'La fuente Internet apoya al protagonista durante el proceso conceptual de scraping.'}]}
    return raw,scene,narration

class IntegrationContracts(unittest.TestCase):
    def validate(self,raw):return ip.normalize(raw,SPEC,NARR)
    def test_real_scene_selection_and_protected_families_remain_unchanged(self):
        source=copy.deepcopy(SPEC);protected=ip.protected_sources();raw=fixture();before=copy.deepcopy(raw)
        result=self.validate(raw)
        self.assertEqual(raw,before);self.assertEqual(SPEC,source);self.assertEqual(ip.protected_sources(),protected)
        self.assertFalse(result['semantic_selection_modified']);self.assertFalse(result['execution_verified']);self.assertEqual(result['frames'],237)
    def test_normalized_contract_revalidates_without_mutation(self):
        result=self.validate(fixture());result['inference']={'real_inference':True};original=copy.deepcopy(result)
        checked=ip.validate_plan(result,SPEC,NARR)
        self.assertEqual(result,original);self.assertEqual(checked['hook_blocks'][1]['text'],'Google anuncia riesgo')
        result['caption_blocks'][0]['text']='Ganador99%'
        with self.assertRaisesRegex(ip.IntegrationError,'Texto normalizado'):ip.validate_plan(result,SPEC,NARR)
    def test_new_families_metrics_and_code_cannot_enter_contract(self):
        for key,value in [('family','phone_rebuild'),('metric',99),('javascript','eval(x)')]:
            raw=fixture();raw[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ip.IntegrationError,'Contrato de integración inválido'):self.validate(raw)
    def test_continuous_face_union_includes_full_split_and_transitions(self):
        raw=fixture();raw['camera_windows'][1]['end_frame']=100
        with self.assertRaisesRegex(ip.IntegrationError,'3s continuos'):self.validate(raw)
        raw=fixture();raw['camera_windows'][-1]['exit_frames']=0
        with self.assertRaisesRegex(ip.IntegrationError,'6frames'):self.validate(raw)
        raw=fixture();raw['camera_windows'][1]['start_frame']=7
        result=self.validate(raw);self.assertEqual(result['visible_intervals_frames'][:2],[(0,6),(7,21)])
    def test_camera_requires_real_narrative_anchor(self):
        raw=fixture();raw['camera_windows'][0]['anchor_indices']=[14]
        with self.assertRaisesRegex(ip.IntegrationError,'no intersecta'):self.validate(raw)
    def test_positive_advantage_and_brand_are_not_arbitrary_red(self):
        for index,block_index,field in [(0,0,'hook_blocks'),(18,1,'caption_blocks')]:
            raw=fixture();b=raw[field][block_index];b.update(color='red',emphasis_word_indices=[index],red_reason='Pretende enfatizar una palabra sin justificación editorial válida.')
            with self.subTest(index=index),self.assertRaisesRegex(ip.IntegrationError,'marca, título o ventaja'):self.validate(raw)
        raw=fixture();raw['hook_blocks'][1].update(color='red',emphasis_word_indices=[2],red_reason='Riesgo es la advertencia ficticia; énfasis editorial, no evidencia del enfado.')
        result=self.validate(raw);self.assertEqual(result['hook_blocks'][1]['emphasis_word_indices'],[2])
    def test_isolated_hook_word_and_missing_text_are_rejected(self):
        raw=fixture();raw['hook_blocks'][0]['word_end']=0
        with self.assertRaisesRegex(ip.IntegrationError,'palabra aislada'):self.validate(raw)
        raw=fixture();raw['caption_blocks'].pop()
        with self.assertRaisesRegex(ip.IntegrationError,'sin representación textual'):self.validate(raw)
    def test_under_chin_is_required_after_hook_and_matches_face_window(self):
        raw=fixture();raw['caption_blocks'][1]['placement']='composition'
        with self.assertRaisesRegex(ip.IntegrationError,'Placement'):self.validate(raw)
        raw=fixture();raw['camera_windows'].pop();raw['camera_windows'][1]['exit_frames']=6;raw['caption_blocks'][1]['placement']='composition'
        result=self.validate(raw);self.assertFalse(any(b['placement']=='under_chin'for b in result['caption_blocks']))
    def test_false_omission_cannot_use_replaced_native_caption(self):
        raw=fixture();raw['caption_blocks'].pop();raw['omissions']=[{'word_start':22,'word_end':23,'scene_id':SPEC['scenes'][0]['id'],'field_path':'caption','reason':'No puede atribuirse a una caption que el adaptador va a sustituir.'}]
        with self.assertRaisesRegex(ip.IntegrationError,'reemplazada'):self.validate(raw)
    def test_cues_are_real_monotonic_and_not_fabricated_phase_actions(self):
        raw=fixture();raw['phase_cues'][1]['cue_id']='step:999'
        with self.assertRaisesRegex(ip.IntegrationError,'Cue inexistente'):self.validate(raw)
        raw=fixture();raw['phase_cues'][1]['anchor_index']=0
        with self.assertRaisesRegex(ip.IntegrationError,'no monótono'):self.validate(raw)
        result=self.validate(fixture());self.assertEqual(result['phase_cues'][0]['timing_basis'],'declared_step_time');self.assertFalse(result['phase_cues'][0]['execution_verified'])
    def test_alignment_or_authenticity_claim_cannot_be_faked(self):
        narration=copy.deepcopy(NARR);narration['words'][0]['text']='Microsoft'
        with self.assertRaisesRegex(ip.IntegrationError,'Palabras no corresponden'):ip.normalize(fixture(),SPEC,narration)
        raw=fixture();raw['conceptual']=False
        with self.assertRaisesRegex(ip.IntegrationError,'no es una prueba auténtica'):self.validate(raw)
    def test_hook_logo_uses_real_entity_and_never_silently_substitutes(self):
        assets={'brand_google':{'kind':'brand_logo','brand':'Google','aliases':['Google'],'sha256':'1'*64},
                'brand_claude':{'kind':'brand_logo','brand':'Claude','aliases':['Claude'],'sha256':'2'*64}}
        raw=fixture();
        for b in raw['hook_blocks'][:2]:b.update(brand_asset='brand_google',brand_entity_id='google',brand_reason='La identidad de Google sigue visible junto a su frase mientras la cámara cubre el motion.')
        with patch.object(ip.p,'resolved_assets',return_value=assets):
            valid=self.validate(raw);self.assertEqual(valid['hook_blocks'][0]['brand_identity_receipt']['sha256'],'1'*64)
            
            for b in raw['hook_blocks'][:2]:b['brand_asset']='brand_claude'
            with self.assertRaisesRegex(ip.IntegrationError,'Logo del hook'):self.validate(raw)
    def test_phase_cue_cannot_overwrite_requested_hold_or_clock_point(self):
        spec=copy.deepcopy(SPEC);target=round(NARR['words'][14]['start']*30)/30
        spec['scenes'][0]['rhythm']={'clock_knots':[{'at':0,'native_at':0},{'at':target,'native_at':4},{'at':7.9,'native_at':7.9}]}
        with self.assertRaisesRegex(ip.IntegrationError,'contradice'):ip.normalize(fixture(),spec,NARR)

    def test_frames_fonts_and_emphasis_have_closed_forms(self):
        for field,value in [('font','Arial'),('color','#FF0000'),('start_frame',True)]:
            raw=fixture();raw['hook_blocks'][0][field]=value
            with self.subTest(field=field),self.assertRaises(ip.IntegrationError):self.validate(raw)

    def test_legacy_v2_still_valid_and_full_first_does_not_require_split(self):
        result=self.validate(fixture());self.assertEqual(result['camera_mode'],'full_first');self.assertEqual(result['split_top'],.55)
        self.assertEqual(result['focus_windows'],[])
        raw=fixture();raw['camera_windows']=[{**raw['camera_windows'][0],'end_frame':21,'exit_frames':6,'anchor_indices':[0,1,2]}]
        raw['caption_blocks'][1]['placement']='composition'
        result=self.validate(raw);self.assertEqual(len(result['camera_windows']),1);self.assertEqual(result['camera_mode'],'full_first')

    def test_split_first_pose_at_zero_needs_no_full_or_initial_reveal(self):
        raw,scene,narration=hook_fixture();before=copy.deepcopy((raw,scene,narration))
        result=ip.normalize(raw,scene,narration,HOOK_CONSTRAINTS)
        self.assertEqual((raw,scene,narration),before);self.assertEqual(result['frames'],108);self.assertEqual(result['hook_end_frame'],108)
        self.assertEqual(result['camera_mode'],'split_first');self.assertEqual(result['split_top'],.5)
        self.assertEqual(len(result['camera_windows']),1);self.assertEqual(result['caption_blocks'],[])
        self.assertFalse(result['focus_execution']['execution_verified']);self.assertEqual(result['visible_frames'],60)
        self.assertEqual(ip.validate_plan(result,scene,narration)['hook_blocks'][-1]['text'],'para resumir información web')
        for change in [{'transition_frames':6},{'start_frame':1},{'end_frame':91},{'state':'full'},{'end_frame':5}]:
            failed=copy.deepcopy(raw);failed['camera_windows'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ip.IntegrationError):ip.normalize(failed,scene,narration,HOOK_CONSTRAINTS)

    def test_split_first_ratio_alternative_requires_framing_reason_and_respects_request(self):
        raw,scene,narration=hook_fixture();raw['split_top']=.55
        constraints={**HOOK_CONSTRAINTS,'split_top':.55}
        with self.assertRaisesRegex(ip.IntegrationError,'motivo concreto'):ip.normalize(raw,scene,narration,constraints)
        raw['split_ratio_reason']='El encuadre requiere altura adicional para conservar frente, barbilla y el micrófono completo.'
        self.assertEqual(ip.normalize(raw,scene,narration,constraints)['split_top'],.55)
        with self.assertRaisesRegex(ip.IntegrationError,'modo/proporción explícitos'):ip.normalize(raw,scene,narration,HOOK_CONSTRAINTS)

    def test_short_all_hook_does_not_disable_word_coverage(self):
        raw,scene,narration=hook_fixture();raw['hook_blocks'].pop()
        with self.assertRaisesRegex(ip.IntegrationError,'sin representación textual'):ip.normalize(raw,scene,narration,HOOK_CONSTRAINTS)
        raw,scene,narration=hook_fixture();raw['hook_end_frame']=100
        with self.assertRaisesRegex(ip.IntegrationError,'segmento autorizado más corto'):ip.normalize(raw,scene,narration,HOOK_CONSTRAINTS)
        raw=fixture();raw['caption_blocks']=[]
        with self.assertRaisesRegex(ip.IntegrationError,'desarrollo'):self.validate(raw)

    def test_focus_ids_enter_coverage_and_two_object_limit_are_real_contracts(self):
        raw,scene,narration=hook_fixture()
        cases=[('unknown',lambda r:r['focus_windows'][1].update(primary_target='eval(x)')),
               ('before_enter',lambda r:(r['focus_windows'][0].update(end_frame=35),r['focus_windows'][1].update(start_frame=35))),
               ('gap',lambda r:r['focus_windows'][1].update(start_frame=37)),
               ('duplicate',lambda r:r['focus_windows'][0].update(support_target='google')),
               ('third',lambda r:r['focus_windows'][2].update(extra_target='google')),
               ('beyond',lambda r:r['focus_windows'][-1].update(end_frame=109)),
               ('promise',lambda r:r.update(focus_windows=[]))]
        for label,change in cases:
            failed=copy.deepcopy(raw);change(failed)
            with self.subTest(label=label),self.assertRaises(ip.IntegrationError):ip.normalize(failed,scene,narration,HOOK_CONSTRAINTS)
        with self.assertRaisesRegex(ip.IntegrationError,'excluye objetos de apoyo'):
            ip.normalize(raw,scene,narration,{**HOOK_CONSTRAINTS,'max_support':0})

    def test_prefix_derivation_preserves_original_scenes_words_and_history(self):
        source=copy.deepcopy(SPEC_V2);voice=copy.deepcopy(NARR)
        scene,narration,receipt=ip.scoped_inputs(source,voice,HOOK_CONSTRAINTS)
        self.assertEqual(source,SPEC_V2);self.assertEqual(voice,NARR)
        self.assertEqual(scene['scenes'],SPEC_V2['scenes'][:1]);self.assertEqual(scene['duration'],3.6)
        self.assertEqual(narration['words'],NARR['words'][:12]);self.assertEqual(narration['source'],NARR['source'])
        self.assertEqual(scene['planner']['manual_sha256'],SPEC_V2['planner']['manual_sha256']);self.assertFalse(receipt['new_primary_inference'])
        self.assertTrue(receipt['scene_parameters_and_steps_unchanged']);self.assertEqual(receipt['excluded_scene_ids'],['sources_condition'])
        for stop in [107,109,237]:
            with self.subTest(stop=stop),self.assertRaises(ip.IntegrationError):ip.scoped_inputs(source,voice,{**HOOK_CONSTRAINTS,'scope_end_frame':stop})
        changed=copy.deepcopy(voice);changed['words'][11]['end']=3.7;changed['words'][12]['start']=3.75;source=copy.deepcopy(source)
        source['timing']['anchors']=ip.p.narration_items(changed)
        with self.assertRaisesRegex(ip.IntegrationError,'recorta una palabra'):ip.scoped_inputs(source,changed,HOOK_CONSTRAINTS)

    def test_scope_cannot_reuse_brand_from_later_narration(self):
        raw,scene,narration=hook_fixture()
        for b in raw['hook_blocks'][:2]:b.update(brand_asset='brand_linkedin',brand_entity_id='linkedin',brand_reason='Pretende usar una identidad que existe solo en la segunda escena del origen.')
        with self.assertRaisesRegex(ip.IntegrationError,'fuera de la narración'):ip.normalize(raw,scene,narration,HOOK_CONSTRAINTS)

    def test_constraints_and_provider_schema_are_closed_and_do_not_force_full_split(self):
        for change in [{'camera_mode':[]},{'split_top':True},{'split_top':[]},{'split_top':.6},{'max_primary':2},{'max_support':2},{'scope_end_frame':True},{'javascript':'x'}]:
            with self.subTest(change=change),self.assertRaises(ip.IntegrationError):ip.constraint_contract(change)
        raw,scene,narration=hook_fixture();prompt=ip.make_prompt(scene,narration,'Identidad YO',constraints=HOOK_CONSTRAINTS)
        self.assertNotIn('seguida de split CONTIGUO',prompt);self.assertIn('No es obligatorio comenzar full',prompt)
        provider=ip.p.strict_provider_schema(ip.SCHEMA)
        self.assertEqual(set(provider['required']),set(provider['properties']));self.assertIn('focus_windows',provider['required'])

if __name__=='__main__':unittest.main(verbosity=2)
