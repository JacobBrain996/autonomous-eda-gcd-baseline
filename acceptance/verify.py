"""One existing-netlist acceptance job; missing capabilities always HOLD."""
import argparse, hashlib, json, math, os, re, subprocess, sys, time, zipfile
from pathlib import Path, PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verieda.formal import observe_yosys
from verieda.constraints import compare_sdc
from verieda.liberty import subset_liberty
from verieda.invariants import strengthen_miter

class FormalCounterexample(RuntimeError):pass

COMMIT='3a964e13f11a4e435aac01ffa14db0a7d2853720'
IMAGE='openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9'
ARCHIVE_SHA='7dbdda5dd2e4d3edff841cda2bf2f7ab26099272d3bec4a0294a57e807001d84'
INPUTS={'6_final.odb':'2707181d3787009955eeb245acfc02fffd3e5c570c8e391aa6b1d2502fa415c4',
 '6_final.sdc':'112a077b756cada0fab67b2061733207a9cd7ac99b3e98454cabcad5aec7aa77',
 '6_final.v':'0d95240b149d075713b919c9bc3d059e296272da95331dc25635ff17016eed9a',
 '6_report.json':'c4504e958b01244433e2acb7a6de89ffe45acd108370cb6e43bf79275d0706fd'}
SOURCES={'designs/nangate45/gcd/constraint.sdc':'952a1a0a6de30877f585ee924004ce66151ff8325ec77e274fd92d1fdbf36582',
 'designs/src/gcd/gcd.v':'5009f224876d39e5e77e59ee1528cb0d2a03697251f0971b77cf3e8b0426dd3e',
 'platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib':'8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1',
 'platforms/nangate45/setRC.tcl':'521df813bf4da9d7400df33e3f680c9a328cc720830dbfca1188083741503fa5',
 'platforms/nangate45/rcx_patterns.rules':'2f65fafbe2c704b378563c53a680b93cef080c2799997019d43df7d1e5a563e9'}
YOSYS='/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys'
OPENROAD='/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad'
BINARIES={YOSYS:'5cd52bc790d39b1e59a88112e9132ef8de338c2a26e4b0df8222d937e65bab92',
 OPENROAD:'7d11382dd5197f40858da92a7ac7c4e32fdeb3f9985a04e77a04e61e4fbfc96e'}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x): Path(p).write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def safe_name(n):
    if PurePosixPath(n).is_absolute() or '..' in PurePosixPath(n).parts or '\\' in n or ':' in n: raise ValueError('HOLD unsafe archive name')
    return n
def restore(archive,out):
    if sha(archive)!=ARCHIVE_SHA: raise ValueError('HOLD wrong Smoke archive')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or len(z.namelist())!=len(set(z.namelist())): raise ValueError('HOLD ZIP integrity')
        for n in z.namelist(): safe_name(n)
        m=json.loads(z.read('manifest.json'))
        if (m['github_run_id']!='38226418563' or m['github_sha']!='9644bb3f8ed42bb3d5f23acc267e1235bc089496'
            or m['orfs_commit_actual']!=COMMIT or IMAGE not in m['container_repo_digests_actual']): raise ValueError('HOLD source identity')
        for n,h in INPUTS.items():
            b=z.read('raw-logs/orfs-logs/'+n if n.endswith('.json') else 'gds/'+n)
            if hashlib.sha256(b).hexdigest()!=h: raise ValueError('HOLD input SHA')
            with (out/n).open('xb') as f: f.write(b)
    return INPUTS.copy()
def package_check(root=Path(__file__).resolve().parents[1]):
    root=Path(root).resolve()
    m=json.loads((root/'acceptance/PACKAGE_SHA256.json').read_text())
    if m.get('schema')!='verieda.native-acceptance-package.v1' or not isinstance(m.get('files'),dict) or not 1<=len(m['files'])<=64:raise ValueError('HOLD package manifest schema')
    for name,h in m['files'].items():
        safe_name(name);p=root/name
        if p.is_symlink() or not p.resolve().is_relative_to(root) or not p.is_file() or not re.fullmatch('[0-9a-f]{64}',h) or sha(p)!=h:raise ValueError('HOLD package missing/changed: '+name)
