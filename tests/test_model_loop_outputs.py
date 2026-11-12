"""Exercise failure gates and portable dossiers with synthetic CPU fixtures."""
import contextlib
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import pytest
from hcu_infra_agent import model_loop, optimization, optimization_output, profiling, quality
from hcu_infra_agent.core import FlowError
from hcu_infra_agent.evidence import retain
from hcu_infra_agent.quality_coverage import policy
from optimization_fixtures import after_profile
from test_model_loop import store, baseline, candidate, profile, step, restore, measurements, start, simulated, independent_review


def output_root(store):
    return store.root/'modules/model-loop/t'


def test_initial_quality_requires_long_and_concurrent_cases(store):
    start(store)
    step(store, 'select-strategy', candidates=[simulated(store)])
    qi, pi = measurements(store)
    for side in ('baseline', 'candidate'):
        qi[side]['samples'] = qi[side]['samples'][:1]
    state = step(store, 'baseline', quality_inputs=retain(store, qi), performance_inputs=retain(store, pi))
    assert state['stage'] == 'adaptation' and state['initial'] is None
    failure = json.loads(store.artifact(state['baseline_failure']))
    assert 'candidate:missing-coverage:long-concurrent' in failure['quality']['failures']
    assert (output_root(store)/'baseline-failures/0001/REPORT.md').is_file()


@pytest.mark.parametrize('fault', ['sequential', 'input-substitution', 'empty-output'])
def test_quality_coverage_uses_observed_requests_not_labels(store, fault):
    qi, _ = measurements(store)
    if fault == 'sequential':
        group = [x for x in qi['candidate']['samples'] if x['run_id'] == 'long-concurrent']
        group[1]['started_at'] = group[0]['finished_at']
        group[1]['finished_at'] = group[1]['started_at'] + 1
    elif fault == 'input-substitution':
        qi['candidate']['samples'][0]['input_sha256'] = 'f' * 64
    else:
        qi['baseline']['samples'][0]['text'] = qi['candidate']['samples'][0]['text'] = '  '
    result = quality.compare_outputs(**qi)
    assert result['status'] == 'fail'
    expected = {'sequential': 'candidate:missing-coverage:long-concurrent',
                'input-substitution': 'request-identity:short-single-0',
                'empty-output': 'candidate:empty-output:short-single-0'}
    assert expected[fault] in result['failures']


def test_coverage_policy_cannot_relabel_short_as_long_or_single_as_concurrent():
    with pytest.raises(FlowError, match='Long input'):
        policy({'short_input_max_tokens': 128, 'long_input_min_tokens': 128, 'min_concurrency': 2})
    with pytest.raises(FlowError, match='at least two'):
        policy({'short_input_max_tokens': 128, 'long_input_min_tokens': 2048, 'min_concurrency': 1})


def test_every_exploration_is_written_before_evaluation(store, tmp_path):
    baseline(store)
    plan = profile(store, tmp_path)
    state = model_loop.status(store, 't')
    directory = output_root(store)/'iterations/0001'
    assert (directory/'REPORT.md').is_file()
    assert json.loads((directory/'prof/after/STATUS.json').read_text())['status'] == 'not-collected'
    snapshots = []
    for index in range(2):
        snapshots.append(store.put(('candidate-' + str(index)).encode()))
        state = step(store, 'explore', plan=plan['plan'], route='triton', candidate_snapshot=snapshots[-1],
                     summary=f'Try tile {index}', changes=[{'path': 'kernel.py', 'symbol': 'score', 'description': f'tile {index}'}],
                     notes='Exploratory, no serving gain claimed', evidence=[snapshots[-1]])
    assert len(state['pending']['explorations']) == 2
    manifest = json.loads((directory/'manifest.json').read_text())
    for index, snapshot in enumerate(snapshots, 1):
        trial = directory/f'explorations/{index:04d}'
        assert json.loads((trial/'record.json').read_text())['snapshot'] == snapshot
        assert f'Try tile {index - 1}' in (trial/'REPORT.md').read_text()
        entry = next(x for x in manifest['artifacts'] if x['artifact'] == snapshot)
        assert (directory/entry['path']).read_bytes() == store.artifact(snapshot)
    assert 'iterations/0001/REPORT.md' in (output_root(store)/'REPORT.md').read_text()


