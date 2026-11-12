# 推理原生引擎调优

用于真实瓶颈已指向调度、attention/KV、MoE、graph 或 host 路径时。能力类别见 [推理机制](inference-mechanisms.md)，不要把类别表变成参数穷举。当前高价值热点有足够证据即可实施。

## 查真实生效链

从启动参数、环境、配置和默认值追到各角色/rank 的有效值，再到 guard、backend dispatcher 和实际加载 kernel/库。参数解析成功不等于命中；记录被覆盖、静默 fallback、依赖缺口、当前不适用与已启用。特别核对环境变量按存在性还是值判断，父工程锁定库的版本和独立库 HEAD 分开。

每项候选记录当前值、候选差异、读者源码、支持的 phase/shape/dtype、依赖/互斥、预期省掉的工作、内存与功能代价及回退。源码与 PR 状态注明已合入/已发布/当前可用/在途，按知识检索结果查固定代码，不因新机制出现就切换执行基点。

## 按卡点实验

- TTFT：分离排队、tokenizer/processor、prefill 计算；chunk 大小与 batch 预算共同影响 decode 尾延迟。固定输入和 cache 冷热，不能靠新增 prefix 命中冒充计算提速。
- TPOT：核 attention/KV 布局、graph 覆盖、动态/尾 batch、host launch、采样；图池与 workspace 的显存成本计入容量。减少提交与减少 GPU 工作分别归因。
- MoE：分清路由/pack、专家计算和跨卡 dispatch/combine；记录每 call token/split、空专家与最慢 rank，不只调平均 shape。
- KV/PD：保留请求身份、KV page 所有权、传输完成、cache 淘汰与会话语义；拓扑或容量改变按新比较条件重新建立基线。

同一假设内有界试参，先验证配置/dispatch 和正确性，再短时筛选。只有可保留候选进入正式质量、profiler-off 场景测量和优化后 Prof；重复次数遵循冻结合同。缺底层能力时交算子开发，接回后重验原选项及受影响的 graph、batch、通信组合。组合整体重测，不能相加各自收益。

依据迁自 TrainFlow 的 native-engine-tuning；训练微批/梯度/优化器语义不适用于本页。
