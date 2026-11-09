"""CLI entry points for the five inference analysis and research modules."""
from .core import Store, read_json, write_json

COMMANDS = {'doctor','component-fetch','prof-analyze','optimization-plan','optimization-check','simulate','cookbook-search','cookbook-read','knowledge-read','knowledge-query'}


def configure(subs):
    for name in sorted(COMMANDS):
        p = subs.add_parser(name)
        if name == 'doctor':
            p.add_argument('config');p.add_argument('--online',action='store_true')
        elif name == 'component-fetch':
            p.add_argument('component',choices=['simtools']);p.add_argument('destination')
        elif name in {'prof-analyze','optimization-plan','optimization-check'}:
            p.add_argument('task'); p.add_argument('request')
        elif name == 'simulate':
            p.add_argument('bindings'); p.add_argument('request')
        else:
            p.add_argument('bindings')
            p.add_argument('path' if name.endswith('-read') else 'query')
            if name.endswith('-read'):
                p.add_argument('--revision');p.add_argument('--start',type=int,default=1);p.add_argument('--lines',type=int,default=80)
            else:
                p.add_argument('--limit',type=int,default=5)
                if name == 'knowledge-query':
                    p.add_argument('--scope',choices=['curated','all'],default='curated')
                    p.add_argument('--timeout',type=int,default=45)
        p.add_argument('--output')


def dispatch(a):
    from . import references, bindings
    c = a.command
    if c == 'doctor':
        from .installation import doctor
        result=doctor(read_json(a.config),a.online)
    elif c == 'component-fetch':
        from .installation import fetch_simtools
        result=fetch_simtools(a.destination)
    elif c in {'cookbook-search','knowledge-query','cookbook-read','knowledge-read'}:
        record = read_json(a.bindings)
        kind = 'cookbook' if c.startswith('cookbook') else 'knowledge'
        if getattr(a,'revision',None):record={**record,'cookbook_revision':a.revision}
        if c.endswith('-read'):result = references.read(record,kind,a.path,a.start,a.lines)
        else:result = references.search(record,kind,a.query,a.limit,getattr(a,'scope','all'),getattr(a,'timeout',45))
    else:
        s = Store(a.workspace)
        request = read_json(a.request)
        if c == 'prof-analyze':
            from .profiling import analyze
            result = analyze(s,a.task,request)
        elif c == 'simulate':
            from .simulation import simulate
            result = simulate(s,read_json(a.bindings),request)
        else:
            from . import optimization
            result = (optimization.plan if c == 'optimization-plan' else optimization.evaluate)(s,a.task,request)
    if a.output:write_json(a.output,result)
    return result
