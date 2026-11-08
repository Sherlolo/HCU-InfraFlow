"""Real DCUSim offline predictions with explicit configuration and backend provenance."""
import json
from pathlib import Path
from . import bindings
from .core import FlowError
from .evidence import pin, retain, run_tool


REQUIRED = {'model','gpu','batch_size','seq_len','output_length', 'prefill_tp','prefill_dp','prefill_pp',
            'prefill_ep','prefill_cp','decode_tp','decode_dp','decode_pp','decode_ep','decode_cp',
            'prefill_nodes','decode_nodes','dp_attention','kv_cache_dtype','attention_compute_dtype'}


def simulate(store, record, request):
    bindings.verify(record)
    python = record.get('simulation_python')
    if not python or not Path(python).is_file():
        raise FlowError('Bind simulation_python to a prepared Python 3.10 DCUSim environment')
    args = request.get('arguments')
    if not isinstance(args, dict):
        raise FlowError('Simulation arguments must be an object')
    if REQUIRED - args.keys():
        raise FlowError('Declare all model/hardware/workload/parallelism/dtype inputs; missing: ' + ', '.join(sorted(REQUIRED - (args or {}).keys())))
    for key in REQUIRED - {'model','gpu','dp_attention','kv_cache_dtype','attention_compute_dtype'}:
        if type(args[key]) is not int or args[key] <= 0:
            raise FlowError('Positive integer required: ' + key)
    if type(args['dp_attention']) is not bool:
        raise FlowError('dp_attention must be boolean')
    if not all(isinstance(args[k], str) and args[k] for k in ('model','gpu','kv_cache_dtype','attention_compute_dtype')):
        raise FlowError('Model, hardware and dtypes must be explicit strings')
    if 'model_json_path' in args:
        raise FlowError('Pass a custom model JSON using the model field so its bytes can be pinned')
    if 'output_path' in args or any('output_dir' in k or 'output_file' in k for k in args):
        raise FlowError('Simulation output is owned by its private run directory')
    args = {**args, 'generate_csv': False, 'verbose': False}
    model_pin = None
    if args['model'].endswith('.json'):
        model_pin = pin(store, args['model'])
        model_path = store.root / 'modules' / 'simulation-inputs' / (model_pin['sha256']+'.json')
        model_path.parent.mkdir(parents=True, exist_ok=True)
        model_path.write_bytes(store.artifact(model_pin['sha256']))
        args['model'] = str(model_path)
    for key in ('util_profile','engram_table','prefill_engram_table','decode_engram_table'):
        if args.get(key):
            raise FlowError('File-valued simulator option requires a dedicated pinned adapter: ' + key)
    input_hash = retain(store, args)
    path = store.root / 'modules' / 'simulation-inputs' / (input_hash+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(store.artifact(input_hash))
    worker = Path(__file__).with_name('simulation_worker.py')
    worker_pin = pin(store, worker)
    tool = run_tool(store, 'simulation', [python, worker, path], request.get('timeout', 120))
    if tool['status'] != 'complete':
        return {'status': 'incomplete', 'reason': 'dcusim-failed-or-timeout', 'execution': tool, 'hardware_executed': False}
    try:
        output = json.loads(store.artifact(tool['stdout']['sha256']))
    except (ValueError, TypeError) as exc:
        raise FlowError('DCUSim worker returned invalid JSON; inspect ' + tool['cwd']) from exc
    if not isinstance(output, dict) or not isinstance(output.get('result'), dict):
        raise FlowError('DCUSim must return a result object')
    raw = output['result']
    summary = {'prefill_latency_ms':raw.get('prefill_latency_ms'), 'decode_latency_ms':raw.get('decode_latency_ms'),
               'throughput_tok_s':raw.get('sys_throughput_tps'), 'memory_feasible':raw.get('memory_feasible_with_activation',raw.get('memory_feasible')),
               'prefill_memory_gib':raw.get('prefill_total_memory_with_act_gb',raw.get('prefill_memory_gb')),
               'decode_memory_gib':raw.get('decode_total_memory_with_act_gb',raw.get('decode_memory_gb'))}
    result = {'status': 'incomplete' if raw.get('error') else 'complete', 'summary':summary, 'qualification': 'simulation-prediction', 'hardware_executed': False,
              'input': request, 'backend_output': output, 'model_input': model_pin,
              'evidence': [input_hash, worker_pin['sha256'], tool['artifact'], tool['stdout']['sha256']],
              'execution': tool, 'limits': 'DCUSim model assumptions and defaults are recorded; predictions do not satisfy measured quality/performance gates.'}
    return {**result, 'artifact': retain(store, result)}
