"""Offline mapping preflight fixtures; no GitHub or application checks are run."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from change_contract import assess
from scaffold import ROOT, render


class ChangeContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '.software-factory'
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        config['acceptance'].append(copy.deepcopy(config['acceptance'][0]))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.files = render(config, research)
        for name, body in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')
        self.subject = 'a' * 40
        self.contract = {'version': 1, 'subject': self.subject, 'classification': 'feature',
                         'rationale': 'Reviewed change uses an existing product criterion.',
                         'issues': [{'reference': 'fixture#12', 'tasks': ['T1'], 'acceptance': ['A1']}]}

    def tearDown(self):
        self.temp.cleanup()

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def plan(self, value):
        (self.root / 'task-plan.json').write_text(json.dumps(value), encoding='utf-8')

    def test_reused_criterion_and_unfinished_task_map_without_passing_evidence(self):
        before = self.snapshot()
        result = assess(self.root, self.contract, self.subject)
        self.assertEqual(result['assessment'], 'MAPPED FOR REVIEW')
        self.assertEqual(result['mappings'][0]['acceptance']['A1'], json.loads(self.files['config.json'])['acceptance'][0])
        self.assertEqual(result['mappings'][0]['tasks'][0]['id'], 'T1')
        self.assertIn('No tests ran', result['notice'])
        self.assertEqual(before, self.snapshot())
        self.assertIn('NOT RUN', (self.root / 'verification.md').read_text())

    def test_invalid_schema_and_missing_links_refused(self):
        variants = [dict(self.contract, version=True), dict(self.contract, version=2),
                    dict(self.contract, issues=[]), dict(self.contract, rationale=''),
                    dict(self.contract, classification='docs-only'), dict(self.contract, extra='x')]
        for field, value in [('tasks', []), ('acceptance', []), ('tasks', ['T999']),
                             ('acceptance', ['G1']), ('acceptance', ['A1', 'A1']), ('tasks', ['T1', 'T1'])]:
            item = copy.deepcopy(self.contract)
            item['issues'][0][field] = value
            variants.append(item)
        duplicate = copy.deepcopy(self.contract)
        duplicate['issues'] *= 2
        variants.append(duplicate)
        for item in variants:
            with self.subTest(item=item), self.assertRaises(ValueError):
                assess(self.root, item, self.subject)

    def test_subject_mismatch_short_or_nonhex_are_refused(self):
        for subject in ('abc1234', 'x' * 40, 'b' * 40, ''):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                assess(self.root, self.contract, subject)

    def test_maintenance_stays_explicit_and_does_not_claim_coverage(self):
        item = dict(self.contract, classification='maintenance', issues=[])
        self.assertEqual(assess(self.root, item, self.subject)['assessment'], 'MAINTENANCE CLAIM FOR REVIEW')
        with self.assertRaises(ValueError):
            assess(self.root, dict(item, rationale=' '), self.subject)

    def test_each_issue_requires_its_own_task_links(self):
        plan = json.loads(self.files['task-plan.json'])
        # A2 exists in the synthetic project; tasks are living records.
        self.assertGreaterEqual(len(json.loads(self.files['config.json'])['acceptance']), 2)
        plan['tasks'][0]['acceptance_ids'] = ['A1']
        plan['tasks'].append({**plan['tasks'][0], 'id': 'T2', 'acceptance_ids': ['A2']})
        self.plan(plan)
        item = copy.deepcopy(self.contract)
        item['issues'].append({'reference': 'fixture#13', 'tasks': ['T2'], 'acceptance': ['A1', 'A2']})
        with self.assertRaisesRegex(ValueError, 'lacks a task'):
            assess(self.root, item, self.subject)
        item['issues'][1]['acceptance'] = ['A2']
        self.assertEqual(len(assess(self.root, item, self.subject)['mappings']), 2)
        item['issues'][0]['tasks'].append('T2')
        with self.assertRaisesRegex(ValueError, 'does not cover'):
            assess(self.root, item, self.subject)

    def test_shared_ids_across_issues_are_valid_but_mutable_definitions_change_digest(self):
        item = copy.deepcopy(self.contract)
        item['issues'].append({**item['issues'][0], 'reference': 'fixture#13'})
        first = assess(self.root, item, self.subject)
        plan = json.loads(self.files['task-plan.json'])
        plan['tasks'][0]['goal'] = 'A changed task requires renewed mapping review'
        self.plan(plan)
        self.assertNotEqual(first['mapping_digest'], assess(self.root, item, self.subject)['mapping_digest'])

    def test_contract_drift_refuses(self):
        path = self.root / 'config.json'
        path.write_text(path.read_text() + ' ', encoding='utf-8')
        with self.assertRaises(ValueError):
            assess(self.root, self.contract, self.subject)

    def test_concurrent_living_edit_refuses(self):
        from change_contract import load
        def changed(root):
            result = load(root)
            path = root / 'task-plan.json'
            path.write_text(path.read_text() + '\n', encoding='utf-8')
            return result
        with patch('change_contract.load', side_effect=changed), self.assertRaisesRegex(ValueError, 'changed during'):
            assess(self.root, self.contract, self.subject)

    def test_cli_readonly_errors_and_duplicate_json(self):
        source = Path(self.temp.name) / 'change.json'
        source.write_text(json.dumps(self.contract), encoding='utf-8')
        command = [sys.executable, str(ROOT / 'scripts/change_contract.py'), '--factory', str(self.root),
                   '--input', str(source), '--revision', self.subject]
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['assessment'], 'MAPPED FOR REVIEW')
        source.write_text(json.dumps(self.contract)[:-1] + ', "issues": []}', encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Duplicate JSON object key', result.stderr)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
