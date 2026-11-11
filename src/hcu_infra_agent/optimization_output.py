"""Portable iteration dossiers, derived from retained evidence rather than prose claims."""
import json
from pathlib import Path
from .core import FlowError, atomic_write, context_epoch, digest, fingerprint, utc, write_json


def text(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def performance_lines(result):
    lines = ['| Scenario / metric | Baseline median | Candidate median | Relative gain |',
             '| --- | ---: | ---: | ---: |']
    for name, values in result.get('metrics', {}).items():
        lines.append(f'| {text(name)} | {values["baseline_median"]:.6g} | '
                     f'{values["candidate_median"]:.6g} | {values["relative_gain"]:+.2%} |')
    if len(lines) == 2:
        lines.append('| Not measured | — | — | — |')
    return lines


def effective(record):
    return (record.get('decision') == 'kept' and bool(record.get('review'))
            and record.get('quality', {}).get('status') == 'pass'
            and bool(record.get('quality', {}).get('coverage'))
            and record.get('performance', {}).get('status') == 'pass'
            and record.get('candidate_profile', {}).get('status') == 'complete'
            and bool(record.get('candidate_profile', {}).get('traces')))


def bundle(store, directory, record, force=False):
    """Export one attempt with exact raw traces and comparison inputs.

    The Store remains authoritative. Generated manifest hashes let an exported
    folder be inspected without knowing the original absolute Store location.
    No profiler, benchmark, model or accuracy test is launched here.
    """
    directory = Path(directory)
    manifest_path = directory / 'manifest.json'
    record_digest = fingerprint(record)
    if not force and manifest_path.is_file():
        previous = json.loads(manifest_path.read_text())
        if previous.get('record_digest') == record_digest and (directory/'REPORT.md').is_file():
            return str(directory/'REPORT.md')
    directory.mkdir(parents=True, exist_ok=True)
    artifacts, generated = [], {}

    def write(relative, value):
        path = directory / relative
        atomic_write(path, json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        generated[relative] = digest(path.read_bytes())

    def materialize(sha, relative):
        blob = store.artifact(sha)
        path = directory / relative
        if not path.is_file() or path.read_bytes() != blob:
            atomic_write(path, blob)
        artifacts.append({'artifact': sha, 'path': relative, 'bytes': len(blob)})
        return blob

    def evidence(values):
        for sha in sorted(set(values)):
            if not any(x['artifact'] == sha for x in artifacts):
                materialize(sha, 'evidence/' + sha)

    def profile(role, analysis_id, capture_id, reason):
        folder = 'prof/' + role + '/'
        if not analysis_id:
            if record.get('kind') == 'baseline':
                write(folder + 'STATUS.json', {'status': 'not-applicable', 'reason': 'Baseline reference; profiling is retained with its following iteration'})
                return
            write(folder + 'STATUS.json', {'status': 'not-collected', 'reason': reason})
            return
        analysis = json.loads(materialize(analysis_id, folder + 'analysis.json'))
        capture_evidence = []
        if capture_id:
            capture = json.loads(materialize(capture_id, folder + 'capture.json'))
            capture_evidence = capture.get('evidence', [])
        for row in analysis.get('ranks', []):
            source = row['source']
            suffix = '.json.gz' if source.get('path', '').endswith('.gz') else '.json'
            filename = f'rank-{row["rank"]}-{source["sha256"][:12]}.trace' + suffix
            materialize(source['sha256'], folder + filename)
        evidence(capture_evidence)
        evidence(analysis.get('evidence', []))
        write(folder + 'STATUS.json', {'status': 'collected', 'analysis': analysis_id,
                                      'capture': capture_id, 'snapshot': record.get('snapshot') if role == 'after' else record.get('previous_snapshot')})

    write('iteration.json', record)
    for key in ('plan', 'failure', 'rollback', 'review', 'interruption', 'snapshot', 'previous_snapshot', 'deployment'):
        if record.get(key):
            # A snapshot may be an archive rather than JSON; preserve its bytes.
            payload = materialize(record[key], key + ('.artifact' if key.endswith('snapshot') else '.json'))
            if key in {'failure', 'rollback', 'interruption', 'review', 'deployment'}:
                evidence(json.loads(payload).get('evidence', []))
            elif key == 'plan':
                evidence(json.loads(payload).get('references', []))
    for kind in ('quality', 'performance'):
        pointer = record.get(kind + '_inputs')
        result = record.get(kind, {'status': 'not-measured', 'failures': ['not-executed']})
        if pointer:
            inputs = json.loads(materialize(pointer, kind + '/inputs.json'))
            for side in ('baseline', 'candidate'):
                evidence([*inputs[side].get('evidence', []),
                          *([inputs[side]['candidate_snapshot']] if inputs[side].get('candidate_snapshot') else [])])
        write(kind + '/result.json', result)
    write('performance/cumulative.json', record.get('cumulative_performance', {'status': 'not-measured'}))
    profile('before', record.get('analysis'), record.get('capture'), 'No pre-change profile recorded')
    after = record.get('candidate_profile', {})
    profile('after', after.get('analysis'), after.get('capture'),
            record.get('rejection_reason', 'Post-change profile not collected; optimization is unverified'))
    for index, trial in enumerate(record.get('explorations', []), 1):
        relative = f'explorations/{index:04d}'
        write(relative + '/record.json', trial)
        evidence([*trial.get('evidence', []), *([trial['snapshot']] if trial.get('snapshot') else []),
                  *([trial['plan']] if trial.get('plan') else [])])
        if trial.get('screening'):
            screening = json.loads(materialize(trial['screening'], relative + '/screening-inputs.json'))
            evidence(screening.get('evidence', []))
            write(relative + '/screening-summary.json', trial['screening_summary'])
        lines = ['# Exploration ' + str(index), '', trial.get('summary', ''), '',
                 'Candidate snapshot: ' + str(trial.get('snapshot', 'not recorded')), '',
                 'Notes: ' + trial.get('notes', ''), '', '## Changes', '']
        for change in trial.get('changes', []):
            lines.append('- ' + text(change['path']) + ' — ' + text(change['description']))
        if trial.get('screening_summary'):
            lines += ['', '## Screening measurements — unverified', '',
                      *performance_lines(trial['screening_summary']), '',
                      'Operator timings are not model TPOT. These numbers do not pass accuracy or performance acceptance.']
        lines += ['', 'Raw artifact locations are listed in ../../manifest.json; details are in record.json.',
                  'This exploration entry is not an accepted performance or quality result.']
        atomic_write(directory/relative/'REPORT.md', '\n'.join(lines) + '\n')
        generated[relative + '/REPORT.md'] = digest((directory/relative/'REPORT.md').read_bytes())
    evidence(record.get('evidence', []))
    decision = record.get('decision', 'pending')
    validated = effective(record)
    title = 'Initial baseline' if record.get('kind') == 'baseline' else 'Failed baseline' if record.get('kind') == 'baseline-failure' else 'Optimization attempt'
    lines = ['# ' + title + ' ' + str(record.get('number', '')), '',
             'Direction: ' + record.get('direction', record.get('hypothesis', 'Exploration pending')),
             'Observation: ' + record.get('observation', 'not recorded'),
             'Status: ' + record.get('status', 'exploring'), 'Decision: ' + decision,
             ('Qualification: reference baseline' if record.get('kind') == 'baseline' else
              'Validated effective optimization: ' + ('yes' if validated else 'no')),
             'Quality: ' + record.get('quality', {}).get('status', 'not-measured'),
             'Post-change Prof: ' + ('not-applicable' if record.get('kind') == 'baseline' else after.get('status', 'not-collected')), '',
             'These are evidence-backed protocol assessments; the exporter itself runs no hardware tests.', '',
             '## Changes', '']
    for change in record.get('changes', []):
        lines.append('- ' + text(change['path']) + (' (' + text(change['symbol']) + ')' if change.get('symbol') else '')
                     + ': ' + text(change['description']))
    if not record.get('changes'):
        lines.append('No implementation changes recorded yet.')
    if record.get('explorations'):
        lines += ['', '## Exploration history', '']
        for index, trial in enumerate(record['explorations'], 1):
            lines.append(f'- [{text(trial["summary"])}](explorations/{index:04d}/REPORT.md)')
    if record.get('screening_summary'):
        lines += ['', '## Latest screening measurements — unverified', '',
                  *performance_lines(record['screening_summary']), '',
                  'The retained screening inputs include repetition counts. A single sample or operator microbenchmark is not model acceptance.']
    lines += ['', '## Performance against the previous best', '', *performance_lines(record.get('performance', {})),
              '', '## Performance against the initial baseline', '', *performance_lines(record.get('cumulative_performance', {})),
              '', 'Relative gains are measurements only. Without passing quality and post-change Prof they do not establish an effective optimization.',
              '', '## Quality coverage', '']
    coverage = record.get('quality', {}).get('coverage', {})
    for side in ('baseline', 'candidate'):
        for cell, samples in coverage.get(side, {}).get('cells', {}).items():
            lines.append(f'- {side} / {cell}: {len(samples)} samples')
    for kind in ('quality', 'performance'):
        for failure in record.get(kind, {}).get('failures', []):
            lines.append('- ' + kind + ': ' + text(failure))
    if not coverage:
        lines.append('Short/long/single/concurrent correctness coverage has not been recorded.')
    lines += ['', '## Evidence and disposition', '',
              '- Before Prof: [status](prof/before/STATUS.json)',
              '- After Prof: [status](prof/after/STATUS.json)',
              '- [Quality assessment](quality/result.json)',
              '- [Performance assessment](performance/result.json)',
              '- [Full iteration record](iteration.json)',
              '- [Artifact manifest](manifest.json)', '',
              'Rejection / missing evidence: ' + record.get('rejection_reason', record.get('missing_reason', 'none recorded'))]
    atomic_write(directory/'REPORT.md', '\n'.join(lines) + '\n')
    generated['REPORT.md'] = digest((directory/'REPORT.md').read_bytes())
    write_json(manifest_path, {'schema_version': 1, 'record_digest': record_digest, 'artifacts': artifacts,
                              'generated_sha256': generated, 'effective': validated,
                              'limits': 'Derived dossier; immutable Store artifacts and reviewed measurements remain authoritative.'})
    return str(directory/'REPORT.md')


def publish_plan(store, task, plan_id, record):
    """Normalize standalone optimization-plan/check output as well as loop output."""
    from .file_questions import writer_lock
    root = store.root/'modules'/'optimization'/task['id']
    with writer_lock(root, name='report.lock'):
        _history_table(store)
        with store.db() as db:
            revision = db.execute('SELECT COALESCE(MAX(number),0) FROM optimization_history WHERE task=? AND plan=?',
                                  (task['id'], plan_id)).fetchone()[0] + 1
        value = {**record, 'task': task['id'], 'plan': plan_id, 'context': task['context'],
                 'context_epoch': task['context_epoch'], 'output_revision': revision, 'number': revision}
        from .evidence import retain
        artifact = retain(store, value)
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT context FROM tasks WHERE id=?', (task['id'],)).fetchone()
            if not current or current['context'] != task['context'] or context_epoch(db, task['id']) != task['context_epoch']:
                raise FlowError('Task context changed while retaining optimization output')
            db.execute('INSERT INTO optimization_history VALUES(?,?,?,?,?)',
                       (task['id'], plan_id, revision, artifact, utc()))
            store.event(db, task['id'], 'optimization-output-recorded', {'plan': plan_id, 'revision': revision, 'artifact': artifact})
        _render_plan_history(store, task, root)
    return {'report': str(root/'REPORT.md'), 'exploration_report': str(root/'explorations'/plan_id/'REPORT.md')}


def _history_table(store):
    with store.db() as db:
        db.execute('CREATE TABLE IF NOT EXISTS optimization_history('
                   'task TEXT NOT NULL, plan TEXT NOT NULL, number INTEGER NOT NULL, artifact TEXT NOT NULL, '
                   'created TEXT NOT NULL, PRIMARY KEY(task,plan,number))')


def _render_plan_history(store, task, root, force=False):
    with store.db() as db:
        rows = db.execute('SELECT * FROM optimization_history WHERE task=? ORDER BY rowid', (task['id'],)).fetchall()
    index = {'schema_version': 1, 'task': task['id'], 'entries': {}}
    histories = {}
    for row in rows:
        value = json.loads(store.artifact(row['artifact']))
        plan_id = row['plan']
        exploration = root/'explorations'/plan_id
        relative = f'attempts/{row["number"]:04d}'
        bundle(store, exploration/relative, value, force=force)
        index['entries'][plan_id] = value
        histories.setdefault(plan_id, []).append(row['number'])
    lines = ['# Optimization explorations', '',
             '| Exploration | Direction | Context | Quality | After Prof | Status |', '| --- | --- | --- | --- | --- | --- |']
    for key, item in index['entries'].items():
        relative = f'attempts/{item["output_revision"]:04d}'
        history = ['# Exploration history', '', 'Latest: [' + item.get('status', 'planned') + '](' + relative + '/REPORT.md)', '']
        history.extend(f'- [Record {n}](attempts/{n:04d}/REPORT.md)' for n in histories[key])
        atomic_write(root/'explorations'/key/'REPORT.md', '\n'.join(history) + '\n')
        current = item['context'] == task['context'] and item['context_epoch'] == task['context_epoch']
        lines.append(f'| [exploration](explorations/{key}/REPORT.md) | {text(item.get("direction", item.get("hypothesis", "pending")))} | '
                     f'{"current" if current else "historical"} / epoch {item["context_epoch"]} | '
                     f'{item.get("quality", {}).get("status", "not-measured")} | '
                     f'{item.get("candidate_profile", {}).get("status", "not-collected")} | {item.get("status", "planned")} |')
    write_json(root/'index.json', index)
    lines += ['', 'Passing measurement gates remains subject to independent flow review. Failed and incomplete explorations are retained.',
              'The index is derived from immutable Store records and can be rebuilt with optimization-report.']
    atomic_write(root/'REPORT.md', '\n'.join(lines) + '\n')


def report_plans(store, task):
    from .file_questions import writer_lock
    root = store.root/'modules'/'optimization'/task['id']
    with writer_lock(root, name='report.lock'):
        _history_table(store)
        _render_plan_history(store, task, root, force=True)
    return {'status': 'complete', 'report': str(root/'REPORT.md')}
