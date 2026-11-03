"""Structural checks for the generated learning-log.md pipe table.

Recognizes the exact generated header, then validates delimiter and row widths.
This is not a general Markdown parser or a check of prose completeness, evidence
truth, or customized table semantics. No files are read or changed by this module.
"""
import re

LEARNING_HEADER = ('Date / task / revision', 'Observed result and evidence', 'Hypothesis',
                   'Proposed change', 'Owner', 'Evaluation measure', 'Approval / outcome')

def learning_cells(line):
    """Split unescaped table delimiters; remove at most one optional outer pipe."""
    text = line.strip()
    cells = []; start = 0; backslashes = 0
    for i, char in enumerate(text):
        if char == '|' and backslashes % 2 == 0:
            cells.append(text[start:i].strip()); start = i + 1
        backslashes = backslashes + 1 if char == '\\' else 0
    cells.append(text[start:].strip())
    if text.startswith('|'): cells.pop(0)
    if text.endswith('|') and len(text) > 1:
        # An escaped final pipe is content, not an outer delimiter.
        n = len(text) - 2
        while n >= 0 and text[n] == '\\': n -= 1
        if (len(text) - 2 - n) % 2 == 0: cells.pop()
    return cells

def validate_learning_log(body):
    """Validate recognized Learn tables only; prose and fenced examples are untouched."""
    lines = body.splitlines(); fence = None; comment = False; state = 'outside'; columns = 0
    for number, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if comment:
            if '-->' in line: comment = False
            continue
        if fence is None and line.startswith(('    ', '\t')):
            if state == 'delimiter': raise ValueError(f'learning-log.md line {number}: missing Learn table delimiter')
            state = 'outside'; continue
        if fence is None and re.match(r'^ {0,3}<!--', line):
            if state == 'delimiter': raise ValueError(f'learning-log.md line {number}: missing Learn table delimiter')
            comment = '-->' not in line; state = 'outside'; continue
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is not None:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence) and not match.group(2).strip():
                fence = None
            continue
        if match and (match.group(1)[0] != '`' or '`' not in match.group(2)):
            if state == 'delimiter':
                raise ValueError(f'learning-log.md line {number}: missing Learn table delimiter')
            fence = match.group(1); state = 'outside'; continue
        if state == 'rows' and re.match(r'^ {0,3}(?:#{1,6}(?:\s|$)|>|[-+*]\s|\d{1,9}[.)]\s|</?(?:script|pre|style|textarea|address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:\s|/?>))', line, re.IGNORECASE):
            state = 'outside'; continue
        cells = learning_cells(line)
        if state == 'outside' and tuple(cells) == LEARNING_HEADER:
            state = 'delimiter'; columns = len(cells); continue
        if state == 'delimiter':
            if len(cells) != columns or not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                raise ValueError(f'learning-log.md line {number}: malformed Learn table delimiter; expected {columns} columns')
            state = 'rows'; continue
        if state == 'rows':
            if not stripped or '|' not in line:
                state = 'outside'; continue
            if len(cells) != columns:
                raise ValueError(f'learning-log.md line {number}: Learn table has {len(cells)} cells; expected {columns}')
    if state == 'delimiter':
        raise ValueError(f'learning-log.md line {len(lines)+1}: missing Learn table delimiter')
