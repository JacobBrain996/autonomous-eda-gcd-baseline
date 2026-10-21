"""Real retained evidence integration; never executes EDA."""
import copy,json,pathlib,sys,unittest,hashlib,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.case import load_case
from verieda.evidence import read_bundle

SMOKE=ROOT/'evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip'
NATIVE=ROOT/'evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip'

class CaseTests(unittest.TestCase):
    def profile(self):return json.loads((ROOT/'cases/gcd.json').read_text())
    def test_real_case_preserves_timing_failure_and_scoped_proof(self):
        s=load_case(self.profile(),SMOKE,NATIVE)
        self.assertEqual(s['gates']['formal'],'PASS_RESET_CONTRACT_UNBOUNDED')
        self.assertEqual(s['gates']['timing'],'FAIL');self.assertEqual(s['gates']['constraints'],'UNKNOWN')
        self.assertAlmostEqual(s['metrics']['WNS']['value'],-0.1615832)
        self.assertEqual(s['timing_analysis']['violating_endpoints'],51)
        self.assertEqual(s['timing_analysis']['dominant_delay'],'CELL')
        self.assertEqual(s['timing_analysis']['worst_path']['endpoint'],'resp_msg[12]')
        self.assertEqual(s['acceptance'],'NOT_ACCEPTED')
        self.assertIn('two',s['formal']['contract'])
        self.assertEqual(s['formal']['trust'],'EXTERNAL_PROFILE_REVIEW')
    def test_missing_review_does_not_repeat_or_forge_proof(self):
        p=self.profile();p.pop('formal_review')
        s=load_case(p,SMOKE,NATIVE)
        self.assertEqual(s['gates']['formal'],'UNKNOWN')
        self.assertEqual(s['formal']['observation'],'UNBOUNDED_PROOF_REPORTED')
    def test_wrong_archive_or_run_is_rejected(self):
        for field in ('sha256','commit','run_id'):
            p=self.profile();p['acceptance'][field]='0'*64
            with self.subTest(field=field),self.assertRaises(ValueError):load_case(p,SMOKE,NATIVE)
    def test_false_review_hash_is_not_certified(self):
        p=self.profile();p['formal_review']['files']['formal/proof.log']='0'*64
        with self.assertRaises(ValueError):load_case(p,SMOKE,NATIVE)
    def test_input_mismatch_is_rejected_even_with_valid_archives(self):
        p=self.profile();p['inputs']['6_final.sdc']='0'*64
        with self.assertRaises(ValueError):load_case(p,SMOKE,NATIVE)
    def test_profile_cannot_omit_input_binding(self):
        p=self.profile();p['inputs'].pop('6_final.v')
        with self.assertRaises(ValueError):load_case(p,SMOKE,NATIVE)
    def test_consistently_sealed_incomplete_or_inconsistent_paths_are_rejected(self):
        # Rebuild actual archive checksums: integrity alone cannot establish coverage.
        for mutation in ('empty','subset','slack'):
            data=read_bundle(NATIVE);name='final-acceptance/output/sta/paths.json';paths=json.loads(data[name])
            if mutation=='empty':paths['all_violating_paths']=[];paths['all_violating_endpoints']=[]
            elif mutation=='subset':
                paths['all_violating_paths']=paths['all_violating_paths'][:1]
                paths['all_violating_endpoints']=[paths['all_violating_paths'][0]['endpoint']]
            else:paths['all_violating_paths'][0]['slack_ns']=-0.2
            data[name]=json.dumps(paths).encode()
            sizes=[{'path':n,'bytes':len(b)} for n,b in data.items() if n not in ('SHA256SUMS.txt','file-sizes.json')]
            data['file-sizes.json']=json.dumps(sizes).encode()
            data['SHA256SUMS.txt']=''.join(hashlib.sha256(b).hexdigest()+'  '+n+'\n' for n,b in data.items() if n!='SHA256SUMS.txt').encode()
            with tempfile.TemporaryDirectory() as tmp:
                archive=pathlib.Path(tmp)/'synthetic-malformed.zip'
                with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                    for n,b in data.items():z.writestr(n,b)
                profile=self.profile();profile['acceptance']['sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):load_case(profile,SMOKE,archive)

if __name__=='__main__':unittest.main()
