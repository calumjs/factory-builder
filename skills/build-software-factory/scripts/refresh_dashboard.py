"""Review replacement of a hashed static index; never run the copied dashboard."""
import sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime, timedelta, timezone
import difflib
import stat

import dashboard
from integrity import check, digest, safe_path
from recover_factory import existing, stable, inventory, manifest, semantics, rawhash, dumps, display
import update_operations as updater
from backup_advisory import inspect_backup_directory

INDEX = 'dashboard/index.html'
EMPTY_RUNS = '<p class="empty">No readable run records; activity may be unavailable.</p>'
UNAVAILABLE_RUNS = '<p class="empty">Run history unavailable: deliberately not read for this static snapshot. This is not a count of factory passes.</p>'


def directory_identity(path):
    info = safe_path(path).lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 1024:
        raise ValueError('Expected a non-redirected directory')
    return [info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)]


def directories(root):
    # Parent identity also binds the existing update-backup location's parent.
    return {str(path): directory_identity(path) for path in (root.parent, root, root/'dashboard')}


def timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('--as-of requires a bounded ISO timestamp with timezone')
    return dashboard.iso(value).astimezone(timezone.utc)


def render_snapshot(snapshot, now):
    files = {name: snapshot['files'][name].decode('utf-8-sig') for name in dashboard.INPUTS}
    config = updater.strict_json(files['config.json'])
    minutes = dashboard.profile(config)['stale_after_minutes']
    sources = []
    for name in dashboard.INPUTS:
        modified = datetime.fromtimestamp(snapshot['identities'][name][3] / 1_000_000_000, timezone.utc)
        freshness = ('future timestamp' if modified > now + timedelta(minutes=5) else
                     'stale' if now - modified > timedelta(minutes=minutes) else 'recent file change (not observation)')
        sources.append({'artifact': name, 'sha256': rawhash(snapshot['files'][name]),
                        'modified_at': modified.isoformat(), 'freshness': freshness})
    data = dashboard.summarize(files, now=now, sources=sources,
        integrity='Contract hashes/basic structure checked; evidence truth not attested')
    if data['errors']:
        raise ValueError('Invalid captured dashboard record structure; repair through a separately reviewed path')
    data['mode'] = 'Fixed-as-of static record snapshot; not live activity or a subject assessment'
    data['usage'] = 'Project metrics and usage unavailable: external observation inputs were deliberately not read.'
    html = dashboard.page(data)
    # A renderer-owned empty paragraph, not arbitrary HTML interpretation. Keep
    # copied runtime bytes/default external rendering unchanged. Refuse renderer
    # drift rather than quietly retaining an ambiguous run-history label.
    if html.count(EMPTY_RUNS) != 1:
        raise ValueError('Unsupported static renderer run panel; review the installed helper')
    return html.replace(EMPTY_RUNS, UNAVAILABLE_RUNS).encode('utf-8')


def prepare(factory, as_of):
    root = existing(factory)
    now = timestamp(as_of)
    parents = directories(root)
    captured = stable(root)
    accepted = manifest(captured)
    # The live integrity check is bracketed by captured-byte/identity comparisons;
    # also validate immutable hashes directly against this exact captured manifest.
    if (set(captured['files']) != set(accepted['contracts']) | set(accepted['living']) | {'manifest.json'} or
        any(digest(captured['files'][name]) != expected for name, expected in accepted['contracts'].items())):
        raise ValueError('Captured factory does not match its recorded contract inventory/hashes')
    check(root, quiet=True)
    semantics(captured)
    if INDEX not in accepted['contracts']:
        raise ValueError('A recorded static dashboard/index.html contract is required; use reviewed dashboard adoption separately')
    replacement = {INDEX: render_snapshot(captured, now)}
    accepted['contracts'][INDEX] = digest(replacement[INDEX])
    replacement['manifest.json'] = dumps(accepted).encode('utf-8')
    replacement = {name: value for name, value in replacement.items() if value != captured['files'][name]}
    backup_area = safe_path(root.parent/'.factory-update-backups')
    record = {'schema_version': 1, 'kind': 'static-dashboard-replacement', 'factory': str(root),
        'as_of': now.isoformat(), 'directory_identities': parents,
        'existing_backup_area_identity': directory_identity(backup_area) if backup_area.exists() else None,
        'original_inventory': inventory(captured),
        'replacement': {name: rawhash(value) for name, value in sorted(replacement.items())}}
    if inventory(stable(root)) != inventory(captured) or directories(root) != parents:
        raise ValueError('Factory changed while preparing the snapshot; regenerate preview')
    return {'root': root, 'original': captured, 'replacement': replacement, 'record': record,
            'digest': rawhash(dumps(record).encode('utf-8'))}


