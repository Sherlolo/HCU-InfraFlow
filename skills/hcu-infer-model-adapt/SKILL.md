---
name: hcu-infer-model-adapt
description: 在 HCU 上为 SGLang 或 vLLM 适配新模型，处理无法加载、缺失算子及输出或状态不兼容，并验证模型支持范围；性能优化另交优化闭环。
---

# HCU 新模型适配

模型首次接入、基线无法运行，或已有支持因新权重/配置失效时使用。复用当前部署阶段和主控，不建立第二个协调器。先读取 [适配与验证契约](references/adaptation-contract.md)。

通过同目录 `workspace.json.project_root` 定位已安装工程；源码使用仓库根。读取工程 `docs/model-adaptation.md` 获取可执行请求格式。工具、模型、容器和框架位置来自当前任务或安装绑定，不假定其他仓库的本机目录。

1. 冻结模型配置、权重清单、tokenizer/processor、量化、工作负载、引擎源码、依赖、镜像和驱动的实际身份。保留文件内容或带不可变 revision/digest 的清单到任务 Store；仅保存 `main`、可变镜像 tag 或一个目录名不构成冻结。
2. 检查指定版本已有模型/加载器/attention/缓存/并行实现，建立架构差异图及必需服务能力。区分必须跑通的支持、发布后修复、可选提速和实验。性能仿真只供容量判断。
3. 运行 `model-adapt-plan`。先补齐 config/registry/权重映射和 eager 正确性，再接入状态缓存、并行角色与服务协议。代码在任务隔离 checkout 中开发，保存候选 snapshot。对绑定参考仓库只读。
4. 缺失算子先查 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot) 中适用 kernel，核实来源 revision、许可证、HCU 架构、dtype、shape 和实际 dispatcher。把 plan artifact 与 gap ID 交给 `hcu-infer-operator-develop`，按需求迁移 Triton 或 HIP/hipcc 实现；没有可用技能时记录组件缺口，不能假称已调用。不能跑模型时使用适配缺口作为正确性开发依据，不伪造 profile 或推断提速。
5. 使用 `model-adapt-run` 的命令卡和资源租约运行候选测试，保留断言结果与日志。仅零退出、成功启动或正常输出一个 token 均不足以验收。用 `model-adapt-check` 检查固定参考输出、计划内所有测试和必需缺口的闭合证据。
6. 检查通过后返回部署/优化主控，重新建立关闭 profiler 的完整基线，再进入 profiling 与优化。完成支持仍需独立 flow 复核；不把适配检查当成性能、发布或全部模型精度证明。

测试失败按最早失败层定位：加载、协议、状态、拓扑、质量。远程命令结果未知时先核对原进程，不重新发起相同实验；恢复操作遵守任务的 recovery owner。更换权重、源码或测试范围后重新冻结/规划，不能沿用旧候选的 pass。
