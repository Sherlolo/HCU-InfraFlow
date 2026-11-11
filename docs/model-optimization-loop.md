# 模型优化闭环

`model-loop-start/step/status/report` 是主控使用的持久协议。执行仍复用 `command-run` / `command-group-run` 与资源租约；Agent 读取每步的 `next` 继续工作。模块不会自行猜测模型启动命令，也不将记录成功视为 HCU 实测。流程仍受原有 flow 独立复核约束。


## 本仓 Skill 协作与优化方法

模型循环由 `$hcu-infer-model-optimize` 协调；**Prof 采集与分析调用本仓 `$hcu-infer-analyze-and-optimize`**，由该 Skill 对接上游 profiler 和 TraceLens，返回当前 analysis/capture/原件。模型循环不调用 TrainFlow 的脚本或 `tracelens-report` 等外仓 CLI。

HCU 适配、性能或故障问题先使用 `$hcu-knowledge-search` 的检索流程，再核当前分支的消费者、父依赖锁和真实加载制品。执行检索使用本仓 `knowledge-bind/query/read`，只将 HCU-Knowledge 的资料目录作为输入；不要求其 `kb.py` 或其他工作流 checkout。适用证据复用，版本/问题变化才重查；不自动更新大库。见 [知识与源码](../skills/hcu-infer-model-optimize/references/knowledge-and-source.md)。

从 TrainFlow 转化的闭环包括：固定初始/最佳/候选；先核引擎原生能力与容量；本仓 Prof 归因；按热点/依赖/融合和性能上限排序；模型内外同条件对照；低成本初筛后正式验收；候选组合重测；停滞复查机制与有证据的停止。具体推理选项见 [推理机制](../skills/hcu-infer-model-optimize/references/inference-mechanisms.md)，证据刷新与复用见 [迭代决策](../skills/hcu-infer-model-optimize/references/iteration-decisions.md)。这些是 Agent 的实施方法，不能将文档中的方法名称当作未实现的 CLI 字段。

同一假设内部的参数点通过 `explore` 留存，选出的候选才提交 evaluate。模型循环现在使用 schema_version=2：同时要求短/长输入及单请求/并发精度覆盖、当前候选的优化后 Prof、质量与性能双门禁、真实独立 flow 复核和本轮执行的恢复证明。初筛数据只展示收益，不形成有效性结论。

## 固定输出结构

每个成功的 step 自动更新总报告和本轮目录，包含进行中、失败、回退和中断状态。目录由模块生成，不再要求 Agent 临时设计目录或手工补齐索引。

```text
WORK/modules/model-loop/TASK/
├── REPORT.md                     # 每步更新：阶段、质量、Prof、决策、增量/累计主指标
├── state.json / manifest.json
├── history/revision-000000.json  # 可重建的状态视图；Store artifact 为不可变原件
├── baseline/                    # 初始输出 oracle、性能和部署记录
├── baseline-failures/0001/       # 启动/基线失败也保留报告与原件
└── iterations/0001/
    ├── REPORT.md / iteration.json / manifest.json
    ├── explorations/0001/        # 每次 explore 的报告、改动、说明、可选初筛数据
    ├── quality/                 # inputs.json、result.json，包含四种精度覆盖
    ├── performance/             # inputs.json、result.json、cumulative.json
    ├── prof/before/             # analysis.json、capture.json、原始 rank trace
    ├── prof/after/              # 优化后的同候选 Prof，保留 .json/.json.gz 原字节
    └── evidence/                # 直接引用的日志、结果和其他原件
```

每轮报告说明改了哪些文件/符号、为什么改、相对上轮最佳及初始基线提升多少、精度是否通过、优化后 Prof 是否齐备、是否保留和缺失原因。未执行的精度检查与未采集的 Prof 分别写 `not-measured` / `not-collected`，不能用空文件或成功标签补造。可运行候选应采集优化后 Prof；构建失败、精度失败后恢复或用户中断导致无法采集时，目录保留缺失状态和原因，候选不得标为有效。

