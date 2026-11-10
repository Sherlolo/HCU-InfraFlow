# 安装与运行入口

安装脚本 `scripts/setup_hcu_infra.py` 使用当前选定 Python，直接安装包和 Skill；没有创建或切换虚拟环境的步骤。

- 默认安装全部工作流与专业 Skill 到 `$CODEX_HOME/skills` 或 `~/.codex/skills`，可用 --skills-dir 指定。
- --with-simtools：CPython 3.10/Linux x86_64 下获取并安装 DCUSim。--simtools-root 可复用指定来源。
- --knowledge-root：绑定手动安装的知识库。未提供时查找相邻 hcu-knowledge；始终不自动安装、更新或重建知识库。
- --pilot-root、--kernel-skill：复用已有推理 Skill/算子入口。推理 Skill 缺失时只在本项目 .deps 中获取，不改已有 checkout。
- --replace：刷新本工程自己管理的 Skill，不覆盖外来绑定。
- --tools-only：只装当前环境的包与组件，用于 Agent 和实际推理容器分开的部署。
- --wheelhouse：离线 wheel 来源（pip 使用 --no-index）。源码也要预先准备，可用 --pilot-root / --simtools-root 指定。
- --test：同时安装测试依赖。--online-check：额外验证官方 Cookbook 网络入口。

保留工程 checkout，安装 Skill 的 workspace.json 记录 project_root 和 python。
`.work/setup/status.json` 保存安装入口，site.json 保存组件路径，components.json 保存组件检查，bindings.json 在依赖条件满足时生成。
Skill 和 Agent 读取这些记录维护内部输入，使用者不需要自己填 JSON。其他工作区需要调用工具时，Agent 使用所记录的解释器执行 `-m hcu_infra_agent`，不依赖 PATH 猜测。

包与 Skill 安装成功不意味着全部组件或 GPU 就绪。缺失知识、服务环境或仿真时记录缺口，仍可按范围使用已就绪能力。
当前 Python 已绑定其他 hcu-infra-agent 项目时安装器拒绝静默替换，请选择已有的合适环境。

再次安装会复用已保存的 Skill 安装目录及组件位置，显式参数可覆盖它们；--serving-python 可指定实际服务解释器。

普通更新：重新运行 setup_hcu_infra.py --replace，再开启新 Agent 会话。若 Skill 目录属于另一工程，使用该工程的更新流程或明确选择新目录。
旧公开入口 bootstrap.py 仍可调用同一安装器；旧的 setup_simulation.py --environment 方式已由“安装到当前所选解释器”替代。
