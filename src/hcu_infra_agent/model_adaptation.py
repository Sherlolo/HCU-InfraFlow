"""Release-locked model adaptation and executable, candidate-bound validation."""
import json

from .core import FlowError, safe_id, valid_pass
from .evidence import retain
from . import quality


LOCK_FIELDS = ('model', 'config', 'weights', 'tokenizer', 'engine', 'dependencies',
               'image', 'driver', 'quantization', 'workload')
CAPABILITIES = ('config', 'checkpoint', 'tokenizer', 'attention', 'kv-cache',
                'quantization', 'parallelism', 'serving')
BASE_TESTS = ('load', 'checkpoint', 'tokenizer', 'attention', 'kv-cache',
              'quantization', 'topology', 'protocol', 'dispatch', 'fallback')


def _task(store, tid):
    task = store.task(tid)
    if task['spec']['mode'] not in {'adapt', 'full', 'optimize'} or task['state'] in {
            'completed', 'cancelled', 'paused', 'blocked', 'failed'}:
        raise FlowError('Model adaptation requires an active adapt/full/optimize task')
    return task


def _refs(store, values):
    if not isinstance(values, list) or not values:
        raise FlowError('Retain nonempty raw evidence references')
    for value in values:
        if not isinstance(value, str):
            raise FlowError('Evidence references must be artifact IDs')
        store.artifact(value)


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise FlowError(name + ' must be nonempty text')


def plan(store, tid, request):
    """Freeze sources and capability gaps without claiming model support."""
    task = _task(store, tid)
    if set(request) - {'framework', 'release_lock', 'gaps', 'required_features', 'risk_pairs', 'failure'}:
        raise FlowError('Unknown model adaptation plan fields')
    if request.get('framework') not in {'sglang', 'vllm'}:
        raise FlowError('Select sglang or vllm and inspect that pinned implementation')
    lock = request.get('release_lock')
    if not isinstance(lock, dict) or set(lock) != set(LOCK_FIELDS):
        raise FlowError('Release lock requires immutable artifact IDs for ' + ', '.join(LOCK_FIELDS))
    _refs(store, list(lock.values()))
    gaps = request.get('gaps')
    if not isinstance(gaps, list) or not gaps:
        raise FlowError('An architecture gap map is required')
    ids, covered = set(), set()
    handoffs = []
    for gap in gaps:
        if not isinstance(gap, dict) or set(gap) - {'id', 'capability', 'status', 'required', 'target', 'contract', 'fallback', 'kind', 'operator_backend'}:
            raise FlowError('Unknown architecture gap fields')
        gid = safe_id(gap.get('id'))
        if gid in ids:
            raise FlowError('Duplicate architecture gap ID')
        ids.add(gid)
        if gap.get('capability') not in CAPABILITIES:
            raise FlowError('Unknown capability family')
        covered.add(gap['capability'])
        if gap.get('status') not in {'supported', 'missing', 'not-applicable'} or type(gap.get('required')) is not bool:
            raise FlowError('Each gap needs status and explicit required flag')
        if gap['required'] and gap['status'] == 'not-applicable':
            raise FlowError('Required capabilities cannot be marked not-applicable')
        for name in ('target', 'contract', 'fallback'):
            _text(gap.get(name), name)
        if gap.get('kind') not in {'kernel', 'framework'}:
            raise FlowError('Gap kind must be kernel or framework')
        if gap['kind'] == 'kernel' and gap['status'] == 'missing':
            if gap.get('operator_backend') not in {'triton', 'hip'}:
                raise FlowError('Missing kernels need a triton or hip implementation route')
            handoffs.append({'gap_id': gid, 'skill': 'hcu-infer-operator-develop',
                             'backend': gap['operator_backend'], 'target': gap['target'],
                             'contract': gap['contract'], 'fallback': gap['fallback'],
                             'source': 'https://github.com/Sherlolo/hcu-infer-pilot',
                             'reason': 'adaptation-required; no performance claim'})
    if covered != set(CAPABILITIES):
        raise FlowError('Gap map must cover every capability family: ' + ', '.join(sorted(set(CAPABILITIES) - covered)))
    features = request.get('required_features')
    if not isinstance(features, list) or not features or any(not isinstance(x, str) or not x.strip() for x in features):
        raise FlowError('Name the required serving features')
    if len(set(features)) != len(features):
        raise FlowError('Required serving features must be unique')
    risks = request.get('risk_pairs', [])
    if not isinstance(risks, list) or any(not isinstance(x, str) or not x.strip() for x in risks):
        raise FlowError('Risk pairs must be a list of concrete test names')
    if len(set(risks)) != len(risks):
        raise FlowError('Risk pair tests must be unique')
    evidence = list(lock.values())
    if 'failure' in request:
        _refs(store, [request['failure']]); evidence.append(request['failure'])
    value = {'module': 'model-adaptation-plan', 'task': tid, 'context': task['context'],
             'context_epoch': task['context_epoch'], **request, 'status': 'planned',
             'required_tests': list(BASE_TESTS) + ['feature:' + x for x in features] + ['risk:' + x for x in risks],
             'operator_handoffs': handoffs, 'evidence': evidence, 'execution_started': False}
    artifact = retain(store, value)
    with store.db() as db:
        store.event(db, tid, 'adaptation-plan-recorded', {'artifact': artifact, 'context': task['context'],
                                                        'context_epoch': task['context_epoch']})
    return {'status': 'complete', 'plan': artifact, 'record': value}


