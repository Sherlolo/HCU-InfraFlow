"""Inference workflow skill identifiers."""
STAGE_SKILLS = {'adapt': 'hcu-infer-check-and-deploy', 'optimize': 'hcu-infer-model-optimize', 'fault-tolerance': 'hcu-infer-diagnose-and-fix'}
PROFILE_SKILL = 'hcu-infer-analyze'
WIKI_SEARCH_SKILL = 'hcu-infer-knowledge-search'
WIKI_UPDATE_SKILL = 'hcu-infer-knowledge-curate'
SPECIALIST_SKILLS = {
    'operator': 'hcu-infer-operator-develop',
    'model-adaptation': 'hcu-infer-model-adapt',
    'model-optimization': 'hcu-infer-model-optimize',
}
WORKFLOW_SKILLS = tuple(dict.fromkeys(('hcu-infra-agent', *STAGE_SKILLS.values(), PROFILE_SKILL,
                                      WIKI_SEARCH_SKILL, WIKI_UPDATE_SKILL, *SPECIALIST_SKILLS.values())))
