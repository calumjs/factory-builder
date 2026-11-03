"""Explicit private analytics and experiment records; no collection or live actions."""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import Counter
import hashlib
from html import escape
import json
import math
import os
import dashboard
from integrity import safe_path
from learning_table import LEARNING_HEADER, validate_learning_log
import run_traces

MAX_INPUT_BYTES = 1_000_000
MAX_OUTPUT_BYTES = 2_000_000
MAX_UNITS = 100
MAX_ATTEMPTS = 500
SELECTORS = {
    **{key: ('phases', key, 'tokens' if key.endswith('_tokens') else 'count') for key in run_traces.COUNTS},
    'active_minutes': ('phases', 'active_minutes', 'minutes'),
    'cost': ('phases', 'cost', 'currency'),
    'rounds': ('run', 'rounds', 'count'),
    **{key: ('outcome', key, 'count') for key in run_traces.OUTCOMES},
}


def raw_digest(data):
    return hashlib.sha256(data).hexdigest()


def digest(value):
    return raw_digest(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('utf-8'))


def capture(path):
    """Reuse the bounded reader; pin canonical parsed JSON, not file bytes."""
    value = run_traces.read_input(path)
    return value, digest(value)


def write_output(factory, output, content, inputs, replace=False):
    """Use the existing snapshot writer, refusing every supplied-input alias."""
    if len(content.encode('utf-8')) > MAX_OUTPUT_BYTES:
        raise ValueError('Generated analytics output exceeds limit')
    target = safe_path(os.path.abspath(output))
    for source in inputs:
        original = safe_path(os.path.abspath(source))
        if original == target or (target.exists() and original.samefile(target)):
            raise ValueError('Output cannot replace an input')
    dashboard.write_output(factory, target, content, replace)


def markdown_cell(value):
    """Escape text for a single Learn-table cell, including literal backslashes."""
    return escape(str(value), quote=True).replace('\\', '\\\\').replace('|', '\\|')


def learn_table(cells):
    if len(cells) != len(LEARNING_HEADER) or any('\n' in str(value) or '\r' in str(value) for value in cells):
        raise ValueError('Learn draft needs seven single-line cells')
    body = '# Uncommitted Learn proposal\n\n| '+' | '.join(LEARNING_HEADER)+' |\n'
    body += '|---|---|---|---|---|---|---|\n| '+' | '.join(markdown_cell(value) for value in cells)+' |\n'
    validate_learning_log(body)
    return body


def measurement(trace, selector, currency=None, phase=None):
    """Extract one compatible measure from a validated #132 trace; never fill gaps."""
    if selector not in SELECTORS:
        raise ValueError('Unsupported analytics selector')
    source, field, unit = SELECTORS[selector]
    if source == 'phases':
        values = [row[field] for row in trace['phases'] if phase is None or row['phase'] == phase]
    elif source == 'outcome':
        values = [trace['outcome'][field]]
    else:
        values = [trace[field]]
    result = {'value': None, 'status': 'unavailable', 'unit': unit, 'currency': currency, 'reasons': []}
    if not values or any(value['status'] == 'unavailable' for value in values):
        result['reasons'].append('missing or unavailable metric values')
        return result
    kinds = {value['status'] for value in values}
    if len(kinds) != 1:
        result['reasons'].append('mixed metric statuses within unit')
        return result
    if selector == 'cost' and (currency is None or {value['currency'] for value in values} != {currency}):
        result['reasons'].append('incompatible currency')
        return result
    numbers = [value['value'] for value in values]
    total = sum(numbers) if all(type(number) is int for number in numbers) else math.fsum(numbers)
    if not math.isfinite(total) or not 0 <= total <= run_traces.MAX_NUMBER:
        raise ValueError('Analytics total exceeds limit')
    result.update(value=total, status=next(iter(kinds)))
    return result


NOTICE = ('Private operator-supplied claims; descriptive conditional summaries only. Pins and chronology do not prove '
          'preregistration, randomization, first-attempt identity, completeness, attribution or causality. '
          'Review every field before sharing. No collection, allocation or adoption is performed.')