def fetch():
    api='repos/JacobBrain996/autonomous-eda-gcd-baseline/actions/artifacts/11736162790'
    m=json.loads(subprocess.check_output(['gh','api',api],timeout=30))
    if m['expired'] or m['workflow_run']['head_sha']!='9644bb3f8ed42bb3d5f23acc267e1235bc089496' or m['size_in_bytes']!=3202166: raise ValueError('HOLD artifact metadata')
    b=subprocess.check_output(['gh','api',api+'/zip'],timeout=60)
    if len(b)!=3202166 or hashlib.sha256(b).hexdigest()!=ARCHIVE_SHA: raise ValueError('HOLD artifact digest')
    p=Path('evidence/final-acceptance');p.mkdir(parents=True,exist_ok=True)
    with (p/'smoke.zip').open('xb') as f:f.write(b)
    restore(p/'smoke.zip',p/'inputs')
    write(p/'artifact-source.json',{'run_id':38226418563,'artifact_id':11736162790,'zip_sha256':ARCHIVE_SHA})
def formal_verdict(rc,log):
    obs=observe_yosys(rc,log)['observation']
    if obs=='UNBOUNDED_PROOF_REPORTED' and rc==0:return 'PASS_RESET_CONTRACT_UNBOUNDED'
    if obs=='COUNTEREXAMPLE_REPORTED':return 'FAIL_COUNTEREXAMPLE'
    if obs=='TIMEOUT':return 'UNKNOWN_TIMEOUT'
    if obs=='MODEL_OR_CAPABILITY_GAP':return 'UNKNOWN_MODEL_OR_CAPABILITY'
    if obs in ('TOOL_SIGNAL','TOOL_ERROR','KILLED_UNKNOWN'):return 'ERROR_TOOL'
    return 'UNKNOWN_UNPROVEN'
def counterexample_record(path):
    try:
        obj=json.loads(Path(path).read_text())
        rows=obj.get('signal',[])
        if not isinstance(rows,list) or not any(isinstance(r,dict) and r.get('name')=='mismatch' and '1' in r.get('wave','') for r in rows):return None
        return {'path':str(path),'sha256':sha(path),'mismatch_seen':True,'scope':'solver-produced WaveJSON; not an independent simulation replay'}
    except (OSError,ValueError,TypeError,AttributeError):return None
def require_models(used,models):
    if not used.issubset(models): raise ValueError('HOLD missing functional cell models')
    for c in used:
        a=models[c].get('attributes',{})
        if str(a.get('blackbox','0')).strip('0'): raise ValueError('HOLD blackbox functional model '+c)
        if not models[c].get('cells'):
            ports=models[c].get('ports',{})
            ins={b for p in ports.values() if p['direction']=='input' for b in p['bits']}
            outs=[b for p in ports.values() if p['direction']=='output' for b in p['bits']]
            if not outs or any(b not in ins and b not in ('0','1') for b in outs):raise ValueError('HOLD empty/unconnected functional model '+c)
def require_model_closure(discovered,used,models):
    if set(used)!=set(discovered) or set(models)!=set(discovered):raise ValueError('HOLD functional model/link/discovery closure differs')
    require_models(set(used),models)

def require_sta_identity(wns,tns,count):
    if not math.isfinite(wns) or not math.isfinite(tns):raise ValueError('HOLD nonfinite STA result')
    if abs(wns+0.161583)>5e-6 or abs(tns+7.08646)>5e-6 or count!=51: raise ValueError('HOLD reconstructed STA does not match Smoke')
