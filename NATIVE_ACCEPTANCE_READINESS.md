# Native acceptance readiness — VeriEDA bridge

本报告取代早期 FINAL_NETLIST_ACCEPTANCE_PREPARATION.md 的当前就绪结论；旧报告保留历史版本及当时的SHA，不能用它证明修订代码已经过原生验证。

## State-relation strengthening candidate after Run 39537975290 — local only

The real run now imports all 39 functional models and links the complete design successfully. Its base cases for induction lengths 1..32 were proven, but every induction step failed; the monolithic output predicate did not converge. This is UNKNOWN_UNPROVEN, not a reachable counterexample. Timing remains FAIL. Raising the bound alone is not the proposed next action.

The new candidate retains the complete original miter bytes (apart from inserting new declarations before the final module end) and its original all-18-output mismatch. A small combinational relation module adds a stronger proof output: original_mismatch OR boot-invalid OR post-boot state-relation violation. No assume, cutpoint, initial equality, changed reset sequence or output-valid masking is introduced. A successful proof of zero strengthened mismatch therefore includes the original property; the candidate relation itself must pass basecase and induction, not be assumed.

Candidate bindings are generated from the native miter.json plus corresponding declared RTLIL wires, checked for exact widths, distinct state bits, unique FF Q drivers and a common positive clock. It covers 71 state bits: original boot counter, gold's 32 data/2 control bits and gate's 32 data/3 control bits. Candidate relation: data A/B registers equal after boot==2; gold control 0/1/2 corresponds to gate bit 0=IDLE / bit 2=CALC / bit 1=DONE, with no undefined state. Boot must always be defined and in 0..2. No relation is required for data during the initial two-edge reset phase. The boot-valid condition is also a proof obligation. Names suggest register correspondences; they are not themselves proof of correspondence.

Mapping evidence: gate.req_rdy aliases state-bit-0 Q. gate.resp_val is state-bit-1 AND NOT(state-bit-0 OR state-bit-2), so its legal one-hot DONE decode identifies bit 1. Gold RTL defines IDLE=0, CALC=1, DONE=2. The remaining candidate CALC bit is 2. This is a hypothesis to prove; wrong mapping should fail an auxiliary obligation without being announced as a chip bug. Raw bindings, FF drivers, original IL/JSON and generated source hashes are saved in evidence/final-acceptance-cbe97b6aaa75/offline-strengthening/strengthening.json. Its status remains UNPROVEN_CANDIDATE.

The future native proof process reads the augmented RTLIL and relation Verilog, checks hierarchy, flattens/normalizes and exports the resulting JSON/RTLIL before the existing temporal-induction command. It proves strengthened_mismatch==0 with the same reset/init/input semantics and maxsteps 32. It shows both original and strengthened mismatch in the raw solver trace. A reported basecase failure without witness evidence of original mismatch=1 becomes UNKNOWN_AUXILIARY_PROPERTY_OR_WITNESS; it does not become a validated functional counterexample. Successful unbounded proof records the auxiliary relation as PROVED_WITH_PROPERTY. Timeout, model/format gaps, compiler errors and bound exhaustion stay distinct.

Offline suite: 124 tests, 123 passed, one existing Linux integration skipped. Tests first failed before the generator existed, then validated original-body preservation, source binding, actual native wire/FF binding, wrong clocks/missing aliases/wrong widths, overlapping state and unsupported file structure. Existing real model-import/STA evidence was not overwritten. New native RTLIL/Verilog import and strengthened induction convergence are NOT_RUN; these tests are not a Formal proof or a full compiler validation.

The proposed next experiment is exactly one separately approved existing-netlist acceptance job: standard public ubuntu-24.04, 10 minutes total, Formal 5 minutes, no auto-retry or physical implementation. Its only design-analysis change is the additional proof obligation; frozen RTL, netlist, SDC, platform, ORFS/image/binary/library identity and original observed outputs stay intact. The original miter.v and workflow are unchanged. No push or dispatch has occurred in this checkpoint. Complete original-to-final constraint acceptance and timing closure are still unresolved even if this proof succeeds.

## Strict used-cell functional library preparation — local only

A bounded structural extractor now preserves selected Liberty cell groups byte-for-byte and removes only unused top-level cell groups. Library/global text, comments, escaped strings, nested groups, ff definitions, pin functions and timing contents are retained. It rejects duplicate/missing cells, unsupported scope, malformed comments/quotes/braces/parentheses, unsafe selection and size/depth excess. define(..., cell, ...) is correctly distinguished from an actual cell group. It is intentionally not a Liberty semantic parser.

