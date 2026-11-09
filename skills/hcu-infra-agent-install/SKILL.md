---
name: hcu-infra-agent-install
description: Check and prepare HCU Infra Agent dependencies in a user-selected container, fetch official SimTools, and guide manual knowledge installation.
---

# HCU Infra Agent installation and readiness

Identify the user's actual container and mapped project/workspace paths before running installation. Prompt the user to select a container only if it cannot be inferred from their environment; do not reuse a historical person's container. Run checks inside the selected container. Distinguish a declared container name from verified runtime context.

Locate the project from adjacent workspace.json.project_root after installation, or the checkout root. Read README and docs/modules.md for the current commands.

Run `hcu-infra-agent doctor CONFIG --online --output REPORT`. Inspect every missing or unverified component, including Python, Git, inference/profiler Skills, service interpreter, simulation runtime and official Cookbook connectivity. A missing optional use case need not block independent available work; state its scope. Passing package checks is not GPU or model qualification.

For SimTools use `component-fetch simtools NEW_DIRECTORY`, which fetches https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools. Inspect available wheels and the source's requirements, then explicitly run scripts/setup_simulation.py with a compatible wheel and a task-owned isolated environment. Do not modify the container's shared serving packages, upgrade its base image, overwrite an existing checkout or retry a partial fetch blindly.

HCU-Knowledge must be installed by the user. Report the missing path/content/access and ask the user to provide their installation. Never clone, bootstrap, update or rebuild it as an installation side effect. Once provided, bind knowledge_root and verify it.

Cookbook queries use https://github.com/HYGON-AI/inference-cookbook-das directly. Read pinned official links and check applicable images, hardware and framework versions before recommending an image or launch command. Do not silently replace this source with a local knowledge mirror.

After setup rerun doctor in the same container and report what is ready, missing or unverified, the selected interpreters and source revisions. Preserve existing user authorization and continue reversible task-local work without repeated permission questions.
