"""Execute documented examples locally; no provider, watcher or real datastore proof."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import run
from scaffold import ROOT, render


def example(name, language):
    text = (ROOT / 'references' / name).read_text(encoding='utf-8')
    blocks = re.findall(r'```' + language + r'\n(.*?)\n```', text, re.S)
    if len(blocks) != 1:
        raise AssertionError('Expected exactly one executable example block')
    return blocks[0]


def functions(name):
    namespace = {}
    exec(compile(example(name, 'python'), name, 'exec'), namespace)
    return namespace


class IntakeLabelExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.root = self.project / '.software-factory'
        self.runs = self.project / '.factory-runs'
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text(encoding='utf-8'))
        self.research = json.loads((ROOT / 'assets/example-research.json').read_text(encoding='utf-8'))
        self.config['budget']['max_workers'] = 2
        self.config['operations'] = {
            'autonomy': {'mode': 'bounded', 'max_items_per_hour': 2,
                         'allowed_submitters': ['synthetic-owner']},
            'issue_intake': {'mode': 'continuous', 'github_scope': 'SYNTHETIC/example',
                             'status': 'enabled'}}
        self.policy = json.loads(example('intake-label-example.md', 'json'))
        self.propose = functions('intake-label-example.md')['propose_intake']
        self.now = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
        self.stop = patch.dict('os.environ', {'FACTORY_STOP': '0'})
        self.stop.start(); self.addCleanup(self.stop.stop)
        self.write()

    def write(self):
        for name, body in render(self.config, self.research).items():
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding='utf-8')

    def snapshot(self):
        return {str(p.relative_to(self.project)): p.read_bytes()
                for p in self.project.rglob('*') if p.is_file()}

    def issue(self, identity, labels=None, **kwargs):
        return {'id': identity, 'submitter': 'synthetic-owner',
                'created_at': '2026-11-03T00:00:00Z',
                'labels': ['factory:ready'] if labels is None else labels, **kwargs}

    def propose_now(self, issues, verified=True):
        return self.propose(*run.load(self.root), self.runs, issues, self.policy,
                            self.now, snapshot_verified=verified)

    def test_filters_real_selector_and_preserves_all_inputs(self):
        issues = [self.issue('03'), self.issue('01'), self.issue('02'),
                  self.issue('04', ['factory:queued']),
                  self.issue('05', submitter='unapproved'),
                  self.issue('06', depends_on=['unknown']),
                  self.issue('07', ['factory:ready', 'factory:pr-open'])]
        before = self.snapshot(); supplied = copy.deepcopy(issues)
        with patch('subprocess.Popen', side_effect=AssertionError('No process')), \
             patch('socket.create_connection', side_effect=AssertionError('No network')):
            result = self.propose_now(issues)
        self.assertEqual(result['issue_ids'], ['01', '02'])
        self.assertEqual(len(result['selection']['issues']['eligible']), 3)
        self.assertEqual(len(result['selection']['issues']['rejected']), 4)
        self.assertEqual(issues, supplied); self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.runs.exists())

    def test_pause_on_unready_issue_stops_whole_repository(self):
        with patch('run.run_records', side_effect=AssertionError('Must stop before selection')):
            result = self.propose_now([self.issue('01'), self.issue('99', ['factory:paused'])])
        self.assertEqual(result['issue_ids'], [])

    def test_unknown_snapshot_and_malformed_pause_data_fail_closed(self):
        for issues, verified in [([self.issue('01')], False), ([{'id': '01'}], True),
                                 ([self.issue('01', [None])], True),
                                 ([self.issue(str(i)) for i in range(1001)], True)]:
            with self.subTest(size=len(issues), verified=verified), self.assertRaises(ValueError):
                self.propose_now(issues, verified)

    def test_recorded_rate_existing_task_and_stop_are_honored(self):
        self.runs.mkdir()
        record = {'started': self.now.isoformat(), 'dispatched': ['previous']}
        (self.runs / 'run-synthetic.json').write_text(json.dumps(record), encoding='utf-8')
        self.assertEqual(self.propose_now([self.issue('01'), self.issue('02')])['issue_ids'], ['01'])
        self.config['tasks'][0].update(status='pending', allowed_paths=['src/'])
        self.write()
        self.assertEqual(self.propose_now([self.issue('01')])['issue_ids'], [])
        (self.runs / 'STOP').write_text('SYNTHETIC stop', encoding='utf-8')
        self.config['tasks'][0]['status'] = 'blocked'; self.write()
        self.assertEqual(self.propose_now([self.issue('01')])['issue_ids'], [])

    def test_repository_mismatch_duplicates_and_disabled_intake_propose_nothing(self):
        self.policy['repository'] = 'SYNTHETIC/wrong'
        self.assertEqual(self.propose_now([self.issue('01')])['issue_ids'], [])
        self.policy['repository'] = 'SYNTHETIC/example'
        self.assertEqual(self.propose_now([self.issue('01'), self.issue('01')])['issue_ids'], [])
        self.config['operations']['issue_intake']['status'] = 'disabled'; self.write()
        self.assertEqual(self.propose_now([self.issue('01')])['issue_ids'], [])


class MemoryFixtureAdapter:
    """Synthetic atomic ownership comparison; never accesses a real application."""
    def __init__(self, receipts):
        self.rows = {r['id']: dict(r) for r in receipts}
        self.calls = []

    def delete_if_owned(self, receipt):
        self.calls.append(('delete', receipt['id']))
        current = self.rows.get(receipt['id'])
        if current is None:
            return 'absent'
        if current != receipt:
            return 'ownership_mismatch'
        del self.rows[receipt['id']]
        return 'deleted'

    def is_absent(self, receipt):
        self.calls.append(('verify', receipt['id']))
        return receipt['id'] not in self.rows


class DisposableFixtureExampleTests(unittest.TestCase):
    def setUp(self):
        self.cleanup = functions('disposable-fixture-example.md')['teardown_created']
        self.receipts = [{'id': identity, 'target': 'SYNTHETIC disposable target',
                          'run_id': 'fixture-synthetic-attempt-1', 'owner_token': 'synthetic-marker'}
                         for identity in ('child', 'parent')]

    def invoke(self, adapter, receipts=None):
        return self.cleanup(adapter, target=self.receipts[0]['target'],
                            run_id=self.receipts[0]['run_id'],
                            receipts=self.receipts if receipts is None else receipts)

    def test_exact_owned_ids_child_first_readback_and_repeat(self):
        foreign = dict(self.receipts[0], id='unrelated', run_id='another-run')
        adapter = MemoryFixtureAdapter(self.receipts + [foreign])
        before = copy.deepcopy(self.receipts)
        self.assertEqual([r['cleanup'] for r in self.invoke(adapter)], ['CLEANED', 'CLEANED'])
        self.assertEqual(adapter.calls, [('delete', 'child'), ('verify', 'child'),
                                         ('delete', 'parent'), ('verify', 'parent')])
        self.assertEqual(adapter.rows, {'unrelated': foreign})
        self.assertEqual([r['cleanup'] for r in self.invoke(adapter)], ['CLEANED', 'CLEANED'])
        self.assertEqual(self.receipts, before)

    def test_whole_plan_validation_precedes_any_delete(self):
        bad_receipts = [dict(self.receipts[1], run_id='foreign-run'),
                        dict(self.receipts[1], target='wrong-target'),
                        dict(self.receipts[1], owner_token=''),
                        dict(self.receipts[1], extra='unexpected'), self.receipts[0]]
        for bad in bad_receipts:
            adapter = MemoryFixtureAdapter(self.receipts)
            with self.subTest(receipt=bad), self.assertRaises(ValueError):
                self.invoke(adapter, [self.receipts[0], bad])
            self.assertEqual(adapter.calls, [])
            self.assertEqual(len(adapter.rows), 2)

    def test_changed_ownership_stops_before_parent_and_preserves_rows(self):
        adapter = MemoryFixtureAdapter(self.receipts)
        adapter.rows['child']['owner_token'] = 'different-owner'
        self.assertEqual([r['cleanup'] for r in self.invoke(adapter)],
                         ['BLOCKED_OWNERSHIP', 'NOT_ATTEMPTED'])
        self.assertEqual(adapter.calls, [('delete', 'child')]); self.assertEqual(len(adapter.rows), 2)

    def test_delete_or_readback_failure_is_unknown_never_cleaned(self):
        for method in ('delete_if_owned', 'is_absent'):
            adapter = MemoryFixtureAdapter(self.receipts)
            with self.subTest(method=method), patch.object(adapter, method, side_effect=TimeoutError('private detail')):
                result = self.invoke(adapter)
            self.assertEqual([r['cleanup'] for r in result], ['UNKNOWN', 'NOT_ATTEMPTED'])
            self.assertNotIn('private detail', repr(result))
            self.assertIn('parent', adapter.rows)

    def test_false_or_nonboolean_readback_and_unknown_response_do_not_claim_success(self):
        for value in (False, 'true', 1, None):
            with self.subTest(value=value):
                adapter = MemoryFixtureAdapter(self.receipts)
                with patch.object(adapter, 'is_absent', return_value=value):
                    self.assertEqual(self.invoke(adapter)[0]['cleanup'], 'UNKNOWN')
        adapter = MemoryFixtureAdapter(self.receipts)
        with patch.object(adapter, 'delete_if_owned', return_value='accepted'):
            self.assertEqual(self.invoke(adapter)[0]['cleanup'], 'UNKNOWN')
        self.assertEqual(len(adapter.rows), 2)

    def test_assertion_failure_is_preserved_when_teardown_runs(self):
        adapter = MemoryFixtureAdapter(self.receipts)
        observed = []
        with self.assertRaisesRegex(AssertionError, 'original feature failure'):
            try:
                raise AssertionError('original feature failure')
            finally:
                observed.extend(self.invoke(adapter))
        self.assertEqual([r['cleanup'] for r in observed], ['CLEANED', 'CLEANED'])

    def test_empty_list_and_over_limit(self):
        adapter = MemoryFixtureAdapter(self.receipts)
        self.assertEqual(self.invoke(adapter, []), [])  # No claim about unreceipted writes.
        with self.assertRaises(ValueError):
            self.invoke(adapter, self.receipts * 51)
        self.assertEqual(adapter.calls, [])


if __name__ == '__main__':
    unittest.main()
