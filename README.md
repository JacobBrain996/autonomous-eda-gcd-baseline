# autonomous-eda-gcd-baseline

Public experiment package for frozen ORFS GCD / Nangate45 RTL-to-GDS.
No private research inputs, credentials, or host environment snapshots are included.

## Frozen experiment
- ORFS commit: `3a964e13f11a4e435aac01ffa14db0a7d2853720`
- ORFS image: `openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9`
- Design / platform: `gcd / nangate45`
- Source RTL SHA-256: `5009f224876d39e5e77e59ee1528cb0d2a03697251f0971b77cf3e8b0426dd3e`
- Testbench SHA-256: `3ecf0e4e9b840d1185feae9e5c6a87c68d34702b7208c82d52c2408eac5c892f`

The package contains the actual testbench. It checks 76 deterministic cases, a
modulo reference model, ready/valid transactions, and response backpressure.
A SHA declaration alone is never accepted: the workflow verifies actual bytes.

## Manual execution
The workflow must be on the repository's default branch. Only
`workflow_dispatch` is enabled. This package requires a **public** repository
and standard `ubuntu-24.04` runner.

The workflow installs Ubuntu 24.04 Icarus package `12.0-2build2` on the temporary
runner, independently of the frozen ORFS container. It probes `iverilog` and
`vvp`, records versions, compiles and runs the testbench with a 180-second
timeout. Package unavailability stops the job; no substitute is selected.

Before container pull: x86_64, RAM total >=14 GiB, RAM available >=6 GiB,
workspace and Docker filesystem free >=10 GiB. After pull: available RAM >=6 GiB
and both filesystems free >=4 GiB. The disk thresholds are guardrails for this
small GCD workload, not proof of image expansion or peak runtime requirements.
Resource failures stop before physical flow; no runner cleanup is performed.

Container core probes use absolute Yosys/OpenROAD/KLayout paths derived from
the frozen upstream docker_shell. Their runtime availability is checked in the
job. Optional frontend plugins are not unconditional core tool probes.
No design configuration, RTL, SDC or PDK is changed.

## Independent gates
- `RTL_SIMULATION_GATE`: compile/run return code and explicit 76-case completion marker.
- `PHYSICAL_FLOW_GATE`: make return code, measured routing DRC=0. Missing DRC remains NOT_AVAILABLE.
- `TIMING_GATE`: numeric final setup/hold worst slack and TNS, all >=0.
- `ARTIFACT_GATE`: matching source/image provenance, core tools, nonempty final ODB/GDS,
  successful KLayout GDS read with gcd top, and required WNS/TNS/area/DRC measurements.

Missing measurements are `null / NOT_AVAILABLE`. Setup WNS is
`min(0, worst_setup_slack)`, not unmodified positive worst slack.
Timing coverage, corners and constraints still require downloaded-artifact review;
these gates do not constitute foundry signoff or a reproducibility claim.

Collector uses exact `logs/nangate45/gcd/base/6_report.json` for final metrics,
and only this variant's JSON logs for DRC. Conflicting measurements are rejected.
Raw logs are scanned for SIGILL/illegal-instruction even when make wraps the
failure as exit 2. Never interpret that signature as an RTL error.

## Evidence
Every job, including failures, attempts an artifact upload using `always()`.
Evidence includes source/image manifest, tool versions, raw logs, metrics,
runtime, four gates, failures, GDS, per-file sizes, and SHA256SUMS.
After download run `sha256sum -c SHA256SUMS.txt` from the extracted evidence
directory. Paths containing spaces are handled correctly; checksum file excludes
itself. file-sizes.json excludes itself and SHA256SUMS to avoid self-reference.

Artifact-upload success is also mandatory for overall job success.
A successful job remains pending artifact audit before baseline Run 1 acceptance.
Run 2 must be a new independent workflow run. No files persist between jobs.

Local syntax checks are not cloud execution. Current state: CLOUD_BASELINE_RUN1=NOT_RUN.
