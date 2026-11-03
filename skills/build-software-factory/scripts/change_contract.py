"""Read-only issue-to-contract preflight; mappings are claims, not test evidence."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path
import re
from integrity import safe_path, strict_json
from scoped_assessment import load


def text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or not value.isprintable():
        raise ValueError(label + ' must be nonempty single-line text')
    return value


def ids(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(label + ' must be a nonempty ID list')
    for item in value:
        text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(label + ' contains duplicate IDs')
    return set(value)


def assess(factory, contract, revision):
    if not isinstance(contract, dict) or set(contract) != {'version', 'subject', 'classification', 'rationale', 'issues'}:
        raise ValueError('Change contract must contain version, subject, classification, rationale and issues')
    if type(contract['version']) is not int or contract['version'] != 1:
        raise ValueError('Unsupported change contract version')
    if not isinstance(revision, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', revision):
        raise ValueError('--revision requires the full lowercase subject commit SHA')
    if contract['subject'] != revision:
        raise ValueError('Change contract subject differs from --revision; review the current diff and mapping')
    if contract['classification'] not in ('feature', 'maintenance'):
        raise ValueError('Classification must be feature or maintenance')
    text(contract['rationale'], 'rationale')
    mappings = contract['issues']
    if not isinstance(mappings, list) or (contract['classification'] == 'feature' and not mappings):
        raise ValueError('Feature changes require explicit issue mappings')
    root = safe_path(factory)
    names = ('manifest.json', 'config.json', 'research.json', 'policy.md', 'task-plan.json')
    before = {name: (root / name).read_bytes() for name in names}
    root, config, research, verification, plan = load(root)
    if before != {name: (root / name).read_bytes() for name in names}:
        raise ValueError('Factory changed during mapping assessment; retry on stable inputs')
    acceptance = {f'A{i+1}': value for i, value in enumerate(config['acceptance'])}
    tasks = {task['id']: task for task in plan['tasks']}
    seen = set()
    records = []
    for item in mappings:
        if not isinstance(item, dict) or set(item) != {'reference', 'tasks', 'acceptance'}:
            raise ValueError('Issue mapping must contain reference, tasks and acceptance')
        reference = text(item['reference'], 'issue reference')
        if reference in seen:
            raise ValueError('Duplicate issue reference')
        seen.add(reference)
        selected_tasks = ids(item['tasks'], 'tasks')
        selected_acceptance = ids(item['acceptance'], 'acceptance')
        if selected_tasks - set(tasks) or selected_acceptance - set(acceptance):
            raise ValueError('Issue mapping names unknown task or acceptance IDs')
        covered = set()
        for tid in selected_tasks:
            links = ids(tasks[tid].get('acceptance_ids'), 'selected task acceptance_ids')
            if links - set(acceptance):
                raise ValueError('Selected task has unknown acceptance links')
            if not links & selected_acceptance:
                raise ValueError('Selected task does not cover this issue mapping')
            covered |= links
        if selected_acceptance - covered:
            raise ValueError('Selected acceptance lacks a task in this issue mapping')
        records.append({'reference': reference,
                        'acceptance': {key: acceptance[key] for key in sorted(selected_acceptance)},
                        'tasks': [{key: value for key, value in tasks[tid].items() if key != 'status'}
                                  for tid in sorted(selected_tasks)]})
    identity = {'contract': contract, 'records': records,
                'factory': str(root),
                'inputs': {name: hashlib.sha256(data).hexdigest() for name, data in before.items()}}
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    return {'assessment': 'MAPPED FOR REVIEW' if mappings else 'MAINTENANCE CLAIM FOR REVIEW',
            'subject': revision, 'classification': contract['classification'], 'rationale': contract['rationale'],
            'mappings': records, 'mapping_digest': digest,
            'notice': 'Operator-supplied mapping only. Review the actual subject and diff for completeness and classification. '
                      'No tests ran, no evidence was passed or waived, no Git revision was resolved, and no CI or release authority was established.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--input', required=True, help='Explicit change-contract JSON outside the factory')
    parser.add_argument('--revision', required=True, help='Independently verified full subject commit SHA')
    args = parser.parse_args()
    source = safe_path(args.input)
    root = safe_path(args.factory)
    if source == root or root in source.parents:
        raise ValueError('Keep the change contract outside the factory')
    contract = strict_json(source.read_text(encoding='utf-8-sig'))
    print(json.dumps(assess(root, contract, args.revision), indent=2, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        sys.exit(2)
