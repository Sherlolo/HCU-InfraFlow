# HCU Infra Agent

## 面向 HCU 大模型推理的智能体协同工作流

给出模型、环境和目标，由主控 Agent 协调部署、Prof 分析、性能优化、仿真和资料查询。内部配置、命令和证据由 Agent 管理，使用者主要通过提示词委托任务。

**当前版本：`0.4.0`。** 支持 SGLang / vLLM 相关工作，也支持只查 Cookbook、只做仿真、只分析 trace 或只诊断问题。

## 如何开始

安装后，在支持 Skill 的 Agent 中说：

> `$hcu-infra-agent` 在 `<环境或容器>` 中部署并优化 `<模型>` 的 SGLang 推理，目标是 `<吞吐或时延目标>`。模型和已有资料在 `<路径>`。

主控先确认任务范围、已有环境和可用证据，再选择相应模块。已知条件和授权会复用，缺少必要信息时才补充确认；不需要在提示词里重复所有检查项，也不用手工维护工具输入文件。

安装会给 Skill 保存工程位置和 Python 入口，换目录开任务仍可定位。真实推理使用哪一个 HCU/DTK 容器、哪些设备和工作目录，需要按任务确认。

### 使用示例

下面的 `<...>` 换成实际信息即可。

**检查安装与环境**

> `$hcu-infra-agent-install` 检查 `<环境或容器>` 中需要的组件并补齐，知识库已手动安装在 `<路径>`。

**模型适配**

> `$hcu-infra-agent` 在 `<环境>` 用 SGLang 跑通并优化 `<模型>`，模型、数据和启动资料在 `<目录>`，目标是 `<目标>`。

**算子开发与自动接入**

> `$hcu-infer-operator-develop` 按 `<Prof 分析>` 的热点开发或优化算子，复用 hcu-infer-pilot 的 LightOp、Triton/TileLang 或 GEMM 技能，接入 `<框架和版本>` 并验证实际分发、精度与回退。

**新模型适配**

> `$hcu-infer-model-adapt` 将 `<新模型及固定版本>` 适配到 `<SGLang/vLLM 基点>`，补齐权重和架构支持；缺算子时迁移或实现 Triton/HIP，再建立可验证基线。

**指定卡数持续优化**

> `$hcu-infer-model-optimize` 在 `<卡型和卡数>` 下先仿真并行策略，建立 `<模型>` 基线；跑不通先适配，再按 Prof 迭代优化，每轮通过精度和性能检查后保留，输出优化报告。停止预算为 `<轮数/时间>`。

**只分析 Prof**

> `$hcu-infra-agent` 分析 `<模型>` 的推理瓶颈，trace 和启动脚本在 `<目录>`。这次只分析，暂不优化。

**服务已跑通，继续优化**

> `$hcu-infra-agent` 这个模型已经跑通了，继续优化性能。工程、基线和日志在 `<目录>`。

**性能仿真**

> `$hcu-infra-agent` 用 SimTools 比较 `<模型>` 在 `<HCU 型号>` 上 TP2 和 TP4 的 prefill、decode 及显存预测，输入/输出/并发为 `<配置>`。

**查询官方 Cookbook**

> `$hcu-infer-knowledge-search` 查一下 `<模型>` 在 `<硬件>` 上的 SGLang / vLLM 部署配方，返回官方链接、适用镜像和版本条件。

**查询知识库**

> `$hcu-infer-knowledge-search` 查一下 `<框架与版本>` 中 `<机制或问题>` 的 HCU 实现、源码入口和适用条件。

**诊断服务问题**

> `$hcu-infra-agent` 这个推理服务出现 `<现象>`，日志、请求样本和部署资料在 `<目录>`，先帮我定位原因。

## 工作流总览

### 1. 环境检查与部署

核对实际容器、DTK、框架、设备与资源范围；查官方 Cookbook 和 HCU 知识，选择适用配方。冻结模型、tokenizer、精度与工作负载，建立可复现的启动及输出质量、性能基线。

### 2. Prof 分析与性能优化

从真实 trace 分析计算、通信、空泡和负载分布，按主要瓶颈检查已有引擎和算子路径。候选经过局部正确性、固定输出/特性、无 profiler 的重复性能与 SLA 验证，再进行独立复核；生成计划或报告不表示已提速。

### 3. 仿真、扩容与服务观察

用真实 DCUSim 评估模型、并行和显存假设，保留全部生效参数。扩容或恢复后重新验证服务质量和性能；观测事件、Agent 消费与实际恢复分别核对。

