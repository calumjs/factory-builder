"""Default smoke gates are generated, start NOT RUN and block until recorded PASSED for the revision."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gates import problems
from operations import operations
from scaffold import ROOT, render

class GateTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())
        self.files = render(self.config, self.research)
    def test_generated_artifacts_include_default_gates(self):
        v = self.files['verification.md']
        for gate in ('G1', 'G2', 'G3'):
            self.assertIn('| ' + gate + ' |', v)
        self.assertIn('production build', v)
        self.assertIn('deployed URL', v)
        self.assertIn('Change-targeted', v)
        self.assertNotIn('PASSED |', v)
        for name in ('factory-verify', 'factory-release'):
            skill = self.files[f'.claude/skills/{name}/SKILL.md']
            self.assertIn('G1', skill); self.assertIn('G2', skill); self.assertIn('NOT RUN', skill)
        self.assertIn('G3', self.files['.claude/skills/factory-release/SKILL.md'])
        self.assertIn('BLOCKED', self.files['release-handoff.md'])
        self.assertIn('G3 post-merge', self.files['release-handoff.md'])
        self.assertIn('Default delivery gates', self.files['policy.md'])
    def test_default_policy_requires_gates(self):
        controls = self.files['policy.md'].split('## Proposed autonomy and review controls', 1)[1].split('```json\n', 1)[1].split('\n```', 1)[0]
        self.assertTrue(json.loads(controls)['smoke_gates']['required'])
    def test_not_run_blocks_both_stages(self):
        v = self.files['verification.md']
        self.assertTrue(problems(v, 'pre-merge', 'abc123'))
        self.assertTrue(problems(v, 'post-merge', 'abc123'))
    def mark(self, v, gate, revision, result, evidence='observed exit 0 at 2026-10-30T00:00Z'):
        out = []
        for line in v.split('\n'):
            if line.startswith('| ' + gate + ' |'):
                c = [x.strip() for x in line.strip().strip('|').split('|')]
                c[5], c[6], c[7] = revision, result, evidence
                line = '| ' + ' | '.join(c) + ' |'
            out.append(line)
        return '\n'.join(out)
    def test_pre_merge_requires_g1_and_g2_passed_for_revision(self):
        v = self.mark(self.files['verification.md'], 'G1', 'abc123', 'PASSED')
        self.assertTrue(any('G2' in x for x in problems(v, 'pre-merge', 'abc123')))
        v = self.mark(v, 'G2', 'abc123', 'PASSED')
        self.assertEqual(problems(v, 'pre-merge', 'abc123'), [])
        self.assertTrue(problems(v, 'pre-merge', 'def456'))
        self.assertTrue(problems(v, 'post-merge', 'abc123'))
    def test_failed_and_blocked_block(self):
        for result in ('FAILED', 'BLOCKED', 'NOT RUN'):
            v = self.mark(self.mark(self.files['verification.md'], 'G1', 'r1', 'PASSED'), 'G2', 'r1', result)
            self.assertTrue(problems(v, 'pre-merge', 'r1'), result)
    def test_post_merge_confirm(self):
        v = self.mark(self.files['verification.md'], 'G3', 'r1', 'FAILED')
        self.assertTrue(problems(v, 'post-merge', 'r1'))
        v = self.mark(v, 'G3', 'r1', 'PASSED')
        self.assertEqual(problems(v, 'post-merge', 'r1'), [])
    def test_removed_gates_block(self):
        v = '\n'.join(l for l in self.files['verification.md'].split('\n') if not l.startswith('| G'))
        self.assertTrue(problems(v, 'pre-merge', 'r1'))
    def test_disabling_gates_requires_exception(self):
        self.config['operations'] = {'smoke_gates': {'required': False}}
        with self.assertRaises(ValueError): operations(self.config)
        self.config['operations'] = {'smoke_gates': {'required': False, 'exception': 'Docs-only repo; accepted by named owner'}}
        self.assertFalse(operations(self.config)['smoke_gates']['required'])
    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'verification.md').write_text(self.files['verification.md'])
            cmd = [sys.executable, str(ROOT/'scripts/gates.py'), '--factory', d, '--stage', 'pre-merge', '--revision', 'r1']
            r = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1); self.assertIn('BLOCKED', r.stdout)
            v = self.mark(self.mark(self.files['verification.md'], 'G1', 'r1', 'PASSED'), 'G2', 'r1', 'PASSED')
            (Path(d)/'verification.md').write_text(v)
            self.assertEqual(subprocess.run(cmd, capture_output=True, text=True).returncode, 0)

if __name__ == '__main__': unittest.main(verbosity=2)
