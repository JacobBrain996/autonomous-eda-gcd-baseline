"""One offline decision over supplied evidence. No scheduler or execution authority.

The caller must supply its latest candidate/result or pinned action history;
absence is not proof that no other pending experiment exists. Profiles and archive hashes remain external
trust roots. Recommendations never grant permission or certify solver results.
"""
import copy,hashlib,math,re
from pathlib import Path
from .case import digest
from .policy import propose
from .action_results import inspect_action
from .verification import review_candidate
from .triage import diagnose

NEXT={
 'VERIFY_PENDING_CANDIDATE':'PREPARE_VERIFICATION_REQUEST',
 'STOPPED_FOR_BUDGET':'STOP_BUDGET',
 'CONTRACT_HOLD':'DECLARE_FORMAL_CONTRACT',
 'EVIDENCE_HOLD':'HOLD_EVIDENCE',
 'PROOF_REVIEW_PENDING':'REVIEW_PROOF_SCOPE',
 'COUNTEREXAMPLE_REVIEW_PENDING':'REVIEW_COUNTEREXAMPLE',
 'VERIFICATION_TIMEOUT':'REVIEW_TIMEOUT',
 'CANDIDATE_TOOL_BLOCKED':'REVIEW_TOOL_FAILURE',
 'VERIFICATION_UNKNOWN':'REVIEW_UNPROVEN',
 'ACCEPTED':'ACCEPT_CANDIDATE','REJECTED':'REJECT_CANDIDATE',
 'FINAL_VERIFICATION_INCOMPLETE':'CONTINUE_FINAL_VERIFICATION',
}

def _action_history(state,rows,result,expected_sha256):
 """Bounded saved actions, not caller-supplied outcome or billing records."""
 if not isinstance(rows,list) or len(rows)>16:raise ValueError('at most 16 action archive references required')
 seen={};candidates={};records=[];anchors=[];completed=[];size=0
 for row in rows:
  if not isinstance(row,dict) or set(row)!={'artifact','sha256'}:raise ValueError('history accepts only artifact and trusted sha256')
  h=row['sha256']
  if not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):raise ValueError('history requires trusted archive SHA256')
  if h in seen:continue
  p=Path(row['artifact']);size+=p.stat().st_size
  if size>32*1024*1024:raise ValueError('history input archive budget exceeded')
  obs=inspect_action(p,h);record=obs.get('history_record')
  if obs['evidence_gate']!='PASS' or obs.get('issues') or obs.get('state_id')!=state['state_id'] or not record:
   raise ValueError('history action invalid, incomplete or foreign')
  cid=record['candidate_id']
  if cid in candidates:raise ValueError('conflicting archives for one candidate require explicit review')
  candidates[cid]=h;seen[h]=True;records.append(record)
  anchors.append({'archive_sha256':h,'candidate_id':cid,'status':obs['status'],'runtime_seconds':record['runtime_seconds']})
  if obs['status']=='SYNTHESIS_COMPLETED':completed.append((p,h))
 if len(completed)>1:raise ValueError('multiple pending candidates require explicit review')
 if completed:
  p,h=completed[0]
  if result is not None and expected_sha256!=h:raise ValueError('current result conflicts with pending history')
  if result is None:result,expected_sha256=p,h
 elif result is not None and expected_sha256 not in seen:
  raise ValueError('explicit result must be included in supplied action history')
 spent=math.fsum(r['runtime_seconds'] for r in records)
 return records,{'evidence_gate':'PASS','unique_action_archives':len(anchors),'archives':anchors,
  'recorded_action_native_seconds':spent,'trust':'caller-trusted digests and bound saved action receipts; no global inventory or billing attestation'},result,expected_sha256


