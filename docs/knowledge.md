# 资料来源与安装边界

Cookbook 只从 https://github.com/HYGON-AI/inference-cookbook-das 查询；search 返回提交固定的官方页面，read 返回正文和相关链接。它不依赖手动知识库，也不会回退到镜像。

HCU-Knowledge 由使用者手动安装后设置 knowledge_root。doctor 显式报告目录、正文和入口是否存在；安装 Skill 不会 clone、bootstrap、更新或重建它。
knowledge-query 默认检索整理后的本机跟踪正文，knowledge-read 读取固定页；原生索引可用时使用 knowledge-search。结果覆盖和失败不得伪装为完整检索。

SimTools 的获取源为 https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools，component-fetch 使用新目录显式 clone，安装使用隔离的 Python 3.10 环境。每次安装/检查先选择运行容器，详情见 README。


## 独立的本仓文本检索 API

`knowledge-bind ROOT DESTINATION` 由本仓 `hcu_infra_agent.references.bind_knowledge` 生成 `kind=knowledge-source` 绑定，DESTINATION 放任务目录，禁止写入所选知识根。随后用 `knowledge-query BINDING QUERY` 和 `knowledge-read BINDING PATH` 读取 Git 跟踪的知识文本和具体正文。根目录只需提供 `knowledge/`，不要求 `kb.py`、其他仓库的 scripts 或完整 profiler/算子工具绑定。绑定记录校验身份与路径范围，查询/阅读本身不创建 Store 或改写来源。

已有全组件 bindings 仍兼容 query/read；新的知识数据绑定不交给旧 `bindings-check` 或原生 `knowledge-search`。后者会调用外部知识工程入口，需要原生能力的任务才选择。本次模型优化的默认文本查证走独立接口，保留目录、revision、命中行与正文哈希。partial/退出码 2 反映本地覆盖有限；飞书、Prof 档案与在线 PR 不属于该接口。

模型优化遇到 HCU 适配、性能、故障问题先使用 `$hcu-knowledge-search` 的检索方法，再核现场分支；具体范围与证据复用见 [知识检索与源码复核](../skills/hcu-infer-model-optimize/references/knowledge-and-source.md)。查询不附带刷新资料、安装大库或重建索引。
