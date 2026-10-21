# VeriEDA — executable core and development checkpoint

## V0 software checkpoint — 2026-10-21 (supersedes historical status below)

### Isolated action adapter

#### Results and feedback

The same CLI recovers the action phase without executing EDA:

```powershell
python -m verieda seal-action --package PACKAGE_DIR --work SAVED_OUTPUT_DIR --output NEW_RESULT.zip
python -m verieda inspect-action NEW_RESULT.zip --expected-sha256 TRUSTED_ZIP_SHA256 --expected-candidate CANDIDATE_ID
python -m verieda advance-action --profile cases/gcd.json --smoke SMOKE.zip --acceptance ACCEPTANCE.zip --result NEW_RESULT.zip --expected-sha256 TRUSTED_ZIP_SHA256 --budget-seconds 600
```

The sealer copies only package state/candidate/manifest/effective.mk, action-execution.json or launcher-result.json, two fixed logs and the designated synthesis netlist/ODB. It never recursively exports the work directory. Other files, including unrelated private data, are excluded. Links/oversized files are rejected, payloads receive complete SHA256 and size coverage, and output ZIPs cannot overwrite an existing file. A package from an older recorded adapter can be sealed/observed without replacing its source identities with current code; this does not authorize executing old package code.

Inspection checks exact state/candidate binding, fixed Make argv, effective values, raw log/output hashes, frozen source/tool fingerprint claims, numerical runtime, exit code, timeout/signal consistency and required outputs. It retains PID/actual child exit when recorded, but does not infer a faulting executable from a shell/Make failure. Missing outputs, inconsistent claims, malformed receipts or a foreign identity stay UNKNOWN with no history record. NOT_RUN also produces no cost/history entry. Trusted archive SHA anchors archive bytes; source fingerprints and caller-supplied host records alone do not authenticate a cloud run. External run/commit/job binding remains a separate requirement.

`advance-action` reads the pinned ZIP itself; it cannot accept an agent-written observation as proof. It returns updated bounded history and budget, does not modify source/history files, and never executes a workflow. Save its `history` array for subsequent `--history FILE` use. Re-reading the same result is idempotent; conflicting records require HOLD. A completed synthesis creates an UNKNOWN adoption outcome and VERIFY_PENDING_CANDIDATE, with new-netlist Formal/physical/timing/constraint/adoption checks NOT_RUN. It does not reuse the old final-netlist proof for the new design. Failures enter STOP_REVIEW_FAILURE, exhausted budget STOP_BUDGET, unexecuted actions AWAIT_SEPARATE_EXECUTION_AUTHORIZATION. No implicit retry or budget expansion occurs.

Real EDA efficacy, authenticated remote receipt integration and full native action validation remain NOT_RUN. Successful/failed native process fixtures in tests are explicitly synthetic. The local end-to-end demonstration uses the actual default NOT_RUN response, not a fabricated successful EDA run.

The frozen GCD config explicitly sets ABC_AREA=1; retained Smoke `1_2_yosys.log` confirms `Using ABC area script.`. The pinned synth preamble selects `abc_speed.script` when ABC_AREA=0. `verieda/action_support.json` records exact public source SHA256, frozen image and core binaries; source bytes were checked against GitHub's frozen-commit Git blob IDs. This establishes an actual parameter change, not a no-op or measured benefit.

After saving a selected candidate JSON from `plan`:

```powershell
python -m verieda prepare-action --profile cases/gcd.json --smoke evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip --acceptance evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip --candidate evidence/verieda-v0-20261021/candidate.json --output evidence/my-new-mapping-package
python -m verieda execute-action --help
```

Preparation is offline and exclusive: never overwrite an existing package. `execute-action` defaults to NOT_RUN. It supports only a fixed synthesis action in a separately authorized Linux x86_64 container, with a clean frozen Git checkout mounted read-only, matching source/tool hashes and fresh output outside source/package. `--execute` is a caller opt-in, not evidence of user/cloud authorization; it must not be set by an automatic goal continuation. The native work path must be an absolute POSIX path without whitespace/Make metacharacters. Use isolated WORK_HOME, FLOW_VARIANT=verieda, ABC_AREA=0, LEC_CHECK=1 and SEC_CHECK=1. Unknown effective values stop before synthesis. No RTL/SDC/ORFS edits, Make clean target, arbitrary target or inherited host environment is allowed.

