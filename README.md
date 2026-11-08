# HCU Infra Agent

面向 HCU 大模型推理的 Agent 工作流，当前版本 **0.2.0**。围绕 **Prof 性能分析、性能优化、性能仿真、Cookbook 查询、知识库查询**五个模块组织工作。

采用 HCU-TrainFlow 的运行方式：**本地主控 Agent → 阶段 Skill → 工具与持久证据 → 独立复核 → 修正或推进**。
实际模型和引擎在获准环境执行，CLI 不隐藏启动 LLM，也不把生成报告当作模型提速。

## 五个模块

| 模块 | 做什么 | CLI / 主要产物 |
| --- | --- | --- |
| **Prof 性能分析** | 导入真实 `.json/.json.gz` rank trace；检查 GPU 事件、rank 身份和组覆盖；统计墙钟、空泡、重叠与热点，可调用原生 profiler triage | `prof-analyze`；原始 trace 哈希、rank 分析、原生 Markdown/日志、当前 analysis artifact |
| **性能优化** | 基于当前 profile 观测提出假设，检查已有实现，再进行隔离实验、固定输出/特性、重复性能和 SLA 验收 | `optimization-plan` / `optimization-check`；计划与质量/性能报告，之后仍需 flow 独立复核 |
| **性能仿真** | 接入真实 **DCUSim** 离线工具，根据模型、HCU、P/D 并行与精度配置预测延迟、TPS、显存 | `simulate`；预测值、模型配置哈希、工具版本、完整生效参数、原始日志；不是实测 |
| **Cookbook 查询** | 定位模型/框架/HCU 配方，读取正文和命令片段，核对版本、量化、并行与依赖 | `cookbook-search` / `cookbook-read`；路径、行号、正文 SHA256、Git 修订、来源类型 |
| **知识库查询** | 查询 HCU 实现、原理、诊断、PR 与优化资料；无派生索引时也可查 Git 跟踪正文 | `knowledge-query` / `knowledge-read`；引用与原文。原生索引入口 `knowledge-search` 仍保留 |

五个模块可按问题独立进入，也可组成：

```text
Cookbook / 知识查询 → 配方与源码核对 → 仿真评估资源/并行假设
                  → 真实部署基线 → Prof → 优化计划 → 实验与质量/性能验收
                  → 独立复核 → 扩容与服务守护
```

查询结果和仿真提供参考；优化方向由真实 profile 与源码判断，不运行预设旋钮穷举。
详细输入和边界见 [五模块指南](docs/modules.md)。

## 安装与准备

通用工作流要求 Python **3.10+**；DCUSim 提供的 wheel 要求 **CPython 3.10 / Linux x86_64**。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/hcu-infra-agent --help
.venv/bin/python scripts/install_skills.py --target /absolute/path/to/task-skills
```

六个自有 Skill：统一主控、部署、优化、运维、知识搜索和知识整理。安装记录工程路径，不覆盖已有同名 Skill；新会话使用新安装目录。
普通任务只读绑定外部知识/Skill，不隐式更新源码或全局安装。

### 在 NMZ_zz_26 上使用

主机 Python 3.6.8 不满足条件；用户容器 `yangyn_sglang_plugin_1022` 已核对为 Python 3.10.12。
进入容器后，在指定仓库运行后续命令：

```bash
docker exec -it yangyn_sglang_plugin_1022 bash
cd /public/home/yangyn1/work_space/2026/agent/hcu-infra-agent

# 项目独立环境；缺少 ensurepip 时也可引导，不改系统包
python3 scripts/bootstrap.py --test

# 并发 SQLite Store 需位于节点/容器本地盘；源码和导出报告可留共享盘
export HCU_INFRA_WORKSPACE=/tmp/hcu-infra-agent-session/store
```

当前 `/public/home/yangyn1` 是 NFS；Store 的本地目录要按任务独立登记并安排备份。不要将多个节点各自的本地 Store 当成一个数据库。

### 绑定外部入口

`examples/site-nmz26.json` 是基础绑定；`examples/site-modules-nmz26.json` 增加 Cookbook 和 DCUSim。
DCUSim 安装在独立环境中；当前 NumPy 只读复用容器已安装版本，openpyxl 和工具包只装到新环境：

```bash
python3 scripts/setup_simulation.py \
  --wheel ../DCUSimTools/dcusim-2.0.0-cp310-cp310-linux_x86_64.whl \
  --environment .work/simulation-env