def test_evaluation_requires_recorded_exploration(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    with pytest.raises(FlowError, match='explore before'):
        model_loop.advance(store, 't', {'revision': model_loop.status(store, 't')['revision'],
                                      'action': 'evaluate', 'plan': plan['plan'], 'route': 'gemm', **inputs})


def test_faster_candidate_without_post_profile_is_incomplete(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    missing = {k: v for k, v in inputs.items() if k not in ('candidate_analysis', 'candidate_capture')}
    state = step(store, 'evaluate', plan=plan['plan'], route='gemm', **missing)
    assert state['stage'] == 'candidate' and state['pending']['status'] == 'incomplete'
    assert state['pending']['quality']['status'] == 'pass'
    assert state['next']['action'] == 'capture-candidate-profile'
    assert state['next']['snapshot'] == state['pending']['snapshot'] != state['best']['snapshot']
    assert state['next']['skill'] == 'hcu-infer-analyze'
    manifest = json.loads((output_root(store)/'iterations/0001/manifest.json').read_text())
    assert manifest['effective'] is False
    assert '+20.00%' in (output_root(store)/'iterations/0001/REPORT.md').read_text()
    with pytest.raises(FlowError):
        step(store, 'keep', flow_round=1)
    assert step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)['stage'] == 'review'


def test_accuracy_failure_cannot_be_offset_by_speed_and_is_archived(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    broken = json.loads(store.artifact(inputs['quality_inputs']))
    broken['candidate']['samples'][1]['text'] = 'wrong long-input result'
    inputs['quality_inputs'] = retain(store, broken)
    state = step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)
    assert state['stage'] == 'rollback' and state['pending']['quality']['status'] == 'fail'
    assert state['pending']['performance']['status'] == 'pass'
    assert state['best']['snapshot'] == state['initial']['snapshot']
    directory = output_root(store)/'iterations/0001'
    assert json.loads((directory/'manifest.json').read_text())['effective'] is False
    step(store, 'rollback', verification=restore(store, pi['baseline']))
    saved = (directory/'REPORT.md').read_bytes()
    profile(store, tmp_path, 'second')
    assert (directory/'REPORT.md').read_bytes() == saved
    overview = (output_root(store)/'REPORT.md').read_text()
    assert 'rejected' in overview and 'iterations/0002/REPORT.md' in overview


@pytest.mark.parametrize('fault', ['wrong-snapshot', 'skipped', 'zero-executed', 'synthetic'])
def test_bad_candidate_capture_cannot_qualify(store, tmp_path, fault):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    capture = json.loads(store.artifact(inputs['candidate_capture']))
    if fault == 'wrong-snapshot': capture['candidate_snapshot'] = store.put(b'wrong snapshot')
    elif fault == 'skipped': capture['skipped_required'] = ['decode']
    elif fault == 'zero-executed': capture['executed'] = 0
    else: capture['synthetic'] = True
    inputs['candidate_capture'] = retain(store, capture)
    with pytest.raises(FlowError, match='Post-change capture'):
        step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)


def test_stale_or_relabelled_prechange_profile_is_rejected(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    snapshot = json.loads(store.artifact(inputs['quality_inputs']))['candidate']['candidate_snapshot']
    after_profile(store, snapshot, name='new-capture')
    with pytest.raises(FlowError, match='stale or replaced'):
        step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)
    old = json.loads(store.artifact(plan['record']['analysis']))
    result = profiling.analyze(store, 't', {
        'candidate_snapshot': snapshot,
        'traces': [{'rank': 0, 'path': old['ranks'][0]['source']['path'], 'window': {'start_us': 0, 'end_us': 10}}],
        'groups': [{'domain': 'tp', 'ranks': [0]}]})
    capture = json.loads(store.artifact(inputs['candidate_capture']))
    capture.update(analysis=result['analysis'], evidence=[row['source']['sha256'] for row in result['report']['ranks']])
    inputs.update(candidate_analysis=result['analysis'], candidate_capture=retain(store, capture))
    with pytest.raises(FlowError, match='cannot reuse pre-change'):
        step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)