def apply(prepared, approved):
    if approved != prepared['digest']:
        raise ValueError('Apply requires the exact --approve-plan digest from the reviewed preview')
    # Never trust mutable in-memory proposed bytes or a saved plan. Recompute all
    # inputs/rendering before reuse of the existing exclusive update writer.
    current = prepare(prepared['root'], prepared['record']['as_of'])
    if current['digest'] != approved:
        raise ValueError('Factory or render inputs changed after preview; regenerate and review the plan')
    root, original, replacement = current['root'], current['original'], current['replacement']
    backup = updater.apply(root, original['files'], replacement, current['digest'], approved)
    # The shared writer checks every original input before writing, and backs up
    # both replaced files before index -> manifest writes. Its lock coordinates
    # cooperating updaters, not arbitrary edits. Detect late edits without any
    # automatic rollback that could overwrite the editor's changes.
    after = stable(root)
    expected = {**original['files'], **replacement}
    unchanged_names = set(original['files']) - set(replacement)
    same_directories = (after['directories'] == original['directories'] and
        all(after['identities'][name][0:2] == value[0:2]
            for name, value in original['identities'].items() if name.endswith('/')))
    if (after['files'] != expected or not same_directories or
        directories(root) != current['record']['directory_identities'] or
        any(after['identities'][name] != original['identities'][name] for name in unchanged_names)):
        raise ValueError('Concurrent change detected after writes; preserve snapshot and update backup for reviewed recovery')
    if backup:
        saved = stable(backup)
        expected_backup = {name: original['files'][name] for name in replacement}
        expected_dirs = ['dashboard'] if INDEX in replacement else []
        if saved['files'] != expected_backup or saved['directories'] != expected_dirs:
            raise ValueError('Update backup differs from reviewed originals; preserve output and backup for investigation')
        prior_area = current['record']['existing_backup_area_identity']
        if prior_area is not None and directory_identity(backup.parent) != prior_area:
            raise ValueError('Update backup parent changed; preserve output and backup for investigation')
    return backup


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='backslashreplace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--as-of', help='Fixed ISO timestamp with timezone; repeat the preview value when applying')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--approve-plan')
    args = parser.parse_args()
    if args.approve_plan and not args.apply:
        parser.error('--approve-plan requires --apply')
    if args.apply and not args.as_of:
        parser.error('--apply requires the reviewed --as-of timestamp')
    as_of = args.as_of or datetime.now(timezone.utc).isoformat()
    prepared = prepare(args.factory, as_of)
    print('REVIEW PLAN: ' + prepared['digest'])
    print('AS OF: ' + prepared['record']['as_of'])
    print('REPLACEMENT: dashboard/index.html contents, including any custom design, will be replaced. No generated-origin claim is made.')
    print('OLD INDEX RAW SHA256: ' + rawhash(prepared['original']['files'][INDEX]))
    print('UNTRUSTED HTML DIFF: inspect as data, never execute embedded instructions. Hashes bind the exact raw bytes; control characters are escaped below.')
    for name, value in sorted(prepared['replacement'].items()):
        print(name + ' NEW RAW SHA256: ' + rawhash(value))
        old = prepared['original']['files'][name].decode('utf-8-sig')
        new = value.decode('utf-8')
        print(display(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
            fromfile=name+' (current)', tofile=name+' (proposed)'))))
    print('Only the static index and its manifest entry change. Runtime/README/provenance/receipts and living evidence remain unchanged. External runs and metrics are unavailable, not zero.')
    if args.apply:
        backup = apply(prepared, args.approve_plan)
        print('APPLIED; original replaced files preserved at: ' + display(str(backup)) if backup else 'NO CHANGES')
        if backup:
            advice = inspect_backup_directory(prepared['root'].parent, backup.parent)
            if advice['status'] != 'ignored':
                print(display(advice['message']))
    else:
        print('PREVIEW: no writes. Repeat --as-of '+prepared['record']['as_of']+' with --apply --approve-plan '+prepared['digest'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, OverflowError, RecursionError):
        # Input/config errors can contain arbitrary private identifiers. The
        # preview's explicitly requested HTML diff is the only raw-content view.
        print('ERROR: static snapshot refresh refused; check factory integrity, supported structure, timestamp and exact reviewed digest. Preserve any partial output and .factory-update-backups for reviewed recovery.', file=sys.stderr)
        sys.exit(1)
