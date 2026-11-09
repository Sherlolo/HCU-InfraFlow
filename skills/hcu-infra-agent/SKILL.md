---
name: hcu-infra-agent
description: 协调 HCU 大模型推理的部署、基于性能分析的优化及服务运维全流程，也支持限定范围的环境检查、性能分析或故障诊断任务。
---

# HCU 推理主控

接收用户提供的模型、环境、资源范围、工作负载、质量要求、SLA 和交付目标。复用已有授权，只对实质缺失的信息补充确认。接续任务前，先读取当前 Store、实际作业状态和已有证据。

完整任务通过 CLI 的 `task-create` / `flow-start` 创建 TaskSpec 和具有明确验收项的计划。使用 `flow-next` 判断下一步是实施、修正、复核、推进、协调还是核对执行结果（work / repair / review / advance / coordinate / reconcile）；不能因远端操作结果不明就直接重试。部署交给 `$hcu-infer-check-and-deploy`，性能分析与优化交给 `$hcu-infer-analyze-and-optimize`，扩容和持续服务交给 `$hcu-infer-scale-and-operate`。仅分析任务不自动授权优化。

保留最初的服务基线、准确的模型、tokenizer、量化方式和固定工作负载。提交候选快照及已留存的证据，由实际独立的 Agent 复核；仅有不同的 author / reviewer 字符串不能证明复核独立。新实验和阶段推进前检查人的指导，默认轮询间隔为 300 秒。并行工作必须具备真实依赖关系和互不冲突的资源；消费结果前，登记并绑定实际宿主会话。

遵守既有预算和资源预约。出现数值或功能回退、证据缺失或执行结果未核清时，停止推进。交付经过验证的启动方法、质量与性能结论的适用范围、剩余缺口和报告；仅筛选可复用的最终结论进入共享知识。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。

## 五个模块的选择

先按任务范围读取 `docs/skill-reading-map.md`，再从 `docs/modules.md` 查对应模块的可执行契约。Cookbook 和知识检索、正文阅读提供与版本相关的参考；`simulate` 提供带适用条件的 DCUSim 预测；`prof-analyze` 留存真实 rank 证据；`optimization-plan` 记录 Agent 的假设；`optimization-check` 重算候选是否满足要求。只调用任务需要的模块，继续遵守既有 flow 复核和资源规则。具体命令及实测覆盖范围见 README。

## 已安装的运行入口

通过 `workspace.json.project_root` 定位工程。存在安装记录时复用 `.work/setup/status.json`、`site.json` 和 `components.json`，使用记录的 Python 执行 `-m hcu_infra_agent`，让使用者无需管理 PATH、JSON 绑定或内部命令。在选定容器中核对组件缺口。使用者提供目标和已有资料，由 Agent 维护任务规格与工具输入。
