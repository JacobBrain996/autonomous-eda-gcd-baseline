import importlib.util,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def helper():
    s=importlib.util.spec_from_file_location('path_acceptance',ROOT/'acceptance/verify.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class PathSegmentsTests(unittest.TestCase):
    def test_real_clock_tree_and_final_port_wire_are_classified(self):
        m=helper();f=ROOT/'tests/fixtures';models=m.read_pin_models(f/'nangate_pin_directions_39531565936.tsv')
        p=m.parse_sta_paths((f/'worst_setup_39531565936.txt').read_text(encoding='utf-8'),models)[0]
        self.assertAlmostEqual(p['data_cell_delay_ns'],0.357314038,places=9)
        self.assertAlmostEqual(p['data_net_delay_ns'],0.002443143,places=9)
        self.assertEqual(p['endpoint'],'resp_msg[12]')
        self.assertTrue(all(x['segment']=='clock' for x in p['points'] if x.get('cell')=='CLKBUF_X3'))
        self.assertEqual(p['points'][-1]['arc'],'net');self.assertEqual(p['points'][-1]['pin'],'resp_msg[12]')
    def test_input_clock_section_does_not_start_data_section(self):
        text='''Startpoint: data_in (input port clocked by clk)
Endpoint: reg (rising edge-triggered flip-flop)
Path Group: clk
Path Type: max
 0.1 0.1 ^ clk (in)
 0.2 0.3 ^ buf/A (BUF_X1)
 0.1 0.4 ^ buf/Z (BUF_X1)
 0.01 0.41 ^ data_in (in)
 0.02 0.43 ^ reg/D (DFF_X1)
 0.43 data arrival time
 -0.1 slack (VIOLATED)
'''
        models={'BUF_X1':{'ports':{'A':{'direction':'input'},'Z':{'direction':'output'}}},'DFF_X1':{'ports':{'D':{'direction':'input'}}}}
        p=helper().parse_sta_paths(text,models)[0]
        self.assertEqual(p['data_cell_delay_ns'],0)
        self.assertAlmostEqual(p['data_net_delay_ns'],0.02)
    def test_missing_launch_boundary_holds(self):
        t='Startpoint: launch\nEndpoint: endpoint\nPath Group: clk\n 0.1 0.2 ^ wrong/Q (DFF_X1)\n -0.1 slack (VIOLATED)\n'
        with self.assertRaises(ValueError):helper().parse_sta_paths(t,{'DFF_X1':{'ports':{'Q':{'direction':'output'}}}})
if __name__=='__main__':unittest.main()
