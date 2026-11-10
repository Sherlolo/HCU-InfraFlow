---
name: hcu-infer-operator-develop
description: 将 HCU 推理 Prof 热点或模型适配的缺失算子转成 LightOp 融合、Triton/TileLang/HIP 开发、GEMM 调优任务，并接入 SGLang/vLLM 验证实际分发与回退。
---

# HCU 推理算子开发

使用当前任务的真实 Prof analysis，或模型适配模块登记的 missing kernel gap。模型尚未跑通时用后者恢复正确性，不编造性能热点。先检查当前引擎、量化与插件的已有实现，记录为什么不能直接复用。

恢复真实 shape、dtype、stride/layout、prefill/decode、量化 scale/zero-point、输出公式、别名/原地写、stream 和图捕获约束。融合还需确认 producer/consumer 的中间结果是否被其他分支使用、通信是否改变数值或同步语义；总 kernel 时间不是可节省墙钟时间。

按证据选择专项 Skill。源仓库为 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)，从实际安装记录读取路径，不假设相邻 checkout：

| 需求 | 路由 |
| --- | --- |
| 融合与 LightOp 开发 | `lightop-kernel-agent-loop`；保留源码、wrapper、绑定、config 与构建契约 |
| Triton 已有算子优化 | `kernel-triton-optimize`；无可调用 baseline/reference 时先 `kernel-triton-baseline` |
| HIP 已有算子优化 | `kernel-hip-optimize`；缺失算子先 `kernel-hip-baseline` |
| TileLang | 显式绑定实际可用的 TileLang Skill 与已验证 HCU 后端；缺失时报告组件缺口，不冒充 Triton 或已运行 |
| 实际 BLAS GEMM 热点 | `gemm-tuning`；核实是否真正经过 hipBLASLt/rocBLAS，按其子路由执行，不把自定义 MoE/Marlin 当作库 GEMM |

运行入口和数据契约见工程 `docs/operator-development.md`。已安装 Skill 用同目录 `workspace.json.project_root` 定位工程；源码版使用仓库根。`operator-plan` 留存当前分析、契约和绑定 Skill 哈希，`operator-dispatch` 将固定任务交给实际 Agent runner，runner 应读取该 Skill 所需的本地资源。读取参考仓库保持只读，在任务私有工作区开发。

先恢复可靠 oracle，再做正确性和同卡重复性能；保留原生 autotune 的可比最佳基线、真实编译参数、gfx/DTK、最终二进制与必要 ISA 证据。按 workload 频率覆盖 shape，包含边界、非对齐、非连续输入、数值极端和未支持形状回退。GEMM 配置需保持 dtype/转置/布局兼容，补齐相邻 token M 后重新验证；不能用兼容点插值代替精度测试。

完成开发后按目标框架的当前源码生成注册、编译、分发与回滚 adapter。SGLang/vLLM 的插件或 custom-op API 随版本变化，核对所选 commit 的实现，避免硬编码猜测入口。仅对支持的架构/shape/dtype 选择新路径，其余走原生 fallback。`operator-integrate` 自动顺序执行 adapter 的 apply、verify；确定失败执行 rollback，远端结果不明则保留操作 ID 给 recovery_owner 核查。

接入验收包含 build/import、算子正确性、框架实际调用候选路径及 serving smoke。通过接入后继续固定输出/必需特性验证、关闭 profiler 的端到端重复性能和独立 flow 复核；退出码零、写出补丁或局部提速均不代表模型优化通过。保存失败候选、回滚结果与停止原因，完成后交回模型适配或优化循环。
