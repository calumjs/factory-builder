"""Contract integrity and basic living-record validation; no external execution."""
import sys
if __name__ == '__main__':sys.dont_write_bytecode = True
import hashlib
import json
from pathlib import Path, PurePosixPath
from assumptions import assumptions
from learning_table import validate_learning_log

LIVING = frozenset(('verification.md', 'task-plan.json', 'learning-log.md', 'release-handoff.md', 'tools.json'))

class ManifestFileSetMismatch(ValueError):
    """Private details remain available to trusted callers; safe summary is structured."""
    def __init__(self, message, unexpected, missing):
        super().__init__(message)
        self.unexpected_count=len(unexpected)
        self.missing_count=len(missing)
        self.dashboard_bytecode=any(name.startswith('dashboard/__pycache__/') and name.endswith('.pyc') for name in unexpected)

def redirected(path):
    junction_check = getattr(path, 'is_junction', None)
    if path.is_symlink() or (callable(junction_check) and junction_check()):
        return True
    # Path.is_junction was added in Python 3.12. Older supported Windows
    # runtimes expose reparse points through lstat without following them.
    try:
        return bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    except (FileNotFoundError, NotADirectoryError):
        return False


def safe_path(path):
    p = Path(path).absolute()
    for node in (p, *p.parents):
        if redirected(node):
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

def strict_json(text):
    """Reject duplicate object keys at every depth before interpreting records."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError('Duplicate JSON object key')
            result[key] = value
        return result
    def constant(value): raise ValueError('Non-finite JSON number')
    return json.loads(text, object_pairs_hook=unique, parse_constant=constant)

def json_diagnostic(name, text, error):
    """Identify the input without displaying content or parser-supplied values."""
    label = json.dumps(str(name), ensure_ascii=True)
    if any(line.lstrip().startswith(('<<<<<<<', '=======', '>>>>>>>')) for line in text.splitlines()):
        return ValueError('Unresolved merge conflict in ' + label + '; preserve original bytes and both sides; use references/recovery.md section 1. No automatic re-hash or repair was performed.')
    location = (' (line ' + str(error.lineno) + ', column ' + str(error.colno) + ')') if isinstance(error, json.JSONDecodeError) else ''
    kind = ('Duplicate JSON object key' if str(error) in ('Duplicate JSON object key', 'Duplicate JSON key') else
            'Non-finite JSON number' if str(error) == 'Non-finite JSON number' else 'Invalid JSON')
    return ValueError(kind + ' in ' + label + location + '; inspect the named input and references/recovery.md before any repair')

def read_json(path):
    path = safe_path(path)
    text = path.read_text(encoding='utf-8-sig')
    try: return strict_json(text)
    except ValueError as exc: raise json_diagnostic(path, text, exc) from exc

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

def missing_manifest_diagnostic(root):
    """Suggest only an observed, non-redirected child; read no candidate contents."""
    message = ('Factory root ' + json.dumps(str(root)) + ' does not contain a regular manifest file; '
               'expected ' + json.dumps(str(root/'manifest.json')) + '. '
               'Pass the directory containing manifest.json as the factory path.')
    try:
        candidate = safe_path(root/'.software-factory'/'manifest.json')
        if candidate.parent.is_dir() and candidate.is_file():
            message += (' A child manifest exists at ' + json.dumps(str(candidate)) + '; '
                        'use ' + json.dumps(str(candidate.parent)) + ' explicitly with --factory '
                        '(or scaffold.py --check). The child has not been validated; no redirect occurred.')
    except (OSError, ValueError):
        pass  # An inaccessible or redirected candidate is not a usable hint.
    return message


def check(path, *, quiet=False):
    p = safe_path(path)
    manifest = safe_path(p/'manifest.json')
    if not p.is_dir() or not manifest.is_file():
        raise ValueError(missing_manifest_diagnostic(p))
    for item in p.rglob('*'):
        if redirected(item):
            raise ValueError('Redirected path inside factory ' + json.dumps(str(p)) + ': ' + json.dumps(str(item)))
    m = read_json(manifest)
    if not isinstance(m, dict) or m.get('schema') != 2 or m.get('hash_mode') != 'utf8-lf' or not isinstance(m.get('contracts'), dict) or not isinstance(m.get('living'), list):
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
        raise ManifestFileSetMismatch('Manifest file set mismatch (' + detail + '). Keep operator/runtime records '
                         'outside the factory directory, e.g. docs/factory-operations.md. '
                         'Do not reset hashes; use reviewed recovery for existing drift.', extra, missing)
    for name, expected in m['contracts'].items():
        if digest((p/name).read_bytes()) != expected:
            raise ValueError('Contract integrity mismatch: ' + name)
        if name.endswith('.json'):
            read_json(p/name)
    for name in m['living']:
        body = (p/name).read_text(encoding='utf-8-sig')
        if name == 'learning-log.md':
            validate_learning_log(body)
        if name.endswith('.json'):
            value = read_json(p/name)
            if name == 'task-plan.json':
                validate_task_plan(value)
            elif not isinstance(value, dict):
                raise ValueError('Invalid living tool registry')
    assumptions(read_json(p/'config.json'))
    if not quiet:
        print(f"PASS: {len(m['contracts'])} contract files match; {len(m['living'])} living files have valid basic structure. Living content and evidence truth are not attested; application checks were not run.")
    return m

if __name__ == '__main__':
    raise SystemExit('ERROR: integrity.py is an import-only module; no check ran. Use the installed builder scripts/scaffold.py --check <factory>.')
