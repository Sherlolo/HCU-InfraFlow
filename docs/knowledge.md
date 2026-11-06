# 知识与 Skill 接入

`bind CONFIG DESTINATION` 校验并保存 pilot_root、knowledge_root、必需推理 Skill 和 kb.py 的入口 SHA256。
来源地址和固定参考修订保存在 provenance.json 和 knowledge/catalog/sources.json，不批量复制外部知识正文。
`bindings-check FILE` 检查入口有无变化；入口 pin 不代表其全部脚本/子依赖身份已验证，实际调用前还需记录使用文件和原件哈希。
`knowledge-search BINDINGS QUERY` 调用知识库原生 `kb.py --root ROOT search QUERY --mode local --limit 5`。
索引缺失、权限/运行时失败、非 JSON 或超时保持 incomplete，不冒充完整检索；可用 `knowledge-discover BINDINGS QUERY` 直接只读检索 Git 跟踪的 Markdown，返回 partial 及正文行号、路径、哈希；不等于原生全量索引，Agent 仍需阅读原文并记录适用范围。

查询可能生成知识库自身派生缓存，使用其既有本机配置；不调用更新、bootstrap、rebuild 或修改共享正文。本项目不宣称隔离了外部查询工具全部副作用。
维护共享知识只在明确知识维护范围内进行；原始候选日志和中间调试留任务 Store，最终有复用价值的推理经验经过出处、适用条件及公开边界检查后再收录。
外部库同时包含训练资料时按当前推理问题过滤，勿把训练 loss、反向、optimizer 或 checkpoint 数值契约当作推理质量验收。

DCU-Infer-Pilot: https://developer.sourcefind.cn/codes/OpenDAS/dcu-infer-pilot.git
Cookbook: https://github.com/HYGON-AI/dcu-inference-cookbook.git
LightOp Skill 参考: https://developer.sourcefind.cn/codes/whlwhlwhl/lightop-skiils.git
这些是所查配置中的路由，网络可用性和具体版本仍需现场确认。

LightOp 是可选专项入口：默认查 pilot 子模块 `skills/lightop-skills/knowledge/SKILL.md`；未初始化时记录 unavailable，不影响已有 benchmark/profile/incident/GEMM/MoE 入口。需要 kernel 工作时必须补齐真实依赖。站点样例显式绑定用户已有 `lightop-skiils/knowledge/SKILL.md`，不声称缺失子模块已安装。
