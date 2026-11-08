# 五模块扩展的使用验证（2026-11-09）

本目录记录 0.2.0 的真实离线使用；`validation/` 根目录的原件属于 2026-11-07 / 0.1.0 历史，不追认为当前代码验证。

| 模块 | 实际调用与证据 | 结论边界 |
| --- | --- | --- |
| Prof | `prof-real.json`、`prof-cli.log`、私有 Store 中固定 trace / 原生 triage Markdown 和 stdout/stderr | 两份既有 TP2 capture，各 15,843 个 GPU kernel；分析、空泡和重叠口径保留，缺 shape/dtype/phase 的上限归属仍未完成 |
| 性能优化 | `optimization-plan.json`、`optimization-plan-command.json` | 基于当前分析生成真实待验证假设，未启动新 GPU 优化实验 |
| 优化验收 | `optimization-check-fixture.json`、`optimization-check-command.json` | CLI 与质量/性能联合门槛用合成 fixture 试跑，accepted_by_flow=false；不是模型 A/B 或提速证据 |
| 仿真 | `simulation.json`、`simulation-cli.log`、安装日志 | 实际 DCUSim 2.0.0，NMZ、工具别名 qwen3_5、TP2、batch4、输入1024/输出128、KV/attention BF16；预测不代表该 INT8 capture 的实测或校准值 |
| Cookbook | `cookbook-search.json`、`cookbook-read.json`、read-command | 查 inference-cookbook 的知识镜像，真实读取命中正文；未宣称最新上游或已采用配方 |
| 知识查询 | `knowledge-query.json`、`knowledge-read.json`、read-command | 默认 curated 范围的只读 tracked 文本检索，明确 partial，不依赖原生索引；读取正文不等于结论已验证 |

实际分析的 rank 0 选定窗口中，一个 INT8 GEMM kernel 占约 22.61%，AITER cross_device_reduce 占约 22.50%；
这是单 rank 窗口等分重叠的归因结果，不是可直接移除的延迟、瓶颈因果或预期提速百分比。
优化计划优先补真实 GEMM shape/dispatch 和跨 rank 依赖，再决定是否调参或改实现。

`pytest.log`：目标容器 Python 3.10.12，215 passed / 2 个 Windows 专属 skip。
新增回归覆盖 rank 冲突/缺失 GPU 证据、过期 analysis、同候选门槛、失败使旧 pass 失效、只读查询范围/逃逸、真实 worker 子进程和超时。
测试临时目录与 Store 位于容器本地 `/tmp/hcu-infra-agent-1109`，源码和导出资料位于用户指定 NFS 仓库。
`skills-install.json` 记录六个自有 Skill 的独立安装；`structure.json` 保存 Skill 和文档静态校验；`wheel-build.log` 记录打包。
`summary.json` 保存最终来源、模块结果、源文件哈希和验证范围。

未在本次运行中启动模型服务、占用 GPU 做新测量或改动外部知识/Skill 源码。实时采集、真实输出精度、候选性能、持续生产恢复需在对应任务中另行执行。

私有 `.work/1109` 保存绑定和请求，Store 由 README 的 --workspace 显式选择。重新运行 prof 会替换当前 analysis，旧计划因此失效，需基于新结果重建计划。
