---
name: hcu-infer-scale-and-operate
description: 验证 HCU 推理扩容，诊断或观测服务可靠性，并明确恢复责任归属。
---

# HCU 推理扩容与运维

检查用户要求的 TP / EP / DP 或 prefill / decode 拓扑变化时，固定引擎、模型和工作负载身份。扩容后重新验证输出、必需功能、SLA 与吞吐，避免直接外推单卡证据。

故障发生时，先保存实际生效的启动配置、日志和可复现请求，再选择 trace、dump 或通信工具。区分服务故障、无流量、遥测过期和观察器故障。将属于当前上下文及具体 attempt 的规范化观测交给 `observe`；使用 outbox 的 claim / complete，并保留实际处理回执。

只有配置的 `recovery_owner` 执行已获授权的恢复。重启或清理进程组前，先核对旧命令的执行结果，并验证进程确实归当前任务管理。恢复后检查服务就绪、模型身份、预热和请求质量。通知送达、Agent 唤醒和恢复成功分别需要证据。明确报告尚未验证的长期运行行为。

## 工程资源

从选定工程根目录读取 `docs/contracts.md`，了解 CLI 数据格式与阶段门槛，再按当前任务读取部署、优化或运维文档。已安装 Skill 通过同目录下的 `workspace.json.project_root` 定位工程；源码 checkout 中使用仓库根目录。任务证据保存在独立的私有工作区。


## 故障与范围交接

故障分流、多节点扩容或观察器换代时读取 [诊断与交接](references/diagnosis-and-handoff.md)。工作区容量、缓存保护和稳定/快速线交付参照工程 `docs/workspace-and-delivery.md`。复用未变的证据，重新验证改变的拓扑、输出和服务行为；报告未验证的长期运行边界。
