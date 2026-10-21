"""Bounded, design-independent saved-log triage. No root-cause certification."""
import hashlib,re,pathlib,zipfile
from .case import digest
from .evidence import read_bundle,verify_bundle,object_json,name_ok

RULES=(
 ('SIGNAL_REPORTED',re.compile(r'child killed:\s*illegal instruction|^\s*(?:[^\n]*?:\s*)?(?:\d+\s+)?Illegal instruction(?:\s*\(core dumped\))?\s*$|terminated (?:by|with) signal (?:4|SIGILL)',re.I),'SIGILL'),
 ('TIMEOUT_REPORTED',re.compile(r'Interrupted SAT solver:\s*TIMEOUT!|TimeoutExpired|process timed out after \d',re.I),None),
 ('MODEL_OR_CAPABILITY_REPORTED',re.compile(r'Failed to import cell|ERROR:.*(?:unsupported cell|no such command|blackbox)|HOLD:.*(?:unsupported|blackbox|missing.*model)',re.I),None),
 ('COUNTEREXAMPLE_REPORTED',re.compile(r'model found for base case:\s*FAIL!|SAT proof finished - model found:\s*FAIL!',re.I),None))
PRIORITIES=(('SIGNAL_REPORTED','REVIEW_REPORTED_SIGNAL'),('TIMEOUT_REPORTED','REVIEW_TIMEOUT'),('MODEL_OR_CAPABILITY_REPORTED','REVIEW_MODEL_OR_CAPABILITY'),('ADMISSION_HOLD_REPORTED','REVIEW_ADMISSION_HOLD'),('COUNTEREXAMPLE_REPORTED','REVIEW_COUNTEREXAMPLE'),('POSSIBLE_SIGNAL_EXIT','REVIEW_POSSIBLE_SIGNAL'),('EXECUTION_ERROR_REPORTED','REVIEW_SAVED_EXECUTION_ERROR'))

