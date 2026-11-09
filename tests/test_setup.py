"""One-command setup contracts: managed updates, interpreter reuse and manual knowledge."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest


def load_script(name):
    import sys
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location(name,root/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def test_managed_skill_update_and_foreign_preservation(tmp_path):
    installer=load_script('install_skills')
    target=tmp_path/'skills';installer.install(target)
    skill=target/'hcu-infra-agent/SKILL.md';skill.write_text('stale')
    installer.install(target,replace=True)
    assert skill.read_text()!='stale'
    binding=target/'hcu-infra-agent/workspace.json'
    binding.write_text(json.dumps({'project_root':str(tmp_path/'another-project')}))
    with pytest.raises(ValueError,match='Foreign'):installer.install(target,replace=True)
    assert json.loads(binding.read_text())['project_root']==str(tmp_path/'another-project')


def test_setup_reuses_current_python_and_does_not_install_knowledge(tmp_path,monkeypatch):
    module=load_script('setup_hcu_infra')
    root=tmp_path/'project';root.mkdir();pilot=tmp_path/'pilot';pilot.mkdir()
    calls=[]
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module,'existing_distribution',lambda p:None)
    monkeypatch.setattr(module,'preflight',lambda *a:None)
    monkeypatch.setattr(module,'run',lambda cmd,**kwargs:calls.append(cmd))
    monkeypatch.setattr(module,'doctor',lambda *a:{'status':'incomplete','components':[]})
    monkeypatch.setattr(module,'install',lambda *a:{'installed':['fixture'],'target':str(tmp_path/'skills')})
    args=SimpleNamespace(with_simtools=False,tools_only=False,skills_dir=tmp_path/'skills',replace=False,wheelhouse=None,
                         test=False,pilot_root=str(pilot),knowledge_root=str(tmp_path/'manual-knowledge'),kernel_skill=None,online_check=False)
    result=module.setup(args)
    assert result['status']=='installed' and result['knowledge_installation']=='manual-only'
    assert calls[0][:3]==[module.sys.executable,'-m','pip']
    assert not any('venv' in str(arg) for cmd in calls for arg in cmd[1:])
    assert not (tmp_path/'manual-knowledge').exists()
    assert (root/'.work/setup/site.json').exists()


def test_readme_uses_install_script_and_prompts():
    root=Path(__file__).resolve().parents[1];text=(root/'README.md').read_text()
    assert '.venv' not in text
    assert 'python scripts/setup_hcu_infra.py' in text
    assert '$hcu-infra-agent' in text and '知识库需要使用者手动安装' in text


def test_update_preserves_saved_component_selection(tmp_path,monkeypatch):
    module=load_script('setup_hcu_infra')
    root=tmp_path/'project';(root/'.work/setup').mkdir(parents=True)
    pilot=tmp_path/'existing-pilot';pilot.mkdir()
    selected=tmp_path/'user-managed-knowledge'
    (root/'.work/setup/site.json').write_text(json.dumps({'pilot_root':str(pilot),'knowledge_root':str(selected),'serving_python':'/selected/python'}))
    monkeypatch.setattr(module,'ROOT',root);monkeypatch.setattr(module,'existing_distribution',lambda *a:None)
    monkeypatch.setattr(module,'run',lambda *a,**k:None);monkeypatch.setattr(module,'doctor',lambda *a:{'status':'incomplete'})
    args=SimpleNamespace(with_simtools=False,tools_only=True,skills_dir=None,replace=False,wheelhouse=None,test=False,
                         pilot_root=None,knowledge_root=None,kernel_skill=None,online_check=False)
    module.setup(args)
    config=json.loads((root/'.work/setup/site.json').read_text())
    assert config['knowledge_root']==str(selected) and config['serving_python']=='/selected/python'
    assert not selected.exists()


def test_source_metadata_does_not_masquerade_as_foreign_install(tmp_path,monkeypatch):
    module=load_script('setup_hcu_infra');project=tmp_path/'project'
    source=SimpleNamespace(metadata={'Name':'hcu-infra-agent'},locate_file=lambda name:project/'src',read_text=lambda name:None)
    monkeypatch.setattr(module.importlib.metadata,'distributions',lambda:[source])
    module.existing_distribution(project)
    foreign=SimpleNamespace(metadata={'Name':'hcu-infra-agent'},locate_file=lambda name:tmp_path/'site',
                            read_text=lambda name:json.dumps({'url':(tmp_path/'other').as_uri()}))
    monkeypatch.setattr(module.importlib.metadata,'distributions',lambda:[source,foreign])
    with pytest.raises(ValueError,match='another'):module.existing_distribution(project)
