"""Offline drafts from disposable factories; no application checks are executed."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import observation_drafts as drafts
from gates import gate_rows, problems, requirements
from incremental_records import preview
from integrity import digest
from scaffold import ROOT, render


class ObservationDraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'factory'
        self.root.mkdir()
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text())
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text())
        self.recipes = {g: {'command': ['python', 'synthetic.py', g, 'argument | data'],
                           'environment': 'synthetic environment ' + g, 'env_names': [],
                           'target': {'kind': 'artifact', 'value': 'planned-' + g, 'base_url_env': None}}
                        for g in ('G1', 'G2', 'G3')}
        self.config['operations'] = {'smoke_gates': {'checks': self.recipes}}
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        for name, body in render(self.config, self.research).items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def edit(self, gate, **changes):
        path = self.root / 'verification.md'
        rows = gate_rows(path.read_text(encoding='utf-8'))
        row = rows[gate]
        row.update(changes)
        lines = [('| ' + ' | '.join(row.values()) + ' |') if line.startswith('| ' + gate + ' |') else line
                 for line in path.read_text(encoding='utf-8').splitlines()]
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def rehash(self, name):
        path = self.root / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['contracts'][name] = digest((self.root / name).read_bytes())
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def test_different_recipes_preserve_exact_planned_strings_and_blank_observations(self):
        before = self.snapshot()
        result = drafts.draft_observations(self.root, ['G2', 'G1'])
        self.assertEqual([d['observation']['gate'] for d in result['drafts']], ['G2', 'G1'])
        for entry in result['drafts']:
            gate = entry['observation']['gate']
            self.assertEqual(entry['planned_context']['recipe'], self.recipes[gate])
            self.assertEqual(entry['planned_context']['environment'], self.recipes[gate]['environment'])
            self.assertEqual(entry['planned_context']['design'], requirements(self.config, self.research)[gate]['design'])
            self.assertEqual(entry['observation'], {'gate': gate, 'result': 'NOT RUN', 'revision': '',
                'environment': 'unconfirmed', 'evidence': '', 'target': '', 'checked_at': '', 'exit_status': ''})
        self.assertEqual(before, self.snapshot())

    def test_g3_prior_evidence_and_configured_target_never_become_actual_observation(self):
        self.edit('G3', result='FAILED', target='prior-actual-target', revision='prior-subject',
                  environment='prior-environment', evidence='private-prior-evidence',
                  checked_at='2026-10-01T12:00:00Z', exit_status='1')
        result = drafts.draft_observations(self.root, ['G3'])
        entry = result['drafts'][0]
        self.assertEqual(entry['planned_context']['target']['value'], 'planned-G3')
        self.assertEqual(entry['observation']['target'], '')
        self.assertNotIn('prior-', json.dumps(result))

    def test_exact_nested_schema_previews_but_envelope_and_result_only_pass_are_rejected(self):
        before = self.snapshot()
        result = drafts.draft_observations(self.root, ['G1', 'G3'])
        with self.assertRaisesRegex(ValueError, 'schema'):
            preview(self.root, 'gate', result)
        for entry in result['drafts']:
            observation = entry['observation']
            _, _, _, output, _ = preview(self.root, 'gate', observation)
            row = gate_rows(output.decode())[observation['gate']]
            self.assertEqual(row['environment'], 'unconfirmed')
            self.assertEqual(row['result'], 'NOT RUN')
            spec = requirements(self.config, self.research)[observation['gate']]
            self.assertTrue(problems(output.decode(), spec['stage'], 'synthetic-subject',
                                     {observation['gate']: spec}, 'synthetic-actual-target'))
            with self.assertRaisesRegex(ValueError, 'exact revision'):
                preview(self.root, 'gate', {**observation, 'result': 'PASSED'})
            with self.assertRaisesRegex(ValueError, 'does not satisfy'):
                preview(self.root, 'gate', {**observation, 'result': 'PASSED', 'revision': 'synthetic-subject'})
        self.assertEqual(before, self.snapshot())

    def test_optional_choice_is_context_and_cannot_turn_unfinished_observation_into_pass(self):
        self.edit('G1', required='no', result='FAILED', evidence='previous-failure')
        before = self.snapshot()
        entry = drafts.draft_observations(self.root, ['G1'])['drafts'][0]
        self.assertEqual(entry['planned_context']['required'], 'no')
        self.assertNotIn('required', entry['observation'])
        with self.assertRaisesRegex(ValueError, 'exact revision'):
            preview(self.root, 'gate', {**entry['observation'], 'result': 'PASSED'})
        with self.assertRaisesRegex(ValueError, 'does not satisfy'):
            preview(self.root, 'gate', {**entry['observation'], 'result': 'PASSED', 'revision': 'synthetic-subject'})
        self.assertEqual(before, self.snapshot())

    def test_acceptance_and_research_without_recipe_preserve_planned_and_retained_designs(self):
        self.research.update(status='complete', summary='Synthetic research fixture')
        self.research['coverage'] = {phase: {'status': 'applicable' if phase == 'release' else 'not_applicable',
                                           'reason': 'Synthetic phase assessment'}
                                    for phase in ('intake', 'plan', 'build', 'verify', 'release', 'learn')}
        self.research['sources'] = [{'id': 'S1', 'url': 'https://example.com/synthetic',
            'accessed_on': date.today().isoformat(), 'kind': 'synthetic fixture', 'version_scope': 'fixture',
            'observation': 'Synthetic observation', 'status': 'read'}]
        self.research['practices'] = [{'id': 'P1', 'decision': 'selected', 'source_ids': ['S1'],
            'phases': ['release'], 'relevance': 'Fixture', 'compatibility': 'Fixture', 'tradeoff': 'Fixture',
            'instruction': 'Inspect the synthetic artifact', 'check': 'Observe synthetic artifact'}]
        self.write()
        self.edit('A1', design='Actual inspected synthetic procedure')
        result = drafts.draft_observations(self.root, ['A1', 'R1'])
        for entry in result['drafts']:
            context = entry['planned_context']
            self.assertIsNone(context['recipe'])
            self.assertIsNone(context['environment'])
            self.assertIsNone(context['target'])
        self.assertNotEqual(result['drafts'][0]['planned_context']['design'],
                            result['drafts'][0]['planned_context']['retained_row_design'])
        self.assertEqual(result['drafts'][1]['planned_context']['stage'], 'post-merge')

    def test_no_release_applicability_is_context_only(self):
        self.config['operations'] = {'smoke_gates': {'target_kind': 'no_release',
            'post_merge_applicability': 'not_applicable', 'post_merge_rationale': 'Synthetic local-only task',
            'accepted_by': 'Synthetic owner'}}
        self.write()
        entry = drafts.draft_observations(self.root, ['G3'])['drafts'][0]
        self.assertEqual(entry['planned_context']['applicability'], 'not_applicable')
        self.assertEqual(entry['observation']['result'], 'NOT RUN')
        self.assertEqual(entry['observation']['evidence'], '')

    def test_explicit_selection_rejects_duplicates_malformed_unknown_and_unconfigured_ids(self):
        for selection in (None, 'G1', [], ['G1', 'G1'], ['g1'], [' G1'], ['G01'], ['G0'],
                          ['G1\nG2'], [True], ['G999'], ['X1'], ['A999'], ['G1'] * 33):
            with self.subTest(selection=selection), self.assertRaises(drafts.DraftInputError):
                drafts.draft_observations(self.root, selection)

    def test_missing_duplicate_malformed_wrong_stage_and_recipe_design_drift_refuse(self):
        original = (self.root / 'verification.md').read_text(encoding='utf-8')
        line = next(line for line in original.splitlines() if line.startswith('| G2 |'))
        for replacement in ('', line + '\n' + line, '| G2 | broken |',
                            line.replace('pre-merge', 'post-merge'), line.replace('argv=', 'changed=')):
            (self.root / 'verification.md').write_text(original.replace(line, replacement), encoding='utf-8')
            with self.subTest(replacement=replacement), self.assertRaises(drafts.DraftInputError):
                drafts.draft_observations(self.root, ['G2'])

    def test_contract_drift_and_policy_controls_mismatch_refuse_without_echo(self):
        path = self.root / 'policy.md'
        path.write_text(path.read_text(encoding='utf-8') + '\nprivate-marker', encoding='utf-8')
        with self.assertRaises(drafts.DraftInputError) as caught:
            drafts.draft_observations(self.root, ['G1'])
        self.assertNotIn('private-marker', str(caught.exception))
        self.write()
        path.write_text(path.read_text(encoding='utf-8').replace('"concurrency": 1', '"concurrency": 2'), encoding='utf-8')
        self.rehash('policy.md')
        with self.assertRaisesRegex(drafts.DraftInputError, 'controls disagree'):
            drafts.draft_observations(self.root, ['G1'])

    def test_unsafe_paths_and_mocked_reparse_are_rejected_without_real_links(self):
        for path in ('\\\\host\\share', '//host/share', '\\\\?\\C:\\fixture', str(self.root) + ':stream'):
            with self.subTest(path=path), patch('observation_drafts.snapshot_factory') as reader:
                with self.assertRaises(drafts.DraftInputError):
                    drafts.draft_observations(path, ['G1'])
                reader.assert_not_called()
        original = Path.lstat
        def metadata(path, *args, **kwargs):
            if path == self.root / 'config.json':
                return SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_file_attributes=0x400)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', metadata), self.assertRaises(drafts.DraftInputError):
            drafts.draft_observations(self.root, ['G1'])

    def test_input_and_output_limits_and_changed_snapshot_refuse(self):
        for name, value in (('MAX_FILE', 10), ('MAX_ENTRIES', 1), ('MAX_TOTAL', 10), ('MAX_DEPTH', 0)):
            with self.subTest(limit=name), patch('acceptance_links.' + name, value), self.assertRaises(drafts.DraftInputError):
                drafts.draft_observations(self.root, ['G1'])
        with patch('observation_drafts.MAX_OUTPUT', 100), self.assertRaisesRegex(drafts.DraftInputError, 'output'):
            drafts.draft_observations(self.root, ['G1'])
        real = drafts.snapshot_factory
        calls = []
        def changed(root):
            files, dirs = real(root)
            calls.append(True)
            if len(calls) == 2:
                files['verification.md'] += b'\n'
            return files, dirs
        with patch('observation_drafts.snapshot_factory', changed), self.assertRaisesRegex(drafts.DraftInputError, 'changed'):
            drafts.draft_observations(self.root, ['G1'])

    def test_read_only_main_prints_review_json_and_never_writes_or_launches(self):
        before = self.snapshot()
        original_open = Path.open
        def read_only(path, mode='r', *args, **kwargs):
            self.assertFalse(any(flag in mode for flag in 'wax+'), mode)
            return original_open(path, mode, *args, **kwargs)
        out = io.StringIO()
        with patch.object(Path, 'open', read_only), patch('subprocess.Popen', side_effect=AssertionError('process')), patch('os.system', side_effect=AssertionError('shell')), redirect_stdout(out):
            self.assertEqual(drafts.main(['--factory', str(self.root), '--gate', 'G1']), 0)
        result = json.loads(out.getvalue())
        self.assertIn('DRAFT ONLY', result['notice'])
        self.assertEqual(result['drafts'][0]['observation']['result'], 'NOT RUN')
        self.assertEqual(before, self.snapshot())
        err = io.StringIO()
        with redirect_stderr(err):
            self.assertEqual(drafts.main(['--factory', str(self.root), '--gate', 'G999']), 2)
        self.assertIn('unknown or unconfigured', err.getvalue())


if __name__ == '__main__':
    unittest.main()
