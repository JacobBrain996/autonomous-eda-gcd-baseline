import hashlib,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import verieda_formal_inputs as m
ARCHIVE=ROOT/'evidence/verieda-action-ed5d84b9bdf7/verieda-action-39571841412.zip'
class FormalInputsTests(unittest.TestCase):
 def test_restore_existing_actual_candidate_and_reject_reuse(self):
  raw=ARCHIVE.read_bytes()
  with tempfile.TemporaryDirectory() as tmp:
   target=pathlib.Path(tmp)/'inputs';r=m.restore(raw,target)
   self.assertEqual(r['candidate_id'],m.CANDIDATE)
   self.assertEqual(hashlib.sha256((target/'result.zip').read_bytes()).hexdigest(),m.INNER_SHA)
   with self.assertRaises(ValueError):m.restore(raw,target)
 def test_restore_exact_reviewed_proof_and_refuse_modified_archive(self):
  raw=(ROOT/'evidence/candidate-formal-b19cc94faa0d/candidate-formal-39617534483.zip').read_bytes()
  with tempfile.TemporaryDirectory() as tmp:
   out=pathlib.Path(tmp)/'proof.zip';result=m.restore_reviewed_proof(raw,out)
   self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(),result['archive_sha256'])
   with self.assertRaises(ValueError):m.restore_reviewed_proof(raw,out)
   with self.assertRaises(ValueError):m.restore_reviewed_proof(raw+b'x',pathlib.Path(tmp)/'bad.zip')
 def test_wrong_bytes_or_missing_input_is_not_substituted(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):m.restore(b'not the authoritative ZIP',pathlib.Path(tmp)/'x')
if __name__=='__main__':unittest.main()
