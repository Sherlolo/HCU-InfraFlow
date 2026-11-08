"""Scoped, read-only Cookbook and knowledge retrieval with exact page citations."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from .core import FlowError


def scope(record, kind):
    from .bindings import verify
    verify(record)
    if kind == 'cookbook':
        if not record.get('cookbook_root'):
            raise FlowError('No Cookbook root bound; set cookbook_root to a checked-out source or explicit knowledge mirror')
        return Path(record['cookbook_root']).resolve(strict=True)
    return Path(record['roots']['knowledge_root']).resolve(strict=True) / 'knowledge'


def read(record, kind, relative, start=1, count=80):
    root = scope(record, kind)
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or path.suffix.lower() not in {'.md','.mdx','.rst','.txt','.json','.yaml','.yml','.sh','.py'}:
        raise FlowError('Read only supported text pages inside the bound root')
    if type(start) is not int or type(count) is not int or start < 1 or not 1 <= count <= 500:
        raise FlowError('Use start>=1 and 1..500 lines')
    data = path.read_bytes()
    if len(data) > 2*1024*1024: raise FlowError('Page exceeds the 2 MiB text limit')
    lines = data.decode('utf-8').splitlines()
    selected = [{'line': n, 'text': line} for n,line in enumerate(lines,1) if start <= n < start+count]
    return {'status': 'complete', 'kind': kind, 'path': str(path), 'relative_path': str(path.relative_to(root)),
            'sha256': hashlib.sha256(data).hexdigest(), 'total_lines': len(lines), 'lines': selected,
            'source_kind': record.get('cookbook_source_kind') if kind == 'cookbook' else 'knowledge-checkout',
            'execution': 'none; examples are reference text, not validated launch commands'}


def search(record, kind, query, limit=5, search_scope="curated", timeout=45):
    root = scope(record, kind)
    if search_scope not in {'curated','all'} or type(timeout) is not int or not 1 <= timeout <= 300:
        raise FlowError('Use scope curated/all and timeout 1..300 seconds')
    terms = list(dict.fromkeys(t.casefold() for t in re.findall(r'[\w.-]+', query) if len(t)>1))
    if not terms or type(limit) is not int or not 1 <= limit <= 50:
        raise FlowError('Provide searchable terms and limit 1..50')
    # One bounded git grep replaces per-page remote filesystem scans. It searches tracked content only.
    checkout = next((p for p in (root,*root.parents) if (p/'.git').exists()),None)
    if checkout is None: raise FlowError('Reference search requires a Git checkout')
    # The user explicitly bound this checkout. Trust that exact directory for container UID differences.
    git = ['git','-c','safe.directory='+str(checkout),'-C',str(checkout)]
    prefix = root.relative_to(checkout).as_posix()
    command = [*git,'-c','core.quotePath=false','grep','--threads=1','-n','-I','-i','-F']
    for term in terms: command += ['-e',term]
    base = prefix.rstrip('/')+'/' if prefix != '.' else ''
    if kind == 'knowledge' and search_scope == 'curated':
        paths = [':(glob)'+base+'**/local/'+section+'/**/*.md' for section in ('tutorials','topics','cases','overview')]
        paths += [':(glob)'+base+'**/concepts/**/*.md']
        coverage = 'Curated tracked local tutorials/topics/cases/overview and concepts only; use --scope all for raw/upstream pages'
    else:
        paths = [base+'*.md',base+'*.mdx',base+'*.yaml']
        coverage = 'Tracked Markdown/MDX/YAML in selected scope; local working bytes, no online freshness or full corpus claim'
    command += ['--',*paths]
    try: found = subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'status':'incomplete','reason':'reference-search-timeout','hits':[],'coverage':coverage}
    if found.returncode not in (0,1):
        raise FlowError('Reference search failed: '+found.stderr[:1000])
    patterns = [re.compile(r'(?<![a-z0-9])'+re.escape(t)+r'(?![a-z0-9])',re.I) for t in terms]
    hits = {}
    for row in found.stdout.splitlines():
        match = re.match(r'^(.*?):(\d+):(.*)$',row)
        if not match: continue
        relative, lineno, text = match.groups()
        if re.match(r'^\s*(?:-\s*)?(?:sha256|revision|digest|id|commit)\s*:',text,re.I):continue
        score = sum(bool(p.search(text)) for p in patterns)
        if not score: continue
        path = (checkout/relative).resolve()
        if not path.is_relative_to(root):continue
        page = hits.setdefault(str(path),{'relative_path':str(path.relative_to(root)),'score':0,'lines':[]})
        page['score'] += score
        if len(page['lines']) < 4:
            page['lines'].append({'line':int(lineno),'text':text[:800]})
    selected = sorted(hits.items(),key=lambda item:(-item[1]['score'],item[0]))[:limit]
    output = []
    for path,page in selected:
        data = Path(path).read_bytes()
        output.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),**page})
    revision_result = subprocess.run([*git,'rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
    revision = revision_result.stdout.strip() if revision_result.returncode == 0 else None
    return {'status':'partial','kind':kind,'query':query,'hits':output,'root':str(root),'revision':revision,
            'source_kind':record.get('cookbook_source_kind') if kind=='cookbook' else 'knowledge-checkout',
            'coverage':coverage, 'search_scope':search_scope if kind == 'knowledge' else 'bound-cookbook',
            'next':'Read matching pages, verify version/hardware/quantization/parallelism, then validate flags in the actual engine.'}
