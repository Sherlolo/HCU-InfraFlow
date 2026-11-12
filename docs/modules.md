# 推理模块的运行方式

沿用 TrainFlow 的“主控 + 三阶段 Skill + 持久证据 + 独立复核”组织方式。各模块可单独使用，完整任务按瓶颈组合；
模拟或查询不自动启动服务，分析任务不自动扩展为优化任务。

| 模块 | 输入与入口 | 产物与消费 |
| --- | --- | --- |
| Prof 性能分析 | `prof-analyze TASK REQUEST`；已有 rank trace、真实组、各 rank 选定窗口 | 保留原始压缩 trace、窗口、GPU 时间归因、覆盖缺口；可调用绑定的原生 triage。analysis artifact 供优化计划和 flow 使用 |
| 性能优化 | `optimization-plan TASK REQUEST`、`optimization-check TASK REQUEST` | Agent 依据观测写假设和目标，不自动枚举固定旋钮；校验固定样本、特性、重复性能和 SLA，保留结果后仍需独立复核 |
| 性能仿真 | `simulate BINDINGS REQUEST` | 调用独立 Python 3.10 环境中的真实 DCUSim，输出 prefill/decode、TPS、显存预测、默认假设与来源；不充当实测 |
| Cookbook 查询 | `cookbook-search BINDINGS QUERY`、`cookbook-read BINDINGS PATH` | 先找到适用模型/框架/硬件配方，再读原文与命令片段，记录路径、行号、正文 SHA256、官方提交与页面链接 |
| 知识库查询 | `knowledge-query BINDINGS QUERY`、`knowledge-read BINDINGS PATH` | 无需原生派生索引，查本机 Git 跟踪的 Markdown/MDX/YAML；原生查询仍使用 knowledge-search |

所有新入口支持 `--output FILE` 保存 JSON。查询类入口不创建 Store；Prof/仿真/优化的产物进入 `--workspace` 指定的私有 Store。
约定退出码：0 完成、1 输入/运行错误、2 失败/不充分/部分覆盖。查询返回 partial/2 是覆盖说明，命中结果仍可读，不能把 2 一律丢弃。

## Prof 分析

`examples/modules/prof.json` 中的 path 是实际 trace 路径；window 是该 rank 代表性 GPU 活动的起止微秒，不是任意跨节点同一绝对时间。
支持 `.json` 和 `.json.gz`。每个非单例组至少两个代表 rank，采样不等于完整 collective 分析。明确 groups，不能从文件数推断并行拓扑。
trace 元数据或事件 rank 与声明冲突、窗口没有 GPU 活动、缺少代表 rank 都会拒绝报告。

