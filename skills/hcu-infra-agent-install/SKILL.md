---
name: hcu-infra-agent-install
description: 在选定的 Python 或容器中安装、更新 HCU Infra Agent 并检查组件，支持按需获取 SimTools，知识库由使用者手动安装。
---

# 安装与组件检查

通过 `workspace.json.project_root` 或源码根目录定位 checkout。阅读 `scripts/setup_hcu_infra.py --help` 和 README。使用者提供环境和已有知识库位置，由 Agent 管理参数、配置文件、检查及内部命令。

在选定且已存在的 Python >=3.10 环境中运行 `python scripts/setup_hcu_infra.py`。脚本直接安装包和七个 Skill，记录解释器及组件路径，不创建虚拟环境。使用 `--skills-dir` 指定实际 Agent 宿主的 Skill 目录。远端容器只安装工具时可使用 `--tools-only`，Agent Skill 保留在其实际宿主。复用 `.work/setup` 中记录的路径，不重复向用户索取。

只有更新本工程管理的 Skill 副本时才使用 `--replace`，不覆盖其他 checkout 的绑定。安装器会拒绝替换归其他安装所有的 Python 包；遇到这种情况，选择已有的合适环境，不静默卸载其他工程。

安装 SimTools 时，选择兼容的 CPython 3.10 Linux 容器，再使用 `--with-simtools`。来源为 https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools；可通过 `--simtools-root` 复用选定的已有源码。安装使用同一个选定解释器。不静默降级不兼容的 NumPy，不升级基础镜像或共享服务软件栈。

HCU-Knowledge 由使用者手动安装。使用 `--knowledge-root` 复用它，或发现已存在的相邻 checkout。安装不附带知识仓库的 clone、bootstrap、更新或重建。知识库缺失属于组件缺口，独立的官方 Cookbook 查询仍可进行。

读取 `.work/setup/components.json`，用生成的 `site.json` 调用 `doctor` 进行后续检查；需要验证网络连通性时加 `--online`。明确保留缺失路径和不可用能力。包检查通过不代表 GPU 访问、模型或性能已经验收。Cookbook 直接从 https://github.com/HYGON-AI/inference-cookbook-das 读取固定提交的内容。

实际运行服务前，确认使用者自己的 HCU/DTK 容器和工作区映射。不复用他人的容器，也不把声明的名称当作已核验的身份。最后说明已安装组件、剩余缺口和简单的下一步提示词，例如：`$hcu-infra-agent 分析这些 trace`。
