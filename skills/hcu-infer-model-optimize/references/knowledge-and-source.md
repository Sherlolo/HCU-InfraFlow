# HCU 知识检索与当前源码复核

在首次判断 HCU 机制、出现新适配/性能/故障问题，或旧证据与当前版本冲突时使用。已有同条件结论直接引用；相同问题的连续试参不用每条命令重新搜索。

## Skill 与本仓工具的关系

领域检索使用 `$hcu-knowledge-search` 的问题拆解和证据阅读方法。已安装 Skill 的 `workspace.json.root` 是知识工程根；本仓安装配置的 `knowledge_root` 指向同一选定资料源。它们与 infra-agent 的 `workspace.json.project_root` 用途不同，不从父目录猜路径，也不把站点绝对路径固化到 Skill。

为保持本仓独立，本任务通过本仓 Python API `hcu_infra_agent.references.bind_knowledge/search/read` 与对应 CLI 读取知识文本，不执行资料源的 `kb.py`、安装脚本或 TrainFlow 命令。调用已安装 `$hcu-knowledge-search` 时明确这一执行约束；Skill 不可用时使用本指引和本仓接口，并报告未加载原生 Skill。外部大库可以只提供 `knowledge/` 资料，不需要其他工作流仓库、原生索引服务或 profiler Skill 才能查询。

Agent 从选定安装记录或用户输入取知识根，用任务目录保存独立绑定：

```bash
hcu-infra-agent knowledge-bind "$KNOWLEDGE_ROOT" "$TASK_DIR/knowledge-source.json"
hcu-infra-agent knowledge-query "$TASK_DIR/knowledge-source.json" \
  "SGLang attention gfx938 KV cache stride" --limit 8
hcu-infra-agent knowledge-read "$TASK_DIR/knowledge-source.json" \
  "$MATCHED_RELATIVE_PATH" --start 1 --lines 120
```

示例查询仅演示实体组合，实际使用当前型号/gfx/DTK、工程与符号；不得把示例架构当作现场事实。使用绑定的 Python 运行本仓 CLI，命中路径相对于 `knowledge/`。默认 curated 查询覆盖已跟踪的专题/教程/案例/概览等文本，明确的上游/原文需求再用 `--scope all --timeout 180`。检索返回 partial/退出码 2 是覆盖声明，仍应读取有效命中；超时或空命中不表示整个大库没有答案。

新的 `knowledge-source` 绑定仅供本仓 `knowledge-query/read`；既有 `bind/bindings-check/knowledge-search` 属于旧的工具整体绑定/原生查询路线，不把两种格式混用。新绑定校验自身身份和资料目录范围，不要求外部可执行脚本存在。正文哈希和检索时仓库 revision 供溯源，绑定根目录本身不冻结整个知识 corpus。

此路径只读本机 Git 跟踪的知识文本，不等价于知识工程的飞书、Prof 档案或线上 PR 全量检索。需这些能力时明确范围和已有工具，不能假装本仓已提供；也不把本地无命中升级为自动更新大库的理由。

## 查询与证据复用

先组合“工程 + 错误/符号 + 机制”，再根据缺口加 shape、dtype、gfx、DTK/库版本、并行组。例如先查当前 attention backend 的符号与 KV 布局，再查该 gfx/版本的长上下文案例；一次塞入全部日志容易误筛，按实体和机制分次收敛。

命中后读取正文和关联固定原件，记录：来源页/行号/哈希或 revision、适用版本与硬件、支持/未验证条件、当前假设得到的支持与反证。若找到硬件基准，区分标称、历史独立实测和当前现场实测；不能用现场低值自行定义可达上限。索引或页面过旧时保留缺口并直接读取可用资料，普通查询不附带 git pull、bootstrap、来源登记或大库更新。

下列情况才重查相关证据：DTK/gfx/框架父锁变化、实际 backend/shape/并行/精度变化、出现新错误、profile 与先验冲突或来源覆盖不足。未变的独立数值/实现资格可引用，不重复验证全部算子。普通查询可产生工具自身的必要缓存，但本仓不改变知识正文、参考源码、全局 Skill 或发布状态。

## 从知识到正在运行的实现

按照真实 launcher/import → 框架配置与 dispatch → 插件/库 API → 编译制品/动态库追踪。固定当前工作分支和已有 patch，核依赖 gitlink/lock、支持 predicate、配置覆盖顺序、实际加载路径及 fallback。资料中新功能、上游已合入和现场已生效是三个不同结论。

HCU 数学库/通信库问题优先核 HCU 维护分支和匹配手册；AMD/NVIDIA 文档仅提供其范围内的机制比较。同名 API、环境变量或相近 gfx 不能推导兼容。源码缺失时保存符号/版本/复现及未知，不假装完成源码审计。

下一实验应关联该知识依据、具体消费者和 profile 热点。检索/阅读结果用 `artifact-add` 保存，填入 `optimization-plan.references`，避免另建不可追踪的结论账本。需要对知识或外部项目提出更新时按原任务授权另行处理，本优化闭环不自动更新大知识库。
