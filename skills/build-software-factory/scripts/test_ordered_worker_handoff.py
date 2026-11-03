"""Ordered fallback proposals stay inert and task copies stay outside contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from integrity import check, digest
from scaffold import ROOT, render


class OrderedWorkerHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.project=self.parent/'project';self.project.mkdir()
        self.root=self.project/'.software-factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def write(self):
        files=render(self.config,self.research)
        for name,body in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        return files

    def test_rendered_ordered_plan_is_unconfigured_hashed_and_has_no_runtime_effects(self):
        before=copy.deepcopy(self.config)
        with patch('subprocess.Popen',side_effect=AssertionError('No worker or command may launch')), patch('socket.create_connection',side_effect=AssertionError('No provider may be contacted')):
            files=render(self.config,self.research)
        self.assertEqual(self.config,before);self.assertEqual(list(self.project.iterdir()),[])
        self.assertEqual(json.loads(files['config.json']),self.config)
        self.assertNotIn('workers',json.loads(files['config.json']).get('operations',{}))
        handoff=files['worker-handoff.md'];flat=' '.join(handoff.split())
        for text in ('| Priority | Provider / existing recipe |','Authority and data, cost, path and action boundaries',
                     'Availability / evidence','Stop or pause conditions','Unconfirmed primary','No fallback configured',
                     'shared cost, time, concurrency and retry budget','empty transcript alone does not establish failure',
                     'location outside the managed factory before filling it','reviewed selective contract/manifest update'):
            self.assertIn(text,flat)
        plan=files['.claude/skills/factory-plan/SKILL.md']
        self.assertIn('ordered worker table',plan);self.assertIn('approved task-specific location outside the factory',plan)
        manifest=json.loads(files['manifest.json'])
        self.assertEqual(manifest['contracts']['worker-handoff.md'],digest(handoff))
        self.assertNotIn('worker-handoff.md',manifest['living'])

    def test_external_task_copy_can_be_filled_without_changing_factory_or_manifest(self):
        self.write();before=self.snapshot();handoff=self.project/'T1-handoff.md'
        handoff.write_bytes((self.root/'worker-handoff.md').read_bytes())
        handoff.write_text(handoff.read_text(encoding='utf-8').replace('Task ID / owner:',
                           'Task ID / owner: T1 / SYNTHETIC operator').replace('Unconfirmed primary',
                           'SYNTHETIC proposed local worker; not executed'),encoding='utf-8')
        check(self.root,quiet=True)
        self.assertEqual(before,self.snapshot());self.assertNotIn('T1-handoff.md',before)

    def test_unreviewed_template_edit_fails_without_rebaselining(self):
        self.write();manifest=(self.root/'manifest.json').read_bytes()
        path=self.root/'worker-handoff.md';path.write_bytes(path.read_bytes()+b'\nSYNTHETIC unreviewed run note\n')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Contract integrity mismatch: worker-handoff.md'):check(self.root,quiet=True)
        self.assertEqual(before,self.snapshot());self.assertEqual((self.root/'manifest.json').read_bytes(),manifest)

    def test_existing_custom_handoff_is_preserved_until_separate_selective_adoption(self):
        self.write();path=self.root/'worker-handoff.md'
        path.write_text('# SYNTHETIC older custom handoff\nPermitted fallback: none\n',encoding='utf-8')
        manifest=self.root/'manifest.json';value=json.loads(manifest.read_text(encoding='utf-8'))
        value['contracts']['worker-handoff.md']=digest(path.read_bytes());manifest.write_text(json.dumps(value),encoding='utf-8')
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/scaffold.py'),'--check',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertEqual(before,self.snapshot());self.assertNotIn('Ordered worker plan',path.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