def run(cmd,log,seconds,env=None):
    start=time.monotonic()
    with Path(log).open('wb') as f:
        try: rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=max(1,seconds),env=env).returncode
        except subprocess.TimeoutExpired: rc=124
    write(str(log)+'.status.json',{'argv':cmd,'return_code':rc,'runtime_seconds':time.monotonic()-start})
    return rc
def identity():
    sources={str(Path('/frozen/flow')/n):h for n,h in SOURCES.items()}
    for p,h in {**sources,**BINARIES}.items():
        if sha(p)!=h: raise ValueError('HOLD frozen file identity '+p)
    for n,h in INPUTS.items():
        if sha(Path('/inputs')/n)!=h: raise ValueError('HOLD restored input '+n)
    write('/work/identity.json',{'orfs_commit':COMMIT,'image':IMAGE,'sources':sources,'binaries':BINARIES,'inputs':INPUTS,
        'tool_versions':{p:subprocess.check_output([p,'-V' if p==YOSYS else '-version'],timeout=10).decode(errors='replace').strip() for p in BINARIES},
        'python':{'path':sys.executable,'sha256':sha(sys.executable),'version':sys.version},
        'hooks':{p.name:sha(p) for p in Path('/audit').iterdir() if p.is_file()},
        'verieda_modules':{p.name:sha(p) for p in Path('/verieda').glob('*.py')},
        'proof_contract':'two forced synchronous reset edges; every output thereafter; arbitrary future defined inputs',
        'baseline_promoted':False})
def require_proof_capabilities(text):
    if 'no such command' in text.lower():raise ValueError('HOLD missing Yosys command')
    header='    sat [options] [selection]'
    if text.count(header)!=1:raise ValueError('HOLD missing/ambiguous SAT help section')
    sat=text.split(header,1)[1]
    declarations=re.findall(r'(?m)^ {4}(-[A-Za-z0-9_-]+(?:,[ \t]+-[A-Za-z0-9_-]+)*)(?=[ \t]|$)',sat)
    options={v for declaration in declarations for v in re.findall(r'-[A-Za-z0-9_-]+',declaration)}
    required={'-seq','-tempinduct','-maxsteps','-prove','-verify','-timeout','-enable_undef','-set-def-inputs','-set-init-def','-dump_json','-show','-show-inputs','-show-regs'}
    missing=sorted(required-options)
    if missing:raise ValueError('HOLD missing SAT options: '+', '.join(missing))

def report_sections(text,names):
    allowed={'units','wns','tns'}
    if not names or len(set(names))!=len(names) or not set(names)<=allowed:raise ValueError('HOLD invalid report request')
    markers=list(re.finditer(r'(?m)^VERIEDA_REPORT_(BEGIN|END) ([^\r\n]+)\r?$',text))
    expected=[(kind,name) for name in names for kind in ('BEGIN','END')]
    if [m.groups() for m in markers]!=expected:raise ValueError('HOLD missing/duplicate/out-of-order native report markers')
    reports={}
    for i,name in enumerate(names):
        value=text[markers[2*i].end():markers[2*i+1].start()].strip('\r\n')
        if not value.strip():raise ValueError('HOLD empty native report '+name)
        reports[name]=value+'\n'
    return reports

def capture_reports(folder,names):
    folder=Path(folder)
    reports=report_sections((folder/'tool.log').read_text(encoding='utf-8'),names)
    for name,value in reports.items():
        with (folder/(name+'.rpt')).open('x',encoding='utf-8',newline='\n') as f:f.write(value)

