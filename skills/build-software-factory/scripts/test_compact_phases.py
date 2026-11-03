"""Generated phase routing and opt-in migration preserve requirements and private research."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from integrity import check, digest, manifest_for
from operations import operations
from research import PHASES
from scaffold import ROOT, RETURN, COMPACT_FOOTER, PHASE_GUIDES, legacy_phase_template, phase_contracts, phase_skill, render
from update_operations import apply, prepare


def inputs(researched=False):
    config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
    research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
    if researched:
        research.update(status='complete',summary='Synthetic research fixture only')
        research['coverage']={phase:{'status':'applicable','reason':'Synthetic fixture assessment'} for phase in PHASES}
        research['sources']=[{'id':'S1','url':'https://example.com/synthetic','accessed_on':date.today().isoformat(),'kind':'fixture','version_scope':'fixture only','observation':'Synthetic observation','status':'read'}]
        research['practices']=[{'id':'P1','decision':'selected','source_ids':['S1'],'phases':list(PHASES),'relevance':'Fixture','compatibility':'Fixture only','tradeoff':'Synthetic','instruction':'Distinct project instruction. '*100,'check':'Retain this exact planned check.'}]
    return config,research


class CompactGenerationTests(unittest.TestCase):
    def test_minimal_word_budget_complete_linked_contracts_and_numbered_routing(self):
        config,research=inputs();files=render(config,research);manifest=json.loads(files['manifest.json'])
        for phase,name in PHASE_GUIDES.items():
            skill=f'.claude/skills/factory-{phase}/SKILL.md';text=files[skill]
            self.assertLessEqual(len(text.split()),300,(phase,len(text.split())))
            self.assertEqual(text,phase_contracts(research)[skill])
            self.assertEqual(re.findall(r'^([1-4])\. ',text,re.M),['1','2','3','4'])
            self.assertLess(text.index('4. Return:'),text.index('## Task-specific research'))
            self.assertTrue(text.rstrip().endswith(COMPACT_FOOTER))
            self.assertNotIn('## Video',text);self.assertNotIn('## Operating preferences',text)
            self.assertIn(name,manifest['contracts']);self.assertEqual(manifest['contracts'][name],digest(files[name]))
            for target in re.findall(r'\]\(([^)]+)\)',text):
                path,_,anchor=target.partition('#')
                self.assertTrue(path.startswith('../../../'),target)
                dest=path[len('../../../'):];self.assertIn(dest,files)
                if anchor:
                    headings={re.sub(r'[^a-z0-9 -]','',line.lstrip('# ').lower()).replace(' ','-') for line in files[dest].splitlines() if line.startswith('#')}
                    self.assertIn(anchor,headings,(phase,target))

    def test_all_prior_guidance_and_legacy_delivery_sources_are_exactly_preserved(self):
        config,research=inputs();files=render(config,research)
        baseline=json.loads((ROOT/'scripts/fixtures/pre_compact_phase_hashes.json').read_text())
        legacy=phase_contracts(research,legacy=True)
        self.assertEqual(digest(files['.claude/skills/factory-run/SKILL.md']),baseline['run_skill'])
        self.assertEqual(set(phase_contracts(research)),{f'.claude/skills/factory-{phase}/SKILL.md' for phase in PHASES})
        for phase,name in PHASE_GUIDES.items():
            prior=files[name]
            if phase=='verify':
                # The reviewed latency example is additive; retain the original
                # baseline digest to prove all earlier guidance survives exactly.
                start=prior.index('### Optional targeted mutation-delay probe\n')
                end=prior.index('## Reconcile shared-contract impact\n',start)
                prior=prior[:start]+prior[end:]
            self.assertEqual(digest(prior),baseline['templates'][phase])
            self.assertEqual(digest(legacy[f'.claude/skills/factory-{phase}/SKILL.md']),baseline['minimal_skills'][phase])
            source=phase_skill(legacy_phase_template(phase)).split('---',2)[2].strip()+'\n\n'+RETURN
            self.assertEqual(digest(source),baseline['delivery_sources'][phase])

    def test_project_research_is_not_truncated_or_reordered_to_meet_budget(self):
        config,research=inputs(researched=True);files=render(config,research)
        legacy=phase_contracts(research,legacy=True)
        for phase in PHASES:
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            old=legacy[name].split('## Task-specific research',1)[1].rsplit('\n\n'+RETURN,1)[0]
            new=files[name].split('## Task-specific research',1)[1].rsplit('\n\n'+COMPACT_FOOTER,1)[0]
            self.assertEqual(new,old)
            self.assertIn(research['practices'][0]['instruction'],files[name])
            self.assertGreater(len(files[name].split()),300)

    def test_enabled_preferences_use_stable_current_config_routes(self):
        config,research=inputs();minimal=render(config,research)
        config['operations']=operations(config)
        config['operations']['done_videos'].update(enabled=True,triggers=['pre_merge_preview','post_g3_release'])
        config['operations']['issue_intake'].update(mode='continuous')
        enabled=render(config,research)
        for phase in PHASES:
            name=f'.claude/skills/factory-{phase}/SKILL.md'
            self.assertEqual(enabled[name],minimal[name])
            self.assertEqual(enabled[PHASE_GUIDES[phase]],minimal[PHASE_GUIDES[phase]])
        self.assertIn('V1',enabled['verification.md']);self.assertIn('V2',enabled['verification.md'])
        for phase in ('intake','plan','verify','release','learn'):
            self.assertIn('current',enabled[f'.claude/skills/factory-{phase}/SKILL.md'])


class CompactMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'factory'
        self.config,self.research=inputs(researched=True)
        files=render(self.config,self.research)
        files.update(phase_contracts(self.research,legacy=True))
        for name in PHASE_GUIDES.values():del files[name]
        files['manifest.json']=json.dumps(manifest_for({name:body for name,body in files.items() if name!='manifest.json'}),indent=2)+'\n'
        for name,body in files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        check(self.root,quiet=True)

    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def contract(self,name,raw):
        (self.root/name).write_bytes(raw)
        path=self.root/'manifest.json';manifest=json.loads(path.read_bytes())
        manifest['contracts'][name]=digest(raw);path.write_bytes(json.dumps(manifest).encode())

    def preview(self):
        before=self.snapshot();result=prepare(self.root,{},compact_phases=True)
        self.assertEqual(before,self.snapshot());return result

    def test_preview_apply_backups_manifest_and_no_unrelated_changes(self):
        before=self.snapshot();prepared=self.preview();root,old,new,plan=prepared
        expected={f'.claude/skills/factory-{phase}/SKILL.md' for phase in PHASES}|set(PHASE_GUIDES.values())|{'manifest.json'}
        self.assertEqual(set(new),expected)
        self.assertEqual(set(PHASE_GUIDES.values())&set(old),set(PHASE_GUIDES.values()))
        self.assertTrue(all(old[name] is None for name in PHASE_GUIDES.values()))
        fingerprints={name:{'before':hashlib.sha256(old[name]).hexdigest() if old[name] is not None else None,'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(new.items())}
        self.assertEqual(plan,hashlib.sha256(json.dumps({'factory':str(root),'files':fingerprints},indent=2,ensure_ascii=False).encode()+b'\n').hexdigest())
        backup=apply(*prepared,plan);check(root,quiet=True)
        self.assertEqual(set(json.loads((backup/'added-files.json').read_bytes())),set(PHASE_GUIDES.values()))
        for name in new:
            self.assertEqual((root/name).read_bytes(),new[name])
            if old[name] is not None:self.assertEqual((backup/name).read_bytes(),old[name])
        for name,raw in before.items():
            if name.removeprefix('factory/') not in new:self.assertEqual((self.base/name).read_bytes(),raw)
        for name,wanted in phase_contracts(self.research).items():self.assertEqual((root/name).read_text(encoding='utf-8'),wanted)

    def test_already_compact_normalized_equivalent_bytes_are_idempotent(self):
        prepared=self.preview();apply(*prepared,prepared[3])
        for name in [*phase_contracts(self.research),*PHASE_GUIDES.values()]:
            path=self.root/name;self.contract(name,path.read_bytes().replace(b'\n',b'\r\n'))
        before=self.snapshot();prepared=self.preview();self.assertFalse(prepared[2]);self.assertIsNone(apply(*prepared,prepared[3]));self.assertEqual(before,self.snapshot())

    def test_custom_or_addendum_skill_refused_without_partial_writes(self):
        name='.claude/skills/factory-verify/SKILL.md';original=(self.root/name).read_bytes()
        for suffix in (b'\nCustom project instruction\n',b'\n<!-- factory-delivery-update:start -->\nReviewed older addendum\n<!-- factory-delivery-update:end -->\n'):
            self.contract(name,original+suffix);before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'Customized or unsupported phase skill'):self.preview()
            self.assertEqual(before,self.snapshot())

    def test_custom_existing_guide_refused(self):
        self.contract('phase-verify-guide.md',b'Custom guide\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized or unsupported phase guide'):self.preview()
        self.assertEqual(before,self.snapshot())

    def test_changed_research_refuses_instead_of_guessing(self):
        research=copy.deepcopy(self.research);research['practices'][0]['instruction']='Different reviewed research'
        self.contract('research.json',json.dumps(research).encode());before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized or unsupported phase skill'):self.preview()
        self.assertEqual(before,self.snapshot())

    def test_missing_shared_guide_refuses_and_custom_runtime_is_preserved(self):
        runtime='dashboard/gates.py';raw=(self.root/runtime).read_bytes()+b'\n# Synthetic reviewed customization\n'
        self.contract(runtime,raw)
        prepared=self.preview();self.assertNotIn(runtime,prepared[2]);apply(*prepared,prepared[3])
        self.assertEqual((self.root/runtime).read_bytes(),raw)
        name='boundaries.md';(self.root/name).unlink()
        manifest_path=self.root/'manifest.json';manifest=json.loads(manifest_path.read_bytes());del manifest['contracts'][name]
        manifest_path.write_bytes(json.dumps(manifest).encode());before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Referenced phase support is missing'):self.preview()
        self.assertEqual(before,self.snapshot())

    def test_wrong_digest_concurrent_skill_research_and_guide_creation_refuse(self):
        prepared=self.preview();before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'digest'):apply(*prepared,'0'*64)
        self.assertEqual(before,self.snapshot())
        name='phase-build-guide.md';(self.root/name).write_bytes(b'Concurrent private guide\n');before=self.snapshot()
        with self.assertRaises(ValueError):apply(*prepared,prepared[3])
        self.assertEqual(before,self.snapshot())
        (self.root/name).unlink()
        for name in ('research.json','.claude/skills/factory-build/SKILL.md'):
            raw=(self.root/name).read_bytes();(self.root/name).write_bytes(raw.replace(b'\n',b'\r\n'));before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'changed after preview'):apply(*prepared,prepared[3])
            self.assertEqual(before,self.snapshot());(self.root/name).write_bytes(raw)

    def test_separate_step_requirement_and_plain_delivery_has_no_missing_guide_links(self):
        for kwargs in ({'delivery_update':True},{'recipe_runtime':True},{'assumptions_update':[]},{'selective_gates':True}):
            before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'separate reviewed plan'):prepare(self.root,{},compact_phases=True,**kwargs)
            self.assertEqual(before,self.snapshot())
        prepared=prepare(self.root,{},delivery_update=True)
        for name,body in prepared[2].items():
            if name.endswith('/SKILL.md'):
                self.assertNotIn(b'phase-verify-guide.md',body);self.assertNotIn(b'phase-release-guide.md',body)
        apply(*prepared,prepared[3]);check(self.root,quiet=True)
        self.assertFalse(any((self.root/name).exists() for name in PHASE_GUIDES.values()))

    def test_cli_preview_and_post_adoption_preference_update_keep_routes(self):
        before=self.snapshot()
        command=[sys.executable,'-B',str(ROOT/'scripts/update_operations.py'),'--factory',str(self.root),'--compact-phases']
        preview=subprocess.run(command,capture_output=True,text=True,timeout=20)
        self.assertEqual(preview.returncode,0,preview.stderr);self.assertIn('PREVIEW ONLY',preview.stdout);self.assertEqual(before,self.snapshot())
        prepared=self.preview();apply(*prepared,prepared[3]);skills={name:(self.root/name).read_bytes() for name in phase_contracts(self.research)}
        changed=prepare(self.root,{'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']},'issue_intake':{'mode':'continuous'}})
        apply(*changed,changed[3]);check(self.root,quiet=True)
        for name,raw in skills.items():self.assertEqual((self.root/name).read_bytes(),raw)
        self.assertIn('| V1 |',(self.root/'verification.md').read_text());self.assertIn('| V2 |',(self.root/'verification.md').read_text())


if __name__=='__main__':unittest.main()
