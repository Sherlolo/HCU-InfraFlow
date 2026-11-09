"""Five-module public contracts: evidence identity, read-only queries and real CPU subprocesses."""
import copy
import gzip
import json
import subprocess
import sys
from pathlib import Path
import pytest
from hcu_infra_agent import bindings, optimization, profiling, references
from hcu_infra_agent.core import FlowError, Store
from hcu_infra_agent.evidence import retain
from hcu_infra_agent.simulation import simulate, REQUIRED


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path/'store')
    s.create({'schema_version':1,'task_id':'t','mode':'optimize','objective':'Optimize fixed inference',
              'context':{'model':'fixed','engine':'fixed','workload':'w'}})
    return s


def trace_request(tmp_path):
    traces=[]
    for rank in (0,1):
        path=tmp_path/('rank-'+str(rank)+'.json.gz')
        with gzip.open(path,'wt') as f:
            json.dump({'distributedInfo':{'rank':rank},'traceEvents':[{'ph':'X','cat':'kernel','name':'gemm',
                      'ts':1,'dur':8,'args':{'shape':[2,2],'dtype':'bf16','phase':'prefill'}}]},f)
        traces.append({'rank':rank,'path':str(path),'window':{'start_us':0,'end_us':10}})
    return {'traces':traces,'groups':[{'domain':'tp','ranks':[0,1]}]}


def test_prof_and_plan_reject_replaced_evidence(store,tmp_path):
    request=trace_request(tmp_path)
    result=profiling.analyze(store,'t',request)
    plan={'analysis':result['analysis'],'observation':'GEMM covers the window','hypothesis':'Check existing dispatch',
          'target':'matching shape','validation':['numerics','profiler-off repeated serving']}
    ready=optimization.plan(store,'t',plan)
    assert ready['record']['execution_started'] is False
    assert len(result['report']['ranks'])==2
    newer=profiling.analyze(store,'t',{**request,'models':{}})
    # A genuinely changed report, not a repeated identical publication.
    body=newer['report'];body['note']='new capture';store.report('t','analysis',body)
    with pytest.raises(FlowError,match='stale|replaced'):optimization.plan(store,'t',plan)


@pytest.mark.parametrize('fault',['rank','coverage','empty'])
def test_prof_rejects_missing_or_misidentified_gpu_evidence(store,tmp_path,fault):
    request=trace_request(tmp_path)
    if fault=='rank':request['traces'][0]['rank']=3
    elif fault=='coverage':request['traces'].pop()
    else:request['traces'][0]['window']={'start_us':100,'end_us':200}
    with pytest.raises(FlowError):profiling.analyze(store,'t',request)


def make_binding(tmp_path):
    pilot=tmp_path/'pilot';kb=tmp_path/'kb';kb.mkdir()
    for relative in bindings.SKILLS.values():
        path=pilot/relative;path.mkdir(parents=True);(path/'SKILL.md').write_text('fixture')
    (kb/'kb.py').write_text('')
    cookbook=kb/'knowledge/inference-cookbook/local';cookbook.mkdir(parents=True)
    (cookbook/'qwen.md').write_text('# Qwen\nSGLang KV cache recipe\n```bash\npython -m sglang.launch_server\n```\n')
    subprocess.run(['git','init',str(kb)],capture_output=True,check=True)
    subprocess.run(['git','-C',str(kb),'add','knowledge'],capture_output=True,check=True)
    return bindings.bind({'pilot_root':str(pilot),'knowledge_root':str(kb),'cookbook_root':str(cookbook),
                          'cookbook_source_kind':'knowledge-mirror'},tmp_path/'binding.json')


def test_cookbook_search_read_and_escape(tmp_path):
    record=make_binding(tmp_path)
    found=references.search(record,'cookbook','SGLang KV')
    assert len(found['hits'])==1 and found['source']=='https://github.com/HYGON-AI/inference-cookbook-das'
    page=references.read(record,'cookbook',found['hits'][0]['relative_path'])
    assert page['lines'][3]['text']=='python -m sglang.launch_server'
    assert page['sha256']==found['hits'][0]['sha256']
    with pytest.raises(FlowError):references.read(record,'cookbook','../../../kb.py')
    assert references.search(record,'knowledge','no-such-model')['hits']==[]


