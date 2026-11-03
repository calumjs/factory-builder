"""Synthetic local Git/CLI composition; no hosted jobs or application execution."""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import feature_contract as feature
from ci_evidence import assess_ci
from scaffold import ROOT, render
import test_ci_evidence as ci_fixture


class FeatureContractTests(unittest.TestCase):
    # Reuse ordinary disposable Git fixture construction, not its full test class.
    git = ci_fixture.CIEvidenceTests.git
    commit = ci_fixture.CIEvidenceTests.commit
    tearDown = ci_fixture.CIEvidenceTests.tearDown

    def setUp(self):
        ci_fixture.CIEvidenceTests.setUp(self)
        self.base = self.subject
        self.policy_path = Path(self.tmp.name)/'PRIVATE-policy.json'
        self.request_path = Path(self.tmp.name)/'PRIVATE-request.json'
        self.policy = {'version': 1, 'acceptance_delta': 'added', 'task_delta': 'added_or_changed'}
        self.mapping = {'reference': 'private-owner/private-project#123', 'tasks': ['T1'], 'acceptance': ['A1']}
        self.request = {'version': 1, 'base': self.base, 'subject': self.subject,
                        'closing_issues': [self.mapping['reference']],
                        'contract': {'version': 1, 'subject': self.subject, 'classification': 'feature',
                                     'rationale': 'PRIVATE reviewed fixture behavior', 'issues': [self.mapping]}}

    def inputs(self):
        self.request['subject'] = self.subject
        self.request['contract']['subject'] = self.subject
        self.policy_path.write_text(json.dumps(self.policy), encoding='utf-8')
        self.request_path.write_text(json.dumps(self.request), encoding='utf-8')
        return {'feature_policy': self.policy_path,
                'feature_policy_sha256': hashlib.sha256(self.policy_path.read_bytes()).hexdigest(),
                'feature_request': self.request_path, 'feature_base': self.base}

    def assess(self, storage, inputs=None):
        return assess_ci(self.repo, '.software-factory', self.subject, storage, 'pre-merge',
                         **(self.inputs() if inputs is None else inputs))

    def cli(self, storage, inputs=None, env=None):
        options = self.inputs() if inputs is None else inputs
        argv = [sys.executable, '-B', str(ROOT/'scripts/ci_evidence.py'), '--repo', str(self.repo),
                '--subject', self.subject, '--storage', storage, '--stage', 'pre-merge']
        for key, value in options.items():
            argv += ['--'+key.replace('_', '-'), str(value)]
        return subprocess.run(argv, capture_output=True, text=True, env=env)

    def record(self, failed=None, waived=None):
        lines = []
        for line in (self.factory/'verification.md').read_text().splitlines():
            if line.startswith('| '):
                cells = [v.strip() for v in line.strip('|').split('|')]
                if len(cells) == 11 and cells[1] == 'pre-merge':
                    cells[2:4] = ['SYNTHETIC supplied check; not executed', 'isolated fixture']
                    cells[5:] = [self.subject, 'FAILED' if cells[0] == failed else 'PASSED',
                                  'SYNTHETIC observation', 'synthetic-package', '2026-10-30T07:00:00Z', '0']
                    if cells[0] == waived:
                        cells[4] = 'no'
                    line = '| '+' | '.join(cells)+' |'
            lines.append(line)
        (self.factory/'verification.md').write_bytes('\n'.join(lines).encode())
        return self.commit()

    def regenerate(self, change):
        config = json.loads((self.factory/'config.json').read_text())
        change(config)
        research = json.loads((self.factory/'research.json').read_text())
        for name, text in render(config, research).items():
            (self.factory/name).write_bytes(text.encode())
        self.subject = self.commit()

    def grow(self):
        def addition(config):
            config['acceptance'].append('SYNTHETIC archive survives reload')
            config['tasks'].append({**copy.deepcopy(config['tasks'][0]), 'id': 'T2',
                                    'goal': 'SYNTHETIC archive behavior', 'acceptance_ids': ['A2']})
        self.regenerate(addition)
        self.mapping.update(tasks=['T2'], acceptance=['A2'])

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def test_actual_cli_blocks_green_records_without_issue_delta_and_preserves_default_dto(self):
        storage = self.record()
        before = self.snapshot()
        legacy = assess_ci(self.repo, '.software-factory', self.subject, storage, 'pre-merge')
        self.assertEqual(legacy['assessment'], 'recorded_requirements_satisfied')
        self.assertNotIn('feature_check', legacy)
        result = self.cli(storage)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertIn('ACCEPTANCE_ADDITION_REQUIRED', str(report['problems']))
        self.assertIn('TASK_DEFINITION_DELTA_REQUIRED', str(report['problems']))
        self.assertNotIn('PRIVATE', result.stdout+result.stderr)
        self.assertNotIn('private-owner', result.stdout+result.stderr)
        self.assertNotIn(str(self.repo), result.stdout+result.stderr)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_actual_cli_accepts_synchronized_added_scope_with_separate_subject_storage(self):
        self.grow()
        storage = self.record()
        before = self.snapshot()
        result = self.cli(storage)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['feature_check']['assessment'], 'structural_policy_satisfied')
        self.assertEqual(report['feature_check']['subject'], self.subject)
        self.assertEqual(report['evidence_storage_revision'], storage)
        self.assertNotEqual(self.subject, storage)
        self.assertEqual(report['feature_check']['issues'][0]['acceptance_added'], 1)
        self.assertEqual(report['feature_check']['issues'][0]['tasks_added'], 1)
        self.assertEqual(before, self.snapshot())

    def test_reuse_policy_preserves_existing_mapping_and_required_gate_failure_or_waiver(self):
        self.policy.update(acceptance_delta='reuse', task_delta='reuse')
        storage = self.record(failed='G2')
        report = self.assess(storage)
        self.assertEqual(report['feature_check']['assessment'], 'structural_policy_satisfied')
        self.assertEqual(report['assessment'], 'blocked')
        storage = self.record(failed='G2', waived='G2')
        report = self.assess(storage)
        self.assertEqual(report['assessment'], 'eligible_with_waivers')
        self.assertIn('G2 WAIVED (recorded FAILED)', report['waivers'])

    def test_each_closing_issue_mapping_must_contain_a_qualifying_delta(self):
        self.grow()
        self.request['closing_issues'].append('private-owner/private-project#124')
        self.request['contract']['issues'].append({'reference': self.request['closing_issues'][1],
                                                  'tasks': ['T1'], 'acceptance': ['A1']})
        report = self.assess(self.record())['feature_check']
        self.assertEqual(report['issues'][0]['problems'], [])
        self.assertIn('ACCEPTANCE_ADDITION_REQUIRED', report['issues'][1]['problems'])
        self.assertEqual(report['issues'][1]['request_issue_index'], 2)

    def test_status_and_property_order_do_not_count_but_task_definition_changes_do(self):
        self.policy['acceptance_delta'] = 'reuse'
        plan = json.loads((self.factory/'task-plan.json').read_text())
        plan['tasks'][0]['status'] = 'done'
        plan['tasks'][0] = dict(reversed(list(plan['tasks'][0].items())))
        (self.factory/'task-plan.json').write_text(json.dumps(plan))
        self.subject = self.commit()
        report = self.assess(self.record())['feature_check']
        self.assertEqual(report['issues'][0]['tasks_changed'], 0)
        self.assertEqual(report['assessment'], 'blocked')
        plan['tasks'][0]['goal'] += ' with durable archive readback'
        (self.factory/'task-plan.json').write_text(json.dumps(plan))
        self.subject = self.commit()
        report = self.assess(self.record())['feature_check']
        self.assertEqual(report['issues'][0]['tasks_changed'], 1)
        self.assertEqual(report['assessment'], 'structural_policy_satisfied')
        self.policy['task_delta'] = 'added'
        self.assertEqual(self.assess(self.git('rev-parse', 'HEAD'))['feature_check']['assessment'], 'blocked')

    def test_acceptance_edits_reordering_and_duplicate_value_reordering_are_unsupported(self):
        for criteria in (['Changed original'], ['new', 'Replace with a measurable criterion'],
                         ['Changed original', 'Replace with a measurable criterion']):
            with self.subTest(criteria=criteria):
                self.git('reset', '--hard', self.base)
                self.regenerate(lambda c: c.update(acceptance=criteria))
                result = self.cli(self.record())
                self.assertEqual(result.returncode, 2)
                self.assertIn('ACCEPTANCE_NOT_APPEND_ONLY', result.stderr)

    def test_maintenance_and_no_closing_claims_are_explicit_not_coverage(self):
        storage = self.record()
        self.request['contract'].update(classification='maintenance', issues=[])
        self.request['closing_issues'] = []
        report = self.assess(storage)['feature_check']
        self.assertEqual(report['assessment'], 'outside_trigger_claim')
        self.assertEqual(report['outside_trigger_reason'], 'maintenance_claim')
        self.request['contract'].update(classification='feature', issues=[self.mapping])
        report = self.assess(storage)['feature_check']
        self.assertEqual(report['outside_trigger_reason'], 'no_closing_issues_claim')
        options = self.inputs()
        options['feature_base'] = '1'*40
        self.request['base'] = '1'*40
        self.request_path.write_text(json.dumps(self.request))
        result = self.cli(storage, options)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('outside_trigger_claim', result.stdout)

    def test_policy_pin_unknown_schema_and_request_identity_fail_privately(self):
        storage = self.record()
        options = self.inputs()
        self.policy_path.write_text('PRIVATE not JSON')
        result = self.cli(storage, options)
        self.assertEqual(result.returncode, 2)
        self.assertIn('POLICY_PIN_MISMATCH', result.stderr)
        self.assertNotIn('PRIVATE', result.stderr)
        self.policy['acceptance_delta'] = 'added_or_changed'
        self.assertIn('UNSUPPORTED_POLICY', self.cli(storage).stderr)
        self.policy['acceptance_delta'] = 'added'
        options = self.inputs()
        self.request['subject'] = 'b'*40
        self.request_path.write_text(json.dumps(self.request))
        self.assertIn('REQUEST_IDENTITY_OR_SCHEMA', self.cli(storage, options).stderr)

    def test_duplicate_json_unmapped_claim_duplicate_claim_and_invalid_task_links_refuse(self):
        storage = self.record()
        options = self.inputs()
        self.request_path.write_text(json.dumps(self.request)[:-1]+',"version":1}')
        self.assertEqual(self.cli(storage, options).returncode, 2)
        self.request['closing_issues'].append(self.request['closing_issues'][0])
        self.assertIn('CLOSING_ISSUES_INVALID', self.cli(storage).stderr)
        self.request['closing_issues'] = ['private-owner/private-project#999']
        self.assertIn('CLOSING_ISSUE_UNMAPPED', self.cli(storage).stderr)
        self.request['closing_issues'] = [self.mapping['reference']]
        self.mapping['acceptance'] = ['A999']
        self.assertEqual(self.cli(storage).returncode, 2)

    def test_partial_flags_post_merge_dirty_storage_and_scope_changes_refuse(self):
        storage = self.record()
        options = self.inputs()
        partial = dict(options);partial.pop('feature_base')
        self.assertEqual(self.cli(storage, partial).returncode, 2)
        with self.assertRaisesRegex(ValueError, 'pre-merge'):
            assess_ci(self.repo, '.software-factory', self.subject, storage, 'post-merge', **options)
        (self.repo/'untracked.txt').write_text('dirty fixture')
        self.assertEqual(self.cli(storage, options).returncode, 2)
        (self.repo/'untracked.txt').unlink()
        plan = json.loads((self.factory/'task-plan.json').read_text())
        plan['tasks'][0]['goal'] += ' scope change hidden in evidence'
        (self.factory/'task-plan.json').write_text(json.dumps(plan))
        changed_storage = self.commit()
        result = self.cli(changed_storage, options)
        self.assertEqual(result.returncode, 2)
        self.assertIn('not evidence-only', result.stderr)

    def test_input_mutation_after_assessment_and_inside_checkout_refuse(self):
        storage = self.record()
        options = self.inputs()
        original = feature.FeatureCheck.assess
        def changed(check, root):
            result = original(check, root)
            self.request_path.write_bytes(self.request_path.read_bytes()+b' ')
            return result
        with patch.object(feature.FeatureCheck, 'assess', changed):
            with self.assertRaisesRegex(ValueError, 'INPUT_CHANGED_REVIEW_AGAIN'):
                self.assess(storage, options)
        options = self.inputs()
        options['feature_request'] = self.factory/'config.json'
        with self.assertRaisesRegex(ValueError, 'EXTERNAL_INPUT_REQUIRED'):
            self.assess(storage, options)

    def test_inactive_job_passes_literal_flags_and_propagates_actual_policy_failure(self):
        storage = self.record()
        options = self.inputs()
        spec = importlib.util.spec_from_file_location('feature_job_fixture', ROOT/'assets/templates/ci/job.example.py')
        job = importlib.util.module_from_spec(spec);spec.loader.exec_module(job)
        env = {'FACTORY_PYTHON': sys.executable, 'FACTORY_TRUSTED_HELPER': str(ROOT/'scripts/ci_evidence.py'),
               'FACTORY_GIT': str(Path(shutil.which('git')).resolve(strict=True)),
               'FACTORY_REPO': str(self.repo), 'FACTORY_TESTED_SUBJECT_SHA': self.subject,
               'FACTORY_EVIDENCE_STORAGE_SHA': storage, 'FACTORY_FEATURE_POLICY': str(self.policy_path),
               'FACTORY_FEATURE_POLICY_SHA256': options['feature_policy_sha256'],
               'FACTORY_FEATURE_REQUEST': str(self.request_path), 'FACTORY_FEATURE_BASE_SHA': self.base}
        argv = job.command(env)
        self.assertEqual(argv[argv.index('--git')+1], env['FACTORY_GIT'])
        result = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, PATH=''))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('ACCEPTANCE_ADDITION_REQUIRED', result.stdout)
        partial = dict(env);partial.pop('FACTORY_FEATURE_REQUEST')
        with self.assertRaises(ValueError):
            job.command(partial)
        with self.assertRaises(ValueError):
            job.command(dict(env, FACTORY_GIT='git'))

    def test_input_size_and_mock_link_count_refuse_without_link_creation(self):
        self.inputs()
        with self.assertRaisesRegex(ValueError, 'INPUT_SHAPE_OR_LIMIT'):
            feature.read_input(self.request_path, self.repo, 1)
        original = os.fstat
        def linked(fd):
            from types import SimpleNamespace
            info = original(fd)
            values = {key: getattr(info, key) for key in dir(info) if key.startswith('st_')}
            values['st_nlink'] = 2
            return SimpleNamespace(**values)
        with patch('feature_contract.os.fstat', side_effect=linked), self.assertRaisesRegex(ValueError, 'INPUT_CHANGED'):
            feature.read_input(self.request_path, self.repo, feature.MAX_REQUEST)

    def test_reader_ignores_worktree_bytes_but_ci_still_requires_clean_storage(self):
        reader = feature.CommittedFiles(self.repo, 40)
        expected = (self.factory/'config.json').read_bytes()
        (self.factory/'config.json').write_bytes(b'PRIVATE dirty replacement')
        self.assertEqual(reader.read(self.base, '.software-factory/config.json'), expected)
        with self.assertRaises(ValueError):
            self.assess(self.base)

    def test_duplicate_task_in_ancestor_base_does_not_become_maintenance_exemption(self):
        original = (self.factory/'task-plan.json').read_bytes()
        plan = json.loads((self.factory/'task-plan.json').read_text())
        plan['tasks'].append(copy.deepcopy(plan['tasks'][0]))
        (self.factory/'task-plan.json').write_text(json.dumps(plan))
        invalid_base = self.commit()
        (self.factory/'task-plan.json').write_bytes(original)
        self.subject = self.commit()
        self.request['contract'].update(classification='maintenance', issues=[])
        self.request['closing_issues'] = []
        self.request['base'] = invalid_base
        options = self.inputs();options['feature_base'] = invalid_base
        result = self.cli(self.subject, options)
        self.assertEqual(result.returncode, 2)
        self.assertIn('INVALID_COMMITTED_TASK_PLAN', result.stderr)

    def test_baseline_registration_and_nonancestor_are_checked_before_exemption(self):
        self.request['contract'].update(classification='maintenance', issues=[])
        self.request['closing_issues'] = []
        original = self.base
        manifest_path = self.factory/'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['contracts']['config.json'] = '0'*64
        manifest_path.write_text(json.dumps(manifest))
        bad = self.commit()
        self.git('reset', '--hard', original)
        options = self.inputs();options['feature_base'] = bad
        self.request['base'] = bad
        self.request_path.write_text(json.dumps(self.request))
        result = self.cli(original, options)
        self.assertEqual(result.returncode, 2)
        self.assertIn('COMMITTED_CONFIG_REGISTRATION_INVALID', result.stderr)
        (self.repo/'branch-only.txt').write_text('SYNTHETIC divergent commit')
        unrelated = self.commit()
        self.git('reset', '--hard', original)
        self.request['base'] = unrelated
        options = self.inputs();options['feature_base'] = unrelated
        result = self.cli(original, options)
        self.assertEqual(result.returncode, 2)
        self.assertIn('INVALID_UNAVAILABLE_OR_UNSTABLE_INPUT', result.stderr)
        # The valid but nonancestor input reaches the actual graph check.
        import release_identity
        with patch('release_identity.bounded_run', wraps=release_identity.bounded_run) as calls:
            with self.assertRaisesRegex(ValueError, 'merge-base'):
                feature.FeatureCheck(self.repo, '.software-factory', self.subject,
                                     options['feature_policy'], options['feature_policy_sha256'],
                                     options['feature_request'], unrelated).assess(self.factory)
        self.assertTrue(any('merge-base' in call.args[0] for call in calls.call_args_list))

    def test_adopted_required_review_is_not_bypassed_by_feature_policy(self):
        self.regenerate(lambda c: c['operations'].update(review={'record_schema': 1, 'required_approvals': 1}))
        self.policy.update(acceptance_delta='reuse', task_delta='reuse')
        report = self.assess(self.record())
        self.assertEqual(report['feature_check']['assessment'], 'structural_policy_satisfied')
        self.assertEqual(report['assessment'], 'blocked')
        self.assertTrue(any('Q1' in problem for problem in report['problems']))

    def test_selected_absolute_git_is_used_for_feature_objects_and_ancestry_without_path_fallback(self):
        selected = str(Path(shutil.which('git')).resolve(strict=True))
        self.policy.update(acceptance_delta='reuse', task_delta='reuse')
        storage = self.record()
        options = self.inputs();options['git'] = selected
        isolated = dict(os.environ, PATH='')
        result = self.cli(storage, options, env=isolated)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['feature_check']['assessment'], 'structural_policy_satisfied')
        # Baseline and feature both need the selected path; no implicit executable substitute.
        options['git'] = str(Path(self.tmp.name)/'missing-approved-git')
        self.assertEqual(self.cli(storage, options, env=isolated).returncode, 2)
        options.pop('git')
        import release_identity
        with patch('release_identity.bounded_run', wraps=release_identity.bounded_run) as calls:
            assess_ci(self.repo, '.software-factory', self.subject, storage, 'pre-merge',
                      git_executable=selected, **options)
        self.assertTrue(any('cat-file' in call.args[0] for call in calls.call_args_list))
        self.assertTrue(any('merge-base' in call.args[0] for call in calls.call_args_list))
        for call in calls.call_args_list:
            self.assertEqual(call.args[0][0], selected)
            self.assertEqual(call.args[1]['GIT_ALLOW_PROTOCOL'], '')
            self.assertEqual(call.args[1]['GIT_CONFIG_GLOBAL'], os.devnull)

    def test_shared_addition_can_cover_multiple_supplied_issues_without_distinctness_rule(self):
        self.grow()
        shared = {**copy.deepcopy(self.mapping), 'reference': 'private-owner/private-project#124'}
        self.request['closing_issues'].append(shared['reference'])
        self.request['contract']['issues'].append(shared)
        report = self.assess(self.record())['feature_check']
        self.assertEqual(report['assessment'], 'structural_policy_satisfied')
        self.assertEqual(len(report['issues']), 2)
        self.assertEqual([row['acceptance_added'] for row in report['issues']], [1, 1])
        self.assertEqual([row['tasks_added'] for row in report['issues']], [1, 1])

    def test_stale_ancestor_recounts_prior_additions_but_selected_recent_base_blocks(self):
        self.grow()
        recent = self.subject
        (self.repo/'app.txt').write_text('SYNTHETIC later change without new scope')
        self.subject = self.commit()
        storage = self.record()
        prior = self.assess(storage)['feature_check']
        self.assertEqual(prior['assessment'], 'structural_policy_satisfied')
        self.assertEqual(prior['base'], self.base)
        self.base = recent
        self.request['base'] = recent
        chosen = self.assess(storage)['feature_check']
        self.assertEqual(chosen['assessment'], 'blocked')
        self.assertIn('ACCEPTANCE_ADDITION_REQUIRED', chosen['issues'][0]['problems'])
        # Both are valid ancestors: this is a trusted base-selection obligation,
        # not a claim that the helper discovers actual PR metadata.

    def test_maintenance_with_nonempty_closing_claims_is_labeled_exemption(self):
        self.request['contract']['classification'] = 'maintenance'
        report = self.assess(self.record())['feature_check']
        self.assertEqual(report['assessment'], 'outside_trigger_claim')
        self.assertEqual(report['outside_trigger_reason'], 'maintenance_claim')
        self.assertEqual(report['closing_issue_count'], 1)

    def test_bom_inputs_are_pinned_before_decode_and_stale_raw_pin_refuses(self):
        self.policy.update(acceptance_delta='reuse', task_delta='reuse')
        storage = self.record()
        options = self.inputs()
        self.policy_path.write_bytes(b'\xef\xbb\xbf'+self.policy_path.read_bytes())
        self.request_path.write_bytes(b'\xef\xbb\xbf'+self.request_path.read_bytes())
        self.assertIn('POLICY_PIN_MISMATCH', self.cli(storage, options).stderr)
        options['feature_policy_sha256'] = hashlib.sha256(self.policy_path.read_bytes()).hexdigest()
        result = self.cli(storage, options)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['feature_check']['request_sha256'],
                         hashlib.sha256(self.request_path.read_bytes()).hexdigest())

    def test_samefile_alias_is_rejected_after_redirect_check_without_creating_aliases(self):
        self.inputs()
        original = Path.samefile
        checks = []
        real_redirect_check = feature.reject_redirected_ancestors
        def checked(path):
            checks.append(Path(path))
            return real_redirect_check(path)
        def aliased(parent, other):
            if parent == self.request_path.parent and other == self.repo:
                self.assertTrue(checks)
                return True  # Synthetic alternate spelling of checkout ancestor.
            return original(parent, other)
        with patch('feature_contract.reject_redirected_ancestors', side_effect=checked), patch.object(Path, 'samefile', aliased):
            with self.assertRaisesRegex(ValueError, 'EXTERNAL_INPUT_REQUIRED'):
                feature.read_input(self.request_path, self.repo, feature.MAX_REQUEST)