The original 6,692,032-byte frozen library contains 135 cells. Offline extraction for the actual pinned final netlist retained 39 complete cell groups, omitted 96 unused groups and produced 636,056 bytes, SHA256 54ee4fb0ff51c15d4e41cbc9982c7d7e3258f3fc1eaae0f6e7a75d61ef1e4b13. Reparse confirms exactly the selected names and identical retained body hashes. CLKGATETST_X1 is omitted because it is not instantiated; no used cell is excluded. Preview/selection evidence is in evidence/final-acceptance-b57565ec3f07/offline-library-preview/. It is NOT_IMPORTED, not a native model PASS or proof.

In the proposed native job, a fresh Yosys process first reads only the frozen final netlist and writes unlinked.json (15 seconds maximum, counted inside the existing 300-second Formal budget). The discovered type set must contain the expected 39 cells in the single gcd module. The helper rechecks the original library SHA, creates functional-used.lib with source/derived/per-cell byte hashes and binds it to the netlist/discovery JSON/engine hashes. Both ordinary read_liberty invocations use this derived library without -lib or ignore-missing flags. Discovery, imported model names and actual linked cell types must match exactly; existing blackbox/functional checks, exact top port set, all 18 outputs, positive shared clock, reset contract and SAT requirements remain enforced. A later coverage file records successful model closure plus selection/source/derived hashes before proof. The pre-import selection manifest stays NOT_IMPORTED by itself.

Offline suite: 119 tests, 118 passed, one existing Linux signal integration skipped on Windows. Tests first failed before implementation, then passed for byte preservation, global text, comments/quotes, actual define syntax, missing/duplicate cells, malformed structure/selection, idempotence and model/link closure; dropped models, unexpected models and blackboxes are rejected. The full actual source extraction also passed locally. No native Yosys discovery, selected-library import or SAT proof was run here. Native JSON frontend behavior/model normalization and induction convergence remain explicitly unverified; timeout/unsupported/error remains HOLD, not PASS.

LIBRARY_SELECTION_STATIC_GATE = PASS_OFFLINE
FORMAL_MODEL_IMPORT_GATE = NOT_RUN
FORMAL_EQUIVALENCE_GATE = NOT_RUN
READY_FOR_ONE_BOUNDED_NATIVE_JOB = YES_PENDING_NEW_AUTHORIZATION

The next proposed action is normal publication of the local path fix and this library fix, followed by exactly one unchanged standard public Ubuntu job (10 minutes total; Formal 5 minutes; no physical flow/ECO, auto-retry, input/library-source/image change or new paid resource). Its purpose is native import plus full sequential proof under the existing contract, not a promise of baseline success. Current timing and full constraint gates remain FAIL/UNKNOWN. No push or dispatch occurred in this checkpoint.

## Local path correction and functional-model inventory after Run 39531565936

The real native run validated the prior report-capture and SAT-help fixes. Exact WNS=-0.161583200 ns, TNS=-7.086462975 ns and 51 negative endpoints are retained. The post-run delay decoder defect is now corrected: a launch-clock input does not start the data section, the actual input-port/launch-Q boundary does, and the final output-port wire increment is included. A missing launch boundary is HOLD. Original producer JSON/ZIP remain immutable; all 51 paths were re-decoded in evidence/final-acceptance-b57565ec3f07/offline-corrected/ using the original reports. Worst-path data-cell delay is 0.357314038 ns including clock-to-Q, and data-net delay is 0.002443143 ns. The new public fixtures are the native worst-path block and deduplicated pin-direction inventory from Artifact 12315334148; fixture normalization changes no direction or delay value.

Current offline suite: 108 tests, 107 passed, one existing Linux signal integration skipped. New tests first reproduced the real 0.070705 ns clock-buffer overcount and missing launch/output-wire defects, then passed. They also cover input launches and clock sections. This is reanalysis of an existing native run, not a new EDA execution or Timing/ECO improvement.

The frozen Nangate45 platform tree ae524ee77146b29759794ddc9e77ac3423250b07 was read recursively (not truncated). Its only .v/.sv files are cells_adders.v, cells_clkgate.v and cells_latch.v; it does not ship a complete functional Verilog library. The exact frozen typical Liberty SHA remains 8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1. A source-text inventory found output function declarations for every used cell type (39), including DFF_X1 Q=IQ/QN=IQN and an ff group. This inventory is not a Liberty semantic parser, successful Yosys import or a proof. Native DB inventories also contain physical-only masters; used-cell coverage must come from the linked netlist, not blindly equate every physical master with a functional instance.