Native execution additionally requires `--image-identity FILE`, an external host Docker record containing exactly image_id, repo_digests, os and architecture, matching the frozen OCI image/ID (linux/amd64). Do not export full docker inspect, process environment or credentials. Matching this caller-supplied record is not cryptographic attestation; the actual cloud runner must bind its host capture to the job.

Make's YOSYS_EXE/OPENROAD_EXE/PYTHON_EXE are explicitly pinned and included in the effective-value check; the executables cannot silently resolve to a second installation beneath the source checkout. Before Make starts, the adapter rejects tracked/untracked dirt and all ignored files beneath flow (including ignored settings.mk). A read-only mount alone would not prevent an existing settings.mk from being evaluated. This deliberately strict fresh-source policy may HOLD a checkout containing caches; prepare a clean source mount rather than deleting user files automatically.

Total synthesis action limit is 300 s, effective-variable check at most 20 s, child-produced file limit 16 MiB, core disabled. Timeout kills the child process group. Each actual tool return code, signal, argv, log hash, runtime and resulting synthesis-netlist hash is recorded in a fresh output action-execution.json. A zero Make rc without its expected netlist/speed mapping log remains HOLD. SYNTHESIS_COMPLETED is **not** PPA improvement, Formal PASS, GDS generation, or candidate acceptance; adoption requires a COMPLETED RTL_TO_GDS receipt plus independent gates. The old final-netlist proof cannot be reused to certify a newly mapped candidate.

Native Linux EDA/container integration is NOT_RUN. Windows/offline tests cover package generation/tampering, native guards and process API doubles for timeout/SIGILL. No new cloud workflow or actual EDA execution was performed. The full RTL→GDS/verification/recovery adapter and authenticated run/receipt ingestion remain work to do; this increment makes the first isolated action runnable after separate authorization, not a completed autonomous optimization loop.

The native acceptance Run 39544704950 at bbf5c1d proved final-netlist sequential equivalence for **two common synchronous reset edges followed by arbitrary defined inputs, all 18 output bits**. Timing still fails (WNS -0.1615832 ns, TNS -7.086462975 ns, 51 endpoints); full constraint coverage is UNKNOWN. These are independent engineering tasks, not prerequisites for software development. Historical checkpoints below remain an execution record, not current authority.

The V0 CLI now joins pinned Smoke/acceptance archives, proposes bounded candidates using an explainable rule policy, and evaluates candidate adoption separately:

```powershell
python -m verieda plan --profile cases/gcd.json --smoke evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip --acceptance evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip --budget-seconds 600
python -m verieda plan --help
python -m verieda evaluate --help
```

`cases/gcd.json` is an **external operator-reviewed trust profile**, not an agent-generated certificate. It pins archive/run/input identity and the previously reviewed proof files. Reusing that review does not rerun Formal or authenticate an arbitrary new run. Remove the review and Formal stays UNKNOWN with an unbounded-proof observation. Do not copy its review onto another candidate or treat profile checksum consistency as cryptographic attestation. All generated state/decision/candidate content is hash-bound; these hashes detect mutation, not a malicious operator rewriting a trust root.

`plan` emits JSON containing state and decision; save stdout if desired. Optional `--history FILE` accepts at most 100 caller-recorded outcomes with exactly `state_id`, `candidate_id`, `outcome` (FAIL/UNKNOWN/TIMEOUT/ERROR/REJECTED/ACCEPTED), and nonnegative `runtime_seconds`. It is a bounded local history, not GitHub billing or authorization. A consumed candidate is not retried automatically. A 600-second candidate cap requires 600 unspent seconds; anything less stops cloud proposal selection while offline constraint review remains available. Default budget is zero. No candidate, history field or CLI exit code authorizes execution.

