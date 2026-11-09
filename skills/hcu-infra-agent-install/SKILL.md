---
name: hcu-infra-agent-install
description: Install or update HCU Infra Agent and check its components in the selected Python/container, with optional SimTools acquisition and manual knowledge installation.
---

# Installation and component readiness

Locate the checkout using workspace.json.project_root or the source root. Read scripts/setup_hcu_infra.py --help and README. The user supplies their environment and available knowledge location; manage flags, config files, checks and internal commands yourself.

Use `python scripts/setup_hcu_infra.py` with the selected existing Python >=3.10. It installs the package and seven Skills directly, records that interpreter and component paths, and creates no virtual environment. Use --skills-dir for the actual Agent host's Skill directory. A remote container tool installation may use --tools-only while Agent Skills remain on their actual host. Reuse recorded paths in .work/setup rather than asking for them again.

Use --replace only for updating this project's managed Skill copies; do not overwrite a foreign checkout binding. The installer refuses a Python package owned by another installation. If that happens, select a suitable existing environment; do not uninstall another project silently.

For SimTools select a compatible CPython 3.10 Linux container, then use --with-simtools. The source is https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools; --simtools-root can reuse an existing selected source. Installation uses the same selected interpreter. Do not silently downgrade an incompatible NumPy or upgrade the base image/shared serving stack.

HCU-Knowledge is manually installed by the user. Pass --knowledge-root to reuse it, or discover an existing sibling checkout. Never clone, bootstrap, update or rebuild the knowledge repository as a setup side effect. Missing knowledge is a component gap; independent Cookbook queries can still proceed.

Read .work/setup/components.json and use doctor with the generated site.json for further checks, adding --online when connectivity must be checked. Missing paths and unavailable features stay explicit. Passing package checks does not validate GPU access, a model or performance. Cookbook reads come directly from https://github.com/HYGON-AI/inference-cookbook-das at pinned commits.

Before real serving, confirm the user's actual HCU/DTK container and workspace mapping. Do not reuse another person's container or infer that a declared name is an inspected identity. End with the installed components, outstanding gaps and a simple next prompt such as `$hcu-infra-agent 分析这些 trace`.
