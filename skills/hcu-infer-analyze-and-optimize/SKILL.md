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
