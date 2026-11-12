# 推理通信与重叠优化

当真实 profile 指向 TP/EP/PD 通信与等待时读取。本仓不固化特定 DTK 的环境变量和库 API；由已绑定 skill 和当前源码确定。

## 通信与重叠

保留 rank→设备/节点/NIC、TP/PP/DP/EP/CP 实际组、消息字节/dtype、collective/P2P 顺序、stream/event 和 producer→consumer。跨 rank 先校时；代表性采样不等于全组一致性验证。通信 kernel 驻留可能含等待，时间线相交不证明通信已有效隐藏。

比较同条件纯通信、纯计算和并发窗口，列暴露通信、计算退化、尾延迟和额外 buffer。`max(Tcompute,Tcomm)` 仅适用于边界清楚且资源独立的理想窗口；共享 CU/HBM/NIC 竞争及依赖会抬高下界。关注最慢 rank、路由偏斜、空 expert、小 token、长上下文和动态 batch。

先验证现有分块/调度、早发晚等、backend 配方；确需 AG-GEMM、GEMM-RS 或 dispatch/compute/combine 融合时，明确发布/可见性、等待范围、进度资源、buffer 回收、generation、尾块和异常路径。异步 handle 返回不代表输出已可读；graph replay、stream join 和跨请求复用须单独检查。已经部分写入后的失败不能直接回退并重复 collective。

低精度通信要核对 scale、累加/舍入顺序和溢出语义，不能只凭 dtype 相同接入原生 SUM。更换 EP backend 要核接口、父版本锁、输出所有权与 supported topology；同名 API 不证明节点内外、普通 eager 与 graph 路径等价。保持服务请求、KV/会话状态以及多租户隔离语义。

