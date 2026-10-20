import json,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class InterfaceCLITests(unittest.TestCase):
    def cli(self,*args):
        p=subprocess.run([sys.executable,'-m','verieda',*map(str,args)],cwd=ROOT,capture_output=True,timeout=10)
        return p.returncode,json.loads(p.stdout)
    def test_real_constraint_profile_cli_does_not_certify_native_context(self):
        p=ROOT/'evidence/smoke-9644bb3f8ed4/artifact/gds/6_final.sdc';rc,result=self.cli('compare-constraints',p,p)
        self.assertEqual(rc,0);self.assertEqual(result['full_constraint_gate'],'UNKNOWN')
        self.assertEqual(result['reference_file_sha256'],'112a077b756cada0fab67b2061733207a9cd7ac99b3e98454cabcad5aec7aa77')
    def test_changed_fixture_constraint_cli_is_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            a=pathlib.Path(d)/'a.sdc';b=pathlib.Path(d)/'b.sdc'
            a.write_text('current_design x\ncreate_clock -name c -period 0.25 [get_ports clk]\n')
            b.write_text(a.read_text().replace('0.25','0.5'))
            rc,r=self.cli('compare-constraints',a,b);self.assertEqual(rc,1);self.assertEqual(r['comparison'],'DIFFERENT')
    def test_reported_counterexample_is_not_a_certified_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'synthetic-only.log';p.write_text('SAT temporal induction proof finished - model found for base case: FAIL!')
            rc,r=self.cli('observe-formal',p,'--return-code','1')
            self.assertEqual(r['observation'],'COUNTEREXAMPLE_REPORTED');self.assertEqual(r['formal_gate'],'UNKNOWN')
    def test_missing_file_is_structured_unknown(self):
        rc,r=self.cli('observe-formal','__nonexistent_verieda_fixture__','--return-code','0')
        self.assertEqual(rc,2);self.assertEqual(r['status'],'UNKNOWN')
if __name__=='__main__':unittest.main()
