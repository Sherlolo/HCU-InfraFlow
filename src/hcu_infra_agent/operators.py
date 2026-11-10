"""Profile-driven operator skill dispatch and recoverable framework integration.

Runner and framework commands are site-supplied command cards, not invented
third-party CLIs. Their execution receipts are distinct from GPU acceptance.
"""
import json
from pathlib import Path

from .core import FlowError, fingerprint, read_json, safe_id, write_json
from .evidence import current_analysis, pin, retain
from .execution import command_plan, run_command
from .optimization import require_scope


SOURCE = 'https://github.com/Sherlolo/hcu-infer-pilot'
ROUTES = {
    'fusion': 'lightop-kernel-agent-loop',
    'triton': 'kernel-triton-optimize',
    'tilelang': None,  # Must be explicitly bound; no fabricated upstream skill.
    'gemm': 'gemm-tuning',
    'hip': 'kernel-hip-optimize',
}
CHECKS = ('build', 'operator_correctness', 'framework_dispatch', 'serving_smoke')


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise FlowError('Operator request fields must include: ' + ', '.join(sorted(required)))


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise FlowError(name + ' must be nonempty text')
    return value


def _task(store, tid, adaptation=False):
    task = store.task(tid)
    if adaptation:
        if task['spec']['mode'] not in {'adapt', 'full', 'optimize'} or task['state'] in {'completed', 'cancelled'}:
            raise FlowError('Missing-operator adaptation requires an active adapt/full/optimize task')
    else:
        require_scope(task)
    if task['state'] in {'paused', 'blocked', 'failed'}:
        raise FlowError('Operator task is not active')
    return task


def _load_plan(store, tid, artifact):
    record = json.loads(store.artifact(artifact))
    task = _task(store, tid, adaptation='adaptation_plan' in record)
    if (record.get('module') != 'operator-plan' or record.get('task') != tid
            or record.get('context') != task['context'] or record.get('context_epoch') != task['context_epoch']):
        raise FlowError('Operator plan belongs to another task/context epoch')
    if 'adaptation_plan' in record:
        _adaptation_gap(store, task, record)
    else:
        current_analysis(store, task, record['analysis'])
    return task, record


def _adaptation_gap(store, task, request):
    adaptation = json.loads(store.artifact(request['adaptation_plan']))
    if (adaptation.get('module') != 'model-adaptation-plan' or adaptation.get('task') != task['id']
            or adaptation.get('context') != task['context'] or adaptation.get('context_epoch') != task['context_epoch']):
        raise FlowError('Adaptation handoff belongs to another task/context')
    with store.db() as db:
        latest = db.execute("SELECT payload FROM events WHERE task=? AND kind='adaptation-plan-recorded' ORDER BY seq DESC LIMIT 1",
                            (task['id'],)).fetchone()
    if not latest or json.loads(latest['payload']).get('artifact') != request['adaptation_plan']:
        raise FlowError('Adaptation plan is stale or was not recorded')
    gap = next((g for g in adaptation.get('gaps', []) if g.get('id') == request['gap_id']), None)
    if (not gap or gap.get('kind') != 'kernel' or gap.get('status') != 'missing'
            or gap.get('operator_backend') != request['kind'] or request['kind'] not in {'triton', 'hip'}):
        raise FlowError('Adaptation handoff must select a missing Triton/HIP kernel gap')
    return gap


