# 模型适配模块

本模块将新模型支持契约、算子缺口移交、实际执行与候选验收接在现有部署阶段中。适用 active `adapt`、`full`、`optimize` 任务；优化任务基线失败时先适配，随后重新建立基线。技能入口为 `hcu-infer-model-adapt`。

## 固定来源与计划

`model-adapt-plan TASK REQUEST` 调用 `model_adaptation.plan`。输入示例见 `examples/modules/adaptation-plan.json`。`release_lock` 的十个值全部为当前 Store artifact ID：模型元数据、config、weights 清单、tokenizer/processor 清单、engine 源码快照、dependencies 锁、image digest 清单、driver inventory、quantization 描述和 workload。大权重可保留逐文件 hash 清单，不要求把权重本体复制进 Store。清单应记录不可变 commit/digest 与实际字节；程序验证 artifact 存在，Agent 仍须审查其内容，不能将含浮动 tag 的文本描述为冻结来源。

`gaps` 必须覆盖 config/checkpoint/tokenizer/attention/kv-cache/quantization/parallelism/serving，每项有唯一 `id`、`status`（supported/missing/not-applicable）、`required`、`target`、`contract`、`fallback` 与 `kind`（framework/kernel）。缺失 kernel 使用 `operator_backend=triton|hip`，返回 `operator_handoffs`；交给算子计划的 `adaptation_plan` 和 `gap_id`，无需伪造尚不存在的服务 profile。

`required_features` 冻结服务能力，`risk_pairs` 增加具有共享状态风险的组合测试。可选 `failure` 引用失败基线或加载日志。plan 只记录范围，返回 `execution_started=false`；后续调用必须使用同一 context epoch 的最新 plan。重复生成相同计划不改变内容身份；更改范围后旧计划不能继续验收。

## 实施与执行

Agent 依据固定源码在任务工作区实施适配与框架注册，缺失 kernel 由算子模块实施并接入。先保留源文件 snapshot，再调用：

```bash
hcu-infra-agent --workspace /path/to/private-store model-adapt-run TASK /path/to/run.json
```

run JSON 字段为 `plan`、`candidate_snapshot`、`tests`（计划 required_tests 中的名称数组）、`operation`（唯一 ID）、`card`（既有命令卡对象）、`lease`（有效租约对象）。一个测试命令可覆盖多个名称，但每个名称都需要单独断言记录。示例见 `examples/modules/adaptation-run.json`。实际测试程序和启动命令按当前模型/框架生成；模块不内置任意新模型的实现，不把生成计划当作代码完成。

执行使用现有 command-run 的权限、资源租约、预算、context epoch、远程未知结果和幂等保护。绑定在执行前持久化；同一 operation 不得换候选或测试集重用。`status=complete` 仅表示命令返回零，仍必须提供断言、输出比较和原始日志。

## 验收与回到基线

`model-adapt-check TASK REQUEST` 的字段：

| 字段 | 内容 |
| --- | --- |
| plan / candidate_snapshot | 当前计划和实际测试源码 artifact ID |
| test_results | 测试结果 artifact ID 列表，基础 load/checkpoint/tokenizer/attention/kv-cache/quantization/topology/protocol/dispatch/fallback 以及计划的 feature/risk 测试 |
| quality_inputs | 与 `quality-check` 相同的 contract/baseline/candidate 对象 artifact ID |
| gap_resolutions | 必需 missing gap 的 ID → 解决证据 artifact ID |

每个 test result 包含 `name`、`context`、`candidate_snapshot`、`operation`、`status`、正整数 `executed`、`candidate_path_exercised=true`、非空 `evidence` artifact 列表，且该列表包含对应 operation 的全部 evidence（stdout/stderr/命令计划）；失败/缺项字段遵循现有质量契约。operation 必须属于本任务，通过 model-adapt-run 绑定本候选和测试，且实际完成。程序校验持久执行记录和原始日志，断言的语义仍须由测试作者与独立 reviewer 核对。

quality contract 的 identities 对应 release_lock：`model=weights`，其余 `tokenizer/quantization/workload/driver` 同名对应。参考和候选需相同固定输入身份，候选 snapshot 必须一致，required_features 必须覆盖整个计划。参考可来自已核对的官方实现，不能通过复制候选输出制造参考。

每个 gap resolution 包含 `gap_id`、`context`、`candidate_snapshot`、`status=pass`、正整数 `executed`、`candidate_path_exercised=true` 和非空原始 `evidence`；保留修复 diff、分发路径和对应模型断言。缺失 kernel 还必须提供 `operator_integration` artifact ID，并放入 evidence；模块核对同一 plan/gap/candidate 的成功集成及持久化 apply/verify 执行记录，不能仅凭源码或自报 pass 闭合。未解决必需 gap、失败命令、跳过测试、质量回退均返回 fail，并替换上一份 adaptation 报告，避免沿用旧 pass。显式 synthetic、hardware_executed=false 或仿真预测的输出不能作为适配质量证据。

通过返回 `ready_for_baseline=true`、`accepted_by_flow=false`。调用方应重新测量关闭 profiler 的基线；只有随后的质量/性能检查及独立 flow review 才能接受完整优化。此报告不认证真实 HCU、全部模型精度、性能或发布状态。

## 来源与边界

流程借鉴新模型 Day-0 的 release lock、架构差异图、分层验证和依赖 DAG；推理验证独立于训练 loss/backward/optimizer。算子参考来自 [hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)，来源仓库只读并固定版本，部署时无需任何作者机器的兄弟目录。真实模型、容器和工具路径由任务绑定提供。CPU 协议测试覆盖计划、执行和证据门槛，不等价于模型适配实测。
