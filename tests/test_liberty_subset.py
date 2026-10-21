import pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
CELL=b'cell (DFF_X1) { ff (IQ, IQN) { next_state : "D"; clocked_on : "CK"; } pin(Q) { direction: output; function: "IQ"; } }'
SOURCE=b'/* license and } cell(fake) { */\nlibrary (example) { time_unit : "1ns";\n'+CELL+b'\ncell (UNUSED) { pin(Q) { direction:output; } }\n}\n'

class LibertySubsetTests(unittest.TestCase):
    def subset(self,data,used):
        from verieda.liberty import subset_liberty
        return subset_liberty(data,used)
    def test_selected_cell_and_global_text_are_byte_exact(self):
        import hashlib
        data,m=self.subset(SOURCE,{'DFF_X1'})
        self.assertEqual(data,SOURCE.replace(b'cell (UNUSED) { pin(Q) { direction:output; } }',b''))
        self.assertEqual(m['selected_cells']['DFF_X1']['sha256'],hashlib.sha256(CELL).hexdigest())
        self.assertEqual(m['omitted_cells'],['UNUSED']);self.assertEqual(m['model_gate'],'NOT_IMPORTED')
    def test_quoted_braces_comments_and_escaped_quotes_are_not_groups(self):
        text=b'library("lib") { cell("A") { comment : "braces } { and \\" ok"; // }\n pin (Z) { function:"A"; } /* } */ } }'
        data,m=self.subset(text,{'A'});self.assertEqual(data,text)
    def test_cell_keyword_in_define_arguments_is_not_a_cell_group(self):
        text=b'library(L) { define(drive_strength, cell, float); cell(A) { area : 1; } }'
        data,m=self.subset(text,{'A'});self.assertEqual(data,text)
    def test_missing_required_cell_is_hold(self):
        with self.assertRaisesRegex(ValueError,'MISSING'):self.subset(SOURCE,{'MISSING'})
    def test_duplicate_cells_are_hold(self):
        with self.assertRaises(ValueError):self.subset(SOURCE.replace(b'cell (UNUSED)',b'cell (DFF_X1)'),{'DFF_X1'})
    def test_malformed_or_unsupported_scope_is_hold(self):
        for text in [SOURCE[:-2],SOURCE+b'library(other) {}',b'cell(A) {}',b'library(L) { cell(A) { cell(B) {} } }',b'library(L) { /* missing',b'library(L) { cell(A) { function:"missing; } }',b'library(L) { cell(A) {} } junk']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):self.subset(text,{'A'})
    def test_empty_or_bad_selection_is_hold(self):
        for used in [set(),{'a/b'},{'$primitive'},{'x'*300},'DFF_X1']:
            with self.assertRaises(ValueError):self.subset(SOURCE,used)
    def test_output_reparses_to_same_complete_selected_body(self):
        data,m=self.subset(SOURCE,{'DFF_X1'});again,n=self.subset(data,{'DFF_X1'})
        self.assertEqual(again,data);self.assertEqual(n['selected_cells']['DFF_X1']['sha256'],m['selected_cells']['DFF_X1']['sha256'])
    def test_real_link_cannot_drop_a_discovered_cell_or_add_a_model(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('library_acceptance',ROOT/'acceptance/verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        alias={'ports':{'A':{'direction':'input','bits':[2]},'Z':{'direction':'output','bits':[2]}},'cells':{}}
        m.require_model_closure({'BUF_X1'},{'BUF_X1'},{'BUF_X1':alias})
        for discovered,used,models in [({'BUF_X1','MISSING'},{'BUF_X1'},{'BUF_X1':alias}),({'BUF_X1'},{'BUF_X1'},{'BUF_X1':alias,'EXTRA':alias}),({'BUF_X1'},{'BUF_X1'}, {})]:
            with self.assertRaises(ValueError):m.require_model_closure(discovered,used,models)
    def test_closed_model_set_still_rejects_blackbox(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('library_acceptance',ROOT/'acceptance/verify.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with self.assertRaises(ValueError):m.require_model_closure({'A'},{'A'},{'A':{'attributes':{'blackbox':'1'}}})
    def test_all_cells_selected_is_exact_identity(self):
        data,m=self.subset(SOURCE,{'DFF_X1','UNUSED'});self.assertEqual(data,SOURCE)

if __name__=='__main__':unittest.main()
