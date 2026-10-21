#!/usr/bin/env bash
set -euo pipefail
mkdir -p /work/sta /work/formal
python3 /audit/verify.py identity
snapshot_rc=0
python3 /audit/verify.py snapshots || snapshot_rc=$?
sta_rc=0
timeout --kill-after=5 60 /OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad \
  -no_init -exit /audit/sta.tcl > /work/sta/tool.log 2>&1 || sta_rc=$?
if [ "$sta_rc" -eq 0 ]; then
  python3 /audit/verify.py sta-reports || sta_rc=$?
fi
if [ "$sta_rc" -eq 0 ]; then
  python3 /audit/verify.py sta-results || sta_rc=$?
fi
formal_rc=0
python3 /audit/verify.py formal || formal_rc=$?
python3 - "$formal_rc" "$sta_rc" "$snapshot_rc" <<'PY'
import json,sys,pathlib
p=pathlib.Path('/work')
formal=json.loads((p/'formal/result.json').read_text()) if (p/'formal/result.json').exists() else {'FORMAL_EQUIVALENCE_GATE':'UNKNOWN_HOLD'}
result={'formal_return_code':int(sys.argv[1]),'sta_return_code':int(sys.argv[2]),'snapshot_return_code':int(sys.argv[3]),
    'CONSTRAINT_SNAPSHOT_GATE':'PASS' if sys.argv[3]=='0' else 'UNKNOWN_HOLD',
    'CONSTRAINT_EQUIVALENCE_GATE':'UNKNOWN',
    'FORMAL_EQUIVALENCE_GATE':formal['FORMAL_EQUIVALENCE_GATE'],
    'STA_EXTRACTION_GATE':'PASS' if sys.argv[2]=='0' else 'UNKNOWN_HOLD',
    'TIMING_GATE':'FAIL' if sys.argv[2]=='0' else 'NOT_AVAILABLE',
    'proof_scope':'all outputs after two common reset edges; arbitrary future defined inputs',
    'baseline_pass':False}
(p/'result.json').write_text(json.dumps(result,indent=2)+'\n')
PY
test "$formal_rc" -eq 0
test "$sta_rc" -eq 0
test "$snapshot_rc" -eq 0
