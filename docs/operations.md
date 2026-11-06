# 扩容、诊断与持续服务

扩容前固定模型、workload、精度与配方，分清 DP/TP/EP 与 prefill/decode 分离的变化；扩容后复验质量、SLA、吞吐、负载与通信。
守护读取实际 readiness、请求失败、队列、延迟和观察链路心跳；无流量不能直接认定服务卡死。
本仓 `observe` 消费显式规范化观测，不自称已接入所有框架日志或已有生产告警通道。

事件在 Store 事务内保存并进入 outbox。claim 是领取，bridge 返回是投递，complete 是消费处理回执；三者不能互代。
recovery_owner 唯一负责服务恢复，恢复后核对原服务退出、endpoint/模型身份、warmup、请求质量和新 attempt 证据。
诊断先保留现场与可重现请求，再按故障选择日志、trace、dump 或分布式工具，不能默认所有异常都先 profiling。

CLI 不含无限自动重启或调度器，部署长期 watcher/告警/Agent 唤醒须按站点接入并分别验收。
`command-run` 不确定结果通过 operation-reconcile，命令组需完整 command-group-reconcile，不能仅凭 SSH 超时重发。
