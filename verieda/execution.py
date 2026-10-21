"""Isolated synthesis adapter. Package preparation never executes an EDA tool."""
import hashlib,json,os,pathlib,platform,re,signal,subprocess,time
from .case import read_json,digest
from .policy import validate_candidate

HERE=pathlib.Path(__file__).resolve().parent
EFFECTIVE=b'''.PHONY: verieda-effective
verieda-effective:
\t@printf 'ABC_AREA=%s\\nLEC_CHECK=%s\\nSEC_CHECK=%s\\nPLATFORM=%s\\nDESIGN_NAME=%s\\nYOSYS_EXE=%s\\nOPENROAD_EXE=%s\\nPYTHON_EXE=%s\\n' '$(ABC_AREA)' '$(LEC_CHECK)' '$(SEC_CHECK)' '$(PLATFORM)' '$(DESIGN_NAME)' '$(YOSYS_EXE)' '$(OPENROAD_EXE)' '$(PYTHON_EXE)'
'''

def _sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def _json_bytes(obj):return (json.dumps(obj,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def _unlinked(path):
    p=pathlib.Path(path).absolute()
    if any(x.is_symlink() or (hasattr(x,'is_junction') and x.is_junction()) for x in (p,*p.parents)):raise ValueError('linked action path forbidden')
    return p

def _contents(state,candidate):
    if validate_candidate(candidate,state)['legality']!='PASS' or candidate['action']!='timing_mapping':raise ValueError('unsupported or illegal executable action')
    support=read_json(HERE/'action_support.json')
    if (state['design']!='gcd' or state['platform']!='nangate45' or state['frozen']['orfs_commit']!=support['orfs_commit']
        or state['tools']!=support['binaries'] or state['frozen']['orfs_image']!=support['image']):raise ValueError('action support does not match frozen case/tools/image')
    files={'state.json':_json_bytes(state),'candidate.json':_json_bytes(candidate),'effective.mk':EFFECTIVE}
    manifest={'schema':'verieda.action-package.v0','candidate_id':candidate['candidate_id'],'state_id':state['state_id'],
              'files':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()},
              'adapter_sources':{n:_sha(HERE/n) for n in ('case.py','policy.py','execution.py','action_support.json')},
              'phase':'SYNTHESIS_ONLY','timeout_seconds':300,'execution_status':'NOT_RUN','support':support,
              'requires':'separate authorization; Linux read-only frozen source mount; fresh isolated output; external OCI attestation'}
    files['manifest.json']=_json_bytes(manifest);return files,manifest

def prepare_action(state,candidate,output):
    files,manifest=_contents(state,candidate);out=_unlinked(output)
    if out.exists():raise ValueError('action package destination already exists')
    out.mkdir()
    for n,b in files.items():
        with (out/n).open('xb') as f:f.write(b)
    return manifest

def verify_package(directory):
    root=_unlinked(directory)
    if not root.is_dir() or {p.name for p in root.iterdir()}!={'state.json','candidate.json','manifest.json','effective.mk'}:raise ValueError('unexpected action package contents')
    for p in root.iterdir():
        if p.is_symlink() or not p.is_file() or p.stat().st_size>4*1024*1024:raise ValueError('invalid action package file')
    files,manifest=_contents(read_json(root/'state.json',4*1024*1024),read_json(root/'candidate.json'))
    if any((root/n).read_bytes()!=b for n,b in files.items()):raise ValueError('action package bytes/adapter identity changed')
    return manifest

def _posix_path(value):
    text=str(value)
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+',text) or '..' in pathlib.PurePosixPath(text).parts:raise ValueError('unsafe native Make path')
    return text

def make_argv(effective,work,target):
    if target not in ('verieda-effective','synth'):raise ValueError('unsupported Make target')
    effective=_posix_path(effective);work=_posix_path(work)
    return ['/usr/bin/make','--no-print-directory','-f','Makefile','-f',effective,
            'DESIGN_CONFIG=./designs/nangate45/gcd/config.mk','WORK_HOME='+work,'FLOW_VARIANT=verieda',
            'ABC_AREA=0','LEC_CHECK=1','SEC_CHECK=1',
            'YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys',
            'OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad','PYTHON_EXE=/usr/bin/python3',target]

def clean_environment(work):
    work=_posix_path(work)
    return {'PATH':'/OpenROAD-flow-scripts/tools/install/yosys/bin:/OpenROAD-flow-scripts/tools/install/OpenROAD/bin:/usr/local/bin:/usr/bin:/bin',
            'HOME':work,'TMPDIR':work+'/tmp','LC_ALL':'C','LANG':'C','TZ':'UTC','PYTHONDONTWRITEBYTECODE':'1'}

def check_image_record(record,support):
    if (not isinstance(record,dict) or set(record)!={'image_id','repo_digests','os','architecture'}
        or record['image_id']!=support['image_id'] or record['repo_digests']!=[support['image']]
        or record['os']!='linux' or record['architecture']!='amd64'):raise ValueError('frozen host image record mismatch or unsafe fields')
    return {'record_sha256':digest(record),'image_id':record['image_id'],'trust':'external caller-supplied host record, not cryptographic attestation'}

def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))

def _run(argv,cwd,env,log,seconds):
    start=time.monotonic();timed_out=False
    with pathlib.Path(log).open('xb') as stream:
        process=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,
                                 shell=False,start_new_session=True,preexec_fn=_limits)
        try:rc=process.wait(timeout=max(0.01,seconds))
        except subprocess.TimeoutExpired:
            timed_out=True
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();rc=124
    return {'argv':argv,'return_code':rc,'timeout':timed_out,'signal':-rc if rc<0 else None,
            'runtime_seconds':time.monotonic()-start,'log_sha256':_sha(log)}

