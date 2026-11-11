"""Persistent, evidence-gated inference optimization; execution remains on command cards.

This module tracks initial oracle, reviewed best and trial separately. A loop step
never runs a model, invents a measurement or changes a production deployment.
"""
import copy
import json
import math
import statistics
from .core import FlowError, atomic_write, context_epoch, utc, write_json
from .evidence import current_analysis, retain, candidate_profile
from .optimization import require_scope
from . import quality, quality_coverage, optimization_output
from .file_questions import writer_lock


ROUTES = {'native': 'hcu-infer-analyze-and-optimize',
          'fusion': 'hcu-infer-operator-develop', 'triton': 'hcu-infer-operator-develop',
          'tilelang': 'hcu-infer-operator-develop', 'hip': 'hcu-infer-operator-develop',
          'gemm': 'hcu-infer-operator-develop'}


def _object(store, artifact):
    value = json.loads(store.artifact(artifact))
    if not isinstance(value, dict):
        raise FlowError('Expected a retained JSON object')
    return value


def _evidence(store, record):
    if not isinstance(record.get('evidence'), list) or not record['evidence']:
        raise FlowError('Retain nonempty raw evidence')
    for item in record['evidence']:
        store.artifact(item)


def _table(store):
    with store.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS model_loops(task TEXT PRIMARY KEY, revision INTEGER NOT NULL, artifact TEXT NOT NULL)')


def _load(store, tid):
    _table(store)
    with store.db() as db:
        row = db.execute('SELECT * FROM model_loops WHERE task=?', (tid,)).fetchone()
    if not row:
        raise FlowError('Start the model optimization loop first')
    return _object(store, row['artifact'])


def _save(store, task, state, previous):
    directory = store.root / 'modules' / 'model-loop' / task['id']
    with writer_lock(directory, name='report.lock'):
        return _save_locked(store, task, state, previous)


def _save_locked(store, task, state, previous):
    state['revision'] = 0 if previous is None else previous + 1
    state['updated'] = utc()
    artifact = retain(store, state)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT context FROM tasks WHERE id=?', (task['id'],)).fetchone()
        if current['context'] != task['context'] or context_epoch(db, task['id']) != task['context_epoch']:
            raise FlowError('Task context changed; restart with a new task')
        row = db.execute('SELECT revision FROM model_loops WHERE task=?', (task['id'],)).fetchone()
        if (row['revision'] if row else None) != previous:
            raise FlowError('Loop changed concurrently; reread its revision before retrying')
        db.execute('INSERT OR REPLACE INTO model_loops VALUES(?,?,?)', (task['id'], state['revision'], artifact))
        store.event(db, task['id'], 'model-loop-step', {'artifact': artifact, 'stage': state['stage'], 'revision': state['revision']})
    rendered = _report_state(store, state, artifact)
    return {**state, 'artifact': artifact, 'report': rendered['report']}


def start(store, tid, request):
    task = store.task(tid)
    require_scope(task)
    fields = {'gpu_count', 'max_iterations', 'max_no_gain', 'metric', 'min_gain', 'max_regression', 'sla', 'quality_coverage'}
    if set(request) - fields or {'gpu_count', 'max_iterations', 'max_no_gain'} - set(request):
        raise FlowError('Declare gpu_count, max_iterations and max_no_gain; optional metric/min_gain/max_regression/sla')
    for key in ('gpu_count', 'max_iterations', 'max_no_gain'):
        if type(request[key]) is not int or request[key] <= 0:
            raise FlowError(key + ' must be a positive integer')
    metric = request.get('metric', 'throughput_tok_s')
    if metric not in {'throughput_tok_s', 'ttft_ms', 'tpot_ms', 'latency_p95_ms'}:
        raise FlowError('Unsupported serving metric')
    for key in ('min_gain', 'max_regression'):
        if quality.number(request.get(key, 0), key) < 0:
            raise FlowError('Negative performance threshold')
    sla = request.get('sla', {})
    if not isinstance(sla, dict) or set(sla) - {'ttft_ms', 'tpot_ms', 'latency_p95_ms'}:
        raise FlowError('Unsupported SLA metric')
    for key, value in sla.items():
        quality.number(value, key, positive=True)
    _table(store)
    state = {'schema_version': 2, 'task': tid, 'context': task['context'], 'context_epoch': task['context_epoch'],
             'stage': 'simulation', 'policy': {'metric': metric, 'min_gain': 0, 'max_regression': 0, 'sla': {}, **request,
                                              'quality_coverage': quality_coverage.policy(request.get('quality_coverage'))},
             'initial': None, 'best': None, 'pending': None, 'iterations': [], 'no_gain': 0,
             'next': {'action': 'simulate-and-select', 'skill': 'hcu-infer-model-optimize'}}
    return _save(store, task, state, None)


