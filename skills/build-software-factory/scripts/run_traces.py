"""Read explicitly supplied private run traces; no harness discovery or live queries."""
import sys
sys.dont_write_bytecode = True
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
import json
import math
import os
from pathlib import Path
import stat
from integrity import safe_path, strict_json
import dashboard

MAX_BYTES = 1_000_000
MAX_RUNS = 100
MAX_PHASES = 64
MAX_NUMBER = 10**12
STATUSES = ('measured', 'supplied', 'estimated', 'unavailable')
PHASES = ('intake', 'plan', 'build', 'verify', 'release', 'learn', 'run', 'review')
COUNTS = ('sessions', 'human_turns', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens')
OUTCOMES = ('files_changed', 'lines_added', 'lines_removed', 'commits_after_handoff', 'human_review_comments', 'failed_checks')
RUN_FIELDS = {'run_id', 'subject', 'observed_at', 'source_label', 'evidence_ref', 'complete', 'pr_state',
              'risk', 'rounds', 'verdict', 'phases', 'outcome'}
NOTICE = ('Private supplied claims, not independently verified measurements, attribution, merge state or review verdicts. '
          'Freshness is age only. Counts do not establish missed fixes, quality, causality or permission to publish.')


def shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Invalid run trace fields')


def label(value, limit=200):
    if not isinstance(value, str) or not 1 <= len(value) <= limit or value != value.strip() or not value.isprintable():
        raise ValueError('Invalid run trace text')
    return value


def timestamp(value):
    label(value, 50)
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Run trace time requires timezone')
    return parsed


def metric(value, *, integer=True, cost=False):
    shape(value, ('status', 'value', 'currency') if cost else ('status', 'value'))
    status = value['status']
    if status not in STATUSES:
        raise ValueError('Invalid run trace metric status')
    number = value['value']
    if status == 'unavailable':
        if number is not None:
            raise ValueError('Unavailable metric must be null')
    elif (type(number) not in (int, float) or not math.isfinite(number) or not 0 <= number <= MAX_NUMBER
          or (integer and type(number) is not int)):
        raise ValueError('Run trace metric needs a bounded nonnegative number')
    if cost:
        currency = value['currency']
        if status == 'unavailable':
            if currency is not None:
                raise ValueError('Unavailable cost currency must be null')
        elif not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or currency != currency.upper():
            raise ValueError('Cost needs an explicit three-letter currency')
    return dict(value)


def summarize(value, *, now=None, stale_after_minutes=1440):
    """Validate typed claims and derive narrowly labeled output-token cohorts."""
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('As-of time requires timezone')
    if type(stale_after_minutes) is not int or not 1 <= stale_after_minutes <= 43200:
        raise ValueError('Invalid run trace freshness window')
    shape(value, ('schema_version', 'runs'))
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported run trace schema')
    if not isinstance(value['runs'], list) or len(value['runs']) > MAX_RUNS:
        raise ValueError('Too many run traces')
    rows = []
    seen = set()
    exclusions = Counter()
    cohorts = {status: [] for status in STATUSES if status != 'unavailable'}
    for item in value['runs']:
        shape(item, RUN_FIELDS)
        run_id = label(item['run_id'], 100)
        if run_id in seen:
            raise ValueError('Duplicate run identity; one subject per run is required')
        seen.add(run_id)
        subject = label(item['subject'])
        observed = timestamp(item['observed_at'])
        if observed > now:
            raise ValueError('Future run trace observation')
        source = label(item['source_label'])
        label(item['evidence_ref'], 500)  # Private reference is validated but never exported or dereferenced.
        if type(item['complete']) is not bool or item['pr_state'] not in ('open', 'merged', 'closed', 'unavailable'):
            raise ValueError('Invalid supplied completion or PR state')
        if item['risk'] not in ('low', 'medium', 'high', 'unavailable') or item['verdict'] not in ('approve', 'request_changes', 'blocked', 'waived', 'unavailable'):
            raise ValueError('Invalid supplied risk or verdict')
        rounds = metric(item['rounds'])
        if not isinstance(item['phases'], list) or len(item['phases']) > MAX_PHASES:
            raise ValueError('Too many phase traces')
        phases = []
        pairs = set()
        for phase in item['phases']:
            shape(phase, set(COUNTS) | {'phase', 'model', 'active_minutes', 'cost'})
            if phase['phase'] not in PHASES:
                raise ValueError('Invalid run trace phase')
            model = label(phase['model'], 100)
            pair = (phase['phase'], model)
            if pair in pairs:
                raise ValueError('Duplicate phase/model attribution')
            pairs.add(pair)
            phases.append({'phase': phase['phase'], 'model': model,
                           **{key: metric(phase[key]) for key in COUNTS},
                           'active_minutes': metric(phase['active_minutes'], integer=False),
                           'cost': metric(phase['cost'], integer=False, cost=True)})
        shape(item['outcome'], OUTCOMES)
        outcome = {key: metric(item['outcome'][key]) for key in OUTCOMES}
        fresh = now - observed <= timedelta(minutes=stale_after_minutes)
        output = [p['output_tokens'] for p in phases]
        available = bool(output) and all(m['status'] != 'unavailable' for m in output)
        total = sum(m['value'] for m in output) if available else None
        if total is not None and total > MAX_NUMBER:
            raise ValueError('Run output-token total exceeds limit')
        kinds = {m['status'] for m in output}
        output_status = next(iter(kinds)) if available and len(kinds) == 1 else 'mixed' if available else 'unavailable'
        reasons = []
        if item['pr_state'] != 'merged': reasons.append('PR not supplied as merged')
        if not item['complete']: reasons.append('trace supplied as incomplete')
        if not fresh: reasons.append('stale observation')
        if not available: reasons.append('missing or unavailable phase output tokens')
        elif output_status == 'mixed': reasons.append('mixed output-token statuses')
        exclusions.update(reasons)
        if not reasons:
            cohorts[output_status].append(total)
        rows.append({'run_id': run_id, 'subject': subject, 'observed_at': item['observed_at'],
                     'source_label': source, 'provenance': 'supplied; private evidence reference withheld',
                     'complete': item['complete'], 'pr_state': item['pr_state'], 'risk': item['risk'],
                     'rounds': rounds, 'verdict': item['verdict'], 'phases': phases, 'outcome': outcome,
                     'freshness': 'recent' if fresh else 'stale', 'output_tokens': {'status': output_status, 'value': total},
                     'average_exclusions': reasons})
    averages = []
    for status, numbers in cohorts.items():
        averages.append({'status': status, 'included_count': len(numbers), 'excluded_count': len(rows)-len(numbers),
                         'mean_output_tokens': sum(numbers)/len(numbers) if numbers else None})
    return {'schema_version': 1, 'as_of': now.isoformat(), 'stale_after_minutes': stale_after_minutes,
            'privacy': 'private; review all fields before sharing or committing', 'notice': NOTICE,
            'runs': rows, 'averages': averages, 'total_supplied_runs': len(rows),
            'excluded_runs': sum(bool(r['average_exclusions']) for r in rows), 'exclusion_reasons': dict(exclusions),
            'average_basis': 'Supplied merged, complete, recent run claims; all phase output values available with one status. '
                             'Each cohort excludes other statuses. Reasons may overlap. No costs or currencies are pooled.'}


def read_input(path):
    """Bounded explicit regular-file read; never scan stores or follow redirects."""
    source = safe_path(os.path.abspath(path))
    if str(source).replace('/', '\\').startswith('\\\\'):
        raise ValueError('Only explicit local trace files are supported')
    before = source.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError('Run trace input must be a bounded regular file')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(source, flags), 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('Trace input changed')
        data = stream.read(MAX_BYTES+1)
        after = os.fstat(stream.fileno())
    current = safe_path(source).stat()
    # Windows path-stat and descriptor-stat can expose different ctime meanings.
    # Compare ctime only within the same API, retaining shared identity/content
    # metadata checks across both APIs and every observation.
    signature = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns)
    if (len(data) > MAX_BYTES or len({signature(s) for s in (before,opened,after,current)}) != 1
            or before.st_ctime_ns != current.st_ctime_ns or opened.st_ctime_ns != after.st_ctime_ns):
        raise ValueError('Trace input changed or exceeds limit')
    return strict_json(data.decode('utf-8-sig'))


