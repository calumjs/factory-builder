"""Audit or create an approved recovered SNAPSHOT. Never edit/activate the source factory."""
import sys
sys.dont_write_bytecode=True
import argparse
import difflib
import hashlib
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from gates import gate_rows, policy_controls, requirements
from integrity import check, digest, LIVING, safe_path
from operations import controls
from research import validate_research
from scaffold import validate

MAX_FILE=262144
MAX_TOTAL=8*1024*1024
MAX_FILES=512
MAX_DIRECTORIES=512
MAX_ENTRIES=1024
RESERVED='RECOVERY-INCOMPLETE.txt'
CORE={'config.json','policy.md','project-brief.md','acceptance.md','research.json','research.md',
      'worker-handoff.md','upstream-provenance.json',
      *(f'.claude/skills/factory-{phase}/SKILL.md' for phase in ('intake','plan','build','verify','release','learn'))}


def rawhash(data):return hashlib.sha256(data).hexdigest()


def dumps(value):return json.dumps(value,indent=2,ensure_ascii=True,sort_keys=True)+'\n'


def strict_json(data):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate JSON key')
            out[key]=value
        return out
    def constant(value):raise ValueError('Non-finite JSON number')
    return json.loads(data.decode('utf-8-sig') if isinstance(data,bytes) else data,
                      object_pairs_hook=pairs,parse_constant=constant)