def _fresh(store, tid, state):
    task = store.task(tid)
    if task['context'] != state['context'] or task['context_epoch'] != state['context_epoch']:
        raise FlowError('Loop context is stale; preserve history and use a new task')
    return task


def status(store, tid, request=None):
    state = _load(store, tid)
    _fresh(store, tid, state)
    return {'status': 'complete', **state}


def _select(store, state, request):
    candidates = request.get('candidates')
    metric = request.get('simulation_metric', 'throughput_tok_s')
    if metric not in {'throughput_tok_s', 'prefill_latency_ms', 'decode_latency_ms'}:
        raise FlowError('Use a supported simulator metric; tail latency requires measurement')
    if not isinstance(candidates, list) or not candidates:
        raise FlowError('Supply retained simulate artifacts and phase device allocations')
    rows, identity = [], None
    for candidate in candidates:
        sim = _object(store, candidate['artifact'])
        if sim.get('status') != 'complete' or sim.get('qualification') != 'simulation-prediction' or sim.get('hardware_executed') is not False:
            raise FlowError('Only completed simulator predictions may select a strategy')
        _evidence(store, sim)
        execution = sim.get('execution', {})
        if (execution.get('status') != 'complete' or execution.get('exit_code') != 0
                or execution.get('timed_out') is not False or not execution.get('artifact')):
            raise FlowError('Simulation needs retained successful backend execution, not only a prediction label')
        retained_execution = _object(store, execution['artifact'])
        if retained_execution != {k: v for k, v in execution.items() if k != 'artifact'}:
            raise FlowError('Simulation execution provenance mismatch')
        output = _object(store, execution['stdout']['sha256'])
        store.artifact(execution['stderr']['sha256'])
        if output != sim.get('backend_output') or output.get('result', {}).get('error'):
            raise FlowError('Simulator output must match the actual retained backend stdout')
        raw = output['result']
        summary = {'prefill_latency_ms': raw.get('prefill_latency_ms'), 'decode_latency_ms': raw.get('decode_latency_ms'),
                   'throughput_tok_s': raw.get('sys_throughput_tps'),
                   'memory_feasible': raw.get('memory_feasible_with_activation', raw.get('memory_feasible')),
                   'prefill_memory_gib': raw.get('prefill_total_memory_with_act_gb', raw.get('prefill_memory_gb')),
                   'decode_memory_gib': raw.get('decode_total_memory_with_act_gb', raw.get('decode_memory_gb'))}
        if summary != sim.get('summary'):
            raise FlowError('Simulation summary was altered from backend results')
        args = sim['input']['arguments']
        pinned_args = _object(store, sim['evidence'][0])
        expected_args = {**args, 'generate_csv': False, 'verbose': False}
        if args['model'].endswith('.json'):
            model = sim.get('model_input', {})
            store.artifact(model['sha256'])
            if (not pinned_args['model'].endswith(model['sha256'] + '.json')
                    or output.get('model_config', {}).get('sha256') != model['sha256']):
                raise FlowError('Custom simulation model must match the pinned model bytes')
            expected_args['model'] = pinned_args['model']
        if pinned_args != expected_args or any(output.get('effective_arguments', {}).get(key) != val for key, val in pinned_args.items()):
            raise FlowError('Simulation inputs differ from retained backend effective arguments')
        # DCUSim TP/DP/PP define phase world size; EP is a subgroup. CP>1
        # needs a site topology adapter, not a silently guessed multiplication.
        groups = []
        for phase in ('prefill', 'decode'):
            devices = candidate.get(phase + '_devices')
            if not isinstance(devices, list) or not devices or any(not isinstance(d, str) or not d for d in devices) or len(set(devices)) != len(devices):
                raise FlowError('Declare distinct physical device identities for each phase')
            world = math.prod(args[phase + '_' + axis] for axis in ('tp', 'dp', 'pp'))
            if args[phase + '_cp'] != 1 or world != len(devices) or world % args[phase + '_ep']:
                raise FlowError('Topology mismatch: TP*DP*PP must match devices; EP must divide it; CP>1 requires an adapter')
            groups.append(set(devices))
        if len(groups[0] | groups[1]) != state['policy']['gpu_count']:
            raise FlowError('Strategy must use exactly the fixed physical GPU count')
        frozen = {key: args[key] for key in ('model', 'gpu', 'batch_size', 'seq_len', 'output_length', 'kv_cache_dtype', 'attention_compute_dtype')}
        if identity is not None and frozen != identity:
            raise FlowError('Simulation strategies changed the model, hardware or workload')
        identity = frozen
        value = sim['summary'].get(metric)
        feasible = sim['summary'].get('memory_feasible') is True
        if feasible:
            quality.number(value, 'simulation score', positive=True)
        rows.append({**candidate, 'score': value, 'memory_feasible': feasible})
    feasible = [row for row in rows if row['memory_feasible']]
    if not feasible:
        raise FlowError('No memory-feasible strategy; preserve evidence and revise capacity assumptions')
    best = sorted(feasible, key=lambda row: row['score'], reverse=metric == 'throughput_tok_s')[0]
    state.update(strategy={'selected': best, 'candidates': rows, 'metric': metric, 'identity': identity,
                           'qualification': 'best-among-simulated-candidates; calibrate with real baseline'},
                 stage='baseline', next={'action': 'measure-baseline', 'skill': 'hcu-infer-check-and-deploy'})


