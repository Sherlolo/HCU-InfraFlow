"""Import offline rank traces into reproducible, task-scoped profiling evidence."""
import gzip
import json
import sys
import uuid
from pathlib import Path
from . import analysis, bindings
from .core import FlowError
from .evidence import pin, retain, run_tool


def analyze(store, tid, request):
    task = store.task(tid)
    traces = request.get('traces')
    if not isinstance(traces, list) or not traces:
        raise FlowError('Declare nonempty traces with path, rank and window')
    groups = request.get('groups')
    if not isinstance(groups, list) or not groups:
        raise FlowError('Declare actual process groups for rank coverage')
    seen = set()
    results = []
    raw_evidence = []
    for item in traces:
        rank = item.get('rank')
        if type(rank) is not int or rank < 0 or rank in seen:
            raise FlowError('Trace ranks must be unique nonnegative integers')
        seen.add(rank)
        source = pin(store, item['path'])
        # Analyze the exact bytes retained in Store, not a path that may change.
        payload = store.artifact(source['sha256'])
        if str(item['path']).endswith('.gz'):
            payload = gzip.decompress(payload)
        trace = json.loads(payload)
        captured = trace.get('distributedInfo', {}).get('rank', trace.get('rank')) if isinstance(trace, dict) else None
        if captured is not None and int(captured) != rank:
            raise FlowError('Trace metadata rank differs from declared rank')
        events = trace.get('traceEvents') if isinstance(trace, dict) else trace
        if not isinstance(events, list):
            raise FlowError('Expected Chrome/PyTorch traceEvents')
        for event in events:
            if isinstance(event, dict) and event.get('cat') in {'kernel','gpu_kernel','hip_kernel','cuda_kernel','communication','gpu_memcpy','gpu_memset'}:
                args = event.setdefault('args', {})
                if 'rank' in args and str(args['rank']) != str(rank):
                    raise FlowError('Event rank differs from its trace assignment')
                args['rank'] = rank
        result = analysis.analyze_trace(trace, item['window'], request.get('models'))
        if not result['ranks']:
            raise FlowError('Trace/window contains no usable GPU duration events')
        results.append({'rank': rank, 'source': source, 'analysis': result})
        raw_evidence.append(source['sha256'])
    coverage = analysis.profile_plan(groups, seen)
    if coverage['status'] != 'pass':
        raise FlowError('Missing representative ranks for declared process groups')
    tools = []
    if request.get('triage_bindings'):
        record = json.loads(Path(request['triage_bindings']).read_text())
        bindings.verify(record)
        script = Path(record['items']['profile']['path']).parent / 'scripts/run_triage_report.py'
        script_pin = pin(store, script)
        for item in traces:
            # Materialize pinned bytes in the private workspace before calling the external analyzer.
            source = next(row['source'] for row in results if row['rank'] == item['rank'])
            input_file = store.root / 'modules' / 'profile-inputs' / (source['sha256'] + ('.json.gz' if str(item['path']).endswith('.gz') else '.json'))
            input_file.parent.mkdir(parents=True, exist_ok=True)
            input_file.write_bytes(store.artifact(source['sha256']))
            output = store.root / 'modules' / 'triage-output' / (source['sha256']+'-'+uuid.uuid4().hex)
            tool = run_tool(store, 'prof', [sys.executable, script, '--work-dir', output,
                                           '--input', input_file, '--framework', request.get('framework', 'auto')], request.get('timeout', 120))
            tool['script'] = script_pin
            report = output / 'torch_profiler_analysis.md'
            if tool['status'] != 'complete' or not report.is_file():
                raise FlowError('External profiler analysis failed; inspect ' + tool['cwd'])
            tool['report'] = pin(store, report)
            tools.append(tool)
            raw_evidence.extend([tool['artifact'], tool['report']['sha256'], script_pin['sha256']])
    evidence = [*raw_evidence, retain(store, request), retain(store, results)]
    report = {'context': task['context'], 'status': 'complete', 'kind': 'offline-prof-analysis',
              'executed': len(results), 'evidence': evidence, 'ranks': results,
              'rank_coverage': coverage, 'tools': tools,
              'qualification': 'offline-trace-analysis; measurement provenance comes from the supplied capture, no new benchmark or speedup claim',
              'limits': 'Per-rank windows, no automatic cross-node clock alignment. Unknown shapes/bounds remain explicit; attribution requires Agent review.'}
    saved = store.report(tid, 'analysis', report)
    return {'status': 'complete', 'task': tid, 'analysis': saved['artifact'],
            'context': task['context'], 'rank_coverage': coverage, 'report': report}
