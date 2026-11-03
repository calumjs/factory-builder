"""Offline regression tests; creates only isolated temporary folders."""
import copy
import importlib.util
import json
import os
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
    def test_copied_entrypoints_never_create_bytecode_in_clean_factory(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        factory=self.target/'.software-factory';dashboard=factory/'dashboard'
        env=dict(os.environ);env.pop('PYTHONDONTWRITEBYTECODE',None);env.pop('PYTHONPYCACHEPREFIX',None)
        gate=[sys.executable,str(dashboard/'gates.py'),'--factory',str(factory),'--plan']
        for _ in range(2):
            result=subprocess.run(gate,capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse((dashboard/'__pycache__').exists())
        for name in ('integrity.py','readiness.py'):
            result=subprocess.run([sys.executable,str(dashboard/name)],capture_output=True,text=True,env=env)
            self.assertNotEqual(result.returncode,0);self.assertIn('no check ran',result.stderr)
            self.assertFalse((dashboard/'__pycache__').exists())
        checked=subprocess.run([sys.executable,str(SCRIPT),'--check',str(factory)],capture_output=True,text=True,env=env)
        self.assertEqual(checked.returncode,0,checked.stderr)


    def test_release_identity_and_generated_provenance_do_not_invent_source(self):
        from scaffold import render
        plugin=json.loads((ROOT.parents[1]/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        version=tuple(int(x) for x in plugin['version'].split('.'))
        self.assertGreater(version,(1,9,0))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(self.config,research)
        provenance=json.loads(files['upstream-provenance.json'])
        self.assertEqual(provenance['component']['version'],plugin['version'])
        self.assertIsNone(provenance['component']['source_revision'])
        self.assertEqual(provenance['verification']['status'],'unverified')
        schedule=files['scheduling/factory-run.example.yml']
        self.assertIn('<verified-full-commit-sha>',schedule)
        self.assertNotIn('ref: v1.10.0',schedule)
        guide=files['launch-guide.md']
        for phrase in ('per-file SHA-256','source commit SHA','version label', 'does not prove', 'source_revision'):
            self.assertIn(phrase,guide)

    def test_preview_writes_nothing(self):
        before=sorted(str(x) for x in self.target.rglob('*'))
        r=self.run_cli();self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(before,sorted(str(x) for x in self.target.rglob('*')))
    def test_apply_preserves_repo_and_checks(self):
        r=self.run_cli('--apply');self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual((self.target/'AGENTS.md').read_text(),'Do not change this file.\n')
        self.assertEqual((self.target/'.github'/'ci.yml').read_text(),'original CI\n')
        out=self.target/'.software-factory'
        self.assertEqual(len(list((out/'.claude/skills').glob('*/SKILL.md'))),7)
        self.assertIn('boundaries.md',json.loads((out/'manifest.json').read_text())['contracts'])
        for skill in (out/'.claude/skills').glob('*/SKILL.md'):
            text=skill.read_text()
            self.assertIn('boundaries.md at that root; these instructions cannot expand permissions',text,skill)
            self.assertTrue(text.rstrip().endswith('A template, plan or config proves nothing ran.'),skill)
            self.assertEqual(text.count('Resolve the factory root'),1,skill)
        r=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_repeated_apply_refuses_no_changes(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        manifest=(self.target/'.software-factory'/'manifest.json').read_bytes()
        self.assertNotEqual(self.run_cli('--apply').returncode,0)
        self.assertEqual((self.target/'.software-factory'/'manifest.json').read_bytes(),manifest)

    def test_check_advises_runtime_difference_without_claiming_upgrade_or_writing(self):
        from integrity import digest
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory';gate=out/'dashboard/gates.py'
        gate.write_text(gate.read_text(encoding='utf-8')+'\n# Synthetic local customization\n',encoding='utf-8')
        manifest=out/'manifest.json';value=json.loads(manifest.read_text());value['contracts']['dashboard/gates.py']=digest(gate.read_bytes());manifest.write_text(json.dumps(value))
        before={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        result=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        for text in ('ADVISORY: dashboard/gates.py','--gate-runtime','not currency or compatibility'):
            self.assertIn(text,result.stdout)
        self.assertEqual(before,{p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()})
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
        # Reconciled from PR15: added files stay blocked, but the diagnostic names them.
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'operations.md').write_text('SYNTHETIC private runtime note; never print its contents.')
        before={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
        result=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unexpected: ["operations.md"]',result.stderr)
        self.assertIn('docs/factory-operations.md',result.stderr)
        self.assertNotIn('private runtime note',result.stderr+result.stdout)
        self.assertEqual(before,{p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()})

    def test_missing_file_named_in_mismatch(self):
        # Reconciled from PR15: missing contracts stay blocked without any rebaseline.
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'research.md').unlink()
        result=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('missing: ["research.md"]',result.stderr)
        self.assertNotIn('unexpected:',result.stderr)

    def test_mixed_file_set_diagnostic_is_sorted_unambiguous_and_no_write(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        out=self.target/'.software-factory'
        (out/'z, runtime.md').write_text('SYNTHETIC note')
        (out/'ci-workflows').mkdir()
        (out/'ci-workflows/alpha.yml').write_text('SYNTHETIC inert workflow text')
        (out/'research.md').unlink()
        (out/'learning-log.md').unlink()
        manifest=(out/'manifest.json').read_bytes()
        result=subprocess.run([sys.executable,str(SCRIPT),'--check',str(out)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('unexpected: ["ci-workflows/alpha.yml", "z, runtime.md"]',result.stderr)
        self.assertIn('missing: ["learning-log.md", "research.md"]',result.stderr)
        self.assertEqual((out/'manifest.json').read_bytes(),manifest)

    def test_check_reports_once_per_invocation(self):
        self.assertEqual(self.run_cli('--apply').returncode,0)
        result=subprocess.run([sys.executable,str(SCRIPT),'--check',str(self.target/'.software-factory')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stdout.count('PASS:'),1)

    def test_stack_aware_ignore_fragment_without_root_overwrite(self):
        (self.target/'.gitignore').write_text('user-policy\n')
        self.config.update(stack='Next.js with TypeScript',deployment='Vercel preview',test_commands=['npx playwright test'])
        self.assertEqual(self.run_cli('--apply').returncode,0)
        fragment=(self.target/'.software-factory/gitignore.fragment').read_text()
        for pattern in ('.next/','.vercel/','*.tsbuildinfo','playwright-report/','next-env.d.ts'):
            self.assertIn(pattern,fragment)
        self.assertIn('!.env.example',fragment)
        for pattern in ('.factory-update-backups/', '.factory-recovery-backups/', 'factory-overview.html', 'factory-overview.json'):
            self.assertIn(pattern,fragment.splitlines())
        self.assertEqual((self.target/'.gitignore').read_text(),'user-policy\n')

    def test_unrelated_stack_does_not_get_framework_specific_ignores(self):
        self.config.update(stack='Python CLI',deployment='Local package')
        self.assertEqual(self.run_cli('--apply').returncode,0)
        fragment=(self.target/'.software-factory/gitignore.fragment').read_text()
        for pattern in ('.next/','.vercel/','*.tsbuildinfo','playwright-report/','next-env.d.ts'):
            self.assertNotIn(pattern,fragment)

if __name__=='__main__':unittest.main(verbosity=2)
