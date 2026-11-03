"""Plan guidance and reviewed synthetic migration; no critic/provider is invoked."""
import json
from pathlib import Path
import tempfile
import unittest

from gates import gate_rows
from integrity import check, digest, manifest_for, LIVING
from scaffold import ROOT, PHASE_GUIDES, phase_contracts, render
from test_compact_phases import inputs
from update_operations import apply, prepare


class SpecChallengeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'synthetic factory'
        self.config,self.research=inputs(researched=True)
        self.config['operations']={'smoke_gates':{'required':False}}
        self.prior=(ROOT/'scripts/fixtures/pre_spec_challenge_plan_guide.txt').read_text(encoding='utf-8')

    def write(self,files):
        files=dict(files)
        files['manifest.json']=json.dumps(manifest_for({n:b for n,b in files.items() if n!='manifest.json'}),indent=2)+'\n'
        for name,body in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        check(self.root,quiet=True)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_generated_route_is_before_decomposition_and_preserves_all_prior_guidance(self):
        files=render(self.config,self.research);guide=files['phase-plan-guide.md']
        self.assertLess(guide.index('## Challenge acceptance'),guide.index('1. Read the accepted brief'))
        start=guide.index('## Challenge acceptance before decomposition\n')
        end=guide.index('1. Read the accepted brief',start)
        self.assertEqual(guide[:start]+guide[end:],self.prior)
        baseline=json.loads((ROOT/'scripts/fixtures/pre_compact_phase_hashes.json').read_text())
        self.assertEqual(digest(self.prior),baseline['templates']['plan'])
        manifest=json.loads(files['manifest.json'])
        self.assertEqual(manifest['contracts']['phase-plan-guide.md'],digest(guide))
        self.assertIn('../../../phase-plan-guide.md',files['.claude/skills/factory-plan/SKILL.md'])
        self.assertIn('references/spec-challenge.md',guide)
        self.assertTrue((ROOT/'references/spec-challenge.md').is_file())

    def test_guidance_does_not_add_gates_rewrite_seed_or_truncate_research(self):
        files=render(self.config,self.research);rows=gate_rows(files['verification.md'])
        self.assertEqual(set(rows),{'G1','G2','G3','A1','R1'})
        self.assertTrue(all(row['result']=='NOT RUN' for row in rows.values()))
        self.assertTrue(all(rows[g]['required']=='no' for g in ('G1','G2','G3')))
        self.assertEqual(json.loads(files['config.json']),self.config)
        self.assertEqual(json.loads(files['task-plan.json']),{'tasks':self.config['tasks'],'events':[]})
        legacy=phase_contracts(self.research,legacy=True)
        instruction=self.research['practices'][0]['instruction']
        for phase in PHASE_GUIDES:
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            self.assertIn(instruction,files[name]);self.assertIn(instruction,legacy[name])
        self.assertNotIn('Challenge acceptance',legacy['.claude/skills/factory-plan/SKILL.md'])

    def test_reference_preserves_availability_round_and_authority_boundaries(self):
        text=(ROOT/'references/spec-challenge.md').read_text(encoding='utf-8')
        for phrase in ('ACCEPT-WITH-RESERVATIONS','REVISE','REJECT','**two revision rounds**',
                       'no critic verdict','Open Questions','repository SHA does not',
                       'only when actually observed','not an automatic third round',
                       'do not invent a new','active adoption remains a separate authorized step',
                       'Edits, deletion, reordering','waivers','not a new runtime JSON schema'):
            self.assertIn(phrase,text)
        for target in ('acceptance-planning.md','acceptance-candidates.md','recovery.md'):
            self.assertIn(']('+target+')',text);self.assertTrue((ROOT/'references'/target).is_file())

    def test_legacy_migration_adds_reviewed_plan_guide_without_changing_records_or_research(self):
        files=render(self.config,self.research)
        files.update(phase_contracts(self.research,legacy=True))
        for name in PHASE_GUIDES.values():del files[name]
        rows=files['verification.md'].splitlines()
        for index,line in enumerate(rows):
            if line.startswith('| G2 |'):
                cells=[c.strip() for c in line.strip('|').split('|')]
                cells[6:8]=['FAILED','SYNTHETIC prior failure retained under waiver']
                rows[index]='| '+' | '.join(cells)+' |'
        files['verification.md']='\n'.join(rows)+'\n';self.write(files)
        before=self.snapshot();root,old,new,plan=prepare(self.root,{},compact_phases=True)
        self.assertEqual(self.snapshot(),before)
        self.assertIn('phase-plan-guide.md',new)
        self.assertIn(b'Challenge acceptance before decomposition',new['phase-plan-guide.md'])
        with self.assertRaises(ValueError):apply(root,old,new,plan,'unreviewed')
        self.assertEqual(self.snapshot(),before)
        backup=apply(root,old,new,plan,plan);after=self.snapshot()
        for name in LIVING|{'config.json','acceptance.md','research.json','research.md','upstream-provenance.json'}:
            self.assertEqual(after[name],before[name],name)
        rows=gate_rows(after['verification.md'].decode());self.assertEqual(rows['G2']['required'],'no')
        self.assertEqual(rows['G2']['result'],'FAILED')
        for phase in PHASE_GUIDES:
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            self.assertIn(self.research['practices'][0]['instruction'].encode(),after[name])
            self.assertEqual((backup/name).read_bytes(),before[name])
        self.assertEqual((backup/'manifest.json').read_bytes(),before['manifest.json'])
        check(self.root,quiet=True)

    def test_existing_older_compact_or_custom_guide_is_preserved_for_selective_adoption(self):
        for body in (self.prior,self.prior+'\nCustom project planning constraint.\n'):
            with self.subTest(custom=body!=self.prior):
                files=render(self.config,self.research);files['phase-plan-guide.md']=body;self.write(files)
                before=self.snapshot()
                with self.assertRaisesRegex(ValueError,'Customized or unsupported phase guide'):
                    prepare(self.root,{},compact_phases=True)
                self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
