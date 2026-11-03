"""Check the generated reusable scene-plan guidance; no media is produced."""
import json
import unittest
from scaffold import ROOT,render

class VideoPlanGuidanceTests(unittest.TestCase):
    def test_scene_plan_is_valid_json_and_preserves_capture_and_authority(self):
        cfg=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        recipe=render(cfg,research)['done-video-recipe.md']
        plan=json.loads(recipe.split('```json\n',1)[1].split('\n```',1)[0])
        self.assertEqual(plan['format_version'],1)
        self.assertEqual([s['kind'] for s in plan['scenes']],['title','genuine_capture','outcome'])
        self.assertIsNone(plan['subject_revision']);self.assertIsNone(plan['scenes'][1]['source'])
        for s in ('not a shell script','or proof of capture','distinct V1/V2',
                  'approval immediately before narration', 'ffmpeg -protocol_whitelist file,pipe',
                  'silent fixture proves only', 'capture.mp4'):
            self.assertIn(s,' '.join(recipe.split()))

if __name__=='__main__': unittest.main()
