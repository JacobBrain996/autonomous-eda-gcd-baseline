import pathlib,sys,json,unittest,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
class InvariantTests(unittest.TestCase):
    def fixture(self):
        names=[('boot',2),('gold.ctrl.state.out',2),('gold.dpath.a_reg.out',16),('gold.dpath.b_reg.out',16)]
        names += [(f'gate.ctrl.state.out[{i}]$_DFF_P_.Q',1) for i in range(3)]
        names += [(f'gate.dpath.{r}_reg.out[{i}]$_DFFE_PP_.Q',1) for r in ['a','b'] for i in range(16)]
        nets={'mismatch':{'bits':[999]}};cells={};wires=['module \\acceptance_miter','  wire input 1 \\clk','  wire output 2 \\mismatch'];bit=10
        for i,(name,width) in enumerate(names):
            bits=list(range(bit,bit+width));bit+=width;nets[name]={'bits':bits}
            cells[str(i)]={'type':'$dff','connections':{'CLK':[1],'Q':bits},'parameters':{'CLK_POLARITY':'1'}}
            wires.append('  wire '+('width '+str(width)+' ' if width>1 else '')+'\\'+name)
        obj={'modules':{'acceptance_miter':{'ports':{'clk':{'direction':'input','bits':[1]},'mismatch':{'direction':'output','bits':[999]}},'netnames':nets,'cells':cells}}}
        return ('\n'.join(wires)+'\nend\n').encode(),obj
    def call(self,il,obj):
        from verieda.invariants import strengthen_miter
        return strengthen_miter(il,json.dumps(obj).encode())
    def test_original_body_preserved_and_bound_to_source(self):
        il,obj=self.fixture();new,v,manifest=self.call(il,obj)
        self.assertTrue(new.startswith(il[:-4]));self.assertEqual(manifest['original_il_sha256'],hashlib.sha256(il).hexdigest())
        self.assertEqual(manifest['lemma_status'],'UNPROVEN_CANDIDATE')
        self.assertIn(b'original_mismatch || boot_bad ||',v)
        self.assertIn(b'connect \\original_mismatch \\mismatch',new)
    def test_clock_or_missing_state_alias_holds(self):
        for which in ['clock','alias']:
            il,obj=self.fixture();m=obj['modules']['acceptance_miter']
            if which=='clock':m['cells']['0']['connections']['CLK']=[88]
            else:del m['netnames']['gold.ctrl.state.out']
            with self.assertRaises(ValueError):self.call(il,obj)
    def test_wrong_native_width_or_ambiguous_structure_holds(self):
        il,obj=self.fixture()
        for bad in [il.replace(b'width 2 \\boot',b'width 3 \\boot'),il+b'junk',il.replace(b'module \\acceptance_miter',b'module \\other'),b'module \\another\nend\n'+il]:
            with self.assertRaises(ValueError):self.call(bad,obj)
    def test_overlapping_gold_gate_state_holds(self):
        il,obj=self.fixture();obj['modules']['acceptance_miter']['netnames']['gate.ctrl.state.out[0]$_DFF_P_.Q']['bits']=obj['modules']['acceptance_miter']['netnames']['boot']['bits'][:1]
        with self.assertRaises(ValueError):self.call(il,obj)
    @unittest.skipUnless((ROOT/'evidence/final-acceptance-cbe97b6aaa75/review/formal/miter.json').exists(),'native miter evidence not installed')
    def test_actual_native_bindings_are_not_numeric_ids_guessed_by_policy(self):
        from verieda.invariants import strengthen_miter
        p=ROOT/'evidence/final-acceptance-cbe97b6aaa75/review/formal';a,v,m=strengthen_miter((p/'miter.il').read_bytes(),(p/'miter.json').read_bytes())
        self.assertEqual(m['bindings']['gate_state'][0]['bits'],[611])
        self.assertEqual(m['bindings']['gold_state'][0]['bits'],[79,80])
        self.assertEqual(len(m['bindings']['gate_a']),16)
        self.assertEqual(m['lemma_status'],'UNPROVEN_CANDIDATE')
if __name__=='__main__':unittest.main()
