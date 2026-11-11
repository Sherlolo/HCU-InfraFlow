"""Inference output, serving feature and frozen-workload performance contracts."""
import json
import math
import statistics
from .core import FlowError, fingerprint


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (positive and value <= 0):
        raise FlowError(name + ' must be a finite ' + ('positive ' if positive else '') + 'number')
    return value


def validate_measurement(value, context, path_required=True):
    if not isinstance(value, dict):
        raise FlowError('Measurement must be an object')
    reasons = []
    if value.get('context') != context: reasons.append('context-mismatch')
    if type(value.get('executed')) is not int or value['executed'] <= 0: reasons.append('no-executed-tests')
    if value.get('failures') or value.get('status', 'pass') != 'pass': reasons.append('reported-failures')
    if value.get('required_missing') or value.get('skipped_required'): reasons.append('missing-required-coverage')
    if path_required and value.get('candidate_path_exercised') is not True: reasons.append('candidate-not-exercised')
    if not isinstance(value.get('evidence'), list) or not value['evidence']: reasons.append('missing-raw-evidence')
    return reasons


IDENTITIES = ('model', 'tokenizer', 'quantization', 'workload', 'driver')


def compare_outputs(contract, baseline, candidate):
    """Require fixed sample IDs and recorded feature results; no training-loss proxy."""
    if not isinstance(contract, dict) or not contract.get('context'):
        raise FlowError('Quality contract needs context')
    identities = contract.get('identities')
    if not isinstance(identities, dict) or any(not isinstance(identities.get(k), str) or not identities[k] for k in IDENTITIES):
        raise FlowError('Freeze model/tokenizer/quantization/workload/driver identities')
    atol = number(contract.get('atol'), 'atol')
    rtol = number(contract.get('rtol'), 'rtol')
    if min(atol, rtol) < 0 or not contract.get('tolerance_basis'):
        raise FlowError('Tolerances require a nonnegative value and basis')
    required = contract.get('required_features')
    if not isinstance(required, list) or not required or any(not isinstance(k, str) or not k for k in required):
        raise FlowError('Declare required serving features')
    reasons = []
    for label, record in [('baseline', baseline), ('candidate', candidate)]:
        reasons += [label + ':' + r for r in validate_measurement(record, contract['context'])]
        if record.get('identities') != identities: reasons.append(label + ':identity-mismatch')
        if not isinstance(record.get('features'), dict): raise FlowError('Features must be an object')
        for name in required:
            if record['features'].get(name) is not True: reasons.append(label + ':feature:' + name)
    for name, passed in baseline['features'].items():
        if passed is True and candidate['features'].get(name) is not True: reasons.append('feature-regressed:' + name)
    left, right = baseline.get('samples'), candidate.get('samples')
    if not isinstance(left, list) or not isinstance(right, list) or not left or len(left) != len(right):
        raise FlowError('Need matched nonempty inference samples')
    seen = set()
    for a, b in zip(left, right):
        sid = a.get('id')
        if not isinstance(sid, str) or not sid or sid in seen or b.get('id') != sid:
            raise FlowError('Sample IDs must be unique and paired in order')
        seen.add(sid)
        if 'values' in a or 'values' in b:
            x, y = a.get('values'), b.get('values')
            if not isinstance(x, list) or not x or not isinstance(y, list) or len(x) != len(y):
                raise FlowError('Numeric references need equal nonempty vectors')
            for u, v in zip(x, y):
                number(u, 'reference'); number(v, 'candidate')
                if abs(u-v) > atol + rtol * abs(u): reasons.append('numeric-output:' + sid); break
        elif isinstance(a.get('text'), str) and isinstance(b.get('text'), str):
            if a['text'] != b['text']: reasons.append('text-output:' + sid)
        else: raise FlowError('Each sample needs text or numeric values')
    if baseline['executed'] < len(left) or candidate['executed'] < len(right):
        reasons.append('executed-count-does-not-cover-samples')
    coverage = None
    if 'coverage' in contract:
        from .quality_coverage import assess
        coverage, coverage_failures = assess(contract, baseline, candidate)
        reasons.extend(coverage_failures)
    return {'status': 'fail' if reasons else 'pass', 'executed': len(left), 'failures': reasons,
            **({'coverage': coverage} if coverage is not None else {}),
            'contract': fingerprint(contract), 'limits': 'Only declared samples and features; not a full model accuracy benchmark.'}


