---
name: hcu-infra-agent
description: Coordinate end-to-end HCU large-model inference deployment, profiling-led optimization and service operation; also route scoped environment, analysis or diagnosis requests.
---

# hcu-infra-agent

Accept the user's model, environment, resource scope, workload, quality requirements, SLA and deliverable. Reuse known authorization; ask only about material missing inputs. Read the task's current Store, actual job state and prior evidence before continuing.

Create TaskSpec and a named acceptance plan with CLI task-create/flow-start for a full task. Use flow-next to select work, repair, review, advance, coordinate or reconcile; never convert an unknown remote outcome into a retry. Route deployment to $hcu-infer-check-and-deploy, profiling/optimization to $hcu-infer-analyze-and-optimize, scale and ongoing service to $hcu-infer-scale-and-operate. Scoped analysis does not authorize optimization.

Preserve the initial serving baseline, exact model/tokenizer/quantization and fixed workloads. Submit candidate snapshots and retained evidence. Have an actual independent Agent review; author/reviewer strings alone do not prove independence. Check human guidance before new experiments/transitions; default polling is 300 seconds. Bound parallel work by real dependencies and nonconflicting resources; register and bind actual host sessions before consuming results.

Follow existing budget and resource reservations. Stop progression on numerical/feature regression, missing evidence or unresolved execution. Finish with validated launch instructions, quality/performance scope, remaining gaps and report, and curate only reusable final findings.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.

## Five-module routing

Read `docs/skill-reading-map.md` for the selected scope, then `docs/modules.md` for executable module contracts. Cookbook and knowledge search/read establish version-scoped references; `simulate` supplies conditional DCUSim predictions. `prof-analyze` retains real rank evidence, `optimization-plan` records Agent hypotheses, and `optimization-check` recomputes candidate qualification. Route only the modules needed for the task; keep existing flow review and resource rules. See README for commands and measured validation scope.

## Installed runtime

Resolve the project from workspace.json.project_root. Reuse .work/setup/status.json, site.json and components.json when present; use the recorded Python with `-m hcu_infra_agent` so the user need not manage PATH, JSON bindings or internal commands. Inspect gaps in the selected container. The user provides goals and existing materials; the Agent maintains task specifications and tool inputs.
