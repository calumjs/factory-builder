"""Print recipe-aware observation drafts; never execute checks or change records."""
import sys
if __name__ == '__main__':
    sys.dont_write_bytecode = True
import argparse
import json
import os
from pathlib import Path
import re

from acceptance_links import guarded_path, snapshot_factory, strict_json, validate_snapshot
from gates import gate_rows, policy_controls, requirements
from operations import controls

MAX_GATES = 32
MAX_OUTPUT = 256_000
NOTICE = ('DRAFT ONLY - NOT EXECUTION EVIDENCE. Planned context is not an observation. '
          'No check ran, no record changed, and no pass, waiver or release authority was created.')


class DraftInputError(ValueError):
    """Fixed diagnostics that do not echo private input contents."""


def _snapshot(factory):
    try:
        raw = os.fspath(factory)
        if (not isinstance(raw, str) or not raw or len(raw) > 4096 or '\x00' in raw
                or raw.replace('/', '\\').startswith(('\\\\', '\\??\\'))):
            raise ValueError('Unsupported path')
        path = Path(raw)
        if any(':' in part for part in path.parts if part != path.anchor):
            raise ValueError('Unsupported path component')
        root = guarded_path(os.path.abspath(guarded_path(path)))
        return root, snapshot_factory(root)
    except (ValueError, OSError, TypeError) as exc:
        raise DraftInputError('Factory path or bounded snapshot is invalid; use stable local regular files without redirects') from exc


def draft_observations(factory, gates):
    """Return a review envelope; only each observation uses the writer's schema."""
    if (not isinstance(gates, list) or not 1 <= len(gates) <= MAX_GATES
            or any(not isinstance(g, str) or re.fullmatch(r'[A-Z][1-9][0-9]{0,5}', g) is None for g in gates)
            or len(set(gates)) != len(gates)):
        raise DraftInputError('Select 1 to 32 unique, exact gate IDs explicitly')
    root, snapshot = _snapshot(factory)
    files, _ = snapshot
    try:
        validate_snapshot(files)
        config = strict_json(files['config.json'])
        research = strict_json(files['research.json'])
        policy = policy_controls(files['policy.md'].decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n'))
        configured_controls = controls(config)
        expected = requirements(config, research)
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        raise DraftInputError('Factory integrity, living records or configured controls are invalid; inspect the factory privately') from exc
    if json.dumps(policy, sort_keys=True) != json.dumps(configured_controls, sort_keys=True):
        raise DraftInputError('Configuration and policy controls disagree; reconcile them before drafting')
    try:
        rows = gate_rows(files['verification.md'].decode('utf-8-sig'))
    except (ValueError, KeyError, TypeError) as exc:
        raise DraftInputError('Gate rows are malformed or ambiguous; repair the record before drafting') from exc
    if any(g not in rows or rows[g]['stage'] != spec['stage'] for g, spec in expected.items()):
        raise DraftInputError('Expected gate rows are missing or in the wrong stage')
    if any(g not in expected for g in gates):
        raise DraftInputError('Selection includes an unknown or unconfigured gate')
    drafts = []
    for gate in gates:
        spec, row = expected[gate], rows[gate]
        recipe = spec.get('recipe')
        if recipe and row['design'] != spec['design']:
            raise DraftInputError('Selected recipe design differs from its row; review a synchronized plan update first')
        planned = {
            'notice': 'PLANNED CONTEXT ONLY; not observed settings or execution authority',
            'stage': spec['stage'], 'design': spec['design'],
            'retained_row_design': row['design'],
            'environment': recipe['environment'] if recipe else None,
            'target': recipe['target'] if recipe else None,
            'recipe': recipe,
            'required': row['required'],
            'applicability': spec['applicability'],
        }
        observation = {'gate': gate, 'result': 'NOT RUN', 'revision': '',
                       'environment': 'unconfirmed', 'evidence': '', 'target': '',
                       'checked_at': '', 'exit_status': ''}
        drafts.append({'planned_context': planned, 'observation': observation})
    result = {'draft_version': 1, 'notice': NOTICE, 'drafts': drafts}
    # Bound the actual escaped JSON emitted by the CLI, including its newline.
    if len((json.dumps(result, ensure_ascii=True, indent=2) + '\n').encode('utf-8')) > MAX_OUTPUT:
        raise DraftInputError('Draft output exceeds the size limit; select fewer gates')
    if _snapshot(root)[1] != snapshot:
        raise DraftInputError('Factory changed during drafting; retry with stable inputs')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True, help='Explicit local factory root; inputs must remain stable')
    parser.add_argument('--gate', action='append', required=True, help='Exact configured gate ID; repeat for up to 32 distinct gates')
    args = parser.parse_args(argv)
    try:
        result = draft_observations(args.factory, args.gate)
    except DraftInputError as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
