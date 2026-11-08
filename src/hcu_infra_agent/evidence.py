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
