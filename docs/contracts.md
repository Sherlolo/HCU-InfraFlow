# 任务和证据契约

先阅读 `examples/task.json`、`examples/flow.json`；CLI 所有输入是 JSON，输出 JSON，拒绝错误返回非零。

```bash
hcu-infra-agent --workspace /task/store init
hcu-infra-agent --workspace /task/store task-create examples/task.json
hcu-infra-agent --workspace /task/store flow-start inference-demo examples/flow.json
hcu-infra-agent --workspace /task/store flow-next inference-demo
```

`flow-next` 可返回 work、repair、review、advance、coordinate、reconcile 或 human，Agent 依返回动作执行。
候选包含 author/context/goal/snapshot/summary/reports/target/evidence；优化候选另需 experiment 和
`profile_evidence: {artifact, observation, hypothesis, target}`。artifact 指向保留的当前 context 分析 JSON，内有原始 evidence。
报告引用必须等于 Store 当前对应报告，candidate_snapshot 必须匹配候选 snapshot。源码 snapshot_id 与报告使用的 artifact ID 不同；
用 artifact-add 保留完整源码快照清单，候选引用其 artifact，清单内再定位 snapshot_id。参见 `demo.py` 的实际调用。

review 契约见 `flow._review()`：round/candidate/goal/context/reviewer/verdict/summary/findings/acceptance/progress/full_alignment/evidence。
verdict 为 accept/revise/blocked；reviewer 必须区别于 author，所有命名验收条件都要评估。程序检查身份字段，不能认证真人/独立会话真实性。

## 质量与性能

`quality-check FILE` 输入 `{contract, baseline, candidate}`，冻结 model/tokenizer/quantization/workload/driver。
样本必须使用相同唯一 id 和顺序，文本精确匹配，数值向量按有依据 atol/rtol 对比；required_features 全部通过，baseline 已通过特性不能回退。
这里只实现固定样本和特性结果的验收。Agent/实际评测工具产生原件，脚本不据此宣称完整准确率。

优化模块额外要求 contract.coverage 及对应请求元数据，覆盖短输入、长输入的单请求与并发四格。样本必须保留输入SHA、token数、run_id、请求并发数和起止时间；请求级并发由区间重叠检查，不能只填标签。参考与候选的请求身份必须一致。缺覆盖或输出不匹配均不能以性能收益抵消，详见[模型优化闭环](model-optimization-loop.md)。通用 quality-check 仍可用于其他明确声明范围的质量任务。

`performance-check FILE` 对相同场景集的吞吐、TTFT、TPOT、p95 延迟重复数组比较；至少三个相等次数的无 profiler 重复，
contract 明确主 metric、min_gain、max_regression、sla。须保持缓存策略、请求和测量条件；统计输出不等于显著性证明。
`report-add` 写 inference-quality/performance 的 pass 时，必须提供 quality_inputs/performance_inputs，保留原比较输入，程序重算，并校验候选身份。

## 命令与观测

命令卡字段参见 `examples/command-local.json` 和 `command-ssh-docker.json`。command-plan 只渲染；
command-run 需要 TaskSpec execute 权限、有效资源租约及相符 assignment 身份，意图持久化后执行。

`observe TASK SAMPLE POLICY` 要求当前 context、attempt_id、timestamp、healthy；policy 可声明 freshness、TTFT/TPOT/延迟/error_rate/queue 阈值。
事件通过 inbox 消费，不会自动重启模型服务。重复相同 observation 不重复创建告警。