def plan(store, tid, request):
    """Capture a concrete profile finding and select an available specialist skill."""
    required = {'kind', 'target', 'observation', 'existing_path', 'shape_contract', 'skill_path'}
    _fields(request, required, {'analysis', 'adaptation_plan', 'gap_id', 'skill_name', 'stopping_condition'})
    adaptation = 'adaptation_plan' in request
    if adaptation == ('analysis' in request) or adaptation != ('gap_id' in request):
        raise FlowError('Choose analysis OR adaptation_plan with gap_id as the operator evidence origin')
    task = _task(store, tid, adaptation=adaptation)
    if adaptation:
        _adaptation_gap(store, task, request)
    else:
        current_analysis(store, task, request['analysis'])
    route = request['kind']
    if route not in ROUTES:
        raise FlowError('Operator kind must be fusion, triton, tilelang, gemm or hip')
    for key in ('target', 'observation', 'existing_path'):
        _text(request[key], key)
    shape = request['shape_contract']
    _fields(shape, {'shapes', 'dtype', 'layout', 'phase', 'semantics', 'tolerance'})
    if not isinstance(shape['shapes'], list) or not shape['shapes']:
        raise FlowError('Record actual shapes, not an empty benchmark workload')
    for dims in shape['shapes']:
        if not isinstance(dims, list) or not dims or any(type(n) is not int or n < 1 for n in dims):
            raise FlowError('Shapes must be nonempty positive integer dimension arrays')
    for key in ('dtype', 'layout', 'phase', 'semantics', 'tolerance'):
        _text(shape[key], key)
    default_name = 'kernel-' + route + '-baseline' if adaptation else ROUTES[route]
    name = request.get('skill_name') or default_name
    if not name:
        raise FlowError('TileLang needs an explicitly available skill_name and skill_path; no implicit Triton substitution')
    safe_id(name)
    if default_name and name != default_name:
        raise FlowError('Skill name does not match the selected operator route')
    path = Path(request['skill_path']).expanduser().resolve(strict=True)
    if path.name != 'SKILL.md':
        raise FlowError('skill_path must identify the installed SKILL.md entry')
    source_text = path.read_text(encoding='utf-8')
    if not any(line.strip() == 'name: ' + name for line in source_text.splitlines()[:30]):
        raise FlowError('Bound skill frontmatter name does not match the selected route')
    entry = pin(store, path)
    record = {'module': 'operator-plan', 'task': tid, 'context': task['context'],
              'context_epoch': task['context_epoch'], **request, 'skill_name': name,
              'skill_entry': entry, 'source': SOURCE, 'status': 'planned',
              'execution_started': False, 'hardware_validated': False}
    prompt = ('Use the installed skill ' + name + ' at ' + str(path) + '.\n'
              'Read its relevant bundled references and scripts. Treat source references as read-only.\n'
              'Develop only in the assigned private workspace. Inspect existing engine dispatch before changing it.\n'
              'Preserve exact semantics, layout, dtype, stream/graph behavior and unsupported-shape fallback.\n'
              'Return candidate source, build/registration patch, rollback, numerical and benchmark evidence.\n'
              'Do not claim GPU success from command exit status. Do not publish or change a live service.\n'
              + json.dumps({k: request[k] for k in ('analysis', 'adaptation_plan', 'gap_id', 'target', 'observation', 'existing_path', 'shape_contract') if k in request},
                           ensure_ascii=False, indent=2))
    record['prompt'] = store.put(prompt.encode())
    return {'status': 'complete', 'plan': retain(store, record), 'record': record}


def dispatch(store, tid, request):
    """Invoke a configured Agent/skill adapter with the retained exact task prompt."""
    _fields(request, {'plan', 'card', 'lease', 'operation'})
    task, record = _load_plan(store, tid, request['plan'])
    entry = record['skill_entry']
    if pin(store, entry['path'])['sha256'] != entry['sha256']:
        raise FlowError('Bound skill changed; create a new reviewed plan')
    card = dict(request['card'])
    command_plan(card)
    if '{operator_prompt}' not in card['argv']:
        raise FlowError('Skill runner argv must contain a separate {operator_prompt} argument')
    card['argv'] = [store.artifact(record['prompt']).decode() if x == '{operator_prompt}' else x for x in card['argv']]
    card['env'] = {**card.get('env', {}), 'HCU_INFRA_OPERATOR_PLAN': request['plan']}
    outcome = run_command(store, tid, request['operation'], card, request['lease'],
                          expected_context=task['context'], expected_context_epoch=task['context_epoch'])
    result = {'kind': 'operator-development', 'task': tid, 'context': task['context'],
              'context_epoch': task['context_epoch'], 'plan': request['plan'], 'execution': outcome,
              'command_card': retain(store, card),
              'status': outcome['status'], 'hardware_validated': False,
              'meaning': 'Skill runner returned; inspect its implementation and evidence before integration.'}
    return {**result, 'artifact': retain(store, result)}


