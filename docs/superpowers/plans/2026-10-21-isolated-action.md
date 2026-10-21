# Isolated mapping action — design and execution plan

Extend the existing V0 CLI, not the EDA toolchain. User delegates local implementation; no new cloud run/push authority is inferred. Reuse the frozen Makefile `synth` target, with only ABC_AREA changing from the observed area script to speed script. The original netlist proof is not a proof of the resulting candidate.

## Contract
`prepare-action` reloads the trusted case and validates a candidate, then writes a new exclusive public package (state, candidate, manifest, effective-variables Makefile). Package files/source hashes are verified before execution. An existing destination is never overwritten; no RTL, SDC or original ORFS file is changed.

`execute-action` defaults to NOT_RUN. Explicit `--execute` is required at the caller boundary; it is not a substitute for human/cloud authorization. Native execution is only supported inside a separately authorized Linux container with frozen ORFS mounted read-only, matching Git head, frozen source/input/tool SHA256 and a fresh output directory outside ORFS/package. Use fixed argv, minimal environment, LEC_CHECK=1, SEC_CHECK=1, ABC_AREA=0 and isolated WORK_HOME/FLOW_VARIANT. No arbitrary commands/parameter names are accepted.

Total native synthesis action cap 300 s, preflight at most 20 s, logs 16 MiB/file, core disabled; terminate the whole child process group on timeout. Exact effective variables must match before synthesis. Save actual return code, runtime, signal, output hashes and receipt. Only SYNTHESIS execution can pass; full design acceptance, PPA gain, GDS/timing/Formal remain NOT_RUN/UNKNOWN. OCI host attestation remains a separate required check; binary SHA is not an OCI proof.

## Tasks / tests
1. RED/GREEN package creation, identity/illegal-action/no-op protection, existing destination, tampering and safe paths in tests/test_execution.py. Implement verieda/execution.py and source support JSON.
2. RED/GREEN default NOT_RUN, explicit native guards, fixed argv/environment, subprocess timeout/signal propagation using isolated test doubles only where Linux EDA is unavailable. Synthetic process results cannot certify EDA efficacy. Add CLI prepare/execute and real evidence offline demo.
3. Full suite + source manifest, independent review/fix pass, local commit. No remote mutation or EDA execution. Future native integration remains NOT_RUN until separately authorized.

## Review focus
Untrusted bundle commands/path traversal; source/tool identity mismatch; Make option injection via environment; overwriting/reusing output; timeout descendants; mistaking synthesis/temporary process success for complete independent design acceptance.

## Execution ledger
- Base35980c6, clean tree. Previous turn was progress. Source inspection confirmed frozen config ABC_AREA=1, historical log area script, preamble0→speed. Exact downloaded bytes checked against Git blob SHA1 and SHA256; kept only in ignored evidence/.
- Package/CLI test-first cycles: missing module/command RED → bounded exclusive package + default NOT_RUN GREEN. No EDA/container run. Process timeout/SIGILL tests use narrowly scoped native-API doubles on Windows.
- Partial synthesis/hold receipt acceptance regression RED → require COMPLETED RTL_TO_GDS receipt GREEN. Synthetic evaluator fixtures updated to name their explicit full-flow receipt; no physical result created.
- Independent review found two Important issues: Make could resolve unverified alternate tools; ignored settings.mk could execute before variable preflight. Fixed with explicit effective tool paths and ignored-flow inventory rejection before Make. RED→GREEN includes a real temporary Git repository whose status is clean but ignored settings.mk exists. No Make command was run in that regression.
- Ruling: inventory rejects all ignored flow files, including benign caches, rather than evaluating arbitrary optional Make configuration. Cost if too strict: native preflight HOLD on a reused checkout; no automatic deletion or relaxation. Native container success remains NOT_RUN and must not be inferred from unit tests.
- Final verification: 157 tests / 156 passed / 1 existing Linux signal test skipped on Windows; package-check, compileall and staged whitespace audit pass. Real pinned GCD evidence created evidence/mapping-action-package-v1; actual execute-action default returned NOT_RUN without touching the nonexistent native paths. Historical evidence/older preparation packages preserved. Explicit 10-file local source/test/doc/manifest commit only; no push or cloud execution.
