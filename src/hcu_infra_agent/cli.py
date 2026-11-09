"""JSON command interface for inference Agents and operators."""
import argparse
import json
import os
import sqlite3
import subprocess
import urllib.error
import sys
from pathlib import Path
from . import __version__
from .core import FlowError, Store, read_json, write_json


def parser():
    p = argparse.ArgumentParser(prog='hcu-infra-agent')
    p.add_argument('--version', action='version', version=__version__)
    p.add_argument('--workspace', default=os.environ.get('HCU_INFRA_WORKSPACE', '.work'))
    subs = p.add_subparsers(dest='command', required=True)
    commands = {
        'init': [], 'task-create': ['file'], 'task-show': ['task'], 'task-context': ['task','file'],
        'task-transition':['task','state'], 'flow-start':['task','file'], 'flow-next':['task'],
        'flow-submit':['task','file'], 'flow-review':['task','file'], 'flow-advance':['task'],
        'flow-questions':['task'], 'flow-answer':['task','question','file'], 'flow-status-update':['task','file'], 'flow-watch':['task'], 'flow-board':['task'], 'flow-replan':['task','file'], 'flow-question':['task','file'],
        'flow-guidance-ack':['task','hash'], 'flow-question-close':['task','question'],
        'artifact-add':['file'], 'artifact-read':['sha','destination'], 'report-add':['task','kind','file'],
        'lease-acquire':['resource','owner'], 'lease-renew':['file'], 'lease-release':['file'],
        'command-plan':['file'], 'command-run':['task','operation','file','lease_file'],
        'command-group-plan':['file'], 'command-group-run':['task','operation','file','leases_file'],
        'command-group-status':['operation'], 'command-group-reconcile':['operation','file'],
        'operation-reconcile':['operation','file'], 'source-snapshot':['repository','paths'],
        'source-materialize':['snapshot','destination'], 'source-bundle':['snapshot','destination'],
        'source-receive':['archive','destination'], 'team-plan':['task','file'], 'team-next':['task'],
        'assignment-claim':['assignment','owner'], 'assignment-bind':['assignment','owner','session'],
        'assignment-return':['assignment','owner','report'], 'assignment-review':['assignment','file'],
        'assignment-cancel':['assignment','file'], 'agent-send':['task','file'], 'agent-inbox':['task'],
        'agent-ack':['message','owner','file'], 'environment-check':['contract','observations'],
        'occupancy-check':['contract','observations'], 'quality-check':['file'], 'performance-check':['file'],
        'iteration-check':['file'], 'profile-plan':['file'], 'profile-analyze':['trace','window'],
        'benchmark':['profile'], 'bind':['file','destination'], 'bindings-check':['file'],
        'knowledge-search':['file','query'], 'knowledge-discover':['file','query'], 'observe':['task','sample','policy'], 'inbox':[],
        'inbox-dispatch':['event','owner','file','lease_file'], 'events-export':['destination'],
        'demo':['destination'], 'report':['task','destination'],
    }
    for name, fields in commands.items():
        q=subs.add_parser(name)
        for field in fields: q.add_argument(field, nargs='+' if field == 'paths' else None)
        if name in {'task-transition','flow-replan'}: q.add_argument('--reason',required=name=='flow-replan')
        if name in {'lease-acquire','lease-renew'}:q.add_argument('--ttl',type=float,default=300)
        if name in {'assignment-bind','assignment-return'}:q.add_argument('--token',type=int,required=True)
        if name in {'command-run','command-group-run'}:
            q.add_argument('--assignment');q.add_argument('--owner');q.add_argument('--token',type=int)
        if name=='profile-analyze':q.add_argument('--models');q.add_argument('--groups')
        if name=='agent-inbox':q.add_argument('--recipient')
        if name=='flow-guidance-ack':q.add_argument('--decision',required=True,choices=['applied','queued','needs-human','not-applicable']);q.add_argument('--note',required=True)
        if name=='flow-question-close':q.add_argument('--guidance',required=True);q.add_argument('--note',required=True)
        if name=='flow-watch':q.add_argument('--once',action='store_true')
        if name=='flow-questions':q.add_argument('--refresh',action='store_true')
        if name=='flow-answer':q.add_argument('--version',required=True);q.add_argument('--file-hash',required=True);q.add_argument('--author',required=True)
        if name=='inbox':q.add_argument('--action',default='list',choices=['list','claim','complete','retry']);q.add_argument('--event');q.add_argument('--owner')
        if name=='events-export':q.add_argument('--after',type=int,default=0)
    from .module_cli import configure
    configure(subs)
    return p


