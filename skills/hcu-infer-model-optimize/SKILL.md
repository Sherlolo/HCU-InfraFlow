---
name: hcu-infer-model-optimize
description: 在固定 HCU 卡数和服务负载下，协调知识检索、并行仿真、模型基线、本仓 Prof 分析、引擎与算子优化、质量性能复核及有界迭代，保存可追溯的模型优化报告。
---

# HCU 大模型推理优化闭环

## 定位、范围与阅读

在 `$hcu-infra-agent` 主控和既有优化阶段内推进同一任务。通过安装目录 `workspace.json.project_root` 定位本仓；源码版使用仓库根。按工程 `docs/skill-reading-map.md` 阅读当前模式入口，执行契约见 `docs/model-optimization-loop.md`，目录、资源和交付边界见 `docs/workspace-and-delivery.md`。任务 Store 与工程位置分别绑定，实际节点/容器映射先核实。

本 Skill 面向 `optimize/full`；只分析 Prof 转交 `$hcu-infer-analyze-and-optimize`，只做仿真按该任务范围交付。稳定发布与快速适配共用质量和性能门槛，执行基点、用户补丁和最终交付形式分别记录。新模型跑通、导出补丁或实现初版融合后，继续完成约定的优化验收。

工作流、检索适配和循环状态 API 均使用本仓 `hcu_infra_agent`。参考工程只用于理解方法，不调用其脚本、CLI 或依赖作者机器路径。实际 profiler、算子库和仿真器属于按任务显式绑定的工具；没有配置时如实记录缺口。

## 先查 HCU 知识，再核当前源码

遇到 HCU 相关适配、性能或故障问题，先用 `$hcu-knowledge-search` 搜索大知识库（按工程、错误/符号、shape、gfx/DTK 和机制组合），再核对当前分支源码。已有适用证据可复用；不是每条命令重复搜，也不自动更新大知识库。

按 [知识检索与源码复核](references/knowledge-and-source.md) 执行。知识库根由 `knowledge_root` 提供，作为只读资料源。本任务使用本仓 `knowledge-bind`、`knowledge-query`、`knowledge-read` 完成文本检索和阅读，不依赖知识工程的 `kb.py` 或 TrainFlow 工具。已安装 `$hcu-knowledge-search` 时将这些入口作为其本次检索工具；未安装时按本仓指引完成可用检索并说明 Skill 未加载。命中后读正文、固定出处与适用条件，再追消费者、父依赖锁、实际分发和加载制品；搜索片段不能代替源码和实测。

## 优化闭环

1. **固定比较契约与预算。** 保存模型/权重、tokenizer/chat template、量化与 KV dtype、采样参数、输入输出长度分布、并发/请求到达方式、cache 冷热、引擎基点/候选快照、驱动和设备身份。约定目标场景的 TTFT、TPOT、P95、吞吐、失败率、质量/服务特性和停止预算。最初数值 oracle 与性能基线不可覆盖，另存已复核最佳和当前候选。
2. **容量与并行先形成假设。** 在给定健康卡数下用本仓 `simulate` 比较少量合法方案，核实际 TP/PP/DP/EP/PD 分组、权重/KV/图池/工作区与最坏 rank 余量。按 `model-loop-start` 和 `select-strategy` 请求记录选型，真实短跑校准。资源足够优先完整模型；代理模型的结果只用于其声明范围。当前选择器 CP=1 等边界见模块文档，不猜支持能力。
3. **建立基线并核查原生能力。** 运行无 profiler 基线；启动、加载或质量失败先检索知识、核源码，转 `$hcu-infer-model-adapt`，适配通过后重新测基线。原生能力检查按 [推理机制选择](references/inference-mechanisms.md) 覆盖调度、attention/KV、编译/graph、MoE、通信和 host 路径。区分已命中、未启用、依赖缺口、在途 PR 与不适用；候选改动必须有当前 Prof/源码依据，不在基线后无记录地打开一组开关。
4. **Prof 明确交给本仓分析 Skill。** 调用 `$hcu-infer-analyze-and-optimize`，交付当前最佳快照、固定 workload、prefill/decode/PD、rank 组、trace 或采集入口及私有输出目录。由它调用 `llm-torch-profiler-analysis`，按问题使用 TraceLens，并通过本仓 `prof-analyze` 产生当前 analysis。接收 trace 原件、窗口/shape/覆盖、上游报告与辅助工具回执后，再提交循环的 `profile` 请求。模型优化 Skill 不直接绕过该分析入口调用参考工程的 profiler 脚本。
5. **按贡献、因果与可兑现空间排序。** 依据 [迭代决策](references/iteration-decisions.md) 维护“热点—源码—上限”“依赖—重叠”“融合—契约”关联记录。墙钟、GPU 服务时间和区间并集分开，保留通信、空泡和未知项。高贡献但上限未知先补证；当前首要热点已足够明确即可推进，不等全部表格填满。说明跳过更高项的理由，完整任务交代约定覆盖目标及其缺口。
6. **低成本筛选，逐层实施。** 在 `optimization-plan` 记录 observation/hypothesis/target/validation、引用原件和停止点。先筛适用性与容量，再局部编译、正确性、dispatch 和短时对照；有希望保留的候选才做正式场景回归。同一假设内允许有界试参，内部试参留实验记录，选出的候选进入循环 evaluate 与独立复核。融合、Triton/TileLang/HIP、GEMM 交 `$hcu-infer-operator-develop`；原生配置与系统路径由 `$hcu-infer-analyze-and-optimize` 承接。缺失库/算子补齐后返回原生选项及相关组合验证，初版融合仍需评估剩余空间。
7. **模型内外同条件对照。** 恢复真实 shape/dtype/stride、phase/rank/call、mask/路由/量化 scale、完整 API 的分配/copy/同步及实际 kernel。独立算子正常而模型内变慢时，先查并发竞争、提交/等待和拓扑；独立也低效时再按匹配上限优化实现。shape 相同的随机输入不能替代动态路由/稀疏数据。复用契约、ABI 和实现未变的已有资格，仅补受影响测试；每个正式新循环按当前 API 刷新 analysis。
8. **质量与正式性能双门禁。** 对初始 oracle 验固定请求、logits/token 或任务质量及必需服务特性；覆盖改变的长上下文、动态 batch、空专家、graph/fallback、流式和 KV 生命周期。质量失败不得以吞吐抵消，不临时放宽容差。默认每场景一次匹配的 profiler-off 性能测量，需要更强置信度时显式使用三次或更多重复并必要时 A/B/A 复查漂移；报告实际次数和有限重复限制。同时比较当前最佳与初始基线，逐场景核 SLA/尾部/显存，不能只看平均收益。任务要求的完整质量集在稳定里程碑复验，小测试通过不等于全模型质量达标。
9. **复核、保留或恢复。** `model-loop-step` 的 evaluate 请求只产生待复核决定，随后 `optimization-check`、独立 `flow-submit/review/advance`，通过后以 keep 更新最佳。失败或复核拒绝先恢复最佳，并提交本轮新执行的回退验证；旧基线记录不可代替恢复。代码/库/形状/调度/融合改变后由本仓 Prof Skill 刷新受影响证据，重排热点；组合候选在共同快照整体重测，独立收益不能相加。
10. **停滞时复查机制，按证据收尾。** 无稳定收益先区分过期证据、测量噪声、未命中、资源竞争、数值约束与实现上限，再决定补采、消融、换机制或停止。遵守 `max_iterations`、`max_no_gain` 和既有执行预算；预算耗尽不等于达到硬件极限。显著空间仍受阻时报告最小证据包、已尝试结果和推荐下一步。未处置候选先恢复再 stop，unknown 操作由既有 recovery_owner 核清。

