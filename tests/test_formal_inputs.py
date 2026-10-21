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
 def test_wrong_bytes_or_missing_input_is_not_substituted(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(ValueError):m.restore(b'not the authoritative ZIP',pathlib.Path(tmp)/'x')
if __name__=='__main__':unittest.main()
