"""Review bounded supplied admission observations; never reserve, fetch or enforce."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import stat
import sys
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from integrity import check, safe_path, strict_json
from operations import operations, controls

MAX_BYTES=1024*1024
NOTICE=('Supplied snapshot claims only: no independent identity, permission, completeness, billing or '
        'terminal-state verification. No reservation, task spend enforcement or action authority.')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def bounded_json(path):
    path=safe_path(path);before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_BYTES:
        raise ValueError('Admission input must be a bounded regular JSON file')
    with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    after=path.lstat()
    if len(raw)>MAX_BYTES or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError('Admission input changed or exceeds its bound')
    return strict_json(raw.decode('utf-8-sig'))


def shape(value,keys):
    if not isinstance(value,dict) or set(value)!=set(keys.split()):
        raise ValueError('Admission snapshot object has unexpected or missing fields')


def label(value):
    if not isinstance(value,str) or not 1<=len(value)<=256 or value!=value.strip() or not value.isprintable():
        raise ValueError('Admission identifiers and references must be bounded printable text')
    return value


def instant(value):
    label(value)
    if len(value)>64:raise ValueError('Admission timestamp exceeds its bound')
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('Admission timestamps must be timezone-aware ISO values') from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Admission timestamps must be timezone-aware ISO values')
    return parsed.astimezone(timezone.utc)


def amount(value):
    if not isinstance(value,str) or re.fullmatch(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?',value) is None:
        raise ValueError('Admission cost observation is unknown or not a bounded decimal string')
    return Decimal(value)


def period_bounds(now,window,name):
    zone=timezone.utc if name=='UTC' else ZoneInfo(name)
    local=now.astimezone(zone)
    start=local.replace(hour=0,minute=0,second=0,microsecond=0)
    if window=='calendar_day':end=start+timedelta(days=1)
    elif window=='calendar_month':
        start=start.replace(day=1)
        end=start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1)
    else:raise ValueError('Unsupported admission period')
    return start.astimezone(timezone.utc),end.astimezone(timezone.utc)


def review(config,snapshot,issues,issue_policy,now=None):
    """Return request-bound hypothetical decisions; never mutate any argument."""
    result={'status':'UNKNOWN','allowed':[],'decisions':[],'problems':[],
            'enforced':False,'independently_verified':False,'notice':NOTICE}
    try:
        ops=operations(config);policy=ops.get('admission')
        if policy is None:
            result.update(status='NOT_CONFIGURED',problems=['No admission policy is configured.']);return result
        result['policy_sha256']=digest(policy)
        if policy['status']!='specified':
            result.update(status='BLOCKED',problems=['Admission policy is a draft; explicit choices are still required.']);return result
        if ops['autonomy']['mode']!='bounded' or ops['issue_intake']['mode']!='continuous' or ops['issue_intake']['status'].strip().casefold()!='enabled':
            result.update(status='BLOCKED',problems=['Bounded, enabled continuous-intake design is required; nothing is activated by this review.']);return result
        if snapshot is None:
            result['problems']=['Admission snapshot is required; no issue admission was proposed.'];return result
        now=now or datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:raise ValueError('Assessment time must be timezone-aware')
        now=now.astimezone(timezone.utc)
        # Bound direct in-process inputs as well as files. No source references are followed.
        if len(json.dumps(snapshot,ensure_ascii=True).encode())>MAX_BYTES:raise ValueError('Admission snapshot exceeds its bound')
        shape(snapshot,'version repository policy_sha256 observed_at coverage period cycles requests')
        if type(snapshot['version']) is not int or snapshot['version']!=1 or snapshot['repository']!=policy['repository'] or snapshot['policy_sha256']!=result['policy_sha256']:
            raise ValueError('Admission snapshot must bind the exact repository and policy')
        observed=instant(snapshot['observed_at']);age=policy['snapshot_max_age_seconds']
        if not now-timedelta(seconds=age)<=observed<=now:raise ValueError('Admission snapshot is stale or future-dated')
        start,end=period_bounds(now,policy['starts']['window'],policy['starts']['timezone'])
        cost_start,cost_end=period_bounds(now,policy['costs']['period']['window'],policy['costs']['period']['timezone'])
        if observed<max(start,cost_start):raise ValueError('Admission snapshot predates the current accounting window')
        coverage=snapshot['coverage'];shape(coverage,'starts_since complete source_reference')
        label(coverage['source_reference'])
        if coverage['complete'] is not True or instant(coverage['starts_since'])>start:
            raise ValueError('Complete current-window admission and liability coverage is required')
        period=snapshot['period'];shape(period,'start end spent reserved accounting_complete accounted_through source_reference')
        label(period['source_reference'])
        if instant(period['start'])!=cost_start or instant(period['end'])!=cost_end:
            raise ValueError('Admission cost period does not match the explicit policy window')
        if period['accounting_complete'] is not True or instant(period['accounted_through'])!=observed:
            raise ValueError('Complete accounting through snapshot time, including unresolved liability, is required')
        spent,reserved=amount(period['spent']),amount(period['reserved'])
        if not isinstance(snapshot['cycles'],list) or len(snapshot['cycles'])>1000 or not isinstance(snapshot['requests'],list) or len(snapshot['requests'])>100:
            raise ValueError('Admission cycle/request inventory exceeds its bound')
        cycles={};open_issues=set();starts=0;total_reserved=Decimal(0);current_period_cycle_spend=Decimal(0)
        for cycle in snapshot['cycles']:
            shape(cycle,'issue_id cycle_id admitted_at state completed_at completion spent reserved evidence')
            iid,cid=label(cycle['issue_id']),label(cycle['cycle_id']);label(cycle['evidence'])
            if cid in cycles:raise ValueError('Duplicate admission cycle identity')
            admitted=instant(cycle['admitted_at'])
            if admitted>observed:raise ValueError('Admission cycle starts after snapshot time')
            paid,held=amount(cycle['spent']),amount(cycle['reserved'])
            if cycle['state']=='completed':
                if cycle['completion']!=policy['completion'] or not admitted<=instant(cycle['completed_at'])<=observed or held!=0:
                    raise ValueError('Completed cycles require ordered terminal evidence and zero outstanding reservation')
            elif cycle['state'] in ('active','unknown'):
                if cycle['completed_at'] is not None or cycle['completion'] is not None or iid in open_issues:
                    raise ValueError('Ambiguous unresolved admission cycles')
                open_issues.add(iid)
            else:raise ValueError('Unknown admission cycle state')
            starts+=int(start<=admitted<end)
            if admitted>=cost_start:current_period_cycle_spend+=paid
            total_reserved+=held;cycles[cid]=(cycle,paid,held)
        if total_reserved!=reserved:raise ValueError('Period reservation total must include all outstanding cycle liability')
        if current_period_cycle_spend>spent:raise ValueError('Period spend understates cycles admitted within this period')
        if not isinstance(issue_policy,dict) or set(issue_policy)!={'repository','ready_label','excluded_labels'} or issue_policy['repository']!=policy['repository']:
            raise ValueError('Explicit matching issue-label policy is required')
        ready=label(issue_policy['ready_label']);excluded=issue_policy['excluded_labels']
        if not isinstance(excluded,list) or len(excluded)>100 or any(not isinstance(v,str) or not v or len(v)>256 for v in excluded):
            raise ValueError('Invalid issue exclusion policy')
        if not isinstance(issues,list) or len(issues)>1000:raise ValueError('Bounded normalized current issues are required')
        current={}
        for issue in issues:
            if not isinstance(issue,dict):raise ValueError('Malformed normalized issue')
            iid=label(issue.get('id'));label(issue.get('submitter'))
            if iid in current:raise ValueError('Ambiguous normalized issue identity')
            labels=issue.get('labels');deps=issue.get('depends_on',[])
            if not isinstance(labels,list) or len(labels)>100 or any(not isinstance(v,str) or len(v)>256 for v in labels) or not isinstance(deps,list) or any(not isinstance(v,str) for v in deps):
                raise ValueError('Malformed normalized issue labels or dependencies')
            current[iid]=issue
        seen_requests=set();seen_issues=set();seen_events=set();seen_cycles=set()
        for request in snapshot['requests']:
            shape(request,'request_id issue_id cycle_id kind author event permission reserve')
            rid,iid,cid=(label(request[k]) for k in ('request_id','issue_id','cycle_id'));label(request['author']);amount(request['reserve'])
            if rid in seen_requests or iid in seen_issues or cid in seen_cycles or request['kind'] not in ('start','retry'):
                raise ValueError('Ambiguous request identity or multiple requests for one issue')
            seen_requests.add(rid);seen_issues.add(iid);seen_cycles.add(cid)
            event=request['event']
            if event is not None:
                shape(event,'id label actor occurred_at')
                for key in ('id','label','actor'):label(event[key])
                if event['id'] in seen_events or instant(event['occurred_at'])>observed:raise ValueError('Duplicate or future trigger event')
                seen_events.add(event['id'])
            permission=request['permission']
            if permission is not None:
                shape(permission,'actor capability decision observed_at reference')
                label(permission['actor']);label(permission['reference'])
                if permission['capability']!='write' or permission['decision'] not in ('allowed','denied','unknown'):
                    raise ValueError('Unsupported permission observation')
                instant(permission['observed_at'])
        item_limit=amount(policy['costs']['max_per_item']);period_limit=amount(policy['costs']['period']['maximum'])
        planned_cost=Decimal(0);planned_starts=0;planned_items=0
        identity=policy['identity'];kind=identity['kind']
        for request in sorted(snapshot['requests'],key=lambda row:(row['issue_id'],row['cycle_id'],row['request_id'])):
            rid,iid,cid=(request[k] for k in ('request_id','issue_id','cycle_id'))
            decision={k:request[k] for k in ('request_id','issue_id','cycle_id','kind','reserve')}
            why=[];unknown=False;issue=current.get(iid);event=request['event'];permission=request['permission']
            if issue is None or request['author']!=issue['submitter']:
                why.append('Request does not bind the exact current issue author')
            elif ready not in issue['labels'] or set(issue['labels'])&set(excluded) or issue.get('depends_on'):
                why.append('Current issue readiness, exclusion or dependency policy blocks admission')
            if event is not None and event['label']!=ready:why.append('Trigger event is for a different readiness label')
            if kind=='legacy_submitters':
                if request['author'] not in ops['autonomy']['allowed_submitters']:why.append('Issue author is outside the named submitter policy')
                if permission is not None:why.append('Unexpected permission observation for account policy')
            elif event is None:
                why.append('Label-trigger actor evidence is missing');unknown=True
            elif kind=='label_actor_accounts':
                if event['actor'] not in identity['accounts']:why.append('Label actor is outside the named actor policy')
                if permission is not None:why.append('Unexpected permission observation for account policy')
            else:
                if permission is None:
                    why.append('Current actor capability evidence is missing');unknown=True
                elif permission['actor']!=event['actor']:
                    why.append('Permission observation names a different actor')
                elif not now-timedelta(seconds=age)<=instant(permission['observed_at'])<=observed:
                    why.append('Actor capability evidence is stale or future-dated');unknown=True
                elif permission['decision']!='allowed':
                    why.append('Actor capability is not recorded as allowed');unknown=permission['decision']=='unknown'
            paid=held=Decimal(0);is_start=request['kind']=='start'
            if is_start:
                if cid in cycles or iid in open_issues:why.append('Start conflicts with an existing cycle or unresolved issue')
            elif cid not in cycles or cycles[cid][0]['issue_id']!=iid or cycles[cid][0]['state']!='active':
                why.append('Retry must name the exact active issue cycle')
            else:_,paid,held=cycles[cid]
            allocation=amount(request['reserve'])
            if policy['starts']['maximum']==0 or policy['max_in_flight_items']==0 or item_limit==0 or period_limit==0:
                why.append('An explicit zero admission limit permits no proposal')
            if is_start and starts+planned_starts>=policy['starts']['maximum']:why.append('Recorded calendar-day start allowance is exhausted')
            if is_start and len(open_issues)+planned_items>=policy['max_in_flight_items']:why.append('Recorded in-flight issue allowance is exhausted')
            if paid+held+allocation>item_limit:why.append('Recorded item spend and reservations exceed its allowance')
            if spent+reserved+planned_cost+allocation>period_limit:why.append('Recorded period spend and reservations exceed its allowance')
            decision.update(status='UNKNOWN' if unknown else 'BLOCKED' if why else 'RECORDED_POLICY_SATISFIED',reasons=why)
            result['decisions'].append(decision)
            if not why:
                result['allowed'].append({k:request[k] for k in ('request_id','issue_id','cycle_id','kind','reserve')})
                planned_cost+=allocation;planned_starts+=int(is_start);planned_items+=int(is_start)
        result['snapshot_sha256']=digest(snapshot)
        result['observed_at']=snapshot['observed_at']
        result['status']='RECORDED_POLICY_SATISFIED' if result['allowed'] else 'UNKNOWN' if any(d['status']=='UNKNOWN' for d in result['decisions']) else 'BLOCKED'
        return result
    except ZoneInfoNotFoundError:
        result['problems']=['Configured timezone data is unavailable; no timezone was substituted.']
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):
        result['problems']=['Admission inputs are malformed, inconsistent, incomplete or outside their freshness/size bounds; review the supplied snapshot.']
    result.update(status='UNKNOWN',allowed=[],decisions=[])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('factory','snapshot','issues','issue-policy'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();root=safe_path(args.factory);check(root,quiet=True)
    config=bounded_json(root/'config.json')
    from gates import policy_controls
    if policy_controls((root/'policy.md').read_text(encoding='utf-8-sig'))!=controls(config):
        raise ValueError('Factory policy/config controls disagree')
    result=review(config,bounded_json(args.snapshot),bounded_json(args.issues),bounded_json(args.issue_policy))
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return 0 if result['status']=='RECORDED_POLICY_SATISFIED' else 1


if __name__=='__main__':
    sys.dont_write_bytecode=True
    try:sys.exit(main())
    except (ValueError,OSError,UnicodeError,RecursionError,KeyError,TypeError,OverflowError):
        print('ERROR: admission inputs could not be read or validated; no admission was proposed.',file=sys.stderr);sys.exit(2)
