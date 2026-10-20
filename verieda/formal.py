"""Classify tool observations, not the truth of unauthenticated proof claims.

Yosys marker reference: passes/sat/sat.cc, a5af9d690a43744bf6b2cc3dea2717c16b54621c.
No arbitrary log can create PASS or a verified counterexample verdict here.
"""
import hashlib

def observe_yosys(return_code,log):
    observation='UNRECOGNIZED';gate='UNKNOWN';low=log.lower()
    if return_code==124 or 'interrupted sat solver: timeout!' in low:observation='TIMEOUT'
    elif return_code in (137,-9):observation='KILLED_UNKNOWN';gate='ERROR'
    elif return_code<0 or return_code>=128 or 'illegal instruction' in low:observation='TOOL_SIGNAL';gate='ERROR'
    elif any(s in low for s in ('no such command','not part of the design','unsupported cell','failed to import cell','blackbox')):observation='MODEL_OR_CAPABILITY_GAP'
    elif 'model found for base case: fail!' in low or 'sat proof finished - model found: fail!' in low:observation='COUNTEREXAMPLE_REPORTED'
    elif 'reached maximum number of time steps -> proof failed.' in low:observation='UNPROVEN_BOUND_EXHAUSTED'
    elif return_code!=0:observation='TOOL_ERROR';gate='ERROR'
    elif 'induction step proven: success!' in low:observation='UNBOUNDED_PROOF_REPORTED'
    elif 'proved base case for' in low or 'sat proof finished - no model found: success!' in low:observation='FINITE_OR_COMBINATIONAL_SUCCESS'
    return {'schema':'verieda.formal-observation.v1','observation':observation,'formal_gate':gate,
            'return_code':return_code,'text_sha256_utf8':hashlib.sha256(log.encode()).hexdigest(),
            'scope':'log classification only; execution identity, exact property, initialization, model coverage and proof/witness are not independently validated'}
