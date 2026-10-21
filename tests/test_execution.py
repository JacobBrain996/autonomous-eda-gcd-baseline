"""Offline action adapter tests; no EDA/container/cloud execution."""
import copy,json,pathlib,sys,tempfile,unittest,subprocess,shutil
from unittest.mock import patch,Mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.case import load_case
from verieda.policy import propose
from verieda.execution import prepare_action,verify_package,execute_action,make_argv,clean_environment,_run,check_image_record
from test_case import SMOKE,NATIVE

class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
        cls.candidate=propose(cls.state,600,[])['selected_candidate']
    def test_package_is_exclusive_bound_and_no_execution_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)/'bundle';prepare_action(self.state,self.candidate,out)
            p=verify_package(out);self.assertEqual(p['candidate_id'],self.candidate['candidate_id'])
            self.assertEqual(execute_action(out,'missing-source','missing-work')['status'],'NOT_RUN')
            with self.assertRaises(ValueError):prepare_action(self.state,self.candidate,out)
            self.assertEqual(set(x.name for x in out.iterdir()),{'state.json','candidate.json','manifest.json','effective.mk'})
    def test_mutation_extra_file_and_illegal_candidate_fail_before_native_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)/'bundle';prepare_action(self.state,self.candidate,out)
            (out/'effective.mk').write_text('$(shell echo unsafe)')
            with self.assertRaises(ValueError):verify_package(out)
        bad=copy.deepcopy(self.candidate);bad['changes']={'CLOCK_PERIOD':1}
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(ValueError):prepare_action(self.state,bad,pathlib.Path(tmp)/'bundle')
    def test_only_fixed_make_scope_and_no_host_environment_leak(self):
        args=make_argv('/bundle/effective.mk','/work/candidate','synth')
        self.assertIn('ABC_AREA=0',args);self.assertIn('LEC_CHECK=1',args);self.assertIn('SEC_CHECK=1',args)
        self.assertIn('WORK_HOME=/work/candidate',args);self.assertEqual(args[-1],'synth')
        self.assertIn('YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys',args)
        self.assertIn('OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad',args)
        self.assertIn('PYTHON_EXE=/usr/bin/python3',args)
        for target in ('all','clean','synth;rm'):
            with self.assertRaises(ValueError):make_argv('/bundle/effective.mk','/work/candidate',target)
        with self.assertRaises(ValueError):make_argv('/bundle/effective.mk','/work/$(shell touch injected)','synth')
        env=clean_environment('/work/candidate')
        self.assertNotIn('GITHUB_TOKEN',env);self.assertNotIn('MAKEFLAGS',env);self.assertNotIn('PYTHONPATH',env)
        self.assertEqual(env['LC_ALL'],'C')
    def test_extra_file_and_unapproved_execution_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)/'bundle';prepare_action(self.state,self.candidate,out)
            (out/'unexpected').write_text('not allowed')
            with self.assertRaises(ValueError):verify_package(out)
        with tempfile.TemporaryDirectory() as tmp:
            out=pathlib.Path(tmp)/'bundle';prepare_action(self.state,self.candidate,out)
            with self.assertRaises(ValueError):execute_action(out,'/missing','/work/unavailable',True)
    def test_timeout_kills_process_group_and_signal_return_is_preserved(self):
        # Native Linux process API is unavailable here. This narrow double tests
        # our process-group/timeout contract, never claims EDA execution success.
        with tempfile.TemporaryDirectory() as tmp:
            proc=Mock(pid=123);proc.wait.side_effect=[subprocess.TimeoutExpired(['make'],1),-9]
            with patch('verieda.execution.subprocess.Popen',return_value=proc) as popen,patch('verieda.execution.os.killpg',create=True) as kill,patch('verieda.execution.signal.SIGKILL',9,create=True):
                result=_run(['make'],'/source',{},pathlib.Path(tmp)/'timeout.log',1)
                self.assertTrue(result['timeout']);self.assertEqual(result['return_code'],124)
                self.assertEqual(result['child_return_code'],-9);self.assertEqual(result['pid'],123)
                kill.assert_called_once();self.assertEqual(kill.call_args.args[0],123)
                self.assertFalse(popen.call_args.kwargs['shell']);self.assertTrue(popen.call_args.kwargs['start_new_session'])
            proc=Mock(pid=124);proc.wait.return_value=-4
            with patch('verieda.execution.subprocess.Popen',return_value=proc):
                result=_run(['make'],'/source',{},pathlib.Path(tmp)/'sigill.log',1)
                self.assertEqual(result['return_code'],-4);self.assertEqual(result['signal'],4)
    def test_host_record_requires_exact_image_and_rejects_environment_fields(self):
        support=json.loads((ROOT/'verieda/action_support.json').read_text())
        record={'image_id':support['image_id'],'repo_digests':[support['image']],'os':'linux','architecture':'amd64'}
        self.assertEqual(check_image_record(record,support)['image_id'],support['image_id'])
        for key,value in [('image_id','wrong'),('architecture','arm64'),('Env',['TOKEN=secret'])]:
            bad=dict(record);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):check_image_record(bad,support)
    def test_actual_clean_git_checkout_with_ignored_make_config_is_rejected(self):
        from verieda.execution import _source_inventory
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'flow').mkdir();(root/'flow/Makefile').write_text('all:\n')
            git=shutil.which('git');self.assertIsNotNone(git)
            def call(*args):return subprocess.check_output([git,'-C',str(root),*args],stderr=subprocess.STDOUT)
            call('init','-q');call('add','flow/Makefile')
            call('-c','user.name=VeriEDA synthetic fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
            self.assertEqual(_source_inventory(root,git),call('rev-parse','HEAD').decode().strip())
            (root/'.git/info/exclude').write_text('flow/settings.mk\n')
            (root/'flow/settings.mk').write_text('$(shell echo must-never-execute)\n')
            self.assertEqual(call('status','--porcelain'),b'')
            with self.assertRaises(ValueError):_source_inventory(root,git)
    def test_synthesis_success_without_expected_odb_remains_hold(self):
        from verieda.execution import EXPECTED_EFFECTIVE
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);bundle=root/'package';prepare_action(self.state,self.candidate,bundle)
            frozen=root/'frozen';frozen.mkdir();work=root/'output'
            support=json.loads((ROOT/'verieda/action_support.json').read_text())
            image={'image_id':support['image_id'],'repo_digests':[support['image']],'os':'linux','architecture':'amd64'}
            def saved_fixture(argv,cwd,env,log,seconds):
                if argv[-1]=='verieda-effective':pathlib.Path(log).write_bytes(EXPECTED_EFFECTIVE)
                elif argv[-1]=='synth':
                    pathlib.Path(log).write_bytes(b'Using ABC speed script.\nSYNTHETIC_ONLY\n')
                    net=work/'results/nangate45/gcd/verieda/1_2_yosys.v';net.parent.mkdir(parents=True);net.write_bytes(b'SYNTHETIC_ONLY')
                else:raise AssertionError('unexpected target')
                return {'argv':argv,'return_code':0,'timeout':False,'signal':None,'runtime_seconds':0}
            with patch('verieda.execution._native_identity',return_value={}),patch('verieda.execution._posix_path',side_effect=str),patch('verieda.execution._run',side_effect=saved_fixture):
                r=execute_action(bundle,frozen,work,True,image)
            self.assertEqual(r['status'],'HOLD_MISSING_ODB');self.assertEqual(r['FORMAL_EQUIVALENCE_GATE'],'NOT_RUN')

if __name__=='__main__':unittest.main()
