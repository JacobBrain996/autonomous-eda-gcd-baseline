import pathlib,sys,unittest,tempfile,json,importlib.util
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def helper():
    spec=importlib.util.spec_from_file_location('native_acceptance',ROOT/'acceptance/verify.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class NativeBridgeTests(unittest.TestCase):
    def test_real_counterexample_has_a_distinct_native_verdict(self):
        self.assertEqual(helper().formal_verdict(1,'SAT temporal induction proof finished - model found for base case: FAIL!'),'FAIL_COUNTEREXAMPLE')
    def test_induction_exhaustion_is_not_counterexample(self):
        self.assertEqual(helper().formal_verdict(1,'Reached maximum number of time steps -> proof failed.'),'UNKNOWN_UNPROVEN')
    def test_sta_does_not_require_yosys_models(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);p=root/'sta';p.mkdir()
            (p/'pin-directions.tsv').write_text('DFF_X1\tQ\tOUTPUT\nDFF_X1\tD\tINPUT\n')
            (p/'wns.rpt').write_text('wns max -0.161583')
            (p/'tns.rpt').write_text('tns max -7.08646')
            blocks=[]
            for i in range(51):
                slack=-0.161583 if i==0 else -0.13849754
                blocks.append(f'Startpoint: launch\nEndpoint: target{i}\nPath Group: core_clock\nPath Type: max\n 0.1 0.2 ^ launch/Q (DFF_X1)\n 0.001 0.201 ^ target{i}/D (DFF_X1)\n 0.201 data arrival time\n {slack} slack (VIOLATED)\n')
            (p/'all_setup.rpt').write_text('\n'.join(blocks))
            helper().sta_results(root)
            self.assertEqual(json.loads((p/'paths.json').read_text())['STA_EXTRACTION_GATE'],'PASS')
            self.assertFalse((root/'formal').exists())
    def test_pin_direction_conflict_holds(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'pins.tsv';p.write_text('BUF_X1\tA\tINPUT\nBUF_X1\tA\tOUTPUT\n')
            with self.assertRaises(ValueError):helper().read_pin_models(p)
    def test_original_sdc_is_an_explicit_frozen_dependency(self):
        self.assertEqual(helper().SOURCES['designs/nangate45/gcd/constraint.sdc'],'952a1a0a6de30877f585ee924004ce66151ff8325ec77e274fd92d1fdbf36582')
    def test_counterexample_witness_must_show_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'witness.json';p.write_text('{"signal":[{"name":"mismatch","wave":"00.1"}]}')
            self.assertTrue(helper().counterexample_record(p)['mismatch_seen'])
            p.write_text('{"signal":[{"name":"mismatch","wave":"0..."}]}')
            self.assertIsNone(helper().counterexample_record(p))
            p.write_text('{"signal":[]}');self.assertIsNone(helper().counterexample_record(p))
    def test_missing_counterexample_is_not_failure_evidence(self):
        with tempfile.TemporaryDirectory() as d:self.assertIsNone(helper().counterexample_record(pathlib.Path(d)/'missing.json'))
    def test_nonfinite_sta_cannot_match_reference(self):
        for x in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaises(ValueError):helper().require_sta_identity(x,-7.08646,51)
    def test_snapshot_requires_explicit_valid_role(self):
        try:import tkinter
        except ImportError:self.skipTest('Tcl interpreter unavailable')
        t=tkinter.Tcl();t.eval('catch {unset env(VERIEDA_SNAPSHOT_ROLE)}')
        script=(ROOT/'acceptance/snapshot.tcl').read_text()
        with self.assertRaises(tkinter.TclError):t.eval(script)
        t.eval('set env(VERIEDA_SNAPSHOT_ROLE) invalid')
        with self.assertRaises(tkinter.TclError):t.eval(script)
        t.eval('unset env(VERIEDA_SNAPSHOT_ROLE)')
    def test_native_tcl_initialization_without_actual_eda(self):
        try:import tkinter
        except ImportError:self.skipTest('Tcl interpreter unavailable')
        for role in ['reference','candidate']:
            t=tkinter.Tcl()
            t.eval('rename file real_file; proc file {args} {}; rename open real_open; proc open {args} {return mock_channel}; rename close real_close; proc close {args} {}; rename puts real_puts; proc puts {args} {}; rename source real_source; proc source {args} {}')
            for cmd in ['help','read_liberty','read_db','write_sdc','report_units','check_setup','define_process_corner','set_extraction_rules_file','extract_parasitics','write_spef','read_spef','report_wns','report_tns','report_checks']:
                t.eval('proc '+cmd+' {args} {}')
            t.eval('proc read_sdc {path} {set ::captured_sdc $path}; namespace eval ord {}; proc ord::get_db_block {} {return mock_db}; proc mock_db {method} {if {$method eq "getBTerms"} {return port_clk}; return inst}; proc port_clk {method} {if {$method eq "getName"} {return clk}; return INPUT}; proc inst {method} {return master}; proc master {method} {if {$method eq "getName"} {return DFF_X1}; return term}; proc term {method} {if {$method eq "getName"} {return D}; return INPUT}')
            t.eval('set env(VERIEDA_SNAPSHOT_ROLE) '+role)
            for file in ['snapshot.tcl','sta.tcl']:
                s=(ROOT/'acceptance'/file).read_text();self.assertEqual(t.call('info','complete',s),1);t.eval(s)
                if file=='snapshot.tcl':self.assertEqual(t.eval('set captured_sdc'),'/frozen/flow/designs/nangate45/gcd/constraint.sdc' if role=='reference' else '/inputs/6_final.sdc')
            t.eval('unset env(VERIEDA_SNAPSHOT_ROLE)')
    def test_package_tamper_stops_before_native_execution(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);(root/'acceptance').mkdir();p=root/'payload.py';p.write_text('original')
            (root/'acceptance/PACKAGE_SHA256.json').write_text(json.dumps({'schema':'verieda.native-acceptance-package.v1','files':{'payload.py':hashlib.sha256(p.read_bytes()).hexdigest()}}))
            helper().package_check(root)
            p.write_text('changed')
            with self.assertRaises(ValueError):helper().package_check(root)
if __name__=='__main__':unittest.main()
