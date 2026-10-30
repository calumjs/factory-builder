"""Read-only CI record assessment with distinct tested-subject and storage commits.

Invoke only from trusted, pinned helper code in an authorized job. Executes bounded
local Git reads, never application commands, checkout/fetch, deployment or writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import threading
sys.dont_write_bytecode=True
from gates import assess, waivers
from integrity import safe_path, validate_task_plan

MAX_FILE=4*1024*1024
MAX_TOTAL=32*1024*1024
MAX_FILES=1024
DATA_SUFFIXES=frozenset(('.txt','.log','.json','.md','.png','.jpg','.jpeg','.mp4','.webm'))


def relative(value):
    if not isinstance(value,str) or not value or value!=value.strip() or not value.isprintable() or '\\' in value or ':' in value:
        raise ValueError('Expected a canonical relative repository path')
    parts=value.split('/')
    if any(part in ('','.','..') or part.casefold()=='.git' for part in parts) or PurePosixPath(value).is_absolute():
        raise ValueError('Unsafe repository path')
    return value


def full_sha(value):
    if not isinstance(value,str) or re.fullmatch(r'(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})',value) is None:
        raise ValueError('Subject and storage must be explicit full commit SHAs, never aliases or row-derived revisions')
    return value.lower()


def bounded_run(argv,env,limit,timeout=30):
    """Drain both pipes concurrently, stopping the child before buffers exceed limits."""
    process=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    outputs=[bytearray(),bytearray()];exceeded=threading.Event()
    def drain(stream,buffer,maximum):
        try:
            while True:
                chunk=stream.read(65536)
                if not chunk:break
                remaining=maximum-len(buffer)
                if len(chunk)>remaining:
                    if remaining>0:buffer.extend(chunk[:remaining])
                    exceeded.set()
                    try:process.kill()
                    except OSError:pass
                    break
                buffer.extend(chunk)
        finally:stream.close()
    threads=[threading.Thread(target=drain,args=(process.stdout,outputs[0],limit),daemon=True),
             threading.Thread(target=drain,args=(process.stderr,outputs[1],65536),daemon=True)]
    for thread in threads:thread.start()
    try:process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill();process.wait()
        raise
    finally:
        for thread in threads:thread.join()
    if exceeded.is_set():raise ValueError('Git output exceeds bounded CI-record size')
    return process.returncode,bytes(outputs[0])


class Git:
    def __init__(self,repo,executable='git'):
        self.repo=repo;self.executable=executable

    def read(self,*args,limit=MAX_TOTAL):
        env=dict(os.environ,GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',
                 GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0')
        status,output=bounded_run([self.executable,'--no-lazy-fetch','--no-optional-locks','--literal-pathspecs',
                               '-c','core.fsmonitor=false','-C',str(self.repo),*args],
                              env,limit)
        if status:
            raise ValueError('Local Git '+args[0]+' failed; verify exact objects/history and checkout availability. No fetch is attempted.')
        return output


def clean_storage(git,storage):
    if git.read('rev-parse','HEAD').decode().strip()!=storage:
        raise ValueError('HEAD must be the explicit evidence-storage commit')
    if git.read('status','--porcelain=v1','-z','--untracked-files=all'):
        raise ValueError('Evidence assessment needs a stable clean checkout; commit/review records or use a separate clean assessment checkout')


def bind_factory(git,factory,storage):
    """Bind working bytes to storage tree, independently of index assume-unchanged."""
    entries={}
    raw=git.read('ls-tree','-r','-z',storage,'--',factory)
    for row in raw.split(b'\0'):
        if not row:continue
        header,path=row.split(b'\t',1);mode,kind,oid=header.decode().split()
        name=relative(path.decode('utf-8'))
        if kind!='blob' or mode not in ('100644','100755'):
            raise ValueError('Redirected/special factory entries are unsupported')
        entries[name]=oid
    if not entries or len(entries)>MAX_FILES:raise ValueError('Missing or oversized committed factory file set')
    root=safe_path(git.repo.joinpath(*factory.split('/')))
    found={};total=0;count=0;pending=[root]
    while pending:
        folder=pending.pop()
        with os.scandir(folder) as scan:
            for entry in scan:
                count+=1
                if count>MAX_FILES*2:raise ValueError('Factory exceeds bounded CI-record entry count')
                path=safe_path(entry.path);info=entry.stat(follow_symlinks=False)
                if len(path.relative_to(root).parts)>20:raise ValueError('Factory exceeds CI-record directory depth')
                if getattr(info,'st_file_attributes',0)&0x400:raise ValueError('Redirected factory entries are unsupported')
                if stat.S_ISDIR(info.st_mode):pending.append(path);continue
                if not stat.S_ISREG(info.st_mode):raise ValueError('Special factory entries are unsupported')
                if len(found)>=MAX_FILES:raise ValueError('Factory exceeds bounded CI-record file count')
                with path.open('rb') as stream:body=stream.read(MAX_FILE+1)
                total+=len(body)
                if len(body)>MAX_FILE or total>MAX_TOTAL:raise ValueError('Factory exceeds bounded CI-record size')
                name=path.relative_to(git.repo).as_posix()
                algorithm='sha1' if len(storage)==40 else 'sha256'
                found[name]=hashlib.new(algorithm,b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
    if entries!=found:raise ValueError('Working factory bytes/file set differ from the evidence-storage commit')
    return root


def task_core(plan):
    validate_task_plan(plan)
    return {**{key:value for key,value in plan.items() if key not in ('events','tasks')},
            'tasks':[{key:value for key,value in row.items() if key!='status'} for row in plan['tasks']]}


def task_history(git,factory,subject,storage):
    plans=[]
    for sha in (subject,storage):
        body=git.read('show',sha+':'+factory+'/task-plan.json',limit=MAX_FILE)
        plans.append(json.loads(body.decode('utf-8-sig')))
    before,after=plans
    if task_core(before)!=task_core(after):raise ValueError('Task definition/rescope changes are not evidence-only')
    prior=before.get('events',[])
    if after.get('events',[])[:len(prior)]!=prior:raise ValueError('Evidence-only updates must preserve prior task evidence history')


def evidence_changes(git,factory,evidence_dir,subject,storage):
    if subject==storage:return []
    git.read('merge-base','--is-ancestor',subject,storage)
    records={factory+'/'+name for name in ('verification.md','task-plan.json','release-handoff.md','learning-log.md')}
    prefix=evidence_dir+'/'+subject+'/'
    fields=git.read('diff','--no-ext-diff','--no-textconv','--no-renames','--name-status','-z',subject,storage,'--').split(b'\0')
    if fields[-1]==b'':fields.pop()
    if len(fields)%2 or len(fields)>MAX_FILES*2:raise ValueError('Unsupported or oversized evidence-only diff')
    changed=[]
    for index in range(0,len(fields),2):
        status=fields[index].decode();path=relative(fields[index+1].decode('utf-8'))
        if path in records and status=='M':pass
        elif path.startswith(prefix) and status=='A' and PurePosixPath(path).suffix.lower() in DATA_SUFFIXES:
            tree=git.read('ls-tree','-z',storage,'--',path)
            if not tree.startswith(b'100644 blob '):raise ValueError('Evidence additions must be non-executable regular data files')
        else:raise ValueError('Not an allowed evidence-only change: '+json.dumps({'status':status,'path':path},ensure_ascii=True))
        changed.append(path)
    task_history(git,factory,subject,storage)
    return changed


def assess_ci(repo,factory,subject,storage,stage,target=None,evidence_dir='docs/factory-evidence',required_tasks=(),git_executable='git'):
    repo=safe_path(repo);factory=relative(factory);evidence_dir=relative(evidence_dir)
    if evidence_dir==factory or evidence_dir.startswith(factory+'/') or factory.startswith(evidence_dir+'/') or evidence_dir.split('/')[0].casefold()=='.github':
        raise ValueError('Evidence data location must be outside the factory and CI configuration')
    subject=full_sha(subject);storage=full_sha(storage)
    if len(subject)!=len(storage):raise ValueError('Subject/storage object formats disagree')
    git=Git(repo,git_executable)
    top=Path(git.read('rev-parse','--show-toplevel').decode().strip())
    if not repo.samefile(top):raise ValueError('--repo must be the exact checkout root')
    for sha in (subject,storage):
        if git.read('rev-parse','--verify',sha+'^{commit}').decode().strip()!=sha:raise ValueError('Expected exact commit object')
    clean_storage(git,storage)
    changed=evidence_changes(git,factory,evidence_dir,subject,storage)
    root=bind_factory(git,factory,storage)
    found=assess(root,stage,subject,target)
    text=(root/'verification.md').read_text(encoding='utf-8-sig')
    skipped=waivers(text,stage)
    plan=json.loads((root/'task-plan.json').read_text(encoding='utf-8-sig'))
    tasks={row['id']:row for row in plan['tasks']}
    if len(set(required_tasks))!=len(required_tasks):raise ValueError('Duplicate CI-required task ID')
    for task in required_tasks:
        if task not in tasks:raise ValueError('Unknown CI-required task ID')
        events=[row for row in plan.get('events',[]) if row['task_id']==task]
        if tasks[task]['status']!='done' or not events or any(events[-1][key]!=value for key,value in (('status','done'),('result','passed'),('revision',subject))):
            found.append('Task '+task+' lacks a done/passed record for the exact tested subject required by CI policy')
    # Detect ordinary drift; an authorized CI adapter must provide stable inputs.
    clean_storage(git,storage);bind_factory(git,factory,storage)
    return {'tested_subject':subject,'evidence_storage_revision':storage,'stage':stage,
            'assessment':'blocked' if found else 'eligible_with_waivers' if skipped else 'recorded_requirements_satisfied',
            'problems':found,'waivers':skipped,'changed_evidence_files':len(changed),
            'incomplete_tasks':[{'id':row['id'],'status':row['status']} for row in plan['tasks'] if row['status']!='done'],
            'notice':'Records were assessed; no application checks were executed or attested. No merge/deploy authority is granted.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True);parser.add_argument('--factory',default='.software-factory')
    parser.add_argument('--subject',required=True);parser.add_argument('--storage',required=True)
    parser.add_argument('--stage',required=True,choices=('pre-merge','post-merge'))
    parser.add_argument('--target');parser.add_argument('--evidence-dir',default='docs/factory-evidence')
    parser.add_argument('--require-task',action='append',default=[]);parser.add_argument('--git',default='git')
    args=parser.parse_args()
    result=assess_ci(args.repo,args.factory,args.subject,args.storage,args.stage,args.target,args.evidence_dir,args.require_task,args.git)
    print(json.dumps(result,ensure_ascii=True,sort_keys=True))
    return 1 if result['problems'] else 0


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'assessment':'error','error':str(exc)},ensure_ascii=True),file=sys.stderr);sys.exit(2)
