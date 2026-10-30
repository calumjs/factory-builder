"""Preview-only by default; narrowly add an overview to an unchanged schema-2 factory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from dashboard_bundle import bundle
from integrity import check, digest, safe_path


def prepare(factory):
    root = safe_path(factory)
    manifest = check(root, quiet=True)
    if (root/'dashboard').exists():
        raise ValueError('Existing dashboard preserved; no overwrite or automatic upgrade')
    names = list(manifest['contracts'])+manifest['living']+['manifest.json']
    old = {name: (root/name).read_bytes() for name in names}
    files = {name: value.decode('utf-8-sig') for name, value in old.items()}
    new = {name: value.encode('utf-8') for name, value in bundle(files).items()}
    for name, value in new.items():
        manifest['contracts'][name] = digest(value)
    new['manifest.json'] = (json.dumps(manifest, indent=2)+'\n').encode('utf-8')
    record = {'factory': str(root), 'before': {k: hashlib.sha256(v).hexdigest() for k, v in sorted(old.items())},
              'after': {k: hashlib.sha256(v).hexdigest() for k, v in sorted(new.items())}}
    plan = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    return root, old, new, plan


def apply(root, old, new, plan, approved):
    if plan != approved:
        raise ValueError('Exact reviewed --approve-plan digest required')
    check(root, quiet=True)
    if (root/'dashboard').exists() or any((root/name).read_bytes()!=data for name, data in old.items()):
        raise ValueError('Concurrent factory edit; regenerate preview')
    backup = safe_path(root.parent/'.factory-update-backups'/('dashboard-'+plan))
    backup.mkdir(parents=True, exist_ok=False)
    with (backup/'manifest.json').open('xb') as stream:
        stream.write(old['manifest.json'])
    # New directory is exclusive. Interrupted writes remain visibly integrity-blocked;
    # preserve them and the original manifest for a reviewed recovery, never rebaseline.
    (root/'dashboard').mkdir()
    for name, data in new.items():
        if name == 'manifest.json':
            continue
        with (root/name).open('xb') as stream:
            stream.write(data)
    if any((root/name).read_bytes()!=data for name, data in old.items()):
        raise ValueError('Concurrent edit preserved; inspect backup and partial new dashboard')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, delete=False, prefix='.dashboard-', suffix='.tmp') as stream:
            temporary = Path(stream.name);stream.write(new['manifest.json']);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, root/'manifest.json');temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    check(root, quiet=True)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--approve-plan')
    args = parser.parse_args()
    if args.approve_plan and not args.apply:
        parser.error('--approve-plan requires --apply')
    root, old, new, plan = prepare(args.factory)
    print('REVIEW PLAN: '+plan)
    for name, value in sorted(new.items()):
        print(name+' SHA256 '+hashlib.sha256(value).hexdigest())
        if name.endswith(('.html', '.md')):
            print(value.decode('utf-8'))
    print('Only new dashboard contracts and manifest are proposed; living records, custom skills, config and policy stay unchanged.')
    if args.apply:
        print('APPLIED; preserved original manifest: '+str(apply(root, old, new, plan, args.approve_plan)))
    else:
        print('PREVIEW: no writes. Review generated files and manifest additions before --apply --approve-plan '+plan)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('ERROR: '+str(exc)+'; preserve any partial dashboard/backup for reviewed recovery', file=sys.stderr)
        sys.exit(1)
