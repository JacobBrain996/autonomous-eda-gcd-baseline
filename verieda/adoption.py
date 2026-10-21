"""Independent acceptance predicate; never consumes a policy's claimed scores."""
import math
from .case import digest
from .policy import _bound_state,validate_candidate

def evaluate(before,after,candidate):
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
    result['evaluation_id']=digest(result)
    return result