The first action space contains a timing-oriented mapping hypothesis (`ABC_AREA=0`, only after verifying the existing value and frozen tool support) and a bounded critical-cell/buffering investigation. Cell/net delay determines ranking, not guaranteed causality or gain. These proposals have legality checks, immutable protected identities, rollback/preparation requirements and independent verifier requirements. Both remain `execution_ready=false`: application/remote adapters are not yet implemented. No EDA run, parameter edit or optimization gain is claimed. Missing constraint coverage does not block planning but does block acceptance.

`evaluate` loads before/after evidence with separate `--before-profile/--before-smoke/--before-acceptance` and `--after-profile/--after-smoke/--after-acceptance`, plus `--candidate FILE`. It refuses the same artifact/netlist as a new experiment. Acceptance requires unchanged frozen design/tools/original constraints, an artifact-bound `output/action-execution.json` receipt matching the candidate/base/changes and return code zero, same complete proof contract, all required gates, positive WNS improvement with no negative setup slack, and at most 10% area overhead. Missing receipt or coverage gives INCONCLUSIVE; contradictory evidence gives REJECTED. Current evidence cannot be accepted as a new optimization. The generic case adapter deliberately cannot certify full constraints or timing coverage from partial data, so genuinely ACCEPTED real candidates still need those verifier adapters. Synthetic acceptance tests are unit tests, not EDA efficacy evidence.

Exit 0 means the command completed, **not** design/candidate PASS. Inspect `decision`, `verdict`, `gates` and missing checks. Exit 2 means malformed/missing evidence/config. No dependencies, API keys, UI or LLM service are required. The rule policy is a reproducible control for future optimizer comparisons; novelty and autonomous optimization efficacy remain NOT_ESTABLISHED.

Design and task ledger: `docs/superpowers/specs/2026-10-21-verieda-v0.md`, `docs/superpowers/plans/2026-10-21-verieda-v0.md`. Remaining substantive work: executable isolated action adapter, trusted execution receipts, constraint/hold/physical coverage, real controlled improvement/adaptation, and more designs. The project Goal remains active.

VeriEDA targets an evidence-backed Design → Analyze → Reason → Optimize → Execute → Verify → Adapt loop. The research objective is active and is not complete. No novelty or successful autonomous optimization is claimed.

## Working software now

Python 3.10+ standard library only, no setup or EDA installation required. From this repository:

```powershell
python -m verieda inspect evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip --expect experiment_identity.json --expected-sha256 7dbdda5dd2e4d3edff841cda2bf2f7ab26099272d3bec4a0294a57e807001d84
python -m unittest discover -s tests -v
```

`inspect` accepts an existing ORFS collector ZIP or directory. It does not extract ZIPs, execute EDA, download artifacts, install software, or dispatch jobs. Exit zero means inspection ran, **not** that the design passed; consumers must use the structured `acceptance` and `gates` fields. Evidence-integrity failure exits 2.

State schema `verieda.state.v1` provides:
- Verified payload SHA256/size coverage, bounded reads, unsafe-path/link/duplicate rejection.
- External experiment identity matching and optional trusted archive SHA anchor. A self-generated checksum manifest alone establishes consistency, not authenticity.
- Raw final setup/hold slack/TNS, unique standard-cell area, router DRC and endpoint count, each with source file/key/unit/availability. Relevant duplicate JSON fields are ambiguous, not silently last-wins.
- Gate separation for evidence, identity, RTL simulation, physical execution, GDS generation/read, timing, routing DRC, formal and constraints.
- Distinct timing/design violations, tool signal, timeout exit code, unknown SIGKILL cause, execution failure, missing evidence and unverified formal claims.
- Saved critical paths with their actual printed precision and explicit incomplete endpoint/delay coverage; existing runtime observations.
- Review suggestions conditioned on observed state. These are not executable Agent actions or an optimizer.

