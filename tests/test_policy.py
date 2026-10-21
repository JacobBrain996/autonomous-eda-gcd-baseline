import copy,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.policy import propose,validate_candidate
from verieda.case import digest

def state(dominant='CELL'):
    s={'schema':'verieda.design-state.v0','design':'gcd','platform':'nangate45',
       'frozen':{'rtl_sha256':'a'*64,'sdc_sha256':'b'*64},'tools':{'yosys':'c'*64},
       'inputs':{'6_final.v':'d'*64},'gates':{'evidence':'PASS','identity':'PASS','timing':'FAIL','constraints':'UNKNOWN'},
       'timing_analysis':{'dominant_delay':dominant,'worst_path':{'endpoint':'out','data_cell_delay_ns':0.3,'data_net_delay_ns':0.002}}}
    s['state_id']=digest(s);return s

class PolicyTests(unittest.TestCase):
    def test_cell_dominated_case_prioritizes_mapping_with_bounded_scope(self):
        s=state();p=propose(s,600,[])
        self.assertEqual(p['selected_candidate']['action'],'timing_mapping')
        self.assertEqual(p['selected_candidate']['changes'],{'ABC_AREA':0})
        self.assertFalse(p['execution_authorized']);self.assertFalse(p['selected_candidate']['execution_ready'])
        self.assertIn('constraints',p['acceptance_blockers'])
        self.assertEqual(validate_candidate(p['selected_candidate'],s)['legality'],'PASS')
    def test_net_delay_selects_local_sizing_investigation_not_area_toggle(self):
        p=propose(state('NET'),600,[])
        self.assertEqual(p['selected_candidate']['action'],'critical_cell_sizing')
    def test_no_budget_does_not_schedule_eda(self):
        p=propose(state(),0,[])
        self.assertIsNone(p['selected_candidate']);self.assertEqual(p['decision'],'STOP_BUDGET')
        self.assertEqual(p['offline_actions'],['audit_constraint_semantics'])
    def test_repeated_outcomes_are_not_retried_and_unrelated_history_is_rejected(self):
        s=state();p=propose(s,600,[]);c=p['selected_candidate']
        h=[{'state_id':s['state_id'],'candidate_id':c['candidate_id'],'outcome':'TIMEOUT','runtime_seconds':30}]
        q=propose(s,600,h)
        self.assertEqual(q['decision'],'STOP_BUDGET')
        h[0]['runtime_seconds']=0
        q=propose(s,600,h)
        self.assertNotEqual(q['selected_candidate']['candidate_id'],c['candidate_id'])
        h[0]['state_id']='unrelated'
        with self.assertRaises(ValueError):propose(s,600,h)
    def test_illegal_mutation_or_foreign_state_is_rejected(self):
        s=state();c=propose(s,600,[])['selected_candidate']
        for change in ({'CLOCK_PERIOD':1},{'ABC_AREA':1},{'ABC_AREA':False}):
            bad=copy.deepcopy(c);bad['changes']=change
            self.assertEqual(validate_candidate(bad,s)['legality'],'FAIL')
        other=state('NET')
        self.assertEqual(validate_candidate(c,other)['legality'],'FAIL')
    def test_bad_integrity_stops_and_invalid_budget_or_history_fails_closed(self):
        s=state();s['gates']['evidence']='FAIL';s.pop('state_id');s['state_id']=digest(s)
        self.assertEqual(propose(s,600,[])['decision'],'HOLD_EVIDENCE')
        for n in (-1,True,601,float('nan')):
            with self.subTest(n=n),self.assertRaises(ValueError):propose(state(),n,[])
        with self.assertRaises(ValueError):propose(state(),600,[{'outcome':'PASS'}])
    def test_missing_worst_path_stops_and_unhashable_history_is_structured_error(self):
        s=state();s['timing_analysis']['worst_path']=None;s.pop('state_id');s['state_id']=digest(s)
        self.assertEqual(propose(s,600,[])['decision'],'HOLD_PATH_EVIDENCE')
        s=state()
        with self.assertRaises(ValueError):propose(s,600,[{'state_id':s['state_id'],'candidate_id':[], 'outcome':'ERROR','runtime_seconds':0}])

if __name__=='__main__':unittest.main()
