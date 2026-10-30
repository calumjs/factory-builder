"""Recovery automation exercises only disposable synthetic snapshots; never live factories."""
import copy
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from gates import assess, gate_rows
from integrity import check, digest
from recover_factory import prepare, apply, preview, verify_output, rawhash, dumps, capture, manifest, name_ok, RESERVED, MAX_DIRECTORIES, MAX_FILE, MAX_ENTRIES
from scaffold import ROOT, render


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.parent=Path(self.tmp.name)
        self.base=self.parent/'accepted';self.base.mkdir()
        self.source=self.parent/'damaged';self.source.mkdir()
        self.output=self.parent/'recovered'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        files=render(config,research)
        files['obsolete.md']='Synthetic accepted optional contract.\n'
        value=json.loads(files['manifest.json']);value['contracts']['obsolete.md']=digest(files['obsolete.md'])
        files['manifest.json']=dumps(value)
        for root in (self.base,self.source):
            for name,body in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        self.pin=rawhash((self.base/'manifest.json').read_bytes())
        self.reference='SYNTHETIC accepted baseline review, not an actual repository attestation'
        policy=self.source/'policy.md';policy.write_bytes(policy.read_bytes()+b'\nCustom accepted project instruction.\n')
        (self.source/'design-note.md').write_bytes(b'Synthetic immutable contract addition.\n')
        (self.source/'obsolete.md').unlink()
        verification=self.source/'verification.md';verification.write_bytes(verification.read_bytes().replace(b'| yes |',b'| no |',1))
        (self.source/'learning-log.md').write_bytes(b'Synthetic operator history; keep byte-for-byte.\r\n')
        self.decisions={'accept_changed':[{'path':'policy.md','reason':'Synthetic reviewed custom rule'}],
                        'register':[{'path':'design-note.md','reason':'Reviewed immutable design, not runtime log'}],
                        'remove':[{'path':'obsolete.md','reason':'Synthetic retired optional contract'}]}

    def tearDown(self):self.tmp.cleanup()

    def files(self,root):return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def plan(self,decisions=True):
        return prepare(self.source,self.base,self.output,self.pin,self.reference,self.decisions if decisions else None)

    def test_audit_and_plan_are_write_free_and_show_full_differences(self):
        before=self.files(self.source);baseline=self.files(self.base)
        result=self.plan(False)
        self.assertIsNone(result['plan'])
        stream=io.StringIO()
        with redirect_stdout(stream):preview(result)
        for text in ('design-note.md','obsolete.md','Custom accepted project instruction','LIVING (preserved unhashed)'):
            self.assertIn(text,stream.getvalue())
        result=self.plan();self.assertEqual(len(result['plan']),64)
        self.assertFalse(self.output.exists());self.assertFalse((self.parent/'.factory-recovery-backups').exists())
        self.assertEqual(before,self.files(self.source));self.assertEqual(baseline,self.files(self.base))

    def test_empty_directory_deltas_are_visible_and_counts_bounded(self):
        (self.source/'new-empty').mkdir();(self.base/'old-empty').mkdir()
        result=self.plan();stream=io.StringIO()
        with redirect_stdout(stream):preview(result)
        self.assertIn('DIRECTORY ADDED: new-empty',stream.getvalue())
        self.assertIn('DIRECTORY REMOVED: old-empty',stream.getvalue())
        for i in range(MAX_DIRECTORIES+1):(self.source/('empty-'+str(i))).mkdir()
        with self.assertRaisesRegex(ValueError,'directory-count|total-entry'):self.plan()

    def test_growing_file_is_read_with_actual_byte_cap(self):
        path=self.source/'design-note.md';original_open=Path.open;sizes=[]
        class Reader:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def read(self,size):sizes.append(size);return self.stream.read(size)
        def grow(current,mode='r',*args,**kwargs):
            if current==path and mode=='rb':
                with original_open(current,'wb') as stream:stream.write(b'x'*(MAX_FILE+100))
                return Reader(original_open(current,mode,*args,**kwargs))
            return original_open(current,mode,*args,**kwargs)
        with patch.object(Path,'open',grow):
            with self.assertRaisesRegex(ValueError,'file-size'):self.plan()
        self.assertEqual(sizes,[MAX_FILE+1]);self.assertFalse(self.output.exists())

    def test_flat_directory_enumeration_is_capped_before_sorting(self):
        calls=[]
        class Many:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def __iter__(self):return self
            def __next__(self):
                calls.append(1)
                if len(calls)>MAX_ENTRIES+1:raise AssertionError('Unbounded enumeration')
                return object()
        with patch('recover_factory.os.scandir',return_value=Many()):
            with self.assertRaisesRegex(ValueError,'before enumeration'):self.plan()
        self.assertEqual(len(calls),MAX_ENTRIES+1)

    def test_apply_requires_exact_digest_and_stable_boundary(self):
        result=self.plan();before=self.files(self.source)
        with self.assertRaises(ValueError):apply(result,'wrong',True)
        with self.assertRaises(ValueError):apply(result,result['plan'])
        self.assertFalse(self.output.exists());self.assertEqual(before,self.files(self.source))

    def test_cached_manifest_or_decisions_cannot_change_after_approval(self):
        result=self.plan();result['manifest']+=b'\n'
        with self.assertRaisesRegex(ValueError,'Cached plan'):apply(result,result['plan'],True)
        result=self.plan();result['decisions']['register'][0]['reason']='Unreviewed change'
        with self.assertRaisesRegex(ValueError,'Cached plan'):apply(result,result['plan'],True)
        self.assertFalse(self.output.exists());self.assertFalse((self.parent/'.factory-recovery-backups').exists())

    def test_output_creation_race_does_not_mark_an_unowned_directory(self):
        result=self.plan();mkdir=Path.mkdir
        def race(path,*args,**kwargs):
            if path==self.output:
                mkdir(path);(path/'concurrent-user.txt').write_bytes(b'Preserve this unrelated output')
            return mkdir(path,*args,**kwargs)
        with patch.object(Path,'mkdir',race):
            with self.assertRaises(FileExistsError):apply(result,result['plan'],True)
        self.assertEqual(self.files(self.output),{'concurrent-user.txt':b'Preserve this unrelated output'})

    def test_bom_and_cr_text_are_parsed_without_rewriting_living_bytes(self):
        for root in (self.base,self.source):
            for path in root.rglob('*'):
                if path.is_file():path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r'))
        self.pin=rawhash((self.base/'manifest.json').read_bytes());before=self.files(self.source)
        result=self.plan();backup=apply(result,result['plan'],True)
        self.assertTrue(verify_output(self.output,backup,result['plan']))
        self.assertEqual((self.output/'learning-log.md').read_bytes(),before['learning-log.md'])

    def test_staged_recovery_preserves_source_evidence_and_unaffected_contract_hashes(self):
        result=self.plan();before=self.files(self.source);baseline=self.files(self.base)
        backup=apply(result,result['plan'],True)
        self.assertTrue(verify_output(self.output,backup,result['plan']))
        self.assertEqual(before,self.files(self.source));self.assertEqual(before,self.files(backup/'source'))
        after=self.files(self.output)
        for name,data in before.items():
            if name!='manifest.json':self.assertEqual(after[name],data)
        recovered=json.loads(after['manifest.json']);old=json.loads(baseline['manifest.json'])
        self.assertEqual(recovered['living'],old['living'])
        self.assertNotIn('obsolete.md',recovered['contracts'])
        for name,expected in old['contracts'].items():
            if name not in ('policy.md','obsolete.md'):self.assertEqual(recovered['contracts'][name],expected)
        self.assertEqual(gate_rows(after['verification.md'].decode())['G1']['required'],'no')
        self.assertTrue(assess(self.output,'pre-merge','synthetic-subject')) # No checks were promoted from NOT RUN.
        with self.assertRaises(ValueError):check(self.source,quiet=True)

    def test_partial_or_blanket_decisions_are_refused(self):
        for group in self.decisions:
            value=copy.deepcopy(self.decisions);value[group]=[]
            with self.assertRaises(ValueError):prepare(self.source,self.base,self.output,self.pin,self.reference,value)
        value=copy.deepcopy(self.decisions);value['accept_changed'].append({'path':'config.json','reason':'Blanket acceptance not allowed'})
        with self.assertRaises(ValueError):prepare(self.source,self.base,self.output,self.pin,self.reference,value)
        value=copy.deepcopy(self.decisions);value['register'][0]['path']='../escape'
        with self.assertRaises(ValueError):prepare(self.source,self.base,self.output,self.pin,self.reference,value)
        self.assertFalse(self.output.exists())

    def test_baseline_pin_manifest_semantics_and_core_deletion_are_refused(self):
        with self.assertRaises(ValueError):prepare(self.source,self.base,self.output,'0'*64,self.reference,self.decisions)
        path=self.source/'manifest.json';original=path.read_bytes();value=json.loads(original)
        value['contracts']['policy.md']=digest((self.source/'policy.md').read_bytes())
        path.write_bytes(dumps(value).encode())
        with self.assertRaises(ValueError):self.plan()
        path.write_bytes(original);(self.source/'.claude/skills/factory-intake/SKILL.md').unlink()
        with self.assertRaises(ValueError):self.plan()

    def test_config_policy_disagreement_and_malformed_living_state_refused(self):
        path=self.source/'config.json';original=path.read_bytes();value=json.loads(original)
        value['operations']={'done_videos':{'enabled':True}};path.write_bytes(dumps(value).encode())
        with self.assertRaisesRegex(ValueError,'controls disagree'):self.plan()
        path.write_bytes(original);(self.source/'task-plan.json').write_bytes(b'{bad json')
        with self.assertRaises(ValueError):self.plan()

    def test_duplicate_json_keys_and_unsafe_actual_paths_refused(self):
        path=self.source/'design-note.md';path.unlink();path=self.source/'ambiguous.json'
        path.write_bytes(b'{"key":1,"key":2}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.plan()
        path.unlink();(self.source/'trailing.').write_bytes(b'Synthetic')
        with self.assertRaises(ValueError):self.plan()

    def test_unsafe_names_and_reparse_entries_are_refused(self):
        for name in ('../x','a//b','C:/x','CON.txt','foo\\bar','file:ads','ending.','hidden\u202etxt',RESERVED.lower()):
            with self.assertRaises(ValueError):name_ok(name)
        redirected=self.source/'redirected';redirected.mkdir()
        original=Path.lstat
        class Reparse:
            def __init__(self,value):self.value=value;self.st_file_attributes=1024
            def __getattr__(self,name):return getattr(self.value,name)
        def lstat(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            return Reparse(value) if path==redirected else value
        with patch.object(Path,'lstat',lstat):
            with self.assertRaisesRegex(ValueError,'reparse'):self.plan()

    def test_completion_record_and_plan_cannot_be_rebound(self):
        result=self.plan();backup=apply(result,result['plan'],True)
        with self.assertRaises(ValueError):verify_output(self.output,backup,'0'*64)
        record=json.loads((backup/'recovery.json').read_bytes())
        record['plan_record']['reference']='Different unreviewed provenance'
        (backup/'recovery.json').write_bytes(dumps(record).encode())
        with self.assertRaises(ValueError):verify_output(self.output,backup,result['plan'])

    def test_output_and_backup_aliases_cannot_write_inputs(self):
        before=self.files(self.source)
        for output in (self.source/'new-output',self.source/'..'/'damaged'/'new-output',self.parent/'.factory-recovery-backups'):
            with self.assertRaises(ValueError):prepare(self.source,self.base,output,self.pin,self.reference,self.decisions)
        self.assertEqual(before,self.files(self.source))
        # A source named exactly as the derived backup parent must also be refused.
        alias=self.parent/'.factory-recovery-backups';self.source.rename(alias)
        with self.assertRaises(ValueError):prepare(alias,self.base,self.output,self.pin,self.reference,self.decisions)
        self.assertEqual(before,self.files(alias))

    @unittest.skipUnless(os.name=='nt','Windows namespace path regression')
    def test_windows_device_namespace_inputs_refused(self):
        for prefix in ('\\\\?\\','\\\\.\\'):
            with self.assertRaises(ValueError):prepare(Path(prefix+str(self.source)),self.base,self.output,self.pin,self.reference,self.decisions)

    def test_stale_plan_and_source_edits_during_backup_are_preserved(self):
        result=self.plan();path=self.source/'learning-log.md';path.write_bytes(b'Concurrent operator edit')
        with self.assertRaises(ValueError):apply(result,result['plan'],True)
        self.assertEqual(path.read_bytes(),b'Concurrent operator edit');self.assertFalse(self.output.exists())
        result=self.plan()
        from recover_factory import copy_snapshot
        def concurrent(root,snapshot,include_manifest=True):
            copy_snapshot(root,snapshot,include_manifest)
            if root.name=='source':path.write_bytes(b'Second concurrent edit')
        with patch('recover_factory.copy_snapshot',side_effect=concurrent):
            with self.assertRaises(ValueError):apply(result,result['plan'],True)
        self.assertEqual(path.read_bytes(),b'Second concurrent edit');self.assertFalse(self.output.exists())

    def test_corrupt_backup_refuses_output_before_manifest_write(self):
        result=self.plan()
        from recover_factory import copy_snapshot
        def corrupt(root,snapshot,include_manifest=True):
            copy_snapshot(root,snapshot,include_manifest)
            if root.name=='source':(root/'learning-log.md').write_bytes(b'Synthetic bad backup')
        with patch('recover_factory.copy_snapshot',side_effect=corrupt):
            with self.assertRaises(ValueError):apply(result,result['plan'],True)
        self.assertFalse(self.output.exists())

    def test_checked_partial_writes_complete_and_zero_progress_quarantines(self):
        real_open=Path.open
        class Partial:
            def __init__(self,stream,zero):self.stream=stream;self.zero=zero
            def __enter__(self):return self
            def __exit__(self,*args):return self.stream.__exit__(*args)
            def write(self,data):return 0 if self.zero else self.stream.write(data[:max(1,len(data)//2)])
            def flush(self):self.stream.flush()
            def fileno(self):return self.stream.fileno()
        result=self.plan()
        def partial(path,mode='r',*args,**kwargs):
            stream=real_open(path,mode,*args,**kwargs)
            return Partial(stream,False) if mode=='xb' and path==self.output/'manifest.json' else stream
        with patch.object(Path,'open',partial):backup=apply(result,result['plan'],True)
        self.assertTrue(verify_output(self.output,backup,result['plan']))
        self.output=self.parent/'zero-output';result=self.plan();before=self.files(self.source)
        def zero(path,mode='r',*args,**kwargs):
            stream=real_open(path,mode,*args,**kwargs)
            return Partial(stream,True) if mode=='xb' and path==self.output/'manifest.json' else stream
        with patch.object(Path,'open',zero):
            with self.assertRaises(OSError):apply(result,result['plan'],True)
        self.assertTrue((self.output/RESERVED).exists());self.assertEqual(before,self.files(self.source))
        with self.assertRaises((ValueError,OSError)):verify_output(self.output,result['backup_parent']/result['plan'],result['plan'])

    def test_process_crash_after_manifest_is_unconfirmed_without_completion(self):
        # os._exit bypasses exception cleanup: valid hashes alone must not prove completion.
        result=self.plan()
        args=[str(self.source),str(self.base),str(self.output),self.pin,self.reference,self.decisions]
        code="""import sys,json,os
sys.dont_write_bytecode=True
sys.path.insert(0,sys.argv[1])
import recover_factory as r
result=r.prepare(*json.loads(sys.argv[2]))
real=r.write_file
def crash(path,data):
    if path.name=='COMPLETED.json':os._exit(9)
    return real(path,data)
r.write_file=crash
r.apply(result,result['plan'],True)
"""
        process=subprocess.run([sys.executable,'-c',code,str(ROOT/'scripts'),json.dumps(args)],capture_output=True,text=True)
        self.assertEqual(process.returncode,9,process.stderr)
        check(self.output,quiet=True) # Snapshot is byte-valid but explicitly unconfirmed/quarantined.
        with self.assertRaises(OSError):verify_output(self.output,result['backup_parent']/result['plan'],result['plan'])

    def test_verified_snapshot_or_backup_mutation_is_rejected(self):
        result=self.plan();backup=apply(result,result['plan'],True)
        path=self.output/'learning-log.md';path.write_bytes(path.read_bytes()+b'Later edit')
        with self.assertRaises(ValueError):verify_output(self.output,backup,result['plan'])

    def test_cli_preview_and_wrong_approval_are_write_free(self):
        path=self.parent/'decisions.json';path.write_bytes(dumps(self.decisions).encode())
        command=[sys.executable,str(ROOT/'scripts/recover_factory.py'),'--factory',str(self.source),'--baseline',str(self.base),
                 '--output',str(self.output),'--baseline-manifest-sha256',self.pin,'--baseline-reference',self.reference,'--decisions',str(path)]
        before=self.files(self.source);result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('REVIEW PLAN:',result.stdout)
        self.assertFalse(self.output.exists())
        result=subprocess.run(command+['--apply','--stable-inputs','--approve-plan','wrong'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(before,self.files(self.source));self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
