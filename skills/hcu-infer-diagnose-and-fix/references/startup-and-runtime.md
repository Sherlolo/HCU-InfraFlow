# 启动、加载和运行失败

先定位第一个失败阶段：解释器/import → 扩展加载 → 模型/权重 → 通信组 → 图捕获/预热 → 请求。收集真实 exit/signal、最早 traceback、各 rank 日志及宿主/容器路径映射，末端 timeout 往往只是其他 rank 首错的结果。

| 证据 | 排查与解决方向 |
| --- | --- |
| import、undefined symbol、invalid device function | 查实际 Python/.so/code object、DTK/Torch/gfx、依赖锁与 ABI；在任务前缀重建匹配制品，不全局覆盖库 |
| 配置、registry、权重 shape/缺 key | 核模型架构/revision、tokenizer、量化元数据、shard 完整性和消费者；确为支持缺口交模型适配 |
| OOM/显存增长 | 分加载、预热/graph、prefill、decode、并发与长时间窗口；列权重、KV、图池、通信 workspace、allocated/reserved 与其他进程 |
| 多 rank 初始化失败 | 查设备与 rank 绑定、world/group、端口、共享内存、NIC/拓扑和全组首错；按 hang 模块补证 |
| 请求校验/长度/多模态输入失败 | 保留原 payload，核服务公开契约与 processor，区分合法输入回归和应拒绝的输入 |

OOM 先按真实资源与峰值调整有依据的容量/调度配置，核受影响 SLA；缓存 reserved 不等于泄漏，重复同场景观察申请/释放与请求状态。缩短上下文、降低并发或精度属于缓解或新比较条件，不冒充原负载修复。

修复后验证首次加载、预热、原失败请求及触发边界；记录原环境与候选差异、实际路径命中和回退。设备/驱动不健康时交现场负责人，普通模型任务不默认重置 GPU/驱动或终止其他作业。
