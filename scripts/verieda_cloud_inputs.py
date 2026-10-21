"""Read-only, exact public artifact restore for the single V0 integration job."""
import hashlib,json,os,pathlib,subprocess,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from verieda.case import read_json
from verieda.execution import _unlinked
from verieda.evidence import object_json
REPO='JacobBrain996/autonomous-eda-gcd-baseline'
PINS={'smoke':{'id':11736162790,'bytes':3202166},'acceptance':{'id':12320692531,'bytes':4299264}}

def validate_metadata(meta,expected,pin):
    try:
        if (meta['expired'] is not False or type(meta['id']) is not int or meta['id']!=pin['id']
            or type(meta['size_in_bytes']) is not int or meta['size_in_bytes']!=pin['bytes']
            or meta['digest']!='sha256:'+expected['sha256'] or str(meta['workflow_run']['id'])!=expected['run_id']
            or meta['workflow_run']['head_sha']!=expected['commit']):raise ValueError('pinned public artifact identity/expiry mismatch')
    except (KeyError,TypeError) as ex:raise ValueError('incomplete artifact metadata') from ex

def download_inputs(output,profile,api,pins=PINS):
    out=_unlinked(output)
    if out.exists():raise ValueError('input restore destination already exists; no retry or overwrite')
    out.mkdir();records={}
    for name in ('smoke','acceptance'):
        expected=profile[name];pin=pins[name];path='actions/artifacts/'+str(pin['id'])
        raw_meta=api(path)
        if len(raw_meta)>65536:raise ValueError('artifact metadata exceeds budget')
        meta,duplicates=object_json({'metadata':raw_meta},'metadata')
        if duplicates or not isinstance(meta,dict):raise ValueError('ambiguous artifact metadata')
        validate_metadata(meta,expected,pin)
        raw=api(path+'/zip')
        if len(raw)!=pin['bytes'] or hashlib.sha256(raw).hexdigest()!=expected['sha256']:raise ValueError('downloaded artifact byte identity mismatch')
        with (out/(name+'.zip')).open('xb') as stream:stream.write(raw)
        records[name]={'artifact_id':pin['id'],'run_id':expected['run_id'],'commit':expected['commit'],'sha256':expected['sha256'],'bytes':len(raw)}
    (out/'restore.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf-8')
    return records

def gh_api(path):
    try:return subprocess.check_output(['gh','api','--hostname','github.com','repos/'+REPO+'/'+path],stderr=subprocess.PIPE,timeout=45)
    except subprocess.CalledProcessError as ex:raise ValueError('GitHub GET failed rc='+str(ex.returncode)+' endpoint='+path+' (credential/response output withheld)') from ex

if __name__=='__main__':
    try:
        if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise ValueError('fixed public repository context required')
        print(json.dumps(download_inputs('evidence/action-job/inputs',read_json('cases/gcd.json'),gh_api),indent=2))
    except (OSError,ValueError,subprocess.SubprocessError) as ex:raise SystemExit('HOLD: '+str(ex))
