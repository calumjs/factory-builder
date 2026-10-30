#!/usr/bin/env python3
"""Offline, no-overwrite factory scaffolder. No command execution or integrations."""
import argparse
import json
import math
from pathlib import Path
import shutil
import sys
from research import apply_research, validate_research
from integrity import check, manifest_for, safe_path
from operations import operations, controls, DELIVERY_POLICY
from gates import initial_table

ROOT = Path(__file__).resolve().parents[1]
TEXT = ('project', 'outcome', 'stack', 'harness', 'deployment', 'data_policy')
LISTS = ('users', 'scope', 'non_goals', 'providers', 'acceptance', 'test_commands', 'permissions', 'open_questions')

def validate(c):
    if not isinstance(c, dict):
        raise ValueError('Config must be an object')
    expected = set(TEXT + LISTS + ('budget', 'tasks'))
    if set(c) - {'operations'} != expected:
        raise ValueError('Config keys must match example-config.json; missing or unknown keys: ' + str(sorted(set(c) ^ expected)))
    for key in TEXT:
        if not isinstance(c[key], str) or not c[key].strip():
            raise ValueError(key + ' must be a nonempty string')
    for key in LISTS:
        if not isinstance(c[key], list) or not all(isinstance(x, str) and x.strip() for x in c[key]):
            raise ValueError(key + ' must be a list of nonempty strings')
    if not c['acceptance']:
        raise ValueError('At least one acceptance criterion is required')
    b = c['budget']
    if not isinstance(b, dict) or set(b) != {'max_cost','currency','max_minutes','max_workers','max_repair_attempts'}:
        raise ValueError('Budget must match example-config.json')
    for key in ('max_cost','max_minutes','max_workers','max_repair_attempts'):
        v = b[key]
        if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0:
            raise ValueError('Budget values must be finite, non-negative numbers')
    for key in ('max_workers','max_repair_attempts'):
        if not isinstance(b[key], int):
            raise ValueError(key + ' must be an integer')
    if not isinstance(b['currency'], str) or not b['currency'].strip():
        raise ValueError('Budget currency is required')
    if not isinstance(c['tasks'], list):
        raise ValueError('tasks must be a list')
    ids = set()
    for t in c['tasks']:
        if not isinstance(t,dict) or set(t) != {'id','goal','owner','depends_on','acceptance_ids','allowed_paths','status'}:
            raise ValueError('Each task must match the example task schema')
        for k in ('id','goal','owner','status'):
            if not isinstance(t[k],str) or not t[k].strip():
                raise ValueError('Task '+k+' must be nonempty text')
        for k in ('depends_on','acceptance_ids','allowed_paths'):
            if not isinstance(t[k],list) or not all(isinstance(v,str) for v in t[k]):
                raise ValueError('Task '+k+' must be a string list')
        if t['id'] in ids:
            raise ValueError('Duplicate task ID')
        ids.add(t['id'])
        if not t['acceptance_ids'] or not set(t['acceptance_ids']) <= {f'A{i+1}' for i in range(len(c['acceptance']))}:
            raise ValueError('Task acceptance references are missing or invalid')
    graph = {t['id']: t['depends_on'] for t in c['tasks']}
    done, active = set(), set()
    def visit(i):
        if i not in ids: raise ValueError('Unknown task dependency: '+i)
        if i in active: raise ValueError('Cyclic task dependencies')
        if i in done: return
        active.add(i)
        for d in graph[i]: visit(d)
        active.remove(i); done.add(i)
    for i in ids: visit(i)
    operations(c)

def dumps(c):
    return json.dumps(c, indent=2, ensure_ascii=False) + '\n'

