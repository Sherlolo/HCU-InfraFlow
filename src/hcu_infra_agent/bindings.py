"""Explicit read-only bindings to inference skills and HCU knowledge."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from .core import FlowError, fingerprint, write_json

SKILLS = {'benchmark': 'skills/llm-serving-auto-benchmark', 'profile': 'skills/llm-torch-profiler-analysis',
          'incident': 'skills/sglang-prod-incident-triage', 'loop': 'skills/sglang-sota-humanize-loop',
          'gemm': 'skills/gemm-tuning', 'moe': 'skills/hcu-aiter-moe-tuning',
          'kernel': 'skills/lightop-kernel-agent-loop', 'simulation': 'skills/model-compute-simulation',
          'blas': 'skills/hipblaslt-rocblas-tuning',
          'triton': 'skills/kernel-triton-optimize', 'hip': 'skills/kernel-hip-optimize'}
OPTIONAL_SKILLS = {'kernel', 'simulation', 'blas', 'triton', 'hip'}
PILOT_URL = 'https://github.com/Sherlolo/hcu-infer-pilot'


def bind(config, destination):
    roots = {key: Path(config[key]).resolve(strict=True) for key in ('pilot_root', 'knowledge_root')}
    items = {}; unavailable = []
    for key, relative in SKILLS.items():
        path = Path(config['kernel_skill']).resolve(strict=True) if key == 'kernel' and config.get('kernel_skill') else roots['pilot_root'] / relative / 'SKILL.md'
        if key in OPTIONAL_SKILLS and not path.is_file() and not (key == 'kernel' and config.get('kernel_skill')):
            unavailable.append({'role':key,'reason':'Optional source not populated; bind its verified local entry before use'});continue
        if not path.is_file(): raise FlowError('Required inference skill missing: ' + str(path))
        items[key] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    kb = roots['knowledge_root'] / 'kb.py'
    if not kb.is_file(): raise FlowError('Knowledge root must contain kb.py')
    items['knowledge'] = {'path': str(kb), 'sha256': hashlib.sha256(kb.read_bytes()).hexdigest()}
    record = {'schema_version': 1, 'roots': {k: str(v) for k,v in roots.items()}, 'items': items,
              'knowledge_python': config.get('knowledge_python', sys.executable), 'unavailable': unavailable, 'source_mutations': False}
    if config.get('simulation_python'):
        python = Path(config['simulation_python']).expanduser().absolute()
        if not python.is_file(): raise FlowError('simulation_python does not exist')
        record['simulation_python'] = str(python)
    if config.get('simulation_wheel'):
        wheel = Path(config['simulation_wheel']).resolve(strict=True)
        record['items']['simulation_wheel'] = {'path':str(wheel), 'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest()}
    record['identity'] = fingerprint(record)
    write_json(destination, record)
    return record


def verify(record):
    body = {k: v for k,v in record.items() if k != 'identity'}
    if fingerprint(body) != record.get('identity'): raise FlowError('Bindings identity mismatch')
    for name, item in record['items'].items():
        path = Path(item['path'])
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise FlowError('Bound source changed: ' + name)
    return {'status': 'pass', 'checked': len(record['items']), 'identity': record['identity'], 'unavailable': record.get('unavailable', [])}


def search(record, query, limit=5):
    verify(record)
    if not query.strip() or not 1 <= limit <= 50: raise FlowError('Nonempty query and limit 1..50 required')
    root = record['roots']['knowledge_root']
    command = [record['knowledge_python'], str(Path(root)/'kb.py'), '--root', root, 'search', query, '--mode', 'local', '--limit', str(limit)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return {'status': 'incomplete', 'reason': 'native-knowledge-search-timeout', 'command': command}
    if result.returncode:
        return {'status': 'incomplete', 'reason': 'native-knowledge-search-failed', 'exit_code': result.returncode, 'stderr': result.stderr[-1000:], 'stdout': result.stdout[-2000:]}
    try: output = json.loads(result.stdout)
    except json.JSONDecodeError: return {'status': 'incomplete', 'reason': 'native-knowledge-search-non-json'}
    if not isinstance(output, dict): return {'status': 'incomplete', 'reason': 'native-knowledge-search-non-object'}
    return {'status': 'complete', 'command': command, 'result': output, 'scope': 'native local knowledge search; applicability requires Agent review'}


def discover(record, query, limit=5):
    """Read tracked Markdown directly when native indexes are unavailable; explicit partial coverage."""
    import re
    verify(record)
    if not query.strip() or not 1 <= limit <= 50: raise FlowError('Nonempty query and limit 1..50 required')
    root=Path(record['roots']['knowledge_root'])
    listing=subprocess.run(['git','-C',str(root),'ls-files','knowledge'],capture_output=True,text=True,timeout=30,check=True)
    terms=[t.casefold() for t in re.findall(r'[\w.-]+',query) if len(t)>1]
    hits=[]
    for relative in listing.stdout.splitlines():
        p=root/relative
        if p.suffix!='.md' or not p.is_file() or p.stat().st_size>512*1024:continue
        text=p.read_text(encoding='utf-8',errors='replace');lines=text.splitlines();matches=[]
        for n,line in enumerate(lines,1):
            if re.match(r'^\s*(?:-\s*)?(?:sha256|id|revision|commit|digest)\s*:',line,re.I):continue
            count=sum(bool(re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',line.casefold())) for term in terms)
            if count:matches.append((count,n,line[:600]))
        if matches:
            best=sorted(matches,reverse=True)[:3]
            hits.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'score':sum(x[0] for x in best),
                         'lines':[{'line':n,'text':line} for _,n,line in best]})
    hits.sort(key=lambda x:(-x['score'],x['path']))
    return {'status':'partial','coverage':'tracked knowledge Markdown only; unindexed materials and online sources excluded',
            'hits':hits[:limit],'source_mutations':False,'limits':'Lexical discovery; Agent must read bodies and judge inference/version applicability.'}
