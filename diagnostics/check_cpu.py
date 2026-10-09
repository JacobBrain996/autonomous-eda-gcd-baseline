"""Classify one trusted runner into one ISA diagnostic arm; never prove AVX-512 causality."""
import json
import os
from pathlib import Path
import re
import zipfile

def fields(text):
    def value(label):
        match=re.search(r"^"+re.escape(label)+r":[ \t]*([^\r\n]*)$",text,re.M)
        return match[1].strip() if match else ""
    return value("Architecture"),value("Model name"),set(value("Flags").split())

def analyze(original,current):
    oa,om,of=fields(original);ca,cm,cf=fields(current)
    reasons=[]
    if oa!="x86_64" or ca!="x86_64":reasons.append("missing_or_unsupported_architecture")
    if not om or not cm:reasons.append("missing_cpu_model")
    if not {"avx","avx2","xsave"}.issubset(of) or not {"avx","avx2","xsave"}.issubset(cf):
        reasons.append("missing_required_exposed_isa")
    if any(f.startswith("avx512") for f in cf) and "avx512f" not in cf:
        reasons.append("inconsistent_avx512_metadata")
    arm="HOLD" if reasons else ("WITH_AVX512" if "avx512f" in cf else "NO_AVX512")
    subset=lambda flags:sorted(f for f in flags if f.startswith(("avx","sse")) or f in ("fma","xsave","xsaveopt"))
    return {"diagnostic_id":"D1B_CPU_GROUPED_LEC_REPLAY","diagnostic_arm":arm,
        "original_cpu_architecture":oa,"current_cpu_architecture":ca,
        "original_cpu_model":om,"current_cpu_model":cm,"model_matches":bool(om and om==cm),
        "original_effective_isa":sorted(of),"current_effective_isa":sorted(cf),
        "isa_flags_added":sorted(cf-of),"isa_flags_removed":sorted(of-cf),
        "original_vector_flags":subset(of),"current_vector_flags":subset(cf),
        "identical_execution_environment":False,
        "environment_claim":"ISA_CLASS_DIAGNOSTIC_ONLY_NOT_IDENTICAL_EXECUTION_ENVIRONMENT",
        "arm_role":"original_isa_class_reproduction_candidate" if arm=="NO_AVX512" else
                   "cross_isa_control" if arm=="WITH_AVX512" else "ineligible",
        "ISA_DIAGNOSTIC_GATE":"HOLD_CPU_METADATA_OR_REQUIREMENTS" if reasons else "PASS_GROUPED_DIAGNOSTIC",
        "hold_reasons":reasons,"AVX512_HYPOTHESIS":"UNPROVEN_HOLD"}

def execution_context(environment):
    keys=("GITHUB_REPOSITORY","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_SHA","RUNNER_OS","RUNNER_ARCH","D1B_RUNNER_ENVIRONMENT")
    context={key:environment.get(key,"NOT_AVAILABLE") for key in keys}
    trusted=(context["GITHUB_REPOSITORY"]=="JacobBrain996/autonomous-eda-gcd-baseline"
        and environment.get("GITHUB_REPOSITORY_VISIBILITY")=="public"
        and context["RUNNER_OS"]=="Linux" and context["RUNNER_ARCH"]=="X64"
        and context["D1B_RUNNER_ENVIRONMENT"]=="github-hosted"
        and context["GITHUB_RUN_ID"].isdigit() and context["GITHUB_RUN_ATTEMPT"].isdigit()
        and re.fullmatch(r"[0-9a-f]{40}",context["GITHUB_SHA"]) is not None
        and environment.get("DIAGNOSTIC_ID")=="D1B_CPU_GROUPED_LEC_REPLAY")
    return context,trusted

if __name__=="__main__":
    root=Path("evidence/cts-lec-diagnostic")
    with zipfile.ZipFile(root/"run1.zip") as z:
        result=analyze(z.read("environment/lscpu.txt").decode(),Path("evidence/environment/lscpu.txt").read_text())
    context,trusted=execution_context(os.environ)
    result["github_execution_identity"]=context
    result["runner_label"]="ubuntu-24.04"
    if not trusted:
        result["ISA_DIAGNOSTIC_GATE"]="HOLD_ENVIRONMENT_UNTRUSTED"
        result["hold_reasons"].append("untrusted_repository_visibility_runner_or_diagnostic_id")
    (root/"cpu-comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    assert result["ISA_DIAGNOSTIC_GATE"].startswith("PASS"),"HOLD: CPU requirements or trusted execution identity failed; no retry"
