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
import re
from pathlib import Path
import tempfile
from gates import gate_rows, requirements
from integrity import check, safe_path
from readiness import report

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
            'integrity': integrity, 'errors': errors, 'sources': sources or [], 'context':report(config),
            'counts': {key: counts[key] for key in ('pending', 'in_progress', 'blocked', 'done')},
            'tasks': tasks, 'workers': workers, 'gates': gates, 'release': release,
            'events': events[:30], 'metrics': observations(extra, now, settings['stale_after_minutes']) if extra is not None else [],
            'usage': 'Unavailable: no measured usage source supplied. Configured budget is a proposed limit, not spending.'}


def run_records(runs, limit=20):
    """Recent factory-run records, read-only; an unreadable record is skipped, never guessed."""
    result = []
    if not runs.is_dir():
        return result
    for path in sorted(runs.glob('run-*.json'), reverse=True)[:limit]:
        if path.stat().st_size > MAX_BYTES:
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or not isinstance(record.get('run_id'), str) or record.get('outcome') not in ('completed', 'blocked', 'stopped', 'failed'):
            continue
        dispatched = record.get('dispatched')
        result.append({'run_id': record['run_id'], 'started': str(record.get('started', '')), 'finished': str(record.get('finished', '')),
                       'outcome': record['outcome'], 'dispatched': [str(x) for x in dispatched] if isinstance(dispatched, list) else [],
                       'notes': str(record.get('notes', ''))[:200]})
    return result


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
    result['runs'] = run_records(root.parent/'.factory-runs')
    # Detect ordinary concurrent changes instead of silently mixing generations.
    if any(hashlib.sha256((root/s['artifact']).read_bytes()).hexdigest()!=s['sha256'] for s in sources):
        raise ValueError('Factory changed while reading; retry the snapshot')
    check(root, quiet=True)
    return result


