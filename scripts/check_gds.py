import pya
layout = pya.Layout()
layout.read("/layout/6_final.gds")
assert any(cell.name == "gcd" for cell in layout.top_cells()), "gcd top cell missing"
assert not layout.cell("gcd").bbox().empty(), "gcd layout is empty"
print("GDS_READ_GATE=PASS")
