"""Bounded supplied review records; no review execution, authentication or authority."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
if __name__=='__main__':sys.dont_write_bytecode=True

START='<!-- factory-review-record:v1:start -->'
END='<!-- factory-review-record:v1:end -->'
MAX_HANDOFF=2_000_000
MAX_SECTION=1_000_000
MAX_ROUNDS=256
MAX_REVIEWS=16
MAX_FINDINGS=64
LENSES=frozenset(('spec','standards','correctness','security','architecture'))
CORE=frozenset(('spec','standards','correctness'))
NOTICE='Supplied review claims only; not execution, identity, independence, provider/family provenance, artifact inspection or authority proof.'


def need(condition,message):
    if not condition:raise ValueError('Review record: '+message)


def fields(value,names):return isinstance(value,dict) and set(value)==set(names.split())
def label(value,limit=2000):return isinstance(value,str) and 0<len(value)<=limit and value==value.strip() and value.isprintable()
def known(value):
    if value is None:return False
    normalized=' '.join(value.casefold().split()).rstrip(' .:')
    return normalized not in ('unknown','unconfirmed','none','n/a','not configured','not set','pending','tbd') and not normalized.startswith(('unknown:','unconfirmed:','tbd:'))
def ident(value):return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}',value) is not None
def digest(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
def policy_digest(controls,budget,acceptance,research):
    from research import validate_research
    try:validate_research(research)
    except (ValueError,KeyError,TypeError,RecursionError) as exc:raise ValueError('Review record: invalid research scope') from exc
    need(isinstance(acceptance,list) and acceptance and all(isinstance(value,str) and value.strip() for value in acceptance),'acceptance scope is invalid')
    return hashlib.sha256(canonical({'controls':controls,'budget':budget,'acceptance':acceptance,'research':research})).hexdigest()
def record_token(value):
    need(bool(value['rounds']),'no selected round token exists')
    return 'review:'+value['selected_round']+':'+hashlib.sha256(canonical(value)).hexdigest()
def empty():return {'schema_version':1,'selected_round':None,'rounds':[]}


def strict(raw):
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate JSON key');result[key]=value
        return result
    def constant(_):raise ValueError('Review record: non-finite JSON value')
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)
    except (ValueError,RecursionError) as exc:raise ValueError('Review record: malformed or ambiguous JSON') from exc


def read_handoff(path):
    path=Path(path)
    for item in (path,*path.parents):
        metadata=item.lstat()
        need(not stat.S_ISLNK(metadata.st_mode) and not getattr(metadata,'st_file_attributes',0)&0x400,'redirected handoff path')
    before=path.stat();need(stat.S_ISREG(before.st_mode) and before.st_size<=MAX_HANDOFF,'handoff must be a bounded regular file')
    with path.open('rb') as stream:raw=stream.read(MAX_HANDOFF+1)
    after=path.stat()
    need(len(raw)==before.st_size and len(raw)<=MAX_HANDOFF and
         (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'handoff changed during read')
    return raw.decode('utf-8-sig')


def stamp(value,now):
    need(isinstance(value,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})',value),'timestamp must include calendar time and timezone')
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise ValueError('Review record: invalid calendar timestamp') from exc
    need(parsed<=now,'future observation timestamp')


def validate(value,now=None):
    now=now or datetime.now(timezone.utc)
    need(fields(value,'schema_version selected_round rounds') and type(value['schema_version']) is int and value['schema_version']==1,'unsupported section schema')
    rounds=value['rounds'];need(isinstance(rounds,list) and len(rounds)<=MAX_ROUNDS,'round history limit exceeded')
    need(value['selected_round']==(rounds[-1].get('id') if rounds and isinstance(rounds[-1],dict) else None),'explicit selected round must be the final appended round')
    seen=set()
    for item in rounds:
        need(fields(item,'id subject base policy_sha256 artifact risk builder required_lenses applicability_reason inversion reviews resolutions'),'unsupported round fields')
        need(ident(item['id']) and item['id'].casefold() not in seen,'duplicate or invalid round ID');seen.add(item['id'].casefold())
        need(all(label(item[key],256) for key in ('subject','base')) and digest(item['policy_sha256']),'subject/base/policy binding is missing')
        artifact=item['artifact'];need(fields(artifact,'kind sha256 reference') and artifact['kind']=='source_diff' and digest(artifact['sha256']) and label(artifact['reference']),'invalid supplied diff artifact identity')
        need(item['risk'] in ('low','medium','high') and label(item['applicability_reason']),'risk/applicability choice is missing')
        builder=item['builder'];need(fields(builder,'identity provider model_family'),'invalid builder provenance')
        need(builder['identity'] is None or ident(builder['identity']),'invalid builder identity')
        need(all(builder[key] is None or label(builder[key],128) for key in ('provider','model_family')),'invalid builder provenance label')
        lenses=item['required_lenses'];need(isinstance(lenses,list) and all(isinstance(v,str) for v in lenses) and len(lenses)==len(set(lenses)) and CORE<=set(lenses)<=LENSES,'invalid lens coverage choice')
        inversion=item['inversion'];need(fields(inversion,'choice reason decided_by') and inversion['choice'] in ('not_selected','selected','waived') and label(inversion['reason']) and ident(inversion['decided_by']),'explicit inversion choice, reason and decision owner are required')
        if inversion['choice']=='waived':need(known(inversion['reason']) and known(inversion['decided_by']),'optional inversion waiver needs a concrete reason and named decision')
        reviews=item['reviews'];need(isinstance(reviews,list) and len(reviews)<=MAX_REVIEWS,'reviewer count limit exceeded')
        reviewers=set();review_ids=set();roles=[]
        for review in reviews:
            need(fields(review,'id reviewer role subject base artifact_sha256 provider model_family independent inputs verdict observed_at evidence lenses findings'),'unsupported reviewer fields')
            need(ident(review['id']) and review['id'].casefold() not in review_ids,'duplicate or invalid review ID');review_ids.add(review['id'].casefold())
            need(ident(review['reviewer']) and review['reviewer'].casefold() not in reviewers,'duplicate or invalid reviewer identity');reviewers.add(review['reviewer'].casefold())
            need(review['role'] in ('primary','inversion','additional'),'unknown reviewer role');roles.append(review['role'])
            need(review['subject']==item['subject'] and review['base']==item['base'] and review['artifact_sha256']==artifact['sha256'],'reviewer subject/base/artifact does not match round')
            need(all(review[key] is None or label(review[key],128) for key in ('provider','model_family')),'invalid reviewer provenance label')
            need(type(review['independent']) is bool and review['inputs'] in ('source_only','shared_context'),'invalid supplied independence/input boundary')
            need(review['verdict'] in ('approve','request_changes','blocked') and label(review['evidence']),'verdict or evidence missing')
            stamp(review['observed_at'],now)
            coverage=review['lenses'];need(isinstance(coverage,list) and all(isinstance(v,str) for v in coverage) and len(coverage)==len(set(coverage)) and set(coverage)<=LENSES,'invalid reviewer lenses')
            findings=review['findings'];need(isinstance(findings,list) and len(findings)<=MAX_FINDINGS,'finding limit exceeded')
            finding_ids=set()
            for finding in findings:
                need(fields(finding,'id severity claim evidence verification') and ident(finding['id']) and finding['id'].casefold() not in finding_ids,'invalid or duplicate finding');finding_ids.add(finding['id'].casefold())
                need(finding['severity'] in ('critical','major','minor') and label(finding['claim']) and label(finding['evidence']),'invalid finding claim')
                check=finding['verification']
                if check is not None:
                    need(fields(check,'reviewer disposition evidence reason') and ident(check['reviewer']) and check['disposition'] in ('confirmed','refuted','resolved','unconfirmed') and label(check['evidence']) and label(check['reason']),'invalid finding verification')
                    need(check['reviewer'].casefold()!=review['reviewer'].casefold(),'finding verifier must differ from original reviewer')
        need(roles.count('primary')<=1 and roles.count('inversion')<=1,'ambiguous primary/inversion identity')
        need(inversion['choice']=='selected' or 'inversion' not in roles,'unselected or waived inversion cannot contain an inversion verdict')
        resolutions=item['resolutions'];need(isinstance(resolutions,list) and len(resolutions)<=256,'resolution count limit exceeded')
        for resolution in resolutions:
            need(fields(resolution,'round_id review_id finding_id reviewer disposition evidence reason') and all(ident(resolution[key]) for key in ('round_id','review_id','finding_id','reviewer')),'invalid resolution reference')
            need(resolution['disposition'] in ('confirmed','refuted','resolved','unconfirmed') and label(resolution['evidence']) and label(resolution['reason']),'invalid resolution disposition')
    finding_states(value)
    return value


def finding_states(record):
    """Exact prior references; no cross-subject lineage or implicit resolution."""
    states={}
    def closed(check):
        return check is not None and check['disposition'] in ('refuted','resolved') and all(known(check[key]) for key in ('reviewer','evidence','reason'))
    for item in record['rounds']:
        seen=set()
        for resolution in item['resolutions']:
            key=tuple(resolution[name] for name in ('round_id','review_id','finding_id'))
            need(key not in seen and key in states,'duplicate, unknown or future resolution reference');seen.add(key)
            state=states[key]
            need(state['subject']==item['subject'] and state['base']==item['base'],'cross-subject/base resolution is outside this schema')
            need(not state['closed'],'stale resolution reference already closed')
            need(resolution['reviewer'].casefold()!=state['reviewer'].casefold(),'resolution checker must differ from original finding reviewer')
            state['closed']=closed(resolution)
        for review in item['reviews']:
            for finding in review['findings']:
                if finding['severity'] in ('critical','major'):
                    key=(item['id'],review['id'],finding['id'])
                    states[key]={'subject':item['subject'],'base':item['base'],'reviewer':review['reviewer'],
                                 'closed':closed(finding['verification']),'severity':finding['severity']}
    return states


def history_summary(record):
    selected=record['rounds'][-1] if record['rounds'] else None
    current=other=0
    for state in finding_states(record).values():
        if state['closed']:continue
        if selected and state['subject']==selected['subject'] and state['base']==selected['base']:current+=1
        else:other+=1
    return {'unresolved_selected_scope':current,'unresolved_other_subject_or_base':other,
            'notice':'Other-subject/base findings remain historical and unresolved; a fresh approval does not assert their repair.'}


def parse(body,now=None):
    need(isinstance(body,str) and len(body)<=MAX_HANDOFF and len(body.encode('utf-8'))<=MAX_HANDOFF,'handoff exceeds byte limit')
    need(not any(re.match(r'^[ \t]*(?:<{7,}|={7,}|>{7,}|\|{7,})(?:[ \t]|$)',line) for line in body.splitlines()),'unresolved merge marker')
    need(body.count(START)==1 and body.count(END)==1,'exactly one marked review section is required')
    start=body.index(START);end=body.index(END)
    need(start<end and (start==0 or body[start-1]=='\n'),'invalid review section boundaries')
    need(end+len(END)==len(body) or body[end+len(END)] in '\r\n','review end marker must be on its own line')
    fence=None;comment=False
    for line in body[:start].splitlines():
        stripped=line.lstrip()
        if comment:
            if '-->' in line:comment=False
            continue
        if fence is None and stripped.startswith('<!--'):
            comment='-->' not in stripped;continue
        marker=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',line)
        if marker:
            if fence is None:fence=marker[1]
            elif marker[1][0]==fence[0] and len(marker[1])>=len(fence) and not marker[2].strip():fence=None
    need(fence is None and not comment,'review section is hidden inside a fence/comment')
    section=body[start+len(START):end].replace('\r\n','\n')
    need(section.startswith('\n```json\n') and section.endswith('\n```\n'),'review section must contain one JSON fence')
    raw=section[len('\n```json\n'):-len('\n```\n')]
    need(len(raw.encode('utf-8'))<=MAX_SECTION and '```' not in raw,'review JSON section exceeds limits or has ambiguous fences')
    return validate(strict(raw),now)


def section(value):
    validate(value)
    body=START+'\n```json\n'+json.dumps(value,indent=2,ensure_ascii=True)+'\n```\n'+END
    need(len(body.encode())<=MAX_SECTION,'review JSON history exceeds byte limit; preserve history and review a separate archival design')
    return body


def initialize(body):
    need(START not in body and END not in body,'existing review section must be preserved')
    return body.rstrip('\r\n')+'\n\n'+section(empty())+'\n'


def append_round(body,item):
    record=parse(body);need(isinstance(item,dict),'round input must be an object')
    result={**record,'selected_round':item.get('id'),'rounds':record['rounds']+[item]}
    rendered=section(result);start=body.index(START);end=body.index(END)+len(END)
    output=body[:start]+rendered+body[end:];parse(output)
    return output.encode('utf-8')


def assessment(body,policy,expected_policy,subject,*,required=True):
    record=parse(body)
    if not required:return []
    if not record['rounds']:return ['Q1 has no selected supplied review round']
    item=record['rounds'][-1];out=[];reviews=item['reviews']
    if item['subject']!=subject:out.append('Q1 review round has stale or missing exact subject')
    if item['policy_sha256']!=expected_policy:out.append('Q1 review round binds different controls, budget, acceptance or research scope')
    if sum(r['role']=='primary' for r in reviews)!=1:out.append('Q1 needs exactly one primary reviewer')
    verdicts={r['verdict'] for r in reviews}
    if {'approve','request_changes'}<=verdicts:out.append('Q1 reviewer disagreement requires a new resolved review round; retain both findings')
    elif 'request_changes' in verdicts:out.append('Q1 reviewers request changes; return to Build')
    if 'blocked' in verdicts:out.append('Q1 contains a blocked review')
    approvals=[r for r in reviews if r['verdict']=='approve']
    if any(not known(r['reviewer']) or not known(r['evidence']) for r in approvals):out.append('Q1 approval identity/evidence is unconfirmed')
    if len(approvals)<max(1,policy['required_approvals']):out.append('Q1 lacks the configured number of distinct supplied approvals')
    coverage=set().union(*(set(r['lenses']) for r in reviews)) if reviews else set()
    if not set(item['required_lenses'])<=coverage:out.append('Q1 required review lenses lack supplied coverage')
    builder=item['builder']
    def independent(review):return review['independent'] and known(builder['identity']) and known(review['reviewer']) and review['reviewer'].casefold()!=builder['identity'].casefold()
    if policy['independent'] and any(not independent(r) for r in approvals):out.append('Q1 required independence claims lack distinct known builder/reviewer identities')
    if policy['distinct_providers']:
        providers=[' '.join(r['provider'].casefold().split()) if known(r['provider']) else None for r in approvals]
        if None in providers or len(set(providers))!=len(providers):out.append('Q1 required distinct provider claims are missing or repeated')
    if item['inversion']['choice']=='selected':
        inverse=[r for r in reviews if r['role']=='inversion']
        if len(inverse)!=1:out.append('Q1 selected inversion has no second reviewer verdict; no automatic waiver')
        else:
            inv=inverse[0]
            if not independent(inv) or inv['inputs']!='source_only':out.append('Q1 inversion lacks supplied independent source-only input boundary')
            if not known(builder['model_family']) or not known(inv['model_family']) or ' '.join(builder['model_family'].casefold().split())==' '.join(inv['model_family'].casefold().split()):out.append('Q1 inversion needs known supplied family distinct from the builder family')
    if history_summary(record)['unresolved_selected_scope']:
        out.append('Q1 has unresolved or unconfirmed Critical/Major findings for the selected subject/base')
    return list(dict.fromkeys(out))


def supplement_waivers(body,stage):
    if stage!='pre-merge':return []
    record=parse(body)
    return ['Q1 inversion WAIVED (explicit named decision; no secondary approval claimed)'] if record['rounds'] and record['rounds'][-1]['inversion']['choice']=='waived' else []


def context(factory):
    """Read current calculation inputs and supplied selection; never fetch references."""
    from integrity import check, safe_path
    from operations import operations, controls
    from gates import policy_controls, control_differences
    root=safe_path(factory);check(root,quiet=True)
    before={name:read_handoff(root/name) for name in ('config.json','research.json','policy.md','release-handoff.md')}
    config=strict(before['config.json']);research=strict(before['research.json'])
    policy=operations(config)['review'];need('record_schema' in policy,'workflow has not been explicitly adopted')
    need(not control_differences(policy_controls(before['policy.md'].replace('\r\n','\n')),controls(config)),'config/policy controls disagree')
    value=policy_digest(controls(config),config['budget'],config['acceptance'],research)
    record=parse(before['release-handoff.md']);selected=record['rounds'][-1] if record['rounds'] else None
    need(all(read_handoff(root/name)==text for name,text in before.items()),'context changed during read')
    return {'schema_version':1,'policy_sha256':value,'review_policy':policy,
            'selected_round':None if selected is None else {'id':selected['id'],'subject':selected['subject'],'base':selected['base'],
                         'evidence_token':record_token(record),'artifact_target':'sha256:'+selected['artifact']['sha256']},
            'review_history':history_summary(record),'notice':NOTICE}


def main(argv=None):
    import argparse
    class Arguments(argparse.ArgumentParser):
        def error(self,message):self.exit(2,'ERROR: invalid review context arguments; use --help.\n')
    parser=Arguments(description=__doc__);parser.add_argument('--factory',required=True);args=parser.parse_args(argv)
    try:result=context(args.factory)
    except (ValueError,OSError,UnicodeError,KeyError,TypeError,RecursionError):
        print('ERROR: malformed, unsupported or changed review context; no files written.',file=sys.stderr);return 2
    print(json.dumps(result,ensure_ascii=True,sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
