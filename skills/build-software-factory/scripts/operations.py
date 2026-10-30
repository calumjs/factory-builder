"""Validate proposed operational metadata; never probe or enable a provider."""
import copy

def operations(config):
    defaults = {
        'identities': [], 'tool_recipes': [],
        'autonomy': {'mode':'manual','kill_switch':'Human stop request; stop scheduling and cancel pending work safely',
                     'max_items_per_hour':0,'allowed_submitters':[],'rejected_items':'Record reason and stop; do not retry without a new authorized decision'},
        'review': {'required_approvals':0,'independent':False,'distinct_providers':False},
        'visual_checks': {'required':False,'reference':'Unconfirmed or not applicable','method':'Rendered comparison and human review when relevant'},
        'issue_intake': {'mode':'one_shot','github_scope':'Not applicable until continuous pickup is chosen','status':'disabled','evidence':'No preference recorded; factory runs only on explicit kickoff'},
        'done_videos': {'enabled':False,'scope':'Not configured','evidence':'No preference recorded'},
        'smoke_gates': {'required':True,
                        'pre_merge':'unconfirmed: prepare a production-equivalent artifact and exercise a representative critical path with expected success and failure outcomes',
                        'targeted':'Smallest suite covering the changed paths/behaviour, chosen per change',
                        'post_merge':'unconfirmed: confirm the merged revision on the actual deployed, installed or published target',
                        'deployed_url':'unconfirmed',
                        'exception':'none', 'target_kind':'unconfirmed',
                        'post_merge_applicability':'applicable',
                        'post_merge_rationale':'No exclusion recorded', 'accepted_by':'unconfirmed', 'check_stages':{}}
    }
    supplied = config.get('operations',{})
    if not isinstance(supplied,dict) or not set(supplied) <= set(defaults):
        raise ValueError('Unknown operations field')
    result = copy.deepcopy(defaults)
    for key,value in supplied.items():
        if isinstance(defaults[key],dict):
            if not isinstance(value,dict) or not set(value) <= set(defaults[key]):
                raise ValueError('Invalid operations section: ' + key)
            result[key].update(value)
        else:
            result[key] = value
    for key,fields in (
        ('identities', {'provider','account','scope','git_author','status','evidence'}),
        ('tool_recipes', {'provider','headless_command','structured_output','tool_restrictions','auth_probe','auth_status','auth_evidence'})
    ):
        if not isinstance(result[key],list):
            raise ValueError(key + ' must be a list')
        for item in result[key]:
            if not isinstance(item,dict) or set(item) != fields or any(not isinstance(v,str) or not v.strip() for v in item.values()):
                raise ValueError('Invalid ' + key + ' record; see intake reference')
    a = result['autonomy']
    if a['mode'] not in ('manual','bounded') or type(a['max_items_per_hour']) is not int or a['max_items_per_hour'] < 0:
        raise ValueError('Invalid autonomy mode or rate limit')
    if not isinstance(a['allowed_submitters'],list) or any(not isinstance(v,str) or not v.strip() for v in a['allowed_submitters']):
        raise ValueError('Autonomy allowed_submitters must be a string list')
    if any(not isinstance(a[k],str) or not a[k].strip() for k in ('kill_switch','rejected_items')):
        raise ValueError('Autonomy stopping and rejection behavior are required')
    if a['mode'] == 'bounded' and (not a['allowed_submitters'] or a['max_items_per_hour'] == 0):
        raise ValueError('Bounded autonomy requires named submitters and a positive rate limit')
    r = result['review']
    if type(r['required_approvals']) is not int or r['required_approvals'] < 0 or any(type(r[k]) is not bool for k in ('independent','distinct_providers')):
        raise ValueError('Invalid review policy')
    v = result['visual_checks']
    if type(v['required']) is not bool or any(not isinstance(v[k],str) or not v[k].strip() for k in ('reference','method')):
        raise ValueError('Invalid visual-check policy')
    i = result['issue_intake']
    if i['mode'] not in ('one_shot','continuous') or any(not isinstance(i[k],str) or not i[k].strip() for k in ('github_scope','status','evidence')):
        raise ValueError('Invalid issue intake policy')
    d = result['done_videos']
    if type(d['enabled']) is not bool or any(not isinstance(d[k],str) or not d[k].strip() for k in ('scope','evidence')):
        raise ValueError('Invalid done-video policy')
    s = result['smoke_gates']
    if type(s['required']) is not bool or any(not isinstance(s[k],str) or not s[k].strip() for k in ('pre_merge','targeted','post_merge','deployed_url','exception','target_kind','post_merge_applicability','post_merge_rationale','accepted_by')):
        raise ValueError('Invalid smoke-gate policy')
    if not s['required']:
        raise ValueError('G1/G2 cannot be disabled wholesale; adapt smoke and targeted checks to the project')
    if s['target_kind'] not in ('unconfirmed','web','artifact','no_release') or s['post_merge_applicability'] not in ('applicable','not_applicable'):
        raise ValueError('Invalid delivery target or applicability')
    if s['post_merge_applicability'] == 'not_applicable':
        if s['target_kind'] != 'no_release' or s['post_merge_rationale'] == 'No exclusion recorded' or s['accepted_by'].lower() in ('none','unconfirmed','unknown'):
            raise ValueError('Post-merge not-applicable requires no-release scope, rationale and named acceptance')
        if d['enabled']:
            raise ValueError('Enabled shipped-work videos conflict with a no-release/not-applicable scope')
    if not isinstance(s['check_stages'],dict):
        raise ValueError('check_stages must map acceptance/research IDs to stage and rationale')
    for key,value in s['check_stages'].items():
        if not isinstance(key,str) or len(key)<2 or key[0] not in 'AR' or not key[1:].isdigit() or not isinstance(value,dict) or set(value)!={'stage','rationale'} or value['stage'] not in ('pre-merge','post-merge') or not isinstance(value['rationale'],str) or not value['rationale'].strip():
            raise ValueError('Invalid additional-check stage/rationale')
    return result

def controls(config):
    ops = operations(config)
    return dict({'concurrency':config['budget']['max_workers']}, **{k:ops[k] for k in ('autonomy','review','visual_checks','issue_intake','done_videos','smoke_gates')})

DELIVERY_POLICY = '''## Default delivery gates
G1 production-equivalent local smoke and G2 change-targeted tests, plus every required acceptance/research check, must pass for the exact pre-merge revision before a merge recommendation or release-ready handoff. A blocked diagnostic handoff may always be prepared. NOT RUN, BLOCKED, FAILED, missing or stale evidence is not ready. Build/hash/lint success alone is not application verification.

G3 confirms the actual post-merge/deploy/install/publish target and merged revision after the separately authorized action. Pending G3 does not block pre-release readiness, but the outcome remains UNCONFIRMED until applicable post-release checks pass. Failure or inability to run must be reported to the release owner/orchestrator with evidence and a rollback/diagnosis decision; no silent success. A no-release G3 exclusion needs explicit rationale and named acceptance in operations; an unknown target stays blocked, not not-applicable.

When done videos are enabled, Verify prepares a scoped recording handoff; Release runs G3 first, then records the authorized narrated demo and artifact as V1. A blocked video is reported explicitly, never fabricated. Video recording/publication, merge, deployment and scheduling need their own authority. All gate records are operator-supplied evidence, not independently executed or attested by the helper.
'''