STYLE = """
:root{--bg:#f6f7fb;--panel:#ffffff;--line:#e3e7ef;--ink:#17202e;--muted:#5d6b80;--accent:#2f6fed;--ok:#1f9d55;--bad:#d6453d;--warn:#d98a0b;--off:#9aa5b5;--waive:#7a5af5;--chip:#eef2f8}
@media(prefers-color-scheme:dark){:root{--bg:#0f141c;--panel:#161d28;--line:#273244;--ink:#e8edf5;--muted:#9aa8bd;--accent:#6ea0ff;--ok:#3ec27a;--bad:#ff6b63;--warn:#f0b541;--off:#6b7788;--waive:#a48cff;--chip:#1f2a3a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1240px;margin:auto;padding:28px 24px 48px}
header{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:22px}
header h1{margin:0;font-size:1.9rem;letter-spacing:-.01em}header .sub{color:var(--muted);margin:4px 0 0}
.meta{display:flex;flex-wrap:wrap;gap:8px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:999px;background:var(--chip);color:var(--muted);font-size:.8rem;white-space:nowrap}
.chip b{color:var(--ink);font-weight:600}
.pill{display:inline-block;white-space:nowrap;padding:2px 9px;border-radius:999px;font-size:.75rem;font-weight:600;letter-spacing:.02em;color:#fff;background:var(--off)}
.pill.ok{background:var(--ok)}.pill.bad{background:var(--bad)}.pill.warn{background:var(--warn)}.pill.waive{background:var(--waive)}.pill.run{background:var(--accent)}
.grid{display:grid;gap:16px}.g4{grid-template-columns:repeat(4,1fr)}.g2{grid-template-columns:3fr 2fr}
@media(max-width:900px){.g4{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.panel h2{margin:0 0 4px;font-size:1rem}.panel .note{margin:0 0 12px;color:var(--muted);font-size:.85rem}
.stat{display:flex;flex-direction:column;gap:2px}.stat .n{font-size:2.2rem;font-weight:700;line-height:1.1}.stat .l{color:var(--muted);font-size:.85rem}
.bar{display:flex;height:10px;border-radius:999px;overflow:hidden;background:var(--chip);margin:10px 0 6px}.bar i{display:block;height:100%}
.legend{display:flex;flex-wrap:wrap;gap:12px;color:var(--muted);font-size:.8rem}.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.flow{display:flex;align-items:stretch;gap:0;margin:6px 0 2px;overflow:auto}
.step{flex:1;min-width:120px;position:relative;padding:12px 14px 12px 22px;background:var(--chip);clip-path:polygon(0 0,calc(100% - 14px) 0,100% 50%,calc(100% - 14px) 100%,0 100%,14px 50%)}
.step:first-child{clip-path:polygon(0 0,calc(100% - 14px) 0,100% 50%,calc(100% - 14px) 100%,0 100%);padding-left:14px}
.step .t{font-weight:600;font-size:.85rem}.step .d{color:var(--muted);font-size:.78rem;margin-top:2px}
.step.on{background:var(--accent);color:#fff}.step.on .d{color:#e4ecff}
.ring{width:96px;height:96px;border-radius:50%;display:grid;place-items:center;flex:none}
.ring span{width:72px;height:72px;border-radius:50%;background:var(--panel);display:grid;place-items:center;font-weight:700;font-size:1.1rem}
.row{display:flex;gap:18px;align-items:center}
table{border-collapse:collapse;width:100%;font-size:.88rem}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);overflow-wrap:anywhere;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}tr:last-child td{border-bottom:0}
.scroll{overflow:auto}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--off);margin-right:6px}.dot.ok{background:var(--ok)}.dot.warn{background:var(--warn)}.dot.bad{background:var(--bad)}
.tl{list-style:none;margin:0;padding:0 0 0 18px;border-left:2px solid var(--line)}.tl li{position:relative;padding:0 0 14px 14px}.tl li:last-child{padding-bottom:0}
.tl li::before{content:"";position:absolute;left:-24px;top:6px;width:10px;height:10px;border-radius:50%;background:var(--off);border:2px solid var(--panel)}
.tl li.ok::before{background:var(--ok)}.tl li.bad::before{background:var(--bad)}.tl li.warn::before{background:var(--warn)}.tl li.run::before{background:var(--accent)}
.tl .when{color:var(--muted);font-size:.78rem}.tl .what{font-weight:600}
details{border-top:1px solid var(--line);padding:10px 0}details summary{cursor:pointer;color:var(--muted);font-size:.9rem;font-weight:600}details[open] summary{margin-bottom:8px}
.empty{color:var(--muted);font-size:.88rem;padding:8px 0}
.alert{border-left:4px solid var(--bad);background:var(--chip);padding:10px 14px;border-radius:8px;margin-bottom:16px}
footer{color:var(--muted);font-size:.8rem;margin-top:26px;text-align:center}
mark{background:transparent;color:var(--muted)}
@media(max-width:700px){.flow{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}.step,.step:first-child{clip-path:none;border-radius:10px;padding:10px 12px;min-width:0}.chip{white-space:normal}}
"""

GATE_CLASS = {'PASSED': 'ok', 'FAILED': 'bad', 'BLOCKED': 'warn', 'WAIVED': 'waive', 'NOT RUN': '', 'NOT APPLICABLE': ''}
RUN_CLASS = {'completed': 'ok', 'failed': 'bad', 'blocked': 'warn', 'stopped': ''}
TASK_CLASS = {'done': 'ok', 'in_progress': 'run', 'blocked': 'warn', 'pending': ''}


