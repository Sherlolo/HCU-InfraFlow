# 现场保留与失败请求重放

先保存实际启动命令和有效配置（脱敏）、源码/插件/动态库身份、节点/容器/设备、所有角色/rank 的日志与首错、时间线、最后成功请求。绑定 task/context/epoch/attempt，不用不同重启的片段拼一个因果链。

## 观察与重放

服务可达时取当前版本支持的 health、模型身份、队列/loads、指标和实际请求结果；端点是否有副作用先核当前实现。无流量的健康快照无法解释负载期 hang，404 也可能是接口不支持。服务已退出则从日志、退出码、可信 dump 开始，不为取 bundle 先重启。

保存触发请求、token/模板/采样、到达顺序、并发、cache 冷热、session/KV 初态；状态相关故障重放必要前序，不能只留下最后一条。dump/pickle 只处理可信且固定哈希的本任务原件，优先安全解析，不照搬绕过安全加载的脚本。大张量、私有请求不输出到共享日志。

隔离目标使用同版本、依赖、模型和配置；缩小长度、并发、rank 时记录变化及是否仍复现，不能把缩小后的成功当原场景修复。每个诊断运行给新 attempt，设置超时和次数预算。没有重放环境就交付现有证据与最小复现方案，明确未执行。

已绑定的 SGLang incident 工具须先读本地 Skill 与脚本帮助。vLLM 或旧 SGLang 用实际 API/日志，不强行调用 SGLang 端点；GPU 调试器、dump 开关从 HCU/DTK 版本查证，不套 NVIDIA CUDA coredump 命令。

诊断工具按归属选：请求分段不明查 router/worker/PD 时间线；计算路径不明交 Prof 分析；rank 等待交 hang 模块；非法访存查 crash；输出首差查 accuracy。已知 good/bad 快照可在隔离 checkout 用确定性 harness 二分，保留构建失败与无法判定，不能把它们当 good。

方法参考绑定版本 sglang-prod-incident-triage 的 replay-first 流程；没有执行上游工具时不声称已获得其报告。
