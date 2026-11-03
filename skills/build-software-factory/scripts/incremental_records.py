"""Preview and atomically record narrowly scoped living task or gate changes.

No evidence is independently verified. Use only with authorized stable local inputs.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import tempfile
from gates import gate_rows, problems, requirements, ROW
from scoped_assessment import load
from operations import operations, smoke_checks, unresolved
from integrity import check, strict_json

GATE_OBSERVATION_FIELDS=frozenset(('gate','result','revision','environment','evidence','target','checked_at','exit_status'))
MAX_BATCH_ITEMS=64
MAX_BATCH_INPUT_BYTES=262144
MAX_BATCH_FIELD_CHARS=8192


def _clean(value, label):
    if not isinstance(value,str) or not value.strip() or value!=value.strip() or '|' in value or not value.isprintable():
        raise ValueError(label+' must be nonempty single-line text without pipes')
    return value


def task_change(plan, config, item):
    keys={'id','goal','owner','depends_on','acceptance_ids','allowed_paths','status'}
    if not isinstance(item,dict) or set(item)!=keys:raise ValueError('Task must match the supported task schema')
    for key in ('id','goal','owner'):_clean(item[key],key)
    if item['status'] not in ('pending','blocked'):raise ValueError('New task must start pending or blocked')
    for key in ('depends_on','acceptance_ids','allowed_paths'):
        if not isinstance(item[key],list) or any(not isinstance(v,str) or not v.strip() for v in item[key]) or len(set(item[key]))!=len(item[key]):raise ValueError('Task '+key+' must be a unique string list')
        for value in item[key]:_clean(value,key)
    tasks={t['id']:t for t in plan['tasks']}
    if item['id'] in tasks:raise ValueError('Task ID already exists')
    if item['id'] in item['depends_on'] or set(item['depends_on'])-set(tasks):raise ValueError('Unknown or cyclic new-task dependency')
    graph={key:value.get('depends_on',[]) for key,value in tasks.items()};graph[item['id']]=item['depends_on']
    visited=set();active=set()
    def visit(key):
        if key not in graph:raise ValueError('Unknown existing task dependency')
        if key in active:raise ValueError('Cyclic task dependencies')
        if key in visited:return
        deps=graph[key]
        if not isinstance(deps,list) or any(not isinstance(v,str) for v in deps):raise ValueError('Malformed existing task dependencies')
        active.add(key)
        for dependency in deps:visit(dependency)
        active.remove(key);visited.add(key)
    for key in graph:visit(key)
    if not item['acceptance_ids'] or set(item['acceptance_ids'])-{f'A{i+1}' for i in range(len(config['acceptance']))}:raise ValueError('Task needs existing acceptance IDs')
    for path in item['allowed_paths']:
        p=PurePosixPath(path)
        if p.is_absolute() or '\\' in path or ':' in path or any(v in ('','..','.') for v in path.split('/')):raise ValueError('Unsafe allowed path')
    result=json.loads(json.dumps(plan));result['tasks'].append(item)
    return (json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode('utf-8')


def gate_change(text, config, research, change, review_text=None):
    mandatory=GATE_OBSERVATION_FIELDS
    if not isinstance(change,dict) or set(change)!=mandatory:raise ValueError('Gate observation must match the documented schema')
    gate=_clean(change['gate'],'gate');rows=gate_rows(text);expected=requirements(config,research)
    if gate not in rows or gate not in expected:raise ValueError('Gate must be an existing configured row')
    if change['result'] not in ('PASSED','FAILED','BLOCKED','NOT RUN'):raise ValueError('Unsupported observation result')
    for key in mandatory-{'gate','result'}:
        value=change[key]
        if not isinstance(value,str) or '|' in value or (value and not value.isprintable()):raise ValueError('Invalid '+key)
    old=rows[gate];line_index=None;lines=text.splitlines()
    for i,line in enumerate(lines):
        m=ROW.match(line)
        if m and m.group(1)==gate:
            if line_index is not None:raise ValueError('Duplicate gate row')
            line_index=i
    cells=[old['gate'],old['stage'],old['design'],change['environment'] or old['environment'],old['required'],change['revision'],change['result'],change['evidence'],change['target'],change['checked_at'],change['exit_status']]
    new='| '+' | '.join(cells)+' |';oldline=lines[line_index];lines[line_index]=new
    if oldline!=new:lines+=['','## Prior gate observation (not current evidence)','> '+oldline]
    result='\n'.join(lines)+'\n';gate_rows(result)
    if change['result']=='PASSED':
        selected={gate:expected[gate]};included={gate}
        if gate=='V1':selected['G3']=expected['G3'];included.add('G3')
        # Validate an observation even if the user chose to waive this row.
        checked_cells=list(cells);checked_cells[4]='yes'
        checked_line='| '+' | '.join(checked_cells)+' |'
        subset='\n'.join(checked_line if ROW.match(line) and ROW.match(line).group(1)==gate else line for line in result.splitlines() if ROW.match(line) and ROW.match(line).group(1) in included)
        issues=problems(subset,old['stage'],change['revision'],selected,change['target'] if old['stage']=='post-merge' else None,review_text)
        if old['stage']=='post-merge' and rows.get('G3',{}).get('required')=='yes':
            smoke=operations(config)['smoke_gates'];recipe=smoke_checks(smoke).get('G3')
            planned=recipe['target']['value'] if recipe else smoke['deployed_url']
            kind=recipe['target']['kind'] if recipe else smoke['target_kind']
            if kind=='unconfirmed' or unresolved(change['target']):issues.append('Actual post-release target or target kind is unresolved')
            elif not unresolved(planned) and planned!=change['target']:issues.append('Actual post-release target differs from configured target')
        if issues:raise ValueError('Observation does not satisfy gate rules: '+'; '.join(issues))
    return result.encode('utf-8')


def gate_batch_change(text, config, research, changes, review_text=None):
    """Validate the whole explicit batch, then reuse the single-observation writer."""
    if not isinstance(changes,list) or not 1<=len(changes)<=MAX_BATCH_ITEMS:
        raise ValueError('Gate batch must be a nonempty array of at most 64 observations')
    gates=set();subjects=set()
    rows=gate_rows(text);expected=requirements(config,research)
    for change in changes:
        if not isinstance(change,dict) or len(change)!=len(GATE_OBSERVATION_FIELDS) or set(change)!=GATE_OBSERVATION_FIELDS:
            raise ValueError('Every batch observation must match the existing gate observation schema')
        if any(not isinstance(value,str) or len(value)>MAX_BATCH_FIELD_CHARS for value in change.values()):
            raise ValueError('Batch observation fields must be strings of at most 8192 characters')
        gate=_clean(change['gate'],'Batch gate');subject=_clean(change['revision'],'Batch revision')
        if unresolved(subject):raise ValueError('Batch revision must identify a concrete subject, not an unresolved placeholder')
        if gate in gates:raise ValueError('Duplicate gate in batch; supply exactly one observation per gate')
        if gate not in rows or gate not in expected:raise ValueError('Every batch gate must be an existing configured row')
        gates.add(gate);subjects.add(subject)
    if len(subjects)!=1:raise ValueError('Batch observations must share one exact nonempty subject; mixed subjects are not accepted')
    # Bound direct API inputs too; individual strings and item count were bounded
    # before serialization. This is data, never interpreted as a command or report.
    encoded_size=0
    for chunk in json.JSONEncoder(ensure_ascii=True).iterencode(changes):
        encoded_size+=len(chunk)
        if encoded_size>MAX_BATCH_INPUT_BYTES:
            raise ValueError('Serialized gate batch exceeds the 256 KiB input limit')
    if {'G3','V1'}<=gates:
        raise ValueError('G3 and V1 require separate reviewed recording steps; V1 must use an existing G3 record. Existing G3 waivers remain respected')
    # Sorting stabilizes output/digests, not execution chronology. Keep supplied
    # timestamps and let gate_change validate each PASSED claim against the records.
    result=text
    for change in sorted(changes,key=lambda item:item['gate']):
        result=gate_change(result,config,research,change,review_text).decode('utf-8')
    return result.encode('utf-8')


def read_gate_batch(path):
    """Bound a regular input before reading or strict JSON parsing; reveal no values."""
    try:
        path=safe_factory(path);before=path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_BATCH_INPUT_BYTES:
            raise ValueError('Gate batch input must be a regular file of at most 256 KiB')
        with path.open('rb') as stream:raw=stream.read(MAX_BATCH_INPUT_BYTES+1)
        after=path.lstat()
        if len(raw)>MAX_BATCH_INPUT_BYTES or len(raw)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
            raise ValueError('Gate batch input changed or exceeded the size limit')
        return strict_json(raw.decode('utf-8-sig'))
    except (UnicodeError,RecursionError) as exc:
        raise ValueError('Gate batch input is not valid bounded JSON') from exc


def preview(factory, kind, data):
    if kind not in ('task','gate','gate-batch','review'):raise ValueError('Unknown record kind')
    root=safe_factory(factory)
    check(root,quiet=True)
    before=inventory(root)
    root,config,research,text,plan=load(root)
    if inventory(root)!=before:raise ValueError('Factory changed during preview')
    review_text=None
    if 'record_schema' in operations(config)['review']:
        from review_records import MAX_HANDOFF
        if len(before['release-handoff.md'])>MAX_HANDOFF:raise ValueError('Review handoff exceeds the byte limit')
        review_text=before['release-handoff.md'].decode('utf-8-sig')
    name='task-plan.json' if kind=='task' else 'release-handoff.md' if kind=='review' else 'verification.md'
    if kind=='review':
        if review_text is None:raise ValueError('Review recording requires explicit review-workflow adoption')
        from review_records import append_round
        after=append_round(review_text,data)
    else:
        after=task_change(plan,config,data) if kind=='task' else gate_batch_change(text,config,research,data,review_text) if kind=='gate-batch' else gate_change(text,config,research,data,review_text)
    h=hashlib.sha256();h.update(str(root).encode());h.update(b'\0'+name.encode())
    for key in sorted(before):h.update(b'\0'+key.encode()+b'\0'+hashlib.sha256(before[key]).digest())
    h.update(b'\0'+hashlib.sha256(after).digest())
    return root,name,before,after,h.hexdigest()

def safe_factory(factory):
    from integrity import safe_path
    return safe_path(factory)

def inventory(root, exclude_lock=False):
    result={}
    for path in root.rglob('*'):
        if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
            raise ValueError('Redirected path inside factory')
        if path.is_file():
            name=path.relative_to(root).as_posix()
            if exclude_lock and name=='.factory-status.lock':continue
            result[name]=path.read_bytes()
    return result


def apply(root,name,before,after,token,approved):
    if approved!=token:raise ValueError('Apply requires the exact reviewed preview digest')
    check(root,quiet=True)
    lock=root/'.factory-status.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    temp=None
    try:
        if inventory(root,exclude_lock=True)!=before:raise ValueError('Factory changed since preview; nothing written')
        with tempfile.NamedTemporaryFile(mode='wb',prefix='.record-',dir=root,delete=False) as stream:
            temp=Path(stream.name)
            if stream.write(after)!=len(after):raise OSError('Incomplete record write')
            stream.flush();os.fsync(stream.fileno())
        os.replace(temp,root/name)
    finally:
        if temp is not None and temp.exists():temp.unlink()
        lock.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--factory',required=True);p.add_argument('--kind',choices=('task','gate','gate-batch','review'),required=True,help='gate-batch records a bounded array for one exact subject; G3/V1 need separate steps. review appends one immutable supplied round; Q1 needs a separate gate observation');p.add_argument('--input',required=True);p.add_argument('--apply',action='store_true');p.add_argument('--approve-plan');a=p.parse_args()
    data=read_gate_batch(a.input) if a.kind in ('gate-batch','review') else strict_json(Path(a.input).read_text(encoding='utf-8-sig'))
    root,name,before,after,token=preview(a.factory,a.kind,data)
    if a.apply:
        apply(root,name,before,after,token,a.approve_plan);print('RECORDED operator-supplied data; no checks were executed or attested.')
    else:
        print(''.join(difflib.unified_diff(before[name].decode('utf-8-sig').splitlines(True),after.decode().splitlines(True),fromfile=name,tofile=name)))
        print('REVIEW PLAN: '+token+' (preview only; no files written)')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:print('ERROR: '+str(exc),file=sys.stderr);sys.exit(1)