def execute(a):
    from . import flow, team, execution, coordination, command_group, quality, analysis, monitor, bindings
    from . import admission, environment
    from .module_cli import dispatch, COMMANDS
    if a.command in COMMANDS:
        return dispatch(a)
    s=Store(a.workspace);c=a.command
    if c=='init':return {'workspace':str(s.root),'version':__version__}
    if c=='task-create':return s.create(read_json(a.file))
    if c=='task-show':return s.task(a.task)
    if c=='task-context':return s.change_context(a.task,read_json(a.file))
    if c=='task-transition':return s.transition(a.task,a.state,a.reason)
    if c in {'flow-start','flow-replan'}:return flow.start(s,a.task,read_json(a.file),getattr(a,'reason',None))
    if c=='flow-questions':
        from . import file_questions
        file_questions.scan(s,a.task,force=a.refresh);return file_questions.state(s,a.task)
    if c=='flow-answer':
        from . import file_questions
        result=file_questions.answer(s,a.task,a.question,a.version,a.file_hash,Path(a.file).read_text(encoding='utf-8-sig'),author=a.author)
        flow.render_board(s,a.task);return result
    if c=='flow-status-update':return flow.status_update(s,a.task,read_json(a.file))
    if c=='flow-next':return flow.next_step(s,a.task)
    if c=='flow-submit':return flow.submit(s,a.task,read_json(a.file))
    if c=='flow-review':return flow.review(s,a.task,read_json(a.file))
    if c=='flow-advance':return flow.advance(s,a.task)
    if c=='flow-watch':
        import time
        while True:
            change=flow.sync_guidance(s,a.task,force=a.once);result={**flow.render_board(s,a.task),**change}
            if a.once:return result
            if change.get('new') or change.get('questions_new'):print(json.dumps(result,ensure_ascii=False),flush=True)
            time.sleep(10)
    if c=='flow-board':return {**flow.sync_guidance(s,a.task,force=True),**flow.render_board(s,a.task)}
    if c=='flow-question':return flow.question(s,a.task,read_json(a.file))
    if c=='flow-guidance-ack':return flow.acknowledge(s,a.task,a.hash,a.decision,a.note)
    if c=='flow-question-close':return flow.close_question(s,a.task,a.question,a.guidance,a.note)
    if c=='artifact-add':return {'artifact':s.put(Path(a.file).read_bytes())}
    if c=='artifact-read':
        if Path(a.destination).exists():raise FlowError('Destination exists')
        from .core import atomic_write
        atomic_write(a.destination,s.artifact(a.sha));return {'destination':a.destination}
    if c=='report-add':return s.report(a.task,a.kind,read_json(a.file))
    if c=='lease-acquire':return s.lease(a.resource,a.owner,a.ttl)
    if c=='lease-renew':return s.renew(read_json(a.file),a.ttl)
    if c=='lease-release':return s.release(read_json(a.file))
    if c=='command-plan':return execution.command_plan(read_json(a.file))
    if c=='command-run':return execution.run_command(s,a.task,a.operation,read_json(a.file),read_json(a.lease_file),assignment=a.assignment,owner=a.owner,token=a.token)
    if c=='command-group-plan':return command_group.group_plan(read_json(a.file))
    if c=='command-group-run':return command_group.run_group(s,a.task,a.operation,read_json(a.file),read_json(a.leases_file),assignment=a.assignment,owner=a.owner,token=a.token)
    if c=='command-group-status':return command_group.group_status(s,a.operation)
    if c=='command-group-reconcile':return command_group.reconcile_group(s,a.operation,read_json(a.file))
    if c=='operation-reconcile':return coordination.reconcile_operation(s,a.operation,**read_json(a.file))
    if c=='source-snapshot':return execution.snapshot(s,a.repository,a.paths)
    if c=='source-materialize':return execution.materialize(s,a.snapshot,a.destination)
    if c=='source-bundle':return execution.bundle(s,a.snapshot,a.destination)
    if c=='source-receive':return execution.receive(s,a.archive,a.destination)
    if c=='team-plan':return team.plan(s,a.task,read_json(a.file))
    if c=='team-next':return team.schedule(s,a.task)
    if c=='assignment-claim':return team.claim(s,a.assignment,a.owner)
    if c=='assignment-bind':return team.bind(s,a.assignment,a.owner,a.token,a.session)
    if c=='assignment-return':return team.finish(s,a.assignment,a.owner,a.report,a.token)
    if c=='assignment-review':return team.review(s,a.assignment,read_json(a.file))
    if c=='assignment-cancel':return team.cancel(s,a.assignment,read_json(a.file))
    if c=='agent-send':return team.send(s,a.task,read_json(a.file))
    if c=='agent-inbox':return {'messages':team.messages(s,a.task,a.recipient)}
    if c=='agent-ack':return team.acknowledge(s,a.message,a.owner,read_json(a.file))
    if c=='environment-check':return environment.assess_health(read_json(a.contract),read_json(a.observations))
    if c=='occupancy-check':return admission.assess_occupancy(read_json(a.contract),read_json(a.observations))
    if c=='quality-check':return quality.compare_outputs(**read_json(a.file))
    if c=='performance-check':return quality.compare_performance(**read_json(a.file))
    if c=='iteration-check':return quality.assess_iteration(**read_json(a.file))
    if c=='profile-plan':
        v=read_json(a.file);return analysis.profile_plan(v['groups'],v['available'])
    if c=='profile-analyze':
        import gzip
        opener=gzip.open if a.trace.endswith('.gz') else open
        with opener(a.trace,'rt',encoding='utf-8') as stream:trace=json.load(stream)
        result=analysis.analyze_trace(trace,read_json(a.window),read_json(a.models) if a.models else None)
        if a.groups:
            coverage=analysis.profile_plan(read_json(a.groups),[int(x) for x in result['ranks'] if x.isdecimal()])
            result['rank_coverage']=coverage
            if coverage['status']!='pass':result['status']='incomplete'
        else:result['rank_coverage']={'status':'unassessed','reason':'Actual process groups not supplied'}
        return result
    if c=='benchmark':
        from .benchmark import measure
        result=measure(read_json(a.profile));proof=s.put(json.dumps(result,allow_nan=False).encode());return {**result,'evidence':[proof]}
    if c=='bind':return bindings.bind(read_json(a.file),a.destination)
    if c=='bindings-check':return bindings.verify(read_json(a.file))
    if c=='knowledge-discover':return bindings.discover(read_json(a.file),a.query)
    if c=='knowledge-search':return bindings.search(read_json(a.file),a.query)
    if c=='observe':return monitor.record(s,a.task,read_json(a.sample),read_json(a.policy))
    if c=='inbox':return monitor.inbox(s,a.action,a.event,a.owner)
    if c=='inbox-dispatch':return coordination.dispatch_inbox(s,a.event,a.owner,read_json(a.file),read_json(a.lease_file))
    if c=='events-export':write_json(a.destination,s.events(a.after));return {'destination':a.destination}
    if c=='demo':
        from .demo import run_demo
        return run_demo(a.destination)
    if c=='report':
        from .report import render
        return render(s,a.task,a.destination)
    raise FlowError('Unsupported command')


def main(argv=None):
    try:
        result=execute(parser().parse_args(argv));print(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))
        status=result.get('status') if isinstance(result,dict) else None
        return 2 if status in {'fail','failed','incomplete','rejected','unknown','attention','needs-repair','partial'} else 0
    except (FlowError,OSError,ValueError,KeyError,TypeError,sqlite3.Error,subprocess.SubprocessError,urllib.error.URLError) as exc:
        print(json.dumps({'status':'error','error':str(exc)},ensure_ascii=False),file=sys.stderr);return 1
    except KeyboardInterrupt:return 130


if __name__=='__main__':raise SystemExit(main())