# 无网络时可给上条命令追加 --wheelhouse /path/to/wheels
.venv/bin/hcu-infra-agent bind examples/site-modules-nmz26.json .work/modules-bindings.json
.venv/bin/hcu-infra-agent bindings-check .work/modules-bindings.json
```

站点绑定包括 DCU-Infer-Pilot 的 benchmark/profiler/优化循环/BLAS/MoE、模型计算说明及实际 LightOp 入口，外加 HCU-Knowledge。
当前 pilot 内 Cookbook submodule 为空，因此示例明确使用 **HCU-Knowledge 的 inference-cookbook 镜像**；不会称为上游最新 Cookbook。
换站点时修改示例中的绝对路径；没有 DCUSim 时可先使用基础绑定运行其他模块。

## 通过 Agent 使用

在支持 Skill 的宿主中给出模型、资料和目标，主控选择相应模块：

- **只分析 Prof**：`$hcu-infra-agent 分析这些 TP2 trace，给出各 rank 的 GEMM、通信和空泡证据；这次不改代码。`
- **优化性能**：`$hcu-infra-agent 以已有基线和 trace 优化这个 HCU SGLang 模型，保持 workload、输出质量与 SLA，先查现有路径再提候选。`
- **性能仿真**：`$hcu-infra-agent 用 DCUSim 比较这个模型在 NMZ 上 TP2/TP4 的 prefill、decode 和显存预测，列出配置假设，暂不占用 GPU。`
- **查询 Cookbook**：`$hcu-infra-agent 查找这个模型的 HCU vLLM/SGLang 部署配方，读正文并核对量化、并行与当前框架版本。`
- **查询知识**：`$hcu-infra-agent 查 SGLang KV cache 和 TP 通信的 HCU 实现，返回版本、源码/PR 和适用条件。`

宿主负责实际 Agent 会话、实施与独立复核。完整任务使用 task-create / flow-start / flow-next，独立查询无需强制走完整状态机。

## 直接使用 CLI

以下命令在工程根执行，所有新模块均可用 `--output FILE` 保存结果。
查询返回 `partial` / **退出码 2** 表示只覆盖本机跟踪文本，仍可能有有效命中；输入/运行错误为 1，完成为 0。

### 1. Cookbook 与知识查询

```bash
.venv/bin/hcu-infra-agent cookbook-search .work/modules-bindings.json "Qwen SGLang" --limit 5 --output .work/cookbook.json
.venv/bin/hcu-infra-agent knowledge-query .work/modules-bindings.json "SGLang KV cache" --limit 5 --output .work/knowledge.json
# 需要原始/上游正文时显式扩大范围和预算
.venv/bin/hcu-infra-agent knowledge-query .work/modules-bindings.json "具体模型与机制" --scope all --timeout 180 --limit 5

# PATH 填搜索返回的 relative_path；按需指定正文范围
.venv/bin/hcu-infra-agent cookbook-read .work/modules-bindings.json PATH --start 1 --lines 100
.venv/bin/hcu-infra-agent knowledge-read .work/modules-bindings.json PATH --start 1 --lines 100
```

读正文后核对来源和现场 CLI help，再采用启动参数。返回的命令片段不会自动执行。
若需要原生索引/知识库自身检索，使用 `knowledge-search BINDINGS QUERY`；索引失败会明确返回 incomplete。

### 2. 性能仿真

```bash
.venv/bin/hcu-infra-agent simulate .work/modules-bindings.json examples/modules/simulation.json --output .work/prediction.json
```

示例使用工具模型别名 `qwen3_5`、NMZ、TP2、batch=4、输入 1024、输出 128、KV/attention BF16。
它不是当前 INT8 服务的校准值。修改 arguments 可比较 P/D 并行；预测值和生效默认参数全部保留，不将预测填入实测报告。

### 3. Prof 性能分析

```bash
# 先将 task.json 的模型/引擎/workload 身份改为实际值
.venv/bin/hcu-infra-agent task-create examples/modules/task.json
.venv/bin/hcu-infra-agent flow-start modules-example examples/modules/flow.json

