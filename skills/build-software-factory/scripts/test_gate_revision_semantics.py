"""Public CLI contract: a subject labels current records, never selects a checkout."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scaffold import ROOT, render


class GateRevisionSemanticsTests(unittest.TestCase):
    SUBJECT = '1234567890abcdef1234567890abcdef12345678'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.factory = self.repo/'.software-factory'
        config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files = render(config, research)
        rows = []
        for line in files['verification.md'].splitlines():
            if any(line.startswith('| '+gate+' |') for gate in ('G1', 'G2', 'A1')):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[2:4] = ['Synthetic observation, no application executed', 'isolated fixture']
                cells[5:] = [self.SUBJECT, 'PASSED', 'SYNTHETIC evidence fixture',
                             'fixture-artifact', '2026-11-03T00:00:00+00:00', '0']
                line = '| '+' | '.join(cells)+' |'
            rows.append(line)
        files['verification.md'] = '\n'.join(rows)+'\n'
        for name, body in files.items():
            path = self.factory/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))
        self.copied_cli = self.factory/'dashboard/gates.py'

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob('*') if p.is_file()}

    def invoke(self, revision=None, script=None, help_only=False):
        command = [sys.executable, '-B', str(script or self.copied_cli)]
        command += ['--help'] if help_only else [
            '--factory', str(self.factory), '--stage', 'pre-merge',
            '--revision', revision or self.SUBJECT]
        before = self.snapshot()
        result = subprocess.run(command, cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(self.snapshot(), before, 'Gate CLI must not modify selected files')
        return result

    def test_source_and_copied_help_explain_current_files_and_exact_subject(self):
        for script in (ROOT/'scripts/gates.py', self.copied_cli):
            with self.subTest(script=script):
                result = self.invoke(script=script, help_only=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                help_text = ' '.join(result.stdout.split())
                self.assertIn('current on-disk files', help_text)
                self.assertIn('untracked or ignored by Git', help_text)
                self.assertIn('does not select or reconstruct a Git checkout', help_text)
                self.assertIn('no short/full SHA equivalence', help_text)

    def test_full_subject_matches_literal_records_without_git_resolution(self):
        self.assertFalse((self.repo/'.git').exists())
        self.assertEqual(self.invoke().returncode, 0)
        for wrong_subject in (self.SUBJECT[:7], 'abcdef1234567890abcdef1234567890abcdef12'):
            with self.subTest(subject=wrong_subject):
                result = self.invoke(wrong_subject)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('stale or missing revision', result.stdout)

    def test_same_subject_reads_current_living_records_without_reconstructing_them(self):
        self.assertEqual(self.invoke().returncode, 0)
        path = self.factory/'verification.md'
        path.write_text(path.read_text(encoding='utf-8').replace('| PASSED |', '| FAILED |'), encoding='utf-8')
        result = self.invoke()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('is FAILED', result.stdout)

    def test_unregistered_files_and_modified_contracts_are_not_ignored(self):
        # This factory need not be a Git checkout: integrity checks the full
        # supplied directory independently of any tracking or ignore metadata.
        (self.repo/'.gitignore').write_text('.software-factory/runtime/\n', encoding='utf-8')
        extra = self.factory/'runtime/local-note.txt'
        extra.parent.mkdir()
        extra.write_text('PRIVATE CONTENT MUST NOT BE PRINTED', encoding='utf-8')
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn('runtime/local-note.txt', result.stderr)
        self.assertNotIn('PRIVATE CONTENT', result.stderr)
        extra.unlink()
        self.assertEqual(self.invoke().returncode, 0)
        (self.factory/'policy.md').write_text('Changed contract', encoding='utf-8')
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn('Contract integrity mismatch: policy.md', result.stderr)


if __name__ == '__main__':
    unittest.main()
