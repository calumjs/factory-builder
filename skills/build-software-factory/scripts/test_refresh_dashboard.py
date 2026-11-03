"""Reviewed static HTML replacement using disposable synthetic factories only."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import dashboard
from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
import refresh_dashboard as refresh

AS_OF = '2026-11-03T12:00:00+00:00'


class StaticRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.factory = self.base/'project with spaces'/'factory [review]'
        config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name, body in render(config, research).items():
            path = self.factory/name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))
        self.contract(refresh.INDEX, b'<!doctype html>\r\n<h1>Custom dashboard design</h1>\r\n')

    def snapshot(self, root=None):
        root = root or self.factory
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def contract(self, name, data):
        (self.factory/name).write_bytes(data)
        path = self.factory/'manifest.json'; manifest = json.loads(path.read_bytes())
        manifest['contracts'][name] = digest(data)
        path.write_bytes((json.dumps(manifest, indent=2)+'\n').encode())

    def prepare(self):
        return refresh.prepare(self.factory, AS_OF)

    def invoke(self, *args):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8', str(ROOT/'scripts/refresh_dashboard.py'),
            '--factory', str(self.factory), *args], capture_output=True, text=True, encoding='utf-8')

    def test_preview_is_write_free_deterministic_and_names_custom_replacement(self):
        before = self.snapshot(self.base)
        first = self.invoke('--as-of', AS_OF)
        second = self.invoke('--as-of', AS_OF)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(self.snapshot(self.base), before)
        self.assertIn('including any custom design', first.stdout)
        self.assertIn(refresh.rawhash(before['project with spaces/factory [review]/dashboard/index.html']), first.stdout)
        self.assertIn('-<h1>Custom dashboard design</h1>', first.stdout)
        self.assertIn('AS OF: '+AS_OF, first.stdout)
        self.assertFalse((self.factory.parent/'.factory-update-backups').exists())

    def test_apply_changes_only_index_and_manifest_with_exact_original_backup(self):
        # A custom copied runtime is data, never imported or silently upgraded.
        self.contract('dashboard/dashboard.py', b'raise RuntimeError("MUST NEVER EXECUTE")\r\n')
        rows = gate_rows((self.factory/'verification.md').read_text(encoding='utf-8'))
        row = rows['G3']; row.update(required='no', result='FAILED', evidence='PRIVATE evidence', revision='synthetic-subject')
        text = (self.factory/'verification.md').read_text(encoding='utf-8')
        original = next(line for line in text.splitlines() if line.startswith('| G3 |'))
        (self.factory/'verification.md').write_text(text.replace(original, '| '+' | '.join(row.values())+' |'), encoding='utf-8')
        before = self.snapshot()
        with patch.object(dashboard, 'read', side_effect=AssertionError('No runtime reads')), patch.object(dashboard, 'run_records', side_effect=AssertionError('No run history')):
            plan = self.prepare()
            backup = refresh.apply(plan, plan['digest'])
        after = self.snapshot()
        self.assertEqual({name for name in before if before[name] != after[name]}, {refresh.INDEX, 'manifest.json'})
        self.assertEqual(self.snapshot(backup), {name: before[name] for name in plan['replacement']})
        manifest_before, manifest_after = json.loads(before['manifest.json']), json.loads(after['manifest.json'])
        manifest_before['contracts'][refresh.INDEX] = digest(after[refresh.INDEX])
        self.assertEqual(manifest_after, manifest_before)
        self.assertIn(b'WAIVED', after[refresh.INDEX]); self.assertIn(b'FAILED', after[refresh.INDEX])
        self.assertNotIn(b'PRIVATE evidence', after[refresh.INDEX])
        self.assertIn(refresh.UNAVAILABLE_RUNS.encode(), after[refresh.INDEX])
        self.assertIn(b'Project metrics and usage unavailable', after[refresh.INDEX])
        self.assertIn(b'Fixed-as-of static record snapshot', after[refresh.INDEX])
        check(self.factory, quiet=True)

    def test_cli_requires_digest_and_as_of_then_applies_with_spaces_and_brackets(self):
        before = self.snapshot(); plan = self.prepare()
        for args in (('--apply', '--approve-plan', plan['digest']), ('--as-of', AS_OF, '--apply'),
                     ('--as-of', AS_OF, '--apply', '--approve-plan', '0'*64)):
            result = self.invoke(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.snapshot(), before)
        result = self.invoke('--as-of', AS_OF, '--apply', '--approve-plan', plan['digest'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('APPLIED', result.stdout)
        self.assertEqual((self.factory/refresh.INDEX).read_bytes(), plan['replacement'][refresh.INDEX])

    def test_unrendered_living_bytes_and_mtimes_are_bound(self):
        for mode in ('whitespace', 'mtime', 'extra_directory'):
            with self.subTest(mode=mode):
                plan = self.prepare()
                path = self.factory/'task-plan.json'
                old = path.read_bytes(); meta = path.stat()
                if mode == 'whitespace':
                    path.write_bytes(old+b'\n')
                elif mode == 'mtime':
                    os.utime(path, ns=(meta.st_atime_ns, meta.st_mtime_ns+10_000_000))
                else:
                    (self.factory/'empty-directory').mkdir()
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'changed after preview'):
                    refresh.apply(plan, plan['digest'])
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.factory.parent/'.factory-update-backups').exists())
                if mode == 'whitespace':path.write_bytes(old)
                elif mode == 'extra_directory':(self.factory/'empty-directory').rmdir()

    def test_all_input_bytes_bind_even_when_output_does_not_change(self):
        plan = self.prepare()
        path = self.factory/'tools.json'; path.write_bytes(path.read_bytes()+b'\n')
        changed = self.prepare()
        self.assertEqual(plan['replacement'][refresh.INDEX], changed['replacement'][refresh.INDEX])
        self.assertNotEqual(plan['digest'], changed['digest'])
        with self.assertRaises(ValueError):refresh.apply(plan, plan['digest'])

    def test_fixed_timestamp_and_captured_source_metadata_are_used(self):
        path = self.factory/'task-plan.json'
        stamp = datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()
        os.utime(path, (stamp, stamp))
        plan = self.prepare(); output = plan['replacement'][refresh.INDEX].decode()
        self.assertIn('2026-11-01T00:00:00+00:00', output)
        self.assertIn(AS_OF.replace('T', ' '), output)
        self.assertIn('stale', output)
        later = refresh.prepare(self.factory, '2026-11-04T12:00:00Z')
        self.assertNotEqual(plan['digest'], later['digest'])
        for invalid in ('2026-11-03T12:00:00', 'nonsense', 'x'*65):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):refresh.prepare(self.factory, invalid)

    def test_directory_substitutions_refuse_identical_file_bytes(self):
        for relative in ('dashboard', '.'):
            with self.subTest(relative=relative):
                plan = self.prepare()
                target = self.factory/relative
                old = self.base/('preserved-'+target.name)
                target.rename(old)
                shutil.copytree(old, target)
                before = self.snapshot()
                with self.assertRaises(ValueError):refresh.apply(plan, plan['digest'])
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.factory.parent/'.factory-update-backups').exists())
                if relative == 'dashboard':
                    # Restore only this disposable copy; use one shell/runtime throughout.
                    self.assertIn(self.base.resolve(), target.resolve().parents)
                    shutil.rmtree(target); old.rename(target)

    def test_tampered_prepared_bytes_are_not_trusted(self):
        plan = self.prepare(); expected = plan['replacement'][refresh.INDEX]
        plan['replacement'][refresh.INDEX] = b'UNREVIEWED'
        refresh.apply(plan, plan['digest'])
        self.assertEqual((self.factory/refresh.INDEX).read_bytes(), expected)

    def test_parent_and_existing_backup_area_substitutions_require_new_review(self):
        area = self.factory.parent/'.factory-update-backups'; area.mkdir()
        plan = self.prepare()
        area.rename(self.base/'preserved-backup-area'); area.mkdir()
        with self.assertRaisesRegex(ValueError, 'changed after preview'):refresh.apply(plan, plan['digest'])
        plan = self.prepare(); parent = self.factory.parent
        preserved = self.base/'preserved-project'; parent.rename(preserved); shutil.copytree(preserved, parent)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed after preview'):refresh.apply(plan, plan['digest'])
        self.assertEqual(self.snapshot(), before)

    def test_capture_integrity_race_refuses_inconsistent_captured_contracts(self):
        stable = refresh.stable
        def capture_then_drift(root):
            result = stable(root)
            result['files']['config.json'] += b' '
            # Whitespace changes the normalized contract digest, even though JSON parses.
            return result
        before = self.snapshot()
        with patch.object(refresh, 'stable', side_effect=capture_then_drift):
            with self.assertRaisesRegex(ValueError, 'Captured factory'):self.prepare()
        self.assertEqual(self.snapshot(), before)

    def test_oversized_or_unsupported_living_data_refuses(self):
        path = self.factory/'tools.json'; original = path.read_bytes()
        path.write_bytes(original+b' '*262144)
        with self.assertRaisesRegex(ValueError, 'file-size'):self.prepare()
        path.write_bytes(original)
        path = self.factory/'task-plan.json'; value = json.loads(path.read_bytes())
        value['tasks'][0]['status'] = 'unsupported-status'; path.write_bytes(json.dumps(value).encode())
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'record structure'):self.prepare()
        self.assertEqual(self.snapshot(), before)

    def test_cli_escapes_untrusted_control_text_and_keeps_errors_private(self):
        self.contract(refresh.INDEX, '<h1>Custom λ design</h1>\x1b[31m\n'.encode('utf-8'))
        result = self.invoke('--as-of', AS_OF)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('\x1b', result.stdout); self.assertIn('\\u001b', result.stdout)
        self.assertIn('Custom λ design', result.stdout)
        (self.factory/'tools.json').write_bytes(b'{"PRIVATE-NOT-FOR-CLI":')
        result = self.invoke('--as-of', AS_OF)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('PRIVATE-NOT-FOR-CLI', result.stdout+result.stderr)

    def test_invalid_or_missing_contract_and_malformed_living_data_refuse_without_writes(self):
        for mode in ('index_drift', 'missing_index_contract', 'duplicate_json'):
            with self.subTest(mode=mode):
                baseline = self.snapshot()
                if mode == 'index_drift':(self.factory/refresh.INDEX).write_bytes(b'Unaccepted custom edit')
                elif mode == 'missing_index_contract':
                    path = self.factory/'manifest.json'; value = json.loads(path.read_bytes())
                    value['contracts'].pop(refresh.INDEX); path.write_bytes(json.dumps(value).encode())
                else:(self.factory/'tools.json').write_bytes(b'{"x":1,"x":2}')
                before = self.snapshot()
                with self.assertRaises((ValueError, RuntimeError)):self.prepare()
                self.assertEqual(self.snapshot(), before)
                for name, value in baseline.items():(self.factory/name).write_bytes(value)

    def test_renderer_run_label_drift_refuses(self):
        original = dashboard.page
        for count in (0, 2):
            with self.subTest(count=count), patch.object(dashboard, 'page', side_effect=lambda data: original(data).replace(refresh.EMPTY_RUNS, refresh.EMPTY_RUNS*count)):
                with self.assertRaisesRegex(ValueError, 'renderer run panel'):self.prepare()

    def test_late_living_edit_fails_after_write_without_rollback(self):
        plan = self.prepare(); before = self.snapshot()
        writer = refresh.updater.apply
        def concurrent(*args):
            backup = writer(*args)
            path = self.factory/'tools.json'; path.write_bytes(path.read_bytes()+b'\n')
            return backup
        with patch.object(refresh.updater, 'apply', side_effect=concurrent):
            with self.assertRaisesRegex(ValueError, 'Concurrent change detected after writes'):
                refresh.apply(plan, plan['digest'])
        self.assertEqual((self.factory/refresh.INDEX).read_bytes(), plan['replacement'][refresh.INDEX])
        self.assertEqual((self.factory/'tools.json').read_bytes(), before['tools.json']+b'\n')
        backup = self.factory.parent/'.factory-update-backups'/plan['digest']
        self.assertEqual(self.snapshot(backup), {name: before[name] for name in plan['replacement']})

    def test_interrupted_manifest_write_preserves_exact_backups_and_no_success(self):
        plan = self.prepare(); before = self.snapshot(); replace = refresh.updater.os.replace
        def interrupt(source, destination):
            if Path(destination).name == 'manifest.json':raise OSError('synthetic interruption')
            return replace(source, destination)
        with patch.object(refresh.updater.os, 'replace', side_effect=interrupt), self.assertRaises(OSError):
            refresh.apply(plan, plan['digest'])
        self.assertEqual((self.factory/'manifest.json').read_bytes(), before['manifest.json'])
        self.assertEqual((self.factory/refresh.INDEX).read_bytes(), plan['replacement'][refresh.INDEX])
        backup = self.factory.parent/'.factory-update-backups'/plan['digest']
        self.assertEqual(self.snapshot(backup), {name: before[name] for name in plan['replacement']})
        self.assertFalse((self.factory/'.operations-update.lock').exists())
        with self.assertRaises(ValueError):check(self.factory, quiet=True)

    def test_interruption_before_first_replace_leaves_factory_unchanged_and_backup_complete(self):
        plan = self.prepare(); before = self.snapshot()
        with patch.object(refresh.updater.os, 'replace', side_effect=OSError('synthetic interruption')), self.assertRaises(OSError):
            refresh.apply(plan, plan['digest'])
        self.assertEqual(self.snapshot(), before)
        backup = self.factory.parent/'.factory-update-backups'/plan['digest']
        self.assertEqual(self.snapshot(backup), {name: before[name] for name in plan['replacement']})

    def test_backup_tampering_after_write_is_not_reported_as_success(self):
        plan = self.prepare(); writer = refresh.updater.apply
        def tamper(*args):
            backup = writer(*args)
            (backup/refresh.INDEX).write_bytes(b'tampered backup')
            return backup
        with patch.object(refresh.updater, 'apply', side_effect=tamper):
            with self.assertRaisesRegex(ValueError, 'backup differs'):refresh.apply(plan, plan['digest'])

    def test_occupied_backup_refuses_before_any_factory_write(self):
        (self.factory.parent/'.factory-update-backups').mkdir()
        plan = self.prepare(); before = self.snapshot()
        backup = self.factory.parent/'.factory-update-backups'/plan['digest']; backup.mkdir(parents=True)
        (backup/'preserve.txt').write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'Backup already exists'):refresh.apply(plan, plan['digest'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((backup/'preserve.txt').read_bytes(), b'preserve')


if __name__ == '__main__':unittest.main()
