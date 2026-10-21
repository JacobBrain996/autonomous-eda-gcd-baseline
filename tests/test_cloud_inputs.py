"""GitHub input validation tests; no network or EDA calls."""
import copy,importlib.util,pathlib,unittest,json,hashlib,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cloud_inputs',ROOT/'scripts/verieda_cloud_inputs.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CloudInputTests(unittest.TestCase):
    def test_artifact_metadata_requires_exact_identity_unexpired_digest_and_size(self):
        p=json.loads((ROOT/'cases/gcd.json').read_text())['smoke'];pin=module.PINS['smoke']
        meta={'id':pin['id'],'expired':False,'size_in_bytes':pin['bytes'],'digest':'sha256:'+p['sha256'],
              'workflow_run':{'id':int(p['run_id']),'head_sha':p['commit']}}
        module.validate_metadata(meta,p,pin)
        for field,value in [('expired',True),('id',0),('digest','wrong'),('size_in_bytes',1)]:
            bad=copy.deepcopy(meta);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):module.validate_metadata(bad,p,pin)
        meta['workflow_run']['head_sha']='0'*40
        with self.assertRaises(ValueError):module.validate_metadata(meta,p,pin)
    def test_fixed_public_inputs_are_downloaded_once_and_never_overwritten(self):
        # Tiny payloads exercise our validation/write contract, not GitHub transport.
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);profile={};pins={};responses={};calls=[]
            for i,name in enumerate(('smoke','acceptance'),1):
                body=('SYNTHETIC_'+name).encode();profile[name]={'run_id':str(i),'commit':'a'*40,'sha256':hashlib.sha256(body).hexdigest()};pins[name]={'id':i,'bytes':len(body)}
                endpoint='actions/artifacts/'+str(i)
                responses[endpoint]=json.dumps({'id':i,'expired':False,'size_in_bytes':len(body),'digest':'sha256:'+profile[name]['sha256'],'workflow_run':{'id':i,'head_sha':'a'*40}}).encode()
                responses[endpoint+'/zip']=body
            def api(path):calls.append(path);return responses[path]
            module.download_inputs(root/'inputs',profile,api,pins)
            self.assertEqual(len(calls),4);self.assertEqual((root/'inputs/smoke.zip').read_bytes(),b'SYNTHETIC_smoke')
            with self.assertRaises(ValueError):module.download_inputs(root/'inputs',profile,api,pins)
            self.assertEqual(len(calls),4)

if __name__=='__main__':unittest.main()
