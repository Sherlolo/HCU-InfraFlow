# 简化安装与提示词使用验证

参照 HCU-TrainFlow 的 README/安装入口，将主流程改为 setup_hcu_infra.py，直接使用当前选定的 Python。
本次实际运行 `python3 scripts/setup_hcu_infra.py --with-simtools --skills-dir <任务安装目录> --online-check`，随后用 `--replace --online-check` 更新，未再次指定 Skill/组件路径。

- install.log：选定容器的当前 Python 直接安装项目、SimTools 和七个 Skill；没有创建虚拟环境。
- update.log：复用之前的 Skill 目录与组件位置，只刷新本工程管理的安装。
- pytest.log：使用同一容器的普通 python3 运行，224 passed / 2 个 Windows 专属 skip。
- version.txt / demo.json：普通 hcu-infra-agent 命令可用，CPU 全流程演示完成。
- setup-status.json / components.json：保存安装和组件状态。官方 Cookbook 在线检查被 GitHub API 限流，检查缺口保留，未宣称联网就绪。

install-first-attempt.log 保留开发过程中首次预检的失败：源码 egg-info 被误判为另一安装；后续已修正，并加入回归。
外来包/Skill 绑定仍被保护；没有卸载其他项目或覆盖外来 Skill。知识库沿用已有手动安装，不下载、不更新。
README 提供简短安装命令和直接委托 Agent 的提示词，高级参数单独放入 docs/installation.md。