加入 `triage_bindings`（绑定 JSON 的路径）可调用执行端已安装的 [llm-torch-profiler-analysis](https://github.com/Sherlolo/hcu-infer-pilot/blob/main/skills/llm-torch-profiler-analysis/SKILL.md) 中 `scripts/run_triage_report.py`；在私有目录分析固定原件，不重新采集 GPU。
外部 triage 失败不会冒充成功，原始 stdout/stderr 和退出码留在 Store 的 modules 目录。分析无模型名时不访问在线架构图。
工具输出引用脚本入口哈希；外部脚本的其他依赖应按站点版本另行核实，不把入口 pin 宣称为整个运行环境冻结。

主报告是可供 Agent 推理的证据，不自动证明算子上限评估完整。缺 shape/dtype、图重放归属、未归因时间、条件上限仍明确保留。
`profile-analyze TRACE WINDOW` 保留为原始单文件检查入口；需要持久任务证据时用 `prof-analyze`。

上游仓库：[Sherlolo/hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)；辅助工具：[AMD-AGI/TraceLens](https://github.com/AMD-AGI/TraceLens)。具体采集、triage 和 TraceLens 组合方式见 [联合分析指引](../skills/hcu-infer-analyze/references/profiler-and-tracelens.md)。

当前 `prof-analyze` 给外部 wrapper 的是完整单 rank 文件，window 仅用于本仓统计；比较口径时核对范围。该 CLI 不自动启动 TraceLens，也不传 `--model` 或 mapping/formal 参数。需要这些分析时由 Agent 按实际工具 CLI 单独执行，用 `artifact-add` 留存结果，加入优化计划的 references；不可将基础解析结果称作 TraceLens 报告。

## 性能优化

用 `prof-analyze` 返回的当前 analysis artifact 填 plan 的 observation/hypothesis/target/validation，见 `examples/modules/plan.json`。
计划可关联已保留的仿真/资料 artifact，但方向由真实 profile 及源码判断。计划仅记录决策，不启动命令或宣称实现完成。
旧 context、被替换 analysis、不允许优化的 analyze/environment/diagnose 范围会被拒绝。

实施时检查现有引擎能力、生效路径、量化/通信/缓存约束，再选择配置或 kernel 改动。用命令卡、隔离工作树和资源准入执行。
`optimization-check` 输入 plan、quality_inputs、performance_inputs、candidate_analysis、candidate_capture（均为当前 Store artifact ID），以及 changes 数组（path/description，可加symbol）。两份比较必须绑定同一候选 snapshot、context、模型与 workload；每条原始测量声明真实硬件执行并保留原件。

质量合同必须带 coverage：短输入上限、长输入下限、并发下限，覆盖短/长×单请求/并发四格。候选 Prof 通过带 candidate_snapshot 的 `prof-analyze` 生成，登记为 candidate-analysis；它不会覆盖计划使用的优化前 analysis。capture 必须绑定同一 snapshot/context/epoch、实际执行和所有 rank trace，不能复用优化前 trace。详见[模型优化合同](model-optimization-loop.md)。

通过会生成 inference-quality/performance 报告；缺候选Prof或修改说明时保存 incomplete，精度/性能失败时保存 fail，防止沿用上一份 pass 继续推进。
`accepted_by_flow=false` 表示尚未经过独立 review；之后仍需原有 flow-submit（含迭代输入）、flow-review、flow-advance。

独立 plan/check 也统一输出到 `WORK/modules/optimization/TASK/REPORT.md`，每个plan在 `explorations/PLAN_SHA/` 下保存历次 `attempts/0001/`。每次计划或检查自动更新总报告，旧评估、失败和原始Prof不被新结果覆盖。模型连续优化以 `modules/model-loop/TASK/` 的逐轮目录为主；两种入口共用同一报告与原件布局。

独立入口的历史也写入SQLite和不可变artifact，不以可编辑的index.json作为权威状态。`optimization-report TASK` 可在报告文件丢失后重建整个目录；不同context/epoch的旧记录标为historical，不当作当前验证。

## DCUSim 仿真

`examples/modules/simulation.json` 显式给出工具模型别名、gpu、batch/输入/输出、P/D 各自 TP/DP/PP/EP/CP/节点数、DPA、KV/计算 dtype。
所有其他实际默认参数在 backend_output.effective_arguments 保存。工具的 model config 路径和 SHA256 也保留；别名不证明与现场权重完全一致。
自定义 JSON 使用 arguments.model 的绝对路径，程序保留原字节后传给 worker。预测目录独立，不覆盖原模型配置。

`simulation_python` 不采用宿主不兼容解释器，绑定到专用 DCUSim venv。`simulation_wheel` 固定发行原件哈希，backend_output 记录运行包版本和 Python 入口哈希；
这些字段不声称已验证所有原生依赖。示例参数只是演示，不是推荐部署配方。预测含默认利用率、通信和缓存模型，需用实际工作负载校准。
显存不可行应据返回 feasibility 判断；仿真结果一律 hardware_executed=false，不可用作 performance 报告原始测量。

## Cookbook 与知识库

可用 `knowledge-bind ROOT DESTINATION` 独立绑定知识资料，再调用 `knowledge-query/read`。此路线的 Python 实现位于本仓，不执行知识库脚本、不要求其他 Skill 仓库或 `kb.py`；绑定文件保存在私有任务目录。详见 [知识接口与边界](knowledge.md)。

Cookbook 使用 `https://github.com/HYGON-AI/inference-cookbook-das` 的 GitHub API 与固定提交原文，返回官方页面及相关链接。
不依赖知识库安装、不采用 cookbook_root 镜像。search 按 Markdown 路径匹配模型/框架关键词，read 的 --revision 固定同一提交。
安装及容器组件检查使用 hcu-infra-agent-install Skill 与 doctor；SimTools 由 component-fetch simtools 显式获取，知识库由使用者手动安装。

知识查询只读 Git 跟踪的文本，范围不是全量线上文档；有界词项检索不证明全文结论已理解。命中后使用 read，核对 dtype、并行、硬件、框架分支与依赖，
再到现场检查当前 CLI help 和实际实现。正文中的启动命令仅作为待验证材料，不会自动执行。read 限制在所绑定根内，拒绝路径逃逸。

知识库体量较大，`knowledge-query` 默认只扫描 local 的专题/教程/案例/概览及 concepts，结果包含 search_scope 和 coverage。需要上游/原文时显式 `--scope all --timeout 180`（最大 300 秒）；超时返回 incomplete，不把它解释为无命中。Cookbook 查询仍限所绑定的配方目录。


## 三个专业模块

| 模块 | 入口 | 详细契约 |
| --- | --- | --- |
| 算子开发与接入 | `operator-plan`、`operator-dispatch`、`operator-integrate` | [算子开发](operator-development.md)：Prof/适配缺口 → 专项 Skill → 自动 apply/verify/rollback |
| 模型适配 | `model-adapt-plan`、`model-adapt-run`、`model-adapt-check` | [模型适配](model-adaptation.md)：发布锁、架构缺口、kernel 迁移、执行测试与 ready_for_baseline |
| 模型优化闭环 | `model-loop-start`、`model-loop-step`、`model-loop-status`、`model-loop-report` | [持续优化](model-optimization-loop.md)：定卡数仿真 → 基线/适配 → Prof → 候选 → 双门禁/独立复核 → 保留/回退 |

上述入口仍使用 `--workspace` 指定的 Store，输入由主控 Agent 根据任务维护。执行命令继续使用已有 command card、lease 和 unknown/reconcile 机制。循环只根据已留存的执行证据推进，不在 Python 进程中隐式启动 LLM；宿主 Agent 负责调用所需技能和实施下一步。

普通环境/分析/查询请求保持原有范围；新模块不会强迫它们执行全部链路。专项技能安装、公开来源与目录独立性见 [工作区与交付](workspace-and-delivery.md)。