ESTIMAND = ('Mean among allocated units whose predeclared first attempt is supplied as merged and complete, '
            'with a compatible available metric in the declared cell. Retries are counted but their measures are excluded.')
DISPOSITIONS = ('no_inventory', 'inventory_incomplete', 'first_attempt_missing', 'error', 'out_of_window',
                'open_censored', 'closed', 'pr_state_unavailable', 'merged_incomplete', 'merged_complete',
                'metric_unavailable', 'mixed_status', 'incompatible_currency', 'outside_declared_cell', 'included')
shape = run_traces.shape
label = run_traces.label
timestamp = run_traces.timestamp


def positive(value, maximum=100):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError('Expected bounded positive integer')


def sequence(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError('Invalid bounded list')


def pin(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid canonical digest')


def validate_experiment(value):
    shape(value, ('schema_version', 'experiment_id', 'version', 'created_at', 'timing', 'method', 'population',
                  'assignment_unit', 'assignment_description', 'assignment_evidence_ref', 'variants', 'analysis_attempt',
                  'min_units', 'minimum_rationale', 'stopping_rule', 'confounders', 'allocations', 'metrics', 'learn'))
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported experiment schema')
    for key in ('experiment_id', 'population', 'assignment_description', 'assignment_evidence_ref',
                'minimum_rationale', 'stopping_rule', 'confounders'):
        label(value[key], 500)
    positive(value['version'], 1000000)
    if value['assignment_unit'] != 'task' or value['analysis_attempt'] != 'predeclared_first':
        raise ValueError('Unsupported analysis unit or attempt policy')
    if value['timing'] not in ('prospective_claim', 'retrospective') or value['method'] not in ('observational', 'operator_allocated', 'before_after', 'randomized_claim'):
        raise ValueError('Unsupported claimed design method')
    created = timestamp(value['created_at'])
    positive(value['min_units'])
    if value['min_units'] < 2:
        raise ValueError('Minimum usable units must be at least two')
    sequence(value['variants'], 2, 2)
    windows = []
    variants = set()
    for variant in value['variants']:
        shape(variant, ('id', 'version', 'intervention', 'start', 'end'))
        label(variant['id'], 100); label(variant['intervention'], 500)
        positive(variant['version'], 1000000)
        if variant['id'] in variants:
            raise ValueError('Duplicate variant')
        variants.add(variant['id'])
        start, end = timestamp(variant['start']), timestamp(variant['end'])
        if start >= end or (value['timing'] == 'prospective_claim' and created > start):
            raise ValueError('Contradictory claimed design chronology')
        windows.append((start, end))
    if value['method'] == 'before_after':
        if windows[0][1] > windows[1][0]:
            raise ValueError('Before/after windows must be ordered and disjoint')
    elif windows[0] != windows[1]:
        raise ValueError('Parallel comparison windows must match')
    sequence(value['allocations'], MAX_UNITS, 2)
    identities = {key: set() for key in ('unit_id', 'task_id', 'first_attempt_id')}
    allocated_variants = set()
    for allocation in value['allocations']:
        shape(allocation, ('unit_id', 'task_id', 'variant', 'first_attempt_id'))
        for key in identities:
            label(allocation[key], 100)
            if allocation[key] in identities[key]:
                raise ValueError('Duplicate allocation identity')
            identities[key].add(allocation[key])
        if allocation['variant'] not in variants:
            raise ValueError('Unknown allocated variant')
        allocated_variants.add(allocation['variant'])
    if allocated_variants != variants:
        raise ValueError('Both variants need allocated tasks')
    sequence(value['metrics'], 12, 1)
    metric_ids, definitions = set(), set()
    primary = 0
    for metric in value['metrics']:
        shape(metric, ('id', 'version', 'description', 'selector', 'phase', 'unit', 'role', 'cell', 'threshold'))
        label(metric['id'], 100); label(metric['description'], 500)
        positive(metric['version'], 1000000)
        if metric['id'] in metric_ids or metric['selector'] not in SELECTORS:
            raise ValueError('Duplicate metric or unsupported selector')
        metric_ids.add(metric['id'])
        origin, _, expected_unit = SELECTORS[metric['selector']]
        if metric['unit'] != expected_unit or (origin == 'phases' and metric['phase'] not in run_traces.PHASES) or (origin != 'phases' and metric['phase'] is not None):
            raise ValueError('Metric unit or phase does not match selector')
        shape(metric['cell'], ('status', 'source_label', 'currency'))
        cell = metric['cell']
        if cell['status'] not in run_traces.STATUSES[:-1]:
            raise ValueError('Declared cell needs available status')
        label(cell['source_label'])
        if metric['selector'] == 'cost':
            run_traces.metric({'status': cell['status'], 'value': 0, 'currency': cell['currency']}, cost=True)
        elif cell['currency'] is not None:
            raise ValueError('Non-cost cell cannot declare currency')
        definition = (metric['selector'], metric['phase'], digest(cell))
        if definition in definitions:
            raise ValueError('Duplicate metric definition')
        definitions.add(definition)
        if metric['role'] not in ('primary', 'secondary', 'guardrail'):
            raise ValueError('Invalid metric role')
        primary += metric['role'] == 'primary'
        if metric['role'] == 'guardrail':
            shape(metric['threshold'], ('direction', 'value'))
            if metric['threshold']['direction'] not in ('max_mean', 'min_mean'):
                raise ValueError('Invalid guardrail direction')
            run_traces.metric({'status':'supplied', 'value':metric['threshold']['value']}, integer=False)
        elif metric['threshold'] is not None:
            raise ValueError('Only guardrails have thresholds')
    if primary != 1:
        raise ValueError('Exactly one declared primary metric is required')
    shape(value['learn'], ('hypothesis', 'proposed_change', 'owner'))
    for text in value['learn'].values(): label(text, 500)
    return value


def validate_assignments(value, experiment, rows, as_of):
    shape(value, ('schema_version', 'experiment_digest', 'units'))
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['experiment_digest'] != digest(experiment):
        raise ValueError('Assignments must bind exact canonical experiment')
    sequence(value['units'], MAX_UNITS)
    allocations = {a['unit_id']: a for a in experiment['allocations']}
    first_owners = {a['first_attempt_id']: a['unit_id'] for a in experiment['allocations']}
    units, attempts_seen, runs_seen = {}, set(), set()
    total = 0
    for unit in value['units']:
        shape(unit, ('unit_id', 'inventory_complete', 'attempts'))
        uid = unit['unit_id']
        if uid not in allocations or uid in units or type(unit['inventory_complete']) is not bool:
            raise ValueError('Unknown, duplicate or invalid inventory')
        sequence(unit['attempts'], MAX_ATTEMPTS)
        total += len(unit['attempts'])
        if total > MAX_ATTEMPTS: raise ValueError('Too many attempts')
        ordinals = set()
        for attempt in unit['attempts']:
            shape(attempt, ('attempt_id', 'ordinal', 'run_id', 'subject', 'storage_subject', 'deployed_subject', 'started_at', 'state', 'error_reason'))
            label(attempt['attempt_id'], 100); label(attempt['subject'])
            if attempt['attempt_id'] in first_owners and first_owners[attempt['attempt_id']] != uid:
                raise ValueError('Pinned attempt cannot move between allocated tasks')
            positive(attempt['ordinal'], MAX_ATTEMPTS)
            for key in ('storage_subject', 'deployed_subject'):
                if attempt[key] is not None: label(attempt[key])
            if attempt['attempt_id'] in attempts_seen or attempt['ordinal'] in ordinals:
                raise ValueError('Duplicate attempt mapping')
            attempts_seen.add(attempt['attempt_id']); ordinals.add(attempt['ordinal'])
            started = timestamp(attempt['started_at'])
            if started > as_of: raise ValueError('Future claimed attempt start')
            if attempt['state'] == 'error':
                label(attempt['error_reason'], 500)
                if attempt['run_id'] is not None: raise ValueError('Error inventory cannot bind trace')
            elif attempt['state'] == 'observed':
                label(attempt['run_id'], 100)
                rid = attempt['run_id']
                if rid in runs_seen or rid not in rows or attempt['error_reason'] is not None:
                    raise ValueError('Duplicate, missing or invalid trace mapping')
                runs_seen.add(rid)
                if rows[rid]['subject'] != attempt['subject'] or started > timestamp(rows[rid]['observed_at']):
                    raise ValueError('Contradictory subject or claimed chronology')
            else: raise ValueError('Invalid attempt state')
        if ordinals != set(range(1, len(unit['attempts'])+1)):
            raise ValueError('Attempt ordinals must form contiguous supplied inventory')
        ordered = sorted(unit['attempts'], key=lambda a:a['ordinal'])
        if any(timestamp(a['started_at']) > timestamp(b['started_at']) for a,b in zip(ordered,ordered[1:])):
            raise ValueError('Contradictory attempt ordering')
        first = next((a for a in ordered if a['attempt_id'] == allocations[uid]['first_attempt_id']), None)
        if first is not None and first['ordinal'] != 1:
            raise ValueError('Pinned first attempt must have ordinal one')
        units[uid] = unit
    return units, runs_seen


def first_disposition(allocation, inventory, rows, window):
    if inventory is None: return 'no_inventory', None
    if not inventory['inventory_complete']: return 'inventory_incomplete', None
    first = next((a for a in inventory['attempts'] if a['attempt_id'] == allocation['first_attempt_id']), None)
    if first is None: return 'first_attempt_missing', None
    if first['state'] == 'error': return 'error', None
    if not window[0] <= timestamp(first['started_at']) < window[1]: return 'out_of_window', None
    trace = rows[first['run_id']]
    if trace['pr_state'] == 'open': return 'open_censored', trace
    if trace['pr_state'] == 'closed': return 'closed', trace
    if trace['pr_state'] == 'unavailable': return 'pr_state_unavailable', trace
    if not trace['complete']: return 'merged_incomplete', trace
    return 'merged_complete', trace


def summary(numbers):
    if not numbers: return {'n':0, 'mean':None, 'min':None, 'max':None}
    total = math.fsum(numbers)
    if not math.isfinite(total) or total > run_traces.MAX_NUMBER:
        raise ValueError('Cohort total exceeds limit')
    return {'n':len(numbers), 'mean':total/len(numbers), 'min':min(numbers), 'max':max(numbers)}


def analyze(traces, experiment, assignments, *, experiment_pin, as_of):
    pin(experiment_pin)
    validate_experiment(experiment)
    if digest(experiment) != experiment_pin: raise ValueError('Experiment pin mismatch')
    if timestamp(experiment['created_at']) > as_of: raise ValueError('Future claimed design creation')
    # This reuses validation only. Its freshness and output-token exclusions are unrelated to this estimand.
    rows = {r['run_id']:r for r in run_traces.summarize(traces, now=as_of)['runs']}
    inventories, assigned_runs = validate_assignments(assignments, experiment, rows, as_of)
    variants = experiment['variants']
    limitations = {'descriptive_only', 'supplied_binding_not_verified', 'selection_and_survivorship_bias_possible',
                   'retries_excluded_from_measures', 'minimum_units_is_not_power_analysis', 'phase_coverage_not_attested'}
    if experiment['timing'] == 'retrospective': limitations.add('post_hoc_design')
    if experiment['method'] == 'randomized_claim': limitations.add('randomization_claim_not_verified')
    elif experiment['method'] == 'before_after': limitations.add('time_confounding')
    else: limitations.add('selection_and_confounding_possible')
    if any(as_of < timestamp(v['end']) for v in variants): limitations.add('observation_window_open')
    subjects = Counter(r['subject'] for r in rows.values())
    if any(n > 1 for n in subjects.values()): limitations.add('shared_subject_possible_dependence_not_duplicate_proof')
    metrics = []
    for definition in experiment['metrics']:
        cell, results, model_sets = definition['cell'], [], []
        for variant in variants:
            allocated = [a for a in experiment['allocations'] if a['variant'] == variant['id']]
            counts = {key:0 for key in DISPOSITIONS}
            numbers, secondary, models = [], {}, set()
            retries = later_attempts = 0
            window = (timestamp(variant['start']), timestamp(variant['end']))
            for allocation in allocated:
                inventory = inventories.get(allocation['unit_id'])
                if inventory:
                    later = sum(a['attempt_id'] != allocation['first_attempt_id'] for a in inventory['attempts'])
                    retries += bool(later); later_attempts += later
                disposition, trace = first_disposition(allocation, inventory, rows, window)
                counts[disposition] += 1
                if disposition == 'open_censored' and as_of >= window[1]: limitations.add('censored_open_attempts')
                if disposition != 'merged_complete': continue
                observed = measurement(trace, definition['selector'], cell['currency'], definition['phase'])
                if observed['value'] is None:
                    reason = 'mixed_status' if 'mixed metric statuses within unit' in observed['reasons'] else 'incompatible_currency' if 'incompatible currency' in observed['reasons'] else 'metric_unavailable'
                    counts[reason] += 1
                    continue
                observed_key = (observed['status'], trace['source_label'], observed['currency'])
                if observed_key != (cell['status'], cell['source_label'], cell['currency']):
                    counts['outside_declared_cell'] += 1
                    secondary.setdefault(observed_key, []).append(observed['value'])
                    continue
                numbers.append(observed['value']); counts['included'] += 1
                models.update(p['model'] for p in trace['phases'] if p['phase'] == definition['phase'])
            stats = summary(numbers)
            threshold_state = None
            if definition['role'] == 'guardrail':
                if stats['n'] < experiment['min_units']:
                    limitations.add('guardrail_unavailable_or_insufficient')
                if stats['n'] == 0: threshold_state = 'guardrail_unavailable_or_insufficient'
                else:
                    threshold = definition['threshold']
                    exceeds = stats['mean'] > threshold['value'] if threshold['direction'] == 'max_mean' else stats['mean'] < threshold['value']
                    threshold_state = 'guardrail_threshold_exceeded_observed' if exceeds else 'guardrail_threshold_not_exceeded_observed'
                if threshold_state != 'guardrail_threshold_not_exceeded_observed': limitations.add(threshold_state)
            if stats['n'] < experiment['min_units']: limitations.add('insufficient_evidence')
            results.append({'variant':variant['id'], 'allocated':len(allocated), 'included':stats['n'], 'excluded':len(allocated)-stats['n'],
                            'dispositions':counts, 'units_with_later_attempts':retries, 'later_attempts_excluded':later_attempts,
                            'statistics':stats, 'threshold_state':threshold_state,
                            'secondary_descriptive_cells':[{'status':key[0], 'source_label':key[1], 'currency':key[2],
                                                            'allocated':len(allocated), 'excluded':len(allocated)-len(values),
                                                            **summary(values)} for key,values in sorted(secondary.items())]})
            model_sets.append(models)
        if results[0]['included']*results[1]['allocated'] != results[1]['included']*results[0]['allocated']:
            limitations.add('differential_inclusion')
        if definition['selector'].endswith('_tokens') and model_sets[0] != model_sets[1]: limitations.add('token_definitions_may_differ')
        metrics.append({'definition':definition, 'estimand':ESTIMAND, 'variants':results})
    # Only analytics inputs and derived interpretation are bound; dashboard state and optional decisions are separate.
    result = {'schema_version':1, 'as_of':as_of.isoformat(), 'notice':NOTICE, 'privacy':'private; review before sharing or committing',
              'canonical_input_digests':{'experiment':experiment_pin, 'traces':digest(traces), 'assignments':digest(assignments)},
              'experiment_id':experiment['experiment_id'], 'experiment_version':experiment['version'], 'method_claim':experiment['method'],
              'timing_claim':experiment['timing'], 'population':experiment['population'], 'assignment_unit':'task',
              'variants':variants, 'min_units':experiment['min_units'], 'minimum_rationale':experiment['minimum_rationale'],
              'stopping_rule':experiment['stopping_rule'], 'confounders':experiment['confounders'], 'metrics':metrics,
              'total_supplied_traces':len(rows), 'unassigned_traces_excluded':len(set(rows)-assigned_runs),
              'observation_age_seconds':{'oldest':max(((as_of-timestamp(r['observed_at'])).total_seconds() for r in rows.values()),default=None)},
              'limitations':sorted(limitations)}
    return {**result, 'analysis_digest':digest(result)}


def validate_decision(value, result):
    shape(value, ('schema_version', 'analysis_digest', 'decided_at', 'decision', 'owner', 'rationale'))
    if type(value['schema_version']) is not int or value['schema_version'] != 1 or value['analysis_digest'] != result['analysis_digest']:
        raise ValueError('Decision must bind exact analysis')
    if value['decision'] not in ('keep', 'revise', 'reject', 'inconclusive'):
        raise ValueError('Invalid supplied decision')
    label(value['owner'], 200); label(value['rationale'], 500)
    if timestamp(value['decided_at']) < timestamp(result['as_of']): raise ValueError('Decision predates analysis as-of')
    return {**value, 'status':'operator supplied; not adopted or verified; analysis limitations unchanged'}


def learn_proposal(result, experiment, decision=None):
    primary = next(m for m in result['metrics'] if m['definition']['role']=='primary')
    counts = ', '.join('variant-'+str(i+1)+' '+str(v['included'])+'/'+str(v['allocated']) for i,v in enumerate(primary['variants']))
    evidence = 'Private analysis SHA256 '+result['analysis_digest']+'; design SHA256 '+result['canonical_input_digests']['experiment']+'; primary-cell '+counts
    approval = 'Pending explicit operator decision; no adoption' if decision is None else 'Supplied decision '+decision['decision']+'; no adoption'
    approval += '; limitations: '+', '.join(result['limitations'])
    text = learn_table([result['as_of'], evidence, experiment['learn']['hypothesis'], experiment['learn']['proposed_change'],
                        experiment['learn']['owner'], 'Declared primary-cell; '+primary['definition']['unit']+'; minimum '+str(result['min_units'])+' per variant', approval])
    return text.replace('# Uncommitted Learn proposal', '# Uncommitted Learn proposal — review all text before committing', 1)


def panel(result, decision=None):
    def text(value): return escape(str(value), quote=True)
    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+text(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+text(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    body = '<section class="panel"><h2>Private supplied experiment analysis</h2><p>'+text(result['notice'])+'</p>'
    body += '<p>Analysis SHA256 '+text(result['analysis_digest'])+'; as of '+text(result['as_of'])+'. The separate factory overview is outside this digest.</p>'
    body += '<p>'+text(result['experiment_id'])+' version '+text(result['experiment_version'])+'; '+text(result['method_claim'])+'; '+text(result['timing_claim'])+'.</p>'
    body += '<p>Canonical design SHA256 '+text(result['canonical_input_digests']['experiment'])+'; population '+text(result['population'])+'; assignment unit task.</p>'
    body += table(('Variant','Definition version','Intervention claim','Start inclusive','End exclusive'),
                  [(v['id'],v['version'],v['intervention'],v['start'],v['end']) for v in result['variants']])
    body += '<p>Minimum usable units per variant: '+str(result['min_units'])+'. Rationale: '+text(result['minimum_rationale'])+'. Supplied stopping rule: '+text(result['stopping_rule'])+'. Confounders: '+text(result['confounders'])+'.</p>'
    body += '<p>Limitations: '+text(', '.join(result['limitations']))+'</p>'
    body += '<p>Unassigned supplied traces excluded: '+str(result['unassigned_traces_excluded'])+'. Observation age is context only, never an eligibility rule.</p>'
    for metric in result['metrics']:
        definition = metric['definition']
        body += '<h3>'+text(definition['id'])+' ('+text(definition['role'])+')</h3><p>'+text(metric['estimand'])+'</p>'
        body += '<p>Declared cell: '+text(json.dumps(definition['cell'],sort_keys=True))+'; selector '+text(definition['selector'])+'; phase '+text(definition['phase'])+'; unit '+text(definition['unit'])+'.</p>'
        if definition['threshold'] is not None: body += '<p>Declared guardrail: '+text(json.dumps(definition['threshold'],sort_keys=True))+'. An observed comparison does not clear sample insufficiency.</p>'
        if definition['selector']=='active_minutes': body += '<p>Sum of supplied phase/model active minutes, not elapsed time.</p>'
        body += table(('Variant','Included / allocated','Excluded','Mean','Min','Max','Units with later attempts / allocated','Later attempts excluded','Guardrail observation'),
                      [(v['variant'],str(v['included'])+'/'+str(v['allocated']),v['excluded'], *('unavailable' if v['statistics'][key] is None else v['statistics'][key] for key in ('mean','min','max')),
                        str(v['units_with_later_attempts'])+'/'+str(v['allocated']),v['later_attempts_excluded'],v['threshold_state'] or 'not applicable') for v in metric['variants']])
        body += '<p>First-attempt dispositions partition allocated units through merged_complete; metric categories then partition that subset.</p>'
        body += table(('Disposition / metric eligibility', *(v['variant'] for v in metric['variants'])), [(key, *(v['dispositions'][key] for v in metric['variants'])) for key in DISPOSITIONS])
        for variant in metric['variants']:
            body += '<p>Secondary descriptive cells for '+text(variant['variant'])+' (never substitute for the declared cell): '+text(json.dumps(variant['secondary_descriptive_cells'],sort_keys=True))+'</p>'
    if decision: body += '<h3>Supplied decision; no adoption</h3><p>'+text(json.dumps(decision,sort_keys=True))+'</p>'
    return body+'</section>'


def distinct_inputs(paths):
    resolved = [safe_path(os.path.abspath(path)) for path in paths]
    for index, left in enumerate(resolved):
        for right in resolved[index+1:]:
            if left == right or left.samefile(right): raise ValueError('Inputs must be distinct files')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--experiment', required=True)
    parser.add_argument('--trace')
    parser.add_argument('--assignments')
    parser.add_argument('--experiment-pin')
    parser.add_argument('--as-of')
    parser.add_argument('--decision')
    parser.add_argument('--definition-only', action='store_true')
    parser.add_argument('--format', choices=('json','html','learn'), default='json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    inputs = [args.experiment]+[p for p in (args.trace,args.assignments,args.decision) if p]
    distinct_inputs(inputs)
    experiment, experiment_digest = capture(args.experiment)
    validate_experiment(experiment)
    if args.definition_only:
        if any((args.trace,args.assignments,args.decision,args.experiment_pin,args.as_of)) or args.format != 'json':
            raise ValueError('Definition-only accepts just experiment and JSON output')
        definition = {k:v for k,v in experiment.items() if k != 'assignment_evidence_ref'}
        content = json.dumps({'schema_version':1,'canonical_experiment_digest':experiment_digest,'definition':definition,'notice':NOTICE},indent=2,ensure_ascii=True)+'\n'
    else:
        if not all((args.trace,args.assignments,args.experiment_pin,args.as_of)): raise ValueError('Analysis needs all explicit inputs and as-of')
        traces, _ = capture(args.trace)
        assignments, _ = capture(args.assignments)
        now = timestamp(args.as_of)
        result = analyze(traces,experiment,assignments,experiment_pin=args.experiment_pin,as_of=now)
        decision = validate_decision(capture(args.decision)[0],result) if args.decision else None
        if args.format == 'learn': content = learn_proposal(result,experiment,decision)
        elif args.format == 'html': content = dashboard.page(dashboard.read(args.factory,now=now),supplemental_html=panel(result,decision))
        else: content = json.dumps({'analysis':result,'supplied_decision':decision},indent=2,ensure_ascii=True)+'\n'
    write_output(args.factory,args.output,content,inputs,args.replace)
    print('Private supplied analytics output written. No collection, allocation or adoption performed.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,TypeError,UnicodeError,OverflowError,RecursionError):
        print('ERROR: Private analytics unavailable; input/schema, identity, chronology or output checks failed. No live actions performed.',file=sys.stderr)
        sys.exit(1)
