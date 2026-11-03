"""Compare an installed plugin with an independently pinned local Git source.

Offline, read-only inventory for trusted, quiescent inputs; not an attestation or
an adversarial-filesystem sandbox. Never follows intentionally supplied links.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import unicodedata
from ci_evidence import bounded_run, full_sha, relative
from integrity import safe_path

MAX_FILE = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_DEPTH = 20
DEADLINE = 90


def local_git(root, args, deadline, limit=MAX_TOTAL):
    remaining = deadline-time.monotonic()
    if remaining <= 0:raise ValueError('Local Git verification time limit exceeded')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,
               GIT_ALLOW_PROTOCOL='',GIT_PROTOCOL_FROM_USER='0',GIT_TERMINAL_PROMPT='0',
               GIT_NO_REPLACE_OBJECTS='1',GIT_NO_LAZY_FETCH='1',GIT_OPTIONAL_LOCKS='0')
    argv=['git','--no-optional-locks','--literal-pathspecs','-c','core.fsmonitor=false',
          '-C',str(root),*args]
    status,data=bounded_run(argv,env,limit,timeout=min(30,remaining))
    if status:raise ValueError('Local Git source verification failed; no fetch is attempted')
    return data


def inventory(root, *, source=False, allowed=None):
    files={};seen=set();total=0;count=0
    def visit(folder, depth=0):
        nonlocal total,count
        if depth>MAX_DEPTH:raise ValueError('Directory depth limit exceeded')
        before=folder.lstat()
        if stat.S_ISLNK(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:
            raise ValueError('Redirected path is unsupported')
        with os.scandir(folder) as scan:entries=list(itertools.islice(scan,MAX_ENTRIES-count+1))
        if len(entries)>MAX_ENTRIES-count:raise ValueError('Inventory entry limit exceeded')
        for entry in entries:
            count+=1;path=Path(entry.path);name=path.relative_to(root).as_posix();info=path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Redirected path is unsupported')
            if name=='.git' and source:
                if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):raise ValueError('Unsafe Git metadata entry')
                continue
            relative(name)
            folded=unicodedata.normalize('NFC',name).casefold()
            if folded in seen:raise ValueError('Ambiguous inventory path')
            seen.add(folded)
            if stat.S_ISDIR(info.st_mode):visit(path,depth+1);continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:raise ValueError('Nonregular or hard-linked file is unsupported')
            if allowed is not None and name not in allowed:
                files[name]={'size':info.st_size,'sha256':None}
                continue
            if info.st_size>MAX_FILE:raise ValueError('Inventory file size limit exceeded')
            flags=os.O_RDONLY | getattr(os,'O_BINARY',0) | getattr(os,'O_NOFOLLOW',0)
            fd=os.open(path,flags)
            try:
                opened=os.fstat(fd)
                identity=lambda x:(x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns)
                if not stat.S_ISREG(opened.st_mode) or identity(opened)!=identity(info):raise ValueError('File changed before reading')
                chunks=[];size=0
                while True:
                    chunk=os.read(fd,min(65536,MAX_FILE+1-size))
                    if not chunk:break
                    chunks.append(chunk);size+=len(chunk)
                    if size>MAX_FILE:raise ValueError('Inventory file size limit exceeded')
                after=os.fstat(fd);last=path.lstat()
                if getattr(last,'st_file_attributes',0)&0x400 or identity(after)!=identity(info) or identity(last)!=identity(info) or size!=info.st_size:
                    raise ValueError('File changed while reading')
            finally:os.close(fd)
            total+=size
            if total>MAX_TOTAL:raise ValueError('Inventory total size limit exceeded')
            files[name]={'size':size,'sha256':hashlib.sha256(b''.join(chunks)).hexdigest()}
        after=folder.lstat()
        if (before.st_dev,before.st_ino,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_mtime_ns):
            raise ValueError('Directory changed while reading')
    visit(root)
    return files


def reject_redirected_ancestors(path):
    # Inspect lexical inputs before resolving, including Windows junctions on
    # Python versions predating pathlib.Path.is_junction.
    if '..' in Path(path).parts:
        raise ValueError('Parent path components are unsupported')
    path=Path(os.path.abspath(path))
    for component in (path,*path.parents):
        info=component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Redirected root or ancestor is unsupported')
    return path


def compare(installed, source, revision):
    revision=full_sha(revision)
    source=reject_redirected_ancestors(source);installed=reject_redirected_ancestors(installed)
    source=safe_path(source).resolve(strict=True);installed=safe_path(installed).resolve(strict=True)
    safe_path(source);safe_path(installed)
    if not source.is_dir() or not installed.is_dir():raise ValueError('Both inputs must be directories')
    if source==installed or source in installed.parents or installed in source.parents or source.samefile(installed):
        raise ValueError('Source and installation must be separate directories')
    deadline=time.monotonic()+DEADLINE
    head=local_git(source,['rev-parse','--verify','HEAD^{commit}'],deadline,1024).decode('ascii').strip().lower()
    if head!=revision:raise ValueError('Source HEAD differs from the independently pinned full revision')
    # Verify object contents, not just their names: cat-file alone can return a
    # corrupt loose object under the pinned hash. Fail closed on unavailable or
    # corrupt objects; fsck may also reject unrelated corruption in this repo.
    local_git(source,['fsck','--strict','--no-reflogs','--no-dangling',revision],deadline)
    raw=local_git(source,['ls-tree','-rz','--full-tree',revision],deadline)
    tracked={};seen=set()
    for item in raw.split(b'\0'):
        if not item:continue
        header,path=item.split(b'\t',1);mode,kind,oid=header.decode('ascii').split();name=relative(path.decode('utf-8'))
        folded=unicodedata.normalize('NFC',name).casefold()
        if folded in seen or mode not in ('100644','100755') or kind!='blob' or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}',oid):
            raise ValueError('Unsupported or ambiguous source tree entry')
        seen.add(folded);tracked[name]=oid
        if len(tracked)>MAX_ENTRIES:raise ValueError('Source tree entry limit exceeded')
    if not tracked:raise ValueError('Pinned source tree is empty')
    expected=inventory(source,source=True,allowed=set(tracked))
    if set(expected)!=set(tracked):raise ValueError('Source checkout has extra or missing files; use a clean pinned source')
    cache={};total=0
    for name,oid in sorted(tracked.items()):
        if oid not in cache:
            blob=local_git(source,['cat-file','blob',oid],deadline,MAX_FILE+1)
            if len(blob)>MAX_FILE:raise ValueError('Source blob size limit exceeded')
            total+=len(blob)
            if total>MAX_TOTAL:raise ValueError('Source blob total size limit exceeded')
            cache[oid]={'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}
        if expected[name]!=cache[oid]:raise ValueError('Source bytes differ from the pinned Git tree; verify checkout line endings and cleanliness')
    actual=inventory(installed,allowed=set(expected))
    # Re-scan both sides to detect ordinary changes while comparing.
    if inventory(source,source=True,allowed=set(tracked))!=expected or inventory(installed,allowed=set(expected))!=actual or local_git(source,['rev-parse','--verify','HEAD^{commit}'],deadline,1024).decode('ascii').strip().lower()!=revision:
        raise ValueError('Inputs changed during inventory; retry with quiescent paths')
    missing=sorted(set(expected)-set(actual));extra=sorted(set(actual)-set(expected))
    changed=sorted(name for name in set(expected)&set(actual) if expected[name]!=actual[name])
    rows=[{'path':name,'source_sha256':expected.get(name,{}).get('sha256'),
           'installed_sha256':actual.get(name,{}).get('sha256')}
          for name in sorted(set(expected)|set(actual))]
    return {'source_revision':revision,'source_files':len(expected),'installed_files':len(actual),
            'files':rows,'missing':missing,'extra':extra,'changed':changed,
            'comparison':'DIFFERENT' if missing or extra or changed else 'MATCH',
            'notice':'Raw-byte comparison only. Pin and trust source independently; this does not prove which cache a running session loaded, establish execution authority, or protect against hostile concurrent filesystem changes.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed',required=True);p.add_argument('--source',required=True);p.add_argument('--revision',required=True)
    args=p.parse_args();result=compare(args.installed,args.source,args.revision)
    print(json.dumps(result,ensure_ascii=True,indent=2));return 0 if result['comparison']=='MATCH' else 1


if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,OSError,UnicodeError,TypeError,OverflowError,subprocess.TimeoutExpired) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);sys.exit(2)
