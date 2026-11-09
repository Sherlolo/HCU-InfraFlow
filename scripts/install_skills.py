"""Install or refresh project-managed Skills without overwriting foreign installations."""
import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path


def preflight(root, target, replace=False):
    root=Path(root).resolve();target=Path(target).expanduser().resolve()
    if target==root or target in root.parents or target.is_relative_to(root/'skills'):
        raise ValueError('Select a Skills directory outside the project Skill sources')
    sources=sorted((root/'skills').glob('*/SKILL.md'))
    for source in sources:
        destination=target/source.parent.name
        if not destination.exists():continue
        if not replace:raise ValueError('Existing Skill preserved; use --replace for this project: '+str(destination))
        binding=destination/'workspace.json'
        if not binding.is_file() or Path(json.loads(binding.read_text()).get('project_root','')).resolve()!=root:
            raise ValueError('Foreign Skill binding preserved: '+str(destination))
    return sources,target


def install(target, replace=False):
    root=Path(__file__).resolve().parents[1]
    sources,target=preflight(root,target,replace)
    target.mkdir(parents=True,exist_ok=True)
    for source in sources:
        destination=target/source.parent.name
        stage=target/('.install-'+uuid.uuid4().hex)
        backup=target/('.previous-'+uuid.uuid4().hex)
        shutil.copytree(source.parent,stage)
        (stage/'workspace.json').write_text(json.dumps({'project_root':str(root),'python':sys.executable},indent=2)+'\n')
        moved=False
        try:
            if destination.exists():destination.rename(backup);moved=True
            stage.rename(destination)
        except OSError:
            if moved:backup.rename(destination)
            raise
        finally:
            if stage.exists():shutil.rmtree(stage)
        if moved:shutil.rmtree(backup)
    return {'status':'complete','installed':[p.parent.name for p in sources],'target':str(target)}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',required=True);p.add_argument('--replace',action='store_true')
    a=p.parse_args();print(json.dumps(install(a.target,a.replace),indent=2))
