"""Evidence-bound verification requests. No EDA execution or proof promotion.

Planning core is design-independent; load_subject uses the existing GCD action
adapter. Result archives are observations, not certified proof receipts.
"""
import copy,hashlib,json,math,pathlib,re,zipfile
from .case import digest
from .policy import _bound_state,validate_candidate
from .action_results import inspect_action,NETLIST,ODB
from .evidence import read_bundle,verify_bundle,object_json
from .formal import observe_yosys
from .execution import _unlinked

CAP_SECONDS=300

def _sha(raw):return hashlib.sha256(raw).hexdigest()
def _hex(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def _obj(data,name):
 obj,duplicates=object_json(data,name)
 if duplicates or not isinstance(obj,dict):raise ValueError('ambiguous/malformed verification object '+name)
 return obj

def load_subject(state,artifact,expected_sha256):
 """Join an independently loaded reference with exact saved candidate bytes."""
 _bound_state(state)
 if not _hex(expected_sha256):raise ValueError('caller-trusted result SHA256 required')
 observation=inspect_action(artifact,expected_sha256)
 if observation.get('status')!='SYNTHESIS_COMPLETED' or observation['evidence_gate']!='PASS' or observation['issues']:
  raise ValueError('complete consistent synthesis evidence required')
 data=read_bundle(artifact);verify_bundle(data)
 if _sha(pathlib.Path(artifact).read_bytes())!=expected_sha256:raise ValueError('result changed during verification preparation')
 candidate=_obj(data,'action/package/candidate.json');prior=_obj(data,'action/package/state.json')
 if prior!=state or validate_candidate(candidate,state)['legality']!='PASS':raise ValueError('foreign/illegal candidate or reference state')
 manifest=_obj(data,'action/package/manifest.json')
 libraries={k:v for k,v in manifest['support']['sources'].items() if k.endswith('.lib')}
 if len(libraries)!=1:raise ValueError('single identified functional source library required')
 subject={'schema':'verieda.verification-subject.v1','design':state['design'],'platform':state['platform'],
  'candidate_id':candidate['candidate_id'],'state_id':state['state_id'],'artifact_sha256':expected_sha256,
  'frozen':copy.deepcopy(state['frozen']),'tools':copy.deepcopy(state['tools']),
  'library':libraries,'formal_contract':state.get('formal',{}).get('contract'),
  'target':{'netlist_sha256':_sha(data['action/output/'+NETLIST]),'odb_sha256':_sha(data['action/output/'+ODB])},
  'reference':{'netlist_sha256':state['inputs']['6_final.v'],'formal_gate':state['gates'].get('formal','UNKNOWN')},
  'execution_scope':'SYNTHESIS_ONLY','external_identity':'caller-trusted archive digest; no remote attestation'}
 subject['subject_id']=digest(subject);return subject

def _validate(subject):
 if not isinstance(subject,dict) or subject.get('schema')!='verieda.verification-subject.v1':raise ValueError('verification subject required')
 if subject.get('subject_id')!=digest({k:v for k,v in subject.items() if k!='subject_id'}):raise ValueError('verification subject identity mismatch')
 try:
  for field in ('candidate_id','state_id','artifact_sha256'):
   if not _hex(subject[field]):raise ValueError('invalid verification identity')
  for group,fields in (('target',('netlist_sha256','odb_sha256')),('frozen',('rtl_sha256','sdc_sha256'))):
   if any(not _hex(subject[group][key]) for key in fields):raise ValueError('incomplete target identity')
  for group in ('tools','library'):
   if not isinstance(subject[group],dict) or not subject[group] or any(not isinstance(k,str) or not _hex(v) for k,v in subject[group].items()):raise ValueError('missing tool/library identity')
  if len(subject['library'])!=1 or any(not isinstance(subject[k],str) or not subject[k] for k in ('design','platform')):raise ValueError('incomplete design/library identity')
  if subject['execution_scope']!='SYNTHESIS_ONLY':raise ValueError('unsupported verification phase')
  if 'formal_contract' not in subject or (subject['formal_contract'] is not None and not isinstance(subject['formal_contract'],str)):raise ValueError('missing/malformed formal contract')
 except (KeyError,TypeError) as ex:raise ValueError('incomplete verification subject') from ex

def _formal_task(subject):
 tools=[h for p,h in subject['tools'].items() if pathlib.PurePosixPath(p).name=='yosys']
 if len(tools)!=1:raise ValueError('exactly one bound Yosys binary required')
 task={'schema':'verieda.verification-task.v1','kind':'FORMAL_SYNTHESIS','design':subject['design'],'platform':subject['platform'],
  'inputs':{'subject_id':subject['subject_id'],'artifact_sha256':subject['artifact_sha256'],
   'netlist_sha256':subject['target']['netlist_sha256'],'rtl_sha256':subject['frozen']['rtl_sha256'],
   'sdc_sha256':subject['frozen']['sdc_sha256'],'library_sha256':next(iter(subject['library'].values())),
   'engine_sha256':tools[0],'contract':subject['formal_contract']},
  'cap_seconds':CAP_SECONDS,'requires_external_authorization':True,
  'external_limits':{'jobs':1,'job_seconds':600,'runner':'ubuntu-24.04-standard-public','automatic_retry':False},
  'requirements':['discover current cell types and derive complete functional model closure from bound source library',
   'gold is original RTL; gate is this candidate netlist; reject unsupported cells or blackboxes',
   'validate reset, clock, initial state and every top output against declared contract',
   'regenerate miter and prove any auxiliary relation with original mismatch; never reuse a prior proof',
   'unbounded proof plus independent property/model/execution review; finite BMC cannot certify PASS'],
  'adapter_status':'PREPARATION_REQUIRED_NOT_NATIVE_TESTED',
  'reuse':'reuse library closure, capability probes and observation classifier; legacy final-netlist harness cannot run unchanged'}
 task['task_id']=digest(task);return task

def observe_verification(task,archive,expected_sha256):
 """Common saved verifier interface: checked identity + raw tool observation.

Even an unbounded solver marker remains UNKNOWN pending scope/model review.
Malformed receipts cannot unlock a dependent check or authorize execution.
"""
 if (not isinstance(task,dict) or task.get('schema')!='verieda.verification-task.v1'
     or task.get('kind')!='FORMAL_SYNTHESIS' or task.get('cap_seconds')!=CAP_SECONDS
     or task.get('task_id')!=digest({k:v for k,v in task.items() if k!='task_id'})):
  raise ValueError('invalid or mutated verifier task')
 if not _hex(expected_sha256):raise ValueError('verifier archive requires caller-trusted SHA256')
 p=pathlib.Path(archive)
 if not p.is_file() or p.stat().st_size>32*1024*1024 or _sha(p.read_bytes())!=expected_sha256:raise ValueError('verifier archive identity/budget mismatch')
 data=read_bundle(p);verify_bundle(data)
 receipt=_obj(data,'receipt.json')
 if (receipt.get('schema')!='verieda.verifier-receipt.v1' or receipt.get('task_id')!=task['task_id']
     or receipt.get('inputs')!=task['inputs'] or receipt.get('engine_sha256')!=task['inputs']['engine_sha256']):raise ValueError('verifier task/input/tool mismatch')
 rc=receipt.get('return_code');runtime=receipt.get('runtime_seconds');name=receipt.get('log_path')
 if type(rc) is not int or type(runtime) not in (float,int) or not math.isfinite(runtime) or not 0<=runtime<=CAP_SECONDS+(1 if rc==124 else 0):raise ValueError('invalid verifier exit/runtime')
 if not isinstance(name,str) or name not in data or len(data[name])>16*1024*1024:raise ValueError('missing/bounded raw verifier log required')
 obs=observe_yosys(rc,data[name].decode('utf-8-sig'))
 obs.update(task_id=task['task_id'],archive_sha256=expected_sha256,raw_log_sha256=_sha(data[name]),
  runtime_seconds=runtime,certification='NOT_CERTIFIED',execution_identity='UNAUTHENTICATED_REPORT')
 return obs

def plan_verification(subject,budget_seconds=0,formal_result=None,formal_sha256=None):
 """Choose next information-producing check, never another mapping sweep.

Budget is unspent verification native time, not queue/setup/billing time. Caps
are conservative admission limits, not predicted runtime or quantified benefit.
"""
 _validate(subject)
 if type(budget_seconds) is not int or not 0<=budget_seconds<=600:raise ValueError('verification budget must be integer 0..600')
 task=_formal_task(subject)
 plan={'schema':'verieda.verification-plan.v1','subject_id':subject['subject_id'],'design_acceptance':'NOT_EVALUATED',
  'execution_authorized':False,'next_check':None,'observation':None,'issues':[],
  'gates':{k:'NOT_RUN' for k in ('formal','physical','timing','constraints','adoption')},
  'budget':{'unspent_native_seconds':budget_seconds,'next_check_cap_seconds':CAP_SECONDS,'monetary_cost':None},
  'rationale':'check new mapping functionality before spending on physical QoR; no measured mapping gain yet',
  'downstream_checks':[
   {'kind':'PHYSICAL_FINAL','requires':['independently reviewed FORMAL_SYNTHESIS','separate execution authorization'],'inputs':['this synthesis netlist/ODB','frozen original SDC/platform/QoR'],'outputs':['new final netlist/ODB/SDC','GDS','routing DRC']},
   {'kind':'FINAL_ACCEPTANCE','requires':['PHYSICAL_FINAL'],'checks':['unbounded Formal on actual final netlist','setup/hold STA with parasitics','constraint semantics and coverage','GDS read and routing DRC']},
   {'kind':'ADOPTION','requires':['FINAL_ACCEPTANCE'],'checks':['independent full-flow receipt','same protected experiment/contract','real WNS gain and nonnegative slack','area overhead at most 10 percent']}],
  'reuse_limit':'synthesis ODB has no routed parasitics; historical final STA/proof cannot validate the new candidate'}
 if formal_result is not None or formal_sha256 is not None:
  try:
   obs=observe_verification(task,formal_result,formal_sha256);plan['observation']=obs
   category=obs['observation']
   plan['gates']['formal']='ERROR' if obs['formal_gate']=='ERROR' else 'TIMEOUT' if category=='TIMEOUT' else 'UNKNOWN'
   plan['decision']=('REVIEW_FORMAL_SCOPE' if category=='UNBOUNDED_PROOF_REPORTED' else
    'REVIEW_COUNTEREXAMPLE' if category=='COUNTEREXAMPLE_REPORTED' else
    'STOP_REVIEW_TIMEOUT' if category=='TIMEOUT' else
    'STOP_REVIEW_TOOL_FAILURE' if obs['formal_gate']=='ERROR' else 'REVIEW_UNPROVEN')
  except (ValueError,OSError,KeyError,TypeError,UnicodeError,zipfile.BadZipFile) as ex:
   plan['decision']='HOLD_VERIFIER_EVIDENCE';plan['gates']['formal']='UNKNOWN';plan['issues'].append(str(ex))
 elif not isinstance(subject['formal_contract'],str) or not subject['formal_contract'].strip():plan['decision']='HOLD_DECLARE_FORMAL_CONTRACT'
 elif budget_seconds<CAP_SECONDS:plan['decision']='STOP_BUDGET'
 else:plan.update(decision='PREPARE_FORMAL_CHECK',next_check=task)
 plan['plan_id']=digest(plan);return plan

def prepare_verification(state,artifact,expected_sha256,output,budget_seconds=0):
 """Materialize only bound candidate inputs, never copy old proof/RTL/SDC."""
 subject=load_subject(state,artifact,expected_sha256);plan=plan_verification(subject,budget_seconds)
 if plan['next_check'] is None:raise ValueError('no eligible verification preparation: '+plan['decision'])
 data=read_bundle(artifact);verify_bundle(data)
 if _sha(pathlib.Path(artifact).read_bytes())!=expected_sha256:raise ValueError('result changed during materialization')
 payload={'subject.json':(json.dumps(subject,indent=2)+'\n').encode(),
  'plan.json':(json.dumps(plan,indent=2)+'\n').encode(),
  'candidate.v':data['action/output/'+NETLIST],'candidate.odb':data['action/output/'+ODB]}
 if _sha(payload['candidate.v'])!=subject['target']['netlist_sha256'] or _sha(payload['candidate.odb'])!=subject['target']['odb_sha256']:raise ValueError('materialized candidate mismatch')
 out=_unlinked(output)
 if out.exists():raise ValueError('verification output already exists')
 manifest={'schema':'verieda.verification-package.v1','subject_id':subject['subject_id'],'task_id':plan['next_check']['task_id'],
  'files':{n:_sha(b) for n,b in payload.items()},'execution_status':'NOT_RUN','ready_for_cloud_execution':False,
  'missing':['candidate-aware Formal harness admission','frozen source/library runtime capability checks','separate cloud authorization'],
  'scope':'immutable verifier input handoff; no old proof carried over'}
 out.mkdir(parents=True,exist_ok=False)
 for n,b in payload.items():
  with (out/n).open('xb') as f:f.write(b)
 with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,indent=2);f.write('\n')
 return manifest

