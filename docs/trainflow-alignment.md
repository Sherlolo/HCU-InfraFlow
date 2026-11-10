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
