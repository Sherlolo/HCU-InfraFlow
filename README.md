# HCU Infra Agent

面向 HCU 大模型推理的 Agent 工作流：环境验收与部署 → profile 驱动分析优化 → 扩容与服务守护。
基于 HCU-TrainFlow 的持久任务、独立复核、快照、租约、命令卡与协作协议开发，推理契约重新实现。
参考 infra-agent-v2 的实测驱动方向选择与固定 workload 比较，绑定 DCU-Infer-Pilot Skills 和 HCU-Knowledge。
来源、固定修订及派生模块见 [provenance.json](provenance.json)；保留上游 MIT 许可。

## 快速开始

Python **3.10+**。无 GPU 的协议演示不安装模型或启动推理服务：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/hcu-infra-agent --help
.venv/bin/hcu-infra-agent demo /absolute/path/to/new-demo
.venv/bin/python -m pytest -q
```

`demo` 运行真实 CPU 子进程和合成质量/性能数据，完成全流程状态与结构化 review，生成 `result.json`、`report.html` 和 Store。
演示中的 reviewer 是测试身份，不是实际独立 Agent。它不证明 HCU 推理精度、性能、真实多 Agent 或生产恢复已通过。

将六个工作流 Skill 安装到明确选定的目录（不会修改参考仓或隐式覆盖现有 Skill）：

```bash
.venv/bin/python scripts/install_skills.py --target /absolute/path/to/task-skills
```

在宿主 Agent 中使用：

> `$hcu-infra-agent` 在指定 HCU 环境部署并优化某模型的推理服务，模型、容器和资源范围在任务资料中；目标 workload 与 SLA 如下……

宿主负责推理、派发专家和独立复核；CLI 返回下一步动作，不会自行调用模型 API。完整与独立 environment/adapt/analyze/optimize/diagnose/operate 模式均支持。

## 功能

- 发现 HCU 环境、加载库、设备占用与通信条件；保持健康证据和性能预期可比。
- 固定源码字节快照与传输校验；local、SSH、SSH+Docker、已有 Slurm allocation 和 K8s Pod 命令卡。
- 实施/独立复核/修正循环、预算与停滞限制、BOARD/GUIDANCE/QUESTIONS 文件指导。
- 团队依赖、原子领取、会话 token、修改范围与资源预约、消息回执、报告验收。
- 对显式指定的 OpenAI-compatible `/v1/completions` 服务进行有界 streaming benchmark；记录固定请求、重复样本、吞吐、TTFT、TPOT 和 p95 延迟。
- 推理输出（文本或数值）、必需服务特性与 baseline 已通过特性的回归检查。
- 对冻结 workload、模型/tokenizer/量化/驱动身份的重复性能数据重算验收，检查所有场景回退与 SLA。
- profile 采样计划与时间线分析；优化提交必须携带当前 context 的 profile 原件引用、观测、假设及目标。原生 TraceLens 与现场采集按绑定 Skill 驱动，通过命令卡记录，而非冒充内置分析已运行。
- 持久服务观测、阈值事件、outbox 与显式消费者回执；未知执行先 reconcile，恢复仍由 recovery_owner 负责。
- 本地绑定并校验 DCU-Infer-Pilot Skill 与 HCU-Knowledge 入口哈希，原生知识查询，明确报告知识索引/权限失败。
- 当前证据 HTML 报告和私有经验归档；不复制训练 Wiki、训练 loss/反向/优化器验收代码及大型原始材料。

## 工作流

```text
prepared → environment_checked → baseline_validated → profiling
         → optimizing → serving_ready → serving → completed
```

见 [架构](docs/architecture.md)、[契约与调用示例](docs/contracts.md)、[部署验收](docs/deployment.md)、
[优化方法](docs/optimization.md)、[运维](docs/operations.md)、[知识接入](docs/knowledge.md)、[验证范围](docs/acceptance.md)。

## 在指定远端环境使用

站点绑定样例见 `examples/site-nmz26.json`；路径是用户指定的参考根，先 `bind` 校验，不自动更新这些来源。
NMZ_zz_26 主机 Python 3.6.8 不满足项目条件；已检查用户容器 `yangyn_sglang_plugin_1022` 有 Python 3.10.12，
且 `/public/home/yangyn1` 为可写映射。使用项目独立 venv，不改服务环境：

```bash
docker exec yangyn_sglang_plugin_1022 bash -lc '
  cd /public/home/yangyn1/work_space/2026/agent/hcu-infra-agent
  python3 scripts/bootstrap.py --test
  .venv/bin/hcu-infra-agent bind examples/site-nmz26.json .work/bindings.json
'
```

本仓开发和 CPU 验证不会占用 GPU、重启已有服务或变更参考仓。新站点、真实模型、采集和恢复均须按任务范围执行验收；没有在本仓进行过的实测不继承为新仓性能结论。

容器缺少 ensurepip 时，`scripts/bootstrap.py` 用已有 pip 的 `--python` 功能引导项目内 venv；可加 `--wheelhouse /path/to/wheels` 离线安装。不会安装系统 apt 包。

**站点存储选择：** 指定共享盘为 NFS；并发控制 Store 需放节点/容器本地文件系统，显式使用 `--workspace` 或 `HCU_INFRA_WORKSPACE`。
源码和导出报告可留共享盘。站点并发与持久性边界见 [架构说明](docs/architecture.md#实际站点文件系统限制)。
