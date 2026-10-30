"""Contract integrity and basic living-record validation; no external execution."""
import hashlib
import json
from pathlib import Path, PurePosixPath
from assumptions import assumptions

LIVING = frozenset(('verification.md', 'task-plan.json', 'learning-log.md', 'release-handoff.md', 'tools.json'))

def safe_path(path):
    p = Path(path).absolute()
    for node in (p, *p.parents):
        if node.is_symlink() or (hasattr(node, 'is_junction') and node.is_junction()):
            raise ValueError('Redirected paths are not supported: ' + str(node))
    return p

def digest(text):
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig')
    return hashlib.sha256(text.replace('\r\n','\n').replace('\r','\n').encode('utf-8')).hexdigest()

def manifest_for(files):
    return {'schema': 2, 'hash_mode': 'utf8-lf',
            'contracts': {name: digest(body) for name, body in sorted(files.items()) if name not in LIVING},
            'living': sorted(name for name in files if name in LIVING)}

def validate_task_plan(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get('tasks'), list) or not isinstance(plan.get('events', []), list):
        raise ValueError('Invalid living task-plan structure')
    ids = set()
    for task in plan['tasks']:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not isinstance(task.get('status'), str) or task['id'] in ids:
            raise ValueError('Invalid or duplicate task')
        ids.add(task['id'])
    for event in plan.get('events', []):
        required = ('id','task_id','timestamp','revision','environment','check','result','evidence','old_status','status')
        if not isinstance(event, dict) or any(not isinstance(event.get(k), str) or not event[k].strip() for k in required):
            raise ValueError('Invalid evidence event')
        if event['task_id'] not in ids or event['result'] not in ('passed','failed','blocked','not-run'):
            raise ValueError('Invalid evidence task or result')

def check(path, *, quiet=False):
    p = safe_path(path)
    for item in p.rglob('*'):
        if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
            raise ValueError('Redirected path inside factory')
    m = json.loads((p/'manifest.json').read_text(encoding='utf-8-sig'))
    if m.get('schema') != 2 or m.get('hash_mode') != 'utf8-lf' or not isinstance(m.get('contracts'), dict) or not isinstance(m.get('living'), list):
        raise ValueError('Unsupported manifest; legacy schema 1 requires a reviewed migration, never automatic rebaselining')
    names = list(m['contracts']) + m['living']
    if len(names) != len(set(names)) or set(m['living']) != LIVING:
        raise ValueError('Invalid contract/living classification')
    for name in names:
        parts = PurePosixPath(name)
        if parts.is_absolute() or '\\' in name or ':' in name or any(v in ('..','.','') for v in name.split('/')):
            raise ValueError('Unsafe manifest path')
    actual = {str(f.relative_to(p)).replace('\\','/') for f in p.rglob('*') if f.is_file()} - {'manifest.json'}
    if actual != set(names):
        extra = sorted(actual - set(names))
        missing = sorted(set(names) - actual)
        detail = '; '.join(label + ': ' + json.dumps(paths, ensure_ascii=True)
                           for label, paths in (('unexpected', extra), ('missing', missing)) if paths)
        raise ValueError('Manifest file set mismatch (' + detail + '). Keep operator/runtime records '
                         'outside the factory directory, e.g. docs/factory-operations.md. '
                         'Do not reset hashes; use reviewed recovery for existing drift.')
    for name, expected in m['contracts'].items():
        if digest((p/name).read_bytes()) != expected:
            raise ValueError('Contract integrity mismatch: ' + name)
    for name in m['living']:
        body = (p/name).read_text(encoding='utf-8-sig')
        if name.endswith('.json'):
            value = json.loads(body)
            if name == 'task-plan.json':
                validate_task_plan(value)
            elif not isinstance(value, dict):
                raise ValueError('Invalid living tool registry')
    assumptions(json.loads((p/'config.json').read_text(encoding='utf-8-sig')))
    if not quiet:
        print(f"PASS: {len(m['contracts'])} contract files match; {len(m['living'])} living files have valid basic structure. Living content and evidence truth are not attested; application checks were not run.")
    return m