def formal():
    d=Path('/work/formal');d.mkdir(exist_ok=True);started=time.monotonic()
    def budget():
        remaining=300-(time.monotonic()-started)
        if remaining<=0:raise TimeoutError('HOLD 300-second total Formal budget')
        return remaining
    helpcmd='; '.join('help '+c for c in ['read_liberty','read_verilog','read_rtlil','write_rtlil','write_json','design','hierarchy','proc','flatten','memory_map','opt','dffunmap','opt_clean','rename','check','sat'])
    rc=run([YOSYS,'-Q','-T','-p',helpcmd],d/'capabilities.log',min(15,budget()))
    helptext=(d/'capabilities.log').read_text(errors='replace')
    if rc:raise ValueError('HOLD Yosys help return code '+str(rc))
    require_proof_capabilities(helptext)
    frozen_lib=Path('/frozen/flow/platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib')
    # Discover the complete instance-type set without importing any library.
    discover='read_verilog /inputs/6_final.v\nwrite_json /work/formal/unlinked.json\n'
    (d/'discover.ys').write_text(discover,encoding='utf-8')
    if run([YOSYS,'-Q','-T','-s',str(d/'discover.ys')],d/'discover.log',min(15,budget())):raise ValueError('HOLD final netlist cell discovery')
    modules=json.loads((d/'unlinked.json').read_text(encoding='utf-8'))['modules']
    if set(modules)!={'gcd'}:raise ValueError('HOLD unexpected netlist module closure')
    discovered={c['type'] for c in modules['gcd']['cells'].values()}
    if len(discovered)!=39:raise ValueError('HOLD unexpected discovered cell coverage')
    raw=frozen_lib.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCES['platforms/nangate45/lib/NangateOpenCellLibrary_typical.lib']:raise ValueError('HOLD functional library source identity')
    derived,selection=subset_liberty(raw,discovered)
    lib=str(d/'functional-used.lib')
    with Path(lib).open('xb') as f:f.write(derived)
    selection.update(netlist_sha256=sha('/inputs/6_final.v'),discovery_json_sha256=sha(d/'unlinked.json'),engine_sha256=sha(YOSYS))
    write(d/'library-selection.json',selection)
    prep=f'''read_liberty {lib}
write_json /work/formal/models.json
design -reset
read_verilog /frozen/flow/designs/src/gcd/gcd.v
hierarchy -check -top gcd
proc; flatten; memory_map; opt; dffunmap; opt_clean
rename gcd gold_core
write_rtlil /work/formal/gold.il
design -reset
read_liberty {lib}
read_verilog /inputs/6_final.v
hierarchy -check -top gcd
write_json /work/formal/gate_linked.json
proc; flatten; opt; dffunmap; opt_clean
rename gcd gate_core
write_rtlil /work/formal/gate.il
design -reset
read_rtlil /work/formal/gold.il
read_rtlil /work/formal/gate.il
read_verilog -formal -sv /audit/miter.v
hierarchy -check -top acceptance_miter
proc; flatten; memory_map; opt; dffunmap; opt_clean; check -assert
write_json /work/formal/miter.json
write_rtlil /work/formal/miter.il
'''
    (d/'prepare.ys').write_text(prep)
    if run([YOSYS,'-Q','-T','-s',str(d/'prepare.ys')],d/'prepare.log',min(60,budget())):raise ValueError('HOLD functional model/RTL preparation')
    if sha(d/'gold.il')==sha(d/'gate.il'):raise ValueError('HOLD gold and gate normalized identities unexpectedly identical')
    linked=json.loads((d/'gate_linked.json').read_text())['modules']['gcd']
    used={c['type'] for c in linked['cells'].values()}
    models=json.loads((d/'models.json').read_text())['modules']
    require_model_closure(discovered,used,models)
    if len(used)!=39:raise ValueError('HOLD unexpected cell coverage')
    expected={'clk':('input',1),'reset':('input',1),'req_val':('input',1),'resp_rdy':('input',1),'req_msg':('input',32),'req_rdy':('output',1),'resp_val':('output',1),'resp_msg':('output',16)}
    if set(linked['ports'])!=set(expected):raise ValueError('HOLD unexpected top ports')
    for n,(direction,width) in expected.items():
        if linked['ports'][n]['direction']!=direction or len(linked['ports'][n]['bits'])!=width:raise ValueError('HOLD top interface')
    top=json.loads((d/'miter.json').read_text())['modules']['acceptance_miter'];clock=top['ports']['clk']['bits']
    for c in top['cells'].values():
        if not c['type'].startswith('$') or 'latch' in c['type'].lower():raise ValueError('HOLD residual blackbox/latch')
        if 'dff' in c['type'].lower():
            if c['connections'].get('CLK',c['connections'].get('C'))!=clock or c['type']=='$_DFF_N_':raise ValueError('HOLD noncommon clock')
            if 'CLK_POLARITY' in c['parameters'] and int(c['parameters']['CLK_POLARITY'],2)!=1:raise ValueError('HOLD negative clock')
    write(d/'coverage.json',{'functional_cells':sorted(used),'outputs':['req_rdy','resp_val','resp_msg[15:0]'],'output_bits':18,'no_blackbox':True,'common_positive_clock':True,'library_selection_sha256':sha(d/'library-selection.json'),'functional_library_sha256':sha(lib),'source_library_sha256':sha(frozen_lib),'closed_used_models':True})
    augmented,relation,plan=strengthen_miter((d/'miter.il').read_bytes(),(d/'miter.json').read_bytes())
    (d/'strengthened.il').write_bytes(augmented)
    (d/'state_relation.v').write_bytes(relation)
    write(d/'strengthening.json',plan)
    proof='read_rtlil /work/formal/strengthened.il\nread_verilog -formal -sv /work/formal/state_relation.v\nhierarchy -check -top acceptance_miter\nproc; flatten; opt; dffunmap; opt_clean; check -assert\nwrite_json /work/formal/strengthened_miter.json\nwrite_rtlil /work/formal/strengthened_miter.il\nsat -seq 5 -tempinduct -maxsteps 32 -enable_undef -set-def-inputs -set-init-def -prove strengthened_mismatch 0 -verify -timeout 30 -show mismatch -show strengthened_mismatch -show-inputs -show-regs -dump_json /work/formal/counterexample.json\n'
    (d/'prove.ys').write_text(proof)
    rc=run([YOSYS,'-Q','-T','-s',str(d/'prove.ys')],d/'proof.log',budget())
    verdict=formal_verdict(rc,(d/'proof.log').read_text(errors='replace'))
    witness=counterexample_record(d/'counterexample.json')
    if verdict=='FAIL_COUNTEREXAMPLE' and witness is None:verdict='UNKNOWN_AUXILIARY_PROPERTY_OR_WITNESS'
    write(d/'result.json',{'FORMAL_EQUIVALENCE_GATE':verdict,'return_code':rc,'contract':'full 18-bit outputs after two forced reset edges for all future defined inputs','method':'basecase plus temporal induction of original property OR auxiliary violations; no BMC promotion',
        'proof_property':'strengthened_mismatch == 0 implies original mismatch == 0',
        'strengthening_manifest_sha256':sha(d/'strengthening.json'),'auxiliary_relation_status':'PROVED_WITH_PROPERTY' if verdict=='PASS_RESET_CONTRACT_UNBOUNDED' else 'UNPROVEN',
        'observation':observe_yosys(rc,(d/'proof.log').read_text(errors='replace')),
        'counterexample':witness,'engine_sha256':sha(YOSYS),
        'proof_script_sha256':sha(d/'prove.ys'),'miter_source_sha256':sha('/audit/miter.v'),'runtime_seconds':time.monotonic()-started})
    if verdict=='FAIL_COUNTEREXAMPLE':raise FormalCounterexample('SAT basecase counterexample under the declared reset contract')
    if verdict!='PASS_RESET_CONTRACT_UNBOUNDED':raise ValueError('HOLD no complete unbounded proof')
