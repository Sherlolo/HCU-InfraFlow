"""Exercise documented command examples and evidence-producing profile analysis."""
import json
from pathlib import Path
from hcu_infra_agent.cli import main
from hcu_infra_agent.benchmark import validate_profile


def test_documented_task_flow_and_trace_command(tmp_path,capsys):
    root=Path(__file__).resolve().parents[1];args=['--workspace',str(tmp_path/'store')]
    assert main(args+['task-create',str(root/'examples/task.json')])==0
    capsys.readouterr()
    assert main(args+['flow-start','inference-demo',str(root/'examples/flow.json')])==0
    capsys.readouterr()
    assert main(args+['flow-next','inference-demo'])==0
    assert json.loads(capsys.readouterr().out)['action']=='work'
    validate_profile(json.loads((root/'examples/benchmark.json').read_text()))
    trace=tmp_path/'trace.json';window=tmp_path/'window.json';groups=tmp_path/'groups.json'
    trace.write_text(json.dumps({'traceEvents':[{'ph':'X','cat':'kernel','name':'gemm','ts':1,'dur':5,'args':{'rank':0,'phase':'prefill'}}]}))
    window.write_text(json.dumps({'start_us':0,'end_us':10}));groups.write_text(json.dumps([{'domain':'tp','ranks':[0]}]))
    status=main(args+['profile-analyze',str(trace),str(window),'--groups',str(groups)])
    result=json.loads(capsys.readouterr().out)
    assert status in {0,2} and result['rank_coverage']['status']=='pass'
