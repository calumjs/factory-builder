"""Factory-root diagnostics through copied CLIs; no real links or junctions created."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from integrity import check
from scaffold import ROOT, render


class FactoryPathDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)/'repo'
        self.factory = self.repo/'.software-factory'
        config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name, body in render(config, research).items():
            path = self.factory/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))
        self.gates = self.factory/'dashboard/gates.py'

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob('*') if p.is_file()}

    def cli(self, script, *args, cwd=None):
        return subprocess.run([sys.executable, '-B', str(script), *args],
                              cwd=cwd or self.repo, capture_output=True, text=True)

    def test_copied_gate_reports_repository_root_and_observed_child_without_redirect(self):
        before = self.snapshot()
        result = self.cli(self.gates, '--factory', '.', '--plan')
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(json.dumps(str(self.repo)), result.stderr)
        self.assertIn(json.dumps(str(self.repo/'manifest.json')), result.stderr)
        self.assertIn(json.dumps(str(self.factory)), result.stderr)
        self.assertIn('explicitly with --factory', result.stderr)
        self.assertIn('has not been validated; no redirect occurred', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.snapshot(), before)

    def test_dot_is_valid_in_factory_and_explicit_child_is_valid_in_repository(self):
        before = self.snapshot()
        for cwd, selected in ((self.factory, '.'), (self.repo, '.software-factory')):
            with self.subTest(cwd=cwd):
                result = self.cli(self.gates, '--factory', selected, '--plan', cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('NOT RUN', result.stdout)
                self.assertNotIn('ERROR:', result.stderr)
        self.assertEqual(self.snapshot(), before)

    def test_scaffold_check_uses_same_diagnostic_and_accepts_factory_dot(self):
        result = self.cli(ROOT/'scripts/scaffold.py', '--check', '.')
        self.assertEqual(result.returncode, 1)
        self.assertIn('scaffold.py --check', result.stderr)
        result = self.cli(ROOT/'scripts/scaffold.py', '--check', '.', cwd=self.factory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('contract files match', result.stdout)

    def test_missing_file_or_directory_root_reports_expected_manifest_without_hint(self):
        file_root = self.repo/'ordinary.txt'
        file_root.write_text('PRIVATE CONTENT MUST NOT APPEAR', encoding='utf-8')
        empty_root = self.repo/'empty'
        empty_root.mkdir()
        for root in (self.repo/'absent', file_root, empty_root):
            with self.subTest(root=root):
                result = self.cli(self.gates, '--factory', str(root), '--plan')
                self.assertEqual(result.returncode, 2)
                self.assertIn(json.dumps(str(root/'manifest.json')), result.stderr)
                self.assertNotIn('A child manifest exists', result.stderr)
                self.assertNotIn('PRIVATE CONTENT', result.stderr)

    def test_directory_named_manifest_is_not_treated_as_a_manifest(self):
        (self.repo/'manifest.json').mkdir()
        with self.assertRaisesRegex(ValueError, 'does not contain a regular manifest file'):
            check(self.repo, quiet=True)

    def test_wrong_root_does_not_walk_repository_or_read_child_manifest(self):
        (self.factory/'manifest.json').write_text('PRIVATE INVALID MANIFEST', encoding='utf-8')
        with patch.object(Path, 'rglob', side_effect=AssertionError('Must not walk repository')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('Must not read candidate')):
            with self.assertRaisesRegex(ValueError, 'A child manifest exists') as raised:
                check(self.repo, quiet=True)
        self.assertNotIn('PRIVATE', str(raised.exception))

    def test_redirected_or_inaccessible_child_gets_no_hint(self):
        # Model the filesystem boundary without creating forbidden real links.
        for method in ('is_symlink', 'is_junction'):
            for redirected in (self.factory, self.factory/'manifest.json'):
                with self.subTest(method=method, redirected=redirected), \
                     patch.object(Path, method, lambda path: path == redirected, create=True):
                    with self.assertRaises(ValueError) as raised:
                        check(self.repo, quiet=True)
                    self.assertIn('Factory root', str(raised.exception))
                    self.assertNotIn('A child manifest exists', str(raised.exception))
        with patch.object(Path, 'is_file', side_effect=PermissionError('PRIVATE ERROR DETAIL')):
            from integrity import missing_manifest_diagnostic
            message = missing_manifest_diagnostic(self.repo)
        self.assertNotIn('A child manifest exists', message)
        self.assertNotIn('PRIVATE', message)

    def test_redirected_root_manifest_and_internal_paths_remain_rejected(self):
        for method in ('is_symlink', 'is_junction'):
            for redirected in (self.factory, self.factory/'manifest.json', self.factory/'config.json'):
                with self.subTest(method=method, redirected=redirected), \
                     patch.object(Path, method, lambda path: path == redirected, create=True):
                    with self.assertRaisesRegex(ValueError, 'Redirected') as raised:
                        check(self.factory, quiet=True)
                    message = str(raised.exception)
                    # Internal path diagnostics escape paths; safe_path's existing
                    # root/ancestor diagnostic retains its original representation.
                    self.assertTrue(str(redirected) in message or json.dumps(str(redirected)) in message)


if __name__ == '__main__':
    unittest.main()
