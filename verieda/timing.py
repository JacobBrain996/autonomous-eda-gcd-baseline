"""Bounded arithmetic over saved worst-path points; no STA, ECO or causality proof."""
import copy,math
from .case import digest
from .policy import _bound_state


def explain_timing(state):
 _bound_state(state)
 result={'schema':'verieda.timing-explanation.v1','state_id':state['state_id'],
  'contribution_gate':'NOT_AVAILABLE','timing_gate':state.get('gates',{}).get('timing','UNKNOWN'),
  'netlist_sha256':state.get('inputs',{}).get('6_final.v'),'path':None,'data':None,'clock':None,'top_cell_arcs':[],'top_net_arcs':[],'issues':[],
  'causal_root_cause':'NOT_ESTABLISHED','execution_authorized':False,
  'expected_improvement_ns':None,'missing_for_eco':['slew','load','fanout','legal equivalent library cells','hold and routed parasitic impact'],
  'scope':'worst reported path only; arithmetic consistency is not independent STA, full endpoint coverage or optimization evidence',
  'provenance':copy.deepcopy(state.get('provenance',{}).get('acceptance'))}
 def finish():result['explanation_id']=digest(result);return result
 path=state.get('timing_analysis',{}).get('worst_path')
 if not isinstance(path,dict) or 'points' not in path:return finish()
 try:
  points=path['points']
  if not isinstance(points,list) or not 1<=len(points)<=4096:raise ValueError('missing or excessive path points')
  def number(x):return type(x) in (int,float) and math.isfinite(x)
  def name(x):return isinstance(x,str) and 0<len(x)<=1024 and all(ord(c)>=32 and ord(c)!=127 for c in x)
  for k in ('startpoint','endpoint','group'):
   if not name(path.get(k)):raise ValueError('missing path identity')
  if not number(path.get('slack_ns')):raise ValueError('missing finite path slack')
  rows=[];clock=[]
  for index,p in enumerate(points):
   if not isinstance(p,dict) or p.get('segment') not in ('data','clock') or p.get('arc') not in ('cell','net'):raise ValueError('unsupported point segment/arc')
   v=p.get('increment_ns')
   if not number(v):raise ValueError('nonfinite point increment')
   if p['segment']=='clock':clock.append((p['arc'],v));continue
   if v<0:raise ValueError('negative data increment needs separate model review')
   if p.get('cell') is not None and not name(p['cell']):raise ValueError('invalid library cell name')
   if not name(p.get('instance')) or not name(p.get('pin')) or (p['arc']=='cell' and not name(p.get('cell'))):raise ValueError('missing data point identity')
   rows.append({'point_index':index,'instance':p['instance'],'pin':p['pin'],'cell':p.get('cell'),
                'increment_ns':v,'arc':p['arc'],'at_startpoint':p['instance']==path['startpoint']})
  cells=[r for r in rows if r['arc']=='cell'];nets=[r for r in rows if r['arc']=='net']
  if not cells or not nets:raise ValueError('incomplete cell/net trace')
  cell=math.fsum(r['increment_ns'] for r in cells);net=math.fsum(r['increment_ns'] for r in nets)
  for key,actual in (('data_cell_delay_ns',cell),('data_net_delay_ns',net)):
   if not number(path.get(key)) or abs(path[key]-actual)>1e-6:raise ValueError('point increments disagree with '+key)
  result.update(contribution_gate='PASS_ARITHMETIC_CHECK',path={k:path[k] for k in ('startpoint','endpoint','group','slack_ns')},
   data={'cell_delay_ns':cell,'net_delay_ns':net,'cell_arc_count':len(cells),'net_arc_count':len(nets),
         'cell_fraction':cell/(cell+net) if cell+net else None,
         'dominant_contribution':'CELL' if cell>2*net else 'NET' if net>2*cell else 'MIXED'},
   clock={'cell_delay_ns':math.fsum(v for arc,v in clock if arc=='cell'),'net_delay_ns':math.fsum(v for arc,v in clock if arc=='net'),
          'scope':'listed clock increments only; not skew, required time or a slack reconstruction'},
   top_cell_arcs=sorted(cells,key=lambda r:(-r['increment_ns'],r['point_index']))[:5],
   top_net_arcs=sorted(nets,key=lambda r:(-r['increment_ns'],r['point_index']))[:5])
 except (ValueError,KeyError,TypeError,OverflowError) as ex:
  result.update(contribution_gate='HOLD',issues=[str(ex)])
 return finish()
