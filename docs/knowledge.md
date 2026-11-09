# 资料来源与安装边界

Cookbook 只从 https://github.com/HYGON-AI/inference-cookbook-das 查询；search 返回提交固定的官方页面，read 返回正文和相关链接。它不依赖手动知识库，也不会回退到镜像。

HCU-Knowledge 由使用者手动安装后设置 knowledge_root。doctor 显式报告目录、正文和入口是否存在；安装 Skill 不会 clone、bootstrap、更新或重建它。
knowledge-query 默认检索整理后的本机跟踪正文，knowledge-read 读取固定页；原生索引可用时使用 knowledge-search。结果覆盖和失败不得伪装为完整检索。

SimTools 的获取源为 https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools，component-fetch 使用新目录显式 clone，安装使用隔离的 Python 3.10 环境。每次安装/检查先选择运行容器，详情见 README。
