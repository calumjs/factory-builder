"""Exercise proposed ignore patterns in a disposable Git repository only."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from scaffold import ROOT, ignore_fragment, render


class PrivateRunIgnoreTests(unittest.TestCase):
    def test_exact_default_patterns_leave_stop_commands_and_unrelated_files_visible(self):
        if not shutil.which('git'):self.skipTest('Git unavailable; no installation attempted')
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        fragment=render(config,research)['gitignore.fragment']
        self.assertEqual(fragment,ignore_fragment(config))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            subprocess.run(['git','init','--quiet',str(root)],check=True,capture_output=True)
            path=root/'.gitignore';path.write_bytes(fragment.encode())
            paths=['.factory-runs/run-123.json','.factory-runs/STOP','.factory-runs/runner.py',
                   '.factory-runs/config.toml','selected-overview.html','selected-overview.json',
                   'app/index.html','config.json','other-runs/run-123.json',
                   'nested/selected-overview.html','nested/.factory-runs/run.json']
            result=subprocess.run(['git','-C',str(root),'check-ignore','-z','--stdin'],
                                  input=('\0'.join(paths)+'\0').encode(),capture_output=True,check=True)
            self.assertEqual(set(result.stdout.decode().rstrip('\0').split('\0')),
                             {'.factory-runs/run-123.json','selected-overview.html','selected-overview.json'})
            self.assertEqual(path.read_bytes(),fragment.encode())
            # Patterns do not remove existing tracked records or modify the index.
            tracked=root/'.factory-runs/run-123.json';tracked.parent.mkdir();tracked.write_bytes(b'{"notes":"synthetic"}')
            subprocess.run(['git','-C',str(root),'add','--force','.factory-runs/run-123.json'],check=True,capture_output=True)
            index=(root/'.git/index').read_bytes()
            check=subprocess.run(['git','-C',str(root),'check-ignore','--quiet','.factory-runs/run-123.json'],capture_output=True)
            self.assertEqual(check.returncode,1);self.assertEqual((root/'.git/index').read_bytes(),index)

    def test_generation_does_not_edit_a_project_ignore_policy_and_documents_retention_choices(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);policy=root/'.gitignore';policy.write_bytes(b'# existing reviewed policy\n')
            files=render(config,research)
            self.assertNotIn('.gitignore',files)
            self.assertEqual(policy.read_bytes(),b'# existing reviewed policy\n')
        text=(ROOT/'references/running.md').read_text()
        for phrase in ('Already tracked','Do not automatically delete or untrack','commented out',
                       'does not prove distributed','--runs <outside-path>','--output'):
            self.assertIn(phrase,text)


if __name__=='__main__':unittest.main()
