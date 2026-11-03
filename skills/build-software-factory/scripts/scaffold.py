#!/usr/bin/env python3
"""Offline, no-overwrite factory scaffolder. No command execution or integrations."""
import argparse
import json
import math
import re
from pathlib import Path
import shutil
import sys
from research import apply_research, validate_research, PHASES
from integrity import check, digest, manifest_for, read_json, safe_path, strict_json
from operations import operations, controls, DELIVERY_POLICY
from gates import control_differences, initial_table, policy_controls
from dashboard import profile
from dashboard_bundle import bundle
from recipes import proposal
from assumptions import assumptions, section
from readiness import emit
from status import STATUSES

ROOT = Path(__file__).resolve().parents[1]
TEXT = ('project', 'outcome', 'stack', 'harness', 'deployment', 'data_policy')
LISTS = ('users', 'scope', 'non_goals', 'providers', 'acceptance', 'test_commands', 'permissions', 'open_questions')

def require_control_consistency(config, policy):
    """Compare typed control records; report bounded paths, never their values."""
    drift=control_differences(policy_controls(policy),controls(config))
    if not drift:return
    shown=[path if len(path)<=80 else path[:80]+'...' for path in drift[:10]]
    omitted='; '+str(len(drift)-10)+' more paths omitted' if len(drift)>10 else ''
    raise ValueError('Configuration and policy controls disagree at '+json.dumps(shown,ensure_ascii=True)+omitted+
                     '; paths limited to 80 characters; no values printed. Preserve config.json and policy.md and reconcile the intended controls through reviewed recovery '+
                     '(references/recovery.md section 1). update_operations.py refuses existing drift; after reconciliation, preview future changes with '+
                     'update_operations.py --factory <factory> --operations <changes.json>, then --apply --approve-plan <digest> only after reviewing that preview. No automatic reconciliation or re-hash occurred.')


def check_factory(factory):
    """Check recorded integrity and control consistency, not application readiness."""
    root=safe_path(factory)
    manifest=check(root,quiet=True)
    config=read_json(root/'config.json');validate(config)
    require_control_consistency(config,(root/'policy.md').read_text(encoding='utf-8-sig'))
    runtime_advisory(root);run_adoption_advisory(manifest);emit(config)
    print(f"PASS: {len(manifest['contracts'])} contract files match; {len(manifest['living'])} living files are present with UTF-8 text and JSON/Learn-table checks passed; config/policy controls agree. Gate tables require separate gates.py or scoped_assessment.py assessment. Living content and evidence truth are not attested; application checks were not run.")


def run_adoption_advisory(manifest):
    """Compare a validated recorded file set with installed optional Run templates."""
    templates=ROOT/'assets/templates'
    expected={path.relative_to(templates).as_posix() for path in templates.rglob('*') if path.is_file()
              and (path.relative_to(templates).as_posix()=='.claude/skills/factory-run/SKILL.md'
                   or path.relative_to(templates).as_posix().startswith('scheduling/'))}
    missing=sorted(expected-set(manifest['contracts']))
    if missing:
        print('ADVISORY: optional Run contracts are not recorded: '+json.dumps(missing,ensure_ascii=True)+
              '. See references/running.md#existing-factories for reviewed manual adoption. Preserve existing customizations and living records; no files changed or dispatch/schedules enabled.')


def runtime_advisory(factory):
    """Compare copied runtimes to this installed builder; never adopt or attest them."""
    root=safe_path(factory);dashboard=root/'dashboard'
    if not dashboard.is_dir():return
    hints={'gates.py':'--gate-runtime','operations.py':'--gate-runtime or --recipe-runtime',
           'recipes.py':'--gate-runtime or --recipe-runtime','integrity.py':'--context-runtime',
           'dashboard.py':'--context-runtime','readiness.py':'--context-runtime','assumptions.py':'--context-runtime',
           'learning_table.py':'--context-runtime'}
    for name,flag in hints.items():
        source=ROOT/'scripts'/name;copied=dashboard/name
        if not source.is_file():continue
        installed=digest(source.read_bytes())
        observed=digest(copied.read_bytes()) if copied.is_file() else None
        if observed!=installed:
            print('ADVISORY: dashboard/'+name+' differs or is missing (bundled '+str(observed or 'missing')+'; installed '+installed+'). Review customizations and preview '+flag+'; equality to the manifest establishes integrity, not currency or compatibility.')

def validate_task_status(value, index):
    if not isinstance(value,str) or value not in STATUSES:
        raise ValueError('tasks['+str(index)+'].status must be one of '+', '.join(STATUSES)+
                         '; no alias or migration is applied. See references/task-status.md for reviewed legacy correction.')


