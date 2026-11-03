"""Preview or create an inactive acceptance candidate; never adopt an active factory."""
import sys
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import argparse
import base64
import itertools
import json
import os
from pathlib import Path
import re
import stat

import acceptance_plan as planner
from integrity import check, safe_path
from recover_factory import (RESERVED, content_inventory, copy_snapshot, existing, inside,
                             inventory, output_path, rawhash, semantics, stable, write_file)

BACKUPS = '.factory-acceptance-backups'
NOTICE = ('INACTIVE CANDIDATE ONLY: the original manifest is retained and contract drift is intentional. '
          'This is not registered scope, valid factory integrity, application evidence or adoption authority. '
          'A separate pinned recovery preview/review/apply/verification is still required. No live factory is modified.')
PLAN_KEYS = {'schema_version', 'kind', 'synchronization', 'output', 'backup_parent', 'directory_guards', 'expected_candidate'}
RECORD_KEYS = {'schema_version', 'kind', 'plan', 'digest', 'backup_verified'}


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode('ascii')


def identity(path):
    path = existing(path)
    meta = path.lstat()
    return [meta.st_dev, meta.st_ino, stat.S_IFMT(meta.st_mode)]


def disjoint(*paths):
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if inside(left, right) or inside(right, left):
                raise ValueError('Source, candidate and backup area must be pairwise disjoint')


def layout(source, output):
    target = output_path(output, source, source)
    parent = existing(target.parent)
    backup_parent = safe_path(parent / BACKUPS)
    backup_identity = identity(backup_parent) if backup_parent.exists() else None
    disjoint(source, target, backup_parent)
    guards = {'output_parent': {'path': str(parent), 'identity': identity(parent)},
              'backup_parent': {'path': str(backup_parent), 'identity': backup_identity}}
    return target, backup_parent, guards


def expected_candidate(sync):
    original = sync['plan']['source_inventory']
    files = dict(original['files'])
    for name, change in sync['plan']['candidate_changes'].items():
        if name == 'manifest.json':
            raise ValueError('Candidate may not replace the original manifest')
        files[name] = change['after_sha256']
    return {'files': files, 'directories': list(original['directories'])}


def candidate_snapshot(snapshot, sync):
    files = dict(snapshot['files'])
    for name, change in sync['plan']['candidate_changes'].items():
        if name == 'manifest.json':
            raise ValueError('Candidate may not replace the original manifest')
        raw = base64.b64decode(change['after_base64'], validate=True)
        if rawhash(raw) != change['after_sha256']:
            raise ValueError('Candidate bytes do not match the reviewed change')
        files[name] = raw
    return {**snapshot, 'files': files}


def prepare(factory, request, baseline_pin, baseline_reference, output):
    sync = planner.preview(factory, request, baseline_pin, baseline_reference)
    source = existing(sync['plan']['factory'])
    target, backup_parent, guards = layout(source, output)
    if planner.canonical(inventory(stable(source))) != planner.canonical(sync['plan']['source_inventory']):
        raise ValueError('Source changed while binding the candidate destination')
    plan = {'schema_version': 1, 'kind': 'acceptance-candidate', 'synchronization': sync,
            'output': str(target), 'backup_parent': str(backup_parent), 'directory_guards': guards,
            'expected_candidate': expected_candidate(sync)}
    result = {'notice': NOTICE, 'plan': plan, 'digest': rawhash(planner.canonical(plan))}
    # Leave bounded space for the fixed record wrapper and completion metadata.
    if len(encoded(result)) + 4096 > planner.MAX_PLAN:
        raise ValueError('Candidate preview exceeds the supported metadata size limit')
    return result