def _measurements(store, state, request, baseline=False):
    qi, pi = (_object(store, request[k]) for k in ('quality_inputs', 'performance_inputs'))
    quality_coverage.require(qi['contract'], state['policy']['quality_coverage'])
    for inputs in (qi, pi):
        if inputs['contract'].get('context') != state['context']:
            raise FlowError('Measurement context mismatch')
        for record in (inputs['baseline'], inputs['candidate']):
            _evidence(store, record)
            if record.get('hardware_executed') is not True or record.get('synthetic') or record.get('qualification') == 'simulation-prediction':
                raise FlowError('Require explicit hardware-executed measurements; synthetic/predicted evidence cannot qualify')
            store.artifact(record['candidate_snapshot'])
    if qi['contract']['identities'] != pi['contract']['identities'] or qi['candidate']['candidate_snapshot'] != pi['candidate']['candidate_snapshot']:
        raise FlowError('Quality and performance must share identities and candidate snapshot')
    policy = state['policy']
    contract = pi['contract']
    for key in ('metric', 'max_regression', 'sla'):
        if contract.get(key, {} if key == 'sla' else 0) != policy[key]:
            raise FlowError('Performance policy cannot change between iterations: ' + key)
    if contract.get('min_gain', 0) != (0 if baseline else policy['min_gain']):
        raise FlowError('Performance gain threshold mismatch')
    if baseline:
        deployment = _object(store, request['deployment'])
        _evidence(store, deployment)
        selected = state['strategy']['selected']
        if (deployment.get('context') != state['context']
                or deployment.get('candidate_snapshot') != pi['candidate']['candidate_snapshot']
                or deployment.get('simulation') != selected['artifact']
                or any(deployment.get(phase + '_devices') != selected[phase + '_devices'] for phase in ('prefill', 'decode'))):
            raise FlowError('Baseline deployment must match selected strategy, devices and snapshot')
        if pi['baseline'] != pi['candidate']:
            raise FlowError('Initial performance record must self-compare the fixed baseline')
    else:
        initial_q = _object(store, state['initial']['quality_inputs'])
        best_p = _object(store, state['best']['performance_inputs'])
        if qi['baseline'] != initial_q['baseline'] or qi['contract'] != initial_q['contract']:
            raise FlowError('Keep the initial numerical oracle and quality contract fixed')
        if pi['baseline'] != best_p['candidate'] or pi['contract']['identities'] != best_p['contract']['identities']:
            raise FlowError('Compare performance against the reviewed best with unchanged identities')
        initial_p = _object(store, state['initial']['performance_inputs'])
        cumulative = quality.compare_performance({**contract, 'min_gain': 0}, initial_p['candidate'], pi['candidate'])
    q = quality.compare_outputs(**qi)
    p = quality.compare_performance(**pi)
    return {'quality_inputs': request['quality_inputs'], 'performance_inputs': request['performance_inputs'],
            'snapshot': qi['candidate']['candidate_snapshot'], 'deployment': request.get('deployment', state['initial']['deployment'] if state['initial'] else None), 'quality': q, 'performance': p,
            'cumulative_performance': p if baseline else cumulative,
            'status': 'pass' if q['status'] == p['status'] == 'pass' and (baseline or cumulative['status'] == 'pass') else 'fail'}


def _next_iteration(state):
    state['pending'] = None
    if len(state['iterations']) >= state['policy']['max_iterations']:
        state.update(stage='stopped', stop_reason='iteration-budget')
    elif state['no_gain'] >= state['policy']['max_no_gain']:
        state.update(stage='stopped', stop_reason='no-gain-budget')
    else:
        state['stage'] = 'profile'
    state['next'] = {'action': 'report' if state['stage'] == 'stopped' else 'capture-current-best-profile',
                     'skill': 'hcu-infer-model-optimize'}


