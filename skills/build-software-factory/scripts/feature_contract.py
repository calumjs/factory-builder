"""Opt-in CI composition of supplied closing claims and committed contract deltas.

No classification discovery, application execution, evidence mutation or authority.
Only ci_evidence calls this installed module; no copied-runtime dependency.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import unicodedata

from change_contract import assess as assess_mapping
from ci_evidence import full_sha, relative, task_core
from export_checksums import Objects, root_tree, MAX_ENTRIES, MAX_DEPTH, MAX_PATH
from integrity import strict_json, validate_task_plan, digest
from release_identity import LocalGit
from scaffold import validate
from verify_install import reject_redirected_ancestors

MAX_POLICY = 4096
MAX_REQUEST = 256 * 1024
MAX_ISSUES = 100
MAX_IDS = 200
ISSUE = re.compile(r'[a-z0-9][a-z0-9-]{0,99}/[a-z0-9][a-z0-9_.-]{0,99}#[1-9][0-9]{0,9}\Z')
PIN = re.compile(r'[0-9a-f]{64}\Z')
NOTICE = ('Supplied closing claims, classification and mappings only; completeness and semantic coverage '
          'are not discovered or attested. Structural policy evaluation does not run tests, pass or waive '
          'evidence, activate CI, or grant merge/deployment authority. References and paths are withheld.')


class FeatureInputError(ValueError):
    pass


def fail(code):
    raise FeatureInputError('Feature contract '+code+'; no feature policy conclusion. '
                            'Review explicit inputs and references/feature-contract-ci.md; no files changed.')


def canonical(value):
    # Property order is immaterial; every list retains its observable order.
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_input(path, repo, limit):
    source = reject_redirected_ancestors(os.path.abspath(path))
    if str(source).replace('/', '\\').startswith('\\\\'):
        fail('LOCAL_INPUT_REQUIRED')
    if source == repo or repo in source.parents:
        fail('EXTERNAL_INPUT_REQUIRED')
    before = source.lstat()
    regular = lambda s: stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and not getattr(s, 'st_file_attributes', 0) & 0x400
    signature = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns)
    if not regular(before) or before.st_size > limit:
        fail('INPUT_SHAPE_OR_LIMIT')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(source, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not regular(opened) or signature(opened) != signature(before):
            fail('INPUT_CHANGED')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    current = reject_redirected_ancestors(source).lstat()
    if (not all(regular(s) for s in (after, current)) or len(raw) != before.st_size or len(raw) > limit
            or len({signature(s) for s in (before, opened, after, current)}) != 1
            or before.st_ctime_ns != current.st_ctime_ns or opened.st_ctime_ns != after.st_ctime_ns):
        fail('INPUT_CHANGED')
    return raw, signature(current), current.st_ctime_ns


class CommittedFiles:
    """Read only named blobs through verified commits/trees, never worktree paths."""
    def __init__(self, repo, width):
        self.git = LocalGit(repo)
        self.objects = Objects(self.git, width)
        self.count = 0

    def members(self, oid):
        raw = self.objects.read(oid, 'tree')
        position = 0
        previous = None
        names = set()
        result = {}
        while position < len(raw):
            self.objects.deadline()
            self.count += 1
            if self.count > MAX_ENTRIES:
                fail('TREE_ENTRY_LIMIT')
            end = raw.find(b'\0', position)
            width = self.objects.width // 2
            if end < 0 or end + 1 + width > len(raw):
                fail('MALFORMED_TREE')
            mode, separator, encoded = raw[position:end].partition(b' ')
            if not separator or mode not in (b'40000', b'100644', b'100755') or b'/' in encoded:
                fail('UNSUPPORTED_TREE_ENTRY')
            name = relative(encoded.decode('utf-8'))
            if len(encoded) > MAX_PATH:
                fail('TREE_PATH_LIMIT')
            normalized = unicodedata.normalize('NFC', name).casefold()
            order = encoded + (b'/' if mode == b'40000' else b'')
            if normalized in names or (previous is not None and order <= previous):
                fail('AMBIGUOUS_TREE')
            names.add(normalized)
            previous = order
            result[name] = (mode, raw[end+1:end+1+width].hex())
            position = end+1+width
        return result

    def read(self, revision, path):
        parts = relative(path).split('/')
        if len(parts) > MAX_DEPTH or len(path.encode('utf-8')) > MAX_PATH:
            fail('TREE_PATH_LIMIT')
        oid = root_tree(self.objects.read(revision, 'commit'), self.objects.width)
        for index, part in enumerate(parts):
            members = self.members(oid)
            if part not in members:
                fail('MISSING_COMMITTED_CONTRACT')
            mode, oid = members[part]
            if index == len(parts)-1:
                if mode not in (b'100644', b'100755'):
                    fail('REGULAR_CONTRACT_REQUIRED')
                return self.objects.read(oid, 'blob')
            if mode != b'40000':
                fail('DIRECTORY_REQUIRED')


def snapshot(reader, revision, factory):
    raw = {name: reader.read(revision, factory+'/'+name) for name in ('config.json', 'task-plan.json', 'manifest.json')}
    config, plan = (strict_json(raw[name].decode('utf-8-sig')) for name in ('config.json', 'task-plan.json'))
    manifest = strict_json(raw['manifest.json'].decode('utf-8-sig'))
    if (not isinstance(manifest, dict) or type(manifest.get('schema')) is not int or manifest['schema'] != 2
            or manifest.get('hash_mode') != 'utf8-lf' or not isinstance(manifest.get('contracts'), dict)
            or not isinstance(manifest.get('living'), list)
            or any(not isinstance(name, str) for name in manifest['living'])
            or len(set(manifest['living'])) != len(manifest['living'])
            or manifest['contracts'].get('config.json') != digest(raw['config.json'])
            or 'config.json' in manifest['living'] or 'task-plan.json' in manifest['contracts']
            or 'task-plan.json' not in manifest['living']):
        fail('COMMITTED_CONFIG_REGISTRATION_INVALID')
    validate(config)
    validate_task_plan(plan)
    acceptance = {f'A{i+1}': criterion for i, criterion in enumerate(config['acceptance'])}
    tasks = {}
    for task in plan['tasks']:
        links = task.get('acceptance_ids')
        if (not isinstance(links, list) or not links or any(not isinstance(v, str) for v in links)
                or len(set(links)) != len(links) or set(links)-set(acceptance)):
            fail('INVALID_COMMITTED_TASK_LINKS')
        tasks[task['id']] = {key: value for key, value in task.items() if key != 'status'}
    return raw, config, plan, acceptance, tasks


def validate_policy(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'acceptance_delta', 'task_delta'}
            or type(value['version']) is not int or value['version'] != 1
            or value['acceptance_delta'] not in ('reuse', 'added')
            or value['task_delta'] not in ('reuse', 'added', 'added_or_changed')):
        fail('UNSUPPORTED_POLICY')
    return value


def validate_request(value, base, subject):
    if (not isinstance(value, dict) or set(value) != {'version', 'base', 'subject', 'closing_issues', 'contract'}
            or type(value['version']) is not int or value['version'] != 1
            or value['base'] != base or value['subject'] != subject):
        fail('REQUEST_IDENTITY_OR_SCHEMA')
    closing = value['closing_issues']
    if (not isinstance(closing, list) or len(closing) > MAX_ISSUES
            or any(not isinstance(v, str) or ISSUE.fullmatch(v) is None for v in closing)
            or len(set(closing)) != len(closing)):
        fail('CLOSING_ISSUES_INVALID')
    contract = value['contract']
    if not isinstance(contract, dict) or not isinstance(contract.get('issues'), list) or len(contract['issues']) > MAX_ISSUES:
        fail('MAPPING_LIMIT_OR_SCHEMA')
    for mapping in contract['issues']:
        if (not isinstance(mapping, dict) or set(mapping) != {'reference', 'tasks', 'acceptance'}
                or not isinstance(mapping['reference'], str) or ISSUE.fullmatch(mapping['reference']) is None):
            fail('MAPPING_REFERENCE_INVALID')
        for key in ('tasks', 'acceptance'):
            if (not isinstance(mapping[key], list) or len(mapping[key]) > MAX_IDS
                    or any(not isinstance(v, str) or len(v) > 100 for v in mapping[key])):
                fail('MAPPING_LIMIT_OR_SCHEMA')
    if set(closing)-{m['reference'] for m in contract['issues']}:
        fail('CLOSING_ISSUE_UNMAPPED')
    return contract


class FeatureCheck:
    """Capture/recheck external inputs; caller retains existing CI checkout guards."""
    def __init__(self, repo, factory, subject, policy_path, policy_pin, request_path, base):
        self.repo = reject_redirected_ancestors(repo).resolve(strict=True)
        self.factory = relative(factory)
        self.base, self.subject = full_sha(base), full_sha(subject)
        if len(self.base) != len(self.subject):
            fail('OBJECT_FORMAT_MISMATCH')
        if not isinstance(policy_pin, str) or PIN.fullmatch(policy_pin) is None:
            fail('INDEPENDENT_POLICY_PIN_REQUIRED')
        self.policy_path, self.request_path = policy_path, request_path
        self.policy_input = read_input(policy_path, self.repo, MAX_POLICY)
        if hashlib.sha256(self.policy_input[0]).hexdigest() != policy_pin:
            fail('POLICY_PIN_MISMATCH')
        self.request_input = read_input(request_path, self.repo, MAX_REQUEST)
        self.policy = validate_policy(strict_json(self.policy_input[0].decode('utf-8')))
        self.request = strict_json(self.request_input[0].decode('utf-8'))
        self.contract = validate_request(self.request, self.base, self.subject)
        self.policy_pin = policy_pin

    def stable(self):
        if (read_input(self.policy_path, self.repo, MAX_POLICY) != self.policy_input
                or read_input(self.request_path, self.repo, MAX_REQUEST) != self.request_input):
            fail('INPUT_CHANGED_REVIEW_AGAIN')

    def assess(self, root):
        reader = CommittedFiles(self.repo, len(self.subject))
        before = snapshot(reader, self.base, self.factory)
        after = snapshot(reader, self.subject, self.factory)
        # Verify both objects before graph lookup; no automatic base selection.
        reader.git.read('merge-base', '--is-ancestor', self.base, self.subject, limit=32)
        if (after[0]['config.json'] != (root/'config.json').read_bytes()
                or canonical(task_core(after[2])) != canonical(task_core(strict_json((root/'task-plan.json').read_bytes())))):
            fail('STORAGE_DEFINITIONS_DIFFER_FROM_SUBJECT')
        mapping = assess_mapping(root, self.contract, self.subject)
        result = {'base': self.base, 'subject': self.subject, 'policy': self.policy,
                  'policy_sha256': self.policy_pin, 'request_sha256': hashlib.sha256(self.request_input[0]).hexdigest(),
                  'mapping_digest': mapping['mapping_digest'], 'closing_issue_count': len(self.request['closing_issues']),
                  'assessment': 'outside_trigger_claim', 'issues': [], 'problems': [], 'notice': NOTICE}
        # Exemption remains an operator claim. Invalid history/mappings never bypass validation above.
        if self.contract['classification'] == 'maintenance' or not self.request['closing_issues']:
            result['outside_trigger_reason'] = ('maintenance_claim' if self.contract['classification'] == 'maintenance'
                                                else 'no_closing_issues_claim')
            return result
        old, new = before[1]['acceptance'], after[1]['acceptance']
        if len(new) < len(old) or canonical(new[:len(old)]) != canonical(old):
            fail('ACCEPTANCE_NOT_APPEND_ONLY_USE_REVIEWED_PLANNER_OR_RECOVERY')
        mappings = {item['reference']: item for item in self.contract['issues']}
        for index, reference in enumerate(self.request['closing_issues'], 1):
            item = mappings[reference]
            acceptance_added = [ident for ident in item['acceptance'] if ident not in before[3]]
            task_added = [ident for ident in item['tasks'] if ident not in before[4]]
            task_changed = [ident for ident in item['tasks'] if ident in before[4]
                            and canonical(before[4][ident]) != canonical(after[4][ident])]
            codes = []
            if self.policy['acceptance_delta'] == 'added' and not acceptance_added:
                codes.append('ACCEPTANCE_ADDITION_REQUIRED')
            rule = self.policy['task_delta']
            if rule == 'added' and not task_added:
                codes.append('TASK_ADDITION_REQUIRED')
            if rule == 'added_or_changed' and not (task_added or task_changed):
                codes.append('TASK_DEFINITION_DELTA_REQUIRED')
            result['issues'].append({'request_issue_index': index, 'acceptance_added': len(acceptance_added),
                                     'tasks_added': len(task_added), 'tasks_changed': len(task_changed), 'problems': codes})
            result['problems'].extend('Feature closing issue '+str(index)+': '+code for code in codes)
        result['assessment'] = 'blocked' if result['problems'] else 'structural_policy_satisfied'
        reader.objects.deadline()
        return result


def guarded(operation):
    """Fixed failure boundary: never echo input values, paths, Git stderr or JSON."""
    try:
        return operation()
    except FeatureInputError:
        raise
    except (ValueError, OSError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError, subprocess.TimeoutExpired):
        fail('INVALID_UNAVAILABLE_OR_UNSTABLE_INPUT')