def require_digest(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ValueError('Exact reviewed candidate plan digest required')


def original_content(plan):
    source = plan['synchronization']['plan']['source_inventory']
    return {'files': source['files'], 'directories': source['directories']}


def source_snapshot(plan):
    source = existing(plan['synchronization']['plan']['factory'])
    snapshot = stable(source)
    if planner.canonical(inventory(snapshot)) != planner.canonical(plan['synchronization']['plan']['source_inventory']):
        raise ValueError('Original factory changed; preserve all edits and review a fresh plan')
    return snapshot


def recheck_layout(plan, created_backup_parent=None, created_candidate=None):
    """Cooperative stable-parent checks; not an adversarial filesystem transaction."""
    source = existing(plan['synchronization']['plan']['factory'])
    target = safe_path(plan['output'])
    parent = existing(target.parent)
    guards = plan['directory_guards']
    if str(parent) != guards['output_parent']['path'] or identity(parent) != guards['output_parent']['identity']:
        raise ValueError('Candidate output parent changed')
    backup_parent = safe_path(parent / BACKUPS)
    if str(backup_parent) != plan['backup_parent'] or str(backup_parent) != guards['backup_parent']['path']:
        raise ValueError('Candidate backup path changed')
    expected = guards['backup_parent']['identity'] or created_backup_parent
    if backup_parent.exists():
        if expected is None or identity(backup_parent) != expected:
            raise ValueError('Candidate backup area changed; review a fresh plan')
    elif expected is not None:
        raise ValueError('Candidate backup area disappeared')
    if target.exists():
        if created_candidate is None or identity(target) != created_candidate:
            raise ValueError('Candidate destination is occupied or changed')
    elif created_candidate is not None:
        raise ValueError('Candidate destination disappeared')
    disjoint(source, target, backup_parent)
    return source, target, backup_parent


def metadata_entries(backup, completed):
    expected = {'source', 'candidate.json', 'decisions.json'} | ({'COMPLETED.json'} if completed else set())
    with os.scandir(backup) as iterator:
        entries = list(itertools.islice(iterator, len(expected) + 1))
    if {entry.name for entry in entries} != expected or len(entries) != len(expected):
        raise ValueError('Candidate backup has missing or unexpected metadata entries')
    for entry in entries:
        path = safe_path(backup / entry.name)
        info = path.lstat()
        wanted = stat.S_ISDIR if entry.name == 'source' else stat.S_ISREG
        if not wanted(info.st_mode):
            raise ValueError('Candidate backup metadata has an unsupported entry type')


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(label + ' has an unsupported schema')


def validate_record(record, digest):
    exact_keys(record, RECORD_KEYS, 'Candidate record')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1 or
            record['kind'] != 'acceptance-candidate-record' or record['digest'] != digest or record['backup_verified'] is not True):
        raise ValueError('Candidate record does not match the reviewed plan')
    plan = record['plan']
    exact_keys(plan, PLAN_KEYS, 'Candidate plan')
    if type(plan['schema_version']) is not int or plan['schema_version'] != 1 or plan['kind'] != 'acceptance-candidate':
        raise ValueError('Unsupported candidate plan version')
    if rawhash(planner.canonical(plan)) != digest:
        raise ValueError('Candidate metadata does not match the externally supplied plan digest')
    exact_keys(plan['synchronization'], {'notice', 'plan', 'digest'}, 'Synchronization envelope')
    exact_keys(plan['directory_guards'], {'output_parent', 'backup_parent'}, 'Directory guards')
    for name, guard in plan['directory_guards'].items():
        exact_keys(guard, {'path', 'identity'}, 'Directory guard')
        value = guard['identity']
        if not isinstance(guard['path'], str) or (value is None and name != 'backup_parent'):
            raise ValueError('Invalid directory guard')
        if value is not None and (not isinstance(value, list) or len(value) != 3 or any(type(part) is not int for part in value)):
            raise ValueError('Invalid directory guard identity')
    return plan


def verified_roots(output, backup, plan, digest):
    """Follow only explicit caller roots and their fixed children, not metadata paths."""
    target, record_root = existing(output), existing(backup)
    if str(target) != plan['output']:
        raise ValueError('Explicit candidate root differs from the reviewed plan')
    parent = existing(target.parent)
    backup_parent = existing(parent / BACKUPS)
    if record_root != backup_parent / digest:
        raise ValueError('Explicit candidate/backup roots differ from the reviewed plan')
    guards = plan['directory_guards']
    if (str(parent) != guards['output_parent']['path'] or identity(parent) != guards['output_parent']['identity'] or
            str(backup_parent) != plan['backup_parent'] or str(backup_parent) != guards['backup_parent']['path']):
        raise ValueError('Candidate parent paths/identity differ from the reviewed plan')
    if guards['backup_parent']['identity'] is not None and identity(backup_parent) != guards['backup_parent']['identity']:
        raise ValueError('Reviewed backup area identity changed')
    disjoint(target, backup_parent)
    return target, record_root


def completion(plan, digest):
    return {'schema_version': 1, 'kind': 'acceptance-candidate-completion', 'digest': digest, 'output': plan['output']}


def read_completion(path, plan, digest):
    value = planner.read_input(path, 4096)
    exact_keys(value, {'schema_version', 'kind', 'digest', 'output'}, 'Candidate completion')
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value != completion(plan, digest):
        raise ValueError('Candidate has no matching strict completion record; it remains unverified')
    return value


