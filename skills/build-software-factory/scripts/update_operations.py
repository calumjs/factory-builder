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
from operations import controls, operations, DELIVERY_POLICY
from recipes import refresh_proposal, INTAKE_FIELDS, VIDEO_FIELDS
from scaffold import validate, ROOT, phase_skill, RETURN
from assumptions import refresh as refresh_assumptions

def dumps(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'

def control_differences(left, right, path='controls'):
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

def refreshed_verification(text, config, research, reset_smoke_defaults=False, prior_config=None):
    expected=requirements(config,research)
    previous=requirements(prior_config,research) if prior_config is not None else {}
    preserved=[];history=[];extra=[];flags={}
    for line in text.splitlines():
        if not ROW.match(line):
            preserved.append(line);continue
        cells=[v.strip() for v in line.strip().strip('|').split('|')]
        if len(cells) not in (8,11):
            raise ValueError('Cannot migrate malformed gate row; review it manually')
        if cells[0] in flags:
            raise ValueError('Duplicate source gate row requires review: '+cells[0])
        flag=cells[4].casefold()
        if flag not in ('yes','y','true','no','n','false'):
            raise ValueError('Malformed source requiredness requires review')
        flags[cells[0]]='yes' if flag in ('yes','y','true') else 'no'
        history.append('> '+line)
        if cells[0] not in expected and (cells[0]=='V1' or cells[0]=='V2' and cells[0] in previous):
            continue  # Reserved video gate is retired by the reviewed disabled preference.
        if cells[0] not in expected:
            cells=(cells+['','',''])[:11]
            cells[5:11]=['','NOT RUN','','','','']
            extra.append('| '+' | '.join(cells)+' |')
    current=[]
    for line in initial_table(config,research).splitlines():
        if ROW.match(line):
            cells=[v.strip() for v in line.strip().strip('|').split('|')]
            if cells[0] in flags and not (reset_smoke_defaults and cells[0] in ('G1','G2','G3')):
                cells[4]=flags[cells[0]]
                line='| '+' | '.join(cells)+' |'
        current.append(line)
    result='\n'.join(preserved).rstrip()+'\n\n## Historical observations (not current evidence)\n'+'\n'.join(history)+'\n\n## Current delivery gate records\n'+'\n'.join(current)+'\n'+'\n'.join(extra)+'\n'
    gate_rows(result)  # Reject ambiguity or malformed legacy extra checks before writing.
    return result

# Exact normalized operations.py shipped in v1.2.0, main ba808cc.
# Only this known source is upgraded automatically under explicit reviewed opt-in.
LEGACY_DASHBOARD_OPERATIONS = 'ef2679811ecf0d340064a87facc2d1e693b9703a65e25c10aac030100ed2e4ef'
LEGACY_CONTEXT = {'dashboard.py':'9e785051fe9cc6a7dba5c4022992878066c264711fca1404e2a75237f49b34f1',
                  'integrity.py':'87c4d45bd1291f74aa468341c6820f82a66cdfd0bf719f5dd42553bc0e7fa576'}
# Exact assumption-aware integrity.py published through v1.5.1: compatible without
# the newer path diagnostics. Preserve it unless a reviewed runtime update is opted in.
COMPATIBLE_CONTEXT = {'integrity.py':'c036ba6ce7bae45e7679ecc111fd33cc7dd65c323d13f1ce651856de6b291f94',
                      'dashboard.py':'3d8aa7b1587795462e31cb1776e81f921f5f0dc69b412e8b069374d4bbf8ffe2'}
LEGACY_DELIVERY_ADDENDUM = {
    'intake':'222e1a4da39797890d2da2f7279d2f3492f678daca322823f0ceafc30c915573',
    'verify':'fea10626d5030ace9cf8a36f8d8246ea0a0d086b4abbb894fd10dfa5d875ea47',
    'release':'08f80342cb4be98daf090c833e0cc209971ec959acff24512d7dd06a9c0e5a87'}
V19_DELIVERY_ADDENDUM = {
    'intake': ('f48fc8e0956c99003f8c46bfaae76c9847cd086332cc99bf25cb74b134742b5d','c179a72f3b39cb7d181a9e04fa0cb2143747f4b7b1039bf0347d042d17900bc3'),
    'verify': ('2599dd944575f04c6a8a25916c7f63037d3168bbb5140f3c885b6d1b13e33a4c',),
    'release': ('8333d61b055b15996b37b8d8c4aec4740e05ec31be6daef27836214c6563bfcb',)}
PRIOR_GATE_RUNTIME = {
    'operations.py':'0a964032c4680520b945f8103185a0cb04fa265a147c1b0bb7f547f5302b8d00',
    'recipes.py':'0290d43d98da9529dd20452c93c5d0bb037a794c3e9a8e68526a546391cd8d27',
    'gates.py':'7303b291fc504d60ede7c8e0f5ada8f6957f71738606b1284e63b440d5f0db01'}
# Exact published v1.7 gate code supports existing recipes. Preserve it unless
# the operator explicitly reviews the newer duplicate-policy diagnostic.
COMPATIBLE_GATE_RUNTIME = {'gates.py':'4e998f0f9a1a013fc06fc9c391ea255d6d7ab57e436ab0abbfd6367b9721be7a'}


def gate_runtime_plan(root, original, replacement, opted_in):
    for filename in ('operations.py','recipes.py','gates.py'):
        name='dashboard/'+filename;path=root/name
        wanted=(ROOT/'scripts'/filename).read_bytes()
        current=path.read_bytes() if path.exists() else None
        if current is not None and digest(current)==digest(wanted):continue
        compatible=current is not None and digest(current)==COMPATIBLE_GATE_RUNTIME.get(filename)
        if compatible and not opted_in:continue
        known=current is not None and digest(current) in (PRIOR_GATE_RUNTIME[filename],LEGACY_DASHBOARD_OPERATIONS if filename=='operations.py' else None)
        if not known and not compatible and not (current is None and filename=='recipes.py'):
            raise ValueError('Customized/unsupported dashboard gate runtime preserved; review manually')
        if not opted_in:raise ValueError('Structured gates need a reviewed dashboard migration; preview with --gate-runtime')
        original[name]=current;replacement[name]=wanted


def context_runtime_plan(root, original, replacement, opted_in):
    for filename in ('dashboard.py','integrity.py','assumptions.py','readiness.py'):
        name='dashboard/'+filename
        path=root/name;wanted=(ROOT/'scripts'/filename).read_bytes()
        current=path.read_bytes() if path.exists() else None
        if current is not None and digest(current)==digest(wanted):continue
        compatible=current is not None and digest(current)==COMPATIBLE_CONTEXT.get(filename)
        if compatible and not opted_in:continue
        if current is not None and digest(current)!=LEGACY_CONTEXT.get(filename) and not compatible:
            raise ValueError('Customized/unsupported dashboard context runtime preserved; review a narrow manual migration')
        if not opted_in:
            raise ValueError('Assumptions need updated dashboard context; preview with --context-runtime')
        original[name]=current;replacement[name]=wanted


def unchanged(root, name, expected):
    path=root/name
    return not path.exists() if expected is None else path.is_file() and path.read_bytes()==expected


def prepare(factory, changes, delivery_update=False, recipe_runtime=False, assumptions_update=None, context_runtime=False, gate_runtime=False):
    root=safe_path(factory);check(root,quiet=True)
    if not isinstance(changes,dict):
        raise ValueError('Operations changes must be an object')
    names=('config.json','policy.md','manifest.json','tools.json','verification.md','release-handoff.md','project-brief.md')
    original={name:(root/name).read_bytes() for name in names}
    config=json.loads(original['config.json'].decode('utf-8-sig'))
    before_config=copy.deepcopy(config)
    before_ops=operations(config)
    before=copy.deepcopy(config.get('operations',{}))
    updated=copy.deepcopy(before)
    for section,value in changes.items():
        if isinstance(value,dict) and isinstance(updated.get(section),dict):
            updated[section].update(value)
        else:
            updated[section]=value
    if changes or (assumptions_update is None and not context_runtime and not gate_runtime):config['operations']=updated
    if assumptions_update is not None:config['assumptions']=copy.deepcopy(assumptions_update)
    validate(config)
    policy=original['policy.md'].decode('utf-8-sig').replace('\r\n','\n')
    existing_controls=policy_controls(policy)
    drift=control_differences(existing_controls,controls(before_config))
    if drift:
        raise ValueError('Policy/config controls disagree at '+', '.join(drift)+'; preserve and reconcile with a reviewed synchronized recovery before updating')
    header='## Proposed autonomy and review controls (not execution authority)'
    pattern=re.escape(header)+r'(\s*```json\n)(.*?)(\n```)'
    policy=re.sub(pattern,lambda m:header+m[1]+dumps(controls(config)).rstrip('\n')+m[3],policy,count=1,flags=re.S)
    scoped_delivery_update=delivery_update or any(key in changes for key in ('smoke_gates','done_videos'))
    if scoped_delivery_update and DELIVERY_POLICY not in policy:
        policy=policy.rstrip()+'\n\n## Reviewed delivery policy addendum\nThis reviewed addendum supersedes conflicting older gate instructions; custom project requirements remain in force.\n\n'+DELIVERY_POLICY
    if 'issue_intake' in changes:
        policy=refresh_proposal(policy,'intake',before_ops['issue_intake'],operations(config)['issue_intake'])
    replacement={'config.json':dumps(config).encode('utf-8'),'policy.md':policy.encode('utf-8')}
    if not changes and not delivery_update:
        replacement['policy.md']=original['policy.md']
    if assumptions_update is not None:
        replacement['project-brief.md']=refresh_assumptions(original['project-brief.md'].decode('utf-8-sig'),before_config,config).encode('utf-8')
    if (assumptions_update is not None or context_runtime) and (root/'dashboard').is_dir():
        context_runtime_plan(root,original,replacement,context_runtime)
    configured=operations(config)
    gate_metadata='checks' in configured['smoke_gates'] or 'triggers' in configured['done_videos']
    if (gate_metadata or gate_runtime) and (root/'dashboard').is_dir():
        gate_runtime_plan(root,original,replacement,gate_runtime)
    recipe_runtime=recipe_runtime or context_runtime or gate_runtime
    if 'done_videos' in changes:
        handoff=refresh_proposal(original['release-handoff.md'].decode('utf-8-sig'),'video',before_ops['done_videos'],operations(config)['done_videos'])
        replacement['release-handoff.md']=handoff.encode('utf-8')
    new_metadata=any(set(changes.get(section,{})) & fields for section,fields in (('issue_intake',INTAKE_FIELDS),('done_videos',VIDEO_FIELDS)))
    runtime='dashboard/operations.py'
    if (new_metadata or recipe_runtime) and (root/runtime).is_file():
        current=replacement.get(runtime,(root/runtime).read_bytes())
        wanted=(ROOT/'scripts/operations.py').read_bytes()
        if digest(current)!=digest(wanted):
            if digest(current) not in (LEGACY_DASHBOARD_OPERATIONS,PRIOR_GATE_RUNTIME['operations.py']):
                raise ValueError('Customized/unsupported dashboard runtime preserved; review a narrow manual compatibility migration')
            if digest(current)==LEGACY_DASHBOARD_OPERATIONS and not recipe_runtime:
                raise ValueError('New recipe metadata needs a reviewed v1.2 dashboard migration; preview with --recipe-runtime')
            if recipe_runtime:original[runtime]=current;replacement[runtime]=wanted
        dependency='dashboard/recipes.py'
        wanted=(ROOT/'scripts/recipes.py').read_bytes()
        if (root/dependency).exists() or dependency in replacement:
            current=replacement.get(dependency,(root/dependency).read_bytes() if (root/dependency).exists() else None)
            if digest(current)!=digest(wanted):
                if digest(current)!=PRIOR_GATE_RUNTIME['recipes.py']:
                    raise ValueError('Customized/unsupported dashboard recipe dependency preserved; review manually')
                if recipe_runtime:original[dependency]=current;replacement[dependency]=wanted
        elif recipe_runtime:
            original[dependency]=None;replacement[dependency]=wanted
        else:
            raise ValueError('Dashboard recipe dependency missing; preview a reviewed --recipe-runtime migration')
    if delivery_update or any(key in changes for key in ('smoke_gates','done_videos')):
        research=json.loads((root/'research.json').read_text(encoding='utf-8-sig'))
        reset_defaults=isinstance(changes.get('smoke_gates'),dict) and 'required' in changes['smoke_gates']
        replacement['verification.md']=refreshed_verification(original['verification.md'].decode('utf-8-sig'),config,research,reset_defaults,before_config).encode('utf-8')
    if delivery_update:
        boundary='boundaries.md'
        boundary_source=(ROOT/'assets/templates'/boundary).read_bytes()
        existing=(root/boundary).read_bytes() if (root/boundary).is_file() else None
        if existing is not None and digest(existing)!=digest(boundary_source):
            raise ValueError('Customized boundaries preserved; review their compatibility before a delivery migration')
        if existing is None:
            original[boundary]=None;replacement[boundary]=boundary_source
        for phase in ('intake','verify','release'):
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            original[name]=(root/name).read_bytes()
            current=original[name].decode('utf-8-sig')
            source=phase_skill((ROOT/'assets/templates'/name).read_text(encoding='utf-8')).split('---',2)[2].strip()+'\n\n'+RETURN
            seven='Confirm all seven skills (six phases plus factory-run) are discovered'
            six='Confirm the six existing phase skills are discovered; if factory-run was separately adopted, confirm it too'
            if phase=='intake' and seven not in source:raise ValueError('Unexpected intake discovery instructions; review migration manually')
            source_six=source.replace(seven,six) if phase=='intake' else source
            def build_addon(body):
                return '<!-- factory-delivery-update:start -->\n## Reviewed delivery-gate addendum\nThis reviewed addendum supersedes conflicting older delivery/intake instructions; other custom project instructions remain in force.\n\n'+body+'\n<!-- factory-delivery-update:end -->'
            addon=build_addon(source_six if phase=='intake' and not (root/'.claude/skills/factory-run/SKILL.md').is_file() else source)
            pattern=r'<!-- factory-delivery-update:start -->.*?<!-- factory-delivery-update:end -->'
            if current.count('<!-- factory-delivery-update:start -->')>1 or current.count('<!-- factory-delivery-update:start -->')!=current.count('<!-- factory-delivery-update:end -->'):
                raise ValueError('Ambiguous prior delivery addendum')
            previous=re.search(pattern,current,flags=re.S)
            if previous and digest(previous.group(0)) not in (LEGACY_DELIVERY_ADDENDUM[phase],*V19_DELIVERY_ADDENDUM[phase],digest(build_addon(source)),digest(build_addon(source_six))):
                raise ValueError('Customized or unsupported delivery addendum preserved; review migration manually: '+phase)
            current=re.sub(pattern,lambda _:addon,current,flags=re.S) if re.search(pattern,current,flags=re.S) else current.rstrip()+'\n\n'+addon+'\n'
            replacement[name]=current.encode('utf-8')
    tools=json.loads(original['tools.json'].decode('utf-8-sig'))
    for source,dest in (('identities','identities'),('tool_recipes','headless_recipes')):
        if source in changes and updated.get(source)!=before.get(source):
            tools[dest]=updated[source]
            replacement['tools.json']=dumps(tools).encode('utf-8')
    manifest=json.loads(original['manifest.json'].decode('utf-8-sig'))
    for name,data in replacement.items():
        if name in manifest['contracts'] or name.startswith('dashboard/') or name=='boundaries.md':
            manifest['contracts'][name]=digest(data)
    replacement['manifest.json']=dumps(manifest).encode('utf-8')
    replacement={k:v for k,v in replacement.items() if v!=original[k]}
    fingerprint={name:{'before':hashlib.sha256(original[name]).hexdigest() if original[name] is not None else None,'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(replacement.items())}
    plan=hashlib.sha256(dumps({'factory':str(root),'files':fingerprint}).encode('utf-8')).hexdigest()
    return root,original,replacement,plan

def apply(root,original,replacement,plan,approved):
    if approved!=plan:
        raise ValueError('Apply requires the exact --approve-plan digest from the reviewed preview')
    check(root,quiet=True)
    if any(not unchanged(root,name,data) for name,data in original.items()):
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
        added=[name for name in replacement if original[name] is None]
        if added:
            with (backup/'added-files.json').open('x',encoding='utf-8') as stream:stream.write(dumps(added))
        for name in replacement:
            if original[name] is None:continue
            (backup/name).parent.mkdir(parents=True,exist_ok=True)
            with (backup/name).open('xb') as stream:stream.write(original[name])
        for name in sorted(replacement,key=lambda n:n=='manifest.json'):
            if not unchanged(root,name,original[name]):
                raise ValueError('Concurrent edit preserved; inspect backup before recovery')
            if original[name] is None:
                with (root/name).open('xb') as stream:
                    stream.write(replacement[name]);stream.flush();os.fsync(stream.fileno())
                continue
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
    parser.add_argument('--factory',required=True);parser.add_argument('--operations')
    parser.add_argument('--assumptions',help='Optional JSON array replacing recorded assumptions; previews selective config/brief changes')
    parser.add_argument('--apply',action='store_true');parser.add_argument('--approve-plan')
    parser.add_argument('--delivery-gates',action='store_true',help='Opt in to a reviewed narrow gate/template migration; preserve other factory files')
    parser.add_argument('--recipe-runtime',action='store_true',help='Opt in to a reviewed known-v1.2 dashboard validator/dependency migration for recipe metadata')
    parser.add_argument('--context-runtime',action='store_true',help='Opt in to a reviewed known dashboard context/diagnostic migration; includes recipe compatibility')
    parser.add_argument('--gate-runtime',action='store_true',help='Opt in to reviewed known dashboard operations/recipes/gates support for structured gate metadata')
    args=parser.parse_args()
    if args.approve_plan and not args.apply:parser.error('--approve-plan requires --apply')
    if not args.operations and not args.assumptions:parser.error('--operations or --assumptions is required')
    changes=json.loads(Path(args.operations).read_text(encoding='utf-8-sig')) if args.operations else {}
    assumption_rows=json.loads(Path(args.assumptions).read_text(encoding='utf-8-sig')) if args.assumptions else None
    if args.assumptions and assumption_rows is None:raise ValueError('Assumptions input must be an array, not null')
    root,original,replacement,plan=prepare(args.factory,changes,args.delivery_gates,args.recipe_runtime,assumption_rows,args.context_runtime,args.gate_runtime)
    print('REVIEW PLAN: '+plan)
    for name,data in replacement.items():
        print(''.join(difflib.unified_diff(original[name].decode('utf-8-sig').splitlines(True) if original[name] is not None else [],data.decode('utf-8').splitlines(True),fromfile=name+' (current)',tofile=name+' (proposed)')))
    if args.apply:
        backup=apply(root,original,replacement,plan,args.approve_plan)
        print('APPLIED narrow operations update; backup: '+str(backup)+'. No command, watcher, video or integration was run or enabled.')
    else:print('PREVIEW ONLY: no files written. Review the diff and local write scope before --apply --approve-plan '+plan)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc)+'; if interrupted, inspect preserved backups before recovery',file=sys.stderr);sys.exit(1)
