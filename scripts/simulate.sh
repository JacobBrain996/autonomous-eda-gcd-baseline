#!/usr/bin/env bash
set -euo pipefail
mkdir -p evidence/raw-logs evidence/status
rc=0
started="$(date +%s)"
{
  iverilog -g2012 -s tb_gcd -o evidence/tb_gcd.vvp orfs/flow/designs/src/gcd/gcd.v tests/tb_gcd.sv &&
  timeout 180 vvp evidence/tb_gcd.vvp
} > evidence/raw-logs/rtl-simulation.log 2>&1 || rc=$?
if [ "$rc" -eq 0 ] && ! grep -Fq 'TESTED_PASS cases=76 seed=5eda0001' evidence/raw-logs/rtl-simulation.log; then rc=1; fi
printf '%s\n' "$rc" > evidence/status/simulation-return-code.txt
printf '%s\n' "$(( $(date +%s) - started ))" > evidence/status/simulation-runtime-seconds.txt
cat evidence/raw-logs/rtl-simulation.log
# Final gate enforces the captured status, independent of physical diagnostics.