def test_query_does_not_create_default_store(tmp_path,monkeypatch,capsys):
    from hcu_infra_agent.cli import main
    record=make_binding(tmp_path);path=tmp_path/'binding.json';path.write_text(json.dumps(record))
    monkeypatch.chdir(tmp_path)
    assert main(['cookbook-search',str(path),'SGLang'])==2
    assert not (tmp_path/'.work').exists()
    assert json.loads(capsys.readouterr().out)['hits']


def test_simulation_missing_runtime_is_not_a_prediction(store,tmp_path):
    record=make_binding(tmp_path)
    with pytest.raises(FlowError,match='simulation_python'):simulate(store,record,{'arguments':{}})


def test_simulation_rejects_invalid_dimensions(store,tmp_path):
    record=make_binding(tmp_path);record['simulation_python']=sys.executable
    from hcu_infra_agent.core import fingerprint
    record['identity']=fingerprint({k:v for k,v in record.items() if k!='identity'})
    args={k:1 for k in REQUIRED};args.update(model='qwen3',gpu='nmz',dp_attention=False,kv_cache_dtype='bf16',attention_compute_dtype='bf16')
    args['batch_size']=0
    with pytest.raises(FlowError):simulate(store,record,{'arguments':args})


def test_worker_executes_pinned_backend_and_preserves_assumptions(store,tmp_path,monkeypatch):
    package=tmp_path/'python';(package/'dcusim').mkdir(parents=True)
    config=package/'config.json';config.write_text('{"hidden_size":16}')
    params=', '.join(sorted(REQUIRED))
    source=f'''__version__='fixture-1'
def resolve_model_json(model): return {str(config)!r}
def dcusim({params}, generate_csv=False, verbose=False):
    print('fixture diagnostic')
    return {{'prefill_latency_ms':10.,'decode_latency_ms':1.,'sys_throughput_tps':100.}}
'''
    (package/'dcusim/__init__.py').write_text(source)
    monkeypatch.setenv('PYTHONPATH',str(package))
    record=make_binding(tmp_path);record['simulation_python']=sys.executable
    from hcu_infra_agent.core import fingerprint
    record['identity']=fingerprint({k:v for k,v in record.items() if k!='identity'})
    args={k:1 for k in REQUIRED};args.update(model='fixture',gpu='nmz',dp_attention=False,kv_cache_dtype='bf16',attention_compute_dtype='bf16')
    result=simulate(store,record,{'arguments':args})
    assert result['qualification']=='simulation-prediction' and result['hardware_executed'] is False
    assert result['backend_output']['backend']['version']=='fixture-1'
    assert result['backend_output']['effective_arguments']['generate_csv'] is False
    assert b'fixture diagnostic' in store.artifact(result['execution']['stderr']['sha256'])


