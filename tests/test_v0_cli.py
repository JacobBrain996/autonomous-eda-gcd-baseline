import json,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SMOKE=ROOT/'evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip'
NATIVE=ROOT/'evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip'
PROFILE=ROOT/'cases/gcd.json'

class V0CLITests(unittest.TestCase):
    def cli(self,*args):
        p=subprocess.run([sys.executable,'-m','verieda',*map(str,args)],cwd=ROOT,capture_output=True,timeout=20)
        return p.returncode,json.loads(p.stdout)
    def test_real_plan_is_repeatable_and_produces_no_execution_authority(self):
        args=('plan','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--budget-seconds','600')
        rc,result=self.cli(*args);self.assertEqual(rc,0)
        self.assertEqual(result['state']['gates']['formal'],'PASS_RESET_CONTRACT_UNBOUNDED')
        self.assertEqual(result['decision']['decision'],'PROPOSAL_REQUIRES_PREPARATION')
        self.assertEqual(result['decision']['selected_candidate']['action'],'timing_mapping')
        self.assertFalse(result['decision']['execution_authorized'])
        self.assertEqual(result,self.cli(*args)[1])
    def test_same_case_evaluation_rejects_false_improvement(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,r=self.cli('plan','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--budget-seconds','600')
            p=pathlib.Path(tmp)/'candidate.json';p.write_text(json.dumps(r['decision']['selected_candidate']))
            rc,result=self.cli('evaluate','--before-profile',PROFILE,'--before-smoke',SMOKE,'--before-acceptance',NATIVE,
                '--after-profile',PROFILE,'--after-smoke',SMOKE,'--after-acceptance',NATIVE,'--candidate',p)
            self.assertEqual(rc,0);self.assertEqual(result['verdict'],'REJECTED')
            self.assertIn('NO_INDEPENDENT_EXECUTION_EVIDENCE',result['rejections'])
    def test_invalid_input_returns_structured_unknown(self):
        rc,r=self.cli('plan','--profile','__missing_profile__','--smoke',SMOKE,'--acceptance',NATIVE)
        self.assertEqual(rc,2);self.assertEqual(r['status'],'UNKNOWN')

if __name__=='__main__':unittest.main()
