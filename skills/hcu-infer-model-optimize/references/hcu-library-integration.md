# HCU 库接入与实现归属


框架 registry/dispatch/布局适配归框架；可复用计算实现归算子库；调优结果归版本绑定配置。仅修改任务范围内的工作树/安装前缀，不直接写绑定参考仓库。集成清单包含构建身份、实际 import/动态库路径、支持 predicate、fallback、shape/dtype/stride、空输入、非整除、graph、流式/并发与精度检查。

本仓算子模块通过命令卡执行适用 skill 和框架接入、验证、回退。它需要实际 runner/工具及已核实的框架入口，不声称能为任意新框架凭空生成有效插件。成功退出只是执行证据；只有局部和模型验证齐全才可接受实现。

## 从消费者追依赖

先检索 HCU 知识，再追 SGLang/vLLM/插件的公共入口、父版本锁、条件分派与实际 .so/code object。按热点查 AITER/LightOp/attention、hipBLASLt/rocBLAS，或 RCCL/DeepEP/MORI/rocSHMEM 等实际 backend；名称清单不代表所有环境已支持，也不是全部安装要求。编译期 ABI、DTK/Torch/gfx 和库加载位置共同核对，环境变量不能修复 ABI。

候选在任务前缀构建，保存编译参数、import/动态库路径、哈希与回退制品。先局部正确性及负例，再框架 apply/verify/rollback；更换 EP 后端须核同步/async、Graph、跨机与单/多 in-flight 的各自资格。内核入口存在不证明消费者已接入。

共享 buffer/zero-copy 输出核 producer event、generation 和消费者寿命；视图不能跨 generation 当稳定副本。修改规约协议核 scale、累加和舍入，不因 dtype 同名就换原生 SUM；原地返回 None 既可能已写出也可能拒绝，必须按明确状态判定，避免重复 collective。出现部分写入或 poisoned 状态先故障收敛，不盲目重试。

上述检查点来自知识条目 sglang-deepep-shared-layout-graph-lifecycle、aiter-int8-fp8-collective-contract、moonep-release-contract 的源码审阅。具体支持范围依绑定修订核实；本仓文档不将其升级成 HCU 实测结论。
