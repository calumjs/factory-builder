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
from integrity import check

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
        root = self.write()
        issues = [{'id': '7', 'title': 'ok', 'submitter': 'alice', 'created_at': '2026-10-01'},
                  {'id': '8', 'title': 'stranger', 'submitter': 'mallory', 'created_at': '2026-10-02'},
                  {'id': 'T1', 'title': 'dup', 'submitter': 'alice', 'created_at': '2026-10-03'},
                  {'id': '9', 'title': 'dep', 'submitter': 'alice', 'created_at': '2026-10-04', 'depends_on': ['7']},
                  'garbage']
        result = run.select(*self.load(root), runs=self.project / '.factory-runs', issues=issues, now=NOW)
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
        for needle in ('exactly one task: T1', '/factory-build', '/factory-verify', 'Allowed paths: tests/', 'Stop conditions'):
            self.assertIn(needle, prompt)
        self.assertEqual(result['after_workers'], ['factory-release', 'factory-learn'])
        self.assertEqual(result['workers'][0]['isolation'], 'worktree')

    def test_schedule_renders_each_kind_and_refuses_unbounded(self):
        root, config, _ = self.load(self.write())
        self.assertIn('0 */2 * * *', run.schedule_text(root, config, 'cron'))
        self.assertIn('<key>StartInterval</key><integer>7200</integer>', run.schedule_text(root, config, 'launchd'))
        self.assertIn('/MO 120', run.schedule_text(root, config, 'windows'))
        github = run.schedule_text(root, config, 'github')
        self.assertIn('cron: "0 */2 * * *"', github)
        self.assertIn('workflow_dispatch', github)
        self.assertIn('0 */4 * * *', run.schedule_text(root, config, 'cron', every=240))
        with self.assertRaises(ValueError):
            run.schedule_text(root, config, 'cron', every=5)
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
        root = self.write()
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/run.py'), '--factory', str(root), 'schedule',
                                 '--kind', 'cron', '--write', str(root / 'cron.txt'), '--apply'],
                                capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((root / 'cron.txt').exists())
        check(root, quiet=True)


if __name__ == '__main__':
    unittest.main()
