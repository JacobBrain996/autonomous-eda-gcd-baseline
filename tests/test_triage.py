"""Failure-aware software checks; no fault ELF or ISA hypothesis is proved."""
import hashlib,json,pathlib,sys,tempfile,unittest,zipfile,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda import triage as t
RUN1=ROOT/'evidence/run1/orfs-gcd-baseline-run1.zip'
RUN1_SHA='9caa14593d6c9db005db2807d8fddd7558c183ccbdc2b9f9faedf4cd1f4481d5'
class TriageTests(unittest.TestCase):
 def test_actual_make_wrapped_sigill_keeps_binary_and_isa_unknown(self):
  r=t.diagnose(RUN1,RUN1_SHA)
  self.assertEqual(r['evidence_gate'],'PASS');self.assertEqual(r['next_action'],'REVIEW_REPORTED_SIGNAL')
  hit=next(x for x in r['findings'] if x['kind']=='SIGNAL_REPORTED' and x['source']['path'].endswith('4_1_cts.log'))
  self.assertEqual(hit['source']['line'],288);self.assertEqual(hit['signal'],'SIGILL')
  self.assertEqual(r['faulting_executable'],'NOT_AVAILABLE');self.assertEqual(r['instruction_set_cause'],'NOT_ESTABLISHED')
  self.assertEqual(r['design_verdict'],'NOT_EVALUATED');self.assertFalse(r['execution_authorized'])
 def test_other_design_names_and_negative_diagnostics_do_not_change_classifier(self):
  r=t.analyze_logs({'raw-logs/other/cpu.log':b'No illegal instruction was observed.\nNo timeout occurred.\nUsing AVX2 without AVX512.\n'})
  self.assertEqual(r['findings'],[]);self.assertEqual(r['next_action'],'NO_FAILURE_CLASSIFIED')
 def test_timeout_model_gap_and_counterexample_require_different_review(self):
  for raw,expected in [(b'Interrupted SAT solver: TIMEOUT!','REVIEW_TIMEOUT'),(b'ERROR: Failed to import cell FOO','REVIEW_MODEL_OR_CAPABILITY'),(b'SAT temporal induction proof finished - model found for base case: FAIL!','REVIEW_COUNTEREXAMPLE')]:
   r=t.analyze_logs({'proof.log':raw});self.assertEqual(r['next_action'],expected);self.assertNotEqual(r['design_verdict'],'FAIL')
 def test_environment_help_and_readme_are_not_execution_logs(self):
  r=t.analyze_logs({'environment/help.txt':b'child killed: illegal instruction','README.md':b'child killed: illegal instruction'})
  self.assertEqual(r['findings'],[])
 def test_bad_checksum_or_zip_is_structured_hold(self):
  self.assertEqual(t.diagnose(RUN1,'0'*64)['evidence_gate'],'FAIL')
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'bad.zip';p.write_bytes(b'not zip')
   self.assertEqual(t.diagnose(p,hashlib.sha256(p.read_bytes()).hexdigest())['evidence_gate'],'FAIL')
 def test_receipt_timeout_cleanup_signal_is_not_oom_or_sigill(self):
  receipt={'schema':'verieda.verifier-receipt.v1','steps':[{'return_code':124,'child_return_code':-9,'signal':9,'timeout':True,'pid':123,'argv':['/tools/yosys']}]}
  r=t.analyze_logs({'receipt.json':json.dumps(receipt).encode()})
  self.assertEqual(r['next_action'],'REVIEW_TIMEOUT');self.assertFalse(any(x.get('signal')=='SIGILL' for x in r['findings']))
  self.assertEqual(r['faulting_executable'],'NOT_AVAILABLE')
 def test_contradictory_process_receipt_is_unknown_not_an_attributed_crash(self):
  receipt={'schema':'verieda.verifier-receipt.v1','steps':[{'return_code':0,'child_return_code':0,'signal':4,'timeout':False,'pid':123,'argv':['/tools/yosys']}]}
  r=t.analyze_logs({'receipt.json':json.dumps(receipt).encode()})
  self.assertEqual(r['analysis_gate'],'HOLD');self.assertEqual(r['faulting_executable'],'NOT_AVAILABLE')
 def test_exit_132_is_only_a_shell_encoding_hint(self):
  r=t.analyze_logs({'status/physical-return-code.txt':b'132\n'})
  self.assertEqual(r['findings'][0]['kind'],'POSSIBLE_SIGNAL_EXIT');self.assertEqual(r['faulting_executable'],'NOT_AVAILABLE')
 def test_receipt_admission_hold_cannot_disappear_when_no_process_started(self):
  data={'receipt.json':json.dumps({'schema':'verieda.verifier-receipt.v1','status':'HOLD_MODEL_OR_CONTRACT','steps':[]}).encode()}
  self.assertEqual(t.analyze_logs(data)['next_action'],'REVIEW_ADMISSION_HOLD')
 def test_boolean_signal_is_not_a_posix_signal_number(self):
  receipt={'schema':'verieda.verifier-receipt.v1','steps':[{'return_code':-1,'child_return_code':-1,'signal':True,'timeout':False}]}
  self.assertEqual(t.analyze_logs({'receipt.json':json.dumps(receipt).encode()})['analysis_gate'],'HOLD')
 def test_findings_do_not_export_log_content_or_borrow_hypothetical_isa_cause(self):
  r=t.analyze_logs({'proof.log':b'Error: child killed: illegal instruction secret-must-not-appear\n'})
  self.assertNotIn('secret-must-not-appear',json.dumps(r));self.assertEqual(r['instruction_set_cause'],'NOT_ESTABLISHED')
 def test_cli_real_run_is_read_only_and_json(self):
  p=subprocess.run([sys.executable,'-m','verieda','diagnose',str(RUN1),'--expected-sha256',RUN1_SHA],cwd=ROOT,capture_output=True,timeout=20)
  self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(json.loads(p.stdout)['next_action'],'REVIEW_REPORTED_SIGNAL')
if __name__=='__main__':unittest.main()
