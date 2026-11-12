"""Synthetic protocol fixtures, never claims of HCU measurements."""
import copy
import json
import sys
import uuid
import pytest
from hcu_infra_agent import flow, model_loop, optimization, profiling
from hcu_infra_agent.core import Store, FlowError
from hcu_infra_agent.evidence import retain
from hcu_infra_agent.simulation import REQUIRED
from hcu_infra_agent.quality_coverage import DEFAULT_COVERAGE
from optimization_fixtures import samples, after_profile


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / 'store')
    store.create({'schema_version': 1, 'task_id': 't', 'mode': 'optimize', 'objective': 'Fixed serving loop',
                  'context': {'model': 'fixture', 'workload': 'w', 'driver': 'fixture'}, 'permissions': ['execute']})
    flow.start(store, 't', {'acceptance': {'quality': 'fixed oracle', 'performance': 'repeatable gain'}})
    return store


def start(store, **kwargs):
    return model_loop.start(store, 't', {'gpu_count': 2, 'max_iterations': 3, 'max_no_gain': 2,
                                        'metric': 'throughput_tok_s', **kwargs})


def step(store, action, **kwargs):
    if action == 'baseline' and 'deployment' not in kwargs:
        selected = model_loop.status(store, 't')['strategy']['selected']
        candidate = json.loads(store.artifact(kwargs['performance_inputs']))['candidate']
        kwargs['deployment'] = retain(store, {'context': store.task('t')['context'], 'candidate_snapshot': candidate['candidate_snapshot'],
            'simulation': selected['artifact'], 'prefill_devices': selected['prefill_devices'], 'decode_devices': selected['decode_devices'],
            'evidence': [store.put(b'fixture effective deployment config')]})
    if action == 'evaluate' and not model_loop.status(store, 't')['pending'].get('explorations'):
        snapshot = json.loads(store.artifact(kwargs['quality_inputs']))['candidate']['candidate_snapshot']
        step(store, 'explore', plan=kwargs['plan'], route=kwargs['route'], candidate_snapshot=snapshot,
             summary='Fixture candidate implementation', changes=kwargs.get('changes', [{'path': 'kernel.py', 'description': 'fixture change'}]),
             evidence=[snapshot])
    return model_loop.advance(store, 't', {'revision': model_loop.status(store, 't')['revision'], 'action': action, **kwargs})


def simulated(store, score=100, feasible=True, tp=2):
    args = {key: 1 for key in REQUIRED}
    args.update(model='fixture', gpu='fixture-gpu', batch_size=1, seq_len=8, output_length=4,
                prefill_tp=tp, decode_tp=tp, dp_attention=False, kv_cache_dtype='bf16', attention_compute_dtype='bf16')
    output = {'result': {'sys_throughput_tps': score, 'memory_feasible': feasible},
              'effective_arguments': {**args, 'generate_csv': False, 'verbose': False}}
    execution = {'status': 'complete', 'exit_code': 0, 'timed_out': False,
                 'stdout': {'sha256': retain(store, output)}, 'stderr': {'sha256': store.put(b'')}}
    execution['artifact'] = retain(store, execution)
    artifact = retain(store, {'execution': execution, 'backend_output': output, 'status': 'complete',
        'qualification': 'simulation-prediction', 'hardware_executed': False, 'input': {'arguments': args},
        'summary': {'throughput_tok_s': score, 'memory_feasible': feasible, 'prefill_latency_ms': None,
                    'decode_latency_ms': None, 'prefill_memory_gib': None, 'decode_memory_gib': None},
        'evidence': [retain(store, {**args, 'generate_csv': False, 'verbose': False}), execution['artifact']]})
    return {'artifact': artifact, 'prefill_devices': ['node:0', 'node:1'], 'decode_devices': ['node:0', 'node:1']}


def measurements(store, snapshot=None):
    snapshot = snapshot or store.put(b'initial source')
    context = store.task('t')['context']
    ids = {key: 'fixed-' + key for key in ('model', 'tokenizer', 'quantization', 'driver')}; ids['workload'] = 'w'
    base = {'context': context, 'identities': ids, 'executed': 6, 'status': 'pass', 'candidate_path_exercised': True,
            'candidate_snapshot': snapshot, 'evidence': [store.put(b'fixture raw measurement')], 'hardware_executed': True}
    qr = {**base, 'features': {'streaming': True}, 'samples': samples()}
    qi = {'contract': {'context': context, 'identities': ids, 'atol': 0, 'rtol': 0, 'tolerance_basis': 'exact fixture',
                       'required_features': ['streaming'], 'coverage': dict(DEFAULT_COVERAGE)}, 'baseline': copy.deepcopy(qr), 'candidate': copy.deepcopy(qr)}
    pr = {**base, 'workload': 'w', 'profiler_off': True, 'scenarios': {'decode': {
        'throughput_tok_s': [100, 101, 99], 'ttft_ms': [1, 1, 1], 'tpot_ms': [1, 1, 1], 'latency_p95_ms': [3, 3, 3]}}}
    pi = {'contract': {'context': context, 'identities': ids, 'workload': 'w', 'metric': 'throughput_tok_s'},
          'baseline': copy.deepcopy(pr), 'candidate': copy.deepcopy(pr)}
    return qi, pi


