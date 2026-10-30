"""Synthetic examples check generated guidance; no application runner is invoked."""
import json
import unittest
from scaffold import ROOT, render

class CollectionGuidanceTests(unittest.TestCase):
    def test_verify_guides_collection_and_outcome_reconciliation(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(config,research)
        guide=' '.join(files['.claude/skills/factory-verify/SKILL.md'].split())
        examples=('mapped spec excluded by a project filter: NOT RUN',
                  'a valid collection with zero tests: NOT RUN',
                  'collected test skipped: SKIPPED, not passed',
                  'one of two expected shards absent: incomplete')
        for example in examples:
            with self.subTest(example=example): self.assertIn(example,guide)
        for condition in ('same subject revision','runner configuration','filters',
                          'final result evidence','separately run suites',
                          'do not run untrusted configuration',
                          'does not prove other mapped tests ran'):
            with self.subTest(condition=condition): self.assertIn(condition,guide)
        self.assertIn('executes and attests nothing',files['verification.md'])

if __name__=='__main__': unittest.main()
