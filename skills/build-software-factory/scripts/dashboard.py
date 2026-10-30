"""Local read-only factory overview. No server, commands, network or external discovery."""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
import json
import math
import os
from pathlib import Path
import tempfile
from gates import gate_rows, requirements
from integrity import check, safe_path

INPUTS = ('config.json', 'task-plan.json', 'verification.md', 'research.json')
MAX_BYTES = 2_000_000


def profile(config):
    value = config.get('dashboard', {})
    if not isinstance(value, dict) or set(value) - {'title', 'audience', 'work_item_label', 'stale_after_minutes'}:
        raise ValueError('Invalid dashboard profile')
    result = {'title': config['project']+' factory overview', 'audience': 'Project operators',
              'work_item_label': 'Work items', 'stale_after_minutes': 60, **value}
    for key in ('title', 'audience', 'work_item_label'):
        if not isinstance(result[key], str) or not 1 <= len(result[key].strip()) <= 200:
            raise ValueError('Dashboard labels must be nonempty text up to 200 characters')
    minutes = result['stale_after_minutes']
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 10080:
        raise ValueError('Dashboard freshness must be 1..10080 minutes')
    return result


def iso(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Timestamp needs timezone')
    return stamp


def observations(value, now, minutes):
    """Explicit, non-secret project measurements; never fetch a named source."""
    if not isinstance(value, dict) or set(value) != {'schema_version', 'metrics'} or value['schema_version'] != 1:
        raise ValueError('Invalid observations schema')
    if not isinstance(value['metrics'], list) or len(value['metrics']) > 50:
        raise ValueError('Observations need at most 50 metrics')
    result = []
    for row in value['metrics']:
        if not isinstance(row, dict) or set(row) != {'name', 'value', 'unit', 'source', 'observed_at', 'status'}:
            raise ValueError('Invalid metric fields')
        if any(not isinstance(row[k], str) or not 1 <= len(row[k]) <= 200 for k in ('name', 'unit', 'source', 'observed_at', 'status')):
            raise ValueError('Invalid metric text')
        if row['status'] not in ('measured', 'unavailable', 'proposed', 'error'):
            raise ValueError('Invalid metric status')
        number = row['value']
        if number is not None and (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number)):
            raise ValueError('Metric values must be finite numbers or null')
        if (row['status'] == 'measured') != (number is not None):
            raise ValueError('Only measured metrics have numeric values')
        stamp = iso(row['observed_at'])
        state = row['status']
        if stamp > now + timedelta(minutes=5):
            state = 'error: future timestamp'
        elif now - stamp > timedelta(minutes=minutes):
            state = 'stale ('+state+')'
        result.append({**row, 'freshness': state})
    return result


def summarize(files, *, now=None, sources=None, integrity='not checked: initial proposed snapshot', extra=None):
    """A versioned allowlist DTO; do not export raw config, evidence or handoff prose."""
    now = now or datetime.now(timezone.utc)
    config = json.loads(files['config.json'])
    settings = profile(config)
    plan = json.loads(files['task-plan.json'])
    from integrity import validate_task_plan
    validate_task_plan(plan)
    rows = gate_rows(files['verification.md'])
    expected = requirements(config, json.loads(files['research.json']))
    errors = []
    for gate, spec in expected.items():
        if gate not in rows or rows[gate]['stage'] != spec['stage']:
            errors.append('Missing or wrong-stage gate: '+gate)
    def freshness(value):
        if not value:
            return 'unavailable'
        try:
            stamp = iso(value)
            return 'future timestamp' if stamp > now+timedelta(minutes=5) else 'stale' if now-stamp > timedelta(minutes=settings['stale_after_minutes']) else 'recent'
        except (ValueError, TypeError):
            return 'invalid timestamp'
    gates = [{'id': key, 'stage': row['stage'], 'required': row['required']=='yes',
              'state': 'WAIVED' if row['required']=='no' else row['result'],
              'recorded_result': row['result'], 'revision': row['revision'], 'observed_at': row['checked_at'],
              'freshness': freshness(row['checked_at'])}
             for key, row in rows.items()]
    tasks = []
    for row in plan['tasks']:
        if row['status'] not in ('pending', 'in_progress', 'blocked', 'done'):
            errors.append('Unsupported task status: '+row['id'])
        tasks.append({'id': row['id'], 'state': row['status'], 'owner': str(row.get('owner', 'unassigned'))})
    counts = Counter(t['state'] for t in tasks)
    owners = sorted(set(t['owner'] for t in tasks))
    workers = [{'owner': owner, 'assigned': sum(t['owner']==owner for t in tasks),
                'in_progress': sum(t['owner']==owner and t['state']=='in_progress' for t in tasks),
                'liveness': 'unavailable'} for owner in owners]
    events = []
    for event in plan.get('events', []):
        events.append({'task': event['task_id'], 'time': event['timestamp'], 'state': event['status'],
                       'result': event['result'], 'revision': event['revision'], 'freshness': freshness(event['timestamp'])})
    def event_order(event):
        try:
            return iso(event['time']).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=timezone.utc)
    events.sort(key=event_order, reverse=True)
    release = next((g for g in gates if g['id']=='G3'), None)
    return {'schema_version': 1, 'profile': settings, 'captured_at': now.isoformat() if sources is not None else None,
            'expires_at': (now+timedelta(minutes=settings['stale_after_minutes'])).isoformat() if sources is not None else None,
            'mode': 'local read-only snapshot; recorded claims, not verified live activity',
            'integrity': integrity, 'errors': errors, 'sources': sources or [],
            'counts': {key: counts[key] for key in ('pending', 'in_progress', 'blocked', 'done')},
            'tasks': tasks, 'workers': workers, 'gates': gates, 'release': release,
            'events': events[:30], 'metrics': observations(extra, now, settings['stale_after_minutes']) if extra is not None else [],
            'usage': 'Unavailable: no measured usage source supplied. Configured budget is a proposed limit, not spending.'}


