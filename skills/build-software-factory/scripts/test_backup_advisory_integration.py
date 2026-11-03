"""Synthetic helper CLIs report write success separately from optional ignore advice."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import add_dashboard
import recover_factory
import update_operations
from backup_advisory import result
from integrity import check
from scaffold import ROOT, render


class BackupAdvisoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.factory = self.base / '.software-factory'
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.files = render(config, research)
        self.write_factory(self.factory)

    def write_factory(self, root, dashboard=True):
        files = dict(self.files)
        if not dashboard:
            files = {name: body for name, body in files.items() if not name.startswith('dashboard/')}
            manifest = json.loads(files['manifest.json'])
            manifest['contracts'] = {name: value for name, value in manifest['contracts'].items() if not name.startswith('dashboard/')}
            files['manifest.json'] = json.dumps(manifest)
        for name, body in files.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def cli(self, module, args):
        output = io.StringIO()
        with patch.object(sys, 'argv', [module.__name__+'.py', *map(str, args)]), redirect_stdout(output):
            module.main()
        return output.getvalue()

    def test_update_advisory_only_after_completed_backup(self):
        changes = {'done_videos': {'enabled': True}}
        path = self.base / 'changes.json'; path.write_text(json.dumps(changes), encoding='utf-8')
        args = ['--factory', self.factory, '--operations', path]
        plan = update_operations.prepare(self.factory, changes)[3]
        with patch('update_operations.inspect_backup_directory', return_value=result('unknown')) as advisory:
            self.assertIn('PREVIEW ONLY', self.cli(update_operations, args)); advisory.assert_not_called()
            with self.assertRaises(ValueError): self.cli(update_operations, args+['--apply', '--approve-plan', 'wrong'])
            advisory.assert_not_called()
            text = self.cli(update_operations, args+['--apply', '--approve-plan', plan])
            advisory.assert_called_once_with(self.base, self.base / '.factory-update-backups')
        self.assertLess(text.index('APPLIED narrow'), text.index('ADVISORY:'))
        self.assertIn('unknown', text); self.assertIn('does not change or determine', text)
        self.assertTrue((self.base / '.factory-update-backups' / plan / 'manifest.json').is_file())
        check(self.factory, quiet=True)

    def test_no_change_apply_does_not_run_advisory(self):
        path = self.base / 'empty.json'; path.write_text('{}', encoding='utf-8')
        plan = update_operations.prepare(self.factory, {})[3]
        with patch('update_operations.inspect_backup_directory') as advisory:
            text = self.cli(update_operations, ['--factory', self.factory, '--operations', path, '--apply', '--approve-plan', plan])
            advisory.assert_not_called()
        self.assertIn('NO FILES WRITTEN', text)
        self.assertFalse((self.base / '.factory-update-backups').exists())

    def test_dashboard_emits_guidance_without_changing_ignore_policy(self):
        factory = self.base / 'without-dashboard'; self.write_factory(factory, dashboard=False)
        ignore = self.base / '.gitignore'; ignore.write_bytes(b'# SYNTHETIC operator rules\ncustom-output/\n')
        before = ignore.read_bytes(); args = ['--factory', factory]
        plan = add_dashboard.prepare(factory)[3]
        with patch('add_dashboard.inspect_backup_directory', return_value=result('tracked')) as advisory:
            preview = self.cli(add_dashboard, args); advisory.assert_not_called()
            for name in ('factory-overview.html', 'factory-overview.json', '.factory-update-backups/', '.factory-recovery-backups/'):
                self.assertIn(name, preview)
            text = self.cli(add_dashboard, args+['--apply', '--approve-plan', plan])
            advisory.assert_called_once_with(self.base, self.base / '.factory-update-backups')
        self.assertLess(text.index('APPLIED;'), text.index('ADVISORY:'))
        self.assertIn('already tracked', text); self.assertEqual(ignore.read_bytes(), before)
        check(factory, quiet=True)

    def test_recovery_reports_verified_snapshot_before_unknown_advisory(self):
        baseline = self.base / 'accepted'; self.write_factory(baseline)
        output = self.base / 'recovered'; decisions = {'accept_changed': [], 'register': [], 'remove': []}
        path = self.base / 'decisions.json'; path.write_text(json.dumps(decisions), encoding='utf-8')
        pin = recover_factory.rawhash((baseline / 'manifest.json').read_bytes())
        prepared = recover_factory.prepare(self.factory, baseline, output, pin, 'SYNTHETIC reviewed baseline', decisions)
        args = ['--factory', self.factory, '--baseline', baseline, '--output', output,
                '--baseline-manifest-sha256', pin, '--baseline-reference', 'SYNTHETIC reviewed baseline', '--decisions', path]
        with patch('backup_advisory.inspect_backup_directory', return_value=result('unknown')) as advisory:
            self.assertIn('PREVIEW ONLY', self.cli(recover_factory, args)); advisory.assert_not_called()
            text = self.cli(recover_factory, args+['--apply', '--approve-plan', prepared['plan'], '--stable-inputs'])
            advisory.assert_called_once_with(self.base, self.base / '.factory-recovery-backups')
        self.assertLess(text.index('RECOVERED SNAPSHOT ONLY'), text.index('ADVISORY:'))
        recover_factory.verify_output(output, self.base / '.factory-recovery-backups' / prepared['plan'], prepared['plan'])
        check(output, quiet=True)


if __name__ == '__main__': unittest.main()
