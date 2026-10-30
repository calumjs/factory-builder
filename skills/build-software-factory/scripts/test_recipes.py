"""Offline design/update regressions; no scheduling, capture or narration performed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch
from gates import gate_rows, policy_controls, requirements
from integrity import check, digest
from operations import controls, operations
from recipes import INTAKE_FIELDS, VIDEO_FIELDS, intake_design, video_design, proposal
from scaffold import ROOT, render, validate
from update_operations import prepare, apply, LEGACY_DASHBOARD_OPERATIONS


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'.software-factory';self.root.mkdir()
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.write()

    def tearDown(self):self.tmp.cleanup()

    def write(self):
        for name,body in render(self.config,self.research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_defaults_are_draft_around_clock_without_mutating_legacy_controls(self):
        config=copy.deepcopy(self.config)
        current=controls(config)
        self.assertEqual(current['issue_intake']['mode'],'one_shot')
        self.assertFalse(current['done_videos']['enabled'])
        self.assertFalse(INTAKE_FIELDS & set(current['issue_intake']))
        self.assertFalse(VIDEO_FIELDS & set(current['done_videos']))
        self.assertEqual(intake_design(current['issue_intake'])['coverage'],'around_the_clock')
        self.assertEqual(intake_design(current['issue_intake'])['window'],'none')
        self.assertEqual(self.config,config)
        self.assertEqual(policy_controls((self.root/'policy.md').read_text()),current)
        self.assertFalse(list(self.root.rglob('*.mp4')))
        self.assertFalse(list(self.root.rglob('*.webm')))

    def test_explicit_window_and_mechanism_are_project_choices(self):
        self.config['operations']={'issue_intake':{'mode':'continuous','coverage':'operator_window',
             'mechanism':'polling','cadence':'Every permitted interval','timezone':'Australia/Sydney',
             'window':'Operator-chosen weekday window','window_evidence':'Synthetic operator choice, not actual authority'}}
        validate(self.config)
        design=intake_design(operations(self.config)['issue_intake'])
        self.assertEqual(design['coverage'],'operator_window')
        self.assertEqual(design['window'],'Operator-chosen weekday window')
        self.assertEqual(operations(self.config)['issue_intake']['status'],'disabled')
        self.config['operations']['issue_intake']={'mode':'continuous','mechanism':'event_driven'}
        self.assertEqual(intake_design(operations(self.config)['issue_intake'])['mechanism'],'event_driven')
        self.assertEqual(intake_design(operations(self.config)['issue_intake'])['coverage'],'around_the_clock')

    def test_ambiguous_windows_and_invalid_schedule_metadata_are_refused(self):
        for fields in ({'coverage':'business_hours'},{'window':'09-17'},{'coverage':'operator_window'},
                       {'coverage':'operator_window','window':'09-17','timezone':'unconfirmed: zone','window_evidence':'chosen'},
                       {'mechanism':'cron'},{'cadence':5},{'window_evidence':True}):
            self.config['operations']={'issue_intake':fields}
            with self.assertRaises(ValueError):validate(self.config)

    def test_video_tool_voice_and_captions_are_explicit_choices_not_commands(self):
        marker=self.base/'should-not-exist'
        self.config['operations']={'done_videos':{'enabled':True,'composition':'Existing peer editor',
             'voice_provider':'Explicit project alternative','delivery_channel':'Local artifact only',
             'branding':'Synthetic project','duration_seconds':75,'captions':False,'media_format':'webm'}}
        validate(self.config);self.write()
        design=video_design(operations(self.config)['done_videos'])
        self.assertEqual(design['voice_provider'],'Explicit project alternative')
        self.assertFalse(design['captions']);self.assertEqual(design['media_format'],'webm')
        self.config['operations']['done_videos']['composition']='create marker '+str(marker)
        render(self.config,self.research)
        self.assertFalse(marker.exists())
        self.assertIn('Explicit project alternative',(self.root/'release-handoff.md').read_text())
        check(self.root,quiet=True)

    def test_malformed_video_fields_and_claimed_permission_fields_rejected(self):
        for fields in ({'duration_seconds':True},{'duration_seconds':0},{'duration_seconds':601},
                       {'duration_seconds':float('nan')},{'captions':'true'},{'media_format':'exe'},
                       {'composition':''},{'voice_provider':[]},{'narration_approved':True}):
            self.config['operations']={'done_videos':fields}
            with self.assertRaises(ValueError):validate(self.config)

    def test_schedule_update_refreshes_only_known_proposal_and_controls(self):
        before=self.snapshot()
        changes={'issue_intake':{'mode':'continuous','coverage':'operator_window','mechanism':'polling',
                 'cadence':'Operator fitted','timezone':'UTC','window':'Chosen hours','window_evidence':'Synthetic explicit choice'}}
        root,old,new,plan=prepare(self.root,changes)
        self.assertEqual(before,self.snapshot())
        apply(root,old,new,plan,plan)
        config=json.loads((root/'config.json').read_text())
        policy=(root/'policy.md').read_text()
        self.assertEqual(policy_controls(policy),controls(config))
        self.assertIn(proposal('intake',operations(config)['issue_intake']),policy)
        for name in ('task-plan.json','verification.md','release-handoff.md','tools.json'):
            self.assertEqual((root/name).read_bytes(),before[name])
        check(root,quiet=True)

    def test_partial_video_patch_preserves_other_fields_custom_handoff_and_waivers(self):
        self.config['operations']={'done_videos':{'enabled':True,'voice_provider':'Chosen voice','composition':'Chosen editor'}}
        self.write()
        handoff=self.root/'release-handoff.md';handoff.write_text(handoff.read_text()+'\nCustom human delivery note.\n')
        verification=self.root/'verification.md';lines=[]
        for line in verification.read_text().splitlines():
            if line.startswith('| V1 |'):
                cells=line.split('|');cells[5]=' no ';cells[7]=' FAILED ';line='|'.join(cells)
            lines.append(line)
        verification.write_text('\n'.join(lines))
        root,old,new,plan=prepare(self.root,{'done_videos':{'duration_seconds':90}})
        apply(root,old,new,plan,plan)
        config=json.loads((root/'config.json').read_text())
        self.assertEqual(config['operations']['done_videos']['voice_provider'],'Chosen voice')
        self.assertEqual(config['operations']['done_videos']['composition'],'Chosen editor')
        self.assertIn('Custom human delivery note.',handoff.read_text())
        self.assertIn('"duration_seconds": 90',handoff.read_text())
        rows=gate_rows(verification.read_text())
        self.assertEqual(rows['V1']['required'],'no')
        self.assertIn('> | V1 |',verification.read_text())  # FAILED remains historical, not a pass.
        self.assertEqual(rows['V1']['result'],'NOT RUN')
        check(root,quiet=True)

    def test_custom_recipe_block_refuses_update_without_discarding_content(self):
        for kind,name,changes in (('intake','policy.md',{'issue_intake':{'mode':'continuous'}}),
                                  ('video','release-handoff.md',{'done_videos':{'enabled':True}})):
            self.write()
            path=self.root/name
            path.write_text(path.read_text().replace('<!-- factory-'+kind+'-design:end -->','Custom reviewed block note.\n<!-- factory-'+kind+'-design:end -->'))
            if name=='policy.md':
                manifest=json.loads((self.root/'manifest.json').read_text());manifest['contracts'][name]=digest(path.read_bytes())
                (self.root/'manifest.json').write_text(json.dumps(manifest))
            before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'Customized'):prepare(self.root,changes)
            self.assertEqual(before,self.snapshot())

    def test_legacy_factory_without_recipe_blocks_can_adopt_preferences_narrowly(self):
        for kind,name in (('intake','policy.md'),('video','release-handoff.md')):
            path=self.root/name;body=path.read_text();start=body.index('<!-- factory-'+kind+'-design:start -->');end=body.index('<!-- factory-'+kind+'-design:end -->')+len('<!-- factory-'+kind+'-design:end -->')
            path.write_text(body[:start]+body[end:])
        manifest=json.loads((self.root/'manifest.json').read_text());manifest['contracts']['policy.md']=digest((self.root/'policy.md').read_bytes())
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        root,old,new,plan=prepare(self.root,{'issue_intake':{'mode':'continuous'},'done_videos':{'enabled':True}})
        apply(root,old,new,plan,plan)
        self.assertIn('around_the_clock',(root/'policy.md').read_text())
        self.assertIn('ElevenLabs',(root/'release-handoff.md').read_text())
        self.assertEqual(policy_controls((root/'policy.md').read_text()),controls(json.loads((root/'config.json').read_text())))
        check(root,quiet=True)

    def test_recipe_metadata_does_not_move_video_gate_before_release(self):
        self.config['operations']={'done_videos':{'enabled':True,'duration_seconds':30,'composition':'Peer editor'}}
        self.assertEqual(requirements(self.config,self.research)['V1']['stage'],'post-merge')
        self.assertNotIn('V2',requirements(self.config,self.research))
        self.config['operations']['done_videos']['enabled']=False
        self.assertNotIn('V1',requirements(self.config,self.research))


    def legacy_dashboard(self):
        source=(ROOT/'scripts/fixtures/v1_2_operations.txt').read_bytes()
        self.assertEqual(digest(source),LEGACY_DASHBOARD_OPERATIONS)
        (self.root/'dashboard/operations.py').write_bytes(source)
        (self.root/'dashboard/recipes.py').unlink()
        manifest=json.loads((self.root/'manifest.json').read_text())
        manifest['contracts']['dashboard/operations.py']=digest(source)
        manifest['contracts'].pop('dashboard/recipes.py')
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        check(self.root,quiet=True)

    def dashboard(self):
        return subprocess.run([sys.executable,str(self.root/'dashboard/dashboard.py'),'--output',str(self.base/'overview.html'),'--replace'],capture_output=True,text=True)

    def test_known_v1_2_runtime_needs_explicit_previewed_compatibility_upgrade(self):
        self.legacy_dashboard()
        self.assertEqual(self.dashboard().returncode,0)
        before=self.snapshot();changes={'done_videos':{'composition':'Existing editor'}}
        with self.assertRaisesRegex(ValueError,'recipe-runtime'):prepare(self.root,changes)
        self.assertEqual(before,self.snapshot())
        root,old,new,plan=prepare(self.root,changes,recipe_runtime=True)
        self.assertEqual(before,self.snapshot())
        self.assertIsNone(old['dashboard/recipes.py'])
        backup=apply(root,old,new,plan,plan)
        self.assertEqual(json.loads((backup/'added-files.json').read_text()),['dashboard/recipes.py'])
        self.assertEqual((backup/'dashboard/operations.py').read_bytes(),before['dashboard/operations.py'])
        result=self.dashboard();self.assertEqual(result.returncode,0,result.stderr)
        check(root,quiet=True)

    def test_custom_runtime_is_preserved_instead_of_overwritten(self):
        self.legacy_dashboard()
        path=self.root/'dashboard/operations.py';path.write_bytes(path.read_bytes()+b'\n# Customized runtime\n')
        manifest=json.loads((self.root/'manifest.json').read_text());manifest['contracts']['dashboard/operations.py']=digest(path.read_bytes())
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):prepare(self.root,{'done_videos':{'composition':'Editor'}},recipe_runtime=True)
        self.assertEqual(before,self.snapshot())

    def test_runtime_upgrade_rejects_concurrent_dependency_and_binds_review_digest(self):
        self.legacy_dashboard()
        root,old,new,plan=prepare(self.root,{'issue_intake':{'coverage':'around_the_clock'}},recipe_runtime=True)
        before=self.snapshot()
        with self.assertRaises(ValueError):apply(root,old,new,plan,'wrong')
        self.assertEqual(before,self.snapshot())
        path=root/'dashboard/recipes.py';path.write_text('Concurrent user file')
        with self.assertRaises(ValueError):apply(root,old,new,plan,plan)
        self.assertEqual(path.read_text(),'Concurrent user file')

    def test_interrupted_runtime_upgrade_preserves_added_file_recovery_record(self):
        self.legacy_dashboard()
        root,old,new,plan=prepare(self.root,{'done_videos':{'composition':'Editor'}},recipe_runtime=True)
        import os
        replace=os.replace
        def fail_manifest(source,target):
            if Path(target).name=='manifest.json':raise OSError('Synthetic interruption')
            return replace(source,target)
        with patch('update_operations.os.replace',side_effect=fail_manifest):
            with self.assertRaises(OSError):apply(root,old,new,plan,plan)
        backup=self.base/'.factory-update-backups'/plan
        self.assertEqual((backup/'manifest.json').read_bytes(),old['manifest.json'])
        self.assertEqual(json.loads((backup/'added-files.json').read_text()),['dashboard/recipes.py'])
        self.assertTrue((root/'dashboard/recipes.py').is_file())
        with self.assertRaises(ValueError):check(root,quiet=True)

if __name__=='__main__':unittest.main()
