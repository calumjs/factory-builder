"""Synthetic feature confirmation through existing records; no app or target runs."""
import json
from pathlib import Path
import tempfile
import unittest
from phase_test_support import phase_text_at

from gates import assess, gate_rows, waivers
from incremental_records import preview, apply
from integrity import check
from scaffold import ROOT, render


class FeatureConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.subject = 'synthetic-released-subject'
        self.target = 'https://production.example.invalid'
        self.root = self.factory('web', self.target)

    def factory(self, kind, target):
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        config['acceptance'] = ['Build completes', 'Released export preserves the selected filters']
        config['operations'] = {'smoke_gates': {
            'target_kind': kind, 'deployed_url': target,
            'check_stages': {'A2': {'stage': 'post-merge', 'rationale': 'Confirm the actual released export'}},
            'checks': {'G3': {
                'command': ['synthetic-health-check'], 'environment': 'synthetic released target',
                'env_names': [], 'target': {'kind': kind, 'value': target, 'base_url_env': None}}}}}
        root = Path(self.temp.name) / kind / '.software-factory'
        for name, body in render(config, research).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8', newline='\n')
        check(root, quiet=True)
        return root

    def observation(self, gate, result='PASSED', **changes):
        data = {
            'gate': gate, 'result': result, 'revision': self.subject,
            'environment': 'synthetic released target', 'target': self.target,
            'evidence': 'SYNTHETIC report: runs/export-1/results.json; selected-filter assertion observed',
            'checked_at': '2026-11-03T00:00:00Z' if result == 'PASSED' else '',
            'exit_status': '0' if result == 'PASSED' else ''}
        data.update(changes)
        return data

    def record(self, data, root=None):
        root = root or self.root
        prepared = preview(root, 'gate', data)
        apply(*prepared, prepared[-1])
        check(root, quiet=True)

    def results(self, root=None, target=None):
        return assess(root or self.root, 'post-merge', self.subject, target or self.target)

    def optional(self, gate):
        path = self.root / 'verification.md'
        lines = path.read_text(encoding='utf-8').splitlines()
        for index, line in enumerate(lines):
            if line.startswith('| ' + gate + ' |'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[4] = 'no'  # Explicit synthetic user choice, not inferred from a failed check.
                lines[index] = '| ' + ' | '.join(cells) + ' |'
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_generic_smoke_does_not_satisfy_required_mapped_feature(self):
        self.record(self.observation('G3', evidence='SYNTHETIC health/login observation only; feature tracked in A2'))
        self.assertEqual(self.results(), ['A2 is NOT RUN'])
        self.record(self.observation('A2', 'BLOCKED', evidence='Required export needs approved production actor; unavailable'))
        self.assertEqual(self.results(), ['A2 is BLOCKED'])
        self.record(self.observation('A2', 'FAILED', evidence='SYNTHETIC export omitted selected filter', exit_status='1',
                                     checked_at='2026-11-03T00:01:00Z'))
        self.assertEqual(self.results(), ['A2 is FAILED'])
        self.assertEqual(gate_rows((self.root / 'verification.md').read_text())['G3']['result'], 'PASSED')

    def test_observation_preview_is_write_free_then_exact_feature_record_can_satisfy(self):
        self.record(self.observation('G3'))
        path = self.root / 'verification.md'
        before = path.read_bytes()
        manifest = (self.root / 'manifest.json').read_bytes()
        prepared = preview(self.root, 'gate', self.observation('A2'))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.results(), ['A2 is NOT RUN'])
        apply(*prepared, prepared[-1])
        self.assertEqual(self.results(), [])
        self.assertEqual((self.root / 'manifest.json').read_bytes(), manifest)
        row = gate_rows(path.read_text())['A2']
        self.assertEqual((row['stage'], row['required'], row['revision'], row['target']),
                         ('post-merge', 'yes', self.subject, self.target))
        self.assertIn('runs/export-1/results.json', row['evidence'])

    def test_preview_target_and_old_subject_cannot_confirm_released_feature(self):
        self.record(self.observation('G3'))
        before = (self.root / 'verification.md').read_bytes()
        with self.assertRaisesRegex(ValueError, 'differs from configured target'):
            preview(self.root, 'gate', self.observation('A2', target='https://preview.example.invalid'))
        self.assertEqual((self.root / 'verification.md').read_bytes(), before)
        self.record(self.observation('A2', revision='synthetic-earlier-subject'))
        self.assertIn('A2 has stale or missing revision', self.results())

    def test_unapproved_required_write_remains_blocked_and_optional_choice_is_a_waiver(self):
        self.record(self.observation('G3'))
        self.record(self.observation('A2', 'BLOCKED', evidence='Awaiting production-write approval; fixture setup not performed'))
        self.assertEqual(self.results(), ['A2 is BLOCKED'])
        self.optional('A2')
        text = (self.root / 'verification.md').read_text()
        self.assertEqual(self.results(), [])
        self.assertEqual(waivers(text, 'post-merge'), ['A2 WAIVED (recorded BLOCKED)'])
        self.assertEqual(gate_rows(text)['A2']['result'], 'BLOCKED')

    def test_optional_smoke_does_not_make_required_feature_optional(self):
        self.optional('G3')
        self.assertEqual(self.results(), ['A2 is NOT RUN'])
        self.record(self.observation('A2'))
        text = (self.root / 'verification.md').read_text()
        self.assertEqual(self.results(), [])
        self.assertEqual(waivers(text, 'post-merge'), ['G3 WAIVED (recorded NOT RUN)'])

    def test_installed_artifact_feature_uses_its_actual_consumer_target(self):
        target = 'synthetic-package-v2'
        root = self.factory('artifact', target)
        self.record(self.observation('G3', target=target), root)
        self.assertEqual(self.results(root, target), ['A2 is NOT RUN'])
        self.record(self.observation('A2', target=target,
                                     evidence='SYNTHETIC installed consumer export assertion; runs/artifact-1/results.json'), root)
        self.assertEqual(self.results(root, target), [])
        self.assertEqual(self.results(root, 'synthetic-package-v1'),
                         ['Actual post-release target differs from the configured target'])

    def test_generated_handoff_connects_mapping_safety_and_actual_results(self):
        verify = phase_text_at(self.root,'verify')
        release = phase_text_at(self.root,'release')
        handoff = (self.root / 'release-handoff.md').read_text()
        for clause in ('actual changed paths, acceptance IDs', 'comparison base', 'test-map.json',
                       'prod-safe tag alone', 'installed-artifact or consumer check'):
            self.assertIn(clause, verify)
        for clause in ('generic G3 smoke alone does not confirm the feature', 'cleanup outcome and any residue',
                       'unique Playwright output/report directory', 'handoff prose alone is not a gate observation'):
            self.assertIn(clause, release)
        self.assertIn('Feature-specific subset actually collected/executed', handoff)
        self.assertIn('Excluded required scope and BLOCKED/NOT RUN reason or explicit optional waiver', handoff)


if __name__ == '__main__':
    unittest.main()
