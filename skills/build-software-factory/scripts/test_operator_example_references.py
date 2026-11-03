"""Documentation routing regressions only; runtime example tests live separately."""
import re
import unittest

from scaffold import ROOT


class OperatorExampleReferenceTests(unittest.TestCase):
    def test_operator_entrypoints_link_to_existing_examples(self):
        references = ROOT / 'references'
        routes = {
            'intake.md': 'disposable-fixture-example.md',
            'gates.md': 'disposable-fixture-example.md',
            'done-videos.md': 'disposable-fixture-example.md',
            'operations-config.md': 'intake-label-example.md',
        }
        for source, target in routes.items():
            with self.subTest(source=source):
                text = (references / source).read_text(encoding='utf-8')
                links = re.findall(r'\[[^\]]+\]\(([^)]+)\)', text)
                self.assertIn(target, links)
                self.assertTrue((references / target).is_file())

    def test_intake_question_keeps_target_choices_and_observation_boundary(self):
        text = (ROOT / 'references/intake.md').read_text(encoding='utf-8')
        questions = [line for line in text.splitlines() if line.startswith('- **Checks that write data:**')]
        self.assertEqual(len(questions), 1)
        for phrase in ('web target with a database', 'read-only', 'run-scoped writes with teardown',
                       'disposable representative target', 'cleanup owner', 'allowed delete scope',
                       'data written, cleanup and residue', 'required production check',
                       'BLOCKED/NOT RUN', 'WAIVED'):
            self.assertIn(phrase, questions[0])


if __name__ == '__main__':
    unittest.main()
