---
name: hcu-infer-analyze-and-optimize
description: 分析 HCU 推理服务的 trace，优化实测的大模型推理瓶颈，同时保持固定工作负载下的质量与 SLA。
---

# HCU 推理性能分析与优化

从固定且关闭 profiler 的基线开始。使用已绑定的 profiler Skill 采集实际 prefill / decode / rank trace，并开展原生 TraceLens 分析。核对 trace 是否为本次采集、是否包含非空 GPU 事件、rank 覆盖、文件哈希及工具的真实输出。文件已存在或启动成功，都不能证明采集成功。

按观测到的墙钟耗时确定优先级，并解释因果假设。选择引擎调参、融合或 kernel 工作前，检查当前实现、相关 HCU 知识，以及上游和本地历史。不执行预设旋钮网格；缺证据时安排有针对性的补采集。区分重叠 kernel 的耗时总和与墙钟时间，并分别处理 shape、dtype、阶段和 rank。

仅在作用范围与瓶颈匹配时调用已绑定的 benchmark、BLAS、MoE 或 LightOp Skill。保留真实 shape、数值与实际分发路径测试，使用隔离构建。在 profiler 关闭时重新测量端到端工作负载和必需功能，至少进行三次可比重复；局部 kernel 收益不等于服务收益。提交包含 observation、hypothesis 和 target 的当前 `profile_evidence`，以及 `quality_inputs`、`performance_inputs`，随后独立复核。记录被拒绝的候选和实际停止原因。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。

## 可执行模块链路

首次使用前读取 `docs/modules.md`。通过 `prof-analyze` 导入实际 trace，检查未明确的项目和原始 triage 输出。使用当前 analysis ID 调用 `optimization-plan`，随后通过既有命令卡执行限定范围的实现与测量。对留存的固定输入比较调用 `optimization-check`；即使通过，仍需独立的 flow 复核。`simulate` 使用 DCUSim 验证模型、硬件和并行假设，不能将预测当成实测性能。实施前搜索并阅读 Cookbook 和知识库，确认已有机制。

## 已安装的运行入口

通过 `workspace.json.project_root` 定位工程。存在安装记录时复用 `.work/setup/status.json`、`site.json` 和 `components.json`，使用记录的 Python 执行 `-m hcu_infra_agent`，让使用者无需管理 PATH、JSON 绑定或内部命令。在选定容器中核对组件缺口。使用者提供目标和已有资料，由 Agent 维护任务规格与工具输入。
