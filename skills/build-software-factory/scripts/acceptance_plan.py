"""Read-only append-only acceptance synchronization preview; no apply or adoption."""
import sys
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import argparse
import base64
import copy
import difflib
import json
import re
import stat

from gates import gate_rows, initial_table, requirements, ROW
from incremental_records import task_change
from integrity import check, digest, safe_path
from recover_factory import (MAX_FILE, MAX_TOTAL, decisions_for, existing, inventory, manifest,
                             rawhash, semantics, stable, strict_json, dumps)
from scaffold import validate

MAX_REQUEST = 65536
MAX_PLAN = 16 * 1024 * 1024
NOTICE = ('PREVIEW ONLY: no files written, scope registered, evidence verified or actions authorized. '
          'Candidate changes retain the original manifest. The predicted recovered manifest is NOT '
          'candidate content. Materialization, independent recovery review and adoption remain separate.')


def clean(value, label, limit=2048):
    if (not isinstance(value, str) or not value or len(value) > limit or
            value != value.strip() or not value.isprintable() or '|' in value):
        raise ValueError(label + ' must be bounded nonempty single-line text without pipes')
    return value


def read_input(path, limit):
    """Bound regular, literal-path input; diagnose without echoing private contents."""
    path = safe_path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError('Input must be a bounded regular file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    after = path.lstat()
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)
    if len(raw) > limit or len(raw) != before.st_size or fields(before) != fields(after):
        raise ValueError('Input changed or exceeded its size limit')
    try:
        return strict_json(raw)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError('Input must contain unambiguous finite JSON') from exc


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def members(text, start):
    """Locate already strict-validated JSON object value spans, without reformatting."""
    decoder = json.JSONDecoder()
    def space(index):
        while index < len(text) and text[index] in ' \t\r\n':
            index += 1
        return index
    index = space(start)
    if text[index] != '{':
        raise ValueError('Unsupported JSON insertion container')
    index = space(index + 1)
    result = {}
    while text[index] != '}':
        key, end = decoder.raw_decode(text, index)
        index = space(end)
        if text[index] != ':':
            raise ValueError('Invalid JSON member boundary')
        begin = space(index + 1)
        _, end = decoder.raw_decode(text, begin)
        result[key] = (begin, end)
        index = space(end)
        if text[index] == '}':
            break
        if text[index] != ',':
            raise ValueError('Invalid JSON member separator')
        index = space(index + 1)
    return result


def append_json(raw, path, value, key=None):
    """Insert only new tokens; every original byte (including BOM/spacing) survives."""
    parsed = strict_json(raw)
    text = raw.decode('utf-8')
    start = 1 if text.startswith('\ufeff') else 0
    while text[start] in ' \t\r\n':
        start += 1
    end = json.JSONDecoder().raw_decode(text, start)[1]
    container = parsed
    for name in path:
        start, end = members(text, start)[name]
        container = container[name]
    if key is None:
        if not isinstance(container, list):
            raise ValueError('Expected an existing JSON array')
        fragment = json.dumps(value, ensure_ascii=True, allow_nan=False)
    else:
        if not isinstance(container, dict) or key in container:
            raise ValueError('Expected an object with no existing insertion key')
        fragment = json.dumps(key) + ': ' + json.dumps(value, ensure_ascii=True, allow_nan=False)
    point = end - 1
    while point > start + 1 and text[point - 1] in ' \t\r\n':
        point -= 1
    addition = (', ' if container else '') + fragment
    result = (text[:point] + addition + text[point:]).encode('utf-8')
    strict_json(result)
    return result


def document(raw):
    text = raw.decode('utf-8')
    if '\r' in text.replace('\r\n', '') or ('\r\n' in text and '\n' in text.replace('\r\n', '')):
        raise ValueError('Mixed/unsupported document line endings require manual review')
    return text.splitlines(keepends=True), '\r\n' if '\r\n' in text else '\n'


