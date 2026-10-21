"""Bounded, read-only observations of native acceptance evidence.

Producer verdicts and logs cannot certify Formal or constraint equivalence.
The adapter does not execute a proof, Tcl, tools, or archive content.
"""
import hashlib, math, re, zipfile
from pathlib import Path
from .evidence import read_bundle, verify_bundle, object_json
from .formal import observe_yosys
from .sta_min import observe_hold
from .constraints import inspect_io_coverage,compare_sdc

PREFIX='final-acceptance/'
OUTPUT=PREFIX+'output/'

def _validation_coverage(data):
    """Describe actual importer limits; file presence is never certification.

    An empty check_setup report can mean no emitted warnings. It is not an
    inventory of checked objects, clocks, exceptions or unconstrained endpoints.
    Names for future hold/coverage evidence deliberately grant no parser support.
    """
    name=OUTPUT+'sta/coverage.rpt';raw=data.get(name)
    report={'path':name,'status':'NOT_AVAILABLE','bytes':None,'sha256':None}
    if raw is not None:
        report.update(status='PRESENT_UNINTERPRETED' if raw.strip() else 'EMPTY_NOT_A_CERTIFICATE',
                      bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    return {'schema':'verieda.validation-coverage.v1','coverage_report':report,
            'checker_capabilities':{'setup_wns_tns':'IMPLEMENTED_OBSERVATION_ONLY',
                                    'independent_hold':'OFFLINE_OBSERVER_IMPLEMENTED_NATIVE_UNVALIDATED',
                                    'constraint_coverage_certification':'NOT_IMPLEMENTED','io_literal_coverage':'IMPLEMENTED_STATIC_OBSERVER',
                                    'raw_formal_result':'OBSERVATION_ONLY_NOT_CERTIFIED'},
            'required_observations':['independent_min_delay_paths_and_wns_tns',
                                     'native_clock_and_endpoint_inventory',
                                     'unconstrained_objects_and_exceptions_inventory',
                                     'original_to_final_constraint_semantics'],
            'coverage_gate':'UNKNOWN','independent_hold_gate':'UNKNOWN',
            'can_certify_full_final_acceptance':False,
            'next_local_action':'implement and test missing validators before claiming complete native acceptance',
            'scope':'capabilities of this native bundle importer, not all VeriEDA modules; no timing/frozen-input/Goal mutation',
            'execution_authorized':False}


def _constraint_context_observation(data):
    root=OUTPUT+'constraints/';filename=root+'contexts.json'
    result={'schema':'verieda.constraint-context-observation.v1','observation':'NOT_AVAILABLE',
            'roles':{},'comparison':None,'full_constraint_gate':'UNKNOWN',
            'scope':'same final-ODB snapshots only; no original RTL-stage or physical clock-equivalence certificate',
            'execution_identity':'UNAUTHENTICATED_REPORT'}
    if filename not in data:return result
    def obj(name):
        value,duplicates=object_json(data,name)
        if duplicates or not isinstance(value,dict):raise ValueError('malformed context object '+name)
        return value
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    try:
        context=obj(filename);identity=obj(OUTPUT+'identity.json')
        if context.get('schema')!='verieda.native-constraint-context.v1' or set(context.get('roles',{}))!={'reference','candidate'}:raise ValueError('unsupported constraint context')
        if not isinstance(identity.get('sources'),dict):raise ValueError('missing source identity map')
        refs=[v for n,v in identity['sources'].items() if n.endswith('/constraint.sdc')]
        if len(refs)!=1:raise ValueError('ambiguous original SDC identity')
        expected={'reference':refs[0],'candidate':sha(data[PREFIX+'inputs/6_final.sdc'])}
        odb=sha(data[PREFIX+'inputs/6_final.odb']);observed={};snapshots={}
        for role in ('reference','candidate'):
            meta=context['roles'][role];base=root+role+'/'
            if meta['source_sdc_sha256']!=expected[role] or meta['odb_sha256']!=odb or type(meta['native_return_code']) is not int or meta['native_return_code']!=0:raise ValueError('snapshot input/exit binding mismatch')
            names=('evaluated.sdc','units.rpt','coverage.rpt','ports.tsv')
            if meta['outputs']!={n:sha(data[base+n]) for n in names}:raise ValueError('snapshot output hash mismatch')
            status=obj(base+'tool.log.status.json')
            if type(status.get('return_code')) is not int or status['return_code']!=0:raise ValueError('native snapshot process did not succeed')
            sdc=data[base+'evaluated.sdc'].decode('utf-8-sig');ports=data[base+'ports.tsv'].decode('utf-8-sig')
            coverage=inspect_io_coverage(sdc,ports)
            if coverage['observation']=='HOLD_PROFILE_OR_INVENTORY':raise ValueError('snapshot I/O profile unsupported: '+coverage.get('reason','unknown'))
            snapshots[role]=sdc
            observed[role]={'io_coverage':coverage,'source_sdc_sha256':expected[role],'odb_sha256':odb,
                            'outputs':meta['outputs'],'process_status_sha256':sha(data[base+'tool.log.status.json'])}
        for name in ('ports.tsv','units.rpt'):
            if data[root+'reference/'+name]!=data[root+'candidate/'+name]:raise ValueError('snapshot port/unit contexts differ')
        result.update(observation='BOUND_SNAPSHOTS_OBSERVED',roles=observed,
                      comparison=compare_sdc(snapshots['reference'],snapshots['candidate']),
                      context_manifest_sha256=sha(data[filename]),identity_record_sha256=sha(data[OUTPUT+'identity.json']))
    except (ValueError,KeyError,TypeError,AttributeError,RecursionError,UnicodeError) as ex:result.update(observation='HOLD_CONTEXT_BINDING',reason=str(ex))
    return result


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
        state['validation_coverage']=_validation_coverage(data)
        state['constraint_context_observation']=_constraint_context_observation(data)
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
    hold_log=OUTPUT+'sta/hold.log';hold_status=hold_log+'.status.json'
    if hold_log in data or hold_status in data:
        try:
            status=obj(hold_status)
            observation=observe_hold(status.get('return_code'),data[hold_log].decode('utf-8-sig'))
            observation['raw_log_sha256']=hashlib.sha256(data[hold_log]).hexdigest()
            state['hold_observation']=observation
            if observation['hold_gate']=='FAIL':state['gates']['timing']='FAIL';state['acceptance']='NOT_ACCEPTED'
        except (KeyError,ValueError,TypeError,UnicodeError) as ex:
            state['hold_observation']={'hold_gate':'UNKNOWN','observation':'HOLD_REPORT_FORMAT','issues':[str(ex)]}
    claims=state.get('producer_claims',{})
    if ((state['gates']['timing']=='FAIL' and claims.get('TIMING_GATE')=='PASS')
        or claims.get('baseline_pass') is True):
        issue('SUMMARY_CONTRADICTION','producer success claim is unsupported or contradicted by independent observations')
    return state