def parse_sta_paths(text,models):
    paths=[]
    for block in text.split('Startpoint: ')[1:]:
        endpoint=re.search(r'Endpoint: ([^\n]+)',block).group(1).split(' (')[0].strip()
        group=re.search(r'Path Group: ([^\n]+)',block).group(1).strip()
        slack=float(re.search(r'([-+\deE.]+)\s+slack \(VIOLATED\)',block).group(1))
        points=[];data=False;ended=False
        start=block.splitlines()[0].split(' (')[0].strip()
        for line in block.splitlines():
            if 'input port' in block.splitlines()[0] and 'input external delay' in line:data=True
            port=re.search(r'([\^v])\s+(\S+)\s+\((in|out)\)',line)
            if port:
                _,name,direction=port.groups()
                if direction=='in' and name==start:data=True
                if direction=='out' and name==endpoint and data and not ended:
                    nums=re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',line[:port.start()])
                    points.append({'instance':name,'pin':name,'cell':None,'increment_ns':float(nums[-2]),'arc':'net','segment':'data','kind':'port'})
            if 'data arrival time' in line:ended=True
            hit=re.search(r'([\^v])\s+(\S+)/(\S+)\s+\((\S+)\)',line)
            if not hit:continue
            _,inst,pin,cell=hit.groups()
            nums=re.findall(r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',line[:hit.start()]);delay=float(nums[-2])
            if inst==start and pin in ('Q','QN'):data=True
            direction=models[cell]['ports'][pin]['direction']
            if direction not in ('input','output'):raise ValueError('HOLD ambiguous path pin direction')
            points.append({'instance':inst,'pin':pin,'cell':cell,'increment_ns':delay,'arc':'net' if direction=='input' else 'cell','segment':'data' if data and not ended else 'clock'})
        if not points or not data:raise ValueError('HOLD missing path delay details/launch boundary')
        paths.append({'startpoint':start,'endpoint':endpoint,'group':group,'slack_ns':slack,'points':points,
            'data_cell_delay_ns':sum(p['increment_ns'] for p in points if p['segment']=='data' and p['arc']=='cell'),
            'data_net_delay_ns':sum(p['increment_ns'] for p in points if p['segment']=='data' and p['arc']=='net')})
    return paths

def read_pin_models(path):
    models={}
    for line in Path(path).read_text().splitlines():
        cell,pin,direction=line.split('\t')
        if direction not in ('INPUT','OUTPUT','INOUT'):raise ValueError('HOLD unknown native pin direction')
        port=models.setdefault(cell,{'ports':{}})['ports']
        value={'direction':direction.lower()}
        if pin in port and port[pin]!=value:raise ValueError('HOLD conflicting native pin direction')
        port[pin]=value
    if not models:raise ValueError('HOLD missing native pin inventory')
    return models

def sta_results(root=Path('/work')):
    d=Path(root)/'sta';models=read_pin_models(d/'pin-directions.tsv')
    wns=float(re.search(r'wns\s+max\s+([-+\deE.]+)',(d/'wns.rpt').read_text()).group(1))
    tns=float(re.search(r'tns\s+max\s+([-+\deE.]+)',(d/'tns.rpt').read_text()).group(1))
    paths=parse_sta_paths((d/'all_setup.rpt').read_text(),models)
    if any(not math.isfinite(p['slack_ns']) or p['slack_ns']>=0 for p in paths):raise ValueError('HOLD invalid violation slack')
    endpoints=sorted({p['endpoint'] for p in paths});require_sta_identity(wns,tns,len(endpoints))
    worst={}
    for p in paths:worst[p['endpoint']]=min(p['slack_ns'],worst.get(p['endpoint'],0))
    if not paths or abs(min(worst.values())-wns)>5e-6 or abs(sum(worst.values())-tns)>5e-6:raise ValueError('HOLD endpoint coverage and aggregate timing disagree')
    paths.sort(key=lambda p:p['slack_ns'])
    write(d/'paths.json',{'top_setup_paths':paths[:20],'all_violating_paths':paths,'all_violating_endpoints':endpoints,'WNS':wns,'TNS':tns,'TIMING_GATE':'FAIL','STA_EXTRACTION_GATE':'PASS','pin_direction_source':'native OpenDB master terminals; independent of Yosys','reference_match_tolerance_ns':5e-6})

def snapshots():
    root=Path('/work/constraints');root.mkdir(exist_ok=True)
    result={'schema':'verieda.native-constraint-context.v1','full_constraint_gate':'UNKNOWN','roles':{},'scope':'evaluated SDC on a final-ODB copy; original RTL-stage context equivalence is not asserted'}
    for role,source in [('reference','/frozen/flow/designs/nangate45/gcd/constraint.sdc'),('candidate','/inputs/6_final.sdc')]:
        folder=root/role;folder.mkdir(exist_ok=True)
        env=dict(os.environ);env['VERIEDA_SNAPSHOT_ROLE']=role
        rc=run([OPENROAD,'-no_init','-exit','/audit/snapshot.tcl'],folder/'tool.log',20,env=env)
        if rc:raise ValueError('HOLD native constraint snapshot '+role+' rc='+str(rc))
        capture_reports(folder,['units'])
        for name in ['evaluated.sdc','units.rpt','coverage.rpt','ports.tsv']:
            if not (folder/name).is_file():raise ValueError('HOLD incomplete native snapshot '+role)
        if not (folder/'ports.tsv').stat().st_size:raise ValueError('HOLD empty native port inventory')
        result['roles'][role]={'source_sdc_sha256':sha(source),'odb_sha256':sha('/inputs/6_final.odb'),
            'native_return_code':rc,'outputs':{name:sha(folder/name) for name in ['evaluated.sdc','units.rpt','coverage.rpt','ports.tsv']}}
    if (root/'reference/units.rpt').read_bytes()!=(root/'candidate/units.rpt').read_bytes():raise ValueError('HOLD native unit contexts differ')
    if (root/'reference/ports.tsv').read_bytes()!=(root/'candidate/ports.tsv').read_bytes():raise ValueError('HOLD native port contexts differ')
    result['comparison']=compare_sdc((root/'reference/evaluated.sdc').read_text(),(root/'candidate/evaluated.sdc').read_text())
    result['snapshot_extraction_gate']='PASS'
    write(root/'contexts.json',result)
def seal(root):
    root=Path(root);files=sorted(p for p in root.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS.txt','file-sizes.json'))
    if any(p.is_symlink() or p.stat().st_size>16*1024*1024 for p in files) or sum(p.stat().st_size for p in files)>128*1024*1024:raise ValueError('HOLD evidence size budget')
    write(root/'file-sizes.json',[{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size} for p in files])
    files.append(root/'file-sizes.json')
    (root/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.relative_to(root).as_posix()+'\n' for p in files),encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['package-check','fetch','identity','formal','sta-results','sta-reports','snapshots','seal']);p.add_argument('directory',nargs='?');a=p.parse_args()
    try:
        if a.mode=='package-check':package_check()
        elif a.mode=='fetch':fetch()
        elif a.mode=='identity':identity()
        elif a.mode=='formal':formal()
        elif a.mode=='sta-results':sta_results()
        elif a.mode=='sta-reports':capture_reports(Path('/work/sta'),['units','wns','tns'])
        elif a.mode=='snapshots':snapshots()
        else:seal(a.directory)
    except FormalCounterexample as ex:
        write('/work/formal/failure.json',{'status':'FAIL_COUNTEREXAMPLE','reason':str(ex),'scope':'declared reset-contract property'})
        raise SystemExit(3)
    except Exception as ex:
        target=Path('/work') if Path('/work').is_dir() else Path('evidence/final-acceptance')
        target.mkdir(parents=True,exist_ok=True);write(target/('hold-'+a.mode+'.json'),{'status':'UNKNOWN_HOLD','reason':str(ex),'mode':a.mode})
        raise SystemExit(2)
