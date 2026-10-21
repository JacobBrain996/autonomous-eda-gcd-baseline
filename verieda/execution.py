"""Isolated synthesis adapter. Package preparation never executes an EDA tool."""
import hashlib,json,os,pathlib,platform,re,signal,subprocess,time,shutil,math
from .case import read_json,digest
from .policy import validate_candidate

HERE=pathlib.Path(__file__).resolve().parent
EFFECTIVE=b'''.PHONY: verieda-effective
verieda-effective:
\t@printf 'ABC_AREA=%s\\nLEC_CHECK=%s\\nSEC_CHECK=%s\\nPLATFORM=%s\\nDESIGN_NAME=%s\\nYOSYS_EXE=%s\\nOPENROAD_EXE=%s\\nPYTHON_EXE=%s\\n' '$(ABC_AREA)' '$(LEC_CHECK)' '$(SEC_CHECK)' '$(PLATFORM)' '$(DESIGN_NAME)' '$(YOSYS_EXE)' '$(OPENROAD_EXE)' '$(PYTHON_EXE)'
'''
def design_paths(design,platform_name):
    """Pure single-file ORFS convention, not a support/authorization decision.

    Multi-file RTL and nonstandard layouts need an explicit future descriptor;
    never infer their input identity from these conventional names.
    """
    for name in (design,platform_name):
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]{0,63}',name):raise ValueError('unsafe ORFS design/platform name')
    base=f'{platform_name}/{design}'
    return {'config':f'designs/{base}/config.mk','rtl':f'flow/designs/src/{design}/{design}.v',
            'sdc':f'flow/designs/{base}/constraint.sdc',
            'netlist':f'results/{base}/verieda/1_2_yosys.v','odb':f'results/{base}/verieda/1_synth.odb'}


def expected_effective(design,platform_name):
    design_paths(design,platform_name)
    return (f'ABC_AREA=0\nLEC_CHECK=1\nSEC_CHECK=1\nPLATFORM={platform_name}\nDESIGN_NAME={design}\n'
            'YOSYS_EXE=/OpenROAD-flow-scripts/tools/install/yosys/bin/yosys\n'
            'OPENROAD_EXE=/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad\nPYTHON_EXE=/usr/bin/python3\n').encode()

# Backwards-compatible names for the registered historical GCD adapter.
EXPECTED_EFFECTIVE=expected_effective('gcd','nangate45')

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

