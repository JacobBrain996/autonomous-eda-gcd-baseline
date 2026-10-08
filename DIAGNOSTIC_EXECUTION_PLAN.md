# DIAGNOSTIC_EXECUTION_PLAN

日期：2026-10-08。当前仅离线准备；任何发布、dispatch 或 rerun 均未授权。
本方案继承 ROOT_CAUSE_STATUS=PARTIALLY_LOCALIZED_HOLD，
SIGILL_SOURCE=CTS_POST_REPAIR_LEC_SUBPROCESS_CHAIN，
AVX512_HYPOTHESIS=UNPROVEN_HOLD。

## D1：直接复现局部 LEC（首选；1 次受控云端 job）

入口：.github/workflows/cts_lec_diagnostic.yml，仅 workflow_dispatch，
公开仓库标准 ubuntu-24.04，最多 15 分钟，无付费/larger/self-hosted runner。

新 runner 必须：
1. checkout 已批准的诊断补丁及现有 13 文件。
2. 用仅 actions:read 的 GitHub token 下载 Run 37756530984 的唯一未过期 baseline artifact。
   token 仅在该步骤环境中使用，不写文件、不打印、不传入 Docker。
   下载 ZIP 上限 8 MiB，必须匹配原 ZIP SHA256
   9caa14593d6c9db005db2807d8fddd7558c183ccbdc2b9f9faedf4cd1f4481d5。
   artifact 不存在、过期、多个候选或字节身份不符即 HOLD；不得自动上传本地 ZIP替代。
3. 仅恢复两份 LEC 网表，逐字节核验冻结散列；不恢复大范围旧 runner 工作区。
4. 获取精确 ORFS commit 与 OCI digest，执行既有 RTL/testbench 身份检查与资源预检。
   运行前再次检查 CPU AVX2 / 非 AVX512 暴露状态，保存与 Run 1 的 CPU/model 差异。
   若出现 AVX512 则 HOLD，不随机重试。模型不相同但 ISA 条件相同仍需在解释时说明。
5. 将冻结 flow 只读挂载。额外 Makefile 只新增打印目标，得到实际有效的
   LEC_CHECK、SEC_CHECK、KEPLER_FORMAL_EXE、LIB_FILES、REMOVE_LIBS_FOR_LEC。
   只允许 LEC_CHECK=1、SEC_CHECK=0；其他状态 HOLD，不主动关闭验证。
6. 用冻结 formal_check.tcl 的 write_lec_script/run_lec_test 重建 4_rsz_lec_test.yml。
   注意：Run 1 未保存该 YAML，因此这是配置重建，不是原始 YAML 的字节级重放。
   库列表来自同一冻结 GCD config，路径映射和新增 hook 进入审计清单。
7. 在同一固定镜像的 OpenROAD Tcl 解释器内，执行一次局部 LEC。
   不重新执行 RTL simulation、synthesis、floorplan、placement 或 clock_tree_synthesis。
8. 回收 effective.json、YAML、两份输入网表、formal.stdout/stderr、formal log、
   executable.notes、实际 binary SHA/Build ID、原始 argv、Tcl errorcode/errorinfo、
   process.json、可用 strace 文件、hooks.json、container 返回码。
   即使失败也尝试上传诊断证据；保留时间 1 天。

科学判据：
- 原始 Kepler 子进程 returncode=-4 / signal=SIGILL，或进程跟踪明确将 SIGILL 关联到
  Kepler 实际 PID/execve：可加强 executable 定位。
- strace 记录的是 tracer PID 或其子进程，必须按 -ff 文件和 execve 事件区分；
  不能把 Python observer 或 tracer 的 PID冒充原始工具 PID。
- Tcl options 是观察后的真实 exec 结果；Python observer 被同一信号终止时，
   Tcl CHILDKILLED PID是 observer PID。process.json 保存实际直接 child PID，两者不同。
- 后续grep读取formal log的错误也被hook记录，但不包装该exec；其PID与Kepler观察器PID区别处理。
- Kepler 自己再启动子进程时，未取得跟踪便不能唯一识别后代故障 ELF。
- 同一 pair 在同一镜像中 PASS 仅表示 LEC_REPLAY_PASS，不代表原 CTS/RTL→GDS baseline PASS；
  应检查配置、CPU、线程/资源与进程包装差异，不能宣称原失败已修复。
- 没有映射到故障二进制的 fault PC/opcode：AVX512_HYPOTHESIS 始终 UNPROVEN_HOLD。
  本补丁不启用 core/GDB，不会根据 signal 或静态 ISA flags宣布 AVX-512 根因。
