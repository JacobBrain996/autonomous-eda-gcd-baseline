> Historical preparation revision. Current package/readiness: NATIVE_ACCEPTANCE_READINESS.md. Original hashes below do not describe the revised VeriEDA bridge.

# Existing final netlist acceptance — preparation

日期：2026-10-12。本轮仅本地准备，未暂存、commit、push、dispatch 或执行 EDA。
权威输入：Smoke Run 38226418563 / commit 9644bb3f8ed42bb3d5f23acc267e1235bc089496 / artifact 11736162790。

```text
STA_PREPARATION_GATE = PASS_OFFLINE_RUNTIME_UNVERIFIED
FORMAL_PREPARATION_GATE = PASS_OFFLINE_RUNTIME_CAPABILITY_UNVERIFIED
FROZEN_IDENTITY_GATE = PASS_OFFLINE_SOURCE_AND_EVIDENCE
OFFLINE_TEST_GATE = PASS (33 passed; 1 existing Linux test skipped)
READY_FOR_ONE_CLOUD_JOB = CONDITIONAL_ON_AUTHORIZATION_AND_RUNTIME_PREFLIGHT
REMAINING_RISKS = native command/model parsing, induction convergence, reset contract, STA reconstruction, artifact expiry
NEXT_MINIMAL_ACTION = review reset contract and authorize publication plus at most one capability-gated acceptance job
```

## 执行范围与初始化

只有一个 ubuntu-24.04 GitHub-hosted public-repository job，上限10分钟；Formal整个阶段包含能力检查、模型解析及证明，上限300秒；STA上限90秒。不安装工具、不重做综合映射/布局/布线，不修改ABC_AREA或设计约束，不调用Kepler。容器禁止网络，原RTL/ODB/SDC/网表/ORFS/source挂载只读，工作目录显式/work，输出单文件16 MiB、总量128 MiB；core禁用。

流程：恢复唯一Smoke Artifact并校验GitHub来源/ZIP与输入SHA → 拉取固定ORFS与OCI → 核验源码/库/工具二进制SHA和实际版本 → 原生Yosys help核验所需证明命令 → 导入功能模型、检查全部39类单元、黑盒/残留latch和共同正沿时钟 → 完整顺序证明 → 原生STA与结果一致性检查 → SHA256/大小封装并上传。任何缺失、解析错误、SIGILL或超时保持UNKNOWN/HOLD，保留退出码与日志，无自动重试。

STA脚本直接使用read_liberty/read_db/read_sdc，没有引用ORFS util/load或隐式REPORTS_DIR环境。Smoke的SPEF未保存；冻结final_outputs.tcl和原始日志已确认使用OpenRCX。准备脚本对ODB副本使用完全相同的corner X、规则文件及默认提取序列重提取RC，保存SPEF后再read_spef分析；不修改布线或回退到placement估算。这是需要在一次授权作业内验证的重建，不宣称已经复现。[冻结Final源码](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/blob/3a964e13f11a4e435aac01ffa14db0a7d2853720/flow/scripts/final_outputs.tcl)。

高精度报告9位小数，最多10000条/组、每endpoint一条最差setup路径；记录global top20、全部负slack endpoint、路径组、pin级cell/net增量及其合计、真实WNS/TNS、单位与check_setup覆盖报告。WNS/TNS须匹配-0.161583/-7.08646（容许原JSON舍入误差5e-6 ns），不同endpoint数须等于51；不一致则STA_EXTRACTION_GATE=HOLD。提取通过仍保留TIMING_GATE=FAIL，不把已有时序违例掩盖为验收PASS。

## Formal语义与判据