def analyze_logs(data):
 result={'schema':'verieda.failure-triage.v1','analysis_gate':'PASS','findings':[],'issues':[],
  'faulting_executable':'NOT_AVAILABLE','instruction_set_cause':'NOT_ESTABLISHED','design_verdict':'NOT_EVALUATED',
  'execution_authorized':False,'automatic_retry':False,'next_action':'NO_FAILURE_CLASSIFIED',
  'scope':'reported saved signatures/exit records only; no process tracing, ISA diagnosis, witness replay or design verdict'}
 findings=result['findings'];hashes={}
 def add(kind,name,raw,line=None,signal=None,pid=None):
  if len(findings)>=128:raise ValueError('finding budget exceeded; partial report is not complete')
  if name not in hashes:hashes[name]=hashlib.sha256(raw).hexdigest()
  row={'kind':kind,'source':{'path':name,'line':line,'sha256':hashes[name]},'evidence_kind':'FILE_BOUND_REPORT'}
  if signal:row['signal']=signal
  if pid is not None:row['reported_pid']=pid
  findings.append(row)
 try:
  if not isinstance(data,dict) or any(not isinstance(n,str) or not isinstance(b,bytes) for n,b in data.items()):raise ValueError('bounded named byte payloads required')
  logs={n:b for n,b in data.items() if n.endswith('.log') and not n.startswith('environment/')}
  if sum(map(len,logs.values()))>32*1024*1024:raise ValueError('execution-log scan budget exceeded')
  for name,raw in sorted(data.items()):
   name_ok(name)
   if name in logs:
    for number,line in enumerate(raw.decode('utf-8',errors='replace').splitlines(),1):
     for kind,pattern,sig in RULES:
      if pattern.search(line):add(kind,name,raw,number,sig)
   elif re.fullmatch(r'status/[^/]+-return-code\.txt',name):
    text=raw.strip()
    if not re.fullmatch(rb'-?\d{1,3}',text):raise ValueError('malformed saved return code')
    rc=int(text)
    if rc in (132,137,139):add('POSSIBLE_SIGNAL_EXIT',name,raw)
    elif rc==124:add('TIMEOUT_REPORTED',name,raw)
    elif rc<0:add('SIGNAL_REPORTED',name,raw,signal={-4:'SIGILL',-9:'SIGKILL',-11:'SIGSEGV'}.get(rc,'SIGNAL_'+str(-rc)))
    elif rc:add('EXECUTION_ERROR_REPORTED',name,raw)
   elif name in ('receipt.json','action/output/action-execution.json'):
    receipt,duplicates=object_json(data,name)
    if duplicates or not isinstance(receipt,dict):raise ValueError('ambiguous execution receipt')
    if receipt.get('schema') not in ('verieda.verifier-receipt.v1','verieda.action-execution.v0'):continue
    if isinstance(receipt.get('status'),str) and receipt['status'].startswith('HOLD_'):add('ADMISSION_HOLD_REPORTED',name,raw)
    steps=receipt.get('steps')
    if not isinstance(steps,list) or len(steps)>16:raise ValueError('missing/bounded process chain required')
    for step in steps:
     if not isinstance(step,dict):raise ValueError('malformed process record')
     rc=step.get('return_code');child=step.get('child_return_code');timeout=step.get('timeout');sig=step.get('signal');pid=step.get('pid')
     if type(rc) is not int or type(timeout) is not bool:raise ValueError('invalid process exit/timeout')
     if sig is not None and (type(sig) is not int or not 1<=sig<=64):raise ValueError('invalid POSIX signal number')
     if child is not None:
      if type(child) is not int or sig!=(-child if child<0 else None) or (not timeout and rc!=child):raise ValueError('child exit/signal contradicts process record')
     elif sig is not None and (type(sig) is not int or rc>=0 or sig!=-rc):raise ValueError('unsubstantiated process signal')
     if pid is not None and (type(pid) is not int or pid<=0):raise ValueError('invalid process PID')
     if timeout:
      if rc!=124:raise ValueError('timeout return code contradiction')
      add('TIMEOUT_REPORTED',name,raw,pid=pid)
     elif rc<0:add('SIGNAL_REPORTED',name,raw,signal={-4:'SIGILL',-9:'SIGKILL',-11:'SIGSEGV'}.get(rc,'SIGNAL_'+str(-rc)),pid=pid)
     elif rc in (132,137,139):add('POSSIBLE_SIGNAL_EXIT',name,raw,pid=pid)
     elif rc:add('EXECUTION_ERROR_REPORTED',name,raw,pid=pid)
  kinds={f['kind'] for f in findings}
  for kind,action in PRIORITIES:
   if kind in kinds:result['next_action']=action;break
 except (ValueError,KeyError,TypeError,UnicodeError) as ex:
  result.update(analysis_gate='HOLD',next_action='HOLD_DIAGNOSTIC_EVIDENCE');result['issues'].append(str(ex))
 result['triage_id']=digest(result);return result

def diagnose(artifact,expected_sha256):
 try:
  p=pathlib.Path(artifact)
  if not isinstance(expected_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_sha256):raise ValueError('caller-trusted archive SHA256 required')
  if not p.is_file() or p.stat().st_size>128*1024*1024 or hashlib.sha256(p.read_bytes()).hexdigest()!=expected_sha256:raise ValueError('archive SHA/size mismatch')
  data=read_bundle(p);verify_bundle(data);result=analyze_logs(data)
  result.update(evidence_gate='PASS',archive_sha256=expected_sha256,trust='caller-trusted archive digest; no execution authentication')
 except (OSError,ValueError,KeyError,TypeError,UnicodeError,zipfile.BadZipFile) as ex:
  result=analyze_logs({});result.update(evidence_gate='FAIL',analysis_gate='HOLD',next_action='HOLD_DIAGNOSTIC_EVIDENCE',issues=[str(ex)])
 result.pop('triage_id',None);result['triage_id']=digest(result);return result