def compare_performance(contract, baseline, candidate):
    """Compare repeated serving results under a fixed workload and SLA."""
    identities = contract.get('identities')
    if not isinstance(identities, dict) or any(not isinstance(identities.get(k), str) or not identities[k] for k in IDENTITIES):
        raise FlowError('Freeze all performance identities')
    if not isinstance(contract.get('sla', {}), dict) or set(contract.get('sla', {})) - {'ttft_ms','tpot_ms','latency_p95_ms'}:
        raise FlowError('SLA must declare supported latency bounds')
    if contract.get('metric') not in {'throughput_tok_s', 'ttft_ms', 'tpot_ms', 'latency_p95_ms'}:
        raise FlowError('Unknown primary performance metric')
    repeats = contract.get('min_repeats', 3)
    if type(repeats) is not int or repeats < 3: raise FlowError('Use at least three repeats')
    regression = number(contract.get('max_regression', 0), 'max_regression')
    gain_floor = number(contract.get('min_gain', 0), 'min_gain')
    if min(regression, gain_floor) < 0: raise FlowError('Gain/regression limits cannot be negative')
    failures = []
    for label, record in [('baseline', baseline), ('candidate', candidate)]:
        failures += [label + ':' + r for r in validate_measurement(record, contract['context'])]
        if record.get('workload') != contract.get('workload') or not contract.get('workload'):
            failures.append(label + ':workload-mismatch')
        if record.get('identities') != contract.get('identities') or not contract.get('identities'):
            failures.append(label + ':identity-mismatch')
        if record.get('profiler_off') is not True: failures.append(label + ':profiled-timing')
    bs, cs = baseline.get('scenarios'), candidate.get('scenarios')
    if not isinstance(bs, dict) or not bs or not isinstance(cs, dict) or bs.keys() != cs.keys():
        raise FlowError('Scenario sets must match and be nonempty')
    results = {}
    for name, original in bs.items():
        current = cs[name]
        for metric in ('throughput_tok_s', 'ttft_ms', 'tpot_ms', 'latency_p95_ms'):
            a, b = original.get(metric), current.get(metric)
            if not isinstance(a, list) or not isinstance(b, list) or len(a) < repeats or len(a) != len(b):
                raise FlowError('Need matched repeats for ' + name + ':' + metric)
            for x in a + b: number(x, metric, positive=metric == 'throughput_tok_s')
            if any(x < 0 for x in a + b): raise FlowError('Negative latency')
            ma, mb = statistics.median(a), statistics.median(b)
            higher = metric == 'throughput_tok_s'
            gain = (mb / ma - 1) if higher else (1 - mb / ma) if ma else (0 if mb == 0 else -1)
            if gain < -regression: failures.append('regressed:' + name + ':' + metric)
            if metric == contract['metric'] and gain < gain_floor: failures.append('gain-below-threshold:' + name)
            for bound_name, bound in contract.get('sla', {}).items():
                if metric == bound_name and mb > number(bound, 'SLA'): failures.append('sla:' + name + ':' + metric)
            results[name + ':' + metric] = {'baseline_median': ma, 'candidate_median': mb, 'relative_gain': gain,
                                           'baseline_stdev': statistics.stdev(a), 'candidate_stdev': statistics.stdev(b)}
    return {'status': 'fail' if failures else 'pass', 'executed': len(results), 'failures': failures, 'metrics': results,
            'limits': 'Matched repetitions, not a statistical-significance or production-readiness claim.'}


def validate_stage_report(store, report):
    pointer = report.get('quality_inputs')
    if pointer not in report.get('evidence', []): raise FlowError('Retain quality_inputs as report evidence')
    inputs = json.loads(store.artifact(pointer))
    result = compare_outputs(inputs['contract'], inputs['baseline'], inputs['candidate'])
    if result['status'] != 'pass' or inputs['contract']['context'] != report.get('context'):
        raise FlowError('Inference quality comparison did not pass for this context')
    if inputs['candidate'].get('candidate_snapshot') != report.get('candidate_snapshot'):
        raise FlowError('Quality candidate snapshot mismatch')
    store.artifact(report['candidate_snapshot'])
    for record in (inputs['baseline'], inputs['candidate']):
        for sha in record['evidence']: store.artifact(sha)
    return result


def validate_performance_report(store, report):
    pointer = report.get('performance_inputs')
    if pointer not in report.get('evidence', []): raise FlowError('Retain performance_inputs as report evidence')
    inputs = json.loads(store.artifact(pointer))
    result = compare_performance(inputs['contract'], inputs['baseline'], inputs['candidate'])
    if result['status'] != 'pass' or inputs['contract']['context'] != report.get('context'):
        raise FlowError('Performance did not pass for this context')
    if inputs['candidate'].get('candidate_snapshot') != report.get('candidate_snapshot'):
        raise FlowError('Performance candidate snapshot mismatch')
    store.artifact(report['candidate_snapshot'])
    for record in (inputs['baseline'], inputs['candidate']):
        for sha in record['evidence']: store.artifact(sha)
    return result


def assess_iteration(correctness, baseline_times, candidate_times, context, max_regression=0.0):
    """Generic local operator timing screen; serving acceptance is separately gated."""
    reasons = validate_measurement(correctness, context)
    if correctness.get('profiler_off') is not True or not correctness.get('measurement_protocol'):
        reasons.append('profiler-off-and-protocol-required')
    if not isinstance(baseline_times, list) or not isinstance(candidate_times, list): raise FlowError('Repetitions must be arrays')
    if len(baseline_times) < 3 or len(baseline_times) != len(candidate_times): reasons.append('need-three-matched-repeats')
    if reasons: return {'status': 'incomplete', 'reasons': reasons}
    for x in baseline_times + candidate_times: number(x, 'time', True)
    limit = number(max_regression, 'max_regression')
    if limit < 0: raise FlowError('Negative regression budget')
    ratio = statistics.median(candidate_times) / statistics.median(baseline_times)
    return {'status': 'iteration-kept' if ratio <= 1 + limit else 'rejected', 'time_ratio': ratio,
            'quality': 'pending-inference-validation', 'production_default': False}
