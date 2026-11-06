"""Standalone escaped HTML reports from current Store evidence."""
import html
import json
from pathlib import Path
from .core import atomic_write


def render(store, tid, destination):
    task=store.task(tid)
    with store.db() as db:
        records=[dict(r) for r in store.current_reports(db,tid,task['context']).values()]
    escape=lambda x:html.escape(str(x))
    cards=[]
    for row in records:
        body=json.loads(store.artifact(row['artifact']))
        cards.append('<section><h2>'+escape(row['kind'])+' · '+escape(row['result'])+'</h2><p>SHA256 '+escape(row['artifact'])+'</p><pre>'+escape(json.dumps(body,indent=2,ensure_ascii=False))+'</pre></section>')
    text='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HCU Inference Report</title><style>body{max-width:1000px;margin:40px auto;padding:0 22px;font:16px/1.8 system-ui;background:#f3f6f2;color:#20332b}section{background:white;padding:24px;margin:20px 0;border-radius:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}p{overflow-wrap:anywhere}</style><h1>HCU 推理任务报告</h1><p>'+escape(task['spec']['objective'])+'</p><p>状态：'+escape(task['state'])+' · context '+escape(task['context'])+'</p><p>报告只展示当前上下文的证据；未提供的硬件、精度、性能或稳定性证据均未验收。</p>'+''.join(cards)+'</html>'
    atomic_write(destination,text)
    return {'status':'complete','destination':str(Path(destination).resolve()),'reports':len(records)}
