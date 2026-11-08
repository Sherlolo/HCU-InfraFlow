---
name: hcu-infer-knowledge-search
description: Retrieve version-scoped HCU inference knowledge and route profiling, benchmarking, BLAS, MoE and incident Skills from bound local sources.
---

# hcu-infer-knowledge-search

Read the selected bindings JSON and verify it with bindings-check. Query knowledge-search for the actual model, engine/version and observed mechanism. Read result bodies and source revisions before using a claim. Keep source/PR reference, local implementation and hardware measurements separate.

If native index, permission or runtime is unavailable, report the gap; direct source reading can continue with explicit paths and hashes. Entry hashes cover those files only, not all nested scripts. Before executing an external Skill's tool, verify its dependencies, version and actual output. Do not bootstrap/update knowledge repositories or install global Skills as a search side effect. Training-only retrieved material does not grant inference acceptance.

## Project resources

For CLI schemas and stage gates read `docs/contracts.md` and the relevant deployment/optimization/operations document from the selected project root. Installed Skills locate that root in adjacent `workspace.json.project_root`; in a source checkout use the repository root. Keep task evidence in its separate private workspace.

## Search without a derived index

Use `knowledge-query`/`knowledge-read` for tracked text and `cookbook-search`/`cookbook-read` for the separately bound recipe scope. These commands do not create a Store or mutate the bound repository; partial/exit 2 preserves usable hits but indicates limited coverage. Read matching bodies, not only snippets. `knowledge-search` retains the separate native index path. Commands and examples are in `docs/modules.md` and README.