def _verification(store, execution, request, task):
    if execution['status'] != 'complete':
        return False, 'verification command did not complete', None
    try:
        receipt = json.loads(store.artifact(execution['evidence'][0]))
        if not isinstance(receipt, dict):
            return False, 'verification stdout must be a JSON object', None
        if (receipt.get('schema_version') != 1 or receipt.get('plan') != request['plan']
                or receipt.get('framework') != request['framework']
                or receipt.get('candidate_snapshot') != request['candidate_snapshot']
                or receipt.get('context') != task['context']
                or receipt.get('context_epoch') != task['context_epoch']):
            return False, 'verification identity mismatch', receipt
        if (type(receipt.get('executed')) is not int or receipt['executed'] < 1
                or receipt.get('candidate_path_exercised') is not True
                or receipt.get('failures') or receipt.get('skipped_required')
                or receipt.get('required_missing')):
            return False, 'missing executed candidate-path verification', receipt
        if not isinstance(receipt.get('checks'), dict) or any(receipt['checks'].get(key) is not True for key in CHECKS):
            return False, 'required integration checks did not pass', receipt
        evidence = receipt.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            return False, 'verification needs retained raw evidence', receipt
        for artifact in evidence:
            store.artifact(artifact)
        return True, None, receipt
    except (ValueError, KeyError, TypeError):
        return False, 'malformed or unavailable verification evidence', None


