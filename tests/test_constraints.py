import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
BASE='''current_design gcd
create_clock -period 0.25 -name core [get_ports {clk}]
create_clock -name virtual -period 0.25
set_clock_latency 0.07 [get_clocks virtual]
set_input_delay 0.05 -clock [get_clocks virtual] -add_delay [get_ports {a[0]}]
set_output_delay 0.05 -clock virtual -add_delay [get_ports {y[0]}]
set_propagated_clock [get_clocks core]
'''
class ConstraintTests(unittest.TestCase):
    def compare(self,a,b):
        from verieda.constraints import compare_sdc
        return compare_sdc(a,b)
    def test_io_coverage_from_actual_export_is_complete_but_not_full_certificate(self):
        import zipfile
        from test_case import NATIVE
        from verieda.constraints import inspect_io_coverage
        with zipfile.ZipFile(NATIVE) as z:
            root='final-acceptance/output/constraints/reference/'
            r=inspect_io_coverage(z.read(root+'evaluated.sdc').decode(),z.read(root+'ports.tsv').decode())
        self.assertEqual(r['observation'],'COMPLETE_WITHIN_LITERAL_PROFILE')
        self.assertEqual(r['port_count'],54);self.assertEqual(r['data_port_count'],53)
        self.assertEqual(r['missing_io_modes'],[]);self.assertEqual(r['full_constraint_gate'],'UNKNOWN')
    def test_io_coverage_detects_missing_modes_and_does_not_exempt_named_reset(self):
        from verieda.constraints import inspect_io_coverage
        ports='clk\tINPUT\na[0]\tINPUT\ny[0]\tOUTPUT\nreset\tINPUT\n'
        r=inspect_io_coverage(BASE.replace('set_output_delay 0.05','set_output_delay 0.05 -max'),ports)
        self.assertEqual(r['observation'],'GAPS_WITHIN_LITERAL_PROFILE')
        self.assertIn({'port':'reset','direction':'INPUT','clock':None,'missing':['min','max']},r['missing_io_modes'])
        self.assertIn({'port':'y[0]','direction':'OUTPUT','clock':'virtual','missing':['min']},r['missing_io_modes'])
    def test_io_coverage_rejects_unresolved_or_directionally_invalid_inventory(self):
        from verieda.constraints import inspect_io_coverage
        for ports in ('clk\tINPUT\na[0]\tINPUT\n','clk\tINPUT\na[0]\tOUTPUT\ny[0]\tOUTPUT\n',
                      'clk\tINPUT\na[0]\tINPUT\na[0]\tINPUT\ny[0]\tOUTPUT\n'):
            self.assertEqual(inspect_io_coverage(BASE,ports)['observation'],'HOLD_PROFILE_OR_INVENTORY')
    def test_io_min_and_max_from_different_clocks_do_not_form_a_complete_pair(self):
        from verieda.constraints import inspect_io_coverage
        sdc=BASE.replace('create_clock -name virtual -period 0.25','create_clock -name virtual -period 0.25\ncreate_clock -name other -period 0.25')
        line='set_input_delay 0.05 -clock [get_clocks virtual] -add_delay [get_ports {a[0]}]'
        sdc=sdc.replace(line,line.replace('0.05','0.05 -min')+'\n'+line.replace('0.05','0.05 -max').replace('[get_clocks virtual]','[get_clocks other]'))
        r=inspect_io_coverage(sdc,'clk\tINPUT\na[0]\tINPUT\ny[0]\tOUTPUT\n')
        self.assertEqual(r['observation'],'GAPS_WITHIN_LITERAL_PROFILE');self.assertEqual(len(r['missing_io_modes']),2)
    def test_module_exists(self):self.assertTrue((ROOT/'verieda/constraints.py').exists())
    def test_equivalent_numbers_and_option_order(self):
        other=BASE.replace('-period 0.25 -name core','-name core -period 2.5e-1').replace('0.05','0.0500')
        r=self.compare(BASE,other);self.assertEqual(r['comparison'],'EQUAL_WITHIN_PROFILE');self.assertEqual(r['full_constraint_gate'],'UNKNOWN')
    def test_period_relaxation_is_detected(self):
        r=self.compare(BASE,BASE.replace('0.25','0.5'));self.assertEqual(r['comparison'],'DIFFERENT');self.assertTrue(r['changes'])
    def test_io_delay_change_is_detected(self):self.assertEqual(self.compare(BASE,BASE.replace('0.05','0.02'))['comparison'],'DIFFERENT')
    def test_false_path_is_unknown_never_equal(self):self.assertEqual(self.compare(BASE,BASE+'set_false_path -from [get_ports a]\n')['comparison'],'UNKNOWN')
    def test_dynamic_tcl_is_not_executed(self):self.assertEqual(self.compare(BASE,'exec touch NEVER_EXECUTE\n')['comparison'],'UNKNOWN')
    def test_unexpanded_variable_is_unknown(self):self.assertEqual(self.compare(BASE,BASE.replace('0.25','$period'))['comparison'],'UNKNOWN')
    def test_propagation_change_is_not_implicitly_allowed(self):self.assertEqual(self.compare(BASE,BASE.replace('set_propagated_clock [get_clocks core]',''))['comparison'],'DIFFERENT')
    def test_duplicate_clock_is_unknown(self):self.assertEqual(self.compare(BASE,BASE+'create_clock -name core -period 1 [get_ports clk]\n')['comparison'],'UNKNOWN')
    def test_array_port_is_literal(self):self.assertEqual(self.compare(BASE,BASE)['comparison'],'EQUAL_WITHIN_PROFILE')
    def test_wildcard_collection_is_unknown(self):self.assertEqual(self.compare(BASE,BASE.replace('{a[0]}','{a*}'))['comparison'],'UNKNOWN')
    def test_malformed_tcl_is_unknown(self):self.assertEqual(self.compare(BASE,BASE+'set_input_delay 1 [get_ports {a]\n')['comparison'],'UNKNOWN')
    def test_nonfinite_and_extreme_numbers_are_unknown(self):
        for x in ['NaN','Infinity','1e-9999','1e9999','0.250000000000000000000000000001']:
            self.assertEqual(self.compare(BASE,BASE.replace('0.25',x))['comparison'],'UNKNOWN')
    def test_clock_must_exist_when_it_is_referenced(self):
        bad='current_design gcd\nset_clock_latency 0.07 [get_clocks virtual]\n'+BASE.replace('current_design gcd\n','').replace('set_clock_latency 0.07 [get_clocks virtual]\n','')
        self.assertEqual(self.compare(BASE,bad)['comparison'],'UNKNOWN')
    def test_real_export_is_supported(self):
        p=ROOT/'evidence/smoke-9644bb3f8ed4/artifact/gds/6_final.sdc';s=p.read_text()
        self.assertEqual(self.compare(s,s)['comparison'],'EQUAL_WITHIN_PROFILE')
if __name__=='__main__':unittest.main()
