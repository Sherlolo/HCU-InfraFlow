---
name: hcu-infer-knowledge-search
description: 检索与版本相关的 HCU 推理知识，并根据已绑定的本地来源选择性能分析、基准测试、BLAS、MoE 和故障诊断 Skill。
---

# HCU 推理知识检索

读取选定的 bindings JSON，使用 `bindings-check` 验证。针对实际模型、引擎及版本、观测到的机制调用 `knowledge-search`。采用结论前阅读结果正文和来源修订。分别陈述来源或 PR 参考、本地实现和硬件实测。

原生索引、权限或运行环境不可用时，说明缺口；仍可根据明确路径和哈希继续阅读源文件。入口哈希只覆盖对应文件，不覆盖全部嵌套脚本。执行外部 Skill 的工具前，核对依赖、版本和实际输出。查询不附带 bootstrap、知识仓库更新或全局 Skill 安装。仅适用于训练的检索材料不能作为推理验收依据。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。

## 无派生索引时的查询

使用 `knowledge-query` / `knowledge-read` 查询和阅读受版本管理的文本，使用 `cookbook-search` / `cookbook-read` 查询官方在线 Cookbook。这些命令不创建 Store，也不修改已绑定的仓库；partial / 退出码 2 表示覆盖有限，仍保留可用命中。阅读匹配正文，不只看片段。`knowledge-search` 保留为单独的原生索引查询入口。命令和示例见 `docs/modules.md` 及 README。

## 已安装的运行入口

通过 `workspace.json.project_root` 定位工程。存在安装记录时复用 `.work/setup/status.json`、`site.json` 和 `components.json`，使用记录的 Python 执行 `-m hcu_infra_agent`，让使用者无需管理 PATH、JSON 绑定或内部命令。在选定容器中核对组件缺口。使用者提供目标和已有资料，由 Agent 维护任务规格与工具输入。


## 专项来源与适用性

算子、性能工具和优化历史的公开入口为 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)。先按架构/机制定位，再以实际 commit、DTK、gfx、shape/dtype 和框架父依赖锁核对；同名能力不能视作兼容。用 `bindings-check` 发现入口变化后重新审阅，不静默刷新。源码审阅、CPU 实验和 HCU 实测分别陈述；缺索引时直接读取已固定原件，不把无命中当作不支持。具体专业模块见工程 `docs/operator-development.md` 和 `docs/model-adaptation.md`。
