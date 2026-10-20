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
