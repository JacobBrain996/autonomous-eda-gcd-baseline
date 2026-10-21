# Reviewed synthesis proof and one candidate physical comparison

Local preparation only. No new push, workflow dispatch, paid service or EDA run.
The long-term VeriEDA Goal remains active; this candidate's external operation
is WAITING_FOR_AUTHORIZATION, not a project-wide blocker.

## Formal conclusion from existing Run 39617534483

PASS_RESET_CONTRACT_UNBOUNDED for the exact synthesis target cacc9a646866…4785,
under contracts/gcd.reset2.json. Gold is the original RTL, gate is the new speed
mapping, all 18 output bits are checked after two common synchronous reset edges.
Future defined inputs/reset remain arbitrary. Arbitrary defined initial design
state is not replaced by all-zero state. All 44 used cell types have functional
models. The auxiliary FSM relation is proved with the original mismatch property,
not assumed. Base and temporal induction succeed at length 2; this is not BMC.

cases/gcd-speed.formal-review.json binds the exact subject, artifact, contract,
engine, public run and reviewed recipes/logs. The software requires both that
registered review and a passing structural scope check before reporting scoped
Formal PASS. This trusts frozen Yosys/SAT and the audited GitHub execution; no
independent SAT certificate or hardware attestation is claimed. The original raw
report/archives remain unchanged. No proof covers a later final netlist.

## Runnable preparation

The existing `python -m verieda review-candidate` interface now recognizes this
specific proof and reports READY_FOR_PHYSICAL with sufficient physical budget;
without checked scope inputs it remains PROOF_REVIEW_PENDING. The physical native
adapter is `python -m verieda execute-physical`; omit --execute for a read-only
admission check. Its required arguments are --package (fresh action package),
--verification-package (original synthesis verification package), --reviewed-proof,
--frozen-root and --work. Real execution additionally requires --image-identity,
--execute and --approve-internal-lec-bypass, plus separate human authorization.
The new workflow supplies these paths/mounts explicitly.

The saved synthesis artifact lacks required 1_synth.sdc / canonicalized synthesis
intermediates. The frozen Makefile (SHA256 1ca0d6a0…97) makes those prerequisites
of floorplan. Reconstruct synthesis in a fresh WORK_HOME with ABC_AREA=0, require
its netlist SHA256 to equal the already proved target before and after Make all,
and then reuse those intermediates. Hash mismatch stops; no new target is silently
substituted. The rebuilt synthesis ODB is recorded, not claimed bit-identical.

The physical segment explicitly uses LEC_CHECK=0 / SEC_CHECK=0, matching the
engineering Smoke reference and avoiding the known failing internal process
chain. The workflow requires approve_internal_lec_bypass=true (default false).
This is a proposed, separately approved engineering bypass; it is neither a
permanent policy change nor Formal PASS. A separate read-only mount of the actual
final netlist creates a new FORMAL_FINAL task and runs the existing independent
Yosys adapter. Final proof remains review-required; the synthesis proof cannot
unlock final acceptance.

The one proposed workflow is .github/workflows/verieda_candidate_physical.yml.
It preserves ORFS 3a964e13f11a4e435aac01ffa14db0a7d2853720, OCI digest
sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9,
GCD/Nangate45 and original 0.25 ns SDC (952a1a0a…6582). No timing relaxation,
RTL change, physical ECO or Kepler diagnosis is included.

## Measurements and decisions

Collect final netlist/ODB/SDC/GDS, raw stage logs/reports, routing DRC, stdcell area,
setup WNS/TNS, hold slack, independent parasitic STA max/min reports, top paths,
violating paths and native evaluated constraint snapshots. The metrics observer
cross-checks finish versus independent native STA with explicit 1 ns units;
missing, ambiguous or inconsistent values stop interpretation. GDS is reopened
in the frozen image. Missing reports never become zero violations.

`evaluate` now reports before/after/delta WNS, TNS, area and hold, and separates
acceptable optimization, improvement with violations, regression, functional or
physical failure, verification insufficiency and budget stop. Native runtime
budget excludes setup/billing, and a budget stop preserves the observed QoR
classification. It never authorizes execution or changes the frozen constraints.
Full adoption still requires independent final proof, constraint/coverage review,
all physical gates, nonnegative setup/hold, real WNS improvement and <=10% area
increase. A single before/after pair does not establish statistical causality.

Full native constraint equivalence remains UNKNOWN: frozen input identity and
literal I/O coverage alone do not certify all propagated-clock/latency semantics.
Recovery must audit the new artifact and normalize its real measurements before
constructing an after-state; this workflow is not yet a demonstrated automatic
acceptance loop. Execution remains registered for GCD/Nangate45 only; shared path,
subject, comparison and decision interfaces are reusable, cross-RTL support unproved.

## Budget, stopping conditions and offline evidence

Proposed authorization: one public-repository standard ubuntu-24.04 job <=20 min,
no self-hosted/larger runner, paid service, retry or second experiment. Physical
container wall cap 560 s (synthesis <=60, flow <=300, STA <=90, snapshots <=40,
GDS read <=30 plus admission); final Formal <=300 s, container wall cap 330 s.
Old physical Smoke took 68 s, old candidate Formal about 2 s; these are historical
observations, not future guarantees. Expected information: actual timing/area
tradeoff and final functional validity of this candidate, including a rejection
if speed mapping regresses. No improvement is assumed. Exact monetary cost is
NOT_AVAILABLE; repository/resource/entitlement anomalies stop before execution.

Network is disabled in tool containers, environment is allowlisted, core dumps
are disabled, each tool output <=16 MiB, selected evidence <=128 MiB /1000 files,
and only public design/tool reports are uploaded. Input/artifact expiry, version
or hash mismatch, unsupported model/format, resource failure, timeout or nonzero
exit stops; preserve raw errors, no fallback or automatic retry. No new physical
result or candidate optimization success is claimed here.

Offline: 261 tests, 260 pass, 1 Linux integration skip; YAML/actionlint, all workflow
Bash blocks and embedded Python, Python AST, Tcl grouping, source package hashes
and git diff checks pass. Real frozen Linux/OpenROAD/hold/physical-to-final-Formal
integration remains NOT_RUN. Source pins grew to 65 files (bounded maximum 80);
no source pin was dropped. Immutable Run1, Smoke, synthesis and current proof ZIP
hashes were checked from actual files. Check details are retained in the local
scratch validation record (excluded from publication). No independent code-review
pass is claimed. The next external step needs fresh, explicit authorization.
