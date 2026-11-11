---
name: hcu-infer-analyze-and-optimize
description: 使用 llm-torch-profiler-analysis 分析 HCU 推理 Prof/torch.profiler trace，结合 TraceLens 复核热点、通信和空泡，并按实测瓶颈优化模型、验证质量与 SLA。
---

# HCU 推理性能分析与优化

优化任务从固定且关闭 profiler 的基线开始；用户只提供已有 Prof 要求分析时，直接核验并分析原件，不强制启动模型。以 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot) 的 [llm-torch-profiler-analysis Skill](https://github.com/Sherlolo/hcu-infer-pilot/blob/main/skills/llm-torch-profiler-analysis/SKILL.md) 为 Prof 主分析入口，结合 [TraceLens](https://github.com/AMD-AGI/TraceLens) 做性能复核。核对 trace 的采集身份、非空 GPU 事件、rank 覆盖、文件哈希及工具真实输出。

## Prof 分析的实际调用

开始时读取 [Profiler 与 TraceLens 联合分析](references/profiler-and-tracelens.md)，并实际读取所绑定的上游 `SKILL.md`。从现有 bindings 的 `items.profile.path` 或安装记录 `pilot_root` 定位它，核对 revision、入口哈希和解释器；远程链接用于来源与获取，不代替本地脚本和依赖。使用完整 Skill 资源，不仅复制一份 Markdown。

已有 trace 默认调用上游报告脚本 `run_triage_report.py`，将 kernel、overlap、fusion 与空泡结论及命令/原始输出落盘；需要源码归因时按上游契约区分 mapping 和 formal trace。采集新 Prof 时沿用真实 workload、框架 profiler 接口和容器路径映射，核实 trace 已 flush；不沿用来源中的 H100 型号、作者目录或示例负载作为 HCU 默认配置。

根据问题实际运行 TraceLens 的单 rank/推理报告、多 rank 通信报告或前后对照。图重放需要相应采集元数据与稳态窗口；缺少 shape、GPU 参考或 rank 时注明对应分析缺口。保存 TraceLens 的独立命令、版本、输出和失败原因；`prof-analyze` 的基础解析或上游 triage 成功不表示已运行 TraceLens。组件不可用时交付已完成的分析并标明尚缺的辅助复核。

按观测到的墙钟耗时确定优先级，并解释因果假设。选择引擎调参、融合或 kernel 工作前，检查当前实现、相关 HCU 知识，以及上游和本地历史。不执行预设旋钮网格；缺证据时安排有针对性的补采集。区分重叠 kernel 的耗时总和与墙钟时间，并分别处理 shape、dtype、阶段和 rank。

仅在作用范围与瓶颈匹配时调用已绑定的 benchmark、BLAS、MoE 或 LightOp Skill。保留真实 shape、数值与实际分发路径测试，使用隔离构建。在 profiler 关闭时重新测量端到端工作负载和必需功能，至少进行三次可比重复；局部 kernel 收益不等于服务收益。提交包含 observation、hypothesis 和 target 的当前 `profile_evidence`，以及 `quality_inputs`、`performance_inputs`，随后独立复核。记录被拒绝的候选和实际停止原因。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。

## 可执行模块链路

首次使用前读取 `docs/modules.md`。通过 `prof-analyze` 导入实际 trace，检查未明确的项目和原始 triage 输出。使用当前 analysis ID 调用 `optimization-plan`，随后通过既有命令卡执行限定范围的实现与测量。对留存的固定输入比较调用 `optimization-check`；即使通过，仍需独立的 flow 复核。`simulate` 使用 DCUSim 验证模型、硬件和并行假设，不能将预测当成实测性能。实施前搜索并阅读 Cookbook 和知识库，确认已有机制。

## 已安装的运行入口

模型优化候选完成后必须补采优化后的真实Prof。使用带 candidate_snapshot 的 prof-analyze，保留 candidate-analysis 及 capture 原件，包含当前 context/epoch、实际执行、候选路径命中和全部分析 rank 的 trace。原始 profile_evidence 仍引用产生计划的优化前 analysis；不要用新 Prof 覆盖它。独立 optimization-check 与模型循环都需要短/长×单请求/并发精度覆盖和候选 Prof，缺失时只保留 incomplete 报告。输出目录与字段以 `docs/model-optimization-loop.md` 为准；预热/采Prof的时延不进入正式性能数组。

通过 `workspace.json.project_root` 定位工程。存在安装记录时复用 `.work/setup/status.json`、`site.json` 和 `components.json`，使用记录的 Python 执行 `-m hcu_infra_agent`，让使用者无需管理 PATH、JSON 绑定或内部命令。在选定容器中核对组件缺口。使用者提供目标和已有资料，由 Agent 维护任务规格与工具输入。


## 按瓶颈补充阅读

形成热点队列、估计收益和决定停止时读取 [热点与上限](references/profile-and-ceilings.md)。涉及 TP/EP/PD、数学库或框架分发时读取 [通信与库接入](references/communication-and-libraries.md)。只读参考材料不触发依赖升级。

Prof 产生的具体算子需求交 `$hcu-infer-operator-develop`，用 `operator-plan` 固定证据和调用契约，由 `operator-dispatch` 调用实际专项 runner，再 `operator-integrate` 执行框架接入/验证/回退。模型级持续任务由 `$hcu-infer-model-optimize` 管理仿真、初始基线、迭代决策和报告；本阶段继续负责每轮真实 profiling 与优化假设，不让循环状态替代实验。
