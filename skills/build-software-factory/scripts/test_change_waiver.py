"""Per-change V1 choices through real record/checker helpers; synthetic observations only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows
from incremental_records import apply, preview
from scaffold import ROOT, render


class ChangeWaiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '.software-factory'
        self.subject = 'synthetic-tests-only-subject'
        self.target = 'synthetic-installed-artifact'
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.config['acceptance'] = ['Build completes', 'Released artifact retains expected behavior']
        self.config['operations'] = {
            'done_videos': {'enabled': True},
            'smoke_gates': {
                'check_stages': {'A2': {'stage': 'post-merge', 'rationale': 'Confirm released behavior'}},
                'checks': {'G3': {
                    'command': ['synthetic-smoke'], 'environment': 'synthetic installed fixture',
                    'env_names': [], 'target': {'kind': 'artifact', 'value': self.target, 'base_url_env': None}}}}}
        self.write_factory()

    def write_factory(self):
        for name, body in render(self.config, self.research).items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8', newline='\n')

    def text(self):
        return (self.root / 'verification.md').read_text(encoding='utf-8')

    def required(self, gate, value):
        # Explicit synthetic operator choice; preserve all observation columns.
        lines = self.text().splitlines()
        for index, line in enumerate(lines):
            if line.startswith('| ' + gate + ' |'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[4] = value
                lines[index] = '| ' + ' | '.join(cells) + ' |'
        (self.root / 'verification.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def record(self, gate, result='PASSED', revision=None):
        change = {
            'gate': gate, 'result': result, 'revision': revision or self.subject,
            'environment': 'synthetic installed fixture', 'target': self.target,
            'evidence': 'SYNTHETIC observation for ' + gate + ': ' + result + '; no application or media run',
            'checked_at': '2026-11-03T01:00:00Z',
            'exit_status': '0' if result == 'PASSED' else '1' if result == 'FAILED' else ''}
        prepared = preview(self.root, 'gate', change)
        apply(*prepared, prepared[-1])

    def cli(self, stage='post-merge', subject=None, target=None):
        # The checker must leave all factory bytes, including failed observations, alone.
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result = subprocess.run([
            sys.executable, '-B', str(ROOT / 'scripts/gates.py'), '--factory', str(self.root),
            '--stage', stage, '--revision', subject or self.subject, '--target', target or self.target],
            capture_output=True, text=True)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertNotEqual(result.returncode, 2, result.stderr)
        return result

    def pass_release_checks(self):
        self.record('G3')
        self.record('A2')

    def test_optional_unrun_video_is_waived_with_passing_required_observations(self):
        self.pass_release_checks()
        before = gate_rows(self.text())['V1']
        self.required('V1', 'no')
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('V1 WAIVED (recorded NOT RUN)', result.stdout)
        self.assertIn('ELIGIBLE WITH WAIVERS', result.stdout)
        self.assertEqual(gate_rows(self.text())['V1'], dict(before, required='no'))
        self.assertTrue(json.loads((self.root / 'config.json').read_text())['operations']['done_videos']['enabled'])

    def test_failed_video_observation_and_history_survive_optional_choice(self):
        self.pass_release_checks()
        self.record('V1', 'FAILED')
        before = gate_rows(self.text())['V1']
        self.required('V1', 'no')
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn('V1 WAIVED (recorded FAILED)', result.stdout)
        self.assertEqual(gate_rows(self.text())['V1'], dict(before, required='no'))
        # A subsequent observation uses the real writer's quoted-history path.
        self.record('V1', 'BLOCKED')
        self.assertIn('> | V1 |', self.text())
        self.assertIn(before['evidence'], self.text())
        self.assertIn('V1 WAIVED (recorded BLOCKED)', self.cli().stdout)

    def test_video_waiver_cannot_bypass_smoke_failure_staleness_or_wrong_target(self):
        self.pass_release_checks()
        self.required('V1', 'no')
        for result, revision, expected in (
                ('FAILED', self.subject, 'G3 is FAILED'),
                ('PASSED', 'synthetic-old-subject', 'G3 has stale or missing revision')):
            with self.subTest(result=result, revision=revision):
                self.record('G3', result, revision)
                checked = self.cli()
                self.assertEqual(checked.returncode, 1)
                self.assertIn(expected, checked.stdout)
        self.record('G3')
        wrong = self.cli(target='synthetic-other-artifact')
        self.assertEqual(wrong.returncode, 1)
        self.assertIn('Actual post-release target differs', wrong.stdout)

    def test_video_waiver_does_not_waive_acceptance_or_premerge_smoke(self):
        self.pass_release_checks()
        self.required('V1', 'no')
        self.record('A2', 'FAILED')
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn('A2 is FAILED', result.stdout)
        result = self.cli(stage='pre-merge')
        self.assertEqual(result.returncode, 1)
        for gate in ('G1', 'G2', 'A1'):
            self.assertIn(gate + ' is NOT RUN', result.stdout)

    def test_shared_waiver_persists_until_next_subject_is_explicitly_reset(self):
        self.pass_release_checks()
        self.required('V1', 'no')
        self.subject = 'synthetic-next-feature-subject'
        self.pass_release_checks()
        # Deliberately prove the documented limitation: no automatic waiver expiry.
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(gate_rows(self.text())['V1']['required'], 'no')
        self.required('V1', 'yes')
        blocked = self.cli()
        self.assertEqual(blocked.returncode, 1)
        self.assertIn('V1 is NOT RUN', blocked.stdout)
        self.record('V1')
        self.assertEqual(self.cli().returncode, 0)
        self.assertNotIn('WAIVED', self.cli().stdout)

    def test_ordinary_feature_requires_video_and_missing_row_is_not_a_waiver(self):
        self.pass_release_checks()
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn('V1 is NOT RUN', result.stdout)
        self.required('V1', 'no')
        path = self.root / 'verification.md'
        path.write_text('\n'.join(line for line in self.text().splitlines()
                                  if not line.startswith('| V1 |')) + '\n', encoding='utf-8')
        result = self.cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn('Missing expected gate row: V1', result.stdout)

    def test_disabled_video_has_no_fabricated_video_observation(self):
        self.config['operations']['done_videos']['enabled'] = False
        self.write_factory()
        self.pass_release_checks()
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertNotIn('V1', gate_rows(self.text()))
        self.assertNotIn('V1', result.stdout)
        self.assertNotIn('WAIVED', result.stdout)


if __name__ == '__main__':
    unittest.main()
