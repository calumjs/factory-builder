"""Strict scaffold intake JSON; synthetic CLI fixtures, never project commands."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from integrity import check
from scaffold import ROOT, render


class ScaffoldStrictInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.target = self.base/'target'; self.target.mkdir()
        self.config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.config_path = self.base/'config.json'; self.research_path = self.base/'research.json'
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')
        self.research_path.write_text(json.dumps(self.research), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.base).as_posix(): None if p.is_dir() else p.read_bytes()
                for p in self.base.rglob('*')}

    def invoke(self, apply=False, explicit_research=True):
        argv = [sys.executable, '-B', str(ROOT/'scripts/scaffold.py'),
                '--config', str(self.config_path), '--target', str(self.target)]
        if explicit_research:argv += ['--research', str(self.research_path)]
        if apply:argv += ['--apply']
        return subprocess.run(argv, capture_output=True, text=True)

    def assert_refused(self, expected):
        before = self.snapshot()
        for apply in (False, True):
            with self.subTest(apply=apply):
                result = self.invoke(apply=apply)
                self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertNotIn('PRIVATE-SENTINEL', result.stdout+result.stderr)
                self.assertNotIn('PASS:', result.stdout)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.target/'.software-factory').exists())

    def test_duplicate_config_keys_at_root_are_not_silently_replaced(self):
        raw = json.dumps(self.config)
        self.config_path.write_text('{"project":"PRIVATE-SENTINEL",'+raw[1:], encoding='utf-8')
        self.assert_refused('Duplicate JSON object key')

    def test_duplicate_config_keys_nested_in_budget_are_refused(self):
        raw = json.dumps(self.config).replace('"max_cost": 0', '"max_cost": 999, "max_cost": 0', 1)
        self.config_path.write_text(raw, encoding='utf-8')
        self.assert_refused('Duplicate JSON object key')

    def test_duplicate_research_keys_at_root_are_not_silently_replaced(self):
        raw = json.dumps(self.research)
        self.research_path.write_text('{"summary":"PRIVATE-SENTINEL",'+raw[1:], encoding='utf-8')
        self.assert_refused('Duplicate JSON object key')

    def test_duplicate_research_keys_nested_in_coverage_are_refused(self):
        raw = json.dumps(self.research).replace('"status": "unassessed"',
            '"status": "applicable", "status": "unassessed"', 1)
        self.research_path.write_text(raw, encoding='utf-8')
        self.assert_refused('Duplicate JSON object key')

    def test_nonfinite_top_level_and_nested_constants_refuse_before_validation(self):
        original_config, original_research = json.dumps(self.config), json.dumps(self.research)
        for kind in ('config', 'research'):
            path = self.config_path if kind == 'config' else self.research_path
            for token in ('NaN', 'Infinity', '-Infinity'):
                for nested in (False, True):
                    with self.subTest(kind=kind, token=token, nested=nested):
                        self.config_path.write_text(original_config, encoding='utf-8')
                        self.research_path.write_text(original_research, encoding='utf-8')
                        raw = token
                        if nested:
                            # Both fields expect strings; parsing must reject JSON
                            # constants before ordinary schema/type validation.
                            value = copy.deepcopy(self.config if kind == 'config' else self.research)
                            if kind == 'config':value['tasks'][0]['goal'] = 'PRIVATE-SENTINEL'
                            else:value['coverage']['intake']['reason'] = 'PRIVATE-SENTINEL'
                            raw = json.dumps(value).replace('"PRIVATE-SENTINEL"', token)
                        path.write_text(raw, encoding='utf-8')
                        self.assert_refused('Non-finite JSON number')

    def test_valid_explicit_legacy_input_keeps_rendered_bytes_and_seed_semantics(self):
        # Valid older configurations may omit all additive settings and carry
        # imported canonical states; strict parsing does not reinterpret either.
        for key in ('operations', 'dashboard', 'assumptions'):self.config.pop(key, None)
        self.config['project'] = 'SYNTHETIC Café'
        self.config['tasks'][0]['status'] = 'done'
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False), encoding='utf-8')
        before = self.snapshot(); preview = self.invoke()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(self.snapshot(), before)
        result = self.invoke(apply=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.target/'.software-factory'; check(root, quiet=True)
        actual = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
        expected = {name:body.encode('utf-8') for name,body in render(self.config,self.research).items()}
        self.assertEqual(actual, expected)
        self.assertEqual(json.loads(actual['task-plan.json'])['events'], [])
        self.assertEqual(json.loads(actual['task-plan.json'])['tasks'][0]['status'], 'done')

    def test_omitted_research_retains_existing_blocked_default_and_output(self):
        result = self.invoke(apply=True, explicit_research=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        root = self.target/'.software-factory'; check(root, quiet=True)
        actual = {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
        expected = {name:body.encode('utf-8') for name,body in render(self.config,self.research).items()}
        self.assertEqual(actual, expected)
        self.assertEqual(json.loads(actual['research.json'])['status'], 'blocked')


if __name__ == '__main__':unittest.main()
