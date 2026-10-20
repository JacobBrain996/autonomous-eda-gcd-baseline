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
