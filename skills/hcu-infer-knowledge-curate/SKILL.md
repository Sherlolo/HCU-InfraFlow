---
name: hcu-infer-knowledge-curate
description: Curate verified, reusable HCU inference findings into the selected project knowledge scope after task milestones or explicit maintenance requests.
---

# hcu-infer-knowledge-curate

Read the private task report and original evidence. Separate intermediate candidates from reusable final findings. Shared entries need trigger, applicability (engine/revision/hardware/shape/dtype), mechanism, source citations, correctness/performance scope, failure cases and fallback. Do not promote raw logs or claim hardware validation from local tests.

Update only the authorized project's shared inference knowledge and affected Skill/contracts. Query HCU-Knowledge read-only unless its maintenance is explicitly in scope. Keep private model/request/environment details out of public outputs. Recheck affected references and validate updated Skills. A knowledge-followup is advisory, not an automatic source fetch or publication authorization.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.
