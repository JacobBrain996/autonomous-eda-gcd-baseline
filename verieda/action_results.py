"""Bounded result recovery. Consistency/observations are not cloud attestation."""
import hashlib,json,math,pathlib,re,zipfile
from .case import digest
from .evidence import read_bundle,verify_bundle,object_json
from .execution import _unlinked,make_argv,design_paths,expected_effective

PREFIX='action/'
NETLIST=design_paths('gcd','nangate45')['netlist']
ODB=design_paths('gcd','nangate45')['odb']
PACKAGE=('state.json','candidate.json','manifest.json','effective.mk')
def output_names(state):
    paths=design_paths(state['design'],state['platform'])
    return ('action-execution.json','launcher-result.json','effective.log','synth.log',paths['netlist'],paths['odb'])

OUTPUTS=output_names({'design':'gcd','platform':'nangate45'})

def _hash(raw):return hashlib.sha256(raw).hexdigest()
def _obj(data,name):
    obj,duplicates=object_json(data,name)
    if duplicates or not isinstance(obj,dict):raise ValueError('invalid or duplicate JSON object '+name)
    return obj
def _number(value):return type(value) in (int,float) and math.isfinite(value) and value>=0

def _package(data):
    try:return _package_unchecked(data)
    except (KeyError,TypeError,IndexError,AttributeError,RecursionError) as ex:raise ValueError('malformed or incomplete historical action package') from ex

def _package_unchecked(data):
    raw={n:data[PREFIX+'package/'+n] for n in PACKAGE}
    manifest=_obj(data,PREFIX+'package/manifest.json');state=_obj(data,PREFIX+'package/state.json');candidate=_obj(data,PREFIX+'package/candidate.json')
    if manifest.get('schema')!='verieda.action-package.v0' or manifest.get('phase')!='SYNTHESIS_ONLY' or manifest.get('timeout_seconds')!=300:raise ValueError('unsupported historical action package')
    if manifest.get('files')!={n:_hash(b) for n,b in raw.items() if n!='manifest.json'}:raise ValueError('package file binding mismatch')
    if state.get('state_id')!=digest({k:v for k,v in state.items() if k!='state_id'}):raise ValueError('state content identity mismatch')
    if candidate.get('candidate_id')!=digest({k:v for k,v in candidate.items() if k!='candidate_id'}):raise ValueError('candidate content identity mismatch')
    if (candidate.get('schema')!='verieda.candidate.v0' or candidate.get('action')!='timing_mapping'
        or digest(candidate.get('changes'))!=digest({'ABC_AREA':0})
        or candidate.get('state_id')!=state['state_id'] or manifest.get('state_id')!=state['state_id']
        or manifest.get('candidate_id')!=candidate['candidate_id']):raise ValueError('foreign candidate/package binding')
    if candidate.get('protected')!={k:state[k] for k in ('design','platform','frozen','tools','inputs')}:raise ValueError('protected identity mismatch')
    sources=manifest.get('adapter_sources')
    if not isinstance(sources,dict) or not sources or any(not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) for h in sources.values()):raise ValueError('missing historical adapter source identities')
    return manifest,state,candidate

