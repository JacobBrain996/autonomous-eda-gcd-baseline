"""Synthetic audit fixtures are never hardware proof or execution attestation."""
import copy,hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda import formal_review as r
from verieda import formal_runtime as f
from verieda.case import digest
from verieda.verification import plan_verification
PACKAGE=ROOT/'evidence/verification-handoff-20261021-v1/package'

class FormalReviewTests(unittest.TestCase):
 def fixture(self,root,mutation=None):
  request=root/'request';request.mkdir();work=root/'output';work.mkdir()
  subject=json.loads((PACKAGE/'subject.json').read_text());c=json.loads((ROOT/'contracts/gcd.reset2.json').read_text());c['strengthening']='none'
  gold=b'module gcd; endmodule';candidate=b'module gcd; wire a; endmodule';lib=b'library(L) { cell(BUF) { pin(A) { direction:input; } pin(Z) { direction:output; function:"A"; } } }'
  c['rtl_sha256']=hashlib.sha256(gold).hexdigest();subject['frozen']['rtl_sha256']=c['rtl_sha256'];subject['library'][c['library_path']]=hashlib.sha256(lib).hexdigest()
  subject['target']['netlist_sha256']=hashlib.sha256(candidate).hexdigest();subject['subject_id']=digest({k:v for k,v in subject.items() if k!='subject_id'})
  plan=plan_verification(subject,300);task=plan['next_check']
  for n,raw in [('candidate.v',candidate),('candidate.odb',b'fixture ODB')]: (request/n).write_bytes(raw)
  subject['target']['odb_sha256']=hashlib.sha256(b'fixture ODB').hexdigest();subject['subject_id']=digest({k:v for k,v in subject.items() if k!='subject_id'});plan=plan_verification(subject,300);task=plan['next_check']
  for n,obj in [('subject.json',subject),('plan.json',plan)]:f.write(request/n,obj)
  f.write(request/'manifest.json',{'schema':'verieda.verification-package.v1','files':{n:f.sha(request/n) for n in ('candidate.v','candidate.odb','subject.json','plan.json')},'subject_id':subject['subject_id'],'task_id':task['task_id'],'execution_status':'NOT_RUN','ready_for_cloud_execution':False})
  contract=root/'contract.json';f.write(contract,c);ports={n:{'direction':'input','bits':list(range(w))} for n,w in c['inputs'].items()};ports.update({n:{'direction':'output','bits':list(range(w))} for n,w in c['outputs'].items()})
  cells={'x':{'type':'BUF'}};model={'ports':{'A':{'direction':'input','bits':[2]},'Z':{'direction':'output','bits':[2]}},'cells':{}}
  miter={'ports':{n:copy.deepcopy(p) for n,p in ports.items() if p['direction']=='input'},'cells':{}}
  miter['ports']['mismatch']={'direction':'output','bits':[100]}
  for n,b in [('gold.v',gold),('candidate.v',candidate),('source.lib',lib),('miter.v',f.make_miter(c).encode()),('miter.il',b'module \\acceptance_miter\nend\n'),('proof-input.il',b'module \\acceptance_miter\nend\n'),('gold.il',b'gold normalized fixture'),('gate.il',b'gate normalized fixture')]: (work/n).write_bytes(b)
  functional,selection=f.subset_liberty(lib,{'BUF'});(work/'functional.lib').write_bytes(functional)
  selection.update(netlist_sha256=hashlib.sha256(candidate).hexdigest(),engine_sha256=task['inputs']['engine_sha256'])
  for n,obj in [('contract.json',c),('library-selection.json',selection),('unlinked.json',{'modules':{'gcd':{'cells':cells}}}),('gold-interface.json',{'modules':{'gcd':{'ports':ports}}}),('gate-linked.json',{'modules':{'gcd':{'ports':ports,'cells':cells}}}),('models.json',{'modules':{'BUF':model}}),('miter.json',{'modules':{'acceptance_miter':miter}}),('proof-model.json',{'modules':{'acceptance_miter':miter}}),('coverage.json',{'inputs':c['inputs'],'outputs':c['outputs'],'output_bits':18,'functional_cells':['BUF'],'no_blackbox':True,'common_positive_clock':True,'property':'mismatch','contract_sha256':digest(c)})]:f.write(work/n,obj)
  work_path='/work/formal';(work/'prepare.ys').write_bytes(f.prepare_script(work_path,c).encode());(work/'proof.ys').write_bytes(f.proof_script(work_path,'mismatch').encode())
  yosys=next(p for p in subject['tools'] if pathlib.PurePosixPath(p).name=='yosys');steps=[]
  for name in ('capabilities','discover','prepare','proof'):
   (work/(name+'.log')).write_bytes(b'Induction step proven: SUCCESS!' if name=='proof' else b'SYNTHETIC fixture')
   steps.append({'argv':[yosys,'-Q','-T','-s',work_path+'/'+name+'.ys'],'pid':100+len(steps),'return_code':0,'child_return_code':0,'timeout':False,'signal':None,'runtime_seconds':0.01,'log_sha256':f.sha(work/(name+'.log'))})
  receipt={'schema':'verieda.verifier-receipt.v1','task_id':task['task_id'],'inputs':task['inputs'],'engine_sha256':task['inputs']['engine_sha256'],'return_code':0,'runtime_seconds':0.1,'log_path':'proof.log','work_path':work_path,'steps':steps,'contract_sha256':digest(c)}
  if mutation=='old-netlist':(work/'candidate.v').write_bytes(b'OLD NETLIST')
  elif mutation=='partial-outputs':
   cov=json.loads((work/'coverage.json').read_text());cov['outputs'].pop('resp_msg');(work/'coverage.json').write_text(json.dumps(cov))
  elif mutation=='same-design':(work/'prepare.ys').write_text('read_verilog /work/formal/candidate.v\n')
  elif mutation=='finite':(work/'proof.ys').write_text('sat -seq 32 -prove mismatch 0\n')
  elif mutation=='assumption':(work/'miter.v').write_bytes((work/'miter.v').read_bytes()+b'// inserted assumption')
  elif mutation=='blackbox':
   d=json.loads((work/'models.json').read_text());d['modules']['BUF']['attributes']={'blackbox':'1'};(work/'models.json').write_text(json.dumps(d))
  elif mutation=='wrong-property-model':
   d=json.loads((work/'proof-model.json').read_text());d['modules']['acceptance_miter']['ports'].pop('mismatch');(work/'proof-model.json').write_text(json.dumps(d))
  elif mutation=='bad-log':receipt['steps'][-1]['log_sha256']='0'*64
  elif mutation=='foreign-contract':receipt['contract_sha256']='0'*64
  f.write(work/'receipt.json',receipt);archive=root/'formal.zip';info=f.seal_formal(work,archive)
  return request,contract,archive,info['sha256'],c
 def test_well_bound_fixture_passes_structural_checks_but_never_formal_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   p,c,z,h,profile=self.fixture(pathlib.Path(tmp))
   with patch('verieda.formal_runtime.contract_registry',return_value={'schema':'verieda.contract-registry.v1','contracts':{profile['rtl_sha256']:digest(profile)}}):got=r.inspect_formal(p,c,z,h)
   self.assertEqual(got['scope_structure_gate'],'PASS_STATIC_CHECKS',got)
   self.assertEqual(got['formal_gate'],'UNKNOWN');self.assertEqual(got['execution_binding'],'UNKNOWN_EXTERNAL_REVIEW_REQUIRED')
   self.assertFalse(got['execution_authorized'])
 def test_resealed_wrong_inputs_scope_models_and_scripts_are_held(self):
  for mutation in ('old-netlist','partial-outputs','same-design','finite','assumption','blackbox','bad-log','foreign-contract','wrong-property-model'):
   with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as tmp:
    p,c,z,h,profile=self.fixture(pathlib.Path(tmp),mutation)
    with patch('verieda.formal_runtime.contract_registry',return_value={'schema':'verieda.contract-registry.v1','contracts':{profile['rtl_sha256']:digest(profile)}}):got=r.inspect_formal(p,c,z,h)
    self.assertNotEqual(got['scope_structure_gate'],'PASS_STATIC_CHECKS',got);self.assertEqual(got['formal_gate'],'UNKNOWN')
 def test_lifecycle_cannot_attach_structurally_valid_foreign_proof(self):
  from verieda.case import load_case
  from verieda.verification import review_candidate
  from test_case import SMOKE,NATIVE
  state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
  result=ROOT/'evidence/verieda-action-ed5d84b9bdf7/result.zip'
  with tempfile.TemporaryDirectory() as tmp:
   p,c,z,h,profile=self.fixture(pathlib.Path(tmp))
   with patch('verieda.formal_runtime.contract_registry',return_value={'schema':'verieda.contract-registry.v1','contracts':{profile['rtl_sha256']:digest(profile)}}):
    got=review_candidate(state,result,'15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3',300,z,h,verification_package=p,formal_contract=c)
   self.assertEqual(got['candidate_status'],'EVIDENCE_HOLD');self.assertFalse(got['execution_authorized'])
 def test_cli_missing_result_is_structured_unknown(self):
  import subprocess
  p=subprocess.run([sys.executable,'-m','verieda','inspect-formal','--package',str(PACKAGE),'--contract',str(ROOT/'contracts/gcd.reset2.json'),'--result','__absent__','--expected-sha256','0'*64],cwd=ROOT,capture_output=True,timeout=20)
  self.assertEqual(p.returncode,2);self.assertEqual(json.loads(p.stdout)['formal_gate'],'UNKNOWN')
if __name__=='__main__':unittest.main()