def _screening(store, state, artifact, snapshot):
    """Keep exploratory timings visible without turning them into acceptance."""
    value = _object(store, artifact)
    _evidence(store, value)
    if (value.get('context') != state['context'] or value.get('candidate_snapshot') != snapshot
            or value.get('hardware_executed') is not True or value.get('synthetic')
            or value.get('qualification') == 'simulation-prediction'
            or value.get('profiler_off') is not True or value.get('candidate_path_exercised') is not True
            or type(value.get('executed')) is not int or value['executed'] <= 0
            or value.get('failures') or value.get('status') not in {'pass', 'complete'}):
        raise FlowError('Screening needs retained successful profiler-off hardware measurements for this candidate')
    metrics = value.get('metrics')
    if not isinstance(metrics, list) or not metrics:
        raise FlowError('Screening needs nonempty metric rows')
    result = {}
    for row in metrics:
        scope, name, metric = row.get('scope'), row.get('scenario'), row.get('metric')
        allowed = {'throughput_tok_s', 'ttft_ms', 'tpot_ms', 'latency_p95_ms'} if scope == 'model' else {'time_ms'} if scope == 'operator' else set()
        if metric not in allowed or not isinstance(name, str) or not name.strip():
            raise FlowError('Screening must distinguish model metrics from operator time_ms and name the scenario')
        a, b = row.get('baseline'), row.get('candidate')
        if not isinstance(a, list) or not a or not isinstance(b, list) or len(a) != len(b):
            raise FlowError('Screening needs paired nonempty timing arrays')
        for number in a + b:
            quality.number(number, 'screening metric', positive=True)
        ma, mb = statistics.median(a), statistics.median(b)
        key = scope + '/' + name + ':' + metric
        if key in result:
            raise FlowError('Screening scenario/metric rows must be unique')
        result[key] = {'scope': scope, 'baseline_median': ma, 'candidate_median': mb,
                       'relative_gain': mb / ma - 1 if metric == 'throughput_tok_s' else 1 - mb / ma,
                       'repeats': len(a)}
    return {'status': 'unverified-screening', 'metrics': result,
            'limits': 'Exploratory data only; accuracy, formal performance repetitions and review remain required.'}


