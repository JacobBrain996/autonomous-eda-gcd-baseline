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
    def test_prepare_and_default_execute_do_not_start_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,r=self.cli('plan','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--budget-seconds','600')
            c=pathlib.Path(tmp)/'candidate.json';c.write_text(json.dumps(r['decision']['selected_candidate']))
            out=pathlib.Path(tmp)/'package'
            rc,result=self.cli('prepare-action','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--candidate',c,'--output',out)
            self.assertEqual(rc,0);self.assertEqual(result['execution_status'],'NOT_RUN')
            rc,result=self.cli('execute-action','--package',out,'--frozen-root','__missing__','--work','__missing_work__')
            self.assertEqual(rc,0);self.assertEqual(result['status'],'NOT_RUN')
            rc,result=self.cli('execute-action','--package',out,'--frozen-root','__missing__','--work','__missing_work__','--execute')
            self.assertEqual(rc,2);self.assertEqual(result['status'],'UNKNOWN')
    def test_recover_actual_default_not_run_and_inspect_without_tool_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,r=self.cli('plan','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--budget-seconds','600')
            c=pathlib.Path(tmp)/'candidate.json';c.write_text(json.dumps(r['decision']['selected_candidate']))
            out=pathlib.Path(tmp)/'package';work=pathlib.Path(tmp)/'output';work.mkdir();z=pathlib.Path(tmp)/'result.zip'
            self.cli('prepare-action','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--candidate',c,'--output',out)
            _,launcher=self.cli('execute-action','--package',out,'--frozen-root','__missing__','--work','__missing_work__')
            (work/'launcher-result.json').write_text(json.dumps(launcher))
            rc,sealed=self.cli('seal-action','--package',out,'--work',work,'--output',z)
            self.assertEqual(rc,0)
            rc,observation=self.cli('inspect-action',z,'--expected-sha256',sealed['sha256'],'--expected-candidate',r['decision']['selected_candidate']['candidate_id'])
            self.assertEqual(rc,0);self.assertEqual(observation['status'],'NOT_RUN');self.assertIsNone(observation['history_record'])
            rc,feedback=self.cli('advance-action','--profile',PROFILE,'--smoke',SMOKE,'--acceptance',NATIVE,'--result',z,'--expected-sha256',sealed['sha256'],'--budget-seconds','600')
            self.assertEqual(rc,0);self.assertEqual(feedback['decision'],'AWAIT_SEPARATE_EXECUTION_AUTHORIZATION');self.assertEqual(feedback['history'],[])

if __name__=='__main__':unittest.main()