def baseline(store):
    start(store)
    step(store, 'select-strategy', candidates=[simulated(store, 100), simulated(store, 120)])
    qi, pi = measurements(store)
    state = step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    assert state['stage'] == 'profile'
    return qi, pi


def profile(store, tmp_path, suffix='first'):
    path = tmp_path / (suffix + '.json')
    path.write_text(json.dumps({'rank': 0, 'traceEvents': [{'ph': 'X', 'cat': 'kernel', 'name': suffix,
                                                          'ts': 1, 'dur': 8, 'args': {'shape': [2, 2]}}]}))
    prof = profiling.analyze(store, 't', {'traces': [{'rank': 0, 'path': str(path), 'window': {'start_us': 0, 'end_us': 10}}],
                                        'groups': [{'domain': 'tp', 'ranks': [0]}]})
    capture = retain(store, {'context': store.task('t')['context'], 'candidate_snapshot': model_loop.status(store, 't')['best']['snapshot'],
                             'analysis': prof['analysis'], 'hardware_executed': True,
                             'evidence': [row['source']['sha256'] for row in prof['report']['ranks']]})
    step(store, 'profile', analysis=prof['analysis'], capture=capture)
    return optimization.plan(store, 't', {'analysis': prof['analysis'], 'observation': 'Measured GEMM cost',
                                          'hypothesis': 'Tune matching GEMM dispatch', 'target': 'gemm',
                                          'validation': ['fixed outputs', 'serving repeats']})


def candidate(store, qi, pi, gain=True):
    qi, pi = copy.deepcopy(qi), copy.deepcopy(pi)
    snapshot = store.put(('candidate source ' + uuid.uuid4().hex).encode())
    qi['candidate']['candidate_snapshot'] = snapshot
    pi['candidate']['candidate_snapshot'] = snapshot
    pi['candidate']['scenarios']['decode']['throughput_tok_s'] = [120, 121, 119] if gain else [90, 91, 89]
    return {'quality_inputs': retain(store, qi), 'performance_inputs': retain(store, pi),
            'changes': [{'path': 'kernel.py', 'description': 'fixture dispatch tuning'}],
            **after_profile(store, snapshot)}


def independent_review(store, plan, inputs):
    result = optimization.evaluate(store, 't', {'plan': plan['plan'], **inputs})
    next_step = flow.next_step(store, 't')
    snapshot = result['candidate_snapshot']
    experiment = retain(store, {'context': store.task('t')['context'], 'correctness': {
        'context': store.task('t')['context'], 'candidate_snapshot': snapshot, 'candidate_path_exercised': True,
        'executed': 1, 'status': 'pass', 'profiler_off': True, 'measurement_protocol': 'fixture paired',
        'evidence': [store.put(b'fixture local operator checks')]}, 'baseline_times': [10, 10, 10], 'candidate_times': [9, 9, 9]})
    submitted = flow.submit(store, 't', {'author': 'implementer', 'context': store.task('t')['context'],
        'goal': next_step['goal'], 'snapshot': snapshot, 'summary': 'Candidate measured', 'reports': result['reports'],
        'target': 'iterate', 'evidence': [inputs['quality_inputs'], inputs['performance_inputs']],
        'profile_evidence': plan['record']['profile_evidence'], 'experiment': experiment})
    decision = flow.next_step(store, 't')
    review = {key: decision[key] for key in ('round', 'candidate', 'goal', 'context')}
    review.update(reviewer='independent', verdict='accept', summary='Checked raw outputs and repeated timings', findings=[],
                  acceptance={'quality': 'met', 'performance': 'met'}, progress='advanced', full_alignment=True,
                  evidence=[inputs['quality_inputs'], inputs['performance_inputs']])
    flow.review(store, 't', review)
    flow.advance(store, 't')
    return decision['round']



def restore(store, record):
    """Execute a CPU fixture restoration; assertions remain explicit test fixtures."""
    from hcu_infra_agent.execution import run_command
    operation = 'restore-' + uuid.uuid4().hex
    lease = store.lease('fixture-cpu', 'test')
    result = run_command(store, 't', operation, {'schema_version': 1, 'backend': 'local',
        'cwd': str(store.root), 'argv': [sys.executable, '-c', 'print("CPU fixture restoration checked")'],
        'basis': 'Synthetic protocol fixture only', 'timeout_seconds': 5}, lease)
    store.release(lease)
    return retain(store, {**record, 'operation': operation, 'evidence': [*record['evidence'], *result['evidence']]})

