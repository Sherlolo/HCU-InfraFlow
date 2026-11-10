# 推理原生机制与优化方向

从已知 workload、源码和当前 profile 选择方向。先核现有能力是否适用和命中，优先解决占据关键路径的开销；这是一张问题导航表，不是开关穷举或所有任务必做清单。

| 观测到的问题 | 检查当前引擎/库能力 | 验证与代价 |
| --- | --- | --- |
| prefill 主导 TTFT | attention 后端、chunked prefill、批处理与队列策略、QKV/投影 GEMM、前处理 | 输入长度桶、prefix cache 冷热、实际 batch/token；不能靠命中缓存或减少输入伪装计算优化 |
| decode 主导 TPOT | paged KV 布局与读写、attention/GEMV、graph replay、小 kernel/host launch、采样路径 | 长上下文、动态 batch/尾 batch、KV dtype/scale、图池峰值和 fallback；同时看吞吐与尾延迟 |
| 队列/host 空泡明显 | tokenizer/processor、scheduler、H2D、Python/C++ 包装、同步、分配/清零、编译断图 | CPU 等待不等于 CPU 计算；图模式改变需重新归因，初次编译和稳态分别计时 |
| TP/EP/PD 通信暴露 | rank 到达、消息与拓扑、已有 overlap/chunk、PD 传输及队列平衡 | 纯通信、纯计算与并发窗口分开；stream 相交不证明有效隐藏，检查最慢 rank 与额外 buffer |
| MoE 路由偏斜或专家耗时高 | router、pack/scatter、实际 expert/grouped GEMM、dispatch/combine 后端及负载分配 | 每 call 的 token/split、空专家、极端偏斜、scale；完整 MoE API 计时，不只统计某个 GEMM |
| GEMM 不及匹配预期 | 实际 hipBLASLt/rocBLAS 路由、真实 bench 日志、已加载 tuning 配置和 workspace | shape 表不足以重放完整描述符；由本仓算子模块调用 gemm-tuning，独立与模型内都复验 |
| 多个短 kernel 或转换主导 | 已有融合的 guard、producer/consumer、alias、layout/cast、launch 和中间写回 | 先确认被删中间值无其他消费者；融合后的寄存器/流量/并行度重建，不能因初版更快停止分析 |
| 显存限制吞吐或容量 | 权重分片、KV token 预算、prefix/cache 淘汰、图池、通信工作区与 allocator | 最坏 rank 峰值和长请求、缓存失效/并发；增大并行或 chunk 可能增加通信/尾延迟 |
| speculative、量化或缓存候选 | 当前框架的已支持实现、验证条件、收益依赖的工作负载 | 另核接受率、token/采样等价与任务质量；超出冻结精度/模型语义时先另立比较契约 |

每个候选写明当前有效配置、真实消费者、知识/源码依据、依赖和互斥项、预计省去的工作、支持 guard、代价与回退。新 PR 在隔离候选上验证，执行基点不因“最新”而变更；环境变量的读取时机和是否按存在性判断需看当前代码。

原生选项受缺失实现阻塞时，先查 HCU 知识和当前库能力。可复用则接入，确需开发则交 `$hcu-infer-operator-develop`；完成后返回原来选项、graph/compile、batch、通信/内存等受影响组合复验。调参改变热点、调用或资源竞争时再次调用本仓 Prof 分析 Skill，而不是继续优化已经退出主要占比的旧 kernel。

改变实际模型/精度/工作负载、拓扑身份或部署基线时，按本仓契约开新的比较任务并重新仿真/基线，保留旧最佳与可复用证据。不要为让同一 loop 通过而伪造不变的 context 或设备映射。与用户约定的容量/并行比较可单独列出结果，但不同条件不能包装成等价实现提速。
