"""Offline install comparison against disposable Git fixtures."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch
from types import SimpleNamespace
from verify_install import compare, inventory, reject_redirected_ancestors

SCRIPT=Path(__file__).with_name('verify_install.py')
class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.src=self.base/'trusted';self.src.mkdir();self.dst=self.base/'installed'
        self.hooks=self.base/'empty-hooks';self.hooks.mkdir()
        (self.src/'skill').mkdir();(self.src/'skill'/'demo.md').write_bytes(b'synthetic\n')
        (self.src/'binary.dat').write_bytes(bytes([0,1,255,10]))
        self.git('init','-q');self.git('add','--all');self.git('commit','-qm','Synthetic source')
        self.sha=self.git('rev-parse','HEAD').stdout.strip()
        shutil.copytree(self.src,self.dst,ignore=shutil.ignore_patterns('.git'))
    def tearDown(self):self.tmp.cleanup()
    def git(self,*args):
        result=subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+str(self.hooks),
            '-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-C',str(self.src),*args],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);return result
    def cli(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),'--installed',str(self.dst),'--source',str(self.src),
                               '--revision',self.sha,*args],capture_output=True,text=True,cwd=self.base)
    def test_matching_raw_bytes_and_binary_from_other_cwd(self):
        result=self.cli();self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertEqual(value['comparison'],'MATCH')
        self.assertEqual(value['source_revision'],self.sha);self.assertEqual(value['source_files'],2)
        self.assertEqual(len(value['files']),2)
        self.assertTrue(all(row['source_sha256']==row['installed_sha256'] for row in value['files']))
        self.assertIn('does not prove',value['notice'])
    def test_installed_changed_extra_and_missing_are_reported(self):
        (self.dst/'binary.dat').write_bytes(b'changed');(self.dst/'extra').write_bytes(b'extra')
        (self.dst/'skill'/'demo.md').unlink();result=self.cli()
        self.assertEqual(result.returncode,1,result.stderr);value=json.loads(result.stdout)
        self.assertEqual(value['changed'],['binary.dat']);self.assertEqual(value['extra'],['extra'])
        self.assertEqual(value['missing'],['skill/demo.md'])
        self.assertIsNone(next(row for row in value['files'] if row['path']=='extra')['installed_sha256'])
    def test_source_must_match_independently_pinned_commit(self):
        for sha in ('bad','0'*40):
            result=subprocess.run([sys.executable,str(SCRIPT),'--installed',str(self.dst),'--source',str(self.src),'--revision',sha],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
        (self.src/'skill'/'demo.md').write_bytes(b'dirty')
        with self.assertRaisesRegex(ValueError,'Source bytes differ'):compare(self.dst,self.src,self.sha)
    def test_corrupt_pinned_blob_never_matches(self):
        oid=self.git('rev-parse','HEAD:binary.dat').stdout.strip()
        obj=self.src/'.git'/'objects'/oid[:2]/oid[2:]
        if not obj.exists(): self.skipTest('Fixture does not use loose objects')
        # This object belongs to this test's disposable repository. Git marks
        # loose objects read-only on Windows; change only that fixture attribute.
        obj.chmod(stat.S_IREAD | stat.S_IWRITE)
        data=b'tampered';obj.write_bytes(zlib.compress(b'blob '+str(len(data)).encode()+b'\0'+data))
        (self.src/'binary.dat').write_bytes(data);(self.dst/'binary.dat').write_bytes(data)
        with self.assertRaisesRegex(ValueError,'source verification failed'):compare(self.dst,self.src,self.sha)

    def test_ancestor_reparse_attribute_is_rejected_without_resolving(self):
        real=Path.lstat
        target=self.base
        def fake(path, *args, **kwargs):
            info=real(path,*args,**kwargs)
            if path == target:
                return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=0x400)
            return info
        with patch.object(Path,'lstat',fake):
            with self.assertRaisesRegex(ValueError,'Redirected root or ancestor'):
                reject_redirected_ancestors(self.src)
        with self.assertRaisesRegex(ValueError,'Parent path components'):
            reject_redirected_ancestors(self.src/'..'/'trusted')

    def test_older_python_ancestor_reparse_blocks_before_git_or_resolution(self):
        real=Path.lstat
        def fake(path,*args,**kwargs):
            info=real(path,*args,**kwargs)
            if path==self.base:return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=0x400)
            return info
        with patch.object(Path,'is_junction',None,create=True), patch.object(Path,'lstat',fake):
            with patch('verify_install.local_git') as git, patch.object(Path,'resolve') as resolve:
                with self.assertRaisesRegex(ValueError,'Redirected root or ancestor'):
                    compare(self.dst,self.src,self.sha)
                git.assert_not_called();resolve.assert_not_called()

    def test_extra_file_is_reported_without_open_or_hash(self):
        import verify_install
        secret=self.dst/'unexpected';secret.write_bytes(b'private content not needed')
        real=verify_install.os.open
        def guarded(path,*args,**kwargs):
            if Path(path)==secret: raise AssertionError('unexpected file was opened')
            return real(path,*args,**kwargs)
        with patch('verify_install.os.open',side_effect=guarded):
            result=compare(self.dst,self.src,self.sha)
        self.assertEqual(result['extra'],['unexpected'])
        row=next(row for row in result['files'] if row['path']=='unexpected')
        self.assertIsNone(row['installed_sha256'])

    def test_unexpected_source_file_is_not_opened(self):
        import verify_install
        private=self.src/'not-needed';private.write_bytes(b'private content')
        real=verify_install.os.open
        def guarded(path,*args,**kwargs):
            if Path(path)==private: raise AssertionError('unexpected source file was opened')
            return real(path,*args,**kwargs)
        with patch('verify_install.os.open',side_effect=guarded):
            with self.assertRaisesRegex(ValueError,'extra or missing'):
                compare(self.dst,self.src,self.sha)

    def test_source_extra_and_same_directory_are_refused(self):
        (self.src/'unexpected').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'extra or missing'):compare(self.dst,self.src,self.sha)
        with self.assertRaisesRegex(ValueError,'separate'):compare(self.src,self.src,self.sha)
    @unittest.skipIf(os.name=='nt', 'Windows hardlink creation is not exercised; hardlink metadata refusal is covered synthetically')
    def test_hardlink_is_refused_without_output(self):
        target=self.base/'private';target.write_bytes(b'not exposed')
        try:os.link(target,self.dst/'hardlink')
        except OSError as exc:self.skipTest('Hardlink creation unavailable: '+str(exc))
        with self.assertRaisesRegex(ValueError,'hard-linked'):inventory(self.dst)

    def test_hardlink_metadata_is_refused_before_file_open(self):
        target=self.dst/'binary.dat';real=Path.lstat
        def fake(path,*args,**kwargs):
            info=real(path,*args,**kwargs)
            if path==target:
                return SimpleNamespace(st_mode=info.st_mode,st_file_attributes=0,st_nlink=2)
            return info
        real_open=os.open
        def guarded(path,*args,**kwargs):
            if Path(path)==target:raise AssertionError('hard-linked file was opened')
            return real_open(path,*args,**kwargs)
        with patch.object(Path,'lstat',fake), patch('verify_install.os.open',side_effect=guarded):
            with self.assertRaisesRegex(ValueError,'hard-linked'):inventory(self.dst)

    @unittest.skipIf(os.name=='nt', 'Windows link creation is not exercised; reparse ancestors are covered synthetically')
    def test_symlink_is_refused_without_output(self):
        target=self.base/'private';target.write_bytes(b'not exposed')
        try:(self.dst/'redirect').symlink_to(target)
        except OSError:self.skipTest('Symlink creation unavailable')
        with self.assertRaisesRegex(ValueError,'Redirected'):inventory(self.dst)

    def test_quiescent_recheck_rejects_concurrent_change(self):
        import verify_install
        real=verify_install.inventory;calls=[]
        def changed(path,**kwargs):
            value=real(path,**kwargs);calls.append(str(path))
            if len(calls)==2:(self.dst/'binary.dat').write_bytes(b'race')
            return value
        with patch('verify_install.inventory',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed during inventory'):compare(self.dst,self.src,self.sha)
    @unittest.skipIf(os.name=='nt', 'Windows directory-link creation is not exercised; reparse ancestors are covered synthetically')
    def test_untracked_redirect_inside_source_blocks(self):
        target=self.base/'outside';target.mkdir()
        try:(self.src/'redirect').symlink_to(target,target_is_directory=True)
        except OSError:self.skipTest('Directory symlink creation unavailable')
        with self.assertRaisesRegex(ValueError,'Redirected'):compare(self.dst,self.src,self.sha)
