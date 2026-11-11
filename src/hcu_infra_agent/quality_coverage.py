"""Small, explicit serving correctness matrices; no model execution is implied."""
import re
from .core import FlowError


DEFAULT_COVERAGE = {'short_input_max_tokens': 128, 'long_input_min_tokens': 2048,
                    'min_concurrency': 2}
CELLS = ('short-single', 'long-single', 'short-concurrent', 'long-concurrent')


def policy(value=None):
    value = DEFAULT_COVERAGE if value is None else value
    if not isinstance(value, dict) or set(value) != set(DEFAULT_COVERAGE):
        raise FlowError('Quality coverage needs short_input_max_tokens, long_input_min_tokens and min_concurrency')
    if any(type(x) is not int or x <= 0 for x in value.values()):
        raise FlowError('Quality coverage limits must be positive integers')
    if value['long_input_min_tokens'] <= value['short_input_max_tokens'] or value['min_concurrency'] < 2:
        raise FlowError('Long input must exceed short input; concurrent validation needs at least two requests')
    return dict(value)


def require(contract, expected=None):
    if not isinstance(contract, dict) or not isinstance(contract.get('coverage'), dict):
        raise FlowError('Optimization quality requires short/long input and concurrent coverage')
    actual = policy(contract['coverage'])
    if expected is not None and actual != expected:
        raise FlowError('Keep the frozen optimization quality coverage policy')
    return actual


def assess(contract, baseline, candidate):
    """Check request identity and real overlapping intervals, not scenario labels.

    Times are recorded by the runner, in one clock domain per run. As with other
    measurement inputs this validates retained records, not their authenticity.
    """
    from .quality import number
    limits = require(contract)
    failures, coverage = [], {}
    fields = ('input_sha256', 'input_tokens', 'concurrency', 'run_id')
    for left, right in zip(baseline['samples'], candidate['samples']):
        if any(left.get(k) != right.get(k) for k in fields):
            failures.append('request-identity:' + left['id'])
    for label, record in (('baseline', baseline), ('candidate', candidate)):
        cells = {cell: [] for cell in CELLS}
        groups = {}
        for sample in record['samples']:
            sid = sample['id']
            if (not isinstance(sample.get('input_sha256'), str)
                    or not re.fullmatch('[0-9a-f]{64}', sample['input_sha256'])
                    or type(sample.get('input_tokens')) is not int or sample['input_tokens'] <= 0
                    or type(sample.get('concurrency')) is not int or sample['concurrency'] <= 0
                    or not isinstance(sample.get('run_id'), str) or not sample['run_id'].strip()):
                raise FlowError('Coverage samples need input_sha256, positive input_tokens/concurrency and run_id')
            start = number(sample.get('started_at'), 'request started_at')
            end = number(sample.get('finished_at'), 'request finished_at')
            if start < 0 or end <= start:
                raise FlowError('Request timing must have nonnegative start and finish after start')
            if 'values' not in sample and 'text' in sample and not sample['text'].strip():
                failures.append(label + ':empty-output:' + sid)
            groups.setdefault(sample['run_id'], []).append(sample)
        runs = []
        for run_id, samples in groups.items():
            concurrency = samples[0]['concurrency']
            if any(s['concurrency'] != concurrency for s in samples):
                raise FlowError('Samples in one quality run must declare the same concurrency')
            events = sorted([(s['started_at'], 1) for s in samples]
                            + [(s['finished_at'], -1) for s in samples])
            active = peak = 0
            for _, delta in events:
                active += delta
                peak = max(peak, active)
            if peak > concurrency:
                failures.append(label + ':concurrency-exceeded:' + run_id)
            for length, condition in (
                ('short', lambda s: s['input_tokens'] <= limits['short_input_max_tokens']),
                ('long', lambda s: s['input_tokens'] >= limits['long_input_min_tokens']),
            ):
                subset = [s for s in samples if condition(s)]
                if concurrency == 1 and peak == 1:
                    cells[length + '-single'].extend(s['id'] for s in subset)
                elif concurrency >= limits['min_concurrency']:
                    # A short request overlapping only long requests does not
                    # prove a complete short-concurrent case (and vice versa).
                    events = sorted([(s['started_at'], 1) for s in subset]
                                    + [(s['finished_at'], -1) for s in subset])
                    active = subset_peak = 0
                    for _, delta in events:
                        active += delta
                        subset_peak = max(subset_peak, active)
                    if subset_peak >= limits['min_concurrency']:
                        cells[length + '-concurrent'].extend(s['id'] for s in subset)
            runs.append({'run_id': run_id, 'declared_concurrency': concurrency,
                         'observed_overlap': peak, 'samples': len(samples)})
        missing = [cell for cell, ids in cells.items() if not ids]
        failures.extend(label + ':missing-coverage:' + cell for cell in missing)
        coverage[label] = {'cells': cells, 'missing': missing, 'runs': runs}
    return {'policy': limits, **coverage}, failures
