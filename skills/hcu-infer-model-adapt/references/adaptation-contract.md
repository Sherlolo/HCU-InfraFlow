# 适配与验证契约

## 从模型定义到框架落点

将官方模型配置/参考实现与固定的 SGLang 或 vLLM checkout 对照。每个差异注明张量或协议契约、当前类/函数、复用依据、需要修改的文件、fallback 和测试。框架内部路径随版本改变，必须查当前源码，不能将历史文件名当作接口保证。

| 能力 | 检查点 | 必需证据 |
| --- | --- | --- |
| config/registry | architecture/model_type、嵌套配置、默认值、remote-code、模型变体 | 实际注册与配置解析 |
| checkpoint | 参数名称、合并投影、expert 映射、共享权重、TP 切分/PP 层过滤 | 加载覆盖、shape/dtype、参考张量比较 |
| tokenizer/processor | 固定 revision、chat template、特殊 token、图像预处理、停止条件 | 确定输入的 token/processor 输出及协议测试 |
| attention | RoPE、MLA/SWA/线性/混合结构、mask、prefill/decode、长短序列 | eager 参考与候选数值比较 |
| KV/其他状态 | dtype/stride/ownership、prefix reuse、eviction、session release、graph padding、speculative rollback | 状态生命周期与边界测试 |
| quantization | checkpoint 元数据、scale 布局、后处理、padding、算术公式 | 独立参考计算和加载后输出 |
| parallelism | 任务要求的 TP/PP/DP/EP/CP、空闲 rank、collective 对称性、PD 角色 | 每个声明拓扑、跨 rank 逻辑状态对应 |
| serving | chat/reasoning/tools/structured/streaming/stop/错误输入 | 需求内协议面与流分片测试 |

不需要的能力写明不适用原因；不能将必需能力标为不适用。模块保留基础测试槽位，不适用功能也应通过验证不适用条件和 fail-fast/fallback 行为的测试，而不是跳过必需测试。

## 迁移 kernel 与接入

先复用匹配实现。缺口移交算子模块时给出语义、布局、shape/dtype 分布、容差来源、目标 dispatcher、fallback 以及适配 plan/gap ID。检查 Triton、HIP/hipcc 的编译目标、依赖与 stream 语义；CUDA/NVIDIA intrinsic 不可直接当作 HCU 实现。需要专用 kernel 时保留 eager fallback，并覆盖 envelope 外的 shape、dtype、layout 和硬件。

证明模型确实调用候选：导入/注册成功只是第一层，dispatcher 测试、调用计数或 trace 必须显示目标路径。权重或量化格式改变时同时重验 loader 和 kernel；stream/graph/缓存路径改变时重验并发与生命周期。不得把未触发的 fast path 的端到端结果当作该 kernel 验证。

## 验证与交付

按源码/加载 → 协议 → 状态 → 拓扑 → 质量与性能 → 发布顺序收敛。优先覆盖共享状态风险对，例如 graph × cache、speculative × recurrent state、TP × quantization、PD × prefix reuse；无需生成所有功能的笛卡尔积。

参考输出来自固定的可信实现或适配前可用路径。给出 tolerance basis，比较确定样本、logits/数值或任务质量；推理训练 loss 不能替代输出正确性。模块的样本比较并不覆盖完整精度集，交付范围必须注明。性能采用新基线及关闭 profiler 的重复测量，不能拿仿真预测作实测。

维护依赖顺序：基础接口 → config/loader/eager → 状态/并行 → 协议 → 平台 kernel → 联合验收。保存修复、候选和回退记录。报告列明支持的模型 revision、精度、硬件、拓扑、协议、测试命令、证据和未覆盖项。公开发布需单独授权并检查私有路径/数据；当前模块不会自动创建 PR 或发布资料。
