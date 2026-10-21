"""Bound candidate Formal execution. Engine observations are not certified PASS.

No old gate netlist, proof, cell-count expectation or STA metrics are reused.
Single-file RTL, one positive clock, synchronous reset; unsupported models HOLD.
"""
import hashlib,json,os,pathlib,platform,re,sys,time,zipfile
from .case import read_json,digest
from .verification import verify_verification_package
from .execution import _unlinked,_posix_path,_source_inventory,_run,clean_environment,check_image_record
from .formal import observe_yosys
from .liberty import subset_liberty
from .invariants import strengthen_miter
from acceptance.verify import require_proof_capabilities,require_model_closure

IDENT=re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')

def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def write(path,obj):
 with pathlib.Path(path).open('xb') as stream:stream.write((json.dumps(obj,indent=2,allow_nan=False)+'\n').encode())
def _name(name):
 if not isinstance(name,str) or not IDENT.fullmatch(name) or name.startswith('__ve_') or name in ('mismatch','acceptance_miter','gold_core','gate_core'):raise ValueError('unsupported/reserved HDL identifier')
 return name

def validate_contract(c):
 fields={'schema','top','description','rtl_sha256','clock','reset','reset_active','reset_edges','inputs','outputs','rtl_path','sdc_path','library_path','strengthening'}
 if not isinstance(c,dict) or set(c)!=fields or c['schema']!='verieda.reset-contract.v1':raise ValueError('explicit supported reset contract required; no extra assumptions')
 for key in ('top','clock','reset'):_name(c[key])
 if not isinstance(c['description'],str) or not c['description'].strip() or not isinstance(c['rtl_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',c['rtl_sha256']):raise ValueError('contract scope/RTL identity missing')
 for group in ('inputs','outputs'):
  if not isinstance(c[group],dict) or not c[group] or len(c[group])>128:raise ValueError('explicit complete port inventory required')
  for n,w in c[group].items():
   _name(n)
   if type(w) is not int or not 1<=w<=4096:raise ValueError('unsupported port width')
 if set(c['inputs'])&set(c['outputs']) or sum(c['outputs'].values())>8192:raise ValueError('ambiguous/bounded output inventory required')
 if c['clock']==c['reset'] or c['inputs'].get(c['clock'])!=1 or c['inputs'].get(c['reset'])!=1:raise ValueError('distinct one-bit clock/reset inputs required')
 if type(c['reset_edges']) is not int or not 1<=c['reset_edges']<=8 or type(c['reset_active']) is not int or c['reset_active'] not in (0,1):raise ValueError('unsupported reset duration/polarity')
 if c['strengthening'] not in ('none','gcd-state-v1'):raise ValueError('unsupported strengthening method')
 for key in ('rtl_path','sdc_path','library_path'):
  if not isinstance(c[key],str):raise ValueError('frozen source reference must be text')
  p=pathlib.PurePosixPath(c[key])
  if p.is_absolute() or '..' in p.parts or p.as_posix()!=c[key] or not re.fullmatch('[A-Za-z0-9_./-]+',c[key]):raise ValueError('unsafe frozen source reference')
 return c

def bind_contract(c,subject):
 validate_contract(c)
 if c['top']!=subject['design'] or c['rtl_sha256']!=subject['frozen']['rtl_sha256'] or c['description']!=subject['formal_contract'] or c['library_path'] not in subject['library']:raise ValueError('contract does not bind candidate RTL/design/library/scope')
 registry=contract_registry()
 if registry.get('schema')!='verieda.contract-registry.v1' or registry.get('contracts',{}).get(c['rtl_sha256'])!=digest(c):raise ValueError('unregistered or altered proof contract; explicit scope review required')
 return digest(c)

def contract_registry():
 return read_json(pathlib.Path(__file__).resolve().parents[1]/'contracts/registry.json')

def make_miter(c):
 validate_contract(c);edges=c['reset_edges'];width=max(1,edges.bit_length())
 ports=[]
 for n,w in c['inputs'].items():ports.append('input '+('' if w==1 else f'[{w-1}:0] ')+n)
 lines=['module acceptance_miter('+', '.join(ports)+', output mismatch);',f'  reg [{width-1}:0] __ve_boot = 0;',
  f"  always @(posedge {c['clock']}) if (__ve_boot < {edges}) __ve_boot <= __ve_boot + 1'b1;",
  f"  wire __ve_reset = __ve_boot < {edges} ? 1'b{c['reset_active']} : {c['reset']};"]
 for side in ('g','t'):
  for n,w in c['outputs'].items():lines.append('  wire '+('' if w==1 else f'[{w-1}:0] ')+f'__ve_{side}_{n};')
 for core,instance,side in [('gold_core','gold','g'),('gate_core','gate','t')]:
  wires=[f'.{n}('+('__ve_reset' if n==c['reset'] else n)+')' for n in c['inputs']]
  wires += [f'.{n}(__ve_{side}_{n})' for n in c['outputs']]
  lines.append(f'  {core} {instance}('+', '.join(wires)+');')
 total=sum(c['outputs'].values())
 for side in ('g','t'):lines.append(f"  wire [{total-1}:0] __ve_{side}_outputs = {{"+', '.join('__ve_'+side+'_'+n for n in c['outputs'])+'};')
 lines += ["  wire __ve_undefined = ((^__ve_g_outputs) === 1'bx) || ((^__ve_t_outputs) === 1'bx);",
  f'  assign mismatch = (__ve_boot == {edges}) && (__ve_undefined || (__ve_g_outputs !== __ve_t_outputs));','endmodule']
 return '\n'.join(lines)+'\n'

def check_ports(ports,c):
 expected={**{n:('input',w) for n,w in c['inputs'].items()},**{n:('output',w) for n,w in c['outputs'].items()}}
 if set(ports)!=set(expected):raise ValueError('top interface coverage differs from explicit contract')
 for n,(direction,width) in expected.items():
  if ports[n]['direction']!=direction or len(ports[n]['bits'])!=width:raise ValueError('top port width/direction mismatch')

def check_sequential_model(model,clock):
 clk=model['ports'][clock]['bits']
 for cell in model['cells'].values():
  kind=cell['type']
  if not kind.startswith('$') or any(x in kind.lower() for x in ('latch','mem','any','all','assert','assume')):raise ValueError('residual blackbox/latch/memory/formal primitive')
  if 'dff' in kind.lower() or 'ff'==kind.lower().strip('$'):
   if kind not in ('$dff','$_DFF_P_') or cell['connections'].get('CLK',cell['connections'].get('C'))!=clk:raise ValueError('unsupported state/clock; only common positive DFFs admitted')
   if int(cell.get('parameters',{}).get('CLK_POLARITY','1'),2)!=1:raise ValueError('negative clock not admitted')

def proof_script(work,property_name):
 work=_posix_path(work)
 if property_name not in ('mismatch','strengthened_mismatch'):raise ValueError('unknown proof property')
 extra=f'read_verilog -formal -sv {work}/state_relation.v\n' if property_name=='strengthened_mismatch' else ''
 return (f'read_rtlil {work}/proof-input.il\n'+extra+f'hierarchy -check -top acceptance_miter\nproc; flatten; opt; dffunmap; opt_clean; check -assert\nwrite_json {work}/proof-model.json\n'
  +f'sat -seq 5 -tempinduct -maxsteps 32 -enable_undef -set-def-inputs -set-init-def -prove {property_name} 0 -verify -timeout 30 -show mismatch -show-inputs -show-regs -dump_json {work}/counterexample.json\n')

def prepare_script(work,c):
 work=_posix_path(work);validate_contract(c)
 return f"""read_liberty {work}/functional.lib
write_json {work}/models.json
design -reset
read_verilog {work}/gold.v
hierarchy -check -top {c['top']}
proc
write_json {work}/gold-interface.json
flatten; memory_map; opt; dffunmap; opt_clean
rename {c['top']} gold_core
write_rtlil {work}/gold.il
design -reset
read_liberty {work}/functional.lib
read_verilog {work}/candidate.v
hierarchy -check -top {c['top']}
write_json {work}/gate-linked.json
proc; flatten; opt; dffunmap; opt_clean
rename {c['top']} gate_core
write_rtlil {work}/gate.il
design -reset
read_rtlil {work}/gold.il
read_rtlil {work}/gate.il
read_verilog -formal -sv {work}/miter.v
hierarchy -check -top acceptance_miter
proc; flatten; memory_map; opt; dffunmap; opt_clean; check -assert
write_json {work}/miter.json
write_rtlil {work}/miter.il
"""

def _admission(package,contract,frozen,work,image_record):
 verify_verification_package(package)
 subject=read_json(package/'subject.json');plan=read_json(package/'plan.json');bind_contract(contract,subject)
 if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):raise ValueError('native Formal requires Linux x86_64; no EDA executed')
 _posix_path(frozen);_posix_path(work);_posix_path(package)
 if not os.statvfs(frozen).f_flag & os.ST_RDONLY:raise ValueError('frozen source must be mounted read-only')
 if not os.statvfs(package).f_flag & os.ST_RDONLY:raise ValueError('candidate package must be mounted read-only')
 if _source_inventory(frozen)!=subject['frozen']['orfs_commit']:raise ValueError('frozen source commit mismatch')
 support=read_json(pathlib.Path(__file__).parent/'action_support.json')
 if subject['frozen']['orfs_image']!=support['image'] or subject['frozen']['orfs_commit']!=support['orfs_commit'] or subject['tools']!=support['binaries']:raise ValueError('unregistered OCI/source/tool identity')
 image=check_image_record(image_record,support)
 files={contract['rtl_path']:subject['frozen']['rtl_sha256'],contract['sdc_path']:subject['frozen']['sdc_sha256'],**subject['library']}
 for n,h in files.items():
  if sha(_unlinked(frozen/n))!=h:raise ValueError('frozen Formal source/library/SDC mismatch')
 yosys=[p for p in subject['tools'] if pathlib.PurePosixPath(p).name=='yosys']
 if len(yosys)!=1 or sha(_unlinked(yosys[0]))!=plan['next_check']['inputs']['engine_sha256']:raise ValueError('Yosys identity mismatch')
 return subject,plan['next_check'],yosys[0],image