This is an independent **offline evidence audit**, not a new hardware proof. RTL simulation/GDS-read PASS refers to recorded tool results in checked evidence; KLayout and simulation are not rerun. Formal claims are never promoted to PASS by this importer. Original-to-final constraint semantics remain UNKNOWN until a real verifier is implemented. Decision policies cannot submit gate values as proof; future action execution must re-run trusted verifiers against immutable evidence.

## Current authoritative findings

Local and remote main started at `9644bb3f8ed42bb3d5f23acc267e1235bc089496`. The engineering Smoke ZIP and payload remain intact. `evidence/verieda-smoke-state.json` was produced by the actual CLI with the trusted archive SHA and external experiment identity:

- Evidence/identity, recorded simulation/physical/GDS-read and router DRC: PASS.
- Timing: FAIL; WNS -0.161583 ns, TNS -7.08646 ns, hold +0.0880612 ns.
- Standard-cell area 943.502 um²; setup endpoint count 51; two distinct saved group-worst max paths, not all 51 endpoints.
- Formal NOT_RUN; constraint equivalence UNKNOWN; acceptance NOT_ACCEPTED.
- Physical runtime 68 seconds, with source recorded. No new EDA or cloud run.

Validation: 45 tests, 44 passed, one existing Linux native-signal test skipped on Windows. Eleven new VeriEDA tests include actual Smoke ZIP/directory parity, forged summary PASS veto, tampering, ambiguous JSON, missing metrics, invalid JSON shape, path escape, timeout/SIGILL/SIGKILL distinctions, and timing PASS without formal PASS. Full native Formal/STA acceptance integration has not run.

Previously prepared `.github/workflows/final_netlist_acceptance.yml`, `acceptance/`, its test and preparation report remain separate, uncommitted and unauthorized for cloud execution. They are not implicitly promoted by these software tests. Review items before release: the old helper folds all failed proofs into UNKNOWN rather than distinguishing a real basecase counterexample; STA delay parsing depends on the Formal model-import output; native command/model parsing and induction convergence remain untested. The recorded original artifact expiry is 2026-10-26, with actual availability to be checked before any separately authorized run; the local authoritative ZIP is retained. Do not rerun Smoke merely to replace expired evidence.

## Technical direction and requirement evidence

Start with a Python CLI/library rather than a service or UI: it can be run and tested against real evidence now, integrates with existing jobs, and avoids maintaining a second execution platform. Keep existing workflow/Tcl/Shell adapters; do not rewrite the EDA flow. The verifier owns evidence-based verdicts; a future policy owns proposals, never PASS flags.

| Research/tool requirement | Current evidence | Remaining work |
|---|---|---|
| Real RTL→GDS execution | Existing frozen Smoke, readable GDS | Independent successful baselines with timing/formal |
| Structured design understanding | Runnable CLI and checked Smoke state | Coverage, precise delay contributions, more adapters/designs |
| Independent validation | Integrity/identity/raw timing audit, fault tests | Constraint semantics, real sequential proof, physical/corner coverage |
| Useful optimization | No claim yet; real timing bottleneck identified | Bounded actions and controlled comparative measurements |
| Full autonomous loop | Not implemented | Policy, execution authorization, independent acceptance and history |
| Research novelty | NOT_ESTABLISHED | Primary literature review, hypotheses and fair ablations |

Next implementation order:
1. Add a conservative constraint-contract verifier using original input identity and evaluated constraint evidence; never treat equal clock periods alone as complete SDC equivalence. Separate positive counterexample, timeout, unsupported model and tool crash in Formal result ingestion. Fix/validate Acceptance prerequisites offline before seeking a single authorized native job.
2. Integrate existing-netlist STA/Formal results when separately authorized. A timeout stays UNKNOWN. A post-reset proof must retain its exact initialization/observability contract and cannot be presented as arbitrary-initial-state equivalence.
3. Add immutable candidate manifests and a small typed action interface with frozen design/constraint/tool identities, resource limits and rollback. Execution permissions remain separate; no automatic cloud budget expansion.
4. Start with a deterministic failure-aware policy as the control, then compare bounded search/other optimizers and an optional LLM policy under the same design inputs, constraints, action space and EDA budget. Mapping, sizing/buffering and local physical repair are candidate families, not a promise to implement all of them. Do not equate the first ABC-area toggle with an autonomous research contribution.
5. Extend beyond GCD only after tool/model/verifier coverage is checked. Measure verified improvement rate, false acceptance, unknown/failure recovery and total tool cost; stratify CPU/tool identity and use repeated independent runs. Whether verification-aware cost allocation offers research value remains a testable hypothesis.

