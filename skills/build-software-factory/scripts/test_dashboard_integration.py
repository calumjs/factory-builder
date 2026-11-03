"""Copied-helper and DOM regressions; structural checks are not visual QA."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from integrity import check, ManifestFileSetMismatch
from scaffold import ROOT, render


class GateTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.ancestors = None
        self.gate_depth = None
        self.cell = None
        self.cells = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'script':
            self.scripts += 1
        if tag == 'table' and attributes.get('class') == 'gate-table':
            self.ancestors = list(self.stack)
            self.gate_depth = len(self.stack)
        if tag == 'td' and self.gate_depth is not None:
            self.cell = []
        if tag not in ('meta', 'link', 'br', 'hr', 'img', 'input'):
            self.stack.append((tag, attributes))

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.cells.append(''.join(self.cell))
            self.cell = None
        if tag == 'table' and self.gate_depth == len(self.stack)-1:
            self.gate_depth = None
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()


class DashboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.factory = self.base/'.software-factory'
        self.config = json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.write_factory()

    def write_factory(self):
        for name, body in render(self.config, self.research).items():
            path = self.factory/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix(): p.read_bytes()
                for p in self.factory.rglob('*') if p.is_file()}

    def invoke(self, output, format='html', replace=False):
        command = [sys.executable, '-B', str(self.factory/'dashboard/dashboard.py'),
                   '--output', str(output), '--format', format]
        if replace:
            command.append('--replace')
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(self.snapshot(), before)
        return result

    def test_copied_mismatch_summary_preserves_existing_html_and_json_outputs(self):
        cache = self.factory/'dashboard/__pycache__'
        cache.mkdir()
        (cache/'PRIVATE-SYNTHETIC.pyc').write_bytes(b'PRIVATE-CONTENT')
        (self.factory/'PRIVATE-TOKEN.txt').write_text('PRIVATE-CONTENT', encoding='utf-8')
        (self.factory/'project-brief.md').unlink()
        for format in ('html', 'json'):
            with self.subTest(format=format):
                output = self.base/('snapshot.'+format)
                output.write_bytes(b'previous snapshot')
                result = self.invoke(output, format, replace=True)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(output.read_bytes(), b'previous snapshot')
                self.assertIn('2 unexpected and 1 missing', result.stderr)
                self.assertIn('Unexpected dashboard/__pycache__/ bytecode is present', result.stderr)
                self.assertIn('scaffold.py --check', result.stderr)
                for private in ('PRIVATE', 'project-brief', str(self.factory)):
                    self.assertNotIn(private, result.stderr)
                self.assertNotIn('Snapshot written', result.stdout)

    def test_trusted_integrity_caller_keeps_named_details_and_structured_counts(self):
        (self.factory/'PRIVATE-TOKEN.txt').write_text('PRIVATE-CONTENT', encoding='utf-8')
        with self.assertRaises(ManifestFileSetMismatch) as raised:
            check(self.factory, quiet=True)
        error = raised.exception
        self.assertEqual((error.unexpected_count, error.missing_count, error.dashboard_bytecode), (1, 0, False))
        self.assertIn('PRIVATE-TOKEN.txt', str(error))
        self.assertNotIn('PRIVATE-CONTENT', str(error))

    def test_unclassified_private_parse_failure_is_not_dumped_or_written(self):
        (self.factory/'task-plan.json').write_text('{"PRIVATE-MALFORMED":', encoding='utf-8')
        output = self.base/'snapshot.html'
        output.write_bytes(b'previous snapshot')
        result = self.invoke(output, replace=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Dashboard unavailable', result.stderr)
        self.assertNotIn('PRIVATE', result.stderr)
        self.assertEqual(output.read_bytes(), b'previous snapshot')

    def test_generated_gate_dom_has_full_width_scroll_container_and_complete_escaped_cells(self):
        self.config['acceptance'] = ['Synthetic criterion '+str(i) for i in range(13)]
        self.write_factory()  # Sixteen gates, matching the issue's crowded-table case.
        verification = self.factory/'verification.md'
        rows = []
        revision = 'a'*40
        timestamp = '2026-10-31T07:56:06+11:00'
        markup = '<script>synthetic</script>'
        for line in verification.read_text(encoding='utf-8').splitlines():
            if line.startswith('| G1 |') or line.startswith('| G2 |'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                cells[5] = revision if cells[0] == 'G1' else markup
                cells[9] = timestamp
                line = '| '+' | '.join(cells)+' |'
            rows.append(line)
        verification.write_text('\n'.join(rows)+'\n', encoding='utf-8')
        output = self.base/'snapshot.html'
        result = self.invoke(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = output.read_text(encoding='utf-8')
        parsed = GateTableParser()
        parsed.feed(document)
        self.assertEqual(parsed.scripts, 0)
        self.assertEqual(len(parsed.cells), 16*7)
        self.assertIn(revision, parsed.cells)
        self.assertIn(timestamp, parsed.cells)
        self.assertIn(markup, parsed.cells)  # Text decoded from escaped HTML, never an element.
        self.assertIn('unavailable', parsed.cells)
        self.assertIsNotNone(parsed.ancestors)
        classes = [attributes.get('class', '') for _, attributes in parsed.ancestors]
        self.assertEqual(classes[-3:], ['grid', 'panel', 'scroll'])
        self.assertNotIn('grid g2', classes)
        self.assertIn("default-src 'none'", document)
        check(self.factory, quiet=True)


if __name__ == '__main__':
    unittest.main()