def insert_lines(lines, at, addition, newline):
    if at and not lines[at - 1].endswith(('\n', '\r')):
        addition = newline + addition
    return (''.join(lines[:at]) + addition + ''.join(lines[at:])).encode('utf-8')


def visible_lines(lines):
    """Conservatively exclude fenced examples and HTML comments, not a Markdown parser."""
    visible = []
    fence = None
    comment = False
    for line in lines:
        content = line.lstrip('\ufeff').rstrip('\r\n')
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', content)
        if fence is not None:
            visible.append(False)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        if not comment and marker:
            fence = marker[1]
            visible.append(False)
            continue
        visible.append(not comment and '<!--' not in content and '-->' not in content)
        position = 0
        while True:
            token = '-->' if comment else '<!--'
            index = content.find(token, position)
            if index < 0:
                break
            comment = not comment
            position = index + len(token)
    return visible


def append_acceptance(raw, old, ident, criterion):
    lines, newline = document(raw)
    plain = [line.rstrip('\r\n') for line in lines]
    visible = visible_lines(lines)
    headings = [i for i, line in enumerate(plain) if visible[i] and line.lstrip('\ufeff') == '# Acceptance criteria']
    if len(headings) != 1:
        raise ValueError('Acceptance document requires one visible recognized heading; review fenced/commented content manually')
    found = []
    for i, line in enumerate(plain):
        if visible[i] and re.match(r'^\s*[-*+]\s*A[0-9]', line):
            match = re.fullmatch(r'- (A[1-9][0-9]*): (.*)', line)
            if match is None:
                raise ValueError('Malformed criterion-like bullet requires manual review')
            found.append((i, match))
    if [(match[1], match[2]) for _, match in found] != [(f'A{i+1}', value) for i, value in enumerate(old)]:
        raise ValueError('Acceptance document does not match the existing ordered criteria')
    end = next((i for i in range(headings[0] + 1, len(lines)) if visible[i] and re.match(r'^#{1,6} ', plain[i])), len(lines))
    for index, _ in found:
        if index <= headings[0] or index + 1 >= end:
            raise ValueError('Acceptance records must follow their heading in the recognized visible section')
        if not visible[index + 1] or re.fullmatch(r'  Owner: .+; status: .+; evidence: .+', plain[index + 1]) is None:
            raise ValueError('Unsupported acceptance metadata; preserve it for manual review')
    at = found[-1][0] + 2
    addition = '- ' + ident + ': ' + criterion + newline + '  Owner: unassigned; status: NOT VERIFIED; evidence: none.' + newline
    return insert_lines(lines, at, addition, newline)


def append_brief(raw, old, criterion):
    lines, newline = document(raw)
    visible = visible_lines(lines)
    headings = [i for i, line in enumerate(lines) if visible[i] and line.rstrip('\r\n') == '## Acceptance']
    if len(headings) != 1:
        raise ValueError('Brief requires one recognized Acceptance section')
    start = headings[0] + 1
    end = next((i for i in range(start, len(lines)) if visible[i] and lines[i].startswith('## ')), len(lines))
    if any(not visible[i] for i in range(start, end)):
        raise ValueError('Brief acceptance section must be visible, outside fenced/commented content')
    body = [line.rstrip('\r\n') for line in lines[start:end] if line.strip()]
    if body != ['- ' + value for value in old]:
        raise ValueError('Custom/ambiguous brief acceptance section requires manual review')
    at = end
    while at > start and not lines[at - 1].strip():
        at -= 1
    return insert_lines(lines, at, '- ' + criterion + newline, newline)


def append_verification(raw, config, research, ident):
    lines, newline = document(raw)
    visible = visible_lines(lines)
    if any(not visible[i] for i, line in enumerate(lines) if ROW.match(line)):
        raise ValueError('Verification rows must be visible, outside fenced/commented content')
    at = max(i for i, line in enumerate(lines) if ROW.match(line)) + 1
    addition = next(line for line in initial_table(config, research).splitlines() if line.startswith('| ' + ident + ' |'))
    result = insert_lines(lines, at, addition + newline, newline)
    gate_rows(result.decode('utf-8-sig'))
    return result


