"""Offline delivery regressions: fail closed; no application checks or live actions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from gates import assess, gate_rows, problems, requirements
from operations import controls, operations
from scaffold import ROOT, render

class GateTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(self.config,self.research)
    def rows(self):
        return self.files['verification.md']
    def mark(self,text,gate,revision='r1',result='PASSED',target='fixture-artifact',time='2026-10-30T00:00:00+00:00'):
        out=[]
        for line in text.split('\n'):
            if line.startswith('| '+gate+' |'):
                c=[v.strip() for v in line.strip().strip('|').split('|')]
                c[2]='Observed synthetic critical-path check; not a live command'
                c[3]='isolated fixture';c[5]=revision;c[6]=result;c[7]='SYNTHETIC observation artifact, no real application result'
                c[8]=target;c[9]=time;c[10]='0'
                line='| '+' | '.join(c)+' |'
            out.append(line)
        return '\n'.join(out)
    def all_pass(self,stage='pre-merge',text=None):
        text=text if text is not None else self.rows()
        for gate,spec in requirements(self.config,self.research).items():
            if spec['stage']==stage and spec['applicability']=='applicable':
                text=self.mark(text,gate)
        return text
    def edit(self,text,gate,index,value):
        lines=[]
        for line in text.split('\n'):
            if line.startswith('| '+gate+' |'):
                cells=[c.strip() for c in line.strip().strip('|').split('|')]
                cells[index]=value;line='| '+' | '.join(cells)+' |'
            lines.append(line)
        return '\n'.join(lines)
    def check(self,text,stage='pre-merge',revision='r1',target=None):
        return problems(text,stage,revision,requirements(self.config,self.research),target)
    def write(self,path,text=None):
        for name,body in self.files.items():
            p=path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body.encode('utf-8'))
        if text is not None:(path/'verification.md').write_text(text,encoding='utf-8')
    def test_default_artifacts_plan_smoke_targeted_and_acceptance(self):
        rows=gate_rows(self.rows())
        self.assertEqual(set(rows),{'G1','G2','G3','A1'})
        self.assertTrue(all(r['result']=='NOT RUN' for r in rows.values()))
        self.assertTrue(controls(self.config)['smoke_gates']['required'])
        self.assertIn('G1',self.files['.claude/skills/factory-verify/SKILL.md'])
        self.assertIn('G3',self.files['.claude/skills/factory-release/SKILL.md'])
    def test_not_run_blocks_both_stages(self):
        self.assertTrue(self.check(self.rows()))
        self.assertTrue(self.check(self.rows(),'post-merge',target='fixture-artifact'))
    def test_pre_merge_does_not_need_future_post_evidence(self):
        text=self.all_pass()
        self.assertEqual(self.check(text),[])
        self.assertEqual(gate_rows(text)['G3']['result'],'NOT RUN')
        self.assertTrue(self.check(text,'post-merge',target='fixture-artifact'))
    def test_expected_gate_rows_cannot_be_removed_or_moved_accidentally(self):
        for gate in ('G1','G2','A1','G3'):
            text=self.all_pass()
            removed='\n'.join(l for l in text.split('\n') if not l.startswith('| '+gate+' |'))
            self.assertTrue(self.check(removed),gate)
            other='post-merge' if gate!='G3' else 'pre-merge'
            self.assertTrue(self.check(self.edit(text,gate,1,other)),gate)
    def test_failed_blocked_missing_and_stale_observations_block(self):
        text=self.all_pass()
        for gate in ('G1','G2','A1'):
            for status in ('FAILED','BLOCKED','NOT RUN','NOT APPLICABLE'):
                self.assertTrue(self.check(self.edit(text,gate,6,status)),(gate,status))
            self.assertTrue(self.check(self.edit(text,gate,5,'old-revision')))
            for index in (2,3,7,8,9,10):
                self.assertTrue(self.check(self.edit(text,gate,index,'')),(gate,index))
            self.assertTrue(self.check(self.edit(text,gate,10,'1')))
            self.assertTrue(self.check(self.edit(text,gate,9,'2026-10-30')))
            self.assertTrue(self.check(self.edit(text,gate,2,'unconfirmed: choose actual command')))
    def test_manual_checks_are_explicit_and_timestamped(self):
        text=self.all_pass()
        self.assertEqual(self.check(self.edit(text,'A1',10,'manual')),[])
    def test_duplicate_and_malformed_rows_rejected(self):
        text=self.all_pass()
        row=next(l for l in text.split('\n') if l.startswith('| G1 |'))
        with self.assertRaises(ValueError):self.check(text+'\n'+row)
        with self.assertRaises(ValueError):self.check(text.replace(row,'| G1 | pre-merge |'))
        with self.assertRaises(ValueError):self.check(self.edit(text,'G1',4,'maybe'))
        with self.assertRaises(ValueError):self.check(self.edit(text,'G1',6,'SUCCESS'))
    def test_additional_required_check_is_evaluated(self):
        text=self.all_pass()
        row=next(l for l in text.split('\n') if l.startswith('| A1 |')).replace('| A1 |','| X1 |')
        text+='\n'+row.replace('| PASSED |','| NOT RUN |')
        self.assertTrue(any('X1' in p for p in self.check(text)))
    def test_post_confirmation_requires_exact_revision_and_actual_target(self):
        text=self.all_pass('post-merge')
        self.assertEqual(self.check(text,'post-merge',target='fixture-artifact'),[])
        self.assertTrue(self.check(text,'post-merge',target='other-target'))
        self.assertTrue(self.check(text,'post-merge'))
        self.assertTrue(self.check(text,'post-merge',revision='new-revision',target='fixture-artifact'))
        self.assertTrue(self.check(self.edit(text,'G3',6,'FAILED'),'post-merge',target='fixture-artifact'))
    def test_nonweb_artifact_uses_actual_target_without_a_url(self):
        self.config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'fixture-artifact'}}
        self.files=render(self.config,self.research)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.write(root,self.all_pass('post-merge'))
            self.assertEqual(assess(root,'post-merge','r1','fixture-artifact'),[])
            self.assertTrue(assess(root,'post-merge','r1','another-artifact'))
    def test_no_release_exclusion_requires_named_rationale(self):
        self.config['operations']={'smoke_gates':{'target_kind':'no_release','post_merge_applicability':'not_applicable'}}
        with self.assertRaises(ValueError):operations(self.config)
        self.config['operations']['smoke_gates'].update(post_merge_rationale='Internal review only; no merge/deploy/publish target in this task',accepted_by='Synthetic authorized owner')
        self.files=render(self.config,self.research)
        self.assertEqual(self.check(self.rows(),'post-merge'),[])
        self.assertTrue(self.check(self.edit(self.rows(),'G3',7,''),'post-merge'))
        self.config['operations']['done_videos']={'enabled':True}
        with self.assertRaises(ValueError):operations(self.config)
    def test_optional_smoke_defaults_need_no_extra_exception_or_approval(self):
        self.config['operations']={'smoke_gates':{'required':False}}
        self.files=render(self.config,self.research)
        self.assertFalse(operations(self.config)['smoke_gates']['required'])
        rows=gate_rows(self.rows())
        for gate in ('G1','G2','G3'):self.assertEqual(rows[gate]['required'],'no')
        self.assertEqual(rows['A1']['required'],'yes')
        self.assertEqual(self.check(self.mark(self.rows(),'A1')),[])
    def test_explicit_optional_rows_are_waived_without_hiding_failures(self):
        from gates import waivers
        for flag in ('no','false','n','NO'):
            text=self.edit(self.all_pass(),'G2',6,'FAILED')
            text=self.edit(text,'G2',4,flag)
            self.assertEqual(self.check(text),[])
            self.assertEqual(waivers(text,'pre-merge'),['G2 WAIVED (recorded FAILED)'])
        text=self.edit(self.rows(),'G3',4,'no')
        self.assertEqual(self.check(text,'post-merge'),[])
    def test_cli_reports_waivers_as_waivers_not_test_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            text=self.edit(self.all_pass(),'G2',4,'no')
            text=self.edit(text,'G2',6,'NOT RUN');self.write(root,text)
            r=subprocess.run([sys.executable,str(ROOT/'scripts/gates.py'),'--factory',d,'--stage','pre-merge','--revision','r1'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn('G2 WAIVED (recorded NOT RUN)',r.stdout)
            self.assertIn('ELIGIBLE WITH WAIVERS',r.stdout)
            self.assertNotIn('PASSED',r.stdout)
    def test_post_only_acceptance_does_not_block_pre_release(self):
        self.config['acceptance'].append('Observe the actually released artifact')
        self.config['operations']={'smoke_gates':{'check_stages':{'A2':{'stage':'post-merge','rationale':'Requires the release action first'}}}}
        self.files=render(self.config,self.research)
        self.assertEqual(self.check(self.all_pass()),[])
        self.assertTrue(self.check(self.mark(self.rows(),'G3'),'post-merge',target='fixture-artifact'))
        self.config['operations']['smoke_gates']['check_stages']['A99']={'stage':'pre-merge','rationale':'Invalid fixture'}
        with self.assertRaises(ValueError):render(self.config,self.research)
    def test_enabled_video_handoff_and_post_smoke_order(self):
        self.config['operations']={'done_videos':{'enabled':True,'scope':'Narrated synthetic release demo'}}
        self.files=render(self.config,self.research)
        self.assertIn('V1',gate_rows(self.rows()))
        self.assertEqual(self.check(self.all_pass()),[])
        text=self.mark(self.mark(self.rows(),'G3'),'V1',time='2026-10-30T00:01:00+00:00')
        self.assertEqual(self.check(text,'post-merge',target='fixture-artifact'),[])
        early=self.mark(text,'V1',time='2026-10-29T23:59:00+00:00')
        self.assertTrue(self.check(early,'post-merge',target='fixture-artifact'))
        self.assertTrue(self.check(self.edit(text,'V1',6,'BLOCKED'),'post-merge',target='fixture-artifact'))
    def test_cli_integrity_policy_synchronization_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.write(root)
            command=[sys.executable,str(ROOT/'scripts/gates.py'),'--factory',d,'--stage','pre-merge','--revision','r1']
            run=lambda:subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(run().returncode,1)
            (root/'verification.md').write_text(self.all_pass(),encoding='utf-8')
            self.assertEqual(run().returncode,0)
            (root/'policy.md').write_text('Changed contract',encoding='utf-8')
            self.assertNotEqual(run().returncode,0)
    def test_plan_mode_is_write_free(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.write(root)
            before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            result=subprocess.run([sys.executable,str(ROOT/'scripts/gates.py'),'--factory',d,'--plan'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('| G1 |',result.stdout)
            self.assertEqual(before,{p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()})
    def test_release_only_research_check_is_not_a_pre_action_dependency(self):
        from datetime import date
        self.research.update(status='complete',summary='Synthetic fixture, not actual research')
        self.research['coverage']={phase:{'status':'applicable' if phase=='release' else 'not_applicable','reason':'Synthetic phase assessment'} for phase in ('intake','plan','build','verify','release','learn')}
        self.research['sources']=[{'id':'S1','url':'https://example.com/synthetic','accessed_on':date.today().isoformat(),'kind':'synthetic fixture','version_scope':'fixture only','observation':'Synthetic observation','status':'read'}]
        self.research['practices']=[{'id':'P1','decision':'selected','source_ids':['S1'],'phases':['release'],'relevance':'Fixture requirement','compatibility':'Fixture only','tradeoff':'Synthetic test','instruction':'Inspect the actual released artifact','check':'Observe the released synthetic artifact'}]
        self.files=render(self.config,self.research)
        self.assertEqual(requirements(self.config,self.research)['R1']['stage'],'post-merge')
        self.assertEqual(self.check(self.all_pass()),[])
        self.assertTrue(any('R1' in p for p in self.check(self.mark(self.rows(),'G3'),'post-merge',target='fixture-artifact')))
    def test_greenfield_has_an_explicit_design_without_invented_executable_commands(self):
        self.assertEqual(self.config['test_commands'],[])
        self.assertIn('success/failure assertions',self.config['tasks'][0]['goal'])
        self.assertIn('representative critical path',gate_rows(self.rows())['G1']['design'])
        self.assertTrue(self.check(self.rows()))

    def test_mixed_phase_research_can_explicitly_wait_for_release(self):
        self.test_release_only_research_check_is_not_a_pre_action_dependency()
        self.research['practices'][0]['phases']=['verify','release']
        self.research['coverage']['verify']={'status':'applicable','reason':'Synthetic planning and release fixture'}
        self.assertEqual(requirements(self.config,self.research)['R1']['stage'],'pre-merge')
        self.config['operations']={'smoke_gates':{'check_stages':{'R1':{'stage':'post-merge','rationale':'Requires the actual released artifact; Verify plans it only'}}}}
        self.files=render(self.config,self.research)
        self.assertEqual(requirements(self.config,self.research)['R1']['stage'],'post-merge')
        self.assertEqual(self.check(self.all_pass()),[])
        self.assertTrue(any('R1' in p for p in self.check(self.mark(self.rows(),'G3'),'post-merge',target='fixture-artifact')))

    def test_preview_video_and_release_video_are_independent_with_waivers(self):
        self.config['operations']={'done_videos':{'enabled':True,'scope':'Synthetic shipped demo'}}
        self.files=render(self.config,self.research)
        text=self.all_pass()
        preview=next(line for line in text.splitlines() if line.startswith('| A1 |')).replace('| A1 |','| V2 |').replace('| PASSED |','| NOT RUN |')
        text+='\n'+preview
        self.assertTrue(any('V2' in p for p in self.check(text)))
        text=self.mark(text,'V2')
        self.assertEqual(self.check(text),[])
        self.assertTrue(any('V1' in p for p in self.check(self.mark(text,'G3'),'post-merge',target='fixture-artifact')))
        text=self.edit(text,'V2',4,'no');text=self.edit(text,'V2',6,'FAILED')
        self.assertEqual(self.check(text),[])
        text=self.edit(self.mark(text,'G3'),'V1',4,'no')
        self.assertEqual(self.check(text,'post-merge',target='fixture-artifact'),[])
    def test_unresolved_actual_targets_never_confirm_release(self):
        for placeholder in ('unknown','TBD','not configured','unconfirmed: target pending','none','n/a'):
            text=self.mark(self.rows(),'G3',target=placeholder)
            self.assertTrue(self.check(text,'post-merge',target=placeholder),placeholder)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.write(root,self.mark(self.rows(),'G3',target='unknown'))
            self.assertTrue(assess(root,'post-merge','r1','unknown'))
            self.write(root,self.mark(self.rows(),'G3',target='fixture-artifact'))
            self.assertTrue(assess(root,'post-merge','r1','fixture-artifact'))
            self.config['operations']={'smoke_gates':{'target_kind':'artifact'}}
            self.files=render(self.config,self.research)
            self.write(root,self.mark(self.rows(),'G3',target='fixture-artifact'))
            self.assertEqual(assess(root,'post-merge','r1','fixture-artifact'),[])

    def test_late_independent_failures_and_new_subject_require_truthful_regating(self):
        self.config['acceptance'] += ['Synthetic retry property','Synthetic persisted state','Synthetic failure recovery']
        self.files=render(self.config,self.research)
        text=self.all_pass();self.assertEqual(self.check(text),[])
        historical=[]
        for gate in ('A3','A4'):
            text=self.mark(text,gate,result='FAILED')
            historical += ['> '+line for line in text.splitlines() if line.startswith('| '+gate+' |')]
        failures=self.check(text)
        self.assertTrue(any('A3 is FAILED' in row for row in failures))
        self.assertTrue(any('A4 is FAILED' in row for row in failures))
        text+='\n## Synthetic historical repros\n'+'\n'.join(historical)
        for gate in ('A3','A4'):text=self.mark(text,gate,revision='repaired-subject')
        self.assertTrue(self.check(text,revision='repaired-subject'))  # Other required observations still old.
        for gate,spec in requirements(self.config,self.research).items():
            if spec['stage']=='pre-merge':text=self.mark(text,gate,revision='repaired-subject')
        self.assertEqual(self.check(text,revision='repaired-subject'),[])
        self.assertIn('> | A3 |',text);self.assertIn('> | A4 |',text)
        self.assertIn('| FAILED |',text)

if __name__=='__main__':unittest.main(verbosity=2)
