"""Run the documented named-contract example only in disposable synthetic factories."""
import copy
import json
from pathlib import Path
import re
import tempfile
import unittest

from gates import gate_rows, initial_table, requirements
from incremental_records import task_change
from integrity import check, digest, LIVING
from recover_factory import apply, dumps, prepare, rawhash, verify_output
from scaffold import ROOT, render


class ReviewedRegistrationExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name);self.base=self.parent/'accepted';self.source=self.parent/'reviewed';self.output=self.parent/'snapshot'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['operations']={'smoke_gates':{'required':False}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(self.config,self.research)
        # A project-specific map was already explicitly accepted as an immutable contract.
        # Its format is fixture data, not a new builder schema or an executed test.
        files['test-map.json']=dumps({'A1':{'check':'SYNTHETIC existing criterion check; UNEXECUTED'}})
        prior=next(line for line in files['verification.md'].splitlines() if line.startswith('| A1 |'))
        cells=[value.strip() for value in prior.strip('|').split('|')]
        cells[3]='synthetic fixture';cells[5:]=['old-subject','FAILED','SYNTHETIC prior failure','synthetic artifact','2026-10-30T00:00:00Z','1']
        self.failure='| '+' | '.join(cells)+' |'
        files['verification.md']=files['verification.md'].replace(prior,self.failure)
        manifest=json.loads(files['manifest.json']);manifest['contracts']['test-map.json']=digest(files['test-map.json'])
        files['manifest.json']=dumps(manifest)
        for root in (self.base,self.source):
            for name,body in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        self.pin=rawhash((self.base/'manifest.json').read_bytes())
        old_wording=self.config['acceptance'][0]
        self.config['acceptance'][0]='SYNTHETIC refinement: filtering preserves the selected sort order'
        (self.source/'config.json').write_text(dumps(self.config),encoding='utf-8')
        path=self.source/'acceptance.md';path.write_text(path.read_text(encoding='utf-8').replace('- A1: '+old_wording,'- A1: '+self.config['acceptance'][0]),encoding='utf-8')
        path=self.source/'project-brief.md';path.write_text(path.read_text(encoding='utf-8').replace('- '+old_wording,'- '+self.config['acceptance'][0]),encoding='utf-8')
        (self.source/'test-map.json').write_text(dumps({'A1':{'check':'SYNTHETIC filtering and retained-sort check; UNEXECUTED'}}),encoding='utf-8')
        new_row=next(line for line in initial_table(self.config,self.research).splitlines() if line.startswith('| A1 |'))
        verification=self.source/'verification.md'
        verification.write_text(verification.read_text(encoding='utf-8').replace(self.failure,new_row)+'\n## Prior gate observation (not current evidence)\n> '+self.failure+'\n',encoding='utf-8')
        guide=(ROOT/'references/recovery.md').read_text(encoding='utf-8')
        section=guide.split('**Example decisions for an existing acceptance/map contract.**',1)[1].split('For **manifest-only adoption**',1)[0]
        self.decisions=json.loads(re.search(r'```json\n(.*?)\n```',section,re.S).group(1))

    def snapshot(self,root):
        return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def plan(self,decisions=None):
        return prepare(self.source,self.base,self.output,self.pin,'SYNTHETIC independently accepted baseline',self.decisions if decisions is None else decisions)

    def test_documented_decisions_preview_apply_and_verify_preserve_source_and_history(self):
        baseline=self.snapshot(self.base);source=self.snapshot(self.source)
        self.assertEqual(source['manifest.json'],baseline['manifest.json'])
        result=self.plan()
        names={'config.json','acceptance.md','project-brief.md','test-map.json'}
        self.assertEqual(result['deltas'],{'accept_changed':names,'register':set(),'remove':set()})
        self.assertEqual(source,self.snapshot(self.source));self.assertEqual(baseline,self.snapshot(self.base))
        self.assertFalse(self.output.exists());self.assertFalse((self.parent/'.factory-recovery-backups').exists())
        backup=apply(result,result['plan'],True);self.assertTrue(verify_output(self.output,backup,result['plan']))
        self.assertEqual(source,self.snapshot(self.source));self.assertEqual(baseline,self.snapshot(self.base))
        self.assertEqual(source,self.snapshot(backup/'source'))
        output=self.snapshot(self.output)
        self.assertEqual({k:v for k,v in output.items() if k!='manifest.json'},{k:v for k,v in source.items() if k!='manifest.json'})
        old=json.loads(source['manifest.json']);new=json.loads(output['manifest.json'])
        self.assertEqual({name for name in old['contracts'] if old['contracts'][name]!=new['contracts'][name]},names)
        for name in names:self.assertEqual(new['contracts'][name],digest(output[name]))
        for name in LIVING:self.assertEqual(output[name],source[name])
        self.assertEqual(output['policy.md'],baseline['policy.md'])
        for name in ('acceptance.md','project-brief.md'):self.assertIn(self.config['acceptance'][0].encode(),output[name])
        rows=gate_rows(output['verification.md'].decode('utf-8'))
        self.assertEqual(rows['A1']['result'],'NOT RUN');self.assertIn(('> '+self.failure).encode(),output['verification.md'])
        for name in ('G1','G2','G3'):self.assertEqual(rows[name]['required'],'no')
        check(self.output,quiet=True)

    def test_example_requires_exact_delta_decisions_and_review_digest(self):
        source=self.snapshot(self.source);baseline=self.snapshot(self.base)
        incomplete=copy.deepcopy(self.decisions);incomplete['accept_changed']=[row for row in incomplete['accept_changed'] if row['path']!='config.json']
        with self.assertRaises(ValueError):self.plan(incomplete)
        result=self.plan()
        with self.assertRaisesRegex(ValueError,'exact reviewed plan digest'):apply(result,'0'*64,True)
        self.assertFalse(self.output.exists());self.assertFalse((self.parent/'.factory-recovery-backups').exists())
        self.assertEqual(source,self.snapshot(self.source));self.assertEqual(baseline,self.snapshot(self.base))

    def test_prose_only_id_does_not_register_acceptance_or_validate_a_task(self):
        path=self.source/'acceptance.md';path.write_bytes(path.read_bytes()+b'\n- A999: SYNTHETIC prose-only claim\n')
        source=self.snapshot(self.source)
        self.assertNotIn('A999',requirements(self.config,self.research))
        plan=json.loads(source['task-plan.json']);item=copy.deepcopy(plan['tasks'][0]);item.update(id='T999',status='pending',acceptance_ids=['A999'])
        with self.assertRaisesRegex(ValueError,'existing acceptance IDs'):task_change(plan,self.config,item)
        self.assertEqual(source,self.snapshot(self.source));self.assertFalse(self.output.exists())


if __name__=='__main__':unittest.main()
