#!/usr/bin/env bash
set -euo pipefail
# Runs only after explicit workflow_dispatch approval; no local Docker execution in preparation.
mkdir -p evidence/cts-lec-diagnostic/run1-inputs evidence/cts-lec-diagnostic/output
python3 diagnostics/prepare.py restore evidence/cts-lec-diagnostic/run1.zip evidence/cts-lec-diagnostic/run1-inputs
set +e
docker run --rm --network none --read-only --cpus=2 --memory=6g --pids-limit=128 \
  --ulimit core=0 --ulimit fsize=8388608 \
  --user "$(id -u):$(id -g)" \
  --tmpfs /tmp:rw,size=67108864,mode=1777 \
  --tmpfs /diagnostic-work:rw,size=134217728,mode=1777 \
  -v "$GITHUB_WORKSPACE/orfs/flow:/OpenROAD-flow-scripts/flow:ro" \
  -v "$GITHUB_WORKSPACE/diagnostics:/diagnostic:ro" \
  -v "$GITHUB_WORKSPACE/evidence/cts-lec-diagnostic/run1-inputs:/run1-inputs:ro" \
  -v "$GITHUB_WORKSPACE/evidence/cts-lec-diagnostic/output:/diagnostic-out" \
  --entrypoint bash "$ORFS_IMAGE" -lc '
    set -eo pipefail
    source /OpenROAD-flow-scripts/env.sh
    set -u
    finish() {
      original_rc=$?
      set +e
      python3 /diagnostic/prepare.py export
      export_rc=$?
      printf "original_rc=%s export_rc=%s\n" "$original_rc" "$export_rc" > /diagnostic-out/export-status.txt
      if [ "$original_rc" -eq 0 ] && [ "$export_rc" -ne 0 ]; then exit 125; fi
      exit "$original_rc"
    }
    trap finish EXIT
    cd /OpenROAD-flow-scripts/flow
    make -f Makefile -f /diagnostic/effective.mk \
      DESIGN_CONFIG=./designs/nangate45/gcd/config.mk diagnostic-effective-vars
    python3 /diagnostic/prepare.py driver
  ' 2>&1 | python3 diagnostics/cap_stream.py evidence/cts-lec-diagnostic/container.log
statuses=("${PIPESTATUS[@]}")
set -e
rc="${statuses[0]}"
if [ "$rc" -eq 0 ] && [ "${statuses[1]}" -ne 0 ]; then rc=125; fi
printf '%s\n' "$rc" > evidence/cts-lec-diagnostic/container-return-code.txt
# Failure status is preserved by the workflow after uploading evidence.
exit "$rc"
