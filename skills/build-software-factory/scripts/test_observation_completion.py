"""Explicit observation export using synthetic local records, not application runs."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import observation_drafts as exporter
from gates import gate_rows
from incremental_records import GATE_OBSERVATION_FIELDS, gate_change, preview
from scaffold import ROOT, render


class ObservationCompletionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'factory'
        self.root.mkdir()
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text())
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text())
        self.recipes = {gate: {'command': ['python', 'synthetic.py', gate],
            'environment': 'fixture-' + gate, 'env_names': [],
            'target': {'kind': 'artifact', 'value': 'artifact-' + gate, 'base_url_env': None}}
            for gate in ('G1', 'G2', 'G3')}
        self.config['operations'] = {'smoke_gates': {'checks': self.recipes}, 'done_videos': {'enabled': True}}
        for name, body in render(self.config, self.research).items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def observation(self, gate='G1'):
        return {'gate': gate, 'result': 'PASSED', 'revision': 'synthetic-subject-S1',
            'environment': 'fixture-' + gate, 'target': 'artifact-' + gate,
            'checked_at': '2026-10-30T12:00:00+00:00', 'exit_status': '0',
            'evidence': 'Synthetic supplied observation; no application run'}

    def args(self, observation):
        args = ['--factory', str(self.root), '--observation']
        for key, value in observation.items():
            args.extend(['--' + key.replace('_', '-'), value])
        return args

    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = exporter.main(args)
        return code, out.getvalue(), err.getvalue()

    def assert_refused(self, observation):
        before = self.snapshot()
        code, out, err = self.invoke(self.args(observation))
        self.assertEqual(code, 2)
        self.assertEqual(out, '')
        self.assertIn('ERROR:', err)
        self.assertEqual(before, self.snapshot())
        return err

    def edit(self, gate, **changes):
        path = self.root / 'verification.md'
        text = path.read_text(encoding='utf-8')
        row = gate_rows(text)[gate]
        row.update(changes)
        lines = ['| ' + ' | '.join(row.values()) + ' |' if line.startswith('| ' + gate + ' |') else line
                 for line in text.splitlines()]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def test_cli_exact_output_round_trips_existing_writer_without_factory_changes(self):
        before = self.snapshot()
        for gate in ('G1', 'G2', 'G3'):
            item = self.observation(gate)
            code, out, err = self.invoke(self.args(item))
            self.assertEqual(code, 0, err)
            exported = json.loads(out)
            self.assertEqual(exported, item)
            self.assertEqual(set(exported), GATE_OBSERVATION_FIELDS)
            self.assertIn('OPERATOR-SUPPLIED', err)
            self.assertIn('No factory record was written', err)
            _, _, _, proposed, _ = preview(self.root, 'gate', exported)
            row = gate_rows(proposed.decode())[gate]
            self.assertEqual(row['environment'], item['environment'])
            self.assertEqual(row['target'], item['target'])
            self.assertEqual(row['result'], 'PASSED')
        self.assertEqual(before, self.snapshot())

    def test_each_observed_flag_is_required_by_presence(self):
        for field in GATE_OBSERVATION_FIELDS - {'gate'}:
            item = self.observation()
            del item[field]
            with self.subTest(field=field):
                self.assertIn('requires --result', self.assert_refused(item))

    def test_no_implicit_mode_or_multiple_gates(self):
        args = self.args(self.observation())
        args.remove('--observation')
        code, out, err = self.invoke(args)
        self.assertEqual((code, out), (2, ''))
        self.assertIn('Observed fields require --observation', err)
        for extra in ('G2', 'G1'):
            code, out, err = self.invoke(self.args(self.observation()) + ['--gate', extra])
            self.assertEqual((code, out), (2, ''))
            self.assertIn('exactly one', err)

    def test_planned_settings_cannot_fill_missing_actuals_or_fix_mismatches(self):
        for gate in ('G1', 'G3'):
            for field, value in (('environment', ''), ('environment', 'unconfirmed'),
                                 ('environment', 'another-fixture'), ('target', ''),
                                 ('target', 'unconfirmed'), ('target', 'another-actual-artifact')):
                with self.subTest(gate=gate, field=field, value=value):
                    self.assert_refused({**self.observation(gate), field: value})

    def test_optional_pass_still_requires_complete_observed_evidence(self):
        self.edit('G1', required='no', result='FAILED', evidence='Preserved failed fixture record')
        for field, value in (('revision', ''), ('evidence', ''), ('checked_at', ''),
                             ('checked_at', '2026-10-30T12:00:00'), ('exit_status', '1')):
            with self.subTest(field=field, value=value):
                self.assert_refused({**self.observation(), field: value})
        result = exporter.validated_observation(self.root, self.observation())
        self.assertNotIn('required', result)
        self.assertEqual(gate_rows((self.root / 'verification.md').read_text())['G1']['result'], 'FAILED')

    def test_negative_mismatches_and_explicit_unknowns_remain_exactly_supplied(self):
        before = self.snapshot()
        for result in ('FAILED', 'BLOCKED', 'NOT RUN'):
            item = {**self.observation(), 'result': result, 'environment': 'unconfirmed',
                    'target': 'observed-different-target', 'revision': '', 'checked_at': '',
                    'exit_status': '', 'evidence': ''}
            code, out, err = self.invoke(self.args(item))
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out), item)
            _, _, _, proposed, _ = preview(self.root, 'gate', json.loads(out))
            row = gate_rows(proposed.decode())['G1']
            self.assertEqual(row['environment'], 'unconfirmed')
            self.assertEqual(row['target'], 'observed-different-target')
            self.assertEqual(row['result'], result)
            for value in ('', '   '):
                self.assertIn('explicit environment', self.assert_refused({**item, 'environment': value}))
        self.assertEqual(before, self.snapshot())

    def test_v1_requires_prior_g3_subject_target_result_and_order(self):
        video = {**self.observation('V1'), 'target': 'artifact-G3', 'exit_status': 'manual',
                 'checked_at': '2026-10-30T12:01:00Z'}
        self.assert_refused(video)  # G3 is still NOT RUN.
        path = self.root / 'verification.md'
        path.write_bytes(gate_change(path.read_text(encoding='utf-8'), self.config, self.research,
                                    self.observation('G3')))
        self.assertEqual(exporter.validated_observation(self.root, video), video)
        for changes in ({'revision': 'synthetic-subject-S2'}, {'target': 'another-target'},
                        {'checked_at': '2026-10-30T11:59:00Z'}):
            self.assert_refused({**video, **changes})
        self.edit('G3', result='FAILED', exit_status='1')
        self.assert_refused(video)
        self.edit('G3', required='no')
        self.assertEqual(exporter.validated_observation(self.root, video), video)
        self.assertEqual(gate_rows(path.read_text())['G3']['required'], 'no')

    def test_existing_writer_errors_are_private_and_failure_has_no_json(self):
        secret = 'private-sentinel-do-not-print'
        for field, value in (('result', secret), ('evidence', secret + '|bad'),
                             ('checked_at', secret), ('gate', secret)):
            err = self.assert_refused({**self.observation(), field: value})
            self.assertNotIn(secret, err)
        with patch('observation_drafts.gate_change', side_effect=ValueError(secret)):
            self.assertNotIn(secret, self.assert_refused(self.observation()))

    def test_input_schema_field_and_output_bounds_refuse_before_export(self):
        for item in ([], {}, {**self.observation(), 'required': 'no'},
                     {**self.observation(), 'result': True},
                     {**self.observation(), 'evidence': 'x' * 8193}):
            with self.subTest(item_type=type(item).__name__), self.assertRaises(exporter.DraftInputError):
                exporter.validated_observation(self.root, item)
        with patch('observation_drafts.MAX_OUTPUT', 10):
            self.assertIn('output exceeds', self.assert_refused(self.observation()))

    def test_changed_snapshot_fails_without_stdout_or_writes(self):
        read = exporter.snapshot_factory
        calls = []
        def changed(root):
            files, directories = read(root)
            calls.append(True)
            if len(calls) == 2:
                files['verification.md'] += b'\n'
            return files, directories
        with patch('observation_drafts.snapshot_factory', changed):
            self.assertIn('changed', self.assert_refused(self.observation()))

    def test_export_does_not_launch_or_write_and_draft_mode_is_unchanged(self):
        before = self.snapshot()
        original_open = Path.open
        def read_only(path, mode='r', *args, **kwargs):
            self.assertFalse(any(flag in mode for flag in 'wax+'))
            return original_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', read_only), patch('subprocess.Popen', side_effect=AssertionError('process')), patch('os.system', side_effect=AssertionError('shell')):
            code, out, err = self.invoke(self.args(self.observation()))
            self.assertEqual(code, 0, err)
            self.assertEqual(json.loads(out), self.observation())
            code, out, err = self.invoke(['--factory', str(self.root), '--gate', 'G1', '--gate', 'G2'])
            self.assertEqual(code, 0, err)
            self.assertEqual(err, '')
            draft = json.loads(out)
            self.assertEqual(set(draft), {'draft_version', 'notice', 'drafts'})
            for entry in draft['drafts']:
                self.assertEqual(entry['observation']['result'], 'NOT RUN')
                self.assertEqual(entry['observation']['environment'], 'unconfirmed')
                self.assertEqual(entry['observation']['target'], '')
        self.assertEqual(before, self.snapshot())

    def test_public_entrypoint_returns_standalone_json_without_artifacts(self):
        before = self.snapshot()
        command = [sys.executable, '-B', str(ROOT / 'scripts/observation_drafts.py')]
        result = subprocess.run(command + self.args(self.observation()), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.observation())
        self.assertIn('OPERATOR-SUPPLIED', result.stderr)
        result = subprocess.run(command + self.args({**self.observation('G3'), 'target': ''}), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
