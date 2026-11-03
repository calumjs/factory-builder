"""Validate proposed operational metadata; never probe or enable a provider."""
import copy
import json
import re
from urllib.parse import urlsplit
from recipes import INTAKE_FIELDS, VIDEO_FIELDS, intake_design, video_design

SMOKE_FIELDS = frozenset(('checks',))
REVIEW_FIELDS = frozenset(('record_schema',))


def smoke_checks(smoke):
    """Validate optional argv/environment/target plans; never execute or read env."""
    checks=smoke.get('checks',{})
    if not isinstance(checks,dict) or not set(checks)<= {'G1','G2','G3'}:
        raise ValueError('smoke_gates.checks maps only G1/G2/G3 to structured recipes')
    def label(value):
        return isinstance(value,str) and bool(value) and value==value.strip() and len(value)<=2000 and value.isprintable() and '|' not in value
    for gate,spec in checks.items():
        if not isinstance(spec,dict) or set(spec)!={'command','environment','env_names','target'}:
            raise ValueError('Structured smoke recipe requires command, environment, env_names and target')
        argv=spec['command']
        if not isinstance(argv,list) or not 1<=len(argv)<=64 or any(not isinstance(v,str) or not v.strip() or len(v)>2000 or any(ord(c)<32 for c in v) for v in argv):
            raise ValueError('Smoke command must be bounded nonempty argv, not a shell string')
        if not label(spec['environment']):raise ValueError('Smoke environment must be a single-line non-secret label')
        env=spec['env_names']
        if not isinstance(env,list) or len(env)>64 or any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',v) for v in env) or len(set(env))!=len(env):
            raise ValueError('Smoke env_names must be unique variable names, never values')
        target=spec['target']
        if not isinstance(target,dict) or set(target)!={'kind','value','base_url_env'} or target['kind'] not in ('web','artifact') or not label(target['value']):
            raise ValueError('Smoke target requires web/artifact kind, value and base_url_env')
        if target['base_url_env'] is not None and (target['kind']!='web' or target['base_url_env'] not in env):
            raise ValueError('base_url_env must be null or a declared web target environment name')
        if target['kind']=='web':
            url=urlsplit(target['value'])
            port=url.port  # Validate an explicitly supplied port; never connect to it.
            if url.scheme not in ('http','https') or not url.hostname or any(c.isspace() for c in url.netloc) or url.username is not None or url.password is not None or url.query or url.fragment:
                raise ValueError('Web smoke target must be an HTTP(S) base URL without credentials, query or fragment')
        if gate=='G3':
            if smoke['target_kind']=='no_release' or smoke['post_merge_applicability']=='not_applicable':
                raise ValueError('A G3 command conflicts with an explicit no-release exclusion')
            if smoke['target_kind']!='unconfirmed' and smoke['target_kind']!=target['kind']:
                raise ValueError('Structured G3 target kind disagrees with smoke target_kind')
            if not unresolved(smoke['deployed_url']) and smoke['deployed_url']!=target['value']:
                raise ValueError('Structured G3 target disagrees with deployed_url')
    return checks


def smoke_design(spec):
    # JSON argv stays data; escape Markdown delimiters rather than changing argv.
    return ('argv='+json.dumps(spec['command'],ensure_ascii=True).replace('|','\\u007c')+
            '; env names='+json.dumps(spec['env_names'])+
            '; base_url_env='+json.dumps(spec['target']['base_url_env']))

def unresolved(value):
    if not isinstance(value,str):return True
    normalized=' '.join(value.casefold().strip().split()).rstrip(' .:')
    return normalized in ('','none','unconfirmed','unknown','tbd','to be determined','not configured','not set','pending','n/a','not applicable') or normalized.startswith(('unknown:','unconfirmed:','tbd:','not configured:'))

def unknown_fields(keys):
    """Bound and escape unknown field names; never include supplied values."""
    names=sorted(str(key) for key in keys)
    shown=[name if len(name)<=80 else name[:80]+'...' for name in names[:10]]
    if len(names)>10:shown.append('... '+str(len(names)-10)+' more fields')
    return json.dumps(shown,ensure_ascii=True)