def read(factory, extra=None, now=None):
    root = safe_path(factory)
    # Integrity errors are explicit and fail closed; no untrusted partial data is promoted.
    check(root, quiet=True)
    files, sources = {}, []
    now = now or datetime.now(timezone.utc)
    config = json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    minutes = profile(config)['stale_after_minutes']
    for name in INPUTS:
        path = root/name
        stat = path.stat()
        if stat.st_size > MAX_BYTES:
            raise ValueError('Dashboard source too large: '+name)
        data = path.read_bytes()
        files[name] = data.decode('utf-8-sig')
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        state = 'future timestamp' if modified > now+timedelta(minutes=5) else 'stale' if now-modified > timedelta(minutes=minutes) else 'recent file change (not observation)'
        sources.append({'artifact': name, 'sha256': hashlib.sha256(data).hexdigest(),
                        'modified_at': modified.isoformat(), 'freshness': state})
    result = summarize(files, now=now, sources=sources,
                       integrity='Contract hashes/basic structure checked; evidence truth not attested', extra=extra)
    # Detect ordinary concurrent changes instead of silently mixing generations.
    if any(hashlib.sha256((root/s['artifact']).read_bytes()).hexdigest()!=s['sha256'] for s in sources):
        raise ValueError('Factory changed while reading; retry the snapshot')
    check(root, quiet=True)
    return result


STYLE = '''body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#101725;color:#edf2fc}main{max-width:1200px;margin:auto;padding:30px}h1{font-size:2rem;margin-bottom:4px}h2{font-size:1.25rem}p{color:#c7d2e5}section,.card{background:#1b263a;border:1px solid #3e506d;border-radius:12px;padding:18px;margin:18px 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px}.card strong{display:block;font-size:2rem}.card{margin:0}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{text-align:left;padding:10px;border-bottom:1px solid #3e506d;overflow-wrap:anywhere}th{color:#9fcef7}caption{text-align:left;color:#c7d2e5;padding-bottom:12px}.scroll{overflow:auto}.notice{border-left:5px solid #f4c367;padding-left:15px}small{color:#c7d2e5}a{color:#a8d9ff}nav{display:flex;gap:16px;flex-wrap:wrap}@media(max-width:600px){main{padding:16px}th,td{padding:6px}}'''


