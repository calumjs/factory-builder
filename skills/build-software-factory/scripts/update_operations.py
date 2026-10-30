"""Preview a narrow config/policy update; apply only an explicitly reviewed plan digest."""
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from gates import policy_controls, initial_table, requirements, gate_rows, ROW
from integrity import check, digest, safe_path
from operations import controls, DELIVERY_POLICY
from scaffold import validate, ROOT

def dumps(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'

def refreshed_verification(text, config, research):
    expected=requirements(config,research)
    preserved=[];history=[];extra=[]
    for line in text.splitlines():
        if not ROW.match(line):
            preserved.append(line);continue
        cells=[v.strip() for v in line.strip().strip('|').split('|')]
        if len(cells) not in (8,11):
            raise ValueError('Cannot migrate malformed gate row; review it manually')
        history.append('> '+line)
        if cells[0] not in expected:
            cells=(cells+['','',''])[:11]
            cells[5:11]=['','NOT RUN','','','','']
            extra.append('| '+' | '.join(cells)+' |')
    result='\n'.join(preserved).rstrip()+'\n\n## Historical observations (not current evidence)\n'+'\n'.join(history)+'\n\n## Current delivery gate records\n'+initial_table(config,research)+'\n'.join(extra)+'\n'
    gate_rows(result)  # Reject ambiguity or malformed legacy extra checks before writing.
    return result

def prepare(factory, changes, delivery_update=False):
    root=safe_path(factory);check(root,quiet=True)
    if not isinstance(changes,dict):
        raise ValueError('Operations changes must be an object')
    names=('config.json','policy.md','manifest.json','tools.json','verification.md')
    original={name:(root/name).read_bytes() for name in names}
    config=json.loads(original['config.json'].decode('utf-8-sig'))
    before=copy.deepcopy(config.get('operations',{}))
    updated=copy.deepcopy(before)
    for section,value in changes.items():
        if isinstance(value,dict) and isinstance(updated.get(section),dict):
            updated[section].update(value)
        else:
            updated[section]=value
    config['operations']=updated;validate(config)
    policy=original['policy.md'].decode('utf-8-sig').replace('\r\n','\n')
    policy_controls(policy)  # Refuse a missing/ambiguous/malformed source section.
    header='## Proposed autonomy and review controls (not execution authority)'
    pattern=re.escape(header)+r'(\s*```json\n)(.*?)(\n```)'
    policy=re.sub(pattern,lambda m:header+m[1]+dumps(controls(config)).rstrip('\n')+m[3],policy,count=1,flags=re.S)
    section=r'^## Default delivery gates\n.*?(?=^## |\Z)'
    if re.search(section,policy,flags=re.M|re.S):
        policy=re.sub(section,lambda _:DELIVERY_POLICY+'\n',policy,count=1,flags=re.M|re.S)
    else:
        policy=policy.rstrip()+'\n\n'+DELIVERY_POLICY
    replacement={'config.json':dumps(config).encode('utf-8'),'policy.md':policy.encode('utf-8')}
    if delivery_update or any(key in changes for key in ('smoke_gates','done_videos')):
        research=json.loads((root/'research.json').read_text(encoding='utf-8-sig'))
        replacement['verification.md']=refreshed_verification(original['verification.md'].decode('utf-8-sig'),config,research).encode('utf-8')
    if delivery_update:
        for phase in ('intake','verify','release'):
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            original[name]=(root/name).read_bytes()
            current=original[name].decode('utf-8-sig')
            source=(ROOT/'assets/templates'/name).read_text(encoding='utf-8').split('---',2)[2].strip()
            addon='<!-- factory-delivery-update:start -->\n## Reviewed delivery-gate addendum\nThis reviewed addendum supersedes conflicting older delivery/intake instructions; other custom project instructions remain in force.\n\n'+source+'\n<!-- factory-delivery-update:end -->'
            pattern=r'<!-- factory-delivery-update:start -->.*?<!-- factory-delivery-update:end -->'
            if current.count('<!-- factory-delivery-update:start -->')>1 or current.count('<!-- factory-delivery-update:start -->')!=current.count('<!-- factory-delivery-update:end -->'):
                raise ValueError('Ambiguous prior delivery addendum')
            current=re.sub(pattern,lambda _:addon,current,flags=re.S) if re.search(pattern,current,flags=re.S) else current.rstrip()+'\n\n'+addon+'\n'
            replacement[name]=current.encode('utf-8')
    tools=json.loads(original['tools.json'].decode('utf-8-sig'))
    for source,dest in (('identities','identities'),('tool_recipes','headless_recipes')):
        if source in changes and updated.get(source)!=before.get(source):
            tools[dest]=updated[source]
            replacement['tools.json']=dumps(tools).encode('utf-8')
    manifest=json.loads(original['manifest.json'].decode('utf-8-sig'))
    for name,data in replacement.items():
        if name in manifest['contracts']:
            manifest['contracts'][name]=digest(data)
    replacement['manifest.json']=dumps(manifest).encode('utf-8')
    replacement={k:v for k,v in replacement.items() if v!=original[k]}
    fingerprint={name:{'before':hashlib.sha256(original[name]).hexdigest(),'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(replacement.items())}
    plan=hashlib.sha256(dumps({'factory':str(root),'files':fingerprint}).encode('utf-8')).hexdigest()
    return root,original,replacement,plan

def apply(root,original,replacement,plan,approved):
    if approved!=plan:
        raise ValueError('Apply requires the exact --approve-plan digest from the reviewed preview')
    check(root,quiet=True)
    if any((root/name).read_bytes()!=data for name,data in original.items()):
        raise ValueError('Factory changed after preview; regenerate and review the plan')
    if not replacement:
        return None
    backup=safe_path(root.parent/'.factory-update-backups'/plan)
    if backup.exists():
        raise ValueError('Backup already exists; inspect it rather than overwriting')
    lock=root/'.operations-update.lock'
    fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    temporary=None
    try:
        backup.mkdir(parents=True)
        for name in replacement:
            (backup/name).parent.mkdir(parents=True,exist_ok=True)
            with (backup/name).open('xb') as stream:stream.write(original[name])
        for name in sorted(replacement,key=lambda n:n=='manifest.json'):
            if (root/name).read_bytes()!=original[name]:
                raise ValueError('Concurrent edit preserved; inspect backup before recovery')
            with tempfile.NamedTemporaryFile(dir=root,prefix='.operations-',suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);stream.write(replacement[name]);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,root/name);temporary=None
    finally:
        if temporary is not None and temporary.exists():temporary.unlink()
        lock.unlink()
    check(root,quiet=True)
    return backup

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--factory',required=True);parser.add_argument('--operations',required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--approve-plan')
    parser.add_argument('--delivery-gates',action='store_true',help='Opt in to a reviewed narrow gate/template migration; preserve other factory files')
    args=parser.parse_args()
    if args.approve_plan and not args.apply:parser.error('--approve-plan requires --apply')
    changes=json.loads(Path(args.operations).read_text(encoding='utf-8-sig'))
    root,original,replacement,plan=prepare(args.factory,changes,args.delivery_gates)
    print('REVIEW PLAN: '+plan)
    for name,data in replacement.items():
        print(''.join(difflib.unified_diff(original[name].decode('utf-8-sig').splitlines(True),data.decode('utf-8').splitlines(True),fromfile=name+' (current)',tofile=name+' (proposed)')))
    if args.apply:
        backup=apply(root,original,replacement,plan,args.approve_plan)
        print('APPLIED narrow operations update; backup: '+str(backup)+'. No command, watcher, video or integration was run or enabled.')
    else:print('PREVIEW ONLY: no files written. Review the diff and local write scope before --apply --approve-plan '+plan)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc)+'; if interrupted, inspect preserved backups before recovery',file=sys.stderr);sys.exit(1)