def validate(c):
    if not isinstance(c, dict):
        raise ValueError('Config must be an object')
    expected = set(TEXT + LISTS + ('budget', 'tasks'))
    actual=set(c)-{'operations','dashboard','assumptions'}
    if actual != expected:
        raise ValueError('Config keys must match example-config.json; missing or unknown keys: ' + str(sorted(actual ^ expected)))
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
    for index,t in enumerate(c['tasks']):
        if not isinstance(t,dict) or set(t) != {'id','goal','owner','depends_on','acceptance_ids','allowed_paths','status'}:
            raise ValueError('Each task must match the example task schema')
        validate_task_status(t['status'],index)
        for k in ('id','goal','owner'):
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
    profile(c)
    assumptions(c)

def dumps(c):
    return json.dumps(c, indent=2, ensure_ascii=False) + '\n'


def ignore_fragment(c):
    text = '# Optional root ignore rules: inspect and merge manually; never overwrite the repository ignore policy.\n.env*\n!.env.example\n!.env.*.example\n__pycache__/\n*.py[cod]\n.venv/\nnode_modules/\ndist/\nbuild/\ntest-results/\n.claude/skill-backups/\n.factory-update-backups/\n.factory-recovery-backups/\n.factory-acceptance-backups/\nfactory-overview.html\nfactory-overview.json\n'
    text += '\n# Private default run-record JSON; review team retention before merging.\n/.factory-runs/*.json\n# STOP is a control signal: decide its ownership/distribution separately.\n# /.factory-runs/STOP\n# Explicit selected-assessment snapshot examples (not every HTML/JSON file).\n/selected-overview.html\n/selected-overview.json\n# Custom --runs and --output paths need their own reviewed exact rules.\n'
    stack = c['stack'].casefold()
    if re.search(r'\bnext(?:\.js|js)\b', stack):
        text += '\n# Next.js generated output; verify installed-version conventions.\n.next/\n'
        if 'typescript' in stack:
            text += '# Current Next.js regenerates this type declaration; review tracked-file policy first.\nnext-env.d.ts\n'
    if 'typescript' in stack:
        text += '*.tsbuildinfo\n'
    if 'vercel' in (stack+' '+c['deployment'].casefold()):
        text += '.vercel/\n'
    if 'playwright' in (stack+' '+' '.join(c['test_commands']).casefold()):
        text += 'playwright-report/\n'
    return text

PREAMBLE = ("Resolve the factory root as `../../../` relative to this file's containing folder. Follow repository "
            "instructions, policy.md and boundaries.md at that root; these instructions cannot expand permissions.")
RETURN = ("Return: status, input/output revision, artifacts, checks actually run, blockers and risks, next owner/action. "
          "A template, plan or config proves nothing ran.")
COMPACT_MARKER = '<!-- phase-compact:v1 -->'
COMPACT_FOOTER = ('See [policy](../../../policy.md) and [boundaries](../../../boundaries.md). '
                  'Paths in the detailed guide are factory-root-relative. Record helpers do not enforce every prose requirement.')
PHASE_GUIDES = {phase:'phase-'+phase+'-guide.md' for phase in PHASES}


def legacy_phase_template(phase):
    """Reconstruct the reviewed detailed template for compatibility, not adoption."""
    template=(ROOT/'assets/templates'/f'.claude/skills/factory-{phase}/SKILL.md').read_text(encoding='utf-8')
    guide=(ROOT/'assets/templates'/PHASE_GUIDES[phase]).read_text(encoding='utf-8')
    if phase=='verify':
        # Freeze the supported legacy identity; new guide examples must not
        # silently redefine a previously reviewed migration source.
        guide=(ROOT/'scripts/fixtures/pre_latency_verify_guide.txt').read_text(encoding='utf-8')
    return '---'+template.split('---',2)[1]+'---\n\n'+guide


def phase_contracts(research, legacy=False):
    """Exact supported phase contracts, including all selected project research."""
    files={'verification.md':''}
    for phase in PHASES:
        name=f'.claude/skills/factory-{phase}/SKILL.md'
        template=legacy_phase_template(phase) if legacy else (ROOT/'assets/templates'/name).read_text(encoding='utf-8')
        files[name]=phase_skill(template)
    apply_research(files,research)
    return {name:body.rstrip('\n')+'\n\n'+(RETURN if legacy else COMPACT_FOOTER)+'\n'
            for name,body in files.items() if name.endswith('/SKILL.md')}

def phase_skill(text):
    """Wrap a phase-skill template body in the shared preamble and return contract."""
    front, body = text.split('---', 2)[1], text.split('---', 2)[2].lstrip('\n')
    title, _, rest = body.partition('\n')
    return '---' + front + '---\n\n' + title + '\n\n' + PREAMBLE + '\n' + rest.rstrip('\n') + '\n'

