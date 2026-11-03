"""Known v1.17 guidance upgrades only under a reviewed delivery plan."""
import json
from pathlib import Path
import tempfile
import unittest

from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
from update_operations import COMPATIBLE_DELIVERY_V117, COMPATIBLE_GATE_V117, apply, prepare


class V117GuidanceMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.factory=Path(self.temp.name)/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(config,research).items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        manifest_path=self.factory/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        for phase in ('verify','release'):
            addon=(ROOT/f'scripts/fixtures/v1_17_delivery_{phase}.txt').read_bytes()
            self.assertEqual(digest(addon),COMPATIBLE_DELIVERY_V117[phase])
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            # Existing project instructions outside the recognized addendum stay owned by the project.
            (self.factory/name).write_bytes(b'---\nname: factory-'+phase.encode()+b'\ndescription: Synthetic retained skill\n---\n\nProject-specific retained instruction.\n\n'+addon+b'\n')
            manifest['contracts'][name]=digest((self.factory/name).read_bytes())
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        path=self.factory/'verification.md'
        lines=path.read_text(encoding='utf-8').splitlines()
        for index,line in enumerate(lines):
            if line.startswith('| G1 |'):
                cells=[cell.strip() for cell in line.strip().strip('|').split('|')]
                cells[4:]=['no','S1','FAILED','synthetic-failure.log','fixture','2026-01-01T00:00:00Z','1']
                lines[index]='| '+' | '.join(cells)+' |'
        path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
        check(self.factory,quiet=True)

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix():p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def test_known_addenda_need_explicit_preview_and_preserve_backup_history(self):
        before=self.snapshot();self.assertFalse(prepare(self.factory,{})[2]);self.assertEqual(before,self.snapshot())
        root,old,new,plan=prepare(self.factory,{},delivery_update=True)
        self.assertEqual(before,self.snapshot())
        with self.assertRaises(ValueError):apply(root,old,new,plan,'wrong')
        self.assertEqual(before,self.snapshot())
        for phase in ('verify','release'):
            text=new[f'.claude/skills/factory-{phase}/SKILL.md'].decode('utf-8')
            self.assertIn('Project-specific retained instruction.',text)
            self.assertEqual(text.count('<!-- factory-delivery-update:start -->'),1)
        self.assertIn('optimistic',new['.claude/skills/factory-verify/SKILL.md'].decode('utf-8'))
        self.assertIn('Retry after failed G3',new['.claude/skills/factory-release/SKILL.md'].decode('utf-8'))
        backup=apply(root,old,new,plan,plan)
        for name in ('.claude/skills/factory-verify/SKILL.md','.claude/skills/factory-release/SKILL.md','verification.md'):
            self.assertEqual((backup/name).read_bytes(),before[name])
        for name in ('config.json','task-plan.json','learning-log.md','release-handoff.md','upstream-provenance.json'):
            self.assertEqual((root/name).read_bytes(),before[name])
        text=(root/'verification.md').read_text(encoding='utf-8')
        self.assertIn('synthetic-failure.log',text)
        self.assertEqual(gate_rows(text)['G1']['required'],'no')
        self.assertEqual(gate_rows(text)['G1']['result'],'NOT RUN')
        check(root,quiet=True)

    def test_customized_prior_addendum_is_refused_without_writes(self):
        name='.claude/skills/factory-release/SKILL.md';path=self.factory/name
        path.write_bytes(path.read_bytes().replace(b'<!-- factory-delivery-update:end -->',b'Custom operator instruction.\n<!-- factory-delivery-update:end -->'))
        manifest_path=self.factory/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['contracts'][name]=digest(path.read_bytes());manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized or unsupported delivery addendum'):
            prepare(self.factory,{},delivery_update=True)
        self.assertEqual(before,self.snapshot())

    def test_known_gate_diagnostic_runtime_is_explicit_and_custom_copy_refused(self):
        name='dashboard/gates.py';path=self.factory/name
        prior=(ROOT/'scripts/fixtures/v1_17_gates.txt').read_bytes()
        self.assertEqual(digest(prior),COMPATIBLE_GATE_V117['gates.py'])
        path.write_bytes(prior)
        manifest_path=self.factory/'manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        manifest['contracts'][name]=digest(prior);manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
        before=self.snapshot();self.assertFalse(prepare(self.factory,{})[2])
        root,old,new,plan=prepare(self.factory,{},gate_runtime=True)
        self.assertEqual(set(new),{name,'manifest.json'});self.assertEqual(before,self.snapshot())
        backup=apply(root,old,new,plan,plan)
        self.assertEqual((backup/name).read_bytes(),prior)
        self.assertEqual(path.read_bytes(),(ROOT/'scripts/gates.py').read_bytes())
        for preserved in ('config.json','policy.md','verification.md','task-plan.json','learning-log.md'):
            self.assertEqual((root/preserved).read_bytes(),before[preserved])
        check(root,quiet=True)
        path.write_bytes(prior+b'\n# SYNTHETIC operator customization\n')
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'));manifest['contracts'][name]=digest(path.read_bytes())
        manifest_path.write_text(json.dumps(manifest),encoding='utf-8');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):
            prepare(root,{},gate_runtime=True)
        self.assertEqual(before,self.snapshot())


if __name__=='__main__':unittest.main()
