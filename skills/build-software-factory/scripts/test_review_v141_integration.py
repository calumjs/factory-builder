"""Exact v1.41 adoption and ordinary handoff drift; synthetic factories only."""
import hashlib
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import gates
import review_records as rr
import scoped_assessment
import test_review_consumers as consumers
import test_review_migration as migration
from test_review_records import supplied_round
from scaffold import ROOT
from status import updated
import update_operations as updater


class ReviewV141IntegrationTests(unittest.TestCase):
    def fixture(self):
        fixture=migration.ReviewMigrationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        raw=(ROOT/'scripts/fixtures/pre_review_v141_dashboard.txt').read_bytes()
        fixture.contract('dashboard/dashboard.py',raw)
        return fixture

    def test_actual_v141_complete_consumers_adopt_and_copied_cli_blocks_empty_review(self):
        fixture=self.fixture()
        for name,wanted in updater.PRE_REVIEW_V141_RUNTIME.items():
            self.assertEqual(hashlib.sha256((fixture.root/'dashboard'/name).read_bytes()).hexdigest(),wanted)
        before=fixture.snapshot();prepared=fixture.prepare();self.assertEqual(before,fixture.snapshot())
        for name in ('operations.py','gates.py','dashboard.py','review_records.py','research.py'):
            self.assertIn('dashboard/'+name,prepared[2])
        updater.apply(*prepared,prepared[-1]);self.assertEqual(fixture.prepare()[2],{})
        root=fixture.root
        copied=subprocess.run([sys.executable,'-B',str(root/'dashboard/gates.py'),'--factory',str(root),
                               '--stage','pre-merge','--revision','S1'],capture_output=True,text=True)
        self.assertEqual(copied.returncode,1,copied.stderr);self.assertIn('Q1',copied.stdout)
        for name in ('ui-verification.md','phase-build-guide.md'):
            self.assertEqual(before[name],(root/name).read_bytes())
        self.assertIn(b'ui-verification.md',(root/'phase-verify-guide.md').read_bytes())
        self.assertIn(b'review-guide.md',(root/'phase-verify-guide.md').read_bytes())
        self.assertIn(b'supplemental_html',(root/'dashboard/dashboard.py').read_bytes())

    def test_v141_custom_or_partial_new_consumers_are_refused_write_free(self):
        for name in ('operations.py','gates.py','dashboard.py'):
            with self.subTest(name=name):
                fixture=self.fixture();fixture.contract('dashboard/'+name,(ROOT/'scripts'/name).read_bytes())
                before=fixture.snapshot()
                with self.assertRaisesRegex(ValueError,'mixed'):fixture.prepare()
                self.assertEqual(before,fixture.snapshot())
        fixture=self.fixture();name='dashboard/dashboard.py'
        fixture.contract(name,(fixture.root/name).read_bytes()+b'\n# custom dashboard extension\n')
        before=fixture.snapshot()
        with self.assertRaisesRegex(ValueError,'customized/mixed'):fixture.prepare()
        self.assertEqual(before,fixture.snapshot())

    def test_v141_legacy_context_preserves_until_explicit_runtime_adoption(self):
        fixture=self.fixture();before=(fixture.root/'dashboard/dashboard.py').read_bytes()
        unchanged=updater.prepare(fixture.root,{})
        self.assertNotIn('dashboard/dashboard.py',unchanged[2])
        self.assertEqual(before,(fixture.root/'dashboard/dashboard.py').read_bytes())
        with self.assertRaisesRegex(ValueError,'complete current copied gate backend'):
            updater.prepare(fixture.root,{},context_runtime=True)
        self.assertEqual(before,(fixture.root/'dashboard/dashboard.py').read_bytes())
        plan=updater.prepare(fixture.root,{},context_runtime=True,gate_runtime=True)
        self.assertIn('dashboard/dashboard.py',plan[2])
        self.assertNotIn('dashboard/review_records.py',plan[2])

    def test_direct_and_scoped_recheck_handoff_after_capture_including_optional_q1(self):
        for scoped in (False,True):
            for optional in (False,True):
                with self.subTest(scoped=scoped,optional=optional):
                    fixture=consumers.ReviewConsumerTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
                    fixture.satisfy();root=fixture.root
                    path=root/'task-plan.json';plan=json.loads(path.read_bytes())
                    updated(plan,'T1','done','passed','Synthetic task result','S1','synthetic','synthetic check')
                    path.write_bytes(json.dumps(plan).encode())
                    if optional:
                        path=root/'verification.md';raw=path.read_bytes()
                        lines=[line.replace(b'| yes |',b'| no |') if line.startswith(b'| Q1 |') else line
                               for line in raw.splitlines(keepends=True)]
                        path.write_bytes(b''.join(lines))
                    def assess():
                        return scoped_assessment.assess_scope(root,{'purpose':'Synthetic subset','gates':['A1'],'tasks':['T1']},'pre-merge','S1') if scoped else gates.assess(root,'pre-merge','S1')
                    stable=assess()
                    if scoped:
                        self.assertFalse(stable['problems'])
                        if optional:self.assertTrue(any(value.startswith('Q1 WAIVED') for value in stable['waivers']))
                    else:self.assertEqual(stable,[])
                    actual=rr.read_handoff;calls=0
                    def after_capture(path):
                        nonlocal calls
                        text=actual(path);calls+=1
                        if calls==1:
                            change=supplied_round(fixture.fixture.config,'round2');change['reviews'][0]['verdict']='request_changes'
                            path.write_bytes(rr.append_round(text,change))
                        return text
                    with patch.object(rr,'read_handoff',side_effect=after_capture):
                        with self.assertRaisesRegex(ValueError,'handoff changed'):assess()
                    self.assertEqual(calls,2)


if __name__=='__main__':unittest.main()
