"""Generated guidance and preserved scaffold semantics, with no app or release run.

Existing test_recovery_evidence and test_incremental_workflow exercise the S1/S2
history and record-writer behavior; these fixtures do not duplicate that lifecycle.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from phase_test_support import phase_text, phase_text_at

from gates import gate_rows
from integrity import check
from scaffold import ROOT, render


VERIFY = '.claude/skills/factory-verify/SKILL.md'
RELEASE = '.claude/skills/factory-release/SKILL.md'


class VerificationRetryGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))

    def test_generated_verify_requires_persistence_success_and_separate_interruption_probe(self):
        verify = phase_text(render(self.config,self.research),'verify')
        text = ' '.join(verify.split())
        for condition in ('application-level persistence success', 'committed-save acknowledgement or durable readback',
                          'zero pending requests or a finished response alone is not proof',
                          'surface failures and timeouts', 'separate interruption-during-write tests',
                          'authorized isolated latency/concurrency probe', 'encoded and malformed inputs',
                          'hydration and subsequent navigation', 'local-server success does not establish hosting or edge parity',
                          'If an equivalent target cannot be exercised within authority'):
            with self.subTest(condition=condition):
                self.assertIn(condition, text)
        self.assertIn('synthetic helper names and selector', text)
        self.assertIn('resolve only on a project-verified committed-save signal', text)
        self.assertIn('reject failed saves and timeouts', text)
        example = verify.split('```javascript\n', 1)[1].split('```', 1)[0]
        self.assertLess(example.index('armCommittedSave('), example.index('.click()'))
        self.assertLess(example.index('await Promise.all('), example.index('await page.reload()'))
        self.assertLess(example.index('await page.reload()'), example.index('await assertPersistedValue('))

    def test_generated_release_preserves_failed_subject_and_reuses_task_with_canonical_checks(self):
        release = ' '.join(phase_text(render(self.config,self.research),'release').split())
        for condition in ('actual FAILED or BLOCKED observation for deployed subject S1',
                          'deployed but unconfirmed', 'same release task ID',
                          "preserving S1's gate history and task events", 'new actual subject S2',
                          'diagnostic-only test does not replace a failing canonical G3',
                          'failed required G3 blocks required V1', 'WAIVED, not passed',
                          'perform either only within existing authority',
                          '`status.py --check` is a free-text event label, not a gate-row writer',
                          'Both helpers record supplied claims and execute no application checks'):
            with self.subTest(condition=condition):
                self.assertIn(condition, release)

    def test_documented_record_options_are_supported_by_the_actual_helper_clis(self):
        release = phase_text(render(self.config,self.research),'release').split('## Retry after failed G3', 1)[1].split('## Video', 1)[0]
        for script in ('incremental_records.py', 'status.py'):
            help_result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), '--help'],
                                         capture_output=True, text=True)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            command = re.search(r'`'+re.escape(script)+r' ([^`]+)`', release).group(1)
            for option in re.findall(r'--[a-z]+(?:-[a-z]+)*', command):
                self.assertIn(option, help_result.stdout)
            if script == 'incremental_records.py':
                self.assertIn('--approve-plan', help_result.stdout)
                self.assertIn('`--apply --approve-plan <digest>`', release)

    def test_guidance_adds_no_gate_or_command_and_preserves_optional_g3(self):
        self.config['stack'] = 'Synthetic artifact CLI; no browser UI'
        self.config['operations'] = {'smoke_gates': {'required': False}, 'done_videos': {'enabled': True}}
        files = render(self.config, self.research)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, body in files.items():
                path = root/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(body.encode('utf-8'))
            check(root, quiet=True)
            self.assertEqual(json.loads((root/'config.json').read_text()), self.config)
            self.assertEqual(json.loads((root/'task-plan.json').read_text())['tasks'], self.config['tasks'])
            self.assertEqual(json.loads((root/'tools.json').read_text())['test_commands'], [])
            rows = gate_rows((root/'verification.md').read_text())
            self.assertEqual(set(rows), {'G1', 'G2', 'G3', 'A1', 'V1'})
            self.assertEqual(rows['G3']['required'], 'no')
            self.assertEqual(rows['V1']['required'], 'yes')
            self.assertTrue(all(row['result'] == 'NOT RUN' for row in rows.values()))
            self.assertEqual(phase_text_at(root,'release').count('## Retry after failed G3'), 1)


if __name__ == '__main__':
    unittest.main()
