#!/usr/bin/env python3
"""Fail-closed delivery-record checks; never execute application checks or release actions."""
import sys
if __name__ == '__main__':sys.dont_write_bytecode = True
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from integrity import check, safe_path
from operations import controls, operations, unresolved, smoke_checks, smoke_design
from recipes import video_triggers

STAGES = ('pre-merge', 'post-merge')
ROW = re.compile(r'^\|\s*([A-Z]\d+)\s*\|')
HEADER = '| Gate | Stage | Check/design | Environment | Required? | Revision | Result | Evidence | Actual target | Checked at (ISO timezone) | Exit status (0/manual) |\n|---|---|---|---|---|---|---|---|---|---|---|'

def requirements(config, research):
    ops = operations(config)
    smoke = ops['smoke_gates']
    required = {
        'G1': {'stage':'pre-merge','design':smoke['pre_merge'],'applicability':'applicable'},
        'G2': {'stage':'pre-merge','design':smoke['targeted'],'applicability':'applicable'},
        'G3': {'stage':'post-merge','design':smoke['post_merge'],'applicability':smoke['post_merge_applicability'],
               'rationale':smoke['post_merge_rationale'],'accepted_by':smoke['accepted_by']}
    }
    for spec in required.values():spec['required']=smoke['required']
    for gate,recipe in smoke_checks(smoke).items():
        required[gate].update(design=smoke_design(recipe),recipe=recipe)
    for i, criterion in enumerate(config['acceptance'], 1):
        required['A'+str(i)] = {'stage':'pre-merge','design':criterion,'applicability':'applicable'}
    selected = [p for p in research['practices'] if p['decision']=='selected']
    for i, practice in enumerate(selected, 1):
        phase_stage = 'post-merge' if set(practice['phases']) <= {'release','learn'} else 'pre-merge'
        required['R'+str(i)] = {'stage':phase_stage,'design':practice['check'],'applicability':'applicable'}
    for gate, override in smoke['check_stages'].items():
        if gate not in required:
            raise ValueError('Unknown additional-check stage override: '+gate)
        required[gate]['stage']=override['stage']
    triggers=video_triggers(ops['done_videos'])
    if 'post_g3_release' in triggers:
        required['V1'] = {'stage':'post-merge','design':'After G3, record the authorized narrated done-video and artifact for the shipped revision; scope: '+ops['done_videos']['scope'],'applicability':'applicable'}
    if 'pre_merge_preview' in triggers:
        required['V2'] = {'stage':'pre-merge','design':'Record the authorized genuine preview demo for the reviewed local/preview subject; scope: '+ops['done_videos']['scope'],'applicability':'applicable'}
    return required

def initial_table(config, research):
    lines = [HEADER]
    for gate, spec in requirements(config, research).items():
        na = spec['applicability']=='not_applicable'
        evidence = spec['rationale']+'; accepted by '+spec['accepted_by'] if na else ''
        cells = [gate,spec['stage'],spec['design'],spec.get('recipe',{}).get('environment','unconfirmed'),'yes' if spec.get('required',True) else 'no','',
                 'NOT APPLICABLE' if na else 'NOT RUN',evidence,'','','']
        lines.append('| '+' | '.join(str(c).replace('|','/') for c in cells)+' |')
    return '\n'.join(lines)+'\n'

def gate_rows(text):
    rows = {}
    keys = ('gate','stage','design','environment','required','revision','result','evidence','target','checked_at','exit_status')
    for line in text.replace('\r\n','\n').split('\n'):
        if ROW.match(line):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells)!=len(keys):
                raise ValueError('Malformed gate row: '+cells[0]+'; use --plan for the current schema')
            row = dict(zip(keys,cells))
            if row['gate'] in rows:
                raise ValueError('Duplicate gate: '+row['gate'])
            flag=row['required'].casefold()
            row['required']='yes' if flag in ('yes','y','true') else 'no' if flag in ('no','n','false') else flag
            if row['stage'] not in STAGES or row['required'] not in ('yes','no'):
                raise ValueError('Invalid gate stage/required flag: '+row['gate'])
            if row['result'] not in ('PASSED','FAILED','BLOCKED','NOT RUN','NOT APPLICABLE'):
                raise ValueError('Unknown gate result: '+row['gate'])
            rows[row['gate']] = row
    return rows

def observed_time(value):
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Evidence time requires an explicit timezone')
    return result