def display_metric(value):
    if value['value'] is None:
        return 'unavailable'
    return str(value['value']) + (' '+value['currency'] if value.get('currency') else '') + ' ('+value['status']+')'


def panel(data):
    """Trusted renderer: every supplied field is escaped; no supplied HTML accepted."""
    text = lambda value: escape(str(value), quote=True)
    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+text(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+text(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    body = '<section class="panel"><h2>Supplied private run traces</h2><p>'+text(data['notice'])+'</p>'
    body += '<p>'+text(data['privacy'])+'. As of '+text(data['as_of'])+'. Evidence references are withheld.</p>'
    body += table(('Run', 'Subject', 'Supplied PR state', 'Supplied completeness', 'Risk', 'Rounds', 'Verdict claim', 'Freshness', 'Output tokens', 'Average exclusions'),
                  [(r['run_id'], r['subject'], 'in progress (open)' if r['pr_state']=='open' else r['pr_state'], 'complete' if r['complete'] else 'incomplete',
                    r['risk'], display_metric(r['rounds']), r['verdict'], r['freshness'], display_metric(r['output_tokens']), '; '.join(r['average_exclusions']) or 'eligible within status cohort') for r in data['runs']])
    for run in data['runs']:
        body += '<h3>'+text(run['run_id'])+' — output tokens by phase</h3>'
        total = run['output_tokens']['value']
        if total is None:
            body += '<p>Stack unavailable: at least one phase output value is missing or unavailable.</p>'
        elif total == 0:
            body += '<p>Supplied phase output-token values total zero.</p>'
        else:
            colors = ('#2864b4', '#8b4bac', '#277d66', '#9b6426', '#b34150', '#466177', '#6a6c21', '#713e61')
            body += '<div style="display:flex;min-height:28px" role="img" aria-label="Supplied output tokens by phase; exact values and statuses in the table below">'
            for phase in run['phases']:
                amount = phase['output_tokens']['value']
                body += '<span style="display:block;background:'+colors[PHASES.index(phase['phase'])]+';width:'+str(100*amount/total)+'%" title="'+text(phase['phase']+' / '+phase['model']+': '+display_metric(phase['output_tokens']))+'"></span>'
            body += '</div>'
        fields = ('sessions', 'active_minutes', 'human_turns', 'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens', 'cost')
        body += table(('Phase', 'Model')+fields, [(p['phase'], p['model'])+tuple(display_metric(p[k]) for k in fields) for p in run['phases']])
        body += table(('Supplied outcome metric', 'Value'), [(k, display_metric(run['outcome'][k])) for k in OUTCOMES])
        body += '<p>Supplied provenance: '+text(run['source_label'])+'; observed '+text(run['observed_at'])+'. Counts are not evidence of missed fixes or causality.</p>'
    body += '<h3>Output-token averages by declared status</h3><p>'+text(data['average_basis'])+'</p>'
    body += table(('Status cohort', 'Included supplied runs', 'Excluded supplied runs', 'Mean output tokens'),
                  [(a['status'], a['included_count'], a['excluded_count'], 'unavailable' if a['mean_output_tokens'] is None else a['mean_output_tokens']) for a in data['averages']])
    body += '<p>Total supplied runs: '+str(data['total_supplied_runs'])+'; excluded from every cohort: '+str(data['excluded_runs'])+'.</p>'
    body += table(('Exclusion reason (overlap possible)', 'Supplied run count'), list(data['exclusion_reasons'].items()))
    return body+'</section>'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory', required=True)
    parser.add_argument('--trace', required=True, help='Explicit approved sanitized private JSON; no store discovery')
    parser.add_argument('--output', required=True)
    parser.add_argument('--format', choices=('html', 'json'), default='html')
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--as-of', help='Explicit aware ISO timestamp for deterministic freshness')
    parser.add_argument('--stale-after-minutes', type=int, default=1440)
    args = parser.parse_args()
    source = safe_path(os.path.abspath(args.trace))
    output = safe_path(os.path.abspath(args.output))
    if source == output or (output.exists() and source.samefile(output)):
        raise ValueError('Trace input cannot be the output')
    now = timestamp(args.as_of) if args.as_of else datetime.now(timezone.utc)
    traces = summarize(read_input(source), now=now, stale_after_minutes=args.stale_after_minutes)
    overview = dashboard.read(args.factory, now=now)
    overview['supplied_run_traces'] = traces
    content = dashboard.page(overview, supplemental_html=panel(traces)) if args.format == 'html' else json.dumps(overview, indent=2, ensure_ascii=True)+'\n'
    dashboard.write_output(args.factory, output, content, args.replace)
    print('Private trace overview written; supplied claims only. No stores, hooks, providers or PR services were queried.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, UnicodeError, OverflowError, RecursionError):
        print('ERROR: Private run trace overview unavailable; input/schema, factory integrity or output checks failed. No live actions performed.', file=sys.stderr)
        sys.exit(1)
