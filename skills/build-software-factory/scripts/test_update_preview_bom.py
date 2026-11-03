"""Actual operations CLI previews preserve byte-bound plans across BOM display."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from scaffold import ROOT, render
import update_operations as updater


class UpdatePreviewBomTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'synthetic factory'
        config=json.loads((ROOT/'assets/example-config.json').read_bytes())
        research=json.loads((ROOT/'assets/example-research.json').read_bytes())
        for name,body in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        self.changes={'review':{'record_schema':1,'required_approvals':1,'independent':True}}
        self.patch=self.base/'change.json';self.patch.write_bytes(json.dumps(self.changes).encode())
        self.command=[sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.root),
                      '--operations',str(self.patch),'--review-workflow']

    def snapshot(self):
        return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def cli(self,encoding,*arguments):
        # Encoding is scoped to this disposable subprocess; no interpreter or OS
        # setting is changed. This isolates the leading-BOM regression, not all
        # possible Unicode project content on every legacy terminal.
        result=subprocess.run(self.command+list(arguments),capture_output=True,
                              env={**os.environ,'PYTHONIOENCODING':encoding+':strict'})
        return result.returncode,result.stdout.decode(encoding),result.stderr.decode(encoding)

    def test_retained_bom_preview_is_symmetric_write_free_and_uses_exact_plan_in_both_encodings(self):
        path=self.root/'release-handoff.md'
        raw=b'\xef\xbb\xbf'+path.read_bytes().replace(b'\n',b'\r\n')+b'\r\n'
        path.write_bytes(raw);before=self.snapshot()
        prepared=updater.prepare(self.root,self.changes,review_workflow=True)
        proposed=prepared[2]['release-handoff.md'];self.assertTrue(proposed.startswith(raw))
        first=raw.decode('utf-8-sig').splitlines()[0]
        expected_hashes='FILE release-handoff.md raw SHA256: '+hashlib.sha256(raw).hexdigest()+' -> '+hashlib.sha256(proposed).hexdigest()
        for encoding in ('utf-8','cp1252'):
            with self.subTest(encoding=encoding):
                code,out,err=self.cli(encoding)
                self.assertEqual(code,0,err)
                self.assertIn('UTF-8 BOM: retained for release-handoff.md',out)
                self.assertNotIn('\ufeff',out)
                self.assertNotIn('-'+first,out.splitlines());self.assertNotIn('+'+first,out.splitlines())
                self.assertIn(expected_hashes,out)
                self.assertEqual(re.search(r'REVIEW PLAN: ([0-9a-f]{64})',out)[1],prepared[-1])
                self.assertEqual(self.snapshot(),before)

    def test_display_does_not_remove_bom_from_applied_handoff_or_backup(self):
        path=self.root/'release-handoff.md';raw=b'\xef\xbb\xbf'+path.read_bytes().replace(b'\n',b'\r\n')
        path.write_bytes(raw);prepared=updater.prepare(self.root,self.changes,review_workflow=True)
        code,out,err=self.cli('cp1252');self.assertEqual(code,0,err)
        token=re.search(r'REVIEW PLAN: ([0-9a-f]{64})',out)[1]
        before=self.snapshot();code,out,err=self.cli('cp1252','--apply','--approve-plan','0'*64)
        self.assertNotEqual(code,0);self.assertEqual(self.snapshot(),before)
        code,out,err=self.cli('cp1252','--apply','--approve-plan',token)
        self.assertEqual(code,0,err)
        self.assertEqual(path.read_bytes(),prepared[2]['release-handoff.md'])
        self.assertTrue(path.read_bytes().startswith(raw))
        self.assertEqual((self.base/'.factory-update-backups'/token/'release-handoff.md').read_bytes(),raw)

    def test_no_bom_and_removed_bom_have_truthful_notices_and_distinct_raw_plans(self):
        plain=updater.prepare(self.root,self.changes,review_workflow=True)
        code,out,err=self.cli('cp1252');self.assertEqual(code,0,err);self.assertNotIn('UTF-8 BOM:',out)
        path=self.root/'config.json';raw=b'\xef\xbb\xbf'+path.read_bytes();path.write_bytes(raw)
        before=self.snapshot();prepared=updater.prepare(self.root,self.changes,review_workflow=True)
        self.assertNotEqual(prepared[-1],plain[-1])
        self.assertFalse(prepared[2]['config.json'].startswith(b'\xef\xbb\xbf'))
        code,out,err=self.cli('cp1252');self.assertEqual(code,0,err)
        self.assertIn('UTF-8 BOM: removed for config.json',out);self.assertNotIn('\ufeff',out)
        self.assertIn('FILE config.json raw SHA256: '+hashlib.sha256(raw).hexdigest(),out)
        self.assertEqual(re.search(r'REVIEW PLAN: ([0-9a-f]{64})',out)[1],prepared[-1])
        self.assertEqual(self.snapshot(),before)

    def test_intake_distinguishes_extra_panels_from_default_independent_review(self):
        text=(ROOT/'references/intake.md').read_text(encoding='utf-8')
        self.assertIn('extra reviewers or panels beyond the default single independent reviewer',text)
        self.assertIn("task's risk, budget and data exposure warrant them",text)
        self.assertIn('one required approval, independent review',text)


if __name__=='__main__':unittest.main()
