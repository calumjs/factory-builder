"""Explicit synthetic reactivation choices; no historical result is rehydrated."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from gates import gate_rows
from scaffold import ROOT, render
from update_operations import prepare, apply, parse_video_requiredness


class VideoReactivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.config['operations']={'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(self.config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        self.path=self.root/'verification.md'

    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
    def edit(self,legacy=False):
        lines=[]
        for line in self.path.read_text().splitlines():
            if line.startswith(('| V1 |','| V2 |')):
                cells=[c.strip() for c in line.strip('|').split('|')]
                cells[4]='false' if cells[0]=='V1' else 'n'
                cells[5:11]=['old-subject','PASSED' if cells[0]=='V1' else 'FAILED','private-old-evidence','old-target','2026-11-01T00:00:00Z','manual']
                line='| '+' | '.join(cells[:8] if legacy else cells)+' |'
            lines.append(line)
        self.path.write_bytes(('\n'.join(lines)+'\n').encode())
    def update(self,changes,**kwargs):
        before=self.snapshot();args=prepare(self.root,changes,**kwargs);self.assertEqual(before,self.snapshot())
        apply(*args,args[-1]);return args
    def assert_fresh(self,expected):
        for gate,required in expected.items():
            row=gate_rows(self.path.read_text())[gate]
            self.assertEqual(row['required'],'yes' if required else 'no')
            self.assertEqual(row['result'],'NOT RUN')
            for field in ('revision','evidence','target','checked_at','exit_status'):self.assertEqual(row[field],'')

    def test_disable_reenable_requires_choice_and_preserves_only_history(self):
        self.edit();self.update({'done_videos':{'enabled':False}});before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Reactivated video gates need explicit'):
            prepare(self.root,{'done_videos':{'enabled':True}})
        self.assertEqual(before,self.snapshot())
        self.update({'done_videos':{'enabled':True}},video_requiredness={'V1':False,'V2':False})
        self.assert_fresh({'V1':False,'V2':False})
        self.assertIn('> | V1 |',self.path.read_text());self.assertIn('private-old-evidence',self.path.read_text())

    def test_new_activation_can_choose_optional_without_separate_approval(self):
        # Remove videos from a clean first-use config; no historical preference exists.
        config=json.loads(json.dumps(self.config));config['operations']['done_videos']['enabled']=False
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            (self.root/name).write_bytes(body.encode())
        self.update({'done_videos':{'enabled':True}},video_requiredness={'V1':False})
        self.assert_fresh({'V1':False,'V2':True})

    def test_trigger_removal_readdition_with_selective_updates_keeps_existing_choice(self):
        self.edit();self.update({'done_videos':{'triggers':['post_g3_release']}},selective_gates=True)
        before=gate_rows(self.path.read_text())['V1']['required']
        self.update({'done_videos':{'triggers':['pre_merge_preview','post_g3_release']}},selective_gates=True,video_requiredness={'V2':True})
        self.assertEqual(gate_rows(self.path.read_text())['V1']['required'],before)
        self.assert_fresh({'V2':True})

    def test_missing_current_row_with_enabled_prior_config_requires_explicit_restoration(self):
        self.edit();text=self.path.read_text()
        old=next(line for line in text.splitlines() if line.startswith('| V1 |'))
        text=text.replace(old+'\n','')
        text+='\n## Historical observations (not current evidence)\n> '+old+'\n'
        self.path.write_bytes(text.encode());before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'explicit current requiredness'):
            prepare(self.root,{'done_videos':{'enabled':True}})
        self.assertEqual(before,self.snapshot())
        self.update({'done_videos':{'enabled':True}},video_requiredness={'V1':False})
        self.assert_fresh({'V1':False})
        self.assertEqual(gate_rows(self.path.read_text())['V2']['required'],'no')
        self.assertIn('> '+old,self.path.read_text())

    def test_multiple_cycles_never_infer_latest_historical_preference(self):
        self.edit()
        for selective,choice in ((False,False),(True,True),(False,False)):
            self.update({'done_videos':{'enabled':False}},selective_gates=selective)
            before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'explicit current requiredness'):
                prepare(self.root,{'done_videos':{'enabled':True}},selective_gates=selective)
            self.assertEqual(before,self.snapshot())
            self.update({'done_videos':{'enabled':True}},selective_gates=selective,video_requiredness={'V1':choice,'V2':choice})
            self.assert_fresh({'V1':choice,'V2':choice})

    def test_legacy_eight_column_rows_and_alias_flags_survive(self):
        self.edit(legacy=True);self.update({'done_videos':{'enabled':False}})
        self.update({'done_videos':{'enabled':True}},video_requiredness={'V1':False,'V2':True})
        self.assert_fresh({'V1':False,'V2':True});self.assertIn('private-old-evidence',self.path.read_text())

    def test_unused_or_invalid_choices_refuse_without_mutation(self):
        before=self.snapshot()
        for choices in ({'V1':False},{'A1':False},{'v1':False},{'V1':0},{'V1':'no'},[],{'V2':None}):
            with self.subTest(choices=choices),self.assertRaises(ValueError):
                prepare(self.root,{'done_videos':{'enabled':True}},video_requiredness=choices)
            self.assertEqual(before,self.snapshot())
        with self.assertRaises(ValueError):prepare(self.root,{},video_requiredness={'V1':False})
        with self.assertRaises(ValueError):prepare(self.root,{'done_videos':{'enabled':False}},video_requiredness={'V1':False})
        self.assertEqual(before,self.snapshot())

    def test_malformed_ambiguous_or_relocated_history_does_not_become_fresh(self):
        self.edit();self.update({'done_videos':{'enabled':False}});original=self.path.read_text()
        for text in (original+'\n## Historical observations (not current evidence)\n',
                     original.replace('## Historical observations (not current evidence)',' ## Historical observations (not current evidence)',1),
                     original.replace('> | V1 |','| V1 |',1),
                     original.replace('> | V1 |','> | V1 malformed |',1),
                     original.replace('> | V1 |','>  | V1 |',1),
                     original.replace('## Historical observations (not current evidence)','## Other notes',1),
                     original.replace('| false |','| unknown |',1)):
            self.path.write_bytes(text.encode());before=self.snapshot()
            with self.assertRaises(ValueError):prepare(self.root,{'done_videos':{'enabled':True}},video_requiredness={'V1':False,'V2':False})
            self.assertEqual(before,self.snapshot())

    def test_duplicate_active_rows_refuse(self):
        row=next(line for line in self.path.read_text().splitlines() if line.startswith('| V1 |'))
        self.path.write_bytes((self.path.read_text()+'\n'+row+'\n').encode());before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Duplicate'):prepare(self.root,{'done_videos':{'enabled':False}})
        self.assertEqual(before,self.snapshot())

    def test_choice_is_bound_to_preview_digest(self):
        self.edit();self.update({'done_videos':{'enabled':False}})
        a=prepare(self.root,{'done_videos':{'enabled':True}},video_requiredness={'V1':False,'V2':False})
        b=prepare(self.root,{'done_videos':{'enabled':True}},video_requiredness={'V1':True,'V2':False})
        self.assertNotEqual(a[-1],b[-1]);before=self.snapshot()
        with self.assertRaises(ValueError):apply(*b,a[-1])
        self.assertEqual(before,self.snapshot())

    def test_cli_choice_preview_is_visible_and_uses_existing_apply_approval(self):
        self.edit();self.update({'done_videos':{'enabled':False}})
        patch=self.base/'change.json';patch.write_text(json.dumps({'done_videos':{'enabled':True}}));before=self.snapshot()
        cmd=[sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.root),'--operations',str(patch),'--video-requiredness','v1=NO','--video-requiredness','V2=yes']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('VIDEO REQUIREDNESS: V1=optional',result.stdout)
        self.assertEqual(before,self.snapshot());token=re.search(r'REVIEW PLAN: ([0-9a-f]{64})',result.stdout)[1]
        result=subprocess.run(cmd+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assert_fresh({'V1':False,'V2':True})

    def test_cli_normalization_detects_duplicates_and_invalid_tokens(self):
        self.assertEqual(parse_video_requiredness(['v1=NO','V2=YES']),{'V1':False,'V2':True})
        for args in (['V1=no','v1=yes'],['G1=no'],['V1=false'],['V1=0'],['V1=no extra']):
            with self.assertRaises(ValueError):parse_video_requiredness(args)


if __name__=='__main__':unittest.main()
