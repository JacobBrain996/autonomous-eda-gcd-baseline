"""Offline structural review of native Formal evidence; never proof certification.

Checks saved input/model/property/command consistency. Does not execute Yosys,
rederive RTLIL, authenticate a cloud run, replay a witness or promote PASS.
"""
import hashlib,math,pathlib,zipfile
from .case import read_json,digest
from .verification import verify_verification_package,observe_verification,_obj
from .evidence import read_bundle,verify_bundle
from .formal_runtime import bind_contract,make_miter,prepare_script,proof_script,check_ports,check_sequential_model
from .liberty import subset_liberty
from .invariants import strengthen_miter
from acceptance.verify import require_model_closure


def _hash(raw):return hashlib.sha256(raw).hexdigest()
def _need(test,message):
 if not test:raise ValueError(message)

def inspect_formal(package,contract_path,archive,expected_sha256):
 result={'schema':'verieda.formal-scope-review.v1','scope_structure_gate':'UNKNOWN','formal_gate':'UNKNOWN',
  'execution_binding':'UNKNOWN_EXTERNAL_REVIEW_REQUIRED','design_acceptance':'NOT_EVALUATED',
  'execution_authorized':False,'issues':[],
  'reviewer_sources':{'verieda/'+n:_hash((pathlib.Path(__file__).parent/n).read_bytes()) for n in ('formal_review.py','formal_runtime.py')},
  'limits':['does not rederive RTLIL or validate solver soundness','does not authenticate external execution','does not replay counterexamples'],
  'next_action':'review_saved_evidence'}
 try:
  verify_verification_package(package);root=pathlib.Path(package);subject=read_json(root/'subject.json');task=read_json(root/'plan.json')['next_check']
  c=read_json(contract_path);bind_contract(c,subject)
  observation=observe_verification(task,archive,expected_sha256)
  result.update(observation=observation,subject_id=subject['subject_id'],task_id=task['task_id'])
  data=read_bundle(archive);verify_bundle(data);receipt=_obj(data,'receipt.json')
  _need(receipt.get('contract_sha256')==digest(c) and _obj(data,'contract.json')==c,'contract identity mismatch')
  for name,key in [('gold.v','rtl_sha256'),('candidate.v','netlist_sha256'),('source.lib','library_sha256')]:
   _need(_hash(data[name])==task['inputs'][key],'saved proof source differs from task: '+name)
  _need(data['miter.v']==make_miter(c).encode(),'miter differs from complete registered output/reset property')
  _need(bool(data['gold.il']) and bool(data['gate.il']) and data['gold.il']!=data['gate.il'],'gold/gate normalized snapshots missing or identical')
  coverage=_obj(data,'coverage.json')
  _need(coverage.get('inputs')==c['inputs'] and coverage.get('outputs')==c['outputs'] and coverage.get('output_bits')==sum(c['outputs'].values()),'incomplete input/output coverage')
  _need(coverage.get('contract_sha256')==digest(c),'coverage contract mismatch')
  gold=_obj(data,'gold-interface.json')['modules'][c['top']];gate=_obj(data,'gate-linked.json')['modules'][c['top']]
  check_ports(gold['ports'],c);check_ports(gate['ports'],c)
  unlinked=_obj(data,'unlinked.json')['modules'];_need(set(unlinked)=={c['top']},'unlinked module closure differs')
  discovered={cell['type'] for cell in unlinked[c['top']]['cells'].values()};used={cell['type'] for cell in gate['cells'].values()}
  models=_obj(data,'models.json')['modules'];require_model_closure(discovered,used,models)
  derived,selection=subset_liberty(data['source.lib'],discovered)
  _need(data['functional.lib']==derived,'functional model selection changes source cell bodies')
  selection.update(netlist_sha256=task['inputs']['netlist_sha256'],engine_sha256=task['inputs']['engine_sha256'])
  _need(_obj(data,'library-selection.json')==selection,'functional library selection identity mismatch')
  _need(coverage.get('functional_cells')==sorted(used) and coverage.get('no_blackbox') is True and coverage.get('common_positive_clock') is True,'model coverage claim differs')
  model=_obj(data,'miter.json')['modules']['acceptance_miter'];check_sequential_model(model,c['clock'])
  expected_ports={n:('input',w) for n,w in c['inputs'].items()};expected_ports['mismatch']=('output',1)
  _need(set(model['ports'])==set(expected_ports),'miter input/property interface differs')
  for n,(direction,width) in expected_ports.items():_need(model['ports'][n]['direction']==direction and len(model['ports'][n]['bits'])==width,'miter port width/direction differs')
  prop=coverage.get('property');_need(prop in ('mismatch','strengthened_mismatch'),'unknown proof property')
  proof_modules=_obj(data,'proof-model.json')['modules']
  _need(set(proof_modules)=={'acceptance_miter'},'proof model hierarchy differs')
  proof_model=proof_modules['acceptance_miter'];check_sequential_model(proof_model,c['clock'])
  proof_ports=dict(expected_ports)
  if prop=='strengthened_mismatch':proof_ports[prop]=('output',1)
  _need(set(proof_model['ports'])==set(proof_ports),'proof model property/interface missing')
  for n,(direction,width) in proof_ports.items():_need(proof_model['ports'][n]['direction']==direction and len(proof_model['ports'][n]['bits'])==width,'proof model port differs')
  if prop=='strengthened_mismatch':
   _need(c['strengthening']=='gcd-state-v1','unregistered auxiliary property')
   augmented,relation,strength=strengthen_miter(data['miter.il'],data['miter.json'],boot_name='__ve_boot')
   _need(data['proof-input.il']==augmented and data['state_relation.v']==relation and _obj(data,'strengthening.json')==strength,'fresh auxiliary relation derivation mismatch')
  else:
   _need(data['proof-input.il']==data['miter.il'] and 'state_relation.v' not in data,'original proof property changed')
  work=receipt['work_path']
  _need(data['prepare.ys']==prepare_script(work,c).encode(),'gold/gate preparation commands changed')
  _need(data['proof.ys']==proof_script(work,prop).encode(),'proof script is not the supported unbounded property recipe')
  yosys=[p for p in subject['tools'] if pathlib.PurePosixPath(p).name=='yosys'][0]
  steps=receipt.get('steps');_need(isinstance(steps,list) and len(steps)==4,'incomplete native proof process chain')
  total=0
  for i,(step,name) in enumerate(zip(steps,('capabilities','discover','prepare','proof'))):
   _need(step.get('argv')==[yosys,'-Q','-T','-s',work+'/'+name+'.ys'],'unexpected proof process command')
   _need(type(step.get('pid')) is int and step['pid']>0,'process PID missing')
   rc=step.get('return_code');child=step.get('child_return_code');timeout=step.get('timeout');runtime=step.get('runtime_seconds')
   _need(type(rc) is int and type(child) is int and type(timeout) is bool,'invalid process exit/timeout record')
   _need(type(runtime) in (int,float) and math.isfinite(runtime) and 0<=runtime<=301,'invalid process runtime')
   _need(step.get('signal')==(-child if child<0 else None),'signal and child exit disagree')
   _need((timeout and rc==124) or (not timeout and rc==child),'inconsistent process exit')
   _need(step.get('log_sha256')==_hash(data[name+'.log']),'native process log SHA mismatch')
   _need(i==3 or (rc==0 and not timeout),'proof ran after failed prerequisite')
   total+=runtime
  _need(receipt['return_code']==steps[-1]['return_code'] and receipt['runtime_seconds']+1e-3>=total,'total runtime/exit disagrees with process chain')
  result.update(scope_structure_gate='PASS_STATIC_CHECKS',next_action='independent_execution_and_proof_review_required',
   proof_property=prop,all_output_bits=sum(c['outputs'].values()),functional_cell_types=len(used),archive_sha256=expected_sha256,
   counterexample_scope='auxiliary relation may fail independently of outputs' if prop=='strengthened_mismatch' else 'original all-output property; witness still requires validation')
 except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,UnicodeError,zipfile.BadZipFile) as ex:result['issues'].append(str(ex))
 result['review_id']=digest(result);return result
