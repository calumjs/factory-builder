"""Private, read-only three-way evidence proposal; never apply or attest records."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
sys.dont_write_bytecode=True

from acceptance_links import bounded, guarded_path, snapshot_factory, validate_snapshot
from gates import HEADER, ROW, gate_rows, requirements, observed_time, policy_controls, control_differences
from integrity import strict_json, validate_task_plan
from learning_table import LEARNING_HEADER, learning_cells, validate_learning_log
from operations import controls, unresolved
from research import validate_research
from scaffold import validate
from status import STATUSES, RESULTS

RECORDS=('verification.md','task-plan.json','learning-log.md')
SIDES=('base','left','right')
HISTORY_HEADINGS=frozenset(('## Prior gate observation (not current evidence)',
                          '## Historical observations (not current evidence)'))
MAX_RECORD=2_000_000
MAX_REPORT=32_000_000
MAX_ROWS=4096
NOTICE=('PRIVATE PREVIEW ONLY: supplied claims are not verified. No files were written, '
        'no approval was applied, and no reservation, merge or distributed concurrency guarantee exists. '
        'Selected subject is an assessment intention, not evidence rebinding or readiness.')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def encoded(value):return (json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'))+'\n').encode()


class ReconcileError(ValueError):
    """Fixed diagnostic text, never interpolated source values."""


def require(condition,message):
    if not condition:raise ReconcileError(message)


def label(value,limit=8192):
    return isinstance(value,str) and bool(value.strip()) and len(value)<=limit and '\0' not in value


def fingerprint(root,identity,files,directories):
    return sha(encoded({'root':str(root),'root_identity':identity,'directories':directories,
                        'files':{name:sha(raw) for name,raw in sorted(files.items())}}))


def capture(root):
    root=guarded_path(root)
    require(root.is_dir(),'Each source must be an existing factory directory')
    before=root.stat();identity=(before.st_dev,before.st_ino)
    files,directories=snapshot_factory(root)
    after=guarded_path(root).stat()
    require(identity==(after.st_dev,after.st_ino),'Source root identity changed during capture')
    validate_snapshot(files)
    return {'root':root,'files':files,'directories':directories,
            'sha256':fingerprint(root,identity,files,directories)}


def text(raw):
    require(len(raw)<=MAX_RECORD,'Evidence record exceeds the byte limit')
    body=raw.decode('utf-8-sig')
    require('\r' not in body.replace('\r\n',''),'Lone carriage returns require separate record review')
    return body


def gate_document(raw):
    """Only the generated current table and explicit quoted-history blocks are supported."""
    body=text(raw);lines=body.splitlines(keepends=True)
    rows={};current={};history=[];skeleton=[];table=False;historical=False;headers=0
    separator=False
    for index,raw_line in enumerate(lines):
        line=raw_line.rstrip('\r\n');stripped=line.lstrip()
        require(not stripped.startswith(('```','~~~','<!--')) and '-->' not in line,
                'Fenced or commented gate documents require separate review')
        if line in HISTORY_HEADINGS:
            historical=True;table=False;continue
        if line.startswith('## '):historical=False;table=False
        if line==HEADER.splitlines()[0]:
            headers+=1;require(headers==1,'Exactly one current gate table is supported')
            separator=True;table=True;historical=False;skeleton.append(line);continue
        if separator:
            require(line==HEADER.splitlines()[1],'The current gate table delimiter is unsupported')
            separator=False;skeleton.append(line);continue
        if stripped.startswith('>') and '|' in stripped:
            require(historical and line.startswith('> |') and ROW.match(line[2:]),
                    'Only explicit quoted gate-history rows are supported')
            parsed=gate_rows(line[2:]);require(len(parsed)==1,'Malformed quoted gate observation')
            history.append(line[2:]);continue
        match=ROW.match(stripped)
        if match:
            require(table and stripped==line,'Gate rows outside the current table require review')
            row=gate_rows(line)[match[1]]
            require(match[1] not in rows,'Duplicate current gate ID')
            rows[match[1]]=row;current[match[1]]=(index,line)
            continue
        if table:
            require(not line.startswith('|'),'Malformed current gate row')
            table=False
        if line.strip():skeleton.append(line)
    require(headers==1 and not separator and rows,'Missing current gate table')
    require(len(rows)+len(history)<=MAX_ROWS,'Gate observation limit exceeded')
    return {'lines':lines,'rows':rows,'current':current,'history':history,'skeleton':skeleton}


def task_document(raw,config):
    plan=strict_json(text(raw));require(isinstance(plan,dict) and set(plan)=={'tasks','events'},
                                      'Only the supported task/event schema is reconciled')
    validate_task_plan(plan)
    require(isinstance(plan['events'],list) and len(plan['tasks'])+len(plan['events'])<=MAX_ROWS,
            'Task/event inventory exceeds its bound')
    tasks={};events={}
    fields={'id','goal','owner','depends_on','acceptance_ids','allowed_paths','status'}
    acceptance={f'A{i+1}' for i in range(len(config['acceptance']))}
    for task in plan['tasks']:
        require(set(task)==fields and all(label(task[k]) for k in ('id','goal','owner')) and task['status'] in STATUSES,
                'Unsupported task definition or status')
        for key in ('depends_on','acceptance_ids','allowed_paths'):
            values=task[key]
            require(isinstance(values,list) and all(label(v) for v in values) and len(values)==len(set(values)),
                    'Malformed task references')
        require(task['acceptance_ids'] and set(task['acceptance_ids'])<=acceptance,'Unknown task acceptance reference')
        for path in task['allowed_paths']:
            require(not PurePosixPath(path).is_absolute() and '\\' not in path and ':' not in path
                    and not any(part in ('','.','..') for part in path.split('/')),'Unsafe task allowed path')
        tasks[task['id']]=task
    active=set();done=set()
    def visit(tid):
        require(tid in tasks and tid not in active,'Unknown or cyclic task dependency')
        if tid in done:return
        active.add(tid)
        for dependency in tasks[tid]['depends_on']:visit(dependency)
        active.remove(tid);done.add(tid)
    for tid in tasks:visit(tid)
    event_fields={'id','task_id','timestamp','revision','environment','check','result','evidence','old_status','status'}
    for event in plan['events']:
        require(set(event)==event_fields and all(label(value) for value in event.values()),'Unsupported event schema')
        require(event['id'] not in events,'Duplicate event ID within a source')
        require(event['status'] in STATUSES and event['old_status'] in STATUSES and event['result'] in RESULTS,
                'Unsupported event status or result')
        require(event['status']!='done' or event['result']=='passed','Done event without recorded passing result')
        observed_time(event['timestamp'])
        events[event['id']]=event
    return {'plan':plan,'tasks':tasks,'events':events}


def learn_document(raw):
    body=text(raw);validate_learning_log(body);lines=body.splitlines(keepends=True)
    starts=[i for i,line in enumerate(lines) if tuple(learning_cells(line))==LEARNING_HEADER]
    require(len(starts)==1,'Exactly one generated Learn table is supported')
    require(not any(line.lstrip().startswith(('```','~~~','<!--')) for line in lines),
            'Fenced or commented Learn tables require separate review')
    start=starts[0]
    require(start+1<len(lines),'Learn table delimiter is missing')
    cells=learning_cells(lines[start+1])
    require(len(cells)==7 and all(re.fullmatch(':?-+:?',cell) for cell in cells),'Unsupported Learn delimiter')
    end=start+2;rows=[]
    while end<len(lines) and lines[end].strip() and '|' in lines[end]:
        require(lines[end].startswith('|') and len(learning_cells(lines[end]))==7,'Unsupported Learn row shape')
        rows.append(lines[end].rstrip('\r\n'));end+=1
    require(len(rows)<=MAX_ROWS,'Learn row limit exceeded')
    return {'prefix':lines[:start+2],'rows':rows,'suffix':lines[end:]}


def prefix(base,side,message):require(side[:len(base)]==base,message)


def choice_options(values):
    return {side:{'sha256':sha(encoded(value)),'value':value} for side,value in values.items()}


def decide(kind,key,options,decisions):
    chosen=decisions[kind][key]
    require(isinstance(chosen,dict) and set(chosen)=={'source','sha256','reason'},'Choice must name source, exact value hash and reason')
    require(chosen['source'] in SIDES and label(chosen['reason'],500),'Choice source or reason is unsupported')
    selected=options[chosen['source']]
    require(chosen['sha256']==selected['sha256'],'Choice value is stale or mismatched')
    return chosen['source']


def derive(sources,subject,decisions=None,decision_sha256=None):
    files={side:sources[side]['files'] for side in SIDES};base=files['base']
    for side in ('left','right'):
        require(set(files[side])==set(base),'Source inventories differ')
        require(all(files[side][name]==raw for name,raw in base.items() if name not in RECORDS),
                'Contracts or unhandled living records differ; reconcile their deliberate choices separately')
    config=strict_json(base['config.json'].decode('utf-8-sig'));validate(config)
    research=strict_json(base['research.json'].decode('utf-8-sig'));validate_research(research)
    require(not control_differences(policy_controls(base['policy.md'].decode('utf-8-sig').replace('\r\n','\n')),controls(config)),
            'Configuration and policy controls disagree')
    gates={side:gate_document(files[side]['verification.md']) for side in SIDES}
    tasks={side:task_document(files[side]['task-plan.json'],config) for side in SIDES}
    learn={side:learn_document(files[side]['learning-log.md']) for side in SIDES}
    expected=requirements(config,research);base_gates=gates['base'];base_tasks=tasks['base'];base_learn=learn['base']
    require(set(base_gates['rows'])==set(expected),'Unknown or missing configured gate IDs')
    require(all(row['stage']==expected[gate]['stage'] for gate,row in base_gates['rows'].items()),
            'Current gate stages disagree with configured stages')
    for side in ('left','right'):
        require(set(gates[side]['rows'])==set(base_gates['rows']),'Current gate IDs differ')
        require(gates[side]['skeleton']==base_gates['skeleton'],'Non-history verification prose differs')
        prefix(base_gates['history'],gates[side]['history'],'Base gate history was removed, reordered or modified')
        for gate,row in base_gates['rows'].items():
            require(all(row[key]==gates[side]['rows'][gate][key] for key in ('stage','design','required')),
                    'Gate plan or requiredness differs; preserve both versions and reconcile deliberate choices separately')
        require(set(tasks[side]['tasks'])==set(base_tasks['tasks']),'Task IDs differ; task registration is outside reconciliation')
        for tid,task in base_tasks['tasks'].items():
            require({k:v for k,v in task.items() if k!='status'}=={k:v for k,v in tasks[side]['tasks'][tid].items() if k!='status'},
                    'Task definitions differ; reconcile scope separately')
        prefix(base_tasks['plan']['events'],tasks[side]['plan']['events'],'Base events were removed, reordered or modified')
        require(learn[side]['prefix']==base_learn['prefix'] and learn[side]['suffix']==base_learn['suffix'],
                'Learn prose or footer differs')
        prefix(base_learn['rows'],learn[side]['rows'],'Base Learn rows were removed, reordered or modified')
    events=list(base_tasks['plan']['events']);known=dict(base_tasks['events']);event_origins=[]
    for side in ('left','right'):
        for event in tasks[side]['plan']['events'][len(base_tasks['plan']['events']):]:
            if event['id'] in known:require(event==known[event['id']],'Conflicting payloads use the same event ID')
            else:known[event['id']]=event;events.append(event)
            event_origins.append({'source':side,'event_id':event['id']})
    gate_options={};task_options={}
    for gate in base_gates['rows']:
        values={side:gates[side]['current'][gate][1] for side in SIDES}
        if len(set(values.values()))>1:gate_options[gate]=choice_options(values)
    for tid in base_tasks['tasks']:
        values={side:tasks[side]['tasks'][tid]['status'] for side in SIDES}
        if len(set(values.values()))>1:task_options[tid]=choice_options(values)
    source_hashes={side:sources[side]['sha256'] for side in SIDES}
    report={'schema':1,'status':'NEEDS_DECISIONS','subject':subject,'sources':source_hashes,
            'options':{'current_rows':gate_options,'task_statuses':task_options},'notice':NOTICE,
            'learn_rule':'Base once, then every left and right append occurrence, including identical text; row positions are provenance, not persistent IDs.',
            'event_order':'Base, left additions, right unique-ID additions; serialization order is not execution chronology.'}
    if decisions is None:return report
    require(isinstance(decisions,dict) and set(decisions)=={'schema','sources','subject','current_rows','task_statuses'}
            and type(decisions['schema']) is int and decisions['schema']==1,'Unsupported decision schema')
    require(decisions['sources']==source_hashes and decisions['subject']==subject,'Decisions bind different or stale sources/subject')
    for name,options in (('current_rows',gate_options),('task_statuses',task_options)):
        require(isinstance(decisions[name],dict) and set(decisions[name])==set(options),'Missing, unknown or stale decision keys')
    selected={};conflicts=[]
    for gate,options in gate_options.items():
        side=decide('current_rows',gate,options,decisions);row=gates[side]['rows'][gate]
        if row['required']=='yes' and row['revision']!=subject and not (not row['revision'] and row['result']=='NOT RUN'):
            conflicts.append({'record':'verification.md','id':gate,'reason':'Chosen changed row does not bind the selected subject; preserve it as history or supply an exact-subject source observation'})
        selected[gate]=side
    statuses={tid:task['status'] for tid,task in base_tasks['tasks'].items()}
    for tid,options in task_options.items():statuses[tid]=options[decide('task_statuses',tid,options,decisions)]['value']
    for tid,task in base_tasks['tasks'].items():
        if statuses[tid]=='done' and any(statuses[dep]!='done' for dep in task['depends_on']):
            conflicts.append({'record':'task-plan.json','id':tid,'reason':'Selected done status has a dependency not selected done; no synthetic status or event is generated'})
    if conflicts:report.update(status='CONFLICT',conflicts=conflicts);return report
    lines=list(base_gates['lines']);current_values={}
    for gate,(index,line) in base_gates['current'].items():
        source=selected.get(gate,'base');value=gates[source]['current'][gate][1];current_values[gate]=value
        ending='\r\n' if lines[index].endswith('\r\n') else '\n' if lines[index].endswith('\n') else ''
        lines[index]=value+ending
    history=[];history_origins=[]
    for side in ('left','right'):
        for index,line in enumerate(gates[side]['history'][len(base_gates['history']):],len(base_gates['history'])):
            history.append(line);history_origins.append({'source':side,'history_index':index})
    represented=set(base_gates['history']+history+list(current_values.values()))
    for side in SIDES:
        for gate,(_,line) in gates[side]['current'].items():
            if line not in represented:
                history.append(line);represented.add(line);history_origins.append({'source':side,'current_gate':gate})
    verification=''.join(lines)
    if history:verification=verification.rstrip('\r\n')+'\n\n## Prior gate observation (not current evidence)\n'+'\n'.join('> '+line for line in history)+'\n'
    gate_document(verification.encode())
    task_plan={'tasks':[dict(task,status=statuses[task['id']]) for task in base_tasks['plan']['tasks']],'events':events}
    task_bytes=(json.dumps(task_plan,ensure_ascii=False,indent=2)+'\n').encode();task_document(task_bytes,config)
    learn_rows=list(base_learn['rows']);learn_origins=[{'source':'base','row_index':i} for i in range(len(learn_rows))]
    for side in ('left','right'):
        for index,line in enumerate(learn[side]['rows'][len(base_learn['rows']):],len(base_learn['rows'])):
            learn_rows.append(line);learn_origins.append({'source':side,'row_index':index})
    learning=''.join(base_learn['prefix'])+''.join(row+'\n' for row in learn_rows)+''.join(base_learn['suffix'])
    learn_document(learning.encode())
    proposed={'verification.md':verification.encode(),'task-plan.json':task_bytes,'learning-log.md':learning.encode()}
    require(all(len(raw)<=MAX_RECORD for raw in proposed.values()),'Merged record exceeds its bound')
    candidate={**base,**proposed};validate_snapshot(candidate)
    binding={'sources':source_hashes,'decisions':decisions,'decision_bytes':decision_sha256,'proposed':{name:sha(raw) for name,raw in proposed.items()}}
    report.update(status='PROPOSED',plan_sha256=sha(encoded(binding)),decisions_sha256=decision_sha256,
                  proposed={name:{'sha256':sha(raw),'utf8':raw.decode()} for name,raw in proposed.items()},
                  diffs={name:''.join(difflib.unified_diff(base[name].decode('utf-8-sig').splitlines(True),raw.decode().splitlines(True),fromfile=name+' (base)',tofile=name+' (proposed)')) for name,raw in proposed.items()},
                  history_origins=history_origins,event_origins=event_origins,learn_origins=learn_origins,
                  current_rows_outside_subject=[gate for gate,line in current_values.items() if gate_rows(line)[gate]['revision']!=subject],
                  task_status_notice='Task statuses are explicit copied side values; underlying event revisions remain unchanged and are not rebound to the selected subject.')
    return report


def review(base,left,right,subject,decision_path=None):
    require(label(subject,256) and subject==subject.strip() and subject.isprintable() and not unresolved(subject),
            'An explicit concrete selected subject is required')
    for value in (base,left,right,decision_path):
        if value is not None:require('..' not in Path(value).parts,'Parent traversal paths are unsupported')
    roots={side:guarded_path(value) for side,value in zip(SIDES,(base,left,right))}
    for i,side in enumerate(SIDES):
        for other in SIDES[i+1:]:
            a,b=roots[side],roots[other]
            require(a!=b and a not in b.parents and b not in a.parents and not a.samefile(b),
                    'Sources must be distinct, non-nested directories without same-file aliases')
    decision_root=guarded_path(decision_path) if decision_path is not None else None
    if decision_root is not None:
        require(all(decision_root!=root and root not in decision_root.parents for root in roots.values()),
                'Decision input must be outside source snapshots')
    decision_raw=bounded(decision_root) if decision_root is not None else None
    decisions=strict_json(decision_raw.decode('utf-8-sig')) if decision_raw is not None else None
    sources={side:capture(root) for side,root in roots.items()}
    result=derive(sources,subject,decisions,sha(decision_raw) if decision_raw is not None else None)
    for side,root in roots.items():
        require(capture(root)['sha256']==sources[side]['sha256'],'Source changed during preview; no proposal is usable')
    if decision_root is not None:require(bounded(decision_root)==decision_raw,'Decisions changed during preview')
    return result


class PrivateArguments(argparse.ArgumentParser):
    def error(self,message):self.exit(2,'ERROR: invalid reconciliation arguments; use --help. No proposal was emitted.\n')


def main(argv=None):
    parser=PrivateArguments(description=__doc__)
    for key in ('base','left','right','subject'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--decisions',help='Strict source-bound choices outside the snapshots; omit to inspect needed decisions')
    args=parser.parse_args(argv)
    try:
        report=review(args.base,args.left,args.right,args.subject,args.decisions)
        chunks=[];size=0
        for chunk in json.JSONEncoder(ensure_ascii=True,indent=2).iterencode(report):
            size+=len(chunk);require(size<=MAX_REPORT,'Reconciliation report exceeds its bound');chunks.append(chunk)
    except ReconcileError as exc:
        print('ERROR: '+str(exc)+'. No proposal was emitted and no files were written.',file=sys.stderr)
        return 2
    except (ValueError,OSError,UnicodeError,TypeError,KeyError,OverflowError,RecursionError):
        print('ERROR: unsafe, malformed, unsupported, conflicting or changed evidence inputs; preserve all sources and reconcile deliberate plan/waiver choices separately. No proposal was emitted and no files were written.',file=sys.stderr)
        return 2
    print(''.join(chunks))
    return 0 if report['status']=='PROPOSED' else 1


if __name__=='__main__':raise SystemExit(main())
