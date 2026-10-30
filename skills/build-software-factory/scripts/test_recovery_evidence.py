"""Exercise the documented recovery/evidence invariants in isolated synthetic factories.

These fixtures manually apply explicitly named reviewed edits; no rebaseline helper
or external deployment is implemented or invoked.
"""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from gates import assess, gate_rows, policy_controls
from integrity import check, digest
from operations import controls
from scaffold import ROOT, render, validate
from status import record
from update_operations import prepare


class RecoveryEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'.software-factory';self.root.mkdir()
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'synthetic-package'}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(self.config,self.research)
        for name,body in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')

    def tearDown(self):self.tmp.cleanup()

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def args(self):
        return SimpleNamespace(task='T1',status='done',result='passed',evidence='SYNTHETIC fixture only; docs/evidence/subject-S/check.txt',revision='subject-S',environment='isolated fixture',check='synthetic observation',apply=True)

    def observations(self):
        lines=[]
        for line in (self.root/'verification.md').read_text().splitlines():
            if line.startswith('| ') and line.split('|')[1].strip() in ('G1','G2','G3','A1'):
                cells=[v.strip() for v in line.strip('|').split('|')]
                cells[2:4]=['Synthetic fixture observation; no application run','isolated fixture']
                cells[5:]=['subject-S','PASSED','docs/evidence/subject-S/check.txt','synthetic-package','2026-10-30T02:00:00Z','0']
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        (self.root/'verification.md').write_text('\n'.join(lines),encoding='utf-8')

    def test_broken_sources_block_status_gates_and_operations_without_mutation(self):
        for mode in ('added-runtime','contract-edit'):
            with self.subTest(mode=mode):
                path=self.root/'test-map.json' if mode=='added-runtime' else self.root/'policy.md'
                before=path.read_bytes() if path.exists() else None
                path.write_text('{}' if before is None else before.decode()+'\nUnreviewed change\n')
                current=self.snapshot()
                for operation in (lambda:record(self.root,self.args()),lambda:assess(self.root,'pre-merge','subject-S'),lambda:prepare(self.root,{})):
                    with self.assertRaises(ValueError):operation()
                    self.assertEqual(current,self.snapshot())
                if before is None:path.unlink()
                else:path.write_bytes(before)

    def test_selective_reviewed_recovery_preserves_customizations_and_living_flags(self):
        baseline=self.snapshot()
        # Explicitly reviewed immutable custom policy; runtime map remains external.
        policy=self.root/'policy.md';policy.write_text(policy.read_text()+'\nCustom accepted local rule.\n',encoding='utf-8')
        config=self.root/'config.json';value=json.loads(config.read_text());value['project']='Synthetic customized project';validate(value)
        config.write_text(json.dumps(value),encoding='utf-8')
        verification=self.root/'verification.md';verification.write_text(verification.read_text().replace('| yes |','| no |',1),encoding='utf-8')
        task_map=self.root/'test-map.json';task_map.write_text('{"synthetic":"map"}')
        with self.assertRaises(ValueError):check(self.root,quiet=True)
        current=self.snapshot()
        backup=self.base/'private-recovery-backup';backup.mkdir()
        for name,data in current.items():
            path=backup/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.assertEqual(current,{p.relative_to(backup).as_posix():p.read_bytes() for p in backup.rglob('*') if p.is_file()})
        task_map.replace(self.base/'test-map.json')
        manifest=json.loads(baseline['manifest.json'])
        for name in ('policy.md','config.json'):manifest['contracts'][name]=digest((self.root/name).read_bytes())
        (self.root/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        result=check(self.root,quiet=True)
        self.assertEqual(result['living'],json.loads(baseline['manifest.json'])['living'])
        for name,expected in json.loads(baseline['manifest.json'])['contracts'].items():
            if name not in ('policy.md','config.json'):self.assertEqual(result['contracts'][name],expected)
        self.assertIn('Custom accepted local rule',policy.read_text())
        self.assertEqual(gate_rows(verification.read_text())['G1']['required'],'no')
        self.assertEqual(policy_controls(policy.read_text()),controls(value))
        self.assertEqual(prepare(self.root,{})[0],self.root)

    def test_named_immutable_addition_can_be_reviewed_without_open_living_area(self):
        manifest=json.loads((self.root/'manifest.json').read_text())
        path=self.root/'accepted-contract.md';path.write_text('Synthetic reviewed immutable design.\n')
        with self.assertRaises(ValueError):check(self.root,quiet=True)
        manifest['contracts']['accepted-contract.md']=digest(path.read_bytes())
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        check(self.root,quiet=True)
        path.write_text('Unreviewed replacement')
        with self.assertRaises(ValueError):check(self.root,quiet=True)

    def test_unsafe_or_reclassified_manifest_is_not_recovery(self):
        original=(self.root/'manifest.json').read_bytes()
        for mode in ('traversal','living-reclassification','legacy'):
            manifest=json.loads(original)
            if mode=='traversal':manifest['contracts']['../outside.txt']='0'*64
            elif mode=='living-reclassification':manifest['living'].append('policy.md');manifest['contracts'].pop('policy.md')
            else:manifest['schema']=1
            (self.root/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):check(self.root,quiet=True)
        (self.root/'manifest.json').write_bytes(original)
        check(self.root,quiet=True)

    def test_evidence_storage_does_not_relabel_tested_or_deployed_subject(self):
        before=check(self.root,quiet=True)['contracts']
        evidence=self.base/'docs/evidence/subject-S/check.txt';evidence.parent.mkdir(parents=True);evidence.write_text('Synthetic observation only')
        self.observations()
        with redirect_stdout(io.StringIO()):record(self.root,self.args())
        (self.root/'release-handoff.md').write_text('Tested/deployed subject: subject-S\nEvidence storage revision: storage-E (synthetic identities)\n')
        self.assertEqual(check(self.root,quiet=True)['contracts'],before)
        self.assertEqual(assess(self.root,'pre-merge','subject-S'),[])
        self.assertEqual(assess(self.root,'post-merge','subject-S','synthetic-package'),[])
        self.assertTrue(assess(self.root,'post-merge','storage-E','synthetic-package'))
        self.assertTrue(assess(self.root,'pre-merge','storage-E'))
        self.assertEqual(json.loads((self.root/'task-plan.json').read_text())['events'][-1]['revision'],'subject-S')

    def test_evidence_home_keeps_missing_and_optional_checks_truthful(self):
        text=(self.root/'verification.md').read_text();lines=[]
        for line in text.splitlines():
            if line.startswith('| G2 |'):
                cells=line.split('|');cells[5]=' no ';cells[7]=' FAILED ';line='|'.join(cells)
            lines.append(line)
        (self.root/'verification.md').write_text('\n'.join(lines))
        self.assertTrue(assess(self.root,'pre-merge','subject-S'))  # Still-required NOT RUN.
        self.assertEqual(gate_rows((self.root/'verification.md').read_text())['G2']['result'],'FAILED')
        self.assertEqual(gate_rows((self.root/'verification.md').read_text())['G2']['required'],'no')


if __name__=='__main__':unittest.main()