def verify_verification_package(directory):
 """Pre-admission input check only; PASS cannot certify a design or proof."""
 root=_unlinked(directory)
 names={'subject.json','plan.json','candidate.v','candidate.odb','manifest.json'}
 if not root.is_dir() or {p.name for p in root.iterdir()}!=names:raise ValueError('unexpected verification package contents')
 data={}
 for name in names:
  path=_unlinked(root/name)
  if not path.is_file() or not 0<path.stat().st_size<=16*1024*1024:raise ValueError('invalid verifier input payload')
  data[name]=path.read_bytes()
 manifest=_obj(data,'manifest.json');subject=_obj(data,'subject.json');plan=_obj(data,'plan.json')
 _validate(subject)
 if (manifest.get('schema')!='verieda.verification-package.v1'
     or manifest.get('files')!={n:_sha(b) for n,b in data.items() if n!='manifest.json'}
     or manifest.get('subject_id')!=subject['subject_id']
     or manifest.get('execution_status')!='NOT_RUN' or manifest.get('ready_for_cloud_execution') is not False):
  raise ValueError('verification package identity/manifest mismatch')
 try:expected=plan_verification(subject,plan['budget']['unspent_native_seconds'])
 except (KeyError,TypeError) as ex:raise ValueError('missing verifier plan budget') from ex
 if plan!=expected or not expected['next_check'] or manifest.get('task_id')!=expected['next_check']['task_id']:raise ValueError('verification task/plan mismatch')
 if any(_sha(data[n])!=subject['target'][key] for n,key in [('candidate.v','netlist_sha256'),('candidate.odb','odb_sha256')]):raise ValueError('verification target payload mismatch')
 return {'input_gate':'PASS','subject_id':subject['subject_id'],'task_id':manifest['task_id'],
  'execution_authorized':False,'ready_for_cloud_execution':False,'trust':'internal consistency; caller must authenticate source archive separately'}