def test_strategy_is_best_among_feasible_fixed_device_candidates(store):
    start(store)
    best = simulated(store, 120)
    selected = step(store, 'select-strategy', candidates=[simulated(store, 200, feasible=False), simulated(store), best])
    assert selected['strategy']['selected']['artifact'] == best['artifact']
    assert selected['stage'] == 'baseline' and selected['initial'] is None


def test_selection_does_not_invent_missing_capacity_or_allow_wrong_gpu_count(store):
    start(store)
    with pytest.raises(FlowError, match='No memory-feasible'):
        step(store, 'select-strategy', candidates=[simulated(store, feasible=None)])
    with pytest.raises(FlowError, match='Topology mismatch'):
        step(store, 'select-strategy', candidates=[simulated(store, tp=1)])
    assert model_loop.status(store, 't')['stage'] == 'simulation'


def test_baseline_failure_routes_adaptation_and_needs_verified_return(store):
    start(store)
    step(store, 'select-strategy', candidates=[simulated(store)])
    failure = retain(store, {'context': store.task('t')['context'], 'status': 'fail', 'evidence': [store.put(b'import failed')]})
    state = step(store, 'baseline-failed', failure=failure)
    assert state['next']['skill'] == 'hcu-infer-model-adapt'
    qi, pi = measurements(store)
    with pytest.raises(FlowError, match='Complete model adaptation'):
        step(store, 'baseline', adaptation=failure, quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    adapted = retain(store, {'module': 'model-adaptation', 'task': 't', 'context': store.task('t')['context'],
                            'context_epoch': store.task('t')['context_epoch'], 'status': 'pass', 'ready_for_baseline': True,
                            'candidate_snapshot': qi['candidate']['candidate_snapshot'],
                            'evidence': [store.put(b'fixture adaptation tests')]})
    assert step(store, 'baseline', adaptation=adapted, quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))['stage'] == 'profile'


def test_unmeasured_or_synthetic_baseline_is_rejected(store):
    start(store); step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    qi['candidate']['hardware_executed'] = False
    with pytest.raises(FlowError, match='hardware-executed'):
        step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    assert model_loop.status(store, 't')['initial'] is None


def test_complete_candidate_requires_flow_and_preserves_initial_oracle(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    state = step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)
    assert state['stage'] == 'review'
    with pytest.raises(FlowError, match='independent flow'):
        step(store, 'keep', flow_round=1)
    number = independent_review(store, plan, inputs)
    state = step(store, 'keep', flow_round=number)
    assert state['stage'] == 'profile' and state['iterations'][0]['decision'] == 'kept'
    assert state['initial']['snapshot'] != state['best']['snapshot']
    assert state['iterations'][0]['performance']['metrics']['decode:throughput_tok_s']['relative_gain'] == pytest.approx(.2)
    assert 'Tune matching GEMM' in model_loop.report(store, 't')['state']['iterations'][0]['direction']
    # Next iteration cannot replace its numerical oracle with the last candidate.
    profile(store, tmp_path, 'second')
    changed_q = json.loads(store.artifact(inputs['quality_inputs'])); changed_q['baseline'] = changed_q['candidate']
    changed_p = json.loads(store.artifact(inputs['performance_inputs'])); changed_p['baseline'] = changed_p['candidate']
    newer_snapshot = store.put(b'second candidate fixture')
    changed_q['candidate'] = {**changed_q['candidate'], 'candidate_snapshot': newer_snapshot}
    changed_p['candidate'] = {**changed_p['candidate'], 'candidate_snapshot': newer_snapshot}
    newer = optimization.plan(store, 't', {'analysis': model_loop.status(store, 't')['analysis'], 'observation': 'new profile',
        'hypothesis': 'new candidate', 'target': 'gemm', 'validation': ['fixed oracle']})
    with pytest.raises(FlowError, match='initial numerical oracle'):
        step(store, 'evaluate', plan=newer['plan'], route='gemm', quality_inputs=retain(store, changed_q), performance_inputs=retain(store, changed_p))


def test_regression_requires_rollback_and_no_gain_stops(store, tmp_path):
    start(store, max_no_gain=1)
    step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    initial = step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    plan = profile(store, tmp_path)
    state = step(store, 'evaluate', plan=plan['plan'], route='native', **candidate(store, qi, pi, gain=False))
    assert state['stage'] == 'rollback' and state['best'] == initial['best']
    with pytest.raises(FlowError, match='invalid for loop stage'):
        step(store, 'stop', reason='cannot stop before rollback')
    restored = {**pi['baseline'], 'candidate_snapshot': initial['best']['snapshot']}
    state = step(store, 'rollback', verification=restore(store, restored))
    assert state['stage'] == 'stopped' and state['stop_reason'] == 'no-gain-budget'
    assert state['iterations'][0]['decision'] == 'rejected'