def _source_inventory(root,git_executable='/usr/bin/git'):
    def git(*args):return subprocess.check_output([git_executable,'-C',str(root),*args],env=clean_environment('/tmp'),timeout=10)
    head=git('rev-parse','HEAD').decode().strip()
    if git('status','--porcelain','--untracked-files=all').strip():raise ValueError('frozen ORFS worktree is not clean')
    if git('ls-files','--others','--ignored','--exclude-standard','--','flow').strip():raise ValueError('ignored files under frozen flow are forbidden before Make')
    return head

def _native_identity(root,state,manifest):
    root=_unlinked(root);_posix_path(root)
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):raise ValueError('native execution requires Linux x86_64; no local EDA was run')
    if not os.statvfs(root).f_flag & os.ST_RDONLY:raise ValueError('frozen ORFS must be mounted read-only')
    hashes={}
    for name,h in manifest['support']['sources'].items():
        hashes[name]=_sha(root/name)
        if hashes[name]!=h:raise ValueError('frozen action source mismatch: '+name)
    sources={'flow/designs/src/gcd/gcd.v':state['frozen']['rtl_sha256'],
             'flow/designs/nangate45/gcd/constraint.sdc':state['frozen']['sdc_sha256']}
    for name,h in {**sources,**state['tools']}.items():
        p=pathlib.Path(name) if name.startswith('/') else root/name
        hashes[name]=_sha(p)
        if hashes[name]!=h:raise ValueError('frozen input/tool mismatch: '+name)
    head=_source_inventory(root)
    if head!=state['frozen']['orfs_commit']:raise ValueError('frozen ORFS Git head mismatch')
    return hashes

def execute_action(package,frozen_root,work,execute=False,image_record=None):
    manifest=verify_package(package)
    if not execute:return {'status':'NOT_RUN','candidate_id':manifest['candidate_id'],'phase':'SYNTHESIS_ONLY','requires_explicit_execution':True}
    image=check_image_record(image_record,manifest['support'])
    root=_unlinked(frozen_root);bundle=_unlinked(package);out=_unlinked(work);_posix_path(out)
    if out.exists() or out.is_relative_to(root) or root.is_relative_to(out) or out.is_relative_to(bundle) or bundle.is_relative_to(out):raise ValueError('fresh output outside frozen source/package required')
    state=read_json(bundle/'state.json',4*1024*1024);candidate=read_json(bundle/'candidate.json')
    identity=_native_identity(root,state,manifest)
    out.mkdir();(out/'tmp').mkdir();start=time.monotonic();env=clean_environment(out)
    receipt={'schema':'verieda.action-execution.v0','state_id':state['state_id'],'candidate_id':candidate['candidate_id'],
             'changes':candidate['changes'],'phase':'SYNTHESIS_ONLY','status':'ERROR','return_code':None,'steps':[],
             'source_tool_sha256':identity,'design_acceptance':'NOT_EVALUATED','FORMAL_EQUIVALENCE_GATE':'NOT_RUN',
             'TIMING_GATE':'NOT_RUN','image_host_record':image,'OCI_IDENTITY_GATE':'HOST_RECORD_MATCH_NOT_ATTESTED'}
    try:
        pre=_run(make_argv(bundle/'effective.mk',out,'verieda-effective'),root/'flow',env,out/'effective.log',20)
        receipt['steps'].append(pre);receipt['return_code']=pre['return_code']
        expected=('ABC_AREA=0\nLEC_CHECK=1\nSEC_CHECK=1\nPLATFORM=nangate45\nDESIGN_NAME=gcd\n'
                  'YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys\n'
                  'OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad\nPYTHON_EXE=/usr/bin/python3\n')
        if pre['return_code']!=0:receipt['status']='TIMEOUT' if pre['timeout'] else 'ERROR'
        elif (out/'effective.log').read_text()!=expected:receipt['status']='HOLD_EFFECTIVE_VARIABLES'
        else:
            remaining=300-(time.monotonic()-start)
            if remaining<=0:receipt.update(status='TIMEOUT',return_code=124)
            else:
                run=_run(make_argv(bundle/'effective.mk',out,'synth'),root/'flow',env,out/'synth.log',remaining)
                receipt['steps'].append(run);receipt['return_code']=run['return_code']
                netlist=out/'results/nangate45/gcd/verieda/1_2_yosys.v'
                if run['return_code']!=0:receipt['status']='TIMEOUT' if run['timeout'] else 'ERROR'
                elif not netlist.is_file() or not 0<netlist.stat().st_size<=16*1024*1024:receipt['status']='HOLD_MISSING_NETLIST'
                elif 'Using ABC speed script.' not in (out/'synth.log').read_text(errors='replace'):receipt['status']='HOLD_MAPPING_NOT_OBSERVED'
                else:receipt.update(status='SYNTHESIS_COMPLETED',netlist_sha256=_sha(netlist),netlist_path='results/nangate45/gcd/verieda/1_2_yosys.v')
    except (OSError,ValueError,subprocess.SubprocessError) as ex:receipt.update(status='ERROR',error=str(ex))
    receipt['runtime_seconds']=time.monotonic()-start
    with (out/'action-execution.json').open('xb') as f:f.write(_json_bytes(receipt))
    return receipt
