"""Limited-repeat policy tests use synthetic fixtures, not hardware evidence."""
import copy
import json

import pytest

from hcu_infra_agent import benchmark, flow, model_loop, optimization, quality
from hcu_infra_agent.core import FlowError, Store
from hcu_infra_agent.evidence import retain
from test_model_loop import (
    start, step, simulated, measurements, baseline as start_baseline,
    profile as capture_profile, candidate as make_candidate,
)


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / 'store')
    store.create({'schema_version': 1, 'task_id': 't', 'mode': 'optimize', 'objective': 'Fixed serving loop',
                  'context': {'model': 'fixture', 'workload': 'w', 'driver': 'fixture'}, 'permissions': ['execute']})
    flow.start(store, 't', {'acceptance': {'quality': 'fixed oracle', 'performance': 'repeatable gain'}})
    return store


def _single_repeat(pi):
    pi = copy.deepcopy(pi)
    for scenario in pi['baseline']['scenarios'].values():
        for key, values in scenario.items():
            scenario[key] = values[:1]
    for scenario in pi['candidate']['scenarios'].values():
        for key, values in scenario.items():
            scenario[key] = values[:1]
    pi['contract']['min_repeats'] = 1
    return pi


def test_single_repeat_reports_limit_and_zero_stdev(store):
    pi = _single_repeat(measurements(store)[1])
    result = quality.compare_performance(**pi)
    assert result['status'] == 'pass' and result['limited_repeats'] is True
    assert result['metrics']['decode:throughput_tok_s']['baseline_stdev'] == 0.0


def test_default_one_repeat_baseline(store):
    start(store)
    step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    result = step(store, 'baseline', quality_inputs=retain(store, qi),
                  performance_inputs=retain(store, _single_repeat(pi)))
    assert result['stage'] == 'profile'
    assert result['policy']['performance_repeats'] == 1


def test_explicit_three_repeat_policy_rejects_one_repeat(store):
    start(store, performance_repeats=3)
    step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    for side in ('baseline', 'candidate'):
        for scenario in pi[side]['scenarios'].values():
            for key in scenario:
                scenario[key] = scenario[key][:1]
    pi['contract']['min_repeats'] = 3
    with pytest.raises(FlowError, match='matched repeats'):
        step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))


def _single_repeat_experiment(store, snapshot):
    return retain(store, {
        'context': store.task('t')['context'],
        'correctness': {
            'context': store.task('t')['context'], 'candidate_snapshot': snapshot,
            'candidate_path_exercised': True, 'executed': 1, 'status': 'pass',
            'profiler_off': True, 'measurement_protocol': 'single-repeat fixture',
            'evidence': [store.put(b'fixture correctness')],
        },
        'baseline_times': [10], 'candidate_times': [9],
        'min_repeats': 1,
    })


def test_single_repeat_candidate_can_complete_review_and_keep(store, tmp_path):
    start(store)
    step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    step(store, 'baseline', quality_inputs=retain(store, qi),
         performance_inputs=retain(store, _single_repeat(pi)))
    plan = capture_profile(store, tmp_path)
    inputs = make_candidate(store, qi, pi, gain=True)
    candidate_pi = _single_repeat(json.loads(store.artifact(inputs['performance_inputs'])))
    inputs['performance_inputs'] = retain(store, candidate_pi)
    evaluated = step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)
    assert evaluated['stage'] == 'review'
    result = optimization.evaluate(store, 't', {'plan': plan['plan'], **inputs})
    assert result['status'] == 'pass'
    next_step = flow.next_step(store, 't')
    snapshot = result['candidate_snapshot']
    experiment = _single_repeat_experiment(store, snapshot)
    submitted = flow.submit(store, 't', {
        'author': 'implementer', 'context': store.task('t')['context'],
        'goal': next_step['goal'], 'snapshot': snapshot, 'summary': 'Single-repeat candidate measured',
        'reports': result['reports'], 'target': 'iterate',
        'evidence': [inputs['quality_inputs'], inputs['performance_inputs']],
        'profile_evidence': plan['record']['profile_evidence'], 'experiment': experiment,
    })
    assert submitted['status'] == 'awaiting-review', submitted
    decision = flow.next_step(store, 't')
    review = {key: decision[key] for key in ('round', 'candidate', 'goal', 'context')}
    review.update(reviewer='independent', verdict='accept', summary='Checked limited-repeat evidence',
                  findings=[], acceptance={'quality': 'met', 'performance': 'met'},
                  progress='advanced', full_alignment=True,
                  evidence=[inputs['quality_inputs'], inputs['performance_inputs'], experiment])
    flow.review(store, 't', review)
    flow.advance(store, 't')
    kept = model_loop.advance(store, 't', {'revision': model_loop.status(store, 't')['revision'],
                                          'action': 'keep', 'flow_round': decision['round']})
    assert kept['best']['snapshot'] == snapshot
    assert kept['iterations'][0]['decision'] == 'kept'


def test_acceptance_reserve_blocks_new_candidate(store, tmp_path, monkeypatch):
    start_baseline(store)
    plan = capture_profile(store, tmp_path)
    monkeypatch.setattr(model_loop, '_execution_budget', lambda task, state: {
        'remaining_seconds': 0, 'acceptance_reserve_active': True,
    })
    snapshot = store.put(b'candidate source')
    with pytest.raises(FlowError, match='Acceptance reserve active'):
        step(store, 'explore', plan=plan['plan'], route='gemm', candidate_snapshot=snapshot,
             summary='Should not start', changes=[{'path': 'kernel.py', 'description': 'new candidate'}],
             evidence=[snapshot])


def test_generic_benchmark_accepts_one_repeat(store):
    context = store.task('t')['context']
    ids = {key: 'fixed-' + key for key in ('model', 'tokenizer', 'quantization', 'workload', 'driver')}
    benchmark.validate_profile({
        'base_url': 'http://127.0.0.1:11010', 'model': 'fixture',
        'context': context, 'candidate_snapshot': 'snapshot', 'identities': ids,
        'repeats': 1, 'request_timeout': 30,
        'scenarios': [{'name': 'decode', 'prompts': ['hello'], 'output_tokens': 1, 'concurrency': 1}],
    })
