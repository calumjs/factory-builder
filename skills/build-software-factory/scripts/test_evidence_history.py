"""Offline migration regressions for retained observations and idempotent history."""
import json
from pathlib import Path
import tempfile
import unittest

from gates import HEADER, gate_rows
from scaffold import ROOT, render
from update_operations import apply, prepare, refreshed_verification


class EvidenceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'.software-factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.files=render(self.config,self.research)
        for name,body in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    @staticmethod
    def edit(text,gate,values):
        lines=[]
        for line in text.splitlines():
            if line.startswith('| '+gate+' |'):
                cells=[c.strip() for c in line.strip('|').split('|')]
                for index,value in values.items():cells[index]=value
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        return '\n'.join(lines)+'\n'

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def refresh(self,text):
        return refreshed_verification(text,self.config,self.research,prior_config=self.config)

    def test_refresh_preserves_failed_custom_optional_and_extra_rows_without_carry_forward(self):
        text=self.edit(self.files['verification.md'],'G1',{5:'old-subject',6:'FAILED',7:'SYNTHETIC failure log'})
        text=self.edit(text,'G2',{2:'Custom planned check',3:'custom environment'})
        text=self.edit(text,'A1',{4:'no'})
        text+='\n| X1 | pre-merge | Extra required check | custom | yes | | NOT RUN | | | | |\n'
        original_rows=[line for line in text.splitlines() if line.startswith('| ') and line.split('|')[1].strip() in ('G1','G2','A1','X1')]
        once=self.refresh(text)
        for row in original_rows:self.assertIn('> '+row,once)
        self.assertNotIn('> | G3 |',once)
        self.assertTrue(all(row['result']=='NOT RUN' for row in gate_rows(once).values()))
        self.assertEqual(gate_rows(once)['A1']['required'],'no')
        self.assertEqual(gate_rows(once)['X1']['design'],'Extra required check')
        self.assertEqual(self.refresh(once),once)

    def test_repeated_preview_apply_keeps_one_history_and_current_table(self):
        path=self.root/'verification.md'
        path.write_text(self.edit(path.read_text(encoding='utf-8'),'G1',{6:'FAILED'}),encoding='utf-8')
        for enabled in (True,False):
            before=self.snapshot()
            root,old,new,plan=prepare(self.root,{'done_videos':{'enabled':enabled}})
            self.assertEqual(self.snapshot(),before)
            apply(root,old,new,plan,plan)
        text=path.read_text(encoding='utf-8')
        self.assertEqual(text.count('## Historical observations (not current evidence)'),1)
        self.assertEqual(text.count('## Current delivery gate records'),1)
        self.assertEqual(text.count(HEADER.splitlines()[0]),1)
        self.assertIn('> | G1 |',text)
        self.assertIn('FAILED',text)
        self.assertIn('> | V1 |',text)
        self.assertNotIn('> | G2 |',text)
        self.assertNotIn('V1',gate_rows(text))

    def test_optional_unrun_choice_is_retained_when_defaults_are_explicitly_reset(self):
        text=self.edit(self.files['verification.md'],'G1',{4:'no'})
        refreshed=refreshed_verification(text,self.config,self.research,True,self.config)
        self.assertTrue(any(line.startswith('> | G1 |') and '| no |' in line for line in refreshed.splitlines()))
        self.assertEqual(gate_rows(refreshed)['G1']['required'],'yes')

    def test_existing_duplicate_section_headers_are_consolidated_without_losing_notes(self):
        original=self.edit(self.files['verification.md'],'G1',{5:'old',6:'FAILED',7:'SYNTHETIC old failure'})
        first=self.refresh(original)
        historical=next(line for line in first.splitlines() if line.startswith('> | G1 |'))
        messy=first+'\n## Historical observations (not current evidence)\n'+historical+'\n\n## Operator notes\nRetain this review rationale.\n\n## Current delivery gate records\n'+HEADER+'\n'
        result=self.refresh(messy)
        self.assertEqual(result.count('## Historical observations (not current evidence)'),1)
        self.assertEqual(result.count('## Current delivery gate records'),1)
        self.assertEqual(result.count(HEADER.splitlines()[0]),1)
        self.assertEqual(result.count(historical),2)  # Existing repeated history is not erased.
        self.assertIn('## Operator notes\nRetain this review rationale.',result)
        self.assertEqual(self.refresh(result),result)

    def test_duplicate_active_rows_still_block_before_any_write(self):
        path=self.root/'verification.md';text=path.read_text(encoding='utf-8')
        text+='\n'+next(line for line in text.splitlines() if line.startswith('| G1 |'))+'\n'
        path.write_text(text,encoding='utf-8');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Duplicate source gate row'):
            prepare(self.root,{},delivery_update=True)
        self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
