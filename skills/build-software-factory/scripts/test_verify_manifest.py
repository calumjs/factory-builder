"""Pinned manifest consumption using disposable files; no cache or service access."""
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import export_checksums
import verify_manifest as vm
import verify_install


class ManifestVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        cls.source = Path(cls.fixture.name)/'source';cls.source.mkdir()
        hooks = Path(cls.fixture.name)/'empty-hooks';hooks.mkdir()
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_ALLOW_PROTOCOL='',GIT_TERMINAL_PROMPT='0')
        def git(*args):
            result = subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+str(hooks),
                 '-c','user.name=Synthetic manifest fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','-C',str(cls.source),*args],capture_output=True,env=env)
            if result.returncode:raise AssertionError(result.stderr.decode(errors='replace'))
            return result.stdout.decode().strip()
        cls.contents = {'a.txt':b'raw\r\nbytes\n','nested/data.bin':b'\0\xff\x01', 'zero':b''}
        for name,body in cls.contents.items():
            path=cls.source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        git('init','-q');git('add','--all');git('commit','-qm','Synthetic manifest fixture')
        cls.revision=git('rev-parse','HEAD')
        cls.exported=export_checksums.export(cls.source,cls.revision)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.installed=self.root/'installed';self.installed.mkdir()
        for name,body in self.contents.items():
            path=self.installed/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.manifest=self.root/'checksums.json'
        self.value=copy.deepcopy(self.exported)
        self.pin=self.write_manifest()

    def write_manifest(self,value=None,raw=None):
        raw = raw if raw is not None else (json.dumps(value if value is not None else self.value,sort_keys=True,indent=2)+'\n').encode()
        self.manifest.write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def compare(self,pin=None,revision=None):
        return vm.compare_manifest(self.installed,self.manifest,pin or self.pin,revision or self.revision)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def cli(self,*extra,manifest=True):
        argv=[sys.executable,'-B',str(Path(verify_install.__file__)),'--installed',str(self.installed),'--revision',self.revision]
        if manifest:argv+=['--manifest',str(self.manifest),'--manifest-sha256',self.pin]
        return subprocess.run([*argv,*extra],capture_output=True,text=True,cwd=self.root)

    def test_actual_exported_manifest_matches_without_git_or_file_changes(self):
        before=self.snapshot()
        with patch.object(verify_install,'local_git',side_effect=AssertionError('No Git in manifest mode')):
            result=self.compare()
        self.assertEqual(result['comparison'],'MATCH')
        self.assertEqual(result['manifest_sha256'],self.pin);self.assertEqual(result['source_revision'],self.revision)
        self.assertEqual(result['files'],[{'path':p,'source_sha256':hashlib.sha256(b).hexdigest(),'installed_sha256':hashlib.sha256(b).hexdigest()} for p,b in sorted(self.contents.items())])
        self.assertIn('executable permission bits',result['notice']);self.assertIn('Independently trust',result['notice'])
        self.assertEqual(before,self.snapshot())
        result=self.cli();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['comparison'],'MATCH');self.assertEqual(before,self.snapshot())

    def test_changed_missing_and_extra_regular_files_are_exact_and_extra_contents_unread(self):
        (self.installed/'a.txt').write_bytes(b'changed')
        (self.installed/'zero').unlink()
        extra=self.installed/'extra-private';extra.write_bytes(b'PRIVATE CONTENT')
        original=os.open
        def guarded(path,*args,**kwargs):
            if Path(path)==extra:raise AssertionError('Unexpected file contents were opened')
            return original(path,*args,**kwargs)
        before=self.snapshot()
        with patch.object(vm.os,'open',side_effect=guarded):result=self.compare()
        self.assertEqual(result['comparison'],'DIFFERENT');self.assertEqual(result['changed'],['a.txt'])
        self.assertEqual(result['missing'],['zero']);self.assertEqual(result['extra'],['extra-private'])
        self.assertIsNone(next(r for r in result['files'] if r['path']=='extra-private')['installed_sha256'])
        self.assertEqual(before,self.snapshot())
        result=self.cli();self.assertEqual(result.returncode,1,result.stderr)

    def test_tampering_and_stale_raw_pins_fail_before_json_parsing(self):
        self.write_manifest(raw=self.manifest.read_bytes()+b' ')
        before=self.snapshot()
        with patch.object(vm,'strict_json',side_effect=AssertionError('Unpinned bytes parsed')):
            with self.assertRaisesRegex(ValueError,'raw digest'):self.compare()
        self.assertEqual(before,self.snapshot())
        result=self.cli();self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
        self.assertNotIn(str(self.manifest),result.stderr)

    def test_expected_source_identity_is_independent_of_manifest_claim(self):
        with self.assertRaisesRegex(ValueError,'identity'):self.compare(revision='0'*40)
        for revision in ('HEAD',self.revision[:12],self.revision+'^{commit}'):
            with self.subTest(revision=revision),self.assertRaises(ValueError):self.compare(revision=revision)
        for pin in ('bad','A'*64,True):
            with self.subTest(pin=pin),self.assertRaises(ValueError):self.compare(pin=pin)

    def test_reformatted_manifest_requires_its_own_raw_pin_and_then_compares(self):
        original=self.pin
        self.pin=self.write_manifest(raw=json.dumps(self.exported,separators=(',',':')).encode())
        self.assertNotEqual(self.pin,original)
        with self.assertRaisesRegex(ValueError,'raw digest'):self.compare(pin=original)
        self.assertEqual(self.compare()['comparison'],'MATCH')

    def test_duplicate_malformed_and_nonfinite_json_refused_without_writes(self):
        raws=[b'{"schema":1,"schema":1}',b'{"files":[{"path":"a","path":"b"}]}',b'{"schema":NaN}',b'\xff',b'[]',b'{']
        for raw in raws:
            self.pin=self.write_manifest(raw=raw);before=self.snapshot()
            with self.subTest(raw=raw),self.assertRaises((ValueError,UnicodeError)):self.compare()
            result=self.cli();self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
            self.assertEqual(before,self.snapshot())

    def test_strict_schema_types_algorithms_counts_sizes_modes_and_hashes(self):
        mutations=[lambda v:v.update(schema=True),lambda v:v.update(schema=2),lambda v:v.update(extra='PRIVATE'),
            lambda v:v.pop('notice'),lambda v:v.update(file_count=True),lambda v:v.update(file_count=4),
            lambda v:v.update(total_file_bytes=True),lambda v:v.update(total_file_bytes=-1),
            lambda v:v.update(total_file_bytes=99),lambda v:v.update(source_tree='a'*64),
            lambda v:v.update(git_object_algorithm='sha256'),lambda v:v.update(checksum_algorithm='sha1'),
            lambda v:v.update(notice={'authority':'self-approved'}),lambda v:v['files'][0].update(size=True),
            lambda v:v['files'][0].update(size=-1),lambda v:v['files'][0].update(size=vm.MAX_FILE+1),
            lambda v:v['files'][0].update(mode='120000'),lambda v:v['files'][0].update(mode='160000'),
            lambda v:v['files'][0].update(sha256='A'*64),lambda v:v['files'][0].update(sha256='a'*63),
            lambda v:v['files'][0].update(extra='unsupported')]
        for change in mutations:
            value=copy.deepcopy(self.exported);change(value);self.pin=self.write_manifest(value)
            with self.subTest(change=change),self.assertRaises(ValueError):self.compare()

    def manifest_paths(self,names):
        value=copy.deepcopy(self.exported)
        value['files']=[{'path':name,'mode':'100644','size':0,'sha256':hashlib.sha256(b'').hexdigest()} for name in names]
        value.update(file_count=len(names),total_file_bytes=0)
        self.pin=self.write_manifest(value)

    def test_unique_safe_sorted_paths_include_directory_aliases_and_prefix_conflicts(self):
        cases=[['a','a'],['b','a'],['../outside'],['/absolute'],['C:/absolute'],['a\\b'],['.git/config'],
               ['a/../b'],['a//b'],['a/ b'],['a\n'],['A','a'],['Dir/a','dir/b'],['a','a/b'],
               ['e\u0301/a','é/b'],['a/'*21+'x'],['x'*4097]]
        for names in cases:
            self.manifest_paths(names)
            with self.subTest(names=names),self.assertRaises(ValueError):self.compare()

    def test_empty_manifest_and_all_allocation_limits_refuse(self):
        self.manifest_paths([])
        with self.assertRaisesRegex(ValueError,'nonempty'):self.compare()
        self.pin=self.write_manifest(self.exported)
        with patch.object(vm,'MAX_MANIFEST',8),self.assertRaisesRegex(ValueError,'bounded'):self.compare()
        with patch.object(vm,'MAX_ENTRIES',3),self.assertRaisesRegex(ValueError,'logical entry'):self.compare()
        with patch.object(vm,'MAX_TOTAL',1),self.assertRaises(ValueError):self.compare()
        self.manifest_paths(['ééé'])
        with patch.object(vm,'MAX_PATH',5),self.assertRaisesRegex(ValueError,'path or depth'):self.compare()

    def test_manifest_must_be_external_and_mode_options_are_unambiguous(self):
        internal=self.installed/'manifest.json';internal.write_bytes(self.manifest.read_bytes())
        with self.assertRaisesRegex(ValueError,'outside'):vm.compare_manifest(self.installed,internal,self.pin,self.revision)
        cases=[('--source',str(self.source)),]
        for args in cases:
            result=self.cli(*args);self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
        result=self.cli('--manifest',str(self.manifest),manifest=False)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
        result=self.cli('--source',str(self.source),'--manifest-sha256',self.pin,manifest=False)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
        result=self.cli('--source',str(self.source),'--manifest-sha256','',manifest=False)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')

    def test_sha256_source_width_is_supported_without_claiming_git_verification(self):
        value=copy.deepcopy(self.exported)
        value.update(source_revision='a'*64,source_tree='b'*64,git_object_algorithm='sha256')
        self.pin=self.write_manifest(value)
        result=self.compare(revision='a'*64)
        self.assertEqual(result['comparison'],'MATCH')
        self.assertIn('No Git/source provenance',result['notice'])
        value['source_tree']='b'*40;self.pin=self.write_manifest(value)
        with self.assertRaisesRegex(ValueError,'tree identity'):self.compare(revision='a'*64)

    def test_descriptive_claims_do_not_become_trust_or_action_authority(self):
        self.value.update(notice='SELF APPROVED PRIVATE AUTHORITY',scope='Caller-authored description')
        self.pin=self.write_manifest()
        result=self.compare()
        self.assertNotIn('SELF APPROVED',json.dumps(result))
        self.assertIn('supplied pins only',result['notice'])

    def test_link_reparse_and_nonregular_metadata_refused_without_real_link_fixtures(self):
        original=Path.lstat
        for target,mutation in [(self.manifest,{'st_nlink':2}), (self.manifest,{'st_file_attributes':0x400}),
                                (self.installed/'a.txt',{'st_mode':stat.S_IFIFO}),
                                (self.installed/'a.txt',{'st_nlink':2}),
                                (self.installed/'nested',{'st_file_attributes':0x400})]:
            def fake(path,*args,**kwargs):
                info=original(path,*args,**kwargs)
                if path!=target:return info
                fields={name:getattr(info,name) for name in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')}
                fields['st_file_attributes']=getattr(info,'st_file_attributes',0);fields.update(mutation)
                return SimpleNamespace(**fields)
            with self.subTest(target=target.name,mutation=mutation),patch.object(Path,'lstat',fake),self.assertRaises(ValueError):self.compare()

    def test_installed_change_between_scans_is_preserved_and_refused(self):
        original=vm.inventory;calls=0
        def change(*args,**kwargs):
            nonlocal calls
            result=original(*args,**kwargs);calls+=1
            if calls==1:(self.installed/'a.txt').write_bytes(b'concurrent actor')
            return result
        with patch.object(vm,'inventory',side_effect=change),self.assertRaisesRegex(ValueError,'changed'):self.compare()
        self.assertEqual((self.installed/'a.txt').read_bytes(),b'concurrent actor')

    def test_manifest_change_during_inventory_is_preserved_and_refused(self):
        original=vm.inventory;calls=0
        def change(*args,**kwargs):
            nonlocal calls
            result=original(*args,**kwargs);calls+=1
            if calls==2:self.manifest.write_bytes(self.manifest.read_bytes()+b' ')
            return result
        with patch.object(vm,'inventory',side_effect=change),self.assertRaisesRegex(ValueError,'digest'):self.compare()
        self.assertTrue(self.manifest.read_bytes().endswith(b' '))

    def test_source_mode_still_matches_and_refuses_dirty_checkout(self):
        before=self.snapshot()
        result=self.cli('--source',str(self.source),manifest=False)
        self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout)
        self.assertEqual(set(value),{'source_revision','source_files','installed_files','files','missing','extra','changed','comparison','notice'})
        self.assertEqual(value,verify_install.compare(self.installed,self.source,self.revision))
        self.assertEqual(before,self.snapshot())
        path=self.source/'a.txt';original=path.read_bytes()
        try:
            path.write_bytes(b'dirty source')
            result=self.cli('--source',str(self.source),manifest=False)
            self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'')
            self.assertIn('Source bytes differ from the pinned Git tree',result.stderr)
        finally:path.write_bytes(original)


if __name__=='__main__':unittest.main()