def decide(state,budget_seconds=0,result=None,expected_sha256=None,
           formal_result=None,formal_sha256=None,verification_package=None,formal_contract=None,after_state=None,action_history=None):
 # Reuse policy state/budget validation without spending or scheduling anything.
 control=propose(state,budget_seconds)
 history=None;history_issue=None;available=budget_seconds
 if action_history is not None:
  try:
   records,history,result,expected_sha256=_action_history(state,action_history,result,expected_sha256)
   control=propose(state,budget_seconds,records)
   available=math.floor(max(0,budget_seconds-history['recorded_action_native_seconds']))
   history.update(total_supplied_native_budget_seconds=budget_seconds,remaining_after_actions_seconds=available,
                  recorded_formal_native_seconds=0,remaining_after_supplied_native_seconds=available,observed_cost_exceeds_budget=history['recorded_action_native_seconds']>budget_seconds,
                  unaccounted_costs=['unsupplied executions','cloud setup/queue/job overhead','billing'])
  except (OSError,ValueError,KeyError,TypeError) as ex:
   history_issue=str(ex);history={'evidence_gate':'FAIL','issues':[history_issue]}
 if (result is None)!=(expected_sha256 is None):raise ValueError('candidate result and trusted SHA256 required together')
 if (formal_result is None)!=(formal_sha256 is None):raise ValueError('Formal result and trusted SHA256 required together')
 if (verification_package is None)!=(formal_contract is None):raise ValueError('scope package and contract required together')
 if history_issue is None and result is None and any(x is not None for x in (formal_result,verification_package,after_state)):raise ValueError('candidate result required for verification evidence')
 if verification_package is not None and formal_result is None:raise ValueError('scope review requires Formal evidence')
 report={'schema':'verieda.control-decision.v1','state_id':state['state_id'],
  'controller':{'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'source_manifest_sha256':hashlib.sha256((Path(__file__).resolve().parents[1]/'acceptance/PACKAGE_SHA256.json').read_bytes()).hexdigest(),
   'trust':'source hashes for replay; not a code audit or execution attestation'},
  'reference_provenance':copy.deepcopy(state.get('provenance',{})),
  'reference':copy.deepcopy({k:state[k] for k in ('design','platform','gates','metrics','formal','timing_analysis')}),
  'history':history,'proposal':None,'candidate':None,'action_observation':None,'failure':None,'issues':[],
  'next_action':'HOLD_EVIDENCE','execution_authorized':False,'design_acceptance':'NOT_EVALUATED',
  'project_status':'NOT_EVALUATED','budget':{'unspent_native_seconds':available,'monetary_cost':None,
   'scope':('total supplied action history plus supplied current Formal and future native budget' if action_history is not None else 'caller supplied remaining native budget')+'; excludes unsupplied runs, setup, queue and billing; no automatic reservation'},
  'trust':'supplied evidence snapshot only; caller must authenticate profiles, hashes and execution; no global experiment inventory'}
 if history_issue is not None:
  report['issues'].append(history_issue)
 elif result is None:
  report['proposal']=control
  selected=control['selected_candidate']
  report['next_action']=('INVESTIGATE_CRITICAL_CELLS' if selected and selected['action']=='critical_cell_sizing' else
                          'PREPARE_CANDIDATE' if selected else control['decision'])
 else:
  obs=inspect_action(result,expected_sha256);report['action_observation']=obs
  if obs['evidence_gate']!='PASS' or obs.get('issues') or obs.get('state_id')!=state['state_id']:
   report['issues'].append('candidate evidence invalid, incomplete or foreign; no fallback proposal')
  elif obs['status']=='SYNTHESIS_COMPLETED':
   if formal_result is not None:report['failure']=diagnose(formal_result,formal_sha256)
   if report['failure'] and (report['failure']['evidence_gate']!='PASS' or report['failure']['analysis_gate']!='PASS'):
    report['issues'].append('Formal diagnostic evidence invalid or contradictory; no adoption evaluation')
   else:
    lifecycle=review_candidate(state,result,expected_sha256,available,formal_result,formal_sha256,after_state=after_state,
                               verification_package=verification_package,formal_contract=formal_contract)
    report['candidate']=lifecycle;report['next_action']=NEXT[lifecycle['candidate_status']]
    report['design_acceptance']=lifecycle['design_acceptance']
    observation=lifecycle['verification']['observation']
    if history is not None and observation is not None:
     formal_seconds=observation['runtime_seconds']
     left=max(0,budget_seconds-history['recorded_action_native_seconds']-formal_seconds)
     history.update(recorded_formal_native_seconds=formal_seconds,formal_archive_sha256=formal_sha256,
                    remaining_after_supplied_native_seconds=math.floor(left),
                    observed_cost_exceeds_budget=history['recorded_action_native_seconds']+formal_seconds>budget_seconds)
     report['budget']['unspent_native_seconds']=math.floor(left)
  elif formal_result is not None or verification_package is not None or after_state is not None:
   report['issues'].append('verification evidence supplied without completed synthesis; no fallback proposal')
  elif obs['status'] in ('ERROR','TOOL_SIGNAL','TIMEOUT'):
   report['failure']=diagnose(result,expected_sha256)
   report['next_action']='REVIEW_TIMEOUT' if obs['status']=='TIMEOUT' else 'REVIEW_TOOL_FAILURE'
   if report['failure']['analysis_gate']!='PASS':report['next_action']='HOLD_EVIDENCE'
  elif obs['status']=='NOT_RUN':report['next_action']='REVIEW_ACTION_ADMISSION'
  else:report['issues'].append('unresolved action outcome; no fallback proposal')
 report['decision_id']=digest(report)
 return report
