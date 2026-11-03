"""Canonical scaffold task statuses; no implicit legacy migration or evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows
from integrity import check
from scaffold import ROOT, render, validate
from status import STATUSES


class TaskStatusVocabularyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.target=self.parent/'project';self.target.mkdir()
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.config_path=self.parent/'config.json'

    def snapshot(self):
        return {p.relative_to(self.parent).as_posix():None if p.is_dir() else p.read_bytes() for p in self.parent.rglob('*')}

    def cli(self,*extra):
        self.config_path.write_text(json.dumps(self.config),encoding='utf-8')
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/scaffold.py'),'--config',str(self.config_path),
                               '--target',str(self.target),*extra],capture_output=True,text=True)
        return result,before

    def write_factory(self):
        root=self.target/'.software-factory'
        for name,body in render(self.config,self.research).items():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        return root

    def test_invalid_config_and_render_statuses_are_bounded_and_do_not_mutate_input(self):
        for value in ('todo','in-progress','Pending',' pending','done ', '',None,True,[],{},'PRIVATE\n'+('secret'*1000)):
            with self.subTest(value_type=type(value).__name__):
                self.config['tasks'][0]['status']=value;before=copy.deepcopy(self.config)
                for operation in (lambda:validate(self.config),lambda:render(self.config,self.research)):
                    with self.assertRaises(ValueError) as caught:operation()
                    message=str(caught.exception)
                    self.assertIn('tasks[0].status',message);self.assertIn(', '.join(STATUSES),message)
                    self.assertIn('references/task-status.md',message);self.assertLess(len(message),300)
                    self.assertNotIn('PRIVATE',message);self.assertNotIn('\n',message)
                    self.assertEqual(self.config,before)
        self.assertEqual(list(self.target.iterdir()),[])

    def test_cli_invalid_status_rejects_preview_and_apply_without_creating_factory(self):
        self.config['tasks'][0]['status']='todo'
        for flags in ((),('--apply',)):
            result,before=self.cli(*flags)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('tasks[0].status',result.stderr);self.assertNotIn('PASS:',result.stdout)
            self.assertEqual(before,self.snapshot());self.assertFalse((self.target/'.software-factory').exists())

    def test_later_invalid_task_names_only_its_position(self):
        task=copy.deepcopy(self.config['tasks'][0]);task.update(id='PRIVATE_TASK_ID',status='UNKNOWN')
        self.config['tasks'].append(task)
        result,before=self.cli('--apply')
        self.assertEqual(result.returncode,1);self.assertIn('tasks[1].status',result.stderr)
        self.assertNotIn('PRIVATE_TASK_ID',result.stdout+result.stderr);self.assertEqual(before,self.snapshot())

    def test_all_canonical_statuses_preserve_config_living_state_and_optional_gates(self):
        self.config['operations']={'smoke_gates':{'required':False}}
        for value in STATUSES:
            with self.subTest(status=value):
                self.config['tasks'][0]['status']=value;before=copy.deepcopy(self.config)
                validate(self.config);files=render(self.config,self.research)
                self.assertEqual(json.loads(files['config.json'])['tasks'][0]['status'],value)
                plan=json.loads(files['task-plan.json']);self.assertEqual(plan['tasks'][0]['status'],value)
                self.assertEqual(plan['events'],[]);self.assertEqual(self.config,before)
                rows=gate_rows(files['verification.md'])
                for gate in ('G1','G2','G3'):
                    self.assertEqual(rows[gate]['required'],'no');self.assertEqual(rows[gate]['result'],'NOT RUN')

    def test_unchanged_default_and_valid_older_config_apply_and_check(self):
        self.assertEqual(self.config['tasks'][0]['status'],'blocked')
        for key in ('operations','dashboard','assumptions'):self.config.pop(key,None)
        result,_=self.cli('--apply');self.assertEqual(result.returncode,0,result.stderr)
        root=self.target/'.software-factory';check(root,quiet=True)
        plan=json.loads((root/'task-plan.json').read_text(encoding='utf-8'))
        self.assertEqual(plan['tasks'][0]['status'],'blocked');self.assertEqual(plan['events'],[])
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/scaffold.py'),'--check',str(root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.count('PASS:'),1)
        self.assertEqual(before,self.snapshot())

    def test_reviewed_living_legacy_correction_preserves_history_and_freeform_check(self):
        root=self.write_factory();path=root/'task-plan.json';plan=json.loads(path.read_text(encoding='utf-8'))
        plan['tasks'][0]['status']='todo';path.write_text(json.dumps(plan),encoding='utf-8')
        before=self.snapshot()
        argv=[sys.executable,'-B',str(ROOT/'scripts/status.py'),'--factory',str(root),'--task','T1',
              '--status','pending','--result','not-run','--evidence','SYNTHETIC reviewed vocabulary correction; no check executed',
              '--revision','synthetic-subject','--environment','isolated fixture','--check','A999 free-form correction label']
        result=subprocess.run(argv,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,self.snapshot())
        result=subprocess.run(argv+['--apply'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        updated=json.loads(path.read_text(encoding='utf-8'));self.assertEqual(updated['tasks'][0]['status'],'pending')
        self.assertEqual(updated['events'][0]['old_status'],'todo');self.assertEqual(updated['events'][0]['result'],'not-run')
        self.assertEqual(updated['events'][0]['check'],'A999 free-form correction label')
        after=self.snapshot();key=path.relative_to(self.parent).as_posix()
        self.assertEqual({k:v for k,v in before.items() if k!=key},{k:v for k,v in after.items() if k!=key})
        check(root,quiet=True)


if __name__=='__main__':unittest.main()
