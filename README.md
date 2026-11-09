# HCU Infra Agent

面向 HCU 大模型推理的 Agent 工作流，当前版本 **0.3.0**。主要模块：Prof 性能分析、性能优化、性能仿真、Cookbook 查询、知识库查询。
采用 HCU-TrainFlow 的主控、阶段 Skill、持久证据和独立复核机制。安装与组件检查推荐使用 **`$hcu-infra-agent-install`**。

## 先选择运行容器

**请先选择自己的 HCU/DTK 推理容器，并在同一容器内执行安装、依赖检查和实际使用。**
核对容器镜像、Python、GPU/DTK、项目挂载、权重只读挂载及任务目录。不要直接沿用他人的容器名或启动命令。

```bash
# 以下变量由使用者设置为自己的容器名和容器内工程路径
docker exec -it "$HCU_CONTAINER" bash
cd "$HCU_PROJECT"
```

工作流要求 Python >=3.10；当前 DCUSim Linux x86_64 wheel 使用 CPython 3.10。
组件检查会报告解释器、容器检测、Skill、仿真和服务运行时；通过依赖检查不代表 GPU、真实模型或性能已验收。
并发 SQLite Store 应放节点/容器本地盘，源码与导出报告可留共享盘；本地证据要安排备份。

## 安装与检查 Skill

```bash
python3 scripts/bootstrap.py --test
.venv/bin/python scripts/install_skills.py --target "$AGENT_SKILLS_DIR"
```

安装七个 Skill：安装检查、统一主控、部署、优化、运维、知识搜索、知识整理。安装器保留已存在的同名目录，避免误覆盖。
在支持 Skill 的宿主中使用：

> `$hcu-infra-agent-install` 检查当前容器里的 HCU Infra Agent 组件，列出缺失项，准备隔离的 SimTools 环境。知识库由我手动安装。

复制 `examples/site.example.json` 为任务配置，替换为自己的路径；填写所选容器信息、真实 serving_python 和依赖根。

```bash
.venv/bin/hcu-infra-agent doctor site.json --online --output readiness.json
```

`doctor` 检查工作流 Python、Git、各 Skill 入口、知识库入口/内容目录、DCUSim 实际导入、服务解释器中的 PyTorch/SGLang/vLLM，
以及官方 Cookbook 连接。结果按组件给出 ready/missing 与补齐方法；未检查的网络或未配置解释器不会伪装成就绪。

## SimTools：从指定仓库获取并隔离安装

唯一获取地址：[OpenDAS/DCUSimTools](https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools)。

```bash
.venv/bin/hcu-infra-agent component-fetch simtools "$SIMTOOLS_DIR" --output simtools-source.json
# 从下载目录选择与容器 Python/架构兼容的 wheel
python3 scripts/setup_simulation.py --wheel "$DCUSIM_WHEEL" --environment "$SIMULATION_ENV"
# 无网络时，可追加 --wheelhouse "$WHEELHOUSE"
```

获取不会覆盖已有目录；部分获取失败时先核对现场。安装仅写所选隔离环境，不自动执行仓库中的其他安装指令，也不升级基础镜像或共享推理依赖。
把实际 simulation_python、simulation_wheel 写进 site.json，再运行 doctor。需要 numpy 1.x 时先在合适容器中准备，检查脚本会显示实际导入情况。

## 知识库：使用者手动安装

**HCU-Knowledge 需要使用者自行安装，并准备正文、访问权限和适用运行环境。** 本安装 Skill 和组件获取命令不会下载、更新或重建知识库。
完成后将 knowledge_root 指向自己的安装；缺失时 doctor 明确报告 manual-only。知识库缺失不阻止独立的官方 Cookbook 查询。

```bash
.venv/bin/hcu-infra-agent bind site.json bindings.json
.venv/bin/hcu-infra-agent bindings-check bindings.json
```

## 五个模块与用法

