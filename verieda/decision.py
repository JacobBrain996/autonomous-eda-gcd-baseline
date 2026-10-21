"""One offline decision over supplied evidence. No scheduler or execution authority.

The caller must supply its latest candidate/result; absence is not proof that no
other pending experiment exists. Profiles and archive hashes remain external
trust roots. Recommendations never grant permission or certify solver results.
"""
import copy,hashlib
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

def decide(state,budget_seconds=0,result=None,expected_sha256=None,
           formal_result=None,formal_sha256=None,verification_package=None,formal_contract=None,after_state=None):
 # Reuse policy state/budget validation without spending or scheduling anything.
 control=propose(state,budget_seconds)
 if (result is None)!=(expected_sha256 is None):raise ValueError('candidate result and trusted SHA256 required together')
 if (formal_result is None)!=(formal_sha256 is None):raise ValueError('Formal result and trusted SHA256 required together')
 if (verification_package is None)!=(formal_contract is None):raise ValueError('scope package and contract required together')
 if result is None and any(x is not None for x in (formal_result,verification_package,after_state)):raise ValueError('candidate result required for verification evidence')
 if verification_package is not None and formal_result is None:raise ValueError('scope review requires Formal evidence')
 report={'schema':'verieda.control-decision.v1','state_id':state['state_id'],
  'controller':{'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'source_manifest_sha256':hashlib.sha256((Path(__file__).resolve().parents[1]/'acceptance/PACKAGE_SHA256.json').read_bytes()).hexdigest(),
   'trust':'source hashes for replay; not a code audit or execution attestation'},
  'reference_provenance':copy.deepcopy(state.get('provenance',{})),
  'reference':copy.deepcopy({k:state[k] for k in ('design','platform','gates','metrics','formal','timing_analysis')}),
  'proposal':None,'candidate':None,'action_observation':None,'failure':None,'issues':[],
  'next_action':'HOLD_EVIDENCE','execution_authorized':False,'design_acceptance':'NOT_EVALUATED',
  'project_status':'NOT_EVALUATED','budget':{'unspent_native_seconds':budget_seconds,'monetary_cost':None,
   'scope':'caller supplied remaining native budget; excludes setup, queue and billing; no automatic reservation'},
  'trust':'supplied evidence snapshot only; caller must authenticate profiles, hashes and execution; no global experiment inventory'}
 if result is None:
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
    lifecycle=review_candidate(state,result,expected_sha256,budget_seconds,formal_result,formal_sha256,after_state=after_state,
                               verification_package=verification_package,formal_contract=formal_contract)
    report['candidate']=lifecycle;report['next_action']=NEXT[lifecycle['candidate_status']]
    report['design_acceptance']=lifecycle['design_acceptance']
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
