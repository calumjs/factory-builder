"""Exercise CI path diagnostics against disposable Git repositories, without services."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scaffold import ROOT, render


class CIPathDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'project'
        self.repo.mkdir()
        self.factory_path = '.software-factory'
        self.factory = self.repo / self.factory_path
        self.hooks = self.repo / '.empty-hooks'
        self.hooks.mkdir()
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        for name, body in render(config, research).items():
            path = self.factory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))
        self.git('init', '-q')
        self.subject = self.commit()

    def git(self, *args):
        result = subprocess.run([
            'git', '--no-optional-locks', '-c', 'core.autocrlf=false',
            '-c', 'core.hooksPath=' + str(self.hooks), '-c', 'user.name=Synthetic CI fixture',
            '-c', 'user.email=fixture@example.invalid', '-C', str(self.repo), *args],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit(self):
        self.git('add', '--all')
        self.git('commit', '-qm', 'Synthetic offline path fixture')
        return self.git('rev-parse', 'HEAD')

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob('*') if p.is_file()}

    def assess(self, storage, factory=None, extra=()):
        before = self.snapshot()
        result = subprocess.run([
            sys.executable, '-B', str(ROOT / 'scripts/ci_evidence.py'),
            '--repo', str(self.repo), '--factory', factory or self.factory_path,
            '--subject', self.subject, '--storage', storage, '--stage', 'pre-merge', *extra],
            cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(self.snapshot(), before, 'Assessment must not mutate working files or Git metadata')
        payload = json.loads(result.stderr if result.returncode == 2 else result.stdout)
        return result.returncode, payload

    def evidence_commit(self):
        with (self.factory / 'release-handoff.md').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write('\nSYNTHETIC record update only; no application result.\n')
        return self.commit()

    def test_repo_prefixed_factory_reports_path_mismatch_before_allowed_record_error(self):
        storage = self.evidence_commit()
        code, payload = self.assess(storage, 'project/.software-factory')
        self.assertEqual(code, 2)
        message = payload['error']
        self.assertIn('No committed factory directory', message)
        self.assertIn('relative to the --repo checkout root', message)
        self.assertIn('not project/.software-factory', message)
        self.assertNotIn('Not an allowed evidence-only change', message)
        self.assertIn('<factory>/task-plan.json', message)
        self.assertIn('docs/factory-evidence/' + self.subject + '/', message)
        # Correcting only the input path reaches the unchanged gate assessment.
        code, payload = self.assess(storage)
        self.assertEqual(code, 1)
        self.assertEqual(payload['assessment'], 'blocked')
        self.assertEqual(payload['changed_evidence_files'], 1)

    def test_nested_factory_even_with_repository_name_prefix_is_not_rewritten(self):
        nested = 'project/apps/crm/.software-factory'
        destination = self.repo / nested
        destination.parent.mkdir(parents=True)
        self.factory.rename(destination)
        self.factory_path, self.factory = nested, destination
        self.subject = self.commit()
        storage = self.evidence_commit()
        code, payload = self.assess(storage)
        self.assertEqual(code, 1)
        self.assertEqual(payload['assessment'], 'blocked')
        self.assertEqual(payload['tested_subject'], self.subject)
        self.assertEqual(payload['evidence_storage_revision'], storage)
        self.assertEqual(payload['changed_evidence_files'], 1)

    def test_noncanonical_factory_is_rejected_with_flag_specific_help(self):
        for factory in ('../.software-factory', str(self.factory), './.software-factory'):
            with self.subTest(factory=factory):
                code, payload = self.assess(self.subject, factory)
                self.assertEqual(code, 2)
                self.assertIn('--factory is a canonical path relative to the --repo', payload['error'])

    def test_committed_file_is_not_accepted_as_factory_directory(self):
        code, payload = self.assess(self.subject, '.software-factory/manifest.json')
        self.assertEqual(code, 2)
        self.assertIn('No committed factory directory', payload['error'])
        self.assertIn('relative to the --repo checkout root', payload['error'])

    def test_disallowed_cumulative_change_lists_precise_envelope_without_contents(self):
        (self.repo / 'DOGFOOD-NOTES.md').write_text('PRIVATE_SENTINEL_MUST_NOT_BE_PRINTED', encoding='utf-8')
        notes_commit = self.commit()
        storage = self.evidence_commit()
        self.assertNotEqual(notes_commit, storage)
        code, payload = self.assess(storage, extra=('--evidence-dir', 'reviewed/logs'))
        self.assertEqual(code, 2)
        message = payload['error']
        self.assertIn('DOGFOOD-NOTES.md', message)
        for name in ('verification.md', 'task-plan.json', 'release-handoff.md', 'learning-log.md'):
            self.assertIn('.software-factory/' + name, message)
        self.assertIn('reviewed/logs/' + self.subject + '/', message)
        self.assertIn('modifications to existing', message)
        self.assertIn('additions of non-executable regular data files', message)
        self.assertIn('No deletions, renames or modifications of prior data files', message)
        self.assertNotIn('PRIVATE_SENTINEL', message)

    def test_valid_path_still_rejects_wrong_or_missing_contract_hash(self):
        manifest = self.factory / 'manifest.json'
        original = json.loads(manifest.read_text(encoding='utf-8'))
        for missing in (False, True):
            with self.subTest(missing=missing):
                changed = json.loads(json.dumps(original))
                if missing:
                    changed['contracts'].pop('config.json')
                else:
                    changed['contracts']['config.json'] = '0' * 64
                manifest.write_text(json.dumps(changed), encoding='utf-8')
                self.subject = self.commit()
                code, payload = self.assess(self.subject)
                self.assertEqual(code, 2)
                self.assertIn('Manifest file set mismatch' if missing else 'Contract integrity mismatch', payload['error'])

    def test_path_diagnostics_do_not_relax_clean_storage_or_commit_identity(self):
        storage = self.evidence_commit()
        for sha in ('HEAD', self.subject):
            with self.subTest(storage=sha):
                code, payload = self.assess(sha)
                self.assertEqual(code, 2)
                self.assertIn('explicit full commit SHAs' if sha == 'HEAD' else 'HEAD must be', payload['error'])
        (self.repo / 'untracked.txt').write_text('SYNTHETIC untracked evidence', encoding='utf-8')
        code, payload = self.assess(storage)
        self.assertEqual(code, 2)
        self.assertIn('stable clean checkout', payload['error'])

    def test_help_explains_relative_paths_and_full_commit_inputs(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/ci_evidence.py'), '--help'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        help_text = ' '.join(result.stdout.split())
        self.assertIn('relative to the --repo checkout root', help_text)
        self.assertIn('40 or 64 hex digits', help_text)
        self.assertIn('no aliases such as HEAD', help_text)


if __name__ == '__main__':
    unittest.main()
