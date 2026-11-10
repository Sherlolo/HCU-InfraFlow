"""Evidence-linked optimization plans and repeatable quality/performance evaluation."""
import json
from .core import FlowError
from . import quality
from .evidence import current_analysis, retain


def require_scope(task):
    if task['spec']['mode'] not in {'optimize', 'full'} or task['state'] in {'completed', 'cancelled', 'paused', 'blocked', 'failed'}:
        raise FlowError('Use an active optimize/full task for optimization work')


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
    return {'status': 'complete', 'plan': artifact, 'record': value}


def evaluate(store, tid, request):
    task = store.task(tid)
    require_scope(task)
    record = json.loads(store.artifact(request['plan']))
    if record.get('task') != tid or record.get('context') != task['context']:
        raise FlowError('Optimization plan belongs to another task/context')
    current_analysis(store, task, record['analysis'])
    inputs = {kind: json.loads(store.artifact(request[kind])) for kind in ('quality_inputs','performance_inputs')}
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
    reports = {}
    # Compute both comparisons before publishing either PASS.
    status = 'pass' if q['status'] == p['status'] == 'pass' else 'fail'
    for kind, field in [('inference-quality','quality_inputs'), ('performance','performance_inputs')]:
        comparison = q if kind == 'inference-quality' else p
        body = {'context': task['context'], 'candidate_snapshot': snapshot, 'status': status,
                'executed': comparison['executed'], 'failures': [] if status == 'pass' else ['candidate-evaluation-failed'],
                'assessment': comparison, field: request[field], 'evidence': [request[field], request['plan']]}
        reports[kind] = store.report(tid, kind, body)['artifact']
    result = {'status': status, 'task': tid, 'plan': request['plan'], 'candidate_snapshot': snapshot,
              'quality': q, 'performance': p, 'reports': reports, 'accepted_by_flow': False,
              'next': 'Submit the candidate and iteration experiment through flow-submit; independent review and flow-advance remain required.'}
    return {**result, 'artifact': retain(store, result)}
