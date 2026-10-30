"""Structured recipe/trigger regressions in disposable offline factories only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from gates import assess, gate_rows, problems, requirements, waivers
from integrity import check, digest
from operations import controls, operations, smoke_design
from scaffold import ROOT, render, validate
from update_operations import PRIOR_GATE_RUNTIME, apply, prepare


class StructuredGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.root=self.base/'.software-factory';self.root.mkdir()
        self.config=json.loads((ROOT/'assets/example-config.json').read_text())
        self.research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.write()

    def tearDown(self):self.tmp.cleanup()

    def write(self):
        self.files=render(self.config,self.research)
        for name,body in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def spec(self,web=False):
        return {'command':['python','smoke.py','argument | remains data'],
                'environment':'isolated synthetic fixture','env_names':['BASE_URL'] if web else [],
                'target':{'kind':'web' if web else 'artifact',
                          'value':'http://127.0.0.1:7000' if web else 'synthetic-package-v1',
                          'base_url_env':'BASE_URL' if web else None}}

    def edit(self,text,gate,values):
        lines=[]
        for line in text.splitlines():
            if line.startswith('| '+gate+' |'):
                cells=[v.strip() for v in line.strip('|').split('|')]
                for index,value in values.items():cells[index]=value
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        return '\n'.join(lines)

    def observed(self,text,gate,revision='subject-S',target='synthetic-package-v1'):
        return self.edit(text,gate,{5:revision,6:'PASSED',7:'SYNTHETIC supplied record only; no application run',
                                   8:target,9:'2026-10-30T07:00:00Z',10:'0'})

    def old_runtime(self):
        manifest=json.loads((self.root/'manifest.json').read_text())
        for name,expected in PRIOR_GATE_RUNTIME.items():
            body=(ROOT/('scripts/fixtures/v1_5_1_'+name[:-3]+'.txt')).read_bytes()
            self.assertEqual(digest(body),expected)
            (self.root/'dashboard'/name).write_bytes(body)
            manifest['contracts']['dashboard/'+name]=digest(body)
        (self.root/'manifest.json').write_text(json.dumps(manifest))
        check(self.root,quiet=True)

    def test_old_defaults_keep_existing_controls_and_release_video_behavior(self):
        self.assertNotIn('checks',controls(self.config)['smoke_gates'])
        self.assertNotIn('triggers',controls(self.config)['done_videos'])
        self.config['operations']={'done_videos':{'enabled':True}}
        expected=requirements(self.config,self.research)
        self.assertIn('V1',expected);self.assertNotIn('V2',expected)

    def test_structured_plan_is_argv_data_with_no_execution_or_fabricated_target(self):
        marker=self.base/'never-created'
        spec=self.spec();spec['command']=[sys.executable,'-c',f'open({str(marker)!r},"w").write("bad")']
        self.config['operations']={'smoke_gates':{'checks':{'G1':spec}}}
        validate(self.config);self.write()
        rows=gate_rows(self.files['verification.md'])
        self.assertEqual(rows['G1']['design'],smoke_design(spec))
        self.assertEqual(rows['G1']['environment'],spec['environment'])
        self.assertEqual(rows['G1']['target'],'')
        self.assertEqual(rows['G1']['result'],'NOT RUN')
        result=subprocess.run([sys.executable,str(ROOT/'scripts/gates.py'),'--factory',str(self.root),'--plan'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(marker.exists())

    def test_invalid_structured_fields_are_refused_without_mutation(self):
        bad=[]
        for key,value in (('command','python smoke.py'),('command',[]),('command',[True]),
                          ('environment','bad\nlabel'),('env_names',['A','A']),('env_names',['KEY=value']),
                          ('env_names',{'SECRET':'do-not-store-values'})):
            spec=self.spec();spec[key]=value;bad.append({'G1':spec})
        for target in ({'kind':'web','value':'https://user:invented@fixture.invalid','base_url_env':None},
                       {'kind':'web','value':'https://fixture.invalid?token=invented','base_url_env':None},
                       {'kind':'artifact','value':'fixture','base_url_env':'BASE_URL'},
                       {'kind':'web','value':'http://127.0.0.1','base_url_env':'UNDECLARED'}):
            spec=self.spec();spec['target']=target;bad.append({'G3':spec})
        bad.extend(([],{'A1':self.spec()},{'G1':{'blocking':False}}))
        before=self.snapshot()
        for checks in bad:
            with self.subTest(checks=checks):
                self.config['operations']={'smoke_gates':{'checks':checks}}
                with self.assertRaises(ValueError):validate(self.config)
                self.assertEqual(before,self.snapshot())

    def test_required_records_must_match_structured_command_environment_and_target(self):
        spec=self.spec();self.config['operations']={'smoke_gates':{'checks':{'G1':spec}}};self.write()
        expected=requirements(self.config,self.research)
        text=self.observed(self.files['verification.md'],'G1')
        self.assertFalse(any(v.startswith('G1 ') for v in problems(text,'pre-merge','subject-S',expected)))
        for index,value in ((2,'different command'),(3,'another environment'),(8,'another artifact')):
            changed=self.edit(text,'G1',{index:value})
            self.assertTrue(any(v.startswith('G1 ') for v in problems(changed,'pre-merge','subject-S',expected)))
        waived=self.edit(text,'G1',{4:'no',6:'FAILED',2:'unexecuted choice'})
        self.assertFalse(any(v.startswith('G1 ') for v in problems(waived,'pre-merge','subject-S',expected)))
        self.assertEqual(waivers(waived,'pre-merge'),['G1 WAIVED (recorded FAILED)'])
        missing='\n'.join(line for line in waived.splitlines() if not line.startswith('| G1 |'))
        self.assertIn('Missing expected gate row: G1',problems(missing,'pre-merge','subject-S',expected))

    def test_structured_g3_target_works_for_nonweb_and_refuses_conflicting_globals(self):
        spec=self.spec();self.config['operations']={'smoke_gates':{'checks':{'G3':spec}}};self.write()
        text=self.observed(self.files['verification.md'],'G3')
        (self.root/'verification.md').write_text(text)
        self.assertEqual(assess(self.root,'post-merge','subject-S','synthetic-package-v1'),[])
        self.assertTrue(assess(self.root,'post-merge','subject-S','other-artifact'))
        for extra in ({'target_kind':'web'},{'deployed_url':'different-target'},
                      {'target_kind':'no_release','post_merge_applicability':'not_applicable',
                       'post_merge_rationale':'Review-only task','accepted_by':'Synthetic owner'}):
            self.config['operations']['smoke_gates'].update(extra)
            with self.assertRaises(ValueError):validate(self.config)
            self.config['operations']['smoke_gates']={'checks':{'G3':spec}}

    def test_explicit_video_triggers_generate_independent_staged_rows(self):
        for enabled,triggers,expected in ((True,['pre_merge_preview'],{'V2'}),
                                         (True,['post_g3_release'],{'V1'}),
                                         (True,['pre_merge_preview','post_g3_release'],{'V1','V2'}),
                                         (False,['pre_merge_preview','post_g3_release'],set())):
            self.config['operations']={'done_videos':{'enabled':enabled,'triggers':triggers}}
            self.write();rows=gate_rows(self.files['verification.md'])
            self.assertEqual({g for g in rows if g.startswith('V')},expected)
            for gate in expected:
                self.assertEqual(rows[gate]['stage'],'pre-merge' if gate=='V2' else 'post-merge')
                self.assertEqual(rows[gate]['result'],'NOT RUN')
        for triggers in ('pre_merge_preview',[],['unknown'],['post_g3_release','post_g3_release'],[True]):
            self.config['operations']={'done_videos':{'enabled':True,'triggers':triggers}}
            with self.assertRaises(ValueError):validate(self.config)

    def test_preview_does_not_certify_release_and_missing_moved_rows_are_errors(self):
        self.config['operations']={'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']}}
        self.write();expected=requirements(self.config,self.research);text=self.files['verification.md']
        for gate in ('G1','G2','A1','V2'):
            text=self.edit(text,gate,{2:'Observed synthetic fixture procedure',3:'isolated fixture'})
            text=self.observed(text,gate)
        self.assertEqual(problems(text,'pre-merge','subject-S',expected),[])
        self.assertIn('V1 is NOT RUN',problems(text,'post-merge','subject-S',expected,'synthetic-package-v1'))
        for gate in ('V1','V2'):
            missing='\n'.join(line for line in text.splitlines() if not line.startswith('| '+gate+' |'))
            self.assertIn('Missing expected gate row: '+gate,problems(missing,'pre-merge','subject-S',expected))
        self.assertTrue(problems(self.edit(text,'V2',{1:'post-merge'}),'pre-merge','subject-S',expected))

    def test_preview_only_is_valid_with_explicit_no_release_scope(self):
        self.config['operations']={'done_videos':{'enabled':True,'triggers':['pre_merge_preview']},
            'smoke_gates':{'target_kind':'no_release','post_merge_applicability':'not_applicable',
                           'post_merge_rationale':'Internal preview only','accepted_by':'Synthetic owner'}}
        validate(self.config);self.write()
        self.assertNotIn('V1',requirements(self.config,self.research))
        self.assertEqual(gate_rows(self.files['verification.md'])['G3']['result'],'NOT APPLICABLE')
        self.config['operations']['done_videos']['triggers'].append('post_g3_release')
        with self.assertRaises(ValueError):validate(self.config)

    def test_trigger_update_retires_only_managed_preview_and_preserves_waivers_history(self):
        self.config['operations']={'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']}}
        self.write();path=self.root/'verification.md'
        text=self.edit(path.read_text(),'V1',{4:'no',6:'FAILED'})
        text=self.edit(text,'V2',{4:'no',6:'FAILED'});path.write_text(text)
        root,old,new,plan=prepare(self.root,{'done_videos':{'triggers':['post_g3_release']}})
        apply(root,old,new,plan,plan);rows=gate_rows(path.read_text())
        self.assertNotIn('V2',rows);self.assertEqual(rows['V1']['required'],'no')
        self.assertIn('> | V2 |',path.read_text());self.assertIn('FAILED',path.read_text())

    def test_known_runtime_upgrade_is_explicit_and_copied_dashboard_works(self):
        self.old_runtime();before=self.snapshot()
        changes={'done_videos':{'enabled':True,'triggers':['pre_merge_preview','post_g3_release']},
                 'smoke_gates':{'checks':{'G1':self.spec()}}}
        with self.assertRaisesRegex(ValueError,'gate-runtime'):prepare(self.root,changes)
        self.assertEqual(before,self.snapshot())
        root,old,new,plan=prepare(self.root,changes,gate_runtime=True)
        self.assertEqual(before,self.snapshot())
        backup=apply(root,old,new,plan,plan)
        for name in PRIOR_GATE_RUNTIME:self.assertEqual((backup/'dashboard'/name).read_bytes(),before['dashboard/'+name])
        result=subprocess.run([sys.executable,str(root/'dashboard/dashboard.py'),'--output',str(self.base/'overview.html')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);check(root,quiet=True)

    def test_custom_runtime_is_not_overwritten_and_new_plan_rejects_concurrent_edit(self):
        self.old_runtime();path=self.root/'dashboard/gates.py';body=path.read_bytes()
        path.write_bytes(body+b'\n# Synthetic custom gate\n')
        manifest=json.loads((self.root/'manifest.json').read_text());manifest['contracts']['dashboard/gates.py']=digest(path.read_bytes());(self.root/'manifest.json').write_text(json.dumps(manifest))
        before=self.snapshot();changes={'done_videos':{'enabled':True,'triggers':['pre_merge_preview']}}
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):prepare(self.root,changes,gate_runtime=True)
        self.assertEqual(before,self.snapshot())
        path.write_bytes(body);manifest['contracts']['dashboard/gates.py']=digest(body);(self.root/'manifest.json').write_text(json.dumps(manifest))
        root,old,new,plan=prepare(self.root,changes,gate_runtime=True)
        (root/'tools.json').write_text('{"synthetic":"concurrent edit"}')
        with self.assertRaises(ValueError):apply(root,old,new,plan,plan)
        self.assertEqual(path.read_bytes(),body)

    def test_existing_recipe_update_preserves_compatible_old_runtime_without_gate_opt_in(self):
        self.old_runtime();before=self.snapshot()
        root,old,new,plan=prepare(self.root,{'done_videos':{'composition':'Existing editor'}})
        self.assertFalse(any(name.startswith('dashboard/') for name in new))
        apply(root,old,new,plan,plan)
        for name in PRIOR_GATE_RUNTIME:self.assertEqual((root/'dashboard'/name).read_bytes(),before['dashboard/'+name])
        result=subprocess.run([sys.executable,str(root/'dashboard/dashboard.py'),'--output',str(self.base/'overview.html')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_v12_gate_migration_adds_dependency_with_backup_and_no_config_defaults(self):
        self.old_runtime();manifest=json.loads((self.root/'manifest.json').read_text())
        source=(ROOT/'scripts/fixtures/v1_2_operations.txt').read_bytes()
        (self.root/'dashboard/operations.py').write_bytes(source)
        manifest['contracts']['dashboard/operations.py']=digest(source)
        (self.root/'dashboard/recipes.py').unlink();manifest['contracts'].pop('dashboard/recipes.py')
        (self.root/'manifest.json').write_text(json.dumps(manifest));check(self.root,quiet=True)
        config=(self.root/'config.json').read_bytes()
        root,old,new,plan=prepare(self.root,{},gate_runtime=True)
        self.assertNotIn('config.json',new)
        backup=apply(root,old,new,plan,plan)
        self.assertEqual((root/'config.json').read_bytes(),config)
        self.assertEqual(json.loads((backup/'added-files.json').read_text()),['dashboard/recipes.py'])
        result=subprocess.run([sys.executable,str(root/'dashboard/dashboard.py'),'--output',str(self.base/'overview.html')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_manual_preview_extra_is_preserved_without_structured_trigger(self):
        text=(self.root/'verification.md').read_text()
        row=next(line for line in text.splitlines() if line.startswith('| A1 |')).replace('| A1 |','| V2 |')
        text+='\n'+row;path=self.root/'verification.md';path.write_text(text)
        root,old,new,plan=prepare(self.root,{'done_videos':{'enabled':True}})
        apply(root,old,new,plan,plan)
        self.assertIn('V2',gate_rows(path.read_text()))
        self.assertIn('> | V2 |',path.read_text())

    def test_reserved_v1_cannot_be_used_as_pre_merge_preview_even_when_not_selected(self):
        expected=requirements(self.config,self.research);text=self.files['verification.md']
        row=next(line for line in text.splitlines() if line.startswith('| A1 |')).replace('| A1 |','| V1 |')
        text+='\n'+row
        self.assertIn('Reserved release video V1 must remain post-merge',problems(text,'pre-merge','subject-S',expected))


if __name__=='__main__':unittest.main()
