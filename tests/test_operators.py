"""CPU-only operator orchestration: actual subprocesses, no GPU claims."""
import json
import sys

import pytest

from hcu_infra_agent import operators
from hcu_infra_agent.core import FlowError, Store
from hcu_infra_agent.evidence import retain


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / 'store')
    store.create({'schema_version': 1, 'task_id': 'op', 'mode': 'optimize', 'objective': 'profile-driven fixture',
                  'context': {'model': 'fixture', 'engine': 'fixture'}, 'permissions': ['execute']})
    analysis = store.report('op', 'analysis', {'context': store.task('op')['context'], 'status': 'pass',
                           'executed': 1, 'evidence': [store.put(b'CPU synthetic profile fixture')]})['artifact']
    skill = tmp_path / 'SKILL.md'
    skill.write_text('---\nname: gemm-tuning\ndescription: fixture\n---\nCPU fixture only\n')
    request = {'analysis': analysis, 'kind': 'gemm', 'target': 'linear', 'observation': 'fixture GEMM hotspot',
               'existing_path': 'engine/linear.py:forward', 'skill_path': str(skill),
               'shape_contract': {'shapes': [[1, 16, 16]], 'dtype': 'bf16', 'layout': 'row-major',
                                  'phase': 'decode', 'semantics': 'Y=XW', 'tolerance': 'exact fixture'}}
    lease = store.lease('fixture-resource', 'operator-test', 300)
    return store, request, lease, tmp_path


def card(tmp_path, source, *args):
    return {'schema_version': 1, 'backend': 'local', 'cwd': str(tmp_path),
            'argv': [sys.executable, '-c', source, *args], 'timeout_seconds': 5,
            'basis': 'CPU-only operator regression fixture'}


def dispatched(setup):
    store, request, lease, directory = setup
    plan = operators.plan(store, 'op', request)
    snapshot = store.put(b'CPU fixture candidate source')
    receipt = {'plan': plan['plan'], 'context': store.task('op')['context'], 'context_epoch': 0,
               'candidate_snapshot': snapshot}
    result = operators.dispatch(store, 'op', {'plan': plan['plan'], 'lease': lease, 'operation': 'develop',
                                'card': card(directory, 'import sys; assert "gemm-tuning" in sys.argv[1]; print(sys.argv[2])',
                                             '{operator_prompt}', json.dumps(receipt))})
    assert result['status'] == 'complete' and result['hardware_validated'] is False
    assert json.loads(store.artifact(result['execution']['evidence'][0])) == receipt
    return plan, result


def integration_request(setup, good=True):
    store, request, lease, directory = setup
    plan, development = dispatched(setup)
    snapshot = store.put(b'CPU fixture candidate source')
    receipt = {'schema_version': 1, 'plan': plan['plan'], 'framework': 'sglang', 'candidate_snapshot': snapshot,
               'context': store.task('op')['context'], 'context_epoch': 0, 'executed': 1,
               'candidate_path_exercised': good, 'checks': {key: True for key in operators.CHECKS},
               'evidence': [store.put(b'CPU fixture dispatch checks')], 'failures': []}
    return {'plan': plan['plan'], 'development': development['artifact'], 'framework': 'sglang',
            'candidate_snapshot': snapshot, 'operation': 'integrate', 'lease': lease,
            'cards': {
                'apply': card(directory, "from pathlib import Path; Path('installed').write_text('candidate')"),
                'verify': card(directory, 'import sys; print(sys.argv[1])', json.dumps(receipt)),
                'rollback': card(directory, "from pathlib import Path; Path('installed').unlink(missing_ok=True)")}}


def test_profile_route_and_bound_skill_change(setup):
    store, request, lease, directory = setup
    planned = operators.plan(store, 'op', request)
    (directory / 'SKILL.md').write_text('changed')
    with pytest.raises(FlowError, match='changed'):
        operators.dispatch(store, 'op', {'plan': planned['plan'], 'lease': lease, 'operation': 'bad',
                            'card': card(directory, 'print(1)', '{operator_prompt}')})
    request['kind'] = 'tilelang'
    with pytest.raises(FlowError, match='TileLang'):
        operators.plan(store, 'op', request)


