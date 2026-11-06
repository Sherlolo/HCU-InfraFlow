"""Inference contract failures and complete durable lifecycle."""
import copy
import json
import pytest
from hcu_infra_agent import quality, flow
from hcu_infra_agent.core import Store, FlowError
from hcu_infra_agent.demo import run_demo
from hcu_infra_agent.monitor import record, inbox


@pytest.fixture
def inputs():
    identity={k:'fixed-'+k for k in quality.IDENTITIES}
    contract={'context':'context','identities':identity,'atol':.01,'rtol':0,'tolerance_basis':'fixed test reference','required_features':['streaming']}
    result={'context':'context','identities':identity,'executed':1,'status':'pass','candidate_path_exercised':True,'evidence':['raw'],
            'features':{'streaming':True,'tools':True},'samples':[{'id':'one','values':[1.,2.]}],'candidate_snapshot':'candidate'}
    return contract,result,copy.deepcopy(result)


def test_output_accepts_matched_samples(inputs):
    assert quality.compare_outputs(*inputs)['status']=='pass'


@pytest.mark.parametrize('change',['model','workload','features','numeric','context','skipped','dispatch'])
def test_output_regression_rejected(inputs,change):
    contract,base,candidate=inputs
    if change in {'model','workload'}:candidate['identities'][change]='changed'
    elif change=='features':candidate['features']['tools']=False
    elif change=='numeric':candidate['samples'][0]['values'][1]=3
    elif change=='context':candidate['context']='old'
    elif change=='skipped':candidate['skipped_required']=1
    elif change=='dispatch':candidate['candidate_path_exercised']=False
    assert quality.compare_outputs(contract,base,candidate)['status']=='fail'


def test_samples_cannot_be_reordered_or_nan(inputs):
    c,b,r=inputs;r['samples'][0]['id']='other'
    with pytest.raises(FlowError):quality.compare_outputs(c,b,r)
    r['samples'][0]['id']='one';r['samples'][0]['values'][0]=float('nan')
    with pytest.raises(FlowError):quality.compare_outputs(c,b,r)


def performance():
    ids={k:'fixed-'+k for k in quality.IDENTITIES}
    contract={'context':'c','identities':ids,'workload':'w','metric':'throughput_tok_s','min_gain':.05,'max_regression':.05,'sla':{'latency_p95_ms':100}}
    baseline={'context':'c','identities':ids,'workload':'w','status':'pass','executed':3,'profiler_off':True,'candidate_path_exercised':True,'evidence':['raw'],
              'scenarios':{'decode':{'throughput_tok_s':[100,101,99],'ttft_ms':[10,11,9],'tpot_ms':[2,2,2],'latency_p95_ms':[50,51,49]}}}
    candidate=copy.deepcopy(baseline);candidate['scenarios']['decode']['throughput_tok_s']=[110,111,109]
    return contract,baseline,candidate


def test_performance_sla_and_profile_exclusion():
    c,b,r=performance();assert quality.compare_performance(c,b,r)['status']=='pass'
    r['profiler_off']=False;assert quality.compare_performance(c,b,r)['status']=='fail'
    r['profiler_off']=True;r['scenarios']['decode']['latency_p95_ms']=[101,102,103]
    assert quality.compare_performance(c,b,r)['status']=='fail'


def test_short_repetitions_and_workload_mismatch():
    c,b,r=performance();r['workload']='other'
    assert quality.compare_performance(c,b,r)['status']=='fail'
    r['scenarios']['decode']['ttft_ms']=[1]
    with pytest.raises(FlowError):quality.compare_performance(c,b,r)


def test_full_protocol_and_forged_quality_report(tmp_path):
    result=run_demo(tmp_path/'demo');assert result['state']=='completed'
    s=Store(tmp_path/'demo/store');task=s.task('demo')
    with s.db() as db:
        states=[json.loads(r['payload'])['to'] for r in db.execute("SELECT payload FROM events WHERE kind='state-changed' ORDER BY seq")]
    assert all(state in states for state in ['environment_checked','baseline_validated','profiling','optimizing','serving_ready','serving','completed'])
    with pytest.raises(FlowError,match='quality_inputs'):
        s.report('demo','inference-quality',{'context':task['context'],'status':'pass','executed':1,'evidence':[s.put(b'raw')],'candidate_snapshot':'fake'})
    assert 'no HCU' in result['qualification']


def test_current_context_change_invalidates_reports(tmp_path):
    s=Store(tmp_path/'store');s.create({'schema_version':1,'task_id':'t','mode':'analyze','objective':'Analyze','context':{'source':'one'}})
    ctx=s.task('t')['context'];proof=s.put(b'raw')
    s.report('t','analysis',{'context':ctx,'status':'complete','evidence':[proof]})
    s.change_context('t',{'source':'two'});s.change_context('t',{'source':'one'})
    with s.db() as db:assert not s.current_reports(db,'t',ctx)


def test_service_incident_dedup_and_claim(tmp_path):
    s=Store(tmp_path/'s');task=s.create({'schema_version':1,'task_id':'t','mode':'operate','objective':'Watch','context':{'model':'m'},'recovery_owner':'site-owner'})
    sample={'context':task['context'],'attempt_id':'a','timestamp':100,'healthy':False}
    first=record(s,'t',sample,{'max_age_seconds':60},now=101)
    assert first['status']=='attention' and first['recovery_executed'] is False
    assert record(s,'t',sample,{},now=101)['duplicate'] is True
    messages=inbox(s);assert len(messages)==1
    event=messages[0]['event_id'];inbox(s,'claim',event,'agent')
    with pytest.raises(FlowError):inbox(s,'complete',event,'other')
    assert inbox(s,'complete',event,'agent')['status']=='complete'
