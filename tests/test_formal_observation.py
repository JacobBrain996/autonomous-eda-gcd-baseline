import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
class FormalObservationTests(unittest.TestCase):
    def observe(self,rc,text):
        from verieda.formal import observe_yosys
        return observe_yosys(rc,text)
    def test_module_exists(self):self.assertTrue((ROOT/'verieda/formal.py').exists())
    def test_counterexample_is_not_induction_exhaustion(self):
        a=self.observe(1,'SAT temporal induction proof finished - model found for base case: FAIL!')
        b=self.observe(1,'Reached maximum number of time steps -> proof failed.')
        self.assertEqual(a['observation'],'COUNTEREXAMPLE_REPORTED');self.assertEqual(b['observation'],'UNPROVEN_BOUND_EXHAUSTED')
    def test_finite_success_stays_unknown(self):
        a=self.observe(0,'SAT proof finished - no model found: SUCCESS!');self.assertEqual(a['observation'],'FINITE_OR_COMBINATIONAL_SUCCESS');self.assertEqual(a['formal_gate'],'UNKNOWN')
    def test_positive_unbounded_log_is_not_an_authenticated_proof(self):self.assertEqual(self.observe(0,'Induction step proven: SUCCESS!')['formal_gate'],'UNKNOWN')
    def test_nonzero_exit_vetoes_positive_log(self):self.assertEqual(self.observe(1,'Induction step proven: SUCCESS!')['observation'],'TOOL_ERROR')
    def test_timeout_is_not_counterexample(self):self.assertEqual(self.observe(124,'model found for base case: FAIL!')['observation'],'TIMEOUT')
    def test_solver_timeout_even_with_zero_exit(self):self.assertEqual(self.observe(0,'Interrupted SAT solver: TIMEOUT!')['observation'],'TIMEOUT')
    def test_sigkill_is_unknown_cause(self):self.assertEqual(self.observe(137,'')['observation'],'KILLED_UNKNOWN')
    def test_sigill_is_tool_error(self):self.assertEqual(self.observe(132,'illegal instruction')['formal_gate'],'ERROR')
    def test_missing_model_is_unknown(self):self.assertEqual(self.observe(1,'ERROR: Module XYZ is not part of the design')['observation'],'MODEL_OR_CAPABILITY_GAP')
if __name__=='__main__':unittest.main()
