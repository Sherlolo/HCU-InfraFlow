---
name: hcu-infer-check-and-deploy
description: Inspect HCU inference environments and adapt or deploy large-model serving with reproducible launch and output-quality baselines.
---

# hcu-infer-check-and-deploy

Read the actual container/host mappings, allocation, device occupancy, DTK and effective engine/plugin/library versions. Prefer the applicable HCU cookbook/launch implementation, checking current CLI help rather than copying NVIDIA-only flags. External inputs stay read-only and caches/builds/logs go under the task workspace.

Freeze source revision plus local bytes, model/tokenizer, quantization and KV dtype, chat template, required endpoints and workload. Budget weights, KV cache, graph/workspace peaks and headroom against actual available resources. Validate readiness, requests, streaming and required model features. Preserve original request/response and numeric evidence; no backward, optimizer or training-loss checks stand in for inference quality.

Deliver fixed command cards and source snapshot, effective env, resource/health observations, initial output-quality and profiler-off performance baseline. Diagnose environment discrepancies before accepting them as the normal limit. A running endpoint alone is not completion.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.

## Recipe and capacity inputs

Use `cookbook-search` then `cookbook-read` to inspect the actual page, source kind and revision before adopting a recipe. Cookbook queries use the official HYGON-AI/inference-cookbook-das site and pinned commits. Use `simulate` for explicit offline model/parallelism memory and latency predictions, then calibrate against actual serving. See `docs/modules.md` for inputs and provenance.
