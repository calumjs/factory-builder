"""Offline regression tests; creates only isolated temporary folders."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT=Path(__file__).with_name('scaffold.py')
ROOT=SCRIPT.parents[1]

class ScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.target=self.base/'repo';self.target.mkdir()
        (self.target/'AGENTS.md').write_text('Do not change this file.\n')
        (self.target/'.github').mkdir();(self.target/'.github'/'ci.yml').write_text('original CI\n')
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.cfg=self.base/'config.json'
    def tearDown(self):self.tmp.cleanup()
    def run_cli(self,*args):
        self.cfg.write_text(json.dumps(self.config))
        return subprocess.run([sys.executable,str(SCRIPT),'--config',str(self.cfg),'--target',str(self.target),*args],capture_output=True,text=True)
    def test_preview_writes_nothing(self):
        before=sorted(str(x) for x in self.target.rglob('*'))
        r=self.run_cli();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(before,sorted(str(x) for x in self.target.rglob('*')))
    def test_apply_preserves_repo_and_checks(self):
        r=self.run_cli('--apply');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((self.target/'AGENTS.md').read_text(),'Do not change this file.\n')
        self.assertEqual((self.target/'.github'/'ci.yml').read_text(),'original CI\n')
        out=self.target/'.software-factory'
        self.assertEqual(len(list((out/'.claude/skills').glob('*/SKILL.md'))),6)
        r=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_repeated_apply_refuses_no_changes(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        manifest=(self.target/'.software-factory'/'manifest.json').read_bytes()
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
        self.assertEqual((self.target/'.software-factory'/'manifest.json').read_bytes(),manifest)
    def test_existing_empty_output_refused(self):
        (self.target/'.software-factory').mkdir()
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
    def test_invalid_config_no_output(self):
        self.config['budget']['max_cost']=-1
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
        self.assertFalse((self.target/'.software-factory').exists())
    def test_dependency_cycle_refused(self):
        self.config['tasks'][0]['depends_on']=['T1']
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
    def test_missing_dependency_refused(self):
        self.config['tasks'][0]['depends_on']=['absent']
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
    def test_invalid_acceptance_refused(self):
        self.config['tasks'][0]['acceptance_ids']=['A99']
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
    def test_commands_never_execute_and_providers_disabled(self):
        marker=self.base/'executed'
        self.config['test_commands']=[f'touch {marker}']
        self.config['providers']=['Unverified provider']
        self.assertEqual(self.run_cli('--apply').returncode,0)
        self.assertFalse(marker.exists())
        tools=json.loads((self.target/'.software-factory'/'tools.json').read_text())
        self.assertFalse(tools['integrations'][0]['enabled'])
        self.assertFalse(tools['test_commands'][0]['execution_authorized'])
    def test_deterministic_output(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        first=(self.target/'.software-factory'/'manifest.json').read_bytes()
        self.target=self.base/'other';self.target.mkdir()
        self.assertEqual(self.run_cli('--apply').returncode,0)
        self.assertEqual(first,(self.target/'.software-factory'/'manifest.json').read_bytes())
    def test_symlink_target_refused(self):
        link=self.base/'link'
        try:link.symlink_to(self.target,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('Symlink creation unavailable')
        self.target=link
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
    def test_modified_artifact_detected(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'acceptance.md').write_text('tampered')
        r=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)

    def test_extra_file_named_in_mismatch(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'operations.md').write_text('ops\n')
        r=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('unexpected: operations.md',r.stderr+r.stdout)
    def test_missing_file_named_in_mismatch(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'research.md').unlink()
        r=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('missing: research.md',r.stderr+r.stdout)

if __name__=='__main__':unittest.main(verbosity=2)
