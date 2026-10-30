"""Offline guide/scaffold and record-semantics regressions; no scanner or model runs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows, problems, requirements, waivers
from integrity import check
from research import PHASES
from scaffold import ROOT, render


class InstallTrustSecretGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())

    def selected_check(self):
        self.research.update(status='complete', summary='SYNTHETIC schema fixture, not online research.')
        self.research['coverage'] = {
            p: {'status': 'applicable' if p == 'verify' else 'not_applicable',
                'reason': 'Synthetic task only assesses the fitted Verify procedure.'}
            for p in PHASES}
        self.research['sources'] = [{
            'id': 'S1', 'url': 'https://example.com/synthetic-check-contract',
            'accessed_on': '2026-10-29', 'kind': 'synthetic fixture',
            'version_scope': 'invented v1', 'observation': 'Invented project contract.',
            'status': 'read'}]
        self.research['practices'] = [{
            'id': 'P-fixtures', 'decision': 'selected', 'source_ids': ['S1'],
            'phases': ['verify'], 'relevance': 'Synthetic connection-check design.',
            'compatibility': 'Invented contract, no scanner implemented.',
            'tradeoff': 'Review context without host/path blanket exceptions.',
            'instruction': 'Classify scoped disposable fixtures and retain simulated-leak coverage.',
            'check': 'SYNTHETIC: unknown provenance blocks; mixed fixture/leak fails; docs/local-host simulated leaks fail.'}]

    def test_generated_launch_preflight_retains_distinct_source_trust_permission_boundaries(self):
        files = render(self.config, self.research)
        guide = ' '.join(files['launch-guide.md'].split())
        for clause in ('actual loaded plugin directory', 'scripts/gates.py',
                       'A version string alone is not proof', 'generated-factory migration are separate',
                       'normal interactive UI', 'absence does not prove',
                       'affected task BLOCKED', 'A denied action remains denied',
                       'exact trusted helper argv', '--setting-sources project'):
            self.assertIn(clause, guide)
        self.assertIn('launch-guide.md', files['.claude/skills/factory-intake/SKILL.md'])
        self.assertIn('launch-guide.md', files['.claude/skills/factory-build/SKILL.md'])
        self.assertNotIn('--bypass', guide)
        self.assertNotIn('--bg', guide)

    def test_current_gate_entrypoint_resolves_real_dependencies_without_running_checks(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts/gates.py'), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for flag in ('--factory', '--stage', '--revision', '--plan'):
            self.assertIn(flag, result.stdout)
        # Only parser/import availability is established, not a gate or application PASS.
        self.assertNotIn('RECORDED requirements satisfied:', result.stdout)

    def test_new_review_guide_is_a_contract_and_does_not_create_a_secret_gate(self):
        files = render(self.config, self.research)
        self.assertEqual(set(requirements(self.config, self.research)), {'G1', 'G2', 'G3', 'A1'})
        self.assertIn('connection-string-review.md', json.loads(files['manifest.json'])['contracts'])
        guide = ' '.join(files['connection-string-review.md'].split())
        for clause in ('no host/name wildcard', 'BLOCKED/unknown', 'documentation is not excluded',
                       'safe match cannot hide another candidate', 'fresh evidence before PASSED',
                       'waiver stays WAIVED', 'not a secret scanner'):
            self.assertIn(clause, guide)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body.encode('utf-8'))
            check(root, quiet=True)
            (root/'connection-string-review.md').write_text('Unreviewed blanket exemption.')
            with self.assertRaises(ValueError):
                check(root, quiet=True)

    def test_task_selected_secret_check_stays_not_run_then_failed_despite_fixture_text(self):
        self.selected_check()
        files = render(self.config, self.research)
        expected = requirements(self.config, self.research)
        self.assertEqual(expected['R1']['design'], self.research['practices'][0]['check'])
        text = files['verification.md']
        self.assertEqual(gate_rows(text)['R1']['result'], 'NOT RUN')
        rows = []
        for line in text.splitlines():
            if line.startswith('| R1 |'):
                cells = [v.strip() for v in line.strip('|').split('|')]
                cells[6] = 'FAILED'
                cells[7] = 'SYNTHETIC mixed fixture/leak; postgres://ci:ci@localhost:5432/fixture_db'
                line = '| '+' | '.join(cells)+' |'
            rows.append(line)
        text = '\n'.join(rows)
        self.assertIn('R1 is FAILED', problems(text, 'pre-merge', 'new-subject', expected))
        optional = text.replace('| R1 | pre-merge | '+expected['R1']['design']+' | unconfirmed | yes |',
                                '| R1 | pre-merge | '+expected['R1']['design']+' | unconfirmed | no |')
        self.assertEqual(waivers(optional, 'pre-merge'), ['R1 WAIVED (recorded FAILED)'])
        self.assertEqual(gate_rows(optional)['R1']['result'], 'FAILED')

    def test_revised_check_cannot_reuse_old_subject_observations(self):
        self.selected_check()
        files = render(self.config, self.research)
        expected = requirements(self.config, self.research)
        rows = []
        for line in files['verification.md'].splitlines():
            if line.startswith('| ') and line.split('|')[1].strip() in ('G1', 'G2', 'A1', 'R1'):
                cells = [v.strip() for v in line.strip('|').split('|')]
                cells[2] = 'SYNTHETIC recorded procedure; no actual scanner executed'
                cells[3] = 'disposable synthetic fixture'
                cells[5:] = ['old-subject', 'PASSED', 'SYNTHETIC observation only',
                             'fixture-artifact', '2026-10-30T04:00:00Z', 'manual']
                line = '| '+' | '.join(cells)+' |'
            rows.append(line)
        text = '\n'.join(rows)
        self.assertIn('R1 has stale or missing revision', problems(text, 'pre-merge', 'new-subject', expected))
        self.assertEqual(problems(text, 'pre-merge', 'new-subject', expected),
                         ['G1 has stale or missing revision', 'G2 has stale or missing revision',
                          'A1 has stale or missing revision', 'R1 has stale or missing revision'])


if __name__ == '__main__':
    unittest.main()
