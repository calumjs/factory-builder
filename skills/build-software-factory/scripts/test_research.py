"""Offline schema/mapping tests with synthetic evidence; no URL is actually researched."""
import copy
import json
from pathlib import Path
import unittest
from research import PHASES, validate_research
from scaffold import render, ROOT

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.r=json.loads((ROOT/'assets/example-research.json').read_text())
        self.r.update(status='complete',summary='SYNTHETIC TEST RECORD: not real online research.')
        self.r['coverage']={x:{'status':'applicable','reason':'Mock phase requirement'} for x in PHASES}
        self.r['sources']=[{'id':'S1','url':'https://example.com/mock-docs','accessed_on':'2026-10-29','kind':'synthetic fixture','version_scope':'mock v1','observation':'Mock documented behavior','status':'read'}]
        self.r['practices']=[{'id':'P-'+x,'decision':'selected','source_ids':['S1'],'phases':[x],'relevance':'Mock relevant requirement','compatibility':'Mock v1 matches','tradeoff':'Mock tradeoff','instruction':'Perform unique mock action for '+x,'check':'Assert mock result for '+x} for x in PHASES]
    def test_selected_practices_applied_to_matching_skills_and_checks(self):
        files=render(self.config,self.r)
        for phase in PHASES:
            skill=files[f'.claude/skills/factory-{phase}/SKILL.md']
            self.assertIn('Perform unique mock action for '+phase,skill)
            self.assertIn('Assert mock result for '+phase,skill)
            self.assertIn('Assert mock result for '+phase,files['verification.md'])
            self.assertIn('P-'+phase,files['research.md'])
        self.assertIn('NOT independently verified',files['research.md'])
    def test_unverified_source_cannot_be_selected(self):
        self.r['sources'][0]['status']='unverified'
        with self.assertRaises(ValueError):render(self.config,self.r)
    def test_unknown_source_cannot_be_selected(self):
        self.r['practices'][0]['source_ids']=['missing']
        with self.assertRaises(ValueError):render(self.config,self.r)
    def test_missing_applicable_phase_rejected(self):
        self.r['practices'].pop()
        with self.assertRaises(ValueError):validate_research(self.r)
    def test_irrelevant_phase_excluded(self):
        self.r['coverage']['learn']={'status':'not_applicable','reason':'No additional research needed for this mock task'}
        self.r['practices'].pop()
        files=render(self.config,self.r)
        self.assertNotIn('Perform unique mock action for learn',files['.claude/skills/factory-learn/SKILL.md'])
    def test_blocked_draft_not_researched(self):
        r=json.loads((ROOT/'assets/example-research.json').read_text())
        files=render(self.config,r)
        for phase in PHASES:self.assertIn('UNRESEARCHED DRAFT',files[f'.claude/skills/factory-{phase}/SKILL.md'])
    def test_stale_cannot_be_promoted(self):
        self.r['sources'][0]['status']='stale'
        with self.assertRaises(ValueError):validate_research(self.r)
    def test_candidates_not_applied(self):
        self.r['status']='draft'
        for p in self.r['practices']:p['decision']='candidate'
        files=render(self.config,self.r)
        for phase in PHASES:self.assertNotIn('Perform unique mock action for '+phase,files[f'.claude/skills/factory-{phase}/SKILL.md'])
    def test_read_requires_access_date(self):
        self.r['sources'][0]['accessed_on']=None
        with self.assertRaises(ValueError):validate_research(self.r)

if __name__=='__main__':unittest.main(verbosity=2)