`manifest.json` 列出相对文件位置、原始 artifact SHA256 和生成文件的字节哈希。原始 trace 从 Store 导出，即使最初采集路径已不存在也可重新生成报告。报告目录用于离线审阅直接证据，不是完整 SQLite Store、模型权重或外部源码仓库的备份。

```bash
hcu-infra-agent --workspace "$WORK" model-loop-report TASK --destination /delivery/model-optimization
```

destination 必须为空/新目录，或属于同任务、同 context 的既有导出。活动 SQLite Store 继续放在节点本地；共享盘可以接收这个导出。旧 v1 loop 保留只读报告/导出能力；继续执行新规则应使用新任务并重新建立明确的精度合同，不能把历史 pass 自动升级为新规则通过。

## 精度的最小场景矩阵

起始 `quality_coverage` 默认如下，并在整轮任务中冻结。质量合同必须显式带相同的 `coverage` 对象：

```json
{"short_input_max_tokens":128,"long_input_min_tokens":2048,"min_concurrency":2}
```

必须覆盖短输入单请求、长输入单请求、短输入并发、长输入并发四格。最小可以是6条请求（1+1+2+2），无需用昂贵完整质量集替代每轮轻量 smoke；默认2048只是轻量测试边界，任务有更长目标上下文时，应在开始时把 long_input_min_tokens 设置到有代表性的目标长度，必要全量质量集和 serving features 仍须单独满足。

每条 `samples` 除 `id` 与 `text` 或 `values` 外，记录：`input_sha256`、`input_tokens`、`concurrency`、`run_id`、`started_at`、`finished_at`。参考与候选的前四项必须相同，不能换短输入冒充长输入；时间使用每个 run 内一致的客户端时钟。并发场景必须至少有 min_concurrency 条同长度类别请求的时间区间重叠；只改并发标签、实际串行请求不会通过。它证明请求级并发，不自动证明 GPU 内部 batch/rank 覆盖，后者应补充调度原件或必需 feature。

空文本不能充作正确输出；数值精度仍按冻结的 atol/rtol 和容差依据比较。样本/覆盖/特性任一失败，性能即使变快也进入失败处理。每条测量仍需真实执行及原始 evidence；框架校验记录和引用一致性，不能独立认证调用者声明的硬件真实性。质量合同模板见 [quality-smoke-contract.json](../examples/modules/quality-smoke-contract.json)。

## 生命周期与边界

```text
simulation → baseline → profile → candidate → review → profile
                 ↓                     ↓        ↓
             adaptation             rollback ← reject
                 ↓                     ↓
              baseline           profile / stopped
```

保留三个对象：初始输出 oracle/性能、已复核最佳组合、当前候选。输出每轮对初始 oracle，性能每轮同时对当前最佳和初始基线比较；不累积数值漂移，不将若干局部加速相加。更新模型、tokenizer、量化、workload、driver 或实质部署身份时新建任务；旧记录保留，不能重置 context 后重用。

流程按 `max_iterations` 和连续无收益 `max_no_gain` 有界停止。常规 `stop` 必须说明原因，未处置候选先拒绝并验证回退。用户明确要求中断时，先停止并核清实际执行，再提交 `interrupt`：verification artifact 必须含 task/context/context_epoch、当前 loop_revision、status=stopped、execution_stopped=true 和非空原始 evidence；仍有 started/unknown operation 时拒绝。中断记录保留为 incomplete/interrupted，不声称已恢复最佳服务，不自动再启动实验。预算耗尽不能用 interrupt 绕过回退验证。

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

实施方向使用 `route=native|fusion|triton|tilelang|hip|gemm`；native 调用阶段优化 skill，其余调用 `hcu-infer-operator-develop`。先用 `action=explore` 登记 plan、route、candidate_snapshot、summary、changes 和 evidence。changes 每项含 path/description，可加 symbol；notes 保留假设、尝试、失败及适用范围。一个正式候选内可多次 explore，各次记录和旧快照都保留，当前评估必须对应最后登记的候选。示例见 [loop-explore.json](../examples/modules/loop-explore.json)。

