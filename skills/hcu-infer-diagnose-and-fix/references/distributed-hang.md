# hang、卡死与无进展

先证明有应推进的请求：同一观察窗口内核接收/完成/token/队列、最后进展时间、遥测新鲜度、所有必需服务 member。区分无流量、router 排队、观察器失联、host 锁/I/O、设备执行、collective 等待。超时阈值以原服务合同和该请求长度为据。

有界采样各 rank 的 host stack、日志与设备/通信活动，保留同一 attempt 和时间基准。先找退出/抛错的 rank，再找仍等待的 rank；仅 rank0 堆栈不能证明整个组死锁。命令 SSH 超时先 operation-reconcile，不能并行拉起另一实例。

对疑似 collective 核有序 group 成员、每 rank sequence/op/dtype/count/split、参与条件、到达顺序及首个分歧；对 EP 检查 token/split 守恒、空专家、偏斜、计划与 generation。通信 kernel 长驻可能等待 peer，不能直接当低链路带宽。所有必要 rank 一起重放，不单独 replay 一个 collective。

对 async/Graph 核 producer event、consumer stream join、buffer 所有权/回收、zero-copy 视图寿命、多 in-flight 是否受支持，以及设备进度所需资源。部分 rank 出错后的 poisoned 状态与错误传播必须收敛；不能忽略状态读取或重复提交已部分写入的通信来“解挂”。相关知识入口：moonep-release-contract、sglang-deepep-shared-layout-graph-lifecycle；具体 API 随父锁版本核对。

逐个检验假设：用隔离请求重放、局部通信复现或受控关闭一个已怀疑机制。Graph-off/同步模式若解除卡住，只说明时序相关线索；最后必须回原执行形态、组规模、并发和动态输入验证。故障注入仅在已授权隔离范围执行。

修复验收检查所有 rank 的请求进展、正确输出、无新首错、超时内完成及重复请求/多 generation；记录实际观察时长。扩大 timeout 或一次重启仅作缓解，保留根因未知状态。
