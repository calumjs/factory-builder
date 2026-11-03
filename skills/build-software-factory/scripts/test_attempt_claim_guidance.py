"""Synthetic guidance checks only; no watcher, claim, process or media is run."""
import json
import unittest
from scaffold import ROOT,render

class AttemptClaimGuidanceTests(unittest.TestCase):
    def setUp(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.files=render(config,research)
    def test_attempt_examples_cover_normal_timeout_forced_and_superseded(self):
        handoff=self.files['release-handoff.md']
        examples={}
        for line in handoff.splitlines():
            if line.startswith('| ') and ' | ' in line:
                cells=[x.strip() for x in line.strip('| ').split('|')]
                if len(cells)==2:examples[cells[0]]=cells[1]
        for situation,outcome in (
            ('Normal zero exit plus matching passing check evidence','PASS for that attempt'),
            ('Timeout; worker termination not confirmed','UNKNOWN/STALE, investigate'),
            ('Supervisor confirms forced termination','ABORTED with termination evidence'),
            ('A successor starts while old outcome is unresolved','Old attempt UNKNOWN; link successor')):
            with self.subTest(situation=situation):self.assertEqual(examples[situation],outcome)
        normalized=' '.join(handoff.split())
        self.assertIn('unique attempt ID',normalized)
        self.assertIn('heartbeat is a timestamped observation, not proof',normalized)
        self.assertIn('no supervisor is installed',normalized)
        self.assertIn('optional gate WAIVED',normalized)
    def test_video_claim_expiry_alone_cannot_authorize_replacement(self):
        recipe=' '.join(self.files['done-video-recipe.md'].split())
        for term in ('unique attempt and owner token','full subject revision',
                     'TTL expiry, missing final marker or stale heartbeat',
                     'cannot enforce the fence and termination is unverified',
                     'Retain that completed identity and evidence',
                     'not distributed exclusion','installs no claim helper'):
            with self.subTest(term=term):self.assertIn(term,recipe)
        self.assertLess(recipe.index('After acquiring exclusive ownership'),
                        recipe.index('before any capture, composition or paid request'))
        self.assertIn('An earlier lookup may be stale',recipe)
        self.assertIn('before releasing the claim',recipe)
        self.assertIn('If indexing is unavailable or the completion is uncertain',recipe)
        self.assertIn('approval immediately before narration',recipe)

if __name__=='__main__':unittest.main()