FORMAL_PREPARATION_GATE remains HOLD: no unsafe ignore-missing flags, blackboxes or design/contract changes have been introduced. Next local work should prepare a strict, bounded Liberty group extractor that preserves every used cell body byte-for-byte and records input/derived/cell identities; retain all 39 required functional models and validate linked closure before proof. Unsupported syntax or missing models must stop. An untested derived library must never create PASS. No push or cloud run is approved by this checkpoint, and no third acceptance attempt has been made.

## Adapter repair after Run 39451358576 — local only

The previous native run failed in verifier adapters, before complete STA reporting and before model import/SAT. This revision invokes report_units, report_wns and report_tns with only their documented options and captures their output through fixed begin/end markers in the existing process log. Python rejects missing, duplicate, reordered or empty sections and refuses stale report overwrite; it preserves the printed precision and propagates tool failures. report_checks/check_setup retain their explicitly documented redirection. The capacitance report field now uses its documented full name.

Yosys capability parsing now uses option declarations from the SAT help section, supports comma-grouped declarations, requires exact option tokens and reports missing names. It does not accept prose references or longer similarly named flags. The public fixture is the actual SAT help section (trailing blank lines normalized) from Artifact 12278756960 / Run 39451358576; the original ZIP SHA256 is f93ea8ad7bded676e2cffb3903fb8961726ccec780826eb00e5d46900a8c1152. A fixtures-scoped LF attribute keeps its checksum portable.

Regression tests first reproduced the old report_units argument failure and absent helper behavior, then passed after repair. Current offline suite: 105 tests, 104 passed, one existing Linux signal integration skipped on Windows. Strict report signatures run both full Tcl scripts, with fixed fake database/tool dependencies; this remains a stubbed integration, not native EDA validation. The real Yosys help fixture passes and missing/near-matching/prose options are rejected. Report precision, malformed markers, stale files and native-error propagation are checked.

Frozen ORFS/image, RTL/SDC, complete library requirements, all 18 output bits, reset contract, Formal budget and baseline gates are unchanged. No repair push or new cloud dispatch is authorized by this local revision. Remaining native risks include stdout ordering/capture, remaining OpenROAD APIs/format, full Liberty import and SAT induction convergence; another job must not be presented as guaranteed success. The next proposed experiment is one separately approved identical 10-minute standard public job with Formal capped at 5 minutes, no physical rerun and no automatic retry. Its current package bindings supersede the failed run's hook hashes, not the frozen design/tool identity.

## 具体拟执行作业（尚未授权、未执行）

`.github/workflows/final_netlist_acceptance.yml`，仅workflow_dispatch，一个标准public ubuntu-24.04 job，10分钟上限。保持ORFS 3a964e13f11a4e435aac01ffa14db0a7d2853720及原OCI digest、GCD RTL、Nangate45和0.25 ns原约束不变；不跑综合/布局/布线/Timing ECO，不调用Kepler，不增加付费资源或自动重试。

1. 先核验acceptance/PACKAGE_SHA256.json中的全部代码绑定，再恢复Smoke Run38226418563 / Artifact11736162790的唯一固定ZIP。ZIP SHA256=7dbdda5dd2e4d3edff841cda2bf2f7ab26099272d3bec4a0294a57e807001d84，3,202,166 bytes。只读GitHub检查确认它当前expired=false，记录到期为2026-10-26 08:57:25 UTC；真正运行前仍需重新检查。过期/缺失即HOLD，不重跑Smoke取代。
2. 获取冻结source/image并检查资源、架构、输入、库及实际二进制SHA。代码/API软件依赖在host和container均显式可见；/audit和/verieda只读挂载，无隐藏PYTHONPATH或REPORTS_DIR前提。
3. 两个全新OpenROAD进程分别在同一final ODB副本上读取冻结原SDC和最终SDC，输出evaluated.sdc、units、原生port inventory及check_setup报告。role是显式且受限的环境变量，source路径不接收任意命令。每次上限20秒。
4. 在原生ODB master terminals中导出INPUT/OUTPUT方向，独立于Yosys执行STA和pin级cell/net增量解析。RC提取沿用原规则；WNS/TNS及51个endpoint须匹配Smoke，路径slack聚合也须与TNS一致。该进程上限60秒。
5. Formal阶段总预算300秒，首先探测所有使用的Yosys命令/选项，再做完整功能模型、时钟、blackbox/latch和全输出范围检查，执行basecase+无界归纳。两次共同reset后所有18位输出始终比较；数据寄存器不初始化为0，未来输入和reset自由。失败时dump WaveJSON；只有basecase反例标记加包含mismatch=1的witness才记录FAIL_COUNTEREXAMPLE。达到归纳长度上限不是反例。超时/模型缺失/工具错误分别记录。
6. 容器总上限420秒，2CPU/6GiB、只读根与输入、network none、core=0、单文件16MiB、总证据128MiB。记录工具版本/二进制、源/库、输入、VeriEDA代码、hook、证明脚本、witness、快照、SPEF、报告及结果SHA256；保留原始错误和退出码。seal依赖失败也生成一个最小HOLD报告，job不转绿。

