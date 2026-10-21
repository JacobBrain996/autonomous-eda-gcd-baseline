"""Join immutable experiment evidence. Profiles are explicit external trust roots.

A reviewed verdict is reusable only for the pinned artifact, not a general
proof checker. New candidates need their own independently reviewed evidence.
"""
import copy,hashlib,json,math
from pathlib import Path
from .evidence import inspect,read_bundle,verify_bundle,object_json
from .native import inspect_acceptance

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def read_json(path,limit=1024*1024):
    p=Path(path)
    if p.stat().st_size>limit:raise ValueError('JSON size limit exceeded')
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    return json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))

def _archive(path,expected):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>128*1024*1024:raise ValueError('bounded archive required')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('archive identity mismatch')
    data=read_bundle(p);verify_bundle(data);return data

def _obj(data,name):
    value,duplicates=object_json(data,name)
    if duplicates or not isinstance(value,dict):raise ValueError('invalid object '+name)
    return value

def load_case(profile,smoke,acceptance):
    try:return _load_case(profile,smoke,acceptance)
    except (KeyError,TypeError,IndexError,OverflowError) as ex:raise ValueError('incomplete or malformed case evidence: '+str(ex)) from ex

def _load_case(profile,smoke,acceptance):
    if profile['schema']!='verieda.case-profile.v1':raise ValueError('unsupported case profile')
    if set(profile['inputs'])!={'6_final.odb','6_final.sdc','6_final.v','6_report.json'}:raise ValueError('complete final input binding required')
    sd=_archive(smoke,profile['smoke']['sha256']);nd=_archive(acceptance,profile['acceptance']['sha256'])
    manifest=_obj(sd,'manifest.json');prefix='final-acceptance/output/'
    source=_obj(nd,'final-acceptance/execution-source.json');identity=_obj(nd,prefix+'identity.json')
    for field,key in [('run_id','github_run_id'),('commit','github_sha')]:
        if str(manifest[key])!=profile['smoke'][field]:raise ValueError('Smoke run identity mismatch')
    for field,key in [('run_id','GITHUB_RUN_ID'),('commit','GITHUB_SHA')]:
        if source[key]!=profile['acceptance'][field]:raise ValueError('acceptance run identity mismatch')
    frozen=profile['frozen']
    if (manifest['design']!=profile['design'] or manifest['platform']!=profile['platform']
        or manifest['orfs_commit_actual']!=frozen['orfs_commit']
        or frozen['orfs_image'] not in manifest['container_repo_digests_actual']
        or identity['orfs_commit']!=frozen['orfs_commit'] or identity['image']!=frozen['orfs_image']):raise ValueError('frozen experiment mismatch')
    if (identity['sources'].get('/frozen/flow/designs/src/'+profile['design']+'/'+profile['design']+'.v')!=frozen['rtl_sha256']
        or identity['sources'].get('/frozen/flow/designs/'+profile['platform']+'/'+profile['design']+'/constraint.sdc')!=frozen['sdc_sha256']):raise ValueError('RTL or original constraints mismatch')
    for name,h in profile['inputs'].items():
        original=('raw-logs/orfs-logs/' if name=='6_report.json' else 'gds/')+name
        candidate='final-acceptance/inputs/'+name
        if sd[original]!=nd[candidate] or hashlib.sha256(nd[candidate]).hexdigest()!=h:raise ValueError('cross-run final input mismatch: '+name)
    base=inspect(smoke,expected_archive_sha=profile['smoke']['sha256'])
    native=inspect_acceptance(acceptance,profile['acceptance']['sha256'])
    if base['gates']['evidence']!='PASS' or native['gates']['evidence']!='PASS':raise ValueError('evidence adapter failure')
    gates=copy.deepcopy(base['gates']);gates['identity']='PASS';gates['formal']='UNKNOWN'
    gates['constraints']='UNKNOWN'
    metrics=copy.deepcopy(base['metrics'])
    for key in ('WNS','TNS'):
        m=native.get('metrics',{}).get(key)
        if m:metrics[key]={'value':m['value'],'unit':m['unit'],'status':'AVAILABLE','source':m['source']}
    paths=_obj(nd,prefix+'sta/paths.json')
    allpaths=paths['all_violating_paths'];endpoints=paths['all_violating_endpoints']
    if not isinstance(allpaths,list) or len(allpaths)>10000:raise ValueError('invalid path list')
    for path in allpaths:
        for key in ('slack_ns','data_cell_delay_ns','data_net_delay_ns'):
            v=path[key]
            if type(v) not in (int,float) or not math.isfinite(v):raise ValueError('invalid path delay')
        if path['slack_ns']>=0 or min(path['data_cell_delay_ns'],path['data_net_delay_ns'])<0:raise ValueError('invalid violating path')
    if len(set(endpoints))!=len(endpoints) or set(endpoints)!={p['endpoint'] for p in allpaths}:raise ValueError('endpoint coverage mismatch')
    if paths['WNS']!=metrics['WNS']['value'] or paths['TNS']!=metrics['TNS']['value']:raise ValueError('raw STA metric mismatch')
    if metrics['WNS']['value']<0:
        if not allpaths:raise ValueError('negative WNS without violating path coverage')
        endpoint_slack={}
        for path in allpaths:endpoint_slack[path['endpoint']]=min(path['slack_ns'],endpoint_slack.get(path['endpoint'],0))
        count=base['metrics'].get('setup_endpoint_count',{}).get('value')
        if (count!=len(endpoint_slack) or abs(min(endpoint_slack.values())-metrics['WNS']['value'])>5e-6
            or abs(sum(endpoint_slack.values())-metrics['TNS']['value'])>5e-6):raise ValueError('path slack/count/aggregate disagree with native timing evidence')
    worst=min(allpaths,key=lambda p:p['slack_ns']) if allpaths else None
    gates['timing']='FAIL' if metrics['WNS']['value']<0 or native['gates']['timing']=='FAIL' else 'UNKNOWN'
    formal={'gate':'UNKNOWN','observation':native.get('formal_observation',{}).get('observation','NOT_AVAILABLE'),
            'contract':None,'trust':'UNREVIEWED_ENGINE_REPORT'}
    review=profile.get('formal_review')
    if review:
        needed={'formal/proof.log','formal/prove.ys','formal/miter.il','formal/strengthened_miter.il'}
        if set(review['files'])!=needed:raise ValueError('incomplete formal review binding')
        for name,h in review['files'].items():
            if hashlib.sha256(nd[prefix+name]).hexdigest()!=h:raise ValueError('formal review hash mismatch')
        status=_obj(nd,prefix+'formal/proof.log.status.json')
        if (review['verdict']!='PASS_RESET_CONTRACT_UNBOUNDED' or status['return_code']!=0
            or formal['observation']!='UNBOUNDED_PROOF_REPORTED' or not review['contract'] or not review['provenance']):raise ValueError('review contradicts engine evidence')
        formal.update(gate=review['verdict'],contract=review['contract'],trust='EXTERNAL_PROFILE_REVIEW',provenance=review['provenance'])
        gates['formal']=review['verdict']
    cell=worst['data_cell_delay_ns'] if worst else 0;net=worst['data_net_delay_ns'] if worst else 0
    state={'schema':'verieda.design-state.v0','design':profile['design'],'platform':profile['platform'],
           'frozen':copy.deepcopy(frozen),'inputs':copy.deepcopy(profile['inputs']),
           'tools':identity['binaries'],'gates':gates,'metrics':metrics,'formal':formal,
           'timing_analysis':{'worst_path':worst,'violating_endpoints':len(endpoints),
                              'dominant_delay':'CELL' if cell>2*net else 'NET' if net>2*cell else 'MIXED',
                              'diagnosis':'delay contribution, not causal attribution'},
           'provenance':{'smoke':profile['smoke'],'acceptance':profile['acceptance'],'profile_sha256':digest(profile),
                         'trust':'caller supplies and reviews profile; not remote authentication'},
           'execution':_obj(nd,prefix+'action-execution.json') if prefix+'action-execution.json' in nd else None,
           'issues':base['issues']+native['issues'],'acceptance':'NOT_ACCEPTED' if gates['timing']=='FAIL' else 'UNKNOWN',
           'cost':{'currency_amount':None,'observed_smoke':base.get('cost',{})},
           'scope':'evidence-backed local planning; no EDA executed'}
    state['state_id']=digest(state)
    return state
