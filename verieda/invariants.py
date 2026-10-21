"""Candidate strengthening of a bound, existing miter; no assumed lemmas."""
import hashlib,json,re

RELATION=b'''module verieda_state_relation(
  input [1:0] boot, gold_state,
  input [2:0] gate_state,
  input [15:0] gold_a, gold_b, gate_a, gate_b,
  input original_mismatch,
  output strengthened_mismatch
);
  wire boot_bad = ((^boot) === 1'bx) || (boot > 2);
  wire undefined_state = ((^{gold_state,gate_state,gold_a,gold_b,gate_a,gate_b}) === 1'bx);
  // Hypothesis: gate bit 0=IDLE, bit 1=DONE, bit 2=CALC.
  // This relation must be proved with base/step, never assumed or used as a cutpoint.
  wire relation_bad = undefined_state || (gold_state > 2) ||
    (gold_a !== gate_a) || (gold_b !== gate_b) ||
    (gate_state !== {gold_state == 1, gold_state == 2, gold_state == 0});
  assign strengthened_mismatch = original_mismatch || boot_bad ||
    ((boot == 2) && relation_bad);
endmodule
'''

def strengthen_miter(il,model_json,boot_name='boot'):
    if not isinstance(boot_name,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',boot_name):raise ValueError('HOLD unsupported boot alias')
    if not isinstance(il,bytes) or not isinstance(model_json,bytes) or max(len(il),len(model_json))>16*1024*1024:raise ValueError('HOLD miter input budget/type')
    text=il.decode('utf-8');obj=json.loads(model_json)
    if set(obj.get('modules',{}))!={'acceptance_miter'} or not text.endswith('\nend\n') or re.findall(r'(?m)^module ([^\n]+)',text)!=['\\acceptance_miter']:raise ValueError('HOLD unsupported miter structure')
    m=obj['modules']['acceptance_miter'];nets=m['netnames'];clk=m['ports']['clk']['bits']
    if len(clk)!=1 or m['ports']['mismatch']['direction']!='output' or len(m['ports']['mismatch']['bits'])!=1:raise ValueError('HOLD miter interface')
    if 'strengthened_mismatch' in nets or 'verieda_relation' in m['cells']:raise ValueError('HOLD strengthening name collision')
    owners={}
    for name,c in m['cells'].items():
        if 'dff' not in c['type'].lower():continue
        if c['type'] not in ('$dff','$_DFF_P_'):raise ValueError('HOLD unsupported state FF')
        connections=c['connections']
        if connections.get('CLK',connections.get('C'))!=clk or int(c.get('parameters',{}).get('CLK_POLARITY','1'),2)!=1:raise ValueError('HOLD noncommon positive state clock')
        for bit in connections['Q']:
            if bit in owners:raise ValueError('HOLD multiple state drivers')
            owners[bit]=name
    def signal(name,width,state=True):
        bits=nets.get(name,{}).get('bits',[])
        if len(bits)!=width or any(type(x) is not int for x in bits):raise ValueError('HOLD state alias/width '+name)
        decl=re.search(r'(?m)^  wire ([^\n]*)\\'+re.escape(name)+r'$',text)
        if not decl:raise ValueError('HOLD absent RTLIL wire '+name)
        size=re.search(r'\bwidth (\d+)\b',decl[1])
        if (int(size[1]) if size else 1)!=width:raise ValueError('HOLD RTLIL/JSON width mismatch')
        if state and any(bit not in owners for bit in bits):raise ValueError('HOLD alias is not a state Q')
        return {'name':name,'bits':bits,'drivers':[owners[bit] for bit in bits] if state else []}
    bindings={'boot':[signal(boot_name,2)],'gold_state':[signal('gold.ctrl.state.out',2)],
      'gold_a':[signal('gold.dpath.a_reg.out',16)],'gold_b':[signal('gold.dpath.b_reg.out',16)],
      'gate_state':[signal(f'gate.ctrl.state.out[{i}]$_DFF_P_.Q',1) for i in range(3)],
      'gate_a':[signal(f'gate.dpath.a_reg.out[{i}]$_DFFE_PP_.Q',1) for i in range(16)],
      'gate_b':[signal(f'gate.dpath.b_reg.out[{i}]$_DFFE_PP_.Q',1) for i in range(16)]}
    state_bits=[bit for group in bindings.values() for item in group for bit in item['bits']]
    if len(state_bits)!=71 or len(set(state_bits))!=71:raise ValueError('HOLD overlapping state bindings')
    original=signal('mismatch',1,False)
    if original['bits']!=m['ports']['mismatch']['bits']:raise ValueError('HOLD original mismatch output binding')
    ports=[int(x) for x in re.findall(r'(?m)^  wire[^\n]*\b(?:input|output) (\d+) ',text)]
    if not ports:raise ValueError('HOLD no native port identifiers')
    lines=[f'  wire output {max(ports)+1} \\strengthened_mismatch','  cell \\verieda_state_relation \\verieda_relation']
    for port,group in bindings.items():
        names=['\\'+item['name'] for item in reversed(group)]
        expression=names[0] if len(names)==1 else '{ '+' '.join(names)+' }'
        lines.append('    connect \\'+port+' '+expression)
    lines.extend(['    connect \\original_mismatch \\mismatch','    connect \\strengthened_mismatch \\strengthened_mismatch','  end'])
    augmented=il[:-4]+('\n'.join(lines)+'\nend\n').encode()
    manifest={'schema':'verieda.strengthening-candidate.v1','original_il_sha256':hashlib.sha256(il).hexdigest(),
      'model_json_sha256':hashlib.sha256(model_json).hexdigest(),'augmented_il_sha256':hashlib.sha256(augmented).hexdigest(),
      'relation_verilog_sha256':hashlib.sha256(RELATION).hexdigest(),'bindings':bindings,
      'original_mismatch':original,'proof_property':'strengthened_mismatch == 0','lemma_status':'UNPROVEN_CANDIDATE',
      'scope':'original all-output mismatch OR auxiliary state/boot violations; no assumptions or initialization constraints added'}
    return augmented,RELATION,manifest
