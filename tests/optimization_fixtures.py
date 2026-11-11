"""Synthetic records for protocol tests; never real model accuracy/Prof claims."""
import json
import uuid
from hcu_infra_agent.core import fingerprint
from hcu_infra_agent import profiling
from hcu_infra_agent.evidence import retain


def samples():
    result = []
    for group, (name, tokens, concurrency) in enumerate([
        ('short-single', 32, 1), ('long-single', 2048, 1),
        ('short-concurrent', 32, 2), ('long-concurrent', 2048, 2),
    ]):
        for index in range(concurrency):
            sid = f'{name}-{index}'
            result.append({'id': sid, 'text': 'fixed output ' + sid,
                           'input_sha256': fingerprint({'fixture': sid}),
                           'input_tokens': tokens, 'concurrency': concurrency, 'run_id': name,
                           'started_at': 100 + group * 10 + index * .1,
                           'finished_at': 102 + group * 10 + index * .1})
    return result


def after_profile(store, snapshot, name=None, ranks=(0,)):
    name = name or uuid.uuid4().hex
    traces = []
    for rank in ranks:
        path = store.root/'fixture-profiles'/(name + '-' + str(rank) + '.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'rank': rank, 'traceEvents': [
            {'ph': 'X', 'cat': 'kernel', 'name': 'candidate-' + name, 'ts': 1, 'dur': 7}]}))
        traces.append({'rank': rank, 'path': str(path), 'window': {'start_us': 0, 'end_us': 10}})
    result = profiling.analyze(store, 't', {
        'traces': traces, 'groups': [{'domain': 'tp', 'ranks': list(ranks)}], 'candidate_snapshot': snapshot})
    task = store.task('t')
    capture = retain(store, {'context': task['context'], 'context_epoch': task['context_epoch'],
                            'candidate_snapshot': snapshot, 'analysis': result['analysis'],
                            'status': 'complete', 'hardware_executed': True, 'executed': len(ranks),
                            'candidate_path_exercised': True,
                            'evidence': [row['source']['sha256'] for row in result['report']['ranks']]})
    return {'candidate_analysis': result['analysis'], 'candidate_capture': capture}
