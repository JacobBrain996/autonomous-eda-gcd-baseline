# VeriEDA — executable core and development checkpoint

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
