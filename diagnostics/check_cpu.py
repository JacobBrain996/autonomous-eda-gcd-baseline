"""Keep the diagnostic on a Run-1-like exposed ISA; never infer a fault opcode."""
import json
from pathlib import Path
import re
import zipfile

def analyze(original,current):
    def fields(text):
        model=re.search(r"^Model name:\s*(.*)$",text,re.M)
        flags=re.search(r"^Flags:\s*(.*)$",text,re.M)
        return model[1] if model else "NOT_AVAILABLE",set(flags[1].split()) if flags else set()
    om,of=fields(original);cm,cf=fields(current)
    subset=lambda flags: sorted(f for f in flags if f.startswith(("avx","sse")) or f in ("fma","xsave","xsaveopt"))
    valid="avx2" in cf and not any(f.startswith("avx512") for f in cf)
    return {"original_cpu_model":om,"current_cpu_model":cm,"model_matches":om==cm,
        "original_vector_flags":subset(of),"current_vector_flags":subset(cf),
        "ISA_DIAGNOSTIC_GATE":"PASS_EXPOSED_AVX2_NO_AVX512" if valid else "HOLD_CPU_CHANGED",
        "AVX512_HYPOTHESIS":"UNPROVEN_HOLD"}
if __name__=="__main__":
    root=Path("evidence/cts-lec-diagnostic")
    with zipfile.ZipFile(root/"run1.zip") as z:
        result=analyze(z.read("environment/lscpu.txt").decode(),Path("evidence/environment/lscpu.txt").read_text())
    (root/"cpu-comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    assert result["ISA_DIAGNOSTIC_GATE"].startswith("PASS"),"HOLD: exposed ISA differs; no automatic rerun"
