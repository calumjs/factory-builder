"""Inactive, plan-only post-deploy adapter. No commands, network or record writes.

Only a separately reviewed trusted bridge may supply context. An event is data,
never proof of deployment identity, readiness, authority or successful testing.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

LIMIT = 1024 * 1024


def fail(message):
    raise ValueError(message)


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected.split()):
        fail('Unsupported context or recipe structure')


def label(value, limit=2000):
    if not isinstance(value, str) or not value or len(value) > limit or value != value.strip() or not value.isprintable():
        fail('Expected a bounded non-secret single-line value')
    return value


def sha(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})', value):
        fail('Use exact lowercase full subject and storage IDs')
    return value


def target(value):
    label(value)
    try:
        parsed = urlsplit(value)
        parsed.port
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment or '\\' in value or any(c.isspace() for c in value):
            fail('Use an approved HTTPS target without credentials, query or fragment')
    except (ValueError, UnicodeError):
        fail('Use an approved HTTPS target without credentials, query or fragment')
    return value


def relative(value):
    label(value, 256)
    if '\\' in value or ':' in value or value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        fail('Use canonical repository-relative evidence and factory paths')
    return value


def absolute(value):
    label(value)
    path = Path(value)
    if not path.is_absolute():
        fail('Use explicit absolute trusted paths and checkout roots')
    return path.resolve()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def plan(context, event=None):
    fields(context, 'schema mode repository subject environment target deployment recipe source_checkout evidence_checkout python helper factory storage evidence_directory required_tasks manual_reason')
    if type(context['schema']) is not int or context['schema'] != 1 or context['mode'] not in ('deployment_status', 'manual'):
        fail('Unsupported adapter schema or trigger mode')
    repository = label(context['repository'], 200)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        fail('Use an explicit repository owner/name')
    subject, storage = sha(context['subject']), sha(context['storage'])
    if len(subject) != len(storage):
        fail('Subject and storage must use the same full object-ID format')
    environment, url = label(context['environment'], 200), target(context['target'])
    deployment = context['deployment']
    fields(deployment, 'repository subject environment target state provider_deployment_id github_deployment_id verification_reference')
    for key in ('repository', 'subject', 'environment', 'target'):
        if deployment[key] != context[key]:
            fail('Independent deployment claims must match the selected repository, subject, environment and target')
    if deployment['state'] != 'READY':
        fail('Independent current deployment readiness must be supplied before planning')
    label(deployment['provider_deployment_id'], 256)
    label(deployment['verification_reference'])
    deployment_id = deployment['github_deployment_id']
    if deployment_id is not None and (type(deployment_id) is not int or not 0 < deployment_id <= 2**63-1):
        fail('GitHub deployment identity must be a positive integer or explicit null for manual fallback')
    if context['mode'] == 'deployment_status':
        if context['manual_reason'] is not None or deployment_id is None:
            fail('Event mode requires a GitHub deployment identity and no manual reason')
        if not isinstance(event, dict):
            fail('Event mode requires a native deployment_status JSON object')
        status, dep, repo = (event.get(key) for key in ('deployment_status', 'deployment', 'repository'))
        if any(not isinstance(value, dict) for value in (status, dep, repo)):
            fail('Deployment event is missing required objects')
        # Native GitHub events contain other fields. They are deliberately ignored.
        if status.get('state') != 'success' or repo.get('full_name') != repository or dep.get('sha') != subject or type(dep.get('id')) is not int or dep['id'] != deployment_id:
            fail('Deployment event does not match the selected successful deployment identity')
        if status.get('environment') != environment or dep.get('environment') != environment:
            fail('Both event environment labels must match the selected environment')
        if status.get('environment_url') != url:
            fail('Event environment_url must match the approved target; use independent manual fallback if unavailable')
    else:
        if event is not None:
            fail('Manual mode does not consume an event')
        label(context['manual_reason'], 1000)

    recipe = context['recipe']
    fields(recipe, 'command environment env_names target')
    argv = recipe['command']
    if not isinstance(argv, list) or not 1 <= len(argv) <= 64:
        fail('Recipe command must be a bounded literal argv array')
    for arg in argv:
        label(arg)
    names = recipe['env_names']
    if not isinstance(names, list) or len(names) > 64 or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', n) for n in names) or len(set(names)) != len(names):
        fail('Recipe environment must contain unique variable names, never secret values')
    spec = recipe['target']
    fields(spec, 'kind value base_url_env')
    if recipe['environment'] != environment or spec['kind'] != 'web' or spec['value'] != url or not isinstance(spec['base_url_env'], str) or spec['base_url_env'] not in names:
        fail('Recipe must name the selected web target, environment and declared base URL variable')
    source, evidence = (absolute(context[key]) for key in ('source_checkout', 'evidence_checkout'))
    for key in ('python', 'helper'):
        trusted = absolute(context[key])
        if any(trusted == root or root in trusted.parents for root in (source, evidence)):
            fail('Trusted interpreter and evidence helper must be outside both source and evidence checkouts')
    for key in ('factory', 'evidence_directory'):
        relative(context[key])
    tasks = context['required_tasks']
    if not isinstance(tasks, list) or len(tasks) > 256 or any(not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', task) for task in tasks) or len(set(tasks)) != len(tasks):
        fail('Required tasks must be explicit bounded unique task IDs')
    env = {'FACTORY_PYTHON': context['python'], 'FACTORY_TRUSTED_HELPER': context['helper'],
           'FACTORY_REPO': context['evidence_checkout'], 'FACTORY_DIRECTORY': context['factory'],
           'FACTORY_TESTED_SUBJECT_SHA': subject, 'FACTORY_EVIDENCE_STORAGE_SHA': storage,
           'FACTORY_STAGE': 'post-merge', 'FACTORY_ACTUAL_TARGET': url,
           'FACTORY_EVIDENCE_DIRECTORY': context['evidence_directory'],
           'FACTORY_REQUIRED_TASKS': json.dumps(tasks)}
    # Fixed sibling in the trusted installed template bundle, never event-selected.
    template = Path(__file__).with_name('job.example.py')
    with template.open('rb') as stream:
        template_bytes = stream.read(LIMIT + 1)
    if len(template_bytes) > LIMIT:
        fail('Trusted sibling template exceeds the size limit')
    # Load the fixed trusted sibling without import cache/bytecode writes. Its main
    # execution guard stays inactive; only its argument builder is called.
    module = {'__name__': 'factory_ci_job_template', '__file__': str(template)}
    exec(compile(template_bytes, str(template), 'exec'), module)
    return {'schema': 1, 'result': 'plan_only', 'trigger': context['mode'],
            'context_sha256': digest(context), 'event_sha256': digest(event) if event is not None else None,
            'subject': subject, 'storage': storage, 'actual_target': url,
            'smoke_plan': {'argv': list(argv), 'cwd': context['source_checkout'],
                           'environment_values': {spec['base_url_env']: url},
                           'other_environment_names': [name for name in names if name != spec['base_url_env']]},
            'assessment_after_recording_argv': module['command'](env),
            'notice': 'PLAN ONLY: no commands, deployment checks, records or gate assessment performed. Supplied claims are not authenticated. Reverify source/deployment binding before and after authorized smoke; record actual results before assessing E. Optional rows remain visible waivers.'}


def read_json(path):
    def finite_float(raw):
        value = float(raw)
        if not math.isfinite(value):
            fail('Nonfinite JSON numbers are unsupported')
        return value

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                fail('Duplicate JSON keys are unsupported')
            out[key] = value
        return out
    # Bounded read even when the file grows after stat; never allocate the full file.
    with Path(path).open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        fail('Input exceeds the adapter size limit')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=pairs, parse_float=finite_float,
                      parse_constant=lambda _: fail('Nonfinite JSON numbers are unsupported'))


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('Use --context and optional --event with bounded JSON files; see the post-deploy guide')


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument('--context', required=True)
    parser.add_argument('--event')
    try:
        args = parser.parse_args(argv)
        result = plan(read_json(args.context), read_json(args.event) if args.event else None)
    except (ValueError, OSError, UnicodeError, RecursionError, TypeError, OverflowError):
        print('Post-deploy plan refused: check the documented context, deployment identity, trusted paths and bounded JSON inputs.', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
