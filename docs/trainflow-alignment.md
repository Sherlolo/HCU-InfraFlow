# 参考设计与推理适用性

本轮参考 HCU-TrainFlow 的技能与工作方法，按推理语义重写为本仓资源；运行时不需要其 checkout。参考提交与来源见根目录 `provenance.json`。下表说明如何使用，而不是要求读取外部路径。

| 参考因素 | 本仓落点 | 推理转化 |
| --- | --- | --- |
| 环境发现、硬件基准、完整模型容量 | 部署 skill 的 `references/environment-and-capacity.md` | KV/图池/工作区与最坏 rank，仿真后真实请求校准 |
| 执行基线和稳定/快速交付轨道 | `workspace-and-delivery.md`、`model-adaptation.md` | 固定框架/模型发布锁，适配补丁与稳定插件分别交付 |
| 证据闭环、热点上限与融合迭代 | 优化 skill 的 `references/profile-and-ceilings.md` | prefill/decode、墙钟与重叠归因；保留初始及最佳基线 |
| 引擎原生调参、库接入与数学库调优 | 优化 skill 的 `references/communication-and-libraries.md`、`operator-development.md` | dispatch 命中、真实 GEMM 日志、局部与服务回归 |
| 通信暴露、通算融合与异步生命周期 | 同上 | TP/EP/PD、动态 token、KV/会话、stream/graph/fallback |
| 失败分流、观察器和恢复交接 | 运维 skill 的 `references/diagnosis-and-handoff.md` | 请求 replay、全部服务 member、attempt 与唯一恢复负责人 |
| 工作区边界、维护、并行交接 | `workspace-and-delivery.md` | 单主控，隔离候选，串行共享硬件测量，保护回退及证据 |
| Wiki/经验沉淀与版本适用性 | `knowledge.md` 与知识 skills | 只读来源，按请求质量/性能筛选可复用结论 |
| 模型级持续优化 | `model-optimization-loop.md` | 给定卡数仿真 → 基线/适配 → Prof → 优化 → 双门禁/复核 → 迭代报告 |

没有移植训练 loss、backward、梯度累积、优化器或 checkpoint 优化器状态作为推理门槛。推理依据是固定输入输出/数值、服务特性、KV/会话一致性和无 profiler 的性能/SLA。训练专属后端和环境变量不直接套用；具体 HCU 库能力由当前部署版本验证。


## 模型推理优化闭环的进一步转化

本仓 `hcu-infer-model-optimize` 将训练优化 Skill 的方法重写为推理场景，运行时不读取 TrainFlow 文档或调用其脚本：

| 借鉴的方法 | 本仓推理落点 |
| --- | --- |
| 先查领域知识再核源码，复用未变证据 | 先 `$hcu-knowledge-search` 方法，再查当前分支；本仓 knowledge-bind/query/read 仅读取外部资料，不执行外仓 Python |
| 原生配置与实现相互反馈 | scheduler、attention/KV、graph/compile、MoE/通信；补齐底层能力后重验配置组合 |
| 映射、稳态、计数器与正式计时分开 | Prof 明确交本仓 hcu-infer-analyze-and-optimize；性能由 profiler-off 服务重复测量决定 |
| 热点/源码/上限、依赖、融合三视角 | prefill/decode/PD、动态 token/shape、关键路径与资源竞争，按实际贡献及可兑现空间排优先级 |
| 模型内外同条件对照 | 真实 mask/路由/KV/scale 与完整调用，区分独立低效、模型并发拖慢和 host 开销 |
| 分层筛选、候选组合与阶段精度 | 先局部正确性与短筛，再固定输出/功能和重复性能；组合整体复测，稳定里程碑完成约定质量集 |
| 停滞复查与交付 | 重新核机制/证据、恢复最佳、预算/阻塞据实报告；不以预算耗尽声称硬件极限 |

没有移植训练反向、优化器状态或长训 loss 门槛。新的数据绑定 API 和文档均位于 infra-agent；外部资料根可由使用者替换，公共 Skill 中不写入站点固定路径。
