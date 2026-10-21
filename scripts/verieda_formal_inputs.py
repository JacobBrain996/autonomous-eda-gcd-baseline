"""Restore only the audited public synthesis result for one candidate job."""
import hashlib,io,json,os,pathlib,stat,sys,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.verieda_cloud_inputs import gh_api,validate_metadata,REPO
from verieda.evidence import name_ok,object_json,read_bundle,verify_bundle
from verieda.verification import prepare_verification
from verieda.execution import _unlinked
PIN={'id':12332122927,'bytes':143054}
EXPECTED={'run_id':'39571841412','commit':'ed5d84b9bdf7435b64c88973c91fab9bb1c3fbc8','sha256':'08e39dad3579134ce58f59e3938997b0203910487a7af085fdd81759904cf379'}
INNER_SHA='15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3'
CANDIDATE='499793611493800ca327c5630a19ddd5620d1857df7755744398c7025a72a86b'
def obj(data,name):
 value,duplicates=object_json(data,name)
 if duplicates or not isinstance(value,dict):raise ValueError('malformed public input object')
 return value

def restore(raw,output):
 out=_unlinked(output)
 if out.exists():raise ValueError('restore output exists; no overwrite/retry')
 if len(raw)!=PIN['bytes'] or hashlib.sha256(raw).hexdigest()!=EXPECTED['sha256']:raise ValueError('public synthesis archive SHA/size mismatch')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  items=z.infolist();names=[name_ok(i.filename) for i in items]
  if len(names)!=len(set(names)) or len(names)>100 or sum(i.file_size for i in items)>32*1024*1024 or any(stat.S_ISLNK(i.external_attr>>16) or i.file_size>16*1024*1024 for i in items):raise ValueError('invalid/bounded public ZIP required')
  source=obj({'s':z.read('action-job/artifact/execution-source.json')},'s')
  if source['GITHUB_RUN_ID']!=EXPECTED['run_id'] or source['GITHUB_SHA']!=EXPECTED['commit'] or source['GITHUB_RUN_ATTEMPT']!='1' or source['GITHUB_REPOSITORY']!=REPO:raise ValueError('parent action execution identity mismatch')
  inner=z.read('action-job/artifact/result.zip')
 if hashlib.sha256(inner).hexdigest()!=INNER_SHA:raise ValueError('inner synthesis result SHA mismatch')
 out.mkdir(parents=True)
 with (out/'result.zip').open('xb') as stream:stream.write(inner)
 data=read_bundle(out/'result.zip');verify_bundle(data);state=obj(data,'action/package/state.json');candidate=obj(data,'action/package/candidate.json')
 if candidate['candidate_id']!=CANDIDATE:raise ValueError('candidate differs from approved fixed input')
 manifest=prepare_verification(state,out/'result.zip',INNER_SHA,out/'package',300)
 record={**EXPECTED,'artifact_id':PIN['id'],'inner_sha256':INNER_SHA,'candidate_id':CANDIDATE,'subject_id':manifest['subject_id'],'task_id':manifest['task_id']}
 (out/'restore.json').write_bytes((json.dumps(record,indent=2)+'\n').encode());return record

def restore_reviewed_proof(raw,output):
 """Exact reviewed public result, never arbitrary producer-supplied PASS."""
 review=json.loads((pathlib.Path(__file__).resolve().parents[1]/'cases/gcd-speed.formal-review.json').read_text())
 pin=review['execution'];out=_unlinked(output)
 if out.exists() or len(raw)!=pin['artifact_bytes'] or hashlib.sha256(raw).hexdigest()!=pin['outer_sha256']:raise ValueError('reviewed proof archive changed/output exists')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  items=z.infolist();names=[name_ok(i.filename) for i in items]
  if len(names)!=len(set(names)) or len(names)>200 or sum(i.file_size for i in items)>64*1024*1024 or any(stat.S_ISLNK(i.external_attr>>16) or i.file_size>32*1024*1024 for i in items):raise ValueError('bounded proof ZIP required')
  hits=[n for n in names if n.endswith('/verifier-result.zip') or n=='verifier-result.zip']
  if len(hits)!=1:raise ValueError('unambiguous inner proof required')
  inner=z.read(hits[0])
 if hashlib.sha256(inner).hexdigest()!=review['archive_sha256']:raise ValueError('reviewed inner proof changed')
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('xb') as stream:stream.write(inner)
 return {'archive_sha256':review['archive_sha256'],'execution':pin}

if __name__=='__main__':
 if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise SystemExit('HOLD repository context')
 endpoint='actions/artifacts/'+str(PIN['id']);meta=gh_api(endpoint)
 if len(meta)>65536:raise SystemExit('HOLD artifact metadata size')
 validate_metadata(obj({'m':meta},'m'),EXPECTED,PIN)
 print(json.dumps(restore(gh_api(endpoint+'/zip'),'evidence/formal-job/inputs'),indent=2))
