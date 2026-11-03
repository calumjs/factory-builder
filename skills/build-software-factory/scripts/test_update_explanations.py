"""Captured-row preview explanations must not change migration or approval semantics."""
import difflib
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gates import gate_rows
from scaffold import ROOT, render
from update_operations import apply, dumps, main, prepare, verification_explanations


class UpdateExplanationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.factory=self.base/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(config,research).items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def edit(self,ident,changes):
        path=self.factory/'verification.md';lines=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| '+ident+' |'):
                cells=[v.strip() for v in line.strip('|').split('|')]
                for index,value in changes.items():cells[index]=value
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')

    def preview(self,changes):
        before=self.snapshot();prepared=prepare(self.factory,changes)
        _,old,new,plan=prepared
        fingerprints={name:{'before':hashlib.sha256(old[name]).hexdigest() if old[name] is not None else None,'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(new.items())}
        self.assertEqual(plan,hashlib.sha256(dumps({'factory':str(prepared[0]),'files':fingerprints}).encode('utf-8')).hexdigest())
        old_copy=dict(old);new_copy=dict(new)
        messages=verification_explanations(old,new)
        self.assertEqual(old,old_copy);self.assertEqual(new,new_copy);self.assertEqual(before,self.snapshot())
        self.assertEqual(prepare(self.factory,changes),prepared)
        return prepared,{line.split(':',1)[0][4:]:line for line in messages}

    def test_failed_optional_custom_and_extra_rows_report_actual_changes_privately(self):
        self.edit('G1',{5:'private-subject',6:'FAILED',7:'private-evidence',8:'private-target'})
        self.edit('G2',{2:'private-custom-design',3:'private-environment'})
        self.edit('A1',{4:'no'})
        path=self.factory/'verification.md'
        path.write_text(path.read_text(encoding='utf-8')+'| X1 | pre-merge | private-extra-design | fixture | yes | | NOT RUN | | | | |\n',encoding='utf-8')
        prepared,rows=self.preview({'done_videos':{'enabled':True}})
        self.assertIn('RESET:',rows['G1']);self.assertIn('ARCHIVED: prior result or observation fields',rows['G1'])
        self.assertIn('UPDATED:',rows['G2']);self.assertIn('ARCHIVED: prior unexecuted row plan',rows['G2'])
        self.assertIn('RETAINED:',rows['A1']);self.assertIn('prior optional unexecuted plan',rows['A1']);self.assertIn('requiredness retained: optional',rows['A1'])
        self.assertIn('RETAINED:',rows['X1']);self.assertIn('ARCHIVED:',rows['X1'])
        self.assertIn('ADDED:',rows['V1']);self.assertIn('NOT ARCHIVED:',rows['G3'])
        self.assertNotIn('private-',str(rows))
        active=gate_rows(prepared[2]['verification.md'].decode('utf-8'))
        self.assertEqual(active['G1']['result'],'NOT RUN');self.assertEqual(active['A1']['required'],'no')
        self.assertEqual(active['X1']['design'],'private-extra-design')

    def test_retirement_and_repeated_noop_do_not_claim_new_archive(self):
        prepared,_=self.preview({'done_videos':{'enabled':True}})
        apply(*prepared,prepared[3])
        self.edit('V1',{6:'FAILED',7:'private-video'})
        prepared,rows=self.preview({'done_videos':{'enabled':False}})
        self.assertIn('RETIRED:',rows['V1']);self.assertIn('ARCHIVED:',rows['V1'])
        apply(*prepared,prepared[3])
        prepared,rows=self.preview({'done_videos':{'enabled':False}})
        self.assertFalse(prepared[2]);self.assertNotIn('V1',rows)
        self.assertTrue(all('RETAINED:' in row and 'ARCHIVED:' not in row.replace('NOT ARCHIVED:','') for row in rows.values()))
        before=self.snapshot();self.assertIsNone(apply(*prepared,prepared[3]));self.assertEqual(before,self.snapshot())

    def test_unrelated_patch_retains_observations_without_archiving(self):
        self.edit('G1',{6:'FAILED',7:'private-failure'})
        prepared,rows=self.preview({'issue_intake':{'mode':'continuous'}})
        self.assertNotIn('verification.md',prepared[2]);self.assertIn('RETAINED:',rows['G1'])
        self.assertIn('NOT ARCHIVED:',rows['G1']);self.assertNotIn('RESET:',rows['G1'])

    def test_repeated_custom_plan_history_is_reported_as_existing(self):
        self.edit('A1',{4:'no'})
        prepared,_=self.preview({'done_videos':{'enabled':False}});apply(*prepared,prepared[3])
        _,rows=self.preview({'done_videos':{'enabled':False}})
        self.assertIn('HISTORY RETAINED:',rows['A1']);self.assertIn('no new copy',rows['A1'])
        self.assertNotIn('ARCHIVED:',rows['A1'])

    def test_explicit_requiredness_change_is_visible_without_implying_new_evidence(self):
        self.edit('G1',{4:'no'})
        prepared,rows=self.preview({'smoke_gates':{'required':True}})
        self.assertIn('requiredness changed',rows['G1']);self.assertIn('ARCHIVED:',rows['G1'])
        self.assertEqual(gate_rows(prepared[2]['verification.md'].decode('utf-8'))['G1']['result'],'NOT RUN')

    def test_legacy_rows_normalize_without_false_observation_reset(self):
        row=b'| G1 | pre-merge | fixture | fixture | Y | | NOT RUN | |\n'
        new=b'| G1 | pre-merge | fixture | fixture | yes | | NOT RUN | | | | |\n'
        messages=verification_explanations({'verification.md':row},{'verification.md':new})
        self.assertIn('RETAINED:',messages[0]);self.assertNotIn('RESET:',messages[0])

    def test_cli_prints_summary_and_unchanged_hashes_diff_and_plan_without_writes(self):
        self.edit('G1',{6:'FAILED',7:'private-failure'})
        patch_file=self.base/'patch.json';patch_file.write_text('{"done_videos":{"enabled":false}}',encoding='utf-8')
        prepared,_=self.preview(json.loads(patch_file.read_text()));before=self.snapshot()
        command=[sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.factory),'--operations',str(patch_file)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,self.snapshot())
        self.assertIn('REVIEW PLAN: '+prepared[3],result.stdout)
        self.assertIn('ROW G1: RESET:',result.stdout)
        self.assertNotIn('private-failure','\n'.join(line for line in result.stdout.splitlines() if line.startswith('ROW ')))
        self.assertIn('--- verification.md (current)',result.stdout);self.assertIn('+++ verification.md (proposed)',result.stdout)
        # Capture before Windows console/subprocess newline translation to compare
        # the exact diff emitted from the raw captured file bytes.
        output=io.StringIO()
        with patch('sys.argv',command[2:]),redirect_stdout(output):main()
        self.assertEqual(before,self.snapshot())
        for name,data in prepared[2].items():
            self.assertIn('FILE '+name+' raw SHA256: '+hashlib.sha256(prepared[1][name]).hexdigest()+' -> '+hashlib.sha256(data).hexdigest(),result.stdout)
            captured_diff=''.join(difflib.unified_diff(prepared[1][name].decode('utf-8-sig').splitlines(True),data.decode('utf-8').splitlines(True),fromfile=name+' (current)',tofile=name+' (proposed)'))
            self.assertIn(captured_diff,output.getvalue())

    def test_explanations_do_not_weaken_wrong_digest_or_changed_source_refusal(self):
        prepared,_=self.preview({'done_videos':{'enabled':True}});before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'exact --approve-plan'):apply(*prepared,'wrong')
        self.assertEqual(before,self.snapshot())
        self.edit('G1',{6:'FAILED'});changed=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):apply(*prepared,prepared[3])
        self.assertEqual(changed,self.snapshot())


if __name__=='__main__':unittest.main()
