import importlib.util, pathlib, unittest, tempfile, zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'acceptance/verify.py'
def module():
    spec=importlib.util.spec_from_file_location('acceptance', SCRIPT)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

class AcceptanceTests(unittest.TestCase):
    def test_prepared_module_exists(self):
        self.assertTrue(SCRIPT.is_file(), 'Independent acceptance implementation missing')
    def test_finite_bmc_never_passes(self):
        self.assertEqual(module().formal_verdict(0, 'SAT proof finished - no model found: SUCCESS!'), 'UNKNOWN_UNPROVEN')
    def test_unbounded_marker_requires_successful_exit(self):
        self.assertEqual(module().formal_verdict(1, 'Induction step proven: SUCCESS!'), 'ERROR_TOOL')
        self.assertEqual(module().formal_verdict(124, 'Induction step proven: SUCCESS!'), 'UNKNOWN_TIMEOUT')
    def test_induction_success_is_distinct_from_bmc(self):
        self.assertEqual(module().formal_verdict(0, 'Induction step proven: SUCCESS!'), 'PASS_RESET_CONTRACT_UNBOUNDED')
    def test_path_traversal_rejected(self):
        with self.assertRaises(ValueError):module().safe_name('../secret')
        with self.assertRaises(ValueError):module().safe_name('/secret')
    @unittest.skipUnless((ROOT/'evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip').is_file(),'authoritative Smoke ZIP absent')
    def test_authoritative_archive(self):
        with tempfile.TemporaryDirectory() as d:
            got=module().restore(ROOT/'evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip',pathlib.Path(d))
            self.assertEqual(set(got), {'6_final.odb','6_final.sdc','6_final.v','6_report.json'})
    def test_wrong_archive_is_hold(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'wrong.zip';p.write_bytes(b'not authoritative')
            with self.assertRaises(ValueError):module().restore(p,pathlib.Path(d)/'out')
    def test_models_required_for_every_used_cell(self):
        with self.assertRaises(ValueError):module().require_models({'DFF_X1','UNKNOWN_X1'},{'DFF_X1':{}})
    def test_functional_buffer_alias_is_not_a_blackbox(self):
        module().require_models({'BUF_X1'},{'BUF_X1':{'ports':{'A':{'direction':'input','bits':[2]},'Z':{'direction':'output','bits':[2]}},'cells':{}}})
    def test_unconnected_output_is_not_a_functional_model(self):
        with self.assertRaises(ValueError):module().require_models({'BAD'},{'BAD':{'ports':{'A':{'direction':'input','bits':[2]},'Z':{'direction':'output','bits':[3]}},'cells':{}}})
    def test_sta_missing_endpoint_coverage_is_hold(self):
        with self.assertRaises(ValueError):module().require_sta_identity(-0.161583,-7.08646,50)
    def test_sta_exact_reference_is_accepted(self):
        module().require_sta_identity(-0.161583,-7.08646,51)
    def test_sta_changed_analysis_is_hold(self):
        with self.assertRaises(ValueError):module().require_sta_identity(-0.15,-7.08646,51)
    def test_pin_increments_are_separated_from_cell_arcs(self):
        text='''Startpoint: launch
Endpoint: target
Path Group: core_clock
Path Type: max
  1 0.008 0.01 0.100123456 0.170123456 ^ launch/Q (DFF_X1)
    0.01 0.001000001 0.171123457 ^ buf/A (BUF_X1)
  1 0.003 0.01 0.020123456 0.191246913 ^ buf/Z (BUF_X1)
    0.01 0.002000002 0.193246915 ^ target/D (DFF_X1)
  0.193246915 data arrival time
  -0.001234567 slack (VIOLATED)
'''
        models={'DFF_X1':{'ports':{'Q':{'direction':'output'},'D':{'direction':'input'}}},'BUF_X1':{'ports':{'A':{'direction':'input'},'Z':{'direction':'output'}}}}
        got=module().parse_sta_paths(text,models)[0]
        self.assertAlmostEqual(got['data_cell_delay_ns'],0.120246912,places=9)
        self.assertAlmostEqual(got['data_net_delay_ns'],0.003000003,places=9)
        self.assertEqual(got['slack_ns'],-0.001234567)
    def test_missing_pin_model_is_hold(self):
        with self.assertRaises(KeyError):module().parse_sta_paths('Startpoint: a\nEndpoint: b\nPath Group: c\n  0.1 0.2 ^ a/Q (UNMODELED)\n -1 slack (VIOLATED)',{})

if __name__=='__main__':unittest.main()
