"""Bounded, read-only observations of native acceptance evidence.

Producer verdicts and logs cannot certify Formal or constraint equivalence.
The adapter does not execute a proof, Tcl, tools, or archive content.
"""
import hashlib, math, re, zipfile
from pathlib import Path
from .evidence import read_bundle, verify_bundle, object_json
from .formal import observe_yosys

PREFIX='final-acceptance/'
OUTPUT=PREFIX+'output/'

def inspect_acceptance(path,expected_archive_sha=None):
    state={'schema':'verieda.native-observations.v1',
           'gates':{k:'UNKNOWN' for k in ('evidence','identity','timing','formal','constraints')},
           'issues':[],'acceptance':'UNKNOWN',
           'scope':'offline native bundle observations; no proof certification or baseline promotion'}
    def issue(kind,detail):state['issues'].append({'kind':kind,'detail':detail})
    try:
        if expected_archive_sha:
            if not re.fullmatch('[0-9a-f]{64}',expected_archive_sha) or not Path(path).is_file():
                raise ValueError('trusted ZIP SHA requires an archive and 64 lowercase hexadecimal digits')
            digest=hashlib.sha256()
            with Path(path).open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            actual=digest.hexdigest()
            if actual!=expected_archive_sha:raise ValueError('trusted archive identity mismatch')
        data=read_bundle(path);verify_bundle(data)
        state['gates']['evidence']='PASS'
        state['evidence']={'files':len(data),'trust':'EXPECTED_ARCHIVE_SHA256' if expected_archive_sha else 'CHECKSUM_CONSISTENCY_ONLY'}
    except (ValueError,KeyError,TypeError,OSError,UnicodeError,zipfile.BadZipFile) as ex:
        state['gates']['evidence']='FAIL';state['acceptance']='EVIDENCE_INVALID'
        issue('EVIDENCE_INVALID',str(ex));return state

    def obj(name):
        value,duplicates=object_json(data,name)
        if duplicates or not isinstance(value,dict):raise ValueError('malformed or duplicate JSON: '+name)
        return value
    try:
        source=obj(PREFIX+'execution-source.json')
        required=('GITHUB_REPOSITORY','GITHUB_RUN_ID','GITHUB_SHA','GITHUB_RUN_ATTEMPT','RUNNER_OS','RUNNER_ARCH')
        if any(not isinstance(source.get(k),str) or not source[k] for k in required):raise ValueError('incomplete execution claim')
        state['execution_claim']={k:source[k] for k in required}
        issue('EXECUTION_NOT_AUTHENTICATED','reported run/commit is not independently bound to a reviewed workflow and GitHub run')
    except (KeyError,ValueError,TypeError,UnicodeError) as ex:issue('IDENTITY_EVIDENCE_INCOMPLETE',str(ex))
    try:
        summary=obj(OUTPUT+'result.json')
        state['producer_claims']={k:summary.get(k) for k in ('TIMING_GATE','FORMAL_EQUIVALENCE_GATE','CONSTRAINT_EQUIVALENCE_GATE','baseline_pass')}
    except (KeyError,ValueError,TypeError,UnicodeError) as ex:issue('SUMMARY_EVIDENCE_INCOMPLETE',str(ex))
    try:
        metrics={}
        for name,label in [('wns','WNS'),('tns','TNS')]:
            filename=OUTPUT+'sta/'+name+'.rpt'
            text=data[filename].decode('utf-8-sig')
            found=re.findall(r'(?m)^\s*'+name+r'\s+max\s+(\S+)\s*$',text)
            if len(found)!=1:raise ValueError('missing or ambiguous setup metric: '+filename)
            value=float(found[0])
            if not math.isfinite(value) or value>0:raise ValueError('invalid nonpositive setup metric: '+filename)
            metrics[label]={'value':value,'unit':'ns','source':filename}
        wns,tns=(metrics[k]['value'] for k in ('WNS','TNS'))
        if (wns<0)!=(tns<0) or tns>wns:raise ValueError('inconsistent WNS/TNS')
        state['metrics']=metrics
        if wns<0:
            state['gates']['timing']='FAIL';state['acceptance']='NOT_ACCEPTED'
            issue('TIMING_VIOLATION','raw setup WNS/TNS violate timing; positive setup alone would not establish hold or constraint coverage')
        else:issue('TIMING_COVERAGE_INCOMPLETE','nonviolating setup reports alone do not prove hold/coverage/constraint acceptance')
    except (KeyError,ValueError,TypeError,UnicodeError) as ex:issue('TIMING_EVIDENCE_INCOMPLETE',str(ex))
    try:
        status=obj(OUTPUT+'formal/proof.log.status.json')
        rc=status.get('return_code')
        if type(rc) is not int:raise ValueError('proof return code must be an integer')
        raw=data[OUTPUT+'formal/proof.log']
        observation=observe_yosys(rc,raw.decode('utf-8-sig'))
        observation['raw_log_sha256']=hashlib.sha256(raw).hexdigest()
        state['formal_observation']=observation
        state['gates']['formal']=observation['formal_gate']
        issue('FORMAL_UNCERTIFIED','property/model/reset/output coverage and authenticated execution still require independent validation')
    except (KeyError,ValueError,TypeError,UnicodeError) as ex:issue('FORMAL_EVIDENCE_INCOMPLETE',str(ex))
    claims=state.get('producer_claims',{})
    if ((state['gates']['timing']=='FAIL' and claims.get('TIMING_GATE')=='PASS')
        or claims.get('baseline_pass') is True):
        issue('SUMMARY_CONTRADICTION','producer success claim is unsupported or contradicted by independent observations')
    return state