def advance(store, tid, request):
    state = copy.deepcopy(_load(store, tid))
    task = _fresh(store, tid, state)
    require_scope(task)
    revision = state['revision']
    if state.get('schema_version') != 2:
        raise FlowError('Legacy loop is report-only: start a new task with explicit quality coverage and candidate profiling')
    if type(request.get('revision')) is not int or request['revision'] != revision:
        raise FlowError('Supply the current loop revision; stale steps cannot replay')
    with store.db() as db:
        if db.execute("SELECT 1 FROM operations WHERE task=? AND status IN ('started','unknown')", (tid,)).fetchone():
            raise FlowError('Reconcile unresolved execution before advancing the loop')
    action, stage = request.get('action'), state['stage']
    if action == 'interrupt':
        if not isinstance(request.get('reason'), str) or not request['reason'].strip():
            raise FlowError('Record the explicit user interruption reason')
        proof = _object(store, request['verification'])
        _evidence(store, proof)
        if (proof.get('task') != tid or proof.get('context') != state['context']
                or proof.get('context_epoch') != state['context_epoch']
                or proof.get('loop_revision') != revision or proof.get('status') != 'stopped'
                or proof.get('execution_stopped') is not True):
            raise FlowError('Interruption requires current-revision evidence that execution is stopped')
        if state.get('pending'):
            state['pending'].update(decision='interrupted', status='incomplete',
                                    rejection_reason=request['reason'], interruption=request['verification'])
            state['iterations'].append(state['pending'])
            state['pending'] = None
        state.update(stage='stopped', stop_reason=request['reason'], interruption=request['verification'],
                     runtime_state='stopped; restoring the reviewed best is not claimed', next={'action': 'report'})
    elif action == 'stop' and stage not in {'candidate', 'review', 'rollback'}:
        if not isinstance(request.get('reason'), str) or not request['reason'].strip():
            raise FlowError('Stopping requires an actual reason')
        state.update(stage='stopped', stop_reason=request['reason'], next={'action': 'report'})
    elif stage == 'simulation' and action == 'select-strategy':
        _select(store, state, request)
    elif stage in {'baseline', 'adaptation'} and action == 'baseline-failed':
        failure = _object(store, request['failure'])
        _evidence(store, failure)
        if failure.get('context') != state['context'] or failure.get('status') not in {'fail', 'incomplete'}:
            raise FlowError('Retain the current failed baseline run')
        state.update(stage='adaptation', baseline_failure=request['failure'],
                     next={'action': 'adapt-model', 'skill': 'hcu-infer-model-adapt', 'failure': request['failure']})
        state.setdefault('baseline_failures', []).append({'failure': request['failure'], 'recorded': utc()})
    elif stage in {'baseline', 'adaptation'} and action == 'baseline':
        if stage == 'adaptation':
            adapted = _object(store, request['adaptation'])
            _evidence(store, adapted)
            if (adapted.get('module') != 'model-adaptation' or adapted.get('task') != tid
                    or adapted.get('context') != state['context'] or adapted.get('context_epoch') != state['context_epoch']
                    or adapted.get('status') != 'pass' or adapted.get('ready_for_baseline') is not True):
                raise FlowError('Complete model adaptation checks before measuring a new baseline')
            if adapted.get('candidate_snapshot') != _object(store, request['quality_inputs'])['candidate']['candidate_snapshot']:
                raise FlowError('New baseline must exercise the adapted snapshot')
            state['adaptation'] = request['adaptation']
        measurement = _measurements(store, state, request, baseline=True)
        if measurement['status'] != 'pass':
            failure = retain(store, {'context': state['context'], **measurement,
                                     'evidence': [request['quality_inputs'], request['performance_inputs']]})
            state.update(stage='adaptation', baseline_failure=failure,
                         next={'action': 'adapt-model', 'skill': 'hcu-infer-model-adapt', 'failure': failure})
            state.setdefault('baseline_failures', []).append({'failure': failure, 'recorded': utc()})
        else:
            state.update(initial=measurement, best=measurement, stage='profile',
                         next={'action': 'capture-current-best-profile', 'skill': 'hcu-infer-analyze-and-optimize'})
    elif stage == 'profile' and action == 'profile':
        current_analysis(store, task, request['analysis'])
        capture = _object(store, request['capture'])
        _evidence(store, capture)
        if capture.get('context') != state['context'] or capture.get('candidate_snapshot') != state['best']['snapshot'] or capture.get('analysis') != request['analysis'] or capture.get('hardware_executed') is not True or capture.get('synthetic'):
            raise FlowError('Capture provenance must bind this analysis to the current best snapshot and hardware run')
        analysis = _object(store, request['analysis'])
        if not analysis.get('ranks') or any(row['source']['sha256'] not in capture['evidence'] for row in analysis['ranks']):
            raise FlowError('Capture must retain every analyzed rank trace')
        if any(item['analysis'] == request['analysis'] for item in state['iterations']):
            raise FlowError('Refresh profiling after each candidate; do not recycle the previous iteration analysis')
        state.update(analysis=request['analysis'], capture=request['capture'], stage='candidate',
                     pending={'number': len(state['iterations']) + 1, 'analysis': request['analysis'],
                              'capture': request['capture'], 'previous_snapshot': state['best']['snapshot'],
                              'status': 'exploring', 'direction': 'Candidate exploration not recorded yet',
                              'explorations': []},
                     next={'action': 'plan-and-implement', 'skill': 'hcu-infer-analyze-and-optimize'})
    elif stage == 'candidate' and action == 'explore':
        plan = _object(store, request['plan'])
        if plan.get('task') != tid or plan.get('context') != state['context'] or plan.get('analysis') != state['analysis']:
            raise FlowError('Exploration plan must use the current loop profile')
        current_analysis(store, task, state['analysis'])
        route = request.get('route')
        if route not in ROUTES:
            raise FlowError('Choose a supported optimization route')
        snapshot = request.get('candidate_snapshot')
        store.artifact(snapshot)
        if snapshot == state['best']['snapshot']:
            raise FlowError('Exploration needs a distinct candidate snapshot')
        changes = request.get('changes')
        if (not isinstance(changes, list) or not changes
                or any(not isinstance(x, dict) or not all(isinstance(x.get(k), str) and x[k].strip()
                                                         for k in ('path', 'description')) for x in changes)):
            raise FlowError('Record nonempty implementation changes with path and description')
        if not isinstance(request.get('summary'), str) or not request['summary'].strip():
            raise FlowError('Describe what this exploration changes')
        if not isinstance(request.get('notes', ''), str):
            raise FlowError('Exploration notes must be text')
        _evidence(store, request)
        trial = {'snapshot': snapshot, 'plan': request['plan'], 'summary': request['summary'],
                 'changes': changes, 'notes': request.get('notes', ''), 'evidence': request['evidence'], 'recorded': utc()}
        if request.get('screening'):
            trial.update(screening=request['screening'],
                         screening_summary=_screening(store, state, request['screening'], snapshot))
        old = state['pending']
        # Keep every attempt, even if the selected candidate later changes.
        state['pending'] = {key: old[key] for key in ('number', 'analysis', 'capture', 'previous_snapshot', 'explorations')}
        state['pending'].update(plan=request['plan'], snapshot=snapshot, direction=plan['hypothesis'],
                                observation=plan['observation'], changes=changes, route=route,
                                skill=ROUTES[route], status='exploring')
        state['pending']['explorations'].append(trial)
        if trial.get('screening'):
            state['pending'].update(screening=trial['screening'], screening_summary=trial['screening_summary'])
        state['next'] = {'action': 'validate-candidate-and-capture-after-profile',
                         'snapshot': snapshot, 'skill': ROUTES[route]}
    elif stage == 'candidate' and action == 'evaluate':
        plan = _object(store, request['plan'])
        if plan.get('task') != tid or plan.get('context') != state['context'] or plan.get('analysis') != state['analysis']:
            raise FlowError('Candidate plan must use the current loop profile')
        current_analysis(store, task, state['analysis'])
        route = request.get('route')
        if route not in ROUTES:
            raise FlowError('Choose native/fusion/triton/tilelang/hip/gemm route from profile evidence')
        exploration = state['pending']
        if (not exploration.get('explorations') or exploration.get('plan') != request['plan']
                or exploration.get('route') != route):
            raise FlowError('Record the candidate with explore before evaluation')
        measurement = _measurements(store, state, request)
        if exploration['snapshot'] != measurement['snapshot']:
            raise FlowError('Evaluated snapshot differs from the recorded exploration')
        after = {'status': 'not-collected'}
        if request.get('candidate_analysis') or request.get('candidate_capture'):
            if not request.get('candidate_analysis') or not request.get('candidate_capture'):
                raise FlowError('Provide both candidate_analysis and candidate_capture')
            after = candidate_profile(store, task, request['candidate_analysis'], request['candidate_capture'],
                                      measurement['snapshot'], state['analysis'])
            used = {sha for item in state['iterations'] for sha in item.get('candidate_profile', {}).get('traces', [])}
            if used.intersection(after['traces']):
                raise FlowError('Refresh candidate profiling for every optimization iteration')
        pending = {**exploration, 'analysis': state['analysis'], 'plan': request['plan'],
                   'direction': plan['hypothesis'], 'observation': plan['observation'], 'route': route,
                   'skill': ROUTES[route], 'previous_snapshot': state['best']['snapshot'], **measurement,
                   'candidate_profile': after}
        if measurement['snapshot'] == state['best']['snapshot']:
            raise FlowError('Candidate must identify a distinct source/configuration snapshot')
        state['pending'] = pending
        ready = measurement['status'] == 'pass' and after['status'] == 'complete'
        if measurement['status'] == 'pass' and not ready:
            pending.update(status='incomplete', missing_reason='Capture the evaluated candidate Prof before review')
        state['stage'] = 'review' if ready else 'rollback' if measurement['status'] == 'fail' else 'candidate'
        state['next'] = {'action': 'independent-flow-review' if ready else 'restore-best-and-verify' if measurement['status'] == 'fail' else 'capture-candidate-profile',
                         'snapshot': pending['snapshot'] if measurement['status'] == 'pass' else state['best']['snapshot'],
                         'skill': 'hcu-infer-analyze-and-optimize' if measurement['status'] == 'pass' and not ready else ROUTES[route]}
    elif stage == 'review' and action == 'keep':
        current_analysis(store, task, state['analysis'])
        pending = state['pending']
        after = pending.get('candidate_profile', {})
        if pending.get('quality', {}).get('status') != 'pass' or after.get('status') != 'complete':
            raise FlowError('Passing accuracy and post-change profiling are required before keep')
        candidate_profile(store, task, after['analysis'], after['capture'], pending['snapshot'], state['analysis'])
        number = request.get('flow_round')
        with store.db() as db:
            row = db.execute('SELECT * FROM flow_rounds WHERE task=? AND number=?', (tid, number)).fetchone()
            latest = db.execute('SELECT MAX(number) FROM flow_rounds WHERE task=?', (tid,)).fetchone()[0]
            current_flow = db.execute('SELECT goal FROM flows WHERE task=?', (tid,)).fetchone()
        if (not row or row['status'] != 'advanced' or row['context'] != state['context'] or number != latest
                or not current_flow or row['goal'] != current_flow['goal'] or row['revision'] != task['revision']):
            raise FlowError('Advance the matching current independent flow review before retaining a candidate')
        candidate, review = _object(store, row['candidate']), _object(store, row['review'])
        pending = state['pending']
        if (candidate.get('snapshot') != pending['snapshot'] or review.get('verdict') != 'accept'
                or review.get('reviewer') == candidate.get('author')
                or candidate.get('profile_evidence', {}).get('artifact') != state['analysis']):
            raise FlowError('Reviewed candidate snapshot or reviewer mismatch')
        with store.db() as db:
            current_reports = store.current_reports(db, tid, state['context'])
        for kind, key in [('inference-quality', 'quality_inputs'), ('performance', 'performance_inputs')]:
            if not current_reports.get(kind) or current_reports[kind]['artifact'] != candidate.get('reports', {}).get(kind):
                raise FlowError('Reviewed measurements were replaced; revalidate the candidate')
            report = _object(store, candidate.get('reports', {}).get(kind))
            if (report.get(key) != pending[key] or report.get('candidate_snapshot') != pending['snapshot']
                    or report.get('status') != 'pass' or current_reports[kind]['result'] != 'pass'):
                raise FlowError('Flow review must cover the exact evaluated measurements')
            (quality.validate_stage_report if kind == 'inference-quality' else quality.validate_performance_report)(store, report)
        pending.update(decision='kept', flow_round=number, review=row['review'])
        state['iterations'].append(pending)
        state['best'] = pending
        gains = [v['relative_gain'] for k, v in pending['performance']['metrics'].items() if k.endswith(':' + state['policy']['metric'])]
        state['no_gain'] = 0 if gains and min(gains) > 0 else state['no_gain'] + 1
        _next_iteration(state)
    elif stage in {'review', 'candidate'} and action == 'reject':
        if not isinstance(request.get('reason'), str) or not request['reason'].strip():
            raise FlowError('Record why the candidate was rejected')
        if stage == 'candidate':
            failure = _object(store, request['failure']); _evidence(store, failure)
            if failure.get('context') != state['context'] or failure.get('status') not in {'fail', 'incomplete'}:
                raise FlowError('Retain the current implementation failure')
            state['pending'].update(status='fail', failure=request['failure'])
            if not state['pending'].get('explorations'):
                state['pending']['direction'] = request['reason']
        state['pending']['rejection_reason'] = request['reason']
        state.update(stage='rollback', next={'action': 'restore-best-and-verify', 'snapshot': state['best']['snapshot']})
    elif stage == 'rollback' and action == 'rollback':
        restored = _object(store, request['verification'])
        _evidence(store, restored)
        with store.db() as db:
            operation = db.execute('SELECT * FROM operations WHERE id=? AND task=?', (restored.get('operation'), tid)).fetchone()
        if (not operation or operation['status'] != 'complete' or operation['created'] <= state['updated']):
            raise FlowError('Rollback needs a fresh completed restoration/validation operation after candidate rejection')
        execution = json.loads(operation['result'] or '{}')
        if (execution.get('returncode') != 0 or execution.get('timed_out') is not False
                or execution.get('context') != state['context'] or execution.get('context_epoch') != state['context_epoch']
                or not execution.get('evidence') or not set(execution['evidence']).issubset(restored['evidence'])):
            raise FlowError('Rollback verification must bind the fresh operation and its raw logs')
        reasons = quality.validate_measurement(restored, state['context'])
        if reasons or restored.get('hardware_executed') is not True or restored.get('synthetic') or restored.get('candidate_snapshot') != state['best']['snapshot']:
            raise FlowError('Verify restored best snapshot on hardware before another iteration')
        pending = state['pending']
        pending.update(decision='rejected', rollback=request['verification'])
        state['iterations'].append(pending)
        state['no_gain'] += 1
        _next_iteration(state)
    else:
        raise FlowError('Action is invalid for loop stage ' + stage)
    return _save(store, task, state, revision)


