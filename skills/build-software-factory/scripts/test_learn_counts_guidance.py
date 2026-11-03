"""Generated evidence guidance only; executes no application tests."""
import json
import unittest
from scaffold import ROOT,render

class LearnCountsGuidanceTests(unittest.TestCase):
    def test_record_intended_and_executed_scope_with_honest_counts(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        guide=' '.join(render(config,research)['.claude/skills/factory-learn/SKILL.md'].split())
        for phrase in ('intended scope','actually executed','passed, failed, skipped and not-run',
                       'retries or flaky','unknown rather than zero','serial failure',
                       'incomplete scope','smaller smoke count'):
            self.assertIn(phrase,guide)
