"""Complete preserved Learn-table cases plus module boundary regressions."""
import unittest
from pathlib import Path
import subprocess
import sys
import tempfile
from learning_table import LEARNING_HEADER, learning_cells, validate_learning_log
HEADER = '| Date / task / revision | Observed result and evidence | Hypothesis | Proposed change | Owner | Evaluation measure | Approval / outcome |'
DELIM = '|---|---|---|---|---|---|---|'
ROW = '| date | evidence | | change | owner | measure | |'
class LearningLogTests(unittest.TestCase):
    def test_template_empty_and_prose(self):
        validate_learning_log((Path(__file__).parents[1]/'assets/templates/learning-log.md').read_text(encoding='utf-8'))
        validate_learning_log('Plain text | not a Learn table\n')
    def test_optional_outer_pipes_escaped_pipes_and_empty_cells(self):
        validate_learning_log(HEADER.strip('|')+'\n'+DELIM.strip('|')+'\ndate | text \\| other | | change | owner | measure | outcome\n')
        validate_learning_log(HEADER+'\n'+DELIM+'\n'+ROW+'\n')
    def test_fenced_examples(self):
        for fence in ('```','~~~~'):
            validate_learning_log(fence+'markdown\n'+HEADER+'\n| bad |\n'+fence+'\nprose\n')
    def test_fence_info_suffix_does_not_close_and_heading_ends_table(self):
        for fence in ('```','~~~~'):
            validate_learning_log(fence+'example\n'+fence+'not-a-closing-fence\n'+HEADER+'\n| malformed example |\n'+fence+'\n')
        validate_learning_log(HEADER+'\n'+DELIM+'\n'+ROW+'\n## Outcome | caveats\n')
    def test_standard_prose_blocks_end_table(self):
        for block in ('> Follow-up | owner notes','- Follow-up | owner notes','1. Follow-up | owner notes','<div>Follow-up | owner notes</div>'):
            with self.subTest(block=block): validate_learning_log(HEADER+'\n'+DELIM+'\n'+ROW+'\n'+block+'\n')
    def test_inline_html_does_not_end_table(self):
        for tag in ('span','code'):
            with self.subTest(tag=tag), self.assertRaisesRegex(ValueError,r'learning-log\.md line 3:'):
                validate_learning_log(HEADER+'\n'+DELIM+'\n<'+tag+'>date</'+tag+'> | truncated\n| also | malformed |\n')
    def test_comments_and_indented_examples(self):
        validate_learning_log(HEADER+'\n'+DELIM+'\n'+ROW+'\n<!-- Follow-up | owner notes -->\n')
        validate_learning_log('    '+HEADER+'\n    | malformed |\n')
        validate_learning_log('<!-- example\n'+HEADER+'\n| malformed |\n-->\n')
    def test_wrong_cell_counts(self):
        for row in ('| date | evidence | truncated |','| a | b | c | d | e | f | g | extra |'):
            with self.subTest(row=row), self.assertRaisesRegex(ValueError,r'learning-log\.md line 3:.*expected 7'):
                validate_learning_log(HEADER+'\n'+DELIM+'\n'+row)
    def test_malformed_and_missing_delimiters(self):
        for delimiter in ('|---|---|---|---|---|---|','|---|---|oops|---|---|---|---|','','```'):
            with self.subTest(delimiter=delimiter), self.assertRaisesRegex(ValueError,r'learning-log\.md line 2:'):
                validate_learning_log(HEADER+'\n'+delimiter)
    def test_short_delimiters_and_header_text_in_a_body_row(self):
        validate_learning_log(HEADER+'\n|-|-|-|-|-|-|-|\n'+HEADER+'\n'+ROW+'\n')
    def test_invalid_backtick_info_is_not_a_fence(self):
        with self.assertRaisesRegex(ValueError,r'learning-log\.md line 3:'):
            validate_learning_log('```bad`info\n'+HEADER+'\n| bad |\n')
    def test_separate_tables_and_prose(self):
        validate_learning_log(HEADER+'\n'+DELIM+'\n'+ROW+'\n\nprose with | pipes\n\n'+HEADER+'\n'+DELIM+'\n')

    def test_cell_splitter_preserves_escape_parity_and_single_outer_pipes(self):
        cases = (
            (r'| a | b \|', ['a', r'b \|']),
            (r'| a\\| b | c |', [r'a\\', 'b', 'c']),
            (r'| a\| b | c |', [r'a\| b', 'c']),
            ('||a||', ['', 'a', '']),
            (' a | b ', ['a', 'b']),
        )
        for line, expected in cases:
            with self.subTest(line=line):
                self.assertEqual(learning_cells(line), expected)

    def test_aligned_delimiters_empty_cells_and_inline_html_are_valid(self):
        aligned = '|:---|---:|:---:|-|-|-|-|'
        empty = '| | | | | | | |'
        inline = '<span>date</span> | evidence | | change | owner | measure | outcome'
        validate_learning_log(HEADER+'\n'+aligned+'\n'+empty+'\n'+inline+'\n')

    def test_only_the_exact_generated_header_selects_this_schema(self):
        self.assertEqual(tuple(learning_cells(HEADER)), LEARNING_HEADER)
        validate_learning_log('| Custom notes | Owner |\n|---|---|\n| prose | may | differ |\n')
        # Matching shape cannot establish whether prose was truncated or true.
        validate_learning_log(HEADER+'\n'+DELIM+'\n| date | unfinished senten | | | | | |\n')
        # An ordinary prose line ends the recognized table; intent is not inferred.
        validate_learning_log(HEADER+'\n'+DELIM+'\nA prose follow-up without a pipe\n')

    def test_error_reports_filename_line_and_counts_without_private_cell_content(self):
        body = '# Learn\r\n\r\n'+HEADER+'\r\n'+DELIM+'\r\n'+ROW+'\r\n| PRIVATE-ROW-CONTENT | truncated |\r\n'
        with self.assertRaises(ValueError) as raised:
            validate_learning_log(body)
        self.assertEqual(str(raised.exception), 'learning-log.md line 6: Learn table has 2 cells; expected 7')
        self.assertNotIn('PRIVATE', str(raised.exception))

    def test_delimiter_required_before_comments_and_indented_examples(self):
        for interrupted in ('<!-- explanation -->', '    indented explanation', '\tindented explanation'):
            with self.subTest(interrupted=interrupted), self.assertRaisesRegex(ValueError, 'line 2: missing Learn table delimiter'):
                validate_learning_log(HEADER+'\n'+interrupted+'\n')
        with self.assertRaisesRegex(ValueError, 'line 2: missing Learn table delimiter'):
            validate_learning_log(HEADER)

    def test_fence_lengths_characters_and_valid_closing_are_respected(self):
        # A shorter fence or different fence character cannot expose example rows.
        validate_learning_log('````markdown\n```\n~~~\n'+HEADER+'\n| malformed example |\n````\n')
        # Validation resumes after a real close, with the original line numbering.
        with self.assertRaisesRegex(ValueError, 'line 6: Learn table has 2 cells; expected 7'):
            validate_learning_log('```\nexample\n```\n'+HEADER+'\n'+DELIM+'\n| bad | row |\n')

    def test_isolated_import_has_no_output_or_writes_and_needs_no_neighboring_helpers(self):
        module = Path(__file__).with_name('learning_table.py').read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'learning_table.py').write_bytes(module)
            before = {path.name: path.read_bytes() for path in root.iterdir()}
            result = subprocess.run([
                sys.executable, '-B', '-I', '-c',
                'import sys; sys.path.insert(0, sys.argv[1]); import learning_table', str(root)
            ], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')
            self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)


if __name__ == '__main__':
    unittest.main()
