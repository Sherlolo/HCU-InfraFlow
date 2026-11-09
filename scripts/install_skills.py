"""Install this checkout's workflow and installation Skills into an explicitly selected directory."""
import argparse
import json
import shutil
from pathlib import Path


def install(target):
    root=Path(__file__).resolve().parents[1]
    sources=sorted((root/'skills').glob('*/SKILL.md'))
    target=Path(target).resolve()
    if target==root or target in root.parents:raise ValueError('Target cannot be the project or its ancestor')
    conflicts=[str(target/p.parent.name) for p in sources if (target/p.parent.name).exists()]
    if conflicts:raise ValueError('Existing skills left intact: '+', '.join(conflicts))
    target.mkdir(parents=True,exist_ok=True)
    for source in sources:
        destination=target/source.parent.name
        shutil.copytree(source.parent,destination)
        (destination/'workspace.json').write_text(json.dumps({'project_root':str(root)},indent=2)+'\n')
    return {'status':'complete','installed':[p.parent.name for p in sources],'target':str(target)}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--target',required=True)
    print(json.dumps(install(parser.parse_args().target),indent=2))