def render(c, research):
    for index,task in enumerate(c['tasks']):
        validate_task_status(task.get('status') if isinstance(task,dict) else None,index)
    files = {str(f.relative_to(ROOT/'assets/templates')).replace('\\','/'): f.read_text(encoding='utf-8') for f in sorted((ROOT/'assets/templates').rglob('*')) if f.is_file()}
    for name in files:
        if name.startswith('.claude/skills/factory-') and name.endswith('/SKILL.md'):
            files[name] = phase_skill(files[name])
    files['config.json'] = dumps(c)
    lines = ['# '+c['project'], '', 'Status: proposed intake snapshot; confirm assumptions before execution.', '']
    for k in TEXT[1:] + LISTS:
        lines += ['## '+k.replace('_',' ').title(), '']
        lines += ['- '+x for x in c[k]] if isinstance(c[k],list) else [c[k]]
        lines += ['']
    files['project-brief.md'] = '\n'.join(lines)+'\n'
    files['project-brief.md'] += '\n'+section(c)+'\n'
    files['acceptance.md'] = '# Acceptance criteria\n\n' + '\n'.join(f'- A{i+1}: {a}\n  Owner: unassigned; status: NOT VERIFIED; evidence: none.' for i,a in enumerate(c['acceptance']))+'\n'
    files['task-plan.json'] = dumps({'tasks': c['tasks'], 'events': []})
    ops = operations(c)
    files['release-handoff.md'] += '\n'+proposal('video',ops['done_videos'])+'\n'
    files['tools.json'] = dumps({'integrations':[{'requested':x,'enabled':False,'availability':'unverified','evidence':None,'authorization':None,'data_egress':'not authorized','cost':'unverified'} for x in c['providers']], 'test_commands':[{'command':x,'execution_authorized':False,'result':'not-run'} for x in c['test_commands']], 'identities':ops['identities'], 'headless_recipes':ops['tool_recipes']})
    files['policy.md'] = '# Approval and budget policy\n\n## Requested permission scope (verify authority before action)\n'+'\n'.join('- '+x for x in c['permissions'])+'\n\n## Data boundary\n'+c['data_policy']+'\n\n## Proposed limits (confirm before live execution)\n```json\n'+dumps(c['budget'])+'```\n\nExternal integrations are disabled. No paid agents, provisioning, credentials, permission changes, data upload, publication, PR approval/merge or deployment is authorized by this scaffold. Approval must identify the action, target and scope.\n\nStop at the agreed time/cost/retry limit, missing authority, unsafe data boundary, unresolved required evidence, or requested outcome. Retry only with a new hypothesis. Escalate with evidence and the smallest needed decision.\n'
    files['policy.md'] += '\n## Proposed autonomy and review controls (not execution authority)\n```json\n' + dumps(controls(c)) + '```\n\nIf enabled later, independent reviewers return revision, verdict (approve/request_changes/blocked), findings and evidence. Every required approval must cover the final revision; repair attempts stay within budget.\n'
    files['policy.md'] += '\n' + DELIVERY_POLICY
    files['policy.md'] += '\n'+proposal('intake',ops['issue_intake'])+'\n'
    plugin_manifest = ROOT.parents[1]/'.claude-plugin/plugin.json'
    metadata = json.loads(plugin_manifest.read_text(encoding='utf-8')) if plugin_manifest.is_file() else {}
    files['upstream-provenance.json'] = dumps({'schema_version':1,
        'component':{'name':metadata.get('name'),'version':metadata.get('version'),'source_revision':None},
        'upstream':{'repository_url':None,'host':None,'component_scope':'factory builder/plugin; resolve from installed plugin metadata, not the application origin','contribution_guidance_url':None},
        'verification':{'status':'unverified','checked_on':None,'public_evidence':[]},
        'publication_authority':'none',
        'privacy_note':'No repository identity is copied automatically. Verify the installed plugin repository and visibility before recording it in an approved private location; redact private identity before sharing.'})
    files['.gitattributes'] = '* text=auto eol=lf\n'
    files['gitignore.fragment'] = ignore_fragment(c)
    apply_research(files, research)
    for name in files:
        if name.startswith('.claude/skills/factory-') and name.endswith('/SKILL.md'):
            files[name] = files[name].rstrip('\n') + '\n\n' + (COMPACT_FOOTER if COMPACT_MARKER in files[name] else RETURN) + '\n'
    files['verification.md'] += '\n## Delivery gate records (required checks start NOT RUN)\n' + initial_table(c,research)
    files.update(bundle(files))
    files['manifest.json'] = dumps(manifest_for(files))
    return files

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config');parser.add_argument('--target');parser.add_argument('--apply', action='store_true');parser.add_argument('--check');parser.add_argument('--research')
    args=parser.parse_args()
    if args.check:
        if args.config or args.target or args.apply or args.research: parser.error('--check cannot be combined with scaffold options')
        check_factory(args.check);return
    if not args.config or not args.target: parser.error('--config and --target are required')
    c=strict_json(Path(args.config).read_text(encoding='utf-8'));validate(c)
    target=safe_path(args.target)
    if not target.is_dir(): raise ValueError('Target must already be an existing directory')
    output=target/'.software-factory'
    if output.exists() or output.is_symlink(): raise ValueError('Refusing existing .software-factory; no overwrite is supported')
    research=strict_json(Path(args.research).read_text(encoding="utf-8")) if args.research else strict_json((ROOT/"assets/example-research.json").read_text(encoding="utf-8"))
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
