# 模型优化闭环

`model-loop-start/step/status/report` 是主控使用的持久协议。执行仍复用 `command-run` / `command-group-run` 与资源租约；Agent 读取每步的 `next` 继续工作。模块不会自行猜测模型启动命令，也不将记录成功视为 HCU 实测。流程仍受原有 flow 独立复核约束。


## 本仓 Skill 协作与优化方法

模型循环由 `$hcu-infer-model-optimize` 协调；**Prof 采集与分析调用本仓 `$hcu-infer-analyze-and-optimize`**，由该 Skill 对接上游 profiler 和 TraceLens，返回当前 analysis/capture/原件。模型循环不调用 TrainFlow 的脚本或 `tracelens-report` 等外仓 CLI。

HCU 适配、性能或故障问题先使用 `$hcu-knowledge-search` 的检索流程，再核当前分支的消费者、父依赖锁和真实加载制品。执行检索使用本仓 `knowledge-bind/query/read`，只将 HCU-Knowledge 的资料目录作为输入；不要求其 `kb.py` 或其他工作流 checkout。适用证据复用，版本/问题变化才重查；不自动更新大库。见 [知识与源码](../skills/hcu-infer-model-optimize/references/knowledge-and-source.md)。

从 TrainFlow 转化的闭环包括：固定初始/最佳/候选；先核引擎原生能力与容量；本仓 Prof 归因；按热点/依赖/融合和性能上限排序；模型内外同条件对照；低成本初筛后正式验收；候选组合重测；停滞复查机制与有证据的停止。具体推理选项见 [推理机制](../skills/hcu-infer-model-optimize/references/inference-mechanisms.md)，证据刷新与复用见 [迭代决策](../skills/hcu-infer-model-optimize/references/iteration-decisions.md)。这些是 Agent 的实施方法，不能将文档中的方法名称当作未实现的 CLI 字段。

同一假设内部的多个参数点留在实验记录，选出的候选才提交 evaluate。API 继续要求每个正式循环刷新 analysis、质量与性能双门禁、真实独立 flow 复核和本轮执行的恢复证明；初筛复用证据不能绕过这些要求。自动 REPORT.md/JSON 保存现有指标与状态，知识依据、源码解释和试参过程由 Agent 补充到当前任务报告/BOARD。

## 生命周期与边界

```text
simulation → baseline → profile → candidate → review → profile
                 ↓                     ↓        ↓
             adaptation             rollback ← reject
                 ↓                     ↓
              baseline           profile / stopped
```

保留三个对象：初始输出 oracle/性能、已复核最佳组合、当前候选。输出每轮对初始 oracle，性能每轮同时对当前最佳和初始基线比较；不累积数值漂移，不将若干局部加速相加。更新模型、tokenizer、量化、workload、driver 或实质部署身份时新建任务；旧记录保留，不能重置 context 后重用。

流程按 `max_iterations` 和连续无收益 `max_no_gain` 有界停止。显式 `stop` 必须说明原因，未处置的候选必须先拒绝并验证回退。预算耗尽是停止原因，不是达到硬件极限。每次成功 step 都更新私有 Store 下 `modules/model-loop/TASK/REPORT.md`；不可变 JSON artifact 保留全部指标、原件引用、拒绝原因和回退证明。

## CLI 与请求

```bash
hcu-infra-agent --workspace "$WORK" model-loop-start TASK loop-start.json
hcu-infra-agent --workspace "$WORK" model-loop-step TASK step.json
hcu-infra-agent --workspace "$WORK" model-loop-status TASK
hcu-infra-agent --workspace "$WORK" model-loop-report TASK
```

`loop-start.json` 见 [`examples/modules/loop-start.json`](../examples/modules/loop-start.json)。所有 step 都带当前 `revision` 和 `action`；旧 revision、并发写入、未核清的远端 operation、过期 context 不得继续。模块不会改动用户指定环境之外的服务。schema 输入可先通过 `artifact-add` 保存，后续使用返回的 SHA256，而不是外部路径。

### 仿真选型

1. 固定健康设备数量、模型身份、输入/输出长度、batch/并发、KV/计算 dtype；用已有 `simulate` 对有依据的并行候选逐个预测。
2. `action=select-strategy`，`candidates` 每项为 `{artifact, prefill_devices, decode_devices}`。artifact 必须是完成的 `simulate` 结果，包含成功 backend execution 和留存 stdout/stderr；程序从原始 stdout 重新核对 backend_output、评分/显存字段及实际生效参数，不能修改 summary 后沿用旧执行回执。设备用完整物理身份如 `node-a:0`，不能用重复的本地卡号掩盖跨节点差异。
3. 两阶段设备集合的并集大小必须等于起始 `gpu_count`；重合表示共享设备，互斥表示分离部署。当前拓扑适配按每阶段 `TP*DP*PP` 计卡、EP 为整除子组，CP 仅支持 1。其他引擎拓扑需要先实现适配器，不猜测乘法关系。
4. 只有 `memory_feasible=true` 的候选参与排序，未知显存可行性不自动通过。默认 `simulation_metric=throughput_tok_s`，也支持 prefill/decode latency；tail latency 必须实测。
5. 输出只是“已仿真候选中的预测最优”，不是全空间最优。显存峰值、最差 rank 余量、通信及 KV 分布须用真实短跑校准。启动配置必须实现选中的并行策略。

