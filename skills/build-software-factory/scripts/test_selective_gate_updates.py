"""Selective plan invalidation preserves observations, never certifies their freshness."""
import copy
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from gates import gate_rows, initial_table, ROW
from integrity import digest
from operations import operations
from scaffold import ROOT, render
import update_operations as updater


class SelectiveGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['acceptance']=['First criterion | exact display','Second criterion']
        self.config['operations']=operations(self.config)
        self.config['operations']['done_videos'].update(enabled=True,triggers=['pre_merge_preview','post_g3_release'])
        self.config['operations']['smoke_gates']['check_stages']={'A2':{'stage':'post-merge','rationale':'Inspect released fixture'}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.research.update(status='complete',summary='Synthetic fixture only, not actual research')
        self.research['coverage']={phase:{'status':'applicable' if phase=='release' else 'not_applicable','reason':'Synthetic fixture assessment'} for phase in ('intake','plan','build','verify','release','learn')}
        self.research['sources']=[{'id':'S1','url':'https://example.com/synthetic','accessed_on':date.today().isoformat(),'kind':'synthetic fixture','version_scope':'fixture only','observation':'Synthetic observation','status':'read'}]
        self.research['practices']=[{'id':'P1','decision':'selected','source_ids':['S1'],'phases':['release'],'relevance':'Fixture requirement','compatibility':'Fixture only','tradeoff':'Synthetic test','instruction':'Inspect artifact','check':'Inspect released fixture'}]
        for name,body in render(self.config,self.research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        self.path=self.root/'verification.md'

    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}

    def edit(self,gate,values):
        output=[]
        for line in self.path.read_bytes().decode().splitlines(keepends=True):
            if ROW.match(line) and ROW.match(line)[1]==gate:
                ending='\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
                cells=[value.strip() for value in line.strip().strip('|').split('|')]
                for index,value in values.items():cells[index]=value
                line='| '+' | '.join(cells)+' |'+ending
            output.append(line)
        self.path.write_bytes(''.join(output).encode())

    def raw_rows(self,raw):return {ROW.match(line)[1]:line for line in raw.decode('utf-8-sig').splitlines(keepends=True) if ROW.match(line)}

    def observe(self):
        for gate in gate_rows(self.path.read_text(encoding='utf-8')):
            self.edit(gate,{3:'isolated fixture',5:'old-private-subject',6:'FAILED' if gate=='G1' else 'PASSED',7:'private-artifact',8:'old-target',9:'2026-11-03T00:00:00+00:00',10:'1' if gate=='G1' else '0'})
        self.edit('A1',{4:'n',5:'',6:'NOT RUN',7:'',8:'',9:'',10:''})

    def preview(self,changes,**kwargs):
        before=self.snapshot()
        with patch('subprocess.run',side_effect=AssertionError('No external commands')):
            result=updater.prepare(self.root,changes,selective_gates=True,**kwargs)
        self.assertEqual(before,self.snapshot())
        root,old,new,token=result
        fingerprints={name:{'before':hashlib.sha256(old[name]).hexdigest() if old[name] is not None else None,'after':hashlib.sha256(data).hexdigest()} for name,data in sorted(new.items())}
        self.assertEqual(token,hashlib.sha256(updater.dumps({'factory':str(root),'files':fingerprints}).encode()).hexdigest())
        return result

    def active(self,prepared):return gate_rows(prepared[2].get('verification.md',prepared[1]['verification.md']).decode('utf-8-sig'))

    def test_post_target_resets_post_rows_and_preserves_pre_rows_exactly(self):
        self.observe();old=self.raw_rows(self.path.read_bytes())
        prepared=self.preview({'smoke_gates':{'deployed_url':'https://fixture.invalid/release','target_kind':'web'}})
        new=self.raw_rows(prepared[2]['verification.md']);rows=self.active(prepared)
        for gate in ('G1','G2','A1','V2'):self.assertEqual(new[gate],old[gate])
        for gate in ('G3','A2','R1','V1'):
            self.assertEqual(rows[gate]['result'],'NOT RUN');self.assertEqual(rows[gate]['revision'],'')
            self.assertIn('> '+old[gate].rstrip(),prepared[2]['verification.md'].decode())

    def test_structured_recipe_changes_are_per_gate_with_video_dependencies(self):
        self.observe()
        recipe={'command':['fixture-check','--check'],'environment':'disposable fixture','env_names':[], 'target':{'kind':'artifact','value':'fixture-artifact','base_url_env':None}}
        for gate,dependent in (('G1','V2'),('G2','V2'),('G3','V1')):
            with self.subTest(gate=gate):
                prepared=self.preview({'smoke_gates':{'checks':{gate:recipe}}})
                rows=self.active(prepared)
                self.assertEqual(rows[gate]['result'],'NOT RUN');self.assertEqual(rows[dependent]['result'],'NOT RUN')
                self.assertEqual(rows['A1']['required'],'no')
                if gate!='G3':self.assertEqual(rows['R1']['result'],'PASSED')

    def test_g3_command_only_change_retains_unrelated_post_rows(self):
        recipe={'command':['fixture-check'],'environment':'disposable fixture','env_names':[], 'target':{'kind':'artifact','value':'fixture-artifact','base_url_env':None}}
        first=self.preview({'smoke_gates':{'checks':{'G3':recipe}}});updater.apply(*first,first[3]);self.observe()
        recipe['command']=['fixture-check','--extra']
        prepared=self.preview({'smoke_gates':{'checks':{'G3':recipe}}});rows=self.active(prepared)
        self.assertEqual(rows['G3']['result'],'NOT RUN');self.assertEqual(rows['V1']['result'],'NOT RUN')
        for gate in ('A2','R1','G1','G2','V2'):self.assertEqual(rows[gate]['result'],'FAILED' if gate=='G1' else 'PASSED')

    def test_missing_or_misaligned_prerequisite_resets_dependent_after_classification(self):
        self.observe();original=self.path.read_bytes()
        for gate,dependent in (('G3','V1'),('G1','V2'),('G2','V2')):
            for mode in ('missing','design','stage'):
                with self.subTest(gate=gate,mode=mode):
                    self.path.write_bytes(original)
                    if mode=='missing':self.path.write_bytes(b''.join(line for line in original.splitlines(keepends=True) if not line.startswith(('| '+gate+' |').encode())))
                    else:self.edit(gate,{2:'private-custom-design'} if mode=='design' else {1:'pre-merge' if gate=='G3' else 'post-merge'})
                    prepared=self.preview({'done_videos':{'enabled':True}});rows=self.active(prepared)
                    self.assertEqual(rows[gate]['result'],'NOT RUN');self.assertEqual(rows[dependent]['result'],'NOT RUN')
                    messages=updater.selective_explanations(prepared[1],prepared[2],{'done_videos':{'enabled':True}})
                    self.assertTrue(any('prerequisite_reset' in msg and dependent in msg for msg in messages));self.assertNotIn('private-',str(messages))

    def test_required_key_even_same_value_broad_resets_and_reapplies_defaults(self):
        self.observe();self.edit('G1',{4:'no'})
        prepared=self.preview({'smoke_gates':{'required':True}});rows=self.active(prepared)
        self.assertTrue(all(row['result']=='NOT RUN' for row in rows.values()))
        self.assertEqual(rows['G1']['required'],'yes');self.assertEqual(rows['A1']['required'],'no')
        self.assertIn('explicit_required_defaults',str(updater.selective_explanations(prepared[1],prepared[2],{'smoke_gates':{'required':True}})))

    def test_stage_rationale_only_resets_that_row(self):
        self.observe()
        prepared=self.preview({'smoke_gates':{'check_stages':{'A2':{'stage':'post-merge','rationale':'New independently reviewed rationale'}}}})
        rows=self.active(prepared);self.assertEqual(rows['A2']['result'],'NOT RUN');self.assertEqual(rows['G3']['result'],'PASSED')
        self.assertIn('stage_override_changed',str(updater.selective_explanations(prepared[1],prepared[2],{'smoke_gates':{}})))

    def test_video_only_change_does_not_clear_other_observations(self):
        self.observe();old=self.raw_rows(self.path.read_bytes())
        prepared=self.preview({'done_videos':{'scope':'New authorized fixture scope'}});new=self.raw_rows(prepared[2]['verification.md'])
        for gate in old.keys()-{'V1','V2'}:self.assertEqual(old[gate],new[gate])
        self.assertEqual(self.active(prepared)['V1']['result'],'NOT RUN');self.assertEqual(self.active(prepared)['V2']['result'],'NOT RUN')

    def test_stage_move_resets_only_moved_row_and_keeps_optional_choice(self):
        self.observe();self.edit('A2',{4:'no'})
        prepared=self.preview({'smoke_gates':{'check_stages':{'A2':{'stage':'pre-merge','rationale':'Review fixture before merge'}}}})
        rows=self.active(prepared)
        self.assertEqual(rows['A2']['stage'],'pre-merge');self.assertEqual(rows['A2']['required'],'no');self.assertEqual(rows['A2']['revision'],'')
        self.assertEqual(rows['G3']['result'],'PASSED');self.assertEqual(rows['G1']['result'],'FAILED')

    def test_exclusion_changes_reset_post_context_without_inventing_optional_flags(self):
        self.observe()
        changes={'done_videos':{'enabled':False},'smoke_gates':{'target_kind':'no_release','post_merge_applicability':'not_applicable','post_merge_rationale':'Operator accepted a fixture-only output','accepted_by':'fixture operator'}}
        prepared=self.preview(changes);rows=self.active(prepared)
        self.assertEqual(rows['G3']['result'],'NOT APPLICABLE');self.assertEqual(rows['G3']['required'],'yes');self.assertEqual(rows['G3']['revision'],'')
        self.assertEqual(rows['A2']['result'],'NOT RUN');self.assertEqual(rows['R1']['result'],'NOT RUN')
        self.assertEqual(rows['G1']['result'],'FAILED');self.assertEqual(rows['A1']['required'],'no')

    def test_retirement_archives_videos_without_resetting_other_rows(self):
        self.observe();prepared=self.preview({'done_videos':{'enabled':False}})
        self.assertNotIn('V1',self.active(prepared));self.assertNotIn('V2',self.active(prepared))
        self.assertEqual(self.active(prepared)['G1']['result'],'FAILED')
        updater.apply(*prepared,prepared[3]);old=self.path.read_bytes()
        again=self.preview({'done_videos':{'enabled':False}});self.assertNotIn('verification.md',again[2]);self.assertEqual(self.path.read_bytes(),old)

    def test_noop_preserves_entire_file_bom_observations_and_waiver(self):
        self.observe();raw=b'\xef\xbb\xbf'+self.path.read_bytes().replace(b'\n',b'\r\n').rstrip(b'\r\n')
        self.path.write_bytes(raw)
        prepared=self.preview({'done_videos':{'enabled':True}})
        self.assertNotIn('verification.md',prepared[2]);self.assertEqual(prepared[1]['verification.md'],raw)
        self.assertEqual(self.active(prepared)['G1']['revision'],'old-private-subject')

    def test_mixed_endings_order_spacing_and_final_newline_edges(self):
        self.observe();raw=self.path.read_bytes();rowmap=self.raw_rows(raw)
        prefix=b''.join(line for line in raw.splitlines(keepends=True) if not ROW.match(line.decode()))
        order=['A2','G3','V1','R1','G1','V2','G2','A1']
        body=[]
        for index,gate in enumerate(order):
            line=rowmap[gate].rstrip('\r\n').replace('| A1 |','|   A1   |')
            body.append(line+('' if index==len(order)-1 else '\r\n' if index%2 else '\n'))
        self.path.write_bytes(prefix+''.join(body).encode());before=self.raw_rows(self.path.read_bytes())
        prepared=self.preview({'smoke_gates':{'post_merge':'New post release design'}});after=self.raw_rows(prepared[2]['verification.md'])
        self.assertEqual(list(after),order)
        for gate in ('A2','R1','G1','V2','G2','A1'):self.assertEqual(after[gate],before[gate])
        self.assertFalse(prepared[2]['verification.md'].endswith(b'\n'))

    def test_added_row_keeps_retained_unterminated_row_last(self):
        first=self.preview({'done_videos':{'enabled':False}});updater.apply(*first,first[3])
        self.path.write_bytes(self.path.read_bytes().rstrip(b'\r\n'));last=list(self.raw_rows(self.path.read_bytes()))[-1]
        previous=self.raw_rows(self.path.read_bytes())[last]
        prepared=self.preview({'done_videos':{'enabled':True}});rows=self.raw_rows(prepared[2]['verification.md'])
        self.assertEqual(list(rows)[-1],last);self.assertEqual(rows[last],previous)

    def test_repeated_changed_failure_history_is_idempotent(self):
        self.observe();change={'smoke_gates':{'pre_merge':'New pre-merge design'}}
        first=self.preview(change);updater.apply(*first,first[3]);raw=self.path.read_bytes()
        self.assertEqual(raw.decode().count('> | G1 |'),1)
        second=self.preview(change);self.assertNotIn('verification.md',second[2]);self.assertFalse(second[2])
        self.assertIsNone(updater.apply(*second,second[3]));self.assertEqual(raw,self.path.read_bytes())

    def test_legacy_fallback_and_duplicate_refusal(self):
        raw=self.path.read_bytes().decode();legacy=[]
        for line in raw.splitlines():
            if ROW.match(line):line='| '+' | '.join([cell.strip() for cell in line.strip('|').split('|')][:8])+' |'
            legacy.append(line)
        self.path.write_bytes(('\n'.join(legacy)+'\n').encode())
        prepared=self.preview({'done_videos':{'enabled':True}})
        self.assertIn('legacy_schema',str(updater.selective_explanations(prepared[1],prepared[2],{'done_videos':{}})))
        self.path.write_bytes(raw.encode()+self.raw_rows(raw.encode())['G1'].encode())
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.preview({'done_videos':{'enabled':True}})

    def test_typed_raw_recipe_change_is_not_hidden_by_same_display(self):
        before=copy.deepcopy(self.config);after=copy.deepcopy(before)
        before['operations']['smoke_gates']['pre_merge']='check | raw';after['operations']['smoke_gates']['pre_merge']='check / raw'
        text=initial_table(before,self.research)
        decision=updater.classify_gate_update(text,before,after,self.research,{'smoke_gates':{}})
        self.assertIn('plan_changed',decision['rows']['G1']['reasons']);self.assertNotIn('source_plan_misaligned',decision['rows']['G1']['reasons'])
        self.assertEqual(decision['rows']['A1']['action'],'retain')

    def test_malformed_modern_rows_refused_before_each_prepare_fallback(self):
        original=self.path.read_bytes()
        cases=[({'smoke_gates':{'required':True}},{}),
               ({'smoke_gates':{'exception':'Reviewed exception'}},{}),
               ({}, {'delivery_update':True}),
               ({'done_videos':{'enabled':True}}, {'assumptions_update':[]})]
        for changes,kwargs in cases:
            for column in (1,4,6):
                with self.subTest(changes=changes,kwargs=kwargs,column=column):
                    self.path.write_bytes(original);self.edit('G1',{column:'INVALID'})
                    before=self.snapshot()
                    with self.assertRaisesRegex(ValueError,'Invalid gate stage/required|Unknown gate result'):
                        updater.prepare(self.root,changes,selective_gates=True,**kwargs)
                    self.assertEqual(before,self.snapshot())

    def test_mixed_legacy_modern_rows_validate_before_any_fallback(self):
        original=self.path.read_bytes()
        for column in (1,4,6):
            self.path.write_bytes(original);self.edit('G1',{column:'INVALID'})
            text=self.path.read_bytes().decode();mixed=[]
            for line in text.splitlines(keepends=True):
                if ROW.match(line) and ROW.match(line)[1]=='G2':
                    line='| '+' | '.join([cell.strip() for cell in line.strip().strip('|').split('|')][:8])+' |\n'
                mixed.append(line)
            mixed=''.join(mixed)
            for kwargs in ({},{'runtime_changed':True},{'delivery':True},{'assumptions':True}):
                with self.subTest(column=column,kwargs=kwargs):
                    with self.assertRaisesRegex(ValueError,'Invalid gate stage/required|Unknown gate result'):
                        updater.classify_gate_update(mixed,self.config,self.config,self.research,{'smoke_gates':{'required':True}},**kwargs)
            self.path.write_bytes(mixed.encode());before=self.snapshot()
            with self.assertRaisesRegex(ValueError,'Invalid gate stage/required|Unknown gate result'):
                updater.prepare(self.root,{'done_videos':{'enabled':True}},selective_gates=True)
            self.assertEqual(before,self.snapshot())

    def test_valid_mixed_legacy_modern_rows_still_migrate_and_archive_failure(self):
        self.observe();text=self.path.read_bytes().decode();mixed=[]
        for line in text.splitlines(keepends=True):
            if ROW.match(line) and ROW.match(line)[1]=='G2':
                line='| '+' | '.join([cell.strip() for cell in line.strip().strip('|').split('|')][:8])+' |\n'
            mixed.append(line)
        self.path.write_bytes(''.join(mixed).encode())
        prepared=self.preview({'done_videos':{'enabled':True}})
        self.assertTrue(all(row['result']=='NOT RUN' for row in self.active(prepared).values()))
        self.assertIn('> | G1 |',prepared[2]['verification.md'].decode());self.assertIn('FAILED',prepared[2]['verification.md'].decode())
        self.assertIn('legacy_schema',str(updater.selective_explanations(prepared[1],prepared[2],{'done_videos':{}})))

    def test_broad_fallback_reasons_for_unmodeled_changes(self):
        for kwargs,reason in (({'delivery':True},'delivery_migration'),({'assumptions':True},'assumptions_changed'),({'runtime_changed':True},'runtime_changed')):
            decision=updater.classify_gate_update(self.path.read_text(),self.config,self.config,self.research,{},**kwargs)
            self.assertEqual(decision['mode'],'fallback');self.assertIn(reason,decision['reasons'])
        after=copy.deepcopy(self.config);after['operations']['smoke_gates']['exception']='Reviewed exception'
        self.assertIn('exception_changed',updater.classify_gate_update(self.path.read_text(),self.config,after,self.research,{})['reasons'])

    def test_wrong_digest_and_concurrent_edits_leave_factory_untouched(self):
        prepared=self.preview({'smoke_gates':{'post_merge':'Changed design'}});before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'digest'):updater.apply(*prepared,'0'*64)
        self.assertEqual(before,self.snapshot())
        self.path.write_bytes(self.path.read_bytes()+b'\nConcurrent note\n');before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):updater.apply(*prepared,prepared[3])
        self.assertEqual(before,self.snapshot())

    def test_captured_research_concurrent_change_is_rejected(self):
        prepared=self.preview({'smoke_gates':{'post_merge':'Changed design'}})
        path=self.root/'research.json';path.write_bytes(path.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'changed after preview'):updater.apply(*prepared,prepared[3])
        self.assertEqual(before,self.snapshot())

    def test_runtime_receipt_mixed_update_broad_fallback_and_provenance_preservation(self):
        self.observe();runtime=self.root/'dashboard/gates.py';runtime.write_bytes((ROOT/'scripts/fixtures/v1_17_gates.txt').read_bytes())
        manifest_path=self.root/'manifest.json';manifest=json.loads(manifest_path.read_text());manifest['contracts']['dashboard/gates.py']=digest(runtime.read_bytes());manifest_path.write_bytes(json.dumps(manifest).encode())
        provenance=(self.root/'upstream-provenance.json').read_bytes()
        prepared=self.preview({'smoke_gates':{'post_merge':'Changed design'}},gate_runtime=True,migration_receipt=True)
        self.assertEqual(self.active(prepared)['G1']['result'],'NOT RUN')
        self.assertIn('runtime_changed',str(updater.selective_explanations(prepared[1],prepared[2],{'smoke_gates':{}})))
        receipt=json.loads(prepared[2][updater.MIGRATION_RECEIPTS])['receipts'][0]
        self.assertEqual(receipt['scope'],'runtime-only');self.assertEqual([row['path'] for row in receipt['components']],['dashboard/gates.py'])
        updater.apply(*prepared,prepared[3]);self.assertEqual((self.root/'upstream-provenance.json').read_bytes(),provenance)

    def test_current_runtime_flag_does_not_itself_force_fallback(self):
        self.observe();prepared=self.preview({'done_videos':{'enabled':True}},gate_runtime=True,migration_receipt=True)
        self.assertNotIn('verification.md',prepared[2]);self.assertNotIn(updater.MIGRATION_RECEIPTS,prepared[2])

    def test_cli_explains_rows_without_exposing_values_in_explanation(self):
        changes=self.base/'changes.json';changes.write_text(json.dumps({'smoke_gates':{'post_merge':'private-design'}}))
        output=io.StringIO();before=self.snapshot()
        with patch.object(sys,'argv',['update_operations.py','--factory',str(self.root),'--operations',str(changes),'--selective-gates']),redirect_stdout(output):updater.main()
        self.assertEqual(before,self.snapshot());messages=[line for line in output.getvalue().splitlines() if line.startswith('GATE ')]
        self.assertTrue(any('RESET G3: plan_changed' in line and 'fields: plan.design' in line for line in messages));self.assertTrue(any('RETAIN A1:' in line for line in messages));self.assertNotIn('private-',str(messages))


if __name__=='__main__':unittest.main()
