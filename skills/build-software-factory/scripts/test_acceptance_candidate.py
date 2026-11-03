"""Disposable candidate/recovery fixtures; no project checks or active adoption."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import acceptance_candidate as candidate
import acceptance_plan as planner
from gates import gate_rows
from integrity import check
import recover_factory as recovery
from scaffold import ROOT
import test_acceptance_plan as fixtures


class AcceptanceCandidateTests(unittest.TestCase):
    write = fixtures.AcceptancePlanTests.write
    snapshot = fixtures.AcceptancePlanTests.snapshot
    pin = fixtures.AcceptancePlanTests.pin
    update_contract = fixtures.AcceptancePlanTests.update_contract

    def setUp(self):
        fixtures.AcceptancePlanTests.setUp(self)
        self.outputs = self.parent / 'outputs [literal] with spaces'
        self.outputs.mkdir()
        self.output = self.outputs / 'inactive candidate [one]'
        self.reference = 'SYNTHETIC independently accepted original baseline'

    def plan(self, output=None):
        return candidate.prepare(self.root, self.request, self.pin(), self.reference, self.output if output is None else output)

    def materialize(self):
        result = self.plan()
        backup = candidate.apply(result, result['digest'], True)
        return result, backup

    def bytes_at(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def test_preview_is_write_free_and_binds_destination_parent_and_original_inventory(self):
        paths = set(self.parent.rglob('*'))
        before = self.snapshot()
        result = self.plan()
        self.assertEqual(set(self.parent.rglob('*')), paths)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(result['digest'], recovery.rawhash(planner.canonical(result['plan'])))
        self.assertNotEqual(result['digest'], self.plan(self.outputs / 'different candidate')['digest'])
        plan = result['plan']
        self.assertEqual(plan['expected_candidate']['files']['manifest.json'], self.pin())
        self.assertEqual(plan['directory_guards']['output_parent']['identity'], candidate.identity(self.outputs))
        self.assertEqual(plan['synchronization']['plan']['source_inventory']['files'], {name: recovery.rawhash(raw) for name, raw in before.items()})
        self.assertIsNone(plan['directory_guards']['backup_parent']['identity'])

    def test_materialization_keeps_original_manifest_backup_bytes_history_and_optional_gates(self):
        before = self.snapshot()
        result, backup = self.materialize()
        plan = candidate.verify_output(self.output, backup, result['digest'])
        self.assertEqual(planner.canonical(plan), planner.canonical(result['plan']))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.bytes_at(backup / 'source'), before)
        after = self.bytes_at(self.output)
        self.assertEqual(after['manifest.json'], before['manifest.json'])
        with self.assertRaises(ValueError):
            check(self.output, quiet=True)  # Deliberate drift: it is not a registered factory.
        changed = set(plan['synchronization']['plan']['candidate_changes'])
        for name in set(before) - changed:
            self.assertEqual(after[name], before[name], name)
        rows = gate_rows(after['verification.md'].decode())
        for name, row in gate_rows(before['verification.md'].decode()).items():
            self.assertEqual(rows[name], row)
        self.assertEqual((rows[self.ident]['required'], rows[self.ident]['result']), ('yes', 'NOT RUN'))
        self.assertEqual(json.loads(after['task-plan.json'])['events'], json.loads(before['task-plan.json'])['events'])
        self.assertEqual(set(path.name for path in backup.iterdir()), {'source', 'candidate.json', 'decisions.json', 'COMPLETED.json'})
        self.assertNotIn('COMPLETED.json', after)
        self.assertNotIn('candidate.json', after)

    def test_two_distinct_review_digests_complete_existing_recovery_only_in_disposable_outputs(self):
        before = self.snapshot()
        first, original_backup = self.materialize()
        handoff = candidate.handoff(self.output, original_backup, first['digest'])
        inputs = handoff['recovery_inputs']
        second_output = self.outputs / 'separately recovered snapshot'
        decisions = planner.read_input(inputs['decisions'], planner.MAX_REQUEST)
        second = recovery.prepare(inputs['factory'], inputs['baseline'], second_output,
                                  inputs['baseline_manifest_sha256'], inputs['baseline_reference'], decisions)
        self.assertNotEqual(first['digest'], second['plan'])
        candidate_before = self.bytes_at(self.output)
        recovery_backup = recovery.apply(second, second['plan'], True)
        self.assertTrue(recovery.verify_output(second_output, recovery_backup, second['plan']))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.bytes_at(original_backup / 'source'), before)
        self.assertEqual(self.bytes_at(recovery_backup / 'source'), candidate_before)
        self.assertEqual(self.bytes_at(self.output), candidate_before)
        self.assertEqual((second_output / 'manifest.json').read_bytes(), second['manifest'])
        self.assertNotEqual((second_output / 'manifest.json').read_bytes(), before['manifest.json'])
        self.assertNotIn(self.ident, {f'A{i+1}' for i in range(len(json.loads((self.root / 'config.json').read_bytes())['acceptance']))})

    def test_explicit_new_map_survives_candidate_and_named_recovery_registration(self):
        (self.root / 'test-map.json').unlink()
        path = self.root / 'manifest.json'
        manifest = json.loads(path.read_bytes())
        del manifest['contracts']['test-map.json']
        path.write_text(json.dumps(manifest), encoding='utf-8')
        self.request['test_map']['register_reason'] = 'Explicit synthetic immutable design registration'
        before = self.snapshot()
        first, backup = self.materialize()
        self.assertNotIn('test-map.json', self.bytes_at(backup / 'source'))
        self.assertIn('test-map.json', self.bytes_at(self.output))
        decisions = planner.read_input(backup / 'decisions.json', planner.MAX_REQUEST)
        second = recovery.prepare(self.output, backup / 'source', self.outputs / 'unused new-map recovery', self.pin(), self.reference, decisions)
        self.assertEqual(second['deltas']['register'], {'test-map.json'})
        self.assertEqual(self.snapshot(), before)
        candidate.verify_output(self.output, backup, first['digest'])

    def test_actual_literal_verification_argv_runs_without_shell_and_preserves_source(self):
        result, backup = self.materialize()
        before = self.snapshot()
        argv = candidate.handoff(self.output, backup, result['digest'])['verify_argv']
        executed = subprocess.run(argv, shell=False, capture_output=True, text=True)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        output = json.loads(executed.stdout)
        self.assertEqual(output['candidate'], str(self.output))
        self.assertEqual(output['backup'], str(backup))
        self.assertEqual(output['plan_id'], result['digest'])
        self.assertEqual(self.snapshot(), before)

    def test_wrong_digest_or_missing_stable_inputs_write_nothing(self):
        result = self.plan()
        before = self.snapshot()
        for approved, stable in (('0' * 64, True), (result['digest'], False), (None, True)):
            with self.subTest(approved=approved, stable=stable), self.assertRaises(ValueError):
                candidate.apply(result, approved, stable)
            self.assertFalse(self.output.exists())
            self.assertFalse((self.outputs / candidate.BACKUPS).exists())
            self.assertEqual(self.snapshot(), before)

    def test_cached_plan_request_or_source_tamper_requires_fresh_review(self):
        original = self.plan()
        for key in ('output', 'synchronization', 'expected_candidate'):
            modified = copy.deepcopy(original)
            if key == 'output':
                modified['plan']['output'] = str(self.outputs / 'different')
            elif key == 'synchronization':
                modified['plan'][key]['plan']['request']['criterion'] = 'Different proposed scope'
            else:
                modified['plan'][key]['files']['verification.md'] = 'f' * 64
            modified['digest'] = recovery.rawhash(planner.canonical(modified['plan']))
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate.apply(modified, original['digest'], True)
        # Even a newly supplied hash cannot make inconsistent cached bytes match
        # a freshly recomputed plan. A genuinely new destination needs its own review.
        modified = copy.deepcopy(original)
        modified['plan']['expected_candidate']['files']['verification.md'] = 'f' * 64
        modified['digest'] = recovery.rawhash(planner.canonical(modified['plan']))
        with self.assertRaises(ValueError):
            candidate.apply(modified, modified['digest'], True)
        with (self.root / 'learning-log.md').open('ab') as stream:
            stream.write(b'\nLater real learning must survive\n')
        changed = self.snapshot()
        with self.assertRaises(ValueError):
            candidate.apply(original, original['digest'], True)
        self.assertEqual(self.snapshot(), changed)
        self.assertFalse((self.outputs / candidate.BACKUPS).exists())

    def test_parent_replacement_invalidates_review_without_writes(self):
        result = self.plan()
        moved = self.parent / 'former output parent'
        self.outputs.rename(moved)
        self.outputs.mkdir()
        with self.assertRaises(ValueError):
            candidate.apply(result, result['digest'], True)
        self.assertEqual(list(self.outputs.iterdir()), [])
        self.assertEqual(list(moved.iterdir()), [])

    def test_overlap_aliases_occupied_targets_and_backup_files_refuse(self):
        for output in (self.root / 'nested', self.root / '..' / self.root.name / 'nested', self.root,
                       self.outputs / candidate.BACKUPS):
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.plan(output)
        occupied = self.outputs / 'occupied'
        occupied.write_bytes(b'Preserve occupied target')
        with self.assertRaises(ValueError):
            self.plan(occupied)
        self.assertEqual(occupied.read_bytes(), b'Preserve occupied target')
        backup_area = self.outputs / candidate.BACKUPS
        backup_area.write_bytes(b'Preserve conflicting backup file')
        with self.assertRaises(ValueError):
            self.plan()
        self.assertEqual(backup_area.read_bytes(), b'Preserve conflicting backup file')

    def test_existing_attempt_is_never_overwritten_or_resumed(self):
        backup_area = self.outputs / candidate.BACKUPS
        backup_area.mkdir()
        result = self.plan()
        occupied = backup_area / result['digest']
        occupied.mkdir()
        sentinel = occupied / 'preserve.txt'
        sentinel.write_bytes(b'Earlier attempt')
        with self.assertRaises(FileExistsError):
            candidate.apply(result, result['digest'], True)
        self.assertEqual(sentinel.read_bytes(), b'Earlier attempt')
        self.assertFalse(self.output.exists())

    def test_writer_change_after_backup_preserves_change_and_never_creates_candidate(self):
        result = self.plan()
        real_copy = candidate.copy_snapshot
        def copying(path, *args, **kwargs):
            real_copy(path, *args, **kwargs)
            if path.name == 'source':
                with (self.root / 'learning-log.md').open('ab') as stream:
                    stream.write(b'\nConcurrent original edit\n')
        with patch.object(candidate, 'copy_snapshot', side_effect=copying):
            with self.assertRaisesRegex(ValueError, 'Original factory changed'):
                candidate.apply(result, result['digest'], True)
        self.assertFalse(self.output.exists())
        self.assertIn(b'Concurrent original edit', (self.root / 'learning-log.md').read_bytes())
        backup = self.outputs / candidate.BACKUPS / result['digest']
        self.assertFalse((backup / 'COMPLETED.json').exists())

    def test_writer_change_during_candidate_copy_quarantines_partial_output(self):
        result = self.plan()
        real_copy = candidate.copy_snapshot
        def copying(path, *args, **kwargs):
            real_copy(path, *args, **kwargs)
            if path == self.output:
                with (self.root / 'learning-log.md').open('ab') as stream:
                    stream.write(b'\nConcurrent original edit\n')
        with patch.object(candidate, 'copy_snapshot', side_effect=copying):
            with self.assertRaisesRegex(ValueError, 'Original factory changed'):
                candidate.apply(result, result['digest'], True)
        backup = self.outputs / candidate.BACKUPS / result['digest']
        self.assertTrue((self.output / recovery.RESERVED).is_file())
        self.assertFalse((self.output / 'manifest.json').exists())
        self.assertFalse((backup / 'COMPLETED.json').exists())
        with self.assertRaises(ValueError):
            candidate.verify_output(self.output, backup, result['digest'])
        self.assertIn(b'Concurrent original edit', (self.root / 'learning-log.md').read_bytes())

    def test_interruption_before_manifest_without_marker_is_still_unverified(self):
        before = self.snapshot()
        result = self.plan()
        real_write = candidate.write_file
        def writing(path, data):
            if path == self.output / 'manifest.json':
                raise KeyboardInterrupt('SYNTHETIC interruption')
            return real_write(path, data)
        with patch.object(candidate, 'write_file', side_effect=writing), patch.object(candidate, 'quarantine'):
            with self.assertRaises(KeyboardInterrupt):
                candidate.apply(result, result['digest'], True)
        backup = self.outputs / candidate.BACKUPS / result['digest']
        self.assertFalse((self.output / 'manifest.json').exists())
        self.assertFalse((self.output / recovery.RESERVED).exists())
        self.assertFalse((backup / 'COMPLETED.json').exists())
        with self.assertRaises(ValueError):
            candidate.verify_output(self.output, backup, result['digest'])
        self.assertEqual(self.snapshot(), before)

    def test_failure_after_original_manifest_write_keeps_backup_and_quarantine(self):
        before = self.snapshot()
        result = self.plan()
        real_verify = candidate.verify_contents
        def verifying(*args, **kwargs):
            value = real_verify(*args, **kwargs)
            if args[-1] is False:
                raise OSError('SYNTHETIC post-manifest failure')
            return value
        with patch.object(candidate, 'verify_contents', side_effect=verifying):
            with self.assertRaises(OSError):
                candidate.apply(result, result['digest'], True)
        backup = self.outputs / candidate.BACKUPS / result['digest']
        self.assertEqual((self.output / 'manifest.json').read_bytes(), before['manifest.json'])
        self.assertTrue((self.output / recovery.RESERVED).exists())
        self.assertFalse((backup / 'COMPLETED.json').exists())
        self.assertEqual(self.bytes_at(backup / 'source'), before)
        self.assertEqual(self.snapshot(), before)

    def test_partial_completion_is_not_success(self):
        result = self.plan()
        real_write = candidate.write_file
        def writing(path, data):
            if path.name == 'COMPLETED.json':
                with path.open('xb') as stream:
                    stream.write(b'{')
                raise OSError('SYNTHETIC incomplete completion write')
            return real_write(path, data)
        with patch.object(candidate, 'write_file', side_effect=writing):
            with self.assertRaises(OSError):
                candidate.apply(result, result['digest'], True)
        backup = self.outputs / candidate.BACKUPS / result['digest']
        self.assertTrue((self.output / recovery.RESERVED).exists())
        with self.assertRaises(ValueError):
            candidate.verify_output(self.output, backup, result['digest'])

    def test_failure_does_not_mark_a_swapped_foreign_candidate_directory(self):
        result = self.plan()
        real_copy = candidate.copy_snapshot
        moved = self.outputs / 'preserved original partial candidate'
        # Both rename endpoints are fixed descendants of this disposable test root.
        self.output.resolve().relative_to(self.parent.resolve())
        moved.resolve().relative_to(self.parent.resolve())
        def copying(path, *args, **kwargs):
            real_copy(path, *args, **kwargs)
            if path == self.output:
                path.rename(moved)
                path.mkdir()
                (path / 'foreign.txt').write_bytes(b'Preserve foreign directory')
                raise OSError('SYNTHETIC directory replacement')
        with patch.object(candidate, 'copy_snapshot', side_effect=copying):
            with self.assertRaises(OSError):
                candidate.apply(result, result['digest'], True)
        self.assertEqual({path.name for path in self.output.iterdir()}, {'foreign.txt'})
        self.assertEqual((self.output / 'foreign.txt').read_bytes(), b'Preserve foreign directory')
        self.assertTrue(moved.is_dir())

    def test_verification_refuses_modified_missing_extra_output_backup_and_metadata(self):
        result, backup = self.materialize()
        original_record = planner.read_input(backup / 'candidate.json', planner.MAX_PLAN)
        extra_record = copy.deepcopy(original_record)
        extra_record['unexpected'] = True
        bool_completion = planner.read_input(backup / 'COMPLETED.json', 4096)
        bool_completion['schema_version'] = True
        float_completion = copy.deepcopy(bool_completion)
        float_completion['schema_version'] = 1.0
        changes = [
            (self.output / 'verification.md', b'Changed living evidence'),
            (self.output / 'manifest.json', b'{}'),
            (self.output / 'private-custom.md', None),
            (self.output / 'extra.txt', b'Unexpected candidate file'),
            (backup / 'source' / 'private-custom.md', b'Changed original backup'),
            (backup / 'decisions.json', b'{"accept_changed":[],"register":[],"remove":[]}'),
            (backup / 'candidate.json', candidate.encoded(extra_record)),
            (backup / 'COMPLETED.json', candidate.encoded(bool_completion)),
            (backup / 'COMPLETED.json', candidate.encoded(float_completion)),
            (backup / 'COMPLETED.json', None),
            (backup / 'extra.txt', b'Unexpected metadata'),
        ]
        before = self.snapshot()
        for path, raw in changes:
            previous = path.read_bytes() if path.exists() else None
            try:
                if raw is None:
                    path.unlink()
                else:
                    path.write_bytes(raw)
                with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                    candidate.verify_output(self.output, backup, result['digest'])
            finally:
                if previous is None:
                    path.unlink()
                else:
                    path.write_bytes(previous)
        for root in (self.output, backup / 'source', backup):
            extra = root / 'unexpected-empty-directory'
            extra.mkdir()
            with self.subTest(root=root), self.assertRaises(ValueError):
                candidate.verify_output(self.output, backup, result['digest'])
            extra.rmdir()
        self.assertEqual(self.snapshot(), before)
        candidate.verify_output(self.output, backup, result['digest'])

    def test_verification_requires_explicit_roots_and_external_original_digest(self):
        result, backup = self.materialize()
        with self.assertRaises(ValueError):
            candidate.verify_output(self.root, backup, result['digest'])
        with self.assertRaises(ValueError):
            candidate.verify_output(self.output, backup, '0' * 64)
        path = backup / 'candidate.json'
        record = planner.read_input(path, planner.MAX_PLAN)
        record['plan']['output'] = str(self.root)
        record['digest'] = recovery.rawhash(planner.canonical(record['plan']))
        path.write_bytes(candidate.encoded(record))
        with self.assertRaises(ValueError):
            candidate.verify_output(self.output, backup, result['digest'])

    def test_cli_preview_bad_apply_and_final_handoff_use_exact_arguments(self):
        request = self.parent / 'request [literal].json'
        request.write_text(json.dumps(self.request), encoding='utf-8')
        args = [sys.executable, '-B', str(ROOT / 'scripts/acceptance_candidate.py'), '--factory', str(self.root),
                '--request', str(request), '--baseline-manifest-sha256', self.pin(), '--baseline-reference', self.reference,
                '--output', str(self.output)]
        before = self.snapshot()
        paths = set(self.parent.rglob('*'))
        preview = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        result = json.loads(preview.stdout)
        self.assertEqual(set(self.parent.rglob('*')), paths)
        rejected = subprocess.run(args + ['--apply', '--approve-plan', '0' * 64, '--stable-inputs'], capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, '')
        self.assertEqual(set(self.parent.rglob('*')), paths)
        changed_request = copy.deepcopy(self.request)
        changed_request['criterion'] = 'Changed scope after the reviewed preview'
        request.write_text(json.dumps(changed_request), encoding='utf-8')
        rejected = subprocess.run(args + ['--apply', '--approve-plan', result['digest'], '--stable-inputs'], capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, '')
        self.assertFalse(self.output.exists())
        self.assertFalse((self.outputs / candidate.BACKUPS).exists())
        request.write_text(json.dumps(self.request), encoding='utf-8')
        applied = subprocess.run(args + ['--apply', '--approve-plan', result['digest'], '--stable-inputs'], capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        handoff = json.loads(applied.stdout)
        self.assertEqual(handoff['candidate'], str(self.output))
        self.assertIn('separate', handoff['notice'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(subprocess.run(handoff['verify_argv'], capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
