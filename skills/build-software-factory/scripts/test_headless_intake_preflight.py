"""Local invocation and actual mapping/scope behavior; no hosted worker proof."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from gates import assess, gate_rows, requirements
from incremental_records import gate_change
from research import PHASES
from scaffold import ROOT, render
from scoped_assessment import assess_scope


class HeadlessHelperPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.env = dict(os.environ)
        for name in ('PYTHONPATH', 'PYTHONHOME'):
            self.env.pop(name, None)

    def probe(self, script, isolated=False):
        command = [sys.executable] + (['-I'] if isolated else [])
        command += ['-B', str(ROOT / 'scripts' / script), '--help']
        return subprocess.run(command, cwd=self.cwd, env=self.env,
                              capture_output=True, text=True, timeout=15)

    def test_absolute_trusted_helpers_launch_without_plugin_host_from_unrelated_cwd(self):
        # This shadow must never replace a sibling in the trusted script directory.
        (self.cwd / 'research.py').write_text('raise AssertionError("wrong source")\n', encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.cwd.iterdir()}
        helpers = {'scaffold.py': '--check', 'status.py': '--task', 'gates.py': '--revision',
                   'run.py': '--factory', 'scoped_assessment.py': '--scope',
                   'incremental_records.py': '--kind', 'observation_drafts.py': '--factory'}
        for script, option in helpers.items():
            with self.subTest(script=script):
                result = self.probe(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(option, result.stdout)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.cwd.iterdir()})

    def test_documented_isolated_invocation_stops_before_scaffold_argument_parsing(self):
        result = self.probe('scaffold.py', isolated=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ModuleNotFoundError', result.stderr)
        self.assertIn("'research'", result.stderr)
        self.assertEqual(list(self.cwd.iterdir()), [])
        guide = (ROOT / 'references/headless-intake-preflight.md').read_text(encoding='utf-8')
        self.assertIn('If the harness requires `-I`, keep', guide)
        self.assertIn('Do not remove that requirement', guide)


class SetupItemScopeExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.factory = Path(self.temp.name) / '.software-factory'
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['acceptance'] = ['Synthetic setup assertion', 'Synthetic per-item assertion']
        self.config['tasks'] = [
            {'id': 'T1', 'goal': 'Synthetic setup', 'owner': 'fixture', 'depends_on': [],
             'acceptance_ids': ['A1'], 'allowed_paths': ['setup/'], 'status': 'done'},
            {'id': 'T2', 'goal': 'Synthetic item', 'owner': 'fixture', 'depends_on': ['T1'],
             'acceptance_ids': ['A2'], 'allowed_paths': ['src/'], 'status': 'done'}]
        self.config['operations'] = {'smoke_gates': {
            'pre_merge': 'Synthetic G1 observation', 'targeted': 'Synthetic G2 observation',
            'target_kind': 'artifact', 'deployed_url': 'synthetic-artifact'}}
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        applicable = {'intake', 'release', 'build', 'verify'}
        self.research.update(status='complete', summary='SYNTHETIC fixture; no actual research')
        self.research['coverage'] = {
            phase: {'status': 'applicable' if phase in applicable else 'not_applicable',
                    'reason': 'Synthetic fixture coverage'} for phase in PHASES}
        self.research['sources'] = [{'id': 'S1', 'url': 'https://example.invalid/synthetic',
                                    'accessed_on': '2026-10-29', 'kind': 'synthetic fixture',
                                    'version_scope': 'synthetic', 'observation': 'No actual source read',
                                    'status': 'read'}]
        self.research['practices'] = [
            self.practice('P2', ['intake'], 'candidate'),
            self.practice('P7', ['intake', 'release']),
            self.practice('P12', ['build', 'verify']),
            self.practice('P20', ['release'])]
        guide = (ROOT / 'references/headless-intake-preflight.md').read_text(encoding='utf-8')
        blocks = re.findall(r'```json\n(.*?)\n```', guide, re.S)
        self.assertEqual(len(blocks), 1)
        self.scope = json.loads(blocks[0])

    def practice(self, identity, phases, decision='selected'):
        return {'id': identity, 'decision': decision, 'source_ids': ['S1'], 'phases': phases,
                'relevance': 'Synthetic relevance', 'compatibility': 'Synthetic compatibility',
                'tradeoff': 'Synthetic tradeoff', 'instruction': 'Synthetic instruction ' + identity,
                'check': 'Synthetic check ' + identity}

    def write(self):
        files = render(self.config, self.research)
        for name, body in files.items():
            path = self.factory / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
        return files

    def snapshot(self):
        return {str(p.relative_to(self.factory)): p.read_bytes()
                for p in self.factory.rglob('*') if p.is_file()}

    def record_item(self):
        self.write()
        plan_path = self.factory / 'task-plan.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        for task, subject in [('T1', 'setup-subject'), ('T2', 'item-subject')]:
            plan['events'].append({'id': 'synthetic-' + task, 'task_id': task,
                'timestamp': '2026-11-03T00:00:00Z', 'revision': subject,
                'environment': 'synthetic', 'check': 'synthetic observation', 'result': 'passed',
                'evidence': 'Synthetic fixture, no application run', 'old_status': 'pending', 'status': 'done'})
        plan_path.write_text(json.dumps(plan), encoding='utf-8')
        path = self.factory / 'verification.md'; text = path.read_text(encoding='utf-8')
        for gate in ('G1', 'G2', 'A2', 'R2'):
            change = {'gate': gate, 'revision': 'item-subject', 'result': 'PASSED',
                      'environment': 'synthetic', 'evidence': 'Synthetic observed fixture only',
                      'target': 'synthetic-artifact', 'checked_at': '2026-11-03T00:00:00Z',
                      'exit_status': '0'}
            text = gate_change(text, self.config, self.research, change).decode('utf-8')
        path.write_text(text, encoding='utf-8')

    def test_selected_order_mapping_and_stages_match_worked_example(self):
        files = self.write(); expected = requirements(self.config, self.research)
        for gate, practice, stage in [('R1', 'P7', 'pre-merge'), ('R2', 'P12', 'pre-merge'),
                                      ('R3', 'P20', 'post-merge')]:
            self.assertIn('- ' + gate + ' / ' + practice, files['verification.md'])
            self.assertEqual(expected[gate]['stage'], stage)
            self.assertEqual(expected[gate]['design'], 'Synthetic check ' + practice)
            self.assertEqual(gate_rows(files['verification.md'])[gate]['result'], 'NOT RUN')
        self.assertNotIn('/ P2 ', files['verification.md'])
        self.assertNotIn('dashboard/status.py', files)
        self.assertNotIn('dashboard/run.py', files)

    def test_reordering_selected_practices_changes_mapping_and_never_invents_observations(self):
        reordered = copy.deepcopy(self.research)
        reordered['practices'][1:3] = reversed(reordered['practices'][1:3])
        files = render(self.config, reordered)
        self.assertIn('- R1 / P12', files['verification.md'])
        self.assertIn('- R2 / P7', files['verification.md'])
        self.assertEqual(requirements(self.config, reordered)['R1']['design'], 'Synthetic check P12')
        self.assertTrue(all(row['result'] == 'NOT RUN' for row in gate_rows(files['verification.md']).values()))

    def test_stage_override_does_not_remove_or_waive_setup_requirement(self):
        self.config['operations']['smoke_gates']['check_stages'] = {
            'R1': {'stage': 'post-merge', 'rationale': 'Synthetic observed deployment prerequisite'}}
        files = self.write(); row = gate_rows(files['verification.md'])['R1']
        self.assertEqual(row['stage'], 'post-merge')
        self.assertEqual(row['required'], 'yes'); self.assertEqual(row['result'], 'NOT RUN')

    def test_documented_scope_can_pass_while_required_setup_stays_visible_and_project_blocks(self):
        self.record_item(); before = self.snapshot()
        result = assess_scope(self.factory, self.scope, 'pre-merge', 'item-subject')
        self.assertEqual(result['assessment'], 'SCOPED ELIGIBLE')
        self.assertEqual(result['waivers'], [])
        excluded = {row['gate']: row for row in result['out_of_scope']}
        self.assertEqual(excluded['R1']['required'], 'yes')
        self.assertEqual(excluded['R1']['result'], 'NOT RUN')
        self.assertTrue(assess(self.factory, 'pre-merge', 'item-subject'))
        self.assertIn('not project-wide readiness', result['notice'])
        self.assertEqual(self.snapshot(), before)

    def test_selected_stale_subject_and_incomplete_setup_dependency_still_block(self):
        self.record_item()
        stale = assess_scope(self.factory, self.scope, 'pre-merge', 'different-item')
        self.assertEqual(stale['assessment'], 'SCOPED BLOCKED')
        path = self.factory / 'task-plan.json'; plan = json.loads(path.read_text(encoding='utf-8'))
        plan['tasks'][0]['status'] = 'blocked'; path.write_text(json.dumps(plan), encoding='utf-8')
        blocked = assess_scope(self.factory, self.scope, 'pre-merge', 'item-subject')
        self.assertEqual(blocked['assessment'], 'SCOPED BLOCKED')
        self.assertIn('Task T2 has incomplete dependencies', blocked['problems'])


if __name__ == '__main__':
    unittest.main()
