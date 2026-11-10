import json
import subprocess
from pathlib import Path
import pytest
from hcu_infra_agent.bindings import bind, verify, discover, SKILLS
from hcu_infra_agent.core import FlowError


def test_bound_sources_are_pinned_and_knowledge_search_readonly(tmp_path):
    pilot=tmp_path/'pilot';kb=tmp_path/'kb';kb.mkdir()
    for path in SKILLS.values():
        p=pilot/path;p.mkdir(parents=True);(p/'SKILL.md').write_text('fixture source')
    (kb/'kb.py').write_text('print("{}")')
    (kb/'knowledge').mkdir();page=kb/'knowledge/topic.md';page.write_text('# Inference\nSGLang KV cache dispatch\n')
    subprocess.run(['git','init',str(kb)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(kb),'add','knowledge'],check=True,capture_output=True)
    record=bind({'pilot_root':str(pilot),'knowledge_root':str(kb)},tmp_path/'bindings.json')
    assert verify(record)['status']=='pass'
    result=discover(record,'SGLang KV')
    assert result['status']=='partial' and result['hits'][0]['lines'][0]['line']==2
    (pilot/SKILLS['profile']/'SKILL.md').write_text('changed')
    with pytest.raises(FlowError):verify(record)


def test_install_has_binding_and_refuses_existing_target(tmp_path):
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'scripts/install_skills.py'
    spec=importlib.util.spec_from_file_location('installer',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    result=m.install(tmp_path/'skills')
    from hcu_infra_agent.skill_registry import WORKFLOW_SKILLS
    assert set(result['installed']) == {*WORKFLOW_SKILLS, 'hcu-infra-agent-install'}
    binding=json.loads((tmp_path/'skills/hcu-infra-agent/workspace.json').read_text())
    assert Path(binding['project_root']).joinpath('pyproject.toml').is_file()
    with pytest.raises(ValueError):m.install(tmp_path/'skills')
