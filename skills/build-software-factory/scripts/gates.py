#!/usr/bin/env python3
"""Check recorded delivery-gate results in verification.md; never runs the checks themselves.

Exit 0 only when every required gate for the stage is PASSED for the exact revision.
NOT RUN, BLOCKED, FAILED, a missing gate or a different revision all block.
"""
import argparse
from pathlib import Path
import re
import sys
from integrity import safe_path

STAGES = ('pre-merge', 'post-merge')
ROW = re.compile(r'^\|\s*(G\d+)\s*\|')

def gate_rows(text):
    rows = []
    for line in text.replace('\r\n', '\n').split('\n'):
        if ROW.match(line):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) < 8:
                raise ValueError('Malformed gate row: ' + cells[0])
            rows.append({'gate': cells[0], 'stage': cells[1].lower(), 'check': cells[2], 'required': cells[4].lower(),
                         'revision': cells[5], 'result': cells[6].upper(), 'evidence': cells[7]})
    return rows

def problems(text, stage, revision):
    if stage not in STAGES:
        raise ValueError('Unknown stage')
    if not revision or not revision.strip():
        raise ValueError('Revision is required')
    rows = [r for r in gate_rows(text) if r['stage'] == stage]
    if not rows:
        return ['No ' + stage + ' gates recorded; gates cannot be dropped silently']
    out = []
    for r in rows:
        if r['required'] in ('no', 'n', 'false'):
            continue
        if r['result'] != 'PASSED':
            out.append(f"{r['gate']} is {r['result'] or 'NOT RUN'}")
        elif r['revision'] != revision.strip():
            out.append(f"{r['gate']} passed for revision {r['revision'] or '(none)'}, not {revision.strip()}")
        elif not r['evidence']:
            out.append(f"{r['gate']} has no evidence")
    return out

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--factory', required=True); p.add_argument('--stage', required=True, choices=STAGES)
    p.add_argument('--revision', required=True)
    a = p.parse_args()
    text = (safe_path(a.factory)/'verification.md').read_text(encoding='utf-8-sig')
    found = problems(text, a.stage, a.revision)
    if found:
        print('BLOCKED: ' + a.stage + ' gates not satisfied for ' + a.revision)
        for x in found: print('  - ' + x)
        sys.exit(1)
    print('PASSED: recorded ' + a.stage + ' gates satisfied for ' + a.revision + ' (records only; this helper ran no checks)')

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr); sys.exit(2)
