"""Deterministic V0 proposals. No subprocess, network, or design mutation."""
import copy,math
from .case import digest

def _bound_state(state):
    if not isinstance(state,dict):raise ValueError('state object required')
    raw={k:v for k,v in state.items() if k!='state_id'}
    if state.get('schema')!='verieda.design-state.v0' or state.get('state_id')!=digest(raw):raise ValueError('state identity mismatch')

def _candidate(state,action):
    mapping=action=='timing_mapping'
    c={'schema':'verieda.candidate.v0','state_id':state['state_id'],
       'action':action,'changes':{'ABC_AREA':0} if mapping else {'max_cells':3,'investigation_only':True},
       'protected':{k:copy.deepcopy(state[k]) for k in ('design','platform','frozen','tools','inputs')},
       'objective':{'metric':'WNS','direction':'maximize','max_area_ratio':1.10},
       'limits':{'jobs':1,'wall_seconds':600,'formal_seconds':300,'runner':'ubuntu-24.04-standard-public'},
       'execution_ready':False,
       'preconditions':['verify current ABC_AREA differs and frozen source supports option','prepare isolated flow override and rollback'] if mapping else
                       ['verify critical pins, slew, fanout, legal equivalent drive cells and parasitics','prepare bounded ECO adapter and rollback'],
       'required_verifiers':['identity','constraints','formal_same_contract','setup_hold','router_drc','gds_read'],
       'rationale':'cell delay dominates; test timing-oriented mapping without RTL/SDC changes' if mapping else
                   'investigate critical cells/buffering using slew, load and fanout before proposing an ECO',
       'expected_gain':None,'monetary_cost':None,'cost_semantics':'limits are caps, not forecasts'}
    c['candidate_id']=digest(c);return c

def validate_candidate(candidate,state):
    try:
        _bound_state(state)
        action=candidate.get('action')
        if action not in ('timing_mapping','critical_cell_sizing'):return {'legality':'FAIL','reason':'unsupported action'}
        expected=_candidate(state,action)
        if digest(candidate)!=digest(expected):return {'legality':'FAIL','reason':'candidate content or protected identity differs from allowed scope'}
        return {'legality':'PASS','scope':'proposal only; execution prerequisites unverified','execution_ready':False}
    except (ValueError,KeyError,TypeError):return {'legality':'FAIL','reason':'malformed or foreign candidate/state'}

def propose(state,budget_seconds=0,history=None):
    _bound_state(state)
    if type(budget_seconds) is not int or not 0<=budget_seconds<=600:raise ValueError('budget must be an integer in 0..600 seconds')
    history=[] if history is None else history
    if not isinstance(history,list) or len(history)>100:raise ValueError('history must contain at most 100 records')
    choices=[_candidate(state,x) for x in ('timing_mapping','critical_cell_sizing')]
    allowed={c['candidate_id'] for c in choices};seen=set();spent=0
    for row in history:
        if (not isinstance(row,dict) or set(row)!={'state_id','candidate_id','outcome','runtime_seconds'}
            or row['state_id']!=state['state_id'] or not isinstance(row['candidate_id'],str) or row['candidate_id'] not in allowed
            or row['outcome'] not in ('FAIL','UNKNOWN','TIMEOUT','ERROR','REJECTED','ACCEPTED')
            or type(row['runtime_seconds']) not in (int,float) or not math.isfinite(row['runtime_seconds']) or row['runtime_seconds']<0
            or row['candidate_id'] in seen):raise ValueError('invalid, duplicate or unrelated outcome history')
        seen.add(row['candidate_id']);spent+=row['runtime_seconds']
    blockers=[k for k,v in state['gates'].items() if v not in ('PASS','PASS_RESET_CONTRACT_UNBOUNDED')]
    result={'schema':'verieda.decision.v0','state_id':state['state_id'],'policy':'deterministic-delay-policy.v0',
            'execution_authorized':False,'acceptance_blockers':blockers,
            'offline_actions':['audit_constraint_semantics'] if state['gates'].get('constraints')!='PASS' else [],
            'budget':{'total_seconds':budget_seconds,'recorded_spent_seconds':spent,'remaining_seconds':max(0,budget_seconds-spent),
                      'scope':'caller-recorded history; not a scheduler or billing account'},
            'selected_candidate':None,'candidates':[],'outcome':'NOT_RUN'}
    if any(state['gates'].get(k)!='PASS' for k in ('evidence','identity')):result['decision']='HOLD_EVIDENCE'
    elif state['gates'].get('physical') in ('ERROR','TIMEOUT'):
        result['decision']='HOLD_TOOL_FAILURE';result['offline_actions'].append('inspect_saved_tool_failure')
    elif state['gates'].get('timing')!='FAIL':result['decision']='HOLD_NO_CONFIRMED_TIMING_TARGET'
    elif budget_seconds-spent<600:result['decision']='STOP_BUDGET'
    else:
        path=state.get('timing_analysis',{}).get('worst_path')
        valid_path=(isinstance(path,dict) and isinstance(path.get('endpoint'),str) and bool(path['endpoint'])
                    and all(type(path.get(k)) in (int,float) and math.isfinite(path[k]) and path[k]>=0
                            for k in ('data_cell_delay_ns','data_net_delay_ns')))
        if not valid_path or state.get('timing_analysis',{}).get('dominant_delay') not in ('CELL','NET','MIXED'):
            result['decision']='HOLD_PATH_EVIDENCE'
        else:
            if state['timing_analysis']['dominant_delay']!='CELL':choices.reverse()
            remaining=[c for c in choices if c['candidate_id'] not in seen]
            result['candidates']=[{'rank':i+1,'candidate':c,'legality':validate_candidate(c,state)} for i,c in enumerate(remaining)]
            result['selected_candidate']=remaining[0] if remaining else None
            result['decision']='PROPOSAL_REQUIRES_PREPARATION' if remaining else 'STOP_REVIEW_OUTCOMES'
    result['decision_id']=digest(result);return result