def render(c, research):
    files = {str(f.relative_to(ROOT/'assets/templates')).replace('\\','/'): f.read_text(encoding='utf-8') for f in sorted((ROOT/'assets/templates').rglob('*')) if f.is_file()}
    files['config.json'] = dumps(c)
    lines = ['# '+c['project'], '', 'Status: proposed intake snapshot; confirm assumptions before execution.', '']
    for k in TEXT[1:] + LISTS:
        lines += ['## '+k.replace('_',' ').title(), '']
        lines += ['- '+x for x in c[k]] if isinstance(c[k],list) else [c[k]]
        lines += ['']
    files['project-brief.md'] = '\n'.join(lines)+'\n'
    files['acceptance.md'] = '# Acceptance criteria\n\n' + '\n'.join(f'- A{i+1}: {a}\n  Owner: unassigned; status: NOT VERIFIED; evidence: none.' for i,a in enumerate(c['acceptance']))+'\n'
    files['task-plan.json'] = dumps({'tasks': c['tasks'], 'events': []})
    ops = operations(c)
    files['tools.json'] = dumps({'integrations':[{'requested':x,'enabled':False,'availability':'unverified','evidence':None,'authorization':None,'data_egress':'not authorized','cost':'unverified'} for x in c['providers']], 'test_commands':[{'command':x,'execution_authorized':False,'result':'not-run'} for x in c['test_commands']], 'identities':ops['identities'], 'headless_recipes':ops['tool_recipes']})
    files['policy.md'] = '# Approval and budget policy\n\n## Requested permission scope (verify authority before action)\n'+'\n'.join('- '+x for x in c['permissions'])+'\n\n## Data boundary\n'+c['data_policy']+'\n\n## Proposed limits (confirm before live execution)\n```json\n'+dumps(c['budget'])+'```\n\nExternal integrations are disabled. No paid agents, provisioning, credentials, permission changes, data upload, publication, PR approval/merge or deployment is authorized by this scaffold. Approval must identify the action, target and scope.\n\nStop at the agreed time/cost/retry limit, missing authority, unsafe data boundary, unresolved required evidence, or requested outcome. Retry only with a new hypothesis. Escalate with evidence and the smallest needed decision.\n'
    files['policy.md'] += '\n## Proposed autonomy and review controls (not execution authority)\n```json\n' + dumps(controls(c)) + '```\n\nIf enabled later, independent reviewers return revision, verdict (approve/request_changes/blocked), findings and evidence. Every required approval must cover the final revision; repair attempts stay within budget.\n'
    files['policy.md'] += '\n' + DELIVERY_POLICY
    plugin_manifest = ROOT.parents[1]/'.claude-plugin/plugin.json'
    metadata = json.loads(plugin_manifest.read_text(encoding='utf-8')) if plugin_manifest.is_file() else {}
    files['upstream-provenance.json'] = dumps({'schema_version':1,
        'component':{'name':metadata.get('name'),'version':metadata.get('version'),'source_revision':None},
        'upstream':{'repository_url':None,'host':None,'component_scope':'factory builder/plugin; resolve from installed plugin metadata, not the application origin','contribution_guidance_url':None},
        'verification':{'status':'unverified','checked_on':None,'public_evidence':[]},
        'publication_authority':'none',
        'privacy_note':'No repository identity is copied automatically. Verify the installed plugin repository and visibility before recording it in an approved private location; redact private identity before sharing.'})
    files['.gitattributes'] = '* text=auto eol=lf\n'
    files['gitignore.fragment'] = '# Optional root ignore rules: inspect and merge manually; never overwrite the repository ignore policy.\n.env*\n!.env.example\n!.env.*.example\n__pycache__/\n*.py[cod]\n.venv/\nnode_modules/\ndist/\nbuild/\ntest-results/\n.claude/skill-backups/\n.factory-update-backups/\n'
    apply_research(files, research)
    files['verification.md'] += '\n## Delivery gate records (required checks start NOT RUN)\n' + initial_table(c,research)
    files['manifest.json'] = dumps(manifest_for(files))
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config');parser.add_argument('--target');parser.add_argument('--apply', action='store_true');parser.add_argument('--check');parser.add_argument('--research')
    args=parser.parse_args()
    if args.check:
        if args.config or args.target or args.apply or args.research: parser.error('--check cannot be combined with scaffold options')
        check(args.check);return
    if not args.config or not args.target: parser.error('--config and --target are required')
    c=json.loads(Path(args.config).read_text(encoding='utf-8'));validate(c)
    target=safe_path(args.target)
    if not target.is_dir(): raise ValueError('Target must already be an existing directory')
    output=target/'.software-factory'
    if output.exists() or output.is_symlink(): raise ValueError('Refusing existing .software-factory; no overwrite is supported')
    research=json.loads(Path(args.research).read_text(encoding="utf-8")) if args.research else json.loads((ROOT/"assets/example-research.json").read_text(encoding="utf-8"))
    validate_research(research)
    files=render(c, research)
    print(('APPLY' if args.apply else 'DRY RUN — no files written')+': '+str(output))
    for name in sorted(files): print('  '+name)
    print('Open questions: '+str(len(c['open_questions']))+'; no integrations or test commands will execute.')
    if not args.apply:return
    output.mkdir() # Exclusive creation; never overwrite another factory.
    try:
        for name,body in sorted(files.items()):
            f=output/name;f.parent.mkdir(parents=True, exist_ok=True)
            with f.open('x',encoding='utf-8',newline='\n') as stream:stream.write(body)
    except BaseException:
        shutil.rmtree(output)
        raise
    check(output)

if __name__=='__main__':
    try: main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('ERROR: '+str(exc), file=sys.stderr);sys.exit(1)