def integrate(store, tid, request):
    """Apply a reviewed framework adapter, verify its dispatch, roll back on failure.

    Existing execution intents make retries idempotent. Unknown remote outcomes
    stop without rollback, since the original command may still be running.
    """
    required = {'plan', 'development', 'framework', 'candidate_snapshot', 'cards', 'lease', 'operation'}
    _fields(request, required)
    task, record = _load_plan(store, tid, request['plan'])
    development = json.loads(store.artifact(request['development']))
    if (development.get('kind') != 'operator-development' or development.get('plan') != request['plan']
            or development.get('task') != tid or development.get('context') != task['context']
            or development.get('context_epoch') != task['context_epoch'] or development.get('status') != 'complete'):
        raise FlowError('Integration needs a completed skill dispatch for the current plan')
    # Resolve the actual execution ledger, rather than trusting a caller-created
    # JSON object that merely labels itself a completed development receipt.
    execution = development.get('execution', {})
    with store.db() as db:
        row = db.execute('SELECT * FROM operations WHERE id=?', (execution.get('operation'),)).fetchone()
    if (not row or row['task'] != tid or row['status'] != 'complete'
            or json.loads(row['result']) != execution):
        raise FlowError('Development must reference the actual completed task operation')
    development_card = json.loads(store.artifact(development['command_card']))
    actual_command = json.loads(store.artifact(execution['evidence'][2]))
    if (command_plan(development_card) != actual_command
            or development_card.get('env', {}).get('HCU_INFRA_OPERATOR_PLAN') != request['plan']
            or store.artifact(record['prompt']).decode() not in development_card.get('argv', [])):
        raise FlowError('Development command is not bound to this operator prompt/plan')
    try:
        produced = json.loads(store.artifact(execution['evidence'][0]))
    except (ValueError, TypeError):
        raise FlowError('Skill runner stdout must retain a JSON candidate receipt') from None
    if (not isinstance(produced, dict) or produced.get('plan') != request['plan']
            or produced.get('context') != task['context'] or produced.get('context_epoch') != task['context_epoch']
            or produced.get('candidate_snapshot') != request['candidate_snapshot']):
        raise FlowError('Candidate snapshot must match the actual skill runner receipt')
    if request['framework'] not in {'sglang', 'vllm'}:
        raise FlowError('Framework integration supports sglang or vllm')
    if 'adaptation_plan' in record:
        adaptation = json.loads(store.artifact(record['adaptation_plan']))
        if adaptation.get('framework') != request['framework']:
            raise FlowError('Integration framework must match the model adaptation plan')
    store.artifact(request['candidate_snapshot'])
    cards = request['cards']
    _fields(cards, {'apply', 'verify', 'rollback'})
    for card in cards.values():
        command_plan(card)
    # All stages must target the same selected checkout and execution environment.
    location = ('backend', 'cwd', 'ssh_target', 'ssh_jump', 'container', 'namespace', 'pod', 'allocation')
    if any({k: cards[stage].get(k, 'local' if k == 'backend' else None) for k in location}
           != {k: cards['apply'].get(k, 'local' if k == 'backend' else None) for k in location}
           for stage in ('verify', 'rollback')):
        raise FlowError('Apply, verify and rollback must target the same framework checkout')
    operation = safe_id(request['operation'])
    for stage in cards:
        safe_id(operation + '-' + stage)
    identity = fingerprint({k: v for k, v in request.items() if k != 'lease'})
    directory = store.root / 'modules' / 'operator-integration'
    state_path = directory / (operation + '.json')
    from .command_group import _controller_lock
    with _controller_lock(store, 'operator-' + operation):
        if state_path.exists():
            previous = read_json(state_path)
            if previous['identity'] != identity:
                raise FlowError('Integration operation belongs to another request')
            if previous.get('artifact'):
                return json.loads(store.artifact(previous['artifact'])) | {'artifact': previous['artifact']}
        else:
            write_json(state_path, {'identity': identity, 'state': 'started'})
        executions = {}
        def execute(stage):
            executions[stage] = run_command(store, tid, operation + '-' + stage, cards[stage], request['lease'],
                                           expected_context=task['context'], expected_context_epoch=task['context_epoch'])
            return executions[stage]
        applied = execute('apply')
        status, reason, verification = 'incomplete', None, None
        if applied['status'] == 'unknown':
            reason = 'Reconcile original apply operation before retry or rollback'
        else:
            passed = False
            if applied['status'] == 'complete':
                verified = execute('verify')
                if verified['status'] == 'unknown':
                    reason = 'Reconcile original verify operation before rollback'
                else:
                    passed, reason, verification = _verification(store, verified, request, task)
            else:
                reason = 'Integration apply failed; rollback covers partial changes'
            if passed:
                status = 'complete'
            elif not any(x['status'] == 'unknown' for x in executions.values()):
                rollback = execute('rollback')
                status = 'failed' if rollback['status'] == 'complete' else 'incomplete'
                if rollback['status'] != 'complete':
                    reason = (reason or '') + '; rollback failed/unknown: recovery owner must reconcile'
        result = {'kind': 'operator-integration', 'task': tid, 'context': task['context'],
                  'context_epoch': task['context_epoch'], 'plan': request['plan'], 'development': request['development'],
                  'framework': request['framework'], 'candidate_snapshot': request['candidate_snapshot'],
                  'status': status, 'reason': reason, 'executions': executions, 'verification': verification,
                  'integration_verified': status == 'complete', 'accepted_by_flow': False,
                  'meaning': 'Integration checks only; end-to-end quality, profiler-off performance and independent review remain required.'}
        artifact = retain(store, result)
        # Incomplete outcomes remain resumable after explicit operation reconciliation.
        write_json(state_path, {'identity': identity, 'state': status,
                               **({'artifact': artifact} if status in {'complete', 'failed'} else {})})
        return {**result, 'artifact': artifact}
