"""Verifier orchestration tests; synthetic logs are not EDA proofs."""
import copy,hashlib,json,pathlib,subprocess,sys,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda import verification as v
from verieda.case import digest,load_case
from test_case import SMOKE,NATIVE

RESULT=ROOT/'evidence/verieda-action-ed5d84b9bdf7/result.zip'
RESULT_SHA='15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3'

class VerificationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
 def test_reviewed_real_proof_unlocks_only_exact_synthesis_subject_with_scope_check(self):
  result=ROOT/'evidence/candidate-formal-b19cc94faa0d/verifier-result.zip'
  h='06619a67e1060a3a0c396b9dcba5867cb5134f46e75074229df6d936471d660b'
  package=ROOT/'evidence/verification-handoff-20261021-v1/package'
  r=v.review_candidate(self.state,RESULT,RESULT_SHA,600,result,h,None,package,ROOT/'contracts/gcd.reset2.json')
  self.assertEqual(r['candidate_status'],'READY_FOR_PHYSICAL')
  self.assertEqual(r['verification']['gates']['formal'],'PASS_RESET_CONTRACT_UNBOUNDED')
  self.assertEqual(r['verification']['gates']['timing'],'NOT_RUN')
  self.assertFalse(r['execution_authorized']);self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
  # Without the checked source/model scope, the marker alone is insufficient.
  r=v.review_candidate(self.state,RESULT,RESULT_SHA,300,result,h)
  self.assertEqual(r['candidate_status'],'PROOF_REVIEW_PENDING')
 def subject(self):return v.load_subject(self.state,RESULT,RESULT_SHA)
 def test_final_netlist_requires_fresh_subject_and_proof(self):
  parent=self.subject()
  with tempfile.TemporaryDirectory() as tmp:
   tmp=pathlib.Path(tmp);final=tmp/'final';final.mkdir()
   (final/'6_final.v').write_bytes(b'new final netlist');(final/'6_final.odb').write_bytes(b'new odb')
   receipt={'candidate_id':parent['candidate_id'],'parent_subject_id':parent['subject_id'],'return_code':0,'phase':'PHYSICAL_FINAL_OUTPUTS',
    'netlist_sha256':hashlib.sha256((final/'6_final.v').read_bytes()).hexdigest(),'odb_sha256':hashlib.sha256((final/'6_final.odb').read_bytes()).hexdigest()}
   (final/'physical-receipt.json').write_text(json.dumps(receipt))
   v.prepare_final_verification(parent,final,tmp/'package')
   subject=json.loads((tmp/'package/subject.json').read_text());plan=json.loads((tmp/'package/plan.json').read_text())
   self.assertNotEqual(subject['subject_id'],parent['subject_id']);self.assertEqual(subject['execution_scope'],'PHYSICAL_FINAL')
   self.assertEqual(plan['next_check']['external_limits']['job_seconds'],1200)
   self.assertEqual(plan['next_check']['kind'],'FORMAL_FINAL');self.assertEqual(plan['gates']['formal'],'NOT_RUN')
   self.assertIsNone(v._registered_formal_review(subject,'06619a67e1060a3a0c396b9dcba5867cb5134f46e75074229df6d936471d660b'))
   receipt['return_code']=False;(final/'physical-receipt.json').write_text(json.dumps(receipt))
   with self.assertRaises(ValueError):v.prepare_final_verification(parent,final,tmp/'bad')
 def test_real_synthesis_requires_new_proof_and_preserves_reference(self):
  s=self.subject();p=v.plan_verification(s,300)
  self.assertEqual(p['decision'],'PREPARE_FORMAL_CHECK')
  self.assertEqual(p['next_check']['kind'],'FORMAL_SYNTHESIS')
  self.assertEqual(s['target']['netlist_sha256'],'cacc9a64686672f85d077c42c2fa2639fee1b649a6c9754b4297ff6725884785')
  self.assertNotEqual(s['target']['netlist_sha256'],self.state['inputs']['6_final.v'])
  self.assertEqual(p['gates']['formal'],'NOT_RUN');self.assertEqual(p['gates']['timing'],'NOT_RUN')
  self.assertEqual(p['design_acceptance'],'NOT_EVALUATED');self.assertFalse(p['execution_authorized'])
  self.assertIn('GDS',str(p['downstream_checks']))
 def test_budget_must_cover_cap_and_invalid_values_fail(self):
  s=self.subject()
  for budget in (0,1,299):self.assertEqual(v.plan_verification(s,budget)['decision'],'STOP_BUDGET')
  for budget in (True,-1,601,float('nan')):
   with self.assertRaises(ValueError):v.plan_verification(s,budget)
 def test_foreign_or_mutated_action_cannot_be_prepared(self):
  with self.assertRaises(ValueError):v.load_subject(self.state,RESULT,'0'*64)
  state=copy.deepcopy(self.state);state['design']='other';state['state_id']=digest({k:x for k,x in state.items() if k!='state_id'})
  with self.assertRaises(ValueError):v.load_subject(state,RESULT,RESULT_SHA)
 def test_subject_mutation_is_not_trusted(self):
  s=self.subject();s['target']['netlist_sha256']='0'*64
  with self.assertRaises(ValueError):v.plan_verification(s,300)
 def test_generic_planner_has_no_gcd_names_or_fixed_interface(self):
  s=self.subject();s['design']='counter';s['platform']='otherlib';s['formal_contract']='one reset edge; all 4 output bits'
  s['subject_id']=digest({k:x for k,x in s.items() if k!='subject_id'})
  p=v.plan_verification(s,300)
  self.assertEqual(p['next_check']['inputs']['contract'],s['formal_contract'])
  self.assertEqual(p['next_check']['design'],'counter')
  self.assertNotIn('18',p['next_check']['requirements'])
 def bundle(self,folder,task,log,rc=0,**changes):
  receipt={'schema':'verieda.verifier-receipt.v1','task_id':task['task_id'],'inputs':task['inputs'],
   'engine_sha256':task['inputs']['engine_sha256'], 'return_code':rc,'runtime_seconds':1.0,'log_path':'proof.log'}
  receipt.update(changes)
  data={'receipt.json':json.dumps(receipt).encode(),'proof.log':log.encode()}
  data['file-sizes.json']=json.dumps([{'path':n,'bytes':len(b)} for n,b in data.items()]).encode()
  data['SHA256SUMS.txt']=''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in data.items()).encode()
  p=pathlib.Path(folder)/'proof.zip'
  with zipfile.ZipFile(p,'x',zipfile.ZIP_DEFLATED) as z:
   for n,b in data.items():z.writestr(n,b)
  return p,hashlib.sha256(p.read_bytes()).hexdigest()
 def test_raw_unbounded_marker_never_becomes_proof_pass_or_auto_physical(self):
  s=self.subject();task=v.plan_verification(s,300)['next_check']
  with tempfile.TemporaryDirectory() as tmp:
   p,h=self.bundle(tmp,task,'Induction step proven: SUCCESS!')
   plan=v.plan_verification(s,300,p,h)
   self.assertEqual(plan['decision'],'REVIEW_FORMAL_SCOPE')
   self.assertEqual(plan['gates']['formal'],'UNKNOWN');self.assertIsNone(plan['next_check'])
   self.assertEqual(plan['observation']['observation'],'UNBOUNDED_PROOF_REPORTED')
 def test_bmc_failure_and_timeout_do_not_trigger_auto_retry(self):
  s=self.subject();task=v.plan_verification(s,300)['next_check']
  for log,rc,decision in [('SAT proof finished - no model found: SUCCESS!',0,'REVIEW_UNPROVEN'),('Model found for base case: FAIL!',1,'REVIEW_COUNTEREXAMPLE'),('',124,'STOP_REVIEW_TIMEOUT'),('child killed: illegal instruction',2,'STOP_REVIEW_TOOL_FAILURE')]:
   with tempfile.TemporaryDirectory() as tmp:
    p,h=self.bundle(tmp,task,log,rc)
    plan=v.plan_verification(s,600,p,h)
    self.assertEqual(plan['decision'],decision);self.assertIsNone(plan['next_check']);self.assertFalse(plan['execution_authorized'])
 def test_wrong_target_or_old_proof_or_bad_runtime_is_held(self):
  s=self.subject();task=v.plan_verification(s,300)['next_check']
  bad=copy.deepcopy(task['inputs']);bad['netlist_sha256']=self.state['inputs']['6_final.v']
  for changes in ({'inputs':bad},{'task_id':'a'*64},{'runtime_seconds':float('nan')},{'return_code':True},{'engine_sha256':'0'*64}):
   with tempfile.TemporaryDirectory() as tmp:
    p,h=self.bundle(tmp,task,'Induction step proven: SUCCESS!',**changes)
    plan=v.plan_verification(s,300,p,h)
    self.assertEqual(plan['decision'],'HOLD_VERIFIER_EVIDENCE')
 def test_materializer_exports_exact_candidate_only_and_refuses_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'request'
   m=v.prepare_verification(self.state,RESULT,RESULT_SHA,out,300)
   self.assertEqual(set(m['files']),{'subject.json','plan.json','candidate.v','candidate.odb'})
   for n,h in m['files'].items():self.assertEqual(hashlib.sha256((out/n).read_bytes()).hexdigest(),h)
   self.assertEqual(hashlib.sha256((out/'candidate.v').read_bytes()).hexdigest(),self.subject()['target']['netlist_sha256'])
   self.assertNotIn('6_final.v',m['files'])
   with self.assertRaises(ValueError):v.prepare_verification(self.state,RESULT,RESULT_SHA,out,300)
 def test_corrupt_verifier_zip_and_wrong_sha_stay_structured_hold(self):
  s=self.subject()
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'not.zip';p.write_bytes(b'NOT A ZIP')
   h=hashlib.sha256(p.read_bytes()).hexdigest()
   self.assertEqual(v.plan_verification(s,300,p,h)['decision'],'HOLD_VERIFIER_EVIDENCE')
   self.assertEqual(v.plan_verification(s,300,p,'0'*64)['decision'],'HOLD_VERIFIER_EVIDENCE')
 def test_missing_contract_holds_without_old_proof_fallback(self):
  s=self.subject();s['formal_contract']=None;s['subject_id']=digest({k:x for k,x in s.items() if k!='subject_id'})
  self.assertEqual(v.plan_verification(s,300)['decision'],'HOLD_DECLARE_FORMAL_CONTRACT')
 def test_mutated_task_cannot_drive_verifier_observation(self):
  s=self.subject();task=v.plan_verification(s,300)['next_check'];task['cap_seconds']=900
  with tempfile.TemporaryDirectory() as tmp:
   p,h=self.bundle(tmp,task,'Induction step proven: SUCCESS!')
   with self.assertRaises(ValueError):v.observe_verification(task,p,h)
 def test_feedback_automatically_offers_bound_verification_request(self):
  from verieda.action_results import advance_action
  r=advance_action(self.state,RESULT,RESULT_SHA,600)
  self.assertEqual(r['verification_handoff']['decision'],'PREPARE_FORMAL_CHECK')
  self.assertEqual(r['verification_handoff']['next_check']['inputs']['netlist_sha256'],self.subject()['target']['netlist_sha256'])
 def test_verifier_handoff_can_be_checked_before_native_initialization(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'request';v.prepare_verification(self.state,RESULT,RESULT_SHA,out,300)
   self.assertEqual(v.verify_verification_package(out)['input_gate'],'PASS')
   (out/'candidate.v').write_bytes(b'mutated')
   with self.assertRaises(ValueError):v.verify_verification_package(out)
 def test_handoff_rejects_unrelated_files_and_wrong_plan(self):
  for mutation in ('extra','plan'):
   with tempfile.TemporaryDirectory() as tmp:
    out=pathlib.Path(tmp)/'request';v.prepare_verification(self.state,RESULT,RESULT_SHA,out,300)
    if mutation=='extra':(out/'unrelated.txt').write_text('exclude')
    else:(out/'plan.json').write_text('{}')
    with self.assertRaises(ValueError):v.verify_verification_package(out)
 def test_malformed_handoff_json_returns_cli_unknown(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'request';v.prepare_verification(self.state,RESULT,RESULT_SHA,out,300)
   (out/'manifest.json').write_text('[]')
   p=subprocess.run([sys.executable,'-m','verieda','inspect-verification',str(out)],cwd=ROOT,capture_output=True,timeout=20)
   self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['status'],'UNKNOWN')
 def test_lifecycle_scopes_candidate_holds_without_stopping_project(self):
  r=v.review_candidate(self.state,RESULT,RESULT_SHA,300)
  self.assertEqual(r['candidate_status'],'VERIFY_PENDING_CANDIDATE')
  self.assertEqual(r['operation_status'],'WAITING_FOR_AUTHORIZATION')
  self.assertEqual(r['block_scope'],'CANDIDATE_ONLY');self.assertFalse(r['execution_authorized'])
  stopped=v.review_candidate(self.state,RESULT,RESULT_SHA,0)
  self.assertEqual(stopped['candidate_status'],'STOPPED_FOR_BUDGET')
  self.assertNotEqual(stopped['candidate_status'],'ACCEPTED')
 def test_lifecycle_rejects_same_reference_as_new_full_acceptance(self):
  r=v.review_candidate(self.state,RESULT,RESULT_SHA,300,after_state=self.state)
  self.assertEqual(r['candidate_status'],'REJECTED');self.assertEqual(r['design_acceptance'],'REJECTED')
  self.assertIn('NO_INDEPENDENT_EXECUTION_EVIDENCE',r['adoption']['rejections'])
 def test_cli_lifecycle_keeps_missing_or_forged_verifier_evidence_as_error(self):
  args=['review-candidate','--profile','cases/gcd.json','--smoke',str(SMOKE),'--acceptance',str(NATIVE),'--result',str(RESULT),'--expected-sha256',RESULT_SHA,'--budget-seconds','300','--formal-result','__missing__','--formal-sha256','0'*64]
  p=subprocess.run([sys.executable,'-m','verieda',*args],cwd=ROOT,capture_output=True,timeout=20)
  self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['candidate_status'],'EVIDENCE_HOLD')
 def test_cli_real_saved_result_is_read_only_and_structured(self):
  p=subprocess.run([sys.executable,'-m','verieda','verify-next','--profile','cases/gcd.json','--smoke',str(SMOKE),'--acceptance',str(NATIVE),'--result',str(RESULT),'--expected-sha256',RESULT_SHA,'--budget-seconds','300'],cwd=ROOT,capture_output=True,timeout=20)
  self.assertEqual(p.returncode,0,p.stderr.decode());r=json.loads(p.stdout)
  self.assertEqual(r['decision'],'PREPARE_FORMAL_CHECK');self.assertFalse(r['execution_authorized'])

if __name__=='__main__':unittest.main()
