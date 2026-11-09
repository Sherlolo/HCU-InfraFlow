---
name: hcu-infer-analyze-and-optimize
description: Analyze HCU serving traces and optimize measured LLM inference bottlenecks while preserving fixed-workload quality and SLA.
---

# hcu-infer-analyze-and-optimize

Begin from fixed profiler-off baseline. Use the bound profiler Skill for actual prefill/decode/rank trace capture and native TraceLens analysis. Validate trace freshness, nonempty GPU events, rank coverage, file hashes and actual tool outputs. Existing files or successful launch do not prove successful collection.

Prioritize observed wall-clock costs and explain a causal hypothesis. Inspect current implementation, relevant HCU knowledge and upstream/local history before selecting engine tuning, fusion or kernel work. Do not run a predetermined knob grid. Missing evidence calls for targeted capture. Keep overlapping kernel sums distinct from wall time and separate shape/dtype/stage/rank.

Use bound benchmark, BLAS, MoE or LightOp Skills only when their scope matches the bottleneck. Preserve real shapes, numerical/dispatch tests and isolated builds. Re-measure the end-to-end workload and required features outside profiling with at least three comparable repeats; local kernel gain is not serving gain. Submit current profile_evidence with observation, hypothesis and target, quality_inputs and performance_inputs, then independent review. Record rejected candidates and actual stop reasons.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.

## Executable module chain

Read `docs/modules.md` before first use. Import actual traces with `prof-analyze`; inspect its unknowns and original triage output. Use current analysis ID with `optimization-plan`, then execute scoped implementation/measurement through existing command cards. Use `optimization-check` on retained fixed-input comparisons; a pass still requires independent flow review. `simulate` invokes DCUSim for model/hardware/parallelism hypotheses, never as measured performance. Search/read Cookbook and knowledge to confirm existing mechanisms before implementing.

## Installed runtime

Resolve the project from workspace.json.project_root. Reuse .work/setup/status.json, site.json and components.json when present; use the recorded Python with `-m hcu_infra_agent` so the user need not manage PATH, JSON bindings or internal commands. Inspect gaps in the selected container. The user provides goals and existing materials; the Agent maintains task specifications and tool inputs.
