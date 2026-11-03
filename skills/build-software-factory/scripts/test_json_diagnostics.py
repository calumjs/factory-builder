"""Named, content-safe JSON failures; disposable factories only, no repair."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gates import assess
from integrity import check, digest, json_diagnostic, read_json
from recover_factory import capture, read_metadata
from scaffold import ROOT, render
from update_operations import prepare


class JsonDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'.software-factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')

    def tearDown(self):self.tmp.cleanup()

    def snapshot(self):return {p.relative_to(self.root):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_malformed_manifest_blocks_all_entry_points_without_changes(self):
        for body,expected in (('{private-content','Invalid JSON'),('{\n<<<<<<< HEAD\nprivate-content\n=======\nother\n>>>>>>> branch\n}','Unresolved merge conflict')):
            (self.root/'manifest.json').write_text(body,encoding='utf-8');before=self.snapshot()
            for operation in (lambda:check(self.root,quiet=True),lambda:assess(self.root,'pre-merge','subject-S'),lambda:prepare(self.root,{}),lambda:capture(self.root)):
                with self.subTest(expected=expected,operation=operation):
                    with self.assertRaises(ValueError) as caught:operation()
                    message=str(caught.exception)
                    self.assertIn(expected,message);self.assertIn('manifest.json',message)
                    self.assertNotIn('private-content',message);self.assertIn('recovery.md',message)
                    self.assertEqual(before,self.snapshot())
            result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/scaffold.py'),'--check',str(self.root)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn(expected,result.stdout+result.stderr)
            self.assertNotIn('private-content',result.stdout+result.stderr)
            self.assertEqual(before,self.snapshot())

    def test_living_and_reviewed_contract_json_are_named(self):
        for name in ('tools.json','task-plan.json','config.json','research.json'):
            path=self.root/name;original=path.read_bytes();manifest=self.root/'manifest.json';original_manifest=manifest.read_bytes()
            path.write_text('{private-content',encoding='utf-8')
            if name in ('config.json','research.json'):
                value=json.loads(original_manifest);value['contracts'][name]=digest(path.read_bytes());manifest.write_text(json.dumps(value))
            with self.assertRaises(ValueError) as caught:check(self.root,quiet=True)
            self.assertIn('Invalid JSON',str(caught.exception));self.assertIn(name,str(caught.exception))
            self.assertNotIn('private-content',str(caught.exception))
            path.write_bytes(original);manifest.write_bytes(original_manifest)

    def test_duplicate_and_nonfinite_json_stay_rejected_and_named(self):
        path=self.root/'tools.json'
        for body,expected in (('{"private-key":1,"private-key":2}','Duplicate JSON'),('{"nested":{"private-key":1,"private-key":2}}','Duplicate JSON'),('{"number":NaN}','Non-finite'),('{"number":Infinity}','Non-finite'),('{"number":-Infinity}','Non-finite')):
            path.write_text(body,encoding='utf-8');before=self.snapshot()
            for operation in (lambda:read_json(path),lambda:check(self.root,quiet=True),lambda:capture(self.root),lambda:read_metadata(path)):
                with self.assertRaises(ValueError) as caught:operation()
                self.assertIn(expected,str(caught.exception));self.assertIn('tools.json',str(caught.exception))
                self.assertNotIn('private-key',str(caught.exception));self.assertEqual(before,self.snapshot())

    def test_diagnostic_escapes_filename_and_does_not_echo_parser_details(self):
        error=ValueError('SENSITIVE parser detail')
        message=str(json_diagnostic('bad\n\x1b.json','SENSITIVE content',error))
        self.assertNotIn('\n',message);self.assertNotIn('\x1b',message);self.assertNotIn('SENSITIVE',message)
        self.assertIn('bad\\n\\u001b.json',message)


if __name__=='__main__':unittest.main()