| 模块 | 主要能力 |
| --- | --- |
| 算子开发与接入 | LightOp 融合、Triton/TileLang/HIP、GEMM tuning，框架 apply/verify/rollback |
| 模型适配 | 新模型发布锁、架构/权重缺口、缺失 kernel 迁移与真实测试门槛 |
| 模型优化闭环 | 指定卡数仿真、基线失败转适配、Prof 驱动迭代、质量/性能与复核、逐轮报告 |
| Prof 性能分析 | 多 rank trace、热点/通信/空泡、原生 triage 和证据归档 |
| 性能优化 | profile 驱动的假设、实验、质量/性能验收与独立复核 |
| 性能仿真 | DCUSim 的 prefill/decode、TPS 与显存预测 |
| Cookbook 查询 | 直接查 [官方 inference-cookbook-das](https://github.com/HYGON-AI/inference-cookbook-das)，返回固定提交页面和相关链接 |
| 知识库查询 | 用户手动安装的 HCU-Knowledge，支持正文检索、阅读与来源核对 |

仿真和资料用于形成假设，不替代实测。实际方法与边界见[模块指南](docs/modules.md)和[架构](docs/architecture.md)。

## 安装

准备 Python **3.10+**、pip 和 Git，获取本工程并进入仓库目录，然后执行：

```bash
python scripts/setup_hcu_infra.py
```

脚本直接使用当前 Python 安装本工程和全部工作流与专业 Skill，自动记录工程、解释器及已有组件路径。默认 Skill 目录为当前 Agent 用户的 `$CODEX_HOME/skills`，未设置时使用 `~/.codex/skills`。

需要同时安装 SimTools 时，在 **CPython 3.10 / Linux x86_64** 的适用环境中执行：

```bash
python scripts/setup_hcu_infra.py --with-simtools
```

SimTools 从 [OpenDAS/DCUSimTools](https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools) 获取并安装到当前 Python。脚本会复用兼容依赖，不自动降级不兼容的 NumPy，也不更换容器镜像。

已有手动安装的知识库，或需要指定 Agent 的 Skill 目录时：

```bash
python scripts/setup_hcu_infra.py --knowledge-root /path/to/hcu-knowledge --skills-dir /path/to/agent/skills
```

**知识库需要使用者手动安装。** 安装器只复用已有目录，不下载、更新或重建知识库；未配置时会记录缺口，仍可使用独立的官方 Cookbook 查询。

完成后新开 Agent 会话，直接使用上面的提示词。组件缺口记录在 `.work/setup/components.json`，可让 `$hcu-infra-agent-install` 继续处理，不必手工编辑配置。

安装在 Agent 的实际运行环境中进行；真实模型运行前仍需选择自己的 HCU/DTK 容器。Agent 在本机、工具在远端容器时，可在容器内用同一脚本的 `--tools-only` 安装工具，Skill 保留在 Agent 所在端。

### 后续更新

更新本工程后执行：

```bash
python scripts/setup_hcu_infra.py --replace
```

只更新本工程管理的 Skill；其他 checkout 或其他项目的安装不会被静默替换。已选择 SimTools 的环境可按需追加 `--with-simtools`。完成后新开 Agent 会话。

安装参数、离线方式及高级命令见[安装说明](docs/installation.md)；常规使用只需提供目标和已有资料。

## 如何与 Agent 协作

任务工作区保留看板、问题、指导和证据。可以直接在对话中补充意见，也可以让 Agent 定位对应的 BOARD / GUIDANCE / QUESTIONS 文件。

主控负责选择模块、组织实施和独立复核；资源冲突、未知执行结果先核查现场，不盲目重复启动。共享 GPU 测量和耦合修改由主控协调。

## 验证与阅读入口

安装后可检查入口或运行 CPU 协议演示：

```bash
hcu-infra-agent --version
hcu-infra-agent demo /path/to/new-demo
```

演示使用合成输入，不构成真实模型精度、提速或生产恢复验收。历史验证保存在 `validation/`，不作为新用户的默认部署配方。

[安装说明](docs/installation.md) · [阅读导航](docs/skill-reading-map.md) · [模块指南](docs/modules.md) · [契约](docs/contracts.md) · [架构](docs/architecture.md) · [验证范围](docs/acceptance.md)


专业模块说明：[算子开发](docs/operator-development.md) · [模型适配](docs/model-adaptation.md) · [模型优化闭环](docs/model-optimization-loop.md)。专项工具来源为 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)，通过安装记录绑定；本仓技能不依赖其他参考工程的固定目录。方法对齐见 [TrainFlow 推理转化](docs/trainflow-alignment.md)。
