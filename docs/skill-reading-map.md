# 按范围读取，而不是每轮通读

| 请求 | 主要 Skill | 首次使用前读取 | 工具链 |
| --- | --- | --- | --- |
| 完整任务/接续 | hcu-infra-agent | architecture.md、contracts.md，当前阶段文档 | task-create、flow-start/next，检查当前 context 和未知操作 |
| Prof 分析 | hcu-infer-analyze | [Profiler/TraceLens 指引](../skills/hcu-infer-analyze/references/profiler-and-tracelens.md)、modules.md 的 Prof 部分 | 读取绑定的 llm-torch-profiler-analysis → triage 报告 → 按问题执行 TraceLens → prof-analyze/原件归档 |
| 性能优化 | hcu-infer-model-optimize | modules.md 的优化部分、contracts.md | 当前 analysis → optimization-plan → 真实实验 → optimization-check → 独立 flow review |
| 算子开发/融合/GEMM | hcu-infer-operator-develop | operator-development.md、模型优化 Skill 的 math-library-tuning、hcu-library-integration | operator-plan → dispatch → integrate → 模型验证 |
| 新模型适配 | hcu-infer-model-adapt | model-adaptation.md、技能自带 references | model-adapt-plan → 缺口实现/算子移交 → run → check → 重新基线 |
| 模型持续优化 | hcu-infer-model-optimize | model-optimization-loop.md；本 Skill 的 knowledge-and-source、iteration-decisions、inference-mechanisms | HCU 知识→当前源码；本仓 Prof Skill→原生/算子候选；model-loop 双门禁/复核/恢复与报告 |
| 性能仿真 | 由部署/优化阶段按问题调用 | modules.md 的 DCUSim 部分 | simulate；核对模型/硬件/并行、dtype、默认值和预测边界 |
| Cookbook/知识查询 | hcu-infer-knowledge-search；部署阶段联查 | modules.md 的查询部分、knowledge.md | search/query → read → 版本与适用条件判断；需要原件再扩大查询范围 |
| 运行失败/hang/崩溃/精度异常 | hcu-infer-diagnose-and-fix | operations.md、incident-replay 与对应症状模块 | 首错/请求 → 重放 → 定向诊断 → 修复 → 原用例与恢复验证 |
| 扩容/持续服务观察 | 主控协调 hcu-infer-check-and-deploy | operations.md | 拓扑/容量/质量/SLA 复验；observe 与事件回执，异常交故障 Skill |

完整主控保存统一目标和验收，独立分析、查询或仿真不被强制扩大成真实优化。
安装 Skill 的 `workspace.json.project_root` 定位工程文档；文档不会仅因被提及就自动进入 Agent 上下文。
需要对应决策时实际读取并沿用未变化的规则。绑定输入、调用结果与人的指导归任务工作区，最终可复用结论另行筛选。

环境与容量、热点上限、通信/库、故障交接的详细指引由对应 stage Skill 的 references 提供。跨阶段工作区和交付范围读 [workspace-and-delivery.md](workspace-and-delivery.md)；参考设计的推理转化见 [trainflow-alignment.md](trainflow-alignment.md)。
