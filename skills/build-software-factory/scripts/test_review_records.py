"""Supplied-review consistency and synthetic factory integration; no provider calls."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gates import assess, gate_rows, initial_table, problems, requirements, waivers
from incremental_records import apply, gate_change, preview
from operations import controls, operations
from scaffold import ROOT, render
import review_records as rr


def configuration(count=1):
    config=json.loads((ROOT/'assets/example-config.json').read_text())
    config['operations']={'review':{'record_schema':1,'required_approvals':count,'independent':True},'smoke_gates':{'required':False}}
    return config


def supplied_round(config=None,ident='round1',subject='S1',research=None):
    config=config or configuration()
    research=research or json.loads((ROOT/'assets/example-research.json').read_text())
    item={'id':ident,'subject':subject,'base':'B1','policy_sha256':rr.policy_digest(controls(config),config['budget'],config['acceptance'],research),
          'artifact':{'kind':'source_diff','sha256':'a'*64,'reference':'synthetic approved diff'},'risk':'medium',
          'builder':{'identity':'builder','provider':'provider-one','model_family':'family-one'},
          'required_lenses':['spec','standards','correctness'],'applicability_reason':'Synthetic logic-only scope; security and architecture not applicable',
          'inversion':{'choice':'not_selected','reason':'Explicit single-review choice','decided_by':'operator'},'reviews':[],'resolutions':[]}
    item['reviews']=[{'id':'review1','reviewer':'reviewer-one','role':'primary','subject':subject,'base':'B1','artifact_sha256':'a'*64,
                      'provider':'provider-one','model_family':'family-one','independent':True,'inputs':'source_only','verdict':'approve',
                      'observed_at':'2026-01-01T12:00:00Z','evidence':'synthetic reviewer report','lenses':['spec','standards','correctness'],'findings':[]}]
    return item


class ReviewParserTests(unittest.TestCase):
    def setUp(self):self.config=configuration();self.item=supplied_round(self.config)
    def body(self,item=None):return rr.initialize('# synthetic handoff\n') if item is False else rr.append_round(rr.initialize('# synthetic handoff\n'),item or self.item).decode()
    def assess(self,item=None,policy=None,subject='S1',required=True):
        return rr.assessment(self.body(item),policy or operations(self.config)['review'],self.item['policy_sha256'],subject,required=required)
    def inverse(self):
        item=copy.deepcopy(self.item);item['inversion']['choice']='selected'
        item['reviews'].append(dict(copy.deepcopy(item['reviews'][0]),id='review2',reviewer='reviewer-two',role='inversion',model_family='family-two'))
        return item

    def test_approve_exact_claim_and_stale_policy_subject_are_distinct(self):
        self.assertEqual(self.assess(),[]);self.assertTrue(self.assess(subject='S2'))
        item=copy.deepcopy(self.item);item['policy_sha256']='b'*64
        self.assertTrue(self.assess(item))
        self.assertIn('review:round1:',rr.record_token(rr.parse(self.body())))

    def test_no_vacuous_zero_approval_and_wellformed_optional_waiver(self):
        body=self.body(False);policy={**operations(self.config)['review'],'required_approvals':0}
        self.assertTrue(rr.assessment(body,policy,self.item['policy_sha256'],'S1'))
        self.assertEqual(rr.assessment(body,policy,self.item['policy_sha256'],'S1',required=False),[])
        with self.assertRaises(ValueError):rr.assessment('missing section',policy,self.item['policy_sha256'],'S1',required=False)

    def test_inversion_compares_builder_family_not_primary_or_provider(self):
        item=self.inverse();self.assertEqual(self.assess(item),[])
        item['reviews'][0]['model_family']='family-two';self.assertEqual(self.assess(item),[])
        item['reviews'][1]['provider']='provider-two';item['reviews'][1]['model_family']='family-one'
        self.assertTrue(any('family' in x for x in self.assess(item)))
        for unknown in (None,'unknown','unconfirmed'):
            item['reviews'][1]['model_family']=unknown;self.assertTrue(self.assess(item))

    def test_provider_and_independence_requirements_do_not_alias_family(self):
        item=self.inverse();policy={**operations(self.config)['review'],'required_approvals':2,'distinct_providers':True}
        self.assertTrue(any('provider' in x for x in self.assess(item,policy)))
        item['reviews'][1]['provider']='provider-two';self.assertEqual(self.assess(item,policy),[])
        item['reviews'][1]['inputs']='shared_context';self.assertTrue(self.assess(item,policy))
        item['reviews'][1]['inputs']='source_only';item['builder']['identity']=None;self.assertTrue(self.assess(item,policy))

    def test_pair_verdict_table_and_no_automatic_unavailable_waiver(self):
        for first,second,fragment in (('approve','request_changes','disagreement'),('request_changes','request_changes','return to Build'),('approve','blocked','blocked')):
            item=self.inverse();item['reviews'][0]['verdict']=first;item['reviews'][1]['verdict']=second
            self.assertTrue(any(fragment in x for x in self.assess(item)))
        item=self.inverse();item['reviews'].pop();self.assertTrue(any('no second' in x for x in self.assess(item)))
        item['inversion'].update(choice='waived',reason='Provider unavailable; operator explicitly waived supplement')
        self.assertEqual(self.assess(item),[])
        self.assertTrue(self.assess(item,{**operations(self.config)['review'],'required_approvals':2}))

    def test_unconfirmed_major_never_downgrades_itself_to_approve(self):
        item=copy.deepcopy(self.item);finding={'id':'F1','severity':'major','claim':'Synthetic failing branch','evidence':'synthetic source reference','verification':None}
        item['reviews'][0]['findings']=[finding];self.assertTrue(self.assess(item))
        for disposition in ('confirmed','unconfirmed'):
            finding['verification']={'reviewer':'checker','disposition':disposition,'evidence':'synthetic check','reason':'synthetic reason'}
            self.assertTrue(self.assess(item))
        finding['verification']['disposition']='refuted';self.assertEqual(self.assess(item),[])
        finding['verification']['reason']='unknown';self.assertTrue(self.assess(item))
        finding['verification']['reason']='Concrete synthetic check explanation'
        finding['verification']['evidence']='unconfirmed';self.assertTrue(self.assess(item))
        finding['verification']['reviewer']='reviewer-one'
        with self.assertRaises(ValueError):self.body(item)

    def test_duplicate_identity_lenses_do_not_inflate_approvals(self):
        item=self.inverse();item['reviews'][1]['reviewer']='REVIEWER-ONE'
        with self.assertRaises(ValueError):self.body(item)
        policy={**operations(self.config)['review'],'required_approvals':2}
        self.assertTrue(self.assess(policy=policy))

    def test_artifact_subject_base_and_lenses_are_exact(self):
        for key,value in (('subject','other'),('base','other'),('artifact_sha256','b'*64)):
            item=copy.deepcopy(self.item);item['reviews'][0][key]=value
            with self.assertRaises(ValueError):self.body(item)
        item=copy.deepcopy(self.item);item['required_lenses'].append('security');self.assertTrue(self.assess(item))

    def test_schema_and_timestamp_negatives_preserve_private_values(self):
        for stamp in ('2026-02-30T12:00:00Z','2026-01-01T12:00:00','2999-01-01T00:00:00Z'):
            item=copy.deepcopy(self.item);item['reviews'][0]['observed_at']=stamp
            with self.assertRaises(ValueError):self.body(item)
        good=self.body()
        for bad in (good+good,good.replace('"schema_version": 1','"schema_version": 1,"schema_version": 1'),good.replace('"schema_version": 1','"schema_version": NaN'),good+'\n<<<<<<<< conflict\n','```text\n'+good+'\n```'):
            with self.assertRaises(ValueError):rr.parse(bad)

    def test_history_is_immutable_and_old_approve_cannot_be_reselected(self):
        first=self.body();second=supplied_round(self.config,'round2','S2');second['reviews'][0]['verdict']='request_changes'
        appended=rr.append_round(first,second).decode();record=rr.parse(appended)
        self.assertEqual(record['rounds'][0],self.item);self.assertEqual(record['rounds'][1],second)
        record['selected_round']='round1'
        with self.assertRaises(ValueError):rr.section(record)
        with self.assertRaises(ValueError):rr.append_round(first,self.item)
        with patch.object(rr,'MAX_ROUNDS',1):
            with self.assertRaises(ValueError):rr.append_round(first,second)

    def test_scope_digest_changes_for_acceptance_and_research_not_json_formatting(self):
        import test_research
        fixture=test_research.ResearchTests();fixture.setUp();research=fixture.r
        def calculated(acceptance,research):return rr.policy_digest(controls(self.config),self.config['budget'],acceptance,research)
        original=calculated(self.config['acceptance'],research)
        self.assertEqual(original,calculated(self.config['acceptance'],json.loads(json.dumps(research,indent=4,sort_keys=True))))
        self.assertNotEqual(original,calculated(['Changed acceptance'],research))
        reordered=copy.deepcopy(research);reordered['practices'].reverse();self.assertNotEqual(original,calculated(self.config['acceptance'],reordered))
        changed=copy.deepcopy(research);changed['practices'][0]['check']='Changed synthetic check';self.assertNotEqual(original,calculated(self.config['acceptance'],changed))
        changed=copy.deepcopy(research);changed['summary']='Different supplied metadata';self.assertNotEqual(original,calculated(self.config['acceptance'],changed))
        body=self.body();self.assertTrue(rr.assessment(body,operations(self.config)['review'],original,'S1'))

    def test_schema_bounds_and_nonfinite_duplicate_metadata_are_refused(self):
        for mutation in (lambda value:value.update(extra='private-sentinel'),
                         lambda value:value['reviews'][0].update(independent='true'),
                         lambda value:value['reviews'][0].update(model_family=[]),
                         lambda value:value['reviews'][0].update(evidence='x'*2001),
                         lambda value:value.update(reviews=value['reviews']*17)):
            item=copy.deepcopy(self.item);mutation(item)
            with self.assertRaises(ValueError):self.body(item)
        for value in (True,2,'1'):
            config=configuration();config['operations']['review']['record_schema']=value
            with self.assertRaises(ValueError):operations(config)
        with patch.object(rr,'MAX_SECTION',32):
            with self.assertRaises(ValueError):self.body()

    def test_same_subject_unresolved_finding_cannot_disappear_in_new_approve_round(self):
        original=copy.deepcopy(self.item);original['reviews'][0]['verdict']='request_changes'
        original['reviews'][0]['findings']=[{'id':'F1','severity':'major','claim':'Synthetic original claim','evidence':'synthetic source','verification':None}]
        body=self.body(original);following=supplied_round(self.config,'round2')
        omitted=rr.append_round(body,following).decode()
        self.assertTrue(rr.assessment(omitted,operations(self.config)['review'],original['policy_sha256'],'S1'))
        reference={'round_id':'round1','review_id':'review1','finding_id':'F1','reviewer':'separate-checker',
                   'disposition':'resolved','evidence':'synthetic independent reproduction','reason':'Actual source check supplied'}
        following['resolutions']=[reference];resolved=rr.append_round(body,following).decode()
        self.assertEqual(rr.assessment(resolved,operations(self.config)['review'],original['policy_sha256'],'S1'),[])
        self.assertEqual(rr.parse(resolved)['rounds'][0],original)
        later=supplied_round(self.config,'round3');later['resolutions']=[reference]
        with self.assertRaisesRegex(ValueError,'stale resolution'):rr.append_round(resolved,later)
        for change in ({'round_id':'missing'},{'review_id':'missing'},{'finding_id':'missing'},{'reviewer':'reviewer-one'}):
            bad=copy.deepcopy(following);bad['resolutions'][0].update(change)
            with self.assertRaises(ValueError):rr.append_round(body,bad)
        duplicate=copy.deepcopy(following);duplicate['resolutions']*=2
        with self.assertRaises(ValueError):rr.append_round(body,duplicate)
        for disposition in ('confirmed','unconfirmed'):
            pending=copy.deepcopy(following);pending['resolutions'][0]['disposition']=disposition
            self.assertTrue(rr.assessment(rr.append_round(body,pending).decode(),operations(self.config)['review'],original['policy_sha256'],'S1'))
        for field in ('reviewer','evidence','reason'):
            pending=copy.deepcopy(following);pending['resolutions'][0][field]='unknown'
            self.assertTrue(rr.assessment(rr.append_round(body,pending).decode(),operations(self.config)['review'],original['policy_sha256'],'S1'))

    def test_unrelated_subject_findings_remain_visibly_historical_not_claimed_repaired(self):
        original=copy.deepcopy(self.item)
        original['reviews'][0]['findings']=[{'id':'F1','severity':'critical','claim':'Prior subject concern','evidence':'synthetic source','verification':None}]
        body=self.body(original);new=supplied_round(self.config,'round2','S2')
        new['artifact']['sha256']='b'*64;new['reviews'][0]['artifact_sha256']='b'*64
        following=rr.append_round(body,new).decode()
        self.assertEqual(rr.assessment(following,operations(self.config)['review'],original['policy_sha256'],'S2'),[])
        summary=rr.history_summary(rr.parse(following));self.assertEqual(summary['unresolved_other_subject_and_artifact'],1)
        self.assertIn('does not assert their repair',summary['notice']);self.assertEqual(rr.parse(following)['rounds'][0],original)
        new['resolutions']=[{'round_id':'round1','review_id':'review1','finding_id':'F1','reviewer':'checker',
                            'disposition':'resolved','evidence':'synthetic','reason':'synthetic'}]
        with self.assertRaisesRegex(ValueError,'unrelated subject/artifact'):rr.append_round(body,new)


class ReviewFactoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'factory'
        self.config=configuration();self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(self.config,self.research)
        for name,body in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        self.waive_others()
    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def waive_others(self):
        path=self.root/'verification.md';lines=path.read_text().splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| ') and line.split('|')[1].strip() not in ('Q1','Gate'):
                cells=line.split('|');cells[5]=' no ';lines[i]='|'.join(cells)
        path.write_bytes(('\n'.join(lines)+'\n').encode())
    def record(self,kind,value):
        prepared=preview(self.root,kind,value);apply(*prepared,prepared[-1]);return prepared
    def observation(self,item=None):
        item=item or supplied_round(self.config)
        record=rr.parse((self.root/'release-handoff.md').read_text())
        if record['selected_round']!=item['id']:record={**record,'selected_round':item['id'],'rounds':record['rounds']+[item]}
        return {'gate':'Q1','result':'PASSED','revision':item['subject'],'environment':'synthetic review','evidence':rr.record_token(record),
                'target':'sha256:'+item['artifact']['sha256'],'checked_at':'2026-01-01T12:01:00Z','exit_status':'manual'}
    def test_fresh_optin_blocks_then_two_explicit_single_record_steps_satisfy(self):
        before=self.snapshot();self.assertTrue(assess(self.root,'pre-merge','S1'));item=supplied_round(self.config)
        proposal=preview(self.root,'review',item);self.assertEqual(before,self.snapshot())
        self.assertEqual(proposal[1],'release-handoff.md');apply(*proposal,proposal[-1])
        self.assertTrue(assess(self.root,'pre-merge','S1'));self.record('gate',self.observation(item))
        self.assertEqual(assess(self.root,'pre-merge','S1'),[]);self.assertTrue(assess(self.root,'pre-merge','S2'))
    def test_arbitrary_pass_target_or_round_token_cannot_replace_review(self):
        with self.assertRaises(ValueError):preview(self.root,'gate',self.observation())
        self.record('review',supplied_round(self.config))
        for key,value in (('evidence','approve'),('target','unrelated-artifact'),('checked_at','2025-01-01T00:00:00Z')):
            with self.assertRaises(ValueError):preview(self.root,'gate',{**self.observation(),key:value})
    def test_stale_digest_and_concurrent_handoff_edits_refuse_apply(self):
        prepared=preview(self.root,'review',supplied_round(self.config));before=self.snapshot()
        with self.assertRaises(ValueError):apply(*prepared,'wrong')
        self.assertEqual(before,self.snapshot())
        path=self.root/'release-handoff.md';path.write_bytes(path.read_bytes()+b'\nconcurrent\n')
        with self.assertRaises(ValueError):apply(*prepared,prepared[-1])
        self.assertIn(b'concurrent',path.read_bytes())
    def test_copied_gate_cli_uses_same_review_dependency(self):
        self.record('review',supplied_round(self.config));self.record('gate',self.observation())
        command=[sys.executable,'-B',str(self.root/'dashboard/gates.py'),'--factory',str(self.root),'--stage','pre-merge','--revision','S1']
        good=subprocess.run(command,capture_output=True,text=True);self.assertEqual(good.returncode,0,good.stderr)
        bad=subprocess.run(command[:-1]+['S2'],capture_output=True,text=True);self.assertNotEqual(bad.returncode,0)
    def test_optional_empty_review_waived_but_missing_structure_still_blocks(self):
        path=self.root/'verification.md';path.write_text(path.read_text().replace('| Q1 | pre-merge |','| Q1 | pre-merge |').replace('subject and diff artifact | unconfirmed | yes |','subject and diff artifact | unconfirmed | no |'))
        self.assertEqual(assess(self.root,'pre-merge','S1'),[])
        self.assertTrue(any('Q1 WAIVED' in value for value in waivers(path.read_text(),'pre-merge')))
        (self.root/'release-handoff.md').write_text('no section')
        self.assertTrue(assess(self.root,'pre-merge','S1'))
    def test_legacy_absence_preserves_review_control_shape_and_no_new_routing(self):
        legacy=copy.deepcopy(self.config);legacy.pop('operations');files=render(legacy,self.research)
        self.assertEqual(controls(legacy)['review'],{'required_approvals':0,'independent':False,'distinct_providers':False})
        self.assertNotIn('Q1',gate_rows(files['verification.md']));self.assertNotIn('review-guide.md',files)
        self.assertNotIn('dashboard/review_records.py',files);self.assertNotIn(rr.START,files['release-handoff.md'])
        self.assertNotIn('Opted-in supplied review',files['phase-verify-guide.md'])

    def test_context_cli_is_read_only_and_exports_exact_selected_token_without_bytecode(self):
        item=supplied_round(self.config);self.record('review',item);before=self.snapshot()
        result=subprocess.run([sys.executable,str(self.root/'dashboard/review_records.py'),'--factory',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);data=json.loads(result.stdout)
        self.assertEqual(data['policy_sha256'],item['policy_sha256']);self.assertEqual(data['selected_round']['evidence_token'],rr.record_token(rr.parse((self.root/'release-handoff.md').read_text())))
        self.assertEqual(before,self.snapshot())

    def test_new_example_has_working_guide_links_and_starts_blocked_without_execution_claims(self):
        config=json.loads((ROOT/'assets/example-review-config.json').read_text());files=render(config,self.research)
        self.assertIn('review-guide.md',files);self.assertEqual(rr.parse(files['release-handoff.md']),rr.empty())
        self.assertEqual(gate_rows(files['verification.md'])['Q1']['result'],'NOT RUN')
        self.assertEqual(gate_rows(files['verification.md'])['Q1']['required'],'yes')
        for phase in ('verify','release'):
            self.assertIn('[review-guide.md](review-guide.md)',files['phase-'+phase+'-guide.md'])
        procedure=' '.join(files['review-guide.md'].split())
        self.assertIn('independently',procedure);self.assertIn('without the first review',procedure)

    def test_gate_token_binds_the_immutable_history_used_by_assessment(self):
        first=supplied_round(self.config);second=supplied_round(self.config,'round2','S2')
        self.record('review',first);self.record('review',second);self.record('gate',self.observation(second))
        self.assertEqual(assess(self.root,'pre-merge','S2'),[])
        path=self.root/'release-handoff.md';body=path.read_text();record=rr.parse(body)
        record['rounds'][0]['reviews'][0]['evidence']='tampered earlier supplied claim'
        start=body.index(rr.START);end=body.index(rr.END)+len(rr.END);path.write_text(body[:start]+rr.section(record)+body[end:])
        self.assertTrue(any('ledger digest' in value for value in assess(self.root,'pre-merge','S2')))

    def test_missing_or_misaligned_q1_blocks_even_when_review_would_be_optional(self):
        path=self.root/'verification.md';raw=path.read_bytes()
        path.write_bytes(b''.join(line for line in raw.splitlines(keepends=True) if not line.startswith(b'| Q1 |')))
        self.assertIn('Missing expected gate row: Q1',assess(self.root,'pre-merge','S1'))
        path.write_bytes(raw.replace(b'| Q1 | pre-merge |',b'| Q1 | post-merge |'))
        self.assertIn('Gate is in the wrong stage: Q1',assess(self.root,'pre-merge','S1'))

    def test_handoff_reader_rejects_size_before_read_and_cli_errors_do_not_echo_arguments(self):
        path=self.root/'release-handoff.md'
        with patch.object(rr,'MAX_HANDOFF',1),patch.object(Path,'open',side_effect=AssertionError('must not read oversized input')):
            with self.assertRaises(ValueError):rr.read_handoff(path)
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/review_records.py'),'--private-sentinel'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,'');self.assertNotIn('private-sentinel',result.stderr)
        self.assertEqual(before,self.snapshot())


if __name__=='__main__':unittest.main()
