"""Side-effect-free component checks and explicit task-local SimTools acquisition."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from .core import FlowError
from .bindings import SKILLS
from .cookbook import URL as COOKBOOK_URL

SIMTOOLS_URL='https://developer.sourcefind.cn/codes/OpenDAS/DCUSimTools'


def doctor(config, online=False):
    rows=[]
    def add(name,ready,detail,action):
        rows.append({'component':name,'status':'ready' if ready else 'missing','detail':detail,'action':None if ready else action})
    in_container=Path('/.dockerenv').exists() or Path('/run/.containerenv').exists()
    context=config.get('execution_context',{})
    host_allowed=context.get('kind')=='host'
    add('execution-container',in_container or host_allowed,
        {'detected_container':in_container,'declared':context,'python':sys.executable},
        'Choose your HCU/DTK serving container, enter it, and rerun this check. A declared name is not an inspected container identity.')
    add('workflow-python',sys.version_info>=(3,10),sys.version.split()[0],'Use Python >=3.10 in the selected environment')
    add('git',bool(shutil.which('git')),shutil.which('git'),'Install Git in the selected environment')
    pilot=Path(config.get('pilot_root','/nonexistent'))
    for role,relative in SKILLS.items():
        path=Path(config['kernel_skill']) if role=='kernel' and config.get('kernel_skill') else pilot/relative/'SKILL.md'
        add('skill:'+role,path.is_file(),str(path),'Manually provide the matching Skill checkout or explicit binding')
    kb=Path(config.get('knowledge_root','/nonexistent'))
    add('knowledge-manual', (kb/'kb.py').is_file() and (kb/'knowledge').is_dir(),str(kb),
        'User must manually install HCU-Knowledge, its content and access permissions, then set knowledge_root; this installer never clones or updates it')
    python=config.get('simulation_python')
    probe={'status':'not-configured'}
    if python and Path(python).is_file():
        code='import json,sys,numpy,openpyxl,dcusim;print(json.dumps({"python":sys.version_info[:2],"numpy":numpy.__version__,"dcusim":dcusim.__version__}))'
        try:
            p=subprocess.run([python,'-c',code],capture_output=True,text=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            probe=json.loads(p.stdout) if p.returncode==0 else {'status':'import-failed','stderr':p.stderr[-1500:]}
        except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:probe={'status':'unverified','reason':str(exc)}
    ready=probe.get('python')==[3,10] and str(probe.get('numpy','')).split('.')[0]=='1' and bool(probe.get('dcusim'))
    add('simulation-runtime',ready,probe,'Fetch SimTools from '+SIMTOOLS_URL+' and run scripts/setup_simulation.py in CPython 3.10; packages install only in the selected isolated environment')
    serving=config.get('serving_python')
    service={'status':'not-configured'}
    if serving:
        code='import importlib.util,json;print(json.dumps({n:importlib.util.find_spec(n) is not None for n in ["torch","sglang","vllm"]}))'
        try:
            p=subprocess.run([serving,'-c',code],capture_output=True,text=True,timeout=20)
            service=json.loads(p.stdout) if p.returncode==0 else {'status':'probe-failed'}
        except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError) as exc:service={'status':'unverified','reason':str(exc)}
    add('serving-runtime',bool(service.get('torch') and (service.get('sglang') or service.get('vllm'))),service,
        'Set serving_python to the selected container interpreter with the actual HCU PyTorch and SGLang/vLLM installation')
    network={'status':'not-checked','url':COOKBOOK_URL}
    if online:
        from .cookbook import revision
        try:network={'status':'ready','url':COOKBOOK_URL,'revision':revision()}
        except (OSError,ValueError,KeyError) as exc:network={'status':'unreachable','url':COOKBOOK_URL,'reason':str(exc)}
    add('official-cookbook',network['status']=='ready',network,'Run doctor --online in the selected container and verify GitHub connectivity; no knowledge mirror fallback is used')
    return {'status':'pass' if all(r['status']=='ready' for r in rows) else 'incomplete','components':rows,
            'knowledge_installation':'manual-only','container_hint':'Run installation, checks and offline simulations in the same selected container. GPU devices/DTK and real model serving require their own deployment checks.',
            'hardware_validated':False}


def fetch_simtools(destination):
    target=Path(destination).expanduser().absolute()
    if target.exists():raise FlowError('Destination exists; inspect it instead of overwriting it')
    target.parent.mkdir(parents=True,exist_ok=True)
    command=['git','clone','--depth','1',SIMTOOLS_URL,str(target)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=180,env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
    if result.returncode:
        return {'status':'incomplete','source':SIMTOOLS_URL,'destination':str(target),'stderr':result.stderr[-2000:],
                'next':'Check source access and any partial destination before retry; do not remove existing user files automatically'}
    commit=subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
    wheels=[str(p) for p in target.rglob('dcusim-*.whl')]
    return {'status':'complete','source':SIMTOOLS_URL,'revision':commit,'destination':str(target),'wheels':wheels,
            'next':'Select a compatible CPython 3.10/Linux wheel and explicitly run scripts/setup_simulation.py; knowledge remains manually installed'}
