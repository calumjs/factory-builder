"""Trace-only link regressions against synthetic, offline factories."""
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from acceptance_links import assess_links
from gates import assess, post_target_problems
from scaffold import ROOT, render


class AcceptanceLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.factory=self.base/'factory';self.factory.mkdir();self.sidecar=self.base/'trace.json'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'synthetic-artifact','post_merge':'Synthetic artifact confirmation'}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(config,research)
        for name,body in self.files.items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
        self.mark('G3',{'design':'Synthetic observed check','environment':'fixture','revision':'S1','result':'PASSED','evidence':'synthetic reference','target':'synthetic-artifact','checked_at':'2026-01-01T00:00:00Z','exit_status':'0'})
        self.record={'schema_version':1,'gate':'G3','subject':'S1','target':'synthetic-artifact','links':[{'acceptance_id':'A1','result':'NOT RUN','evidence':'','observed_at':''}]}
        self.write()

    def tearDown(self):self.tmp.cleanup()
    def write(self):self.sidecar.write_text(json.dumps(self.record),encoding='utf-8')
    def snapshot(self):return {p.relative_to(self.base).as_posix():p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
    def mark(self,gate,changes):
        path=self.factory/'verification.md';keys=('gate','stage','design','environment','required','revision','result','evidence','target','checked_at','exit_status');out=[]
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.startswith('| '+gate+' |'):
                cells=[x.strip() for x in line.strip().strip('|').split('|')];row=dict(zip(keys,cells));row.update(changes)
                line='| '+' | '.join(row[key] for key in keys)+' |'
            out.append(line)
        path.write_text('\n'.join(out)+'\n',encoding='utf-8')
    def assess(self,subject='S1',target='synthetic-artifact'):
        return assess_links(self.factory,self.sidecar,subject,target)

    def test_valid_reference_without_observation_is_unconfirmed_and_read_only(self):
        before=self.snapshot();result=self.assess()
        self.assertEqual(before,self.snapshot());self.assertIn('NOT READINESS OR PROOF',result['notice'])
        self.assertEqual(result['links'][0]['linked_claim']['state'],'UNCONFIRMED')
        self.assertEqual(result['scope'],['A1']);self.assertTrue(result['g3']['recorded_positive_claim'])

    def test_post_merge_target_is_observed_explicitly_and_diagnostic_is_actionable(self):
        before=self.snapshot()
        missing=assess(self.factory,'post-merge','S1')
        self.assertEqual(len(missing),1);self.assertIn('actual --target',missing[0])
        self.assertNotIn('kind is unconfirmed',missing[0])
        self.assertEqual(assess(self.factory,'post-merge','S1','synthetic-artifact'),[])
        mismatch=assess(self.factory,'post-merge','S1','private-target-sentinel')
        self.assertEqual(mismatch,['Actual post-release target differs from the configured target'])
        cmd=[sys.executable,str(ROOT/'scripts/gates.py'),'--factory',str(self.factory),'--stage','post-merge','--revision','S1']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stderr);self.assertIn('actual --target',result.stdout)
        confirmed=subprocess.run(cmd+['--target','synthetic-artifact'],capture_output=True,text=True)
        self.assertEqual(confirmed.returncode,0,confirmed.stdout+confirmed.stderr)
        self.assertEqual(before,self.snapshot())

    def test_missing_target_and_unconfirmed_kind_are_distinct_without_value_disclosure(self):
        issues=post_target_problems('unconfirmed','private-plan-sentinel',None)
        self.assertEqual(len(issues),2)
        self.assertIn('kind is unconfirmed',issues[0]);self.assertIn('actual --target',issues[1])
        self.assertNotIn('private-plan-sentinel',' '.join(issues))
        self.assertEqual(post_target_problems('unconfirmed','private-plan-sentinel','observed'),issues[:1])

    def test_optional_post_merge_gate_does_not_require_target_or_gain_positive_claim(self):
        self.mark('G3',{'required':'no','result':'FAILED'})
        self.assertEqual(assess(self.factory,'post-merge','S1'),[])
        output=self.assess()
        self.assertEqual(output['g3']['state'],'WAIVED')
        self.assertFalse(output['g3']['recorded_positive_claim'])

    def test_canonical_acceptance_id_cannot_be_duplicated_across_stages_or_missing(self):
        path=self.factory/'verification.md';original=path.read_text(encoding='utf-8')
        row=next(line for line in original.splitlines() if line.startswith('| A1 |'))
        path.write_text(original+row.replace('| pre-merge |','| post-merge |')+'\n',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Duplicate gate: A1'):self.assess()
        path.write_text(original.replace(row+'\n',''),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'missing or duplicate acceptance ID'):self.assess()

    def test_linked_pass_never_promotes_failed_stale_or_waived_canonical_row(self):
        self.record['links'][0].update(result='PASSED',evidence='private-ref-sentinel',observed_at='2026-01-01T00:00:00Z');self.write()
        for required,result,revision in (('yes','FAILED','S1'),('yes','PASSED','old'),('no','FAILED','S1')):
            with self.subTest(required=required,result=result,revision=revision):
                self.mark('A1',{'required':required,'result':result,'revision':revision})
                output=self.assess();row=output['links'][0]
                self.assertEqual(row['canonical']['recorded_result'],result);self.assertEqual(row['canonical']['revision'],revision)
                self.assertEqual(row['canonical']['state'],'WAIVED' if required=='no' else result)
                self.assertEqual(row['linked_claim']['state'],'SUPPLIED CLAIM — NOT VERIFIED')
                self.assertNotIn('private-ref-sentinel',json.dumps(output))

    def test_mismatch_and_nonpositive_g3_are_not_promoted(self):
        self.assertTrue(self.assess(subject='other')['binding_errors'])
        self.assertTrue(self.assess(target='other')['binding_errors'])
        self.record['subject']='S2';self.write();mismatch=self.assess()
        self.assertEqual(mismatch['requested_context']['subject'],'S1')
        self.assertEqual(mismatch['recorded_envelope']['subject'],'S2')
        self.assertTrue(mismatch['binding_errors']);self.assertFalse(mismatch['g3']['recorded_positive_claim'])
        self.record['subject']='S1';self.write()
        for required,result in (('yes','FAILED'),('yes','BLOCKED'),('yes','NOT RUN'),('no','FAILED')):
            with self.subTest(required=required,result=result):
                self.mark('G3',{'required':required,'result':result})
                output=self.assess();self.assertFalse(output['g3']['recorded_positive_claim'])
                self.assertEqual(output['g3']['state'],'WAIVED' if required=='no' else result)

    def test_invalid_schema_ids_evidence_and_timestamps_refused(self):
        base=json.loads(json.dumps(self.record))
        variants=[{**base,'schema_version':True},{**base,'schema_version':2},{**base,'extra':'x'},
                  {**base,'links':[base['links'][0],base['links'][0]]},
                  {**base,'links':[{**base['links'][0],'acceptance_id':'A999'}]},
                  {**base,'links':[{**base['links'][0],'result':'PASSED'}]},
                  {**base,'links':[{**base['links'][0],'result':'PASSED','evidence':'todo','observed_at':'2026-01-01T00:00:00Z'}]},
                  {**base,'links':[{**base['links'][0],'observed_at':'2026-01-01T00:00:00'}]}]
        for record in variants:
            with self.subTest(record=record):
                self.record=record;self.write()
                with self.assertRaises(ValueError):self.assess()
        self.sidecar.write_text('{"schema_version":1,"schema_version":1}',encoding='utf-8')
        with self.assertRaises(ValueError):self.assess()
        self.sidecar.write_bytes(b'x'*2_000_001)
        with self.assertRaises(ValueError):self.assess()

    def test_no_release_is_never_a_positive_g3_claim(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['operations']={'smoke_gates':{'target_kind':'no_release','post_merge_applicability':'not_applicable','post_merge_rationale':'Synthetic no-release scope','accepted_by':'fixture owner'}}
        research=json.loads((ROOT/'assets/example-research.json').read_text());other=self.base/'no-release';other.mkdir()
        for name,body in render(config,research).items():
            path=other/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
        result=assess_links(other,self.sidecar,'S1','synthetic-artifact')
        self.assertEqual(result['g3']['applicability'],'not_applicable');self.assertFalse(result['g3']['recorded_positive_claim'])

    def test_wrong_acceptance_stage_and_redirected_record_are_refused(self):
        self.mark('A1',{'stage':'post-merge'})
        with self.assertRaises(ValueError):self.assess()
        self.mark('A1',{'stage':'pre-merge'})
        link=self.base/'link.json';real=Path.lstat
        def redirected(path,*args,**kwargs):
            if path==link:return SimpleNamespace(st_mode=stat.S_IFLNK|0o600)
            return real(path,*args,**kwargs)
        with patch.object(Path,'lstat',redirected),self.assertRaises(ValueError):
            assess_links(self.factory,link,'S1','synthetic-artifact')

    @unittest.skipUnless(sys.platform=='win32','Windows namespace regression')
    def test_windows_device_namespace_cannot_bypass_factory_containment(self):
        from integrity import digest
        internal=self.factory/'registered-trace.json';internal.write_bytes(self.sidecar.read_bytes())
        manifest=self.factory/'manifest.json';value=json.loads(manifest.read_text());value['contracts']['registered-trace.json']=digest(internal.read_bytes());manifest.write_text(json.dumps(value))
        for prefix in ('\\\\?\\','\\\\.\\'):
            alias=prefix+str(internal)
            with self.subTest(alias=prefix),self.assertRaisesRegex(ValueError,'Device namespace'):
                assess_links(self.factory,alias,'S1','synthetic-artifact')

    def test_changed_inputs_and_inside_factory_are_refused(self):
        from acceptance_links import bounded
        calls=[]
        def change(path):
            data=bounded(path);calls.append(str(path))
            if Path(path)==self.sidecar and calls.count(str(path))==1:self.sidecar.write_text(self.sidecar.read_text()+' ')
            return data
        with patch('acceptance_links.bounded',side_effect=change),self.assertRaisesRegex(ValueError,'changed'):
            self.assess()
        with self.assertRaises(ValueError):assess_links(self.factory,self.factory/'verification.md','S1','synthetic-artifact')

    def test_oversized_factory_input_is_refused_before_any_json_parse(self):
        from integrity import digest
        config=self.factory/'config.json';config.write_bytes(b' '*2_000_000+b'{}')
        manifest=self.factory/'manifest.json';data=json.loads(manifest.read_text());data['contracts']['config.json']=digest(config.read_bytes());manifest.write_text(json.dumps(data))
        with patch('acceptance_links.strict_json',side_effect=AssertionError('must not parse')) as parser:
            with self.assertRaises(ValueError):self.assess()
        parser.assert_not_called()

    def test_nonregular_manifest_and_inventory_limit_are_refused(self):
        manifest=self.factory/'manifest.json';manifest.unlink();manifest.mkdir()
        with self.assertRaises(ValueError):self.assess()
        manifest.rmdir();manifest.write_text(self.files['manifest.json'],encoding='utf-8')
        with patch('acceptance_links.MAX_ENTRIES',2),self.assertRaises(ValueError):self.assess()

    def test_invalid_utf8_living_records_refuse_without_mutation(self):
        for name in ('learning-log.md','release-handoff.md'):
            with self.subTest(name=name):
                path=self.factory/name;original=path.read_bytes();path.write_bytes(b'\xff')
                before=self.snapshot()
                with self.assertRaisesRegex(ValueError,'valid UTF-8'):self.assess()
                cmd=[sys.executable,str(ROOT/'scripts/acceptance_links.py'),'--factory',str(self.factory),'--record',str(self.sidecar),'--subject','S1','--target','synthetic-artifact']
                result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,2)
                self.assertEqual(before,self.snapshot());path.write_bytes(original)

    def test_deeply_nested_policy_refuses_safely_without_writes(self):
        from integrity import digest
        path=self.factory/'policy.md';text=path.read_text(encoding='utf-8')
        start=text.index('```json\n',text.index('## Proposed autonomy and review controls'))+len('```json\n')
        self.assertEqual(text[start],'{')
        path.write_text(text[:start+1]+'"unused":'+'['*15000+'0'+']'*15000+','+text[start+1:],encoding='utf-8')
        manifest=self.factory/'manifest.json';value=json.loads(manifest.read_text());value['contracts']['policy.md']=digest(path.read_bytes());manifest.write_text(json.dumps(value))
        before=self.snapshot()
        cmd=[sys.executable,str(ROOT/'scripts/acceptance_links.py'),'--factory',str(self.factory),'--record',str(self.sidecar),'--subject','S1','--target','synthetic-artifact']
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,2);self.assertIn('policy controls are malformed',result.stderr)
        self.assertNotIn('Traceback',result.stderr);self.assertEqual(before,self.snapshot())

    def test_windows_reparse_attributes_are_refused_even_when_not_a_symlink(self):
        real=Path.lstat
        def lstat(path,*args,**kwargs):
            if path==self.sidecar:return SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_file_attributes=0x400)
            return real(path,*args,**kwargs)
        with patch.object(Path,'lstat',lstat),self.assertRaises(ValueError):self.assess()

    def test_cli_exit_codes_are_trace_only(self):
        cmd=[sys.executable,str(ROOT/'scripts/acceptance_links.py'),'--factory',str(self.factory),'--record',str(self.sidecar),'--subject','S1','--target','synthetic-artifact']
        result=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('NOT READINESS OR PROOF',result.stdout)
        mismatch=subprocess.run(cmd[:-1]+['other'],capture_output=True,text=True);self.assertEqual(mismatch.returncode,1)
        self.record['links'][0]['acceptance_id']='A999';self.write()
        unknown=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(unknown.returncode,2)
        self.assertIn('Unknown, malformed, missing or duplicate acceptance ID',unknown.stderr)
        self.sidecar.write_text('{broken');invalid=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(invalid.returncode,2)

    def test_cli_help_does_not_create_bytecode_in_fresh_install(self):
        scripts=self.base/'installed-scripts'
        shutil.copytree(ROOT/'scripts',scripts,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        before={p.relative_to(scripts).as_posix():p.read_bytes() for p in scripts.rglob('*') if p.is_file()}
        env=dict(os.environ);env.pop('PYTHONDONTWRITEBYTECODE',None)
        result=subprocess.run([sys.executable,str(scripts/'acceptance_links.py'),'--help'],capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(before,{p.relative_to(scripts).as_posix():p.read_bytes() for p in scripts.rglob('*') if p.is_file()})

if __name__=='__main__':unittest.main()
