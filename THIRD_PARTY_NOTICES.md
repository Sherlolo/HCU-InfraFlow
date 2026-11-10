# Third-party notices

HCU-TrainFlow, MIT, Copyright (c) 2026 HCU-TrainFlow contributors. Original LICENSE is retained verbatim.
Derived infrastructure modules and exact reference commit are enumerated in provenance.json. Inference contracts and workflow routing were changed for this distribution.

infra-agent-v2 (AMD Hyperloom based adaptation), MIT: consulted for profile-driven inference planning, fixed workload and validation design. No Hyperloom runtime package is vendored.
DCU-Infer-Pilot and HCU-Knowledge are external local bindings; their content, permissions and licenses remain owned by their repositories. No training corpus or large source/evidence assets are redistributed.

Specialist workflow expansion (2026-11-09): HCU-TrainFlow skill concepts were rewritten for inference; source revision and scope are recorded in provenance.json. The sglang-model-day0-support skill was consulted for release locks and architecture-gap validation. hcu-infer-pilot (https://github.com/Sherlolo/hcu-infer-pilot) remains an external, explicitly bound source for operator skills and kernels; no third-party kernel implementation is copied into this package.