def verify_contents(output, backup, digest, completed):
    require_digest(digest)
    # These roots were explicitly supplied. Nothing from metadata is followed.
    target, record_root = existing(output), existing(backup)
    metadata_entries(record_root, completed)
    record = planner.read_input(record_root / 'candidate.json', planner.MAX_PLAN)
    plan = validate_record(record, digest)
    target, record_root = verified_roots(target, record_root, plan, digest)
    decisions = planner.read_input(record_root / 'decisions.json', planner.MAX_REQUEST)
    sync = plan['synchronization']
    source = sync['plan']
    if not isinstance(source, dict) or not isinstance(source.get('factory'), str) or not Path(source['factory']).is_absolute():
        raise ValueError('Synchronization source must identify an absolute original path')
    if type(source.get('schema_version')) is not int or source['schema_version'] != 1:
        raise ValueError('Unsupported synchronization schema version')
    original_inventory = source.get('source_inventory')
    exact_keys(original_inventory, {'files', 'directories', 'identities'}, 'Original inventory')
    if (not isinstance(original_inventory['files'], dict) or not isinstance(original_inventory['directories'], list) or
            not isinstance(original_inventory['identities'], dict) or any(not isinstance(name, str) for name in original_inventory['directories'])):
        raise ValueError('Original inventory has an unsupported structure')
    expected_identity_keys = set(original_inventory['files']) | {'/'} | {name + '/' for name in original_inventory['directories']}
    if set(original_inventory['identities']) != expected_identity_keys:
        raise ValueError('Original inventory identity coverage differs')
    for name, value in original_inventory['identities'].items():
        if not isinstance(value, list) or len(value) != (3 if name.endswith('/') else 4) or any(type(part) is not int for part in value):
            raise ValueError('Original inventory has an unsupported identity')
    if decisions != source['recovery_decisions']:
        raise ValueError('Candidate recovery decisions differ from the reviewed plan')
    if completed:
        read_completion(record_root / 'COMPLETED.json', plan, digest)
    saved = stable(existing(record_root / 'source'))
    if content_inventory(saved) != original_content(plan):
        raise ValueError('Original backup differs from the approved full inventory')
    check(record_root / 'source', quiet=True)
    semantics(saved)
    # Re-derive the transformation from the independently pinned original bytes.
    # Backup path/identities differ; all transformation and provenance fields must agree.
    recomputed = planner.preview(record_root / 'source', source['request'], source['accepted_manifest_sha256'], source['baseline_reference'])
    if sync['notice'] != recomputed['notice'] or sync['digest'] != rawhash(planner.canonical(source)):
        raise ValueError('Synchronization envelope differs from its reviewed digest')
    if set(source) != set(recomputed['plan']):
        raise ValueError('Unsupported synchronization plan schema')
    for key in source:
        if key not in ('factory', 'source_inventory') and source[key] != recomputed['plan'][key]:
            raise ValueError('Candidate synchronization cannot be reproduced from the verified original backup')
    if plan['expected_candidate'] != expected_candidate(sync):
        raise ValueError('Expected candidate inventory differs from the synchronization plan')
    observed = stable(target)
    if content_inventory(observed) != plan['expected_candidate']:
        raise ValueError('Candidate differs from its complete reviewed inventory')
    if observed['files']['manifest.json'] != saved['files']['manifest.json']:
        raise ValueError('Candidate must retain the exact original manifest')
    semantics(observed)  # Integrity intentionally drifts until the separate recovery step.
    if content_inventory(stable(target)) != plan['expected_candidate'] or content_inventory(stable(record_root / 'source')) != original_content(plan):
        raise ValueError('Candidate or backup changed during verification')
    metadata_entries(record_root, completed)
    if (planner.read_input(record_root / 'candidate.json', planner.MAX_PLAN) != record or
            planner.read_input(record_root / 'decisions.json', planner.MAX_REQUEST) != decisions):
        raise ValueError('Candidate metadata changed during verification')
    if completed:
        read_completion(record_root / 'COMPLETED.json', plan, digest)
    verified_roots(target, record_root, plan, digest)
    return plan


def verify_output(output, backup, digest):
    return verify_contents(output, backup, digest, True)


def quarantine(target, owned_identity):
    """Best effort only for the same nonredirected root created by this process."""
    try:
        if owned_identity is not None and identity(target) == owned_identity:
            write_file(safe_path(target / RESERVED), b'Acceptance candidate incomplete. Original factory untouched. Preserve backup and partial output; do not recover or adopt this attempt.\n')
    except (OSError, ValueError):
        pass


