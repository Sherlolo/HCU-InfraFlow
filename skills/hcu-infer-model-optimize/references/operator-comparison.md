# 模型内外同条件对照

用于局部算子更快但服务更慢，或热点是否有实现空间尚不清楚时。先保存具体 run/rank/phase/call 的契约，再构造独立重放。

| 调用 | 重放所需条件 |
| --- | --- |
| GEMM/grouped | 每组 shape/stride/transpose、dtype/累加、alpha/beta、epilogue/scale、workspace、真实后端；不使用平均 M 代替分组 |
| Attention/KV | Q/K/V 布局、head/group、causal/mask、长度与 page table、position、KV dtype/scale、cache 初态与写回 |
| MoE | 实际路由/token/split、空专家与偏斜、量化 scales、dispatch/combine 输出所有权和事件 |
| 通信 | 有序 process group、拓扑、各 peer split、发送接收守恒、dtype、原地语义、异步完成和 stream |
| Copy/cast/其他 | 源目标设备、字节与 layout/offset/alias、pinned/nonblocking、完整子 kernel、分配/清零/同步 |

动态路由、mask 和索引的真实值影响算法；相同 shape 的随机张量只是合成回放。必要时保存可信输入样本及脱敏策略。采集内容带来的同步另列，不混入正式性能。

分别保存：关闭 profiler 的端到端测量、模型内诊断 trace、独立重放的设备及 host-to-completion 时间。编译/预热/生成输入在计时外；实际 API 必需的 copy、reset、分配、等待必须计入。明确冷/热缓存、工作集、频率与共享负载；所有通信 rank 共同重放，不能孤立 replay collective 导致等待 peer。

差距超出采样噪声后才归因：独立也慢则核匹配上限和实现；独立正常而模型慢则查 CU/HBM/NIC 竞争、stream、rank 到达与 host 提交；kernel 短而 API 长则查小调用、分配及同步。同名/同层但调用条件不同不能强配；服务时间求和与区间并集分开。

改变 tile/融合后重算实际流量、资源与并行度，初版快于 eager 不表示近上限。局部正确性和实际 dispatch 通过后回模型复验固定请求/状态及正式场景，保留失败样本。来源为 TrainFlow operator-comparison 的推理改写，不包含反向与优化器状态。
