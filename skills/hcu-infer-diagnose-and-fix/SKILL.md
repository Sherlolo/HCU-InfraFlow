---
name: hcu-infer-diagnose-and-fix
description: 分析并解决 HCU 模型启动或运行失败、hang/卡死、崩溃/OOM 和精度异常，保留现场与失败请求，定向重放、定位根因、修复或缓解并验证恢复。
---

# HCU 推理故障诊断与修复

本 Skill 承接 `fault-tolerance` 阶段，能力聚焦模型失败、hang、崩溃和精度异常；扩容配方由部署 Skill 负责，健康服务的性能优化由模型优化 Skill 负责。旧 `operate` 任务若经兼容路由进入本 Skill，健康观测与扩容部分交回主控/部署，仅承接实际异常。独立诊断只在用户范围内执行，已有日志可直接分析，不要求先部署或跑完整优化。

通过安装目录 `workspace.json.project_root` 定位工程；源码版使用仓库根。读取 `docs/operations.md`、`docs/contracts.md` 和 [现场与重放](references/incident-replay.md)。日志、请求、dump 和诊断实验写入私有工作区，参考源码与知识库只读。

## 从症状到解决

1. 固定 context/epoch/attempt、节点/容器/PID 启动时间、全体 rank、模型/tokenizer/量化、引擎与实际库、有效启动配置和最近变更。保存首错、退出码、失败请求或可信 dump，记录最后成功及失败时间；请求内容与凭据按任务边界保存。
2. 使用本仓知识检索 Skill 定向查错误/符号、gfx/DTK、框架版本和机制，读固定正文并核当前源码。可用时读取绑定 `sglang-prod-incident-triage`；其端点、脚本及 CUDA 示例须逐项核 HCU/当前框架适用性，不能直接套用。
3. 先选择问题分支，使用最小能证伪假设的手段。已有决定性首错可直接定位；可重放时在授权隔离目标重放原请求、顺序与并发。不先抓大 Prof，不默认重启线上服务。

| 症状 | 阅读模块 | 关键分流 |
| --- | --- | --- |
| 起不来、加载/运行失败、OOM | [启动与运行失败](references/startup-and-runtime.md) | 配置/依赖/权重/容量/设备首错；明确支持缺口再交模型适配 |
| hang、卡死、请求无进展 | [分布式卡死](references/distributed-hang.md) | 无流量/遥测失效、host 阻塞、rank 分歧、通信与异步生命周期 |
| 进程崩溃、非法访存、core | [崩溃定位](references/crash-diagnosis.md) | 首个设备错误、真实二进制、最小输入与局部复现 |
| 输出变化、NaN、精度异常 | [精度定位](references/accuracy-diagnosis.md) | 固定 oracle、首次分歧、数值/索引/KV/并发状态 |

4. 将事实、根因假设和排除项分开；提出最小修复或可回退缓解，在任务候选中实施。新模型注册/权重或算子支持缺口交 `$hcu-infer-model-adapt`，具体 kernel 修复交 `$hcu-infer-operator-develop`。计算性能归因才调用 Prof Skill，健康后的持续优化返回 `$hcu-infer-model-optimize`。
5. 重放原失败用例并验证受影响边界、固定输出、服务特性和请求持续进展。重启仅证明恢复动作，不能证明根因已修复；不再复现、暂时缓解、根因修复和未验证范围分别报告。优化候选仍需返回原质量/性能和候选 Prof 门槛。

## 恢复、事件和交付

按 [恢复与交接](references/diagnosis-and-handoff.md) 核销未知 operation，再由既定 `recovery_owner` 执行已授权恢复。限定对象与重试预算，保留原失败证据，不按模糊进程名清理。`observe`、outbox claim/complete 只登记观测与处理，不能当作自动恢复。

报告故障类别、影响、已检查项、最强证据、根因/置信度、修复或缓解差异、原用例回归、恢复后请求/质量结果、剩余风险和下一步。没有真实运行时明确 source-reviewed/hardware-not-run；长期稳定性仅声明实际观察窗口。
