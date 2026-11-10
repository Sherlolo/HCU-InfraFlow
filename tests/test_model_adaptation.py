"""CPU protocol tests, not new-model or hardware validation."""
import copy
import json
import sys

import pytest

from hcu_infra_agent import model_adaptation as adaptation
from hcu_infra_agent.core import FlowError, Store
from hcu_infra_agent.evidence import retain


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / 'store')
    store.create({'schema_version': 1, 'task_id': 'new-model', 'mode': 'adapt',
                  'objective': 'CPU adaptation fixture', 'context': {'model': 'fixture'},
                  'permissions': ['execute']})
    lock = {key: store.put(('immutable fixture ' + key).encode()) for key in adaptation.LOCK_FIELDS}
    gaps = [{'id': name, 'capability': name, 'status': 'supported', 'required': True,
             'target': 'fixture.' + name, 'contract': 'fixture contract', 'fallback': 'eager',
             'kind': 'framework'} for name in adaptation.CAPABILITIES]
    request = {'framework': 'sglang', 'release_lock': lock, 'gaps': gaps, 'required_features': ['streaming']}
    return store, request, tmp_path


def evidence(setup, *, code=0):
    store, request, directory = setup
    planned = adaptation.plan(store, 'new-model', request)
    snapshot = store.put(b'candidate fixture source')
    task = store.task('new-model')
    lease = store.lease('cpu-fixture', 'adaptation-fixture', 300)
    run = adaptation.run(store, 'new-model', {
        'plan': planned['plan'], 'candidate_snapshot': snapshot, 'tests': planned['record']['required_tests'],
        'operation': 'adaptation-fixture', 'lease': lease,
        'card': {'schema_version': 1, 'backend': 'local', 'cwd': str(directory),
                 'argv': [sys.executable, '-c', 'print("CPU assertion fixture");raise SystemExit(' + str(code) + ')'],
                 'timeout_seconds': 10, 'basis': 'CPU contract fixture; no model or GPU evidence'}})
    logs = run['execution']['evidence']
    tests = [retain(store, {'name': name, 'context': task['context'], 'candidate_snapshot': snapshot,
              'status': 'pass', 'executed': 1, 'candidate_path_exercised': True,
              'operation': 'adaptation-fixture', 'evidence': logs}) for name in planned['record']['required_tests']]
    identities = {key: request['release_lock']['weights' if key == 'model' else key]
                  for key in ('model', 'tokenizer', 'quantization', 'workload', 'driver')}
    measurement = {'context': task['context'], 'candidate_snapshot': snapshot, 'status': 'pass',
                   'executed': 1, 'candidate_path_exercised': True, 'evidence': logs,
                   'identities': identities, 'samples': [{'id': 'fixed', 'text': 'CPU fixture'}],
                   'features': {'streaming': True}}
    quality_inputs = {'contract': {'context': task['context'], 'identities': identities,
                                  'atol': 0, 'rtol': 0, 'tolerance_basis': 'exact CPU fixture',
                                  'required_features': ['streaming']},
                      'baseline': copy.deepcopy(measurement), 'candidate': measurement}
    check = {'plan': planned['plan'], 'candidate_snapshot': snapshot, 'test_results': tests,
             'quality_inputs': retain(store, quality_inputs), 'gap_resolutions': {}}
    return planned, check, quality_inputs


def test_actual_cpu_command_and_complete_matrix_permit_new_baseline(setup):
    store, _, _ = setup
    _, check, _ = evidence(setup)
    result = adaptation.evaluate(store, 'new-model', check)
    assert result['status'] == 'pass'
    assert result['report']['ready_for_baseline'] is True
    assert result['report']['accepted_by_flow'] is False
    with store.db() as db:
        assert db.execute("SELECT 1 FROM reports WHERE kind='performance'").fetchone() is None


def test_missing_matrix_row_and_failed_command_never_pass(setup):
    store, _, _ = setup
    _, check, _ = evidence(setup, code=1)
    check['test_results'].pop()
    result = adaptation.evaluate(store, 'new-model', check)
    assert result['status'] == 'fail'
    assert any('missing-test' in x for x in result['report']['failures'])
    assert any('execution-not-complete' in x for x in result['report']['failures'])


def test_quality_regression_replaces_previous_pass(setup):
    store, _, _ = setup
    _, check, inputs = evidence(setup)
    adaptation.evaluate(store, 'new-model', check)
    inputs['candidate']['samples'][0]['text'] = 'regressed'
    check['quality_inputs'] = retain(store, inputs)
    result = adaptation.evaluate(store, 'new-model', check)
    assert result['status'] == 'fail'
    with store.db() as db:
        reports = store.current_reports(db, 'new-model', store.task('new-model')['context'])
    assert reports['model-adaptation']['result'] == 'fail'


