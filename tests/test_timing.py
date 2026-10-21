"""Offline path contribution interpretation, not new timing or ECO results."""
import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from verieda.timing import explain_timing
from verieda.case import load_case,digest
from verieda.decision import decide
from test_case import SMOKE,NATIVE

class TimingExplanationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.state=load_case(json.loads((ROOT/'cases/gcd.json').read_text()),SMOKE,NATIVE)
 def bind(self,s):s['state_id']=digest({k:v for k,v in s.items() if k!='state_id'});return s
 def test_real_path_sums_clock_exclusion_and_actual_cell_targets(self):
  r=explain_timing(self.state)
  self.assertEqual(r['contribution_gate'],'PASS_ARITHMETIC_CHECK')
  self.assertEqual(r['path']['endpoint'],'resp_msg[12]')
  self.assertEqual(r['path']['group'],'vclk_core_clock')
  self.assertAlmostEqual(r['data']['cell_delay_ns'],0.357314038)
  self.assertAlmostEqual(r['data']['net_delay_ns'],0.002443143)
  self.assertEqual(r['data']['cell_arc_count'],14)
  self.assertEqual(r['top_cell_arcs'][0]['cell'],'DFF_X1')
  self.assertTrue(r['top_cell_arcs'][0]['at_startpoint'])
  self.assertNotIn('CLKBUF',str(r['top_cell_arcs']))
  self.assertEqual(r['causal_root_cause'],'NOT_ESTABLISHED');self.assertFalse(r['execution_authorized'])
  self.assertIn('slew',r['missing_for_eco']);self.assertEqual(r['timing_gate'],'FAIL')
 def test_missing_trace_is_not_invented_and_inconsistent_trace_holds_proposals(self):
  s=copy.deepcopy(self.state);del s['timing_analysis']['worst_path']['points'];self.bind(s)
  self.assertEqual(explain_timing(s)['contribution_gate'],'NOT_AVAILABLE')
  s=copy.deepcopy(self.state);s['timing_analysis']['worst_path']['points'][-1]['increment_ns']=1;self.bind(s)
  r=explain_timing(s);self.assertEqual(r['contribution_gate'],'HOLD')
  self.assertEqual(decide(s,600)['next_action'],'HOLD_EVIDENCE')
 def test_negative_nonfinite_unknown_segments_and_oversize_trace_hold(self):
  for field,value in [('segment','unknown'),('arc','unknown'),('increment_ns',-1)]:
   s=copy.deepcopy(self.state);s['timing_analysis']['worst_path']['points'][-1][field]=value;self.bind(s)
   self.assertEqual(explain_timing(s)['contribution_gate'],'HOLD')
  s=copy.deepcopy(self.state);s['timing_analysis']['worst_path']['points']*=500;self.bind(s)
  self.assertEqual(explain_timing(s)['contribution_gate'],'HOLD')
 def test_no_design_name_cell_library_suffix_or_endpoint_pattern_is_required(self):
  s=copy.deepcopy(self.state);s['design']='counter'
  p=s['timing_analysis']['worst_path'];p.update(startpoint='q',endpoint='count',group='clk',data_cell_delay_ns=0.2,data_net_delay_ns=0.01)
  p['points']=[{'instance':'u_logic','pin':'OUT','cell':'arbitrary_cell','increment_ns':0.2,'arc':'cell','segment':'data'},
               {'instance':'count','pin':'count','cell':None,'increment_ns':0.01,'arc':'net','segment':'data'}]
  r=explain_timing(self.bind(s));self.assertEqual(r['contribution_gate'],'PASS_ARITHMETIC_CHECK')
  self.assertEqual(r['top_cell_arcs'][0]['cell'],'arbitrary_cell')

if __name__=='__main__':unittest.main()
