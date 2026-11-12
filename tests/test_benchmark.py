"""Exercise actual HTTP/SSE client I/O without GPU or external services."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from hcu_infra_agent.benchmark import measure, percentile
from hcu_infra_agent.core import FlowError


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
            events=[{'choices':[{'text':'hello'}]}, {'choices':[{'text':' world'}]},
                    {'usage':{'prompt_tokens':len(body['prompt']),'completion_tokens':body['max_tokens']}}]
            for event in events:self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(server.server_port)
    server.shutdown();server.server_close();thread.join()


def test_actual_stream_measurement_and_fixed_scenarios(endpoint):
    p={'base_url':endpoint,'model':'fixture','context':'c','candidate_snapshot':'s','identities':{k:'fixture' for k in ('model','tokenizer','quantization','workload','driver')},'repeats':3,
       'scenarios':[{'name':'decode','prompts':[[1,2,3],[4,5,6]],'output_tokens':2,'concurrency':2}]}
    r=measure(p)
    assert r['executed']==6 and len(r['scenarios']['decode']['throughput_tok_s'])==3
    assert r['raw']['decode'][0]['requests'][0]['text']=='hello world'
    p['repeats']=1
    single=measure(p)
    assert single['executed']==2 and len(single['scenarios']['decode']['throughput_tok_s'])==1
    p['repeats']=0
    with pytest.raises(FlowError):measure(p)


def test_tail_percentile_for_small_batches():
    assert percentile([1,100],.95)==100
