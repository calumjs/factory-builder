"""Release comparison through disposable local Git objects; no service access."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import release_identity as release


class ReleaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / 'repo'
        self.repo.mkdir()
        self.hooks = Path(self.tmp.name) / 'empty-hooks'
        self.hooks.mkdir()
        self.git('init', '-q')
        self.plugin = self.repo / release.MANIFEST
        self.plugin.parent.mkdir()
        self.write_manifest()
        (self.repo / 'skill.md').write_text('Synthetic original content\n', encoding='utf-8')
        self.base = self.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args, input=None):
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='')
        result = subprocess.run(['git', '-c', 'core.autocrlf=false',
                                 '-c', 'core.hooksPath=' + str(self.hooks),
                                 '-c', 'user.name=Synthetic release fixture',
                                 '-c', 'user.email=fixture@example.invalid',
                                 '-c', 'commit.gpgsign=false', '-C', str(self.repo), *args],
                                input=input, capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def write_manifest(self, version='1.10.0', name='software-factory'):
        self.plugin.write_text(json.dumps({'name': name, 'version': version}), encoding='utf-8')

    def commit(self, stage=True):
        if stage:
            self.git('add', '--all')
        self.git('commit', '-qm', 'Synthetic fixture', '--allow-empty')
        return self.git('rev-parse', 'HEAD')

    def cli(self, base=None, candidate=None):
        result = subprocess.run([sys.executable, '-B', str(Path(release.__file__)),
                                 '--repo', str(self.repo), '--base=' + (base or self.base),
                                 '--candidate=' + (candidate or self.base)], capture_output=True, text=True)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob('*') if p.is_file()}

    def test_same_commit_and_different_commits_with_identical_trees_pass(self):
        for candidate in (self.base, self.commit()):
            code, result = self.cli(candidate=candidate)
            self.assertEqual(code, 0)
            self.assertEqual(result['assessment'], 'passed')
            self.assertEqual(result['changed_files'], 0)
            self.assertFalse(result['version_advanced'])

    def test_changed_content_same_version_blocks_with_actionable_message(self):
        (self.repo / 'skill.md').write_text('Synthetic new content\n', encoding='utf-8')
        code, result = self.cli(candidate=self.commit())
        self.assertEqual(code, 1)
        self.assertEqual(result['assessment'], 'blocked')
        self.assertEqual(result['changed_path_sample'], ['skill.md'])
        self.assertIn('reviewed version bump', result['diagnostic'])

    def test_numeric_version_advance_and_renamed_two_point_zero_candidate_pass(self):
        for version, name in (('1.10.1', 'software-factory'), ('1.11.0', 'software-factory'), ('2.0.0', 'factory-builder')):
            with self.subTest(version=version):
                self.write_manifest(version, name)
                candidate = self.commit()
                code, result = self.cli(candidate=candidate)
                self.assertEqual(code, 0)
                self.assertTrue(result['version_advanced'])
                self.assertEqual(result['candidate_plugin'], {'name': name, 'version': version})

    def test_downgrade_is_not_an_advance(self):
        self.write_manifest('1.9.99')
        code, result = self.cli(candidate=self.commit())
        self.assertEqual(code, 1)
        self.assertFalse(result['version_advanced'])

    def test_index_dirty_worktree_and_untracked_files_are_ignored_without_writes(self):
        self.write_manifest('2.0.0')
        candidate = self.commit()
        self.plugin.write_text('not even JSON in the worktree', encoding='utf-8')
        self.git('add', '--all')
        (self.repo / 'untracked.txt').write_text('Private synthetic scratch', encoding='utf-8')
        before = self.snapshot()
        code, result = self.cli(candidate=candidate)
        self.assertEqual(code, 0)
        self.assertEqual(result['candidate_plugin']['version'], '2.0.0')
        self.assertEqual(before, self.snapshot())

    def test_error_and_blocked_outcomes_leave_repository_unchanged(self):
        (self.repo / 'skill.md').write_text('changed', encoding='utf-8')
        candidate = self.commit()
        for base, expected in ((self.base, 1), ('0' * 40, 2)):
            before = self.snapshot()
            code, _ = self.cli(base=base, candidate=candidate)
            self.assertEqual(code, expected)
            self.assertEqual(before, self.snapshot())

    def test_add_delete_and_mode_changes_count_as_content(self):
        (self.repo / 'added.txt').write_text('added', encoding='utf-8')
        (self.repo / 'skill.md').unlink()
        candidate = self.commit()
        result = release.compare(self.repo, self.base, candidate)
        self.assertEqual(result['assessment'], 'blocked')
        self.assertEqual(result['changed_path_sample'], ['added.txt', 'skill.md'])
        self.git('update-index', '--chmod=+x', 'added.txt')
        changed_mode = self.commit(stage=False)
        result = release.compare(self.repo, candidate, changed_mode)
        self.assertEqual(result['assessment'], 'blocked')
        self.assertEqual(result['changed_path_sample'], ['added.txt'])

    def test_missing_and_malformed_manifest_and_metadata_are_errors(self):
        bodies = [None, '{', '[]', '{"name":"x","version":"1.10.0","version":"2.0.0"}',
                  '{"name":"x","version":"1.10.0","extra":NaN}',
                  '{"name":"x","version":"1.10.0","extra":{"a":1,"a":2}}',
                  '{"name":null,"version":"1.10.0"}',
                  '{"name":" x ","version":"1.10.0"}',
                  '{"name":"x","version":true}', '{"name":"x"}']
        for body in bodies:
            with self.subTest(body=body):
                if body is None:
                    self.plugin.unlink()
                else:
                    self.plugin.write_text(body, encoding='utf-8')
                candidate = self.commit()
                code, result = self.cli(candidate=candidate)
                self.assertEqual(code, 2)
                self.assertEqual(result['assessment'], 'error')

    def test_invalid_utf8_and_oversized_manifest_are_errors(self):
        for body in (b'\xff', b' ' * (release.MAX_MANIFEST + 1)):
            self.plugin.write_bytes(body)
            code, result = self.cli(candidate=self.commit())
            self.assertEqual(code, 2)
            self.assertEqual(result['assessment'], 'error')

    def test_versions_reject_leading_zeroes_aliases_prerelease_and_metadata(self):
        for version in ('01.2.3', '1.2', 'v1.2.3', '1.2.3-rc.1', '1.2.3+build.1', ' 1.2.3', '1.2.3\n', '1.' + '1' * 130 + '.0'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'stable MAJOR.MINOR.PATCH'):
                release.stable_version(version)

    def test_commit_identifiers_cannot_be_aliases_expressions_or_other_object_types(self):
        for value in ('HEAD', self.base[:12], self.base + '^{commit}', '--all'):
            with self.subTest(value=value):
                code, result = self.cli(candidate=value)
                self.assertEqual(code, 2)
                self.assertIn('explicit full commit SHAs', result['error'])
        tree = self.git('rev-parse', self.base + '^{tree}')
        code, result = self.cli(candidate=tree)
        self.assertEqual(code, 2)
        self.assertIn('commit object directly', result['error'])

    def test_symlink_and_submodule_objects_are_refused_without_following(self):
        blob = self.git('hash-object', '-w', '--stdin', input=b'../outside')
        for mode, oid in (('120000', blob), ('160000', self.base)):
            with self.subTest(mode=mode):
                self.git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',redirect')
                candidate = self.commit(stage=False)
                code, result = self.cli(candidate=candidate)
                self.assertEqual(code, 2)
                self.assertIn('regular tracked files only', result['error'])

    def test_missing_local_manifest_blob_and_unknown_commit_do_not_fetch(self):
        oid = self.git('rev-parse', self.base + ':' + release.MANIFEST)
        loose_object = self.repo / '.git' / 'objects' / oid[:2] / oid[2:]
        loose_object.chmod(stat.S_IWRITE | stat.S_IREAD)  # Disposable Git blobs are read-only on Windows.
        loose_object.unlink()
        self.git('config', 'extensions.partialClone', 'origin')
        self.git('config', 'remote.origin.promisor', 'true')
        self.git('config', 'remote.origin.url', (Path(self.tmp.name) / 'absent-local-remote').as_uri())
        for candidate in (self.base, '0' * 40):
            before = self.snapshot()
            code, result = self.cli(candidate=candidate)
            self.assertEqual(code, 2)
            self.assertEqual(result['assessment'], 'error')
            self.assertEqual(before, self.snapshot())

    def test_git_environment_cannot_redirect_repository_or_enable_transports(self):
        observed = []
        original = release.bounded_run
        def record(argv, env, limit, timeout):
            observed.append(env)
            return original(argv, env, limit, timeout=timeout)
        with patch.dict(os.environ, {'GIT_DIR': str(self.repo / 'absent'), 'GIT_ALLOW_PROTOCOL': 'file:https',
                                     'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.fsmonitor', 'GIT_CONFIG_VALUE_0': 'unwanted'}):
            with patch.object(release, 'bounded_run', side_effect=record):
                result = release.compare(self.repo, self.base, self.base)
        self.assertEqual(result['assessment'], 'passed')
        for env in observed:
            self.assertNotIn('GIT_DIR', env)
            self.assertNotIn('GIT_CONFIG_COUNT', env)
            self.assertEqual(env['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(env['GIT_NO_LAZY_FETCH'], '1')
            self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'], '1')

    def test_inventory_and_manifest_bounds_fail_closed(self):
        with patch.object(release, 'MAX_ENTRIES', 1), self.assertRaisesRegex(ValueError, 'entry comparison limit'):
            release.compare(self.repo, self.base, self.base)
        with patch.object(release, 'MAX_MANIFEST', 8), self.assertRaisesRegex(ValueError, 'manifest exceeds'):
            release.compare(self.repo, self.base, self.base)
        for number in range(25):
            (self.repo / ('file-' + str(number) + '-' + 'x' * 70)).write_text('fixture', encoding='utf-8')
        candidate = self.commit()
        # The reader's default is bound at definition time; exercise its explicit limit.
        with self.assertRaisesRegex(ValueError, 'exceeds bounded'):
            release.LocalGit(self.repo).read('ls-tree', '-r', '-z', candidate, limit=128)
        result = release.compare(self.repo, self.base, candidate)
        self.assertEqual(result['changed_files'], 25)
        self.assertEqual(len(result['changed_path_sample']), 20)
        self.assertEqual(result['paths_omitted'], 5)

    def test_malformed_tree_metadata_is_never_a_pass(self):
        row = b'100644 blob ' + b'a' * 40 + b' 1\tfile.txt\0'
        invalid = [b'', row[:-1], row + row, row.replace(b' 1\t', b' -\t'),
                   row.replace(b'blob', b'tree'), row.replace(b'100644', b'000000'),
                   row.replace(b'a' * 40, b'bad-id'), row.replace(b'file.txt', b'../outside'),
                   row.replace(b'file.txt', b'\xff'), row.replace(b'\t', b' ')]
        for raw in invalid:
            with self.subTest(raw=raw):
                with patch.object(release.LocalGit, 'read', side_effect=[b'commit\n', raw]):
                    with self.assertRaises(ValueError):
                        release.inventory(release.LocalGit(self.repo), self.base)

    def test_manifest_object_corruption_and_expired_deadline_are_errors(self):
        reader = release.LocalGit(self.repo)
        entries = release.inventory(reader, self.base)
        with patch.object(reader, 'read', return_value=b'{"name":"x","version":"99.0.0"}'):
            with self.assertRaisesRegex(ValueError, 'object identity'):
                release.manifest(reader, entries)
        reader.deadline = 0
        with patch.object(release, 'bounded_run') as run:
            with self.assertRaisesRegex(ValueError, 'time limit'):
                reader.read('cat-file', '-t', self.base)
            run.assert_not_called()

    def test_sha256_repository_has_the_same_comparison_semantics(self):
        self.repo = Path(self.tmp.name) / 'sha256-repo'
        self.repo.mkdir()
        self.git('init', '-q', '--object-format=sha256')
        self.plugin = self.repo / release.MANIFEST
        self.plugin.parent.mkdir()
        self.write_manifest()
        base = self.commit()
        self.assertEqual(len(base), 64)
        self.write_manifest('2.0.0', 'factory-builder')
        candidate = self.commit()
        result = release.compare(self.repo, base, candidate)
        self.assertEqual(result['assessment'], 'passed')


if __name__ == '__main__':
    unittest.main()
