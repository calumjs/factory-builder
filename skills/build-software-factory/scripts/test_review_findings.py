"""Independent-review regressions: retained claims, checkers and exact byte writes."""
import contextlib
import copy
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

import dashboard
import gates
import review_records as rr
import scoped_assessment
from ci_evidence import assess_ci
from incremental_records import preview,apply
from operations import operations
import test_review_consumers as consumer_fixture
from test_review_records import configuration,supplied_round


class ReviewFindingTests(unittest.TestCase):
    def setUp(self):
        self.config=configuration();self.old=supplied_round(self.config)
        self.old['reviews'][0]['verdict']='request_changes'
        self.old['reviews'][0]['findings']=[{'id':'F1','severity':'major','claim':'Synthetic unresolved source concern','evidence':'synthetic source','verification':None}]
        self.body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[self.old]})
    def resolution(self,reviewer='separate-checker'):
        return {'round_id':'round1','review_id':'review1','finding_id':'F1','reviewer':reviewer,
                'disposition':'refuted','evidence':'Synthetic independent source check','reason':'Synthetic claim contradicted by the bounded reproducer'}
    def assess(self,new,body=None,independent=True):
        policy={**operations(self.config)['review'],'independent':independent}
        return rr.assessment(rr.append_round(body or self.body,new).decode(),policy,new['policy_sha256'],new['subject'])

    def test_same_subject_different_base_or_artifact_cannot_hide_unresolved_claim(self):
        for different_artifact in (False,True):
            new=supplied_round(self.config,'round2');new['base']='B2';new['reviews'][0]['base']='B2'
            if different_artifact:new['artifact']['sha256']='b'*64;new['reviews'][0]['artifact_sha256']='b'*64
            self.assertTrue(self.assess(new))
            new['resolutions']=[self.resolution()];self.assertEqual(self.assess(new),[])

    def test_same_artifact_carries_claims_without_inventing_prefix_equivalence(self):
        old=copy.deepcopy(self.old);old['subject']='abc1234';old['reviews'][0]['subject']=old['subject']
        body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[old]})
        new=supplied_round(self.config,'round2','abc1234'+'0'*33)
        self.assertTrue(self.assess(new,body))
        new['resolutions']=[self.resolution()];self.assertEqual(self.assess(new,body),[])
        new['resolutions']=[];new['artifact']['sha256']='b'*64;new['reviews'][0]['artifact_sha256']='b'*64
        self.assertEqual(self.assess(new,body),[])
        summary=rr.history_summary(rr.parse(rr.append_round(body,new).decode()))
        self.assertEqual(summary['unresolved_other_subject_and_artifact'],1)

    def test_builder_resolution_does_not_close_under_independent_policy_but_can_be_rechecked(self):
        new=supplied_round(self.config,'round2');new['resolutions']=[self.resolution('builder')]
        self.assertTrue(self.assess(new))
        self.assertEqual(self.assess(new,independent=False),[])
        body=rr.append_round(self.body,new).decode();later=supplied_round(self.config,'round3')
        later['resolutions']=[self.resolution()]
        self.assertEqual(self.assess(later,body),[])
        self.assertEqual(rr.parse(rr.append_round(body,later).decode())['rounds'][1],new)

    def test_builder_inline_verification_does_not_close_under_independent_policy(self):
        new=supplied_round(self.config,'round2');new['reviews'][0]['findings']=copy.deepcopy(self.old['reviews'][0]['findings'])
        new['reviews'][0]['findings'][0]['verification']={key:value for key,value in self.resolution('builder').items() if key in ('reviewer','disposition','evidence','reason')}
        body=rr.section(rr.empty());self.assertTrue(self.assess(new,body));self.assertEqual(self.assess(new,body,False),[])
        supplied=rr.append_round(body,new).decode();later=supplied_round(self.config,'round3')
        reference=self.resolution();reference['round_id']='round2';later['resolutions']=[reference]
        self.assertEqual(self.assess(later,supplied),[])

    def test_unknown_original_or_closing_builder_cannot_prove_independent_closure(self):
        for unknown_original in (False,True):
            old=copy.deepcopy(self.old);new=supplied_round(self.config,'round2');new['resolutions']=[self.resolution()]
            (old if unknown_original else new)['builder']['identity']=None
            body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[old]})
            record=rr.parse(rr.append_round(body,new).decode())
            self.assertEqual(rr.history_summary(record,True)['unresolved_selected_scope'],1)
            self.assertEqual(rr.history_summary(record,False)['unresolved_selected_scope'],0)

    def test_confirmed_or_unconfirmed_recheck_reopens_unqualified_builder_closure(self):
        new=supplied_round(self.config,'round2');new['resolutions']=[self.resolution('builder')]
        body=rr.append_round(self.body,new).decode()
        for disposition in ('confirmed','unconfirmed'):
            later=supplied_round(self.config,'round3');reference=self.resolution();reference['disposition']=disposition;later['resolutions']=[reference]
            self.assertTrue(self.assess(later,body,False));self.assertTrue(self.assess(later,body,True))

    def test_punctuation_only_resolution_evidence_or_reason_is_not_concrete(self):
        for field in ('evidence','reason'):
            new=supplied_round(self.config,'round2');reference=self.resolution();reference[field]='...';new['resolutions']=[reference]
            self.assertTrue(self.assess(new))

    def test_new_complete_verdict_retains_prior_nonmajor_verdict_without_claiming_consensus(self):
        old=copy.deepcopy(self.old);old['reviews'][0]['findings']=[]
        body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[old]})
        new=supplied_round(self.config,'round2');new['applicability_reason']='Explicit escalation retained the earlier verdict; this is a new supplied review, not consensus'
        self.assertEqual(self.assess(new,body),[])
        self.assertEqual(rr.parse(rr.append_round(body,new).decode())['rounds'][0],old)

    def test_future_timestamp_is_malformed_even_when_q1_optional(self):
        new=supplied_round(self.config);body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[new]})
        body=body.replace(new['reviews'][0]['observed_at'],'2999-01-01T00:00:00Z')
        with self.assertRaisesRegex(ValueError,'future'):
            rr.assessment(body,operations(self.config)['review'],new['policy_sha256'],'S1',required=False)


class ReviewByteAndConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=consumer_fixture.ReviewConsumerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root
    def test_gate_writer_cannot_pass_changed_base_over_prior_major(self):
        config=self.fixture.fixture.config;old=supplied_round(config)
        old['reviews'][0]['verdict']='request_changes'
        old['reviews'][0]['findings']=[{'id':'F1','severity':'major','claim':'Synthetic persisted concern','evidence':'synthetic source','verification':None}]
        self.fixture.fixture.record('review',old)
        new=supplied_round(config,'round2');new['base']='different-base';new['reviews'][0]['base']='different-base'
        self.fixture.fixture.record('review',new)
        with self.assertRaisesRegex(ValueError,'Critical/Major'):
            preview(self.root,'gate',self.fixture.fixture.observation(new))
        self.assertTrue(any('Critical/Major' in value for value in gates.assess(self.root,'pre-merge','S1')))
    def test_review_append_preserves_bom_and_exact_prefix_suffix_outside_section(self):
        path=self.root/'release-handoff.md'
        raw=b'\xef\xbb\xbf'+path.read_bytes().replace(b'\n',b'\r\n')+b'\r\nCustom outside-section footer.\r\n'
        path.write_bytes(raw);before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        item=supplied_round(self.fixture.fixture.config);prepared=preview(self.root,'review',item);after=prepared[3]
        for marker,side in ((rr.START.encode(),0),(rr.END.encode(),1)):
            self.assertEqual(raw.split(marker)[side],after.split(marker)[side])
        self.assertEqual(path.read_bytes(),raw);self.assertEqual(before,prepared[2]);apply(*prepared,prepared[-1])
        self.assertEqual(path.read_bytes(),after);self.assertTrue(after.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(rr.parse(after.decode('utf-8-sig'))['rounds'],[item])

    def malformed(self):
        self.fixture.satisfy(waived=True);path=self.root/'release-handoff.md'
        path.write_bytes(path.read_bytes().replace(b'"schema_version": 1',b'"schema_version": 99'))

    def test_malformed_ledger_is_reported_blocked_without_fabricated_waiver(self):
        self.malformed()
        self.assertTrue(any('malformed' in value for value in gates.assess(self.root,'pre-merge','S1')))
        data=dashboard.read(self.root,assessment=self.fixture.selection)
        self.assertEqual(data['assessment']['state'],'blocked');self.assertNotIn({'id':'Q1/inversion','recorded_result':'WAIVED'},data['assessment']['waived'])
        scoped=scoped_assessment.assess_scope(self.root,{'purpose':'Synthetic scope','gates':['A1'],'tasks':['T1']},'pre-merge','S1')
        self.assertEqual(scoped['assessment'],'SCOPED BLOCKED');self.assertFalse(any('inversion WAIVED' in value for value in scoped['waivers']))
        result=subprocess.run([sys.executable,'-B',str(self.root/'dashboard/gates.py'),'--factory',str(self.root),'--stage','pre-merge','--revision','S1'],capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stderr);self.assertIn('malformed',result.stdout);self.assertNotIn('inversion WAIVED',result.stdout)

    def test_cli_rechecks_handoff_between_assessment_and_waiver_output(self):
        self.fixture.satisfy();real=gates.waivers_for_factory
        def changed(*args):
            result=real(*args);path=self.root/'release-handoff.md';item=supplied_round(self.fixture.fixture.config,'round2');item['reviews'][0]['verdict']='request_changes'
            path.write_bytes(rr.append_round_bytes(path.read_bytes(),item));return result
        output=io.StringIO()
        with patch.object(sys,'argv',['gates.py','--factory',str(self.root),'--stage','pre-merge','--revision','S1']),patch.object(gates,'waivers_for_factory',side_effect=changed),contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError,'handoff changed'):gates.main()
        self.assertEqual(output.getvalue(),'')

    def test_ci_malformed_current_snapshot_is_blocked_without_waiver_crash(self):
        self.malformed();repo=self.root.parent;hooks=repo/'empty-hooks';hooks.mkdir()
        def git(*args):
            result=subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+str(hooks),'-c','user.name=Synthetic fixture',
                                   '-c','user.email=fixture@example.invalid','-C',str(repo),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
        git('init','-q');git('add','--all');git('commit','-qm','Synthetic malformed supplied ledger');subject=git('rev-parse','HEAD')
        data=assess_ci(repo,'factory',subject,subject,'pre-merge')
        self.assertEqual(data['assessment'],'blocked');self.assertTrue(any('malformed' in value for value in data['problems']))
        self.assertFalse(any('inversion WAIVED' in value for value in data['waivers']))


if __name__=='__main__':unittest.main()
