#!/usr/bin/env bash
set -euo pipefail
started="$(date +%s)"
rc=0
docker run --rm --network none --entrypoint bash \
  --user "$(id -u):$(id -g)" \
  -v "$GITHUB_WORKSPACE/orfs/flow:/OpenROAD-flow-scripts/flow" \
  "$ORFS_IMAGE" -lc '
    set -eo pipefail
    source /OpenROAD-flow-scripts/env.sh
    set -u
    cd /OpenROAD-flow-scripts/flow
    make DESIGN_CONFIG=./designs/nangate45/gcd/config.mk
  ' > evidence/raw-logs/orfs-gcd-baseline.log 2>&1 || rc=$?
printf '%s\n' "$rc" > evidence/status/physical-return-code.txt
printf '%s\n' "$(( $(date +%s) - started ))" > evidence/status/physical-runtime-seconds.txt
if [ "$rc" -ne 0 ]; then cp evidence/raw-logs/orfs-gcd-baseline.log evidence/failure/physical.log; fi
if [ "$rc" -eq 0 ] && [ -s orfs/flow/results/nangate45/gcd/base/6_final.gds ]; then
  verify_rc=0
  docker run --rm --network none --entrypoint /usr/bin/klayout \
    --user "$(id -u):$(id -g)" \
    -v "$GITHUB_WORKSPACE/orfs/flow/results/nangate45/gcd/base:/layout:ro" \
    -v "$GITHUB_WORKSPACE/scripts:/audit:ro" \
    "$ORFS_IMAGE" -b -r /audit/check_gds.py > evidence/raw-logs/gds-read.log 2>&1 || verify_rc=$?
  printf '%s\n' "$verify_rc" > evidence/status/gds-read-return-code.txt
fi