def request_values(request, count):
    if not isinstance(request, dict) or set(request) != {'schema_version', 'issue', 'criterion', 'task', 'test_map'} or type(request['schema_version']) is not int or request['schema_version'] != 1:
        raise ValueError('Request must match the version-1 acceptance plan schema')
    if len(canonical(request)) > MAX_REQUEST:
        raise ValueError('Request exceeds 64 KiB')
    clean(request['issue'], 'Issue reference')
    clean(request['criterion'], 'Criterion')
    if '<!--' in request['criterion'] or '-->' in request['criterion']:
        raise ValueError('Criterion cannot contain HTML comment delimiters')
    task = request['task']
    if not isinstance(task, dict) or set(task) != {'id', 'goal', 'owner', 'depends_on', 'allowed_paths', 'status'}:
        raise ValueError('Task must contain the supported fields; acceptance ID is allocated by this planner')
    task = copy.deepcopy(task)
    task['acceptance_ids'] = [f'A{count+1}']
    mapping = request['test_map']
    if not isinstance(mapping, dict) or set(mapping) != {'adapter', 'design', 'register_reason'} or mapping['adapter'] != 'a-keyed-opaque-v1':
        raise ValueError('Explicit a-keyed-opaque-v1 test-map adapter required')
    if not isinstance(mapping['design'], (dict, list, str)) or not mapping['design'] or (isinstance(mapping['design'], str) and not mapping['design'].strip()):
        raise ValueError('Provide nonempty bounded test design data; it is not verified or executed')
    if not isinstance(mapping['register_reason'], str):
        raise ValueError('Test-map registration reason must be a string')
    return task, mapping


def file_change(before, after):
    return {'before_sha256': rawhash(before) if before is not None else None,
            'after_sha256': rawhash(after), 'after_base64': base64.b64encode(after).decode('ascii'),
            'diff': ''.join(difflib.unified_diff((before or b'').decode('utf-8-sig').splitlines(True),
                                               after.decode('utf-8-sig').splitlines(True), fromfile='before', tofile='proposed'))}