def page(data):
    def text(value):
        return escape(str(value), quote=True)
    def table(title, columns, rows, note=''):
        head = ''.join('<th scope="col">'+text(label)+'</th>' for _, label in columns)
        body = ''.join('<tr>'+''.join('<td>'+text(row.get(key, 'unavailable'))+'</td>' for key, _ in columns)+'</tr>' for row in rows)
        if not body:
            body = '<tr><td colspan="'+str(len(columns))+'">No recorded data</td></tr>'
        return '<section><h2>'+text(title)+'</h2><div class="scroll"><table><caption>'+text(note)+'</caption><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div></section>'
    profile_data = data['profile']
    title = text(profile_data['title'])
    body = '<header><p>FACTORY OVERVIEW · READ ONLY</p><h1>'+title+'</h1><p>'+text(profile_data['audience'])+'</p></header>'
    body += '<p class="notice">'+text(data['mode'])+'. No application check, release, watcher or worker was executed by this overview.</p>'
    body += '<p>Captured: '+text(data['captured_at'] or 'not captured; proposed scaffold')+'<br>Stale after: '+text(data['expires_at'] or 'initial snapshot is not current activity')+'. Compare this fixed snapshot with the current time; refresh explicitly.</p>'
    body += '<p>'+text(data['integrity'])+'</p>'
    if data['errors']:
        body += '<section class="notice"><h2>Data errors: readiness unavailable</h2>'+''.join('<p>'+text(e)+'</p>' for e in data['errors'])+'</section>'
    body += '<div class="cards">'+''.join('<div class="card">'+text(label)+'<strong>'+str(data['counts'][key])+'</strong>recorded</div>' for key, label in [('pending','Queued'),('in_progress','In progress'),('blocked','Blocked'),('done','Done')])+'</div>'
    body += table(profile_data['work_item_label'], [('id','ID'),('state','Recorded state'),('owner','Assigned owner')], data['tasks'], 'Task-plan records; not a live queue or verified completion.')
    body += table('Worker assignments', [('owner','Owner'),('assigned','Assigned'),('in_progress','Marked in progress'),('liveness','Live worker state')], data['workers'], 'Assignments do not prove a worker is running.')
    body += table('Verification gates and waivers', [('id','Gate'),('stage','Stage'),('state','State'),('recorded_result','Recorded result'),('revision','Revision'),('observed_at','Observation time'),('freshness','Freshness')], data['gates'], 'WAIVED never means passed. Recorded PASSED is not a readiness assessment; use the gate checker with an exact revision/target.')
    release = data['release']
    body += '<section><h2>Release confirmation</h2><p>'+text('G3 '+release['state']+' (recorded '+release['recorded_result']+')' if release else 'Unavailable: missing G3 record')+'</p><p>Recorded claim only; no live deployment/artifact query. Future post-action evidence is not required for pre-action readiness.</p></section>'
    body += table('Recent recorded events', [('time','Recorded time'),('task','Task'),('state','State'),('result','Result'),('freshness','Freshness')], data['events'], 'Latest 30 by parsed observation time; no event means activity is unavailable, not zero activity.')
    body += '<section><h2>Budget and usage</h2><p>'+text(data['usage'])+'</p></section>'
    body += table('Project observations', [('name','Metric'),('value','Value'),('unit','Unit'),('freshness','State'),('source','Source label'),('observed_at','Observed at')], data['metrics'], 'Explicit local adapter input only; source claims are not independently attested.')
    body += table('Artifact provenance', [('artifact','Artifact'),('modified_at','File modified'),('freshness','Freshness'),('sha256','SHA256')], data['sources'], 'File modification is not evidence of an observation. Raw evidence, goals, credentials, URLs and handoff prose are not exported.')
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+title+'</title><style>'+STYLE+'</style></head><body><main>'+body+'</main></body></html>\n'


def write_output(factory, output, content, replace=False):
    # Reject redirects before normalizing traversal; containment must compare
    # canonical lexical paths, including aliases with '..'.
    root = safe_path(os.path.abspath(safe_path(factory)))
    target = safe_path(os.path.abspath(safe_path(output)))
    if target == root or root in target.parents:
        raise ValueError('Runtime dashboard output must be outside the factory')
    if not target.parent.is_dir():
        raise ValueError('Output parent must already exist')
    if target.exists() and not replace:
        raise ValueError('Output exists; review it and explicitly use --replace')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False, mode='w', encoding='utf-8', newline='\n') as stream:
            temporary = Path(stream.name)
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, target)
        else:
            # Exclusive final create prevents an unnoticed concurrent overwrite.
            with target.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = Path(__file__).resolve().parent.parent if Path(__file__).parent.name == 'dashboard' else None
    parser.add_argument('--factory', default=str(default) if default else None, required=default is None)
    parser.add_argument('--output', required=True)
    parser.add_argument('--format', choices=('html', 'json'), default='html')
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--observations', help='Explicit approved local non-secret metric JSON; no URL fetching')
    args = parser.parse_args()
    extra = None
    if args.observations:
        path = safe_path(args.observations)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError('Observations file too large')
        extra = json.loads(path.read_text(encoding='utf-8-sig'))
    data = read(args.factory, extra)
    content = page(data) if args.format == 'html' else json.dumps(data, indent=2, ensure_ascii=False)+'\n'
    write_output(args.factory, args.output, content, args.replace)
    print('Snapshot written; no live activity attested: '+str(safe_path(args.output)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        # Avoid echoing raw malformed data or private file content.
        print('ERROR: Dashboard unavailable ('+type(exc).__name__+'); source integrity/schema or output path failed. No live actions executed.', file=sys.stderr)
        sys.exit(1)
