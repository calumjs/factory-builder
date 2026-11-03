"""Offline scenario accounting with generated rows; no actors or services are used."""
import json
import unittest

from gates import gate_rows, problems, requirements, waivers
from incremental_records import gate_change
from scaffold import ROOT, render


class MultiActorEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.files = render(self.config, self.research)
        self.expected = requirements(self.config, self.research)
        self.target = 'https://production.example.invalid'
        self.revision = 'synthetic-subject'
        self.text = self.files['verification.md']
        # Supplied synthetic observation: only the unsigned request was exercised.
        self.text = self.edit(self.text, 'G3', {
            2: 'Unsigned request rejects access; notification fan-out tracked separately in M1',
            3: 'synthetic production target', 5: self.revision, 6: 'PASSED',
            7: 'SYNTHETIC unsigned-request observation only; excluded fan-out: M1',
            8: self.target, 9: '2026-11-03T00:00:00Z', 10: '0'})
        self.text += ('\n| M1 | post-merge | Notification fan-out from second actor | synthetic production target'
                      ' | yes | synthetic-subject | BLOCKED | Second approved actor unavailable; no setup authorized'
                      ' | https://production.example.invalid | | |\n')

    @staticmethod
    def edit(text, gate, values):
        output = []
        for line in text.splitlines():
            if line.startswith('| ' + gate + ' |'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                for index, value in values.items():
                    cells[index] = value
                line = '| ' + ' | '.join(cells) + ' |'
            output.append(line)
        return '\n'.join(output)

    def assess(self, text):
        return problems(text, 'post-merge', self.revision, self.expected, self.target)

    def test_filtered_success_does_not_hide_missing_required_actor_scenario(self):
        for result in ('BLOCKED', 'NOT RUN'):
            with self.subTest(result=result):
                text = self.edit(self.text, 'M1', {6: result})
                self.assertEqual(gate_rows(text)['G3']['result'], 'PASSED')
                self.assertIn('M1 is ' + result, self.assess(text))
                self.assertEqual(waivers(text, 'post-merge'), [])

    def test_preview_actor_success_cannot_confirm_required_production_scenario(self):
        text = self.edit(self.text, 'M1', {
            3: 'disposable representative preview', 6: 'PASSED',
            7: 'SYNTHETIC preview fan-out observation with isolated actors',
            8: 'https://preview.example.invalid', 9: '2026-11-03T00:01:00Z', 10: '0'})
        self.assertIn('M1 evidence is for a different target', self.assess(text))

    def test_explicit_optional_scenario_remains_visible_as_waiver_with_actual_result(self):
        text = self.edit(self.text, 'M1', {
            4: 'no', 7: 'User explicitly chose preview-only fan-out coverage; production actors unavailable'})
        self.assertEqual(self.assess(text), [])
        self.assertEqual(gate_rows(text)['M1']['result'], 'BLOCKED')
        self.assertEqual(waivers(text, 'post-merge'), ['M1 WAIVED (recorded BLOCKED)'])

    def test_confirmed_approved_actors_allow_required_scenario_evidence(self):
        text = self.edit(self.text, 'M1', {
            6: 'PASSED', 7: 'SYNTHETIC fan-out observation with two approved preprovisioned actors',
            9: '2026-11-03T00:01:00Z', 10: '0'})
        self.assertEqual(self.assess(text), [])
        self.assertEqual(waivers(text, 'post-merge'), [])

    def test_filter_expression_uses_evidence_reference_without_changing_writer_schema(self):
        observation = {
            'gate': 'G3', 'result': 'BLOCKED', 'revision': self.revision,
            'environment': 'synthetic production target', 'evidence': '',
            'target': self.target, 'checked_at': '', 'exit_status': ''}
        for expression in ('--grep-invert "fan-out|handoff"', '--grep-invert "fan-out\\|handoff"'):
            with self.subTest(expression=expression):
                observation['evidence'] = expression
                with self.assertRaisesRegex(ValueError, 'Invalid evidence'):
                    gate_change(self.files['verification.md'], self.config, self.research, observation)
        observation['evidence'] = 'logs/synthetic-g3-scope.txt; fan-out and handoff excluded; approved actors unavailable'
        updated = gate_change(self.files['verification.md'], self.config, self.research, observation).decode('utf-8')
        row = gate_rows(updated)['G3']
        self.assertEqual(row['evidence'], observation['evidence'])
        self.assertEqual(row['result'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