class FeatureContractBoundaryTests(unittest.TestCase):
    def test_strict_policy_types_and_properties(self):
        valid = {'version': 1, 'acceptance_delta': 'reuse', 'task_delta': 'added'}
        for value in (dict(valid, version=True), dict(valid, version=2), dict(valid, extra=1),
                      dict(valid, task_delta=None), dict(valid, acceptance_delta='changed')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                feature.validate_policy(value)

    def test_canonical_comparison_preserves_lists_and_types_but_not_property_order(self):
        self.assertEqual(feature.canonical({'a': 1, 'b': 2}), feature.canonical({'b': 2, 'a': 1}))
        self.assertNotEqual(feature.canonical({'depends_on': ['T1', 'T2']}), feature.canonical({'depends_on': ['T2', 'T1']}))
        self.assertNotEqual(feature.canonical(True), feature.canonical(1))

    def test_guarded_errors_never_echo_private_values(self):
        def error():
            raise ValueError('PRIVATE/path?token=SECRET')
        with self.assertRaises(ValueError) as caught:
            feature.guarded(error)
        self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertNotIn('SECRET', str(caught.exception))

    def test_tree_parser_rejects_redirects_aliases_disorder_malformed_and_entry_limits(self):
        from types import SimpleNamespace
        entry = lambda mode, name: mode+b' '+name+b'\0'+bytes.fromhex('a'*40)
        fixtures = (entry(b'120000', b'symlink'), entry(b'160000', b'submodule'),
                    entry(b'100644', b'A')+entry(b'100644', b'a'),
                    entry(b'100644', b'z')+entry(b'100644', b'a'),
                    entry(b'100644', b'../escape'), b'100644 missing-null')
        for raw in fixtures:
            reader = object.__new__(feature.CommittedFiles)
            reader.count = 0
            reader.trees = {}
            reader.objects = SimpleNamespace(read=lambda *args: raw, width=40, deadline=lambda: None)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                reader.members('a'*40)
        reader.objects.read = lambda *args: entry(b'100644', b'a')
        reader.count = feature.MAX_ENTRIES
        with self.assertRaisesRegex(ValueError, 'TREE_ENTRY_LIMIT'):
            reader.members('a'*40)

    def test_verified_tree_cache_counts_unique_entries_and_still_checks_reader(self):
        from types import SimpleNamespace
        raw = b'100644 entry\0'+bytes.fromhex('a'*40)
        reads = []
        def verified(oid, kind):
            reads.append((oid, kind))
            return raw
        reader = object.__new__(feature.CommittedFiles)
        reader.count = 0;reader.trees = {}
        reader.objects = SimpleNamespace(read=verified, width=40, deadline=lambda: None)
        first = reader.members('b'*40)
        self.assertEqual(reader.members('b'*40), first)
        self.assertEqual(reader.count, 1)
        self.assertEqual(reads, [('b'*40, 'tree'), ('b'*40, 'tree')])
        reader.objects.read = lambda *args: (_ for _ in ()).throw(ValueError('Synthetic deadline/type refusal'))
        with self.assertRaisesRegex(ValueError, 'deadline/type'):
            reader.members('b'*40)


if __name__ == '__main__':
    unittest.main()
