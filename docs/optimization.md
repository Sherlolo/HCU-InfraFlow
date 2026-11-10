# Profile 驱动推理优化

先测固定无 profiler 基线，再捕获有代表性 prefill/decode、并发/长度、TP/EP/PP/PD rank 证据。
保留实际采集端点、全部命令、trace 文件哈希与 rank 覆盖；输出目录存在不证明 trace 成功，CPU-only trace 不证明 GPU 已采集。
主分析使用 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot) 的 [llm-torch-profiler-analysis Skill](https://github.com/Sherlolo/hcu-infer-pilot/blob/main/skills/llm-torch-profiler-analysis/SKILL.md)，辅助复核使用 [TraceLens](https://github.com/AMD-AGI/TraceLens)。分别保留实际调用和输出；原始报告、推理分析和实际服务验证分别成立。

依据耗时证据选择调度、KV/cache、量化/GEMM、attention、MoE、通信或 host 路径。方向来自观测与假设，不运行固定旋钮穷举。
区分总 kernel duration 与墙钟，重叠不能相加，prefill/decode、shape、dtype、rank 分开比较。覆盖不足时补采集而不补猜测。
查当前源码、HCU-Knowledge 与 PR/本地历史确认是否已有实现；优先修复未命中路径。必要时调用 BLAS/MoE/LightOp Skill，保持真实 shape/布局和生效证据。

候选先局部数值和 dispatch 验证，再固定请求、输出/必需特性、无 profiler 重复性能以及资源代价。
微基准更快不代表端到端更快；合并候选要重测，不能叠加独立收益。输出精度变化不应被吞吐收益抵消。
提交 profile_evidence，独立 review 后保留或回退。停止条件来自预算、可信上限、平台期、质量风险或明确资源缺口。

benchmark CLI 使用 closed-loop 并发和客户端时间，固定文本或 token ID 请求；cache_policy 明确为 endpoint-state-not-reset。
跨框架公平比较需通过绑定 benchmark Skill 核对 tokenizer/token 数、缓存、服务 flag、设备/负载与场景，不由一次客户端结果自动宣称公平。
TTFT 是首个非空文本 chunk 到达时间；TPOT 是首末文本 chunk 间时间除以输出 token 间隔，chunk 聚合影响估计。


## Prof Skill 与 TraceLens 的配合

从 [联合分析指引](../skills/hcu-infer-analyze-and-optimize/references/profiler-and-tracelens.md) 进入。Agent 实际读取绑定版本的上游 Skill，默认用其 `scripts/run_triage_report.py` 分析已有 Prof，并将 Markdown、命令记录和原始输出写入私有工作区。外部来源使用任务选定的 revision 和可配置路径，不依赖作者机器上的目录。

TraceLens 根据问题补充 eager/推理图报告、通信偏斜和前后比较；核对 graph capture、窗口、rank 组、shape 与当前 HCU 的性能建模参考。两种工具结果需要按相同时间分母和覆盖范围复核；缺失组件或解析失败保持可见。

`prof-analyze` 的 `triage_bindings` 可触发上游报告脚本，基础解析本身不运行 TraceLens。模型结构图、mapping/formal 双 trace 与 TraceLens 按所选版本单独执行并归档，然后作为 `optimization-plan.references` 交接。完整调用示例、已有入口限制及报告要求见联合分析指引。
