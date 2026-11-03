"""Run adoption notices for valid recorded factories; no adoption or external action."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from integrity import digest
from scaffold import ROOT, render


class RunAdoptionAdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.root=self.parent/'.software-factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.files=render(config,research)
        # Select actual rendered contract names, independently of the advisory helper.
        self.run_names=sorted(name for name in self.files if name=='.claude/skills/factory-run/SKILL.md' or name.startswith('scheduling/'))
        self.assertIn('.claude/skills/factory-run/SKILL.md',self.run_names)
        self.assertTrue(any(name.startswith('scheduling/') for name in self.run_names))

    def write(self,omit=()):
        manifest=json.loads(self.files['manifest.json'])
        for name in omit:del manifest['contracts'][name]
        for name,body in self.files.items():
            if name in omit:continue
            if name=='manifest.json':body=json.dumps(manifest)
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.parent).as_posix():None if p.is_dir() else p.read_bytes() for p in self.parent.rglob('*')}

    def check_cli(self):
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/scaffold.py'),'--check',str(self.root)],capture_output=True,text=True)
        self.assertEqual(before,self.snapshot())
        return result

    def advisory_names(self,result):
        lines=[line for line in result.stdout.splitlines() if line.startswith('ADVISORY: optional Run contracts')]
        self.assertEqual(len(lines),1,result.stdout)
        return json.JSONDecoder().raw_decode(lines[0].split(': ',2)[2])[0]

    def test_six_phase_factory_passes_once_with_exact_missing_contracts(self):
        self.write(self.run_names)
        self.assertEqual(len(list((self.root/'.claude/skills').glob('*/SKILL.md'))),6)
        result=self.check_cli()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertEqual(self.advisory_names(result),self.run_names)
        self.assertIn('references/running.md#existing-factories',result.stdout)
        self.assertIn('no files changed or dispatch/schedules enabled',result.stdout)
        self.assertIn('application checks were not run',result.stdout)

    def test_complete_factory_has_no_adoption_advisory(self):
        self.write();result=self.check_cli()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertNotIn('ADVISORY: optional Run contracts',result.stdout)

    def test_partial_consistent_adoption_lists_only_absent_contracts(self):
        missing=[name for name in self.run_names if name.startswith('scheduling/')][:1]
        self.write(missing);result=self.check_cli()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertEqual(self.advisory_names(result),missing)

    def test_manifest_listed_missing_file_is_failure_not_adoption_notice(self):
        self.write();(self.root/'.claude/skills/factory-run/SKILL.md').unlink()
        result=self.check_cli()
        self.assertEqual(result.returncode,1);self.assertIn('Manifest file set mismatch',result.stderr)
        self.assertNotIn('PASS:',result.stdout);self.assertNotIn('ADVISORY: optional Run contracts',result.stdout)

    def test_malformed_manifest_is_failure_not_adoption_notice(self):
        self.write(self.run_names);(self.root/'manifest.json').write_text('{invalid',encoding='utf-8')
        result=self.check_cli()
        self.assertEqual(result.returncode,1);self.assertIn('Invalid JSON',result.stderr)
        self.assertNotIn('PASS:',result.stdout);self.assertNotIn('ADVISORY: optional Run contracts',result.stdout)

    def test_custom_run_and_living_records_are_preserved_with_partial_adoption(self):
        missing=[name for name in self.run_names if name.startswith('scheduling/')]
        self.write(missing)
        skill=self.root/'.claude/skills/factory-run/SKILL.md';skill.write_bytes(skill.read_bytes()+b'\nPRIVATE synthetic custom rule\n')
        manifest_path=self.root/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['contracts']['.claude/skills/factory-run/SKILL.md']=digest(skill.read_bytes());manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        (self.root/'release-handoff.md').write_bytes(b'PRIVATE synthetic unfinished handoff\r\n')
        result=self.check_cli()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertEqual(self.advisory_names(result),missing);self.assertNotIn('PRIVATE',result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
