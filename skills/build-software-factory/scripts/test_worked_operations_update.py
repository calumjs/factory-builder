"""Exercise the shipped synthetic patch on disposable factories, without running its argv."""
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gates import gate_rows, policy_controls, requirements, waivers
from integrity import check, digest
from operations import controls, operations
from readiness import watcher
from scaffold import ROOT, render, validate
from update_operations import PRIOR_GATE_RUNTIME, apply, prepare


EXAMPLE = ROOT / 'assets/example-operations-update.json'


class WorkedOperationsUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.factory = self.base / '.software-factory'
        self.example = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.config['operations'] = {
            'review': {'required_approvals': 2, 'independent': True},
            'smoke_gates': {'required': False}}
        for name, body in render(self.config, self.research).items():
            path = self.factory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8', newline='\n')
        policy = self.factory / 'policy.md'
        policy.write_text(policy.read_text(encoding='utf-8') + '\nCustom reviewed project policy must survive.\n', encoding='utf-8')
        self.rehash('policy.md')
        path = self.factory / 'verification.md'
        text = path.read_text(encoding='utf-8')
        lines = []
        for line in text.splitlines():
            if line.startswith('| G1 |') or line.startswith('| G2 |'):
                cells = [value.strip() for value in line.strip('|').split('|')]
                if cells[0] == 'G1':
                    cells[4] = 'yes'  # A deliberate row choice despite optional smoke defaults.
                else:
                    cells[6:8] = ['FAILED', 'SYNTHETIC earlier optional failure; retain history']
                line = '| ' + ' | '.join(cells) + ' |'
            lines.append(line)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        check(self.factory, quiet=True)

    def snapshot(self):
        return {path.relative_to(self.base).as_posix(): path.read_bytes()
                for path in self.base.rglob('*') if path.is_file()}

    def rehash(self, name):
        path = self.factory / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['contracts'][name] = digest((self.factory / name).read_bytes())
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def test_example_validates_as_operations_only_and_remains_disabled(self):
        config = copy.deepcopy(self.config)
        config['operations'] = copy.deepcopy(self.example)
        validate(config)
        ops = operations(config)
        self.assertEqual(ops['autonomy']['mode'], 'manual')
        self.assertEqual(ops['autonomy']['allowed_submitters'], [])
        self.assertEqual(ops['autonomy']['max_items_per_hour'], 0)
        self.assertEqual(ops['issue_intake']['mode'], 'continuous')
        self.assertEqual(ops['issue_intake']['status'], 'disabled')
        self.assertEqual(ops['issue_intake']['coverage'], 'around_the_clock')
        self.assertFalse(ops['done_videos']['enabled'])
        self.assertEqual(ops['done_videos']['triggers'], ['pre_merge_preview', 'post_g3_release'])
        self.assertEqual(set(ops['smoke_gates']['checks']), {'G1', 'G2', 'G3'})
        self.assertNotIn('required', self.example['smoke_gates'])
        self.assertEqual(watcher(config)['state'], 'disabled_design')
        self.assertEqual(watcher(config)['scheduler_authority'], 'unverified')
        self.assertEqual(set(requirements(config, self.research)), {'G1', 'G2', 'G3', 'A1'})
        for spec in ops['smoke_gates']['checks'].values():
            self.assertIn('SYNTHETIC UNEXECUTED', spec['environment'])
            # Syntax validation only; the illustrative fail-stop snippet is never executed.
            compile(spec['command'][2], '<unexecuted-synthetic-recipe>', 'exec')

    def test_cli_checklist_preview_wrong_digest_apply_and_preservation(self):
        cmd = [sys.executable, '-B', str(ROOT / 'scripts/update_operations.py'),
               '--factory', str(self.factory), '--operations', str(EXAMPLE)]
        before = self.snapshot()
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PREVIEW ONLY: no files written', result.stdout)
        self.assertEqual(self.snapshot(), before)
        token = re.search(r'REVIEW PLAN: ([0-9a-f]{64})', result.stdout).group(1)
        denied = subprocess.run(cmd + ['--apply', '--approve-plan', 'wrong'], capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertEqual(self.snapshot(), before)
        accepted = subprocess.run(cmd + ['--apply', '--approve-plan', token], capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertIn('No command, watcher, video or integration was run or enabled', accepted.stdout)
        check(self.factory, quiet=True)
        config = json.loads((self.factory / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['operations']['review'], self.config['operations']['review'])
        self.assertFalse(config['operations']['smoke_gates']['required'])
        self.assertEqual(policy_controls((self.factory / 'policy.md').read_text(encoding='utf-8')), controls(config))
        self.assertIn('Custom reviewed project policy must survive', (self.factory / 'policy.md').read_text())
        text = (self.factory / 'verification.md').read_text()
        rows = gate_rows(text)
        self.assertEqual(rows['G1']['required'], 'yes')
        self.assertEqual(rows['G2']['required'], 'no')
        self.assertEqual(rows['G3']['required'], 'no')
        self.assertEqual({row['result'] for row in rows.values()}, {'NOT RUN'})
        self.assertIn('SYNTHETIC earlier optional failure; retain history', text)
        self.assertEqual(waivers(text, 'pre-merge'), ['G2 WAIVED (recorded NOT RUN)'])
        backup = self.base / '.factory-update-backups' / token
        self.assertEqual((backup / 'config.json').read_bytes(), before['.software-factory/config.json'])
        for name in ('acceptance.md', 'research.json', 'task-plan.json', 'learning-log.md', 'tools.json'):
            self.assertEqual((self.factory / name).read_bytes(), before['.software-factory/' + name])

    def test_explicit_synthetic_video_choice_generates_staged_unexecuted_rows(self):
        changes = copy.deepcopy(self.example)
        changes['done_videos']['enabled'] = True  # Disposable design preference, not execution authority.
        before = self.snapshot()
        with patch('subprocess.Popen', side_effect=AssertionError('Updater must not run recipe commands')) as spawn:
            root, old, new, token = prepare(self.factory, changes)
            self.assertEqual(self.snapshot(), before)
            apply(root, old, new, token, token)
            spawn.assert_not_called()
        rows = gate_rows((self.factory / 'verification.md').read_text())
        self.assertEqual((rows['V2']['stage'], rows['V1']['stage']), ('pre-merge', 'post-merge'))
        self.assertEqual((rows['V2']['result'], rows['V1']['result']), ('NOT RUN', 'NOT RUN'))
        self.assertEqual(rows['G2']['required'], 'no')

    def test_known_old_runtime_needs_explicit_flag_and_verified_backup(self):
        original = {}
        for name, expected in PRIOR_GATE_RUNTIME.items():
            data = (ROOT / ('scripts/fixtures/v1_5_1_' + name[:-3] + '.txt')).read_bytes()
            self.assertEqual(digest(data), expected)
            path = 'dashboard/' + name
            original[path] = data
            (self.factory / path).write_bytes(data)
            self.rehash(path)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'gate-runtime'):
            prepare(self.factory, self.example)
        self.assertEqual(self.snapshot(), before)
        root, old, new, token = prepare(self.factory, self.example, gate_runtime=True)
        self.assertEqual(self.snapshot(), before)
        backup = apply(root, old, new, token, token)
        for name, data in original.items():
            self.assertEqual((backup / name).read_bytes(), data)
            self.assertEqual((root / name).read_bytes(), (ROOT / 'scripts' / Path(name).name).read_bytes())
        check(root, quiet=True)

    def test_custom_runtime_is_preserved_even_with_migration_flag(self):
        path = self.factory / 'dashboard/gates.py'
        path.write_bytes(path.read_bytes() + b'\n# Reviewed synthetic customization\n')
        self.rehash('dashboard/gates.py')
        before = self.snapshot()
        for migrate in (False, True):
            with self.subTest(gate_runtime=migrate):
                with self.assertRaisesRegex(ValueError, 'Customized/unsupported'):
                    prepare(self.factory, self.example, gate_runtime=migrate)
                self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
