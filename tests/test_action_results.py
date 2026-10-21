"""Synthetic process fixtures test recovery semantics, never EDA efficacy."""
import copy,json,pathlib,sys,tempfile,unittest,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.case import load_case
from verieda.policy import propose
from verieda.execution import prepare_action,make_argv
from verieda.action_results import seal_action,inspect_action
from test_case import SMOKE,NATIVE

class ActionResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
        cls.candidate=propose(cls.state,600,[])['selected_candidate']
    def fixture(self,root,status='SYNTHESIS_COMPLETED'):
        bundle=root/'package';manifest=prepare_action(self.state,self.candidate,bundle);work=root/'output';work.mkdir()
        (work/'effective.log').write_bytes(b'ABC_AREA=0\nLEC_CHECK=1\nSEC_CHECK=1\nPLATFORM=nangate45\nDESIGN_NAME=gcd\nYOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys\nOPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad\nPYTHON_EXE=/usr/bin/python3\n')
        (work/'synth.log').write_bytes(b'Using ABC speed script.\nsynthetic process fixture\n')
        net='results/nangate45/gcd/verieda/1_2_yosys.v';odb='results/nangate45/gcd/verieda/1_synth.odb'
        for name in (net,odb):
            p=work/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'SYNTHETIC_ONLY_NOT_EDA\n')
        sha=lambda p:hashlib.sha256((work/p).read_bytes()).hexdigest()
        sources={**manifest['support']['sources'],'flow/designs/src/gcd/gcd.v':self.state['frozen']['rtl_sha256'],
                 'flow/designs/nangate45/gcd/constraint.sdc':self.state['frozen']['sdc_sha256'],**self.state['tools']}
        steps=[{'argv':make_argv('/package/effective.mk','/work/action',target),'return_code':0,'timeout':False,'signal':None,
                'runtime_seconds':1.0,'log_sha256':sha(log)} for target,log in [('verieda-effective','effective.log'),('synth','synth.log')]]
        receipt={'schema':'verieda.action-execution.v0','state_id':self.state['state_id'],'candidate_id':self.candidate['candidate_id'],
                 'changes':self.candidate['changes'],'phase':'SYNTHESIS_ONLY','status':status,'return_code':0,'steps':steps,
                 'runtime_seconds':2.1,'source_tool_sha256':sources,'design_acceptance':'NOT_EVALUATED',
                 'FORMAL_EQUIVALENCE_GATE':'NOT_RUN','TIMING_GATE':'NOT_RUN','OCI_IDENTITY_GATE':'HOST_RECORD_MATCH_NOT_ATTESTED',
                 'netlist_path':net,'netlist_sha256':sha(net),'odb_path':odb,'odb_sha256':sha(odb)}
        self.write_receipt(work,receipt);return bundle,work,receipt
    def write_receipt(self,work,r):
        (work/'action-execution.json').write_text(json.dumps(r)+'\n',encoding='utf-8')
    def inspect(self,root,bundle,work):
        zip_path=root/'result.zip';info=seal_action(bundle,work,zip_path)
        return inspect_action(zip_path,info['sha256'],self.candidate['candidate_id'])
    def test_synthesis_is_only_partial_and_unrelated_files_are_not_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root);(w/'private-unrelated.txt').write_text('must not collect')
            r=self.inspect(root,b,w)
            self.assertEqual(r['status'],'SYNTHESIS_COMPLETED');self.assertEqual(r['design_acceptance'],'NOT_EVALUATED')
            self.assertEqual(r['history_record']['outcome'],'UNKNOWN');self.assertFalse(r['execution_authorized'])
            self.assertNotIn('private-unrelated.txt',str(r['files']))
            feedback=propose(self.state,600,[r['history_record']]);self.assertEqual(feedback['decision'],'STOP_BUDGET')
    def test_not_run_has_no_fabricated_cost_or_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b=root/'package';prepare_action(self.state,self.candidate,b);w=root/'output';w.mkdir()
            (w/'launcher-result.json').write_text(json.dumps({'status':'NOT_RUN','candidate_id':self.candidate['candidate_id'],'phase':'SYNTHESIS_ONLY','requires_explicit_execution':True}))
            r=self.inspect(root,b,w);self.assertEqual(r['status'],'NOT_RUN');self.assertIsNone(r['history_record'])
    def test_failed_process_timeout_and_signal_remain_distinct(self):
        for kind,rc,timeout,signal,want in [('timeout',124,True,9,'TIMEOUT'),('sigill',-4,False,4,'TOOL_SIGNAL'),('error',2,False,None,'ERROR')]:
            with tempfile.TemporaryDirectory() as tmp:
                root=pathlib.Path(tmp);b,w,r=self.fixture(root,'TIMEOUT' if timeout else 'ERROR')
                r.update(return_code=rc);r['steps'][-1].update(return_code=rc,timeout=timeout,signal=signal)
                self.write_receipt(w,r);got=self.inspect(root,b,w)
                self.assertEqual(got['status'],want,kind);self.assertNotEqual(got['history_record']['outcome'],'ACCEPTED')
    def test_false_success_foreign_identity_and_bad_runtime_cannot_enter_history(self):
        for mutation in ('missing_netlist','wrong_log','foreign','nan','wrong_command','missing_odb','wrong_effective','inconsistent_signal'):
            with tempfile.TemporaryDirectory() as tmp:
                root=pathlib.Path(tmp);b,w,r=self.fixture(root)
                if mutation=='missing_netlist':(w/r['netlist_path']).unlink()
                elif mutation=='missing_odb':(w/r['odb_path']).unlink()
                elif mutation=='wrong_log':r['steps'][-1]['log_sha256']='0'*64
                elif mutation=='foreign':r['candidate_id']='foreign'
                elif mutation=='nan':r['runtime_seconds']=float('nan')
                elif mutation=='wrong_effective':
                    (w/'effective.log').write_bytes(b'LEC_CHECK=0\n')
                    r['steps'][0]['log_sha256']=hashlib.sha256((w/'effective.log').read_bytes()).hexdigest()
                elif mutation=='inconsistent_signal':r['steps'][-1]['signal']=4
                else:r['steps'][-1]['argv']=['arbitrary','command']
                self.write_receipt(w,r);got=self.inspect(root,b,w)
                self.assertIsNone(got['history_record'],mutation);self.assertEqual(got['status'],'UNKNOWN',mutation)
    def test_archive_tampering_or_foreign_expected_candidate_fails_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root);z=root/'r.zip';info=seal_action(b,w,z)
            r=inspect_action(z,'0'*64,self.candidate['candidate_id']);self.assertEqual(r['evidence_gate'],'FAIL')
            r=inspect_action(z,info['sha256'],'different');self.assertIsNone(r['history_record'])
            with self.assertRaises(ValueError):seal_action(b,w,z)
    def test_missing_package_file_does_not_escape_structured_seal_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root);(b/'state.json').unlink()
            with self.assertRaises(ValueError):seal_action(b,w,root/'invalid.zip')
    def test_historical_source_hash_is_preserved_not_replaced_by_current_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root)
            m=json.loads((b/'manifest.json').read_text());m['adapter_sources']['execution.py']='a'*64
            (b/'manifest.json').write_text(json.dumps(m))
            r=self.inspect(root,b,w);self.assertEqual(r['historical_adapter_sources']['execution.py'],'a'*64)
            self.assertEqual(r['status'],'SYNTHESIS_COMPLETED')
    def test_oversized_allowed_payload_is_rejected_without_collecting_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root)
            with (w/'synth.log').open('wb') as f:f.truncate(16*1024*1024+1)
            with self.assertRaises(ValueError):seal_action(b,w,root/'oversized.zip')
    def test_feedback_tracks_pending_verification_and_is_idempotent(self):
        from verieda.action_results import advance_action
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root);z=root/'r.zip';info=seal_action(b,w,z)
            r=advance_action(self.state,z,info['sha256'],600,[])
            self.assertEqual(r['decision'],'VERIFY_PENDING_CANDIDATE');self.assertFalse(r['execution_authorized'])
            self.assertEqual(len(r['history']),1);self.assertAlmostEqual(r['budget']['remaining_seconds'],597.9)
            again=advance_action(self.state,z,info['sha256'],600,r['history'])
            self.assertEqual(again['history'],r['history']);self.assertEqual(again['budget'],r['budget'])
            self.assertEqual(again['pending_verifiers']['formal_new_netlist'],'NOT_RUN')
            exhausted=advance_action(self.state,z,info['sha256'],0,r['history'])
            self.assertEqual(exhausted['decision'],'STOP_BUDGET')
    def test_feedback_cannot_silently_replace_conflicting_outcome_or_trust_bad_zip(self):
        from verieda.action_results import advance_action
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);b,w,_=self.fixture(root);z=root/'r.zip';info=seal_action(b,w,z)
            row={'state_id':self.state['state_id'],'candidate_id':self.candidate['candidate_id'],'outcome':'ERROR','runtime_seconds':1}
            r=advance_action(self.state,z,info['sha256'],600,[row]);self.assertEqual(r['decision'],'HOLD_CONFLICTING_HISTORY')
            r=advance_action(self.state,z,'0'*64,600,[]);self.assertEqual(r['decision'],'HOLD_RESULT_EVIDENCE');self.assertEqual(r['history'],[])
    def test_contradictory_launcher_or_preflight_timeout_cannot_enter_history(self):
        for mutation in ('launcher','preflight_timeout'):
            with tempfile.TemporaryDirectory() as tmp:
                root=pathlib.Path(tmp);b,w,r=self.fixture(root)
                if mutation=='launcher':
                    (w/'launcher-result.json').write_text(json.dumps({'candidate_id':self.candidate['candidate_id'],'phase':'SYNTHESIS_ONLY','status':'NOT_RUN'}))
                else:r['steps'][0]['timeout']=True;self.write_receipt(w,r)
                observed=self.inspect(root,b,w)
                self.assertEqual(observed['status'],'UNKNOWN',mutation);self.assertIsNone(observed['history_record'],mutation)

if __name__=='__main__':unittest.main()
