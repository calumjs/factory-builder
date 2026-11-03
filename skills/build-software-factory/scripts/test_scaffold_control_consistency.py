"""Read-only scaffold/recovery consistency checks on disposable synthetic factories."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from gates import assess, policy_controls
from integrity import check, digest
from recover_factory import rawhash
from scaffold import ROOT, render


class ScaffoldControlConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.root=self.parent/'source';self.base=self.parent/'accepted'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['operations']={'issue_intake':{'mode':'continuous','status':'disabled'},
                                   'autonomy':{'allowed_submitters':['synthetic-operator']}}
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for root in (self.root,self.base):
            for name,body in render(self.config,research).items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        self.pin=rawhash((self.base/'manifest.json').read_bytes())

    def snapshot(self):
        return {p.relative_to(self.parent).as_posix():p.read_bytes() for p in self.parent.rglob('*') if p.is_file()}

    def rehash(self,name):
        path=self.root/'manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
        manifest['contracts'][name]=digest((self.root/name).read_bytes());path.write_text(json.dumps(manifest),encoding='utf-8')

    def change_policy(self,change,rehash=True):
        path=self.root/'policy.md';text=path.read_text(encoding='utf-8');value=policy_controls(text);change(value)
        header='## Proposed autonomy and review controls (not execution authority)'
        pattern=re.escape(header)+r'(\s*```json\n)(.*?)(\n```)'
        text=re.sub(pattern,lambda match:header+match[1]+json.dumps(value,indent=2)+match[3],text,count=1,flags=re.S)
        path.write_text(text,encoding='utf-8')
        if rehash:self.rehash('policy.md')

    def cli(self,script,*args):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),*map(str,args)],capture_output=True,text=True)

    def scaffold_check(self):return self.cli('scaffold.py','--check',self.root)

    def test_valid_hashes_with_typed_control_drift_fail_without_pass_or_mutation(self):
        def drift(value):
            value['smoke_gates']['required']=1
            value['issue_intake']['evidence']='PRIVATE_EVIDENCE_SENTINEL'
            value['smoke_gates']['deployed_url']='PRIVATE_TARGET_SENTINEL'
            value['autonomy']['allowed_submitters'][0]=17
        self.change_policy(drift);check(self.root,quiet=True);before=self.snapshot()
        result=self.scaffold_check();self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        for path in ('controls.smoke_gates.required','controls.issue_intake.evidence','controls.smoke_gates.deployed_url','controls.autonomy.allowed_submitters[0]'):
            self.assertIn(path,result.stderr)
        self.assertNotIn('PASS:',result.stdout);self.assertNotIn('PRIVATE_',result.stdout+result.stderr)
        self.assertIn('update_operations.py refuses existing drift',result.stderr)
        self.assertIn('--apply --approve-plan <digest>',result.stderr)
        self.assertEqual(before,self.snapshot())

    def test_recovery_cli_reports_same_paths_without_creating_backup_or_output(self):
        def drift(value):
            value['issue_intake']['evidence']='PRIVATE_SENTINEL'
            value['smoke_gates']['required']=1
        self.change_policy(drift,rehash=False)
        before=self.snapshot();output=self.parent/'recovered'
        result=self.cli('recover_factory.py','--factory',self.root,'--baseline',self.base,'--output',output,
                        '--baseline-manifest-sha256',self.pin,'--baseline-reference','SYNTHETIC accepted fixture')
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('controls.issue_intake.evidence',result.stderr);self.assertIn('references/recovery.md section 1',result.stderr)
        self.assertIn('controls.smoke_gates.required',result.stderr)
        self.assertIn('update_operations.py refuses existing drift',result.stderr);self.assertNotIn('PRIVATE_',result.stdout+result.stderr)
        self.assertFalse(output.exists());self.assertFalse((self.parent/'.factory-recovery-backups').exists())
        self.assertEqual(before,self.snapshot())

    def test_matching_controls_pass_once_and_keep_runtime_and_disabled_advisories(self):
        path=self.root/'dashboard/gates.py';path.write_bytes(path.read_bytes()+b'\n# SYNTHETIC customization\n');self.rehash('dashboard/gates.py')
        before=self.snapshot();result=self.scaffold_check()
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        for text in ('config/policy controls agree','application checks were not run','ADVISORY: dashboard/gates.py','Configured disabled'):
            self.assertIn(text,result.stdout)
        self.assertTrue(assess(self.root,'pre-merge','synthetic-subject'))  # Required evidence remains NOT RUN.
        self.assertEqual(before,self.snapshot());self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_malformed_or_duplicate_policy_controls_never_print_pass(self):
        path=self.root/'policy.md';original=path.read_text(encoding='utf-8')
        for replacement in ('"concurrency": 1, "concurrency":','"concurrency": INVALID, "unused":'):
            path.write_text(original.replace('"concurrency":',replacement,1),encoding='utf-8');self.rehash('policy.md')
            before=self.snapshot();result=self.scaffold_check()
            self.assertEqual(result.returncode,1);self.assertNotIn('PASS:',result.stdout);self.assertEqual(before,self.snapshot())

    def test_strict_config_json_rejection_precedes_success(self):
        path=self.root/'config.json';text=path.read_text(encoding='utf-8')
        path.write_text(text.replace('{','{"project":"PRIVATE_SENTINEL",',1),encoding='utf-8');self.rehash('config.json')
        before=self.snapshot();result=self.scaffold_check()
        self.assertEqual(result.returncode,1);self.assertIn('Duplicate JSON',result.stderr)
        self.assertNotIn('PASS:',result.stdout);self.assertNotIn('PRIVATE_',result.stdout+result.stderr);self.assertEqual(before,self.snapshot())

    def test_diagnostic_paths_are_bounded_and_terminal_escaped(self):
        self.change_policy(lambda value:value.update({'unknown\n'+str(i)+'x'*400:'PRIVATE_SENTINEL' for i in range(30)}))
        before=self.snapshot();result=self.scaffold_check()
        self.assertEqual(result.returncode,1);self.assertIn('20 more paths omitted',result.stderr)
        self.assertIn('unknown\\n',result.stderr);self.assertLess(len(result.stderr),2000)
        self.assertNotIn('PRIVATE_',result.stdout+result.stderr);self.assertNotIn('PASS:',result.stdout);self.assertEqual(before,self.snapshot())


if __name__=='__main__':unittest.main()