def apply(result, approved, stable_inputs=False):
    require_digest(approved)
    exact_keys(result, {'notice', 'plan', 'digest'}, 'Candidate preview')
    supplied = result['plan']
    source = supplied['synchronization']['plan']
    current = prepare(source['factory'], source['request'], source['accepted_manifest_sha256'], source['baseline_reference'], supplied['output'])
    if approved != current['digest'] or planner.canonical(result) != planner.canonical(current):
        raise ValueError('Apply requires the exact current reviewed candidate digest; nothing written')
    if not stable_inputs:
        raise ValueError('Apply requires coordinated stable inputs/output parent; no writer or activation is managed here')
    plan = current['plan']
    snapshot = source_snapshot(plan)
    candidate = candidate_snapshot(snapshot, plan['synchronization'])
    _, target, backup_parent = recheck_layout(plan)
    created_backup_parent = None
    created_candidate = None
    backup = backup_parent / approved
    if not backup_parent.exists():
        backup_parent.mkdir()
        created_backup_parent = identity(backup_parent)
    recheck_layout(plan, created_backup_parent)
    backup.mkdir()  # Exclusive: never overwrite or resume an earlier attempt.
    copy_snapshot(backup / 'source', snapshot)
    if content_inventory(stable(backup / 'source')) != original_content(plan):
        raise ValueError('Original backup verification failed; candidate was not created')
    check(backup / 'source', quiet=True)
    semantics(stable(backup / 'source'))
    record = {'schema_version': 1, 'kind': 'acceptance-candidate-record', 'plan': plan, 'digest': approved, 'backup_verified': True}
    write_file(backup / 'candidate.json', encoded(record))
    write_file(backup / 'decisions.json', encoded(source['recovery_decisions']))
    source_snapshot(plan)
    recheck_layout(plan, created_backup_parent)
    try:
        target.mkdir()
        created_candidate = identity(target)
        copy_snapshot(target, candidate, include_manifest=False, create=False)
        staged = {**candidate, 'files': {name: raw for name, raw in candidate['files'].items() if name != 'manifest.json'}}
        if content_inventory(stable(target)) != content_inventory(staged):
            raise ValueError('Staged candidate differs from reviewed bytes')
        source_snapshot(plan)
        recheck_layout(plan, created_backup_parent, created_candidate)
        write_file(target / 'manifest.json', snapshot['files']['manifest.json'])
        verify_contents(target, backup, approved, False)
        source_snapshot(plan)
        recheck_layout(plan, created_backup_parent, created_candidate)
        write_file(backup / 'COMPLETED.json', encoded(completion(plan, approved)))
        verify_output(target, backup, approved)
        source_snapshot(plan)
        recheck_layout(plan, created_backup_parent, created_candidate)
    except BaseException:
        quarantine(target, created_candidate)
        raise
    return backup


def handoff(output, backup, digest):
    plan = verify_output(output, backup, digest)
    target, record_root = existing(output), existing(backup)
    source = plan['synchronization']['plan']
    return {'notice': NOTICE, 'candidate': str(target), 'backup': str(record_root), 'plan_id': digest,
            'verify_argv': [sys.executable, '-B', str(Path(__file__).resolve()), '--verify-output', str(target), '--backup', str(record_root), '--plan-id', digest],
            'recovery_inputs': {'factory': str(target), 'baseline': str(record_root / 'source'),
                                'baseline_manifest_sha256': source['accepted_manifest_sha256'],
                                'baseline_reference': source['baseline_reference'], 'decisions': str(record_root / 'decisions.json')},
            'next_step': 'Choose a new disjoint recovery output, then run the trusted recovery helper preview and review its separate digest. Do not adopt this candidate. The copied baseline adds no provenance attestation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('factory', 'request', 'baseline-manifest-sha256', 'baseline-reference', 'output', 'approve-plan', 'verify-output', 'backup', 'plan-id'):
        parser.add_argument('--' + name)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--stable-inputs', action='store_true')
    args = parser.parse_args()
    construction = (args.factory, args.request, args.baseline_manifest_sha256, args.baseline_reference, args.output)
    if args.verify_output:
        if not args.backup or not args.plan_id or any(construction) or args.apply or args.approve_plan or args.stable_inputs:
            parser.error('--verify-output requires only --backup and --plan-id')
    elif not all(construction) or args.backup or args.plan_id or ((args.approve_plan or args.stable_inputs) and not args.apply):
        parser.error('Supply all candidate preview inputs; apply additionally requires its exact review digest and stable inputs')
    try:
        if args.verify_output:
            result = handoff(args.verify_output, args.backup, args.plan_id)
        else:
            result = prepare(args.factory, planner.read_input(args.request, planner.MAX_REQUEST), args.baseline_manifest_sha256, args.baseline_reference, args.output)
            if args.apply:
                backup = apply(result, args.approve_plan, args.stable_inputs)
                result = handoff(args.output, backup, result['digest'])
        print(encoded(result).decode('ascii'), end='')
    except (OSError, ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
        print('Acceptance candidate rejected: ' + json.dumps(str(exc), ensure_ascii=True), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
