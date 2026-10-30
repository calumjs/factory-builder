"""Exercise the optional CI adapter against isolated local Git fixtures, never services."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ci_evidence import Git, assess_ci, bounded_run, full_sha, relative
from scaffold import ROOT, render


class CIEvidenceTests(unittest.TestCase):
    def test_git_output_is_bounded_during_stdout_and_stderr_collection(self):
        for descriptor in (1,2):
            code='import os; os.write('+str(descriptor)+', b"x" * 200000)'
            with self.assertRaisesRegex(ValueError,'exceeds bounded'):
                bounded_run([sys.executable,'-c',code],dict(os.environ),1024)

    def test_pipe_held_by_descendant_cannot_defeat_deadline(self):
        code='import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(1.5)"])'
        started=time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            bounded_run([sys.executable,'-c',code],dict(os.environ),1024,timeout=0.2)
        self.assertLess(time.monotonic()-started,1.2)

    def test_partial_clone_missing_object_cannot_use_any_transport(self):
        # Simulate older Git ignoring the newer no-lazy-fetch environment flag.
        # The only configured remote is this disposable local fixture.
        self.git('config','extensions.partialClone','origin')
        self.git('config','remote.origin.promisor','true')
        self.git('config','remote.origin.url',self.repo.as_uri())
        env=dict(os.environ,GIT_NO_LAZY_FETCH='0',GIT_ALLOW_PROTOCOL='',GIT_TERMINAL_PROMPT='0')
        result=subprocess.run(['git','-C',str(self.repo),'cat-file','-e','1'*40],capture_output=True,env=env)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'not allowed',result.stderr.lower())

    def test_git_read_always_denies_transports_even_if_environment_allowed_them(self):
        observed=[]
        def fake(argv,env,limit):
            observed.append(env)
            return 0,b'synthetic'
        with patch.dict(os.environ,{'GIT_ALLOW_PROTOCOL':'file:https'}):
            with patch('ci_evidence.bounded_run',side_effect=fake):
                self.assertEqual(Git(self.repo).read('status'),b'synthetic')
        self.assertEqual(observed[0]['GIT_ALLOW_PROTOCOL'],'')
        self.assertEqual(observed[0]['GIT_PROTOCOL_FROM_USER'],'0')

    def test_generated_ci_guide_describes_transport_restriction(self):
        guide=(self.factory/'ci/README.md').read_text(encoding='utf-8')
        self.assertIn('independently denies all Git transport protocols',guide)
        self.assertNotIn('must support --no-lazy-fetch',guide)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name)/'project';self.repo.mkdir()
        self.hooks=self.repo/'.fixture-empty-hooks';self.hooks.mkdir()
        self.factory=self.repo/'.software-factory';self.factory.mkdir()
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'synthetic-package'}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        (self.repo/'app.txt').write_text('SYNTHETIC application subject\n')
        self.git('init','-q');self.subject=self.commit()

    def tearDown(self):self.tmp.cleanup()

    def git(self,*args):
        result=subprocess.run(['git','-c','core.autocrlf=false','-c','user.name=Synthetic CI fixture',
                               '-c','core.hooksPath='+str(self.hooks),
                               '-c','user.email=fixture@example.invalid','-C',str(self.repo),*args],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def commit(self):
        self.git('add','--all');self.git('commit','-qm','Synthetic offline fixture')
        return self.git('rev-parse','HEAD')

    def record(self,stage='pre-merge',revision=None,failed=None,waived=None):
        lines=[]
        for line in (self.factory/'verification.md').read_text().splitlines():
            if line.startswith('| ') and line.split('|')[1].strip() in ('G1','G2','G3','A1'):
                cells=[v.strip() for v in line.strip('|').split('|')]
                if cells[1]==stage:
                    cells[2:4]=['Observed SYNTHETIC procedure; no app executed','isolated local fixture']
                    cells[5:]=[revision or self.subject,'FAILED' if cells[0]==failed else 'PASSED',
                               'SYNTHETIC stored observation only','synthetic-package','2026-10-30T07:00:00Z','0']
                    if cells[0]==waived:cells[4]='no'
                    line='| '+' | '.join(cells)+' |'
            lines.append(line)
        (self.factory/'verification.md').write_bytes('\n'.join(lines).encode('utf-8'))

    def assess(self,storage,**kwargs):
        return assess_ci(self.repo,'.software-factory',self.subject,storage,'pre-merge',**kwargs)

    def test_same_commit_missing_evidence_blocks_without_writes(self):
        before=self.git('status','--porcelain')
        result=self.assess(self.subject)
        self.assertEqual(result['assessment'],'blocked')
        self.assertTrue(any('NOT RUN' in row for row in result['problems']))
        self.assertEqual(self.git('status','--porcelain'),before)

    def test_evidence_only_storage_keeps_original_tested_subject_and_future_post_stage(self):
        self.record();storage=self.commit()
        result=self.assess(storage)
        self.assertEqual(result['assessment'],'recorded_requirements_satisfied')
        self.assertEqual(result['tested_subject'],self.subject)
        self.assertEqual(result['evidence_storage_revision'],storage)
        self.assertNotEqual(self.subject,storage)
        self.assertEqual(result['changed_evidence_files'],1)
        self.assertTrue(result['incomplete_tasks'])
        self.assertIn('no application checks',result['notice'].lower())
        wrong=assess_ci(self.repo,'.software-factory',storage,storage,'pre-merge')
        self.assertEqual(wrong['assessment'],'blocked')
        self.assertTrue(any('stale' in row for row in wrong['problems']))

    def test_new_deployed_storage_subject_requires_separate_post_confirmation(self):
        self.record();self.record('post-merge');storage=self.commit()
        prior=assess_ci(self.repo,'.software-factory',self.subject,storage,'post-merge','synthetic-package')
        self.assertFalse(prior['problems'])
        deployed=assess_ci(self.repo,'.software-factory',storage,storage,'post-merge','synthetic-package')
        self.assertTrue(any('stale' in row for row in deployed['problems']))

    def test_failure_and_intentional_waiver_stay_distinct(self):
        self.record(failed='G2');storage=self.commit()
        self.assertEqual(self.assess(storage)['assessment'],'blocked')
        self.record(failed='G2',waived='G2');storage=self.commit();result=self.assess(storage)
        self.assertEqual(result['assessment'],'eligible_with_waivers')
        self.assertEqual(result['waivers'],['G2 WAIVED (recorded FAILED)'])

    def test_source_or_tool_policy_change_cannot_hide_in_evidence_storage(self):
        self.record();(self.repo/'app.txt').write_text('Changed SYNTHETIC application\n');storage=self.commit()
        with self.assertRaisesRegex(ValueError,'Not an allowed evidence-only change'):self.assess(storage)
        # tools.json is living but is deliberately not an evidence-only allowlist entry.
        self.git('reset','--hard',self.subject)
        self.record();(self.factory/'tools.json').write_text('{"synthetic":"tool policy change"}');storage=self.commit()
        with self.assertRaisesRegex(ValueError,'Not an allowed evidence-only change'):self.assess(storage)

    def test_clean_storage_identity_and_full_sha_are_required(self):
        self.record();storage=self.commit()
        with self.assertRaisesRegex(ValueError,'HEAD'):self.assess(self.subject)
        (self.factory/'release-handoff.md').write_text('Uncommitted SYNTHETIC record')
        with self.assertRaisesRegex(ValueError,'clean checkout'):self.assess(storage)
        for value in ('HEAD',self.subject[:8],'--all','x'*40,'a'*41):
            with self.assertRaises(ValueError):full_sha(value)

    def test_index_assume_unchanged_cannot_hide_modified_living_bytes(self):
        self.record();storage=self.commit()
        self.git('update-index','--assume-unchanged','.software-factory/verification.md')
        with (self.factory/'verification.md').open('a') as stream:stream.write('\nUncommitted hidden SYNTHETIC note\n')
        self.assertEqual(self.git('status','--porcelain'),'')
        with self.assertRaisesRegex(ValueError,'Working factory bytes'):self.assess(storage)

    def test_line_ending_normalization_is_not_a_byte_binding(self):
        self.record();storage=self.commit();path=self.factory/'verification.md'
        path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n'))
        self.git('add','--','.software-factory/verification.md')  # Git normalizes this back to the same stored LF blob.
        self.assertEqual(self.git('status','--porcelain'),'')
        with self.assertRaisesRegex(ValueError,'Working factory bytes'):self.assess(storage)

    def test_durable_log_additions_are_subject_scoped_and_append_only(self):
        self.record();path=self.repo/'docs/factory-evidence'/self.subject/'smoke.txt'
        path.parent.mkdir(parents=True);path.write_text('SYNTHETIC inert observed log\n');storage=self.commit()
        self.assertFalse(self.assess(storage)['problems'])
        wrong=path.parent.parent/'other-subject'/'smoke.txt';wrong.parent.mkdir();wrong.write_text('SYNTHETIC wrong subject')
        storage=self.commit()
        with self.assertRaisesRegex(ValueError,'Not an allowed evidence-only change'):self.assess(storage)

    def test_evidence_path_does_not_admit_code_or_factory_escape(self):
        self.record();path=self.repo/'docs/factory-evidence'/self.subject/'execute.py';path.parent.mkdir(parents=True);path.write_text('SYNTHETIC not executed')
        storage=self.commit()
        with self.assertRaisesRegex(ValueError,'Not an allowed evidence-only change'):self.assess(storage)
        for path in ('../escape','/absolute','a//b','a/./b','.git/config','C:/drive','a\\b'):
            with self.assertRaises(ValueError):relative(path)
        with self.assertRaises(ValueError):self.assess(storage,evidence_dir='.software-factory')

    def test_task_definitions_and_prior_event_history_are_not_evidence_only(self):
        self.record();path=self.factory/'task-plan.json';plan=json.loads(path.read_text())
        plan['tasks'][0]['goal']='Changed SYNTHETIC scope';path.write_text(json.dumps(plan));storage=self.commit()
        with self.assertRaisesRegex(ValueError,'definition/rescope'):self.assess(storage)

    def test_prior_task_evidence_cannot_be_deleted_by_storage_commit(self):
        path=self.factory/'task-plan.json';plan=json.loads(path.read_text())
        plan['events'].append({'id':'old-synthetic-event','task_id':'T1','timestamp':'2026-10-30T06:00:00Z',
            'revision':self.subject,'environment':'isolated fixture','check':'SYNTHETIC failed observation',
            'result':'failed','evidence':'SYNTHETIC history','old_status':'blocked','status':'blocked'})
        path.write_text(json.dumps(plan));self.subject=self.commit()
        self.record();plan['events']=[];path.write_text(json.dumps(plan));storage=self.commit()
        with self.assertRaisesRegex(ValueError,'preserve prior task evidence'):self.assess(storage)

    def test_executable_log_and_unrelated_subject_are_rejected(self):
        self.record();path=self.repo/'docs/factory-evidence'/self.subject/'smoke.txt'
        path.parent.mkdir(parents=True);path.write_text('SYNTHETIC inert text')
        path.chmod(path.stat().st_mode|0o111)  # keep the working tree clean where core.fileMode is true
        self.git('add','--all');self.git('update-index','--chmod=+x',path.relative_to(self.repo).as_posix())
        self.git('commit','-qm','Synthetic executable mode fixture');storage=self.git('rev-parse','HEAD')
        with self.assertRaisesRegex(ValueError,'non-executable regular data'):self.assess(storage)
        self.git('checkout','--orphan','synthetic-unrelated')
        storage=self.commit()
        with self.assertRaisesRegex(ValueError,'merge-base'):self.assess(storage)

    def test_selected_task_requires_done_and_current_subject_event(self):
        self.record();storage=self.commit()
        result=self.assess(storage,required_tasks=['T1'])
        self.assertTrue(any('Task T1' in row for row in result['problems']))
        path=self.factory/'task-plan.json';plan=json.loads(path.read_text())
        plan['tasks'][0]['status']='done'
        plan['events'].append({'id':'synthetic-event','task_id':'T1','timestamp':'2026-10-30T07:00:00Z',
            'revision':self.subject,'environment':'isolated fixture','check':'SYNTHETIC observation',
            'result':'passed','evidence':'SYNTHETIC non-secret record','old_status':'blocked','status':'done'})
        path.write_text(json.dumps(plan));storage=self.commit()
        self.assertFalse(self.assess(storage,required_tasks=['T1'])['problems'])
        with self.assertRaisesRegex(ValueError,'Unknown'):self.assess(storage,required_tasks=['T999'])

    def test_template_uses_explicit_inputs_as_argv_and_propagates_blocked_exit(self):
        template=ROOT/'assets/templates/ci/job.example.py'
        spec=importlib.util.spec_from_file_location('synthetic_ci_job',template)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        env={'FACTORY_PYTHON':sys.executable,'FACTORY_TRUSTED_HELPER':str(ROOT/'scripts/ci_evidence.py'),
             'FACTORY_REPO':str(self.repo),'FACTORY_TESTED_SUBJECT_SHA':self.subject,
             'FACTORY_EVIDENCE_STORAGE_SHA':self.subject,'FACTORY_REQUIRED_TASKS':'["T1"]'}
        argv=module.command(env)
        self.assertIn(self.subject,argv);self.assertEqual(argv[-2:],['--require-task','T1'])
        result=subprocess.run(argv,capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['assessment'],'blocked')
        for missing in ('FACTORY_TRUSTED_HELPER','FACTORY_TESTED_SUBJECT_SHA'):
            bad=dict(env);bad.pop(missing)
            with self.assertRaises(ValueError):module.command(bad)
        bad=dict(env,FACTORY_TRUSTED_HELPER=str(self.repo/'untrusted-helper.py'))
        with self.assertRaisesRegex(ValueError,'outside the change checkout'):module.command(bad)
        env['FACTORY_ACTUAL_TARGET']='literal $(no-command) target'
        self.assertIn('literal $(no-command) target',module.command(env))


if __name__=='__main__':unittest.main()
