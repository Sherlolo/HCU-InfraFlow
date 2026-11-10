# 算子开发与框架接入

模块把真实 profile 的热点交给专项算子 Skill，再自动执行选定框架 adapter 的接入与验证。它提供可运行的协调协议；具体 kernel、框架补丁及站点 runner 由 Agent 根据现场源码与工作负载生成。不会假定所有模型共享一份融合 kernel，也不把命令执行当成 GPU 验证。

## 入口与证据

三个命令均为 `hcu-infra-agent --workspace WORKSPACE COMMAND TASK REQUEST.json`，支持 `--output FILE`。

- `operator-plan`：固定当前 analysis 与真实 shape 契约，选择已安装的 Skill，返回 `plan` artifact。
- `operator-dispatch`：执行已配置的 skill/Agent runner，返回 `artifact`（development receipt）。
- `operator-integrate`：执行框架 apply → verify，已知失败时 rollback；返回接入报告 artifact。

Profile 来源要求 active optimize/full task 的当前 analysis。`operator-plan` 的 JSON：

```json
{
  "analysis": "CURRENT_ANALYSIS_ARTIFACT",
  "kind": "gemm",
  "target": "linear projection dispatch",
  "observation": "真实 trace 中对应 GEMM 占据主要 decode 时间，已核查调用栈",
  "existing_path": "所选引擎 commit 的文件:函数及现有库调用",
  "shape_contract": {
    "shapes": [[1, 4096, 4096]],
    "dtype": "bf16",
    "layout": "实际 stride、转置与连续性",
    "phase": "decode",
    "semantics": "Y = X W；记录 scale、epilogue 等适用条件",
    "tolerance": "固定 oracle 与模型质量契约确定的容差"
  },
  "skill_path": "实际安装的 gemm-tuning/SKILL.md"
}
```

该 shape 仅为格式示例，不能作为默认调优 workload。kind 为 fusion/triton/tilelang/gemm/hip；对应 `lightop-kernel-agent-loop`、`kernel-triton-optimize`、显式 TileLang Skill、`gemm-tuning`、`kernel-hip-optimize`。TileLang 必须同时提供实际 `skill_name`，不会虚构上游不存在的入口。绑定文件需有匹配的 frontmatter name；执行前重验入口哈希。入口哈希不代表所有脚本/依赖均已冻结，专项 Skill 应另行记录实际依赖与版本。

模型跑不通且缺 kernel 时，用 `adaptation_plan`、`gap_id` **替代** `analysis`。来源必须是当前 task/context epoch 的最新 `adaptation-plan-recorded` artifact，gap 必须为 missing kernel 且 operator_backend 与 kind 同为 triton 或 hip。此时选择对应 baseline Skill，允许 adapt/full/optimize 模式。这条路径恢复运行能力，不宣称 profile 证明了收益。

## 专项 Skill 的真实调用

