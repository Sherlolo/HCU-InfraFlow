"""Evidence-linked optimization plans and repeatable quality/performance evaluation."""
import json
from .core import FlowError
from . import quality, quality_coverage, optimization_output
from .evidence import current_analysis, retain, candidate_profile


def require_scope(task):
    if task['spec']['mode'] not in {'optimize', 'full'} or task['state'] in {'completed', 'cancelled', 'paused', 'blocked', 'failed'}:
        raise FlowError('Use an active optimize/full task for optimization work')


def report(store, tid, request=None):
    if request:
        raise FlowError('optimization-report takes no request fields')
    return optimization_output.report_plans(store, store.task(tid))


def plan(store, tid, request):
    task = store.task(tid)
    require_scope(task)
    required = {'analysis', 'observation', 'hypothesis', 'target', 'validation'}
    if required - request.keys() or any(not isinstance(request[k], str) or not request[k].strip() for k in required - {'validation'}):
        raise FlowError('Plan needs analysis, observation, hypothesis, target and validation checks')
    if set(request) - (required | {'references', 'allowed_paths', 'stopping_condition'}):
        raise FlowError('Unknown optimization plan fields')
    checks = request['validation']
    if not isinstance(checks, list) or not checks or any(not isinstance(x, str) or not x.strip() for x in checks):
        raise FlowError('Plan validation must list concrete nonempty checks')
    current_analysis(store, task, request['analysis'])
    references = request.get('references', [])
    if not isinstance(references, list):
        raise FlowError('References must be retained artifact IDs')
    for sha in references:
        store.artifact(sha)
    value = {'task': tid, 'context': task['context'], **request, 'status': 'planned',
             'execution_started': False, 'profile_evidence': {'artifact': request['analysis'],
             'observation': request['observation'], 'hypothesis': request['hypothesis'], 'target': request['target']},
             'next': 'Agent inspects existing engine/source paths, runs authorized isolated experiments, retains quality/performance inputs, then submits for independent flow review.'}
    artifact = retain(store, value)
    output = optimization_output.publish_plan(store, task, artifact, value)
    return {'status': 'complete', 'plan': artifact, 'record': value, **output}


def evaluate(store, tid, request):
    task = store.task(tid)
    require_scope(task)
    record = json.loads(store.artifact(request['plan']))
    if record.get('task') != tid or record.get('context') != task['context']:
        raise FlowError('Optimization plan belongs to another task/context')
    current_analysis(store, task, record['analysis'])
    inputs = {kind: json.loads(store.artifact(request[kind])) for kind in ('quality_inputs','performance_inputs')}
    quality_coverage.require(inputs['quality_inputs']['contract'])
    for pair in inputs.values():
        for side in ('baseline', 'candidate'):
            measurement = pair[side]
            if measurement.get('hardware_executed') is not True or measurement.get('synthetic'):
                raise FlowError('Optimization needs explicit hardware-executed measurements')
    q = quality.compare_outputs(**inputs['quality_inputs'])
    p = quality.compare_performance(**inputs['performance_inputs'])
    snapshots = {value['candidate'].get('candidate_snapshot') for value in inputs.values()}
    if len(snapshots) != 1 or None in snapshots:
        raise FlowError('Quality and performance must describe the same candidate snapshot')
    snapshot = snapshots.pop()
    store.artifact(snapshot)
    if any(value['contract'].get('context') != task['context'] for value in inputs.values()):
        raise FlowError('Comparison inputs belong to another task context')
    qrecord, precord = inputs['quality_inputs']['contract'], inputs['performance_inputs']['contract']
    if qrecord['identities'] != precord['identities'] or qrecord['identities']['workload'] != precord['workload']:
        raise FlowError('Quality/performance workload or model identity mismatch')
    after = {'status': 'not-collected'}
    if request.get('candidate_analysis') or request.get('candidate_capture'):
        if not request.get('candidate_analysis') or not request.get('candidate_capture'):
            raise FlowError('Provide both candidate_analysis and candidate_capture')
        after = candidate_profile(store, task, request['candidate_analysis'], request['candidate_capture'],
                                  snapshot, record['analysis'])
    changes = request.get('changes', [])
    if (not isinstance(changes, list)
            or any(not isinstance(x, dict) or not all(isinstance(x.get(k), str) and x[k].strip()
                                                     for k in ('path', 'description')) for x in changes)):
        raise FlowError('Changes must record path and description')
    reports = {}
    # Compute both comparisons before publishing either PASS.
    status = 'pass' if q['status'] == p['status'] == 'pass' else 'fail'
    if status == 'pass' and (after['status'] != 'complete' or not changes):
        status = 'incomplete'
    for kind, field in [('inference-quality','quality_inputs'), ('performance','performance_inputs')]:
        comparison = q if kind == 'inference-quality' else p
        body = {'context': task['context'], 'candidate_snapshot': snapshot, 'status': status,
                'executed': comparison['executed'], 'failures': [] if status == 'pass' else ['candidate-evaluation-' + status],
                'assessment': comparison, field: request[field], 'candidate_profile': after,
                'evidence': [request[field], request['plan'], *([after['analysis'], after['capture']] if after['status'] == 'complete' else [])]}
        reports[kind] = store.report(tid, kind, body)['artifact']
    result = {'status': status, 'task': tid, 'plan': request['plan'], 'candidate_snapshot': snapshot,
              'quality': q, 'performance': p, 'candidate_profile': after, 'changes': changes,
              'reports': reports, 'accepted_by_flow': False,
              'next': 'Submit the candidate and iteration experiment through flow-submit; independent review and flow-advance remain required.'}
    if status == 'incomplete':
        result['next'] = 'Retain implementation changes and the evaluated candidate Prof before review.'
    elif status == 'fail':
        result['next'] = 'Repair or reject this candidate; failed accuracy/performance cannot be accepted.'
    output = optimization_output.publish_plan(store, task, request['plan'], {
        **record, **result, 'snapshot': snapshot, 'quality_inputs': request['quality_inputs'],
        'performance_inputs': request['performance_inputs'], 'direction': record['hypothesis']})
    return {**result, 'artifact': retain(store, result), **output}
