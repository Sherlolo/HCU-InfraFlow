"""CPU-only full workflow with explicitly synthetic inference evidence."""
import json
import sys
from pathlib import Path
from . import flow, quality, execution
from .core import FlowError, Store, write_json
from .report import render


def run_demo(destination):
    root=Path(destination).resolve()
    if root.exists(): raise FlowError('Demo destination must be new')
    s=Store(root/'store')
    task=s.create({'schema_version':1,'task_id':'demo','mode':'full','objective':'Exercise the full inference protocol with synthetic CPU fixtures',
                   'context':{'model':'synthetic','workload':'fixed-fixture','environment':'local-cpu'},'permissions':['execute'],'recovery_owner':'demo-external-owner'})
    flow.start(s,'demo',{'acceptance':{'protocol':'Complete all inference stages using declared synthetic inputs'}})
    source=root/'source';source.mkdir();(source/'check.py').write_text("print('CPU fixture only; no HCU inference claim')\n")
    snap=execution.snapshot(s,source,['check.py']);execution.materialize(s,snap['snapshot_id'],root/'run')
    lease=s.lease('cpu-fixture','author')
    run=execution.run_command(s,'demo','cpu-check',{'schema_version':1,'backend':'local','argv':[sys.executable,'check.py'],'cwd':str(root/'run'),'basis':'Bundled CPU-only fixture','timeout_seconds':30},lease)
    s.release(lease)
    proof=run['evidence'][0];snapshot=flow.retain(s,snap);ctx=task['context']
    identity={k:'synthetic-'+k for k in quality.IDENTITIES}
    qc={'context':ctx,'identities':identity,'atol':0.001,'rtol':0,'tolerance_basis':'Synthetic fixture only','required_features':['streaming']}
    qr={'context':ctx,'identities':identity,'status':'pass','executed':1,'candidate_path_exercised':True,'evidence':[proof],
        'features':{'streaming':True},'samples':[{'id':'fixed-prompt','values':[1.0,2.0]}],'candidate_snapshot':snapshot}
    qinputs=flow.retain(s,{'contract':qc,'baseline':qr,'candidate':qr})
    pc={'context':ctx,'identities':identity,'workload':'synthetic-workload','metric':'throughput_tok_s','min_gain':0,'max_regression':0}
    pr={'context':ctx,'identities':identity,'workload':'synthetic-workload','status':'pass','executed':3,'profiler_off':True,'candidate_path_exercised':True,'evidence':[proof],'candidate_snapshot':snapshot,
        'scenarios':{'prefill-decode':{'throughput_tok_s':[100,101,102],'ttft_ms':[10,11,12],'tpot_ms':[1,1,1],'latency_p95_ms':[20,21,22]}}}
    pinputs=flow.retain(s,{'contract':pc,'baseline':pr,'candidate':pr})
    experiment=flow.retain(s,{'context':ctx,'correctness':{'context':ctx,'status':'pass','executed':3,'candidate_path_exercised':True,'candidate_snapshot':snapshot,'evidence':[proof],'profiler_off':True,'measurement_protocol':'synthetic-fixture'},'baseline_times':[2,2,2],'candidate_times':[1,1,1]})
    rounds=[];analysis_sha=None
    while s.task('demo')['state']!='completed':
        decision=flow.next_step(s,'demo')
        if decision['action']=='advance':flow.advance(s,'demo');continue
        reports={}
        for kind in decision['required_reports']:
            body={'context':ctx,'status':'pass','executed':1,'evidence':[proof],'candidate_snapshot':snapshot,'qualification':'synthetic-cpu-fixture-no-hcu-claim'}
            if kind=='inference-quality':body.update(quality_inputs=qinputs,evidence=[proof,qinputs])
            if kind=='performance':body.update(performance_inputs=pinputs,evidence=[proof,pinputs])
            reports[kind]=s.report('demo',kind,body)['artifact']
            if kind=='analysis':analysis_sha=reports[kind]
        candidate={'author':'fixture-author','context':ctx,'goal':decision['goal'],'snapshot':snapshot,'summary':'Synthetic protocol fixture, not model validation','reports':reports,'target':decision['target'],'evidence':[proof]}
        if candidate['target']=='serving_ready':
            candidate.update(experiment=experiment,profile_evidence={'artifact':analysis_sha,'observation':'Fixture timeline','hypothesis':'Exercise protocol only','target':'synthetic local screen'})
        submitted=flow.submit(s,'demo',candidate)
        review=flow.next_step(s,'demo')
        if review['action']!='review':raise FlowError('Unexpected demo decision '+str(review))
        flow.review(s,'demo',{'round':review['round'],'candidate':review['candidate'],'goal':review['goal'],'context':ctx,'reviewer':'fixture-reviewer',
                  'verdict':'accept','summary':'Synthetic structured review fixture; no actual independent Agent or HCU validation',
                  'findings':[],'acceptance':{'protocol':'met'},'progress':'advanced','full_alignment':True,'evidence':[proof]})
        rounds.append(submitted['round']);flow.advance(s,'demo')
    report=render(s,'demo',root/'report.html')
    result={'status':'complete','state':s.task('demo')['state'],'rounds':rounds,'report':report['destination'],
            'qualification':'synthetic evidence and real CPU subprocess; no HCU benchmark, model accuracy or independent Agent claim'}
    write_json(root/'result.json',result);return result