### 基线与适配

`action=baseline` 提交 `quality_inputs`、`performance_inputs`、`deployment` 三个 artifact。前两者使用现有 quality-check/performance-check 的输入结构，额外要求每条测量 `hardware_executed=true`，禁止 synthetic、缺失原件或预测充当运行。初始性能 baseline/candidate 必须为同一测量；质量可对独立参考输出。性能 policy 中 metric、max_regression、sla 固定，初始 min_gain=0，后续 min_gain 使用 loop policy。

`deployment` 记录 `{context,candidate_snapshot,simulation,prefill_devices,decode_devices,evidence}`：simulation 是已选候选的 artifact，设备分配必须与选型一致；evidence 是实际配置/加载及启动日志的留存原件，不能只有计划。Agent 检查日志里的生效并行组与预测输入一致。

服务无法启动时用 `action=baseline-failed` 加 `failure` artifact，失败对象包含当前 context、fail/incomplete 状态和原始日志 evidence。进入 `hcu-infer-model-adapt`。完成适配后重新提交 baseline，并增加 `adaptation` artifact；必须是 model-adaptation 检查生成、匹配 task/context/epoch/snapshot、`status=pass` 且 `ready_for_baseline=true` 的报告。不能以适配补丁完成替代运行基线。

### Prof → 候选

`action=profile` 提交当前 `prof-analyze` 返回的 `analysis` 和 `capture` artifact。capture 包含 `{context,candidate_snapshot,analysis,hardware_executed:true,evidence}`，必须绑定当前最佳快照，留存每个分析 rank 的原 trace。采集实际运行日志、PID、容器与设备也应放 evidence。模块只核对声明与原件身份，不能独立认证硬件真实性。

每轮重新采集，不能复用上一轮 analysis ID。Agent 检查 prefill/decode、shape/dtype/layout、实际 rank、graph、墙钟分母和覆盖未知项；重叠 kernel 时长不能直接求和为端到端成本。读取现有引擎调度、算子/库和上游能力后，通过 `optimization-plan` 写 observation/hypothesis/target/validation。

实施方向使用 `route=native|fusion|triton|tilelang|hip|gemm`；native 调用阶段优化 skill，其余调用 `hcu-infer-operator-develop`。详细专家 Skill 和框架集成由算子模块选择。融合需说明可省中间量、launch、契约和支持 guard；通信需区分等待、传输与关键路径暴露；GEMM 用真实 shape 分布决定调优，不先固定算子名单或扫全参数网格。

`action=evaluate` 提交 plan、route、quality_inputs、performance_inputs。必须同一候选快照、初始输出 oracle、固定 feature/质量合同；performance baseline 必须等于当前最佳的 candidate 测量。默认至少三次 profiler-off 配对重复，保留 TTFT、TPOT、P95、吞吐和 SLA，最差场景退化不可由平均数遮盖。另算相对初始基线的累计指标，累计回退也拒绝。

### 接受、拒绝和继续

通过 evaluate 只进入 review。先用 `optimization-check` 生成精度与性能报告，再 `flow-submit`、独立 `flow-review`、`flow-advance`；循环中的候选 target 用 `iterate`。`action=keep` 携 `flow_round`，仅接受当前最新且 advanced 的轮次，匹配候选快照和原始比较输入，并重新核对当前报告未被替换。loop 不代替独立复核，也不会隐式完成整个 flow。

质量/性能失败自动进入 rollback。构建失败或复核不接受时 `action=reject` 并说明 reason；candidate 阶段另需 failure 原件。先通过算子模块 rollback 或部署命令卡恢复最佳快照，再 `action=rollback` 提交 verification artifact；必须包含当前 context、最佳 candidate_snapshot、hardware_executed、实际 executed、candidate_path_exercised、成功状态、非空 evidence，且不能有失败、跳过或缺失检查。verification 还必须包含 `operation`，引用在本轮进入 rollback 之后执行完成的同任务 command-run 操作，并将该操作所有原始日志/命令 evidence 纳入验证原件；旧基线或旧回退结果不能重放。只有恢复验证成功才进入下一轮或预算停止。

不调用 `stop` 绕过未恢复候选。对现场无写入的失败也验证当前服务仍为最佳配置。多个算子可独立分析实现，但共享设备测量、耦合修改和组合验收由同一主控串行化。未知远端结果先 reconcile，恢复仍由任务的 recovery_owner 负责。

## 验证范围

`tests/test_model_loop.py` 使用显式构造的合成协议数据，覆盖真实 flow API 的复核状态转移、不可变 oracle、选型与设备数、基线失败转适配、回退和预算、过期证据。它验证协议行为，不是任何模型在 HCU 上的性能或精度结果。真实任务还必须运行对应模型、算子和多卡验证。
