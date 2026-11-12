# Torch 推理执行、编译与 Graph

仅当实际服务路径使用 Torch compile/Inductor、eager 或图执行时读取；依据 TrainFlow torch-native-training 中通用编译与内存方法改写，DDP/FSDP、梯度累积和训练 loss 不迁入。

固定 Torch/HIP/编译器/插件和生成制品身份，追真实调用者；服务代码可能通过自定义算子或独立 graph runner 执行，不能从开关推断模型被 compile。检查 graph breaks、recompile、shape guard、动态 batch/上下文、padding、捕获 bucket、warmup 和 fallback。

区分编译耗时、首次运行、稳态与冷启动目标。诊断日志和同步开关只在隔离诊断运行启用；正式测量恢复实际 serving 配置。保存生成代码、有效配置、cache key 和实际加载路径；切换编译器或全局选项影响其他算子时必须回归共同快照，不仅测试一个融合。

Graph 侧检查静态地址、输入更新、stream/event join、KV 页表与写回、workspace 的跨请求复用。共享 MoE buffer 的形状/stride 改变可能影响 graph 缓存和视图；producer event 要在消费者读取前生效。eager 正确不证明 replay 正确，至少覆盖重复 replay、动态/尾 batch、长短请求交错、fallback 和 cache 失效。

推理执行模式与 eval 状态按实际模型要求固定；改变 inference_mode、autocast 或 dtype 不能静默改变质量合同。没有可靠 oracle 时先补参考，不以“没有报错”作为数值验收。

用 Prof Skill 分辨提交成本与设备成本，再决定编译边界/融合候选。局部编译命中后仍由模型优化 Skill 完成质量、profiler-off 性能与候选 Prof。知识入口可检索 pytorch-compile-aoti-debug-contract、pytorch-memory-stream-graph-lifecycle；查到资料仍需匹配当前部署版本。