def test_stale_steps_and_context_reset_do_not_replay(store):
    start(store)
    with pytest.raises(FlowError, match='stale steps'):
        model_loop.advance(store, 't', {'revision': 999, 'action': 'stop', 'reason': 'fixture'})
    store.change_context('t', {'model': 'changed'})
    with pytest.raises(FlowError, match='stale'):
        model_loop.status(store, 't')


def test_prediction_label_without_backend_execution_is_not_accepted(store):
    start(store)
    row = simulated(store)
    value = json.loads(store.artifact(row['artifact'])); del value['execution']
    row['artifact'] = retain(store, value)
    with pytest.raises(FlowError, match='backend execution'):
        step(store, 'select-strategy', candidates=[row])


def test_review_rejection_and_implementation_failure_remain_auditable(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    step(store, 'evaluate', plan=plan['plan'], route='fusion', **candidate(store, qi, pi))
    rejected = step(store, 'reject', reason='Independent reviewer found unsupported long-context guard')
    assert rejected['stage'] == 'rollback'
    verification = restore(store, pi['baseline'])
    state = step(store, 'rollback', verification=verification)
    assert state['iterations'][0]['rejection_reason'].startswith('Independent reviewer')
    profile(store, tmp_path, 'after-rollback')
    failure = retain(store, {'context': store.task('t')['context'], 'status': 'fail', 'evidence': [store.put(b'compile error')]})
    step(store, 'reject', reason='HIP compilation failed', failure=failure)
    state = step(store, 'rollback', verification=restore(store, pi['baseline']))
    assert state['stage'] == 'stopped' and len(state['iterations']) == 2
    assert state['iterations'][1]['failure'] == failure


def test_baseline_missing_feature_routes_adaptation_and_skipped_restore_is_blocked(store):
    start(store); step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    qi['candidate']['features']['streaming'] = False
    state = step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    assert state['stage'] == 'adaptation' and state['initial'] is None


def test_restore_cannot_skip_required_checks(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    step(store, 'evaluate', plan=plan['plan'], route='gemm', **candidate(store, qi, pi, gain=False))
    restored = {**pi['baseline'], 'skipped_required': ['long-context']}
    with pytest.raises(FlowError, match='Verify restored'):
        step(store, 'rollback', verification=restore(store, restored))
    assert model_loop.status(store, 't')['stage'] == 'rollback'


@pytest.mark.parametrize('tamper', ['summary', 'arguments', 'backend'])
def test_simulation_cannot_relabel_successful_backend_receipt(store, tamper):
    start(store)
    row = simulated(store)
    value = json.loads(store.artifact(row['artifact']))
    if tamper == 'summary':
        value['summary']['throughput_tok_s'] = 100000
    elif tamper == 'arguments':
        value['input']['arguments']['seq_len'] = 1
    else:
        value['backend_output']['result']['memory_feasible'] = False
    row['artifact'] = retain(store, value)
    with pytest.raises(FlowError, match='altered|effective arguments|retained backend stdout'):
        step(store, 'select-strategy', candidates=[row])


def test_old_baseline_and_old_restore_cannot_prove_current_rollback(store, tmp_path):
    qi, pi = baseline(store)
    old_restore = restore(store, pi['baseline'])
    plan = profile(store, tmp_path)
    step(store, 'evaluate', plan=plan['plan'], route='gemm', **candidate(store, qi, pi, gain=False))
    for proof in (retain(store, pi['baseline']), old_restore):
        with pytest.raises(FlowError, match='fresh completed'):
            step(store, 'rollback', verification=proof)
    assert step(store, 'rollback', verification=restore(store, pi['baseline']))['stage'] == 'profile'


def test_profile_returns_native_implementation_to_model_optimizer(store, tmp_path):
    baseline(store)
    assert model_loop.status(store, 't')['next']['skill'] == 'hcu-infer-analyze'
    plan = profile(store, tmp_path)
    state = model_loop.status(store, 't')
    assert state['next'] == {'action': 'plan-and-implement', 'skill': 'hcu-infer-model-optimize'}
    snapshot = store.put(b'native configuration candidate')
    state = step(store, 'explore', plan=plan['plan'], route='native', candidate_snapshot=snapshot,
                 summary='Change native configuration',
                 changes=[{'path': 'launch.json', 'description': 'fixture native option'}], evidence=[snapshot])
    assert state['pending']['route'] == 'native'
    assert state['pending']['skill'] == 'hcu-infer-model-optimize'
    assert state['next']['skill'] == 'hcu-infer-model-optimize'
