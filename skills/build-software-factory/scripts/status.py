"""Preview or record task status and evidence in one atomic living record."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from integrity import check, safe_path, validate_task_plan

STATUSES = ('blocked','pending','in_progress','done')
RESULTS = ('passed','failed','blocked','not-run')

def updated(plan, task_id, status, result, evidence, revision, environment, label):
    validate_task_plan(plan)
    for value in (evidence, revision, environment, label):
        if not value or not value.strip():
            raise ValueError('Evidence, revision, environment and check must be nonempty')
    tasks = {t['id']: t for t in plan['tasks']}
    if task_id not in tasks:
        raise ValueError('Unknown task ID')
    if status not in STATUSES or result not in RESULTS:
        raise ValueError('Unsupported status or result')
    if status == 'done':
        if result != 'passed':
            raise ValueError('Done requires passing evidence for the named revision')
        if any(tasks.get(dep,{}).get('status') != 'done' for dep in tasks[task_id].get('depends_on', [])):
            raise ValueError('Task dependencies are not done')
    event = {'id':str(uuid.uuid4()),'task_id':task_id,'timestamp':datetime.now(timezone.utc).isoformat(),
             'revision':revision,'environment':environment,'check':label,'result':result,'evidence':evidence,
             'old_status':tasks[task_id]['status'],'status':status}
    tasks[task_id]['status'] = status
    plan.setdefault('events',[]).append(event)
    return event

def record(factory, args):
    root = safe_path(factory)
    check(root, quiet=True)
    path = root/'task-plan.json'
    original = path.read_bytes()
    plan = json.loads(original.decode('utf-8-sig'))
    event = updated(plan, args.task, args.status, args.result, args.evidence, args.revision, args.environment, args.check)
    if not args.apply:
        print('PREVIEW: no files written. ' + json.dumps(event, ensure_ascii=False))
        return
    lock = root/'.factory-status.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    temporary = None
    try:
        if path.read_bytes() != original:
            raise ValueError('Concurrent task edit detected; no record written')
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', prefix='.status-', suffix='.tmp', dir=root, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(plan,stream,indent=2,ensure_ascii=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        lock.unlink()
    check(root, quiet=True)
    print('RECORDED (operator-supplied evidence, not independently executed): ' + json.dumps(event, ensure_ascii=False))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory',required=True)
    parser.add_argument('--task',required=True)
    parser.add_argument('--status',choices=STATUSES,required=True)
    parser.add_argument('--result',choices=RESULTS,required=True)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--environment',required=True)
    parser.add_argument('--check',required=True)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    record(args.factory, args)

if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: ' + str(exc),file=sys.stderr); sys.exit(1)
