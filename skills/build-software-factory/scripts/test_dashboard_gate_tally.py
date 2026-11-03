"""Required-gate tally presentation on synthetic in-memory data only.

The PASSED ring stays a raw recorded count; NOT APPLICABLE is shown beside it,
never added to it, and optional WAIVED rows never become PASSED.
"""
import copy
from datetime import datetime, timezone
import json
import re
import unittest

from dashboard import page, summarize
from scaffold import ROOT, render, validate


def gate(ident, state, required=True, recorded=None, stage='pre-merge'):
    return {'id': ident, 'stage': stage, 'required': required, 'state': state,
            'recorded_result': recorded or state, 'revision': 'b'*40,
            'observed_at': '2026-11-03T12:00:00+00:00', 'freshness': 'recent'}


class GateTallyTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)

    def data(self, gates):
        data = summarize(render(self.config, self.research), now=self.now)
        data['gates'] = gates
        data['release'] = next((g for g in gates if g['id'] == 'G3'), None)
        return data

    def panel(self, html):
        start = html.index('<h2>Required gates passed</h2>')
        return html[start:html.index('</section>', start)]

    def test_not_applicable_is_separate_from_passed_and_others(self):
        gates = [gate('G1', 'PASSED'), gate('G2', 'PASSED'), gate('G4', 'FAILED'),
                 gate('G3', 'NOT APPLICABLE', stage='post-merge'),
                 gate('X1', 'WAIVED', required=False, recorded='FAILED')]
        data = self.data(gates); before = copy.deepcopy(data)
        panel = self.panel(page(data))
        self.assertEqual(data, before)  # Presentation never rewrites recorded rows.
        self.assertIn('<span aria-hidden="true">2/4</span>', panel)
        self.assertIn('aria-label="2 of 4 required gate rows recorded PASSED"', panel)
        self.assertIn('conic-gradient(var(--ok) 50%', panel)
        self.assertIn('<li><b>2</b> recorded PASSED</li>', panel)
        self.assertIn('<li><b>1</b> recorded NOT APPLICABLE; shown separately, not counted as passed', panel)
        self.assertIn('exception is not validated here', panel)
        self.assertIn('<li><b>1</b> other recorded result (FAILED', panel)
        self.assertIn('1 optional row shown as WAIVED; excluded from these counts.', panel)
        self.assertIn('they are not release readiness', panel)
        self.assertIn('G3 NOT APPLICABLE', panel); self.assertIn('X1 WAIVED', panel)
        # No combined PASSED+N/A figure and no aggregate "satisfied" claim.
        self.assertNotIn('3/4', panel); self.assertNotIn('<b>3</b>', panel)
        self.assertNotIn('satisf', panel.lower())

    def test_only_not_applicable_never_reads_as_passed(self):
        panel = self.panel(page(self.data([gate('G3', 'NOT APPLICABLE', stage='post-merge')])))
        self.assertIn('<span aria-hidden="true">0/1</span>', panel)
        self.assertIn('<li><b>0</b> recorded PASSED</li>', panel)
        self.assertIn('<li><b>1</b> recorded NOT APPLICABLE', panel)
        self.assertIn('<li><b>0</b> other recorded result', panel)
        self.assertNotIn('1/1', panel)

    def test_optional_waived_with_recorded_pass_is_not_counted(self):
        gates = [gate('G1', 'FAILED'), gate('X1', 'WAIVED', required=False, recorded='PASSED'),
                 gate('X2', 'WAIVED', required=False, recorded='NOT RUN')]
        html = page(self.data(gates)); panel = self.panel(html)
        self.assertIn('<span aria-hidden="true">0/1</span>', panel)
        self.assertIn('<li><b>0</b> recorded PASSED</li>', panel)
        self.assertIn('<li><b>1</b> other recorded result', panel)
        self.assertIn('2 optional rows shown as WAIVED; excluded from these counts.', panel)
        self.assertNotIn('X1 PASSED', html)
        self.assertIn('WAIVED keeps its recorded result and never counts as passed.', html)

    def test_empty_records_show_no_tally_and_zero_ring(self):
        panel = self.panel(page(self.data([])))
        self.assertIn('<span aria-hidden="true">0/0</span>', panel)
        self.assertIn('aria-label="0 of 0 required gate rows recorded PASSED"', panel)
        self.assertIn('No required gate rows recorded.', panel)
        self.assertNotIn('class="tally"', panel); self.assertNotIn('optional row', panel)

    def test_all_required_passed(self):
        panel = self.panel(page(self.data([gate('G1', 'PASSED'), gate('G2', 'PASSED')])))
        self.assertIn('<span aria-hidden="true">2/2</span>', panel)
        self.assertIn('conic-gradient(var(--ok) 100%', panel)
        self.assertIn('<li><b>0</b> recorded NOT APPLICABLE', panel)
        self.assertIn('<li><b>0</b> other recorded result', panel)

    def test_selected_assessment_stays_separate_and_unchanged(self):
        gates = [gate('G1', 'PASSED'), gate('G3', 'NOT APPLICABLE', stage='post-merge')]
        data = self.data(gates)
        data['assessment'] = {'state': 'satisfied', 'subject': 'c'*40, 'stage': 'post-merge', 'reason': 'SYNTHETIC reason',
                              'actual_target': None, 'scope': 'SYNTHETIC scope', 'problems': [],
                              'omitted_problem_count': 0, 'waived': [], 'notice': 'SYNTHETIC notice'}
        html = page(data)
        self.assertIn('SATISFIES RECORD RULES', html)
        self.assertLess(html.index('Selected record assessment'), html.index('Required gates passed'))
        panel = self.panel(html)
        self.assertIn('<span aria-hidden="true">1/2</span>', panel)
        self.assertNotIn('SATISFIES', panel)

    def test_labels_are_escaped_from_unexpected_state_values(self):
        panel = self.panel(page(self.data([gate('G1', '<script>x</script>')])))
        self.assertNotIn('<script>', panel)
        self.assertIn('<li><b>1</b> other recorded result', panel)

    def test_rendered_no_release_factory_shows_recorded_not_applicable_g3(self):
        # Same validated no-release scope used by the structured gate tests.
        self.config['operations'] = {'done_videos': {'enabled': True, 'triggers': ['pre_merge_preview']},
            'smoke_gates': {'target_kind': 'no_release', 'post_merge_applicability': 'not_applicable',
                            'post_merge_rationale': 'Internal preview only', 'accepted_by': 'Synthetic owner'}}
        validate(self.config)
        data = summarize(render(self.config, self.research), now=self.now)
        g3 = next(g for g in data['gates'] if g['id'] == 'G3')
        self.assertTrue(g3['required']); self.assertEqual(g3['state'], 'NOT APPLICABLE')
        required = [g for g in data['gates'] if g['required']]
        passed = sum(g['state'] == 'PASSED' for g in required)
        na = sum(g['state'] == 'NOT APPLICABLE' for g in required)
        panel = self.panel(page(data))
        self.assertEqual(g3['state'], 'NOT APPLICABLE')
        self.assertIn('<span aria-hidden="true">'+str(passed)+'/'+str(len(required))+'</span>', panel)
        self.assertIn('<li><b>'+str(na)+'</b> recorded NOT APPLICABLE', panel)
        self.assertGreaterEqual(na, 1)
        self.assertEqual(re.findall(r'<b>(\d+)</b>', panel)[0], str(passed))


if __name__ == '__main__':
    unittest.main()
