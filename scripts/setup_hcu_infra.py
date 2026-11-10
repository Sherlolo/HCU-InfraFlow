"""Install HCU Infra Agent and Skills using the selected Python, without virtual environments."""
import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from hcu_infra_agent.core import FlowError, write_json
from hcu_infra_agent.bindings import bind
from hcu_infra_agent.installation import doctor, fetch_simtools
from install_skills import install, preflight

PILOT_URL='https://github.com/Sherlolo/hcu-infer-pilot.git'


def existing_distribution(project):
    from urllib.parse import unquote,urlsplit
    for d in importlib.metadata.distributions():
        if d.metadata.get('Name','').lower().replace('_','-')!='hcu-infra-agent':continue
        # Editable source metadata is not an installed environment binding.
        if Path(d.locate_file('')).resolve()==project/'src':continue
        direct=json.loads(d.read_text('direct_url.json') or '{}')
        bound=unquote(urlsplit(direct.get('url','')).path)
        if not bound or Path(bound).resolve()!=project:
            raise FlowError('This Python already has another hcu-infra-agent installation. Select a different existing container/interpreter rather than replacing it silently.')



def run(argv, **kwargs):
    result=subprocess.run([str(x) for x in argv],check=False,**kwargs)
    if result.returncode:raise FlowError('Installation stage failed; inspect the output and rerun after fixing it')


def setup(args):
    if sys.version_info<(3,10):raise FlowError('Use Python >=3.10 in the selected environment')
    if args.with_simtools and sys.version_info[:2]!=(3,10):raise FlowError('--with-simtools requires CPython 3.10 on Linux x86_64')
    previous_path=ROOT/'.work/setup/site.json'
    previous=json.loads(previous_path.read_text()) if previous_path.is_file() else {}
    status_path=ROOT/'.work/setup/status.json'
    prior_status=json.loads(status_path.read_text()) if status_path.is_file() else {}
    args.skills_dir=args.skills_dir or prior_status.get('skills',{}).get('target') or str(Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'skills')
    if not args.tools_only:preflight(ROOT,args.skills_dir,args.replace)
    existing_distribution(ROOT)
    flags=['--no-index','--find-links',str(Path(args.wheelhouse).resolve())] if args.wheelhouse else []
    package=str(ROOT)+('[test]' if args.test else '')
    print('Setup: install package into selected Python '+sys.executable,flush=True)
    run([sys.executable,'-m','pip','install',*flags,*([] if args.test else ['--no-deps']),'-e',package],cwd=ROOT)
    config={**previous,'execution_context':{'kind':'container' if Path('/.dockerenv').exists() or Path('/run/.containerenv').exists() else 'host'},
            'serving_python':getattr(args,'serving_python',None) or previous.get('serving_python',sys.executable),'knowledge_python':previous.get('knowledge_python',sys.executable)}
    pilot_arg=args.pilot_root or previous.get('pilot_root')
    pilot=Path(pilot_arg).expanduser().resolve() if pilot_arg else next((p for p in [ROOT/'.deps/hcu-infer-pilot',ROOT.parent/'hcu-infer-pilot',ROOT.parent/'dcu-infer-pilot',ROOT/'.deps/dcu-infer-pilot'] if p.is_dir()),ROOT/'.deps/hcu-infer-pilot')
    if not pilot.exists():
        print('Setup: fetch inference Skills',flush=True)
        pilot.parent.mkdir(parents=True,exist_ok=True)
        run(['git','clone','--depth','1',PILOT_URL,pilot],timeout=180,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
    config['pilot_root']=str(pilot)
    knowledge_arg=args.knowledge_root or previous.get('knowledge_root')
    knowledge=Path(knowledge_arg).expanduser().resolve() if knowledge_arg else ROOT.parent/'hcu-knowledge'
    config['knowledge_root']=str(knowledge)
    kernel_arg=args.kernel_skill or previous.get('kernel_skill')
    kernel=Path(kernel_arg).expanduser().resolve() if kernel_arg else pilot/'skills/lightop-kernel-agent-loop/SKILL.md'
    if kernel.is_file():config['kernel_skill']=str(kernel)
    if args.with_simtools:
        tools=Path(args.simtools_root).expanduser().resolve() if args.simtools_root else ROOT/'.deps/DCUSimTools'
        if not tools.exists():
            fetched=fetch_simtools(tools)
            write_json(ROOT/'.work/setup/simtools-source.json',fetched)
            if fetched['status']!='complete':raise FlowError('SimTools acquisition incomplete; inspect .work/setup/simtools-source.json')
        wheels=sorted(p for p in tools.rglob('dcusim-*.whl') if 'cp310-cp310-linux_x86_64' in p.name)
        if len(wheels)!=1:raise FlowError('Expected one compatible DCUSim wheel; select a source directory containing the intended release')
        print('Setup: install SimTools in selected Python',flush=True)
        command=[sys.executable,ROOT/'scripts/setup_simulation.py','--wheel',wheels[0]]
        if args.wheelhouse:command+=['--wheelhouse',args.wheelhouse]
        run(command,cwd=ROOT)
        config.update(simulation_python=sys.executable,simulation_wheel=str(wheels[0]))
    else:
        try:importlib.metadata.version('dcusim');config['simulation_python']=sys.executable
        except importlib.metadata.PackageNotFoundError:pass
    config_path=ROOT/'.work/setup/site.json'
    write_json(config_path,config)
    report=doctor(config,args.online_check)
    write_json(ROOT/'.work/setup/components.json',report)
    bindings=None
    if knowledge.is_dir():
        try:bindings=bind(config,ROOT/'.work/setup/bindings.json')
        except (OSError,ValueError) as exc:report['binding_error']=str(exc)
    write_json(ROOT/'.work/setup/components.json',report)
    if not args.tools_only:
        print('Setup: install Skills',flush=True)
        installed=install(args.skills_dir,args.replace)
    else:installed={'installed':[],'target':None}
    result={'status':'installed','project_root':str(ROOT),'python':sys.executable,'skills':installed,
            'config':str(config_path),'components_status':report['status'],'bindings_ready':bindings is not None,
            'knowledge_installation':'manual-only','next':'Start a new Agent session and use $hcu-infra-agent. The Agent reads .work/setup/site.json and components.json; missing knowledge must be supplied by the user.'}
    write_json(ROOT/'.work/setup/status.json',result)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skills-dir',help='Agent Skill directory; reuses the previous target or the default Agent directory')
    p.add_argument('--serving-python');p.add_argument('--knowledge-root');p.add_argument('--pilot-root');p.add_argument('--kernel-skill')
    p.add_argument('--with-simtools',action='store_true');p.add_argument('--simtools-root')
    p.add_argument('--replace',action='store_true');p.add_argument('--tools-only',action='store_true')
    p.add_argument('--wheelhouse');p.add_argument('--test',action='store_true');p.add_argument('--online-check',action='store_true')
    try:
        result=setup(p.parse_args(argv));print(json.dumps(result,indent=2,ensure_ascii=False))
        print('Installed. Open a new Agent session. Component gaps are recorded for the installation Skill.')
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        print('Setup incomplete: '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
