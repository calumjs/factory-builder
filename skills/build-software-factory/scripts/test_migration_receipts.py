"""Opt-in runtime byte receipts stay within the reviewed update transaction."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from integrity import check, digest
from scaffold import ROOT, render
import update_operations as updater


class MigrationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        # Deliberately distinct raw line endings verify raw, not normalized hashes.
        self.old_gate=(ROOT/'scripts/fixtures/v1_17_gates.txt').read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
        self.contract('dashboard/gates.py',self.old_gate)
        provenance=json.loads((self.root/'upstream-provenance.json').read_text(encoding='utf-8'))
        provenance['component'].update(version='historical-whole-factory-label',source_revision='a'*40)
        provenance['upstream']['repository_url']='https://private.invalid/application-origin'
        self.provenance=json.dumps(provenance,separators=(',',':')).encode('utf-8')
        self.contract('upstream-provenance.json',self.provenance)

    def contract(self,name,data):
        (self.root/name).write_bytes(data)
        path=self.root/'manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
        manifest['contracts'][name]=digest(data);path.write_bytes(json.dumps(manifest).encode('utf-8'))

    def remove_contract(self,name):
        (self.root/name).unlink()
        path=self.root/'manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
        del manifest['contracts'][name];path.write_bytes(json.dumps(manifest).encode('utf-8'))

    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def proposed(self,**kwargs):
        return updater.prepare(self.root,kwargs.pop('changes',{}),migration_receipt=True,**({'gate_runtime':True}|kwargs))

    def record(self,prepared):return updater.apply(*prepared,prepared[-1])

    def ledger(self):return json.loads((self.root/updater.MIGRATION_RECEIPTS).read_text(encoding='utf-8'))

    def sample_ledger(self):return json.loads(self.proposed()[2][updater.MIGRATION_RECEIPTS])

    def old_context(self):
        self.contract('dashboard/integrity.py',(ROOT/'scripts/fixtures/v1_13_integrity.txt').read_bytes())

    def test_first_receipt_binds_actual_raw_component_bytes_and_preserves_provenance(self):
        before=self.snapshot();prepared=self.proposed();root,old,new,token=prepared
        self.assertEqual(before,self.snapshot());self.assertIsNone(old[updater.MIGRATION_RECEIPTS])
        self.assertEqual(set(new),{'dashboard/gates.py',updater.MIGRATION_RECEIPTS,'manifest.json'})
        receipt=json.loads(new[updater.MIGRATION_RECEIPTS])['receipts'][0]
        self.assertEqual(receipt['scope'],'runtime-only')
        self.assertEqual(receipt['components'],[{'path':'dashboard/gates.py','before_raw_sha256':hashlib.sha256(self.old_gate).hexdigest(),
                                               'after_raw_sha256':hashlib.sha256(new['dashboard/gates.py']).hexdigest()}])
        self.assertNotEqual(receipt['components'][0]['before_raw_sha256'],digest(self.old_gate))
        self.assertIsNone(receipt['installed_builder']['verified_source_revision'])
        self.assertEqual(receipt['installed_builder']['declared_version'],json.loads((ROOT.parents[1]/'.claude-plugin/plugin.json').read_text(encoding='utf-8'))['version'])
        self.assertNotIn('private.invalid',json.dumps(receipt));self.assertNotIn('historical-whole-factory-label',json.dumps(receipt))
        fingerprints={name:{'before':hashlib.sha256(old[name]).hexdigest() if old[name] is not None else None,
                            'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(new.items())}
        expected=hashlib.sha256(updater.dumps({'factory':str(root),'files':fingerprints}).encode('utf-8')).hexdigest()
        self.assertEqual(token,expected);self.assertEqual(self.proposed(),prepared)
        backup=self.record(prepared)
        self.assertEqual((backup/'dashboard/gates.py').read_bytes(),self.old_gate)
        self.assertIn(updater.MIGRATION_RECEIPTS,json.loads((backup/'added-files.json').read_text(encoding='utf-8')))
        self.assertEqual((root/'upstream-provenance.json').read_bytes(),self.provenance)
        after=self.snapshot()
        for name,data in before.items():
            if name not in ('factory/dashboard/gates.py','factory/manifest.json'):self.assertEqual(after[name],data)
        check(root,quiet=True)

    def test_append_preserves_prior_receipt_and_backs_up_original_ledger_bytes(self):
        self.record(self.proposed());prior=self.ledger();raw=(self.root/updater.MIGRATION_RECEIPTS).read_bytes()
        self.old_context();before=self.snapshot()
        prepared=self.proposed(gate_runtime=False,context_runtime=True)
        self.assertEqual(before,self.snapshot())
        next_ledger=json.loads(prepared[2][updater.MIGRATION_RECEIPTS])
        self.assertEqual(next_ledger['receipts'][:-1],prior['receipts'])
        self.assertEqual([item['path'] for item in next_ledger['receipts'][-1]['components']],['dashboard/integrity.py'])
        backup=self.record(prepared);self.assertEqual((backup/updater.MIGRATION_RECEIPTS).read_bytes(),raw)
        self.assertEqual((self.root/'upstream-provenance.json').read_bytes(),self.provenance);check(self.root,quiet=True)

    def test_no_flag_noop_and_unrelated_changes_do_not_invent_runtime_receipts(self):
        ordinary=updater.prepare(self.root,{},gate_runtime=True)
        self.assertNotIn(updater.MIGRATION_RECEIPTS,ordinary[1]);self.assertNotIn(updater.MIGRATION_RECEIPTS,ordinary[2])
        self.record(ordinary);before=self.snapshot()
        with patch('update_operations.installed_builder_labels',side_effect=AssertionError('no label reads for noop')):
            noop=self.proposed();self.assertFalse(noop[2]);self.assertIsNone(self.record(noop))
            unrelated=self.proposed(changes={'issue_intake':{'mode':'continuous'}})
        self.assertNotIn(updater.MIGRATION_RECEIPTS,unrelated[2]);self.assertEqual(before,self.snapshot())
        with self.assertRaisesRegex(ValueError,'explicit runtime migration flag'):
            updater.prepare(self.root,{},migration_receipt=True)
        self.assertEqual(before,self.snapshot())

    def test_mixed_update_receipt_lists_only_changed_runtime_components(self):
        before=self.snapshot();prepared=self.proposed(changes={'done_videos':{'enabled':True}})
        self.assertIn('config.json',prepared[2]);self.assertIn('verification.md',prepared[2])
        receipt=json.loads(prepared[2][updater.MIGRATION_RECEIPTS])['receipts'][0]
        self.assertEqual(receipt['scope'],'runtime-only')
        self.assertEqual([item['path'] for item in receipt['components']],['dashboard/gates.py'])
        self.assertEqual(before,self.snapshot())

    def test_added_dependency_and_receipt_are_both_in_added_file_backup_accounting(self):
        self.old_context();self.remove_contract('dashboard/learning_table.py')
        prepared=self.proposed(context_runtime=True)
        receipt=json.loads(prepared[2][updater.MIGRATION_RECEIPTS])['receipts'][0]
        components={item['path']:item for item in receipt['components']}
        self.assertIsNone(components['dashboard/learning_table.py']['before_raw_sha256'])
        self.assertEqual(components['dashboard/learning_table.py']['after_raw_sha256'],hashlib.sha256(prepared[2]['dashboard/learning_table.py']).hexdigest())
        backup=self.record(prepared);added=json.loads((backup/'added-files.json').read_text(encoding='utf-8'))
        self.assertEqual(set(added),{updater.MIGRATION_RECEIPTS,'dashboard/learning_table.py'});check(self.root,quiet=True)

    def test_unknown_custom_runtime_refused_without_receipt_or_provenance_changes(self):
        self.contract('dashboard/gates.py',self.old_gate+b'\n# synthetic custom runtime\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):self.proposed()
        self.assertEqual(before,self.snapshot());self.assertFalse((self.root/updater.MIGRATION_RECEIPTS).exists())

    def test_strict_schema_rejects_unsupported_or_fabricated_claims_without_rewriting(self):
        good=self.sample_ledger()
        variants=[]
        for mutation in ('version','boolean','scope','source','path','duplicate','hash','nochange','extra','label'):
            value=copy.deepcopy(good);receipt=value['receipts'][0];component=receipt['components'][0]
            if mutation=='version':value['schema_version']=2
            elif mutation=='boolean':value['schema_version']=True
            elif mutation=='scope':receipt['scope']='whole-factory'
            elif mutation=='source':receipt['installed_builder']['verified_source_revision']='a'*40
            elif mutation=='path':component['path']='../private-origin'
            elif mutation=='duplicate':receipt['components'].append(copy.deepcopy(component))
            elif mutation=='hash':component['after_raw_sha256']='not-a-hash'
            elif mutation=='nochange':component['after_raw_sha256']=component['before_raw_sha256']
            elif mutation=='extra':receipt['attested']=True
            elif mutation=='label':receipt['installed_builder']['declared_version']='private\nlabel'
            variants.append(json.dumps(value).encode('utf-8'))
        variants += [b'{"schema_version":1,"schema_version":1,"receipts":[]}',b'{"schema_version":1,"receipts":[NaN]}',b'{broken']
        for raw in variants:
            with self.subTest(raw=raw[:50]):
                self.contract(updater.MIGRATION_RECEIPTS,raw);before=self.snapshot()
                with self.assertRaises(ValueError):self.proposed()
                self.assertEqual(before,self.snapshot())

    def test_unknown_receipt_schema_is_preserved_without_receipt_opt_in(self):
        raw=b'{"schema_version":99,"custom":"preserve"}\n';self.contract(updater.MIGRATION_RECEIPTS,raw)
        prepared=updater.prepare(self.root,{},gate_runtime=True)
        self.assertNotIn(updater.MIGRATION_RECEIPTS,prepared[2]);self.record(prepared)
        self.assertEqual((self.root/updater.MIGRATION_RECEIPTS).read_bytes(),raw)

    def test_size_and_history_limits_refuse_before_read_or_trimming(self):
        source=self.root/updater.MIGRATION_RECEIPTS
        source.write_bytes(b' '*(updater.MAX_RECEIPT_BYTES+1))
        with patch.object(Path,'open',side_effect=AssertionError('must not read oversized receipt')):
            with self.assertRaisesRegex(ValueError,'bounded regular file'):self.proposed()
        source.unlink()
        ledger=self.sample_ledger();ledger['receipts']*=updater.MAX_RECEIPTS
        raw=updater.dumps(ledger).encode('utf-8');self.assertLess(len(raw),updater.MAX_RECEIPT_BYTES)
        self.contract(updater.MIGRATION_RECEIPTS,raw);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'history limit reached'):self.proposed()
        self.assertEqual(before,self.snapshot())
        oversized_history=copy.deepcopy(ledger);oversized_history['receipts'].append(ledger['receipts'][0])
        with self.assertRaisesRegex(ValueError,'history limit'):updater.migration_receipts(json.dumps(oversized_history).encode('utf-8'))
        # Also exercise the generated-byte cap without creating a large fixture.
        self.remove_contract(updater.MIGRATION_RECEIPTS)
        with patch('update_operations.MAX_RECEIPT_BYTES',10),self.assertRaisesRegex(ValueError,'size limit reached'):self.proposed()
        self.assertFalse(source.exists())

    def test_wrong_digest_and_concurrent_receipt_creation_preserve_new_data(self):
        prepared=self.proposed();before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'exact --approve-plan'):updater.apply(*prepared,'wrong')
        self.assertEqual(before,self.snapshot())
        self.contract(updater.MIGRATION_RECEIPTS,b'{"schema_version":1,"receipts":[]}\n');concurrent=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):self.record(prepared)
        self.assertEqual(concurrent,self.snapshot());self.assertFalse((self.base/'.factory-update-backups').exists())

    def test_concurrent_receipt_edit_changes_plan_and_refuses_prior_approval(self):
        self.record(self.proposed());self.old_context();prepared=self.proposed(context_runtime=True)
        ledger=self.ledger();ledger['receipts'][0]['installed_builder']['declared_version']='reviewed-other-label'
        self.contract(updater.MIGRATION_RECEIPTS,json.dumps(ledger).encode('utf-8'));before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):self.record(prepared)
        new=self.proposed(context_runtime=True);self.assertNotEqual(prepared[-1],new[-1])
        with self.assertRaisesRegex(ValueError,'exact --approve-plan'):updater.apply(*new,prepared[-1])
        self.assertEqual(before,self.snapshot())

    def test_raw_receipt_edit_is_detected_even_when_normalized_manifest_digest_matches(self):
        self.record(self.proposed());self.old_context();prepared=self.proposed(context_runtime=True)
        path=self.root/updater.MIGRATION_RECEIPTS;old=path.read_bytes();changed=old.replace(b'\n',b'\r\n')
        self.assertNotEqual(old,changed);self.assertEqual(digest(old),digest(changed))
        path.write_bytes(changed);check(self.root,quiet=True);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):self.record(prepared)
        self.assertEqual(before,self.snapshot())

    def test_declared_metadata_is_not_a_verified_revision_and_no_git_lookup_occurs(self):
        original=updater.receipt_bytes
        metadata_path=ROOT.parents[1]/'.claude-plugin/plugin.json'
        def metadata(path,*args,**kwargs):
            if path==metadata_path:return b'{"name":"synthetic-builder","version":"declared-dirty-label","source_revision":"ffffffff","repository":"private-origin"}'
            return original(path,*args,**kwargs)
        with patch('update_operations.receipt_bytes',side_effect=metadata),patch.object(subprocess,'Popen',side_effect=AssertionError('no Git/provider lookup')):
            receipt=json.loads(self.proposed()[2][updater.MIGRATION_RECEIPTS])['receipts'][0]
        self.assertEqual(receipt['installed_builder'],{'declared_name':'synthetic-builder','declared_version':'declared-dirty-label','verified_source_revision':None})
        self.assertNotIn('private-origin',json.dumps(receipt));self.assertNotIn('ffffffff',json.dumps(receipt))
        self.assertEqual((self.root/'upstream-provenance.json').read_bytes(),self.provenance)

    def test_new_label_changes_preview_digest_and_metadata_limits_are_strict(self):
        labels={'declared_name':'synthetic','declared_version':'label-one','verified_source_revision':None}
        with patch('update_operations.installed_builder_labels',return_value=labels):first=self.proposed()
        with patch('update_operations.installed_builder_labels',return_value={**labels,'declared_version':'label-two'}):second=self.proposed()
        self.assertNotEqual(first[-1],second[-1]);self.assertEqual(first[2]['dashboard/gates.py'],second[2]['dashboard/gates.py'])
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'exact --approve-plan'):updater.apply(*second,first[-1])
        self.assertEqual(before,self.snapshot())
        fake=self.base/'installed'/'skills'/'builder';fake.mkdir(parents=True)
        metadata=fake.parents[1]/'.claude-plugin'/'plugin.json';metadata.parent.mkdir()
        with patch('update_operations.ROOT',fake):
            self.assertEqual(updater.installed_builder_labels(),{'declared_name':None,'declared_version':None,'verified_source_revision':None})
            for raw in (b'{"version":"a","version":"b"}',b'{"version":NaN}',json.dumps({'version':'x'*129}).encode('utf-8')):
                metadata.write_bytes(raw)
                with self.assertRaises(ValueError):updater.installed_builder_labels()
            metadata.write_bytes(b' '*65537)
            with patch.object(Path,'open',side_effect=AssertionError('oversized metadata must not be read')):
                with self.assertRaisesRegex(ValueError,'bounded regular file'):updater.installed_builder_labels()

    def test_failure_before_manifest_never_reports_success_and_keeps_recovery_material(self):
        prepared=self.proposed();old_manifest=(self.root/'manifest.json').read_bytes()
        original_replace=os.replace;order=[]
        def fail_manifest(source,destination):
            name=Path(destination).relative_to(self.root).as_posix();order.append(name)
            if name=='manifest.json':
                self.assertEqual((self.root/'dashboard/gates.py').read_bytes(),prepared[2]['dashboard/gates.py'])
                self.assertEqual((self.root/updater.MIGRATION_RECEIPTS).read_bytes(),prepared[2][updater.MIGRATION_RECEIPTS])
                raise OSError('synthetic interruption before manifest')
            return original_replace(source,destination)
        output=io.StringIO()
        argv=['update_operations.py','--factory',str(self.root),'--gate-runtime','--migration-receipt','--apply','--approve-plan',prepared[-1]]
        with patch.object(sys,'argv',argv),patch('update_operations.os.replace',side_effect=fail_manifest),redirect_stdout(output):
            with self.assertRaisesRegex(OSError,'synthetic interruption'):updater.main()
        self.assertEqual(order[-1],'manifest.json');self.assertNotIn('APPLIED narrow',output.getvalue())
        self.assertEqual((self.root/'manifest.json').read_bytes(),old_manifest)
        backup=self.base/'.factory-update-backups'/prepared[-1]
        self.assertEqual((backup/'manifest.json').read_bytes(),old_manifest)
        self.assertEqual((backup/'dashboard/gates.py').read_bytes(),self.old_gate)
        self.assertIn(updater.MIGRATION_RECEIPTS,json.loads((backup/'added-files.json').read_text(encoding='utf-8')))
        self.assertFalse((self.root/'.operations-update.lock').exists());self.assertFalse(list(self.root.glob('.operations-*.tmp')))
        self.assertEqual((self.root/'upstream-provenance.json').read_bytes(),self.provenance)
        with self.assertRaises(ValueError):check(self.root,quiet=True)

    def test_component_failure_occurs_before_receipt_and_leaves_original_component(self):
        prepared=self.proposed()
        with patch('update_operations.os.replace',side_effect=OSError('synthetic component failure')):
            with self.assertRaises(OSError):self.record(prepared)
        self.assertFalse((self.root/updater.MIGRATION_RECEIPTS).exists())
        self.assertEqual((self.root/'dashboard/gates.py').read_bytes(),self.old_gate);check(self.root,quiet=True)

    def test_cli_preview_is_write_free_and_labels_runtime_only_scope(self):
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.root),
                               '--gate-runtime','--migration-receipt'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,self.snapshot())
        self.assertIn('RUNTIME-ONLY RECEIPT:',result.stdout);self.assertIn('declared version is not verified provenance',result.stdout)
        self.assertIn('FILE migration-receipts.json raw SHA256: missing ->',result.stdout)
        self.assertIn('"verified_source_revision": null',result.stdout);self.assertNotIn('private.invalid',result.stdout)


if __name__=='__main__':unittest.main()