可选 screening 指向初筛 artifact：包含 context/candidate_snapshot、hardware_executed、candidate_path_exercised、profiler_off、executed、status、evidence，以及 metrics 数组。每行用 scope=model 或 operator，前者支持四项 serving metric，后者只用 time_ms；同时给 scenario、baseline/candidate 的配对数组。可保留单次值，报告明确标为 unverified-screening。它不能替代精度、三次正式性能或 Prof，局部算子加速也不能当模型收益。

实现后还需采集该候选的 Prof。调用 `prof-analyze` 时提供 candidate_snapshot，模块将其登记为 `candidate-analysis`，不会替换产生原计划的优化前 analysis。随后 retain capture：包含 context/context_epoch/candidate_snapshot/analysis、hardware_executed=true、candidate_path_exercised=true、executed>0、status=complete 和全部 rank trace/采集日志 evidence；不能有失败或跳过的必需项。见 [candidate-prof.json](../examples/modules/candidate-prof.json) 和 [candidate-capture.json](../examples/modules/candidate-capture.json)。

`action=evaluate` 提交 plan、route、quality_inputs、performance_inputs、candidate_analysis 和 candidate_capture。质量/性能同一候选快照，质量对初始 oracle，performance baseline 对当前最佳，合同及覆盖要求冻结。优化后 Prof 必须匹配当前快照和最新 candidate-analysis、原有 rank/group 覆盖；不能拿优化前或此前迭代的 trace 字节重新贴标签。

缺优化后 Prof 时会保留本次评估和数据，但留在 candidate/incomplete，不能进入 review/keep。质量或性能失败进入 rollback；质量通过和 Prof 齐备只是有效性的必要条件，最终还要满足性能和独立 review。正式性能仍至少三次 profiler-off 配对重复，保留 TTFT、TPOT、P95、吞吐和 SLA；初筛数值不纳入正式收益。另算相对初始基线的累计指标，累计回退也拒绝。

### 接受、拒绝和继续

通过 evaluate 只进入 review。先用 `optimization-check` 生成精度与性能报告，再 `flow-submit`、独立 `flow-review`、`flow-advance`；循环中的候选 target 用 `iterate`。`action=keep` 携 `flow_round`，仅接受当前最新且 advanced 的轮次，匹配候选快照和原始比较输入，并重新核对当前报告未被替换。loop 不代替独立复核，也不会隐式完成整个 flow。

质量/性能失败自动进入 rollback。构建失败或复核不接受时 `action=reject` 并说明 reason；candidate 阶段另需 failure 原件。先通过算子模块 rollback 或部署命令卡恢复最佳快照，再 `action=rollback` 提交 verification artifact；必须包含当前 context、最佳 candidate_snapshot、hardware_executed、实际 executed、candidate_path_exercised、成功状态、非空 evidence，且不能有失败、跳过或缺失检查。verification 还必须包含 `operation`，引用在本轮进入 rollback 之后执行完成的同任务 command-run 操作，并将该操作所有原始日志/命令 evidence 纳入验证原件；旧基线或旧回退结果不能重放。只有恢复验证成功才进入下一轮或预算停止。

不调用 `stop` 绕过未恢复候选。对现场无写入的失败也验证当前服务仍为最佳配置。多个算子可独立分析实现，但共享设备测量、耦合修改和组合验收由同一主控串行化。未知远端结果先 reconcile，恢复仍由任务的 recovery_owner 负责。

## 验证范围

`tests/test_model_loop.py` 使用显式构造的合成协议数据，覆盖真实 flow API 的复核状态转移、不可变 oracle、选型与设备数、基线失败转适配、回退和预算、过期证据。它验证协议行为，不是任何模型在 HCU 上的性能或精度结果。真实任务还必须运行对应模型、算子和多卡验证。