No UI, multi-agent controller, training framework or novel-toolchain rebuild is introduced. The full goal stays active; this checkpoint is an implemented foundation, not a redefinition of the final outcome.

## Verification interfaces checkpoint

Two additional local interfaces now exist:

```powershell
python -m verieda compare-constraints reference-export.sdc candidate-export.sdc
python -m verieda observe-formal proof.log --return-code 1
```

`compare-constraints` does not execute Tcl. Its `exported-sdc-literals.v1` profile covers current_design, explicitly named physical/virtual clocks, period/waveform, propagation, basic network latency, explicit I/O port collections and min/max delays. Numeric values use bounded exact decimals, not float tolerances. It checks definition order and rejects duplicate/ambiguous specifications. Variables, source/exec/eval, wildcards, timing exceptions, unsupported flags and malformed grouping yield UNKNOWN. It does not assume an ideal-to-propagated conversion is automatically permitted.

Exit codes: 0 EQUAL_WITHIN_PROFILE, 1 DIFFERENT, 2 UNKNOWN/input error. Equality is deliberately not complete native SDC equivalence: `full_constraint_gate` remains UNKNOWN until native timing units, dependencies, object inventory and coverage are independently certified. Both raw file hashes and normalized contract hashes are recorded. Equal periods alone never suffice. The original Tcl source is not silently interpreted by a partial evaluator.