def admission_policy(value, autonomy, intake, currency):
    """Validate recorded admission design inline; copied runtimes need no new module."""
    fields={'version','status','repository','identity','starts','max_in_flight_items',
            'completion','costs','snapshot_max_age_seconds'}
    if not isinstance(value,dict) or set(value)!=fields or type(value['version']) is not int or value['version']!=1 or value['status'] not in ('draft','specified'):
        raise ValueError('Admission must match the version-1 recorded policy schema')
    specified=value['status']=='specified'
    if specified and any(value[key] is None for key in fields):
        raise ValueError('Specified admission requires every explicit policy choice')
    def integer(item,minimum,maximum):
        return type(item) is int and minimum<=item<=maximum
    def money(item):
        return isinstance(item,str) and re.fullmatch(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?',item) is not None
    def window(item,kinds,amount=False):
        if not isinstance(item,dict) or set(item)!={'maximum','window','timezone'}:
            return False
        return ((money(item['maximum']) if amount else integer(item['maximum'],0,1000000))
                and item['window'] in kinds and isinstance(item['timezone'],str)
                and re.fullmatch(r'[A-Za-z0-9_+\-/]{1,100}',item['timezone']) is not None
                and not any(part in ('','.','..') for part in item['timezone'].split('/')))
    repository=value['repository']
    if repository is not None and (not isinstance(repository,str) or len(repository)>200 or re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository) is None or repository!=intake['github_scope']):
        raise ValueError('Admission repository must match the explicit intake repository')
    identity=value['identity']
    if identity is not None:
        if not isinstance(identity,dict):raise ValueError('Invalid admission identity rule')
        kind=identity.get('kind')
        if kind=='legacy_submitters':
            if set(identity)!={'kind'} or (specified and not autonomy['allowed_submitters']):
                raise ValueError('Legacy admission identity needs the named submitter list')
        elif kind=='label_actor_accounts':
            accounts=identity.get('accounts')
            if set(identity)!={'kind','accounts'} or not isinstance(accounts,list) or not 1<=len(accounts)<=100 or any(not isinstance(v,str) or re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',v) is None for v in accounts) or len(set(accounts))!=len(accounts):
                raise ValueError('Admission actor accounts must be a bounded unique account list')
        elif kind=='label_actor_capability':
            if set(identity)!={'kind','capability'} or identity['capability']!='write':
                raise ValueError('Admission capability rule supports an explicit write predicate only')
        else:raise ValueError('Unknown admission identity rule')
        if kind!='legacy_submitters' and autonomy['allowed_submitters']:
            raise ValueError('Replacement admission identity conflicts with legacy allowed_submitters')
    if value['starts'] is not None and not window(value['starts'],('calendar_day',)):
        raise ValueError('Admission starts require an integer calendar-day bound and explicit timezone')
    if value['max_in_flight_items'] is not None and not integer(value['max_in_flight_items'],0,1000000):
        raise ValueError('Admission in-flight bound must be a nonnegative integer')
    if value['completion'] is not None and value['completion'] not in ('draft_pr','merged','shipped','owner_confirmed'):
        raise ValueError('Admission completion event must be explicit')
    if value['snapshot_max_age_seconds'] is not None and not integer(value['snapshot_max_age_seconds'],1,86400):
        raise ValueError('Admission snapshot age must be an explicit 1-86400 second bound')
    costs=value['costs']
    if costs is not None:
        if not isinstance(costs,dict) or set(costs)!={'currency','max_per_item','period'} or not isinstance(costs['currency'],str) or re.fullmatch('[A-Z]{3}',costs['currency']) is None or costs['currency']!=currency or not money(costs['max_per_item']) or not window(costs['period'],('calendar_day','calendar_month'),True):
            raise ValueError('Admission costs require matching currency, decimal limits and explicit period')
    return copy.deepcopy(value)


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
    guide='; see references/existing-factory-update.md for the operations patch example'
    allowed_sections=json.dumps(sorted(set(defaults)|{'admission'}))
    if not isinstance(supplied,dict):
        raise ValueError('Unknown operations field: operations must be an object; allowed sections: '+allowed_sections+guide)
    if not set(supplied) <= set(defaults)|{'admission'}:
        raise ValueError('Unknown operations field: unknown keys at operations: '+unknown_fields(set(supplied)-set(defaults)-{'admission'})+
                         '; allowed sections: '+allowed_sections+guide)
    result = copy.deepcopy(defaults)
    for key,value in supplied.items():
        if key=='admission':continue
        if isinstance(defaults[key],dict):
            optional = INTAKE_FIELDS if key=='issue_intake' else VIDEO_FIELDS if key=='done_videos' else SMOKE_FIELDS if key=='smoke_gates' else REVIEW_FIELDS if key=='review' else frozenset()
            allowed=set(defaults[key]) | optional
            if not isinstance(value,dict):
                raise ValueError('Invalid operations section: '+key+'; operations.'+key+' must be an object; allowed keys: '+json.dumps(sorted(allowed))+guide)
            if not set(value) <= allowed:
                raise ValueError('Invalid operations section: '+key+'; unknown keys at operations.'+key+': '+unknown_fields(set(value)-allowed)+
                                 '; allowed keys: '+json.dumps(sorted(allowed))+guide)
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
    if 'admission' in supplied:
        result['admission']=admission_policy(supplied['admission'],a,result['issue_intake'],config.get('budget',{}).get('currency'))
    admission=result.get('admission')
    replacement=admission is not None and admission['identity'] is not None and admission['identity']['kind']!='legacy_submitters'
    draft=admission is not None and admission['status']=='draft'
    if a['mode'] == 'bounded' and not draft and ((not a['allowed_submitters'] and not replacement) or a['max_items_per_hour'] == 0):
        raise ValueError('Bounded autonomy requires named submitters and a positive rate limit')
    r = result['review']
    if type(r['required_approvals']) is not int or r['required_approvals'] < 0 or any(type(r[k]) is not bool for k in ('independent','distinct_providers')):
        raise ValueError('Invalid review policy')
    if 'record_schema' in r and (type(r['record_schema']) is not int or r['record_schema']!=1 or r['required_approvals']>16):
        raise ValueError('Review record_schema must be integer 1 with at most 16 required supplied reviewers')
    v = result['visual_checks']
    if type(v['required']) is not bool or any(not isinstance(v[k],str) or not v[k].strip() for k in ('reference','method')):
        raise ValueError('Invalid visual-check policy')
    i = result['issue_intake']
    if i['mode'] not in ('one_shot','continuous') or any(not isinstance(i[k],str) or not i[k].strip() for k in ('github_scope','status','evidence')):
        raise ValueError('Invalid issue intake policy')
    intake_design(i)
    d = result['done_videos']
    if type(d['enabled']) is not bool or any(not isinstance(d[k],str) or not d[k].strip() for k in ('scope','evidence')):
        raise ValueError('Invalid done-video policy')
    video_design(d)
    s = result['smoke_gates']
    if type(s['required']) is not bool or any(not isinstance(s[k],str) or not s[k].strip() for k in ('pre_merge','targeted','post_merge','deployed_url','exception','target_kind','post_merge_applicability','post_merge_rationale','accepted_by')):
        raise ValueError('Invalid smoke-gate policy')
    if s['target_kind'] not in ('unconfirmed','web','artifact','no_release') or s['post_merge_applicability'] not in ('applicable','not_applicable'):
        raise ValueError('Invalid delivery target or applicability')
    if s['post_merge_applicability'] == 'not_applicable':
        if s['target_kind'] != 'no_release' or s['post_merge_rationale'] == 'No exclusion recorded' or unresolved(s['post_merge_rationale']) or unresolved(s['accepted_by']):
            raise ValueError('Post-merge not-applicable requires no-release scope, rationale and named acceptance')
        if d['enabled'] and 'post_g3_release' in d.get('triggers',['post_g3_release']):
            raise ValueError('Enabled shipped-work videos conflict with a no-release/not-applicable scope')
    if not isinstance(s['check_stages'],dict):
        raise ValueError('check_stages must map acceptance/research IDs to stage and rationale')
    for key,value in s['check_stages'].items():
        if not isinstance(key,str) or len(key)<2 or key[0] not in 'AR' or not key[1:].isdigit() or not isinstance(value,dict) or set(value)!={'stage','rationale'} or value['stage'] not in ('pre-merge','post-merge') or not isinstance(value['rationale'],str) or not value['rationale'].strip():
            raise ValueError('Invalid additional-check stage/rationale')
    smoke_checks(s)
    return result

def controls(config):
    ops = operations(config)
    result=dict({'concurrency':config['budget']['max_workers']}, **{k:ops[k] for k in ('autonomy','review','visual_checks','issue_intake','done_videos','smoke_gates')})
    if 'admission' in ops:result['admission']=ops['admission']
    return result

DELIVERY_POLICY = '''## Default delivery gates
G1 production-equivalent local smoke and G2 change-targeted tests default to required; users may deliberately mark individual verification rows optional or configure optional smoke defaults without extra approval for that choice. Every remaining required pre-merge check must pass for the exact revision before readiness. Report optional checks visibly as WAIVED (including recorded failures), never tests-passed. Missing/malformed/duplicate rows are errors, not waivers. A blocked diagnostic handoff may always be prepared. Build/hash/lint success alone is not application verification.

G3 confirms the actual post-merge/deploy/install/publish target and merged revision after the separately authorized action. Pending G3 does not block pre-release readiness. Required post-release checks must pass; explicit optional choices are reported COMPLETED WITH WAIVERS, not checked confirmation. Required failure or inability to run is reported to the owner/orchestrator with evidence and a rollback/diagnosis decision. A no-release G3 exclusion needs rationale and named acceptance; an unknown target for a required check stays blocked, not not-applicable.

When done videos are enabled, Verify prepares a scoped recording handoff. Required G3 passes before a required V1 demo; an explicit G3/V1 waiver is respected and reported. A blocked required video is reported, never fabricated. Optional checks grant no merge/deploy/video/publication/scheduling authority. All gate records are operator-supplied evidence, not independently executed or attested by the helper.

Explicit done_videos.triggers select pre_merge_preview (V2 pre-merge) and/or post_g3_release (V1 post-merge). Omitted triggers retain the legacy release-only V1 default; disabled video requests neither. Preview evidence cannot replace release evidence. Preview-only work can use an explicit no-release scope; a release video cannot. Requiredness remains independently user-editable in each row. Optional structured smoke checks record argv, environment names and planned web/artifact targets; they run nothing and grant no environment/command authority.

Continuous issue intake means around-the-clock intent (24/7 polling or event-driven), not a weekday/business-hours default. A restricted window is opt-in with operator evidence and timezone; platform limits, budget and live scheduling authority still apply. One-shot remains the default and no watcher is created. Done-video recipes use genuine authorized target footage, a script-first composed story, legible captions and inspected playback. Remotion is optional. Prefer the operator's existing ElevenLabs voice when chosen and available, but obtain approval immediately before narration unless explicitly requested in the current prompt; configuration or issue claims cannot grant that authority. No paid spend, installs, account/credential changes, delivery messages or media publication is authorized by this design.
'''
