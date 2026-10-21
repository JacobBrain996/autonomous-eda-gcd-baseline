"""Synthetic native bundles test import policy, not EDA correctness."""
import hashlib,json,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

class NativeEvidenceTests(unittest.TestCase):
    def fixture(self,root,extra=None):
        payload={
            'final-acceptance/execution-source.json':json.dumps({'GITHUB_REPOSITORY':'test/repo','GITHUB_RUN_ID':'12','GITHUB_SHA':'a'*40,'GITHUB_RUN_ATTEMPT':'1','RUNNER_OS':'Linux','RUNNER_ARCH':'X64'}),
            'final-acceptance/container-return-code.txt':'0',
            'final-acceptance/output/result.json':json.dumps({'TIMING_GATE':'PASS','FORMAL_EQUIVALENCE_GATE':'PASS_RESET_CONTRACT_UNBOUNDED','baseline_pass':True}),
            'final-acceptance/output/sta/wns.rpt':'wns max -0.161583',
            'final-acceptance/output/sta/tns.rpt':'tns max -7.08646',
            'final-acceptance/output/formal/proof.log':'Induction step proven: SUCCESS!',
            'final-acceptance/output/formal/proof.log.status.json':'{"return_code":0}',
        }
        payload.update(extra or {})
        for n,v in payload.items():
            p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(v,encoding='utf-8')
        files=list(root.rglob('*'));files=[p for p in files if p.is_file()]
        (root/'file-sizes.json').write_text(json.dumps([{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size} for p in files]))
        files.append(root/'file-sizes.json')
        (root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files))
    def inspect(self,p,**kwargs):
        from verieda.native import inspect_acceptance
        return inspect_acceptance(p,**kwargs)
    def test_raw_timing_vetoes_forged_summary_and_proof_log_is_not_certification(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);s=self.inspect(p)
            self.assertEqual(s['gates']['evidence'],'PASS')
            self.assertEqual(s['gates']['timing'],'FAIL')
            self.assertEqual(s['gates']['formal'],'UNKNOWN')
            self.assertEqual(s['formal_observation']['observation'],'UNBOUNDED_PROOF_REPORTED')
            self.assertEqual(s['acceptance'],'NOT_ACCEPTED')
            self.assertIn('SUMMARY_CONTRADICTION',[x['kind'] for x in s['issues']])
    def test_real_final_bundle_exposes_missing_checker_capabilities_and_empty_coverage(self):
        from test_case import NATIVE
        s=self.inspect(NATIVE,expected_archive_sha='58b83ba6a4253323b5f3768197c1b7e832bbe5faebc09c3f8071d46b25fc6566')
        r=s['validation_coverage']
        self.assertEqual(r['coverage_report']['status'],'EMPTY_NOT_A_CERTIFICATE')
        self.assertEqual(r['coverage_report']['bytes'],0)
        self.assertEqual(r['checker_capabilities']['independent_hold'],'OFFLINE_OBSERVER_IMPLEMENTED_NATIVE_UNVALIDATED')
        self.assertEqual(r['checker_capabilities']['constraint_coverage_certification'],'NOT_IMPLEMENTED')
        self.assertFalse(r['can_certify_full_final_acceptance'])
        self.assertEqual(r['coverage_gate'],'UNKNOWN');self.assertEqual(s['gates']['timing'],'FAIL')
        self.assertIn('original_to_final_constraint_semantics',r['required_observations'])
    def test_nonempty_or_success_claimed_coverage_does_not_implement_missing_checker(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{
                'final-acceptance/output/sta/coverage.rpt':'All checks PASS. All ports constrained.',
                'final-acceptance/output/sta/hold.rpt':'wns min 0',
                'final-acceptance/output/sta/constraint-inventory.json':'{"coverage_gate":"PASS"}'})
            r=self.inspect(p)['validation_coverage']
            self.assertEqual(r['coverage_report']['status'],'PRESENT_UNINTERPRETED')
            self.assertEqual(r['coverage_gate'],'UNKNOWN')
            self.assertFalse(r['can_certify_full_final_acceptance'])
    def hold_log(self,wns='0',tns='0'):
        return ('VERIEDA_REPORT_BEGIN units\ntime 1ns\nVERIEDA_REPORT_END units\n'
                'VERIEDA_REPORT_BEGIN hold_wns\nwns min '+wns+'\nVERIEDA_REPORT_END hold_wns\n'
                'VERIEDA_REPORT_BEGIN hold_tns\ntns min '+tns+'\nVERIEDA_REPORT_END hold_tns\n')
    def test_hold_observer_distinguishes_violation_timeout_error_and_unproven_zero(self):
        from verieda.sta_min import observe_hold
        self.assertEqual(observe_hold(0,self.hold_log('-0.01','-0.02'))['hold_gate'],'FAIL')
        r=observe_hold(0,self.hold_log());self.assertEqual(r['observation'],'NO_NEGATIVE_HOLD_REPORTED')
        self.assertEqual(r['hold_gate'],'UNKNOWN');self.assertIsNone(r['worst_hold_slack_ns'])
        self.assertEqual(observe_hold(124,self.hold_log())['observation'],'TIMEOUT')
        self.assertEqual(observe_hold(1,self.hold_log())['observation'],'TOOL_ERROR')
    def test_hold_parser_rejects_ambiguous_units_metrics_markers_and_missing_reports(self):
        from verieda.sta_min import observe_hold
        logs=[self.hold_log().replace('time 1ns','time 1ps'),self.hold_log('nan','0'),
              self.hold_log('0.01','0'),self.hold_log('-0.02','-0.01'),self.hold_log('-0.01','0'),
              self.hold_log()+self.hold_log(),self.hold_log().replace('time 1ns','time 1ns\ntime 1ps'),self.hold_log().replace('VERIEDA_REPORT_END hold_tns','')]
        for log in logs:
            with self.subTest(log=log):self.assertEqual(observe_hold(0,log)['observation'],'HOLD_REPORT_FORMAT')
    def test_hold_collector_keeps_exact_validated_initialization_and_supported_min_commands(self):
        import zipfile
        from verieda.sta_min import build_hold_script
        from test_case import NATIVE
        script=build_hold_script()
        self.assertTrue(script.startswith((ROOT/'acceptance/sta.tcl').read_bytes()))
        self.assertIn(b'report_wns -min -digits 9',script);self.assertIn(b'report_tns -min -digits 9',script)
        self.assertIn(b'report_checks -path_delay min',script)
        with zipfile.ZipFile(NATIVE) as z:
            help_text=z.read('final-acceptance/output/sta/tool.log')
        self.assertIn(b'report_wns [-min] [-max]',help_text)
        self.assertIn(b'report_tns [-min] [-max]',help_text)
    def test_optional_bound_hold_status_is_observed_without_final_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{
                'final-acceptance/output/sta/hold.log':self.hold_log('-0.01','-0.03'),
                'final-acceptance/output/sta/hold.log.status.json':'{"return_code":0}'})
            r=self.inspect(p);self.assertEqual(r['hold_observation']['hold_gate'],'FAIL')
            self.assertFalse(r['validation_coverage']['can_certify_full_final_acceptance'])
    def test_changed_payload_fails_integrity_before_observations(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);(p/'final-acceptance/output/sta/wns.rpt').write_text('wns max 1')
            s=self.inspect(p);self.assertEqual(s['gates']['evidence'],'FAIL');self.assertNotIn('formal_observation',s)
    def test_incomplete_bundle_is_hold_not_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'final-acceptance/output/formal/proof.log.status.json':'{}'})
            s=self.inspect(p);self.assertEqual(s['gates']['formal'],'UNKNOWN');self.assertNotIn('formal_observation',s)
            self.assertIn('FORMAL_EVIDENCE_INCOMPLETE',[x['kind'] for x in s['issues']])
    def test_duplicate_status_and_noninteger_return_codes_are_rejected(self):
        for status in ['{"return_code":0,"return_code":124}','{"return_code":true}','{"return_code":0.0}']:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);self.fixture(p,{'final-acceptance/output/formal/proof.log.status.json':status})
                self.assertNotIn('formal_observation',self.inspect(p))
    def test_timeout_and_signal_remain_distinct(self):
        for rc,expected in [(124,'TIMEOUT'),(-4,'TOOL_SIGNAL'),(137,'KILLED_UNKNOWN')]:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);self.fixture(p,{'final-acceptance/output/formal/proof.log.status.json':json.dumps({'return_code':rc})})
                self.assertEqual(self.inspect(p)['formal_observation']['observation'],expected)
    def test_positive_setup_does_not_establish_hold_or_full_timing_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'final-acceptance/output/sta/wns.rpt':'wns max 0','final-acceptance/output/sta/tns.rpt':'tns max 0'})
            s=self.inspect(p);self.assertEqual(s['gates']['timing'],'UNKNOWN');self.assertNotEqual(s['acceptance'],'PASS')
    def test_ambiguous_or_inconsistent_timing_is_not_promoted(self):
        for w,t in [('wns max nan','tns max -1'),('wns max 0\nwns max -1','tns max -1'),('wns max 0','tns max -1'),('wns max -1','tns max 1')]:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);self.fixture(p,{'final-acceptance/output/sta/wns.rpt':w,'final-acceptance/output/sta/tns.rpt':t})
                self.assertEqual(self.inspect(p)['gates']['timing'],'UNKNOWN')
    def test_claimed_execution_identity_is_never_authentication(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);s=self.inspect(p)
            self.assertEqual(s['gates']['identity'],'UNKNOWN')
            self.assertEqual(s['execution_claim']['GITHUB_RUN_ID'],'12')
    def test_cli_reports_integrity_error_as_nonzero_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);(p/'extra').write_text('unsealed')
            r=subprocess.run([sys.executable,'-m','verieda','inspect-acceptance',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,2);self.assertEqual(json.loads(r.stdout)['gates']['evidence'],'FAIL')
    def test_trusted_zip_digest_does_not_authenticate_execution_or_proof(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);p=root/'bundle';p.mkdir();self.fixture(p)
            z=root/'bundle.zip'
            with zipfile.ZipFile(z,'w') as out:
                for f in p.rglob('*'):
                    if f.is_file():out.write(f,f.relative_to(p).as_posix())
            s=self.inspect(z,expected_archive_sha=hashlib.sha256(z.read_bytes()).hexdigest())
            self.assertEqual(s['evidence']['trust'],'EXPECTED_ARCHIVE_SHA256')
            self.assertEqual(s['gates']['identity'],'UNKNOWN');self.assertEqual(s['gates']['formal'],'UNKNOWN')
            self.assertEqual(self.inspect(z,expected_archive_sha='0'*64)['gates']['evidence'],'FAIL')
    def test_cli_zero_means_observation_completed_not_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p)
            r=subprocess.run([sys.executable,'-m','verieda','inspect-acceptance',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['acceptance'],'NOT_ACCEPTED')

if __name__=='__main__':unittest.main()
