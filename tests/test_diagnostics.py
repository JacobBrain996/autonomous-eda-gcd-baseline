import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tkinter
import unittest
import os

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observer", ROOT / "diagnostics/observe.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

class DiagnosticTests(unittest.TestCase):
    def test_exit_and_separate_streams(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as d:
            rc = observer.observe([sys.executable, "-c",
                "import sys; print('PUBLIC_STDOUT'); print('PUBLIC_STDERR',file=sys.stderr); sys.exit(7)"],
                Path(d), limit=1024, seconds=10, tracing=False, forward=False)
            self.assertEqual(rc, 7)
            self.assertIn("PUBLIC_STDOUT", (Path(d)/"formal.stdout").read_text())
            self.assertIn("PUBLIC_STDERR", (Path(d)/"formal.stderr").read_text())
            record=json.loads((Path(d)/"process.json").read_text())
            self.assertEqual(record["actual_returncode"], 7)
            self.assertGreater(record["pid"], 0)
            self.assertNotIn("environment", record)
            self.assertEqual(record["AVX512_HYPOTHESIS"], "UNPROVEN_HOLD")

    def test_limit_drain_no_deadlock(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as d:
            rc=observer.observe([sys.executable,"-c",
                "import sys; sys.stdout.write('x'*100000); sys.stderr.write('y'*100000)"],
                Path(d), limit=64, seconds=10, tracing=False, forward=False)
            self.assertEqual(rc,0)
            self.assertEqual((Path(d)/"formal.stdout").stat().st_size,64)
            self.assertEqual((Path(d)/"formal.stderr").stat().st_size,64)
            self.assertTrue(json.loads((Path(d)/"process.json").read_text())["truncated"])

    def test_timeout_not_pass(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as d:
            self.assertEqual(observer.observe([sys.executable,"-c","import time; time.sleep(5)"],
                Path(d),limit=64,seconds=.15,tracing=False,forward=False),124)

    def test_signal_mapping(self):
        self.assertEqual(observer.signal_name(-4),"SIGILL")
        self.assertIsNone(observer.signal_name(2))

    def test_console_limit(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tests") as d:
            dest=Path(d)/"container.log"
            p=subprocess.run([sys.executable,str(ROOT/"diagnostics/cap_stream.py"),str(dest)],
                input=b"x"*(9*1024*1024),capture_output=True)
            self.assertEqual(p.returncode,0)
            self.assertEqual(dest.stat().st_size,8*1024*1024)
            self.assertTrue(json.loads(dest.with_suffix(".size.json").read_text())["truncated"])

    def test_cpu_isa_gate(self):
        sys.path.insert(0,str(ROOT/"diagnostics"))
        import check_cpu
        base="Architecture: x86_64\nModel name: AMD EPYC 7763\nFlags: avx avx2 fma xsave\n"
        self.assertTrue(check_cpu.analyze(base,base)["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))
        changed=base.replace("xsave","xsave avx512f")
        self.assertTrue(check_cpu.analyze(base,changed)["ISA_DIAGNOSTIC_GATE"].startswith("PASS"))
        self.assertEqual(check_cpu.analyze(base,changed)["diagnostic_arm"],"WITH_AVX512")

    def test_artifact_budget(self):
        sys.path.insert(0,str(ROOT/"diagnostics"))
        import seal
        with tempfile.TemporaryDirectory(dir=ROOT/"tests") as d:
            root=Path(d);p=root/"public.log";p.write_bytes(b"x"*32)
            self.assertTrue(seal.inventory([p],root,single=64,total=64)["within_limits"])
            self.assertFalse(seal.inventory([p],root,single=16,total=64)["within_limits"])
            self.assertFalse(seal.inventory([p],root,single=64,total=16)["within_limits"])

    def test_restore_identity_and_reject_wrong_zip(self):
        sys.path.insert(0,str(ROOT/"diagnostics"))
        import prepare
        with tempfile.TemporaryDirectory(dir=ROOT/"tests") as d:
            archive=Path("E:/AUTONOMOUS_EDA_V1/workspace/autonomous-eda-gcd-baseline/evidence/run1/orfs-gcd-baseline-run1.zip")
            prepare.restore(archive,Path(d)/"results")
            for name,h in prepare.INPUTS.items():
                self.assertEqual(observer.sha(Path(d)/"results"/name),h)
            wrong=Path(d)/"wrong.zip";wrong.write_bytes(b"not the approved archive")
            with self.assertRaises(AssertionError):prepare.restore(wrong,Path(d)/"rejected")

    def test_tcl_success_passthrough(self):
        t=tkinter.Tcl();t.eval('rename ::exec ::native_exec')
        t.eval('proc ::exec {args} {return {PUBLIC_RESULT}}')
        t.setvar("env(KEPLER_FORMAL_EXE)","mock-kepler")
        t.setvar("env(DIAG_TEST_NO_LAUNCHER)","1")
        t.eval("source {%s}" % (ROOT/"diagnostics/exec_hook.tcl").as_posix())
        self.assertEqual(t.eval('exec mock-kepler --config public.yml'),"PUBLIC_RESULT")

    def test_lec_grep_signal_is_not_misattributed(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tests") as d:
            t=tkinter.Tcl();t.eval('rename ::exec ::native_exec')
            t.eval('proc ::exec {args} {return -code error -errorcode {CHILDKILLED 456 SIGILL {illegal instruction}} {child killed: illegal instruction}}')
            t.setvar("env(DIAG_DIR)",Path(d).as_posix())
            t.setvar("env(KEPLER_FORMAL_EXE)","mock-kepler")
            t.eval("source {%s}" % (ROOT/"diagnostics/exec_hook.tcl").as_posix())
            self.assertEqual(t.eval('catch {exec grep -c {Found difference} /public/4_rsz_lec_check.log} r o'),"1")
            text=(Path(d)/"tcl-exec-error.txt").read_text()
            self.assertIn("original_argv {grep",text)
            self.assertIn("CHILDKILLED 456 SIGILL",text)

    @unittest.skipUnless(os.name=="posix","Linux signal integration is not executed on Windows")
    def test_native_child_sigill(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tests") as d:
            rc=observer.observe([sys.executable,"-c","import os,signal; os.kill(os.getpid(),signal.SIGILL)"],
                Path(d),seconds=10,tracing=False,forward=False)
            self.assertEqual(rc,-4)

    def test_tcl_errors_propagate(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as d:
            t=tkinter.Tcl()
            t.eval("rename ::exec ::native_exec")
            t.eval('proc ::exec {args} {return -code error -errorcode {CHILDKILLED 123 SIGILL {illegal instruction}} {child killed: illegal instruction}}')
            t.setvar("env(DIAG_DIR)",Path(d).as_posix())
            t.setvar("env(DIAG_TEST_NO_LAUNCHER)","1")
            t.setvar("env(KEPLER_FORMAL_EXE)","mock-kepler")
            t.eval("source {%s}" % (ROOT/"diagnostics/exec_hook.tcl").as_posix())
            code=t.eval('catch {exec mock-kepler --config public.yml} r o')
            self.assertEqual(code,"1")
            self.assertEqual(t.eval('dict get $o -errorcode'),"CHILDKILLED 123 SIGILL {illegal instruction}")
            self.assertEqual(t.eval('set r'),"child killed: illegal instruction")
            self.assertIn("SIGILL",(Path(d)/"tcl-exec-error.txt").read_text())
            # Unrelated exec is not redirected or silently made successful.
            self.assertEqual(t.eval('catch {exec other-tool} r o'),"1")

if __name__=="__main__":
    unittest.main(verbosity=2)
