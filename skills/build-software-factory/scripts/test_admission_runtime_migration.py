"""Reviewed copied-runtime adoption with synthetic policy and preserved evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows, policy_controls
from integrity import check, digest
from operations import controls
from scaffold import ROOT, render
from update_operations import PRE_ADMISSION_RUNTIME, apply, prepare


class AdmissionRuntimeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.factory = self.base / 'factory'
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['operations'] = {
            'autonomy': {'mode': 'bounded', 'allowed_submitters': ['synthetic-author'], 'max_items_per_hour': 4},
            'issue_intake': {'mode': 'continuous', 'status': 'enabled', 'github_scope': 'SYNTHETIC/example'}}
        self.policy = {
            'version': 1, 'status': 'specified', 'repository': 'SYNTHETIC/example',
            'identity': {'kind': 'legacy_submitters'},
            'starts': {'maximum': 3, 'window': 'calendar_day', 'timezone': 'UTC'},
            'max_in_flight_items': 1, 'completion': 'draft_pr',
            'costs': {'currency': 'USD', 'max_per_item': '1.00',
                      'period': {'maximum': '3.00', 'window': 'calendar_month', 'timezone': 'UTC'}},
            'snapshot_max_age_seconds': 300}
        self.patch = {'admission': self.policy}
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.write_factory()
        self.prior = {}
        for filename, expected in PRE_ADMISSION_RUNTIME.items():
            data = (ROOT / 'scripts/fixtures' / ('pre_admission_' + filename[:-3] + '.txt')).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)
            self.assertEqual(digest(data), expected)
            self.prior['dashboard/' + filename] = data
        self.replace_helpers(self.prior)

    def write_factory(self):
        for name, body in render(self.config, self.research).items():
            path = self.factory / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def replace_helpers(self, helpers):
        """Construct explicit synthetic fixtures, never repair a real manifest."""
        manifest_path = self.factory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for name, data in helpers.items():
            path = self.factory / name
            if data is None:
                path.unlink(); manifest['contracts'].pop(name)
            else:
                path.write_bytes(data); manifest['contracts'][name] = digest(data)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

    def current_helpers(self):
        return {name: (ROOT / 'scripts' / Path(name).name).read_bytes() for name in self.prior}

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix(): p.read_bytes()
                for p in self.factory.rglob('*') if p.is_file()}

    def assert_refused(self, changes, **flags):
        before = self.snapshot()
        with self.assertRaises(ValueError): prepare(self.factory, changes, **flags)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.base / '.factory-update-backups').exists())

    def test_unrelated_updates_keep_exact_legacy_helpers(self):
        before = self.snapshot()
        self.assertFalse(prepare(self.factory, {})[2])
        root, old, new, plan = prepare(self.factory, {'review': {'required_approvals': 2}})
        self.assertFalse(any(name.startswith('dashboard/') for name in new))
        apply(root, old, new, plan, plan)
        for name in self.prior: self.assertEqual((root / name).read_bytes(), before[name])

    def test_runtime_only_context_migration_preserves_config_policy_and_evidence_bytes(self):
        before = self.snapshot()
        root, old, new, plan = prepare(self.factory, {}, context_runtime=True)
        self.assertEqual(set(new), set(self.prior) | {'manifest.json'})
        self.assertEqual(self.snapshot(), before)
        backup = apply(root, old, new, plan, plan)
        for name, data in before.items():
            if name not in new: self.assertEqual((root / name).read_bytes(), data)
        for name, data in self.prior.items(): self.assertEqual((backup / name).read_bytes(), data)
        check(root, quiet=True)

    def test_normalized_known_helpers_back_up_their_actual_original_bytes(self):
        crlf = {name: data.replace(b'\n', b'\r\n') for name, data in self.prior.items()}
        self.replace_helpers(crlf)
        root, old, new, plan = prepare(self.factory, self.patch, context_runtime=True)
        backup = apply(root, old, new, plan, plan)
        for name, data in crlf.items():
            self.assertEqual(old[name], data)
            self.assertEqual((backup / name).read_bytes(), data)
            self.assertEqual((root / name).read_bytes(), self.current_helpers()[name])

    def test_admission_requires_review_of_both_old_consumers(self):
        for flags in ({}, {'gate_runtime': True}, {'recipe_runtime': True}):
            with self.subTest(flags=flags): self.assert_refused(self.patch, **flags)

    def test_draft_policy_also_requires_supported_copied_metadata(self):
        draft = {key: None for key in self.policy}
        draft.update(version=1, status='draft')
        self.assert_refused({'admission': draft})
        self.assertTrue(prepare(self.factory, {'admission': draft}, context_runtime=True)[2])

    def test_mixed_generation_pairs_cannot_hide_missing_support(self):
        current = self.current_helpers()
        self.replace_helpers({'dashboard/operations.py': current['dashboard/operations.py']})
        self.assert_refused(self.patch, gate_runtime=True)
        self.assertTrue(prepare(self.factory, self.patch, context_runtime=True)[2])
        self.replace_helpers(self.prior)
        self.replace_helpers({'dashboard/readiness.py': current['dashboard/readiness.py']})
        self.assert_refused(self.patch)
        _, _, new, _ = prepare(self.factory, self.patch, gate_runtime=True)
        self.assertIn('dashboard/operations.py', new)
        self.assertNotIn('dashboard/readiness.py', new)

    def test_supported_bundle_needs_no_redundant_migration_flag(self):
        self.replace_helpers(self.current_helpers())
        root, old, new, plan = prepare(self.factory, self.patch)
        self.assertEqual(set(new), {'config.json', 'policy.md', 'manifest.json'})
        self.assertTrue(set(self.prior) <= set(old))
        apply(root, old, new, plan, plan)
        check(root, quiet=True)

    def test_existing_admission_policy_is_checked_even_without_an_admission_patch(self):
        self.config['operations'].update(copy.deepcopy(self.patch))
        self.write_factory(); self.replace_helpers(self.prior)
        self.assert_refused({})
        self.assert_refused({'review': {'required_approvals': 2}})
        _, _, new, _ = prepare(self.factory, {}, context_runtime=True)
        self.assertEqual(set(new), set(self.prior) | {'manifest.json'})

    def test_admission_drift_between_config_and_policy_is_refused(self):
        config = copy.deepcopy(self.config)
        config['operations'].update(copy.deepcopy(self.patch))
        self.replace_helpers({'config.json': json.dumps(config).encode('utf-8')})
        self.assert_refused({}, context_runtime=True)

    def test_custom_helpers_are_never_replaced(self):
        for name, data in self.prior.items():
            with self.subTest(helper=name):
                self.replace_helpers({name: data + b'\n# Synthetic project customization\n'})
                self.assert_refused(self.patch)
                self.assert_refused(self.patch, context_runtime=True, gate_runtime=True)
                self.replace_helpers({name: data})

    def test_missing_consumers_fail_without_an_explicit_supported_proposal(self):
        for name, data in self.prior.items():
            with self.subTest(helper=name):
                self.replace_helpers({name: None})
                self.assert_refused(self.patch)
                self.replace_helpers({name: data})

    def test_unchanged_supported_helpers_are_bound_against_concurrent_byte_edits(self):
        current = self.current_helpers(); self.replace_helpers(current)
        for name, data in current.items():
            with self.subTest(helper=name):
                root, old, new, plan = prepare(self.factory, self.patch)
                self.assertEqual(old[name], data)
                self.assertNotIn(name, new)
                # Same normalized digest, so integrity alone cannot detect this edit.
                (root / name).write_bytes(b'\xef\xbb\xbf' + data)
                check(root, quiet=True)
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'changed after preview'):
                    apply(root, old, new, plan, plan)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.base / '.factory-update-backups').exists())
                (root / name).write_bytes(data)

    def test_context_migration_synchronizes_policy_keeps_waivers_and_runs_copied_consumers(self):
        verification = self.factory / 'verification.md'
        lines = verification.read_text(encoding='utf-8').splitlines()
        for index, line in enumerate(lines):
            if line.startswith('| G2 |'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[4:11] = ['no', 'a'*40, 'FAILED', 'synthetic failure retained',
                               'local-fixture', '2026-11-03T00:00:00Z', '1']
                lines[index] = '| ' + ' | '.join(cells) + ' |'
        verification.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        before = self.snapshot()
        root, old, new, plan = prepare(self.factory, self.patch, context_runtime=True, migration_receipt=True)
        expected = set(self.prior) | {'config.json', 'policy.md', 'manifest.json', 'migration-receipts.json'}
        self.assertEqual(set(new), expected)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ValueError): apply(root, old, new, plan, 'wrong')
        self.assertEqual(self.snapshot(), before)
        backup = apply(root, old, new, plan, plan)
        for name, data in before.items():
            if name not in new: self.assertEqual((root / name).read_bytes(), data)
            else: self.assertEqual((backup / name).read_bytes(), data)
        config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['operations']['admission'], self.policy)
        self.assertEqual(policy_controls((root / 'policy.md').read_text(encoding='utf-8')), controls(config))
        self.assertEqual(gate_rows(verification.read_text(encoding='utf-8'))['G2']['result'], 'FAILED')
        old_manifest = json.loads(before['manifest.json'])['contracts']
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))['contracts']
        self.assertEqual({name for name in manifest if manifest[name] != old_manifest.get(name)}, expected - {'manifest.json'})
        args = ['--factory', str(root), '--stage', 'pre-merge', '--revision', 'a'*40]
        results = [subprocess.run([sys.executable, '-B', str(path), *args], capture_output=True, text=True)
                   for path in (ROOT / 'scripts/gates.py', root / 'dashboard/gates.py')]
        self.assertEqual((results[0].returncode, results[0].stdout, results[0].stderr),
                         (results[1].returncode, results[1].stdout, results[1].stderr))
        self.assertEqual(results[1].returncode, 1)
        self.assertIn('WAIVED', results[1].stdout)
        output = self.base / 'overview.json'
        result = subprocess.run([sys.executable, '-B', str(root / 'dashboard/dashboard.py'),
                                 '--output', str(output), '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(output.read_text(encoding='utf-8'))
        self.assertTrue(any('Admission policy' in notice for notice in summary['context']['watcher']['diagnostics']))
        row = next(row for row in summary['gates'] if row['id'] == 'G2')
        self.assertEqual((row['state'], row['recorded_result']), ('WAIVED', 'FAILED'))
        self.assertFalse((root / 'dashboard/admission_review.py').exists())
        self.assertFalse((root / 'dashboard/__pycache__').exists())
        check(root, quiet=True)


if __name__ == '__main__': unittest.main()
