"""Synthetic, offline scoped assessment and preview-first record tests."""
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
import re
from unittest.mock import patch
from scaffold import ROOT, render
from gates import gate_rows, assess
from scoped_assessment import assess_scope
from incremental_records import preview, apply
from gate_plan_status import compare

class IncrementalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'.software-factory';self.root.mkdir()
        config=json.loads((ROOT/'assets/example-config.json').read_text());research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
    def tearDown(self):self.temp.cleanup()
    def snapshot(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def task(self):return {'id':'T2','goal':'Synthetic change','owner':'owner','depends_on':['T1'],'acceptance_ids':['A1'],'allowed_paths':['src/file.py'],'status':'pending'}
    def scope(self):return {'purpose':'Synthetic change','gates':['A1'],'tasks':['T2']}
    def test_task_preview_apply_and_invalid_inputs(self):
        before=self.snapshot();root,name,old,new,token=preview(self.root,'task',self.task());self.assertEqual(before,self.snapshot())
        with self.assertRaises(ValueError):apply(root,name,old,new,token,'wrong')
        self.assertEqual(before,self.snapshot());apply(root,name,old,new,token,token)
        plan=json.loads((root/'task-plan.json').read_text());self.assertEqual(plan['tasks'][-1]['id'],'T2')
        with self.assertRaises(ValueError):preview(root,'task',self.task())
        for key,value in [('acceptance_ids',['A999']),('depends_on',['missing']),('allowed_paths',['../escape'])]:
            task=self.task();task['id']='T3';task[key]=value
            with self.assertRaises(ValueError):preview(root,'task',task)
    def test_concurrent_edit_rejects_digest_and_preserves_data(self):
        root,name,old,new,token=preview(self.root,'task',self.task())
        path=root/'task-plan.json';source=path.read_text();path.write_text(source+'\n')
        before=self.snapshot()
        with self.assertRaises(ValueError):apply(root,name,old,new,token,token)
        self.assertEqual(before,self.snapshot())

    def test_changed_contract_and_extra_file_block_apply(self):
        for mutation in ('contract','extra'):
            with self.subTest(mutation=mutation):
                root,name,old,new,token=preview(self.root,'task',self.task())
                path=root/('acceptance.md' if mutation=='contract' else 'unexpected.txt')
                original=path.read_bytes() if path.exists() else None
                path.write_bytes(b'changed')
                before=self.snapshot()
                with self.assertRaises(ValueError):apply(root,name,old,new,token,token)
                self.assertEqual(before,self.snapshot())
                if original is None:path.unlink()
                else:path.write_bytes(original)

    def test_cli_preview_prints_digest_without_writes(self):
        path=Path(self.temp.name)/'task.json';path.write_text(json.dumps(self.task()))
        before=self.snapshot()
        result=subprocess.run([sys.executable,str(ROOT/'scripts/incremental_records.py'),'--factory',str(self.root),'--kind','task','--input',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('REVIEW PLAN:',result.stdout)
        self.assertEqual(before,self.snapshot())
        token=re.search(r'REVIEW PLAN: ([0-9a-f]{64})',result.stdout).group(1)
        command=[sys.executable,str(ROOT/'scripts/incremental_records.py'),'--factory',str(self.root),'--kind','task','--input',str(path)]
        denied=subprocess.run(command+['--apply','--approve-plan','wrong'],capture_output=True,text=True)
        self.assertNotEqual(denied.returncode,0);self.assertEqual(before,self.snapshot())
        accepted=subprocess.run(command+['--apply','--approve-plan',token],capture_output=True,text=True)
        self.assertEqual(accepted.returncode,0,accepted.stderr)
        self.assertEqual(json.loads((self.root/'task-plan.json').read_text())['tasks'][-1]['id'],'T2')
    def test_gate_record_retains_prior_row_and_refuses_false_pass(self):
        data={'gate':'G1','result':'FAILED','revision':'subject','environment':'synthetic','evidence':'Synthetic observed failure','target':'artifact','checked_at':'2026-10-30T00:00:00Z','exit_status':'1'}
        root,name,old,new,token=preview(self.root,'gate',data);apply(root,name,old,new,token,token)
        text=(root/'verification.md').read_text();self.assertEqual(gate_rows(text)['G1']['result'],'FAILED');self.assertIn('> | G1 |',text)
        data['result']='PASSED';data['exit_status']='0'
        with self.assertRaises(ValueError):preview(root,'gate',data) # Unconfirmed design must not pass.
        data['evidence']='bad | injected'
        with self.assertRaises(ValueError):preview(root,'gate',data)

    def test_nonpassing_record_rejects_unicode_line_breaks_without_write(self):
        data={'gate':'G1','result':'FAILED','revision':'subject','environment':'synthetic','evidence':'bad'+chr(0x2028)+'injected','target':'artifact','checked_at':'','exit_status':''}
        before=self.snapshot()
        with self.assertRaises(ValueError):preview(self.root,'gate',data)
        self.assertEqual(before,self.snapshot())
        task=self.task();task['goal']='bad'+chr(0x2029)+'injected'
        with self.assertRaises(ValueError):preview(self.root,'task',task)
        self.assertEqual(before,self.snapshot())
    def test_scope_is_not_project_readiness_and_no_stale_evidence_carry(self):
        root,name,old,new,token=preview(self.root,'task',self.task());apply(root,name,old,new,token,token)
        result=assess_scope(root,self.scope(),'pre-merge','subject')
        self.assertEqual(result['assessment'],'SCOPED BLOCKED');self.assertTrue(result['problems'])
        self.assertIn('not project-wide readiness',result['notice'])
        self.assertTrue(assess(root,'pre-merge','subject'))
        with self.assertRaises(ValueError):assess_scope(root,{'purpose':'x','gates':['A999'],'tasks':['T2']},'pre-merge','subject')
        changed=self.scope();changed['gates']=['A1','A1']
        with self.assertRaises(ValueError):assess_scope(root,changed,'pre-merge','subject')
    def test_scope_identity_binds_task_definition(self):
        root,name,old,new,token=preview(self.root,'task',self.task());apply(root,name,old,new,token,token)
        first=assess_scope(root,self.scope(),'pre-merge','subject')['scope_id']
        path=root/'task-plan.json';plan=json.loads(path.read_text());plan['tasks'][-1]['goal']='changed';path.write_text(json.dumps(plan))
        self.assertNotEqual(first,assess_scope(root,self.scope(),'pre-merge','subject')['scope_id'])

    def test_task_acceptance_links_cannot_point_at_smoke_or_research_gates(self):
        root,name,old,new,token=preview(self.root,'task',self.task());apply(root,name,old,new,token,token)
        path=root/'task-plan.json';plan=json.loads(path.read_text());plan['tasks'][-1]['acceptance_ids']=['G1'];path.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError,'invalid acceptance links'):
            assess_scope(root,{'purpose':'Synthetic','gates':['G1'],'tasks':['T2']},'pre-merge','subject')

    def test_scope_rejects_cyclic_or_unknown_task_dependencies(self):
        path=self.root/'task-plan.json';original=json.loads(path.read_text())
        for dependency in ('T1','missing'):
            plan=json.loads(json.dumps(original));plan['tasks'][0]['depends_on']=[dependency]
            path.write_text(json.dumps(plan))
            with self.assertRaises(ValueError):
                assess_scope(self.root,{'purpose':'Synthetic','gates':['A1'],'tasks':['T1']},'pre-merge','subject')

    def test_scope_blocks_incomplete_transitive_dependency(self):
        path=self.root/'task-plan.json';plan=json.loads(path.read_text())
        first=plan['tasks'][0];first['status']='blocked'
        second=dict(first,id='T2',status='done',depends_on=[first['id']])
        third=dict(first,id='T3',status='done',depends_on=['T2'])
        plan['tasks'].extend([second,third]);path.write_text(json.dumps(plan))
        result=assess_scope(self.root,{'purpose':'Synthetic','gates':['A1'],'tasks':['T3']},'pre-merge','subject')
        self.assertEqual(result['assessment'],'SCOPED BLOCKED')
        self.assertIn('Task T2 has incomplete dependencies',result['problems'])

    def test_scoped_success_does_not_make_excluded_project_gates_pass(self):
        root,name,old,new,token=preview(self.root,'task',self.task());apply(root,name,old,new,token,token)
        path=root/'task-plan.json';plan=json.loads(path.read_text());plan['tasks'][0]['status']='done';plan['tasks'][-1]['status']='done'
        plan['events'].append({'id':'e1','task_id':'T2','timestamp':'2026-10-30T00:00:00Z','revision':'subject','environment':'synthetic','check':'fixture','result':'passed','evidence':'synthetic only','old_status':'pending','status':'done'})
        path.write_text(json.dumps(plan))
        path=root/'verification.md';lines=[]
        for line in path.read_text().splitlines():
            if any(line.startswith('| '+g+' |') for g in ('G1','G2','A1')):
                c=[v.strip() for v in line.strip().strip('|').split('|')]
                c[2:4]=['Synthetic check','synthetic'];c[5:]=['subject','PASSED','synthetic evidence','artifact','2026-10-30T00:00:00Z','0']
                line='| '+' | '.join(c)+' |'
            lines.append(line)
        # Add an additional required pre-merge row which must stay out of scope.
        lines.append('| X1 | pre-merge | other | synthetic | yes | | NOT RUN | | | | |')
        path.write_text('\n'.join(lines)+'\n')
        result=assess_scope(root,self.scope(),'pre-merge','subject')
        self.assertEqual(result['assessment'],'SCOPED ELIGIBLE')
        self.assertTrue(any(row['gate']=='X1' and row['result']=='NOT RUN' for row in result['out_of_scope']))
        self.assertTrue(assess(root,'pre-merge','subject'))
        self.assertEqual(assess_scope(root,self.scope(),'pre-merge','other')['assessment'],'SCOPED BLOCKED')

    def test_passed_waived_row_still_needs_concrete_observation(self):
        path=self.root/'verification.md'
        path.write_text(path.read_text().replace('| G1 | pre-merge |','| G1 | pre-merge |',1).replace('| yes | | NOT RUN |','| no | | NOT RUN |',1))
        data={'gate':'G1','result':'PASSED','revision':'subject','environment':'synthetic','evidence':'claim','target':'artifact','checked_at':'2026-10-30T00:00:00Z','exit_status':'0'}
        with self.assertRaises(ValueError):preview(self.root,'gate',data)
    def test_write_failure_keeps_existing_record(self):
        root,name,old,new,token=preview(self.root,'task',self.task());before=self.snapshot()
        with patch('incremental_records.os.replace',side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):apply(root,name,old,new,token,token)
        self.assertEqual(before,self.snapshot())

    def test_gate_plan_view_reports_missing_extra_and_drift_without_writes(self):
        path=self.root/'verification.md';lines=[]
        for line in path.read_text().splitlines():
            if line.startswith('| G2 |'):continue
            if line.startswith('| G1 |'):
                cells=[v.strip() for v in line.strip().strip('|').split('|')]
                cells[1]='post-merge';cells[2]='Synthetic changed check';line='| '+' | '.join(cells)+' |'
            lines.append(line)
        lines.append('| X1 | pre-merge | Other | local | yes | | NOT RUN | | | | |')
        path.write_text('\n'.join(lines)+'\n');before=self.snapshot()
        rows={r['gate']:r for r in compare(self.root)['gates']}
        self.assertIn('stage differs',rows['G1']['differences'])
        self.assertIn('design differs; inspect actual observation',rows['G1']['differences'])
        self.assertIn('missing',rows['G2']['differences']);self.assertIn('extra',rows['X1']['differences'])
        self.assertEqual(before,self.snapshot())

    def test_new_task_cannot_complete_a_preexisting_cycle(self):
        path=self.root/'task-plan.json';plan=json.loads(path.read_text())
        plan['tasks'][0]['depends_on']=['T2'];path.write_text(json.dumps(plan))
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Cyclic'):preview(self.root,'task',self.task())
        self.assertEqual(before,self.snapshot())

    def test_gate_preview_accepts_realistic_concrete_record_without_changing_waiver(self):
        path=self.root/'verification.md';lines=[]
        for line in path.read_text().splitlines():
            if line.startswith('| G1 |'):
                cells=[v.strip() for v in line.strip().strip('|').split('|')]
                cells[2]='Synthetic inspected check';cells[4]='no';line='| '+' | '.join(cells)+' |'
            lines.append(line)
        path.write_text('\n'.join(lines)+'\n')
        data={'gate':'G1','result':'PASSED','revision':'subject','environment':'synthetic','evidence':'actual synthetic observation','target':'artifact','checked_at':'2026-10-30T00:00:00Z','exit_status':'0'}
        root,name,old,new,token=preview(self.root,'gate',data);apply(root,name,old,new,token,token)
        row=gate_rows(path.read_text())['G1']
        self.assertEqual((row['required'],row['result']),('no','PASSED'))
        self.assertIn('> | G1 |',path.read_text())

if __name__=='__main__':unittest.main()
