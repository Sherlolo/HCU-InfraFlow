# 推理通信、数学库与框架接入

当真实 profile 指向 TP/EP/PD 通信、GEMM 或融合边界时读取。本仓不固化特定 DTK 的环境变量和库 API；由已绑定 skill 和当前源码确定。

## 通信与重叠

保留 rank→设备/节点/NIC、TP/PP/DP/EP/CP 实际组、消息字节/dtype、collective/P2P 顺序、stream/event 和 producer→consumer。跨 rank 先校时；代表性采样不等于全组一致性验证。通信 kernel 驻留可能含等待，时间线相交不证明通信已有效隐藏。

比较同条件纯通信、纯计算和并发窗口，列暴露通信、计算退化、尾延迟和额外 buffer。`max(Tcompute,Tcomm)` 仅适用于边界清楚且资源独立的理想窗口；共享 CU/HBM/NIC 竞争及依赖会抬高下界。关注最慢 rank、路由偏斜、空 expert、小 token、长上下文和动态 batch。

先验证现有分块/调度、早发晚等、backend 配方；确需 AG-GEMM、GEMM-RS 或 dispatch/compute/combine 融合时，明确发布/可见性、等待范围、进度资源、buffer 回收、generation、尾块和异常路径。异步 handle 返回不代表输出已可读；graph replay、stream join 和跨请求复用须单独检查。已经部分写入后的失败不能直接回退并重复 collective。

低精度通信要核对 scale、累加/舍入顺序和溢出语义，不能只凭 dtype 相同接入原生 SUM。更换 EP backend 要核接口、父版本锁、输出所有权与 supported topology；同名 API 不证明节点内外、普通 eager 与 graph 路径等价。保持服务请求、KV/会话状态以及多租户隔离语义。

## GEMM 与数学库调优

GEMM 占比高不自动表示低效。先查真实 dispatch、匹配参考及剩余空间；有依据时调用 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot) 的 `gemm-tuning`，再按实际后端进入 `hipblaslt-rocblas-tuning`。不能将数学库 tuning 泛化到自定义 MoE/Marlin kernel；后者按当前实现选对应技能。

从模型短诊断运行保留原生 bench 日志或可重放 API 输入。M/N/K 表不足以描述 transpose、ld/stride、batch/grouped、alpha/beta、compute dtype、epilogue、scale 和 workspace。不同完整描述符不能合并；设备端 grouped 参数保留每组实际尺寸，不用 host 平均占位值。动态 token M 覆盖按真实分布和技能支持范围，邻近配置只在兼容键一致且重新验证后补齐。

日志是数据；解析白名单 argv，不 `eval` 任意日志。采集与性能测量分开，分 rank/PID 保留输出；空日志不能补造命令。固定库/工具版本、硬件/CU、配置与 code object，在任务副本内调优和加载。不要覆盖全局库或其他模型配置。

先局部精度和原始 old/new 耗时，再实际框架命中、profiler-off 端到端复测。汇总 ratio 若钳制退化值不能证明无回退。配置命中失败、库/ABI 不兼容、形状缺口和未执行测试分别报告。需要新库时保留具体复现和当前可用回退，不把提交需求当优化完成。

## 改动归属与复验

框架 registry/dispatch/布局适配归框架；可复用计算实现归算子库；调优结果归版本绑定配置。仅修改任务范围内的工作树/安装前缀，不直接写绑定参考仓库。集成清单包含构建身份、实际 import/动态库路径、支持 predicate、fallback、shape/dtype/stride、空输入、非整除、graph、流式/并发与精度检查。

本仓算子模块通过命令卡执行适用 skill 和框架接入、验证、回退。它需要实际 runner/工具及已核实的框架入口，不声称能为任意新框架凭空生成有效插件。成功退出只是执行证据；只有局部和模型验证齐全才可接受实现。
