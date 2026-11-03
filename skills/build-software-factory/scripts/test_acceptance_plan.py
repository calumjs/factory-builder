"""Offline acceptance preview fixtures; proposed project checks are never executed."""
import base64
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import acceptance_plan as planner
from gates import gate_rows, requirements
from integrity import check, digest, LIVING
from recover_factory import prepare, rawhash, strict_json
from scaffold import ROOT, render


class AcceptancePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'factory [literal] with spaces'
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['operations'] = {'smoke_gates': {'required': False}}
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        files = {name: value.encode('utf-8') for name, value in render(self.config, self.research).items()}
        files['test-map.json'] = b'{ "A1" : {"check": "SYNTHETIC existing design; UNEXECUTED"} }\n'
        files['private-custom.md'] = b'Preserve customized bytes \xc3\xa9\r\n'
        files['acceptance.md'] += b'\n## Custom notes\nKeep this exact text.\n'
        files['project-brief.md'] += b'\n## Operator notes\nRetain these bytes.\n'
        rows = gate_rows(files['verification.md'].decode())
        cells = list(rows['A1'].values())
        cells[4] = 'no'
        cells[5:] = ['old-subject', 'FAILED', 'retained failure and waiver', 'old actual target', '2026-10-30T00:00:00Z', '1']
        old_line = next(line for line in files['verification.md'].decode().splitlines() if line.startswith('| A1 |'))
        self.old_line = '| ' + ' | '.join(cells) + ' |'
        files['verification.md'] = files['verification.md'].replace(old_line.encode(), self.old_line.encode())
        files['verification.md'] += b'\n## Prior observation\n> | A1 | retained historical text |\n'
        plan = strict_json(files['task-plan.json'])
        self.old_task = {'id': 'Tliving', 'goal': 'Existing later task', 'owner': 'operator', 'depends_on': ['T1'],
                         'acceptance_ids': ['A1'], 'allowed_paths': ['src/old.py'], 'status': 'done'}
        plan['tasks'].append(self.old_task)
        plan['events'] = [{'id': 'event-1', 'task_id': 'Tliving', 'timestamp': '2026-10-30T00:00:00Z',
                           'revision': 'old-subject', 'environment': 'synthetic', 'check': 'free form check',
                           'result': 'failed', 'evidence': 'keep failure', 'old_status': 'in_progress', 'status': 'blocked'}]
        plan['custom_notes'] = 'Keep this extra living metadata'
        files['task-plan.json'] = (json.dumps(plan, ensure_ascii=False, indent=3) + '\n').encode()
        manifest = strict_json(files['manifest.json'])
        for name in set(manifest['contracts']) | {'test-map.json', 'private-custom.md'}:
            manifest['contracts'][name] = digest(files[name])
        files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
        self.write(self.root, files)
        self.ident = f'A{len(self.config["acceptance"])+1}'
        self.request = {'schema_version': 1, 'issue': 'owner/project#123',
                        'criterion': 'SYNTHETIC appended criterion with Unicode \u00e9',
                        'task': {'id': 'Tnew', 'goal': 'SYNTHETIC new task', 'owner': 'operator',
                                 'depends_on': ['Tliving'], 'allowed_paths': ['src/new.py'], 'status': 'pending'},
                        'test_map': {'adapter': 'a-keyed-opaque-v1',
                                     'design': {'check': 'SYNTHETIC supplied design; UNEXECUTED'}, 'register_reason': ''}}

    def write(self, root, files):
        for name, raw in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

    def pin(self):
        return rawhash((self.root / 'manifest.json').read_bytes())

    def preview(self, request=None):
        return planner.preview(self.root, self.request if request is None else request, self.pin(), 'SYNTHETIC independently accepted fixture baseline')

    def edits(self, result):
        return {name: base64.b64decode(item['after_base64'], validate=True) for name, item in result['plan']['candidate_changes'].items()}

    def update_contract(self, name, raw):
        (self.root / name).write_bytes(raw)
        manifest_path = self.root / 'manifest.json'
        manifest = strict_json(manifest_path.read_bytes())
        manifest['contracts'][name] = digest(raw)
        manifest_path.write_bytes((json.dumps(manifest, indent=2) + '\n').encode())

    def test_preview_synchronizes_new_scope_and_preserves_custom_bytes_and_history(self):
        before = self.snapshot()
        result = self.preview()
        self.assertEqual(before, self.snapshot())
        edits = self.edits(result)
        self.assertEqual(set(edits), {'config.json', 'acceptance.md', 'project-brief.md', 'task-plan.json', 'verification.md', 'test-map.json'})
        self.assertNotIn('manifest.json', edits)
        new_config = strict_json(edits['config.json'])
        self.assertEqual(new_config['acceptance'], self.config['acceptance'] + [self.request['criterion']])
        self.assertEqual(new_config['tasks'], self.config['tasks'])
        old_plan = strict_json(before['task-plan.json'])
        new_plan = strict_json(edits['task-plan.json'])
        self.assertEqual(new_plan['tasks'][:-1], old_plan['tasks'])
        self.assertEqual(new_plan['tasks'][-1]['acceptance_ids'], [self.ident])
        self.assertEqual(new_plan['tasks'][-1]['depends_on'], ['Tliving'])
        self.assertEqual(new_plan['events'], old_plan['events'])
        self.assertEqual(new_plan['custom_notes'], old_plan['custom_notes'])
        old_rows = gate_rows(before['verification.md'].decode())
        new_rows = gate_rows(edits['verification.md'].decode())
        for name, row in old_rows.items():
            self.assertEqual(new_rows[name], row)
        new_row = new_rows[self.ident]
        self.assertEqual((new_row['stage'], new_row['required'], new_row['result']), ('pre-merge', 'yes', 'NOT RUN'))
        for name in ('revision', 'evidence', 'target', 'checked_at', 'exit_status'):
            self.assertEqual(new_row[name], '')
        new_line = next(line for line in edits['verification.md'].splitlines(keepends=True) if line.startswith(('| ' + self.ident + ' |').encode()))
        self.assertEqual(edits['verification.md'].replace(new_line, b'', 1), before['verification.md'])
        self.assertIn(b'## Custom notes\nKeep this exact text.\n', edits['acceptance.md'])
        self.assertIn(b'## Operator notes\nRetain these bytes.\n', edits['project-brief.md'])
        self.assertEqual(strict_json(edits['test-map.json'])['A1'], strict_json(before['test-map.json'])['A1'])
        predicted = strict_json(base64.b64decode(result['plan']['predicted_recovered_manifest']['after_base64']))
        original = strict_json(before['manifest.json'])
        changed = {name for name in original['contracts'] if original['contracts'][name] != predicted['contracts'][name]}
        self.assertEqual(changed, {'config.json', 'acceptance.md', 'project-brief.md', 'test-map.json'})
        self.assertEqual(predicted['living'], original['living'])
        self.assertEqual(result['plan']['source_inventory']['files'], {name: rawhash(raw) for name, raw in before.items()})
        self.assertEqual(result['digest'], rawhash(planner.canonical(result['plan'])))

    def test_test_only_candidate_keeps_baseline_manifest_and_matches_recovery_prediction(self):
        before = self.snapshot()
        result = self.preview()
        candidate = self.parent / 'synthetic candidate'
        self.write(candidate, {**before, **self.edits(result)})
        self.assertEqual((candidate / 'manifest.json').read_bytes(), before['manifest.json'])
        output = self.parent / 'unused recovered output'
        recovered = prepare(candidate, self.root, output, self.pin(), 'SYNTHETIC accepted baseline', result['plan']['recovery_decisions'])
        self.assertEqual(recovered['manifest'], base64.b64decode(result['plan']['predicted_recovered_manifest']['after_base64']))
        self.assertEqual(recovered['deltas'], {'accept_changed': {'config.json', 'acceptance.md', 'project-brief.md', 'test-map.json'}, 'register': set(), 'remove': set()})
        self.assertFalse(output.exists())
        self.assertFalse((self.parent / '.factory-recovery-backups').exists())
        self.assertEqual(before, self.snapshot())

    def test_missing_map_requires_explicit_registration_and_does_not_reclassify_living(self):
        (self.root / 'test-map.json').unlink()
        manifest_path = self.root / 'manifest.json'
        manifest = strict_json(manifest_path.read_bytes())
        del manifest['contracts']['test-map.json']
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'registration reason'):
            self.preview()
        self.request['test_map']['register_reason'] = 'Explicit immutable synthetic design contract'
        result = self.preview()
        self.assertEqual(result['plan']['recovery_decisions']['register'], [{'path': 'test-map.json', 'reason': self.request['test_map']['register_reason']}])
        self.assertEqual(set(strict_json(self.edits(result)['test-map.json'])), {self.ident})
        predicted = strict_json(base64.b64decode(result['plan']['predicted_recovered_manifest']['after_base64']))
        self.assertEqual(set(predicted['living']), LIVING)

    def test_blocked_task_and_six_phase_older_factory_remain_supported(self):
        manifest_path = self.root / 'manifest.json'
        manifest = strict_json(manifest_path.read_bytes())
        for name in list(manifest['contracts']):
            if '/factory-run/' in name:
                (self.root / name).unlink()
                del manifest['contracts'][name]
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        self.request['task']['status'] = 'blocked'
        result = self.preview()
        self.assertEqual(strict_json(self.edits(result)['task-plan.json'])['tasks'][-1]['status'], 'blocked')
        self.assertFalse(any('/factory-run/' in name for name in result['plan']['candidate_changes']))

    def test_saved_plan_rejects_tamper_even_when_attacker_rehashes(self):
        current = self.preview()
        self.assertTrue(planner.validate_plan(json.loads(json.dumps(current)), current))
        for field in ('candidate_changes', 'predicted_recovered_manifest'):
            saved = copy.deepcopy(current)
            if field == 'candidate_changes':
                saved['plan'][field]['verification.md']['after_base64'] = base64.b64encode(b'FAKE PASSED').decode()
            else:
                saved['plan'][field]['after_sha256'] = 'f' * 64
            saved['digest'] = rawhash(planner.canonical(saved['plan']))
            with self.assertRaisesRegex(ValueError, 'Saved plan differs'):
                planner.validate_plan(saved, current)

    def test_digest_binds_request_baseline_reference_and_living_bytes(self):
        old = self.preview()
        self.request['issue'] = 'owner/project#124'
        self.assertNotEqual(old['digest'], self.preview()['digest'])
        self.request['issue'] = 'owner/project#123'
        changed_ref = planner.preview(self.root, self.request, self.pin(), 'Different explicit baseline reference')
        self.assertNotEqual(old['digest'], changed_ref['digest'])
        with (self.root / 'learning-log.md').open('ab') as stream:
            stream.write(b'\nPreserve a concurrent learning entry\n')
        current = self.preview()
        self.assertNotEqual(old['digest'], current['digest'])
        with self.assertRaises(ValueError):
            planner.validate_plan(old, current)

    def test_unrelated_new_directory_invalidates_saved_plan(self):
        old = self.preview()
        (self.root / 'new-empty-directory').mkdir()
        with self.assertRaises(ValueError):
            planner.validate_plan(old, self.preview())

    def test_unregistered_extra_or_missing_files_refuse_before_preview(self):
        path = self.root / 'unregistered-note.md'
        path.write_text('Unregistered content', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.preview()
        path.unlink()
        (self.root / 'private-custom.md').unlink()
        with self.assertRaises(ValueError):
            self.preview()

    def test_existing_gate_collision_or_unresolved_task_link_requires_manual_review(self):
        path = self.root / 'verification.md'
        before = path.read_bytes()
        extra = self.old_line.replace('| A1 |', '| ' + self.ident + ' |', 1)
        path.write_bytes(before + ('\n' + extra + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'gate inventory'):
            self.preview()
        path.write_bytes(before)
        task_path = self.root / 'task-plan.json'
        task_plan = strict_json(task_path.read_bytes())
        task_plan['tasks'][-1]['acceptance_ids'] = ['A99999']
        task_path.write_text(json.dumps(task_plan), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unresolved acceptance'):
            self.preview()

    def test_documented_request_is_an_executable_preview_fixture(self):
        doc = (ROOT / 'references/acceptance-planning.md').read_text(encoding='utf-8')
        request = json.loads(re.search(r'```json\n(.*?)\n```', doc, re.S).group(1))
        before = self.snapshot()
        result = self.preview(request)
        self.assertEqual(result['plan']['request'], request)
        self.assertEqual(before, self.snapshot())

    def test_request_and_proposed_snapshot_limits_are_enforced(self):
        item = copy.deepcopy(self.request)
        item['test_map']['design'] = 'x' * planner.MAX_REQUEST
        with self.assertRaisesRegex(ValueError, '64 KiB'):
            self.preview(item)
        before = self.snapshot()
        with patch.object(planner, 'MAX_PLAN', 100):
            with self.assertRaisesRegex(ValueError, 'plan size limit'):
                self.preview()
        with patch.object(planner, 'MAX_FILE', 100):
            with self.assertRaisesRegex(ValueError, 'size limit'):
                self.preview()
        self.assertEqual(before, self.snapshot())

    def test_preview_detects_changes_after_snapshot(self):
        real_stable = planner.stable
        calls = 0
        def changed(root):
            nonlocal calls
            calls += 1
            if calls == 2:
                with (root / 'learning-log.md').open('ab') as stream:
                    stream.write(b'\nConcurrent writer\n')
            return real_stable(root)
        with patch.object(planner, 'stable', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'changed during preview'):
                self.preview()

    def test_invalid_request_variants_do_not_write(self):
        variants = []
        for field, value in [('status', 'done'), ('status', 'todo'), ('id', 'Tliving'), ('depends_on', ['missing']), ('allowed_paths', ['../escape'])]:
            item = copy.deepcopy(self.request); item['task'][field] = value; variants.append(item)
        for value in ('', 'new | ambiguous', 'new\ncriterion'):
            item = copy.deepcopy(self.request); item['criterion'] = value; variants.append(item)
        for field, value in [('adapter', 'guess'), ('design', {}), ('design', []), ('design', ''), ('design', False), ('register_reason', 'Unexpected re-registration')]:
            item = copy.deepcopy(self.request); item['test_map'][field] = value; variants.append(item)
        item = copy.deepcopy(self.request); item['task']['acceptance_ids'] = ['A1']; variants.append(item)
        item = copy.deepcopy(self.request); item['stage_override'] = 'post-merge'; variants.append(item)
        before = self.snapshot()
        for item in variants:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.preview(item)
        self.assertEqual(before, self.snapshot())

    def test_unrecognized_map_and_unknown_acceptance_ids_refuse(self):
        for value in ({'metadata': 'custom format'}, {self.ident: {'check': 'collision'}}, ['unknown format']):
            self.update_contract('test-map.json', json.dumps(value).encode())
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'object keyed only'):
                self.preview()
            self.assertEqual(before, self.snapshot())

    def test_custom_acceptance_section_or_collision_is_not_rewritten(self):
        path = self.root / 'project-brief.md'
        original = path.read_bytes()
        for raw in (original.replace(b'## Acceptance\n', b'## Acceptance\nCustom in-section note\n'), original + b'\n## Acceptance\n- duplicate\n'):
            self.update_contract('project-brief.md', raw)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                self.preview()
            self.assertEqual(before, self.snapshot())
        self.update_contract('project-brief.md', original)
        self.update_contract('acceptance.md', (self.root / 'acceptance.md').read_bytes() + ('\n- ' + self.ident + ': collision\n  Owner: unassigned; status: NOT VERIFIED; evidence: none.\n').encode())
        with self.assertRaisesRegex(ValueError, 'ordered criteria'):
            self.preview()

    def test_contract_corruption_wrong_pin_and_schema1_refuse(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'pin does not match'):
            planner.preview(self.root, self.request, '0' * 64, 'Independently accepted fixture')
        (self.root / 'private-custom.md').write_bytes(b'unreviewed drift')
        with self.assertRaises(ValueError):
            self.preview()
        self.write(self.root, before)
        manifest = strict_json(before['manifest.json']); manifest['schema'] = 1
        (self.root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'schema-2'):
            self.preview()

    def test_bom_crlf_and_unicode_preserve_every_original_json_byte(self):
        raw = b'\xef\xbb\xbf{\r\n "accept\\u0061nce" : ["bracket ] } and quote \\\"", "\xc3\xa9"], "other" : {"[":"}"}\r\n}\r\n'
        addition = ', ' + json.dumps('new \u03bb', ensure_ascii=True)
        result = planner.append_json(raw, ('acceptance',), 'new \u03bb')
        self.assertEqual(result.replace(addition.encode(), b'', 1), raw)
        self.assertEqual(strict_json(result)['acceptance'], strict_json(raw)['acceptance'] + ['new \u03bb'])
        for original in (b'{"tasks":[]}', b'{"tasks":[ ]}\r\n', b' {"tasks": [ {"id":"a]"} ]}\n'):
            result = planner.append_json(original, ('tasks',), {'id': 'new'})
            self.assertEqual(strict_json(result)['tasks'][-1], {'id': 'new'})
            fragment = json.dumps({'id': 'new'}).encode()
            if strict_json(original)['tasks']:
                fragment = b', ' + fragment
            self.assertEqual(result.replace(fragment, b'', 1), original)
        result = planner.append_json(b' { "A\\u0031": "braces {} []" }\n', (), ['new'], key='A2')
        self.assertEqual(result.replace(b', "A2": ["new"]', b'', 1), b' { "A\\u0031": "braces {} []" }\n')

    def test_crlf_factory_documents_remain_crlf_and_bom_is_preserved(self):
        for name in ('config.json', 'acceptance.md', 'project-brief.md', 'test-map.json'):
            self.update_contract(name, b'\xef\xbb\xbf' + (self.root / name).read_bytes().replace(b'\n', b'\r\n'))
        for name in ('verification.md', 'task-plan.json'):
            path = self.root / name
            path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes().replace(b'\n', b'\r\n'))
        edits = self.edits(self.preview())
        for name, raw in edits.items():
            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'), name)
            self.assertNotIn(b'\n', raw.replace(b'\r\n', b''), name)

    def test_cli_preview_and_validate_plan_are_read_only_and_reject_unsafe_inputs(self):
        request_path = self.parent / 'request [literal].json'
        request_path.write_text(json.dumps(self.request), encoding='utf-8')
        args = [sys.executable, '-B', str(ROOT / 'scripts/acceptance_plan.py'), '--factory', str(self.root),
                '--request', str(request_path), '--baseline-manifest-sha256', self.pin(),
                '--baseline-reference', 'SYNTHETIC independently accepted fixture baseline']
        before = self.snapshot()
        original_paths = set(self.parent.rglob('*'))
        result = subprocess.run(args, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(set(self.parent.rglob('*')), original_paths)
        saved_path = self.parent / 'saved preview.json'
        saved_path.write_text(result.stdout, encoding='utf-8')
        validated = subprocess.run(args + ['--validate-plan', str(saved_path)], capture_output=True, text=True)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(json.loads(validated.stdout), saved)
        self.assertEqual(before, self.snapshot())
        saved['plan']['candidate_changes']['verification.md']['after_base64'] = base64.b64encode(b'FAKE PASS').decode()
        saved['digest'] = rawhash(planner.canonical(saved['plan']))
        saved_path.write_text(json.dumps(saved), encoding='utf-8')
        rejected = subprocess.run(args + ['--validate-plan', str(saved_path)], capture_output=True, text=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, '')
        self.assertNotEqual(subprocess.run(args + ['--apply'], capture_output=True).returncode, 0)
        self.assertEqual(before, self.snapshot())
        for raw in ('{"schema_version":1,"schema_version":1}', '{"x":NaN}', '{"x":Infinity}', '{"secret":"PRIVATE-CONTENT",'):
            request_path.write_text(raw, encoding='utf-8')
            rejected = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(rejected.stdout, '')
            self.assertNotIn('PRIVATE-CONTENT', rejected.stderr)
            self.assertEqual(before, self.snapshot())
        request_path.write_bytes(b' ' * (planner.MAX_REQUEST + 1))
        self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
