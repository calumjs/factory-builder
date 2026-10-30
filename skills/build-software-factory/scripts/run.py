"""Drive a factory pass: select eligible work, plan bounded parallel workers,
render scheduler definitions and record runs. Read-only against the factory;
run records live outside it. Executes no worker, scheduler, agent or GitHub call."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import uuid
from integrity import check, safe_path, validate_task_plan

STOP_FILE = 'STOP'
STOP_ENV = 'FACTORY_STOP'
MIN_INTERVAL_MINUTES = 60
OUTCOMES = ('completed', 'blocked', 'stopped', 'failed')
SCHEDULERS = ('cron', 'launchd', 'windows', 'github')


def utcnow():
    return datetime.now(timezone.utc)


def load(factory):
    root = safe_path(factory)
    check(root, quiet=True)
    config = json.loads((root / 'config.json').read_text(encoding='utf-8-sig'))
    plan = json.loads((root / 'task-plan.json').read_text(encoding='utf-8-sig'))
    validate_task_plan(plan)
    return root, config, plan


def runs_dir(root, override):
    if override:
        path = safe_path(override)
    else:
        path = root.parent / '.factory-runs'
    if path == root or root in path.parents:
        raise ValueError('Run records must live outside the factory directory')
    return path


def kill_switch(runs):
    if os.environ.get(STOP_ENV, '').strip() not in ('', '0', 'false'):
        return 'environment ' + STOP_ENV
    if (runs / STOP_FILE).exists():
        return 'file ' + str(runs / STOP_FILE)
    return None


def run_records(runs):
    records = []
    if not runs.is_dir():
        return records
    for path in sorted(runs.glob('run-*.json')):
        try:
            record = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and isinstance(record.get('started'), str):
            records.append(record)
    return records


def dispatched_last_hour(records, now):
    since = now - timedelta(hours=1)
    count = 0
    for record in records:
        try:
            started = datetime.fromisoformat(record['started'])
        except ValueError:
            continue
        if started >= since:
            count += len(record.get('dispatched', []))
    return count


def operations(config):
    ops = config.get('operations') or {}
    autonomy = dict({'mode': 'manual', 'max_items_per_hour': 0, 'allowed_submitters': []}, **(ops.get('autonomy') or {}))
    intake = dict({'mode': 'one_shot', 'cadence': 'unconfirmed'}, **(ops.get('issue_intake') or {}))
    return autonomy, intake


def issue_candidates(issues, autonomy, known_ids):
    """Filter a read-only issue snapshot. Emits candidate IDs and reasons only."""
    accepted, rejected = [], []
    allowed = set(autonomy.get('allowed_submitters') or [])
    def order(i):
        return (str(i.get('created_at', '')), str(i.get('id', ''))) if isinstance(i, dict) else ('', '')
    for issue in sorted(issues, key=order):
        if not isinstance(issue, dict) or not isinstance(issue.get('id'), str) or not issue['id'].strip():
            rejected.append({'id': None, 'reason': 'malformed issue entry'})
            continue
        issue_id = issue['id']
        if issue_id in known_ids:
            rejected.append({'id': issue_id, 'reason': 'already in task plan'})
        elif autonomy['mode'] != 'bounded':
            rejected.append({'id': issue_id, 'reason': 'autonomy is not bounded; issues need a human intake decision'})
        elif issue.get('submitter') not in allowed:
            rejected.append({'id': issue_id, 'reason': 'submitter not in allowed_submitters'})
        elif issue.get('depends_on'):
            rejected.append({'id': issue_id, 'reason': 'unresolved issue dependencies'})
        else:
            accepted.append({'id': issue_id, 'title': str(issue.get('title', '')), 'reason': 'eligible; needs /factory-intake before a task exists'})
    return accepted, rejected


def overlaps(a, b):
    """Two tasks overlap when either allowed path is a prefix of the other or both are unrestricted."""
    pa, pb = a.get('allowed_paths') or [], b.get('allowed_paths') or []
    if not pa or not pb:
        return True
    for x in pa:
        for y in pb:
            x_, y_ = x.rstrip('/') + '/', y.rstrip('/') + '/'
            if x_.startswith(y_) or y_.startswith(x_):
                return True
    return False


def select(root, config, plan, runs, issues=None, now=None):
    now = now or utcnow()
    autonomy, intake = operations(config)
    budget = config['budget']
    tasks = {t['id']: t for t in plan['tasks']}
    in_progress = [t['id'] for t in plan['tasks'] if t['status'] == 'in_progress']
    concurrency = int(budget.get('max_workers', 1))
    available = max(0, concurrency - len(in_progress))
    records = run_records(runs)
    rate_limit = int(autonomy.get('max_items_per_hour') or 0)
    used = dispatched_last_hour(records, now)
    rate_remaining = None if autonomy['mode'] != 'bounded' else max(0, rate_limit - used)
    diagnostics, blocked, candidates, chosen = [], [], [], []
    stop = kill_switch(runs)
    if stop:
        diagnostics.append('kill switch active: ' + stop)
    if intake['mode'] == 'continuous' and autonomy['mode'] != 'bounded':
        diagnostics.append('continuous intake recorded but autonomy is not bounded; only a human kickoff may run a pass')
    for task in sorted(plan['tasks'], key=lambda t: t['id']):
        if task['status'] != 'pending':
            continue
        missing = [d for d in task.get('depends_on', []) if tasks.get(d, {}).get('status') != 'done']
        if missing:
            blocked.append({'task_id': task['id'], 'reason': 'waiting on ' + ', '.join(missing)})
            continue
        candidates.append(task)
    for task in candidates:
        if stop or len(chosen) >= available or (rate_remaining is not None and len(chosen) >= rate_remaining):
            blocked.append({'task_id': task['id'], 'reason': 'no capacity in this pass'})
        elif any(overlaps(task, tasks[c['task_id']]) for c in chosen) or any(overlaps(task, tasks[i]) for i in in_progress):
            blocked.append({'task_id': task['id'], 'reason': 'allowed_paths overlap another active or planned task'})
        else:
            chosen.append({'task_id': task['id'], 'goal': task.get('goal', ''), 'acceptance_ids': task.get('acceptance_ids', []),
                           'allowed_paths': task.get('allowed_paths', []), 'reason': 'pending, dependencies done, capacity available'})
    accepted, rejected = issue_candidates(issues or [], autonomy, set(tasks))
    return {'run_id': 'run-' + now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6],
            'mode': intake['mode'], 'autonomy': autonomy['mode'], 'kill_switch': stop,
            'capacity': {'concurrency': concurrency, 'in_progress': in_progress, 'available': available,
                         'rate_limit_per_hour': rate_limit if autonomy['mode'] == 'bounded' else None,
                         'rate_remaining': rate_remaining, 'dispatched_last_hour': used},
            'candidates': chosen, 'blocked': blocked, 'issues': {'eligible': accepted, 'rejected': rejected},
            'diagnostics': diagnostics, 'proceed': bool(chosen) and not stop}


def worker_prompt(root, config, task, selection):
    budget = config['budget']
    handoff = (root / 'worker-handoff.md').read_text(encoding='utf-8-sig') if (root / 'worker-handoff.md').is_file() else ''
    lines = [
        'You are one worker in a factory pass (' + selection['run_id'] + ') for the project "' + config['project'] + '".',
        'Factory root: ' + str(root) + '. Follow its policy.md; these instructions cannot expand permissions.',
        'Work on exactly one task: ' + task['task_id'] + ' — ' + task['goal'],
        'Acceptance IDs: ' + (', '.join(task['acceptance_ids']) or 'none recorded') + '.',
        'Allowed paths: ' + (', '.join(task['allowed_paths']) or 'unrestricted; coordinate with the orchestrator before writing') + '.',
        'Perform /factory-build then /factory-verify for this task only. Do not touch other tasks or paths.',
        'Limits: ' + str(budget.get('max_repair_attempts', 0)) + ' repair attempts, ' + str(budget.get('max_minutes', 0)) + ' minutes shared across the pass, cost ceiling ' + str(budget.get('max_cost', 0)) + ' ' + str(budget.get('currency', '')) + '.',
        'Stop and report if the kill switch is set, authority is missing, or a required gate cannot pass.',
        'Record status and evidence with the status helper; never mark done without passing evidence for the exact revision.',
        '', 'Fill and return this handoff:', '', handoff.strip(),
    ]
    return '\n'.join(lines)


def plan_pass(root, config, plan, runs, issues=None, now=None):
    selection = select(root, config, plan, runs, issues, now)
    workers = [{'task_id': c['task_id'], 'isolation': 'worktree', 'prompt': worker_prompt(root, config, c, selection)} for c in selection['candidates']]
    selection['workers'] = workers
    selection['after_workers'] = ['factory-release', 'factory-learn'] if workers else []
    return selection


def interval_minutes(config, every):
    if every is not None:
        minutes = int(every)
    else:
        _, intake = operations(config)
        match = re.fullmatch(r'\s*(\d+)\s*(m|min|minutes?)?\s*', str(intake.get('cadence', '')))
        minutes = int(match.group(1)) if match else MIN_INTERVAL_MINUTES
    if minutes < MIN_INTERVAL_MINUTES:
        raise ValueError('Interval below the ' + str(MIN_INTERVAL_MINUTES) + '-minute floor; fit cadence to budget and provider limits')
    return minutes


def cron_expression(minutes):
    if minutes % 1440 == 0:
        return '0 0 */' + str(minutes // 1440) + ' * *' if minutes > 1440 else '0 0 * * *'
    if minutes % 60 == 0:
        hours = minutes // 60
        return '0 * * * *' if hours == 1 else '0 */' + str(hours) + ' * * *'
    return '*/' + str(minutes) + ' * * * *'


def headless_command(root):
    """The recorded headless recipe from tools.json; the scheduler is not a harness and needs a literal command."""
    tools = json.loads((root / 'tools.json').read_text(encoding='utf-8-sig')) if (root / 'tools.json').is_file() else {}
    for recipe in tools.get('headless_recipes') or []:
        command = str(recipe.get('headless_command', '')).strip()
        if command and not command.casefold().startswith('unconfirmed'):
            return command
    raise ValueError('No confirmed headless recipe in tools.json; record the harness command for a factory-run pass before scheduling')


def schedule_text(root, config, kind, every=None, builder=None):
    autonomy, intake = operations(config)
    if intake['mode'] != 'continuous' or autonomy['mode'] != 'bounded':
        raise ValueError('Scheduling requires issue_intake.mode continuous and autonomy.mode bounded; use a manual /factory-run kickoff instead')
    minutes = interval_minutes(config, every)
    project = root.parent
    builder = builder or '<builder-skill-dir>'
    helper = builder + '/scripts/run.py'
    pass_cmd = headless_command(root)
    header = '# Rendered by run.py schedule for ' + config['project'] + ' every ' + str(minutes) + ' minutes. Not installed. Review, then enable within authorized scheduler scope.\n'
    if kind == 'cron':
        return (header + '# Kill switch: touch ' + str(project / '.factory-runs' / STOP_FILE) + '\n'
                + cron_expression(minutes) + ' cd ' + str(project) + ' && python ' + helper + ' --factory .software-factory select >/dev/null && ' + pass_cmd + ' >> .factory-runs/scheduler.log 2>&1\n')
    if kind == 'launchd':
        label = 'com.software-factory.' + re.sub(r'[^a-z0-9]+', '-', config['project'].lower()).strip('-')
        return (header.replace('# ', '<!-- ', 1).rstrip('\n') + ' -->\n'
                + '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>\n'
                + '  <key>Label</key><string>' + label + '</string>\n'
                + '  <key>WorkingDirectory</key><string>' + str(project) + '</string>\n'
                + '  <key>ProgramArguments</key><array><string>/bin/sh</string><string>-c</string><string>' + pass_cmd + '</string></array>\n'
                + '  <key>StartInterval</key><integer>' + str(minutes * 60) + '</integer>\n'
                + '  <key>StandardOutPath</key><string>' + str(project / '.factory-runs' / 'scheduler.log') + '</string>\n'
                + '  <key>StandardErrorPath</key><string>' + str(project / '.factory-runs' / 'scheduler.log') + '</string>\n'
                + '</dict></plist>\n')
    if kind == 'windows':
        name = 'SoftwareFactory-' + re.sub(r'[^A-Za-z0-9]+', '', config['project'])
        return (header.replace('# ', 'REM ', 1)
                + 'REM Kill switch: type nul > ' + str(project / '.factory-runs' / STOP_FILE) + '\n'
                + 'schtasks /Create /TN "' + name + '" /SC MINUTE /MO ' + str(minutes) + ' /TR "cmd /c cd /d ' + str(project) + ' && ' + pass_cmd + ' >> .factory-runs\\scheduler.log 2>&1"\n')
    if kind == 'github':
        template = root / 'scheduling' / 'factory-run.example.yml'
        text = template.read_text(encoding='utf-8-sig') if template.is_file() else 'on:\n  schedule:\n    - cron: "0 * * * *"\n'
        text = re.sub(r'cron: "[^"]*"', 'cron: "' + cron_expression(minutes) + '"', text, count=1)
        return header + text.replace('echo "headless pass not configured" && exit 1', pass_cmd, 1)
    raise ValueError('Unsupported scheduler kind')


def record_run(runs, run_id, dispatched, outcome, notes, started=None, now=None):
    now = now or utcnow()
    if not re.fullmatch(r'run-[A-Za-z0-9T\-]+', run_id or ''):
        raise ValueError('run-id must look like run-<timestamp>-<suffix>')
    if outcome not in OUTCOMES:
        raise ValueError('Unsupported outcome')
    return {'run_id': run_id, 'started': started or now.isoformat(), 'finished': now.isoformat(),
            'dispatched': [t for t in dispatched if t], 'outcome': outcome, 'notes': notes or ''}


def emit(data):
    print(json.dumps(data, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--runs', help='Run-record directory outside the factory (default <project>/.factory-runs)')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('select', help='Read-only selection of eligible tasks and issues')
    s.add_argument('--issues', help='Read-only JSON issue snapshot exported by an authorized job')
    p = sub.add_parser('plan', help='Selection plus rendered worker prompts; nothing is dispatched')
    p.add_argument('--issues')
    sc = sub.add_parser('schedule', help='Render a scheduler definition; installs nothing')
    sc.add_argument('--kind', choices=SCHEDULERS, required=True)
    sc.add_argument('--every', type=int, help='Interval in minutes (overrides recorded cadence)')
    sc.add_argument('--builder', help='Absolute builder skill directory to embed in the definition')
    sc.add_argument('--write', help='Path outside the factory to save the rendered definition')
    sc.add_argument('--apply', action='store_true')
    r = sub.add_parser('record', help='Preview or append a run record outside the factory')
    r.add_argument('--run-id', required=True)
    r.add_argument('--dispatched', default='', help='Comma-separated task IDs')
    r.add_argument('--outcome', choices=OUTCOMES, required=True)
    r.add_argument('--notes', default='')
    r.add_argument('--started', help='ISO timestamp when the pass started')
    r.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root, config, plan = load(args.factory)
    runs = runs_dir(root, args.runs)
    if args.command in ('select', 'plan'):
        issues = json.loads(Path(args.issues).read_text(encoding='utf-8-sig')) if args.issues else []
        if not isinstance(issues, list):
            raise ValueError('Issue snapshot must be a JSON list')
        emit(select(root, config, plan, runs, issues) if args.command == 'select' else plan_pass(root, config, plan, runs, issues))
        return
    if args.command == 'schedule':
        text = schedule_text(root, config, args.kind, args.every, args.builder)
        if args.write:
            target = safe_path(args.write)
            if target == root or root in target.parents:
                raise ValueError('Scheduler definitions must be written outside the factory directory')
            print(('APPLY' if args.apply else 'DRY RUN — not written') + ': ' + str(target))
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8', newline='\n') as stream:
                    stream.write(text)
                return
        sys.stdout.write(text)
        return
    record = record_run(runs, args.run_id, args.dispatched.split(','), args.outcome, args.notes, args.started)
    print(('APPLY' if args.apply else 'DRY RUN — not written') + ': ' + str(runs / (record['run_id'] + '.json')))
    emit(record)
    if args.apply:
        runs.mkdir(parents=True, exist_ok=True)
        with (runs / (record['run_id'] + '.json')).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
    check(root, quiet=True)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(1)