def review_candidate(state,artifact,expected_sha256,budget_seconds=0,formal_result=None,formal_sha256=None,after_state=None,verification_package=None,formal_contract=None):
 """Candidate lifecycle. A candidate hold never writes the project Goal state.

 `after_state` must be independently loaded evidence, not an Agent verdict.
 Full adoption delegates to the existing independent identity/gate/QoR predicate.
 """
 subject=load_subject(state,artifact,expected_sha256)
 plan=plan_verification(subject,budget_seconds,formal_result,formal_sha256)
 statuses={'PREPARE_FORMAL_CHECK':'VERIFY_PENDING_CANDIDATE','STOP_BUDGET':'STOPPED_FOR_BUDGET',
  'HOLD_DECLARE_FORMAL_CONTRACT':'CONTRACT_HOLD','HOLD_VERIFIER_EVIDENCE':'EVIDENCE_HOLD',
  'REVIEW_FORMAL_SCOPE':'PROOF_REVIEW_PENDING','REVIEW_COUNTEREXAMPLE':'COUNTEREXAMPLE_REVIEW_PENDING',
  'STOP_REVIEW_TIMEOUT':'VERIFICATION_TIMEOUT','STOP_REVIEW_TOOL_FAILURE':'CANDIDATE_TOOL_BLOCKED','REVIEW_UNPROVEN':'VERIFICATION_UNKNOWN'}
 result={'schema':'verieda.candidate-lifecycle.v1','candidate_id':subject['candidate_id'],'subject_id':subject['subject_id'],
  'candidate_status':statuses[plan['decision']],'verification':plan,'adoption':None,
  'operation_status':'WAITING_FOR_AUTHORIZATION' if plan['next_check'] else 'NOT_SCHEDULED',
  'block_scope':'CANDIDATE_ONLY','execution_authorized':False,'design_acceptance':'NOT_EVALUATED'}
 if plan['decision']=='HOLD_VERIFIER_EVIDENCE':
  result['lifecycle_id']=digest(result);return result
 if verification_package is not None or formal_contract is not None:
  if verification_package is None or formal_contract is None or formal_result is None or formal_sha256 is None:raise ValueError('scope review requires package, contract and bound Formal archive')
  from .formal_review import inspect_formal
  review=inspect_formal(verification_package,formal_contract,formal_result,formal_sha256)
  result['formal_scope_review']=review
  if review.get('subject_id')!=subject['subject_id'] or review['scope_structure_gate']!='PASS_STATIC_CHECKS':
   result.update(candidate_status='EVIDENCE_HOLD',operation_status='NOT_SCHEDULED',scope_join_issue='scope evidence invalid or foreign to the current candidate')
   result['lifecycle_id']=digest(result);return result
 if after_state is not None:
  from .adoption import evaluate
  data=read_bundle(artifact);verify_bundle(data)
  if _sha(pathlib.Path(artifact).read_bytes())!=expected_sha256:raise ValueError('candidate result changed during adoption')
  adoption=evaluate(state,after_state,_obj(data,'action/package/candidate.json'))
  result.update(adoption=adoption,operation_status='NOT_SCHEDULED',
   design_acceptance=adoption['verdict'],
   candidate_status={'ACCEPTED':'ACCEPTED','REJECTED':'REJECTED','INCONCLUSIVE':'FINAL_VERIFICATION_INCOMPLETE'}[adoption['verdict']])
 result['lifecycle_id']=digest(result);return result
