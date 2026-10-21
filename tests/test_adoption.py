"""Synthetic validator cases do not claim any physical optimization."""
import copy,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.adoption import evaluate
from verieda.case import digest
from verieda.policy import propose
from test_policy import state

def bind(s):s.pop('state_id',None);s['state_id']=digest(s);return s

class AdoptionTests(unittest.TestCase):
    def setup_states(self):
        before=state();before.update(metrics={'WNS':{'value':-0.1},'stdcell_area':{'value':100}},
            formal={'contract':'two resets; all outputs'},provenance={'acceptance':{'sha256':'a'*64}},execution=None)
        for k in ('physical','rtl_simulation','gds_generation','gds_read','router_drc'):before['gates'][k]='PASS'
        before['gates']['formal']='PASS_RESET_CONTRACT_UNBOUNDED';bind(before)
        c=propose(before,600,[])['selected_candidate']
        after=copy.deepcopy(before);after['metrics']['WNS']['value']=0;after['gates']['timing']='PASS';after['gates']['constraints']='PASS'
        after['inputs']['6_final.v']='e'*64;after['provenance']['acceptance']['sha256']='f'*64
        after['execution']={'candidate_id':c['candidate_id'],'state_id':before['state_id'],'return_code':0,'changes':c['changes']}
        bind(after);return before,after,c
    def test_acceptance_requires_all_independent_gates_and_improvement(self):
        b,a,c=self.setup_states();r=evaluate(b,a,c)
        self.assertEqual(r['verdict'],'ACCEPTED');self.assertAlmostEqual(r['WNS_improvement_ns'],0.1)
    def test_missing_constraints_or_proof_is_inconclusive_not_pass(self):
        for gate in ('constraints','formal','gds_read'):
            b,a,c=self.setup_states();a['gates'][gate]='UNKNOWN';bind(a)
            self.assertEqual(evaluate(b,a,c)['verdict'],'INCONCLUSIVE')
    def test_improved_negative_slack_or_failed_drc_is_rejected(self):
        for gate in ('timing','router_drc','formal'):
            b,a,c=self.setup_states();a['gates'][gate]='FAIL';bind(a)
            self.assertEqual(evaluate(b,a,c)['verdict'],'REJECTED')
    def test_same_evidence_or_unexecuted_candidate_cannot_be_accepted(self):
        b,a,c=self.setup_states();a['provenance']=copy.deepcopy(b['provenance']);bind(a)
        self.assertEqual(evaluate(b,a,c)['verdict'],'REJECTED')
        b,a,c=self.setup_states();a['execution']=None;bind(a)
        self.assertEqual(evaluate(b,a,c)['verdict'],'INCONCLUSIVE')
    def test_changed_contract_constraints_or_area_overhead_is_rejected(self):
        for field in ('contract','sdc','area','no_gain','unchanged_netlist'):
            b,a,c=self.setup_states()
            if field=='contract':a['formal']['contract']='bounded ten cycles'
            elif field=='sdc':a['frozen']['sdc_sha256']='relaxed'
            elif field=='area':a['metrics']['stdcell_area']['value']=111
            elif field=='no_gain':a['metrics']['WNS']['value']=-0.1
            else:a['inputs']['6_final.v']=b['inputs']['6_final.v']
            bind(a)
            self.assertEqual(evaluate(b,a,c)['verdict'],'REJECTED',field)
    def test_policy_mutation_and_missing_metrics_never_pass(self):
        b,a,c=self.setup_states();c['changes']={'CLOCK_PERIOD':1}
        self.assertEqual(evaluate(b,a,c)['verdict'],'REJECTED')
        b,a,c=self.setup_states();a['metrics'].pop('stdcell_area');bind(a)
        self.assertEqual(evaluate(b,a,c)['verdict'],'INCONCLUSIVE')
    def test_nonobject_candidate_is_structured_inconclusive(self):
        b,a,_=self.setup_states()
        self.assertEqual(evaluate(b,a,[])['verdict'],'INCONCLUSIVE')

if __name__=='__main__':unittest.main()