def test_export_is_self_contained_and_can_be_rebuilt_after_source_trace_removal(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    # Replace the post trace with a real gzip fixture to exercise exact export bytes.
    snapshot = json.loads(store.artifact(inputs['quality_inputs']))['candidate']['candidate_snapshot']
    trace = tmp_path/'after.trace.json.gz'
    trace.write_bytes(gzip.compress(json.dumps({'rank': 0, 'traceEvents': [
        {'ph': 'X', 'cat': 'kernel', 'name': 'gz-after', 'ts': 1, 'dur': 6}]}).encode()))
    result = profiling.analyze(store, 't', {'candidate_snapshot': snapshot,
        'traces': [{'rank': 0, 'path': str(trace), 'window': {'start_us': 0, 'end_us': 10}}],
        'groups': [{'domain': 'tp', 'ranks': [0]}]})
    capture = json.loads(store.artifact(inputs['candidate_capture']))
    capture.update(analysis=result['analysis'], evidence=[result['report']['ranks'][0]['source']['sha256']])
    inputs.update(candidate_analysis=result['analysis'], candidate_capture=retain(store, capture))
    step(store, 'evaluate', plan=plan['plan'], route='gemm', **inputs)
    number = independent_review(store, plan, inputs)
    step(store, 'keep', flow_round=number)
    trace.unlink()
    (tmp_path/'first.json').unlink()
    shutil.rmtree(output_root(store))
    exported = tmp_path/'delivery'
    result = model_loop.report(store, 't', {'destination': str(exported)})
    assert result['report'] == str(exported/'REPORT.md')
    directory = exported/'iterations/0001'
    manifest = json.loads((directory/'manifest.json').read_text())
    assert manifest['effective'] is True
    for entry in manifest['artifacts']:
        assert hashlib.sha256((directory/entry['path']).read_bytes()).hexdigest() == entry['artifact']
    for relative, sha in manifest['generated_sha256'].items():
        assert hashlib.sha256((directory/relative).read_bytes()).hexdigest() == sha
    files = list((directory/'prof/after').glob('*.json.gz'))
    assert len(files) == 1 and json.loads(gzip.decompress(files[0].read_bytes()))['traceEvents'][0]['name'] == 'gz-after'
    unrelated = tmp_path/'unrelated'; unrelated.mkdir(); (unrelated/'REPORT.md').write_text('keep me')
    with pytest.raises(FlowError, match='destination must be new'):
        model_loop.report(store, 't', {'destination': str(unrelated)})
    assert (unrelated/'REPORT.md').read_text() == 'keep me'
    cli_export = tmp_path/'cli-delivery'
    command = subprocess.run([sys.executable, '-m', 'hcu_infra_agent', '--workspace', str(store.root),
                              'model-loop-report', 't', '--destination', str(cli_export)],
                             capture_output=True, text=True)
    assert command.returncode == 0, command.stderr
    assert json.loads(command.stdout)['report'] == str(cli_export/'REPORT.md')
    assert (cli_export/'iterations/0001/prof/after/analysis.json').is_file()


def test_standalone_outputs_preserve_each_assessment_and_require_candidate_prof(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    missing = {k: v for k, v in inputs.items() if k not in ('candidate_analysis', 'candidate_capture')}
    result = optimization.evaluate(store, 't', {'plan': plan['plan'], **missing})
    assert result['status'] == 'incomplete'
    folder = store.root/'modules/optimization/t/explorations'/plan['plan']
    failed_report = (folder/'attempts/0002/REPORT.md').read_bytes()
    result = optimization.evaluate(store, 't', {'plan': plan['plan'], **inputs})
    assert result['status'] == 'pass' and result['accepted_by_flow'] is False
    assert (folder/'attempts/0002/REPORT.md').read_bytes() == failed_report
    assert (folder/'attempts/0003/prof/after/analysis.json').is_file()
    assert 'incomplete' in failed_report.decode()
    assert 'attempts/0003/REPORT.md' in (folder/'REPORT.md').read_text()
    # Generated files are not the journal: reconstruct all old assessments from Store.
    root = store.root/'modules/optimization/t'
    shutil.rmtree(root)
    optimization.report(store, 't')
    assert (folder/'attempts/0002/REPORT.md').read_bytes() == failed_report
    assert (folder/'attempts/0003/prof/after/analysis.json').is_file()


def test_single_run_screening_is_preserved_but_never_effective(store, tmp_path):
    baseline(store)
    plan = profile(store, tmp_path)
    snapshot = store.put(b'exploratory source')
    raw = store.put(b'synthetic screening receipt')
    screen = {'context': store.task('t')['context'], 'candidate_snapshot': snapshot,
              'hardware_executed': True, 'candidate_path_exercised': True,
              'executed': 1, 'profiler_off': True, 'status': 'pass', 'evidence': [raw],
              'metrics': [
                  {'scope': 'model', 'scenario': 'BS1', 'metric': 'throughput_tok_s', 'baseline': [10], 'candidate': [20]},
                  {'scope': 'operator', 'scenario': 'index', 'metric': 'time_ms', 'baseline': [2], 'candidate': [.5]},
              ]}
    state = step(store, 'explore', plan=plan['plan'], route='triton', candidate_snapshot=snapshot,
                 summary='First screening, no accuracy claim', changes=[{'path': 'kernel.py', 'description': 'try reuse'}],
                 evidence=[raw], screening=retain(store, screen))
    assert state['stage'] == 'candidate'
    directory = output_root(store)/'iterations/0001'
    manifest = json.loads((directory/'manifest.json').read_text())
    assert manifest['effective'] is False
    report = (directory/'REPORT.md').read_text()
    assert '+100.00%' in report and '+75.00%' in report and 'unverified' in report
    assert 'not-measured' in report
    assert 'screening / unverified' in (output_root(store)/'REPORT.md').read_text()
    inputs = json.loads((directory/'explorations/0001/screening-inputs.json').read_text())
    assert inputs == screen


def test_policy_is_frozen_and_missing_policy_is_not_accepted(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    q = json.loads(store.artifact(inputs['quality_inputs']))
    q['contract']['coverage']['long_input_min_tokens'] = 512
    with pytest.raises(FlowError, match='frozen optimization quality coverage'):
        step(store, 'evaluate', plan=plan['plan'], route='gemm', **{**inputs, 'quality_inputs': retain(store, q)})
    q['contract']['coverage'] = None
    with pytest.raises(FlowError, match='requires short/long'):
        step(store, 'evaluate', plan=plan['plan'], route='gemm', **{**inputs, 'quality_inputs': retain(store, q)})


def test_user_interruption_retains_unverified_attempt_without_claiming_restoration(store, tmp_path):
    qi, pi = baseline(store)
    plan = profile(store, tmp_path)
    inputs = candidate(store, qi, pi)
    missing = {k: v for k, v in inputs.items() if not k.startswith('candidate_')}
    state = step(store, 'evaluate', plan=plan['plan'], route='gemm', **missing)
    proof = {'task': 't', 'context': state['context'], 'context_epoch': state['context_epoch'],
             'loop_revision': state['revision'] - 1, 'status': 'stopped', 'execution_stopped': True,
             'evidence': [store.put(b'fixture stop receipt; no real hardware process')]}
    with pytest.raises(FlowError, match='current-revision'):
        step(store, 'interrupt', reason='User requested stop', verification=retain(store, proof))
    proof['loop_revision'] = state['revision']
    stopped = step(store, 'interrupt', reason='User requested stop', verification=retain(store, proof))
    assert stopped['stage'] == 'stopped' and stopped['iterations'][0]['decision'] == 'interrupted'
    assert stopped['best']['snapshot'] == stopped['initial']['snapshot']
    folder = output_root(store)/'iterations/0001'
    assert (folder/'interruption.json').is_file()
    assert json.loads((folder/'manifest.json').read_text())['effective'] is False
    assert 'restoring the reviewed best is not claimed' in (output_root(store)/'REPORT.md').read_text()


def test_export_rechecks_ownership_after_acquiring_lock(store, tmp_path, monkeypatch):
    baseline(store)
    destination = tmp_path/'racing-export'

    @contextlib.contextmanager
    def intervening_writer(directory, name):
        directory.mkdir(parents=True)
        (directory/'manifest.json').write_text(json.dumps({'task': 'someone-else', 'module': 'model-loop'}))
        (directory/'REPORT.md').write_text('foreign report')
        yield

    monkeypatch.setattr(model_loop, 'writer_lock', intervening_writer)
    with pytest.raises(FlowError, match='destination must be new'):
        model_loop.report(store, 't', {'destination': str(destination)})
    assert (destination/'REPORT.md').read_text() == 'foreign report'


def test_failed_standalone_render_keeps_durable_history(store, tmp_path, monkeypatch):
    baseline(store)
    trace = tmp_path/'before.json'
    trace.write_text(json.dumps({'rank': 0, 'traceEvents': [{'ph': 'X', 'cat': 'kernel', 'name': 'before', 'ts': 1, 'dur': 8}]}))
    prof = profiling.analyze(store, 't', {'traces': [{'rank': 0, 'path': str(trace), 'window': {'start_us': 0, 'end_us': 10}}],
                                       'groups': [{'domain': 'tp', 'ranks': [0]}]})
    original = optimization_output.bundle

    def unavailable_output(*args, **kwargs):
        raise OSError('fixture disk unavailable')

    monkeypatch.setattr(optimization_output, 'bundle', unavailable_output)
    with pytest.raises(OSError, match='disk unavailable'):
        optimization.plan(store, 't', {'analysis': prof['analysis'], 'observation': 'Measured cost',
                                      'hypothesis': 'Tune dispatch', 'target': 'gemm', 'validation': ['accuracy']})
    with store.db() as db:
        rows = db.execute('SELECT * FROM optimization_history WHERE task=?', ('t',)).fetchall()
    assert len(rows) == 1
    monkeypatch.setattr(optimization_output, 'bundle', original)
    optimization.report(store, 't')
    assert (store.root/'modules/optimization/t/explorations'/rows[0]['plan']/'attempts/0001/REPORT.md').is_file()


def test_legacy_loop_remains_reportable_but_cannot_bypass_new_gates(store):
    baseline(store)
    state = model_loop.status(store, 't')
    state.pop('status', None)
    state.pop('schema_version')
    state['policy'].pop('quality_coverage')
    artifact = retain(store, state)
    with store.db() as db:
        db.execute('UPDATE model_loops SET artifact=? WHERE task=?', (artifact, 't'))
    assert model_loop.report(store, 't')['report'].endswith('REPORT.md')
    with pytest.raises(FlowError, match='Legacy loop is report-only'):
        step(store, 'stop', reason='Cannot silently migrate validation')
