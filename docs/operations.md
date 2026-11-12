# 故障诊断、恢复与服务观察

扩容前固定模型、workload、精度与配方，分清 DP/TP/EP 与 prefill/decode 分离的变化；扩容后复验质量、SLA、吞吐、负载与通信。
守护读取实际 readiness、请求失败、队列、延迟和观察链路心跳；无流量不能直接认定服务卡死。
本仓 `observe` 消费显式规范化观测，不自称已接入所有框架日志或已有生产告警通道。

事件在 Store 事务内保存并进入 outbox。claim 是领取，bridge 返回是投递，complete 是消费处理回执；三者不能互代。
recovery_owner 唯一负责服务恢复，恢复后核对原服务退出、endpoint/模型身份、warmup、请求质量和新 attempt 证据。
诊断先保留现场与可重现请求，再按故障选择日志、trace、dump 或分布式工具，不能默认所有异常都先 profiling。

CLI 不含无限自动重启或调度器，部署长期 watcher/告警/Agent 唤醒须按站点接入并分别验收。
`command-run` 不确定结果通过 operation-reconcile，命令组需完整 command-group-reconcile，不能仅凭 SSH 超时重发。

## 入口和验收

`hcu-infer-diagnose-and-fix` 负责失败、hang、崩溃和精度异常的分析解决。详细模块见 [故障 Skill](../skills/hcu-infer-diagnose-and-fix/SKILL.md)：现场与重放、启动/运行失败、分布式卡死、崩溃、精度、恢复交接。已有日志的独立 diagnose 不强制启动服务；修复在任务授权范围内执行。

扩容由主控调用部署 Skill：固定模型和负载、核 TP/EP/DP/PP/PD、容量与最慢 rank，拓扑变更更新 context 后重验质量、必需特性及 SLA。持续观察沿现有 operate/observe/outbox 合同由主控组织；发现异常再进入故障 Skill，故障 Skill 不承担健康服务的扩容或调参。

诊断交付区分已修复、已缓解、未复现与证据不足，保存首错、原失败请求、根因证据、修改/回退及原用例回归。恢复成功需全部必需成员、endpoint/模型身份、预热和固定请求证据；重新加载权重不代表 KV/会话已恢复，重试请求还要核幂等性。没有硬件运行时标 hardware-not-run，不把流程测试当生产恢复证明。
