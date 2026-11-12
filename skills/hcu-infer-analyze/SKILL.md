---
name: hcu-infer-analyze
description: 分析 HCU 大模型推理 Prof/torch.profiler trace，调用 llm-torch-profiler-analysis 并结合 TraceLens 复核热点、通信、空泡与源码归因，交付证据和建议；仅负责分析，模型优化由 hcu-infer-model-optimize 执行。
---

# HCU 推理 Prof 分析

职责限定为 Prof 采集契约核验、性能归因和分析交付。已有 trace 请求默认离线处理；没有采集授权时不启动服务。优化实验、原生参数调整、代码修改、候选保留与回退统一交 `$hcu-infer-model-optimize`。运行失败、hang、崩溃或精度异常先交 `$hcu-infer-diagnose-and-fix`。

## 输入和工具

通过安装目录 `workspace.json.project_root` 定位工程；源码版使用仓库根。读取工程 `docs/modules.md` 的 Prof 部分及 [Profiler 与 TraceLens 联合分析](references/profiler-and-tracelens.md)。由 `bindings.items.profile.path` 或安装记录 `pilot_root` 定位完整的 `llm-torch-profiler-analysis`，实际读取绑定版本的 SKILL.md、核对 revision、入口哈希及解释器。远程来源链接不替代可执行资源。

固定模型/引擎/设备身份、workload、prefill/decode/PD、rank 和进程组、graph 状态、原件哈希及分析窗口。未知项保留未知，核验非空 GPU 事件、flush、重复/merged 文件与 rank 覆盖；CPU-only trace 不能证明已采到 GPU。补采仅在任务已授权范围内执行，沿当前框架真实接口和容器路径映射；捕获失败先核清原 operation。

## 分析流程

1. 实际运行上游 `run_triage_report.py`，保留命令、stdout/stderr、报告和工具身份；按需要区分 mapping 与 formal trace。用本仓 `prof-analyze` 保存当前 analysis 和原件；基础解析不等于调用过上游工具。
2. 按问题运行 TraceLens 单 rank、推理 graph、多 rank 通信或前后比较，保留独立回执。缺依赖、rank、capture 元数据或 shape 时交付可用分析和覆盖缺口，不宣称复核已完成。
3. 以可解释窗口墙钟为分母，分别列 GPU 服务时间、区间并集、暴露通信、host/调度等待和未归因空白。按逻辑调用链聚合，再按 phase/rank/shape/dtype/实现拆分。父 op、子 kernel、并发 stream/rank 不能重复累加；时间线相交不证明有效 overlap。
4. 追当前源码与实际 dispatch，区分观测、条件模型及待验证假设。报告高贡献项、最慢 rank、调用次数、输入/输出契约和未解释范围；缺匹配 HCU 参考时不套其他 GPU 峰值。若用户提供前后 Prof，只在可比身份/窗口下说明变化，不把采集时延当正式加速比。
5. 输出按贡献排序的分析和最小验证建议。仅分析请求到此交付；优化请求将 analysis、capture、报告及假设交回模型优化 Skill，由后者创建 `optimization-plan` 并选择实现方向。

## 模型循环的交接

优化前交付当前最佳快照的 analysis/capture；优化后按模型优化 Skill 提供的候选快照补采，`prof-analyze` 带 `candidate_snapshot`。两次原件独立保存，capture 绑定 context/epoch/snapshot、实际执行、路径命中及全部分析 rank 的 trace。前置 analysis 继续作为计划依据；不能给旧 trace 换标签充当候选 Prof。

交接包包含：输入身份与哈希、rank/窗口/覆盖、上游 triage、TraceLens 实际执行项、热点及墙钟口径、源码/dispatch、假设和缺口。候选验收字段见工程 `docs/model-optimization-loop.md`；本 Skill 不提交 evaluate/keep，不执行算子调优或服务性能验收。证据存任务私有目录，分析工具成功不等于 HCU 质量或性能达标。
