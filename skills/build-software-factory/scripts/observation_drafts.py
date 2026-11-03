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
from incremental_records import GATE_OBSERVATION_FIELDS, gate_change
from operations import controls

MAX_GATES = 32
MAX_OUTPUT = 256_000
MAX_OBSERVATION_FIELD = 8192
NOTICE = ('DRAFT ONLY - NOT EXECUTION EVIDENCE. Planned context is not an observation. '
          'No check ran, no record changed, and no pass, waiver or release authority was created.')
OBSERVATION_NOTICE = ('OPERATOR-SUPPLIED OBSERVATION ONLY. Validated against recorded rules; '
                      'not independently verified or executed. No factory record was written; '
                      'this output does not make a gate pass or grant execution or release authority. '
                      'Review it with the existing observation writer before any authorized apply.')


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


def _context(factory, gates):
    """Validate one captured factory and the explicit selection without writing."""
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
    for gate in gates:
        if expected[gate].get('recipe') and rows[gate]['design'] != expected[gate]['design']:
            raise DraftInputError('Selected recipe design differs from its row; review a synchronized plan update first')
    return root, snapshot, config, research, expected, rows


def _bounded_output(result):
    # Bound the actual escaped JSON emitted by the CLI, including its newline.
    if len((json.dumps(result, ensure_ascii=True, indent=2) + '\n').encode('utf-8')) > MAX_OUTPUT:
        raise DraftInputError('Prepared output exceeds the size limit; supply a smaller selection or observation')


def _unchanged(root, snapshot):
    if _snapshot(root)[1] != snapshot:
        raise DraftInputError('Factory changed during preparation; retry with stable inputs')


def draft_observations(factory, gates):
    """Return a review envelope; only each observation uses the writer's schema."""
    root, snapshot, _, _, expected, rows = _context(factory, gates)
    drafts = []
    for gate in gates:
        spec, row = expected[gate], rows[gate]
        recipe = spec.get('recipe')
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
    _bounded_output(result)
    _unchanged(root, snapshot)
    return result


def validated_observation(factory, observation):
    """Export exactly supplied values after existing writer validation; write nothing."""
    if not isinstance(observation, dict) or set(observation) != GATE_OBSERVATION_FIELDS:
        raise DraftInputError('Observation must explicitly supply exactly the existing eight fields')
    if any(not isinstance(value, str) or len(value) > MAX_OBSERVATION_FIELD for value in observation.values()):
        raise DraftInputError('Observation fields must be strings of at most 8192 characters')
    # An empty environment invokes the underlying writer's old-row fallback.
    # This convenience mode instead requires an explicit supplied value.
    if not observation['environment'].strip():
        raise DraftInputError('Supply an explicit environment; use unconfirmed for an unknown negative observation')
    result = dict(observation)
    root, snapshot, config, research, _, _ = _context(factory, [result['gate']])
    try:
        # Discard the proposed record. This is the same validation as the single
        # observation writer, including optional PASSED and G3/V1 dependencies.
        gate_change(snapshot[0]['verification.md'].decode('utf-8-sig'), config, research, result)
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise DraftInputError('Observation fails existing writer rules; privately review actual fields, recipe agreement and gate dependencies') from exc
    _bounded_output(result)
    _unchanged(root, snapshot)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True, help='Explicit local factory root; inputs must remain stable')
    parser.add_argument('--gate', action='append', required=True, help='Exact configured gate ID; repeat for up to 32 distinct gates')
    parser.add_argument('--observation', action='store_true', help='Export one explicitly supplied observation in the existing writer schema; does not write or execute')
    fields = ('result', 'revision', 'environment', 'target', 'checked_at', 'exit_status', 'evidence')
    for field in fields:
        parser.add_argument('--' + field.replace('_', '-'), help='Explicit operator-supplied ' + field + '; required with --observation, never filled from a recipe')
    args = parser.parse_args(argv)
    try:
        values = {field: getattr(args, field) for field in fields}
        if args.observation:
            if len(args.gate) != 1:
                raise DraftInputError('Observation mode requires exactly one --gate')
            if any(value is None for value in values.values()):
                raise DraftInputError('Observation mode requires --result, --revision, --environment, --target, --checked-at, --exit-status and --evidence explicitly')
            result = validated_observation(args.factory, dict(gate=args.gate[0], **values))
        else:
            if any(value is not None for value in values.values()):
                raise DraftInputError('Observed fields require --observation; draft mode accepts only factory and gate selection')
            result = draft_observations(args.factory, args.gate)
    except DraftInputError as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2
    if args.observation:
        print(OBSERVATION_NOTICE, file=sys.stderr)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