def test_integration_executes_and_retry_is_idempotent(setup):
    store, _, _, directory = setup
    request = integration_request(setup)
    result = operators.integrate(store, 'op', request)
    assert result['integration_verified'] is True and result['accepted_by_flow'] is False
    assert (directory / 'installed').read_text() == 'candidate'
    assert operators.integrate(store, 'op', request)['artifact'] == result['artifact']
    with store.db() as db:
        assert db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] == 3


@pytest.mark.parametrize('failure', ['dispatch', 'empty-output', 'apply', 'wrong-identity'])
def test_failed_integration_rolls_back(setup, failure):
    store, _, _, directory = setup
    request = integration_request(setup, good=failure != 'dispatch')
    if failure == 'empty-output':
        request['cards']['verify'] = card(directory, 'pass')
    elif failure == 'apply':
        request['cards']['apply'] = card(directory, "from pathlib import Path; Path('installed').write_text('partial'); raise RuntimeError('failure')")
    elif failure == 'wrong-identity':
        receipt = json.loads(request['cards']['verify']['argv'][-1]); receipt['candidate_snapshot'] = 'wrong'
        request['cards']['verify']['argv'][-1] = json.dumps(receipt)
    result = operators.integrate(store, 'op', request)
    assert result['status'] == 'failed' and not result['integration_verified']
    assert result['executions']['rollback']['status'] == 'complete'
    assert not (directory / 'installed').exists()
    assert operators.integrate(store, 'op', request)['artifact'] == result['artifact']


def test_unknown_outcome_does_not_rollback(setup, monkeypatch):
    store, _, _, _ = setup
    request = integration_request(setup)
    calls = []
    def unknown(*args, **kwargs):
        calls.append(args[2])
        return {'status': 'unknown', 'operation': args[2], 'evidence': []}
    monkeypatch.setattr(operators, 'run_command', unknown)
    result = operators.integrate(store, 'op', request)
    assert result['status'] == 'incomplete' and calls == ['integrate-apply']
    assert 'Reconcile' in result['reason']


def test_reject_stale_profile_and_mixed_targets(setup):
    store, request, lease, directory = setup
    integration = integration_request(setup)
    integration['cards']['rollback']['cwd'] = str(directory / 'elsewhere')
    with pytest.raises(FlowError, match='same framework'):
        operators.integrate(store, 'op', integration)
    store.report('op', 'analysis', {'context': store.task('op')['context'], 'status': 'pass', 'executed': 1,
                                  'evidence': [store.put(b'new capture')]})
    with pytest.raises(FlowError, match='stale|replaced'):
        operators.plan(store, 'op', request)


def test_missing_kernel_adaptation_needs_no_fake_profile(setup):
    store, request, lease, directory = setup
    task = store.task('op')
    adaptation = retain(store, {'module': 'model-adaptation-plan', 'task': 'op', 'context': task['context'],
                                'context_epoch': 0, 'gaps': [{'id': 'attention', 'kind': 'kernel',
                                'status': 'missing', 'operator_backend': 'hip'}]})
    with store.db() as db:
        store.event(db, 'op', 'adaptation-plan-recorded', {'artifact': adaptation})
    request.pop('analysis')
    request.update(adaptation_plan=adaptation, gap_id='attention', kind='hip')
    (directory / 'SKILL.md').write_text('---\nname: kernel-hip-baseline\ndescription: fixture\n---\n')
    result = operators.plan(store, 'op', request)
    assert result['record']['skill_name'] == 'kernel-hip-baseline'
    assert result['record']['hardware_validated'] is False


@pytest.mark.parametrize('fault', ['fabricated-operation', 'different-candidate', 'unrelated-command'])
def test_integration_requires_real_bound_development(setup, fault):
    store, _, _, directory = setup
    request = integration_request(setup)
    development = json.loads(store.artifact(request['development']))
    if fault == 'fabricated-operation':
        development['execution']['operation'] = 'never-executed'
        request['development'] = retain(store, development)
    elif fault == 'different-candidate':
        request['candidate_snapshot'] = store.put(b'unproduced candidate')
    else:
        command = json.loads(store.artifact(development['command_card']))
        command['argv'][-1] = 'substituted input'
        development['command_card'] = retain(store, command)
        request['development'] = retain(store, development)
    with pytest.raises(FlowError, match='actual|bound'):
        operators.integrate(store, 'op', request)
    assert not (directory / 'installed').exists()
