"""Preview a narrow config/policy update; apply only an explicitly reviewed plan digest."""
import argparse
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from gates import policy_controls, initial_table, requirements, gate_rows, ROW, HEADER, control_differences
from integrity import check, digest, safe_path, strict_json
from operations import controls, operations, DELIVERY_POLICY
from recipes import refresh_proposal, INTAKE_FIELDS, VIDEO_FIELDS, video_design, video_triggers
from scaffold import validate, ROOT, phase_skill, RETURN, legacy_phase_template, phase_contracts, PHASE_GUIDES
from assumptions import refresh as refresh_assumptions
from backup_advisory import inspect_backup_directory

MIGRATION_RECEIPTS='migration-receipts.json'
MAX_RECEIPT_BYTES=262144
MAX_RECEIPTS=128
RUNTIME_COMPONENTS=frozenset('dashboard/'+name for name in (
    'dashboard.py','integrity.py','gates.py','operations.py','recipes.py',
    'assumptions.py','readiness.py','learning_table.py'))

def dumps(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'

def receipt_bytes(path, limit, label, optional=False):
    """Bound receipt/label inputs before parsing; never include their values in errors."""
    path=safe_path(path)
    try:before=path.lstat()
    except FileNotFoundError:
        if optional:return None
        raise ValueError(label+' is missing')
    if not stat.S_ISREG(before.st_mode) or before.st_size>limit:
        raise ValueError(label+' must be a bounded regular file')
    with path.open('rb') as stream:raw=stream.read(limit+1)
    after=path.lstat()
    if len(raw)>limit or len(raw)!=before.st_size or (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError(label+' changed during read or exceeded its limit')
    return raw


def declared_label(value):
    return value is None or isinstance(value,str) and 0<len(value)<=128 and value==value.strip() and value.isprintable()


def migration_receipts(raw):
    if raw is None:return {'schema_version':1,'receipts':[]}
    try:value=strict_json(raw.decode('utf-8-sig'))
    except (ValueError,RecursionError) as exc:raise ValueError('Malformed migration receipts; preserve and review manually') from exc
    if (not isinstance(value,dict) or set(value)!={'schema_version','receipts'} or type(value['schema_version']) is not int
            or value['schema_version']!=1 or not isinstance(value['receipts'],list) or len(value['receipts'])>MAX_RECEIPTS):
        raise ValueError('Unsupported migration receipts schema or history limit; preserve and review manually')
    def raw_hash(item):return isinstance(item,str) and re.fullmatch(r'[0-9a-f]{64}',item) is not None
    for receipt in value['receipts']:
        if not isinstance(receipt,dict) or set(receipt)!={'scope','installed_builder','components'} or receipt['scope']!='runtime-only':
            raise ValueError('Unsupported runtime migration receipt')
        builder=receipt['installed_builder']
        if (not isinstance(builder,dict) or set(builder)!={'declared_name','declared_version','verified_source_revision'}
                or not declared_label(builder['declared_name']) or not declared_label(builder['declared_version'])
                or builder['verified_source_revision'] is not None):
            raise ValueError('Unsupported installed-builder labels or source revision in receipt')
        components=receipt['components'];seen=set()
        if not isinstance(components,list) or not 1<=len(components)<=len(RUNTIME_COMPONENTS):
            raise ValueError('Invalid runtime receipt component list')
        for component in components:
            if not isinstance(component,dict) or set(component)!={'path','before_raw_sha256','after_raw_sha256'}:
                raise ValueError('Invalid runtime receipt component fields')
            name=component['path'];old=component['before_raw_sha256'];new=component['after_raw_sha256']
            if (not isinstance(name,str) or name not in RUNTIME_COMPONENTS or name in seen
                    or old is not None and not raw_hash(old) or not raw_hash(new) or old==new):
                raise ValueError('Unknown, duplicate or invalid runtime receipt component')
            seen.add(name)
    return value


def installed_builder_labels():
    raw=receipt_bytes(ROOT.parents[1]/'.claude-plugin/plugin.json',65536,'Installed builder metadata',optional=True)
    if raw is None:metadata={}
    else:
        try:metadata=strict_json(raw.decode('utf-8-sig'))
        except (ValueError,RecursionError) as exc:raise ValueError('Installed builder metadata is malformed; no verified provenance inferred') from exc
    if not isinstance(metadata,dict) or any(not declared_label(metadata.get(key)) for key in ('name','version')):
        raise ValueError('Installed builder name/version must be bounded declared labels')
    # Labels are not proof of the copied bytes' release or source revision.
    # No application origin, HEAD, dirty checkout, or supplied SHA is consulted.
    return {'declared_name':metadata.get('name'),'declared_version':metadata.get('version'),'verified_source_revision':None}


def append_runtime_receipt(original, replacement, ledger):
    components=[]
    for name in sorted(RUNTIME_COMPONENTS & replacement.keys()):
        if name not in original:raise ValueError('Runtime receipt requires captured original component bytes')
        before=original[name];after=replacement[name]
        if before==after:continue
        components.append({'path':name,'before_raw_sha256':None if before is None else hashlib.sha256(before).hexdigest(),
                           'after_raw_sha256':hashlib.sha256(after).hexdigest()})
    if not components:return
    if len(ledger['receipts'])>=MAX_RECEIPTS:raise ValueError('Migration receipt history limit reached; history will not be trimmed')
    proposed=copy.deepcopy(ledger)
    proposed['receipts'].append({'scope':'runtime-only','installed_builder':installed_builder_labels(),'components':components})
    data=dumps(proposed).encode('utf-8')
    if len(data)>MAX_RECEIPT_BYTES:raise ValueError('Migration receipt size limit reached; history will not be trimmed')
    replacement[MIGRATION_RECEIPTS]=data

def verification_explanations(original, replacement):
    """Describe captured row transitions without disclosing free-form row values."""
    def rows(data):
        active={};history=set();in_history=False
        for line in data.decode('utf-8-sig').splitlines():
            if line.startswith('## '):
                in_history=line=='## Historical observations (not current evidence)'
            historical=in_history and line.startswith('> | ')
            candidate=line[2:] if historical else line
            match=ROW.match(candidate)
            if not match:continue
            cells=[cell.strip() for cell in candidate.strip().strip('|').split('|')]
            if len(cells)==8:cells+=['','','']
            if len(cells)!=11:return None
            flag=cells[4].casefold()
            cells[4]='yes' if flag in ('yes','y','true') else 'no' if flag in ('no','n','false') else flag
            row=tuple(cells)
            if historical:history.add(row)
            elif cells[0] in active:return None
            else:active[cells[0]]=row
        return active,history

    before=rows(original['verification.md'])
    after=rows(replacement.get('verification.md',original['verification.md']))
    if before is None or after is None:
        return ['ROW SUMMARY unavailable: ambiguous or unrecognized row shape; review the captured diff.']
    old,old_history=before;new,new_history=after;messages=[]
    observation_columns=(5,6,7,8,9,10)
    for ident in dict.fromkeys((*old,*new)):
        prior=old.get(ident);current=new.get(ident);parts=[]
        if prior is None:
            parts.append('ADDED: new current row in the proposed plan')
        elif current is None:
            parts.append('RETIRED: absent from the proposed current rows')
        elif prior==current:
            parts.append('RETAINED: current row fields unchanged')
        elif tuple(current[i] for i in observation_columns)==('','NOT RUN','','','','') and any(prior[i]!=current[i] for i in observation_columns):
            parts.append('RESET: prior observation fields cleared; current result is NOT RUN')
        else:
            parts.append('UPDATED: current row fields differ in the proposed plan')
        if prior is not None:
            if prior in new_history:
                if prior in old_history:
                    parts.append('HISTORY RETAINED: matching prior row already historical; no new copy')
                else:
                    observed=prior[6]!='NOT RUN' or any(prior[i] for i in (5,7,8,9,10))
                    reason='prior result or observation fields' if observed else 'prior optional unexecuted plan' if prior[4]=='no' else 'prior unexecuted row plan'
                    parts.append('ARCHIVED: '+reason+' preserved as history, not current evidence')
            elif prior not in old_history and current is not None:
                parts.append('NOT ARCHIVED: no historical copy of the prior row added')
        if current is not None:
            if prior is not None and prior[4]!=current[4]:
                parts.append('requiredness changed in the proposed row; review the diff')
            elif current[4] in ('yes','no'):
                parts.append(('requiredness retained: ' if prior is not None else 'requiredness: ')+('optional' if current[4]=='no' else 'required'))
        messages.append('ROW '+ident+': '+'; '.join(parts)+'.')
    return messages

def classify_gate_update(text, before, after, research, changes, *, delivery=False, assumptions=False, runtime_changed=False):
    """Compare plans, never assess or rebind observations. Reasons contain no input values."""
    fallback=[]
    if delivery:fallback.append('delivery_migration')
    if 'required' in changes.get('smoke_gates',{}):fallback.append('explicit_required_defaults')
    if assumptions:fallback.append('assumptions_changed')
    if runtime_changed:fallback.append('runtime_changed')
    old_ops,new_ops=operations(before),operations(after)
    for section in old_ops.keys() | new_ops.keys():
        if section not in ('smoke_gates','done_videos','issue_intake') and control_differences(old_ops.get(section),new_ops.get(section)):
            fallback.append('other_controls_changed')
    old_smoke,new_smoke=old_ops['smoke_gates'],new_ops['smoke_gates']
    if control_differences(old_smoke['exception'],new_smoke['exception']):fallback.append('exception_changed')
    source={}
    for raw in text.splitlines(keepends=True):
        match=ROW.match(raw)
        if not match:continue
        gate=match[1]
        if gate in source:raise ValueError('Duplicate source gate row requires review: '+gate)
        source[gate]=raw
        width=len(raw.strip().strip('|').split('|'))
        if width==8:fallback.append('legacy_schema')
        elif width!=11:raise ValueError('Cannot migrate malformed gate row; review it manually')
        else:gate_rows(raw)  # A fallback may reset valid plans, never repair malformed modern rows.
    if '\r' in text.replace('\r\n',''):fallback.append('unsupported_line_endings')
    if fallback:return {'mode':'fallback','reasons':sorted(set(fallback)),'rows':{}}
    rows=gate_rows(text)
    previous,expected=requirements(before,research),requirements(after,research)
    baseline=gate_rows(initial_table(before,research))
    decisions={}
    def reset(gate,reason,fields=()):
        decision=decisions.setdefault(gate,{'action':'retain','reasons':[],'fields':[]})
        decision['action']='reset'
        if reason not in decision['reasons']:decision['reasons'].append(reason)
        decision['fields']=sorted(set(decision['fields'])|set(fields))
    target_fields=('deployed_url','target_kind','post_merge_applicability','post_merge_rationale','accepted_by')
    def target_context(smoke,specs):
        return {**{key:smoke[key] for key in target_fields},'g3_target':specs['G3'].get('recipe',{}).get('target')}
    target_changes=control_differences(target_context(old_smoke,previous),target_context(new_smoke,expected),'post_context')
    def video_context(ops):
        video=ops['done_videos']
        return {'preference':video,'design':video_design(video),'triggers':video_triggers(video)}
    video_changes=control_differences(video_context(old_ops),video_context(new_ops),'video')
    for gate in dict.fromkeys([*rows,*expected]):
        decisions[gate]={'action':'retain','reasons':[],'fields':[]}
        if gate not in rows:reset(gate,'missing_row')
        if gate not in expected:reset(gate,'retired_or_unconfigured')
        if gate not in previous:reset(gate,'new_plan')
        if gate in rows and (gate not in baseline or any(rows[gate][key]!=baseline[gate][key] for key in ('stage','design'))):
            reset(gate,'source_plan_misaligned')
        plan_changes=control_differences(previous.get(gate),expected.get(gate),'plan')
        if plan_changes:reset(gate,'plan_changed',plan_changes)
        stage_changes=control_differences(old_smoke['check_stages'].get(gate),new_smoke['check_stages'].get(gate),'check_stages')
        if stage_changes:reset(gate,'stage_override_changed',stage_changes)
        if target_changes and any(spec.get(gate,{}).get('stage')=='post-merge' for spec in (previous,expected)):
            reset(gate,'post_target_context_changed',target_changes)
        if video_changes and gate in ('V1','V2'):reset(gate,'video_preference_changed',video_changes)
    # Closure follows classification: a missing/misaligned prerequisite is just
    # as invalidating as an edited recipe, even when its config was unchanged.
    for dependent,prerequisites in (('V1',('G3',)),('V2',('G1','G2'))):
        if dependent in decisions and any(decisions.get(gate,{}).get('action')!='retain' for gate in prerequisites):
            reset(dependent,'prerequisite_reset')
    return {'mode':'selective','reasons':[],'rows':decisions}


def selective_explanations(original, replacement, changes, *, delivery=False, assumptions=False):
    if 'research.json' not in original:return []
    decision=classify_gate_update(original['verification.md'].decode('utf-8-sig'),
        json.loads(original['config.json'].decode('utf-8-sig')),
        json.loads(replacement.get('config.json',original['config.json']).decode('utf-8-sig')),
        json.loads(original['research.json'].decode('utf-8-sig')),changes,
        delivery=delivery,assumptions=assumptions,
        runtime_changed=any(name in RUNTIME_COMPONENTS and data!=original[name] for name,data in replacement.items()))
    if decision['mode']=='fallback':return ['GATE FALLBACK: '+', '.join(decision['reasons'])+'; broad reset.']
    return ['GATE '+row['action'].upper()+' '+gate+': '+(', '.join(row['reasons']) or 'plan_dependencies_unchanged')
            +('; fields: '+', '.join(row['fields']) if row['fields'] else '')+'.'
            for gate,row in decision['rows'].items()]


def refreshed_verification(text, config, research, reset_smoke_defaults=False, prior_config=None, retained_rows=None):
    expected=requirements(config,research)
    if retained_rows is not None and set(retained_rows)==set(expected)==set(gate_rows(text)):
        return text
    previous=requirements(prior_config,research) if prior_config is not None else {}
    baseline=gate_rows(initial_table(prior_config,research)) if prior_config is not None else {}
    preserved=[];history=[];observations=[];extra=[];flags={}
    in_history=False;table_header=False;skip_blank=False
    for line in text.splitlines():
        if line in ('## Historical observations (not current evidence)', '## Current delivery gate records', '## Delivery gate records (required checks start NOT RUN)'):
            while preserved and not preserved[-1].strip():preserved.pop()
            in_history=line.startswith('## Historical');table_header=False;skip_blank=True;continue
        if line.startswith('## '):in_history=False
        if in_history and line.startswith('> | '):
            history.append(line);skip_blank=True;continue
        if line == HEADER.splitlines()[0]:
            table_header=True;skip_blank=True;continue
        if table_header and re.fullmatch(r'\|(?:\s*:?-+:?\s*\|)+',line):
            table_header=False;skip_blank=True;continue
        table_header=False
        if skip_blank and not line.strip():continue
        if not ROW.match(line):
            preserved.append(line);skip_blank=False;continue
        skip_blank=True
        cells=[v.strip() for v in line.strip().strip('|').split('|')]
        if len(cells) not in (8,11):
            raise ValueError('Cannot migrate malformed gate row; review it manually')
        if cells[0] in flags:
            raise ValueError('Duplicate source gate row requires review: '+cells[0])
        flag=cells[4].casefold()
        if flag not in ('yes','y','true','no','n','false'):
            raise ValueError('Malformed source requiredness requires review')
        flags[cells[0]]='yes' if flag in ('yes','y','true') else 'no'
        if retained_rows is not None and cells[0] in retained_rows:continue
        # Blank default plans have no observation. Preserve customized plans and
        # optional choices, including retired video rows, without carrying a PASS.
        prior=baseline.get(cells[0])
        customized=prior is None or cells[1:4]!=[prior['stage'],prior['design'],prior['environment']] or flags[cells[0]]!=prior['required']
        if cells[6]!='NOT RUN' or any(cells[i] for i in (5,7)) or (len(cells)==11 and any(cells[8:11])) or customized or cells[0] in ('V1','V2') and cells[0] not in expected:
            observations.append('> '+line)
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
    # Retain existing history verbatim; refreshing the same active plan twice
    # must not append the same observation again merely because table spacing,
    # a requiredness alias or empty legacy columns were normalized.
    def history_key(line):
        cells=[cell.strip() for cell in line[2:].strip().strip('|').split('|')]
        if len(cells)==8:cells+=['','','']
        if len(cells)==11:
            flag=cells[4].casefold()
            cells[4]='yes' if flag in ('yes','y','true') else 'no' if flag in ('no','n','false') else flag
        return tuple(cells)
    seen={history_key(line) for line in history}
    for observation in observations:
        key=history_key(observation)
        if key not in seen:history.append(observation);seen.add(key)
    prefix='\n'.join(preserved).rstrip()+'\n\n## Historical observations (not current evidence)\n'+'\n'.join(history)+'\n\n## Current delivery gate records\n'
    if retained_rows is None:
        result=prefix+'\n'.join(current)+'\n'+'\n'.join(extra)+'\n'
    else:
        generated={ROW.match(line)[1]:line+'\n' for line in current+extra if ROW.match(line)}
        order=[gate for gate in flags if gate in generated]
        additions=[gate for gate in generated if gate not in order]
        # A retained final row without a newline must remain the final row.
        if order and order[-1] in retained_rows and not retained_rows[order[-1]].endswith(('\r','\n')):
            order[-1:-1]=additions
        else:order+=additions
        result=prefix+HEADER+'\n'+''.join(retained_rows.get(gate,generated[gate]) for gate in order)
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
COMPATIBLE_CONTEXT_V17 = {'integrity.py':'b03fb25cc9d78a55618e4a58504cda9d496b3c21e7b79f12e26e66d74863e498',
                          'readiness.py':'b93eecff7f8cca84d015626b11b308f22853995981255d0c1cced1963072fea5'}
COMPATIBLE_CONTEXT_PRE65 = {'integrity.py':'e76455b29979257e7f94cc418a629c46248547481ff31986c996d80edcbb4de0',
                           'readiness.py':'9ddda7edccbc0e90cb589fb871afad0bafa16213ab0e81e4ad764b89238d207d'}
COMPATIBLE_CONTEXT_PRE_DIAGNOSTICS = {'integrity.py':'8585924619380d8434083dd6f5915b75c312fdbdca61c9e2f254a44f037ec738'}
# Exact reviewed local helpers at 116eefe. Runtime-only updates preserve them by
# default and replace only these known bytes under the explicit migration flags.
COMPATIBLE_CONTEXT_PRE_RUNTIME_INTEGRATION = {
    'integrity.py':'0a830ff249d538daf1783e58a0318bafaf6c022ec768c648d06d72df7e33894d',
    'dashboard.py':'cdc39b7c105c6270b0d491676dd05c4a081a149e5c17704fcfa256808e95ead7'}
COMPATIBLE_CONTEXT_V113 = {'integrity.py':'87c8fdc0f300917a08af9afddf5275e5b744ac529b6e8d405e7919ddc26912f7'}
COMPATIBLE_DELIVERY_V117 = {
    'verify':'fdc035dd604139cf904b8d62025fc67403cd1d89c721535d2e1727f0d9190019',
    'release':'626347ff37fe9d49faa787ea571b5804f154ef49ba3bb40887e8d137eb2b20a9'}
V19_DELIVERY_ADDENDUM = {
    'intake': ('f48fc8e0956c99003f8c46bfaae76c9847cd086332cc99bf25cb74b134742b5d','c179a72f3b39cb7d181a9e04fa0cb2143747f4b7b1039bf0347d042d17900bc3'),
    'verify': ('8d861d2de61e8a4c14d7fcc1109a91395943bea8c38b30407a9962352b2e3e76','bfcae3e6622ec55ff2f232bb630ac7c340978c7dff9462c1ead95e7ff36592d9','2599dd944575f04c6a8a25916c7f63037d3168bbb5140f3c885b6d1b13e33a4c','4662208da23353e382335504b5035771f23d05f108833e2a3e86be13d518fcd3','393cbed734fc4011bcf52eaa1d48111fa49dcaac79c5b2e8fb3320f50194eafd'),
    'release': ('23800c8a793c1498841236a213dd9b6c5981dd0e2f75a1eaadc5ff2b71d83527','ad1854c67d8c3ff699dcefa954f7eebfa5791adc3ac55ef16b36ced0cca72f87','8333d61b055b15996b37b8d8c4aec4740e05ec31be6daef27836214c6563bfcb',)}
PRIOR_GATE_RUNTIME = {
    'operations.py':'0a964032c4680520b945f8103185a0cb04fa265a147c1b0bb7f547f5302b8d00',
    'recipes.py':'0290d43d98da9529dd20452c93c5d0bb037a794c3e9a8e68526a546391cd8d27',
    'gates.py':'7303b291fc504d60ede7c8e0f5ada8f6957f71738606b1284e63b440d5f0db01'}
# Exact published v1.7 gate code supports existing recipes. Preserve it unless
# the operator explicitly reviews the newer duplicate-policy diagnostic.
COMPATIBLE_GATE_RUNTIME = {'gates.py':'4e998f0f9a1a013fc06fc9c391ea255d6d7ab57e436ab0abbfd6367b9721be7a'}

COMPATIBLE_GATE_PRE65 = {'gates.py':'4aba0903e6a87f9ad3e89b46d67284b2a9e9f397999bab073bbccbbbef50bf47'}
COMPATIBLE_GATE_V19 = {'gates.py':'1114c6617a89295cc5a933852e8bd7eddb234182f2e682de2d8095b89ee93a76'}
COMPATIBLE_GATE_PRE_DIAGNOSTICS = {'gates.py':'45ba27c4aeee79b8be18dd729526c2e795705bedf05b13b5351429795e1f9c33'}
COMPATIBLE_GATE_PRE_RUNTIME_INTEGRATION = {
    'gates.py':'d1411d3f0d75e112d6d463c22c307f3407b6c9de0bfc862505f2c487761882bf',
    'operations.py':'c0a11db48df30f2b29f3770eb52a784d1b9b425a91420df8e5175470cb6eca2a'}
COMPATIBLE_GATE_V113 = {'gates.py':'bb706626fb04bf509ff4cb8805d0da353c4add1309f310441bc1dbbde7fe5da4'}
COMPATIBLE_GATE_V115 = {'gates.py':'cba74ee0273ad98461a23af1e52c2d486e60bd066947315ea07aa049cf1bcbde'}
COMPATIBLE_GATE_V117 = {'gates.py':'11b5ca9fce5e6eec5ec06c60d0417546e74aea05968d0346f7fe4f6076b4c697'}
# Exact published helpers through v1.27, before optional admission metadata.
# Compatible with legacy config; migrate only through the existing runtime flags.
PRE_ADMISSION_RUNTIME = {
    'operations.py':'0490290d091e30fad21f700fa1eba52a4cf451c686472813438ca3e7f3a92b94',
    'readiness.py':'4182ec36b619909823c2bbe9e1fbce2573ac41c121dcf408b0f56fb885bd6637'}

# Exact published 2ca1470 dashboard, before opt-in subject assessment.
PRE_SUBJECT_DASHBOARD = {'dashboard.py':'4754a7d98a9da9a6732ee9a88b07f58b59313670badecaf5939cdfc53cb780ac'}


def gate_runtime_plan(root, original, replacement, opted_in):
    for filename in ('operations.py','recipes.py','gates.py'):
        name='dashboard/'+filename;path=root/name
        wanted=(ROOT/'scripts'/filename).read_bytes()
        current=path.read_bytes() if path.exists() else None
        if current is not None and digest(current)==digest(wanted):continue
        compatible=current is not None and digest(current) in (COMPATIBLE_GATE_RUNTIME.get(filename),COMPATIBLE_GATE_PRE65.get(filename),COMPATIBLE_GATE_V19.get(filename),COMPATIBLE_GATE_PRE_DIAGNOSTICS.get(filename),COMPATIBLE_GATE_PRE_RUNTIME_INTEGRATION.get(filename),COMPATIBLE_GATE_V113.get(filename),COMPATIBLE_GATE_V115.get(filename),COMPATIBLE_GATE_V117.get(filename),PRE_ADMISSION_RUNTIME.get(filename))
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
        compatible=current is not None and digest(current) in (COMPATIBLE_CONTEXT.get(filename),COMPATIBLE_CONTEXT_V17.get(filename),COMPATIBLE_CONTEXT_PRE65.get(filename),COMPATIBLE_CONTEXT_PRE_DIAGNOSTICS.get(filename),COMPATIBLE_CONTEXT_PRE_RUNTIME_INTEGRATION.get(filename),COMPATIBLE_CONTEXT_V113.get(filename),PRE_ADMISSION_RUNTIME.get(filename),PRE_SUBJECT_DASHBOARD.get(filename))
        if compatible and not opted_in:continue
        if current is not None and digest(current)!=LEGACY_CONTEXT.get(filename) and not compatible:
            raise ValueError('Customized/unsupported dashboard context runtime preserved; review a narrow manual migration')
        if not opted_in:
            raise ValueError('Assumptions need updated dashboard context; preview with --context-runtime')
        original[name]=current;replacement[name]=wanted
    # Older helpers have no dependency on the Learn parser. Preserve that bundle
    # during unrelated updates; the explicit context plan adds the new dependency.
    if opted_in:
        name='dashboard/learning_table.py';path=root/name
        wanted=(ROOT/'scripts/learning_table.py').read_bytes()
        current=path.read_bytes() if path.exists() else None
        if current is not None and digest(current)!=digest(wanted):
            raise ValueError('Customized/unsupported dashboard Learn parser preserved; review manually')
        if current is None:
            original[name]=None;replacement[name]=wanted


def require_subject_assessment_runtime(root, original, replacement):
    """Bind the unchanged backend too; explicit flags alone may replace known bytes."""
    for filename in ('gates.py','operations.py','recipes.py'):
        name='dashboard/'+filename;path=root/name
        current=path.read_bytes() if path.is_file() else None
        original.setdefault(name,current)
        proposed=replacement.get(name,current)
        if proposed is None or digest(proposed)!=digest((ROOT/'scripts'/filename).read_bytes()):
            raise ValueError('Subject assessment needs the complete current copied gate backend; preview --context-runtime --gate-runtime for known predecessors. Missing/customized/unsupported copies are preserved and require manual review')


def require_admission_runtime(root, original, replacement):
    """Bind both copied consumers and refuse an unsupported proposed bundle."""
    for filename in ('operations.py','readiness.py'):
        name='dashboard/'+filename;path=root/name
        current=path.read_bytes() if path.is_file() else None
        if name in original and original[name]!=current:
            raise ValueError('Admission runtime changed during preview; regenerate and review the plan')
        original[name]=current  # Also bind supported, unchanged helpers for apply.
        proposed=replacement.get(name,current)
        wanted=(ROOT/'scripts'/filename).read_bytes()
        if proposed is None or digest(proposed)!=digest(wanted):
            raise ValueError('Admission needs supported copied operations and readiness helpers; preview with --context-runtime. Customized/unsupported helpers require manual review')


def unchanged(root, name, expected):
    path=root/name
    return not path.exists() if expected is None else path.is_file() and path.read_bytes()==expected


def compact_phase_plan(root, original, replacement):
    """Opt-in adoption of exact generated phase contracts; custom text is never extracted."""
    for name in ('boundaries.md','launch-guide.md','worker-handoff.md','connection-string-review.md',
                 'done-video-recipe.md','ci/README.md','ci/job.example.py','dashboard/README.md','research.md'):
        if not (root/name).is_file():
            raise ValueError('Referenced phase support is missing; preserve and review adoption before compact migration: '+name)
        original[name]=(root/name).read_bytes()
    original['research.json']=(root/'research.json').read_bytes()
    research=strict_json(original['research.json'].decode('utf-8-sig'))
    legacy=phase_contracts(research,legacy=True)
    compact=phase_contracts(research)
    for name,wanted in compact.items():
        original[name]=(root/name).read_bytes()
        current=digest(original[name])
        if current not in (digest(wanted),digest(legacy[name])):
            raise ValueError('Customized or unsupported phase skill preserved; compact migration requires exact supported generated contracts: '+name)
        replacement[name]=original[name] if current==digest(wanted) else wanted.encode('utf-8')
    for name in PHASE_GUIDES.values():
        path=root/name
        original[name]=path.read_bytes() if path.exists() else None
        wanted=(ROOT/'assets/templates'/name).read_bytes()
        if original[name] is not None and digest(original[name])!=digest(wanted):
            raise ValueError('Customized or unsupported phase guide preserved: '+name)
        replacement[name]=original[name] if original[name] is not None else wanted


def prepare(factory, changes, delivery_update=False, recipe_runtime=False, assumptions_update=None, context_runtime=False, gate_runtime=False, migration_receipt=False, selective_gates=False, compact_phases=False):
    if compact_phases and (changes or delivery_update or recipe_runtime or assumptions_update is not None or context_runtime or gate_runtime or migration_receipt or selective_gates):
        raise ValueError('--compact-phases requires a separate reviewed plan; do not combine operations or other migration options')
    if migration_receipt and not any((recipe_runtime,context_runtime,gate_runtime)):
        raise ValueError('--migration-receipt requires an explicit runtime migration flag')
    root=safe_path(factory)
    if migration_receipt:
        receipt_before=receipt_bytes(root/MIGRATION_RECEIPTS,MAX_RECEIPT_BYTES,'Migration receipts',optional=True)
        ledger=migration_receipts(receipt_before)
    check(root,quiet=True)
    if not isinstance(changes,dict):
        raise ValueError('Operations changes must be an object')
    names=('config.json','policy.md','manifest.json','tools.json','verification.md','release-handoff.md','project-brief.md')
    original={name:(root/name).read_bytes() for name in names}
    if migration_receipt:
        original[MIGRATION_RECEIPTS]=receipt_before
        if not unchanged(root,MIGRATION_RECEIPTS,receipt_before):raise ValueError('Migration receipts changed during preview')
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
    if changes:config['operations']=updated
    if assumptions_update is not None:config['assumptions']=copy.deepcopy(assumptions_update)
    validate(config)
    policy=original['policy.md'].decode('utf-8-sig').replace('\r\n','\n')
    existing_controls=policy_controls(policy)
    drift=control_differences(existing_controls,controls(before_config))
    if drift:
        raise ValueError('Policy/config controls disagree at '+json.dumps(drift,ensure_ascii=True)+'; preserve and reconcile with a reviewed synchronized recovery before updating')
    header='## Proposed autonomy and review controls (not execution authority)'
    pattern=re.escape(header)+r'(\s*```json\n)(.*?)(\n```)'
    policy=re.sub(pattern,lambda m:header+m[1]+dumps(controls(config)).rstrip('\n')+m[3],policy,count=1,flags=re.S)
    scoped_delivery_update=delivery_update or any(key in changes for key in ('smoke_gates','done_videos'))
    if scoped_delivery_update and DELIVERY_POLICY not in policy:
        policy=policy.rstrip()+'\n\n## Reviewed delivery policy addendum\nThis reviewed addendum supersedes conflicting older gate instructions; custom project requirements remain in force.\n\n'+DELIVERY_POLICY
    if 'issue_intake' in changes:
        policy=refresh_proposal(policy,'intake',before_ops['issue_intake'],operations(config)['issue_intake'])
    replacement={'config.json':dumps(config).encode('utf-8'),'policy.md':policy.encode('utf-8')}
    if not changes and assumptions_update is None:
        replacement['config.json']=original['config.json']
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
            if digest(current) not in (LEGACY_DASHBOARD_OPERATIONS,PRIOR_GATE_RUNTIME['operations.py'],COMPATIBLE_GATE_PRE_RUNTIME_INTEGRATION['operations.py'],PRE_ADMISSION_RUNTIME['operations.py']):
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
    if 'admission' in configured and (root/'dashboard').is_dir():
        require_admission_runtime(root,original,replacement)
    if context_runtime and (root/'dashboard').is_dir():
        require_subject_assessment_runtime(root,original,replacement)
    if delivery_update or any(key in changes for key in ('smoke_gates','done_videos')):
        research_bytes=(root/'research.json').read_bytes()
        research=json.loads(research_bytes.decode('utf-8-sig'))
        reset_defaults=isinstance(changes.get('smoke_gates'),dict) and 'required' in changes['smoke_gates']
        text=original['verification.md'].decode('utf-8-sig')
        retained=None
        if selective_gates:
            original['research.json']=research_bytes
            decision=classify_gate_update(text,before_config,config,research,changes,
                delivery=delivery_update,assumptions=assumptions_update is not None,
                runtime_changed=any(name in RUNTIME_COMPONENTS and data!=original[name] for name,data in replacement.items()))
            if decision['mode']=='selective':
                retained={ROW.match(line)[1]:line for line in text.splitlines(keepends=True)
                    if ROW.match(line) and decision['rows'][ROW.match(line)[1]]['action']=='retain'}
        refreshed=refreshed_verification(text,config,research,reset_defaults,before_config,retained)
        replacement['verification.md']=original['verification.md'] if selective_gates and refreshed==text else refreshed.encode('utf-8')
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
            source=phase_skill(legacy_phase_template(phase)).split('---',2)[2].strip()+'\n\n'+RETURN
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
            if previous and digest(previous.group(0)) not in (LEGACY_DELIVERY_ADDENDUM[phase],*V19_DELIVERY_ADDENDUM[phase],COMPATIBLE_DELIVERY_V117.get(phase),digest(build_addon(source)),digest(build_addon(source_six))):
                raise ValueError('Customized or unsupported delivery addendum preserved; review migration manually: '+phase)
            current=re.sub(pattern,lambda _:addon,current,flags=re.S) if re.search(pattern,current,flags=re.S) else current.rstrip()+'\n\n'+addon+'\n'
            replacement[name]=current.encode('utf-8')
    tools=json.loads(original['tools.json'].decode('utf-8-sig'))
    for source,dest in (('identities','identities'),('tool_recipes','headless_recipes')):
        if source in changes and updated.get(source)!=before.get(source):
            tools[dest]=updated[source]
            replacement['tools.json']=dumps(tools).encode('utf-8')
    if compact_phases:compact_phase_plan(root,original,replacement)
    if migration_receipt:append_runtime_receipt(original,replacement,ledger)
    manifest=json.loads(original['manifest.json'].decode('utf-8-sig'))
    prior_manifest=copy.deepcopy(manifest)
    for name,data in replacement.items():
        if name in manifest['contracts'] or name.startswith('dashboard/') or name in ('boundaries.md',MIGRATION_RECEIPTS) or compact_phases and name in PHASE_GUIDES.values():
            manifest['contracts'][name]=digest(data)
    replacement['manifest.json']=dumps(manifest).encode('utf-8') if manifest!=prior_manifest else original['manifest.json']
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
        # Receipts describe this reviewed runtime transition, not atomic success:
        # write them after components, then the manifest last as before.
        for name in sorted(replacement,key=lambda n:(n=='manifest.json',n==MIGRATION_RECEIPTS)):
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
    parser.add_argument('--migration-receipt',action='store_true',help='With a runtime migration flag, append a reviewed runtime-only byte receipt; preserve original factory provenance')
    parser.add_argument('--selective-gates',action='store_true',help='For operations gate updates, retain unchanged row bytes and reset changed plans/dependents; ambiguous migrations use the broad reset')
    parser.add_argument('--compact-phases',action='store_true',help='Separately review exact generated phase entrypoints and complete detailed guides; preserve custom skills by refusing unsupported inputs')
    args=parser.parse_args()
    if args.approve_plan and not args.apply:parser.error('--approve-plan requires --apply')
    if not any((args.operations,args.assumptions,args.delivery_gates,args.recipe_runtime,args.context_runtime,args.gate_runtime,args.compact_phases)):
        parser.error('Choose operations, assumptions, or a specific reviewed migration flag')
    changes=json.loads(Path(args.operations).read_text(encoding='utf-8-sig')) if args.operations else {}
    assumption_rows=json.loads(Path(args.assumptions).read_text(encoding='utf-8-sig')) if args.assumptions else None
    if args.assumptions and assumption_rows is None:raise ValueError('Assumptions input must be an array, not null')
    root,original,replacement,plan=prepare(args.factory,changes,args.delivery_gates,args.recipe_runtime,assumption_rows,args.context_runtime,args.gate_runtime,args.migration_receipt,args.selective_gates,args.compact_phases)
    print('REVIEW PLAN: '+plan)
    if args.migration_receipt:
        print('RUNTIME-ONLY RECEIPT: '+('proposed component byte transition; declared version is not verified provenance.' if MIGRATION_RECEIPTS in replacement else 'no changed runtime components; no receipt appended.'))
    if args.selective_gates:
        for explanation in selective_explanations(original,replacement,changes,delivery=args.delivery_gates,assumptions=assumption_rows is not None):print(explanation)
    for explanation in verification_explanations(original,replacement):print(explanation)
    for name,data in replacement.items():
        before=hashlib.sha256(original[name]).hexdigest() if original[name] is not None else 'missing'
        print('FILE '+name+' raw SHA256: '+before+' -> '+hashlib.sha256(data).hexdigest())
        print(''.join(difflib.unified_diff(original[name].decode('utf-8-sig').splitlines(True) if original[name] is not None else [],data.decode('utf-8').splitlines(True),fromfile=name+' (current)',tofile=name+' (proposed)')))
    if not replacement:print('NO CHANGES: no supported differences were proposed; this does not attest current runtime behavior.')
    if args.apply:
        backup=apply(root,original,replacement,plan,args.approve_plan)
        if backup is None:print('NO FILES WRITTEN; the reviewed plan contained no changes.')
        else:
            print('APPLIED narrow operations update; backup: '+str(backup)+'. No command, watcher, video or integration was run or enabled.')
            advice=inspect_backup_directory(root.parent,backup.parent)
            if advice['status']!='ignored':print(advice['message'])
    else:print('PREVIEW ONLY: no files written. Review the diff and local write scope before --apply --approve-plan '+plan)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('ERROR: '+str(exc)+'; if interrupted, inspect preserved backups before recovery',file=sys.stderr);sys.exit(1)
