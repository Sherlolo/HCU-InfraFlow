# Repository instructions

Develop HCU large-model inference workflows. User task requirements take precedence.
- Preserve the single coordinator, deployment, optimization and operations stages; standalone environment/analysis/diagnosis are valid.
- Decide optimization directions from actual serving profiles; verify existing engine paths before writing kernels. Never treat a script run or bound skill as GPU validation.
- Freeze model/tokenizer/quantization, workload, engine snapshot and driver identity. Measure TTFT, TPOT, tail latency and throughput outside profiling; gate output quality and required serving features before accepting improvements.
- Never turn training loss, backward or optimizer checks into inference quality evidence.
- Keep experiments and secrets in the private workspace. Query bound sources read-only; do not update reference repositories or global skills implicitly.
- Reconcile unknown remote operations before retrying; the configured recovery_owner owns service recovery. Resource leases are not OS isolation.
- Run relevant tests and the offline demo; document actual validation scope. Do not claim HCU performance without executed evidence.