- 任何截断、资源限制造成的 SIGXFSZ/SIGXCPU/SIGKILL、timeout、ENOSPC，
  都可能使诊断失真，必须报告 HOLD/限制干扰，不归因于原 SIGILL。

## D2：必要时重建前序 CTS（条件实验，另需授权）

仅在 D1 不复现或配置差异无法排除时考虑。D2 尚未提供自动运行入口。
新 runner 上重新 clone 冻结 ORFS、pull 固定 image；公开 GCD RTL、Nangate45
库/LEF/RC、原始 config.mk/SDC/PDN/rules/QoR 均保持不变。
重建阶段：synthesis → floorplan → placement → CTS repair → LEC。
不可假设上一次 runner 文件或容器继续存在。

也可复用经过完整 manifest/散列核验的 Run 1 3_place.odb、3_place.sdc；
同时需要同工具 image、LEF/lib/RC、相同 effective Make/Tcl 参数。
ODB 与库/工具身份必须一致，不能把单个 ODB 当作自包含实验。
CTS 输入副本与工作输出隔离，不覆盖原始 ZIP；如启用 CTS snapshot，
它是观察性新增参数，必须列入该次实验 manifest。

判据：若原 frozen CTS 路径在保留 LEC情况下同位置复现，并能取得 PID/exec身份，
再定位 exact executable；否则继续 HOLD。不能靠换镜像/放宽 SDC改善结果。

## D3：LEC_CHECK=0 独立对照（可选，另需授权）

本补丁没有关闭 LEC，也没有将该对照并入 D1。
只有单独批准时才使用
make DESIGN_CONFIG=./designs/nangate45/gcd/config.mk cts LEC_CHECK=0
并标记
FORMAL_EQUIVALENCE_GATE=NOT_RUN_WITH_APPROVED_DIAGNOSTIC_BYPASS。
该对照只检验 LEC路径是否是触发条件，不能证明 AVX-512；
不能升级原 baseline 为 PASS，也不能永久保存为默认参数。
其他设计/时序/QoR参数不变。

## 资源与数据范围

- D1：2 vCPU container quota，6 GiB RAM，128 PID，network=none，read-only root/source。
- 继承拉取前 ≥10 GiB、拉取后 ≥4 GiB磁盘预检，以及标准公开 runner RAM检查。
- 工具/日志/跟踪工作区：tmpfs 总上限 128 MiB；/tmp 单独 64 MiB。
- stdout、stderr、console各最多 8 MiB；读完并丢弃超限部分，避免 pipe堵塞；
  truncated 会明确记录。forwarded streams 也截断，因此属于可审计观察差异。
- tool/trace单文件 RLIMIT_FSIZE=8 MiB；整个 tmpfs硬容量约束128 MiB；
  不对大日志使用无上限捕获。
- Python观察器 wall timeout=150 s，CPU上限120 s；Docker入口 wall timeout=300 s；
  job整体15分钟。超时只终止本次隔离进程组/容器所属工作，不能 PASS。
- core 上限 0 bytes；不导出 core、完整进程环境、完整内存、密钥或宿主凭据。
- 诊断导出仅来自全新的128 MiB工作区，拒绝 symlink；
  单文件/总量校验；宿主 console另8 MiB，环境小文本作为额外开销。
  artifact预算144 MiB，发布/运行前需确认剩余存储/零付费预算。
- strace仅在镜像已有且 /bin/true 预检成功时使用，范围仅 exec/fork/wait/signal，
  不加 -v，不导出 execve环境。缺失/拒绝则记录 HOLD并保留直接进程观测。
  不安装工具、不增加 ptrace能力、不放宽 seccomp/security。

## 预计次数与费用

首先只申请 D1：1 次 job。D2/D3各是额外1次，条件触发且分别重新授权；
不自动连跑，总计划最多1+2次。它们均不计为 baseline Run 2。

公开仓库标准 runner计算费预计 $0；larger runners即使在公开仓库也收费，
本补丁不使用。Artifact/Packages共享存储可能受账户额度与超额政策影响，
本轮没有核验余额或变更账单配置。144 MiB、保留1天时，若全部存储均按
$0.25/GB-month收费，示例上限约 $0.0012/次（实际按月份小时、额度与平台规则结算）。
这不是收费授权。若零付费预算/可用存储无法确认，应 HOLD。
[GitHub官方计费说明](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。

## 下一次授权范围

应明确批准：仅发布本诊断补丁，手动触发 D1一次，下载/回收新的diagnostic artifact。
授权前不 push/dispatch；D2、D3、任何诊断工具安装或权限扩大均需另行授权。
