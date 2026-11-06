"""Bounded OpenAI-compatible streaming benchmarks against an explicitly selected service."""
import concurrent.futures
import json
import math
import statistics
import time
import urllib.request
from .core import FlowError, fingerprint
from .quality import number, IDENTITIES


def percentile(values, q):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def stream(base, model, prompt, output_tokens, timeout):
    payload = {'model': model, 'prompt': prompt, 'max_tokens': output_tokens, 'temperature': 0,
               'stream': True, 'stream_options': {'include_usage': True}, 'ignore_eos': True}
    req = urllib.request.Request(base.rstrip('/') + '/v1/completions', data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    started = time.perf_counter(); first = None; last = None; usage = {}; chunks = []; done = False
    with urllib.request.urlopen(req, timeout=timeout) as response:
        for raw in response:
            if not raw.startswith(b'data:'): continue
            line = raw[5:].strip()
            if line == b'[DONE]': done = True; break
            event = json.loads(line)
            if event.get('error'): raise FlowError('Serving endpoint reported an error')
            if event.get('usage'): usage = event['usage']
            for choice in event.get('choices', []):
                text = choice.get('text', '')
                if text:
                    last = time.perf_counter()
                    if first is None: first = last
                    chunks.append(text)
    ended = time.perf_counter()
    count = usage.get('completion_tokens')
    if not done or first is None or type(count) is not int or count != output_tokens:
        raise FlowError('Incomplete stream, missing usage, or changed output-token workload')
    if isinstance(prompt, list) and usage.get('prompt_tokens') != len(prompt):
        raise FlowError('Endpoint changed the input-token workload')
    return {'text': ''.join(chunks), 'output_tokens': count, 'input_tokens': usage.get('prompt_tokens'),
            'ttft_ms': (first-started)*1000, 'latency_ms': (ended-started)*1000,
            'tpot_ms': (last-first)*1000/(count-1) if count > 1 else 0}


def validate_profile(profile):
    from urllib.parse import urlsplit
    url = urlsplit(profile.get('base_url', ''))
    if url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password:
        raise FlowError('Specify an HTTP(S) service URL without embedded credentials')
    if not isinstance(profile.get('model'), str) or not profile['model']: raise FlowError('Specify a model')
    for key in ('context', 'candidate_snapshot', 'identities'):
        if not profile.get(key): raise FlowError('Missing measurement identity: ' + key)
    if not isinstance(profile['identities'],dict) or any(not isinstance(profile['identities'].get(k),str) or not profile['identities'][k] for k in IDENTITIES):
        raise FlowError('Freeze all model/tokenizer/quantization/workload/driver identities')
    if type(profile.get('repeats')) is not int or not 3 <= profile['repeats'] <= 100:
        raise FlowError('Use 3..100 measurement repeats')
    scenarios = profile.get('scenarios')
    if not isinstance(scenarios, list) or not scenarios: raise FlowError('Declare scenarios')
    seen = set()
    for scenario in scenarios:
        name = scenario.get('name')
        if not isinstance(name, str) or not name or name in seen: raise FlowError('Scenario names must be unique')
        seen.add(name)
        for key in ('output_tokens', 'concurrency'):
            if type(scenario.get(key)) is not int or scenario[key] <= 0: raise FlowError('Positive integer ' + key + ' required')
        prompts = scenario.get('prompts')
        if not isinstance(prompts, list) or not prompts or len(prompts) > 10000:
            raise FlowError('Provide 1..10000 fixed prompts per scenario')
        for prompt in prompts:
            if not (isinstance(prompt, str) and prompt or isinstance(prompt, list) and prompt and all(type(t) is int and t >= 0 for t in prompt)):
                raise FlowError('Prompts must be nonempty text or integer token arrays')
    timeout = number(profile.get('request_timeout', 300), 'request_timeout', True)
    if timeout > 3600: raise FlowError('Request timeout must be at most one hour')


def measure(profile):
    validate_profile(profile)
    workload = fingerprint({'model': profile['model'], 'scenarios': profile['scenarios'],
                            'repeats': profile['repeats'], 'warmup': profile.get('warmup', True),
                            'cache_policy': 'endpoint-state-not-reset'})
    results = {}; raw = {}
    for scenario in profile['scenarios']:
        def one(prompt):
            return stream(profile['base_url'], profile['model'], prompt, scenario['output_tokens'], profile.get('request_timeout', 300))
        if profile.get('warmup', True): one(scenario['prompts'][0])
        rounds = []
        for _ in range(profile['repeats']):
            started = time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=scenario['concurrency']) as pool:
                rows = list(pool.map(one, scenario['prompts']))
            elapsed = time.perf_counter()-started
            rounds.append({'throughput_tok_s': sum(r['output_tokens'] for r in rows)/elapsed,
                           'ttft_ms': statistics.mean(r['ttft_ms'] for r in rows),
                           'tpot_ms': statistics.mean(r['tpot_ms'] for r in rows),
                           'latency_p95_ms': percentile([r['latency_ms'] for r in rows], .95), 'requests': rows})
        results[scenario['name']] = {key: [r[key] for r in rounds] for key in ('throughput_tok_s', 'ttft_ms', 'tpot_ms', 'latency_p95_ms')}
        raw[scenario['name']] = rounds
    return {'status': 'pass', 'executed': sum(len(s['prompts']) for s in profile['scenarios'])*profile['repeats'],
            'context': profile['context'], 'candidate_snapshot': profile['candidate_snapshot'], 'identities': profile['identities'],
            'workload': workload, 'profiler_off': True, 'candidate_path_exercised': True, 'scenarios': results, 'raw': raw,
            'cache_policy': 'endpoint-state-not-reset', 'limits': 'Closed-loop client load; no assertion of exclusive GPU use or cache equivalence.'}
