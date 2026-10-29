"""Isolated regression tests for mutable state, evidence, portability and controls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from integrity import check
from scaffold import ROOT, render, validate

class OperatingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.factory = self.base/'.software-factory'
        self.factory.mkdir()
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())
        self.write_factory()
    def tearDown(self):
        self.temp.cleanup()
    def write_factory(self):
        for name,body in render(self.config,self.research).items():
            p = self.factory/name; p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(body.encode('utf-8'))
    def status(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'scripts/status.py'),'--factory',str(self.factory),
            '--task','T1','--status','done','--result','passed','--check','synthetic acceptance check',
            '--evidence','SYNTHETIC fixture passed; not a live application result','--revision','fixture-rev',
            '--environment','isolated-test',*args],capture_output=True,text=True)
    def test_living_evidence_edit_does_not_break_contract_check(self):
        (self.factory/'verification.md').write_text('Operator records a new observed result.\n')
        (self.factory/'learning-log.md').write_text('New lesson.\n')
        check(self.factory,quiet=True)
    def test_crlf_and_bom_check_without_rebaseline(self):
        for p in self.factory.rglob('*'):
            if p.is_file():
                p.write_bytes(b'\xef\xbb\xbf'+p.read_bytes().replace(b'\n',b'\r\n'))
        check(self.factory,quiet=True)
    def test_corrupt_living_json_rejected(self):
        (self.factory/'task-plan.json').write_text('{bad json')
        with self.assertRaises(ValueError):check(self.factory,quiet=True)
    def test_unexpected_file_rejected(self):
        (self.factory/'unexpected.txt').write_text('unexpected')
        with self.assertRaises(ValueError):check(self.factory,quiet=True)
    def test_legacy_manifest_is_not_automatically_migrated(self):
        p=self.factory/'manifest.json';p.write_text('{"schema":1,"files":{}}')
        before=p.read_bytes()
        with self.assertRaises(ValueError):check(self.factory,quiet=True)
        self.assertEqual(p.read_bytes(),before)
    def test_preview_does_not_write_status(self):
        before={str(p):p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}
        r=self.status();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.factory.rglob('*') if p.is_file()})
    def test_atomic_task_and_evidence_record(self):
        r=self.status('--apply');self.assertEqual(r.returncode,0,r.stderr)
        plan=json.loads((self.factory/'task-plan.json').read_text())
        self.assertEqual(plan['tasks'][0]['status'],'done')
        event=plan['events'][0]
        self.assertEqual(event['task_id'],'T1');self.assertEqual(event['revision'],'fixture-rev')
        self.assertEqual(event['result'],'passed');self.assertEqual(event['environment'],'isolated-test')
        self.assertEqual(len(list(self.factory.glob('.status-*'))),0)
        self.assertFalse((self.factory/'.factory-status.lock').exists())
        check(self.factory,quiet=True)
    def test_failed_evidence_cannot_mark_done(self):
        p=self.factory/'task-plan.json';before=p.read_bytes()
        r=self.status('--result','failed','--apply')
        self.assertNotEqual(r.returncode,0);self.assertEqual(p.read_bytes(),before)
    def test_dependency_gate_preserves_status(self):
        task=copy.deepcopy(self.config['tasks'][0]);task['id']='T2';task['depends_on']=['T1']
        self.config['tasks'].append(task);self.write_factory()
        r=self.status('--task','T2','--apply')
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(json.loads((self.factory/'task-plan.json').read_text())['events'],[])
    def test_contract_tamper_blocks_recording(self):
        (self.factory/'policy.md').write_text('Changed authority')
        self.assertNotEqual(self.status('--apply').returncode,0)
    def test_existing_lock_preserves_record(self):
        p=self.factory/'task-plan.json';before=p.read_bytes()
        (self.factory/'.factory-status.lock').write_text('another writer')
        self.assertNotEqual(self.status('--apply').returncode,0)
        self.assertEqual(p.read_bytes(),before)
    def test_invalid_autonomy_controls_refused(self):
        self.config['operations']={'autonomy':{'mode':'bounded','max_items_per_hour':5,'allowed_submitters':[]}}
        with self.assertRaises(ValueError):validate(self.config)
    def test_headless_recipes_are_data_not_execution(self):
        marker=self.base/'executed'
        self.config['providers']=['Example provider']
        self.config['operations']={'tool_recipes':[{
            'provider':'Example provider','headless_command':f'create marker {marker}',
            'structured_output':'unverified','tool_restrictions':'unverified','auth_probe':f'create marker {marker}',
            'auth_status':'unverified','auth_evidence':'not probed'}]}
        validate(self.config);files=render(self.config,self.research)
        tools=json.loads(files['tools.json'])
        self.assertFalse(tools['integrations'][0]['enabled'])
        self.assertEqual(tools['headless_recipes'][0]['auth_status'],'unverified')
        self.assertFalse(marker.exists())
    def test_provenance_has_no_automatic_private_upstream_or_authority(self):
        record=json.loads((self.factory/'upstream-provenance.json').read_text())
        self.assertIsNone(record['upstream']['repository_url'])
        self.assertEqual(record['publication_authority'],'none')
        self.assertEqual(record['verification']['status'],'unverified')

if __name__=='__main__':unittest.main(verbosity=2)