def page(data):
    def text(value):
        return escape(str(value), quote=True)
    def when(value):
        # Display form only: drop sub-second precision; raw timestamps remain in the JSON DTO.
        return text(re.sub(r'\.\d+(?=[+-]\d\d:\d\d$|Z$)', '', str(value)).replace('T', ' '))
    def pill(label, cls):
        return '<span class="pill '+cls+'">'+text(label)+'</span>'
    def table(columns, rows, render=None):
        head = ''.join('<th scope="col">'+text(label)+'</th>' for _, label in columns)
        body = ''
        for row in rows:
            cells = ''
            for key, _ in columns:
                value = row.get(key, 'unavailable')
                cells += '<td>'+((render or {}).get(key, lambda v, r: text(v))(value, row))+'</td>'
            body += '<tr>'+cells+'</tr>'
        if not body:
            return '<p class="empty">No recorded data</p>'
        return '<div class="scroll"><table><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div>'
    def panel(title, note, inner):
        return '<section class="panel"><h2>'+text(title)+'</h2><p class="note">'+text(note)+'</p>'+inner+'</section>'

    profile_data, counts, gates, context = data['profile'], data['counts'], data['gates'], data['context']
    title = text(profile_data['title'])
    captured = data['captured_at'] or 'not captured; proposed scaffold'
    expires = data['expires_at'] or 'initial snapshot'
    total = sum(counts.values()) or 1
    required = [g for g in gates if g['required']]
    passed = [g for g in required if g['state'] == 'PASSED']
    pre = [g for g in gates if g['stage'] == 'pre-merge']
    runs = data.get('runs', [])
    release = data['release']

    # Header
    body = '<header><div><h1>'+title+'</h1><p class="sub">'+text(profile_data['audience'])+' · read-only snapshot of recorded claims</p></div>'
    body += '<div class="meta"><span class="chip">captured <b>'+when(captured)+'</b></span><span class="chip">stale after <b>'+when(expires)+'</b></span><span class="chip">integrity <b>'+text(data['integrity'])+'</b></span></div></header>'
    if data['errors']:
        body += '<div class="alert"><strong>Data errors; readiness unavailable.</strong> '+' · '.join(text(e) for e in data['errors'])+'</div>'

    # Flow
    phase_counts = [('Intake', str(len(context['assumptions']))+' assumption'+('' if len(context['assumptions'])==1 else 's'), False),
                    ('Plan', str(total if sum(counts.values()) else 0)+' task'+('' if total==1 else 's'), False),
                    ('Build', str(counts['in_progress'])+' in progress', counts['in_progress']>0),
                    ('Verify', str(sum(g['state']=='PASSED' for g in pre))+'/'+str(len(pre))+' pre-merge passed', False),
                    ('Release', 'G3 '+(release['state'] if release else 'missing'), bool(release and release['state']=='PASSED')),
                    ('Learn', str(len(data['events']))+' event'+('' if len(data['events'])==1 else 's'), False)]
    body += '<div class="flow">'+''.join('<div class="step'+(' on' if on else '')+'"><div class="t">'+text(name)+'</div><div class="d">'+text(detail)+'</div></div>' for name, detail, on in phase_counts)+'</div>'
    body += '<p class="note" style="margin:4px 0 18px;color:var(--muted);font-size:.8rem">Phase counts are derived from recorded tasks, gates and events; nothing here ran.</p>'

    # Stats
    segs = [('pending','Queued','var(--off)'),('in_progress','In progress','var(--accent)'),('blocked','Blocked','var(--warn)'),('done','Done','var(--ok)')]
    tiles = ''.join('<div class="panel stat"><span class="n">'+str(counts[k])+'</span><span class="l">'+text(l)+'</span></div>' for k, l, _ in segs)
    body += '<div class="grid g4" style="margin-bottom:16px">'+tiles+'</div>'
    bar = ''.join('<i style="width:'+str(round(100*counts[k]/total, 2))+'%;background:'+c+'"></i>' for k, _, c in segs)
    legend = ''.join('<span><i style="background:'+c+'"></i>'+text(l)+' '+str(counts[k])+'</span>' for k, l, c in segs)
    pct = round(100*len(passed)/len(required)) if required else 0
    ring = ('<div class="ring" style="background:conic-gradient(var(--ok) '+str(pct)+'%,var(--chip) 0)"><span>'+str(len(passed))+'/'+str(len(required))+'</span></div>')
    gate_pills = ' '.join(pill(g['id']+' '+g['state'], GATE_CLASS.get(g['state'], 'warn')) for g in gates)
    body += '<div class="grid g2" style="margin-bottom:16px">'
    body += panel('Progress', 'Recorded task states; not a live queue.', '<div class="bar">'+bar+'</div><div class="legend">'+legend+'</div>')
    body += panel('Required gates passed', 'For the recorded revisions; readiness for one revision comes from the gate checker.', '<div class="row">'+ring+'<div>'+gate_pills+'</div></div>')
    body += '</div>'

    # Tables
    body += '<div class="grid g2" style="margin-bottom:16px">'
    body += panel(profile_data['work_item_label'], 'From task-plan.json.', table([('id','ID'),('state','State'),('owner','Owner')], data['tasks'],
                   {'state': lambda v, r: pill(v.replace('_',' '), TASK_CLASS.get(v, ''))}))
    body += panel('Gates and waivers', 'WAIVED keeps its recorded result and never counts as passed.',
                  table([('id','Gate'),('stage','Stage'),('state','State'),('revision','Revision'),('freshness','Freshness')], gates,
                        {'stage': lambda v, r: '<span style="white-space:nowrap">'+text(v)+'</span>', 'state': lambda v, r: pill(v, GATE_CLASS.get(v, 'warn')),
                         'freshness': lambda v, r: '<span class="dot '+{'recent':'ok','stale':'warn'}.get(v, 'bad' if v in ('invalid timestamp','future timestamp') else '')+'"></span>'+text(v)}))
    body += '</div>'

    # Runs and events
    body += '<div class="grid g2" style="margin-bottom:16px">'
    if runs:
        items = ''.join('<li class="'+RUN_CLASS.get(r['outcome'], '')+'"><div class="when">'+when(r['started'])+(' → '+when(r['finished']) if r.get('finished') and r['finished']!=r['started'] else '')+'</div><div class="what">'+text(r['run_id'])+' '+pill(r['outcome'], RUN_CLASS.get(r['outcome'], ''))+'</div><div>'+(text(', '.join(r['dispatched'])) if r['dispatched'] else '<mark>nothing dispatched</mark>')+(' · '+text(r['notes']) if r.get('notes') else '')+'</div></li>' for r in runs)
        runs_html = '<ul class="tl">'+items+'</ul>'
    else:
        runs_html = '<p class="empty">No run records in .factory-runs/ yet.</p>'
    body += panel('Factory passes', 'Run records written by factory-run.', runs_html)
    if data['events']:
        items = ''.join('<li class="'+{'passed':'ok','failed':'bad','blocked':'warn'}.get(e['result'], '')+'"><div class="when">'+when(e['time'])+' · '+text(e['freshness'])+'</div><div class="what">'+text(e['task'])+' → '+text(e['state'].replace('_',' '))+' '+pill(e['result'], {'passed':'ok','failed':'bad','blocked':'warn'}.get(e['result'], ''))+'</div><div><mark>'+text(e['revision'])+'</mark></div></li>' for e in data['events'])
        events_html = '<ul class="tl">'+items+'</ul>'
    else:
        events_html = '<p class="empty">No recorded events; activity is unavailable, not zero.</p>'
    body += panel('Recent evidence events', 'Latest 30 status/evidence records by observation time.', events_html)
    body += '</div>'

    # Details
    watcher = context['watcher']
    details = '<details><summary>Continuous intake · '+text(watcher['state'])+'</summary>'+''.join('<p class="note">'+text(d)+'</p>' for d in watcher['diagnostics'])+'</details>'
    details += '<details><summary>Assumptions · '+str(len(context['assumptions']))+' recorded</summary>'+table([('id','Assumption'),('status','Status'),('blocker_count','Blockers')], context['assumptions'])+'<p class="note">Text and sources stay in the private config.</p></details>'
    details += '<details><summary>Workers</summary>'+table([('owner','Owner'),('assigned','Assigned'),('in_progress','In progress'),('liveness','Live state')], data['workers'])+'</details>'
    details += '<details><summary>Project observations and usage</summary>'+table([('name','Metric'),('value','Value'),('unit','Unit'),('freshness','State'),('source','Source'),('observed_at','Observed')], data['metrics'])+'<p class="note">'+text(data['usage'])+'</p></details>'
    details += '<details><summary>Artifact provenance</summary>'+table([('artifact','Artifact'),('modified_at','Modified'),('freshness','Freshness'),('sha256','SHA256')], data['sources'])+'</details>'
    body += '<section class="panel">'+details+'</section>'
    body += '<footer>'+text(data['mode'])+'. No application check, release, watcher or worker was executed by this overview.</footer>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'"><title>'+title+'</title><style>'+STYLE+'</style></head><body><main>'+body+'</main></body></html>\n'


def write_output(factory, output, content, replace=False):
    # Reject redirects before normalizing traversal; containment must compare
    # canonical lexical paths, including aliases with '..'.
    root = safe_path(os.path.abspath(safe_path(factory)))
    target = safe_path(os.path.abspath(safe_path(output)))
    # Device/extended namespaces and short/UNC aliases can differ lexically while
    # identifying the same directory on Windows. Reject special namespaces and
    # compare existing ancestor identities as well as normalized path spelling.
    for path in (root, target):
        if str(path).replace('/', '\\').startswith(('\\\\?\\', '\\\\.\\', '\\??\\')):
            raise ValueError('Device/extended namespace paths are not supported')
    if not root.is_dir():
        raise ValueError('Factory must be an existing directory')
    if target == root or root in target.parents or any(parent.exists() and parent.samefile(root) for parent in (target, *target.parents)):
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
