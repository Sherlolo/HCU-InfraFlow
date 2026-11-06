"""Service-health observations and durable incidents; recovery remains externally owned."""
import json
import time
from .core import FlowError, fingerprint
from .quality import number


def assess(sample, policy, now=None):
    now = time.time() if now is None else number(now, 'now')
    number(sample.get('timestamp'), 'timestamp')
    if sample['timestamp'] > now: raise FlowError('Future service observation')
    if type(sample.get('healthy')) is not bool: raise FlowError('Explicit healthy status required')
    issues = []
    if now-sample['timestamp'] > number(policy.get('max_age_seconds', 60), 'max_age_seconds', True): issues.append('observer-stale')
    if not sample['healthy']: issues.append('service-unhealthy')
    for key in ('ttft_ms', 'tpot_ms', 'latency_p95_ms', 'queue_depth', 'error_rate'):
        if key in policy:
            value = number(sample.get(key), key)
            if value < 0: raise FlowError('Negative service metric')
            if value > number(policy[key], key): issues.append('threshold:' + key)
    return {'status': 'attention' if issues else 'pass', 'issues': issues, 'recovery_executed': False}


def record(store, tid, sample, policy, now=None):
    task = store.task(tid)
    if sample.get('context') != task['context'] or not sample.get('attempt_id'):
        raise FlowError('Observation requires current context and attempt_id')
    result = assess(sample, policy, now)
    sid = fingerprint(sample)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT context FROM tasks WHERE id=?', (tid,)).fetchone()
        if current['context'] != task['context']: raise FlowError('Task changed while observing')
        previous = db.execute("SELECT 1 FROM events WHERE task=? AND kind='service-observation' AND json_extract(payload,'$.sample_id')=?", (tid,sid)).fetchone()
        if not previous:
            store.event(db, tid, 'service-observation', {'context': task['context'], 'sample_id': sid, 'sample':sample, **result}, channel='agent' if result['issues'] else None)
    return {**result, 'sample_id': sid, 'duplicate': bool(previous), 'recovery_owner': task['spec'].get('recovery_owner')}


def inbox(store, action='list', event_id=None, owner=None):
    with store.db() as db:
        if action == 'list':
            return [dict(r) for r in db.execute('SELECT o.*,e.task,e.kind,e.payload FROM outbox o JOIN events e USING(event_id) ORDER BY e.seq')]
        if action not in {'claim','complete','retry'} or not event_id or not owner: raise FlowError('Explicit inbox action/event/owner required')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM outbox WHERE event_id=?',(event_id,)).fetchone()
        if not row: raise FlowError('Unknown event')
        detail = json.loads(row['detail'] or '{}')
        if action == 'claim':
            if row['status'] not in {'pending','retry'}: raise FlowError('Event is not claimable')
            detail = {'owner':owner,'claimed_at':time.time()};status='claimed'
        else:
            if row['status'] != 'claimed' or detail.get('owner') != owner: raise FlowError('Only current claimant can acknowledge')
            status = 'complete' if action == 'complete' else 'retry'
        db.execute('UPDATE outbox SET status=?,detail=?,attempts=attempts+? WHERE event_id=?',(status,json.dumps(detail),int(action=='claim'),event_id))
    return {'status':status,'event_id':event_id,**detail}
