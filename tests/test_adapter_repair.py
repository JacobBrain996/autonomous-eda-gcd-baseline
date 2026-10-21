import importlib.util,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def helper():
    s=importlib.util.spec_from_file_location('acceptance_repair',ROOT/'acceptance/verify.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class AdapterRepairTests(unittest.TestCase):
    def help_text(self):return (ROOT/'tests/fixtures/yosys_sat_help_39451358576.txt').read_text(encoding='utf-8')
    def test_real_grouped_options_are_supported(self):helper().require_proof_capabilities(self.help_text())
    def test_similarly_named_or_prose_options_do_not_satisfy_requirement(self):
        t=self.help_text()
        for candidate in [t.replace('-show-inputs,','-show-inputs-extra,'),t.replace('    -show-inputs, -show-outputs, -show-ports','        Example: -show-inputs')]:
            with self.assertRaises(ValueError):helper().require_proof_capabilities(candidate)
    def test_missing_sat_command_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):helper().require_proof_capabilities('No such command: sat\n'+self.help_text())
    def test_missing_option_reports_exact_name(self):
        with self.assertRaisesRegex(ValueError,'-set-init-def'):helper().require_proof_capabilities(self.help_text().replace('    -set-init-def','    -set-init-unknown'))
    def test_report_sections_keep_full_precision(self):
        t='noise\nVERIEDA_REPORT_BEGIN units\ntime 1ns\nVERIEDA_REPORT_END units\nVERIEDA_REPORT_BEGIN wns\nwns max -0.161583000\nVERIEDA_REPORT_END wns\n'
        self.assertEqual(helper().report_sections(t,['units','wns']),{'units':'time 1ns\n','wns':'wns max -0.161583000\n'})
    def test_truncated_duplicate_unordered_or_empty_reports_hold(self):
        for text in ['VERIEDA_REPORT_BEGIN units\n', 'VERIEDA_REPORT_BEGIN units\nVERIEDA_REPORT_END units\n','VERIEDA_REPORT_END units\nVERIEDA_REPORT_BEGIN units\nx\n', 'VERIEDA_REPORT_BEGIN other\nx\nVERIEDA_REPORT_END other\n']:
            with self.assertRaises(ValueError):helper().report_sections(text,['units'])
        t='VERIEDA_REPORT_BEGIN units\nx\nVERIEDA_REPORT_END units\n'
        with self.assertRaises(ValueError):helper().report_sections(t+t,['units'])
    def test_materialization_requires_exact_sections_and_no_stale_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'tool.log').write_text('VERIEDA_REPORT_BEGIN units\ntime 1ns\nVERIEDA_REPORT_END units\n')
            helper().capture_reports(p,['units']);self.assertEqual((p/'units.rpt').read_text(),'time 1ns\n')
            with self.assertRaises(FileExistsError):helper().capture_reports(p,['units'])
    def strict_tcl(self,role):
        try:import tkinter
        except ImportError:self.skipTest('Tcl interpreter unavailable')
        t=tkinter.Tcl()
        t.eval('set ::output {}; rename file real_file; proc file {args} {}; rename open real_open; proc open {args} {return mock_channel}; rename close real_close; proc close {args} {}; rename puts real_puts; proc puts {args} {if {[llength $args]==1} {lappend ::output [lindex $args 0]}}; rename source real_source; proc source {args} {}')
        for cmd in ['help','read_liberty','read_db','write_sdc','check_setup','define_process_corner','set_extraction_rules_file','extract_parasitics','write_spef','read_spef','report_checks']:
            t.eval('proc '+cmd+' {args} {}')
        t.eval('proc report_units {} {puts {time 1ns}}; proc report_wns {a b c} {if {[list $a $b $c] ne {-max -digits 9}} {error {invalid WNS options}}; puts {wns max -0.161583000}}; proc report_tns {a b c} {if {[list $a $b $c] ne {-max -digits 9}} {error {invalid TNS options}}; puts {tns max -7.086460000}}')
        t.eval('proc read_sdc {path} {}; namespace eval ord {}; proc ord::get_db_block {} {return mock_db}; proc mock_db {method} {if {$method eq "getBTerms"} {return port_clk}; return inst}; proc port_clk {method} {if {$method eq "getName"} {return clk}; return INPUT}; proc inst {method} {return master}; proc master {method} {if {$method eq "getName"} {return DFF_X1}; return term}; proc term {method} {if {$method eq "getName"} {return D}; return INPUT}')
        t.eval('set env(VERIEDA_SNAPSHOT_ROLE) '+role)
        return t
    def test_full_native_scripts_obey_strict_report_signatures(self):
        for name,names in [('snapshot.tcl',['units']),('sta.tcl',['units','wns','tns'])]:
            t=self.strict_tcl('reference');t.eval((ROOT/'acceptance'/name).read_text(encoding='utf-8'))
            output='\n'.join(t.splitlist(t.eval('set ::output')))+'\n'
            sections=helper().report_sections(output,names)
            self.assertEqual(sections['units'],'time 1ns\n')
            if name=='sta.tcl':self.assertIn('-0.161583000',sections['wns'])
    def test_native_error_is_not_swallowed_by_markers(self):
        import tkinter
        t=self.strict_tcl('candidate');t.eval('proc report_units {} {error {native report failure}}')
        with self.assertRaisesRegex(tkinter.TclError,'native report failure'):t.eval((ROOT/'acceptance/snapshot.tcl').read_text())

if __name__=='__main__':unittest.main()
