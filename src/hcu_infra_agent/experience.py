"""Private task summaries derived from retained reports, never shared automatically."""
from .core import write_json


def sync(store, tid):
    task = store.task(tid)
    with store.db() as db:
        reports = [dict(row) for row in store.current_reports(db, tid, task['context']).values()]
    path = store.root / 'experience' / (tid + '.json')
    write_json(path, {'task': tid, 'context': task['context'], 'state': task['state'], 'reports': reports,
                      'visibility': 'private', 'shared_knowledge_promoted': False})
    return {'status': 'archived', 'path': str(path), 'visibility': 'private'}
