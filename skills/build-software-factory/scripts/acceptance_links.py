"""Read-only, opt-in G3 acceptance trace claims; never verifies or changes gates."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
sys.dont_write_bytecode = True

from gates import gate_rows, observed_time, policy_controls, post_target_problems, problems, requirements
from integrity import LIVING, digest, safe_path, validate_task_plan
from assumptions import assumptions
from operations import controls, operations, smoke_checks, unresolved

MAX_FILE = 2_000_000
MAX_TOTAL = 32_000_000
MAX_ENTRIES = 2048
MAX_DEPTH = 20
MAX_LINKS = 500
NOTICE = 'TRACE ONLY — NOT READINESS OR PROOF. Supplied claims and references are not independently verified.'


class TraceInputError(ValueError):
    """Fixed diagnostic text safe to return without echoing input contents."""


def guarded_path(value):
    if str(value).replace('/','\\').startswith(('\\\\?\\','\\\\.\\','\\??\\')):
        raise TraceInputError('Device namespace paths are unsupported')
    path=safe_path(value)
    for node in (path,*path.parents):
        try:metadata=node.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata,'st_file_attributes',0)&0x400:
            raise TraceInputError('Redirected paths are unsupported')
    return path


def bounded(path):
    path=guarded_path(path);before=path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_FILE:
        raise TraceInputError('Input must be a bounded regular file')
    with path.open('rb') as stream:data=stream.read(MAX_FILE+1)
    after=path.lstat()
    if len(data)>MAX_FILE or len(data)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise TraceInputError('Input changed or exceeded the size limit')
    return data


def strict_json(data):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    def constant(_):raise ValueError('Non-finite JSON number')
    try:return json.loads(data.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=constant)
    except (UnicodeError,ValueError,RecursionError) as exc:raise TraceInputError('Invalid or duplicate-key JSON') from exc


def snapshot_factory(root):
    """Bounded regular-file inventory; never parse inputs before size checks."""
    files={};directories=[];total=0;count=0
    def visit(directory,relative='',depth=0):
        nonlocal total,count
        if depth>MAX_DEPTH:raise TraceInputError('Factory directory depth limit exceeded')
        with os.scandir(directory) as entries:
            for entry in entries:
                count+=1
                if count>MAX_ENTRIES:raise TraceInputError('Factory entry limit exceeded')
                path=Path(entry.path);name=(relative+'/' if relative else '')+entry.name
                meta=path.lstat()
                if stat.S_ISLNK(meta.st_mode) or getattr(meta,'st_file_attributes',0)&0x400 or (hasattr(path,'is_junction') and path.is_junction()):
                    raise TraceInputError('Redirected factory path is unsupported')
                if stat.S_ISDIR(meta.st_mode):
                    directories.append(name);visit(path,name,depth+1)
                elif stat.S_ISREG(meta.st_mode):
                    data=bounded(path);total+=len(data)
                    if total>MAX_TOTAL:raise TraceInputError('Factory total size limit exceeded')
                    files[name]=data
                else:raise TraceInputError('Factory contains a non-regular entry')
    visit(root)
    return files,sorted(directories)


def validate_snapshot(files):
    """Validate factory integrity using captured bytes, not reopened inputs."""
    if 'manifest.json' not in files:raise TraceInputError('Factory manifest is missing')
    manifest=strict_json(files['manifest.json'])
    if not isinstance(manifest,dict) or manifest.get('schema')!=2 or manifest.get('hash_mode')!='utf8-lf' or not isinstance(manifest.get('contracts'),dict) or not isinstance(manifest.get('living'),list):
        raise TraceInputError('Unsupported factory manifest')
    names=list(manifest['contracts'])+manifest['living']
    if any(not isinstance(n,str) for n in names) or len(names)!=len(set(names)) or set(manifest['living'])!=LIVING:
        raise TraceInputError('Invalid factory contract/living classification')
    for name in names:
        parts=PurePosixPath(name)
        if parts.is_absolute() or '\\' in name or ':' in name or any(v in ('..','.','') for v in name.split('/')):
            raise TraceInputError('Unsafe factory manifest path')
    if set(files)-{'manifest.json'}!=set(names):raise TraceInputError('Factory file set differs from manifest')
    for name,expected in manifest['contracts'].items():
        if digest(files[name])!=expected:raise TraceInputError('Factory contract integrity mismatch')
        if name.endswith('.json'):strict_json(files[name])
    for name in manifest['living']:
        try:files[name].decode('utf-8-sig')
        except UnicodeError as exc:raise TraceInputError('Living factory record is not valid UTF-8') from exc
        if name.endswith('.json'):
            value=strict_json(files[name])
            if name=='task-plan.json':validate_task_plan(value)
            elif not isinstance(value,dict):raise TraceInputError('Invalid living tool registry')
    from learning_table import validate_learning_log
    validate_learning_log(files['learning-log.md'].decode('utf-8-sig'))
    assumptions(strict_json(files['config.json']))


def text(value, *, empty=False):
    return isinstance(value,str) and len(value)<=2000 and (not value if empty else bool(value.strip())) and (not value or value.isprintable())


def assess_links(factory, sidecar, subject, target):
    root=guarded_path(os.path.abspath(guarded_path(factory)))
    path=guarded_path(os.path.abspath(guarded_path(sidecar)))
    if path==root or root in path.parents or any(parent.exists() and parent.samefile(root) for parent in path.parents):
        raise TraceInputError('Trace record must be outside the factory')
    if unresolved(subject) or unresolved(target) or not text(subject) or not text(target):
        raise TraceInputError('Explicit concrete subject and actual target are required')
    files,directories=snapshot_factory(root)
    validate_snapshot(files)
    names=('manifest.json','config.json','research.json','policy.md','verification.md')
    before={name:files[name] for name in names};raw=bounded(path)
    config=strict_json(before['config.json']);research=strict_json(before['research.json'])
    try:
        policy=policy_controls(before['policy.md'].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))
    except (ValueError,RecursionError) as exc:raise TraceInputError('Factory policy controls are malformed') from exc
    if json.dumps(policy,sort_keys=True)!=json.dumps(controls(config),sort_keys=True):
        raise ValueError('Configuration and policy controls disagree')
    record=strict_json(raw)
    if not isinstance(record,dict) or set(record)!={'schema_version','gate','subject','target','links'} or type(record['schema_version']) is not int or record['schema_version']!=1 or record['gate']!='G3':
        raise TraceInputError('Unsupported trace record schema or version')
    if not text(record['subject']) or not text(record['target']) or unresolved(record['subject']) or unresolved(record['target']):
        raise TraceInputError('Trace record needs a concrete subject and target')
    links=record['links']
    if not isinstance(links,list) or not 1<=len(links)<=MAX_LINKS:raise TraceInputError('Trace links must be a bounded nonempty list')
    expected=requirements(config,research);rows=gate_rows(before['verification.md'].decode('utf-8-sig'))
    seen=set();out=[]
    for link in links:
        if not isinstance(link,dict) or set(link)!={'acceptance_id','result','evidence','observed_at'}:
            raise TraceInputError('Invalid trace link fields')
        ident=link['acceptance_id']
        if not isinstance(ident,str) or re.fullmatch(r'A[1-9][0-9]*',ident) is None or ident in seen or ident not in expected or ident not in rows:
            raise TraceInputError('Unknown, malformed, missing or duplicate acceptance ID')
        seen.add(ident);canonical=rows[ident]
        if canonical['stage']!=expected[ident]['stage']:raise TraceInputError('Acceptance row stage differs from configured stage')
        if link['result'] not in ('PASSED','FAILED','BLOCKED','NOT RUN'):
            raise TraceInputError('Invalid linked observation result')
        evidence=link['evidence'];stamp=link['observed_at']
        if not (text(evidence) or text(evidence,empty=True)) or not (text(stamp) or text(stamp,empty=True)):
            raise TraceInputError('Invalid trace evidence or timestamp')
        if stamp:
            try:observed_time(stamp)
            except (ValueError,TypeError,OverflowError) as exc:raise TraceInputError('Trace timestamp requires a valid timezone') from exc
        evidence_present=not unresolved(evidence) and evidence.strip().casefold() not in ('not run','todo')
        if link['result']=='PASSED' and (not evidence_present or not stamp):
            raise TraceInputError('A recorded PASSED claim requires evidence and observation time')
        out.append({'acceptance_id':ident,'canonical':{'stage':canonical['stage'],'required':canonical['required'],
                    'state':'WAIVED' if canonical['required']=='no' else canonical['result'],
                    'recorded_result':canonical['result'],'revision':canonical['revision']},
                    'linked_claim':{'result':link['result'],'evidence_supplied':evidence_present,
                    'observed_at':stamp or None,'state':'UNCONFIRMED' if link['result']=='NOT RUN' or not evidence_present else 'SUPPLIED CLAIM — NOT VERIFIED'}})
    g3=rows.get('G3');spec=expected['G3'];binding=[]
    if record['subject']!=subject or record['target']!=target:binding.append('Trace envelope differs from explicit subject or target')
    if not g3 or g3['stage']!='post-merge':binding.append('G3 row missing or wrong stage')
    elif g3['revision']!=subject or g3['target']!=target:binding.append('G3 row differs from explicit subject or target')
    smoke=operations(config)['smoke_gates'];recipe=smoke_checks(smoke).get('G3')
    kind=recipe['target']['kind'] if recipe else smoke['target_kind']
    planned=recipe['target']['value'] if recipe else smoke['deployed_url']
    gate_issues=post_target_problems(kind,planned,target) if spec['applicability']=='applicable' and g3 and g3['required']=='yes' else []
    if g3:
        line='| '+' | '.join(g3[k] for k in ('gate','stage','design','environment','required','revision','result','evidence','target','checked_at','exit_status'))+' |'
        gate_issues+=problems(line,'post-merge',subject,{'G3':spec},target)
    positive=bool(g3 and spec['applicability']=='applicable' and g3['required']=='yes' and g3['result']=='PASSED' and not gate_issues and not binding)
    after,after_directories=snapshot_factory(root)
    if after!=files or after_directories!=directories or bounded(path)!=raw:
        raise TraceInputError('Inputs changed during assessment')
    return {'notice':NOTICE,'requested_context':{'subject':subject,'target':target},
            'recorded_envelope':{'subject':record['subject'],'target':record['target']},'scope':[entry['acceptance_id'] for entry in out],
            'binding_errors':binding,'g3':{'state':'MISSING' if not g3 else 'WAIVED' if g3['required']=='no' else g3['result'],
            'recorded_result':None if not g3 else g3['result'],'applicability':spec['applicability'],
            'recorded_positive_claim':positive,'problems':gate_issues},'links':out}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('factory','record','subject','target'):parser.add_argument('--'+flag,required=True)
    args=parser.parse_args();result=assess_links(args.factory,args.record,args.subject,args.target)
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return 1 if result['binding_errors'] else 0


if __name__=='__main__':
    try:sys.exit(main())
    except TraceInputError as exc:
        print('ERROR: '+str(exc)+'; no readiness assessment was made.',file=sys.stderr)
        sys.exit(2)
    except (ValueError,OSError,KeyError,TypeError,OverflowError,RecursionError) as exc:
        print('ERROR: trace inputs invalid or unavailable ('+type(exc).__name__+'); no readiness assessment was made.',file=sys.stderr)
        sys.exit(2)
