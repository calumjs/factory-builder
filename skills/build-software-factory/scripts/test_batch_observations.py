"""Explicit offline batch observations reuse the existing preview/atomic writer."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gates import assess, gate_rows
from incremental_records import (MAX_BATCH_INPUT_BYTES, MAX_BATCH_ITEMS, apply,
                                 gate_batch_change, preview, read_gate_batch)
from scaffold import ROOT, render


class BatchObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['acceptance']=['Synthetic export criterion','Synthetic unrelated criterion']
        self.config['operations']={'smoke_gates':{'pre_merge':'Synthetic build check','targeted':'Synthetic targeted check',
                                                 'post_merge':'Synthetic artifact check','target_kind':'artifact','deployed_url':'artifact'},
                                   'done_videos':{'enabled':True}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(self.config,self.research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    @staticmethod
    def observation(gate,result='FAILED',subject='S1',**fields):
        value={'gate':gate,'result':result,'revision':subject,'environment':'synthetic fixture',
               'evidence':'synthetic observed '+result,'target':'artifact','checked_at':'2026-11-01T12:00:00Z',
               'exit_status':'0' if result=='PASSED' else '1'}
        value.update(fields);return value

    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def edit(self,gate,changes):
        path=self.root/'verification.md';lines=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| '+gate+' |'):
                cells=[value.strip() for value in line.strip('|').split('|')]
                for index,value in changes.items():cells[index]=value
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        path.write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))

    def record(self,kind,value):
        prepared=preview(self.root,kind,value);apply(*prepared,prepared[-1]);return prepared

    def test_write_free_preview_has_one_atomic_replace_and_preserves_excluded_rows(self):
        changes=[self.observation('G1','PASSED'),self.observation('G2','FAILED')]
        before=self.snapshot();oldrows=gate_rows((self.root/'verification.md').read_text(encoding='utf-8'))
        prepared=preview(self.root,'gate-batch',changes)
        self.assertEqual(before,self.snapshot());self.assertEqual(prepared[1],'verification.md')
        rows=gate_rows(prepared[3].decode('utf-8'))
        self.assertEqual(rows['G1']['result'],'PASSED');self.assertEqual(rows['G2']['result'],'FAILED')
        for gate in set(rows)-{'G1','G2'}:self.assertEqual(rows[gate],oldrows[gate])
        replace=os.replace;calls=[]
        def atomic(source,destination):
            self.assertEqual(Path(source).read_bytes(),prepared[3])
            self.assertEqual(destination,self.root/'verification.md');calls.append(destination)
            return replace(source,destination)
        with patch('incremental_records.os.replace',side_effect=atomic):apply(*prepared,prepared[-1])
        self.assertEqual(len(calls),1)
        self.assertEqual((self.root/'verification.md').read_bytes(),prepared[3])
        after=self.snapshot()
        self.assertEqual({name for name in before if before[name]!=after[name]},{'factory/verification.md'})
        self.assertEqual(set(before),set(after));self.assertTrue(assess(self.root,'pre-merge','S1'))

    def test_invalid_later_item_rejects_whole_batch_without_partial_preview_or_write(self):
        good=self.observation('G1','PASSED')
        for invalid in (self.observation('G2','PASSED',evidence=''),self.observation('G2','PASSED',target=''),
                        self.observation('G2','PASSED',checked_at='not-a-time'),self.observation('G2','PASSED',exit_status='1'),
                        self.observation('G2','WAIVED'),
                        self.observation('G2',evidence='bad | table injection')):
            for changes in ([good,invalid],[invalid,good]):
                before=self.snapshot()
                with self.assertRaises(ValueError):preview(self.root,'gate-batch',changes)
                self.assertEqual(before,self.snapshot())

    def test_duplicate_unknown_unconfigured_and_malformed_identity_refused(self):
        self.edit('A2',{0:'X1'})
        good=self.observation('G1')
        invalid_batches=[[],{},[good,good],[good,self.observation('A999')],[good,self.observation('X1')],
                         [good,self.observation('G2',subject='S2')],[good,self.observation('G2',subject=' S1')],
                         [self.observation('G1',subject='a'*40),self.observation('G2',subject='a'*7)],
                         [good,self.observation('G2',subject='')],[{**good,'required':'no'}],
                         [self.observation(' G1')],[self.observation('G1',subject='S1\nother')],
                         [good]* (MAX_BATCH_ITEMS+1),[{**good,'target':None}]]
        for changes in invalid_batches:
            with self.subTest(changes=changes):
                before=self.snapshot()
                with self.assertRaises(ValueError):preview(self.root,'gate-batch',changes)
                self.assertEqual(before,self.snapshot())

    def test_canonical_batch_order_preserves_each_timestamp_and_same_digest(self):
        first=self.observation('G1','PASSED',checked_at='2026-11-01T12:05:00Z')
        second=self.observation('G2','PASSED',checked_at='2026-11-01T12:00:00Z')
        a=preview(self.root,'gate-batch',[first,second]);b=preview(self.root,'gate-batch',[second,first])
        self.assertEqual(a,b)
        rows=gate_rows(a[3].decode('utf-8'))
        self.assertEqual(rows['G1']['checked_at'],first['checked_at']);self.assertEqual(rows['G2']['checked_at'],second['checked_at'])

    def test_same_unresolved_placeholder_does_not_establish_batch_subject_identity(self):
        for subject in ('unknown','unconfirmed','TBD','pending','unknown: choose the revision'):
            before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'unresolved placeholder'):
                preview(self.root,'gate-batch',[self.observation('G1',subject=subject),self.observation('G2',subject=subject)])
            self.assertEqual(before,self.snapshot())

    def test_prior_failure_history_and_excluded_old_subject_are_preserved(self):
        self.record('gate',self.observation('G1','FAILED','S0',evidence='prior failure S0'))
        self.record('gate',self.observation('A2','PASSED','S0',evidence='unrelated old observation'))
        prior=(self.root/'verification.md').read_text(encoding='utf-8');oldrows=gate_rows(prior)
        self.record('gate-batch',[self.observation('G1','PASSED'),self.observation('G2','PASSED')])
        current=(self.root/'verification.md').read_text(encoding='utf-8');rows=gate_rows(current)
        self.assertIn('prior failure S0',current);self.assertIn('> | G1 |',current)
        self.assertEqual(rows['A2'],oldrows['A2']);self.assertEqual(rows['A2']['revision'],'S0')
        self.assertTrue(any('A2 has stale or missing revision' in issue for issue in assess(self.root,'pre-merge','S1')))
        self.assertEqual(rows['A1']['result'],'NOT RUN')

    def test_configured_acceptance_and_research_rows_can_share_explicit_observations(self):
        self.research.update(status='complete',summary='Synthetic research fixture; no external research performed',
            coverage={phase:{'status':'applicable' if phase=='verify' else 'not_applicable','reason':'Synthetic test scope'} for phase in self.research['coverage']},
            sources=[{'id':'S1','url':'https://example.invalid/synthetic','accessed_on':'2026-11-01','kind':'synthetic',
                      'version_scope':'fixture','observation':'Synthetic supplied observation','status':'read'}],
            practices=[{'id':'P1','decision':'selected','source_ids':['S1'],'phases':['verify'],'relevance':'Synthetic scope',
                        'compatibility':'Synthetic fixture','tradeoff':'Synthetic fixture','instruction':'Synthetic planned instruction','check':'Synthetic research-derived check'}])
        for name,body in render(self.config,self.research).items():
            (self.root/name).write_bytes(body.encode('utf-8'))
        self.record('gate-batch',[self.observation('A1','PASSED'),self.observation('R1','FAILED')])
        rows=gate_rows((self.root/'verification.md').read_text(encoding='utf-8'))
        self.assertEqual((rows['A1']['result'],rows['R1']['result']),('PASSED','FAILED'))
        self.assertEqual(rows['R1']['revision'],'S1');self.assertEqual(rows['R1']['required'],'yes')
        self.assertEqual(rows['G1']['result'],'NOT RUN');self.assertTrue(assess(self.root,'pre-merge','S1'))

    def test_optional_requiredness_survives_and_passing_claim_still_needs_evidence(self):
        self.edit('A1',{4:'no',6:'FAILED',7:'prior optional failure'})
        self.record('gate-batch',[self.observation('G1'),self.observation('A1','PASSED')])
        text=(self.root/'verification.md').read_text(encoding='utf-8');row=gate_rows(text)['A1']
        self.assertEqual((row['required'],row['result']),('no','PASSED'));self.assertIn('prior optional failure',text)
        before=self.snapshot()
        with self.assertRaises(ValueError):preview(self.root,'gate-batch',[self.observation('A1','PASSED',evidence='')])
        self.assertEqual(before,self.snapshot())

    def test_nonpassing_fields_are_not_filled_with_target_or_success_defaults(self):
        changes=[self.observation('G1','BLOCKED',target='',checked_at='',exit_status='',evidence=''),
                 self.observation('A1','NOT RUN',target='',checked_at='',exit_status='',evidence='')]
        proposed=preview(self.root,'gate-batch',changes)[3]
        rows=gate_rows(proposed.decode('utf-8'))
        for item in changes:
            for key in ('result','revision','target','checked_at','exit_status','evidence'):
                self.assertEqual(rows[item['gate']][key],item[key])

    def test_stale_approval_changed_inputs_and_concurrent_factory_changes_refuse(self):
        first=[self.observation('G1'),self.observation('G2')]
        prepared=preview(self.root,'gate-batch',first);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'exact reviewed'):apply(*prepared,'wrong')
        self.assertEqual(before,self.snapshot())
        revised=preview(self.root,'gate-batch',[{**first[0],'evidence':'different observation'},first[1]])
        self.assertNotEqual(prepared[-1],revised[-1])
        with self.assertRaisesRegex(ValueError,'exact reviewed'):apply(*revised,prepared[-1])
        self.assertEqual(before,self.snapshot())
        self.edit('A2',{6:'FAILED',7:'concurrent failure'});changed=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed since preview'):apply(*prepared,prepared[-1])
        self.assertEqual(changed,self.snapshot())

    def test_replace_failure_keeps_entire_prior_record_and_removes_temporary_artifacts(self):
        prepared=preview(self.root,'gate-batch',[self.observation('G1'),self.observation('G2')]);before=self.snapshot()
        with patch('incremental_records.os.replace',side_effect=OSError('synthetic replacement failure')):
            with self.assertRaises(OSError):apply(*prepared,prepared[-1])
        self.assertEqual(before,self.snapshot())
        self.assertFalse((self.root/'.factory-status.lock').exists());self.assertFalse(list(self.root.glob('.record-*')))

    def test_g3_and_v1_same_batch_refused_in_both_orders_even_with_existing_success(self):
        self.record('gate',self.observation('G3','PASSED'))
        for result in ('PASSED','FAILED'):
            changes=[self.observation('G3',result),self.observation('V1',result,checked_at='2026-11-01T12:01:00Z')]
            for ordered in (changes,list(reversed(changes))):
                before=self.snapshot()
                with self.assertRaisesRegex(ValueError,'separate reviewed recording steps'):preview(self.root,'gate-batch',ordered)
                self.assertEqual(before,self.snapshot())

    def test_v1_uses_existing_required_g3_subject_target_and_observation_time(self):
        video=self.observation('V1','PASSED',checked_at='2026-11-01T12:01:00Z')
        with self.assertRaises(ValueError):preview(self.root,'gate-batch',[video])
        self.record('gate',self.observation('G3','FAILED'))
        with self.assertRaises(ValueError):preview(self.root,'gate-batch',[video])
        self.record('gate-batch',[self.observation('G3','PASSED')])
        for invalid in ({**video,'revision':'other'}, {**video,'target':'other'}, {**video,'checked_at':'2026-11-01T11:59:00Z'}):
            with self.assertRaises(ValueError):preview(self.root,'gate-batch',[invalid])
        self.record('gate-batch',[video])
        self.assertEqual(gate_rows((self.root/'verification.md').read_text(encoding='utf-8'))['V1']['result'],'PASSED')

    def test_existing_g3_waiver_does_not_become_a_required_pass_for_v1(self):
        self.edit('G3',{4:'no',6:'FAILED',7:'optional failure retained'})
        self.record('gate-batch',[self.observation('V1','PASSED')])
        rows=gate_rows((self.root/'verification.md').read_text(encoding='utf-8'))
        self.assertEqual((rows['G3']['required'],rows['G3']['result']),('no','FAILED'))

    def test_strict_json_and_bounds_refuse_before_large_read_or_parser(self):
        source=self.base/'observations.json'
        for raw in ('[{"gate":"G1","gate":"G2"}]','[NaN]','[Infinity]', '['*15000+'0'+']'*15000):
            source.write_bytes(raw.encode('utf-8'))
            with self.assertRaises(ValueError):read_gate_batch(source)
        source.write_bytes(('['*2000+'0'+']'*2000).encode('utf-8'))
        with self.assertRaises(ValueError):preview(self.root,'gate-batch',read_gate_batch(source))
        source.write_bytes(b' '*(MAX_BATCH_INPUT_BYTES+1))
        with patch.object(Path,'open',side_effect=AssertionError('oversized input must not be opened')):
            with self.assertRaisesRegex(ValueError,'256 KiB'):read_gate_batch(source)
        with self.assertRaises(ValueError):read_gate_batch(self.base)
        huge=self.observation('G1',evidence='x'*8193)
        with self.assertRaisesRegex(ValueError,'8192'):preview(self.root,'gate-batch',[huge])
        data=[self.observation(gate,evidence='\u2603'*8192) for gate in ('G1','G2','G3','A1','A2','V1')]
        with self.assertRaisesRegex(ValueError,'256 KiB'):preview(self.root,'gate-batch',data)

    def test_cli_preview_digest_invalid_item_and_apply_are_single_file_and_offline(self):
        source=self.base/'observations.json';data=[self.observation('G1'),self.observation('G2')]
        source.write_text(json.dumps(data),encoding='utf-8');before=self.snapshot()
        command=[sys.executable,'-B',str(ROOT/'scripts/incremental_records.py'),'--factory',str(self.root),'--kind','gate-batch','--input',str(source)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(before,self.snapshot())
        token=re.search(r'REVIEW PLAN: ([a-f0-9]{64})',result.stdout).group(1)
        source.write_text(json.dumps([data[0],self.observation('G2','PASSED',evidence='')]),encoding='utf-8');invalid=self.snapshot()
        result=subprocess.run(command+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertEqual(invalid,self.snapshot())
        source.write_text(json.dumps(data),encoding='utf-8')
        result=subprocess.run(command+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('no checks were executed or attested',result.stdout)
        rows=gate_rows((self.root/'verification.md').read_text(encoding='utf-8'))
        self.assertEqual(rows['G1']['result'],'FAILED');self.assertEqual(rows['G2']['result'],'FAILED')

    def test_batch_planning_never_executes_commands_in_observations(self):
        text=(self.root/'verification.md').read_text(encoding='utf-8')
        data=[self.observation('G1',evidence='synthetic-command --never-execute')]
        with patch.object(subprocess,'Popen',side_effect=AssertionError('no process')):
            proposed=gate_batch_change(text,self.config,self.research,data)
        self.assertEqual(gate_rows(proposed.decode('utf-8'))['G1']['evidence'],data[0]['evidence'])


if __name__=='__main__':unittest.main()
