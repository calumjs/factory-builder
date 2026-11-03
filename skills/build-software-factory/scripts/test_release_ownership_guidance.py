"""Offline assertions for generated release guidance; no deployment is run."""
import json
from pathlib import Path
import unittest
from phase_test_support import phase_text
from scaffold import ROOT,render

class ReleaseOwnershipGuidanceTests(unittest.TestCase):
    def test_release_lane_and_migration_order_are_proposals_not_enforcement(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(config,research)
        release=' '.join(phase_text(files,'release').split())
        for term in ('one release owner','atomic admission mechanism','non-owner waits',
                     'migration-before-promotion','expand/contract','later G3 observation',
                     'without scoped authority', 'non-interactive transactions', 'migration ledger',
                     'network-policy bypass', 'No generic transport fallback'):
            self.assertIn(term,release)
        handoff=files['release-handoff.md']
        self.assertIn('Release owner, subject/target',handoff)
        self.assertIn('Migration-before-traffic',handoff)
        for term in ('SUCCESS / FAILED / CANCELLED / UNKNOWN','terminal marker is absent',
                     'authorized handoff','local claim alone'):
            self.assertIn(term,handoff)
