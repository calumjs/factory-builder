"""Known v1.15 gate runtime remains compatible until an explicit reviewed update."""
import json
from pathlib import Path
import tempfile
import unittest

from integrity import check, digest
from scaffold import ROOT, render
from update_operations import COMPATIBLE_GATE_V115, apply, prepare


class V115RuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.factory = Path(self.temp.name) / 'factory'
        config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        for name, body in render(config, research).items():
            path = self.factory / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))
        self.old = (ROOT / 'scripts/fixtures/v1_15_gates.txt').read_bytes()
        self.assertEqual(digest(self.old), COMPATIBLE_GATE_V115['gates.py'])
        self.replace_gate(self.old)

    def replace_gate(self, data):
        (self.factory / 'dashboard/gates.py').write_bytes(data)
        path = self.factory / 'manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['contracts']['dashboard/gates.py'] = digest(data)
        path.write_text(json.dumps(manifest), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix(): p.read_bytes()
                for p in self.factory.rglob('*') if p.is_file()}

    def test_known_runtime_is_preserved_until_reviewed_opt_in(self):
        before = self.snapshot()
        self.assertFalse(prepare(self.factory, {})[2])
        root, old, new, plan = prepare(self.factory, {}, gate_runtime=True)
        self.assertEqual(set(new), {'dashboard/gates.py', 'manifest.json'})
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(ValueError): apply(root, old, new, plan, 'wrong')
        self.assertEqual(before, self.snapshot())
        backup = apply(root, old, new, plan, plan)
        self.assertEqual((backup / 'dashboard/gates.py').read_bytes(), self.old)
        for name, data in before.items():
            if name not in new: self.assertEqual((root / name).read_bytes(), data)
        self.assertEqual((root / 'dashboard/gates.py').read_bytes(), (ROOT / 'scripts/gates.py').read_bytes())
        check(root, quiet=True)

    def test_customized_old_runtime_is_refused_without_writes(self):
        self.replace_gate(self.old + b'\n# SYNTHETIC operator customization\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Customized/unsupported'):
            prepare(self.factory, {}, gate_runtime=True)
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__': unittest.main()
