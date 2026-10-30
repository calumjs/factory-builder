"""Offline scoped record assessment; supplied records are not independently attested."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from gates import gate_rows, problems, requirements, policy_controls, ROW
from integrity import check, safe_path
from operations import controls, operations, smoke_checks, unresolved


def load(factory):
    root=safe_path(factory);check(root,quiet=True)
    def read(name):return (root/name).read_bytes()
    config=json.loads(read('config.json').decode('utf-8-sig'))
    research=json.loads(read('research.json').decode('utf-8-sig'))
    policy=policy_controls(read('policy.md').decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))
    if json.dumps(policy,sort_keys=True)!=json.dumps(controls(config),sort_keys=True):
        raise ValueError('Configuration and policy controls disagree')
    text=read('verification.md').decode('utf-8-sig')
    plan=json.loads(read('task-plan.json').decode('utf-8-sig'))
    return root,config,research,text,plan


def assess_scope(factory, scope, stage, revision, target=None):
    root,config,research,text,plan=load(factory)
    if not isinstance(scope,dict) or set(scope)!={'purpose','gates','tasks'}:
        raise ValueError('Scope must contain exactly purpose, gates and tasks')
    if not isinstance(scope['purpose'],str) or not scope['purpose'].strip():raise ValueError('Scope purpose required')
    for key in ('gates','tasks'):
        values=scope[key]
        if not isinstance(values,list) or any(not isinstance(v,str) or not v for v in values) or len(values)!=len(set(values)):
            raise ValueError('Scope '+key+' must be a unique string list')
    if not scope['gates'] or not scope['tasks']:raise ValueError('Explicit nonempty gates and tasks required')
    expected=requirements(config,research);rows=gate_rows(text)
    if set(scope['gates'])-set(expected):raise ValueError('Scope names unknown or unconfigured gates')
    tasks={t['id']:t for t in plan['tasks']}
    if set(scope['tasks'])-set(tasks):raise ValueError('Scope names unknown tasks')
    visited=set();active=set()
    def visit(tid):
        if tid not in tasks:raise ValueError('Unknown selected-task dependency: '+tid)
        if tid in active:raise ValueError('Cyclic selected-task dependencies')
        if tid in visited:return
        deps=tasks[tid].get('depends_on')
        if not isinstance(deps,list) or any(not isinstance(d,str) or not d for d in deps) or len(deps)!=len(set(deps)):
            raise ValueError('Malformed selected-task dependencies: '+tid)
        active.add(tid)
        for dependency in deps:visit(dependency)
        active.remove(tid);visited.add(tid)
    for tid in scope['tasks']:visit(tid)
    for tid in scope['tasks']:
        links=tasks[tid].get('acceptance_ids')
        if not isinstance(links,list) or not links or any(not isinstance(a,str) for a in links):
            raise ValueError('Selected task needs explicit acceptance links: '+tid)
        valid={f'A{i+1}' for i in range(len(config['acceptance']))}
        if len(links)!=len(set(links)) or not set(links)<=valid:
            raise ValueError('Selected task has invalid acceptance links: '+tid)
    if stage not in ('pre-merge','post-merge') or not isinstance(revision,str) or not revision.strip():raise ValueError('Stage and exact subject required')
    selected=set(scope['gates'])|({'G1','G2'} if stage=='pre-merge' else {'G3'})
    selected|={a for tid in scope['tasks'] for a in tasks[tid].get('acceptance_ids',[])}
    if selected-set(expected):raise ValueError('Selected task refers to unknown acceptance gate')
    chosen={key:expected[key] for key in sorted(selected)}
    subset='\n'.join(line for line in text.splitlines() if ROW.match(line) and ROW.match(line).group(1) in selected)
    found=problems(subset,stage,revision,chosen,target)
    smoke=operations(config)['smoke_gates']
    if stage=='post-merge' and smoke['post_merge_applicability']=='applicable' and rows.get('G3',{}).get('required')=='yes':
        recipe=smoke_checks(smoke).get('G3');kind=recipe['target']['kind'] if recipe else smoke['target_kind']
        planned=recipe['target']['value'] if recipe else smoke['deployed_url']
        if kind=='unconfirmed' or unresolved(target):found.append('Actual post-release target or target kind is unresolved')
        elif not unresolved(planned) and target!=planned:found.append('Actual post-release target differs from the configured target')
    for tid in scope['tasks']:
        events=[e for e in plan.get('events',[]) if e['task_id']==tid]
        if tasks[tid]['status']!='done' or not events or any(events[-1][k]!=v for k,v in (('status','done'),('result','passed'),('revision',revision))):
            found.append('Task '+tid+' lacks done/passed evidence for the exact subject')
    for tid in sorted(visited):
        if any(tasks[dep]['status']!='done' for dep in tasks[tid]['depends_on']):
            found.append('Task '+tid+' has incomplete dependencies')
    excluded=[{'gate':g,'stage':row['stage'],'required':row['required'],'result':row['result'],'revision':row['revision']} for g,row in rows.items() if g not in selected]
    excluded += [{'gate':g,'stage':spec['stage'],'required':'unknown','result':'MISSING','revision':''} for g,spec in expected.items() if g not in selected and g not in rows]
    waivers=[g+' WAIVED (recorded '+rows[g]['result']+')' for g in sorted(selected) if g in rows and rows[g]['stage']==stage and rows[g]['required']=='no']
    task_definitions=[{k:v for k,v in tasks[tid].items() if k!='status'} for tid in sorted(visited)]
    scope_bytes=json.dumps({'scope':scope,'task_definitions':task_definitions},sort_keys=True,ensure_ascii=True,separators=(',',':')).encode()
    manifest=(root/'manifest.json').read_bytes()
    scope_id=hashlib.sha256(str(root).encode()+b'\0'+manifest+b'\0'+scope_bytes).hexdigest()
    records=[{'gate':g,'planned_stage':expected[g]['stage'],'planned_design':expected[g]['design'],'recorded':rows.get(g)} for g in sorted(selected)]
    return {'scope_id':scope_id,'scope':scope,'stage':stage,'subject':revision,'assessment':'SCOPED BLOCKED' if found else 'SCOPED ELIGIBLE WITH WAIVERS' if waivers else 'SCOPED ELIGIBLE','problems':found,'waivers':waivers,'selected_records':records,'out_of_scope':excluded,'notice':'Only selected recorded claims were assessed; this is not project-wide readiness, execution, attestation or release authority.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--factory',required=True);p.add_argument('--scope',required=True);p.add_argument('--stage',choices=('pre-merge','post-merge'),required=True);p.add_argument('--revision',required=True);p.add_argument('--target');a=p.parse_args()
    scope=json.loads(safe_path(a.scope).read_text(encoding='utf-8-sig'))
    result=assess_scope(a.factory,scope,a.stage,a.revision,a.target)
    print(json.dumps(result,ensure_ascii=True,indent=2));return 1 if result['problems'] else 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError) as exc:print('ERROR: '+str(exc),file=sys.stderr);sys.exit(2)
