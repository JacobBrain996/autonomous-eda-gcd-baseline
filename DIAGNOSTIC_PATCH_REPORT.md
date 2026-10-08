# DIAGNOSTIC_PATCH_REPORT

任务：CTS_LEC_DIAGNOSTIC_PATCH_PREPARATION_V1
日期：2026-10-08。仅本地准备；继承现有根因报告，不重复 Run 1 基础审计。

## 结果
DIAGNOSTIC_STATIC_GATE=PASS_OFFLINE
DIAGNOSTIC_SCOPE=ISOLATED_FROZEN_IMAGE_CTS_POST_REPAIR_LEC_REPLAY
EXPECTED_CLOUD_RUNS=1_INITIAL; UP_TO_2_ADDITIONAL_SEPARATELY_AUTHORIZED
ROOT_CAUSE_STATUS=PARTIALLY_LOCALIZED_HOLD
READY_FOR_DIAGNOSTIC_AUTHORIZATION=YES_STATIC_ONLY
AVX512_HYPOTHESIS=UNPROVEN_HOLD
CLOUD_BASELINE_RUN1=FAIL
CLOUD_BASELINE_RUN2=NOT_RUN

## 补丁内容
新增独立 cts_lec_diagnostic workflow，没有修改原 baseline workflow。
新增诊断 Make target、OpenROAD/Tcl replay entry、exec hook、Python进程观察器、
Run 1 artifact恢复、CPU对比、有限console记录、离线测试。
原有13个文件、冻结上游文件和Run 1 ZIP都保持原样；没有git add/commit/push。

Tcl hook观察实际 Kepler执行路径与其后读取4_rsz_lec_check.log的grep调用；无关exec仍调用原命令。
grep不经过Python包装，单独保留argv、errorcode/errorinfo与grep二进制散列，避免误归因于Kepler。
捕获 -errorcode/-errorinfo 后 return -options传播失败，不吞掉错误。
Python包装实际Kepler进程，分开记录 stdout/stderr、argv、PID、退出码/信号、
resolved binary SHA256与可获得的Build ID。core禁止；opcode/PC默认null。
没有strace或权限不足时不安装/提权，明确保留HOLD。
所有hook与Python/OpenROAD执行身份在runtime hooks.json中记录。

静态 DIAGNOSTIC_FILE_MANIFEST.json列出各补丁文件SHA256、大小、角色、
原13文件散列和冻结实验输入Git blob身份。清单自身不自引用。

## 离线验收
- YAML 1.2解析、actionlint 1.7.7检查。
- Bash -n，包括workflow run blocks。
- Python AST，Tcl由现有8.6解释器执行mock测试。
- 12个单元检查：11通过，1明确跳过（真实Linux SIGILL集成）。
- 测试覆盖：双流输出、非零退出不被成功覆盖、截断后的pipe排空、
  wall timeout、信号映射、Tcl errorcode/errorinfo与成功值传播、
  正确Run 1网表恢复、错误archive拒绝、console大小限制、ISA条件拒绝。
- 原始输入/旧文件差异审计；仅新增诊断文件，未改旧13文件。
- 不依赖本机Docker/WSL，也没有执行Kepler/OpenROAD或GitHub jobs。

Linux process/strace/core-limit语义、容器集成、Make目标完整展开、
OpenROAD直接LEC重放与artifact上传均未运行，因此 runtime gate=NOT_RUN。
PASS_OFFLINE不是诊断成功、修复成功或baseline成功。

## 已知观察差异与风险
- Run 1缺失原LEC YAML，本补丁重建配置；库过滤和路径来自冻结源码，
  但不能声称字节级复制未保存的原配置。
- Python observer和可选strace改变父子链/PID及时间行为。
  Tcl CHILDKILLED可能指observer；必须结合process.json与跟踪定位真正工具。
- 输出会有明确截断，文件/内存/CPU上限可能造成新失败。
  限制导致的信号、ENOSPC、截断必须标HOLD，不作为原SIGILL根因证据。
- 默认禁止core导出，因此若strace无法提供可解释的fault PC/opcode，
  AVX512_HYPOTHESIS继续UNPROVEN_HOLD。
- LEC replay通过只证明该次局部检查通过；原CTS报告已有setup violation，
  原physical/timing/artifact gate不因局部replay改变。
- 零付费约束：只用公开标准runner，artifact存储仍须在授权时核验。
- 原archive过期/下载身份不符、runner ISA变化或诊断权限不足时停止，
  不静默换版本、不随机重试。

详细入口、资源上限、阶段、科学判据和费用见 DIAGNOSTIC_EXECUTION_PLAN.md。
本轮到此停止，等待D1诊断授权。
