"""Inspect generated seed-prerequisite guidance; no database is touched."""
import json
import unittest
from phase_test_support import phase_text
from scaffold import ROOT,render

class SeedDataGuidanceTests(unittest.TestCase):
    def test_guidance_distinguishes_environment_and_retains_feature_checks(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(config,research)
        build=' '.join(phase_text(files,'build').split())
        verify=' '.join(phase_text(files,'verify').split())
        for term in ('review it together with assertions','data prerequisites','fresh CI database',
                     'authorized isolated disposable fixture','BLOCKED'):
            with self.subTest(term=term):self.assertIn(term,build)
        for term in ('long-lived target is in scope','without relying on newly introduced seeds',
                     'green fresh-seeded CI run','Never reseed production',
                     'Retain meaningful feature assertions','optional row remains WAIVED'):
            with self.subTest(term=term):self.assertIn(term,verify)
        scenarios={}
        for line in phase_text(files,'verify').splitlines():
            if line.startswith('| ') and ' | ' in line:
                cells=[x.strip() for x in line.strip('| ').split('|')]
                if len(cells)==2:scenarios[cells[0]]=cells[1]
        self.assertEqual(scenarios['Fresh CI database contains newly added seed rows'],
                         'CI evidence only; long-lived prerequisites unconfirmed')
        self.assertIn('BLOCKED/NOT RUN',scenarios['Required data unavailable and safe setup not authorized'])
        self.assertIn('disposable fixture',scenarios['Feature needs controlled records and isolated setup is authorized'])
        self.assertIn('executes and attests nothing',files['verification.md'])

if __name__=='__main__':unittest.main()