def execute_formal(package,contract_path,frozen_root,work,execute=False,image_record=None):
 package=_unlinked(package);verify_verification_package(package);c=read_json(contract_path);subject=read_json(package/'subject.json');bind_contract(c,subject)
 if not execute:return {'status':'NOT_RUN','subject_id':subject['subject_id'],'requires_explicit_execution':True}
 frozen=_unlinked(frozen_root);out=_unlinked(work)
 if out.exists() or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (frozen,package)):raise ValueError('fresh work outside frozen source/package required')
 subject,task,yosys,image=_admission(package,c,frozen,out,image_record)
 out.mkdir(parents=True);(out/'tmp').mkdir();started=time.monotonic();env=clean_environment(out);steps=[]
 receipt={'schema':'verieda.verifier-receipt.v1','task_id':task['task_id'],'inputs':task['inputs'],
  'engine_sha256':task['inputs']['engine_sha256'],'return_code':2,'runtime_seconds':0,'log_path':'admission.log',
  'work_path':str(out),'python':{'version':sys.version,'executable_sha256':sha(sys.executable)},
  'status':'UNKNOWN','formal_gate':'UNKNOWN','contract_sha256':digest(c),'image_host_record':image,'steps':steps,
  'adapter_sources':{str(p.relative_to(pathlib.Path(__file__).resolve().parents[1])):sha(p) for p in
   [pathlib.Path(__file__),*[pathlib.Path(__file__).parent/n for n in ('invariants.py','liberty.py','execution.py','verification.py','case.py','evidence.py','formal.py')],pathlib.Path(__file__).resolve().parents[1]/'acceptance/verify.py',pathlib.Path(__file__).resolve().parents[1]/'contracts/registry.json']},
  'design_acceptance':'NOT_EVALUATED'}
 def run_script(name,script):
  remaining=300-(time.monotonic()-started)
  if remaining<=0:raise TimeoutError('300-second Formal budget exhausted')
  (out/(name+'.ys')).write_bytes(script.encode());log=out/(name+'.log')
  step=_run([yosys,'-Q','-T','-s',str(out/(name+'.ys'))],out,env,log,remaining)
  steps.append(step);receipt.update(return_code=step['return_code'],log_path=log.name)
  if step['return_code']!=0:raise RuntimeError('tool exit during '+name)
 try:
  helptext='; '.join('help '+n for n in ['read_liberty','read_verilog','read_rtlil','write_rtlil','write_json','design','hierarchy','proc','flatten','memory_map','opt','dffunmap','opt_clean','rename','check','sat'])
  run_script('capabilities',helptext+'\n');require_proof_capabilities((out/'capabilities.log').read_text())
  # Copy only the exact identified sources; original state/proof artifacts are absent.
  (out/'gold.v').write_bytes((frozen/c['rtl_path']).read_bytes());(out/'candidate.v').write_bytes((package/'candidate.v').read_bytes())
  (out/'source.lib').write_bytes((frozen/c['library_path']).read_bytes())
  if sha(out/'gold.v')!=task['inputs']['rtl_sha256'] or sha(out/'candidate.v')!=task['inputs']['netlist_sha256'] or sha(out/'source.lib')!=task['inputs']['library_sha256']:raise ValueError('copied proof input SHA mismatch')
  write(out/'contract.json',c)
  run_script('discover',f'read_verilog {out}/candidate.v\nwrite_json {out}/unlinked.json\n')
  modules=read_json(out/'unlinked.json',16*1024*1024)['modules']
  if set(modules)!={c['top']}:raise ValueError('candidate module closure differs from contract top')
  discovered={cell['type'] for cell in modules[c['top']]['cells'].values()}
  if not discovered or len(discovered)>512:raise ValueError('unsupported candidate functional-cell count')
  derived,selection=subset_liberty((out/'source.lib').read_bytes(),discovered);(out/'functional.lib').write_bytes(derived)
  selection.update(netlist_sha256=sha(out/'candidate.v'),engine_sha256=sha(yosys));write(out/'library-selection.json',selection)
  (out/'miter.v').write_bytes(make_miter(c).encode())
  prep=prepare_script(out,c)
  run_script('prepare',prep)
  gold=read_json(out/'gold-interface.json',16*1024*1024)['modules'][c['top']]
  linked=read_json(out/'gate-linked.json',16*1024*1024)['modules'][c['top']]
  check_ports(gold['ports'],c);check_ports(linked['ports'],c)
  used={cell['type'] for cell in linked['cells'].values()};models=read_json(out/'models.json',16*1024*1024)['modules'];require_model_closure(discovered,used,models)
  if sha(out/'gold.il')==sha(out/'gate.il'):raise ValueError('gold/gate normalized designs unexpectedly identical')
  m=read_json(out/'miter.json',16*1024*1024)['modules']['acceptance_miter'];check_sequential_model(m,c['clock'])
  prop='mismatch';il=(out/'miter.il').read_bytes();strength={'status':'NOT_USED'}
  if c['strengthening']=='gcd-state-v1':
   try:
    # The auxiliary relation is ORed into the property, never assumed.
    il,relation,strength=strengthen_miter(il,(out/'miter.json').read_bytes(),boot_name='__ve_boot')
    (out/'state_relation.v').write_bytes(relation);prop='strengthened_mismatch'
   except ValueError as ex:strength={'status':'UNAVAILABLE_FRESH_BINDINGS','reason':str(ex)}
  (out/'proof-input.il').write_bytes(il);write(out/'strengthening.json',strength)
  write(out/'coverage.json',{'inputs':c['inputs'],'outputs':c['outputs'],'output_bits':sum(c['outputs'].values()),'functional_cells':sorted(used),'no_blackbox':True,'common_positive_clock':True,'property':prop,'contract_sha256':digest(c)})
  run_script('proof',proof_script(out,prop))
 except (OSError,ValueError,KeyError,TypeError,RuntimeError,TimeoutError) as ex:
  receipt['error']=str(ex)
  if not steps or isinstance(ex,(ValueError,KeyError,TypeError)):
   (out/'admission.log').write_bytes(('HOLD: '+str(ex)+'\n').encode());receipt.update(return_code=2,log_path='admission.log')
  if isinstance(ex,TimeoutError):receipt.update(return_code=124)
 elapsed=time.monotonic()-started;receipt['runtime_seconds']=elapsed
 raw=(out/receipt['log_path']).read_text(errors='replace') if (out/receipt['log_path']).is_file() else ''
 obs=observe_yosys(receipt['return_code'],raw)
 receipt.update(status=obs['observation'],observation=obs,formal_gate=obs['formal_gate'])
 # Explicit model/contract admission failures must not be mistaken for RTL bugs.
 if 'error' in receipt and receipt['log_path']=='admission.log':receipt['status']='HOLD_MODEL_OR_CONTRACT'
 write(out/'receipt.json',receipt)
 archive=seal_formal(out,out/'verifier-result.zip')
 return {**receipt,'result_archive':archive}

