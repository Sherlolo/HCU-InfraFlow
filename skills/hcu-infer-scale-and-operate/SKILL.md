---
name: hcu-infer-scale-and-operate
description: Validate HCU inference scale-out and diagnose or observe serving reliability with explicit recovery ownership.
---

# hcu-infer-scale-and-operate

Keep engine/model/workload identities fixed while checking requested TP/EP/DP or prefill/decode topology changes. Revalidate outputs, required features, SLA and throughput after scaling; avoid extrapolating single-card evidence.

For incidents preserve effective launch, logs and a reproducible request before choosing trace/dump/communication tools. Distinguish service failure, idle load, telemetry staleness and observer failure. Feed normalized current-context and attempt-specific observations to observe; use outbox claim/complete with actual handling receipts.

Only the configured recovery_owner performs authorized recovery. Reconcile old commands and verify owned process identity before restarting or cleaning a process group. Check readiness, model identity, warmup and request quality after recovery. Notification delivery, Agent wakeup and successful recovery require separate evidence. Explicitly report unverified long-running behavior.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.