专项来源：[hcu-infer-pilot](https://github.com/Sherlolo/hcu-infer-pilot)。读取实际已安装的 Skill，保留其依赖引用与许可；不要把外部 checkout 的机器路径写进本项目 Skill。Agent 用户通常只提供目标；下面的绑定和命令卡由主控根据实际运行环境维护。

dispatch 请求包含 `plan`、`operation`（唯一且可重试的操作 ID）、`lease`（`lease-acquire` 返回的对象）、`card`（已有 command-card schema）。card.argv 必须包含独立的 `"{operator_prompt}"` 参数。模块以完整固定任务文本替换该参数，交给站点提供、确实存在的 Agent/skill adapter。没有通用的 `gemm-tuning` 可执行命令；先确认所选 runner 的真实 CLI。

```json
{
  "plan": "OPERATOR_PLAN_ARTIFACT",
  "operation": "develop-linear-1",
  "lease": {"resource": "选定资源", "owner": "实际owner", "token": 1},
  "card": {
    "schema_version": 1,
    "backend": "local",
    "cwd": "任务私有目录绝对路径",
    "argv": ["实际runner入口", "实际prompt参数", "{operator_prompt}"],
    "timeout_seconds": 600,
    "basis": "已核对的 runner 接口及授权算子任务"
  }
}
```

runner 文本参数是 argv 数据，不拼入 shell。允许已有 ssh/ssh-docker 等 backend，绑定 Skill 路径及依赖必须在 runner 侧可访问；控制端和执行端不同的情况下按已验证映射准备资源。`status=complete` 仅说明 runner 返回，`hardware_validated=false` 明确不把它升级为硬件证据。原始 stdout/stderr/plan 由既有 execution machinery 留存。

runner 完成开发后把实际候选源码快照留存到相同 Store，stdout 输出一个 JSON 对象，包含 `plan`、`context`、`context_epoch`、`candidate_snapshot`；诊断写 stderr。模块在命令环境中注入 `HCU_INFRA_OPERATOR_PLAN` 供 adapter 读取计划 ID。进入 integration 时会核对 operations 表中的真实已完成操作、原命令卡、固定 prompt/plan 及该 stdout receipt；自己写一个“开发完成”JSON、替换候选 snapshot 或引用无关成功命令都不能接入。

## 框架 adapter 与自动接入

integration 请求字段：`plan`、`development`（dispatch artifact）、`framework`（sglang/vllm）、`candidate_snapshot`（已留存源快照 artifact）、`operation`、`lease`、`cards`。cards 必须含 apply/verify/rollback 三份 command card，三者目标 backend/host/container/cwd 一致。先验证所有命令卡，再执行任何变更。

缺失算子来源的 framework 还必须与模型适配计划一致。profile 来源按当前模型任务的实际框架生成 adapter，不能只因另一个框架也提供同名算子就直接套用。

Agent 根据当前框架源码写 adapter：

1. apply 核验基线 commit/源文件哈希，在隔离候选 checkout 应用补丁、构建或加载。可使用插件/注册 API 时优先复用；不可复用时提供可回放 patch。只切换该任务的候选，不隐式替换运行服务或全局包。
2. verify 核对 build/import、与 oracle 的算子正确性、实际 serving dispatch 命中新 kernel、动态形状与未支持情况的 fallback，并运行 serving smoke。需要图模式的任务还覆盖 capture/replay 与 stream；多卡则验证 rank 一致性和通信语义。
3. rollback 恢复 adapter 修改前的快照、分发开关与包配置，覆盖 apply 部分失败。避免用会抹除无关变更的 reset/clean 命令。脚本应检查恢复后的源哈希/状态再返回零。

verify stdout 必须是**一个 JSON 对象**；诊断写 stderr。对象格式：

```json
{
  "schema_version": 1,
  "plan": "OPERATOR_PLAN_ARTIFACT",
  "framework": "sglang",
  "candidate_snapshot": "RETAINED_CANDIDATE_ARTIFACT",
  "context": "TASK_CONTEXT_HASH",
  "context_epoch": 0,
  "executed": 4,
  "candidate_path_exercised": true,
  "checks": {
    "build": true,
    "operator_correctness": true,
    "framework_dispatch": true,
    "serving_smoke": true
  },
  "failures": [],
  "skipped_required": [],
  "required_missing": [],
  "evidence": ["RETAINED_RAW_CHECK_LOG_ARTIFACT"]
}
```

脚本用相同 Store 的 `artifact-add` 或 Python API 留存实际日志，再将 artifact ID 放入 evidence；不能随意填路径或空证据。身份不符、空 stdout、未实际调用候选、跳过必需检查均失败并回滚。receipt 是 adapter 的可审计声明，模块不自行推断 stdout 中的数值正确性；独立复核仍需检查原始证据。后续固定模型质量和端到端性能必须使用现有 `optimization-check`。

报告的 `integration_verified=true` 仅表示上述接入检查已通过，`accepted_by_flow=false` 保持独立复核边界。CPU fixture 的通过不得报告 HCU 验收或模型提速。

## 重试、停止与回退

apply/verify/rollback 使用原操作 ID 的固定后缀，重复同一请求复用原 execution intent 和结果，不重复应用补丁。相同 integration operation ID 不能绑定不同卡片/候选；更换有效 lease 不改变请求身份。终态报告存入 `modules/operator-integration/` 并引用不可变 artifact。

远端非零退出或超时产生 unknown，模块停止，不执行可能与原进程冲突的 rollback。由任务 recovery_owner 核查原操作，使用 `operation-reconcile` 后重试原请求；不要另起 operation 绕过未知状态。rollback 自身失败或未知时返回 incomplete，要求恢复核查。预算、资源租约和 flow 指导门槛沿用既有执行模块；租约不等于 OS 隔离。

局部优化完成后保留精度、性能、ISA（需要时）、注册分发和回退证据，再交回模型适配或模型优化循环。对所有候选记录相同输入下的基线、当前最佳、拒绝原因与停止条件；不因单算子提速直接保留模型改动。

## 从 TrainFlow 迁移的推理测量约束

保留模型内外同条件对照与底层依赖联动的方法，去除 backward、optimizer、训练 loss 的验收含义。算子调用绑定具体 run/rank/step/call；MoE token/split、动态序列和 KV 长度不同，即使同层同算子名也不能强行配对。只重建 shape/dtype 的随机张量属于合成元数据重放，索引、mask、稀疏分布与量化 scale 需由实际 adapter 补齐。

分别保存干净 serving、模型内诊断和独立算子重放。计时覆盖完整调用的 scratch 初始化、必要 copy 及全部子 kernel，区分设备服务时间与主机提交到完成时间；不要给拆分后的每个子 kernel 重复记整张量 FLOPs。缓存命中、启动、编译、warmup 与初始化不混入稳态收益口径。

独立算子快而模型内慢时先查队列、stream、通信 overlap、HBM/缓存竞争、CPU 提交与 rank 到达，不直接重写 kernel。底层改动同时固定父仓 gitlink、构建脚本实际 checkout 与最终加载 wheel/so/code-object 哈希、ABI、DTK/gfx；三者可能不同。仅在隔离前缀构建和加载候选，核查 import/动态链接/真实 dispatch，避免旧 JIT 缓存掩盖结果。共享 buffer、通信协议或 ABI 耦合修改需共同集成验证。
