"""Same review consistency across explicit dashboard, scoped and local CI readers."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
import review_records as rr
from unittest.mock import patch

import dashboard
from ci_evidence import assess_ci
from scoped_assessment import assess_scope
import test_review_records as fixtures
from test_review_records import supplied_round
from status import updated


class ReviewConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ReviewFactoryTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.selection={'subject':'S1','stage':'pre-merge','actual_target':None,'reason':'Synthetic supplied subject assessment'}
    def satisfy(self,subject='S1',waived=False):
        item=supplied_round(self.fixture.config,subject=subject)
        if waived:item['inversion'].update(choice='waived',reason='Explicit operator choice after provider unavailable')
        self.fixture.record('review',item);self.fixture.record('gate',self.fixture.observation(item))
    def test_dashboard_default_inputs_unchanged_and_explicit_review_is_consumed(self):
        plain=dashboard.read(self.root);self.assertNotIn('assessment',plain)
        self.assertEqual([row['artifact'] for row in plain['sources']],list(dashboard.INPUTS))
        blocked=dashboard.read(self.root,assessment=self.selection);self.assertEqual(blocked['assessment']['state'],'blocked')
        self.assertIn('release-handoff.md',[row['artifact'] for row in blocked['sources']])
        self.satisfy();ready=dashboard.read(self.root,assessment=self.selection);self.assertEqual(ready['assessment']['state'],'satisfied')
        stale=dashboard.read(self.root,assessment={**self.selection,'subject':'S2'});self.assertEqual(stale['assessment']['state'],'blocked')
    def test_dashboard_rechecks_handoff_bytes_after_gate_assessment(self):
        self.satisfy();real=dashboard.assess_gates
        def racing(*args,**kwargs):
            result=real(*args,**kwargs);path=self.root/'release-handoff.md';path.write_bytes(path.read_bytes()+b'\nconcurrent supplied edit\n');return result
        with patch.object(dashboard,'assess_gates',side_effect=racing):
            with self.assertRaisesRegex(ValueError,'changed while reading'):dashboard.read(self.root,assessment=self.selection)
    def test_scoped_assessment_adds_q1_without_requiring_unrelated_project_gates(self):
        path=self.root/'task-plan.json';plan=json.loads(path.read_bytes())
        updated(plan,'T1','done','passed','Synthetic task observation','S1','synthetic','synthetic check');path.write_text(json.dumps(plan))
        scope={'purpose':'Synthetic selected task','gates':['A1'],'tasks':['T1']}
        blocked=assess_scope(self.root,scope,'pre-merge','S1');self.assertTrue(any('Q1' in value for value in blocked['problems']))
        self.assertIn('Q1',[row['gate'] for row in blocked['selected_records']]);self.satisfy()
        selected=assess_scope(self.root,scope,'pre-merge','S1');self.assertFalse(selected['problems'])
        self.assertTrue(any(row['gate']=='G3' for row in selected['out_of_scope']))
    def test_copied_dashboard_cli_rejects_stale_same_as_installed(self):
        self.satisfy();target=self.root.parent/'overview.json'
        args=[sys.executable,'-B',str(self.root/'dashboard/dashboard.py'),'--factory',str(self.root),'--output',str(target),'--format','json',
              '--assessment-subject','S2','--assessment-stage','pre-merge','--assessment-reason','Synthetic stale probe']
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(target.read_text())['assessment']['state'],'blocked')
    def test_optional_inversion_waiver_is_visible_in_gate_dashboard_and_scope_outputs(self):
        self.satisfy(waived=True)
        result=dashboard.read(self.root,assessment=self.selection)
        self.assertIn({'id':'Q1/inversion','recorded_result':'WAIVED'},result['assessment']['waived'])
        scoped=assess_scope(self.root,{'purpose':'Synthetic subset','gates':['A1'],'tasks':['T1']},'pre-merge','S1')
        self.assertTrue(any('inversion WAIVED' in value for value in scoped['waivers']))
        command=[sys.executable,'-B',str(self.root/'dashboard/gates.py'),'--factory',str(self.root),'--stage','pre-merge','--revision','S1']
        cli=subprocess.run(command,capture_output=True,text=True);self.assertEqual(cli.returncode,0,cli.stderr)
        self.assertIn('inversion WAIVED',cli.stdout)
    def test_actual_local_ci_adapter_uses_handoff_and_exact_subject_storage_binding(self):
        repo=self.root.parent;hooks=repo/'empty-hooks';hooks.mkdir()
        def git(*args):
            result=subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+str(hooks),'-c','user.name=Synthetic review fixture',
                                   '-c','user.email=fixture@example.invalid','-C',str(repo),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
        def commit():git('add','--all');git('commit','-qm','Synthetic supplied review fixture');return git('rev-parse','HEAD')
        prior=supplied_round(self.fixture.config,'round0','PRIOR-SUBJECT')
        self.fixture.record('review',prior);self.fixture.record('gate',self.fixture.observation(prior))
        git('init','-q');subject=commit()
        self.assertEqual(assess_ci(repo,'factory',subject,subject,'pre-merge')['assessment'],'blocked')
        self.satisfy(subject);storage=commit();before=git('status','--porcelain')
        ready=assess_ci(repo,'factory',subject,storage,'pre-merge');self.assertEqual(ready['assessment'],'eligible_with_waivers')
        self.assertEqual(before,git('status','--porcelain'))
        item=supplied_round(self.fixture.config,'round2',subject);item['inversion'].update(choice='waived',reason='Explicit unavailable-provider waiver')
        self.fixture.record('review',item);self.fixture.record('gate',self.fixture.observation(item));waived_storage=commit()
        self.assertTrue(any('inversion WAIVED' in value for value in assess_ci(repo,'factory',subject,waived_storage,'pre-merge')['waivers']))
        item=supplied_round(self.fixture.config,'round3',subject);item['reviews'][0]['verdict']='request_changes'
        self.fixture.record('review',item);failed_storage=commit()
        failed=assess_ci(repo,'factory',subject,failed_storage,'pre-merge');self.assertEqual(failed['assessment'],'blocked')
        self.assertTrue(any('Q1' in value for value in failed['problems']))
        path=self.root/'release-handoff.md';body=path.read_text();record=rr.parse(body);record['rounds'].pop(0)
        start=body.index(rr.START);end=body.index(rr.END)+len(rr.END);path.write_bytes((body[:start]+rr.section(record)+body[end:]).encode('utf-8'))
        dropped=commit()
        with self.assertRaisesRegex(ValueError,'preserve prior review'):assess_ci(repo,'factory',subject,dropped,'pre-merge')


if __name__=='__main__':unittest.main()
