"""Inference workflow skill identifiers."""
STAGE_SKILLS = {'adapt': 'hcu-infer-check-and-deploy', 'optimize': 'hcu-infer-analyze-and-optimize', 'fault-tolerance': 'hcu-infer-scale-and-operate'}
WIKI_SEARCH_SKILL = 'hcu-infer-knowledge-search'
WIKI_UPDATE_SKILL = 'hcu-infer-knowledge-curate'
SPECIALIST_SKILLS = {
    'operator': 'hcu-infer-operator-develop',
    'model-adaptation': 'hcu-infer-model-adapt',
    'model-optimization': 'hcu-infer-model-optimize',
}
WORKFLOW_SKILLS = ('hcu-infra-agent', *STAGE_SKILLS.values(), WIKI_SEARCH_SKILL,
                   WIKI_UPDATE_SKILL, *SPECIALIST_SKILLS.values())