def name_ok(name):
    if not isinstance(name,str) or not name or name.casefold()==RESERVED.casefold() or name.casefold().startswith('.recovery-'):
        raise ValueError('Unsafe/reserved recovery path')
    if PurePosixPath(name).is_absolute() or any(v in name for v in ('\\',':','<','>','"','|','?','*')):
        raise ValueError('Unsafe recovery path')
    for part in name.split('/'):
        if part in ('','.','..') or part.rstrip(' .')!=part or any(unicodedata.category(c) in ('Cc','Cf') for c in part):
            raise ValueError('Unsafe recovery path component')
        if part.split('.')[0].casefold() in {'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}:
            raise ValueError('Reserved device path')


def existing(path):
    value=Path(path)
    if str(value).replace('/','\\').startswith(('\\\\?\\','\\\\.\\','\\??\\')):
        raise ValueError('Device namespace paths unsupported')
    value=safe_path(value).resolve(strict=True)
    if not value.is_dir():raise ValueError('Expected an existing directory')
    return value


def inside(path,root):
    return path==root or root in path.parents or (root.exists() and any(p.exists() and p.samefile(root) for p in (path,*path.parents)))


def output_path(path,base,source):
    raw=Path(path)
    name_ok(raw.name)
    if raw.exists() or raw.is_symlink():raise ValueError('Output must not exist; preserve partial attempts for review')
    parent=existing(raw.parent)
    result=parent/raw.name
    if inside(result,base) or inside(result,source):raise ValueError('Output must be outside both input factories')
    return result


def capture(root):
    files={};identities={};directories=[];seen=set();total=0
    def visit(folder,relative='',depth=0):
        nonlocal total
        if depth>20:raise ValueError('Recovery directory depth limit exceeded')
        before=folder.lstat()
        if stat.S_ISLNK(before.st_mode) or getattr(before,'st_file_attributes',0)&1024:
            raise ValueError('Redirected/reparse path unsupported')
        identities[relative+'/']=(before.st_dev,before.st_ino,before.st_mtime_ns)
        remaining=MAX_ENTRIES-len(seen)
        with os.scandir(folder) as iterator:entries=list(itertools.islice(iterator,remaining+1))
        if len(entries)>remaining:raise ValueError('Recovery total-entry limit exceeded before enumeration')
        for entry in sorted(entries,key=lambda value:value.name):
            path=Path(entry.path)
            name=(relative+'/' if relative else '')+path.name;name_ok(name)
            if len(seen)>=MAX_ENTRIES:raise ValueError('Recovery total-entry limit exceeded')
            folded=unicodedata.normalize('NFC',name).casefold()
            if folded in seen:raise ValueError('Ambiguous case/Unicode path collision')
            seen.add(folded)
            meta=path.lstat()
            if stat.S_ISLNK(meta.st_mode) or getattr(meta,'st_file_attributes',0)&1024:
                raise ValueError('Redirected/reparse path unsupported')
            if stat.S_ISDIR(meta.st_mode):
                if len(directories)>=MAX_DIRECTORIES:raise ValueError('Recovery directory-count limit exceeded')
                directories.append(name);visit(path,name,depth+1)
            elif stat.S_ISREG(meta.st_mode):
                if meta.st_size>MAX_FILE or len(files)>=MAX_FILES:raise ValueError('Recovery file-size/count limit exceeded')
                with path.open('rb') as stream:data=stream.read(MAX_FILE+1)
                if len(data)>MAX_FILE:raise ValueError('Recovery actual file-size limit exceeded')
                after=path.lstat()
                if (meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                    raise ValueError('File changed while reading; obtain a stable snapshot')
                if len(data)!=meta.st_size:raise ValueError('Incomplete/changed recovery read')
                data.decode('utf-8-sig')
                if name.casefold().endswith('.json'):strict_json(data)
                total+=len(data)
                if total>MAX_TOTAL:raise ValueError('Recovery total-size limit exceeded')
                files[name]=data;identities[name]=(meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns)
            else:raise ValueError('Special filesystem entry unsupported')
        after=folder.lstat()
        if (before.st_dev,before.st_ino,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns):
            raise ValueError('Directory changed while reading; obtain a stable snapshot')
    visit(root)
    return {'files':files,'directories':sorted(directories),'identities':identities}


def inventory(snapshot):
    return {'files':{name:rawhash(data) for name,data in sorted(snapshot['files'].items())},
            'directories':snapshot['directories'],'identities':snapshot['identities']}


def stable(root):
    first=capture(root);second=capture(root)
    if inventory(first)!=inventory(second):raise ValueError('Input inventory changed; obtain a stable snapshot')
    return second


def manifest(snapshot):
    result=strict_json(snapshot['files']['manifest.json'])
    if not isinstance(result,dict) or set(result)!={'schema','hash_mode','contracts','living'} or type(result['schema']) is not int or result['schema']!=2 or result['hash_mode']!='utf8-lf':
        raise ValueError('Only known schema-2 normalized manifests are supported')
    if not isinstance(result['contracts'],dict) or not isinstance(result['living'],list) or any(not isinstance(v,str) for v in result['living']) or set(result['living'])!=LIVING:
        raise ValueError('Living classification must remain exactly the five supported files')
    names=list(result['contracts'])+result['living']
    if len(names)!=len(set(names)) or len({name.casefold() for name in names})!=len(names):raise ValueError('Ambiguous manifest entries')
    for name in names:name_ok(name)
    if any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in result['contracts'].values()):raise ValueError('Invalid contract hash')
    return result


def semantics(snapshot):
    files=snapshot['files']
    if not CORE|LIVING|{'manifest.json'} <= set(files):raise ValueError('Core factory files missing; separate manual recovery required')
    config=strict_json(files['config.json']);validate(config)
    if policy_controls(files['policy.md'].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))!=controls(config):
        raise ValueError('Configuration and policy controls disagree; recover their reviewed design together')
    research=strict_json(files['research.json']);validate_research(research)
    from integrity import validate_task_plan
    validate_task_plan(strict_json(files['task-plan.json']))
    if not isinstance(strict_json(files['tools.json']),dict):raise ValueError('Invalid living tool registry')
    rows=gate_rows(files['verification.md'].decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'))
    for gate,spec in requirements(config,research).items():
        if gate not in rows or rows[gate]['stage']!=spec['stage']:
            raise ValueError('Missing/wrong-stage expected gate; preserve evidence and review record structure: '+gate)


def decisions_for(value,deltas):
    if not isinstance(value,dict) or set(value)!={'accept_changed','register','remove'}:
        raise ValueError('Decisions require exactly accept_changed/register/remove arrays')
    for key,expected in deltas.items():
        rows=value[key]
        if not isinstance(rows,list):raise ValueError('Decision group must be an array')
        paths=[]
        for row in rows:
            if not isinstance(row,dict) or set(row)!={'path','reason'} or not isinstance(row['reason'],str) or not row['reason'].strip() or len(row['reason'])>2000:
                raise ValueError('Each named recovery decision requires path and a specific reason')
            name_ok(row['path']);paths.append(row['path'])
        if len(paths)!=len(set(paths)) or set(paths)!=expected:
            raise ValueError(key+' must classify exactly these paths: '+', '.join(sorted(expected)))


def prepare(factory,baseline,output,pin,reference,decisions=None):
    source,base=existing(factory),existing(baseline)
    if inside(source,base) or inside(base,source):raise ValueError('Baseline and source must be independent, non-nested directories')
    target=output_path(output,base,source)
    backup_parent=target.parent/'.factory-recovery-backups'
    if backup_parent.exists():backup_parent=existing(backup_parent)
    for root in (source,base):
        if inside(backup_parent,root) or inside(root,backup_parent):raise ValueError('Backup area must be disjoint from both inputs')
    if inside(target,backup_parent) or inside(backup_parent,target):raise ValueError('Output and backup area must be disjoint')
    if not re.fullmatch('[0-9a-f]{64}',pin or '') or not isinstance(reference,str) or not reference.strip() or len(reference)>2000:
        raise ValueError('Independently verified raw baseline-manifest SHA256 and provenance reference required')
    b,s=stable(base),stable(source)
    if rawhash(b['files']['manifest.json'])!=pin:raise ValueError('Pinned baseline manifest does not match')
    bm,sm=manifest(b),manifest(s)
    check(base,quiet=True);semantics(b)
    if sm!=bm:raise ValueError('Current manifest differs semantically from pinned accepted baseline; manual recovery required')
    semantics(s)
    if not LIVING <= set(s['files']):raise ValueError('Missing living evidence must be recovered manually')
    changed={name for name,expected in bm['contracts'].items() if name in s['files'] and digest(s['files'][name])!=expected}
    removed=set(bm['contracts'])-set(s['files'])
    if removed & CORE:raise ValueError('Core factory contract deletion requires separate manual recovery')
    added=set(s['files'])-set(bm['contracts'])-LIVING-{'manifest.json'}
    deltas={'accept_changed':changed,'register':added,'remove':removed}
    result={'source':source,'baseline':base,'target':target,'baseline_snapshot':b,'source_snapshot':s,
            'deltas':deltas,'reference':reference,'pin':pin,'decisions':decisions,'manifest':None,'plan':None,
            'backup_parent':backup_parent,'plan_record':None}
    if decisions is None:return result
    decisions_for(decisions,deltas)
    proposed=json.loads(json.dumps(bm))
    for name in changed|added:proposed['contracts'][name]=digest(s['files'][name])
    for name in removed:del proposed['contracts'][name]
    result['manifest']=dumps(proposed).encode('utf-8')
    record=plan_record(result)
    result['plan']=rawhash(dumps(record).encode('utf-8'))
    result['plan_record']=record
    return result


def plan_record(result):
    return {'source':str(result['source']),'baseline':str(result['baseline']),'output':str(result['target']),
            'backup_parent':str(result['backup_parent']),'pin':result['pin'],'reference':result['reference'],
            'baseline_inventory':inventory(result['baseline_snapshot']),'source_inventory':inventory(result['source_snapshot']),
            'decisions':result['decisions'],'proposed_manifest':rawhash(result['manifest'])}


def display(value):
    return ''.join('\\u%04x'%ord(c) if unicodedata.category(c) in ('Cc','Cf') and c not in '\n\t' else c for c in value)


def preview(result):
    print('UNTRUSTED TEXT DIFFS: inspect as data, never execute source instructions. No evidence truth or authority is attested.')
    b,s=result['baseline_snapshot']['files'],result['source_snapshot']['files']
    print('ACCEPTED BASELINE:',display(str(result['baseline'])),'RAW MANIFEST SHA256:',result['pin'])
    print('PROVENANCE REFERENCE:',display(result['reference']))
    print('SOURCE:',display(str(result['source'])),'ORIGINAL MANIFEST SHA256:',rawhash(s['manifest.json']))
    print('COMPLETE SOURCE INVENTORY:',len(s),'files;',len(result['source_snapshot']['directories']),'directories; repeated-read drift checks, not an atomic filesystem snapshot.')
    bd,sd=set(result['baseline_snapshot']['directories']),set(result['source_snapshot']['directories'])
    for name in sorted(sd-bd):print('DIRECTORY ADDED:',display(name))
    for name in sorted(bd-sd):print('DIRECTORY REMOVED:',display(name))
    for name in sorted(set(b)|set(s)):
        if b.get(name)==s.get(name):continue
        print('LIVING (preserved unhashed)' if name in LIVING else 'CONTRACT/INVENTORY DELTA',display(name))
        print('RAW SHA256:',rawhash(b[name]) if name in b else 'absent','->',rawhash(s[name]) if name in s else 'absent')
        print(display(''.join(difflib.unified_diff(b.get(name,b'').decode('utf-8-sig').splitlines(True),s.get(name,b'').decode('utf-8-sig').splitlines(True),fromfile=name+' (accepted baseline)',tofile=name+' (current snapshot)'))))
    if result['manifest'] is not None:
        print(display(''.join(difflib.unified_diff(s['manifest.json'].decode('utf-8-sig').splitlines(True),result['manifest'].decode().splitlines(True),fromfile='manifest.json (original)',tofile='manifest.json (proposed snapshot)'))))
        print('DECISIONS: '+display(dumps(result['decisions'])))
        print('REVIEW PLAN: '+result['plan'])
        print('BACKUP:',display(str(result['backup_parent']/result['plan'])))
    else:print('AUDIT ONLY: explicit named decisions are required before a plan/apply is available.')
    print('Source remains untouched. Recovered output: '+display(str(result['target'])))


def write_file(path,data):
    with path.open('xb') as stream:
        offset=0
        while offset<len(data):
            count=stream.write(data[offset:])
            if type(count) is not int or count<=0 or count>len(data)-offset:raise OSError('Incomplete recovery write')
            offset+=count
        stream.flush();os.fsync(stream.fileno())
    with path.open('rb') as stream:observed=stream.read(len(data)+1)
    if observed!=data:raise OSError('Recovery write verification failed')


def copy_snapshot(root,snapshot,include_manifest=True,create=True):
    if create:root.mkdir()
    for directory in sorted(snapshot['directories'],key=lambda v:(v.count('/'),v)):(root/directory).mkdir()
    for name,data in sorted(snapshot['files'].items()):
        if include_manifest or name!='manifest.json':write_file(root/name,data)


def same_content(left,right):
    return left['files']==right['files'] and left['directories']==right['directories']


def verify_inputs(result):
    for key,path in (('source_snapshot',result['source']),('baseline_snapshot',result['baseline'])):
        if inventory(stable(path))!=inventory(result[key]):raise ValueError('Recovery input changed; review a fresh inventory and plan')


def content_inventory(snapshot):
    value=inventory(snapshot);value.pop('identities');return value


def read_metadata(path):
    path=safe_path(path)
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&1024 or info.st_size>MAX_TOTAL:
        raise ValueError('Recovery metadata must be a bounded regular non-redirected file')
    with path.open('rb') as stream:data=stream.read(MAX_TOTAL+1)
    if len(data)>MAX_TOTAL:raise ValueError('Recovery metadata grew beyond limit')
    return strict_json(data)


def verify_output(output,backup,plan):
    target,record_root=existing(output),existing(backup)
    record=read_metadata(record_root/'recovery.json')
    complete=read_metadata(record_root/'COMPLETED.json')
    if rawhash(dumps(record['plan_record']).encode('utf-8'))!=plan or record.get('backup_verified') is not True:
        raise ValueError('Recovery record does not match the reviewed plan')
    reviewed=record['plan_record']
    if reviewed['output']!=str(target) or complete!={'plan':plan,'output':str(target)}:
        raise ValueError('Missing/mismatched completion record; snapshot remains quarantined')
    expected={'files':dict(reviewed['source_inventory']['files']),'directories':reviewed['source_inventory']['directories']}
    if content_inventory(stable(record_root/'source'))!=expected:raise ValueError('Original backup differs from reviewed source inventory')
    expected['files']['manifest.json']=reviewed['proposed_manifest']
    if content_inventory(stable(target))!=expected:raise ValueError('Recovered output differs from the reviewed snapshot')
    check(target,quiet=True);semantics(stable(target))
    return True


def apply(result,approved,stable_inputs=False):
    if result['plan'] is None or approved!=result['plan']:raise ValueError('Apply requires the exact reviewed plan digest')
    current_record=plan_record(result)
    if current_record!=result['plan_record'] or rawhash(dumps(current_record).encode('utf-8'))!=approved:
        raise ValueError('Cached plan content changed; review a fresh plan')
    if not stable_inputs:raise ValueError('Apply requires coordinated stable inputs/output parent; no live writer or activation is managed here')
    output_path(result['target'],result['baseline'],result['source']);verify_inputs(result)
    backup_parent=result['backup_parent']
    if backup_parent.exists():existing(backup_parent)
    else:backup_parent.mkdir()
    backup=backup_parent/result['plan'];backup.mkdir()
    copy_snapshot(backup/'source',result['source_snapshot'])
    if not same_content(stable(backup/'source'),result['source_snapshot']):raise ValueError('Backup verification failed; source untouched')
    write_file(backup/'recovery.json',dumps({'plan_record':result['plan_record'],'backup_verified':True}).encode())
    verify_inputs(result)
    target=result['target'];created=False
    try:
        target.mkdir();created=True
        copy_snapshot(target,result['source_snapshot'],include_manifest=False,create=False)
        expected={**result['source_snapshot'],'files':{k:v for k,v in result['source_snapshot']['files'].items() if k!='manifest.json'}}
        if not same_content(stable(target),expected):raise ValueError('Staged content changed; preserve partial output')
        verify_inputs(result)
        write_file(target/'manifest.json',result['manifest'])  # The only changed file, committed last in a new snapshot.
        check(target,quiet=True);semantics(stable(target));verify_inputs(result)
        final=stable(target)
        expected['files']['manifest.json']=result['manifest']
        if not same_content(final,expected):raise ValueError('Recovered snapshot changed; preserve partial output')
        write_file(backup/'COMPLETED.json',dumps({'plan':result['plan'],'output':str(target)}).encode())
        verify_output(target,backup,result['plan'])
    except BaseException:
        if created:
            try:write_file(target/RESERVED,b'Recovery incomplete. Source untouched; inspect verified backup and partial output.\n')
            except OSError:pass
        raise
    return backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('factory','baseline','output','baseline-manifest-sha256','baseline-reference'):parser.add_argument('--'+flag)
    parser.add_argument('--decisions');parser.add_argument('--apply',action='store_true');parser.add_argument('--approve-plan')
    parser.add_argument('--stable-inputs',action='store_true',help='Attest coordinated stable inputs and exclusive output-parent boundary; creates no lock or authority')
    parser.add_argument('--verify-output');parser.add_argument('--backup');parser.add_argument('--plan-id')
    args=parser.parse_args()
    if args.verify_output:
        if any((args.factory,args.baseline,args.output,args.baseline_manifest_sha256,args.baseline_reference,args.decisions,args.apply,args.approve_plan,args.stable_inputs)):
            parser.error('--verify-output is separate from preview/apply')
        if not args.backup or not args.plan_id:parser.error('--verify-output requires --backup and --plan-id')
        verify_output(args.verify_output,args.backup,args.plan_id)
        print('SNAPSHOT BYTES/COMPLETION VERIFIED; not activated; no application evidence attested.');return
    if args.backup or args.plan_id:parser.error('--backup/--plan-id require --verify-output')
    if not all((args.factory,args.baseline,args.output,args.baseline_manifest_sha256,args.baseline_reference)):
        parser.error('Preview/apply requires --factory, --baseline, --output, --baseline-manifest-sha256 and --baseline-reference')
    if args.approve_plan and not args.apply:parser.error('--approve-plan requires --apply')
    if args.apply and not args.decisions:parser.error('--apply requires explicit decisions')
    decisions=read_metadata(Path(args.decisions)) if args.decisions else None
    if args.decisions and decisions is None:raise ValueError('Decisions cannot be null')
    result=prepare(args.factory,args.baseline,args.output,args.baseline_manifest_sha256,args.baseline_reference,decisions)
    preview(result)
    if args.apply:
        backup=apply(result,args.approve_plan,args.stable_inputs)
        print('RECOVERED SNAPSHOT ONLY; original unchanged; no application checks or activation performed. Verified backup: '+display(str(backup)))
    else:print('PREVIEW ONLY: no files written.')


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+display(str(exc))+'; helper did not modify inputs. Preserve any partial output/backup for review.',file=sys.stderr);sys.exit(1)
