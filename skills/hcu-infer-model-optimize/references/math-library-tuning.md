# 推理数学库调优


GEMM 占比高不自动表示低效。先查真实 dispatch、匹配参考及剩余空间；有依据时调用 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot) 的 `gemm-tuning`，再按实际后端进入 `hipblaslt-rocblas-tuning`。不能将数学库 tuning 泛化到自定义 MoE/Marlin kernel；后者按当前实现选对应技能。

从模型短诊断运行保留原生 bench 日志或可重放 API 输入。M/N/K 表不足以描述 transpose、ld/stride、batch/grouped、alpha/beta、compute dtype、epilogue、scale 和 workspace。不同完整描述符不能合并；设备端 grouped 参数保留每组实际尺寸，不用 host 平均占位值。动态 token M 覆盖按真实分布和技能支持范围，邻近配置只在兼容键一致且重新验证后补齐。

日志是数据；解析白名单 argv，不 `eval` 任意日志。采集与性能测量分开，分 rank/PID 保留输出；空日志不能补造命令。固定库/工具版本、硬件/CU、配置与 code object，在任务副本内调优和加载。不要覆盖全局库或其他模型配置。

先局部精度和原始 old/new 耗时，再实际框架命中、profiler-off 端到端复测。汇总 ratio 若钳制退化值不能证明无回退。配置命中失败、库/ABI 不兼容、形状缺口和未执行测试分别报告。需要新库时保留具体复现和当前可用回退，不把提交需求当优化完成。


## 诊断采集与其他数学库

BLAS 日志开关和 bench 参数从当前 DTK/已加载库的帮助及已绑定 tuning Skill 取得，分 rank/PID 保留非空原件；不要为取得日志暗中更换后端。仅 shape 归因表不能伪装原生 bench 输入，动态 M 和设备侧 grouped 描述符要核真实分布。

多模态模型确有 MIOpen 卷积热点时，保存完整 tensor/layout/groups/pad/stride/dilation、算法/workspace、Find/cache 身份及原生 Driver 或最小 API 复现。先确认选优结果实际命中，搜索预热与正式计时分开；没有对应专项 runner 时交付可重放缺口，不套用 BLAS 命令。来源为 TrainFlow math-library-tuning 的通用方法；调优执行沿本仓算子模块和已绑定工具，不沿用训练目录或发布动作。