def _load_plan(store, task, artifact):
    value = json.loads(store.artifact(artifact))
    if (value.get('module') != 'model-adaptation-plan' or value.get('task') != task['id']
            or value.get('context') != task['context'] or value.get('context_epoch') != task['context_epoch']):
        raise FlowError('Adaptation plan belongs to another task/context epoch')
    with store.db() as db:
        latest = db.execute("SELECT payload FROM events WHERE task=? AND kind='adaptation-plan-recorded' ORDER BY seq DESC LIMIT 1", (task['id'],)).fetchone()
    if not latest or json.loads(latest['payload'])['artifact'] != artifact:
        raise FlowError('Adaptation plan has been replaced')
    return value


def run(store, tid, request):
    """Run reviewed implementation/validation command through existing lease guards."""
    from .execution import run_command
    task = _task(store, tid)
    if set(request) != {'plan', 'candidate_snapshot', 'tests', 'operation', 'card', 'lease'}:
        raise FlowError('Adaptation run needs plan, candidate_snapshot, tests, operation, card and lease')
    value = _load_plan(store, task, request['plan'])
    _refs(store, [request['candidate_snapshot']])
    tests = request['tests']
    if not isinstance(tests, list) or not tests or any(x not in value['required_tests'] for x in tests):
        raise FlowError('Run must name tests from the adaptation plan')
    # Persist the association before execution so a crash cannot orphan its scope.
    receipt = {k: request[k] for k in ('plan', 'candidate_snapshot', 'tests', 'operation')}
    receipt.update(context=task['context'], context_epoch=task['context_epoch'])
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute("SELECT payload FROM events WHERE kind='adaptation-run-bound' AND json_extract(payload,'$.operation')=? ORDER BY seq DESC LIMIT 1", (request['operation'],)).fetchone()
        if prior and json.loads(prior['payload']) != receipt:
            raise FlowError('Operation already bound to another adaptation candidate/test set')
        if not prior:
            if db.execute('SELECT 1 FROM operations WHERE id=?', (request['operation'],)).fetchone():
                raise FlowError('Existing unbound operation cannot become adaptation validation')
            store.event(db, tid, 'adaptation-run-bound', receipt)
    execution = run_command(store, tid, request['operation'], request['card'], request['lease'],
                            expected_context=task['context'], expected_context_epoch=task['context_epoch'])
    result = {**receipt, 'execution': execution, 'status': execution['status'],
              'validation': 'Test assertions and output comparison remain required; exit zero is not model validation.'}
    return {**result, 'artifact': retain(store, result)}


