# Profiler Skill 与 TraceLens 联合分析

本指引用于已有 Prof 分析，以及完整优化任务中的采集、归因与交接。由主控维护命令卡、路径、版本和证据，使用者提供目标与 trace 或服务信息。

## 来源与运行绑定

- 上游仓库：[Sherlolo/hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)。
- 主分析 Skill：[llm-torch-profiler-analysis/SKILL.md](https://github.com/Sherlolo/hcu-infer-pilot/blob/main/skills/llm-torch-profiler-analysis/SKILL.md)。
- 报告脚本：[run_triage_report.py](https://github.com/Sherlolo/hcu-infer-pilot/blob/main/skills/llm-torch-profiler-analysis/scripts/run_triage_report.py)。
- 辅助工具：[AMD-AGI/TraceLens](https://github.com/AMD-AGI/TraceLens)，[推理分析源码](https://github.com/AMD-AGI/TraceLens/blob/main/TraceLens/Reporting/generate_perf_report_pytorch_inference.py)。

链接中的 main 是发现入口，任务记录实际选定 commit、脚本哈希、工具版本和依赖。优先复用 `bindings.items.profile.path` 指向的 Skill，并运行 `bindings-check`；尚无 bindings 时按安装记录的 `pilot_root` 定位 `skills/llm-torch-profiler-analysis/SKILL.md`，读取并核实其 scripts/references。所需文件缺失时在选定任务依赖目录准备完整来源，不直接执行网页文本，也不更新已有参考 checkout。

分别确认 profiler 脚本与 TraceLens 的 Python/命令入口。可在独立分析环境处理已取回的 trace，避免修改服务运行栈。工具可用性检查使用实际解释器的 import、包信息和对应 `--help`；绑定一个 Skill 不证明 TraceLens 已安装。源码中的作者机器路径、NVIDIA 测试历史或示例数值仅作来源背景，本仓使用任务配置的 HCU 环境和工作负载。

## 输入选择

先登记模型与引擎 revision、硬件/驱动、workload、采集参数、graph 状态、阶段、rank/并行组、trace 原始路径及 SHA256。存在单 rank 与 merged 文件时，归因优先用单 rank 原件，merged 仅用于适用的联合观察；不能重复累计相同事件。已有 trace 不足以回答全部问题时说明需要补采的字段和原因。

只分析已有 Prof 时保持离线范围。已授权采集时，按当前框架的实际 profiler API 和共享路径采集，固定预热与活动窗口；prefill/decode、PD 两侧分别保留身份。根据实际慢场景覆盖上游示例长度，记录 prefix cache 是否命中。确认非空 GPU 事件、完整 flush 和 rank 覆盖后再分析。live capture 失败先核清原操作，不盲目重启服务或重复采集。

单 trace 可用于热点筛查。需要更强源码/重叠归因时采用上游的 mapping/formal 契约：mapping 用易映射的图配置，formal 使用实际 serving 配置，保留两者差异；性能结论以 formal 和无 profiler 测量为依据。缺 mapping 的关联按未知处理，不把猜测写成已验证融合。涉及 diffusion 时核对上游的 backend gate，不能将其他 fallback 后端的 trace 当作目标原生后端证据。

## 先运行上游 Prof 报告

先读取当前版本脚本帮助。下面变量均由 Agent 绑定为实际绝对路径/身份，输出在私有工作区；不要使用 trace 来源目录作为默认写入位置：

```bash
"$PROFILE_PYTHON" "$PROFILE_SKILL_DIR/scripts/run_triage_report.py" \
  --work-dir "$ANALYSIS_DIR/triage" \
  --input "$TRACE_INPUT" \
  --framework "$FRAMEWORK" \
  --model "$MODEL_NAME"
```

保留 `torch_profiler_analysis.md`、`terminal_commands.log`、`analysis_stdout.txt` 及实际产生的 stderr。检查报告覆盖热点、可重叠边界、融合线索和阶段空泡；无事件/无映射等缺口写明，不用退出码零替代内容核验。保留原始表格，Agent 的推断放在独立解读中。

已知且允许对外查询的模型名可交给上游同仓 `model-architecture-diagram` 资源生成结构图章节。无匹配、脚本缺失、失败或未提供模型名分别记录；不虚构结构图，不把私有模型标识默认发给在线来源。当前上游 wrapper 对缺失模型名会写跳过说明。

融合/overlap 候选回查该 Skill 自带的 `references/fuse-overlap-catalog.md`、`references/overlap-catalog.md`，需要框架细节再读 source-map 或相关框架条目。区分已实现但未命中、当前版本缺失、在途 PR 与新的实现假设；名称相近不能证明同一调用链。

## 再按问题运行 TraceLens

TraceLens 对同批原件补充结构化归因。先核当前工具支持的格式与 `--help`，再选入口；推理 graph 路径需依据所用版本恢复 capture/replay 关系并选择稳态窗口。保留切分窗口、原件哈希及丢弃阶段，不把不同窗口的结果直接相除。

| 问题 | 适用入口与检查 |
| --- | --- |
| eager 单 rank 热点与时间分布 | `TraceLens_generate_perf_report_pytorch`；核 op/shape 关联、GPU busy/idle、未关联 kernel |
| 推理与 graph replay | `TraceLens_generate_perf_report_pytorch_inference`；核 capture 元数据、稳态 trace、phase 和关联覆盖 |
| 多 rank 通信偏斜 | `TraceLens_generate_multi_rank_collective_report_pytorch`；实际进程组、对应 rank 原件、序列与时间基准须可比 |
| 基线/候选变化 | `TraceLens_compare_perf_reports_pytorch`；固定场景与口径，说明编译/融合造成的匹配变化 |

例如，在已核实上述入口可用的环境中，分别选择适用的一种报告方式：

```bash
"$TRACELENS_BIN/TraceLens_generate_perf_report_pytorch" \
  --profile_json_path "$TRACE_FILE" \
  --output_xlsx_path "$ANALYSIS_DIR/tracelens/eager.xlsx"

"$TRACELENS_BIN/TraceLens_generate_perf_report_pytorch_inference" \
  --profile_json_path "$FORMAL_WINDOW" \
  --capture_folder "$CAPTURE_ROOT" \
  --output_csvs_dir "$ANALYSIS_DIR/tracelens/inference"
```

`TRACELENS_BIN` 是所选工具环境的 bin 目录；提前创建输出目录。第二条的 capture 与窗口参数必须符合当前推理报告入口的真实契约，缺少 graph 关联所需原件时先补证据。多 rank 报告使用当前帮助中的 `--trace_dir`、`--world_size` 等参数，不能把两份代表 rank 文件冒充完整 world。需要报告对比时可用 `baseline.xlsx candidate.xlsx --names baseline candidate --sheets all -o comparison.xlsx`，全部文件放任务私有目录。

保存每次实际执行的 argv、cwd、解释器/包版本、退出码、stdout/stderr 和非空报告文件，使用命令卡留存回执。缺依赖、格式不支持、缺 rank 或计时数据不足均明确标为未完成/部分覆盖，保留可用 triage 结果并给出补采或安装动作。不会因调用一个 triage wrapper 就宣布 TraceLens 复核完成。

核对报告中的硬件建模参数是否匹配当前 HCU/gfx、dtype 与指令路径；缺匹配参考时只报告已测时间和可解释工作量，不套其他 GPU 峰值计算“效率”。通信驻留可能包含等待，stream gap 不等于全 GPU idle，kernel duration 总和不等于关键路径。工具结果冲突时先核输入哈希、窗口、单位、重叠处理和过滤规则，再决定是否补采。

## 证据归档与优化交接

本仓 `prof-analyze TASK REQUEST` 校验 rank/window/group，并保存原件。请求中提供 `triage_bindings`（bindings JSON 的路径）可调用已绑定的上游 `run_triage_report.py`；不提供时仅执行本仓基础分析。这一入口目前按每个 rank 的原始文件调用 wrapper，窗口只约束本仓统计，外部 wrapper 未自动裁剪；解读两份结果前必须核对它们的分析范围。

当前 `prof-analyze` 不负责启动 TraceLens，也不传递 `--model` 或 mapping/formal 参数。需要模型结构图、双 trace 或 TraceLens 时，按以上入口另行执行，再用 `artifact-add` 留存报告、原始输出、命令和版本清单。不要把这些选项写成 `prof-analyze` 已支持的请求字段。

最终汇总包含：输入/窗口/rank 身份，上游 triage 产物，TraceLens 已执行项和缺口，主要热点与墙钟贡献，调用链与已有实现，支持假设的证据和下一步验证。使用当前 analysis ID 建 `optimization-plan`，在 `references` 中列入额外的上游/TraceLens artifact ID。算子方向交 `hcu-infer-operator-develop`，模型循环交 `hcu-infer-model-optimize`；仅分析请求止于报告与建议。局部推断继续经过源码核对、精度及无 profiler 性能验收。