def seal_action(package,work,output):
    package=_unlinked(package);work=_unlinked(work);output=_unlinked(output)
    if output.exists():raise ValueError('result destination already exists')
    data={}
    def collect(folder,names,prefix):
        if not folder.is_dir():raise ValueError('result input directory missing')
        for name in names:
            path=_unlinked(folder/name)
            if not path.exists():continue
            if not path.is_file() or path.stat().st_size>16*1024*1024:raise ValueError('invalid or oversized result payload')
            raw=path.read_bytes()
            if len(raw)>16*1024*1024:raise ValueError('result grew beyond bound')
            data[prefix+name]=raw
    collect(package,PACKAGE,PREFIX+'package/')
    _,state,_=_package(data)
    collect(work,output_names(state),PREFIX+'output/')
    if not any(PREFIX+'output/'+n in data for n in ('action-execution.json','launcher-result.json')):raise ValueError('no action execution or launcher result to seal')
    if sum(map(len,data.values()))>128*1024*1024:raise ValueError('result total byte budget exceeded')
    data['file-sizes.json']=(json.dumps([{'path':n,'bytes':len(b)} for n,b in data.items()],indent=2)+'\n').encode()
    data['SHA256SUMS.txt']=''.join(_hash(b)+'  '+n+'\n' for n,b in data.items()).encode()
    if sum(map(len,data.values()))>128*1024*1024:raise ValueError('sealed metadata exceeds total byte budget')
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in data.items():archive.writestr(name,raw)
    return {'path':str(output),'sha256':_hash(output.read_bytes()),'bytes':output.stat().st_size,'files':len(data),'execution_authorized':False}

