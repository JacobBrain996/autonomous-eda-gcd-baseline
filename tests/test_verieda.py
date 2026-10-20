import importlib.util, pathlib, sys, tempfile, unittest, zipfile, json, hashlib
ROOT=pathlib.Path('E:/AUTONOMOUS_EDA_V1/workspace/autonomous-eda-gcd-baseline')
sys.path.insert(0,str(ROOT))

class VeriEDATests(unittest.TestCase):
    def core(self):
        from verieda.evidence import inspect
        return inspect
    def fixture(self,root,overrides=None):
        values={'manifest.json':json.dumps({'design':'test','platform':'test','orfs_commit':'abc','orfs_commit_actual':'abc','orfs_image':'image@sha256:abc','container_repo_digests_actual':['image@sha256:abc']}),
          'raw-logs/orfs-logs/6_report.json':json.dumps({'finish__timing__setup__ws':-0.1,'finish__timing__setup__tns':-1,'finish__timing__hold__ws':0.1,'finish__timing__hold__tns':0,'finish__design__instance__area__stdcell':10}),
          'raw-logs/orfs-logs/5_2_route.json':'{"detailedroute__route__drc_errors":0}',
          'gates.json':'{"TIMING_GATE":"PASS","FORMAL_EQUIVALENCE_GATE":"PASS"}',
          'status/physical-return-code.txt':'0','status/simulation-return-code.txt':'0',
          'raw-logs/rtl-simulation.log':'TESTED_PASS cases=76',
          'gds/6_final.gds':b'\x00\x06\x00\x02\x02\x58\x00\x04\x04\x00',
          'gds/6_final.odb':b'db','gds/6_final.sdc':'create_clock -name clk -period 0.25 [get_ports clk]',
          'status/gds-read-return-code.txt':'0','raw-logs/gds-read.log':'GDS_READ_GATE=PASS'}
        values.update(overrides or {})
        for n,v in values.items():
            p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v.encode() if isinstance(v,str) else v)
        payload=[p for p in root.rglob('*') if p.is_file()]
        (root/'file-sizes.json').write_text(json.dumps([{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size} for p in payload]))
        payload.append(root/'file-sizes.json')
        (root/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in payload))
    def test_cli_module_exists(self):self.assertTrue((ROOT/'verieda/evidence.py').is_file())
    def test_raw_timing_vetoes_claimed_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);s=self.core()(p)
            self.assertEqual(s['gates']['timing'],'FAIL');self.assertEqual(s['gates']['formal'],'UNKNOWN');self.assertEqual(s['acceptance'],'NOT_ACCEPTED')
    def test_tamper_is_evidence_failure_not_design_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p);(p/'gds/6_final.odb').write_bytes(b'tampered')
            s=self.core()(p);self.assertEqual(s['gates']['evidence'],'FAIL');self.assertEqual(s['gates']['timing'],'UNKNOWN')
    def test_timeout_and_sigill_are_distinct(self):
        for rc,kind in [('124','TIMEOUT'),('132','TOOL_SIGNAL')]:
            with tempfile.TemporaryDirectory() as d:
                p=pathlib.Path(d);self.fixture(p,{'status/physical-return-code.txt':rc});s=self.core()(p)
                self.assertEqual(s['gates']['physical'],'ERROR');self.assertIn(kind,[x['kind'] for x in s['issues']])
    def test_sigkill_is_not_assumed_to_be_timeout_or_oom(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'status/physical-return-code.txt':'137'});s=self.core()(p)
            self.assertIn('KILLED_UNKNOWN',[x['kind'] for x in s['issues']])
    def test_wrong_json_shape_does_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'raw-logs/orfs-logs/6_report.json':'[]'});s=self.core()(p)
            self.assertIn('EVIDENCE_SEMANTIC_ERROR',[x['kind'] for x in s['issues']])
    def test_positive_timing_does_not_imply_formal_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'raw-logs/orfs-logs/6_report.json':json.dumps({'finish__timing__setup__ws':0.1,'finish__timing__setup__tns':0,'finish__timing__hold__ws':0.1,'finish__timing__hold__tns':0})});s=self.core()(p)
            self.assertEqual(s['gates']['timing'],'PASS');self.assertEqual(s['acceptance'],'UNKNOWN')
    def test_missing_timing_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'raw-logs/orfs-logs/6_report.json':'{}'});s=self.core()(p)
            self.assertEqual(s['gates']['timing'],'UNKNOWN')
    def test_duplicate_relevant_metric_is_not_silently_last_wins(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);self.fixture(p,{'raw-logs/orfs-logs/6_report.json':'{"finish__timing__setup__ws":1,"finish__timing__setup__ws":-1}'});s=self.core()(p)
            self.assertEqual(s['metrics']['setup_slack']['status'],'AMBIGUOUS');self.assertEqual(s['gates']['timing'],'UNKNOWN')
    def test_zip_path_escape_is_rejected_without_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'bad.zip'
            with zipfile.ZipFile(p,'w') as z:z.writestr('../escape','x')
            self.assertEqual(self.core()(p)['gates']['evidence'],'FAIL')
    def test_real_smoke_zip_matches_directory(self):
        e=ROOT/'evidence/smoke-9644bb3f8ed4'
        a=self.core()(e/'artifact',ROOT/'experiment_identity.json')
        b=self.core()(e/'NO_LEC_SMOKE-38226418563.zip',ROOT/'experiment_identity.json')
        self.assertEqual(a['gates'],b['gates']);self.assertEqual(a['metrics']['WNS']['value'],-0.161583)
        self.assertEqual(a['metrics']['stdcell_area']['value'],943.502);self.assertEqual(a['gates']['formal'],'NOT_RUN')
        self.assertEqual(len(a['critical_paths']),2)
        self.assertEqual(a['metrics']['setup_endpoint_count']['value'],51)
        self.assertEqual(a['cost']['physical_runtime_seconds'],68)

if __name__=='__main__':unittest.main()
