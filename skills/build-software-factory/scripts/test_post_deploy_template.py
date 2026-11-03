"""Synthetic plan/CLI tests; no provider, workflow or application execution."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/templates/ci'
ADAPTER = ASSETS / 'post-deploy.example.py'
spec = importlib.util.spec_from_file_location('post_deploy_template', ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class PostDeployTemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='factory-post-deploy-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.context = json.loads((ASSETS / 'post-deploy-context.example.json').read_text())
        self.context.update(source_checkout=str(self.root / 'source'), evidence_checkout=str(self.root / 'evidence'),
                            python=str(self.root / 'trusted/python'), helper=str(self.root / 'trusted/ci_evidence.py'))
        self.context['required_tasks'] = ['T1', 'T2']
        self.event = {'repository': {'full_name': 'example/project', 'private': True},
                      'deployment': {'id': 42, 'sha': '1' * 40, 'environment': 'Production',
                                     'ref': 'ignored; $(hostile-command)', 'payload': {'command': 'do not run'}},
                      'deployment_status': {'state': 'success', 'environment': 'Production',
                                            'environment_url': 'https://example.invalid',
                                            'target_url': 'https://logs.invalid/do-not-use', 'id': 100},
                      'sender': {'login': 'actor'}, 'installation': {'id': 77}, 'action': 'created'}

    def result(self):
        return adapter.plan(self.context, self.event)

    def test_native_event_plan_uses_explicit_source_and_later_storage(self):
        result = self.result()
        self.assertEqual(result['result'], 'plan_only')
        self.assertEqual(result['smoke_plan']['cwd'], self.context['source_checkout'])
        self.assertEqual(result['smoke_plan']['argv'], ['npm', 'run', 'test:smoke'])
        argv = result['assessment_after_recording_argv']
        for flag, value in (('--subject', '1' * 40), ('--storage', '2' * 40), ('--stage', 'post-merge'),
                            ('--target', 'https://example.invalid'), ('--repo', self.context['evidence_checkout'])):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertEqual(argv.count('--require-task'), 2)
        self.assertNotIn('PASSED', json.dumps(result))
        self.assertNotIn('do not run', json.dumps(result))

    def test_all_event_identity_mismatches_refused(self):
        cases = [('repository', 'full_name', 'other/project'), ('deployment', 'sha', '3' * 40),
                 ('deployment', 'sha', '1' * 7), ('deployment', 'id', True), ('deployment', 'id', 43),
                 ('deployment', 'environment', 'Preview'), ('deployment_status', 'state', 'pending'),
                 ('deployment_status', 'state', 'failure'), ('deployment_status', 'environment', 'Preview'),
                 ('deployment_status', 'environment_url', 'https://other.invalid')]
        for obj, key, value in cases:
            with self.subTest(key=key, value=value):
                event = copy.deepcopy(self.event); event[obj][key] = value
                with self.assertRaises(ValueError): adapter.plan(self.context, event)

    def test_no_log_url_fallback(self):
        del self.event['deployment_status']['environment_url']
        self.event['deployment_status']['target_url'] = self.context['target']
        with self.assertRaisesRegex(ValueError, 'environment_url'): self.result()

    def test_missing_or_wrong_event_objects(self):
        for event in (None, [], {}, {'deployment': []}, {'deployment_status': 'success'}):
            with self.subTest(event=event), self.assertRaises(ValueError): adapter.plan(self.context, event)

    def test_manual_without_github_deployment_still_has_independent_facts(self):
        self.context.update(mode='manual', manual_reason='No matching GitHub deployment was emitted before the deadline')
        self.context['deployment']['github_deployment_id'] = None
        self.assertEqual(adapter.plan(self.context)['trigger'], 'manual')
        for key, value in (('provider_deployment_id', ''), ('verification_reference', ''), ('state', 'pending'),
                           ('subject', '3' * 40), ('repository', 'other/project'), ('target', 'https://wrong.invalid')):
            with self.subTest(key=key):
                context = copy.deepcopy(self.context); context['deployment'][key] = value
                with self.assertRaises(ValueError): adapter.plan(context)

    def test_mode_cannot_ambiguously_mix_event_and_manual(self):
        self.context['manual_reason'] = 'reason'
        with self.assertRaises(ValueError): self.result()
        self.context['mode'] = 'manual'
        with self.assertRaises(ValueError): self.result()
        self.context['manual_reason'] = ''
        with self.assertRaises(ValueError): adapter.plan(self.context)

    def test_event_requires_positive_independent_github_id(self):
        for value in (None, 0, -1, True, '42', 2**63):
            with self.subTest(value=value):
                self.context['deployment']['github_deployment_id'] = value
                with self.assertRaises(ValueError): self.result()

    def test_subject_and_storage_full_exact_same_format(self):
        for value in ('main', 'A' * 40, '1' * 7, '1' * 64):
            with self.subTest(value=value):
                context = copy.deepcopy(self.context); context['subject'] = value
                with self.assertRaises(ValueError): adapter.plan(context, self.event)
        self.context['subject'] = self.context['deployment']['subject'] = self.event['deployment']['sha'] = 'a' * 64
        self.context['storage'] = 'b' * 64
        self.assertEqual(self.result()['subject'], 'a' * 64)

    def test_unsafe_targets_refused_even_when_all_claims_agree(self):
        for value in ('http://example.invalid', 'https://user:token@example.invalid', 'https://example.invalid/?secret=1',
                      'https://example.invalid/#fragment', 'https://example.invalid\\evil', 'https://exa mple.invalid',
                      'https://example.invalid:bad', 'file:///tmp/private'):
            with self.subTest(value=value):
                context = copy.deepcopy(self.context); context['target'] = context['deployment']['target'] = value
                context['recipe']['target']['value'] = value
                event = copy.deepcopy(self.event); event['deployment_status']['environment_url'] = value
                with self.assertRaises(ValueError): adapter.plan(context, event)

    def test_trusted_paths_outside_both_checkouts(self):
        for key in ('python', 'helper'):
            for root in ('source_checkout', 'evidence_checkout'):
                with self.subTest(key=key, root=root):
                    context = copy.deepcopy(self.context); context[key] = str(Path(context[root]) / 'tool')
                    with self.assertRaises(ValueError): adapter.plan(context, self.event)
        for key in ('source_checkout', 'evidence_checkout', 'python', 'helper'):
            with self.subTest(key=key):
                context = copy.deepcopy(self.context); context[key] = 'relative'
                with self.assertRaises(ValueError): adapter.plan(context, self.event)

    def test_canonical_relative_factory_and_evidence_paths(self):
        for key in ('factory', 'evidence_directory'):
            for value in ('/absolute', '../escape', 'a/../b', 'a//b', 'a\\b', 'a:b'):
                with self.subTest(key=key, value=value):
                    context = copy.deepcopy(self.context); context[key] = value
                    with self.assertRaises(ValueError): adapter.plan(context, self.event)

    def test_structured_recipe_only_and_no_target_replacement(self):
        mutations = [('command', 'npm run smoke'), ('command', []), ('command', ['x'] * 65),
                     ('command', ['x' * 2001]), ('environment', 'Preview'), ('env_names', ['BASE_URL', 'BASE_URL']),
                     ('env_names', ['SECRET=private']), ('target', {'kind': 'artifact', 'value': 'x', 'base_url_env': None})]
        for key, value in mutations:
            with self.subTest(key=key):
                context = copy.deepcopy(self.context); context['recipe'][key] = value
                with self.assertRaises(ValueError): adapter.plan(context, self.event)

    def test_shell_metacharacters_are_literal_data_no_execution_or_writes(self):
        self.context['recipe']['command'] = ['tool', '; echo PRIVATE_SENTINEL', '$(do-not-run)', '--flag=value']
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*'))
        with patch('subprocess.run', side_effect=AssertionError('command executed')), patch('os.system', side_effect=AssertionError('shell executed')):
            result = self.result()
        self.assertEqual(result['smoke_plan']['argv'], self.context['recipe']['command'])
        self.assertEqual(before, sorted(str(p.relative_to(self.root)) for p in self.root.rglob('*')))
        self.assertNotIn('G3', result)  # no fabricated observation or gate policy

    def test_context_unknown_keys_and_type_bounds(self):
        for key, value in (('extra', 'x'), ('schema', True), ('required_tasks', ['T1', 'T1']),
                           ('required_tasks', ['T1'] * 257), ('required_tasks', ['--command']), ('repository', 'x')):
            with self.subTest(key=key):
                context = copy.deepcopy(self.context); context[key] = value
                with self.assertRaises(ValueError): adapter.plan(context, self.event)

    def test_strict_bounded_input_reader(self):
        path = self.root / 'input.json'
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'\xff', b' ' * (adapter.LIMIT + 1)):
            with self.subTest(size=len(raw)):
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeError)): adapter.read_json(path)

    def test_plan_hash_binds_manual_claim_and_event_ignored_fields(self):
        first = self.result()
        self.event['sender']['login'] = 'different'
        second = self.result()
        self.assertNotEqual(first['event_sha256'], second['event_sha256'])
        self.assertEqual(first['smoke_plan'], second['smoke_plan'])
        self.context['deployment']['verification_reference'] = 'new independent check'
        self.assertNotEqual(second['context_sha256'], self.result()['context_sha256'])

    def test_actual_cli_plan_and_sanitized_failures(self):
        context, event = self.root / 'context.json', self.root / 'event.json'
        context.write_text(json.dumps(self.context)); event.write_text(json.dumps(self.event))
        command = [sys.executable, '-B', str(ADAPTER), '--context', str(context), '--event', str(event)]
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['result'], 'plan_only')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        for suffix in (['--unknown-private-argument'], ['PRIVATE_SENTINEL'], ['--context']):
            result = subprocess.run(command + suffix, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertNotIn('PRIVATE_SENTINEL', result.stderr)
            self.assertNotIn(str(self.root), result.stderr)
        event.write_text('{"deployment_status":{"state":"PRIVATE_SENTINEL"}}')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('PRIVATE_SENTINEL', result.stderr)

    def test_assets_remain_inactive_and_all_local_guide_links_exist(self):
        yaml = (ASSETS / 'post-deploy-smoke.yml.example').read_text()
        self.assertIn('if: ${{ false }}', yaml)
        self.assertIn('exit 2', yaml)
        self.assertIn('cancel-in-progress: false', yaml)
        self.assertNotIn('github.event.', yaml)
        self.assertNotIn('secrets.', yaml)
        self.assertNotIn('uses:', yaml)
        import re
        guide = ASSETS / 'post-deploy.md'
        for link in re.findall(r'\]\(([^)]+)\)', guide.read_text()):
            if not link.startswith('https:'):
                self.assertTrue((guide.parent / link).is_file(), link)

    def test_generated_bundle_is_manifest_bound_inactive_and_read_only_without_B(self):
        target = self.root / 'project'; target.mkdir()
        workflow = target / '.github/workflows/existing.yml'
        workflow.parent.mkdir(parents=True); workflow.write_text('existing project CI\n')
        config = self.root / 'config.json'
        config.write_bytes((ROOT / 'assets/example-config.json').read_bytes())
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/scaffold.py'),
                                 '--config', str(config), '--target', str(target), '--apply'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        factory = target / '.software-factory'
        manifest = json.loads((factory / 'manifest.json').read_text())
        for name in ('post-deploy.example.py', 'post-deploy-smoke.yml.example', 'post-deploy-context.example.json', 'post-deploy.md'):
            self.assertIn('ci/' + name, manifest['contracts'])
            self.assertEqual((factory / 'ci' / name).read_bytes(), (ASSETS / name).read_bytes())
        self.assertEqual([p.name for p in workflow.parent.iterdir()], ['existing.yml'])
        context, event = self.root / 'context.json', self.root / 'event.json'
        context.write_text(json.dumps(self.context)); event.write_text(json.dumps(self.event))
        before = {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()}
        # Deliberately omit -B: the adapter must not dirty generated contracts with pyc.
        result = subprocess.run([sys.executable, str(factory / 'ci/post-deploy.example.py'),
                                 '--context', str(context), '--event', str(event)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['result'], 'plan_only')
        self.assertEqual(before, {str(p.relative_to(target)): p.read_bytes() for p in target.rglob('*') if p.is_file()})
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/scaffold.py'), '--check', str(factory)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
