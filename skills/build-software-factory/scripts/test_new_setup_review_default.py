"""New interview guidance selects visible review without changing legacy parsing."""
import copy
import json
import re
import unittest

from dashboard import summarize
from gates import gate_rows, problems, requirements, waivers
from integrity import digest
from operations import operations
import review_records as review
from scaffold import ROOT, render, validate


class NewSetupReviewDefaultTests(unittest.TestCase):
    def setUp(self):
        skill=(ROOT/'SKILL.md').read_text(encoding='utf-8')
        self.seed=re.search(r'adapt `(assets/[^`]+\.json)`',skill)[1]
        self.config=json.loads((ROOT/self.seed).read_text(encoding='utf-8'))
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))

    def test_recommended_seed_renders_required_unrun_review_and_complete_routes(self):
        self.assertEqual(self.seed,'assets/example-review-config.json')
        before=copy.deepcopy(self.config);validate(self.config)
        files=render(self.config,self.research)
        self.assertEqual(self.config,before)
        self.assertEqual(operations(self.config)['review'],{'record_schema':1,'required_approvals':1,
                                                           'independent':True,'distinct_providers':False})
        row=gate_rows(files['verification.md'])['Q1']
        self.assertEqual((row['required'],row['result'],row['revision'],row['evidence']),('yes','NOT RUN','',''))
        self.assertEqual(review.parse(files['release-handoff.md']),review.empty())
        for phase in ('verify','release'):
            self.assertIn('[review-guide.md](review-guide.md)',files['phase-'+phase+'-guide.md'])
        manifest=json.loads(files['manifest.json'])
        self.assertEqual(manifest['contracts']['review-guide.md'],digest(files['review-guide.md']))
        text='\n'.join(line for line in files['verification.md'].splitlines() if line.startswith('| Q1 |'))
        found=problems(text,'pre-merge','synthetic-subject',{'Q1':requirements(self.config,self.research)['Q1']},
                       review_text=files['release-handoff.md'])
        self.assertIn('Q1 has no selected supplied review round',found)
        self.assertIn('Q1 is NOT RUN',found)

    def test_explicit_zero_choice_stays_visible_waived_without_inventing_approval(self):
        self.config['operations']['review']['required_approvals']=0
        validate(self.config);files=render(self.config,self.research)
        row=gate_rows(files['verification.md'])['Q1']
        self.assertEqual((row['required'],row['result']),('no','NOT RUN'))
        self.assertEqual(review.parse(files['release-handoff.md']),review.empty())
        self.assertIn('review-guide.md',files)
        self.assertIn('Q1 WAIVED (recorded NOT RUN)',waivers(files['verification.md'],'pre-merge',files['release-handoff.md']))
        displayed=next(row for row in summarize(files)['gates'] if row['id']=='Q1')
        self.assertEqual((displayed['state'],displayed['recorded_result']),('WAIVED','NOT RUN'))

    def test_legacy_absence_still_has_no_review_row_or_implicit_adoption(self):
        legacy=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        before=copy.deepcopy(legacy);validate(legacy);files=render(legacy,self.research)
        self.assertEqual(legacy,before)
        self.assertNotIn('record_schema',operations(legacy)['review'])
        self.assertNotIn('Q1',gate_rows(files['verification.md']))
        self.assertNotIn(review.START,files['release-handoff.md'])
        self.assertNotIn('review-guide.md',files)
        for phase in ('verify','release'):
            self.assertNotIn('[review-guide.md](review-guide.md)',files['phase-'+phase+'-guide.md'])

    def test_interview_and_scaffolding_guidance_match_new_seed_and_legacy_boundary(self):
        intake=(ROOT/'references/intake.md').read_text(encoding='utf-8')
        scaffolding=(ROOT/'references/scaffolding.md').read_text(encoding='utf-8')
        for guide in (intake,scaffolding):
            self.assertIn('`'+self.seed+'`',guide)
            self.assertIn('`record_schema: 1`',guide)
            self.assertIn('`required_approvals: 0`',guide)
            self.assertIn('WAIVED',guide)
            self.assertIn('setup assumptions/proposal',guide)
        self.assertIn('ask only consequential missing questions',intake)
        self.assertIn('Existing factories retain their config, evidence and waivers',scaffolding)
        self.assertIn('not a change to legacy parsing',scaffolding)
        self.assertIn('settings authorize no provider call or spending',scaffolding)


if __name__=='__main__':unittest.main()
