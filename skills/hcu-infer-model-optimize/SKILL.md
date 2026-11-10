---
name: hcu-infer-model-optimize
description: 在固定 HCU 卡数下执行模型仿真、运行基线、真实 Prof、候选优化、精度性能复核和有界迭代，持续保存优化报告；适用于完整模型优化任务。
---

# HCU 模型优化闭环

在主控和既有优化阶段内运行闭环，不另起独立调度器。已安装 Skill 通过同目录 `workspace.json.project_root` 找到工程和解释器；源码中从仓库根读取 `docs/model-optimization-loop.md` 的 CLI 契约。Agent 维护请求和 evidence，用户只需指定模型、实际环境、卡数与目标。

1. 固定模型/tokenizer/量化、workload、引擎快照、driver、设备分配、性能/SLA 和质量判定。按目标选择少量有依据的并行候选，用真实 `simulate` 预测；只选显存明确可行且物理卡数匹配的方案。预测最优只相对于候选集合，先用最差 rank 余量和真实短跑校准。
2. `model-loop-start` 后逐步消费 `next`。执行走已授权命令卡、隔离目录和资源租约。运行无 profiler 基线；跑不通进入 `hcu-infer-model-adapt`，适配通过后重新测基线，不把补丁/计划等同于跑通。
3. 保留初始输出 oracle、初始性能、已复核最佳和候选各自快照。每轮质量对初始 oracle，性能同时对当前最佳和初始基线。身份或 workload 实质改变时另建比较任务。
4. 采集当前最佳的真实 profile，以 trace 原件、rank、shape/dtype、prefill/decode、graph 和 dispatch 解释热点。按 `references/iteration-decisions.md` 选择下一项假设；先核查已有引擎能力，再派发实现。融合、Triton/TileLang/HIP、GEMM 交 `hcu-infer-operator-develop`；调度、缓存和并行配置由阶段优化 skill 处理。
5. 候选先做局部正确性与 dispatch 证明，再做固定样本/特性检查和至少三次无 profiler 的匹配性能测量，保持 TTFT、TPOT、P95、吞吐和所有目标场景 SLA。`model-loop-step evaluate` 通过后仍要 `optimization-check` 和独立 flow review/advance；随后 keep 才可更新最佳组合。
6. 候选失败保留原因和原始数据，恢复最佳快照并验证后继续。无收益或预算停止时报告实际原因、剩余热点/证据缺口。每步自动保存私有 `REPORT.md` 和不可变 JSON，报告每轮方向、增量/累计性能、质量、保留/拒绝、快照和复核证据。

使用者只要分析或仿真时，保持原任务范围，不进入实施闭环。未知远端执行先核清，不盲目重试；共享硬件测量与耦合修改由主控协调。脚本返回成功、skill 已绑定、source review 或 CPU 协议测试都不能作为 HCU 性能证据。