Golden读取冻结原RTL；Gate读取已审核6_final.v，分开重置Yosys设计容器、分别展开再组合，保留两侧规范化身份。read_liberty不使用-lib/ignore选项，完整导入function/ff模型；功能buffer端口直连不是blackbox，未驱动或未知模型必须HOLD。[Yosys官方read_liberty定义](https://yosyshq.readthedocs.io/projects/yosys/en/v0.51/cmd/read_liberty.html)。当前库已从冻结提交只读获取并核验Git blob；39类单元的实际原生导入覆盖将在运行时判定。

契约：仅harness的boot计数器初始化0，强制两次共同同步reset边沿；gold/gate数据状态保持独立、任意定义的二态初始值，不强制置零或假设FSM状态位同名对应。随后reset、req_msg、req_val、resp_rdy全部自由；覆盖req_rdy、resp_val和resp_msg全部18位，不用握手mask忽略输出，也检查输出未定义值。证明域是两次reset之后的所有未来同步行为，不是任意未复位初态或物理延迟等价。该复位契约须随下一轮授权审核。

使用带basecase的sat -tempinduct，无skip/baseonly/inductonly/prove-x；有限步成功不获得PASS。只有命令退出0且实际日志包含无界归纳成功标记，且模型、时钟、输入身份与范围检查全部通过，才记录PASS_RESET_CONTRACT_UNBOUNDED。最大归纳长度32不是“证明32周期就PASS”；无法建立归纳不变式或5分钟超时均UNKNOWN/HOLD。[Yosys官方SAT定义](https://yosyshq.readthedocs.io/projects/yosys/en/v0.51/cmd/sat.html)。文档只用于设计命令；冻结binary的实际能力尚未执行核验，不能以离线检查宣称Formal PASS。

## 身份

- ORFS commit：3a964e13f11a4e435aac01ffa14db0a7d2853720。
- OCI：openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9。
- ODB：2707181d3787009955eeb245acfc02fffd3e5c570c8e391aa6b1d2502fa415c4。
- SDC：112a077b756cada0fab67b2061733207a9cd7ac99b3e98454cabcad5aec7aa77。
- Final netlist：0d95240b149d075713b919c9bc3d059e296272da95331dc25635ff17016eed9a。
- 原RTL：5009f224876d39e5e77e59ee1528cb0d2a03697251f0971b77cf3e8b0426dd3e。
- Liberty：8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1，Git blob 90e4afb274cfc6514c587c434c77903d554117d1。
- RCX rules：2f65fafbe2c704b378563c53a680b93cef080c2799997019d43df7d1e5a563e9。
- setRC.tcl：521df813bf4da9d7400df33e3f680c9a328cc720830dbfca1188083741503fa5。
- OpenROAD：7d11382dd5197f40858da92a7ac7c4e32fdeb3f9985a04e77a04e61e4fbfc96e。
- Yosys：5cd52bc790d39b1e59a88112e9132ef8de338c2a26e4b0df8222d937e65bab92。

实际执行时还会记录Python身份、二进制版本、运行commit/run、脚本SHA、功能模型JSON、规范化两侧、证明脚本、每份报告/结果的SHA256与大小；token仅用于host恢复公共Artifact，不传入容器或输出。新文件SHA256如下（报告自身不自引用）：

- .github/workflows/final_netlist_acceptance.yml: 9c160757077c6ba48cca2d680f023afc708be50559fe10bc789c2e2d58b545f9
- acceptance/verify.py: 694b13ec1d4f198920ee402d853b976f312895a760f1d0368dd35aca4d55824d
- acceptance/sta.tcl: 146d5b04b39d197ae39d924d5c71139f09c333e8ceb79a7ebd2f38b174f69f6a
- acceptance/miter.v: 6f0f4600f2a8004427e8381d39c246306de54754b5993bbcdd55180c5097d824
- acceptance/run.sh: 009a2ff4fea1f7f0f02479e87b907f296983640870676e377ed224cd9c863f3d
- tests/test_acceptance.py: 128695b0b3686726eb0e5c4ed9f143947ded1d81058ad6ed389961cd92f60caa

## 离线结果、风险和成本

15项新增测试全部通过；全套34项中33通过，1项既有Linux信号测试跳过。验证覆盖错误ZIP/路径、缺失功能模型、buffer功能直连、未驱动端口、BMC不升格、非零/超时不PASS、STA参考/endpoint覆盖与高精度cell/net分离。YAML/actionlint、所有嵌入Bash段及run.sh、Python AST、Tcl语法/初始化stub检查通过。miter接口与契约已静态审阅，但原生Verilog/Liberty/SAT/OpenROAD集成未执行；不将stub或单元fixture当作真实工具验证。

风险：冻结binary命令/输出格式与文档不同、function/ff导入或clock/latch规范化不支持、FSM重编码导致归纳不收敛、RC重建与Smoke不匹配、Artifact在2026-10-26之后可能过期（恢复失败即HOLD，不能重跑Smoke取代证据）。本次测试验证退出码/标记处理，不构成实际顺序证明。Formal若缺失能力或模型，不换容器、不安装新引擎、不增加实验次数。

本轮EDA成本0；未来最多一次标准免费runner job、10分钟上限，Formal实际耗时与Codex费用NOT_AVAILABLE。SHA检查失败时尽早停止，避免大镜像或证明浪费。现有TIMING_GATE=FAIL和Formal未执行状态均保持，Baseline Run2仍NOT_RUN。没有额外研究控制器或Agent开发。
