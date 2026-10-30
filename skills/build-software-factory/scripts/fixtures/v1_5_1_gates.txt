#!/usr/bin/env python3
"""Fail-closed delivery-record checks; never execute application checks or release actions."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import sys
from integrity import check, safe_path
from operations import controls, operations, unresolved

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
    if ops['done_videos']['enabled']:
        required['V1'] = {'stage':'post-merge','design':'After G3, record the authorized narrated done-video and artifact for the shipped revision; scope: '+ops['done_videos']['scope'],'applicability':'applicable'}
    return required

def initial_table(config, research):
    lines = [HEADER]
    for gate, spec in requirements(config, research).items():
        na = spec['applicability']=='not_applicable'
        evidence = spec['rationale']+'; accepted by '+spec['accepted_by'] if na else ''
        cells = [gate,spec['stage'],spec['design'],'unconfirmed','yes' if spec.get('required',True) else 'no','',
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

def problems(text, stage, revision, required=None, target=None):
    if stage not in STAGES or not isinstance(revision,str) or not revision.strip():
        raise ValueError('Known stage and exact revision are required')
    required = required if required is not None else {
        'G1':{'stage':'pre-merge','applicability':'applicable'},
        'G2':{'stage':'pre-merge','applicability':'applicable'},
        'G3':{'stage':'post-merge','applicability':'applicable'}}
    rows = gate_rows(text)
    out = []
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
            out.append(gate+' has stale or missing revision')
        if unresolved(row['design']) or row['design'].lower().startswith(('unconfirmed','replace with','design (not a command)')) or unresolved(row['environment']) or unresolved(row['evidence']) or row['evidence'].lower() in ('not run','todo'):
            out.append(gate+' lacks concrete check, environment or evidence')
        if unresolved(row['target']):
            out.append(gate+' lacks the actual target')
        if target is not None and row['target'] != target:
            out.append(gate+' evidence is for a different target')
        if stage=='post-merge' and not target:
            out.append(gate+' requires the actual --target for post-merge confirmation')
        if row['exit_status'] not in ('0','manual'):
            out.append(gate+' has no successful exit status or explicit manual observation')
        try:
            observed_time(row['checked_at'])
        except (ValueError,TypeError):
            out.append(gate+' lacks a valid observation timestamp with timezone')
    if stage=='post-merge' and 'V1' in required:
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
    return json.loads(match.group(1))

def waivers(text,stage):
    return [gate+' WAIVED (recorded '+row['result']+')' for gate,row in gate_rows(text).items() if row['stage']==stage and row['required']=='no']

def assess(factory, stage, revision, target=None):
    root = safe_path(factory)
    check(root,quiet=True)
    config = json.loads((root/'config.json').read_text(encoding='utf-8-sig'))
    research = json.loads((root/'research.json').read_text(encoding='utf-8-sig'))
    if policy_controls((root/'policy.md').read_text(encoding='utf-8-sig')) != controls(config):
        raise ValueError('Configuration and policy controls disagree; use a reviewed synchronized operations update')
    expected = requirements(config,research)
    s = operations(config)['smoke_gates']
    rows=gate_rows((root/'verification.md').read_text(encoding='utf-8-sig'))
    if stage=='post-merge' and s['post_merge_applicability']=='applicable' and rows.get('G3',{}).get('required')=='yes':
        if s['target_kind']=='unconfirmed' or unresolved(target):
            return ['Actual post-release target or target kind is unresolved']
        if not unresolved(s['deployed_url']) and target!=s['deployed_url']:
            return ['Actual post-release target differs from the configured target']
    return problems((root/'verification.md').read_text(encoding='utf-8-sig'),stage,revision,expected,target)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory',required=True)
    parser.add_argument('--stage',choices=STAGES)
    parser.add_argument('--revision')
    parser.add_argument('--target')
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
