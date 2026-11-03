"""Local synthetic repositories only; no real backups, hooks or links are used."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import backup_advisory as advisory


class BackupAdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/'project'
        self.root.mkdir()
        self.backup = self.root/'.factory-update-backups'
        self.backup.mkdir()
        self.git('-c', 'init.templateDir=', 'init', '-q', str(self.root))

    def git(self, *args):
        result = subprocess.run(['git', '-C', str(self.root), *args],
                                env=advisory.git_environment(), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result

    def inspect(self):
        return advisory.inspect_backup_directory(self.root, self.backup)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file()}

    def test_ignored_by_root_rule_and_info_exclude_for_both_containers(self):
        for name in advisory.BACKUP_NAMES:
            with self.subTest(name=name):
                backup = self.root/name
                backup.mkdir(exist_ok=True)
                (self.root/'.gitignore').write_text('/'+name+'/\n', encoding='utf-8')
                answer = advisory.inspect_backup_directory(self.root, backup)
                self.assertEqual(answer['status'], 'ignored')
                self.assertEqual(answer['scope'], 'project-local rules only')
        (self.root/'.gitignore').write_text('', encoding='utf-8')
        (self.root/'.git/info').mkdir(exist_ok=True)
        (self.root/'.git/info/exclude').write_text(self.backup.name+'/\n', encoding='utf-8')
        self.assertEqual(self.inspect()['status'], 'ignored')

    def test_unignored_and_negated_rules_warn_without_claiming_write_failure(self):
        for rules in ('', self.backup.name+'/\n!'+self.backup.name+'/\n'):
            with self.subTest(rules=rules):
                (self.root/'.gitignore').write_text(rules, encoding='utf-8')
                answer = self.inspect()
                self.assertEqual(answer['status'], 'unignored')
                self.assertIn('project-local', answer['message'])
                self.assertIn('does not change or determine the backup/write outcome', answer['message'])

    def test_tracked_descendant_wins_over_ignore_rule_without_reading_its_content(self):
        tracked = self.backup/'PRIVATE-file.txt'
        tracked.write_text('PRIVATE-CONTENT', encoding='utf-8')
        self.git('add', '--', tracked.relative_to(self.root).as_posix())
        (self.root/'.gitignore').write_text(self.backup.name+'/\n', encoding='utf-8')
        answer = self.inspect()
        self.assertEqual(answer['status'], 'tracked')
        self.assertNotIn('PRIVATE', str(answer))
        self.assertNotIn('ignored by project-local', answer['message'])

    def test_non_git_and_linked_worktree_are_unknown_without_git_execution(self):
        non_git = self.root/'another'
        non_git.mkdir()
        backup = non_git/self.backup.name
        backup.mkdir()
        with patch.object(advisory, 'bounded_run', side_effect=AssertionError('Git must not run')) as run:
            self.assertEqual(advisory.inspect_backup_directory(non_git, backup)['status'], 'unknown')
            (non_git/'.git').write_text('gitdir: PRIVATE-OUTSIDE', encoding='utf-8')
            answer = advisory.inspect_backup_directory(non_git, backup)
            self.assertEqual(answer['status'], 'unknown')
            self.assertNotIn('PRIVATE', str(answer))
            run.assert_not_called()

    def test_unsafe_wrong_or_missing_paths_are_unknown_before_git_execution(self):
        cases = ((self.root, self.root.parent/self.backup.name),
                 (self.root, self.root/'arbitrary'),
                 (self.root, self.backup/'nested'),
                 (self.root, self.root/'.factory-recovery-backups'),
                 (self.root/'..', self.root.parent/self.backup.name))
        with patch.object(advisory, 'bounded_run') as run:
            for root, backup in cases:
                with self.subTest(root=root, backup=backup):
                    self.assertEqual(advisory.inspect_backup_directory(root, backup)['status'], 'unknown')
            run.assert_not_called()
        with patch.object(advisory, 'safe_path', side_effect=ValueError('PRIVATE redirected path')), \
             patch.object(advisory, 'bounded_run') as run:
            answer = self.inspect()
            self.assertEqual(answer['status'], 'unknown')
            self.assertNotIn('PRIVATE', str(answer))
            run.assert_not_called()

    def test_timeout_runner_error_or_malformed_output_stays_unknown_and_sanitized(self):
        errors = (subprocess.TimeoutExpired('PRIVATE argv', 5),
                  OSError('PRIVATE error'), ValueError('PRIVATE output limit'), RuntimeError('PRIVATE failure'))
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(advisory, 'bounded_run', side_effect=error):
                answer = self.inspect()
                self.assertEqual(answer['status'], 'unknown')
                self.assertNotIn('PRIVATE', str(answer))
        for results in ([(128, b'')], [(0, b'bad-index-output')],
                        [(0, b'PRIVATE-unrelated\0')], [(0, b''), (128, b'')],
                        [(0, b''), (0, b'PRIVATE unexpected stdout')]):
            with self.subTest(results=results), patch.object(advisory, 'bounded_run', side_effect=results):
                self.assertEqual(self.inspect()['status'], 'unknown')

    def test_fixed_argv_environment_and_shared_deadline(self):
        injected = {'GIT_DIR': 'PRIVATE outside', 'GIT_CONFIG_COUNT': '1',
                    'GIT_TRACE': 'PRIVATE file', 'AWS_SECRET_ACCESS_KEY': 'PRIVATE secret'}
        with patch.dict(os.environ, injected), \
             patch.object(advisory, 'bounded_run', side_effect=[(0, b''), (1, b'')]) as run:
            self.assertEqual(self.inspect()['status'], 'unignored')
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            argv, env, limit = call.args
            for flag in ('--no-optional-locks', 'core.fsmonitor=false',
                         'core.hooksPath='+os.devnull, 'core.excludesFile='+os.devnull):
                self.assertIn(flag, argv)
            self.assertEqual(argv[-2:], ['--', self.backup.name])
            self.assertIn('--git-dir='+str(self.root/'.git'), argv)
            self.assertIn('--work-tree='+str(self.root), argv)
            self.assertTrue(set(injected).isdisjoint(env))
            self.assertEqual(env['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(env['GIT_CONFIG_GLOBAL'], os.devnull)
            self.assertEqual(limit, advisory.OUTPUT_LIMIT)
            self.assertLessEqual(call.kwargs['timeout'], advisory.TIME_LIMIT)
        self.assertIn('--cached', run.call_args_list[0].args[0])
        self.assertIn('--literal-pathspecs', run.call_args_list[0].args[0])
        self.assertIn('--quiet', run.call_args_list[1].args[0])
        self.assertNotIn('--literal-pathspecs', run.call_args_list[1].args[0])
        with patch.object(advisory.time, 'monotonic', side_effect=[0, 0, 6]), \
             patch.object(advisory, 'bounded_run', return_value=(0, b'')) as run:
            self.assertEqual(self.inspect()['status'], 'unknown')
            self.assertEqual(run.call_count, 1)

    def test_no_backup_scan_content_reads_or_repository_writes(self):
        (self.root/'.gitignore').write_text(self.backup.name+'/\n', encoding='utf-8')
        (self.backup/'PRIVATE-file.txt').write_text('PRIVATE-CONTENT', encoding='utf-8')
        (self.backup/'.gitignore').write_text('PRIVATE-BACKUP-POLICY', encoding='utf-8')
        before = self.snapshot()
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('No Python content reads')), \
             patch.object(Path, 'read_text', side_effect=AssertionError('No Python content reads')), \
             patch.object(Path, 'rglob', side_effect=AssertionError('No backup recursion')), \
             patch('os.scandir', side_effect=AssertionError('No backup scanning')):
            answer = self.inspect()
        self.assertEqual(answer['status'], 'ignored')
        self.assertNotIn('PRIVATE', str(answer))
        self.assertEqual(self.snapshot(), before)

    def test_repository_external_excludes_are_deliberately_not_used(self):
        outside = Path(self.tmp.name)/'global-ignore'
        outside.write_text(self.backup.name+'/\n', encoding='utf-8')
        self.git('config', 'core.excludesFile', str(outside))
        self.assertEqual(self.inspect()['status'], 'unignored')


if __name__ == '__main__':
    unittest.main()
