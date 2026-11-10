---
name: hcu-infer-check-and-deploy
description: 检查 HCU 推理环境，适配或部署大模型服务，并建立可复现的启动方式和输出质量基线。
---

# HCU 推理环境检查与部署

核对实际容器与宿主的目录映射、资源分配、设备占用、DTK，以及实际生效的引擎、插件和库版本。优先采用适用的 HCU Cookbook 和启动实现，查看当前版本的 CLI 帮助，不照搬仅适用于 NVIDIA 的参数。外部输入保持只读，缓存、构建产物和日志放在任务工作区。

冻结源码修订与本地实际字节、模型和 tokenizer、量化方式、KV dtype、对话模板、必需端点及工作负载。按实际可用资源预算权重、KV cache、图执行与工作空间峰值，并保留余量。验证服务就绪、请求、流式输出和必需模型功能。保留原始请求、响应和数值证据；反向传播、优化器或训练 loss 检查不能代替推理质量验证。

交付固定命令卡、源码快照、生效环境、资源与健康观测、初始输出质量，以及关闭 profiler 的性能基线。环境差异应先排查，不能直接当成正常上限。端点能够响应并不代表任务已经完成。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。

## 配方与容量评估

采用配方前，先使用 `cookbook-search`，再通过 `cookbook-read` 阅读实际页面，核对来源类型和修订。Cookbook 查询使用官方 HYGON-AI/inference-cookbook-das 网站及固定提交。使用 `simulate` 显式预测模型与并行配置的显存、时延，再通过实际服务校准。输入要求和来源记录见 `docs/modules.md`。

## 已安装的运行入口

通过 `workspace.json.project_root` 定位工程。存在安装记录时复用 `.work/setup/status.json`、`site.json` 和 `components.json`，使用记录的 Python 执行 `-m hcu_infra_agent`，让使用者无需管理 PATH、JSON 绑定或内部命令。在选定容器中核对组件缺口。使用者提供目标和已有资料，由 Agent 维护任务规格与工具输入。


## 按问题补充阅读

首次环境与容量判断、固定执行基线或性能异常时读取 [环境与容量](references/environment-and-capacity.md)。模型 registry、权重或算子缺口交给 `$hcu-infer-model-adapt`（工程 `docs/model-adaptation.md`）；得到 ready_for_baseline 后重新测真实服务基线。完整模型优化按 `$hcu-infer-model-optimize` 先比较指定卡数的仿真策略，部署阶段负责验证实际映射和校准。