PUBLIC_FILES=('receipt.json','contract.json','admission.log','capabilities.ys','capabilities.log','gold.v','candidate.v','source.lib','functional.lib',
 'discover.ys','discover.log','unlinked.json','library-selection.json','miter.v','prepare.ys','prepare.log','models.json','gold-interface.json',
 'gate-linked.json','gold.il','gate.il','miter.json','miter.il','proof-input.il','state_relation.v','strengthening.json','coverage.json',
 'proof.ys','proof.log','proof-model.json','counterexample.json')

def seal_formal(work,output):
 work=_unlinked(work);output=_unlinked(output)
 if output.exists():raise ValueError('formal archive already exists')
 data={}
 for name in PUBLIC_FILES:
  p=_unlinked(work/name)
  if not p.exists():continue
  if not p.is_file() or p.stat().st_size>16*1024*1024:raise ValueError('oversized/invalid formal payload')
  data[name]=p.read_bytes()
 if 'receipt.json' not in data or sum(map(len,data.values()))>32*1024*1024:raise ValueError('formal payload receipt/total budget')
 data['file-sizes.json']=(json.dumps([{'path':n,'bytes':len(b)} for n,b in data.items()])+ '\n').encode()
 data['SHA256SUMS.txt']=''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in data.items()).encode()
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED) as z:
  for n,b in data.items():z.writestr(n,b)
 return {'path':str(output),'sha256':sha(output),'bytes':output.stat().st_size}
