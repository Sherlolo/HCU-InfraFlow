# 推理精度异常与首次分歧

先固定独立可信 oracle 与原失败请求。比对权重/分片、tokenizer/chat template、采样/seed、输入 token、量化及 KV dtype/scales、模型模式、position/mask、cache/session 初态和输出协议。随机生成 token 不一致不自动证明 kernel 错误；确定性诊断可以辅助定位，但最终按原任务质量合同验收。

保留输出、logits/任务指标、NaN/Inf 与出现位置；按冻结的绝对/相对容差、特殊值策略和任务阈值判断，不事后放宽。无另一 GPU 平台时使用已验初始实现、可信高精度参考或语义 oracle，说明参考范围；不能因没有 NVIDIA 环境放弃正确性。

从首次不同的 token/阶段/层查到输入与输出，必要时二分调用链。采集张量快照需保证异步 copy 完成且内容属于当时 generation；加 hook 后差异消失须记录时序扰动，不以新同步掩盖竞争。

| 首差位置 | 核对重点 |
| --- | --- |
| 输入/embedding/位置 | tokenizer、模板、weight shard、padding、position、多模态 processor |
| attention/KV | causal/mask、变长边界、page table、KV scale、prefix 复用、跨请求污染和释放 |
| GEMM/融合/量化 | 累加与 cast/舍入顺序、FMA/重结合、溢出、stride/alias、真实 dispatch |
| MoE/通信 | 路由/split、有效 token/空专家、scale、规约顺序、输出所有权、event/generation |
| 采样/协议 | logits processor、temperature/top-k/top-p、stop/EOS、流式与工具输出语义 |

低精度通信区分位复制和数值 SUM；同 dtype 不证明相同 scale/舍入。核原地接口的成功/拒绝状态，避免返回 None 后再做一次 collective。知识条目 aiter-int8-fp8-collective-contract 只提供对应版本的查证入口，不是任意库的支持表。

局部修复先重放首差输入和边界，再全模型短/长×单请求/并发、graph/fallback、KV 多次复用及必需服务特性；优化任务还要无 profiler 性能与候选 Prof。报告根因、原错误幅度与修复结果、未覆盖范围。训练 loss、梯度或优化器测试不能代替上述推理证据。