@pytest.mark.parametrize('fault', ['foreign-operation', 'snapshot', 'identity', 'duplicate'])
def test_rejects_misattributed_evidence(setup, fault):
    store, _, _ = setup
    _, check, inputs = evidence(setup)
    row = json.loads(store.artifact(check['test_results'][0]))
    if fault == 'foreign-operation':
        row['operation'] = 'never-ran'
    elif fault == 'snapshot':
        row['candidate_snapshot'] = store.put(b'other source')
    elif fault == 'identity':
        inputs['contract']['identities']['model'] = 'other weights'
        check['quality_inputs'] = retain(store, inputs)
    else:
        check['test_results'].append(check['test_results'][0])
    check['test_results'][0] = retain(store, row)
    with pytest.raises(FlowError):
        adaptation.evaluate(store, 'new-model', check)


def test_replaced_plan_and_context_roundtrip_rejected(setup):
    store, request, _ = setup
    _, check, _ = evidence(setup)
    replacement = copy.deepcopy(request)
    replacement['risk_pairs'] = ['graph-cache']
    adaptation.plan(store, 'new-model', replacement)
    with pytest.raises(FlowError, match='replaced'):
        adaptation.evaluate(store, 'new-model', check)
    original = copy.deepcopy(store.task('new-model')['spec']['context'])
    store.change_context('new-model', {'model': 'another'})
    store.change_context('new-model', original)
    with pytest.raises(FlowError, match='epoch'):
        adaptation.evaluate(store, 'new-model', check)


def test_missing_kernel_creates_explicit_correctness_handoff(setup):
    store, request, _ = setup
    request['gaps'][3].update(status='missing', kind='kernel', operator_backend='triton')
    planned, check, _ = evidence(setup)
    assert planned['record']['operator_handoffs'][0]['backend'] == 'triton'
    result = adaptation.evaluate(store, 'new-model', check)
    assert result['status'] == 'fail'
    assert 'unresolved-gap:attention' in result['report']['failures']


def test_operation_cannot_be_rebound_to_another_candidate(setup):
    store, _, directory = setup
    planned, _, _ = evidence(setup)
    with pytest.raises(FlowError, match='already bound'):
        adaptation.run(store, 'new-model', {
            'plan': planned['plan'], 'candidate_snapshot': store.put(b'other candidate'),
            'tests': ['load'], 'operation': 'adaptation-fixture',
            'card': {}, 'lease': {}})


def test_assertions_cannot_replace_actual_command_logs(setup):
    store, _, _ = setup
    _, check, _ = evidence(setup)
    row = json.loads(store.artifact(check['test_results'][0]))
    row['evidence'] = [store.put(b'unrelated logs')]
    check['test_results'][0] = retain(store, row)
    with pytest.raises(FlowError, match='actual operation logs'):
        adaptation.evaluate(store, 'new-model', check)


@pytest.mark.parametrize('flag,value', [('synthetic', True), ('hardware_executed', False),
                                       ('qualification', 'simulation-prediction')])
def test_explicit_synthetic_outputs_cannot_qualify_adaptation(setup, flag, value):
    store, _, _ = setup
    _, check, inputs = evidence(setup)
    inputs['candidate'][flag] = value
    check['quality_inputs'] = retain(store, inputs)
    with pytest.raises(FlowError, match='Synthetic or predicted'):
        adaptation.evaluate(store, 'new-model', check)


def test_source_only_kernel_resolution_cannot_close_missing_operator(setup):
    store, request, _ = setup
    request['gaps'][3].update(status='missing', kind='kernel', operator_backend='triton')
    _, check, _ = evidence(setup)
    check['gap_resolutions']['attention'] = retain(store, {
        'gap_id': 'attention', 'context': store.task('new-model')['context'],
        'candidate_snapshot': check['candidate_snapshot'], 'status': 'pass', 'executed': 1,
        'candidate_path_exercised': True, 'evidence': [store.put(b'source-only unsupported claim')]})
    with pytest.raises(FlowError, match='operator_integration'):
        adaptation.evaluate(store, 'new-model', check)


@pytest.mark.parametrize('fault', ['floating-lock', 'coverage', 'required-na'])
def test_incomplete_release_contract_rejected(setup, fault):
    store, request, _ = setup
    if fault == 'floating-lock':
        request['release_lock']['engine'] = 'main'
    elif fault == 'coverage':
        request['gaps'].pop()
    else:
        request['gaps'][0]['status'] = 'not-applicable'
    with pytest.raises(FlowError):
        adaptation.plan(store, 'new-model', request)
