"""Read the user-selected official Cookbook over HTTPS at a pinned commit."""
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import PurePosixPath
from .core import FlowError

REPO = 'HYGON-AI/inference-cookbook-das'
URL = 'https://github.com/'+REPO


def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'hcu-infra-agent','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:
        return response.read()


def revision(ref='main'):
    return json.loads(fetch('https://api.github.com/repos/'+REPO+'/commits/'+urllib.parse.quote(ref,safe='')))['sha']


def page(path, commit):
    if not re.fullmatch(r'[0-9a-f]{40}',commit):raise FlowError('Cookbook revision must be a commit SHA')
    p=PurePosixPath(path)
    if p.is_absolute() or '..' in p.parts or p.suffix.lower() not in {'.md','.mdx'}:
        raise FlowError('Use a relative Cookbook Markdown path')
    raw=fetch('https://raw.githubusercontent.com/'+REPO+'/'+commit+'/'+urllib.parse.quote(str(p)))
    return raw.decode('utf-8'),hashlib.sha256(raw).hexdigest()


def search(query,limit=5):
    terms=[re.sub(r'[^\w]','',t).casefold() for t in query.split()]
    terms=[t for t in terms if t]
    if not terms or type(limit) is not int or not 1<=limit<=50:raise FlowError('Provide a query and limit 1..50')
    commit=revision()
    tree=json.loads(fetch('https://api.github.com/repos/'+REPO+'/git/trees/'+commit+'?recursive=1'))
    if tree.get('truncated'):raise FlowError('Cookbook file listing is truncated')
    candidates=[]
    for entry in tree['tree']:
        path=entry['path']
        if not path.endswith(('.md','.mdx')):continue
        normalized=re.sub(r'[^\w]','',path).casefold()
        score=sum(t in normalized for t in terms if t)
        if score:candidates.append((score,path))
    hits=[]
    for score,path in sorted(candidates,key=lambda x:(-x[0],x[1]))[:limit]:
        text,sha=page(path,commit)
        lines=[{'line':n,'text':line[:800]} for n,line in enumerate(text.splitlines(),1)
               if any(t in re.sub(r'[^\w]','',line).casefold() for t in terms if t)][:4]
        hits.append({'relative_path':path,'url':URL+'/blob/'+commit+'/'+urllib.parse.quote(path),
                     'sha256':sha,'score':score,'lines':lines})
    return {'status':'partial','kind':'cookbook','source':URL,'revision':commit,'hits':hits,
            'coverage':'Official repository Markdown paths matched against query; selected bodies fetched at the pinned commit, not exhaustive semantic search'}


def read(path,start=1,count=80,commit=None):
    if start<1 or not 1<=count<=500:raise FlowError('Use start>=1 and 1..500 lines')
    commit=commit or revision()
    text,sha=page(path,commit)
    lines=text.splitlines();url=URL+'/blob/'+commit+'/'+urllib.parse.quote(path)
    links=[]
    for label,target in re.findall(r'\[([^\]]*)\]\(([^\s)]+)\)',text):
        links.append({'label':label,'url':urllib.parse.urljoin(url,target)})
    return {'status':'complete','kind':'cookbook','source':URL,'revision':commit,'relative_path':path,
            'url':url,'sha256':sha,'total_lines':len(lines),
            'lines':[{'line':n,'text':line} for n,line in enumerate(lines,1) if start<=n<start+count],
            'links':links,'execution':'Reference text only; verify container and engine version before running commands'}
