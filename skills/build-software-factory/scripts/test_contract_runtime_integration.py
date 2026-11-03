"""Cross-helper validation and reviewed migration of synthetic v1.13 factories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from acceptance_links import validate_snapshot
from integrity import check, digest
from scaffold import ROOT, render
from scoped_assessment import assess_scope
from update_operations import apply, prepare, COMPATIBLE_CONTEXT_V113, COMPATIBLE_GATE_V113


class ContractRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.factory=self.base/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'synthetic-artifact'}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(config,research)
        for name,body in self.files.items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(body,encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix():p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def broken_log(self):
        text=self.files['learning-log.md']
        delimiter='|---|---|---|---|---|---|---|'
        self.assertIn(delimiter,text)
        return text.replace(delimiter,delimiter+'\n| observed failure | only two cells |')

    def test_copied_helpers_validate_learn_rows_without_bytecode(self):
        check(self.factory,quiet=True)
        log=self.factory/'learning-log.md';log.write_text(self.broken_log(),encoding='utf-8')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,r'learning-log\.md line 5:'):
            check(self.factory,quiet=True)
        result=subprocess.run([sys.executable,str(self.factory/'dashboard/gates.py'),'--factory',str(self.factory),'--plan'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('learning-log.md line 5:',result.stderr)
        self.assertEqual(before,self.snapshot())
        self.assertFalse((self.factory/'dashboard/__pycache__').exists())

    def test_trace_snapshot_checks_captured_learn_bytes_without_reopening_files(self):
        files={name:body.encode('utf-8') for name,body in self.files.items()}
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Snapshot reopened a path')):
            validate_snapshot(files)
            files['learning-log.md']=self.broken_log().encode('utf-8')
            with self.assertRaisesRegex(ValueError,r'learning-log\.md line 5:'):
                validate_snapshot(files)

    def test_v113_context_migration_adds_dependency_with_review_and_backup(self):
        manifest_path=self.factory/'manifest.json';manifest=json.loads(manifest_path.read_text())
        prior={}
        for script,mapping in (('integrity',COMPATIBLE_CONTEXT_V113),('gates',COMPATIBLE_GATE_V113)):
            data=(ROOT/f'scripts/fixtures/v1_13_{script}.txt').read_bytes()
            self.assertEqual(digest(data),mapping[script+'.py'])
            name=f'dashboard/{script}.py';prior[name]=data
            (self.factory/name).write_bytes(data);manifest['contracts'][name]=digest(data)
        dependency='dashboard/learning_table.py'
        (self.factory/dependency).unlink();del manifest['contracts'][dependency]
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        check(self.factory,quiet=True);before=self.snapshot()
        _,_,replacement,_=prepare(self.factory,{})
        self.assertFalse(replacement)
        root,old,new,token=prepare(self.factory,{},context_runtime=True,gate_runtime=True)
        self.assertEqual(before,self.snapshot())
        self.assertEqual(set(new),set(prior)|{dependency,'manifest.json'})
        with self.assertRaises(ValueError):apply(root,old,new,token,'wrong-digest')
        self.assertEqual(before,self.snapshot())
        backup=apply(root,old,new,token,token)
        self.assertIn(dependency,(backup/'added-files.json').read_text())
        for name,data in prior.items():
            self.assertEqual((backup/name).read_bytes(),data)
        for name in ('config.json','policy.md','task-plan.json','verification.md','learning-log.md'):
            self.assertEqual((root/name).read_bytes(),before[name])
        self.assertEqual((root/dependency).read_bytes(),(ROOT/'scripts/learning_table.py').read_bytes())
        args=['--factory',str(root),'--plan']
        installed=subprocess.run([sys.executable,str(ROOT/'scripts/gates.py'),*args],capture_output=True,text=True)
        copied=subprocess.run([sys.executable,str(root/'dashboard/gates.py'),*args],capture_output=True,text=True)
        self.assertEqual((installed.returncode,installed.stdout),(copied.returncode,copied.stdout))
        self.assertEqual(copied.returncode,0,copied.stderr)
        check(root,quiet=True)

    def test_captured_contract_json_matches_integrity_rejection(self):
        for raw in (b'{',b'{"duplicate":1,"duplicate":2}',b'{"value":NaN}'):
            with self.subTest(raw=raw):
                files={name:body.encode('utf-8') for name,body in self.files.items()}
                name='test-map.json';files[name]=raw
                manifest=json.loads(files['manifest.json'])
                manifest['contracts'][name]=digest(raw)
                files['manifest.json']=json.dumps(manifest).encode('utf-8')
                for relative in (name,'manifest.json'):
                    (self.factory/relative).write_bytes(files[relative])
                with self.assertRaisesRegex(ValueError,'JSON'):
                    check(self.factory,quiet=True)
                with patch.object(Path,'read_bytes',side_effect=AssertionError('Snapshot reopened a path')):
                    with self.assertRaisesRegex(ValueError,'JSON'):
                        validate_snapshot(files)

    def test_custom_learn_dependency_is_preserved_and_refused(self):
        name='dashboard/learning_table.py';path=self.factory/name
        path.write_bytes(path.read_bytes()+b'\n# Operator customization\n')
        manifest_path=self.factory/'manifest.json';manifest=json.loads(manifest_path.read_text())
        manifest['contracts'][name]=digest(path.read_bytes())
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported dashboard Learn parser'):
            prepare(self.factory,{},context_runtime=True)
        self.assertEqual(before,self.snapshot())

    def test_scoped_post_action_assessment_requires_observed_target(self):
        scope={'purpose':'Synthetic changed feature','gates':['A1'],'tasks':['T1']}
        result=assess_scope(self.factory,scope,'post-merge','S1')
        self.assertTrue(any('actual --target' in problem for problem in result['problems']))
        self.assertFalse(any('kind is unconfirmed' in problem for problem in result['problems']))
        supplied=assess_scope(self.factory,scope,'post-merge','S1','synthetic-artifact')
        self.assertFalse(any('actual --target' in problem for problem in supplied['problems']))
        self.assertTrue(supplied['problems'])  # Supplying a target never runs or passes G3.


if __name__=='__main__':unittest.main()
