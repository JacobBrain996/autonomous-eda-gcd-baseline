# D1B 最小执行计划与离线验收

日期：2026-10-09。当前只准备补丁，无 push、dispatch、rerun、D2/D3 或 Baseline Run 2。

## 权威 D1 结果
Run 37795979593 / artifact 11558521840 / commit f0c29017c705aab3eb6f7ec14716bfe3727eca4b。
已下载至 evidence/d1-37795979593/D1-37795979593.zip，6,109 bytes。
GitHub digest / ZIP SHA256：
6d3b51af17f3b0c694820a2e11f055b1658267994964d9cca8a20f9679e48d36。
ZIP CRC通过，内部manifest的11个文件大小与SHA256全部匹配。
API步骤确认 source/image 与 LEC replay均 skipped；ZIP无process/effective/formal输出。
CPU：Run 1=AMD EPYC 7763，无AVX-512；D1=Intel Xeon Platinum 8370C，有AVX-512。
D1_RESULT=HOLD_CPU_ISA_MISMATCH。它不是一次Kepler失败，也不是局部LEC成功。

## 最小变更
修改4个已有文件：check_cpu.py、seal.py、诊断workflow、旧CPU单元断言；
新增分组单元测试、本计划和D1B_FILE_MANIFEST.json。
不修改Kepler/OpenROAD执行器、Tcl错误传播、数据/日志/core资源上限或baseline workflow。
旧DIAGNOSTIC_FILE_MANIFEST.json及旧报告保持为D1历史，不覆盖；D1B发布应使用新manifest。

## 一次运行、按实际CPU进入一个组
- NO_AVX512：x86_64，具有AVX/AVX2/xsave，未暴露任何AVX512 flag；
  仅是原ISA类别的复现候选，不等于同型号或相同执行环境。
- WITH_AVX512：同一基础要求，暴露avx512f；作为跨ISA对照。
  记录每个实际暴露的AVX512子集，不能假定支持所有AVX512扩展。
- 缺少架构、完整型号、必要flags，或出现有AVX512子flag却没有avx512f等不一致信息：HOLD。
- 非指定公开仓库、非GitHub-hosted Linux/X64、缺少run/commit身份、诊断ID不符：HOLD。

完整原始lscpu、CPU型号、全部kernel-exposed flags、ISA新增/缺失、型号是否相同、
run/attempt/commit/runner身份均回收；identical_execution_environment恒为false。
工具身份沿用runtime hooks.json、process.json、effective.json、
image-inspect.json中的实际SHA256/Build ID和固定image/source身份。
若LEC未执行，则工具运行数据缺失，必须标NOT_AVAILABLE/HOLD，不能宣称已采集。

同一个标准ubuntu-24.04 runner只会属于一个组。
本次后续授权只允许一次job、一个局部LEC调用，不能循环dispatch寻找另一个CPU，
不能保证一次运行产生一对跨ISA结果。若未来需要另一组，必须重新授权独立实验。

## 保持的实验与资源
ORFS=3a964e13f11a4e435aac01ffa14db0a7d2853720。
Image=openroad/orfs@sha256:7fbb16f7aaf3caa170ea308c1bd833defc7fdf1f5316303dce6a0e6eeb6deee9。
GCD、Nangate45、原SDC/PDN/QoR配置、LEC_CHECK=1、SEC_CHECK=0均不变。
标准免费公开runner，job 15分钟，局部重放入口300秒，原2CPU/6GiB/128PID、
128MiB工作区、8MiB单流/文件、144MiBartifact预算、core=0、network=none均不变。
仍需执行既有资源/证据/镜像身份门禁。不安装诊断工具、不提权、不更换版本。
只导出允许的CPU/GitHub身份字段；不导出完整环境、GH_TOKEN、凭据或无关内存。

## 判据
1. 有效工具确实执行且同次局部LEC返回成功：仅报告LOCAL_LEC_REPLAY_SUCCESS及所在组。
2. SIGILL：依据真实PID、original argv、binary SHA/Build ID、trace/errorcode归因，
   区分Kepler、后代、grep、observer及strace；没有对应信息继续HOLD。
3. NO_AVX512失败、WITH_AVX512成功只能增强ISA相关假设，不单独证明因果。
   CPU厂商/型号、完整flags及其他环境因素不同，都必须说明。
4. 未取得能映射到故障二进制的明确fault PC/opcode，则AVX512_HYPOTHESIS=UNPROVEN_HOLD。
5. 不关闭LEC、不放宽timing、不吞掉错误；局部诊断不改变Run 1 FAIL或Run 2 NOT_RUN。

## 离线验收
YAML 1.2/actionlint通过；Bash静态解析通过；Python AST通过。
19个测试：18通过，1跳过（Windows不执行真实Linux SIGILL集成）。
包括真实D1数据在新逻辑下进入WITH_AVX512，以及不可信/不完整环境继续HOLD。
未执行真实LEC、Linux容器集成或云端job。
差异与文件SHA256见D1B_FILE_MANIFEST.json。

NEXT_MINIMAL_ACTION：批准D1B补丁发布并手动触发一次分组局部LEC诊断。
ROOT_CAUSE_STATUS=PARTIALLY_LOCALIZED_HOLD。
