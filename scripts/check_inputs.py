import argparse
import hashlib
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--testbench-only", action="store_true")
p.add_argument("--rtl", type=Path)
args = p.parse_args()
identity = json.loads(Path("experiment_identity.json").read_text())
tb = Path("tests/tb_gcd.sv").read_bytes()
assert hashlib.sha256(tb).hexdigest() == identity["testbench_sha256"], "testbench SHA256 mismatch"
ports = {"clk": ("input", 1), "reset": ("input", 1), "req_msg": ("input", 32),
         "req_val": ("input", 1), "req_rdy": ("output", 1), "resp_msg": ("output", 16),
         "resp_rdy": ("input", 1), "resp_val": ("output", 1)}
if args.rtl:
    raw = args.rtl.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == identity["rtl_sha256"], "frozen RTL SHA256 mismatch"
    header = re.search(r"module\s+gcd\s*\((.*?)\);", raw.decode(), re.S).group(1)
    actual = {}
    for direction, msb, lsb, name in re.findall(
            r"(input|output)\s+wire\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*(\w+)", header):
        actual[name] = (direction, int(msb) - int(lsb) + 1 if msb else 1)
    assert actual == ports, f"RTL interface mismatch: {actual}"
    connections = set(re.findall(r"\.(\w+)\(", re.search(r"gcd\s+dut\((.*?)\);", tb.decode(), re.S).group(1)))
    assert connections == set(ports), "testbench DUT connection mismatch"
    for name, (_, width) in ports.items():
        declaration = re.search(r"(?:reg|wire)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s+" + name + r"\b", tb.decode())
        assert declaration, f"testbench signal missing: {name}"
        declared_width = int(declaration[1]) - int(declaration[2]) + 1 if declaration[1] else 1
        assert declared_width == width, f"testbench width mismatch: {name}"
print("TESTBENCH_HASH_AND_INTERFACE=PASS" if args.rtl else "TESTBENCH_HASH=PASS")