def _report_state(store, state, artifact, directory=None, force=False):
    tid = state['task']
    directory = directory or store.root / 'modules' / 'model-loop' / tid
    lines = ['# Model optimization loop', '', 'Task: ' + tid,
             'Objective: ' + optimization_output.text(store.task(tid)['spec']['objective']),
             'Stage: ' + state['stage'], 'Stop reason: ' + state.get('stop_reason', 'not stopped'),
             'Runtime disposition: ' + state.get('runtime_state', 'see execution/rollback evidence'),
             'Validation: evidence protocol; no hardware execution is implied by this report.', '',
             '| Iteration | Direction | Assessment / decision | Quality | After Prof | Effective | Incremental primary metric | Cumulative primary metric |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    def metrics(value):
        entries = [(k, v['relative_gain']) for k, v in value.get('metrics', {}).items()
                   if k.endswith(':' + state['policy']['metric'])]
        if len(entries) > 3:
            values = [v for _, v in entries]
            return f'{state["policy"]["metric"]}: {min(values):+.2%} to {max(values):+.2%} ({len(values)} scenarios)'
        return '; '.join(f'{k}: {v:+.2%}' for k, v in entries) or 'not measured'
    records = state['iterations'] + ([state['pending']] if state.get('pending') else [])
    for item in records:
        relative = f'iterations/{item["number"]:04d}'
        optimization_output.bundle(store, directory / relative, item, force=force)
        direction = item['direction'].replace('|', '\\|').replace('\n', ' ')
        lines.append(f'| [{item["number"]}]({relative}/REPORT.md) | {direction} | {item.get("status", "exploring")} / {item.get("decision", "pending")} | '
                     f'{item.get("quality", {}).get("status", "not-measured")} | '
                     f'{item.get("candidate_profile", {}).get("status", "not-collected")} | '
                     f'{"yes" if optimization_output.effective(item) else "no"} | '
                     f'{metrics(item["performance"]) if item.get("performance") else "screening / unverified: " + metrics(item["screening_summary"]) if item.get("screening_summary") else "not measured"} | '
                     f'{metrics(item.get("cumulative_performance", {}))} |')
    if state.get('pending'):
        lines += ['', 'Pending candidate (not retained): ' + state['pending']['direction']]
    if state['initial']:
        optimization_output.bundle(store, directory/'baseline', {**state['initial'], 'kind': 'baseline', 'direction': 'Initial baseline'}, force=force)
        lines += ['', '[Initial baseline and fixed accuracy oracle](baseline/REPORT.md)']
    for number, failed in enumerate(state.get('baseline_failures', []), 1):
        failure = _object(store, failed['failure'])
        relative = f'baseline-failures/{number:04d}'
        optimization_output.bundle(store, directory/relative,
                                   {**failure, 'failure': failed['failure'], 'kind': 'baseline-failure', 'direction': 'Failed baseline',
                                    'decision': 'failed', 'number': number}, force=force)
        lines += ['', f'[Failed baseline {number}]({relative}/REPORT.md)']
    if state.get('interruption'):
        optimization_output.bundle(store, directory/'interruption', {
            'direction': 'Loop interrupted', 'decision': 'interrupted', 'status': 'incomplete',
            'interruption': state['interruption'], 'rejection_reason': state['stop_reason']}, force=force)
        lines += ['', '[User interruption and stopped-execution evidence](interruption/REPORT.md)']
    lines += ['', 'Initial snapshot: ' + (state['initial']['snapshot'] if state['initial'] else 'unmeasured'),
              'Reviewed best snapshot: ' + (state['best']['snapshot'] if state['best'] else 'unmeasured'),
              '', 'Each iteration retains exploration history, quality/performance inputs, raw before/after Prof and a manifest.',
              'Measured gains without passing quality or candidate Prof are unverified. Only independently reviewed kept candidates are effective.',
              '', 'Full immutable evidence and per-metric medians/deviation are in the JSON artifact.']
    write_json(directory/'state.json', state)
    write_json(directory/'history'/f'revision-{state["revision"]:06d}.json', state)
    write_json(directory/'manifest.json', {'schema_version': 1, 'module': 'model-loop', 'task': tid,
                                         'context': state['context'], 'state_artifact': artifact,
                                         'revision': state['revision'], 'report': 'REPORT.md'})
    path = directory / 'REPORT.md'
    atomic_write(path, '\n'.join(lines) + '\n')
    return {'status': 'complete', 'report': str(path), 'artifact': artifact, 'state': state}


def report(store, tid, request=None):
    from pathlib import Path
    request = request or {}
    if set(request) - {'destination'}:
        raise FlowError('Report accepts only an optional destination directory')
    directory = store.root / 'modules' / 'model-loop' / tid
    if request.get('destination'):
        directory = Path(request['destination']).expanduser().resolve()
        _check_destination(directory, tid, store.task(tid)['context'])
    with writer_lock(directory, name='report.lock'):
        state = _load(store, tid)
        _fresh(store, tid, state)
        if request.get('destination'):
            _check_destination(directory, tid, state['context'])
        return _report_state(store, state, retain(store, state), directory=directory, force=True)


def _check_destination(directory, tid, context):
    if directory.exists() and any(p.name != 'report.lock' for p in directory.iterdir()):
        marker = directory/'manifest.json'
        metadata = json.loads(marker.read_text()) if marker.is_file() else {}
        if (metadata.get('task') != tid or metadata.get('module') != 'model-loop'
                or metadata.get('context') != context):
            raise FlowError('Export destination must be new or an existing export of this task')
