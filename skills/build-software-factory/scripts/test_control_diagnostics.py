"""Read-only, value-free control/schema diagnostics in disposable factories."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from gates import assess, control_differences, policy_controls
from integrity import check, digest
from operations import operations
from scaffold import ROOT, render
from update_operations import prepare


class ControlDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'.software-factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(self.config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def policy(self,change):
        path=self.root/'policy.md';text=path.read_text(encoding='utf-8')
        controls=policy_controls(text);change(controls)
        header='## Proposed autonomy and review controls (not execution authority)'
        pattern=re.escape(header)+r'(\s*```json\n)(.*?)(\n```)'
        text=re.sub(pattern,lambda match:header+match[1]+json.dumps(controls,indent=2)+match[3],text,count=1,flags=re.S)
        path.write_bytes(text.encode('utf-8'))
        manifest_path=self.root/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['contracts']['policy.md']=digest(path.read_bytes())
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8')

    def test_valid_hashes_do_not_hide_named_typed_control_drift_or_print_values(self):
        def drift(controls):
            controls['smoke_gates']['required']=1  # Python's ordinary equality equates 1 and True.
            controls['smoke_gates']['deployed_url']='PRIVATE_TARGET_SENTINEL'
            controls['issue_intake']['evidence']='PRIVATE_EVIDENCE_SENTINEL'
        self.policy(drift)
        check(self.root,quiet=True)  # Integrity alone does not attest controls consistency.
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/gates.py'),'--factory',str(self.root),
                               '--stage','pre-merge','--revision','synthetic-subject'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        for path in ('controls.smoke_gates.required','controls.smoke_gates.deployed_url','controls.issue_intake.evidence'):
            self.assertIn(path,result.stderr)
        self.assertNotIn('PRIVATE_',result.stdout+result.stderr)
        self.assertIn('update_operations.py refuses existing drift',result.stderr)
        self.assertIn('references/recovery.md',result.stderr)
        self.assertIn('--factory <factory> --operations <changes.json>',result.stderr)
        self.assertIn('controls consistency, not application delivery readiness',result.stderr)
        with self.assertRaisesRegex(ValueError,'controls.smoke_gates.required') as raised:
            prepare(self.root,{'done_videos':{'enabled':True}})
        self.assertNotIn('PRIVATE_',str(raised.exception))
        self.assertEqual(self.snapshot(),before)

    def test_typed_list_differences_are_paths_only_and_matching_controls_proceed(self):
        self.assertEqual(control_differences({'a':[True,{'rate':2}]},{'a':[1,{'rate':3}]}),
                         ['controls.a[0]','controls.a[1].rate'])
        self.assertEqual(control_differences({'a':[]},{'a':[]} ),[])
        self.assertEqual(control_differences({'a':[]},{'a':['private value']}),['controls.a'])
        before=self.snapshot()
        self.assertTrue(assess(self.root,'pre-merge','synthetic-subject'))  # Reaches NOT RUN gate checks.
        self.assertEqual(self.snapshot(),before)

    def test_control_field_names_are_escaped_in_terminal_diagnostics(self):
        self.policy(lambda controls:controls.update({'unknown\nfield':'PRIVATE_SENTINEL'}))
        with self.assertRaises(ValueError) as raised:assess(self.root,'pre-merge','subject')
        message=str(raised.exception)
        self.assertIn('controls.unknown\\nfield',message)
        self.assertNotIn('\n',message)
        self.assertNotIn('PRIVATE_SENTINEL',message)

    def test_operations_shape_errors_name_path_allowed_schema_and_preserve_inputs(self):
        cases=[
            (['PRIVATE_SENTINEL'],'Unknown operations field','operations must be an object','issue_intake'),
            ({'unknown':'PRIVATE_SENTINEL'},'Unknown operations field','unknown keys at operations','smoke_gates'),
            ({'issue_intake':['PRIVATE_SENTINEL']},'Invalid operations section: issue_intake','operations.issue_intake must be an object','coverage'),
            ({'issue_intake':{'schedule':'PRIVATE_SENTINEL'}},'Invalid operations section: issue_intake','unknown keys at operations.issue_intake','mechanism'),
            ({'done_videos':{'unknown':'PRIVATE_SENTINEL'}},'Invalid operations section: done_videos','operations.done_videos','triggers'),
            ({'smoke_gates':{'unknown':'PRIVATE_SENTINEL'}},'Invalid operations section: smoke_gates','operations.smoke_gates','checks')]
        before=self.snapshot()
        for supplied,prefix,path,allowed in cases:
            with self.subTest(path=path):
                value={'operations':supplied};original=json.dumps(value)
                with self.assertRaises(ValueError) as raised:operations(value)
                message=str(raised.exception)
                self.assertTrue(message.startswith(prefix))
                self.assertIn(path,message);self.assertIn('"'+allowed+'"',message)
                self.assertIn('references/existing-factory-update.md',message)
                self.assertNotIn('PRIVATE_SENTINEL',message)
                self.assertEqual(json.dumps(value),original)
                if isinstance(supplied,dict):
                    with self.assertRaises(ValueError):prepare(self.root,supplied)
        self.assertEqual(self.snapshot(),before)

    def test_unknown_key_output_is_bounded_and_escaped(self):
        supplied={'bad\n'+str(i)+'x'*500:'PRIVATE_SENTINEL' for i in range(30)}
        with self.assertRaises(ValueError) as raised:operations({'operations':supplied})
        message=str(raised.exception)
        self.assertLess(len(message),2000)
        self.assertIn('20 more fields',message)
        self.assertNotIn('\n',message)
        self.assertNotIn('PRIVATE_SENTINEL',message)


if __name__=='__main__':unittest.main()