`observe-formal` separates basecase counterexample reports, induction bound exhaustion, finite/combinational success, reported unbounded proof, timeout, model/capability gap, unknown SIGKILL cause and tool error. Log markers were checked against the [Yosys SAT source referenced by frozen ORFS](https://github.com/YosysHQ/yosys/blob/a5af9d690a43744bf6b2cc3dea2717c16b54621c/passes/sat/sat.cc). That source reference is not an assertion about the image binary's build provenance. Raw and decoded-text hashes are distinct. No untrusted log can create certified PASS or a validated counterexample verdict; execution identity, exact property, initialization, models and native proof/witness validation are still required. Exit zero means classification completed, never Formal PASS.

Latest validation: 74 tests, 73 passed, one existing Linux native-signal test skipped on Windows. Added regressions cover constraint relaxation, I/O changes, dynamic/unknown Tcl, malformed syntax, numeric precision/range, unresolved/duplicate clocks, propagation changes, actual exported SDC support, formal result distinctions and CLI exit/status behavior. `evidence/verieda-constraint-profile-check.json` was produced by the real CLI against the retained final SDC; it reports equality within the profile and full native constraint gate UNKNOWN. Tests include synthetic logs; these are not real Formal experiments.

The core tests now resolve the repository from their own file path. The legacy unpublished Acceptance preparation still has workspace-bound fixtures and needs separate native integration review before a future CI release. Existing Acceptance code/workflow/report were not changed or published in this checkpoint.

Next integration work remains substantive: native reference/candidate constraint exports with bound context; authenticated Formal results and witness/proof validation; then immutable action/candidate manifests and an independent adoption predicate. Actual optimization, successful formal/timing baselines, multiple designs and fair research comparisons remain unachieved. No new cloud execution authority is inferred from software progress.

## Native bridge preparation checkpoint

The unpublished native acceptance package has now been revised and versioned locally; NATIVE_ACCEPTANCE_READINESS.md is authoritative for this revision. It adds native evaluated reference/candidate SDC snapshots with context/output hashes; native OpenDB pin directions decouple STA parsing from Yosys; endpoint aggregates are checked against WNS/TNS. Trusted native Formal handling now distinguishes a basecase counterexample with witness, unproven bound exhaustion, timeout/model gap and tool errors using the shared VeriEDA observation classifier. Snapshot extraction is never equated with complete constraint equivalence.

Current offline suite: 85 tests, 84 passed, one existing Linux integration skipped. Native execution remains NOT_RUN. A package checksum preflight detects incomplete publication before downloading artifacts or pulling the image. The reference/candidate contexts and exact reset contract still need real execution and review. No actual Formal/PPA improvement, independent successful Baseline, or autonomous optimization is claimed. A single bounded native run requires explicit new user approval, followed by evidence ingestion and verification; the project goal stays active.

Native verifier source uses acceptance/.gitattributes to pin LF within that directory; this prevents Windows checkout conversion from invalidating source SHA bindings. The original root attributes and frozen experiment files are unchanged.

## Native evidence importer checkpoint

`python -m verieda inspect-acceptance ARTIFACT_OR_DIRECTORY [--expected-sha256 TRUSTED_ZIP_SHA]` reads the bounded native bundle without extracting or executing its content. It reuses the complete checksum/size audit and independently parses raw setup WNS/TNS and Yosys exit/log observations. Claimed summary PASS cannot override negative raw timing. Missing, duplicate or inconsistent data stays UNKNOWN; tool signals and timeouts remain distinct.

This interface does not authenticate a GitHub run merely because execution-source.json names one, even with a trusted archive digest. It does not independently validate the exact proof property, functional model, reset contract or witness. Formal and complete constraints cannot receive PASS here; positive setup alone cannot establish hold/coverage acceptance. The existing native package and an external run/commit binding remain prerequisites for future certified ingestion.

Exit 0 means observation completed, not design accepted. Exit 2 means input/integrity failure. Tests use synthetic bundles, not new EDA results. Current offline suite: 96 tests, 95 passed, one existing Linux native-signal test skipped on Windows. The native package source manifest includes the new adapter/CLI/test bindings. The real Smoke ZIP and its existing CLI results were rechecked unchanged: timing FAIL, formal NOT_RUN, acceptance NOT_ACCEPTED. No workflow, physical input, cloud authority or remote branch changed.


## Unified offline decision

`python -m verieda decide` joins the existing reference, candidate and optional
Formal evidence into one auditable next action. It never executes EDA or grants
permission. Example using retained real evidence (PowerShell, repository root):

```powershell
python -m verieda decide --profile cases/gcd.json `
 --smoke evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip `
 --acceptance evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip `
 --budget-seconds 300 `
 --result evidence/verieda-action-ed5d84b9bdf7/result.zip `
 --expected-sha256 15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3 `
 --formal-result evidence/candidate-formal-9a84b59a1c60/verifier-result.zip `
 --formal-sha256 98f42872720c8fe0b73492ef8766f3b966725c049507975f9b58c6799e2511f7
```

This case returns REVIEW_TOOL_FAILURE / CANDIDATE_TOOL_BLOCKED, with proof not
started. It does not reject the design or block the project. Without Formal
inputs it requests candidate verification; without candidate inputs it proposes
from the reference (mapping requires a 600-second cap). Always supply the latest
known candidate: this is a supplied-evidence snapshot, not a scheduler or global
inventory. Pending/failed candidate evidence never falls back to another mapping.
Exit 2 means evidence HOLD; exit 0 means analysis completed, not design PASS.

Optional --verification-package and --formal-contract reuse static proof-scope
review. --after-profile / --after-smoke / --after-acceptance load independent final
evidence and delegate accept/reject/continue to the existing full-flow predicate.
The CLI takes no raw agent verdict. Invalid/contradictory Formal evidence HOLDs
before adoption. Counterexample, timeout, unknown and tool errors remain distinct.
Synthesis success cannot satisfy final Formal, timing, DRC or constraint checks.

JSON binds reference provenance, decision-entrypoint/source-manifest hashes and
complete decision content. Hashes support replay, not attestation. Budget means
caller-supplied remaining native time; setup/queue/billing, monetary cost and
expected gain are not inferred. No reservation or retry occurs. Synthetic
cross-design tests do not establish a second real RTL flow. This deterministic
V0 integration does not demonstrate LLM optimization ability.


Local integration checkpoint: 232 offline tests, 231 passed and one existing
Linux-only integration skipped on Windows. Nine new tests cover real retained
reference/candidate/native-failure evidence, CLI/API parity, budget/identity
holds and synthetic final accept/reject/continue outcomes. A re-sealed native
archive with the wrong task ID reproduced a lifecycle override defect: final
state evaluation could overwrite HOLD_VERIFIER_EVIDENCE. The shared lifecycle
now returns that HOLD before considering final adoption. Original ZIPs remain
unchanged. No repaired native Formal run, push or dispatch occurred.


## Recover candidate and native budget from saved action history

`decide --action-history HISTORY.json --budget-seconds N` accepts at most 16
references, with 32 MiB total unique action ZIP bytes. HISTORY.json is a list:

```json
[{"artifact":"evidence/verieda-action-ed5d84b9bdf7/result.zip","sha256":"15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3"}]
```

Paths use the current working directory. Only these two keys are accepted;
caller-supplied outcome, runtime or acceptance claims are rejected. Every unique
archive is SHA-checked and parsed through the existing action receipt inspector,
then bound to this reference state. Repeated SHA references count once. Different
archives for the same candidate HOLD for review rather than being treated as
an authorized retry. Multiple unresolved completed candidates also HOLD. An
explicit --result must be included and agree with any pending history candidate.

The single completed candidate is recovered automatically, so forgetting --result
does not launch another mapping proposal. Optional current --formal-result and
--formal-sha256 join its independently bound saved verification observation.
Failed actions remain in the policy's exclusion history; they are not retried.

With this flag only, N is a TOTAL supplied native budget (0..600 seconds), rather
than the default unspent budget: checked action time is subtracted before future
verification admission. Remaining admission time is rounded down. Saved current
Formal runtime is also reported/subtracted once its task identity is verified;
no new work is scheduled when reviewing it. Costs beyond N remain visible and
do not prevent free offline diagnosis. This is not a complete research-account
ledger: unsupplied executions, cloud queue/setup/job overhead and billing remain
unaccounted. No expected benefit, monetary price, permission or reservation is
inferred. Caller-trusted archive identities are not independent cloud attestation.

For the retained action, a 304-second total leaves a 300-second Formal cap after
3.140316279 seconds of synthesis execution. A 303-second total stops for budget.
Joining the actual saved Formal preparation failure additionally records about
0.822325418 seconds and recommends tool-failure review, not another EDA run.

History checkpoint: 236 offline tests, 235 passed and one Linux-only test skipped.
New coverage includes actual artifact cost/identity, duplicate and conflicting
references, budget admission boundary, directory rejection and CLI/API parity.
No new EDA run or proof result was generated.


## Shared ORFS layout boundary

`verieda.execution.design_paths(design, platform_name)` now supplies the single-file
ORFS convention used by native command generation, source identity checks,
output sealing, historical receipt inspection and candidate verification packing.
`expected_effective` provides the matching checked Make output. Strict bounded
ASCII names reject traversal and Make/shell metacharacters. Historical GCD argv,
paths, effective-variable bytes and verifier subject/task identities remain
compatible; old archived source identities are retained rather than rewritten.
The NETLIST/ODB/OUTPUTS and EXPECTED_EFFECTIVE aliases keep their GCD defaults.

This is a reusable path capability, not another registered execution backend.
`prepare-action` still admits only the audited GCD/Nangate45 source/tool/image
combination. A synthetic counter layout test checks conventions and verifies that
its preparation remains rejected. Multi-file RTL, different source/top naming or
nonstandard directories need an explicit future descriptor and source identity
review, not guessed paths. No second RTL execution/proof is claimed.

Offline checkpoint: 239 tests, 238 passed and one existing Linux integration
skipped on Windows. Regression also preserved structured rejection of missing
package files. Python syntax, source package hashes and diff checks passed.
Frozen RTL/SDC/ORFS/image, original artifacts and remote state were not modified;
no push, dispatch or EDA execution occurred.
