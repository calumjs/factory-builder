"""Known copied helpers migrate only after explicit review; synthetic factories only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
from update_operations import apply, prepare


class RuntimeIntegrationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.factory = self.base / '.software-factory'
        config = json.loads((ROOT / 'assets/example-config.json').read_text())
        research = json.loads((ROOT / 'assets/example-research.json').read_text())
        for name, text in render(config, research).items():
            path = self.factory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')
        self.prior = {}
        for name in ('integrity', 'dashboard', 'gates', 'operations'):
            data = (ROOT / f'scripts/fixtures/pre_runtime_integration_{name}.txt').read_bytes()
            relative = f'dashboard/{name}.py'
            (self.factory / relative).write_bytes(data)
            self.prior[relative] = data
        self.rehash_test_fixture()

    def rehash_test_fixture(self):
        """Explicit fixture construction, never a recovery mechanism for real factories."""
        path = self.factory / 'manifest.json'
        manifest = json.loads(path.read_text())
        for name in self.prior:
            manifest['contracts'][name] = digest((self.factory / name).read_bytes())
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix(): p.read_bytes()
                for p in self.factory.rglob('*') if p.is_file()}

    def test_exact_prior_runtimes_preview_migrate_and_keep_recorded_failure_and_waiver(self):
        from update_operations import COMPATIBLE_CONTEXT_PRE_RUNTIME_INTEGRATION, COMPATIBLE_GATE_PRE_RUNTIME_INTEGRATION
        expected = {**COMPATIBLE_CONTEXT_PRE_RUNTIME_INTEGRATION, **COMPATIBLE_GATE_PRE_RUNTIME_INTEGRATION}
        for name, data in self.prior.items():
            self.assertEqual(digest(data), expected[Path(name).name])
        verification = self.factory / 'verification.md'
        lines = []
        for line in verification.read_text(encoding='utf-8').splitlines():
            if line.startswith('| G2 |'):
                cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
                cells[4:11] = ['no', 'a'*40, 'FAILED', 'synthetic failure retained; operator chose optional', 'local-fixture', '2026-11-03T00:00:00Z', '1']
                line = '| ' + ' | '.join(cells) + ' |'
            lines.append(line)
        verification.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        check(self.factory, quiet=True)
        before = self.snapshot()
        _, _, unchanged, _ = prepare(self.factory, {})
        self.assertFalse(unchanged)
        root, old, new, plan = prepare(self.factory, {}, context_runtime=True, gate_runtime=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(set(new), set(self.prior) | {'manifest.json'})
        with self.assertRaises(ValueError):
            apply(root, old, new, plan, 'wrong-digest')
        self.assertEqual(before, self.snapshot())
        backup = apply(root, old, new, plan, plan)
        for name, data in self.prior.items():
            self.assertEqual((backup / name).read_bytes(), data)
            self.assertEqual((root / name).read_bytes(), (ROOT / 'scripts' / Path(name).name).read_bytes())
        for name in ('config.json', 'policy.md', 'verification.md', 'task-plan.json', 'learning-log.md'):
            self.assertEqual((root / name).read_bytes(), before[name])
        self.assertEqual(gate_rows(verification.read_text())['G2']['result'], 'FAILED')
        args = ['--factory', str(root), '--stage', 'pre-merge', '--revision', 'a'*40]
        results = [subprocess.run([sys.executable, str(path), *args], capture_output=True, text=True)
                   for path in (ROOT / 'scripts/gates.py', root / 'dashboard/gates.py')]
        self.assertEqual((results[0].returncode, results[0].stdout, results[0].stderr),
                         (results[1].returncode, results[1].stdout, results[1].stderr))
        self.assertEqual(results[1].returncode, 1)
        self.assertIn('WAIVED', results[1].stdout)
        output = self.base / 'overview.json'
        result = subprocess.run([sys.executable, str(root / 'dashboard/dashboard.py'), '--output', str(output), '--format', 'json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        row = next(row for row in json.loads(output.read_text())['gates'] if row['id'] == 'G2')
        self.assertEqual((row['state'], row['recorded_result']), ('WAIVED', 'FAILED'))
        self.assertFalse((root / 'dashboard/__pycache__').exists())
        check(root, quiet=True)

    def test_customized_prior_helpers_are_preserved_and_refused(self):
        for relative, original in self.prior.items():
            with self.subTest(helper=relative):
                path = self.factory / relative
                path.write_bytes(original + b'\n# Project-specific customization\n')
                self.rehash_test_fixture()
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'Customized/unsupported'):
                    prepare(self.factory, {}, context_runtime=True, gate_runtime=True)
                self.assertEqual(before, self.snapshot())
                path.write_bytes(original)
                self.rehash_test_fixture()


if __name__ == '__main__':
    unittest.main()