| 模块 | 入口 | 产物 |
| --- | --- | --- |
| Prof 性能分析 | `prof-analyze TASK REQUEST` | rank 覆盖、固定原始 trace、热点/通信/空泡、原生 triage 报告 |
| 性能优化 | `optimization-plan` / `optimization-check` | 当前 profile 假设、候选质量/重复性能/SLA 验收；独立复核仍须执行 |
| 性能仿真 | `simulate BINDINGS REQUEST` | 实际 DCUSim 离线预测、模型/工具来源和生效参数，不是实测 |
| Cookbook 查询 | `cookbook-search` / `cookbook-read` | 指定官方 GitHub 的固定提交页面及相关链接 |
| 知识库查询 | `knowledge-query` / `knowledge-read` | 手动安装知识库的正文位置、行号、哈希；默认 curated，可扩大范围 |

### 官方 Cookbook 查询

**直接查询 [HYGON-AI/inference-cookbook-das](https://github.com/HYGON-AI/inference-cookbook-das.git)**，不默认使用知识镜像。
按模型/框架关键词匹配官方 Markdown 路径，读取命中正文，返回 revision、sha256、官方页面 URL。
`cookbook-read` 还返回正文中的相关链接。路径匹配不等于完整语义检索；无匹配或网络失败如实返回。

```bash
# Cookbook 不依赖知识库；此文件可以仅包含 {}
.venv/bin/hcu-infra-agent cookbook-search site.json "Qwen3.8 SGLang" --limit 5 --output cookbook.json
# PATH 和 SHA 使用搜索返回的 relative_path / revision，确保读取同一版本
.venv/bin/hcu-infra-agent cookbook-read site.json PATH --revision SHA --start 1 --lines 100
```

联网查询需要所选容器能访问 GitHub API 与 raw.githubusercontent.com。读取命令/镜像后核对硬件、DTK、框架和量化版本，再决定是否部署；查询不会拉镜像或启动服务。

### 知识库与仿真

```bash
.venv/bin/hcu-infra-agent knowledge-query bindings.json "SGLang KV cache" --limit 5
.venv/bin/hcu-infra-agent knowledge-read bindings.json PATH --start 1 --lines 100
.venv/bin/hcu-infra-agent knowledge-query bindings.json "具体模型与机制" --scope all --timeout 180
.venv/bin/hcu-infra-agent simulate bindings.json examples/modules/simulation.json --output prediction.json
```

知识查询的 partial/退出码 2 表示覆盖有限，命中仍可读取；不把超时解释为无资料。仿真示例必须按实际模型、硬件、P/D 并行和 dtype 修改后再用。

### Prof 与优化

```bash
export HCU_INFRA_WORKSPACE="$LOCAL_TASK_STORE"
# 替换样例中的模型身份、实际 trace、各 rank 窗口和进程组
.venv/bin/hcu-infra-agent task-create examples/modules/task.json
.venv/bin/hcu-infra-agent flow-start modules-example examples/modules/flow.json
.venv/bin/hcu-infra-agent prof-analyze modules-example examples/modules/prof.json --output prof.json
# plan.json 的 analysis 填当前分析 artifact，填写观测、假设、目标和验证项
.venv/bin/hcu-infra-agent optimization-plan modules-example examples/modules/plan.json --output plan.json
# CHECK.json 引用同一 Store 中的 plan、quality_inputs、performance_inputs
.venv/bin/hcu-infra-agent optimization-check modules-example CHECK.json --output assessment.json
```

优化按实际瓶颈和源码推进，不自动穷举旋钮；仿真/查询不代替实测。通过联合检查后仍需 flow-submit、独立 flow-review 与 flow-advance。

## 阅读与验证

[模块指南](docs/modules.md) · [阅读导航](docs/skill-reading-map.md) · [架构](docs/architecture.md) · [契约](docs/contracts.md)

```bash
.venv/bin/python -m pytest -q -rs
.venv/bin/hcu-infra-agent demo "$NEW_DEMO_DIR"
```

CPU 演示与合成测试不代表 HCU 模型精度、提速或生产恢复。历史站点验证只在 validation 中保存，不作为新使用者的默认目录、容器或部署配方。