def evaluate(store, tid, request):
    """Check declared support only after actual candidate-bound test commands."""
    task = _task(store, tid)
    if set(request) != {'plan', 'candidate_snapshot', 'test_results', 'quality_inputs', 'gap_resolutions'}:
        raise FlowError('Adaptation check needs plan, candidate_snapshot, test_results, quality_inputs and gap_resolutions')
    value = _load_plan(store, task, request['plan'])
    snapshot = request['candidate_snapshot']
    _refs(store, [snapshot, request['quality_inputs']])
    _refs(store, request['test_results'])
    inputs = json.loads(store.artifact(request['quality_inputs']))
    for record in (inputs.get('baseline', {}), inputs.get('candidate', {})):
        if (record.get('synthetic') is True or record.get('hardware_executed') is False
                or record.get('qualification') == 'simulation-prediction'):
            raise FlowError('Synthetic or predicted outputs cannot qualify model adaptation')
    assessment = quality.compare_outputs(**inputs)
    expected_ids = {name: value['release_lock']['weights' if name == 'model' else name] for name in quality.IDENTITIES}
    if inputs['contract']['context'] != task['context'] or inputs['contract']['identities'] != expected_ids:
        raise FlowError('Quality identities must match the release lock and current context')
    if set(inputs['contract']['required_features']) != set(value['required_features']):
        raise FlowError('Quality comparison must cover the planned serving features')
    if inputs['candidate'].get('candidate_snapshot') != snapshot:
        raise FlowError('Quality candidate snapshot mismatch')
    for record in (inputs['baseline'], inputs['candidate']):
        _refs(store, record['evidence'])
    failures, seen = list(assessment['failures']), set()
    for sha in request['test_results']:
        record = json.loads(store.artifact(sha))
        name = record.get('name')
        if not isinstance(name, str) or name not in value['required_tests'] or name in seen:
            raise FlowError('Unknown or duplicate adaptation test result')
        seen.add(name)
        if (record.get('context') != task['context'] or record.get('candidate_snapshot') != snapshot):
            raise FlowError('Test result belongs to another candidate/context')
        _refs(store, record.get('evidence'))
        with store.db() as db:
            op = db.execute('SELECT * FROM operations WHERE id=? AND task=?', (record.get('operation'), tid)).fetchone()
            bound = db.execute("SELECT payload FROM events WHERE task=? AND kind='adaptation-run-bound' AND json_extract(payload,'$.operation')=? ORDER BY seq DESC LIMIT 1", (tid, record.get('operation'))).fetchone()
        if not op or not bound:
            raise FlowError('Test needs an executed model-adapt-run operation')
        binding = json.loads(bound['payload'])
        if (binding['plan'] != request['plan'] or binding['candidate_snapshot'] != snapshot
                or name not in binding['tests'] or binding['context_epoch'] != task['context_epoch']):
            raise FlowError('Test execution binding does not match current adaptation')
        executed = json.loads(op['result'] or '{}')
        if op['status'] != 'complete' or executed.get('returncode') != 0 or executed.get('timed_out'):
            failures.append(name + ':execution-not-complete')
        if executed.get('context') != task['context'] or executed.get('context_epoch') != task['context_epoch']:
            raise FlowError('Test execution belongs to another context epoch')
        _refs(store, executed.get('evidence'))
        if not set(executed['evidence']).issubset(record['evidence']):
            raise FlowError('Test assertions must retain their actual operation logs and command plan')
        if record.get('status') != 'pass' or not valid_pass(record) or record.get('candidate_path_exercised') is not True:
            failures.append(name + ':assertions-not-passed')
    failures.extend('missing-test:' + name for name in value['required_tests'] if name not in seen)
    resolutions = request['gap_resolutions']
    if not isinstance(resolutions, dict) or set(resolutions) - {g['id'] for g in value['gaps']}:
        raise FlowError('Gap resolutions must map declared gap IDs to evidence artifacts')
    for gap in value['gaps']:
        if gap['required'] and gap['status'] == 'missing':
            if gap['id'] not in resolutions:
                failures.append('unresolved-gap:' + gap['id'])
            else:
                _refs(store, [resolutions[gap['id']]])
                resolution = json.loads(store.artifact(resolutions[gap['id']]))
                if (resolution.get('candidate_snapshot') != snapshot or resolution.get('context') != task['context']
                        or resolution.get('status') != 'pass' or resolution.get('gap_id') != gap['id']
                        or not valid_pass(resolution) or resolution.get('candidate_path_exercised') is not True):
                    failures.append('invalid-gap-resolution:' + gap['id'])
                _refs(store, resolution.get('evidence'))
                if gap['kind'] == 'kernel':
                    _kernel_resolution(store, task, request['plan'], gap, snapshot, resolution)
    status = 'fail' if failures else 'pass'
    report = {'module': 'model-adaptation', 'task': tid, 'context': task['context'],
              'context_epoch': task['context_epoch'], 'candidate_snapshot': snapshot, 'plan': request['plan'],
              'status': status, 'executed': len(seen), 'failures': failures,
              'evidence': [request['plan'], snapshot, request['quality_inputs'], *request['test_results'], *resolutions.values()],
              'quality': assessment, 'ready_for_baseline': status == 'pass', 'accepted_by_flow': False,
              'next': 'Establish a fresh profiler-off baseline; independent flow review is still required.',
              'limits': 'Only declared test assertions and retained execution evidence; no performance or release claim.'}
    # Reject supersession during evidence inspection, in addition to the Store's
    # atomic context-epoch guard. Coordinators serialize coupled plan updates.
    _load_plan(store, _task(store, tid), request['plan'])
    result = store.report(tid, 'model-adaptation', report)
    return {'status': status, 'artifact': result['artifact'], 'report': report}


def _kernel_resolution(store, task, plan_id, gap, snapshot, resolution):
    """Require the operator integration and its actual verification operation."""
    from .operators import _verification
    artifact = resolution.get('operator_integration')
    if artifact not in resolution['evidence']:
        raise FlowError('Missing kernel resolution needs retained operator_integration evidence')
    integration = json.loads(store.artifact(artifact))
    if (integration.get('kind') != 'operator-integration' or integration.get('task') != task['id']
            or integration.get('context') != task['context'] or integration.get('context_epoch') != task['context_epoch']
            or integration.get('candidate_snapshot') != snapshot or integration.get('status') != 'complete'
            or integration.get('integration_verified') is not True):
        raise FlowError('Kernel resolution requires current candidate integration verification')
    operator_plan = json.loads(store.artifact(integration['plan']))
    if operator_plan.get('adaptation_plan') != plan_id or operator_plan.get('gap_id') != gap['id']:
        raise FlowError('Operator integration belongs to another adaptation gap')
    for stage in ('apply', 'verify'):
        execution = integration.get('executions', {}).get(stage, {})
        with store.db() as db:
            row = db.execute('SELECT * FROM operations WHERE id=? AND task=?',
                             (execution.get('operation'), task['id'])).fetchone()
        if not row or row['status'] != 'complete' or json.loads(row['result']) != execution:
            raise FlowError('Kernel integration needs actual completed apply/verify operations')
    verified, _, _ = _verification(store, integration['executions']['verify'], integration, task)
    if not verified:
        raise FlowError('Kernel integration dispatcher verification did not pass')
