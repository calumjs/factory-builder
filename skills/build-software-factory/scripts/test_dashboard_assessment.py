"""Explicit full-stage record assessments on isolated synthetic factory copies."""
import copy
from datetime import datetime, timezone
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import dashboard
from gates import assess, gate_rows
from integrity import check, digest
from scaffold import ROOT, render
import update_operations as updater


GATE_PANEL_START = '<section class="panel"><h2>Required gates passed</h2>'
ROW_RULE = '.row{display:flex;gap:18px;align-items:center}\n'
TALLY_RULE = '.tally{list-style:none;margin:0 0 8px;padding:0;font-size:.85rem}.tally li{margin:2px 0}\n'
RING_FIGURE = re.compile(r'<span(?: aria-hidden="true")?>(\d+/\d+)</span>')
PILL = re.compile(r'<span class="pill [^"]*">[^<]*</span>')


def gate_panel_drift(old_html, new_html):
    """List differences beyond the intended Required gates tally panel and its single CSS rule.

    Outside that panel the successor must equal the predecessor byte for byte, except that
    TALLY_RULE is inserted exactly once, immediately after the existing .row rule. Inside the
    panel the heading/note, gate pills and PASSED ring figure must be unchanged.
    """
    problems = []
    parts = {}
    for label, html in (('old', old_html), ('new', new_html)):
        if html.count(GATE_PANEL_START) != 1:
            return [label+' HTML must contain exactly one Required gates panel']
        start = html.index(GATE_PANEL_START)
        end = html.index('</section>', start)+len('</section>')
        parts[label] = (html[:start], html[start:end], html[end:])
    (old_pre, old_panel, old_post), (new_pre, new_panel, new_post) = parts['old'], parts['new']
    if old_pre.count(ROW_RULE) != 1 or TALLY_RULE in old_html:
        problems.append('predecessor CSS anchor changed')
    elif old_pre.replace(ROW_RULE, ROW_RULE+TALLY_RULE, 1) != new_pre:
        problems.append('HTML before the Required gates panel differs beyond the single tally CSS rule')
    if new_html.count(TALLY_RULE) != 1:
        problems.append('tally CSS rule must appear exactly once')
    if old_post != new_post:
        problems.append('HTML after the Required gates panel differs')
    for label, panel in (('old', old_panel), ('new', new_panel)):
        if panel.count('<div class="row">') != 1:
            problems.append(label+' Required gates panel lost its row container')
    if not problems:
        if old_panel.split('<div class="row">')[0] != new_panel.split('<div class="row">')[0]:
            problems.append('Required gates heading or note changed')
        if PILL.findall(old_panel) != PILL.findall(new_panel):
            problems.append('Required gates pills changed')
        old_ring, new_ring = RING_FIGURE.findall(old_panel), RING_FIGURE.findall(new_panel)
        if len(old_ring) != 1 or old_ring != new_ring:
            problems.append('Required gates PASSED ring figure changed: '+repr((old_ring, new_ring)))
    return problems


class DashboardAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.factory = self.base / '.software-factory'
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.config['operations'] = {'smoke_gates': {'required': True, 'target_kind': 'artifact', 'deployed_url': 'artifact:synthetic'}}
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())
        self.write_factory()
        self.subject = 'a' * 40
        self.selection = {'subject': self.subject, 'stage': 'pre-merge', 'actual_target': None,
                          'reason': 'These synthetic checks were recorded for the reviewed head; storage commit differs.'}
        self.now = datetime.now(timezone.utc)
        self.fill_rows()

    def write_factory(self):
        for name, text in render(self.config, self.research).items():
            path = self.factory/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(text.encode('utf-8'))

    def snapshot(self):
        return {path.relative_to(self.factory).as_posix(): path.read_bytes() for path in self.factory.rglob('*') if path.is_file()}

    def contract(self, name, data):
        (self.factory/name).write_bytes(data)
        manifest = json.loads((self.factory/'manifest.json').read_bytes())
        manifest['contracts'][name] = digest(data)
        (self.factory/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')

    def fill_rows(self):
        path = self.factory/'verification.md'; text = path.read_text(encoding='utf-8')
        for ident, row in gate_rows(text).items():
            original = next(line for line in text.splitlines() if line.startswith('| '+ident+' |'))
            row.update(design='SYNTHETIC check', environment='synthetic', revision=self.subject, result='PASSED',
                       evidence='PRIVATE-EVIDENCE-BODY', target='artifact:synthetic', checked_at=self.now.isoformat(), exit_status='0')
            text = text.replace(original, '| '+' | '.join(row.values())+' |')
        path.write_text(text, encoding='utf-8')

    def row(self, ident, **changes):
        path = self.factory/'verification.md'; text = path.read_text(encoding='utf-8')
        row = gate_rows(text)[ident]; row.update(changes)
        original = next(line for line in text.splitlines() if line.startswith('| '+ident+' |'))
        path.write_text(text.replace(original, '| '+' | '.join(row.values())+' |'), encoding='utf-8')

    def read(self, selection=None):
        return dashboard.read(self.factory, now=self.now, assessment=self.selection if selection is None else selection)

    def old_dashboard(self):
        path = ROOT/'scripts/fixtures/pre_subject_dashboard.txt'
        loader = importlib.machinery.SourceFileLoader('pre_subject_fixture', str(path))
        module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader)); loader.exec_module(module)
        return module

    def test_no_selection_dto_matches_predecessor_and_html_differs_only_by_gate_tally_panel_and_css_rule(self):
        before = self.snapshot(); prior = self.old_dashboard()
        expected = prior.read(self.factory, now=self.now)
        with patch.object(dashboard, 'assess_gates', side_effect=AssertionError('No implicit assessment')):
            actual = dashboard.read(self.factory, now=self.now)
        self.assertEqual(actual, expected)
        self.assertNotIn('assessment', actual)
        old_html, new_html = prior.page(expected), dashboard.page(actual)
        self.assertNotEqual(new_html, old_html)  # The tally panel change is intentional.
        self.assertEqual(gate_panel_drift(old_html, new_html), [])
        self.assertEqual(self.snapshot(), before)

    def test_gate_panel_drift_probe_rejects_changes_outside_the_intended_presentation(self):
        prior = self.old_dashboard(); data = prior.read(self.factory, now=self.now)
        old_html, new_html = prior.page(data), dashboard.page(dashboard.read(self.factory, now=self.now))
        start = new_html.index(GATE_PANEL_START); end = new_html.index('</section>', start)+len('</section>')
        pre, panel, post = new_html[:start], new_html[start:end], new_html[end:]
        figure = RING_FIGURE.search(panel).group(1); passed, total = figure.split('/')
        first_pill = PILL.search(panel).group(0)
        mutations = {
            'before panel': new_html.replace('Recorded task states; not a live queue.', 'Recorded task states.', 1),
            'after panel': pre+panel+post.replace('</main>', '<p>extra</p></main>', 1),
            'extra CSS': new_html.replace(TALLY_RULE, TALLY_RULE+'.extra{color:red}\n', 1),
            'missing CSS': new_html.replace(TALLY_RULE, '', 1),
            'moved CSS': new_html.replace(TALLY_RULE, '', 1).replace('</style>', TALLY_RULE+'</style>', 1),
            'duplicated CSS': new_html.replace(TALLY_RULE, TALLY_RULE+TALLY_RULE, 1),
            'panel note': new_html.replace('readiness for one revision comes from the gate checker.', 'ready.', 1),
            'pill': pre+panel.replace(first_pill, first_pill.replace('</span>', ' X</span>'), 1)+post,
            'ring promotion': pre+panel.replace('>'+figure+'</span>', '>'+str(int(passed)+1)+'/'+total+'</span>', 1)+post,
            'second panel': pre+panel+panel+post,
        }
        self.assertEqual(gate_panel_drift(old_html, new_html), [])
        for name, mutated in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(mutated, new_html)
                self.assertTrue(gate_panel_drift(old_html, mutated))

    def test_explicit_subject_reason_full_stage_and_backend_result_are_exported_without_promotion(self):
        before = self.snapshot(); data = self.read(); result = data['assessment']
        self.assertEqual(result['subject'], self.subject)
        self.assertEqual(result['reason'], self.selection['reason'])
        self.assertEqual(result['problems'], assess(self.factory, 'pre-merge', self.subject))
        self.assertEqual(result['state'], 'satisfied')
        self.assertIsNone(result['actual_target'])
        self.assertIn('policy.md', {source['artifact'] for source in data['sources']})
        self.assertIn('SATISFIES RECORD RULES', dashboard.page(data))
        self.assertNotIn('PRIVATE-EVIDENCE-BODY', json.dumps(data))
        self.assertEqual(self.snapshot(), before)

    def test_exact_subject_does_not_follow_storage_commit_or_match_prefix(self):
        task_path = self.factory/'task-plan.json'; plan = json.loads(task_path.read_bytes())
        plan['events'] = [{'id':'stored', 'task_id':'T1', 'timestamp':self.now.isoformat(), 'revision':'e'*40,
                           'environment':'synthetic','check':'record storage','result':'not-run','evidence':'PRIVATE storage note',
                           'old_status':'blocked','status':'blocked'}]
        task_path.write_text(json.dumps(plan), encoding='utf-8')
        self.assertEqual(self.read()['assessment']['state'], 'satisfied')
        for value in ('b'*40, 'e'*40, self.subject[:7]):
            selected = {**self.selection, 'subject': value}
            result = self.read(selected)['assessment']
            self.assertEqual(result['state'], 'blocked')
            self.assertTrue(any('stale or missing revision' in item for item in result['problems']))
            self.assertEqual(result['subject'], value)

    def test_failed_missing_and_stale_required_rows_block(self):
        path = self.factory/'verification.md'; original = path.read_bytes()
        for changes in ({'result':'FAILED'}, {'revision':'b'*40}):
            path.write_bytes(original); self.row('A1', **changes)
            self.assertEqual(self.read()['assessment']['state'], 'blocked')
        path.write_bytes(original)
        path.write_text('\n'.join(line for line in path.read_text().splitlines() if not line.startswith('| A1 |'))+'\n', encoding='utf-8')
        data = self.read()
        self.assertEqual(data['assessment']['state'], 'blocked')
        self.assertIn('Missing expected gate row: A1', data['assessment']['problems'])
        self.assertTrue(data['errors'])

    def test_waived_failure_retains_underlying_result_and_does_not_become_passed(self):
        self.row('A1', required='no', result='FAILED', revision='old-subject')
        data = self.read()
        self.assertEqual(data['assessment']['state'], 'satisfied')
        self.assertIn({'id':'A1','recorded_result':'FAILED'}, data['assessment']['waived'])
        row = next(item for item in data['gates'] if item['id']=='A1')
        self.assertEqual((row['state'], row['recorded_result']), ('WAIVED', 'FAILED'))
        self.assertIn('A1 (recorded FAILED)', dashboard.page(data))

    def test_actual_post_target_is_never_filled_from_planned_or_recorded_target(self):
        selected = {**self.selection, 'stage':'post-merge'}
        missing = self.read(selected)['assessment']
        self.assertEqual(missing['state'], 'blocked'); self.assertIsNone(missing['actual_target'])
        self.assertTrue(any('actual --target' in issue for issue in missing['problems']))
        wrong = self.read({**selected, 'actual_target':'artifact:wrong'})['assessment']
        self.assertEqual(wrong['state'], 'blocked')
        self.assertTrue(any('differs from the configured target' in issue for issue in wrong['problems']))
        self.assertEqual(self.read({**selected, 'actual_target':'artifact:synthetic'})['assessment']['state'], 'satisfied')
        self.row('G3', target='PRIVATE-RECORDED-TARGET')
        data = self.read({**selected, 'actual_target':'artifact:synthetic'})
        self.assertEqual(data['assessment']['state'], 'blocked')
        self.assertNotIn('PRIVATE-RECORDED-TARGET', json.dumps(data))

    def test_post_stage_all_waived_remains_waived_without_inventing_target(self):
        for ident, row in gate_rows((self.factory/'verification.md').read_text()).items():
            if row['stage']=='post-merge': self.row(ident, required='no', result='FAILED')
        result = self.read({**self.selection, 'stage':'post-merge'})['assessment']
        self.assertEqual(result['state'], 'satisfied'); self.assertTrue(result['waived']); self.assertIsNone(result['actual_target'])
        self.assertTrue(all(item['recorded_result']=='FAILED' for item in result['waived']))

    def test_video_ordering_still_comes_from_full_stage_gate_checker(self):
        self.config['operations']['done_videos'] = {'enabled':True,'scope':'Synthetic release','evidence':'Synthetic preference'}
        self.write_factory(); self.fill_rows()
        self.row('G3', checked_at='2026-11-03T12:00:00+00:00')
        self.row('V1', checked_at='2026-11-03T11:00:00+00:00')
        result = self.read({**self.selection, 'stage':'post-merge', 'actual_target':'artifact:synthetic'})['assessment']
        self.assertEqual(result['state'], 'blocked')
        self.assertIn('V1 must follow passing G3 evidence for the shipped revision', result['problems'])

    def test_invalid_or_partial_context_refuses_without_factory_writes(self):
        before = self.snapshot()
        variants = [{'actual_target':'artifact:synthetic'}, {**self.selection, 'stage':None}, {**self.selection, 'reason':None},
                    {**self.selection, 'subject':' '+self.subject}, {**self.selection, 'reason':'line\nbreak'},
                    {**self.selection, 'reason':'x'*501}, {**self.selection, 'actual_target':'x'*2049}]
        for value in variants:
            with self.subTest(value=value), self.assertRaises(ValueError): self.read(value)
        self.assertEqual(self.snapshot(), before)

    def test_escaped_explicit_context_does_not_export_implicit_private_fields(self):
        selected = {**self.selection, 'reason':'Approved <script>example</script> & explanation', 'actual_target':'artifact:<approved>'}
        data = self.read(selected); html = dashboard.page(data)
        self.assertIn('&lt;script&gt;example&lt;/script&gt;', html)
        self.assertNotIn('<script>example</script>', html)
        self.assertIn('artifact:&lt;approved&gt;', html)
        self.assertNotIn('PRIVATE-EVIDENCE-BODY', html)
        self.assertEqual(data['assessment']['reason'], selected['reason'])

    def test_policy_drift_and_ordinary_mutation_do_not_produce_an_assessment_snapshot(self):
        real_assess = dashboard.assess_gates
        for name in ('verification.md', 'policy.md'):
            def assess_then_edit(*args):
                issues = real_assess(*args)
                path = self.factory/name
                if name == 'policy.md':
                    raw = path.read_bytes(); changed = raw.replace(b'\n', b'\r\n')
                    self.assertEqual(digest(raw), digest(changed)); path.write_bytes(changed)
                else:
                    with path.open('a', encoding='utf-8') as stream: stream.write('\nConcurrent note\n')
                return issues
            with patch.object(dashboard, 'assess_gates', side_effect=assess_then_edit):
                with self.subTest(source=name), self.assertRaisesRegex(ValueError, 'changed while reading'): self.read()
        self.config['operations']['smoke_gates']['required'] = False
        self.contract('config.json', json.dumps(self.config).encode())
        with self.assertRaisesRegex(ValueError, 'policy controls disagree'): self.read()

    def test_diagnostic_truncation_cannot_turn_blocked_into_satisfied(self):
        with patch.object(dashboard, 'assess_gates', return_value=['A1 '+('x'*900)]*105):
            data = self.read()
        result = data['assessment']
        self.assertEqual(result['state'], 'blocked'); self.assertEqual(len(result['problems']), 100)
        self.assertEqual(result['omitted_problem_count'], 5)
        self.assertTrue(all(len(item)<650 for item in result['problems']))
        self.assertIn('additional problems omitted; assessment remains blocked', dashboard.page(data))

    def test_copied_cli_explicit_selection_and_failed_refresh_preserve_prior_output(self):
        output = self.base/'selected.json'
        argv = [sys.executable, '-B', str(self.factory/'dashboard/dashboard.py'), '--output', str(output), '--format','json']
        selected = ['--assessment-subject', self.subject, '--assessment-stage','pre-merge','--assessment-reason', self.selection['reason']]
        before = self.snapshot()
        result = subprocess.run(argv+selected, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_bytes())['assessment']['state'], 'satisfied')
        old = output.read_bytes()
        result = subprocess.run(argv+['--replace','--assessment-target','artifact:only'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0); self.assertEqual(output.read_bytes(), old)
        self.assertEqual(self.snapshot(), before)

    def test_known_predecessor_is_preserved_by_default_and_joint_migration_executes(self):
        predecessor = (ROOT/'scripts/fixtures/pre_subject_dashboard.txt').read_bytes()
        self.assertEqual(digest(predecessor), updater.PRE_SUBJECT_DASHBOARD['dashboard.py'])
        self.contract('dashboard/dashboard.py', predecessor)
        old_gate = (ROOT/'scripts/fixtures/pre65_gates.txt').read_bytes()
        self.contract('dashboard/gates.py', old_gate)
        before = self.snapshot()
        _, _, replacements, _ = updater.prepare(self.factory, {}, assumptions_update=[])
        self.assertNotIn('dashboard/dashboard.py', replacements)
        self.assertNotIn('dashboard/gates.py', replacements)
        with self.assertRaisesRegex(ValueError, '--context-runtime --gate-runtime'):
            updater.prepare(self.factory, {}, context_runtime=True)
        self.assertEqual(self.snapshot(), before)
        root, old, replacements, token = updater.prepare(self.factory, {}, context_runtime=True, gate_runtime=True)
        with self.assertRaises(ValueError): updater.apply(root, old, replacements, token, 'wrong')
        self.assertEqual(self.snapshot(), before)
        backup = updater.apply(root, old, replacements, token, token)
        self.assertEqual((backup/'dashboard/dashboard.py').read_bytes(), predecessor)
        self.assertEqual((backup/'dashboard/gates.py').read_bytes(), old_gate)
        self.assertEqual((self.factory/'verification.md').read_bytes(), before['verification.md'])
        self.assertEqual((self.factory/'task-plan.json').read_bytes(), before['task-plan.json'])
        check(self.factory, quiet=True)
        output = self.base/'migrated.json'
        result = subprocess.run([sys.executable,'-B',str(self.factory/'dashboard/dashboard.py'),'--output',str(output),'--format','json',
                                 '--assessment-subject',self.subject,'--assessment-stage','pre-merge','--assessment-reason',self.selection['reason']], capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_bytes())['assessment']['state'], 'satisfied')

    def test_custom_dashboard_and_gate_copies_are_not_overwritten(self):
        for name in ('dashboard.py', 'gates.py'):
            self.write_factory(); self.fill_rows()
            path = 'dashboard/'+name
            self.contract(path, (self.factory/path).read_bytes()+b'\n# SYNTHETIC customization\n')
            before = self.snapshot()
            with self.assertRaisesRegex(ValueError, 'Customized/unsupported'):
                updater.prepare(self.factory, {}, context_runtime=True, gate_runtime=True)
            self.assertEqual(self.snapshot(), before)

    def test_complete_proposed_backend_handles_missing_modules_and_binds_unchanged_bytes(self):
        predecessor = (ROOT/'scripts/fixtures/pre_subject_dashboard.txt').read_bytes()
        for filename in ('gates.py', 'operations.py', 'recipes.py'):
            self.write_factory(); self.fill_rows()
            self.contract('dashboard/dashboard.py', predecessor)
            name = 'dashboard/'+filename
            (self.factory/name).unlink()
            manifest = json.loads((self.factory/'manifest.json').read_bytes())
            del manifest['contracts'][name]
            (self.factory/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            before = self.snapshot()
            if filename == 'recipes.py':
                # Existing explicit context/recipe migration can supply this known dependency.
                root, old, replacements, token = updater.prepare(self.factory, {}, context_runtime=True)
                self.assertIsNone(old[name])
                self.assertEqual(replacements[name], (ROOT/'scripts'/filename).read_bytes())
                backup = updater.apply(root, old, replacements, token, token)
                self.assertTrue(backup.exists()); check(self.factory, quiet=True)
            else:
                with self.subTest(missing=filename), self.assertRaisesRegex(ValueError, 'complete current copied gate backend'):
                    updater.prepare(self.factory, {}, context_runtime=True)
                self.assertEqual(self.snapshot(), before)
        for filename in ('gates.py', 'operations.py', 'recipes.py'):
            self.write_factory(); self.fill_rows()
            self.contract('dashboard/dashboard.py', predecessor)
            root, old, replacements, token = updater.prepare(self.factory, {}, context_runtime=True)
            name = 'dashboard/'+filename; current = (self.factory/name).read_bytes()
            self.assertEqual(old[name], current)
            self.assertNotIn(name, replacements)
            # Same normalized contract digest, different raw reviewed bytes.
            changed = current.replace(b'\n', b'\r\n')
            self.assertNotEqual(changed, current); self.assertEqual(digest(changed), digest(current))
            (self.factory/name).write_bytes(changed); before = self.snapshot(); check(self.factory, quiet=True)
            with self.subTest(concurrent=filename), self.assertRaises(ValueError):
                updater.apply(root, old, replacements, token, token)
            self.assertEqual(self.snapshot(), before)


if __name__ == '__main__': unittest.main()