## 每轮记录与有效性门槛（v2）

1. 每次候选实施/试参用 `model-loop-step` 的 `explore` 登记 plan、route、candidate_snapshot、summary、changes 和 evidence；changes 写实际文件、可选符号和修改说明，notes 留存观察、失败及适用范围。不要只写聊天总结或等成功后才建记录。同一假设内多次 explore 都保留，evaluate 必须对应最后登记的候选。
2. 可选 screening artifact 保存单次模型或算子微测，明确 scope；只作为未验证初筛显示，不代替正式模型精度/性能，不把算子加速当作模型收益。
3. 每轮执行短输入单请求、长输入单请求、短输入并发、长输入并发四格精度验证，按开始时冻结的 coverage 和初始 oracle 比较。保存输入 SHA/token数、run_id、并发和起止时间，核对实际请求重叠与原件。可用少量请求做轻量检查，但长输入阈值必须按本任务代表性上下文设置，不能用默认2048冒充更长目标范围；必要完整质量集及 serving features 仍需覆盖。精度失败不能用吞吐抵消。
4. 实现后调用本仓分析 Skill 补采该候选的优化后 Prof。`prof-analyze` 带 candidate_snapshot，保留独立 candidate-analysis 和 capture；原 profile_evidence 仍引用产生计划的优化前 analysis。capture 绑定当前 context/epoch/snapshot、实际执行、候选路径命中、全部分析 rank 的 trace 与采集日志，不能复用前置或旧轮 trace 贴新标签。
5. evaluate 传 candidate_analysis/candidate_capture 与精度/性能输入。缺优化后 Prof 保持 incomplete；精度或性能失败进入 rollback；通过后才进入独立 flow 复核及 keep。可运行候选应收集优化后 Prof；无法运行/明确中断时保留缺失状态及原因，不能伪造成功 Prof。
6. 模块自动维护 `modules/model-loop/TASK/REPORT.md` 和 `iterations/NNNN/`：每轮有报告、探索历史、quality/performance输入与结果、prof/before、prof/after、原始证据及manifest。每步更新总报告，失败、中断、缺证据都可见；用 `model-loop-report TASK --destination` 导出交付树。源码解释、资源代价和因果仍须提供真实记录，模块不会凭空生成。
7. 用户明确要求中断时，先停止并核清实际执行，再用 interrupt 及当前 revision 的停止原件记录 incomplete/interrupted；不冒称已恢复最佳服务，不自动再启动。常规失败/预算停止仍按原回退门槛执行。字段与目录以 `docs/model-optimization-loop.md` 为准。

## 协作、报告与交付

依据真实热点和依赖拆分独立工作；实际可用且获授权时才使用子 Agent。开发/CPU 分析可并行，共享 GPU/NIC/存储计时串行或证明隔离。采用同一基线和质量契约，接口影响及时交接，在共同实例验证兼容组合，不按固定名单分派算子。新实验和阶段推进前处理主控已采集的人的指导。

每步使用本仓循环自动生成的私有 `REPORT.md` 和不可变 JSON。Agent 在既有任务报告/BOARD 补充知识与源码依据、因果假设、覆盖缺口、是否命中、内存/功能代价、内部试参及实际停止原因；当前自动报告不会凭空生成这些解释。保留初始基线、最佳快照、失败候选、原始 Prof、数值与恢复证据，清理仅针对已核销的可重建缓存。

完整 `full` 任务还需交回主控完成约定的部署/扩容/服务观察；独立优化按其目标交付。共享知识仅整理经验证、可复用的适用条件和最终里程碑，逐轮调参留私有工作区。脚本成功、计划生成、来源审阅和 CPU 协议测试均不能冒充 HCU 模型精度或性能实测。
