# Evidence-bound candidate verification handoff

This increment connects a successful real synthesis action to independent
verification preparation. It neither executes EDA nor accepts a candidate.
The reference case and Run 39571841412 are immutable inputs.

## Runnable interfaces

From the repository, use the same --profile, --smoke and --acceptance arguments
as `advance-action`, plus the candidate result archive and its trusted digest:

```powershell
python -m verieda verify-next --profile cases/gcd.json --smoke evidence/smoke-9644bb3f8ed4/NO_LEC_SMOKE-38226418563.zip --acceptance evidence/final-acceptance-bbf5c1de8b7c/acceptance-39544704950.zip --result evidence/verieda-action-ed5d84b9bdf7/result.zip --expected-sha256 15ad5d562b81007dc4364dd4a5320890f7160adcfaf893e8aa14308f968f7bf3 --budget-seconds 300
```

`prepare-verification` accepts those arguments and `--output NEW_DIRECTORY`.
It writes only candidate.v, candidate.odb, subject.json, plan.json and manifest.json;
existing output is refused. `inspect-verification DIRECTORY` checks bounded,
nonlinked inputs, exact file inventory, SHA coverage, task and plan identities.
An input_gate PASS means package consistency only, never hardware acceptance.

`advance-action` now includes verification_handoff using the remaining recorded
native budget. Other execution/history behavior is retained. `verify-next` takes
an explicitly *unspent* native verification budget, rather than subtracting the
same synthesis cost twice. No function grants execution authority.

## Why Formal first

No mapped-candidate timing gain has been measured. A bounded functionality check
can reject or expose model/proof gaps before spending on place/route. This is a
qualitative information-value ordering; no fabricated success probability or
speedup forecast is used. The full 300-second Formal cap must fit the budget;
299 seconds is not enough. Setup/queue time and money are separate and unknown.

The planner emits the dependency chain: synthesis Formal review -> physical
implementation -> final-netlist Formal plus extracted setup/hold/constraints,
GDS/DRC -> independent adoption. A pre-layout synthesis ODB cannot replace a
routed database, and a synthesis proof cannot certify a later final netlist.

## Common saved-verifier interface

Optional `verify-next --formal-result ZIP --formal-sha256 TRUSTED_SHA` ingests a
bounded checksum/size-sealed archive using existing VeriEDA evidence readers.
It requires receipt.json with schema verieda.verifier-receipt.v1, exact task_id
and inputs copied from the request, engine_sha256, integer return_code, measured
runtime_seconds <=300, and log_path pointing to the raw Yosys log. Extra producer
PASS claims are not authority. Input binding includes netlist, original RTL/SDC,
library, Yosys binary, reset/output contract and source candidate archive.

Unbounded marker -> REVIEW_FORMAL_SCOPE (formal UNKNOWN); BMC -> REVIEW_UNPROVEN;
reported counterexample -> REVIEW_COUNTEREXAMPLE (not a validated design bug);
SIGILL/tool error -> STOP_REVIEW_TOOL_FAILURE; timeout -> STOP_REVIEW_TIMEOUT;
wrong target/digest/runtime -> HOLD_VERIFIER_EVIDENCE. No automatic retry or
physical job is unlocked. Execution authentication, exact property/model/reset
review and witness validation remain independent responsibilities. Historical
reference Formal PASS is metadata only and cannot fill the new target's gate.

## Reuse and limits

The task planner and saved-verifier interface have no GCD port/width/state-name
assumptions; a counter-design unit fixture exercises that boundary. This is not
proof of general RTL support. The existing source/action intake still supports
only the frozen GCD adapter. New-design evidence import and native adapters are
not implemented by renaming a profile. Candidate generation remains the existing
auditable rule-policy control, not a claim of LLM reasoning or research efficacy.

Reuse existing capability probes, complete used-cell functional-model closure,
all-output miter handling, induction, immutable evidence checks and STA extraction.
Do not launch acceptance/verify.py unchanged: it pins the OLD four final inputs,
expects exactly 39 used cells and old internal state aliases, and its STA path
pins old WNS/TNS. The new candidate requires discovered cell coverage and freshly
validated miter/state bindings. The old strengthened relation may only be a new
proof hypothesis with the original mismatch retained, never an assumed lemma.

## Validation and next boundary

Offline suite: 189 tests, 188 pass, one existing Linux signal integration skip on
Windows. Seventeen new tests cover actual saved synthesis evidence, CLI/materialized
handoff, budget admission, target/tool identity, wrong old proof input, mutation,
BMC/unbounded/counterexample/timeout/signal distinctions and package integrity.
Synthetic logs test software behavior, not EDA or proof success. Native admission
and a second real RTL design remain untested. No new API/model/cloud calls or
external publishing are part of this increment.