def preview(factory, request, baseline_pin, baseline_reference):
    clean(baseline_reference, 'Independent baseline reference', 2000)
    if not isinstance(baseline_pin, str) or re.fullmatch('[0-9a-f]{64}', baseline_pin) is None:
        raise ValueError('Independently supplied raw accepted-manifest SHA256 required')
    root = existing(factory)
    snapshot = stable(root)
    files = snapshot['files']
    accepted = manifest(snapshot)
    if rawhash(files['manifest.json']) != baseline_pin:
        raise ValueError('Accepted-manifest pin does not match; do not derive a replacement pin from drifted files')
    check(root, quiet=True)
    semantics(snapshot)
    config = strict_json(files['config.json'])
    research = strict_json(files['research.json'])
    plan = strict_json(files['task-plan.json'])
    old = config['acceptance']
    ident = f'A{len(old)+1}'
    expected = requirements(config, research)
    rows = gate_rows(files['verification.md'].decode('utf-8-sig'))
    if set(rows) != set(expected):
        raise ValueError('Existing gate inventory must match configured requirements before registration')
    known = {f'A{i+1}' for i in range(len(old))}
    for task in plan['tasks']:
        links = task.get('acceptance_ids')
        if not isinstance(links, list) or not links or any(not isinstance(link, str) or link not in known for link in links):
            raise ValueError('Existing living task has unresolved acceptance links')
    task, mapping = request_values(request, len(old))
    config_after = copy.deepcopy(config)
    config_after['acceptance'].append(request['criterion'])
    validate(config_after)
    # Use existing insertion validation, but preserve the original JSON bytes below.
    task_change(plan, config_after, task)
    changes = {
        'config.json': append_json(files['config.json'], ('acceptance',), request['criterion']),
        'acceptance.md': append_acceptance(files['acceptance.md'], old, ident, request['criterion']),
        'project-brief.md': append_brief(files['project-brief.md'], old, request['criterion']),
        'task-plan.json': append_json(files['task-plan.json'], ('tasks',), task),
        'verification.md': append_verification(files['verification.md'], config_after, research, ident),
    }
    if 'test-map.json' in files:
        if mapping['register_reason'] or 'test-map.json' not in accepted['contracts']:
            raise ValueError('Existing test map must remain a named immutable contract; registration reason must be empty')
        current = strict_json(files['test-map.json'])
        if not isinstance(current, dict) or any(key not in known for key in current):
            raise ValueError('Explicit adapter requires an object keyed only by existing acceptance IDs')
        changes['test-map.json'] = append_json(files['test-map.json'], (), mapping['design'], key=ident)
    else:
        clean(mapping['register_reason'], 'Explicit new immutable test-map registration reason')
        changes['test-map.json'] = (json.dumps({ident: mapping['design']}, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
    proposed = copy.deepcopy(accepted)
    decisions = {'accept_changed': [], 'register': [], 'remove': []}
    for name, raw in sorted(changes.items()):
        if len(raw) > MAX_FILE:
            raise ValueError('Proposed file exceeds the supported recovery size limit')
        if name in accepted['living']:
            continue
        if name in accepted['contracts']:
            decisions['accept_changed'].append({'path': name, 'reason': 'Reviewed append-only ' + ident + ' registration for ' + request['issue']})
        elif name == 'test-map.json':
            decisions['register'].append({'path': name, 'reason': mapping['register_reason']})
        else:
            raise ValueError('Unexpected contract registration')
        proposed['contracts'][name] = digest(raw)
    decisions_for(decisions, {key: {entry['path'] for entry in entries} for key, entries in decisions.items()})
    proposed_manifest = dumps(proposed).encode('utf-8')
    combined = {**files, **changes, 'manifest.json': proposed_manifest}
    if (len(combined) > 512 or any(len(raw) > MAX_FILE for raw in combined.values()) or
            sum(map(len, combined.values())) > MAX_TOTAL):
        raise ValueError('Proposed snapshot exceeds supported recovery limits')
    semantics({**snapshot, 'files': combined})
    if inventory(stable(root)) != inventory(snapshot):
        raise ValueError('Factory changed during preview; no plan is valid')
    payload = {'schema_version': 1, 'factory': str(root), 'accepted_manifest_sha256': baseline_pin,
               'baseline_reference': baseline_reference, 'source_inventory': inventory(snapshot),
               'request': copy.deepcopy(request), 'new_acceptance_id': ident,
               'candidate_changes': {name: file_change(files.get(name), raw) for name, raw in sorted(changes.items())},
               'recovery_decisions': decisions,
               'predicted_recovered_manifest': file_change(files['manifest.json'], proposed_manifest)}
    envelope = {'notice': NOTICE, 'plan': payload, 'digest': rawhash(canonical(payload))}
    if len(json.dumps(envelope, ensure_ascii=True, indent=2, allow_nan=False).encode('ascii')) + 1 > MAX_PLAN:
        raise ValueError('Preview exceeds the supported plan size limit')
    return envelope


def validate_plan(saved, current):
    """Caller recomputes current from explicit inputs; never trust saved output bytes."""
    if canonical(saved) != canonical(current):
        raise ValueError('Saved plan differs from the current recomputed preview; review a fresh plan')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--baseline-manifest-sha256', required=True)
    parser.add_argument('--baseline-reference', required=True)
    parser.add_argument('--validate-plan', help='Read and compare a previously saved preview; no writes or approval')
    args = parser.parse_args()
    try:
        result = preview(args.factory, read_input(args.request, MAX_REQUEST), args.baseline_manifest_sha256, args.baseline_reference)
        if args.validate_plan:
            validate_plan(read_input(args.validate_plan, MAX_PLAN), result)
        # JSON escapes terminal controls in untrusted diffs; no command is executed.
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
        print('Acceptance preview rejected: ' + json.dumps(str(exc), ensure_ascii=True), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