def inspect_action(artifact,expected_sha256=None,expected_candidate=None):
    result={'schema':'verieda.action-observation.v0','status':'UNKNOWN','evidence_gate':'UNKNOWN','issues':[],
            'design_acceptance':'NOT_EVALUATED','history_record':None,'execution_authorized':False,
            'scope':'saved synthesis-phase observations only; no proof, PPA improvement or authenticated cloud execution'}
    try:
        p=pathlib.Path(artifact)
        if p.is_file() and p.stat().st_size>128*1024*1024:raise ValueError('archive size limit exceeded')
        if expected_sha256:
            if not p.is_file() or p.stat().st_size>128*1024*1024 or _hash(p.read_bytes())!=expected_sha256:raise ValueError('trusted archive SHA mismatch')
        data=read_bundle(artifact);verify_bundle(data);result['evidence_gate']='PASS';result['files']=sorted(data)
        result['trust']='EXPECTED_ARCHIVE_SHA256' if expected_sha256 else 'CHECKSUM_CONSISTENCY_ONLY'
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,RecursionError,zipfile.BadZipFile) as ex:
        result['evidence_gate']='FAIL';result['issues'].append(str(ex));return result
    try:
        manifest,state,candidate=_package(data);cid=candidate['candidate_id']
        paths=design_paths(state['design'],state['platform'])
        allowed={PREFIX+'package/'+n for n in PACKAGE}|{PREFIX+'output/'+n for n in output_names(state)}|{'file-sizes.json','SHA256SUMS.txt'}
        if set(data)-allowed:raise ValueError('unexpected exported result payload')
        result.update(candidate_id=cid,state_id=state['state_id'],phase='SYNTHESIS_ONLY',historical_adapter_sources=manifest['adapter_sources'])
        if expected_candidate and cid!=expected_candidate:raise ValueError('expected candidate mismatch')
        receipt_name=PREFIX+'output/action-execution.json'
        if receipt_name not in data:
            launcher=_obj(data,PREFIX+'output/launcher-result.json')
            if launcher.get('candidate_id')!=cid or launcher.get('phase')!='SYNTHESIS_ONLY':raise ValueError('launcher candidate/phase mismatch')
            if launcher.get('status')=='NOT_RUN':result.update(status='NOT_RUN',next_action='obtain_separate_execution_authorization')
            else:result['issues'].append('launcher-only result; no process execution evidence')
            return result
        receipt=_obj(data,receipt_name)
        if PREFIX+'output/launcher-result.json' in data:
            launcher=_obj(data,PREFIX+'output/launcher-result.json')
            if any(launcher.get(k)!=receipt.get(k) for k in ('candidate_id','phase','status')):raise ValueError('launcher and execution receipt contradict each other')
        if (receipt.get('schema')!='verieda.action-execution.v0' or receipt.get('candidate_id')!=cid
            or receipt.get('state_id')!=state['state_id'] or receipt.get('phase')!='SYNTHESIS_ONLY'
            or digest(receipt.get('changes'))!=digest(candidate['changes'])):raise ValueError('receipt identity/scope mismatch')
        expected_sources={**manifest['support']['sources'],paths['rtl']:state['frozen']['rtl_sha256'],
                          paths['sdc']:state['frozen']['sdc_sha256'],**state['tools']}
        if receipt.get('source_tool_sha256')!=expected_sources:raise ValueError('frozen source/tool receipt mismatch')
        steps=receipt.get('steps');runtime=receipt.get('runtime_seconds');rc=receipt.get('return_code')
        if not isinstance(steps,list) or not 1<=len(steps)<=2 or not _number(runtime) or runtime>301 or type(rc) is not int:raise ValueError('missing/bounded measured process runtime or return code')
        for i,step in enumerate(steps):
            argv=step['argv'];target='verieda-effective' if i==0 else 'synth';log='effective.log' if i==0 else 'synth.log'
            if not isinstance(argv,list) or len(argv)<8 or not isinstance(argv[7],str) or not argv[7].startswith('WORK_HOME='):raise ValueError('invalid Make argv')
            if argv!=make_argv(argv[5],argv[7].split('=',1)[1],target,state['design'],state['platform']):raise ValueError('unexpected process command')
            if (type(step.get('return_code')) is not int or type(step.get('timeout')) is not bool
                or not _number(step.get('runtime_seconds')) or step['runtime_seconds']>301):raise ValueError('invalid process exit/runtime')
            if step['timeout'] and step['return_code']!=124:raise ValueError('per-step timeout/exit contradiction')
            if step.get('signal') is not None and (type(step['signal']) is not int or not 1<=step['signal']<=64):raise ValueError('invalid signal')
            if not step['timeout'] and step['return_code']>=0 and step.get('signal') is not None:raise ValueError('normal exit contradicts signal claim')
            if 'child_return_code' in step and (type(step['child_return_code']) is not int or (not step['timeout'] and step['child_return_code']!=step['return_code'])):raise ValueError('inconsistent child exit status')
            if 'child_return_code' in step and step.get('signal')!=(-step['child_return_code'] if step['child_return_code']<0 else None):raise ValueError('child return code contradicts signal')
            if 'pid' in step and (type(step['pid']) is not int or step['pid']<=0):raise ValueError('invalid recorded process PID')
            if _hash(data[PREFIX+'output/'+log])!=step['log_sha256']:raise ValueError('raw process log hash mismatch')
        if runtime+1e-3<sum(s['runtime_seconds'] for s in steps) or rc!=steps[-1]['return_code']:raise ValueError('inconsistent total runtime/return code')
        if len(steps)==2 and (steps[0]['return_code']!=0 or steps[0]['timeout']):raise ValueError('synthesis ran after failed effective-variable check')
        if len(steps)==2 and data[PREFIX+'output/effective.log']!=expected_effective(state['design'],state['platform']):raise ValueError('synthesis ran without exact effective variables')
        last=steps[-1];status=receipt.get('status')
        if last['timeout']:
            if rc!=124 or status!='TIMEOUT':raise ValueError('timeout status contradiction')
            observed='TIMEOUT';outcome='TIMEOUT';next_action='review_budget_and_timeout_logs_before_any_retry'
        elif rc<0:
            if last.get('signal')!=-rc or status!='ERROR':raise ValueError('signal/return code contradiction')
            observed='TOOL_SIGNAL';outcome='ERROR';next_action='inspect_saved_process_signal_without_guessing_fault_binary'
        elif rc!=0:
            if status!='ERROR':raise ValueError('nonzero process return code contradicts declared status')
            observed='ERROR';outcome='ERROR';next_action='inspect_saved_tool_failure'
        elif status=='SYNTHESIS_COMPLETED':
            if len(steps)!=2:raise ValueError('completed synthesis without two observed steps')
            for field,name in [('netlist',paths['netlist']),('odb',paths['odb'])]:
                raw=data.get(PREFIX+'output/'+name,b'')
                if not raw or receipt.get(field+'_path')!=name or _hash(raw)!=receipt.get(field+'_sha256'):raise ValueError('missing or mismatched completed synthesis output')
            if b'Using ABC speed script.' not in data[PREFIX+'output/synth.log']:raise ValueError('speed mapping not observed in raw log')
            observed='SYNTHESIS_COMPLETED';outcome='UNKNOWN';next_action='independently_verify_new_netlist_and_prepare_physical_followup'
        elif isinstance(status,str) and status.startswith('HOLD_'):
            observed='UNKNOWN';outcome='UNKNOWN';next_action='resolve_saved_preflight_or_missing_output_hold'
        else:raise ValueError('unsupported process/status combination')
        result.update(status=observed,next_action=next_action,return_code=rc,runtime_seconds=runtime,
                      signal_observation=last.get('signal'),process_pid=last.get('pid'),child_return_code=last.get('child_return_code'),
                      faulting_executable='NOT_AVAILABLE',run_identity_gate='UNKNOWN_EXTERNAL_EXECUTION_BINDING_REQUIRED',executed_argv=last['argv'],
                      history_record={'state_id':state['state_id'],'candidate_id':cid,'outcome':outcome,'runtime_seconds':runtime},
                      history_provenance={'receipt_sha256':_hash(data[receipt_name]),'archive_anchor':expected_sha256,
                                          'trust':'bound saved observations; caller must authenticate external execution'})
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,UnicodeError,RecursionError) as ex:
        result.update(status='UNKNOWN',history_record=None);result['issues'].append(str(ex))
    return result