## Reset-contract source audit

Frozen RTL was fetched read-only from the exact ORFS commit and checked against SHA256 `5009f224876d39e5e77e59ee1528cb0d2a03697251f0971b77cf3e8b0426dd3e`. Source: https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/3a964e13f11a4e435aac01ffa14db0a7d2853720/flow/designs/src/gcd/gcd.v . This is source analysis, not a new simulation or Formal run.

The datapath RegEn does not directly reset (lines 571-578), but the controller synchronous reset sets state to IDLE (lines 143, 352-358). In IDLE, both register enables are one and both muxes select request data independently of req_val (lines 279-285). Thus after reset edge 1 the controller is IDLE; at reset edge 2 the two data banks load common defined request bits. This explains why the existing boot==2 observation boundary need not force data initialization to zero or mask outputs when resp_val is low. resp_msg is the subtractor output (lines 535-538), so idle output data remains observable in the miter.

The claim is limited to the frozen RTL. Corresponding gate-state reset/recoding, Liberty semantics and all-output equivalence still require the actual native proof. No gate equivalence, induction convergence or arbitrary-unreset-state equivalence follows from this source inspection. A solver counterexample must be inspected against this exact two-edge contract, not automatically interpreted as a physical implementation bug.

## 判据与限制

- Formal仅真正无界归纳成功且全部前置检查通过才为PASS_RESET_CONTRACT_UNBOUNDED；有限BMC或未经身份/范围验证的日志不能PASS。
- Counterexample verdict来自受控、冻结engine和固定property。WaveJSON不是额外的独立仿真重放；归纳失败时的debug模型可能是不可达状态，不当成设计反例。
- native快照成功仅表示提取成功。原SDC是在final ODB的端口上下文中重新求值，不宣称与最初RTL-stage对象集合完全相同；check_setup和对象清单供审查。
- ideal clock模型到propagated clock的变化不会被悄悄豁免。当前完整CONSTRAINT_EQUIVALENCE_GATE保持UNKNOWN，比较器只输出受支持profile内的差异。即使job成功，也不意味着完整约束验收或正式Baseline通过。
- 现有TIMING_GATE仍应为FAIL；只精确读取，不放宽0.25 ns或修复物理设计。CLOUD_BASELINE_RUN1=FAIL，RUN2=NOT_RUN。

## 已完成离线验证

85项测试：84通过，1项既有Linux signal integration在Windows跳过。新增测试实际覆盖STA在没有formal/models.json时完成解析、反例与归纳未收敛区别、缺失/不含mismatch的witness、NaN/Inf拒绝、显式role、Tcl完整初始化以及包篡改提前停止。Tcl测试使用stub，不是原生EDA运行。

Python AST、嵌入Python、YAML/actionlint、完整Bash段和Tcl语法均离线检查通过。没有在本机启动Docker/WSL，也没有安装组件、改BIOS或重启。默认Python缺PyYAML时，静态YAML验证使用已安装的C:/Python314；产品与原生job本身仍仅使用Python标准库。

原生OpenROAD数据库API、Liberty导入和SAT归纳收敛尚未执行；这些是拟议一次作业要回答的问题，不能以静态检查替代。若10分钟内不能得到完整证明或发现证据/资源/命令异常，HOLD并停止。

## 发布/授权边界

本轮只做本地提交，不push、不dispatch。准备中的变更仅公开软件、测试、workflow和说明；原ZIP及其他科研目录不进入提交。包内软件SHA清单self-excluded；它证明一致性，不授予执行权限，实际运行commit/run另由GitHub记录。

用户Goal明确“原Final Netlist Acceptance的云端运行尚未获得新授权”。因此接下来需要用户明确批准：正常推送这批可审阅的公开代码，然后只触发上述作业一次，并回收证据。没有批准前继续保持LOCAL_ONLY / NATIVE_RUN=NOT_RUN。

Native verifier source uses acceptance/.gitattributes to pin LF within that directory; this prevents Windows checkout conversion from invalidating source SHA bindings. The original root attributes and frozen experiment files are unchanged.
