"""Offline synthetic Git and mocked corrupt responses; no corrupt-object writes."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import export_checksums as ec
import release_identity


class SyntheticGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root/'repo'
        self.repo.mkdir()
        self.hooks = self.root/'empty-hooks'
        self.hooks.mkdir()
        self.git('init', '-q')
        (self.repo/'nested').mkdir()
        (self.repo/'nested/data.bin').write_bytes(b'\0\xff\r\nraw\n')
        (self.repo/'z.txt').write_bytes(b'last\n')
        (self.repo/'a.sh').write_bytes(b'#!/bin/sh\nexit 0\n')
        self.git('add', '--all')
        self.git('update-index', '--chmod=+x', 'a.sh')
        self.sha = self.commit()

    def git(self, *args, input=None, check=True):
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_ALLOW_PROTOCOL='', GIT_TERMINAL_PROMPT='0')
        result = subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.hooksPath='+str(self.hooks),
            '-c', 'user.name=Synthetic checksum fixture', '-c', 'user.email=fixture@example.invalid',
            '-c', 'commit.gpgsign=false', '-C', str(self.repo), *args], input=input, capture_output=True, env=env)
        if check:self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result

    def commit(self):
        self.git('commit', '-qm', 'Synthetic checksum fixture', '--allow-empty')
        return self.git('rev-parse', 'HEAD').stdout.decode().strip()

    def cli(self, revision=None):
        return subprocess.run([sys.executable, '-B', str(Path(ec.__file__)), '--repo', str(self.repo),
                               '--revision', revision or self.sha], capture_output=True, text=True, cwd=self.root)

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.repo.rglob('*') if p.is_file()}

    def test_real_raw_bytes_modes_sorted_paths_and_repeatability(self):
        before = self.snapshot()
        first = self.cli();second = self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        result = json.loads(first.stdout)
        self.assertEqual(result['source_revision'], self.sha)
        self.assertEqual(result['file_count'], 3)
        self.assertEqual([r['path'] for r in result['files']], ['a.sh', 'nested/data.bin', 'z.txt'])
        for row in result['files']:
            raw = (self.repo/row['path']).read_bytes()
            self.assertEqual(row['size'], len(raw))
            self.assertEqual(row['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['files'][0]['mode'], '100755')
        self.assertNotIn(str(self.repo), first.stdout)
        self.assertEqual(before, self.snapshot())

    def test_historical_commit_ignores_dirty_index_and_untracked_bytes(self):
        expected = self.cli().stdout
        (self.repo/'z.txt').write_bytes(b'new committed file')
        self.git('add', '--all');self.commit()
        (self.repo/'nested/data.bin').write_bytes(b'index replacement')
        self.git('add', '--all')
        (self.repo/'nested/data.bin').write_bytes(b'working replacement')
        (self.repo/'PRIVATE-untracked').write_bytes(b'not read')
        before = self.snapshot();result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(before, self.snapshot())

    def test_unknown_commit_alias_and_noncommit_reject_without_partial_manifest(self):
        tree = self.git('rev-parse', self.sha+'^{tree}').stdout.decode().strip()
        self.git('config', 'extensions.partialClone', 'origin')
        self.git('config', 'remote.origin.promisor', 'true')
        self.git('config', 'remote.origin.url', (self.root/'missing-remote').as_uri())
        for revision in ('0'*40, 'HEAD', self.sha[:12], self.sha+'^{commit}', tree):
            with self.subTest(revision=revision):
                before = self.snapshot();result = self.cli(revision)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn('No manifest was emitted', result.stderr)
                self.assertNotIn(str(self.repo), result.stderr)
                self.assertEqual(before, self.snapshot())

    def test_symlink_and_gitlink_modes_reject_without_creating_links(self):
        blob = self.git('hash-object', '-w', '--stdin', input=b'../outside').stdout.decode().strip()
        for mode, oid in (('120000', blob), ('160000', self.sha)):
            with self.subTest(mode=mode):
                self.git('update-index', '--add', '--cacheinfo', mode+','+oid+',redirect')
                candidate = self.commit()
                result = self.cli(candidate)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')

    def test_sha256_repository_when_supported(self):
        self.repo = self.root/'sha256'
        self.repo.mkdir()
        result = self.git('init', '-q', '--object-format=sha256', check=False)
        if result.returncode:self.skipTest('Installed Git lacks SHA-256 repository support')
        (self.repo/'sample').write_bytes(b'SHA-256 object fixture')
        self.git('add', '--all');self.sha = self.commit()
        result = self.cli();self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data['source_revision']), 64)
        self.assertEqual(data['git_object_algorithm'], 'sha256')
        self.assertEqual(data['files'][0]['sha256'], hashlib.sha256(b'SHA-256 object fixture').hexdigest())

    def test_inherited_git_redirects_replacements_and_transports_are_disabled(self):
        observed = []
        original = release_identity.bounded_run
        def spy(argv, env, limit, timeout):
            observed.append((argv, env))
            return original(argv, env, limit, timeout=timeout)
        with patch.dict(os.environ, {'GIT_DIR': str(self.root/'wrong'), 'GIT_WORK_TREE': str(self.root),
             'GIT_OBJECT_DIRECTORY': str(self.root/'other'), 'GIT_ALTERNATE_OBJECT_DIRECTORIES': str(self.root),
             'GIT_CONFIG_COUNT':'1', 'GIT_CONFIG_KEY_0':'core.fsmonitor', 'GIT_CONFIG_VALUE_0':'untrusted',
             'GIT_ALLOW_PROTOCOL':'https:file', 'GIT_NO_LAZY_FETCH':'0'}), patch.object(release_identity,'bounded_run',side_effect=spy):
            self.assertEqual(ec.export(self.repo,self.sha)['file_count'],3)
        for argv, env in observed:
            self.assertNotIn('GIT_DIR',env);self.assertNotIn('GIT_WORK_TREE',env)
            self.assertNotIn('GIT_OBJECT_DIRECTORY',env);self.assertNotIn('GIT_ALTERNATE_OBJECT_DIRECTORIES',env)
            self.assertNotIn('GIT_CONFIG_COUNT',env)
            self.assertEqual(env['GIT_NO_LAZY_FETCH'],'1');self.assertEqual(env['GIT_ALLOW_PROTOCOL'],'')
            self.assertEqual(env['GIT_NO_REPLACE_OBJECTS'],'1')
            self.assertIn('core.fsmonitor=false',argv)


class FakeGit:
    def __init__(self):
        self.deadline = time.monotonic()+90
        self.objects = {}
        self.calls = []
        self.responses = {}
    def add(self, kind, body):
        oid = ec.object_digest(kind,body,'sha1')
        self.objects[oid] = (kind,body)
        return oid
    def tree(self, entries):
        return self.add('tree',b''.join(mode.encode()+b' '+name+b'\0'+bytes.fromhex(oid) for mode,name,oid in entries))
    def commit(self, tree, extra=b''):
        return self.add('commit',b'tree '+tree.encode()+b'\n'+extra+b'author Fixture <fixture@example.invalid> 1 +0000\ncommitter Fixture <fixture@example.invalid> 1 +0000\n\nSynthetic\n')
    def read(self, *args, limit):
        self.calls.append(args)
        if args in self.responses:return self.responses[args]
        _, option, oid = args
        if oid not in self.objects:raise ValueError('Missing synthetic object')
        kind, body = self.objects[oid]
        result = kind.encode()+b'\n' if option=='-t' else str(len(body)).encode()+b'\n' if option=='-s' else body
        if len(result)>limit:raise ValueError('Bound exceeded')
        return result


class ObjectValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git = FakeGit()
        self.blob = self.git.add('blob',b'synthetic')
        self.tree = self.git.tree([('100644',b'file',self.blob)])
        self.commit = self.git.commit(self.tree)
    def export(self, revision=None):
        with patch.object(ec,'LocalGit',return_value=self.git):return ec.export(self.repo,revision or self.commit)

    def test_corrupt_commit_tree_and_blob_responses_reject_without_corrupting_disk(self):
        for kind,oid in [('commit',self.commit),('tree',self.tree),('blob',self.blob)]:
            self.git.responses = {('cat-file',kind,oid): b'X'*len(self.git.objects[oid][1])}
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'identity mismatch'):self.export()

    def test_wrong_type_and_inconsistent_size_fail_closed(self):
        for responses in [{('cat-file','-t',self.blob):b'tree\n'},
                          {('cat-file','-s',self.blob):b'8\n'},
                          {('cat-file','-s',self.blob):b'-1\n'},
                          {('cat-file','-s',self.blob):b'09\n'}]:
            self.git.responses = responses
            with self.subTest(responses=responses),self.assertRaises(ValueError):self.export()

    def test_cached_object_still_requires_matching_type(self):
        reader = ec.Objects(self.git,40);reader.read(self.blob,'blob')
        with self.assertRaisesRegex(ValueError,'type conflicts'):reader.read(self.blob,'tree')

    def test_root_header_must_be_unique_canonical_and_before_message(self):
        oid = self.tree.encode()
        bodies = [b'author x\n\ntree '+oid+b'\n', b'tree '+oid+b'\ntree '+oid+b'\n\nmessage',
                  b'tree '+oid+b'\n tree '+oid+b'\n\nmessage', b'tree '+oid[:-1]+b'\n\nmessage',
                  b'tree '+oid+b'\nauthor x',b'tree '+oid+b'\0\n\nmessage']
        for body in bodies:
            with self.subTest(body=body),self.assertRaises(ValueError):self.export(self.git.add('commit',body))

    def test_missing_blob_is_unknown_not_empty_content(self):
        del self.git.objects[self.blob]
        with self.assertRaisesRegex(ValueError,'Missing'):self.export()

    def test_malformed_unsafe_aliased_and_unsorted_tree_records_reject(self):
        oid = bytes.fromhex(self.blob)
        bodies = [b'100644 file',b'100644 file\0'+oid[:-1],b'100644 ../file\0'+oid,
                  b'100644 .git\0'+oid,b'100644 \xff\0'+oid,b'100644 x:y\0'+oid,
                  b'100644 file\0'+oid+b'100644 file\0'+oid,
                  b'100644 Z\0'+oid+b'100644 A\0'+oid,
                  b'100644 A\0'+oid+b'100644 a\0'+oid,
                  b'100644 e\xcc\x81\0'+oid+b'100644 \xc3\xa9\0'+oid]
        for body in bodies:
            with self.subTest(body=body),self.assertRaises((ValueError,UnicodeError)):
                self.export(self.git.commit(self.git.add('tree',body)))

    def test_byte_entry_depth_and_logical_duplicate_bounds(self):
        with patch.object(ec,'MAX_BLOB',2),self.assertRaisesRegex(ValueError,'byte limit'):self.export()
        self.assertNotIn(('cat-file','blob',self.blob),self.git.calls)
        with patch.object(ec,'MAX_TOTAL',1),self.assertRaisesRegex(ValueError,'byte limit'):self.export()
        tree = self.git.tree([('40000',b'dir',self.tree)])
        with patch.object(ec,'MAX_ENTRIES',1),self.assertRaisesRegex(ValueError,'entry limit'):
            self.export(self.git.commit(tree))
        with patch.object(ec,'MAX_DEPTH',0),self.assertRaisesRegex(ValueError,'depth limit'):
            self.export(self.git.commit(tree))
        with patch.object(ec,'MAX_PATH',5),self.assertRaisesRegex(ValueError,'path byte limit'):
            self.export(self.git.commit(tree))
        large = self.git.add('blob',b'x'*2000)
        tree = self.git.tree([('100644',b'a',large),('100644',b'b',large)])
        with patch.object(ec,'MAX_TOTAL',3000),self.assertRaisesRegex(ValueError,'logical file byte'):
            self.export(self.git.commit(tree))

    def test_repeated_subtrees_count_all_logical_entries_and_directories(self):
        tree = self.git.tree([('40000',b'a',self.tree),('40000',b'b',self.tree)])
        revision = self.git.commit(tree)
        with patch.object(ec,'MAX_ENTRIES',3),self.assertRaisesRegex(ValueError,'entry limit'):self.export(revision)
        self.assertEqual(self.export(revision)['file_count'],2)

    def test_full_path_limit_counts_utf8_bytes(self):
        tree = self.git.tree([('100644','ééé'.encode(),self.blob)])
        with patch.object(ec,'MAX_PATH',5),self.assertRaisesRegex(ValueError,'path byte limit'):
            self.export(self.git.commit(tree))

    def test_deadline_is_rechecked_after_a_tree_read_before_traversal(self):
        original = self.git.read
        def expire(*args,**kwargs):
            value = original(*args,**kwargs)
            if args == ('cat-file','tree',self.tree):self.git.deadline = 0
            return value
        with patch.object(self.git,'read',side_effect=expire),self.assertRaisesRegex(ValueError,'deadline'):self.export()
        self.assertNotIn(('cat-file','blob',self.blob),self.git.calls)

    def test_empty_root_and_git_directory_sorting_are_valid(self):
        empty = self.git.tree([])
        self.assertEqual(self.export(self.git.commit(empty))['files'],[])
        tree = self.git.tree([('100644',b'a.txt',self.blob),('40000',b'a',self.tree)])
        self.assertEqual([r['path'] for r in self.export(self.git.commit(tree))['files']],['a.txt','a/file'])

    def test_deadline_and_redirected_ancestor_stop_before_object_reads(self):
        self.git.deadline = 0
        with self.assertRaisesRegex(ValueError,'deadline'):self.export()
        self.assertEqual(self.git.calls,[])
        with patch.object(ec,'reject_redirected_ancestors',side_effect=ValueError('redirect')),patch.object(ec,'LocalGit') as reader:
            with self.assertRaises(ValueError):ec.export(self.repo,self.commit)
            reader.assert_not_called()

    def test_cli_error_never_leaks_private_names_or_partial_manifest(self):
        out,err = io.StringIO(),io.StringIO()
        with patch.object(ec,'export',side_effect=ValueError('PRIVATE filename/contents')),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code = ec.main(['--repo',str(self.repo),'--revision',self.commit])
        self.assertEqual(code,2);self.assertEqual(out.getvalue(),'')
        self.assertNotIn('PRIVATE',err.getvalue());self.assertNotIn(str(self.repo),err.getvalue())


if __name__ == '__main__':unittest.main()
