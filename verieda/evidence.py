"""Read-only ORFS artifact adapter. No EDA execution or network access."""
import hashlib
import json
import math
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

LIMIT=128*1024*1024
FINAL='raw-logs/orfs-logs/6_report.json'
ROUTE='raw-logs/orfs-logs/5_2_route.json'

def name_ok(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or any(ord(c)<32 for c in name):
        raise ValueError('unsafe evidence path')
    if p.as_posix()!=name:raise ValueError('noncanonical evidence path')
    return name

def read_bundle(path):
    path=Path(path);data={}
    if path.is_file():
        with zipfile.ZipFile(path) as z:
            items=[i for i in z.infolist() if not i.is_dir()]
            if len(items)>5000 or sum(i.file_size for i in items)>LIMIT:raise ValueError('evidence budget exceeded')
            for i in items:
                name=name_ok(i.filename)
                if name in data or stat.S_ISLNK(i.external_attr>>16) or i.file_size>16*1024*1024:raise ValueError('duplicate, link, or oversized ZIP entry')
                data[name]=z.read(i)
    else:
        root=path.resolve()
        if path.is_symlink() or not path.is_dir():raise ValueError('artifact directory missing or linked')
        for p in path.rglob('*'):
            if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('linked artifact path')
            if p.is_file():
                if not p.resolve().is_relative_to(root) or p.stat().st_size>16*1024*1024:raise ValueError('unsafe or oversized file')
                data[name_ok(p.relative_to(path).as_posix())]=p.read_bytes()
                if len(data)>5000 or sum(map(len,data.values()))>LIMIT:raise ValueError('evidence budget exceeded')
    return data

def object_json(data,name):
    duplicates=set()
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:duplicates.add(k)
            out[k]=v
        return out
    def bad_constant(s):raise ValueError('nonfinite JSON constant')
    obj=json.loads(data[name].decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=bad_constant)
    return obj,duplicates

def verify_bundle(data):
    covered=set()
    for line in data['SHA256SUMS.txt'].decode('utf-8-sig').splitlines():
        escaped=line.startswith('\\');line=line[1:] if escaped else line
        digest,name=line.split('  ',1)
        if escaped:
            name=re.sub(r'\\([\\n])',lambda m:'\n' if m[1]=='n' else '\\',name)
        name=name_ok(name)
        if name in covered or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('invalid checksum entry')
        if hashlib.sha256(data[name]).hexdigest()!=digest:raise ValueError('payload SHA256 mismatch: '+name)
        covered.add(name)
    if covered!=set(data)-{'SHA256SUMS.txt'}:raise ValueError('checksum coverage mismatch')
    sizes,dups=object_json(data,'file-sizes.json')
    if dups or not isinstance(sizes,list):raise ValueError('invalid file size manifest')
    size_names=set()
    for item in sizes:
        name=name_ok(item['path'])
        if name in size_names or len(data[name])!=item['bytes']:raise ValueError('file size mismatch')
        size_names.add(name)
    if size_names!=set(data)-{'SHA256SUMS.txt','file-sizes.json'}:raise ValueError('size coverage mismatch')

def metric(data,path,key,unit):
    out={'value':None,'unit':unit,'status':'NOT_AVAILABLE','source':{'path':path,'key':key}}
    if path not in data:return out
    obj,duplicates=object_json(data,path)
    if not isinstance(obj,dict):raise ValueError('metric report must be an object: '+path)
    if key in duplicates:out['status']='AMBIGUOUS';return out
    value=obj.get(key)
    if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):out.update(value=value,status='AVAILABLE')
    return out

