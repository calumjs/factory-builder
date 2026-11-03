"""Explicit review adoption uses synthetic factories and the reviewed updater."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
import update_operations as updater
from test_review_records import supplied_round
from incremental_records import preview, apply
import review_records as rr


class ReviewMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(self.config,self.research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        for name in updater.PRE_REVIEW_RUNTIME:self.contract('dashboard/'+name,(ROOT/'scripts/fixtures'/('pre_review_'+name[:-3]+'.txt')).read_bytes())
        self.changes={'review':{'record_schema':1,'required_approvals':1,'independent':True}}
    def contract(self,name,raw):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        target=self.root/'manifest.json';manifest=json.loads(target.read_bytes());manifest['contracts'][name]=digest(raw);target.write_bytes(json.dumps(manifest).encode())
    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def prepare(self,**kwargs):return updater.prepare(self.root,self.changes,review_workflow=True,**kwargs)
    def adopt(self):
        prepared=self.prepare();return updater.apply(*prepared,prepared[-1])
    def test_explicit_pristine_adoption_is_write_free_then_adds_complete_compatible_bundle(self):
        before=self.snapshot();prepared=self.prepare();self.assertEqual(before,self.snapshot())
        root,old,new,token=prepared
        self.assertIsNone(old['dashboard/review_records.py']);self.assertIsNone(old['review-guide.md'])
        self.assertEqual(rr.parse(new['release-handoff.md'].decode()),rr.empty())
        self.assertEqual(gate_rows(new['verification.md'].decode())['Q1']['required'],'yes')
        oldrows=[line for line in before['verification.md'].splitlines(keepends=True) if line.startswith(b'| ') and not line.startswith(b'| Gate')]
        newrows=[line for line in new['verification.md'].splitlines(keepends=True) if line.startswith(b'| ') and not line.startswith((b'| Gate',b'| Q1'))]
        self.assertEqual(oldrows,newrows)
        backup=updater.apply(*prepared,token);check(root,quiet=True)
        added=json.loads((backup/'added-files.json').read_text());self.assertIn('dashboard/review_records.py',added);self.assertIn('review-guide.md',added)
        self.assertEqual(before['upstream-provenance.json'],(root/'upstream-provenance.json').read_bytes())
        self.assertEqual(self.prepare()[2],{})
    def test_adoption_requires_flag_and_retains_explicit_legacy_zero(self):
        with self.assertRaisesRegex(ValueError,'explicit --review-workflow'):updater.prepare(self.root,self.changes)
        self.changes={'review':{'record_schema':1}}
        prepared=self.prepare();self.assertEqual(gate_rows(prepared[2]['verification.md'].decode())['Q1']['required'],'no')
    def test_custom_and_mixed_consumers_or_skills_are_refused_without_writes(self):
        for name in ('operations.py','gates.py','dashboard.py'):
            path='dashboard/'+name;old=(self.root/path).read_bytes()
            self.contract(path,(ROOT/'scripts'/name).read_bytes());before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'mixed'):self.prepare()
            self.assertEqual(before,self.snapshot());self.contract(path,old)
        name='.claude/skills/factory-verify/SKILL.md';self.contract(name,(self.root/name).read_bytes()+b'\ncustom scope\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized'):self.prepare()
        self.assertEqual(before,self.snapshot())
    def test_phase_guide_and_parser_customizations_are_never_overwritten(self):
        for name in ('phase-release-guide.md','review-guide.md','dashboard/review_records.py'):
            original=(self.root/name).read_bytes() if (self.root/name).exists() else None
            self.contract(name,b'custom instructions\n');before=self.snapshot()
            with self.assertRaises(ValueError):self.prepare()
            self.assertEqual(before,self.snapshot())
            if original is not None:self.contract(name,original)
            else:
                (self.root/name).unlink();manifest=json.loads((self.root/'manifest.json').read_bytes());del manifest['contracts'][name];(self.root/'manifest.json').write_text(json.dumps(manifest))
    def test_captured_unchanged_dependency_and_added_file_races_refuse_apply(self):
        prepared=self.prepare();path=self.root/'dashboard/recipes.py';path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n'))
        with self.assertRaises(ValueError):updater.apply(*prepared,prepared[-1])
        self.assertFalse((self.root/'review-guide.md').exists())
        prepared=self.prepare();(self.root/'review-guide.md').write_bytes(b'concurrent')
        with self.assertRaises(ValueError):updater.apply(*prepared,prepared[-1])
        self.assertEqual((self.root/'review-guide.md').read_bytes(),b'concurrent')
    def test_review_only_policy_change_resets_q1_preserving_waivers_history_and_other_raw_rows(self):
        self.adopt();config=json.loads((self.root/'config.json').read_bytes())
        round1=supplied_round(config);prepared=preview(self.root,'review',round1);apply(*prepared,prepared[-1])
        path=self.root/'verification.md';lines=path.read_bytes().splitlines(keepends=True)
        for i,line in enumerate(lines):
            if line.startswith(b'| Q1 |'):
                cells=line.decode().split('|');cells[5]=' no ';cells[6]=' S1 ';cells[7]=' FAILED ';cells[8]=' prior failure ';lines[i]='|'.join(cells).encode()
            elif line.startswith(b'| G1 |'):lines[i]=line.replace(b'| yes |',b'| no |').replace(b'| NOT RUN |',b'| FAILED |')
        raw=b''.join(line.replace(b'\n',b'\r\n') if i%2 else line for i,line in enumerate(lines)).rstrip(b'\r\n');path.write_bytes(raw)
        other=[line for line in raw.splitlines(keepends=True) if line.startswith(b'| ') and not line.startswith(b'| Q1')]
        self.changes={'review':{'required_approvals':2}}
        prepared=self.prepare();proposed=prepared[2]['verification.md'];rows=gate_rows(proposed.decode())
        self.assertEqual((rows['Q1']['required'],rows['Q1']['result']),('no','NOT RUN'));self.assertIn(b'> | Q1 |',proposed);self.assertIn(b'prior failure',proposed)
        self.assertEqual(other,[line for line in proposed.splitlines(keepends=True) if line.startswith(b'| ') and not line.startswith(b'| Q1')])
        self.assertNotIn('release-handoff.md',prepared[2]);updater.apply(*prepared,prepared[-1]);self.assertEqual(self.prepare()[2],{})
    def test_optional_receipt_accounts_for_new_runtime_dependency(self):
        prepared=self.prepare(migration_receipt=True);receipt=json.loads(prepared[2][updater.MIGRATION_RECEIPTS])['receipts'][0]
        entry=next(row for row in receipt['components'] if row['path']=='dashboard/review_records.py')
        self.assertIsNone(entry['before_raw_sha256']);self.assertIsNone(receipt['installed_builder']['verified_source_revision'])
        self.assertEqual(receipt['scope'],'runtime-only')
    def test_raw_unchanged_guard_changes_review_digest(self):
        first=self.prepare();path=self.root/'dashboard/recipes.py';raw=path.read_bytes();path.write_bytes(raw.replace(b'\n',b'\r\n'))
        second=self.prepare();self.assertEqual(first[2],second[2]);self.assertNotEqual(first[-1],second[-1])

    def test_compact_phase_noop_retains_opted_in_routing_and_captures_guide(self):
        self.adopt();prepared=updater.prepare(self.root,{},compact_phases=True)
        self.assertEqual(prepared[2],{});self.assertIn('review-guide.md',prepared[1])
        self.assertIn(b'review-guide.md',prepared[1]['phase-verify-guide.md'])

    def test_interruption_before_manifest_cannot_claim_complete_adoption(self):
        prepared=self.prepare();manifest=(self.root/'manifest.json').read_bytes();replace=updater.os.replace
        def fail_before_manifest(source,destination):
            if Path(destination)==self.root/'manifest.json':raise OSError('synthetic interrupted manifest write')
            return replace(source,destination)
        with patch.object(updater.os,'replace',side_effect=fail_before_manifest):
            with self.assertRaises(OSError):updater.apply(*prepared,prepared[-1])
        self.assertEqual((self.root/'manifest.json').read_bytes(),manifest)
        with self.assertRaises(ValueError):check(self.root,quiet=True)
        self.assertFalse((self.root/'.operations-update.lock').exists())


if __name__=='__main__':unittest.main()