def subject_abbreviation_hint(recorded, requested):
    """Explain a recognizable spelling mismatch without resolving or equating IDs."""
    def prefix(short, full):
        return (len(full) in (40,64) and len(short) not in (40,64) and 7<=len(short)<len(full)
                and re.fullmatch(r'[0-9a-fA-F]+',full) is not None
                and re.fullmatch(r'[0-9a-fA-F]+',short) is not None
                and full.casefold().startswith(short.casefold()))
    if prefix(requested,recorded):
        return ('Supplied --revision looks like a hexadecimal abbreviation of the recorded full subject. Independently verify the evidence provenance, '
                'then pass the exact full recorded subject with --revision; prefixes are not accepted or resolved.')
    if prefix(recorded,requested):
        return ('The recorded subject looks like a hexadecimal abbreviation; this does not establish full-subject binding. Verify provenance and obtain '
                'a new evidence record for the exact full subject; do not automatically expand the existing observation.')
    return None

def problems(text, stage, revision, required=None, target=None):
    if stage not in STAGES or not isinstance(revision,str) or not revision.strip():
        raise ValueError('Known stage and exact revision are required')
    required = required if required is not None else {
        'G1':{'stage':'pre-merge','applicability':'applicable'},
        'G2':{'stage':'pre-merge','applicability':'applicable'},
        'G3':{'stage':'post-merge','applicability':'applicable'}}
    rows = gate_rows(text)
    out = []
    if 'V1' in rows and rows['V1']['stage']!='post-merge':
        out.append('Reserved release video V1 must remain post-merge')
    for gate, spec in required.items():
        row = rows.get(gate)
        if row is None:
            out.append('Missing expected gate row: '+gate)
        elif row['stage'] != spec['stage']:
            out.append('Gate is in the wrong stage: '+gate)
    for gate,row in rows.items():
        if row['stage'] != stage or row['required']=='no':
            continue
        spec = required.get(gate, {'applicability':'applicable'})
        if spec['applicability']=='not_applicable':
            if row['result']!='NOT APPLICABLE' or spec['rationale'] not in row['evidence'] or spec['accepted_by'] not in row['evidence']:
                out.append(gate+' needs the explicit not-applicable rationale and named acceptance')
            continue
        if row['result']!='PASSED':
            out.append(gate+' is '+row['result'])
            continue
        if row['revision'] != revision.strip():
            hint=subject_abbreviation_hint(row['revision'],revision.strip())
            out.append(gate+' has stale or missing revision'+('; '+hint if hint else ''))
        if 'recipe' in spec:
            if row['design']!=spec['design']:out.append(gate+' command record differs from the configured argv recipe')
            if row['environment']!=spec['recipe']['environment']:out.append(gate+' environment differs from the configured recipe')
            if row['target']!=spec['recipe']['target']['value']:out.append(gate+' target differs from the configured recipe')
        if unresolved(row['design']) or row['design'].lower().startswith(('unconfirmed','replace with','design (not a command)')) or unresolved(row['environment']) or unresolved(row['evidence']) or row['evidence'].lower() in ('not run','todo'):
            out.append(gate+' lacks concrete check, environment or evidence')
        if unresolved(row['target']):
            out.append(gate+' lacks the actual target')
        # A configured pre-merge recipe identifies its own artifact. Other rows
        # still match an explicit global target; post-merge never bypasses it.
        if target is not None and not (stage=='pre-merge' and 'recipe' in spec) and row['target'] != target:
            out.append(gate+' evidence is for a different target')
        if stage=='post-merge' and not target:
            out.append(gate+' requires the actual --target for post-merge confirmation')
        if row['exit_status'] not in ('0','manual'):
            out.append(gate+' has no successful exit status or explicit manual observation')
        try:
            observed_time(row['checked_at'])
        except (ValueError,TypeError):
            out.append(gate+' lacks a valid observation timestamp with timezone')
    if stage=='post-merge' and 'V1' in rows:
        smoke,video = rows.get('G3'),rows.get('V1')
        if smoke and video and smoke['required']=='yes' and video['required']=='yes' and video['result']=='PASSED':
            try:
                if smoke['result']!='PASSED' or observed_time(video['checked_at']) < observed_time(smoke['checked_at']):
                    out.append('V1 must follow passing G3 evidence for the shipped revision')
            except (ValueError,TypeError):
                out.append('G3/V1 ordering lacks valid observation timestamps')
    return out

def policy_controls(policy):
    header = '## Proposed autonomy and review controls (not execution authority)'
    if policy.count(header)!=1:
        raise ValueError('Policy control section is missing or ambiguous')
    suffix = policy.split(header,1)[1]
    match = re.match(r'\s*\x60\x60\x60json\n(.*?)\n\x60\x60\x60',suffix,re.S)
    if match is None:
        raise ValueError('Malformed policy control JSON')
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate key in policy controls')
            result[key]=value
        return result
    return json.loads(match.group(1),object_pairs_hook=unique_object)

