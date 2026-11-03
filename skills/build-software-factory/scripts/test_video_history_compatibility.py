"""Real incremental-writer history remains compatible with reviewed updates."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows
from incremental_records import preview, apply as record
from scaffold import ROOT, render
from update_operations import prepare, apply, video_reactivation_choices, VIDEO_HISTORY_HEADINGS


class VideoHistoryCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name); self.root=self.base/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            path=self.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(body.encode())
        self.path=self.root/'verification.md'

    def snapshot(self):
        return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def observe(self,gate,result):
        change=dict(gate=gate,result=result,revision='a'*40,environment='fixture',evidence='SYNTHETIC '+result,
                    target='',checked_at='2026-11-01T00:00:00Z',exit_status='1')
        args=preview(self.root,'gate',change); record(*args,args[-1])

    def missing_video(self):
        self.observe('V1','FAILED'); self.observe('V1','BLOCKED')
        text=self.path.read_text()
        row=next(line for line in text.splitlines() if line.startswith('| V1 |'))
        self.path.write_bytes(text.replace(row+'\n','').encode())

    def test_history_heading_contract_matches_reconciler_without_runtime_dependency(self):
        from reconcile_evidence import HISTORY_HEADINGS
        self.assertEqual(VIDEO_HISTORY_HEADINGS,HISTORY_HEADINGS)

    def test_unquoted_historical_video_is_not_mistaken_for_current_row(self):
        row=next(line for line in self.path.read_text().splitlines() if line.startswith('| V1 |'))
        for heading in VIDEO_HISTORY_HEADINGS:
            with self.subTest(heading=heading),self.assertRaisesRegex(ValueError,'Unquoted gate row'):
                video_reactivation_choices(heading+'\n'+row+'\n',{'V1':{}},{'V1':False})

    def test_real_writer_then_delivery_and_video_updates_preserve_history(self):
        self.observe('G1','FAILED'); self.observe('G1','BLOCKED')
        old=[line for line in self.path.read_text().splitlines() if line.startswith('> | ')]
        self.assertEqual(self.path.read_text().count('## Prior gate observation'),2)
        for changes,kwargs in (({},dict(delivery_update=True)),({'done_videos':{'enabled':False}},{})):
            before=self.snapshot(); args=prepare(self.root,changes,**kwargs)
            self.assertEqual(before,self.snapshot()); apply(*args,args[-1])
            text=self.path.read_text()
            for row in old:self.assertIn(row,text)
            self.assertIn('SYNTHETIC FAILED',text); self.assertIn('SYNTHETIC BLOCKED',text)
            self.assertEqual(text.count('## Historical observations (not current evidence)'),1)
            self.assertEqual(gate_rows(text)['G1']['result'],'NOT RUN')

    def test_repeated_recognized_history_requires_choice_never_latest_preference(self):
        self.missing_video()
        old=self.path.read_text()
        historical=next(line for line in old.splitlines() if line.startswith('> | V1 |'))
        self.path.write_bytes((old+'\n## Historical observations (not current evidence)\n'+historical+
                              '\n\n## Operator notes\nKeep this rationale.\n').encode())
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'explicit current requiredness'):
            prepare(self.root,{'done_videos':{}})
        self.assertEqual(before,self.snapshot())
        args=prepare(self.root,{'done_videos':{}},video_requiredness={'V1':False})
        self.assertEqual(before,self.snapshot()); apply(*args,args[-1])
        text=self.path.read_text(); row=gate_rows(text)['V1']
        self.assertEqual((row['required'],row['result']),('no','NOT RUN'))
        for name in ('revision','evidence','target','checked_at','exit_status'):self.assertEqual(row[name],'')
        self.assertEqual(text.count(historical),2)
        self.assertIn('SYNTHETIC FAILED',text); self.assertIn('Keep this rationale.',text)

    def test_cli_runtime_restoration_diagnostic_leads_to_valid_reviewed_plan(self):
        self.missing_video(); before=self.snapshot()
        command=[sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.root),'--delivery-gates']
        denied=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(denied.returncode,0)
        self.assertIn('--operations <reviewed-patch.json>',denied.stderr)
        self.assertIn('{"done_videos": {}}',denied.stderr)
        self.assertEqual(before,self.snapshot())
        patch=self.base/'restore.json'; patch.write_text('{"done_videos": {}}')
        before=self.snapshot(); command+=['--operations',str(patch),'--video-requiredness','V1=no']
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(before,self.snapshot())
        token=re.search(r'REVIEW PLAN: ([0-9a-f]{64})',result.stdout)[1]
        refused=subprocess.run(command+['--apply'],capture_output=True,text=True)
        self.assertNotEqual(refused.returncode,0); self.assertEqual(before,self.snapshot())
        result=subprocess.run(command+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        row=gate_rows(self.path.read_text())['V1']
        self.assertEqual((row['required'],row['result'],row['revision']),('no','NOT RUN',''))


if __name__=='__main__':unittest.main()
