# Native acceptance readiness — VeriEDA bridge

本报告取代早期 FINAL_NETLIST_ACCEPTANCE_PREPARATION.md 的当前就绪结论；旧报告保留历史版本及当时的SHA，不能用它证明修订代码已经过原生验证。

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