def waivers(text,stage):
    return [gate+' WAIVED (recorded '+row['result']+')' for gate,row in gate_rows(text).items() if row['stage']==stage and row['required']=='no']


def post_target_problems(kind, planned_target, target):
    """Require separately observed target evidence; planned values are not proof."""
    issues=[]
    if kind=='unconfirmed':issues.append('Configured post-release target kind is unconfirmed; resolve the release design')
    if unresolved(target):issues.append('Post-merge confirmation requires the actual --target; pass the observed deployment or artifact target')
    if not issues and not unresolved(planned_target) and target!=planned_target:
        issues.append('Actual post-release target differs from the configured target')
    return issues


def control_differences(left, right, path='controls'):
    """Return differing field paths without exposing configured or recorded values."""
    if type(left) is not type(right):return [path]
    if isinstance(left,dict):
        result=[]
        for key in sorted(left.keys() | right.keys()):
            child=path+'.'+str(key)
            if key not in left or key not in right:result.append(child)
            else:result.extend(control_differences(left[key],right[key],child))
        return result
    if isinstance(left,list):
        if len(left)!=len(right):return [path]
        return [item for index,(a,b) in enumerate(zip(left,right)) for item in control_differences(a,b,path+'['+str(index)+']')]
    return [] if left==right else [path]


def assess(factory, stage, revision, target=None):
    root = safe_path(factory)
    check(root,quiet=True)
    config = json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    research = json.loads((root/'research.json').read_text(encoding='utf-8-sig'))
    drift=control_differences(policy_controls((root/'policy.md').read_text(encoding='utf-8-sig')),controls(config))
    if drift:
        raise ValueError('Configuration and policy controls disagree at '+json.dumps(drift,ensure_ascii=True)+
                         '; no values printed. Preserve both records and reconcile the intended controls through reviewed recovery '+
                         '(references/recovery.md). update_operations.py refuses existing drift; once reconciled, preview future changes with '+
                         'update_operations.py --factory <factory> --operations <changes.json>, then --apply --approve-plan <digest> only after reviewing that preview. '+
                         'scaffold.py --check checks integrity, basic structure and controls consistency, not application delivery readiness.')
    expected = requirements(config,research)
    s = operations(config)['smoke_gates']
    rows=gate_rows((root/'verification.md').read_text(encoding='utf-8-sig'))
    if stage=='post-merge' and s['post_merge_applicability']=='applicable' and rows.get('G3',{}).get('required')=='yes':
        recipe=smoke_checks(s).get('G3')
        kind=recipe['target']['kind'] if recipe else s['target_kind']
        planned_target=recipe['target']['value'] if recipe else s['deployed_url']
        issues=post_target_problems(kind,planned_target,target)
        if issues:return issues
    return problems((root/'verification.md').read_text(encoding='utf-8-sig'),stage,revision,expected,target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory',required=True,help='Directory whose current on-disk files are checked, including files untracked or ignored by Git')
    parser.add_argument('--stage',choices=STAGES)
    parser.add_argument('--revision',help='Exact evidence subject identifier to match in records; does not select or reconstruct a Git checkout. Reads current --factory files; no short/full SHA equivalence')
    parser.add_argument('--target',help='Observed deployment or artifact target required for still-required post-merge confirmation; never inferred from the planned target')
    parser.add_argument('--plan',action='store_true',help='Print proposed gate rows; writes and executes nothing')
    args = parser.parse_args()
    if args.plan:
        if args.stage or args.revision or args.target:
            parser.error('--plan cannot be combined with evidence assessment')
        root=safe_path(args.factory);check(root,quiet=True)
        print(initial_table(json.loads((root/'config.json').read_text(encoding='utf-8-sig')),
                            json.loads((root/'research.json').read_text(encoding='utf-8-sig'))))
        return
    if not args.stage or not args.revision:
        parser.error('--stage and --revision are required for evidence assessment')
    found = assess(args.factory,args.stage,args.revision,args.target)
    skipped=waivers((safe_path(args.factory)/'verification.md').read_text(encoding='utf-8-sig'),args.stage)
    for item in skipped:print(item+'; not evidence that the check ran or passed')
    if found:
        print('BLOCKED: recorded '+args.stage+' gates are not satisfied')
        for item in found: print('  - '+item)
        sys.exit(1)
    print(('ELIGIBLE WITH WAIVERS: ' if skipped else 'RECORDED requirements satisfied: ')+args.stage+'. No checks were executed or attested; this grants no release authority.')

if __name__=='__main__':
    try: main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(2)
