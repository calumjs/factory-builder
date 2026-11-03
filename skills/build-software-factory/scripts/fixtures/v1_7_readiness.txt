"""Advisory design diagnostics only. No probe, scheduling or permission inference."""
import json
import re
from operations import operations, unresolved
from assumptions import summary
from recipes import intake_design


def watcher(config):
    ops=operations(config);intake=ops['issue_intake']
    if intake['mode']!='continuous':
        return {'state':'one_shot','liveness':'unverified','scheduler_authority':'unverified','diagnostics':[]}
    notices=[]
    disabled=intake['status'].strip().casefold()=='disabled'
    if disabled:notices.append('Configured disabled: do not start a watcher from this design.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',intake['github_scope'].strip()):
        notices.append('Repository scope lacks a concrete owner/repository design; verify exact authorized scope.')
    a=ops['autonomy'];budget=config['budget']
    if a['mode']!='bounded':notices.append('Autonomy is manual; continuous pickup needs reviewed bounded controls before live use.')
    if not a['allowed_submitters']:notices.append('No permitted submitters are recorded.')
    if a['max_items_per_hour']<=0:notices.append('No positive intake rate bound is recorded.')
    if budget['max_workers']<=0:notices.append('No positive worker concurrency bound is recorded.')
    if budget['max_minutes']<=0:notices.append('No positive task time bound is recorded.')
    design=intake_design(intake)
    if design['mechanism']=='unconfirmed':notices.append('Event/polling mechanism is unconfirmed; 24/7 intent does not wire a schedule.')
    cadence=' '.join(design['cadence'].casefold().split())
    if design['mechanism']=='polling' and (unresolved(design['cadence']) or cadence.startswith(('unconfirmed','unknown','tbd'))):
        notices.append('Polling cadence is unresolved; fit it to actual platform limits and budget.')
    notices.append('Scheduler authority, kill-switch wiring, authentication and actual watcher liveness are unverified by metadata; check applicable authority and observed runtime before live use. Do not start/change a watcher from this report.')
    return {'state':'disabled_design' if disabled else 'incomplete_design' if len(notices)>1 else 'configured_unverified',
            'liveness':'unverified','scheduler_authority':'unverified','diagnostics':notices}


def report(config):
    return {'watcher':watcher(config),'assumptions':summary(config)}


def emit(config):
    result=report(config)
    for message in result['watcher']['diagnostics']:print('ADVISORY: '+message)
    if result['assumptions']:
        print('RECORDED ASSUMPTIONS (claims only; no sources executed): '+json.dumps(result['assumptions'],sort_keys=True))
    return result
