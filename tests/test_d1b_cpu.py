import importlib.util
from pathlib import Path
import unittest
import zipfile

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("cpu",root/"diagnostics/check_cpu.py")
cpu=importlib.util.module_from_spec(spec);spec.loader.exec_module(cpu)
ORIGINAL="Architecture: x86_64\nModel name: AMD EPYC 7763\nFlags: sse sse2 avx avx2 xsave fma\n"

class CPUDiagnosticArmTests(unittest.TestCase):
    def test_no_avx512_is_not_identical_environment(self):
        changed=ORIGINAL.replace("AMD EPYC 7763","OTHER AVX2 CPU")
        result=cpu.analyze(ORIGINAL,changed)
        self.assertEqual(result["diagnostic_arm"],"NO_AVX512")
        self.assertTrue(result["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))
        self.assertFalse(result["model_matches"])
        self.assertFalse(result["identical_execution_environment"])
    def test_with_avx512_is_control_not_proof(self):
        changed=ORIGINAL.replace("AMD EPYC 7763","Intel Xeon 8370C").replace("fma","fma avx512f avx512vl")
        result=cpu.analyze(ORIGINAL,changed)
        self.assertEqual(result["diagnostic_arm"],"WITH_AVX512")
        self.assertTrue(result["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))
        self.assertEqual(result["AVX512_HYPOTHESIS"],"UNPROVEN_HOLD")
        self.assertIn("avx512vl",result["current_effective_isa"])
    def test_missing_model_flags_arch_holds(self):
        for value in ["", ORIGINAL.replace("Flags:","Other:"),ORIGINAL.replace("x86_64","aarch64"),
                      ORIGINAL.replace("Model name: AMD EPYC 7763","Model name:")]:
            self.assertEqual(cpu.analyze(ORIGINAL,value)["diagnostic_arm"],"HOLD")
    def test_missing_requirements_or_inconsistent_avx512_holds(self):
        for value in [ORIGINAL.replace("avx2",""),ORIGINAL.replace("xsave",""),
                      ORIGINAL.replace("fma","fma avx512vl")]:
            self.assertFalse(cpu.analyze(ORIGINAL,value)["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))
    def test_complete_flags_preserved(self):
        result=cpu.analyze(ORIGINAL,ORIGINAL.replace("fma","fma bmi2 clflushopt"))
        self.assertIn("clflushopt",result["current_effective_isa"])
        self.assertIn("bmi2",result["current_effective_isa"])
        self.assertFalse(result["identical_execution_environment"])
    def test_actual_d1_grouped_as_control(self):
        with zipfile.ZipFile("E:/AUTONOMOUS_EDA_V1/workspace/autonomous-eda-gcd-baseline/evidence/run1/orfs-gcd-baseline-run1.zip") as z:
            old=z.read("environment/lscpu.txt").decode()
        with zipfile.ZipFile("E:/AUTONOMOUS_EDA_V1/workspace/autonomous-eda-gcd-baseline/evidence/d1-37795979593/D1-37795979593.zip") as z:
            current=z.read("environment/lscpu.txt").decode()
        result=cpu.analyze(old,current)
        self.assertEqual(result["diagnostic_arm"],"WITH_AVX512")
        self.assertFalse(result["model_matches"])
        self.assertTrue(result["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))

    def test_untrusted_or_incomplete_context_holds(self):
        good={"GITHUB_REPOSITORY":"JacobBrain996/autonomous-eda-gcd-baseline",
              "GITHUB_REPOSITORY_VISIBILITY":"public","RUNNER_OS":"Linux","RUNNER_ARCH":"X64",
              "D1B_RUNNER_ENVIRONMENT":"github-hosted",
              "DIAGNOSTIC_ID":"D1B_CPU_GROUPED_LEC_REPLAY","GITHUB_RUN_ID":"123",
              "GITHUB_RUN_ATTEMPT":"1","GITHUB_SHA":"f"*40,"GH_TOKEN":"MUST_NOT_EXPORT"}
        context,trusted=cpu.execution_context(good)
        self.assertTrue(trusted);self.assertNotIn("GH_TOKEN",context)
        for key,value in [("GITHUB_REPOSITORY_VISIBILITY","private"),("RUNNER_ARCH","ARM64"),
                          ("GITHUB_RUN_ID",""),("GITHUB_SHA","missing"),("DIAGNOSTIC_ID","D1"),
                          ("D1B_RUNNER_ENVIRONMENT","self-hosted")]:
            bad=dict(good);bad[key]=value
            self.assertFalse(cpu.execution_context(bad)[1])

if __name__=="__main__":unittest.main(verbosity=2)
