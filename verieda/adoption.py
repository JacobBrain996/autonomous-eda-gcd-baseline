"""Independent acceptance predicate; never consumes a policy's claimed scores."""
import math
from .case import digest
from .policy import _bound_state,validate_candidate

def evaluate(before,after,candidate,budget_seconds=None):
    if budget_seconds is not None and (type(budget_seconds) is not int or not 0<=budget_seconds<=3600):raise ValueError("native comparison budget must be integer 0..3600")
    reject=[];unknown=[]
    malformed=any(not isinstance(x,dict) for x in (before,after,candidate))
    before=before if isinstance(before,dict) else {}
    after=after if isinstance(after,dict) else {}
    candidate=candidate if isinstance(candidate,dict) else {}
    result={'schema':'verieda.adoption.v0','verdict':'INCONCLUSIVE','rejections':reject,'missing_checks':unknown,
            'before_state_id':before.get('state_id'),'after_state_id':after.get('state_id'),
            'candidate_id':candidate.get('candidate_id'),'WNS_improvement_ns':None,
            'scope':'independent loaded-evidence predicate; synthetic unit cases are not EDA runs'}
    try:
        if malformed:raise ValueError('object inputs required')
        _bound_state(before);_bound_state(after)
        if validate_candidate(candidate,before)['legality']!='PASS':reject.append('ILLEGAL_OR_MUTATED_CANDIDATE')
        for key in ('design','platform','frozen','tools'):
            if before.get(key)!=after.get(key):reject.append('CHANGED_'+key.upper())
        old=before['provenance']['acceptance']['sha256'];new=after['provenance']['acceptance']['sha256']
        if old==new:reject.append('NO_INDEPENDENT_EXECUTION_EVIDENCE')
        if before['inputs']['6_final.v']==after['inputs']['6_final.v']:reject.append('UNCHANGED_NETLIST')
        execution=after.get('execution')
        if not isinstance(execution,dict):unknown.append('ACTION_EXECUTION_RECEIPT')
        elif (execution.get('candidate_id')!=candidate.get('candidate_id') or execution.get('state_id')!=before['state_id']
              or type(execution.get('return_code')) is not int or execution['return_code']!=0
              or execution.get('phase')!='RTL_TO_GDS' or execution.get('status')!='COMPLETED'
              or digest(execution.get('changes'))!=digest(candidate.get('changes'))):reject.append('ACTION_EXECUTION_MISMATCH')
        contract=before.get('formal',{}).get('contract')
        if not contract:unknown.append('REFERENCE_FORMAL_CONTRACT')
        elif after.get('formal',{}).get('contract')!=contract:reject.append('FORMAL_CONTRACT_CHANGED')
        for key in ('evidence','identity','rtl_simulation','physical','gds_generation','gds_read','router_drc','timing','constraints','formal'):
            value=after.get('gates',{}).get(key,'UNKNOWN')
            if value in ('FAIL','ERROR','FAIL_COUNTEREXAMPLE'):reject.append('FAILED_'+key.upper())
            elif value!=('PASS_RESET_CONTRACT_UNBOUNDED' if key=='formal' else 'PASS'):unknown.append(key.upper())
        def metric(state,name):
            value=state.get('metrics',{}).get(name,{}).get('value')
            if type(value) not in (int,float) or not math.isfinite(value):return None
            return value
        bw,aw=metric(before,'WNS'),metric(after,'WNS')
        ba,aa=metric(before,'stdcell_area'),metric(after,'stdcell_area')
        if bw is None or aw is None:unknown.append('WNS_COMPARISON')
        else:
            result['WNS_improvement_ns']=aw-bw
            if aw<=bw:reject.append('NO_WNS_IMPROVEMENT')
            if aw<0:reject.append('NEGATIVE_SETUP_SLACK')
        if ba is None or aa is None or ba<=0 or aa<=0:unknown.append('AREA_COMPARISON')
        elif aa>ba*1.10:reject.append('AREA_OVERHEAD_EXCEEDS_10_PERCENT')
    except (ValueError,KeyError,TypeError,OverflowError):unknown.append('MALFORMED_STATE_OR_CANDIDATE')
    result['verdict']='REJECTED' if reject else 'INCONCLUSIVE' if unknown else 'ACCEPTED'
    def observed(state,name):
        metrics=state.get('metrics',{});row=metrics.get(name,{}) if isinstance(metrics,dict) else {}
        v=row.get('value') if isinstance(row,dict) else None
        return v if type(v) in (int,float) and math.isfinite(v) else None
    comparison={}
    for name in ('WNS','TNS','stdcell_area','hold_slack'):
        bv,av=observed(before,name),observed(after,name)
        comparison[name]={'before':bv,'after':av,'delta':av-bv if bv is not None and av is not None else None,
                          'status':'AVAILABLE' if bv is not None and av is not None else 'NOT_AVAILABLE'}
    gain=comparison['WNS']['delta'];wns=comparison['WNS']['after']
    unbound=any(r.startswith(('CHANGED_','ILLEGAL_','ACTION_EXECUTION_MISMATCH','FORMAL_CONTRACT_CHANGED','NO_INDEPENDENT_EXECUTION')) for r in reject)
    failed=any(r in reject for r in ('FAILED_RTL_SIMULATION','FAILED_FORMAL','FAILED_PHYSICAL','FAILED_ROUTER_DRC','FAILED_GDS_GENERATION','FAILED_GDS_READ'))
    unbound=unbound or 'MALFORMED_STATE_OR_CANDIDATE' in unknown
    outcome=('VERIFICATION_INSUFFICIENT' if unbound else 'FUNCTIONAL_OR_PHYSICAL_CHECK_FAILED' if failed else
             'OPTIMIZATION_ACCEPTABLE' if result['verdict']=='ACCEPTED' else
             'METRIC_REGRESSION' if (gain is not None and gain<0) or 'AREA_OVERHEAD_EXCEEDS_10_PERCENT' in reject else
             'IMPROVED_BUT_CONSTRAINTS_UNMET' if gain is not None and gain>0 and (wns<0 or 'FAILED_TIMING' in reject) else
             'VERIFICATION_INSUFFICIENT' if unknown else 'NO_IMPROVEMENT')
    runtime=after.get('execution',{}).get('runtime_seconds') if isinstance(after.get('execution'),dict) else None
    valid_runtime=type(runtime) in (int,float) and math.isfinite(runtime) and runtime>=0
    stop=not unbound and budget_seconds is not None and valid_runtime and runtime>budget_seconds
    result.update(comparison=comparison,qor_outcome=outcome,outcome_class='STOP_BUDGET' if stop else outcome,
                  decision='STOP_BUDGET' if stop else 'ACCEPT_CANDIDATE' if result['verdict']=='ACCEPTED' else 'REJECT_CANDIDATE' if result['verdict']=='REJECTED' else 'CONTINUE_VERIFICATION',
                  budget={'cap_native_seconds':budget_seconds,'observed_native_seconds':runtime if valid_runtime else None,
                          'scope':'bound after execution receipt only; not campaign/job/billing time'},execution_authorized=False)
    result['evaluation_id']=digest(result)
    return result