def make_argv(effective,work,target,design='gcd',platform_name='nangate45'):
    if target not in ('verieda-effective','synth'):raise ValueError('unsupported Make target')
    effective=_posix_path(effective);work=_posix_path(work);paths=design_paths(design,platform_name)
    return ['/usr/bin/make','--no-print-directory','-f','Makefile','-f',effective,
            'DESIGN_CONFIG=./'+paths['config'],'WORK_HOME='+work,'FLOW_VARIANT=verieda',
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
        try:rc=process.wait(timeout=max(0.01,seconds));child_rc=rc
        except subprocess.TimeoutExpired:
            timed_out=True
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child_rc=process.wait();rc=124
    return {'argv':argv,'return_code':rc,'child_return_code':child_rc,'pid':process.pid,'timeout':timed_out,'signal':-child_rc if child_rc<0 else None,
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
    paths=design_paths(state['design'],state['platform'])
    sources={paths['rtl']:state['frozen']['rtl_sha256'],paths['sdc']:state['frozen']['sdc_sha256']}
    for name,h in {**sources,**state['tools']}.items():
        p=pathlib.Path(name) if name.startswith('/') else root/name
        hashes[name]=_sha(p)
        if hashes[name]!=h:raise ValueError('frozen input/tool mismatch: '+name)
    head=_source_inventory(root)
    if head!=state['frozen']['orfs_commit']:raise ValueError('frozen ORFS Git head mismatch')
    return hashes

def execute_action(package,frozen_root,work,execute=False,image_record=None,budget_seconds=300):
    if type(budget_seconds) is not int or not 1<=budget_seconds<=300:raise ValueError("action budget must be integer 1..300")
    manifest=verify_package(package)
    if not execute:return {'status':'NOT_RUN','candidate_id':manifest['candidate_id'],'phase':'SYNTHESIS_ONLY','requires_explicit_execution':True}
    image=check_image_record(image_record,manifest['support'])
    root=_unlinked(frozen_root);bundle=_unlinked(package);out=_unlinked(work);_posix_path(out)
    if out.exists() or out.is_relative_to(root) or root.is_relative_to(out) or out.is_relative_to(bundle) or bundle.is_relative_to(out):raise ValueError('fresh output outside frozen source/package required')
    state=read_json(bundle/'state.json',4*1024*1024);candidate=read_json(bundle/'candidate.json')
    paths=design_paths(state['design'],state['platform'])
    identity=_native_identity(root,state,manifest)
    out.mkdir();(out/'tmp').mkdir();start=time.monotonic();env=clean_environment(out)
    receipt={'schema':'verieda.action-execution.v0','state_id':state['state_id'],'candidate_id':candidate['candidate_id'],
             'changes':candidate['changes'],'phase':'SYNTHESIS_ONLY','status':'ERROR','return_code':None,'steps':[],
             'source_tool_sha256':identity,'design_acceptance':'NOT_EVALUATED','FORMAL_EQUIVALENCE_GATE':'NOT_RUN',
             'TIMING_GATE':'NOT_RUN','image_host_record':image,'OCI_IDENTITY_GATE':'HOST_RECORD_MATCH_NOT_ATTESTED'}
    try:
        pre=_run(make_argv(bundle/'effective.mk',out,'verieda-effective',state['design'],state['platform']),root/'flow',env,out/'effective.log',min(20,budget_seconds))
        receipt['steps'].append(pre);receipt['return_code']=pre['return_code']
        if pre['return_code']!=0:receipt['status']='TIMEOUT' if pre['timeout'] else 'ERROR'
        elif (out/'effective.log').read_bytes()!=expected_effective(state['design'],state['platform']):receipt['status']='HOLD_EFFECTIVE_VARIABLES'
        else:
            remaining=budget_seconds-(time.monotonic()-start)
            if remaining<=0:receipt.update(status='TIMEOUT',return_code=124)
            else:
                run=_run(make_argv(bundle/'effective.mk',out,'synth',state['design'],state['platform']),root/'flow',env,out/'synth.log',remaining)
                receipt['steps'].append(run);receipt['return_code']=run['return_code']
                netlist=out/paths['netlist']
                odb=out/paths['odb']
                if run['return_code']!=0:receipt['status']='TIMEOUT' if run['timeout'] else 'ERROR'
                elif not netlist.is_file() or not 0<netlist.stat().st_size<=16*1024*1024:receipt['status']='HOLD_MISSING_NETLIST'
                elif not odb.is_file() or not 0<odb.stat().st_size<=16*1024*1024:receipt['status']='HOLD_MISSING_ODB'
                elif 'Using ABC speed script.' not in (out/'synth.log').read_text(errors='replace'):receipt['status']='HOLD_MAPPING_NOT_OBSERVED'
                else:receipt.update(status='SYNTHESIS_COMPLETED',netlist_sha256=_sha(netlist),netlist_path=paths['netlist'],
                                    odb_sha256=_sha(odb),odb_path=paths['odb'])
    except (OSError,ValueError,subprocess.SubprocessError) as ex:receipt.update(status='ERROR',error=str(ex))
    receipt['runtime_seconds']=time.monotonic()-start
    with (out/'action-execution.json').open('xb') as f:f.write(_json_bytes(receipt))
    return receipt


def physical_argv(effective,work,approve_internal_lec_bypass=False,design='gcd',platform_name='nangate45'):
    """Explicit engineering-only bypass; final independent Formal is mandatory."""
    if approve_internal_lec_bypass is not True:raise ValueError('separate approval for internal LEC/SEC diagnostic bypass required')
    argv=make_argv(effective,work,'synth',design,platform_name)
    return [({'LEC_CHECK=1':'LEC_CHECK=0','SEC_CHECK=1':'SEC_CHECK=0'}.get(a,a)) for a in argv[:-1]]+['all']


def check_rebuilt_netlist(path,expected_sha256):
    p=_unlinked(path)
    if not p.is_file() or not 0<p.stat().st_size<=16*1024*1024 or _sha(p)!=expected_sha256:
        raise ValueError('HOLD regenerated synthesis netlist differs from proved candidate')
    return expected_sha256


def observe_physical_metrics(log_directory,sta_directory):
    """Bounded saved reports only; cross-check two observations, never acceptance."""
    from .evidence import metric
    logs=_unlinked(log_directory);sta=_unlinked(sta_directory);data={}
    for name in ('6_report.json','5_2_route.json'):
        p=_unlinked(logs/name)
        if not p.is_file() or not 0<p.stat().st_size<=16*1024*1024:raise ValueError('missing bounded physical report '+name)
        data[name]=p.read_bytes()
    specs={'setup_slack':('finish__timing__setup__ws','ns'),'TNS':('finish__timing__setup__tns','ns'),
           'hold_slack':('finish__timing__hold__ws','ns'),'stdcell_area':('finish__design__instance__area__stdcell','um^2')}
    metrics={k:metric(data,'6_report.json',key,unit) for k,(key,unit) in specs.items()}
    metrics['router_drc']=metric(data,'5_2_route.json','detailedroute__route__drc_errors','count')
    if any(v['status']!='AVAILABLE' for v in metrics.values()):raise ValueError('incomplete/ambiguous physical metrics; preserve raw reports')
    metrics['WNS']={**metrics['setup_slack'],'value':min(0,metrics['setup_slack']['value'])}
    drc=metrics['router_drc']['value']
    if drc<0 or int(drc)!=drc or metrics['stdcell_area']['value']<=0:raise ValueError('invalid DRC count or cell area')
    paths={name:_unlinked(sta/(name+'.rpt')) for name in ('units','wns','tns','hold_wns','hold_tns')}
    if any(not p.is_file() or not 0<p.stat().st_size<=1024*1024 for p in paths.values()):raise ValueError('bounded native STA reports required')
    if re.findall(r'(?m)^\s*time\s+(\S+)\s*$',paths['units'].read_text())!=['1ns']:raise ValueError('native STA time unit must be 1ns')
    observed={}
    for name,cmd,kind in [('wns','wns','max'),('tns','tns','max'),('hold_wns','wns','min'),('hold_tns','tns','min')]:
        match=re.fullmatch(r'\s*'+cmd+' '+kind+r'\s+(\S+)\s*',paths[name].read_text())
        if not match:raise ValueError('unsupported native STA format '+name)
        value=float(match[1])
        if not math.isfinite(value) or value>0:raise ValueError('invalid clipped native STA metric '+name)
        observed[name]=value
    for w,t in [('wns','tns'),('hold_wns','hold_tns')]:
        if (observed[w]<0)!=(observed[t]<0) or observed[t]>observed[w]:raise ValueError('inconsistent native WNS/TNS')
    for native,reported in [('wns',metrics['WNS']['value']),('tns',metrics['TNS']['value']),('hold_wns',min(0,metrics['hold_slack']['value']))]:
        if abs(observed[native]-reported)>5e-6:raise ValueError('native STA/finish mismatch '+native)
    return {'schema':'verieda.physical-metrics-observation.v1','metrics':metrics,'native_clipped_metrics_ns':observed,
            'source_sha256':{**{n:hashlib.sha256(b).hexdigest() for n,b in data.items()},**{n+'.rpt':_sha(p) for n,p in paths.items()}},
            'design_acceptance':'NOT_EVALUATED','constraint_gate':'UNKNOWN','final_formal':'NOT_RUN'}


def execute_physical(package,verification_package,reviewed_proof,frozen_root,work,execute=False,
                     approve_internal_lec_bypass=False,image_record=None):
    """One frozen candidate physical experiment, not design acceptance.

    Fixed native mount convention deliberately matches the actually executed
    GCD STA initializer. Other designs remain unsupported by this adapter.
    """
    from .verification import verify_verification_package,_registered_formal_review,prepare_final_verification
    from .formal_review import inspect_formal
    from .sta_min import build_hold_script
    from acceptance.verify import capture_reports,snapshots
    manifest=verify_package(package);verify_verification_package(verification_package)
    state=read_json(pathlib.Path(package)/'state.json',4*1024*1024)
    subject=read_json(pathlib.Path(verification_package)/'subject.json')
    if (subject['candidate_id']!=manifest['candidate_id'] or subject['state_id']!=state['state_id']
        or subject['execution_scope']!='SYNTHESIS_ONLY'):raise ValueError('foreign physical parent')
    proof=_unlinked(reviewed_proof)
    if not proof.is_file() or not 0<proof.stat().st_size<=32*1024*1024:raise ValueError('bounded reviewed proof required')
    review=_registered_formal_review(subject,_sha(proof))
    contract=HERE.parent/'contracts/gcd.reset2.json'
    if not review or inspect_formal(verification_package,contract,proof,_sha(proof))['scope_structure_gate']!='PASS_STATIC_CHECKS':
        raise ValueError('scoped reviewed synthesis proof required')
    if not execute:return {'status':'NOT_RUN','candidate_id':manifest['candidate_id'],'execution_authorized':False,
                           'requires':['separate external execution authorization','explicit internal LEC/SEC bypass approval','fresh final-netlist proof']}
    physical_argv('/package/effective.mk','/work/physical/action',approve_internal_lec_bypass)
    root=_unlinked(frozen_root);out=_unlinked(work);inputs=_unlinked('/inputs');sta=_unlinked('/work/sta')
    if str(root)!='/frozen' or str(out)!='/work/physical' or out.exists() or sta.exists() or not inputs.is_dir() or any(inputs.iterdir()):
        raise ValueError('fresh fixed physical/STA/input mount convention required')
    # Admission before creating output or starting synthesis.
    image=check_image_record(image_record,manifest['support']);identity=_native_identity(root,state,manifest)
    out.mkdir();started=time.monotonic()
    receipt={'schema':'verieda.physical-execution.v1','phase':'PHYSICAL_FINAL_OUTPUTS','status':'ERROR','return_code':None,
             'candidate_id':subject['candidate_id'],'state_id':state['state_id'],'parent_subject_id':subject['subject_id'],
             'changes':read_json(pathlib.Path(package)/'candidate.json')['changes'],'source_tool_sha256':identity,
             'image_host_record':image,'steps':[],'internal_formal':'NOT_RUN_WITH_APPROVED_DIAGNOSTIC_BYPASS',
             'independent_final_formal':'NOT_RUN','design_acceptance':'NOT_EVALUATED','constraint_gate':'UNKNOWN',
             'reviewed_synthesis_proof':review,'native_source_sha256':_sha(__file__)}
    try:
        synthesis=execute_action(package,root,out/'action',True,image_record,60)
        receipt['synthesis']=synthesis
        if synthesis['status']!='SYNTHESIS_COMPLETED':raise ValueError('synthesis prerequisite reconstruction failed')
        paths=design_paths(state['design'],state['platform'])
        receipt['rebuilt_netlist_sha256']=check_rebuilt_netlist(out/'action'/paths['netlist'],subject['target']['netlist_sha256'])
        env=clean_environment(out/'action');flow=root/'flow'
        step=_run(physical_argv(pathlib.Path(package)/'effective.mk',out/'action',True),flow,env,out/'physical.log',300)
        receipt['steps'].append(step);receipt['return_code']=step['return_code']
        if step['return_code']:raise ValueError('physical flow failed; no automatic retry')
        receipt['retained_synthesis_netlist_sha256']=check_rebuilt_netlist(out/'action'/paths['netlist'],subject['target']['netlist_sha256'])
        final=out/'final';final.mkdir()
        base=out/'action/results/nangate45/gcd/verieda'
        for name in ('6_final.v','6_final.odb','6_final.sdc','6_final.gds'):
            p=_unlinked(base/name)
            if not p.is_file() or not 0<p.stat().st_size<=16*1024*1024:raise ValueError('missing/bounded final output '+name)
            shutil.copyfile(p,final/name)
        for name in ('6_final.v','6_final.odb','6_final.sdc'):shutil.copyfile(final/name,inputs/name)
        receipt.update(netlist_sha256=_sha(final/'6_final.v'),odb_sha256=_sha(final/'6_final.odb'))
        sta.mkdir();script=sta/'candidate.tcl';script.write_bytes(build_hold_script())
        receipt['sta_script_sha256']=_sha(script)
        openroad=next(p for p in state['tools'] if pathlib.PurePosixPath(p).name=='openroad')
        step=_run([openroad,'-no_init','-exit',str(script)],flow,env,sta/'tool.log',90)
        receipt['steps'].append(step);receipt['return_code']=step['return_code']
        if step['return_code']:raise ValueError('independent max/min STA failed')
        capture_reports(sta,['units','wns','tns','hold_wns','hold_tns'])
        metrics=observe_physical_metrics(out/'action/logs/nangate45/gcd/verieda',sta)
        (out/'metrics.json').write_bytes(_json_bytes(metrics))
        # Reuse the native evaluated-SDC observer; it explicitly keeps full gate UNKNOWN.
        snapshots()
        klayout=pathlib.Path('/usr/bin/klayout')
        receipt['klayout_sha256']=_sha(klayout)
        script=out/'read_gds.py'
        script.write_text('import pya\nl=pya.Layout()\nl.read("'+str(final/'6_final.gds')+'")\nassert any(c.name=="gcd" for c in l.top_cells())\nassert not l.cell("gcd").bbox().empty()\nprint("GDS_READ_GATE=PASS")\n')
        step=_run([str(klayout),'-b','-r',str(script)],flow,env,out/'gds-read.log',30)
        receipt['steps'].append(step);receipt['return_code']=step['return_code']
        if step['return_code'] or 'GDS_READ_GATE=PASS' not in (out/'gds-read.log').read_text():raise ValueError('GDS read failed')
        receipt.update(status='PHYSICAL_AND_OBSERVERS_COMPLETED',return_code=0,
                       final_files={p.name:_sha(p) for p in final.iterdir()})
        (final/'physical-receipt.json').write_bytes(_json_bytes(receipt))
        prepare_final_verification(subject,final,pathlib.Path('/work/final-package'))
    except (OSError,ValueError,subprocess.SubprocessError) as ex:
        receipt.update(status='HOLD_EXECUTION_OR_EVIDENCE',error=str(ex))
        if receipt['return_code'] in (None,0):receipt['return_code']=2
    receipt['runtime_seconds']=time.monotonic()-started
    (out/'physical-execution.json').write_bytes(_json_bytes(receipt))
    return receipt
