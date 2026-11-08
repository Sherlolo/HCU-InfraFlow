# 按范围读取，而不是每轮通读

| 请求 | 主要 Skill | 首次使用前读取 | 工具链 |
| --- | --- | --- | --- |
| 完整任务/接续 | hcu-infra-agent | architecture.md、contracts.md，当前阶段文档 | task-create、flow-start/next，检查当前 context 和未知操作 |
| Prof 分析 | hcu-infer-analyze-and-optimize | modules.md 的 Prof 部分、optimization.md | prof-analyze；需要外部 triage 时核对绑定和原始输出 |
| 性能优化 | hcu-infer-analyze-and-optimize | modules.md 的优化部分、contracts.md | 当前 analysis → optimization-plan → 真实实验 → optimization-check → 独立 flow review |
| 性能仿真 | 由部署/优化阶段按问题调用 | modules.md 的 DCUSim 部分 | simulate；核对模型/硬件/并行、dtype、默认值和预测边界 |
| Cookbook/知识查询 | hcu-infer-knowledge-search；部署阶段联查 | modules.md 的查询部分、knowledge.md | search/query → read → 版本与适用条件判断；需要原件再扩大查询范围 |
| 扩容/诊断/守护 | hcu-infer-scale-and-operate | operations.md | 当前服务和观测证据、既有 recovery_owner、事件处理回执 |

完整主控保存统一目标和验收，独立分析、查询或仿真不被强制扩大成真实优化。
安装 Skill 的 `workspace.json.project_root` 定位工程文档；文档不会仅因被提及就自动进入 Agent 上下文。
需要对应决策时实际读取并沿用未变化的规则。绑定输入、调用结果与人的指导归任务工作区，最终可复用结论另行筛选。
