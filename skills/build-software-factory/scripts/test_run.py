"""Factory-run driver regressions: deterministic selection, bounded capacity,
kill switch, run records outside the factory, scheduler rendering. No worker,
scheduler or network action is performed."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import run
from scaffold import ROOT, render, main as scaffold_main
from integrity import check, digest

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def task(i, deps=(), paths=(), status='pending'):
    return {'id': i, 'goal': 'Goal ' + i, 'owner': 'agent', 'depends_on': list(deps),
            'acceptance_ids': ['A1'], 'allowed_paths': list(paths), 'status': status}


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / 'project'
        self.project.mkdir()
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text())
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text())
        self.config['budget']['max_workers'] = 2
        self.config['tasks'] = [task('T1', paths=['tests/']), task('T2', paths=['src/export/']),
                                task('T3', deps=['T1'], paths=['src/x/']), task('T4', paths=['src/'])]
        self.config['operations'] = {
            'autonomy': {'mode': 'bounded', 'kill_switch': 'STOP file', 'max_items_per_hour': 3,
                         'allowed_submitters': ['alice'], 'rejected_items': 'record and stop'},
            'issue_intake': {'mode': 'continuous', 'github_scope': 'org/repo', 'status': 'disabled',
                             'evidence': 'synthetic test', 'cadence': '120'}}

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, config=None):
        files = render(config or self.config, self.research)
        root = self.project / '.software-factory'
        for name, body in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8', newline='\n')
        check(root, quiet=True)
        return root

    def load(self, root):
        return root, json.loads((root / 'config.json').read_text()), json.loads((root / 'task-plan.json').read_text())

    def test_generated_factory_has_run_skill_and_scheduling_templates(self):
        files = render(self.config, self.research)
        skill = files['.claude/skills/factory-run/SKILL.md']
        self.assertIn('name: factory-run', skill)
        for phase in ('factory-build', 'factory-verify', 'factory-release', 'factory-learn'):
            self.assertIn(phase, skill)
        self.assertIn('scheduling/README.md', files)
        self.assertIn('scheduling/factory-run.example.yml', files)
        self.assertIn('.claude/skills/factory-run/SKILL.md', files['manifest.json'])

    def test_selection_respects_dependencies_concurrency_and_path_overlap(self):
        root = self.write()
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', now=NOW)
        self.assertEqual([c['task_id'] for c in result['candidates']], ['T1', 'T2'])
        blocked = {b['task_id']: b['reason'] for b in result['blocked']}
        self.assertIn('waiting on T1', blocked['T3'])
        self.assertIn('no capacity', blocked['T4'])
        self.assertTrue(result['proceed'])
        self.assertEqual(result['capacity']['available'], 2)

    def test_overlapping_paths_are_never_planned_together(self):
        self.config['budget']['max_workers'] = 4
        root = self.write()
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', now=NOW)
        self.assertEqual([c['task_id'] for c in result['candidates']], ['T1', 'T2'])
        blocked = {b['task_id']: b['reason'] for b in result['blocked']}
        self.assertIn('overlap', blocked['T4'])

    def test_in_progress_tasks_consume_capacity(self):
        self.config['tasks'][0]['status'] = 'in_progress'
        root = self.write()
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', now=NOW)
        self.assertEqual(result['capacity']['in_progress'], ['T1'])
        self.assertEqual([c['task_id'] for c in result['candidates']], ['T2'])

    def test_kill_switch_file_and_env_stop_selection(self):
        root = self.write()
        runs = self.project / '.factory-runs'
        runs.mkdir()
        (runs / 'STOP').write_text('')
        result = run.select(*self.load(root), runs=runs, now=NOW)
        self.assertFalse(result['proceed'])
        self.assertEqual(result['candidates'], [])
        self.assertIn('STOP', result['kill_switch'])
        (runs / 'STOP').unlink()
        old = os.environ.get('FACTORY_STOP')
        os.environ['FACTORY_STOP'] = '1'
        try:
            self.assertFalse(run.select(*self.load(root), runs=runs, now=NOW)['proceed'])
        finally:
            if old is None:
                del os.environ['FACTORY_STOP']
            else:
                os.environ['FACTORY_STOP'] = old

    def test_rate_limit_counts_dispatches_in_the_last_hour(self):
        root = self.write()
        runs = self.project / '.factory-runs'
        runs.mkdir()
        recent = run.record_run(runs, 'run-a-1', ['T9', 'T8'], 'completed', '', now=NOW - timedelta(minutes=30))
        old = run.record_run(runs, 'run-b-1', ['T7', 'T6', 'T5'], 'completed', '', now=NOW - timedelta(hours=2))
        for record in (recent, old):
            (runs / (record['run_id'] + '.json')).write_text(json.dumps(record))
        result = run.select(*self.load(root), runs=runs, now=NOW)
        self.assertEqual(result['capacity']['dispatched_last_hour'], 2)
        self.assertEqual(result['capacity']['rate_remaining'], 1)
        self.assertEqual([c['task_id'] for c in result['candidates']], ['T1'])

    def test_manual_autonomy_has_no_rate_limit_but_continuous_intake_is_diagnosed(self):
        self.config['operations']['autonomy'] = {'mode': 'manual', 'kill_switch': 'x', 'max_items_per_hour': 0,
                                                 'allowed_submitters': [], 'rejected_items': 'x'}
        root = self.write()
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', now=NOW)
        self.assertIsNone(result['capacity']['rate_remaining'])
        self.assertTrue(any('not bounded' in d for d in result['diagnostics']))

    def test_issue_snapshot_is_filtered_read_only(self):
        self.config['operations']['issue_intake']['status']='enabled'
        root = self.write()
        issues = [{'id': '7', 'title': 'ok', 'submitter': 'alice', 'created_at': '2026-10-01','labels':['ready']},
                  {'id': '8', 'title': 'stranger', 'submitter': 'mallory', 'created_at': '2026-10-02','labels':['ready']},
                  {'id': 'T1', 'title': 'dup', 'submitter': 'alice', 'created_at': '2026-10-03','labels':['ready']},
                  {'id': '9', 'title': 'dep', 'submitter': 'alice', 'created_at': '2026-10-04', 'depends_on': ['7'],'labels':['ready']},
                  'garbage']
        policy={'repository':'org/repo','ready_label':'ready','excluded_labels':['paused','rejected']}
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', issues=issues, now=NOW,issue_policy=policy)
        self.assertEqual([i['id'] for i in result['issues']['eligible']], ['7'])
        reasons = {r['id']: r['reason'] for r in result['issues']['rejected']}
        self.assertIn('allowed_submitters', reasons['8'])
        self.assertIn('already', reasons['T1'])
        self.assertIn('dependencies', reasons['9'])
        self.assertIn(None, reasons)

    def test_plan_renders_one_worker_per_candidate_with_handoff(self):
        root = self.write()
        result = run.plan_pass(*self.load(root), runs=self.project / '.factory-runs', now=NOW)
        self.assertEqual([w['task_id'] for w in result['workers']], ['T1', 'T2'])
        prompt = result['workers'][0]['prompt']
        for needle in ('"task_id": "T1"', '/factory-build', '/factory-verify', '"allowed_paths": ["tests/"]', 'untrusted task and handoff data'):
            self.assertIn(needle, prompt)
        self.assertEqual(result['after_workers'], ['integrate-and-reverify', 'factory-release-if-authorized', 'factory-learn'])
        self.assertEqual(result['workers'][0]['isolation'], 'worktree')

    def test_worker_budget_text_stays_quoted_untrusted_data(self):
        self.config['budget']['currency']='USD\nSYNTHETIC injected directive'
        root=self.write();result=run.plan_pass(*self.load(root),runs=self.project/'.factory-runs',now=NOW)
        prompt=result['workers'][0]['prompt']
        self.assertNotIn('USD\nSYNTHETIC',prompt)
        self.assertIn('USD\\nSYNTHETIC',prompt)
        self.assertIn('untrusted task and handoff data',prompt)

    def test_issue_intake_fail_closed_on_policy_labels_duplicates_and_stop(self):
        self.config['operations']['issue_intake']['status']='enabled'
        root=self.write();runs=self.project/'.factory-runs'
        policy={'repository':'org/repo','ready_label':'ready','excluded_labels':['paused']}
        issues=[{'id':'1','submitter':'alice','labels':['ready','paused']},
                {'id':'2','submitter':'alice','labels':['ready']},
                {'id':'2','submitter':'alice','labels':['ready']},
                {'id':'3','submitter':'alice','labels':['ready']}]
        result=run.select(*self.load(root),runs=runs,issues=issues,now=NOW,issue_policy=policy)
        self.assertEqual([x['id'] for x in result['issues']['eligible']],['3'])
        self.assertEqual(len(result['issues']['rejected']),3)
        missing=run.select(*self.load(root),runs=runs,issues=issues,now=NOW)
        self.assertEqual(missing['issues']['eligible'],[])
        no_capacity=copy.deepcopy(self.config);no_capacity['budget']['max_workers']=0
        self.assertEqual(run.select(root,no_capacity,self.load(root)[2],runs,issues,NOW,policy)['issues']['eligible'],[])
        disabled=copy.deepcopy(self.config);disabled['operations']['issue_intake']['status']='disabled'
        self.assertEqual(run.select(root,disabled,self.load(root)[2],runs,issues,NOW,policy)['issues']['eligible'],[])
        runs.mkdir();(runs/'STOP').write_text('')
        self.assertEqual(run.select(*self.load(root),runs=runs,issues=issues,now=NOW,issue_policy=policy)['issues']['eligible'],[])

    def test_path_aliases_are_conservatively_overlapping(self):
        for left,right in (('src/*','tests/file'),('src/../x','x/a'),('Src','src/file'),('src\\file','other'),('.','src/file')):
            self.assertTrue(run.overlaps({'allowed_paths':[left]},{'allowed_paths':[right]}))
        self.assertFalse(run.overlaps({'allowed_paths':['src/a']},{'allowed_paths':['src/b']}))

    def test_unsafe_or_missing_paths_block_even_the_only_task(self):
        self.config['tasks']=[task('T1',paths=['src/../other'])]
        root=self.write();result=run.select(*self.load(root),runs=self.project/'.factory-runs',now=NOW)
        self.assertEqual(result['candidates'],[]);self.assertIn('unsafe',result['blocked'][0]['reason'])

    def test_policy_config_drift_blocks_runner_load(self):
        root=self.write();path=root/'policy.md'
        source=path.read_text(encoding='utf-8');changed=source.replace('"mode": "bounded"','"mode": "manual"',1)
        self.assertNotEqual(source,changed);path.write_text(changed,encoding='utf-8')
        manifest=json.loads((root/'manifest.json').read_text());manifest['contracts']['policy.md']=digest(path.read_bytes())
        (root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'controls disagree'):run.load(root)

    def test_normalized_run_directory_cannot_alias_factory(self):
        root=self.write();outside=self.project/'scratch';outside.mkdir()
        alias=outside/'..'/'.software-factory'/'unsafe-runs'
        with self.assertRaises(ValueError):run.runs_dir(root,str(alias))
        self.assertFalse((root/'unsafe-runs').exists());check(root,quiet=True)

    def test_select_cli_require_work_reports_stop_as_nonzero(self):
        root=self.write();runs=self.project/'.factory-runs';runs.mkdir();(runs/'STOP').write_text('')
        cmd=[sys.executable,str(ROOT/'scripts/run.py'),'--factory',str(root),'select','--require-work']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertFalse(json.loads(result.stdout)['proceed'])

    def test_malformed_and_naive_run_records_block_selection(self):
        root=self.write();runs=self.project/'.factory-runs';runs.mkdir();path=runs/'run-malformed.json'
        for contents in ('{bad',json.dumps({'started':'2026-10-30T11:00:00','dispatched':['T1']})):
            path.write_text(contents)
            with self.assertRaises(ValueError):run.select(*self.load(root),runs=runs,now=NOW)

    def test_select_does_not_claim_atomic_reservation(self):
        root=self.write();runs=self.project/'.factory-runs'
        first=run.select(*self.load(root),runs=runs,now=NOW)
        second=run.select(*self.load(root),runs=runs,now=NOW)
        self.assertEqual(first['candidates'],second['candidates'])
        self.assertTrue(any('no reservation' in x for x in first['diagnostics']))
        self.assertFalse(runs.exists())

    def test_zero_time_budget_blocks_task_selection(self):
        self.config['budget']['max_minutes']=0
        root=self.write();result=run.select(*self.load(root),runs=self.project/'.factory-runs',now=NOW)
        self.assertFalse(result['proceed']);self.assertEqual(result['candidates'],[])
        self.assertTrue(any('zero' in text for text in result['diagnostics']))

    def test_schedule_renders_each_kind_and_refuses_unbounded(self):
        self.config['operations']['issue_intake']['status']='enabled'
        root, config, _ = self.load(self.write())
        for kind in ('cron','launchd','windows','github'):
            proposal=json.loads(run.schedule_text(root,config,kind))
            self.assertFalse(proposal['executable']);self.assertEqual(proposal['interval_minutes'],120)
        self.assertEqual(json.loads(run.schedule_text(root,config,'cron',every=240))['cron_expression'],'0 */4 * * *')
        with self.assertRaises(ValueError):
            run.schedule_text(root, config, 'cron', every=5)
        for invalid in (90,1500,2880):
            with self.assertRaises(ValueError):run.schedule_text(root,config,'cron',every=invalid)
        window=copy.deepcopy(config);window['operations']['issue_intake'].update(coverage='operator_window',window='09:00-17:00',timezone='Europe/London',window_evidence='operator choice')
        with self.assertRaisesRegex(ValueError,'Restricted coverage'):run.schedule_text(root,window,'cron')
        manual = copy.deepcopy(config)
        manual['operations']['autonomy']['mode'] = 'manual'
        with self.assertRaises(ValueError):
            run.schedule_text(root, manual, 'cron')

    def test_cli_record_writes_outside_factory_and_preserves_integrity(self):
        root = self.write()
        runs = self.project / '.factory-runs'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
        cmd = [sys.executable, str(ROOT / 'scripts/run.py'), '--factory', str(root), 'record',
               '--run-id', 'run-20261030T120000Z-abc', '--dispatched', 'T1,T2', '--outcome', 'completed', '--notes', 'synthetic']
        preview = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('DRY RUN', preview.stdout)
        self.assertFalse(runs.exists())
        applied = subprocess.run(cmd + ['--apply'], capture_output=True, text=True, env=env)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        record = json.loads((runs / 'run-20261030T120000Z-abc.json').read_text())
        self.assertEqual(record['dispatched'], ['T1', 'T2'])
        check(root, quiet=True)
        again = subprocess.run(cmd + ['--apply'], capture_output=True, text=True, env=env)
        self.assertNotEqual(again.returncode, 0)

    def test_run_records_inside_factory_are_refused(self):
        root = self.write()
        with self.assertRaises(ValueError):
            run.runs_dir(root, root / 'runs')

    def test_cli_schedule_write_refuses_factory_path(self):
        self.config['operations']['issue_intake']['status']='enabled'
        root = self.write()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/run.py'), '--factory', str(root), 'schedule',
                                 '--kind', 'cron', '--write', str(root / 'cron.txt'), '--apply'],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / 'cron.txt').exists())
        check(root, quiet=True)

    def test_schedule_write_refuses_normalized_factory_alias_and_active_workflows(self):
        self.config['operations']['issue_intake']['status']='enabled'
        root=self.write();scratch=self.project/'scratch';scratch.mkdir()
        for target in (scratch/'..'/'.software-factory'/'proposal.json', self.project/'.github'/'workflows'/'proposal.yml'):
            result=subprocess.run([sys.executable,str(ROOT/'scripts/run.py'),'--factory',str(root),'schedule','--kind','cron','--write',str(target),'--apply'],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertFalse(target.exists())
        check(root,quiet=True)


if __name__ == '__main__':
    unittest.main()
