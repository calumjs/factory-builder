"""Generated contract-impact guidance and reviewed updates, using local fixtures only.

These tests exercise scaffold/update artifacts, not an agent's discovery quality or
application compatibility. A separate behavioral review must assess those decisions.
"""
import json
from pathlib import Path
import tempfile
import unittest
from phase_test_support import phase_text

from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
from update_operations import apply, prepare


PLAN = '.claude/skills/factory-plan/SKILL.md'
VERIFY = '.claude/skills/factory-verify/SKILL.md'


class SharedContractGuidanceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))

    def write_factory(self, root, files):
        for name, body in files.items():
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def test_generated_plan_and_verify_connect_existing_assertions_to_run_evidence(self):
        files = render(self.config, self.research)
        plan = ' '.join(phase_text(files,'plan').split())
        verify = ' '.join(phase_text(files,'verify').split())
        for clause in ('existing producers, consumers and tests',
                       'contract symbols and representative old values',
                       'affected existing test paths and assertions',
                       'retain a still-valid assertion and run it',
                       'does not require editing every consumer',
                       'A change with no shared-contract impact needs no extra inventory'):
            with self.subTest(clause=clause):
                self.assertIn(clause, plan)
        for clause in ('compare the final diff with the Plan inventory',
                       'preserve still-valid assertions',
                       'consumer that selects named fields stays unchanged',
                       'collection and result reconciliation below',
                       'Missing required coverage remains NOT RUN/BLOCKED'):
            with self.subTest(clause=clause):
                self.assertIn(clause, verify)

    def test_scaffold_preserves_project_scope_commands_and_unrun_evidence(self):
        self.config['stack'] = 'Python standard library CSV export'
        self.config['acceptance'] = ['Append a count column while preserving named-field readers']
        self.config['test_commands'] = ['python -m unittest tests.test_export tests.test_import']
        self.config['tasks'][0].update(
            goal='Review existing export assertions and named-field readers',
            allowed_paths=['src/export.py', 'tests/test_export.py'], status='pending')
        files = render(self.config, self.research)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_factory(root, files)
            check(root, quiet=True)
            self.assertEqual(json.loads((root/'config.json').read_text()), self.config)
            self.assertEqual(json.loads((root/'task-plan.json').read_text())['tasks'], self.config['tasks'])
            commands = json.loads((root/'tools.json').read_text())['test_commands']
            self.assertEqual(commands, [{'command': self.config['test_commands'][0],
                                        'execution_authorized': False, 'result': 'not-run'}])
            rows = gate_rows((root/'verification.md').read_text())
            self.assertEqual(set(rows), {'G1', 'G2', 'G3', 'A1'})
            self.assertTrue(all(row['result'] == 'NOT RUN' for row in rows.values()))
            # Editing the generated guidance without a reviewed update is detected.
            (root/PLAN).write_text('Unreviewed consumer exemption.', encoding='utf-8')
            with self.assertRaises(ValueError):
                check(root, quiet=True)

    def test_reviewed_verify_upgrade_preserves_project_plan_and_test_map(self):
        files = render(self.config, self.research)
        old_addon = (ROOT/'scripts/fixtures/pre100_verify_addendum.txt').read_text(encoding='utf-8')
        files[VERIFY] = ('---\nname: factory-verify\ndescription: Project verification\n---\n\n'
                         '# Verify\n\nRetain project-specific checks.\n\n' + old_addon + '\n')
        files[PLAN] += '\nProject scope: retain tests/test_import.py unchanged and run it.\n'
        files['test-map.json'] = json.dumps({'A1': ['tests/test_export.py', 'tests/test_import.py']})
        manifest = json.loads(files['manifest.json'])
        for name in (PLAN, VERIFY, 'test-map.json'):
            manifest['contracts'][name] = digest(files[name].encode('utf-8'))
        files['manifest.json'] = json.dumps(manifest)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'.software-factory'
            self.write_factory(root, files)
            check(root, quiet=True)
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            factory, old, new, plan = prepare(root, {}, delivery_update=True)
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes()
                                      for p in root.rglob('*') if p.is_file()})
            self.assertIn('Reconcile shared-contract impact', new[VERIFY].decode())
            self.assertNotIn(PLAN, new)
            self.assertNotIn('test-map.json', new)
            backup = apply(factory, old, new, plan, plan)
            self.assertEqual((backup/VERIFY).read_bytes(), before[VERIFY])
            self.assertEqual((root/PLAN).read_bytes(), before[PLAN])
            self.assertEqual((root/'test-map.json').read_bytes(), before['test-map.json'])
            self.assertIn('Retain project-specific checks.', (root/VERIFY).read_text())
            check(root, quiet=True)


if __name__ == '__main__':
    unittest.main()
