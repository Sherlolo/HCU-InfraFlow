"""Real CPU subprocess handoff across adaptation, operator and framework modules.

The tiny list operator exercises orchestration only. It is not a Triton kernel,
new-model implementation, GPU correctness result or performance measurement.
"""
import json
import sys
from pathlib import Path

from hcu_infra_agent import model_adaptation, operators
from hcu_infra_agent.cli import main
from hcu_infra_agent.core import Store
from hcu_infra_agent.evidence import retain


def test_adaptation_missing_kernel_develop_integrate_and_resume_baseline(tmp_path, capsys):
    workspace = tmp_path / 'store'
    store = Store(workspace)
    store.create({'schema_version': 1, 'task_id': 'cross-module', 'mode': 'adapt',
                  'objective': 'CPU integration protocol fixture', 'context': {'model': 'tiny CPU fixture'},
                  'permissions': ['execute']})
    task = store.task('cross-module')
    lock = {name: store.put(('CPU fixture immutable ' + name).encode())
            for name in model_adaptation.LOCK_FIELDS}
    gaps = [{'id': name, 'capability': name, 'status': 'supported', 'required': True,
             'target': 'engine.forward', 'contract': 'CPU list x+1 fixture', 'fallback': 'Python reference',
             'kind': 'framework'} for name in model_adaptation.CAPABILITIES]
    gaps[3].update(status='missing', kind='kernel', operator_backend='triton')
    adaptation_request = {'framework': 'sglang', 'release_lock': lock, 'gaps': gaps,
                          'required_features': ['streaming']}

    def cli(command, request):
        path = tmp_path / (command + '.json')
        path.write_text(json.dumps(request))
        result = main(['--workspace', str(workspace), command, 'cross-module', str(path)])
        output = json.loads(capsys.readouterr().out)
        assert result == 0, output
        return output

    adaptation = cli('model-adapt-plan', adaptation_request)
    assert adaptation['record']['operator_handoffs'][0]['gap_id'] == 'attention'
    skill = tmp_path / 'SKILL.md'
    skill.write_text('---\nname: kernel-triton-baseline\ndescription: CPU runner fixture only\n---\n')
    operator = cli('operator-plan', {
        'adaptation_plan': adaptation['plan'], 'gap_id': 'attention', 'kind': 'triton',
        'target': 'engine.forward', 'existing_path': 'engine.py', 'observation': 'Missing x+1 fixture implementation',
        'skill_path': str(skill), 'shape_contract': {'shapes': [[3]], 'dtype': 'int64', 'layout': 'list',
        'phase': 'decode', 'semantics': 'x+1 CPU fixture', 'tolerance': 'exact integer equality'}})
    lease = store.lease('cpu-fixture', 'integration-test', 300)
    target = tmp_path / 'candidate'
    target.mkdir()
    (target / 'engine.py').write_text('def forward(values):\n    raise NotImplementedError("fixture missing operator")\n')

    def card(source, *args):
        return {'schema_version': 1, 'backend': 'local', 'cwd': str(target),
                'argv': [sys.executable, '-c', source, *args], 'timeout_seconds': 10,
                'basis': 'CPU-only cross-module fixture; no GPU validation'}

    development = cli('operator-dispatch', {
        'plan': operator['plan'], 'lease': lease, 'operation': 'develop-cpu',
        'card': card('import sys,json,os\nfrom pathlib import Path\n'
                     'assert "kernel-triton-baseline" in sys.argv[1]\n'
                     'Path("candidate_kernel.py").write_text("def add_one(values):\\n    return [x+1 for x in values]\\n")\n'
                     'Path("candidate_engine.py").write_text("from kernel import add_one\\ndef forward(values):\\n    return add_one(values)\\n")\n'
                     'sys.path.insert(0,sys.argv[2])\n'
                     'from hcu_infra_agent.core import Store\n'
                     'from hcu_infra_agent.execution import snapshot\n'
                     'from hcu_infra_agent.evidence import retain\n'
                     'store=Store(sys.argv[3])\n'
                     'manifest=snapshot(store,Path.cwd(),["candidate_kernel.py","candidate_engine.py"])\n'
                     'manifest.pop("snapshot_id")\n'
                     'candidate=retain(store,manifest)\n'
                     'task=store.task("cross-module")\n'
                     'print(json.dumps({"plan":os.environ["HCU_INFRA_OPERATOR_PLAN"],"context":task["context"],'
                     '"context_epoch":task["context_epoch"],"candidate_snapshot":candidate}))',
                     '{operator_prompt}', str(Path(__file__).resolve().parents[1] / 'src'), str(workspace))})
    assert development['hardware_validated'] is False
    candidate = json.loads(store.artifact(development['execution']['evidence'][0]))['candidate_snapshot']
    assertion_log = store.put(b'CPU list reference: [-2, 0, 3] -> [-1, 1, 4]')
    receipt = {'schema_version': 1, 'plan': operator['plan'], 'framework': 'sglang',
               'candidate_snapshot': candidate, 'context': task['context'], 'context_epoch': task['context_epoch'],
               'executed': 4, 'candidate_path_exercised': True,
               'checks': {key: True for key in operators.CHECKS}, 'evidence': [assertion_log]}
    integration = cli('operator-integrate', {
        'plan': operator['plan'], 'development': development['artifact'], 'framework': 'sglang',
        'candidate_snapshot': candidate, 'operation': 'integrate-cpu', 'lease': lease,
        'cards': {
            'apply': card('from pathlib import Path\n'
                          'Path("engine.before").write_bytes(Path("engine.py").read_bytes())\n'
                          'Path("kernel.py").write_bytes(Path("candidate_kernel.py").read_bytes())\n'
                          'Path("engine.py").write_bytes(Path("candidate_engine.py").read_bytes())'),
            'verify': card('import json,sys\nimport engine,kernel\n'
                           'assert engine.add_one is kernel.add_one\n'
                           'assert engine.forward([-2,0,3]) == [-1,1,4]\n'
                           'assert engine.forward([]) == []\n'
                           'print(sys.argv[1])', json.dumps(receipt)),
            'rollback': card('from pathlib import Path\n'
                             'Path("engine.py").write_bytes(Path("engine.before").read_bytes())\n'
                             'Path("kernel.py").unlink(missing_ok=True)')}})
    assert integration['integration_verified'] is True
    assert integration['accepted_by_flow'] is False
    tests = adaptation['record']['required_tests']
    # Tiny explicit assertions stand in for each test adapter in this CPU protocol
    # fixture; the real skill requires model-specific tests for each capability.
    validation = cli('model-adapt-run', {
        'plan': adaptation['plan'], 'candidate_snapshot': candidate, 'tests': tests,
        'operation': 'model-tests-cpu', 'lease': lease,
        'card': card('import json,sys\nimport engine\n'
                     'assert engine.forward([-2,0,3]) == [-1,1,4]\n'
                     'print(json.dumps({"qualification":"CPU-protocol-fixture", "tests":json.loads(sys.argv[1]), "output":[-1,1,4]}))',
                     json.dumps(tests))})
    logs = validation['execution']['evidence']
    outputs = json.loads(store.artifact(logs[0]))
    test_results = [retain(store, {'name': name, 'context': task['context'], 'candidate_snapshot': candidate,
                    'status': 'pass', 'executed': 1, 'candidate_path_exercised': True,
                    'operation': 'model-tests-cpu', 'evidence': logs, 'qualification': 'CPU-protocol-fixture'})
                    for name in tests]
    identities = {key: lock['weights' if key == 'model' else key] for key in ('model','tokenizer','quantization','workload','driver')}
    measured = {'context': task['context'], 'candidate_snapshot': candidate, 'status': 'pass', 'executed': 1,
                'candidate_path_exercised': True, 'evidence': logs, 'identities': identities,
                'features': {'streaming': True}, 'samples': [{'id': 'cpu-fixed', 'values': outputs['output']}]}
    reference = {**measured, 'samples': [{'id': 'cpu-fixed', 'values': [x + 1 for x in [-2, 0, 3]]}],
                 'evidence': [assertion_log]}
    quality = retain(store, {'contract': {'context': task['context'], 'identities': identities, 'atol': 0, 'rtol': 0,
                        'tolerance_basis': 'CPU integer fixture', 'required_features': ['streaming']},
                        'baseline': reference, 'candidate': measured})
    resolved = retain(store, {'gap_id': 'attention', 'context': task['context'], 'candidate_snapshot': candidate,
                             'status': 'pass', 'executed': 1, 'candidate_path_exercised': True,
                             'operator_integration': integration['artifact'], 'evidence': [integration['artifact'], *logs]})
    result = cli('model-adapt-check', {'plan': adaptation['plan'], 'candidate_snapshot': candidate,
                 'test_results': test_results, 'quality_inputs': quality, 'gap_resolutions': {'attention': resolved}})
    assert result['report']['ready_for_baseline'] is True
    assert result['report']['accepted_by_flow'] is False
    assert Path(target / 'engine.before').is_file()
    with store.db() as db:
        assert db.execute('SELECT count(*) FROM operations').fetchone()[0] == 4
        assert db.execute("SELECT 1 FROM reports WHERE kind='performance'").fetchone() is None