## Native Formal and lifecycle increment

The candidate-aware adapter now exists in verieda/formal_runtime.py. This
supersedes the earlier adapter-preparation gap; native Linux integration is still
NOT_RUN. It reuses audited capability/model-closure checks without calling the
old 39-cell/final-input acceptance routine.

```powershell
python -m verieda execute-formal --package evidence/verification-handoff-20261021-v1/package --contract contracts/gcd.reset2.json --frozen-root __unavailable__ --work __not_created__
```

Default is NOT_RUN and creates no work directory. --execute additionally requires
Linux x86_64, read-only frozen source and package mounts, exact registered
OCI/source/tool hashes, and --image-identity from the host. It discovers actual
cell types, retains complete selected functional Liberty cell bodies, checks
both top interfaces and common positive DFF clocks, regenerates the all-output
miter and independently loads original RTL and new gate netlist. Blackboxes,
unsupported clocks/latches/memories, missing models or input mismatch HOLD.

The explicit reset/port contract is registered by content digest in
contracts/registry.json. Keeping the same English description while changing
reset duration/polarity or output inventory is rejected. A new RTL needs a
reviewed profile/registry entry and supported evidence/action adapters, not just
a renamed GCD case. The generic miter generator is tested with a different
counter interface; there is no claim of a second native RTL experiment.

The prior GCD state relation is only an optional fresh proof hypothesis.
Its state/boot bindings are revalidated on the current miter; the original
all-output mismatch is ORed into the proved property, never assumed or cut.
If fresh bindings are unsupported, the adapter uses the original property and
reports the missing strengthening; it does not substitute historical proof.
The single induction invocation can therefore remain UNKNOWN if it cannot
converge. No BMC bound is treated as equivalence.

The process driver kills the process group on timeout, records PID/exit/signal,
and limits every child log and core output. Capability discovery, model import
and proof share a 300-second native budget; killed-timeout receipt parsing permits
one second of reaping overhead. Archives allow only explicit proof/model/source
files, each <=16 MiB and total payload <=32 MiB; no environments or cores are
collected. Actual Python, hooks, registry, tool/library/input identities are saved.

`review-candidate` accepts the same arguments as verify-next. It reports candidate
state and operation state separately: VERIFY_PENDING_CANDIDATE +
WAITING_FOR_AUTHORIZATION; PROOF_REVIEW_PENDING; VERIFICATION_UNKNOWN/TIMEOUT;
CANDIDATE_TOOL_BLOCKED; or EVIDENCE_HOLD. block_scope is CANDIDATE_ONLY and it
never updates a project Goal. With --after-profile/--after-smoke/--after-acceptance,
it loads actual final evidence and delegates ACCEPTED/REJECTED/INCONCLUSIVE to
the existing independent full-flow/contract/identity/gate/QoR predicate. A policy
PASS string or old reference proof is never an adoption input.

### Controlled external execution, not yet authorized

Prepared workflow: .github/workflows/verieda_candidate_formal.yml. It restores
only the pinned 143,054-byte public parent Artifact 12332122927 from Run
39571841412, verifies outer/inner SHA and candidate ID, and prepares a fresh
request. It does not depend on old runner files or re-download the older Smoke.
An expired/mismatched parent artifact stops; there is no EDA rerun fallback.

Scope: one public standard ubuntu-24.04 job <=10 minutes, Formal <=5 minutes,
2 vCPUs/6 GiB container, no network/capabilities, read-only source/package/image
mounts, no paid/larger/self-hosted runner, no automatic retry. Original resource
checks before and after pull are retained. No synthesis, place/route, Timing
ECO, Kepler or full baseline run. Only explicit public artifacts are uploaded.
One dispatch per published commit and attempt 1 only; further dispatch is still
a human authorization decision, not granted by workflow availability.

Expected information: equivalence/proof capability of the saved speed-mapped
netlist. An unbounded marker exits the engine step successfully but remains
UNKNOWN/PROOF_REVIEW_PENDING until independent execution/property/model/reset
review. Counterexamples require validation; timeout, model gaps and SIGILL stop
without retries or design-bug attribution. Routed Timing and final-netlist Formal
remain separate later tasks. No PPA improvement or baseline PASS is claimed.

Local delivery uses no paid API and starts zero new EDA jobs. Runtime caps are
limits, not forecasts; monetary cost is NOT_AVAILABLE. The next meaningful
runtime validation needs separate authorization to publish this source and
execute this exact one-job workflow, followed by evidence recovery and review.
No additional controller or parameter sweep is introduced.
