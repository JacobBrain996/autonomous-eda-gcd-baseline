"""Offline native-Formal adapter checks, not hardware proof results."""
import copy,hashlib,json,pathlib,sys,tempfile,unittest,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda import formal_runtime as f
from verieda.verification import verify_verification_package
PACKAGE=ROOT/'evidence/verification-handoff-20261021-v1/package'

class FormalRuntimeTests(unittest.TestCase):
 def contract(self):return json.loads((ROOT/'contracts/gcd.reset2.json').read_text())
 def test_contract_rejects_assumptions_partial_outputs_and_injection(self):
  c=self.contract();self.assertEqual(f.validate_contract(c)['top'],'gcd')
  for key,value in [('reset_edges',0),('reset_edges',True),('clock','clk;exec'),('assume_equal_state',True),('outputs',{})]:
   bad=copy.deepcopy(c);bad[key]=value
   with self.assertRaises(ValueError):f.validate_contract(bad)
 def test_miter_covers_all_outputs_and_only_harness_boot_is_initialized(self):
  c=self.contract();s=f.make_miter(c)
  self.assertIn('gold_core gold',s);self.assertIn('gate_core gate',s)
  self.assertIn('.resp_msg(__ve_g_resp_msg)',s);self.assertIn('.resp_msg(__ve_t_resp_msg)',s)
  self.assertIn('!==',s);self.assertNotIn('assume',s);self.assertNotIn('init-zero',s)
  self.assertEqual(s.count('= 0;'),1)
 def test_other_rtl_interface_is_supported_by_generator(self):
  c=self.contract();c.update(top='counter',clock='tick',reset='rst',inputs={'tick':1,'rst':1,'enable':1},outputs={'count':4},strengthening='none')
  f.validate_contract(c);s=f.make_miter(c)
  self.assertIn('.count(__ve_g_count)',s);self.assertNotIn('req_msg',s)
 def test_interface_and_clock_checks_do_not_allow_omitted_outputs_or_async_state(self):
  c=self.contract();ports={n:{'direction':'input','bits':list(range(w))} for n,w in c['inputs'].items()}
  ports.update({n:{'direction':'output','bits':list(range(w))} for n,w in c['outputs'].items()})
  f.check_ports(ports,c)
  bad=copy.deepcopy(ports);bad['debug']={'direction':'output','bits':[1]}
  with self.assertRaises(ValueError):f.check_ports(bad,c)
  model={'ports':{'clk':{'bits':[1]}},'cells':{'a':{'type':'$adff','connections':{'CLK':[1]},'parameters':{}}}}
  with self.assertRaises(ValueError):f.check_sequential_model(model,'clk')
 def test_proof_is_unbounded_and_keeps_original_mismatch_without_assumptions(self):
  p=f.proof_script('/work/check','mismatch')
  for token in ('-tempinduct','-enable_undef','-set-init-def','-verify','-prove mismatch 0'):self.assertIn(token,p)
  for token in ('-set-init-zero','-set-assumes','-seq 0'):self.assertNotIn(token,p)
  with self.assertRaises(ValueError):f.proof_script('/work/check','mismatch;exec')
 def test_default_execution_is_not_run_and_does_not_create_work(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=pathlib.Path(tmp)/'work'
   r=f.execute_formal(PACKAGE,ROOT/'contracts/gcd.reset2.json','__missing_frozen__',w)
   self.assertEqual(r['status'],'NOT_RUN');self.assertFalse(w.exists())
 def test_contract_must_bind_real_candidate_rtl_and_declared_scope(self):
  subject=json.loads((PACKAGE/'subject.json').read_text())
  f.bind_contract(self.contract(),subject)
  for key,value in [('rtl_sha256','0'*64),('description','different reset contract'),('top','counter')]:
   c=self.contract();c[key]=value
   with self.assertRaises(ValueError):f.bind_contract(c,subject)
 def test_fresh_boot_alias_can_be_bound_without_changing_old_helper_default(self):
  from test_invariants import InvariantTests
  from verieda.invariants import strengthen_miter
  il,model=InvariantTests().fixture()
  il=il.replace(b'\\boot',b'\\__ve_boot');model['modules']['acceptance_miter']['netnames']['__ve_boot']=model['modules']['acceptance_miter']['netnames'].pop('boot')
  augmented,relation,plan=strengthen_miter(il,json.dumps(model).encode(),boot_name='__ve_boot')
  self.assertEqual(plan['bindings']['boot'][0]['name'],'__ve_boot')
  self.assertIn(b'original_mismatch',augmented)
 def test_native_coordinator_artifact_round_trip_with_recorded_fixture_not_eda(self):
  from unittest.mock import patch
  from verieda.verification import plan_verification
  original_subject=json.loads((PACKAGE/'subject.json').read_text());original_contract=self.contract()
  for mode,want in [('proof','REVIEW_FORMAL_SCOPE'),('bmc','REVIEW_UNPROVEN'),('timeout','STOP_REVIEW_TIMEOUT'),('sigill','STOP_REVIEW_TOOL_FAILURE')]:
   with tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);frozen=root/'frozen';out=root/'output'
    c=copy.deepcopy(original_contract)
    for key in ('rtl_path','library_path'):(frozen/c[key]).parent.mkdir(parents=True,exist_ok=True)
    (frozen/c['rtl_path']).write_text('SYNTHETIC GOLD NOT RTL')
    (frozen/c['library_path']).write_bytes(b'library(L) { cell(BUF) { pin(Z) { direction:output; function:"A"; } } }')
    # Synthetic, consistently bound request; no fixture SHA is represented as real EDA.
    from verieda.case import digest
    subject=copy.deepcopy(original_subject);subject['frozen']['rtl_sha256']=f.sha(frozen/c['rtl_path'])
    subject['library'][c['library_path']]=f.sha(frozen/c['library_path']);subject['subject_id']=digest({k:x for k,x in subject.items() if k!='subject_id'})
    c['rtl_sha256']=subject['frozen']['rtl_sha256'];request=root/'request';shutil.copytree(PACKAGE,request)
    request_plan=plan_verification(subject,300);task=request_plan['next_check']
    for n,obj in [('subject.json',subject),('plan.json',request_plan)]: (request/n).write_bytes((json.dumps(obj)+'\n').encode())
    manifest=json.loads((request/'manifest.json').read_text());manifest.update(subject_id=subject['subject_id'],task_id=task['task_id'])
    manifest['files']={n:f.sha(request/n) for n in manifest['files']};(request/'manifest.json').write_text(json.dumps(manifest))
    contract_file=root/'contract.json';contract_file.write_text(json.dumps(c))
    ports={n:{'direction':'input','bits':list(range(w))} for n,w in c['inputs'].items()};ports.update({n:{'direction':'output','bits':list(range(w))} for n,w in c['outputs'].items()})
    def fake_run(argv,cwd,env,log,seconds):
     name=pathlib.Path(log).stem;rc=0;text='synthetic coordinator fixture'
     if name=='capabilities':text=(ROOT/'tests/fixtures/yosys_sat_help_39451358576.txt').read_text()
     elif name=='discover':f.write(out/'unlinked.json',{'modules':{'gcd':{'cells':{'x':{'type':'BUF'}}}}})
     elif name=='prepare':
      f.write(out/'gold-interface.json',{'modules':{'gcd':{'ports':ports}}});f.write(out/'gate-linked.json',{'modules':{'gcd':{'ports':ports,'cells':{'x':{'type':'BUF'}}}}})
      f.write(out/'models.json',{'modules':{'BUF':{'ports':{'A':{'direction':'input','bits':[2]},'Z':{'direction':'output','bits':[2]}},'cells':{}}}})
      f.write(out/'miter.json',{'modules':{'acceptance_miter':{'ports':{'clk':{'bits':[0]}},'cells':{}}}})
      for n in ('gold.il','gate.il','miter.il'):(out/n).write_text('synthetic '+n)
     elif name=='proof':
      text={'proof':'Induction step proven: SUCCESS!','bmc':'SAT proof finished - no model found: SUCCESS!','timeout':'','sigill':'child killed: illegal instruction'}[mode];rc={'timeout':124,'sigill':-4}.get(mode,0)
     pathlib.Path(log).write_bytes(text.encode())
     return {'argv':argv,'return_code':rc,'runtime_seconds':0.01,'timeout':mode=='timeout' and name=='proof','pid':100,'child_return_code':rc,'signal':4 if rc==-4 else None,'log_sha256':hashlib.sha256(pathlib.Path(log).read_bytes()).hexdigest()}
    with patch('verieda.formal_runtime.contract_registry',return_value={'schema':'verieda.contract-registry.v1','contracts':{c['rtl_sha256']:digest(c)}}),patch('verieda.formal_runtime._admission',return_value=(subject,task,'/fake/yosys',{})),patch('verieda.formal_runtime._posix_path',side_effect=str),patch('verieda.formal_runtime.clean_environment',return_value={'LC_ALL':'C'}),patch('verieda.formal_runtime._run',side_effect=fake_run),patch('verieda.formal_runtime.sha',side_effect=lambda p:'a'*64 if str(p)=='/fake/yosys' else hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()):
     r=f.execute_formal(request,contract_file,frozen,out,True,{})
     archive=out/'verifier-result.zip'
     plan=plan_verification(subject,300,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
     self.assertEqual(plan['decision'],want, r)
     self.assertNotEqual(plan['gates']['formal'],'PASS');self.assertEqual(plan['design_acceptance'],'NOT_EVALUATED')
 def test_cli_default_and_windows_admission_never_start_native_eda(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   args=['--package',str(PACKAGE),'--contract',str(ROOT/'contracts/gcd.reset2.json'),'--frozen-root','__missing__','--work',str(pathlib.Path(tmp)/'work')]
   p=subprocess.run([sys.executable,'-m','verieda','execute-formal',*args],cwd=ROOT,capture_output=True,timeout=20)
   self.assertEqual(p.returncode,0,p.stderr.decode());self.assertEqual(json.loads(p.stdout)['status'],'NOT_RUN')
 def test_same_description_cannot_hide_a_weaker_reset_contract(self):
  c=self.contract();c['reset_edges']=3
  subject=json.loads((PACKAGE/'subject.json').read_text())
  with self.assertRaises(ValueError):f.bind_contract(c,subject)
 def test_old_39_cell_assumption_is_absent_from_runtime(self):
  source=(ROOT/'verieda/formal_runtime.py').read_text()
  self.assertNotIn('len(discovered)!=39',source);self.assertNotIn('6_final.v',source)

if __name__=='__main__':unittest.main()
