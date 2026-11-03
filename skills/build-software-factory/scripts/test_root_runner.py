"""Exercise the root test entry point using only isolated synthetic suites."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

RUNNER = Path(__file__).resolve().parents[3] / 'run_tests.py'


class RootRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'plugin'
        self.root.mkdir()
        shutil.copyfile(RUNNER, self.root / 'run_tests.py')
        self.suite = self.root / 'skills' / 'build-software-factory' / 'scripts'
        self.suite.mkdir(parents=True)
        self.other = Path(self.tmp.name) / 'other'
        self.other.mkdir()

    def invoke(self, cwd):
        return subprocess.run([sys.executable, str(self.root / 'run_tests.py')],
                              cwd=cwd, capture_output=True, text=True)

    def test_runs_from_checkout_and_another_directory(self):
        (self.suite / 'test_fixture.py').write_text(
            'import unittest\nclass Fixture(unittest.TestCase):\n'
            ' def test_pass(self): self.assertTrue(True)\n', encoding='utf-8')
        for cwd in (self.root, self.other):
            with self.subTest(cwd=cwd):
                result = self.invoke(cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('Ran 1 test', result.stderr)

    def test_failing_test_returns_failure(self):
        (self.suite / 'test_fixture.py').write_text(
            'import unittest\nclass Fixture(unittest.TestCase):\n'
            ' def test_fail(self): self.fail("synthetic failure")\n', encoding='utf-8')
        result = self.invoke(self.other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('synthetic failure', result.stderr)

    def test_empty_or_missing_suite_is_not_success(self):
        (self.suite / 'test_empty.py').write_text('# no tests\n', encoding='utf-8')
        result = self.invoke(self.other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no plugin tests were discovered', result.stderr)
        shutil.rmtree(self.suite)
        result = self.invoke(self.other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('could not discover plugin tests', result.stderr)

    def test_import_errors_are_failures(self):
        (self.suite / 'test_broken.py').write_text('raise RuntimeError("synthetic import failure")\n', encoding='utf-8')
        result = self.invoke(self.other)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('synthetic import failure', result.stderr)
