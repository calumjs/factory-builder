"""Synthetic supplied observations; no application, issue, or deployment is queried."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gates import gate_rows, problems, waivers
from incremental_records import preview, apply as apply_record
from integrity import check, digest
from scaffold import ROOT, render
from update_operations import prepare, apply, COMPATIBLE_GATE_V133

S1='a'*40
S2='b'*40
REQUIRED={'G3':{'stage':'post-merge','applicability':'applicable'}}

class FailedSubjectTests(unittest.TestCase):
    @staticmethod
    def row(subject=S1,evidence='private-sentinel [follow-up: example/project#9]',required='yes',result='FAILED'):
        return '| G3 | post-merge | Synthetic check | fixture | '+required+' | '+subject+' | '+result+' | '+evidence+' | fixture-artifact | 2026-11-01T00:00:00Z | '+('0' if result=='PASSED' else '1')+' |\n'
    def assess(self,text,subject=S1):return problems(text,'post-merge',subject,REQUIRED,'fixture-artifact')

    def test_current_failure_identifies_exact_subject_and_explicit_reference(self):
        found=self.assess(self.row())
        self.assertEqual(found[0],'G3 is FAILED')
        self.assertIn('recorded FAILED at '+S1,found[1]);self.assertIn('matches requested subject exactly',found[1])
        self.assertIn('follow-up example/project#9 (recorded reference; not verified)',found[1])
        self.assertNotIn('private-sentinel',' '.join(found))

    def test_stale_failure_does_not_certify_requested_subject(self):
        for requested in (S2,S1[:7],S1.upper()):
            found=self.assess(self.row(),requested)
            self.assertIn('recorded FAILED at '+S1,found[1]);self.assertIn('different from requested subject',found[1])
            self.assertIn('no current-subject pass is established',found[1])

    def test_missing_and_unsafe_subjects_do_not_expose_paths_or_controls(self):
        for subject in ('','C:\\private\\subject','https://private.invalid/subject','x'*129,'secret\x1b[31m'):
            found=self.assess(self.row(subject))
            self.assertIn('[missing or non-displayable subject]',found[1])
            if subject:self.assertNotIn(subject,' '.join(found))
        self.assertIn('no recorded subject',self.assess(self.row(''))[1])

    def test_followup_is_explicit_unique_bounded_and_not_inferred(self):
        for evidence in ('private-sentinel https://private.invalid/issues/9','[follow-up: https://private.invalid/issues/9]',
                         '[follow-up: #0] private-sentinel','[follow-up: #01]','[follow-up: #12345678901]',
                         '[follow-up: #9] [follow-up: #10]','[follow-up: #9] [follow-up: malformed',
                         '[follow-up: owner/../repo#9]','[follow-up: secret\x1b[31m]'):
            found=' '.join(self.assess(self.row(evidence=evidence)))
            self.assertIn('no unambiguous explicit follow-up reference',found)
            for private in ('private-sentinel','private.invalid','secret','follow-up #9 ('):self.assertNotIn(private,found)
        self.assertIn('follow-up #9 (recorded reference; not verified)',self.assess(self.row(evidence='[follow-up: #9]'))[1])

    def test_optional_failure_is_waived_and_history_is_not_current(self):
        optional=self.row(required='no')
        self.assertEqual(self.assess(optional,S2),[])
        self.assertEqual(waivers(optional,'post-merge'),['G3 WAIVED (recorded FAILED)'])
        text='> '+self.row()+self.row(S2,'synthetic-pass',result='PASSED')
        self.assertEqual(self.assess(text,S2),[])
        self.assertNotIn('recorded FAILED',' '.join(self.assess(text,S1)))

class FailedSubjectIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'fixture-artifact','post_merge':'Synthetic artifact confirmation'}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,text in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode('utf-8'))
    def tearDown(self):self.tmp.cleanup()
    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def record(self,subject,result):
        change={'gate':'G3','result':result,'revision':subject,'environment':'fixture',
                'evidence':'private-sentinel [follow-up: example/project#9]' if result=='FAILED' else 'synthetic-pass',
                'target':'fixture-artifact','checked_at':'2026-11-01T00:00:00Z','exit_status':'1' if result=='FAILED' else '0'}
        root,name,before,after,token=preview(self.root,'gate',change);apply_record(root,name,before,after,token,token)
    def cli(self,subject):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/gates.py'),'--factory',str(self.root),
                               '--stage','post-merge','--revision',subject,'--target','fixture-artifact'],capture_output=True,text=True)

    def test_failed_then_new_pass_preserves_history_and_cli_is_read_only(self):
        self.record(S1,'FAILED');before=self.snapshot();current=self.cli(S1);stale=self.cli(S2)
        self.assertEqual(current.returncode,1,current.stderr);self.assertEqual(stale.returncode,1,stale.stderr)
        self.assertIn('matches requested subject exactly',current.stdout);self.assertIn('different from requested subject',stale.stdout)
        self.assertNotIn('private-sentinel',current.stdout+current.stderr+stale.stdout+stale.stderr)
        self.assertEqual(before,self.snapshot())
        self.record(S2,'PASSED');before=self.snapshot();passed=self.cli(S2)
        self.assertEqual(passed.returncode,0,passed.stdout+passed.stderr);self.assertNotIn('recorded FAILED',passed.stdout)
        text=(self.root/'verification.md').read_text()
        self.assertIn('> | G3 |',text);self.assertIn(S1,text);self.assertIn('[follow-up: example/project#9]',text)
        self.assertEqual(gate_rows(text)['G3']['revision'],S2);self.assertEqual(before,self.snapshot())

    def test_cli_optional_failure_displays_context_without_blocking(self):
        self.record(S1,'FAILED');path=self.root/'verification.md'
        text='\n'.join(line.replace('| yes |','| no |') if line.startswith('| G3 |') else line for line in path.read_text().splitlines())+'\n'
        path.write_bytes(text.encode('utf-8'));before=self.snapshot();result=self.cli(S2)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('G3 WAIVED (recorded FAILED)',result.stdout)
        self.assertIn('WAIVED observation only: G3 recorded FAILED at '+S1,result.stdout)
        self.assertIn('different from requested subject',result.stdout);self.assertIn('ELIGIBLE WITH WAIVERS',result.stdout)
        self.assertNotIn('private-sentinel',result.stdout);self.assertEqual(before,self.snapshot())

    def test_published_runtime_reviewed_upgrade_and_custom_refusal(self):
        prior=(ROOT/'scripts/fixtures/v1_33_gates.txt').read_bytes()
        self.assertEqual(digest(prior),COMPATIBLE_GATE_V133['gates.py'])
        path=self.root/'dashboard/gates.py';manifest_path=self.root/'manifest.json'
        def install(data):
            path.write_bytes(data);manifest=json.loads(manifest_path.read_text());manifest['contracts']['dashboard/gates.py']=digest(data)
            manifest_path.write_bytes(json.dumps(manifest).encode('utf-8'));check(self.root,quiet=True)
        install(prior);before=self.snapshot()
        self.assertNotIn('dashboard/gates.py',prepare(self.root,{},delivery_update=True)[2])
        root,old,new,token=prepare(self.root,{},gate_runtime=True)
        self.assertEqual(before,self.snapshot());self.assertEqual(old['dashboard/gates.py'],prior)
        backup=apply(root,old,new,token,token)
        self.assertEqual((backup/'dashboard/gates.py').read_bytes(),prior)
        self.assertEqual(path.read_bytes(),(ROOT/'scripts/gates.py').read_bytes());check(root,quiet=True)
        install(prior+b'\n# custom\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):prepare(self.root,{},gate_runtime=True)
        self.assertEqual(before,self.snapshot())

if __name__=='__main__':unittest.main()
