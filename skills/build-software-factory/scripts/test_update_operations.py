"""Narrow update regressions; only isolated synthetic factories are modified."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from gates import assess, gate_rows, policy_controls
from integrity import check, digest
from operations import controls
from scaffold import ROOT, render
from update_operations import apply, prepare

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.factory=self.base/'.software-factory';self.factory.mkdir()
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(self.config,research).items():
            p=self.factory/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body,encoding='utf-8')
        self.add_custom_policy()
    def tearDown(self):self.tmp.cleanup()
    def add_custom_policy(self):
        p=self.factory/'policy.md';p.write_text(p.read_text()+'\n## Custom project rule\nPreserve this reviewed policy.\n')
        manifest=json.loads((self.factory/'manifest.json').read_text())
        manifest['contracts']['policy.md']=digest(p.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest))
    def snapshot(self):
        return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
    def test_pristine_v19_delivery_addenda_are_selectively_upgraded(self):
        from update_operations import V19_DELIVERY_ADDENDUM
        paths={phase:self.factory/f'.claude/skills/factory-{phase}/SKILL.md' for phase in ('intake','verify','release')}
        originals={phase:path.read_text(encoding='utf-8') for phase,path in paths.items()}
        for variant in ('six','seven'):
            manifest=json.loads((self.factory/'manifest.json').read_text())
            for phase,path in paths.items():
                name=f'.claude/skills/factory-{phase}/SKILL.md'
                fixture=ROOT/f'scripts/fixtures/v1_9_addendum_{phase}_{variant if phase=="intake" else "normal"}.txt'
                addon=fixture.read_text(encoding='utf-8')
                self.assertIn(digest(addon),V19_DELIVERY_ADDENDUM[phase])
                path.write_text(originals[phase].rstrip()+'\n\n'+addon+'\n',encoding='utf-8')
                manifest['contracts'][name]=digest(path.read_bytes())
            (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
            root,old,new,plan=prepare(self.factory,{},delivery_update=True)
            for phase in paths:
                self.assertEqual(new[f'.claude/skills/factory-{phase}/SKILL.md'].decode().count('<!-- factory-delivery-update:start -->'),1)
            intake=paths['intake'];intake.write_text(intake.read_text(encoding='utf-8').replace('Reviewed delivery-gate addendum','Customized delivery-gate addendum'),encoding='utf-8')
            manifest['contracts']['.claude/skills/factory-intake/SKILL.md']=digest(intake.read_bytes())
            (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
            with self.assertRaisesRegex(ValueError,'Customized or unsupported delivery addendum'):
                prepare(self.factory,{},delivery_update=True)


    def test_preview_and_wrong_approval_write_nothing(self):
        before=self.snapshot();root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':True}})
        self.assertEqual(self.snapshot(),before)
        with self.assertRaises(ValueError):apply(root,old,new,plan,'not-approved')
        self.assertEqual(self.snapshot(),before)

    def test_delivery_migration_adds_reviewed_boundaries_to_older_factory(self):
        from scaffold import PREAMBLE, RETURN
        boundary=self.factory/'boundaries.md';boundary.unlink()
        manifest=json.loads((self.factory/'manifest.json').read_text());manifest['contracts'].pop('boundaries.md')
        (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
        before=self.snapshot();root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        self.assertEqual(before,self.snapshot());self.assertIsNone(old['boundaries.md'])
        self.assertIn('boundaries.md',new)
        for phase in ('intake','verify','release'):
            text=new[f'.claude/skills/factory-{phase}/SKILL.md'].decode()
            addon=text.split('<!-- factory-delivery-update:start -->',1)[1]
            self.assertIn(PREAMBLE,addon);self.assertIn(RETURN,addon)
        backup=apply(root,old,new,plan,plan)
        self.assertIn('boundaries.md',json.loads((backup/'added-files.json').read_text()))
        check(root,quiet=True)

    def test_six_skill_factory_migration_does_not_require_uninstalled_run(self):
        manifest=json.loads((self.factory/'manifest.json').read_text())
        for name in ('boundaries.md','.claude/skills/factory-run/SKILL.md'):
            (self.factory/name).unlink();manifest['contracts'].pop(name)
        intake=self.factory/'.claude/skills/factory-intake/SKILL.md'
        intake.write_text('---\nname: factory-intake\ndescription: Legacy intake\n---\n\n# Intake\n\nLegacy project instructions.\n')
        manifest['contracts']['.claude/skills/factory-intake/SKILL.md']=digest(intake.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        addon=new['.claude/skills/factory-intake/SKILL.md'].decode().split('<!-- factory-delivery-update:start -->',1)[1]
        self.assertIn('Confirm the six existing phase skills',addon)
        self.assertIn('if factory-run was separately adopted',addon)
        self.assertNotIn('Confirm all seven skills',addon)
        apply(root,old,new,plan,plan);check(root,quiet=True)

    def test_known_legacy_addenda_upgrade_and_unknown_custom_addenda_refuse(self):
        from update_operations import LEGACY_DELIVERY_ADDENDUM
        manifest=json.loads((self.factory/'manifest.json').read_text())
        for phase in ('intake','verify','release'):
            name=f'.claude/skills/factory-{phase}/SKILL.md';path=self.factory/name
            addon=(ROOT/f'scripts/fixtures/v1_7_delivery_{phase}.txt').read_text(encoding='utf-8')
            self.assertEqual(digest(addon),LEGACY_DELIVERY_ADDENDUM[phase])
            path.write_text(path.read_text()+'\n'+addon+'\n');manifest['contracts'][name]=digest(path.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        self.assertIn('factory-delivery-update:start',new['.claude/skills/factory-intake/SKILL.md'].decode())
        path=root/'.claude/skills/factory-intake/SKILL.md'
        path.write_text(path.read_text().replace('<!-- factory-delivery-update:end -->','Custom retained instruction.\n<!-- factory-delivery-update:end -->'))
        manifest=json.loads((root/'manifest.json').read_text());manifest['contracts']['.claude/skills/factory-intake/SKILL.md']=digest(path.read_bytes())
        (root/'manifest.json').write_text(json.dumps(manifest));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized or unsupported delivery addendum'):
            prepare(root,{},delivery_update=True)
        self.assertEqual(before,self.snapshot())

    def test_delivery_migration_preserves_custom_boundaries(self):
        path=self.factory/'boundaries.md';path.write_text(path.read_text()+'\nCustom policy.\n')
        manifest=json.loads((self.factory/'manifest.json').read_text());manifest['contracts']['boundaries.md']=digest(path.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized boundaries'):
            prepare(self.factory,{},delivery_update=True)
        self.assertEqual(before,self.snapshot())

    def test_delivery_migration_rejects_policy_drift_without_writes(self):
        path=self.factory/'policy.md';source=path.read_text()
        changed=source.replace('"concurrency": 1','"concurrency": true')
        self.assertNotEqual(source,changed);path.write_text(changed)
        manifest=json.loads((self.factory/'manifest.json').read_text());manifest['contracts']['policy.md']=digest(path.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'controls.concurrency'):
            prepare(self.factory,{},delivery_update=True)
        self.assertEqual(before,self.snapshot())

    def test_duplicate_policy_keys_block_migration_and_gate_assessment(self):
        path=self.factory/'policy.md';source=path.read_text()
        changed=source.replace('"concurrency": 1','"concurrency": 999,\n  "concurrency": 1',1)
        self.assertNotEqual(source,changed);path.write_text(changed)
        manifest=json.loads((self.factory/'manifest.json').read_text());manifest['contracts']['policy.md']=digest(path.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(manifest));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Duplicate key'):
            prepare(self.factory,{},delivery_update=True)
        with self.assertRaisesRegex(ValueError,'Duplicate key'):
            assess(self.factory,'pre-merge','synthetic')
        self.assertEqual(before,self.snapshot())

    def test_nested_duplicate_policy_keys_are_rejected(self):
        text=(self.factory/'policy.md').read_text()
        changed=text.replace('"independent": false','"independent": true,\n    "independent": false',1)
        self.assertNotEqual(text,changed)
        with self.assertRaisesRegex(ValueError,'Duplicate key'):policy_controls(changed)

    def test_published_v17_gate_code_is_preserved_or_reviewedly_upgraded(self):
        from update_operations import COMPATIBLE_GATE_RUNTIME
        data=(ROOT/'scripts/fixtures/v1_7_gates.txt').read_bytes()
        self.assertEqual(digest(data),COMPATIBLE_GATE_RUNTIME['gates.py'])
        path=self.factory/'dashboard/gates.py';path.write_bytes(data)
        manifest=json.loads((self.factory/'manifest.json').read_text());manifest['contracts']['dashboard/gates.py']=digest(data)
        (self.factory/'manifest.json').write_text(json.dumps(manifest));check(self.factory,quiet=True)
        changes={'done_videos':{'enabled':True,'triggers':['post_g3_release']}}
        root,old,new,plan=prepare(self.factory,changes,gate_runtime=False)
        self.assertNotIn('dashboard/gates.py',new)
        root,old,new,plan=prepare(self.factory,changes,gate_runtime=True)
        backup=apply(root,old,new,plan,plan)
        self.assertEqual((backup/'dashboard/gates.py').read_bytes(),data)
        self.assertEqual(path.read_bytes(),(ROOT/'scripts/gates.py').read_bytes());check(root,quiet=True)
    def test_synchronized_update_preserves_custom_policy_and_evidence_history(self):
        evidence=self.factory/'verification.md';evidence.write_text(evidence.read_text()+'\nOperator notes: preserve this history.\n')
        before=self.snapshot()
        root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':True,'scope':'Synthetic approved demo'}})
        backup=apply(root,old,new,plan,plan)
        config=json.loads((root/'config.json').read_text())
        self.assertEqual(policy_controls((root/'policy.md').read_text()),controls(config))
        self.assertIn('Preserve this reviewed policy',(root/'policy.md').read_text())
        self.assertIn('Operator notes: preserve this history',(root/'verification.md').read_text())
        self.assertEqual(gate_rows((root/'verification.md').read_text())['V1']['result'],'NOT RUN')
        for name in new:self.assertEqual((backup/name).read_bytes(),old[name])
        self.assertEqual((root/'task-plan.json').read_bytes(),before['.software-factory/task-plan.json'])
        check(root,quiet=True)
    def test_ops_edit_cannot_hide_under_a_rebaselined_stale_policy(self):
        config=json.loads((self.factory/'config.json').read_text())
        config['operations']={'done_videos':{'enabled':True}}
        (self.factory/'config.json').write_text(json.dumps(config))
        m=json.loads((self.factory/'manifest.json').read_text());m['contracts']['config.json']=digest((self.factory/'config.json').read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(m))
        check(self.factory,quiet=True)
        with self.assertRaisesRegex(ValueError,'disagree'):assess(self.factory,'pre-merge','r1')
    def test_changed_contract_blocks_preview(self):
        (self.factory/'policy.md').write_text('Unreviewed edit')
        before=self.snapshot()
        with self.assertRaises(ValueError):prepare(self.factory,{})
        self.assertEqual(self.snapshot(),before)
    def test_concurrent_change_invalidates_the_reviewed_plan(self):
        root,old,new,plan=prepare(self.factory,{'issue_intake':{'mode':'continuous'}})
        (root/'tools.json').write_text('{"user":"new living edit"}')
        before=self.snapshot()
        with self.assertRaises(ValueError):apply(root,old,new,plan,plan)
        self.assertEqual(self.snapshot(),before)
    def test_invalid_operations_do_not_write(self):
        before=self.snapshot()
        for changes in ({'unexpected':{}},{'smoke_gates':{'required':'false'}},{'autonomy':{'mode':'bounded'}}):
            with self.assertRaises(ValueError):prepare(self.factory,changes)
        self.assertEqual(self.snapshot(),before)
    def test_narrow_delivery_opt_in_preserves_other_files_and_custom_skill(self):
        path=self.factory/'.claude/skills/factory-intake/SKILL.md'
        path.write_text(path.read_text()+'\nCustom reviewed project intake instructions.\n')
        m=json.loads((self.factory/'manifest.json').read_text());m['contracts']['.claude/skills/factory-intake/SKILL.md']=digest(path.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(m))
        before=self.snapshot()
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        self.assertEqual(self.snapshot(),before)
        apply(root,old,new,plan,plan)
        self.assertIn('Custom reviewed project intake instructions',path.read_text())
        self.assertIn('Reviewed delivery-gate addendum',path.read_text())
        for name in ('research.json','acceptance.md','task-plan.json','learning-log.md','release-handoff.md'):
            self.assertEqual((root/name).read_bytes(),before['.software-factory/'+name])
        self.assertTrue(assess(root,'pre-merge','r1'))
    def test_failure_preserves_backup_and_blocks_integrity_until_recovery(self):
        root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':True}})
        import os
        real_replace=os.replace;calls=[]
        def fail_second(source,dest):
            calls.append(str(dest))
            if len(calls)==2:raise OSError('Synthetic interrupted write')
            return real_replace(source,dest)
        with patch('update_operations.os.replace',side_effect=fail_second):
            with self.assertRaises(OSError):apply(root,old,new,plan,plan)
        backup=self.base/'.factory-update-backups'/plan
        self.assertTrue(backup.is_dir())
        for name in new:self.assertEqual((backup/name).read_bytes(),old[name])
        self.assertFalse((root/'.operations-update.lock').exists())
        with self.assertRaises(ValueError):check(root,quiet=True)
    def test_revised_smoke_plan_resets_prior_passed_claims(self):
        path=self.factory/'verification.md'
        text=path.read_text().replace('| NOT RUN |','| PASSED |')
        path.write_text(text)
        root,old,new,plan=prepare(self.factory,{'smoke_gates':{'pre_merge':'New inspected smoke design'}})
        apply(root,old,new,plan,plan)
        self.assertIn('> | G1 |',path.read_text())
        self.assertEqual(gate_rows(path.read_text())['G1']['result'],'NOT RUN')
    def test_legacy_eight_column_gate_migration_preserves_history_and_extra_requirements(self):
        verification=self.factory/'verification.md'
        verification.write_text('| G1 | pre-merge | old smoke | local | yes | old-rev | PASSED | original evidence |\n| G2 | pre-merge | targeted | local | yes | | NOT RUN | |\n| G3 | post-merge | confirmation | live | yes | | NOT RUN | |\n| X1 | pre-merge | custom requirement | local | yes | old-rev | PASSED | custom history |\n')
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        apply(root,old,new,plan,plan)
        self.assertIn('> | G1 |',verification.read_text())
        self.assertIn('original evidence',verification.read_text())
        rows=gate_rows(verification.read_text())
        self.assertEqual(set(rows),{'G1','G2','G3','A1','X1'})
        self.assertTrue(all(r['result']=='NOT RUN' for r in rows.values()))
    def test_cli_requires_review_digest_before_apply(self):
        import re
        import subprocess
        import sys
        changes=self.base/'ops.json';changes.write_text('{"done_videos":{"enabled":true}}')
        command=[sys.executable,str(ROOT/'scripts/update_operations.py'),'--factory',str(self.factory),'--operations',str(changes)]
        before=self.snapshot()
        preview=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(preview.returncode,0,preview.stderr);self.assertEqual(self.snapshot(),before)
        token=re.search(r'REVIEW PLAN: ([0-9a-f]{64})',preview.stdout).group(1)
        no_approval=subprocess.run(command+['--apply'],capture_output=True,text=True)
        self.assertNotEqual(no_approval.returncode,0);self.assertEqual(self.snapshot(),before)
        approved=subprocess.run(command+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertEqual(approved.returncode,0,approved.stderr)
        self.assertTrue(json.loads((self.factory/'config.json').read_text())['operations']['done_videos']['enabled'])
    def test_disabling_video_retires_reserved_gate_but_keeps_history(self):
        root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':True}})
        apply(root,old,new,plan,plan)
        self.assertIn('V1',gate_rows((root/'verification.md').read_text()))
        root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':False}})
        apply(root,old,new,plan,plan)
        text=(root/'verification.md').read_text()
        self.assertNotIn('V1',gate_rows(text));self.assertIn('> | V1 |',text)
        config=json.loads((root/'config.json').read_text())
        self.assertFalse(controls(config)['done_videos']['enabled'])
    def test_unrelated_update_preserves_custom_text_inside_delivery_policy_section(self):
        p=self.factory/'policy.md'
        p.write_text(p.read_text().replace('## Default delivery gates\n','## Default delivery gates\nCustom package-signature requirement remains mandatory.\n'))
        m=json.loads((self.factory/'manifest.json').read_text());m['contracts']['policy.md']=digest(p.read_bytes())
        (self.factory/'manifest.json').write_text(json.dumps(m))
        root,old,new,plan=prepare(self.factory,{'issue_intake':{'mode':'continuous'}})
        apply(root,old,new,plan,plan)
        self.assertIn('Custom package-signature requirement remains mandatory.',p.read_text())
        self.assertNotIn('Reviewed delivery policy addendum',p.read_text())
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        apply(root,old,new,plan,plan)
        self.assertIn('Custom package-signature requirement remains mandatory.',p.read_text())
    def test_preference_updates_preserve_deliberate_row_waivers(self):
        p=self.factory/'verification.md'
        lines=[]
        for line in p.read_text().splitlines():
            if line.startswith('| G2 |'):
                cells=[v.strip() for v in line.strip().strip('|').split('|')]
                cells[4]='false';line='| '+' | '.join(cells)+' |'
            lines.append(line)
        p.write_text('\n'.join(lines))
        root,old,new,plan=prepare(self.factory,{'done_videos':{'enabled':True}})
        apply(root,old,new,plan,plan)
        self.assertEqual(gate_rows(p.read_text())['G2']['required'],'no')
        root,old,new,plan=prepare(self.factory,{'smoke_gates':{'required':False}})
        apply(root,old,new,plan,plan)
        rows=gate_rows(p.read_text())
        self.assertTrue(all(rows[g]['required']=='no' for g in ('G1','G2','G3')))
        self.assertEqual(rows['A1']['required'],'yes')

if __name__=='__main__':unittest.main(verbosity=2)
