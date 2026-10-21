"""Unified offline decision tests; no new EDA execution or proof claims."""
import copy,hashlib,json,pathlib,subprocess,sys,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.decision import decide
from verieda.case import load_case,digest
from test_case import SMOKE,NATIVE
from test_verification import RESULT,RESULT_SHA
FORMAL=ROOT/'evidence/candidate-formal-9a84b59a1c60/verifier-result.zip'
FORMAL_SHA='98f42872720c8fe0b73492ef8766f3b966725c049507975f9b58c6799e2511f7'

class DecisionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
 def test_initial_state_proposes_but_never_accepts_or_authorizes(self):
  r=decide(self.state,600)
  self.assertEqual(r['next_action'],'PREPARE_CANDIDATE')
  self.assertEqual(r['proposal']['selected_candidate']['action'],'timing_mapping')
  self.assertEqual(r['proposal']['candidates'][0]['legality']['legality'],'PASS')
  self.assertFalse(r['execution_authorized']);self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
  self.assertEqual(r['reference']['gates']['constraints'],'UNKNOWN')
 def test_pending_candidate_prevents_another_mapping_and_historical_proof_reuse(self):
  r=decide(self.state,300,RESULT,RESULT_SHA)
  self.assertIsNone(r['proposal']);self.assertEqual(r['next_action'],'PREPARE_VERIFICATION_REQUEST')
  self.assertEqual(r['candidate']['candidate_status'],'VERIFY_PENDING_CANDIDATE')
  self.assertEqual(r['candidate']['verification']['gates']['formal'],'NOT_RUN')
  self.assertEqual(r['reference']['gates']['formal'],'PASS_RESET_CONTRACT_UNBOUNDED')
  self.assertNotEqual(r['candidate']['subject_id'],self.state['state_id'])
 def test_actual_native_preparation_error_becomes_candidate_review_not_design_rejection(self):
  r=decide(self.state,300,RESULT,RESULT_SHA,FORMAL,FORMAL_SHA)
  self.assertEqual(r['next_action'],'REVIEW_TOOL_FAILURE')
  self.assertEqual(r['candidate']['candidate_status'],'CANDIDATE_TOOL_BLOCKED')
  self.assertEqual(r['failure']['evidence_gate'],'PASS')
  self.assertIsNone(r['proposal']);self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
  self.assertEqual(r['project_status'],'NOT_EVALUATED')
 def test_bad_or_foreign_evidence_holds_and_never_falls_back_to_proposing(self):
  r=decide(self.state,600,RESULT,'0'*64)
  self.assertEqual(r['next_action'],'HOLD_EVIDENCE');self.assertIsNone(r['proposal'])
  r=decide(self.state,300,RESULT,RESULT_SHA,FORMAL,'0'*64)
  self.assertEqual(r['next_action'],'HOLD_EVIDENCE')
  self.assertIsNone(r['candidate']);self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
 def test_budget_and_incomplete_pairs_fail_closed(self):
  self.assertEqual(decide(self.state,299,RESULT,RESULT_SHA)['next_action'],'STOP_BUDGET')
  for kwargs in ({'result':RESULT},{'formal_result':FORMAL,'formal_sha256':FORMAL_SHA},{'budget_seconds':True}):
   with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):decide(self.state,**kwargs)
 def test_generic_state_and_net_dominated_evidence_select_investigation(self):
  s=copy.deepcopy(self.state);s['design']='counter';s['timing_analysis']['dominant_delay']='NET'
  s['state_id']=digest({k:v for k,v in s.items() if k!='state_id'})
  r=decide(s,600)
  self.assertEqual(r['next_action'],'INVESTIGATE_CRITICAL_CELLS')
  self.assertEqual(r['proposal']['selected_candidate']['protected']['design'],'counter')
 def test_decision_is_content_bound_and_does_not_mutate_state(self):
  before=copy.deepcopy(self.state);r=decide(self.state,300,RESULT,RESULT_SHA,FORMAL,FORMAL_SHA)
  self.assertEqual(r['decision_id'],digest({k:v for k,v in r.items() if k!='decision_id'}))
  self.assertEqual(before,self.state)
 def test_final_decisions_delegate_to_independent_gate_predicate(self):
  # Synthetic after-state tests routing only, never a physical optimization.
  from verieda.policy import propose
  c=propose(self.state,600)['selected_candidate']
  a=copy.deepcopy(self.state)
  for gate in a['gates']:a['gates'][gate]='PASS_RESET_CONTRACT_UNBOUNDED' if gate=='formal' else 'PASS'
  a['metrics']['WNS']['value']=0.01;a['inputs']['6_final.v']='e'*64
  a['provenance']['acceptance']['sha256']='f'*64
  a['execution']={'candidate_id':c['candidate_id'],'state_id':self.state['state_id'],'return_code':0,'changes':c['changes'],'phase':'RTL_TO_GDS','status':'COMPLETED'}
  for value,want in [('PASS','ACCEPT_CANDIDATE'),('FAIL','REJECT_CANDIDATE'),('UNKNOWN','CONTINUE_FINAL_VERIFICATION')]:
   a['gates']['constraints']=value;a['state_id']=digest({k:v for k,v in a.items() if k!='state_id'})
   r=decide(self.state,0,RESULT,RESULT_SHA,after_state=a)
   self.assertEqual(r['next_action'],want,r)
   self.assertFalse(r['execution_authorized'])
  r=decide(self.state,0,RESULT,RESULT_SHA,FORMAL,'0'*64,after_state=a)
  self.assertEqual(r['next_action'],'HOLD_EVIDENCE');self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
  self.assertIsNone(r['candidate'])
  # A checksummed, parseable archive can still refer to the wrong task.
  from verieda.evidence import read_bundle
  a['gates']['constraints']='PASS';a['state_id']=digest({k:v for k,v in a.items() if k!='state_id'})
  data=read_bundle(FORMAL);receipt=json.loads(data['receipt.json']);receipt['task_id']='f'*64
  data['receipt.json']=json.dumps(receipt).encode()
  payload={n:b for n,b in data.items() if n not in ('SHA256SUMS.txt','file-sizes.json')}
  payload['file-sizes.json']=json.dumps([{'path':n,'bytes':len(b)} for n,b in payload.items()]).encode()
  payload['SHA256SUMS.txt']=''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in payload.items()).encode()
  with tempfile.TemporaryDirectory() as tmp:
   archive=pathlib.Path(tmp)/'foreign.zip'
   with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for n,b in payload.items():z.writestr(n,b)
   h=hashlib.sha256(archive.read_bytes()).hexdigest()
   r=decide(self.state,300,RESULT,RESULT_SHA,archive,h,after_state=a)
   self.assertEqual(r['failure']['analysis_gate'],'PASS')
   self.assertEqual(r['next_action'],'HOLD_EVIDENCE');self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
  with self.assertRaises(ValueError):decide(self.state,after_state=a)
 def test_cli_loads_real_evidence_and_matches_api(self):
  args=[sys.executable,'-m','verieda','decide','--profile','cases/gcd.json','--smoke',str(SMOKE),'--acceptance',str(NATIVE),'--budget-seconds','300','--result',str(RESULT),'--expected-sha256',RESULT_SHA,'--formal-result',str(FORMAL),'--formal-sha256',FORMAL_SHA]
  p=subprocess.run(args,cwd=ROOT,capture_output=True,timeout=30)
  self.assertEqual(p.returncode,0,p.stderr.decode())
  r=json.loads(p.stdout);self.assertEqual(r,decide(self.state,300,RESULT,RESULT_SHA,FORMAL,FORMAL_SHA))

if __name__=='__main__':unittest.main()