# prof.json 填实际 trace、各 rank 代表性窗口与真实进程组
.venv/bin/hcu-infra-agent prof-analyze modules-example examples/modules/prof.json --output .work/prof.json
```

给 prof.json 增加 `"triage_bindings": ".work/modules-bindings.json"` 可运行绑定的原生 profiler triage。
这条命令分析已有材料；新采集和服务操作由获准命令卡及 profiler Skill 单独执行。
shape、dtype、Graph replay 归属或上限缺失保持未完成，不会因报告生成而伪造性能结论。

### 4. 性能优化

```bash
# plan.json 的 analysis 填 prof 返回的 analysis artifact；填写实际观测、假设、目标与验证项
.venv/bin/hcu-infra-agent optimization-plan modules-example examples/modules/plan.json --output .work/plan.json

# 实际候选实验完成后，使用同一 Store 中保留的比较输入
# CHECK.json: {"plan":"计划artifact", "quality_inputs":"质量比较输入artifact", "performance_inputs":"性能比较输入artifact"}
.venv/bin/hcu-infra-agent optimization-check modules-example CHECK.json --output .work/assessment.json
```

质量和性能必须对应同一 snapshot、context、模型和 workload；失败会替换当前 pass 报告，防止误用旧结果。
通过只产生待复核报告；仍需原有 flow-submit（含局部迭代输入）、flow-review 和 flow-advance。计划、仿真或 query 命中都不代表已提速。

## 已执行的使用验证

2026-11-09 在 NMZ_zz_26 用户容器完成了以下离线调用，记录见 [本次验证](validation/1109/README.md)：

- 读取已有 HCU TP2 capture，两 rank 各 **15,843 个 GPU kernel 事件**；保留原 trace、分析和实际原生 triage 报告。
- 根据该 profile 生成优化计划；没有新启动模型服务或宣称候选提速。
- 真实调用 **DCUSim 2.0.0**，记录 NMZ 示例配置的延迟、TPS、显存预测、配置哈希和完整默认参数。
- 实际查询并读取 Cookbook 镜像和知识正文，返回可核对的路径、行号、SHA256 与 revision。
- 质量/性能评估路径另由固定合成输入回归覆盖，不冒充真实模型 A/B 优化。

## 其他能力与架构

持续保留环境/设备占用验收、源码快照传输、local/SSH/Docker/Slurm/K8s 命令卡、资源租约、未知执行 reconcile、
团队依赖/会话绑定/消息、人的指导文件、服务观测/outbox、streaming benchmark 和当前证据 HTML 报告。

完整任务状态：

```text
prepared → environment_checked → baseline_validated → profiling
         → optimizing → serving_ready → serving → completed
```

CPU 协议演示：`hcu-infra-agent demo /absolute/new-directory`。演示是合成质量/性能数据与 fixture reviewer，不是真实 HCU 验收。
回归：`.venv/bin/python -m pytest -q -rs`，使用本地临时目录。

[阅读导航](docs/skill-reading-map.md) · [架构](docs/architecture.md) · [模块输入与边界](docs/modules.md) · [契约](docs/contracts.md) · [优化方法](docs/optimization.md) · [知识接入](docs/knowledge.md) · [验证范围](docs/acceptance.md)

基础源码来自 HCU-TrainFlow，参考 infra-agent-v2 的 profile 驱动方法；固定来源与派生记录见 [provenance.json](provenance.json)。保留上游 MIT 许可，DCUSim 与知识/Skill 作为外部绑定，不复制原生工具或训练语料。
