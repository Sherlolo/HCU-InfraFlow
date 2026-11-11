"""Pins and isolated CPU tool runs shared by inference analysis modules."""
import json
import os
import signal
import subprocess
import uuid
from pathlib import Path
from .core import FlowError, fingerprint, write_json


def retain(store, value):
    return store.put(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode())


def pin(store, path):
    path = Path(path).expanduser().resolve(strict=True)
    data = path.read_bytes()
    return {'path': str(path), 'sha256': store.put(data), 'bytes': len(data)}


def run_tool(store, module, argv, timeout=120):
    """A timeout kills only this invocation's process group and preserves its logs."""
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise FlowError('Tool timeout must be an integer in 1..3600 seconds')
    directory = store.root / 'modules' / module / uuid.uuid4().hex
    directory.mkdir(parents=True)
    command = [str(a) for a in argv]
    stdout = directory / 'stdout.log'
    stderr = directory / 'stderr.log'
    with stdout.open('wb') as out, stderr.open('wb') as err:
        process = subprocess.Popen(command, cwd=directory, stdout=out, stderr=err,
                                   env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'TMPDIR':str(directory), 'XDG_CACHE_HOME':str(directory/'cache')},
                                   start_new_session=os.name != 'nt')
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    result = {'status': 'incomplete' if timed_out or code else 'complete', 'argv': command,
              'cwd': str(directory), 'exit_code': code, 'timed_out': timed_out,
              'stdout': pin(store, stdout), 'stderr': pin(store, stderr)}
    write_json(directory / 'execution.json', result)
    result['artifact'] = retain(store, result)
    return result


def current_analysis(store, task, artifact):
    """Only the latest current-context analysis may drive a new optimization plan."""
    with store.db() as db:
        row = store.current_reports(db, task['id'], task['context']).get('analysis')
    if not row or row['artifact'] != artifact:
        raise FlowError('Analysis is stale, replaced or belongs to another task')
    value = json.loads(store.artifact(artifact))
    if value.get('context') != task['context'] or value.get('status') not in {'pass', 'complete'}:
        raise FlowError('Analysis is not ready for hypothesis planning')
    for sha in value.get('evidence', []):
        store.artifact(sha)
    if not value.get('evidence'):
        raise FlowError('Analysis requires retained raw evidence')
    return value


def candidate_profile(store, task, analysis_id, capture_id, snapshot, before_analysis=None):
    """Bind a fresh post-change profile to the exact evaluated candidate."""
    analysis = json.loads(store.artifact(analysis_id))
    capture = json.loads(store.artifact(capture_id))
    with store.db() as db:
        latest = store.current_reports(db, task['id'], task['context']).get('candidate-analysis')
    if not latest or latest['artifact'] != analysis_id:
        raise FlowError('Candidate profile is stale or replaced; use prof-analyze with candidate_snapshot')
    if (analysis.get('task') != task['id'] or analysis.get('context') != task['context']
            or analysis.get('context_epoch') != task['context_epoch']
            or analysis.get('candidate_snapshot') != snapshot
            or analysis.get('kind') != 'offline-prof-analysis' or analysis.get('status') != 'complete'):
        raise FlowError('Post-change analysis must match this task/context/epoch and candidate snapshot')
    if (capture.get('context') != task['context'] or capture.get('context_epoch') != task['context_epoch']
            or capture.get('candidate_snapshot') != snapshot or capture.get('analysis') != analysis_id
            or capture.get('hardware_executed') is not True or capture.get('synthetic')
            or type(capture.get('executed')) is not int or capture['executed'] <= 0
            or capture.get('candidate_path_exercised') is not True
            or capture.get('failures') or capture.get('required_missing') or capture.get('skipped_required')
            or capture.get('qualification') == 'simulation-prediction'
            or capture.get('status') not in {'pass', 'complete'}):
        raise FlowError('Post-change capture needs successful hardware provenance for the evaluated snapshot')
    evidence = capture.get('evidence')
    if not isinstance(evidence, list) or not evidence or not analysis.get('ranks'):
        raise FlowError('Retain candidate profile traces and capture evidence')
    for sha in evidence + analysis.get('evidence', []):
        store.artifact(sha)
    sources = {row['source']['sha256'] for row in analysis['ranks']}
    if not sources.issubset(evidence):
        raise FlowError('Candidate capture must retain every analyzed rank trace')
    if before_analysis:
        before = json.loads(store.artifact(before_analysis))
        previous = {row['source']['sha256'] for row in before.get('ranks', [])}
        if sources & previous:
            raise FlowError('Post-change profiling cannot reuse pre-change trace bytes')
        # Preserve declared rank/group coverage for a meaningful before/after view.
        if analysis.get('rank_coverage') != before.get('rank_coverage'):
            raise FlowError('Candidate profile rank/group coverage differs from the pre-change profile')
    return {'analysis': analysis_id, 'capture': capture_id, 'status': 'complete',
            'snapshot': snapshot, 'traces': sorted(sources)}
