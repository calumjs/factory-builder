"""Offline three-way previews against complete disposable factory snapshots."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import reconcile_evidence as rec
from acceptance_links import validate_snapshot
from gates import gate_rows
from incremental_records import gate_change
from scaffold import ROOT, render
from status import updated


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.roots={s:self.root/s for s in rec.SIDES}
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.config['operations']={'smoke_gates':{'post_merge':'Synthetic artifact check','target_kind':'artifact','deployed_url':'artifact'},'done_videos':{'enabled':True}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(self.config,self.research)
        for root in self.roots.values():
            for name,body in self.files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        self.decisions=self.root/'decisions.json'

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def read(self,side,name):return (self.roots[side]/name).read_bytes()
    def write(self,side,name,raw):(self.roots[side]/name).write_bytes(raw)
    def review(self,decision=False,subject='S1'):return rec.review(*(self.roots[s] for s in rec.SIDES),subject,self.decisions if decision else None)
    def choices(self,source='left',subject='S1'):
        report=self.review(subject=subject)
        data={'schema':1,'sources':report['sources'],'subject':subject}
        for kind in ('current_rows','task_statuses'):
            data[kind]={key:{'source':source,'sha256':options[source]['sha256'],'reason':'Explicit synthetic test choice'} for key,options in report['options'][kind].items()}
        self.decisions.write_text(json.dumps(data),encoding='utf-8');return data
    def record(self,side,gate='G3',result='FAILED',subject='S1'):
        item={'gate':gate,'result':result,'revision':subject,'environment':'synthetic fixture','evidence':'synthetic '+subject+' '+result,
              'target':'artifact','checked_at':'2026-11-01T12:00:00Z','exit_status':'0' if result=='PASSED' else '1'}
        self.write(side,'verification.md',gate_change(self.read(side,'verification.md').decode(),self.config,self.research,item))
    def event(self,side,status='blocked',result='failed',subject='S1'):
        plan=json.loads(self.read(side,'task-plan.json'))
        event=updated(plan,'T1',status,result,'synthetic evidence',subject,'synthetic fixture','synthetic check')
        self.write(side,'task-plan.json',json.dumps(plan).encode());return event
    def learn(self,side,rows):
        parsed=rec.learn_document(self.read(side,'learning-log.md'))
        raw=''.join(parsed['prefix'])+''.join(r+'\n' for r in parsed['rows']+rows)+''.join(parsed['suffix'])
        self.write(side,'learning-log.md',raw.encode())
    def edit_row(self,side,gate,column,value):
        lines=self.read(side,'verification.md').decode().splitlines()
        for i,line in enumerate(lines):
            if line.startswith('| '+gate+' |'):
                cells=[c.strip() for c in line.strip('|').split('|')];cells[column]=value;lines[i]='| '+' | '.join(cells)+' |'
        self.write(side,'verification.md',('\n'.join(lines)+'\n').encode())

    def test_discovery_and_exact_proposal_are_write_free(self):
        self.record('left');self.record('right',result='PASSED',subject='S2')
        before=self.snapshot();discovery=self.review()
        self.assertEqual(discovery['status'],'NEEDS_DECISIONS');self.assertNotIn('proposed',discovery)
        self.assertEqual(before,self.snapshot());self.choices();before=self.snapshot()
        result=self.review(True);self.assertEqual(result['status'],'PROPOSED');self.assertEqual(before,self.snapshot())
        proposed={name:item['utf8'].encode() for name,item in result['proposed'].items()}
        self.assertEqual(set(proposed),set(rec.RECORDS))
        source=rec.capture(self.roots['base'])['files'];validate_snapshot({**source,**proposed})
        row=gate_rows(proposed['verification.md'].decode())['G3']
        self.assertEqual((row['result'],row['revision']),('FAILED','S1'))
        self.assertIn('> | G3 |',proposed['verification.md'].decode());self.assertIn('S2 | PASSED',proposed['verification.md'].decode())
        self.assertTrue(result['diffs']['verification.md']);self.assertIn('G1',result['current_rows_outside_subject'])
        self.assertEqual(result,self.review(True))

    def test_learn_all_append_occurrences_survive_including_identical_text(self):
        row='| same date / task / revision | observed | hypothesis | change | owner | measure | pending |'
        for side in rec.SIDES:self.learn(side,[row,row])
        base_count=len(rec.learn_document(self.read('base','learning-log.md'))['rows'])
        self.learn('left',[row,row]);self.learn('right',[row,row.replace('observed','different observed')])
        self.choices();result=self.review(True)
        rows=rec.learn_document(result['proposed']['learning-log.md']['utf8'].encode())['rows']
        self.assertEqual(len(rows),base_count+4);self.assertEqual(rows.count(row),5)
        self.assertEqual([v['source'] for v in result['learn_origins']][-4:],['left','left','right','right'])

    def test_unique_events_preserved_and_identical_event_ids_deduplicated(self):
        first=self.event('left');second=self.event('right',subject='S2')
        right=json.loads(self.read('right','task-plan.json'));right['events'].append(first)
        self.write('right','task-plan.json',json.dumps(right).encode());self.choices();result=self.review(True)
        events=json.loads(result['proposed']['task-plan.json']['utf8'])['events']
        self.assertEqual(events,[first,second]);self.assertEqual(events[0]['result'],'failed')

    def test_duplicate_or_conflicting_event_ids_refused_before_decisions(self):
        event=self.event('left');right=json.loads(self.read('right','task-plan.json'))
        right['events']=[dict(event,evidence='different payload')]
        self.write('right','task-plan.json',json.dumps(right).encode())
        with self.assertRaisesRegex(ValueError,'Conflicting payloads'):self.review()
        right['events']=[event,event];self.write('right','task-plan.json',json.dumps(right).encode())
        with self.assertRaisesRegex(ValueError,'Duplicate event'):self.review()

    def test_base_event_and_learn_deletion_or_modification_refused(self):
        self.event('base');self.learn('base',['| base | observed | h | c | o | m | pending |'])
        with self.assertRaisesRegex(ValueError,'Base events'):self.review()
        for side in ('left','right'):self.write(side,'task-plan.json',self.read('base','task-plan.json'))
        with self.assertRaisesRegex(ValueError,'Base Learn'):self.review()

    def test_wrong_subject_choice_has_no_proposed_files(self):
        self.record('right',subject='S2');self.choices('right')
        result=self.review(True);self.assertEqual(result['status'],'CONFLICT');self.assertNotIn('proposed',result)

    def test_explicit_task_status_keeps_underlying_event_subject(self):
        self.event('left','done','passed','S-old');self.event('right','in_progress','failed','S2')
        self.choices();result=self.review(True);plan=json.loads(result['proposed']['task-plan.json']['utf8'])
        self.assertEqual(plan['tasks'][0]['status'],'done');self.assertEqual([e['revision'] for e in plan['events']],['S-old','S2'])
        self.assertIn('not rebound',result['task_status_notice'])

    def test_requiredness_difference_refuses_without_forcing_required(self):
        self.edit_row('left','G3',4,'no')
        with self.assertRaisesRegex(ValueError,'requiredness differs'):self.review()
        for side in ('base','right'):self.edit_row(side,'G3',4,'no')
        self.record('left');self.choices();result=self.review(True)
        self.assertEqual(gate_rows(result['proposed']['verification.md']['utf8'])['G3']['required'],'no')

    def test_plan_contract_and_unknown_task_fields_refused(self):
        plan=json.loads(self.read('left','task-plan.json'));plan['tasks'][0]['extra']='private'
        self.write('left','task-plan.json',json.dumps(plan).encode())
        with self.assertRaises(ValueError):self.review()
        self.write('left','task-plan.json',self.read('base','task-plan.json'))
        self.write('left','policy.md',self.read('left','policy.md')+b'changed')
        with self.assertRaises(ValueError):self.review()

    def test_malformed_hidden_duplicate_gate_tables_and_history_refused(self):
        original=self.read('left','verification.md')
        for raw in (original+b'\n```\n',original+b'\n<!-- hidden -->\n',original+rec.HEADER.encode(),
                    original+b'\n## Prior gate observation (not current evidence)\n> | G3 | broken |\n',
                    original.replace(b'| NOT RUN |',b'| INVALID |',1)):
            with self.subTest(raw=raw[-25:]):
                self.write('left','verification.md',raw)
                with self.assertRaises(ValueError):self.review()

    def test_history_removal_and_different_prose_refused(self):
        self.record('base')
        for side in ('left','right'):self.write(side,'verification.md',self.read('base','verification.md'))
        self.write('left','verification.md',self.read('left','verification.md').split(b'\n## Prior gate')[0]+b'\n')
        with self.assertRaisesRegex(ValueError,'Base gate history'):self.review()
        self.write('left','verification.md',self.read('base','verification.md')+b'\nDifferent policy prose\n')
        with self.assertRaisesRegex(ValueError,'prose differs'):self.review()

    def test_decisions_bind_exact_raw_bytes_and_reject_stale_unknown_keys(self):
        self.record('left');data=self.choices();first=self.review(True)
        self.decisions.write_text(json.dumps(data,indent=2));second=self.review(True)
        self.assertNotEqual(first['plan_sha256'],second['plan_sha256']);self.assertEqual(first['proposed'],second['proposed'])
        mutations=[lambda d:d.update(extra=True),lambda d:d['sources'].update(left='0'*64),
                   lambda d:d['current_rows'].update(UNKNOWN={}),lambda d:d['current_rows']['G3'].update(sha256='0'*64)]
        for change in mutations:
            bad=copy.deepcopy(data);change(bad);self.decisions.write_text(json.dumps(bad))
            with self.assertRaises(ValueError):self.review(True)

    def test_source_file_directory_and_decision_races_refused(self):
        self.choices();real=rec.derive
        def raced(*args,**kwargs):
            result=real(*args,**kwargs);(self.roots['left']/'new-empty-directory').mkdir();return result
        with patch.object(rec,'derive',side_effect=raced):
            with self.assertRaisesRegex(ValueError,'Source changed'):self.review(True)
        (self.roots['left']/'new-empty-directory').rmdir();self.choices()
        def decision_race(*args,**kwargs):
            result=real(*args,**kwargs);self.decisions.write_bytes(self.decisions.read_bytes()+b' ');return result
        with patch.object(rec,'derive',side_effect=decision_race):
            with self.assertRaisesRegex(ValueError,'Decisions changed'):self.review(True)

    def test_missing_nested_same_and_parent_traversal_paths_refused(self):
        for other in (self.roots['base'],self.roots['base']/'nested',self.root/'missing',self.roots['left']/'..'/'left'):
            with self.assertRaises((ValueError,OSError)):rec.review(self.roots['base'],other,self.roots['right'],'S1')

    def test_bounds_and_strict_decision_json(self):
        self.choices()
        for raw in (b'{"schema":1,"schema":1}',b'{"schema":NaN}'):
            self.decisions.write_bytes(raw)
            with self.assertRaises(ValueError):self.review(True)
        with patch.object(rec,'MAX_ROWS',1):
            with self.assertRaises(ValueError):self.review()
        with patch.object(rec,'MAX_RECORD',1):
            with self.assertRaises(ValueError):self.review()

    def test_actual_cli_outputs_only_preview_and_rejects_apply_privately(self):
        self.choices();before=self.snapshot()
        args=[sys.executable,'-B',str(Path(rec.__file__))]
        for side,path in self.roots.items():args+=['--'+side,str(path)]
        args+=['--subject','S1','--decisions',str(self.decisions)]
        result=subprocess.run(args,capture_output=True,text=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'PROPOSED')
        bad=subprocess.run(args+['--apply','private-sentinel'],capture_output=True,text=True,check=False)
        self.assertEqual(bad.returncode,2);self.assertEqual(bad.stdout,'');self.assertNotIn('private-sentinel',bad.stderr)
        self.assertEqual(before,self.snapshot())

    def test_optional_old_subject_preserved_and_explicitly_excluded(self):
        for side in rec.SIDES:self.edit_row(side,'G3',4,'no')
        self.record('left',subject='S-old');self.choices();result=self.review(True)
        row=gate_rows(result['proposed']['verification.md']['utf8'])['G3']
        self.assertEqual((row['required'],row['revision'],row['result']),('no','S-old','FAILED'))
        self.assertIn('G3',result['current_rows_outside_subject'])

    def test_done_status_cannot_synthesize_completed_dependencies(self):
        for side in rec.SIDES:
            plan=json.loads(self.read(side,'task-plan.json'))
            plan['tasks'].append(dict(plan['tasks'][0],id='T2',depends_on=['T1']))
            self.write(side,'task-plan.json',json.dumps(plan).encode())
        left=json.loads(self.read('left','task-plan.json'));left['tasks'][1]['status']='done'
        self.write('left','task-plan.json',json.dumps(left).encode());self.choices()
        result=self.review(True);self.assertEqual(result['status'],'CONFLICT');self.assertNotIn('proposed',result)

    def test_g3_video_and_all_prior_failures_survive_without_new_pass(self):
        self.record('left','G3','FAILED');self.record('left','G3','PASSED');self.record('left','V1','PASSED')
        self.record('right','G3','FAILED','S2');self.record('right','V1','BLOCKED','S2')
        self.choices();result=self.review(True);body=result['proposed']['verification.md']['utf8']
        rows=gate_rows(body);self.assertEqual(rows['V1']['revision'],'S1')
        self.assertIn('S1 | FAILED',body);self.assertIn('S2 | FAILED',body);self.assertIn('S2 | BLOCKED',body)
        for gate in ('G3','V1'):
            self.assertEqual(rows[gate],gate_rows(self.read('left','verification.md').decode())[gate])

    def test_source_byte_race_and_captured_root_identity_change_refused(self):
        self.choices();real=rec.derive
        def race(*args,**kwargs):
            result=real(*args,**kwargs);self.write('right','verification.md',self.read('right','verification.md')+b'\n');return result
        with patch.object(rec,'derive',side_effect=race):
            with self.assertRaisesRegex(ValueError,'Source changed'):self.review(True)
        root=self.roots['base'];files,dirs=rec.snapshot_factory(root)
        self.assertNotEqual(rec.fingerprint(root,(1,1),files,dirs),rec.fingerprint(root,(1,2),files,dirs))

    def test_malformed_learn_and_record_inventory_fail_before_decisions(self):
        original=self.read('left','learning-log.md')
        self.write('left','learning-log.md',original.replace(b'| Hypothesis |',b'| WRONG |'))
        with self.assertRaises(ValueError):self.review()
        self.write('left','learning-log.md',original)
        (self.roots['left']/'verification.md').unlink()
        with self.assertRaises((ValueError,KeyError)):self.review()


if __name__=='__main__':unittest.main()
