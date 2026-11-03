"""Execute the documented comparison on synthetic Git objects, never hosted history."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import ci_evidence
from gates import gate_rows, problems, requirements
from incremental_records import gate_change
from scaffold import ROOT, render


@unittest.skipUnless(shutil.which('git'), 'Local Git is required for synthetic object tests')
class MergeSubjectEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'synthetic-repository'; self.repo.mkdir()
        self.env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME='Synthetic fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
                        GIT_COMMITTER_NAME='Synthetic fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid',
                        GIT_AUTHOR_DATE='2026-11-03T00:00:00+00:00',
                        GIT_COMMITTER_DATE='2026-11-03T00:00:00+00:00',
                        GIT_ALLOW_PROTOCOL='', GIT_TERMINAL_PROMPT='0')
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
                     'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR'):
            self.env.pop(name, None)
        self.git('init', '-q')
        self.base_tree = self.tree('base content\n')
        self.head_tree = self.tree('reviewed feature content\n')
        self.base = self.commit(self.base_tree, 'base')
        self.head = self.commit(self.head_tree, 'reviewed head', self.base)
        self.squash = self.commit(self.head_tree, 'squashed result', self.base)
        self.git('update-ref', 'refs/heads/synthetic', self.squash)
        self.git('symbolic-ref', 'HEAD', 'refs/heads/synthetic')
        text = (ROOT / 'references/merge-subject-evidence.md').read_text(encoding='utf-8')
        blocks = re.findall(r'```python\n(.*?)\n```', text, re.S)
        self.assertEqual(len(blocks), 1)
        namespace = {}
        exec(compile(blocks[0], 'merge-subject-evidence.md', 'exec'), namespace)
        self.compare = namespace['compare_subject_trees']

    def git(self, *args, data=None):
        result = subprocess.run(['git', '-c', 'commit.gpgsign=false', '-C', str(self.repo), *args],
                                input=data, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        return result.stdout.decode('ascii').strip()

    def tree(self, content, mode='100644', extra=False):
        blob = self.git('hash-object', '-w', '--stdin', data=content.encode('utf-8'))
        rows = [f'{mode} blob {blob}\tapp.txt\n']
        if extra:
            evidence = self.git('hash-object', '-w', '--stdin', data=b'SYNTHETIC stored observations\n')
            rows.append(f'100644 blob {evidence}\tobservations.txt\n')
        return self.git('mktree', data=''.join(rows).encode('ascii'))

    def commit(self, tree, message, *parents):
        arguments = ['commit-tree', tree, '-m', message]
        for parent in parents:
            arguments.extend(['-p', parent])
        return self.git(*arguments)

    def snapshot(self):
        return {str(path.relative_to(self.repo)): path.read_bytes()
                for path in self.repo.rglob('*') if path.is_file()}

    def test_distinct_squash_rebase_and_merge_commits_have_equal_trees_without_transfer(self):
        new_base = self.commit(self.base_tree, 'different base metadata', self.base)
        rebased = self.commit(self.head_tree, 'rebased feature', new_base)
        merged = self.commit(self.head_tree, 'two parent merge', self.base, self.head)
        self.assertEqual(len({self.head, self.squash, rebased, merged}), 4)
        before = self.snapshot()
        for integrated in (self.squash, rebased, merged):
            with self.subTest(integrated=integrated):
                result = self.compare(self.repo, self.head, integrated)
                self.assertTrue(result['trees_equal'])
                self.assertFalse(result['evidence_transferred'])
                self.assertEqual(result['reviewed_subject'], self.head)
                self.assertEqual(result['integrated_subject'], integrated)
        self.assertEqual(self.snapshot(), before)

    def test_content_mode_and_evidence_only_tree_differences_are_not_hidden(self):
        trees = [self.tree('different integration result\n'),
                 self.tree('reviewed feature content\n', mode='100755'),
                 self.tree('reviewed feature content\n', extra=True)]
        for tree in trees:
            integrated = self.commit(tree, 'changed tree', self.squash)
            result = self.compare(self.repo, self.head, integrated)
            self.assertFalse(result['trees_equal']); self.assertFalse(result['evidence_transferred'])

    def test_same_subject_and_dirty_worktree_do_not_change_object_comparison(self):
        (self.repo / 'app.txt').write_text('SYNTHETIC dirty/untracked working content', encoding='utf-8')
        before = self.snapshot()
        result = self.compare(self.repo, self.head, self.head)
        self.assertTrue(result['trees_equal']); self.assertFalse(result['evidence_transferred'])
        self.assertEqual(self.snapshot(), before)

    def test_aliases_prefixes_and_revision_syntax_are_rejected_before_git(self):
        for invalid in ('HEAD', self.head[:7], self.head + '^', '--help', '', None):
            with self.subTest(invalid=invalid), patch.object(ci_evidence.Git, 'read',
                    side_effect=AssertionError('Invalid identity must not reach Git')):
                with self.assertRaises(ValueError):
                    self.compare(self.repo, invalid, self.squash)

    def test_tree_blob_and_unknown_commit_objects_are_refused(self):
        blob = self.git('hash-object', '-w', '--stdin', data=b'synthetic non-commit')
        before = self.snapshot()
        for identity in (self.head_tree, blob, '0' * 40):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                self.compare(self.repo, identity, self.squash)
        self.assertEqual(self.snapshot(), before)

    def test_ambient_repository_redirects_are_refused_before_reading_objects(self):
        for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE',
                     'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES'):
            with self.subTest(name=name), patch.dict(os.environ, {name: str(self.repo)}), \
                 patch.object(ci_evidence.Git, 'read', side_effect=AssertionError('Redirect must not reach Git')):
                with self.assertRaisesRegex(ValueError, 'redirects'):
                    self.compare(self.repo, self.head, self.squash)

    def test_reader_bounds_output_and_disables_transport_and_replace_objects(self):
        observed = []
        original = ci_evidence.bounded_run

        def capture(argv, env, limit):
            observed.append((argv, env, limit))
            return original(argv, env, limit)

        with patch('ci_evidence.bounded_run', side_effect=capture), \
             patch.dict(os.environ, {'GIT_ALLOW_PROTOCOL': 'file:https'}):
            with self.assertRaises(ValueError):
                self.compare(self.repo, '0' * 40, self.squash)
        self.assertEqual(len(observed), 1)
        for argv, env, limit in observed:
            self.assertEqual(limit, 128)
            self.assertEqual(env['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(env['GIT_NO_LAZY_FETCH'], '1')
            self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'], '1')
            self.assertEqual(env['GIT_OPTIONAL_LOCKS'], '0')
            self.assertIn('cat-file', argv)

    def records(self, revision):
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        config['operations'] = {'smoke_gates': {'target_kind': 'artifact',
                                               'deployed_url': 'synthetic-delivered-artifact'}}
        text = render(config, research)['verification.md']
        lines = []
        for line in text.splitlines():
            if line.startswith('| ') and line.split('|')[1].strip() in ('G1', 'G2', 'G3', 'A1'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[2:4] = ['SYNTHETIC observed check', 'isolated synthetic fixture']
                cells[5:] = [revision, 'PASSED', 'SYNTHETIC evidence, not an application run',
                             'synthetic-delivered-artifact', '2026-11-03T00:00:00Z', '0']
                line = '| ' + ' | '.join(cells) + ' |'
            lines.append(line)
        return config, research, '\n'.join(lines) + '\n'

    def test_equal_trees_do_not_satisfy_gate_for_a_different_subject(self):
        config, research, text = self.records(self.head)
        expected = requirements(config, research)
        self.assertTrue(self.compare(self.repo, self.head, self.squash)['trees_equal'])
        self.assertEqual(problems(text, 'pre-merge', self.head, expected), [])
        stale = problems(text, 'pre-merge', self.squash, expected)
        self.assertTrue(stale); self.assertTrue(any('revision' in problem for problem in stale))
        self.assertTrue(all(row['revision'] == self.head for row in gate_rows(text).values()))

    def test_storage_commit_is_not_the_delivered_subject(self):
        storage = self.commit(self.tree('reviewed feature content\n', extra=True),
                              'store observations', self.squash)
        config, research, text = self.records(self.squash)
        expected = requirements(config, research)
        self.assertEqual(problems(text, 'post-merge', self.squash, expected,
                                  'synthetic-delivered-artifact'), [])
        self.assertTrue(problems(text, 'post-merge', storage, expected,
                                 'synthetic-delivered-artifact'))

    def test_explicit_new_observation_keeps_previous_failed_subject_in_history(self):
        config, research, text = self.records(self.head)
        old_row = next(line for line in text.splitlines() if line.startswith('| G1 |'))
        failed = old_row.replace('| PASSED |', '| FAILED |').replace('| 0 |', '| 1 |')
        text = text.replace(old_row, failed)
        self.assertTrue(problems(text, 'pre-merge', self.head, requirements(config, research)))
        change = {'gate': 'G1', 'revision': self.squash, 'result': 'PASSED',
                  'environment': 'isolated synthetic fixture', 'evidence': 'SYNTHETIC new observation only',
                  'target': 'synthetic-delivered-artifact', 'checked_at': '2026-11-03T00:01:00Z',
                  'exit_status': '0'}
        updated = gate_change(text, config, research, change).decode('utf-8')
        self.assertIn('> ' + failed, updated)
        self.assertEqual(gate_rows(updated)['G1']['revision'], self.squash)
        # Other H observations were not silently copied; readiness for M stays blocked.
        self.assertTrue(problems(updated, 'pre-merge', self.squash, requirements(config, research)))


if __name__ == '__main__':
    unittest.main()