def inspect(path,expected_identity=None,expected_archive_sha=None):
    state={'schema':'verieda.state.v1','adapter':'orfs-artifact-v1','gates':{k:'UNKNOWN' for k in ('evidence','identity','rtl_simulation','physical','gds_generation','gds_read','timing','router_drc','formal','constraints')},
           'metrics':{},'issues':[],'acceptance':'UNKNOWN','scope':'offline evidence audit; no EDA rerun, formal proof, or foundry signoff'}
    gates=state['gates']
    def issue(kind,detail,source=None):state['issues'].append({'kind':kind,'detail':detail,'source':source})
    try:
        if expected_archive_sha:
            if not Path(path).is_file() or hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected_archive_sha:raise ValueError('trusted archive identity mismatch')
        data=read_bundle(path);verify_bundle(data);gates['evidence']='PASS'
        state['evidence']={'payload_files':len(data)-1,'trust':'EXPECTED_ARCHIVE_SHA256' if expected_archive_sha else 'CHECKSUM_CONSISTENCY_ONLY'}
    except (ValueError,KeyError,OSError,UnicodeError,zipfile.BadZipFile) as ex:
        gates['evidence']='FAIL';issue('EVIDENCE_INVALID',str(ex));state['acceptance']='EVIDENCE_INVALID';return state
    try:
        manifest,duplicates=object_json(data,'manifest.json')
        if duplicates or not isinstance(manifest,dict):raise ValueError('duplicate or malformed identity')
        state['design']={k:manifest.get(k) for k in ('design','platform','orfs_commit_actual','orfs_image','github_run_id','github_sha')}
        if expected_identity:
            expected=json.loads(Path(expected_identity).read_text(encoding='utf-8-sig'))
            if not isinstance(expected,dict):raise ValueError('expected identity must be an object')
            same=all(manifest.get(k)==v for k,v in expected.items())
            same= same and manifest.get('orfs_commit_actual')==expected.get('orfs_commit') and expected.get('orfs_image') in manifest.get('container_repo_digests_actual',[])
            gates['identity']='PASS' if same else 'FAIL'
            if not same:issue('IDENTITY_MISMATCH','external expected experiment identity does not match','manifest.json')
        else:issue('IDENTITY_UNANCHORED','no external expected experiment identity supplied')
        specs={'setup_slack':('finish__timing__setup__ws','ns'),'setup_TNS':('finish__timing__setup__tns','ns'),
               'hold_slack':('finish__timing__hold__ws','ns'),'hold_TNS':('finish__timing__hold__tns','ns'),
               'stdcell_area':('finish__design__instance__area__stdcell','um^2'),'setup_endpoint_count':('finish__timing__drv__setup_violation_count','count')}
        metrics={n:metric(data,FINAL,k,u) for n,(k,u) in specs.items()}
        metrics['router_drc']=metric(data,ROUTE,'detailedroute__route__drc_errors','count')
        ws=metrics['setup_slack'];metrics['WNS']={**ws,'value':min(0,ws['value']) if ws['value'] is not None else None}
        state['metrics']=metrics
        timing=[metrics[k] for k in ('setup_slack','setup_TNS','hold_slack','hold_TNS')]
        if all(m['status']=='AVAILABLE' for m in timing):
            if metrics['setup_TNS']['value']>0 or metrics['hold_TNS']['value']>0:issue('METRIC_INCONSISTENT','TNS cannot be positive',FINAL)
            else:
                gates['timing']='PASS' if all(m['value']>=0 for m in timing) else 'FAIL'
                if gates['timing']=='FAIL':issue('TIMING_VIOLATION','final setup/hold metrics contain negative slack',FINAL)
        else:issue('TIMING_EVIDENCE_INCOMPLETE','missing or ambiguous final timing metrics',FINAL)
        drc=metrics['router_drc']
        if drc['status']=='AVAILABLE' and drc['value']>=0 and int(drc['value'])==drc['value']:
            gates['router_drc']='PASS' if drc['value']==0 else 'FAIL'
            if drc['value']:issue('ROUTER_DRC_VIOLATION','routing violations remain',ROUTE)
        def rc(name):
            b=data.get('status/'+name+'-return-code.txt')
            return int(b.strip()) if b is not None else None
        physical=rc('physical');simulation=rc('simulation')
        if physical is not None:
            gates['physical']='PASS' if physical==0 else 'ERROR'
            if physical:issue('TIMEOUT' if physical==124 else 'KILLED_UNKNOWN' if physical in (137,-9) else 'TOOL_SIGNAL' if physical in (132,-4) else 'EXECUTION_ERROR','physical return code '+str(physical),'status/physical-return-code.txt')
        if simulation==0 and re.search(rb'TESTED_PASS cases=\d+',data.get('raw-logs/rtl-simulation.log',b'')):gates['rtl_simulation']='PASS'
        elif simulation is not None:gates['rtl_simulation']='ERROR'
        gds=data.get('gds/6_final.gds',b'');gates['gds_generation']='PASS' if gds else 'NOT_RUN'
        if gds:state['gds_sha256']=hashlib.sha256(gds).hexdigest()
        if gds and rc('gds-read')==0 and b'GDS_READ_GATE=PASS' in data.get('raw-logs/gds-read.log',b''):gates['gds_read']='PASS'
        declared=manifest.get('FORMAL_EQUIVALENCE_GATE')
        if declared is None and 'gates.json' in data:declared=object_json(data,'gates.json')[0].get('FORMAL_EQUIVALENCE_GATE')
        if isinstance(declared,str) and declared.startswith('NOT_RUN'):gates['formal']='NOT_RUN';issue('FORMAL_NOT_RUN','formal bypass is not proof','manifest.json')
        else:issue('FORMAL_UNVERIFIED','no independently validated proof adapter; a claimed PASS is insufficient')
        if 'gds/6_final.sdc' in data:
            state['constraints']={'sha256':hashlib.sha256(data['gds/6_final.sdc']).hexdigest(),'status':'UNKNOWN','reason':'original-to-final constraint semantics not independently verified'}
        state['critical_paths']=[]
        report_path='raw-logs/orfs-reports/6_finish.rpt'
        seen=set()
        for block in data.get(report_path,b'').decode('utf-8',errors='replace').split('Startpoint: ')[1:]:
            if 'Path Type: max' not in block:continue
            end=re.search(r'Endpoint: ([^\n]+)',block);group=re.search(r'Path Group: ([^\n]+)',block)
            slack=re.search(r'([-+\d.]+)\s+slack \(VIOLATED\)',block)
            if not (end and group and slack):continue
            start=block.splitlines()[0].split(' (')[0].strip();endpoint=end[1].split(' (')[0].strip()
            key=(start,endpoint,group[1].strip())
            if key in seen:continue
            seen.add(key)
            state['critical_paths'].append({'startpoint':start,'endpoint':endpoint,'group':key[2],
                'slack_ns_rounded':float(slack[1]),'precision_digits':len(slack[1].split('.')[-1]),
                'source':report_path,'all_endpoint_coverage':'UNKNOWN','cell_net_delay_totals':'NOT_AVAILABLE'})
        state['cost']={'physical_runtime_seconds':None,'simulation_runtime_seconds':None,'source':'runtime.json'}
        if 'runtime.json' in data:
            runtime,dups=object_json(data,'runtime.json')
            if isinstance(runtime,dict):
                for k in ('physical_runtime_seconds','simulation_runtime_seconds'):
                    v=runtime.get(k)
                    if k not in dups and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0:state['cost'][k]=v
        # A decision policy cannot write these gates. Constraint/formal proof adapters are intentionally still required.
        state['acceptance']='NOT_ACCEPTED' if any(v=='FAIL' for v in gates.values()) else 'UNKNOWN'
        state['next_actions']=[]
        if gates['identity']=='FAIL':state['next_actions'].append({'action':'resolve_identity_mismatch','requires_execution_authorization':False})
        elif gates['physical']=='ERROR':state['next_actions'].append({'action':'diagnose_saved_execution_logs','requires_execution_authorization':False})
        else:
            if gates['formal']!='PASS':state['next_actions'].append({'action':'verify_existing_final_netlist','requires_execution_authorization':True})
            if gates['timing']=='FAIL':state['next_actions'].append({'action':'analyze_saved_critical_paths','requires_execution_authorization':False})
            if gates['constraints']=='UNKNOWN':state['next_actions'].append({'action':'audit_constraint_semantics','requires_execution_authorization':False})
    except (ValueError,KeyError,TypeError,OSError,UnicodeError) as ex:
        issue('EVIDENCE_SEMANTIC_ERROR',str(ex));state['acceptance']='UNKNOWN'
    return state