def advance_action(state,artifact,expected_sha256,budget_seconds=0,history=None):
    """Read evidence itself, never accept an agent-supplied observation as proof."""
    from .policy import propose
    if not isinstance(expected_sha256,str) or not re.fullmatch('[0-9a-f]{64}',expected_sha256):raise ValueError('feedback requires caller-trusted archive SHA256')
    prior=[] if history is None else history
    control=propose(state,budget_seconds,prior)
    rows=[dict(row) for row in prior]
    observation=inspect_action(artifact,expected_sha256)
    result={'schema':'verieda.feedback.v0','state_id':state['state_id'],'observation':observation,
            'history':rows,'budget':control['budget'],'execution_authorized':False,
            'design_acceptance':'NOT_EVALUATED','decision':'HOLD_RESULT_EVIDENCE'}
    result['cost_scope']='saved native action duration only; cloud setup/queue/job duration and monetary cost NOT_AVAILABLE'
    record=observation['history_record']
    if observation.get('state_id') not in (None,state['state_id']):result['decision']='HOLD_FOREIGN_STATE'
    elif record:
        matching=[row for row in rows if row['candidate_id']==record['candidate_id']]
        if matching and digest(matching[0])!=digest(record):result['decision']='HOLD_CONFLICTING_HISTORY'
        else:
            if not matching:rows.append(dict(record))
            control=propose(state,budget_seconds,rows);result['budget']=control['budget']
            if observation['status']=='SYNTHESIS_COMPLETED':
                result['pending_verifiers']={k:'NOT_RUN' for k in ('formal_new_netlist','physical_flow','setup_hold','constraint_coverage','independent_adoption')}
                result['decision']='VERIFY_PENDING_CANDIDATE' if result['budget']['remaining_seconds']>0 else 'STOP_BUDGET'
                from .verification import load_subject,plan_verification
                try:
                    subject=load_subject(state,artifact,expected_sha256)
                    result['verification_handoff']=plan_verification(subject,int(result['budget']['remaining_seconds']))
                except (ValueError,OSError,KeyError,TypeError,UnicodeError) as ex:
                    result['verification_handoff']={'decision':'HOLD_VERIFICATION_PREPARATION','reason':str(ex),'execution_authorized':False}
            else:result['decision']='STOP_REVIEW_FAILURE'
    elif observation['status']=='NOT_RUN':result['decision']='AWAIT_SEPARATE_EXECUTION_AUTHORIZATION'
    result['feedback_id']=digest(result)
    return result