def test_optimization_checks_require_same_snapshot_and_current_analysis(store,tmp_path):
    prof=profiling.analyze(store,'t',trace_request(tmp_path))
    p=optimization.plan(store,'t',{'analysis':prof['analysis'],'observation':'GPU cost','hypothesis':'Inspect dispatch',
                        'target':'gemm','validation':['outputs and serving repetitions']})
    snapshot=store.put(b'fixture source');raw=store.put(b'fixture measurements')
    ids={k:'fixed-'+k for k in ('model','tokenizer','quantization','workload','driver')};ids['workload']='w'
    base={'context':store.task('t')['context'],'identities':ids,'executed':3,'status':'pass',
          'candidate_path_exercised':True,'candidate_snapshot':snapshot,'evidence':[raw]}
    qr={**base,'features':{'streaming':True},'samples':[{'id':'a','text':'exact output'}]}
    qi={'contract':{'context':base['context'],'identities':ids,'atol':0,'rtol':0,'tolerance_basis':'exact fixture',
                   'required_features':['streaming']},'baseline':copy.deepcopy(qr),'candidate':copy.deepcopy(qr)}
    pr={**base,'workload':'w','profiler_off':True,'scenarios':{'decode':{'throughput_tok_s':[10,10,10],
        'ttft_ms':[1,1,1],'tpot_ms':[1,1,1],'latency_p95_ms':[3,3,3]}}}
    pi={'contract':{'context':base['context'],'identities':ids,'workload':'w','metric':'throughput_tok_s'},'baseline':copy.deepcopy(pr),'candidate':copy.deepcopy(pr)}
    request={'plan':p['plan'],'quality_inputs':retain(store,qi),'performance_inputs':retain(store,pi)}
    result=optimization.evaluate(store,'t',request)
    assert result['status']=='pass' and result['accepted_by_flow'] is False
    assert set(result['reports'])=={'inference-quality','performance'}
    bad=copy.deepcopy(pi);bad['candidate']['candidate_snapshot']=store.put(b'other source')
    with pytest.raises(FlowError,match='same candidate'):optimization.evaluate(store,'t',{**request,'performance_inputs':retain(store,bad)})
    bad=copy.deepcopy(qi);bad['candidate']['samples'][0]['text']='regressed'
    failed=optimization.evaluate(store,'t',{**request,'quality_inputs':retain(store,bad)})
    assert failed['status']=='fail'
    with store.db() as db:
        reports=store.current_reports(db,'t',store.task('t')['context'])
    assert reports['inference-quality']['result']=='fail' and reports['performance']['result']=='fail'


def test_hcu_cross_device_reduce_is_communication():
    from hcu_infra_agent.analysis import analyze_trace
    result=analyze_trace({'rank':0,'traceEvents':[{'ph':'X','cat':'kernel','name':'aiter::cross_device_reduce_1stage_naive',
        'ts':0,'dur':10,'args':{}}]}, {'start_us':0,'end_us':10})
    op=result['ranks']['0']['operators'][0]
    assert op['communication'] is True and op['assessment']['status']=='communication'


def test_knowledge_scope_is_explicit_and_curated_first(tmp_path):
    record=make_binding(tmp_path)
    root=Path(record['roots']['knowledge_root'])
    p=root/'knowledge/framework/local/topics/kv.md';p.parent.mkdir(parents=True);p.write_text('# KV\nSGLang KV cache tutorial\n')
    subprocess.run(['git','-C',str(root),'add','knowledge'],capture_output=True,check=True)
    curated=references.search(record,'knowledge','SGLang')
    all_pages=references.search(record,'knowledge','SGLang',search_scope='all')
    assert len(curated['hits'])==1 and curated['hits'][0]['path']==str(p)
    assert len(all_pages['hits'])==2
    assert curated['search_scope']=='curated' and all_pages['search_scope']=='all'


def test_external_tool_timeout_preserves_failed_invocation(store):
    from hcu_infra_agent.evidence import run_tool
    result=run_tool(store,'timeout-fixture',[sys.executable,'-c','import time;print("start",flush=True);time.sleep(20)'],timeout=1)
    assert result['status']=='incomplete' and result['timed_out'] is True
    assert b'start' in store.artifact(result['stdout']['sha256'])


@pytest.fixture(autouse=True)
def official_cookbook_fixture(monkeypatch):
    from hcu_infra_agent import cookbook
    def fake(url):
        if '/commits/' in url:return json.dumps({'sha':'a'*40}).encode()
        if '/git/trees/' in url:return json.dumps({'tree':[{'path':'qwen-sglang-kv.md'}]}).encode()
        return b'# Qwen\nSGLang KV cache recipe\n```bash\npython -m sglang.launch_server\n```\n'
    monkeypatch.setattr(cookbook,'fetch',fake)
