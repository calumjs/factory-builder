"""Inactive-example/local diagnostics only; no GitHub, workflow or worker execution."""
import contextlib
import copy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest

from gates import assess
from integrity import check, digest
from readiness import watcher
from scaffold import ROOT, check_factory, render, validate
from scoped_assessment import assess_scope
import run
import update_operations as updater


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.factory=self.base/'.software-factory'
        self.config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        self.config['operations']={'autonomy':{'mode':'bounded','max_items_per_hour':3,'allowed_submitters':['synthetic-author']},
            'issue_intake':{'mode':'continuous','status':'enabled','github_scope':'SYNTHETIC/example','mechanism':'polling','cadence':'120'}}
        self.research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        self.policy={'repository':'SYNTHETIC/example','ready_label':'ready','excluded_labels':['blocked']}
        self.issue_rows=[{'id':'42','title':'SYNTHETIC','submitter':'synthetic-author','created_at':'2026-01-01T00:00:00Z','labels':['ready'],'depends_on':[]}]
        self.policy_path=self.base/'reviewed policy.json';self.issues_path=self.base/'issues.json'
        self.policy_path.write_text(json.dumps(self.policy),encoding='utf-8')
        self.issues_path.write_text(json.dumps(self.issue_rows),encoding='utf-8')
        self.write_factory()
        self.example=(ROOT/'assets/templates/scheduling/factory-run.example.yml').read_text(encoding='utf-8')

    def write_factory(self):
        for name,body in render(self.config,self.research).items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix():p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def preflight(self):
        snippet=textwrap.dedent(self.example.split("<<'PY'\n",1)[1].split('\n          PY',1)[0])
        snippet=snippet.replace('".builder/skills/build-software-factory/scripts"',repr(str(ROOT/'scripts')))
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B','-',str(self.policy_path)],input=snippet,cwd=self.base,
                              capture_output=True,text=True)
        self.assertEqual(self.snapshot(),before)
        return result

    def selection(self, admission_path=None):
        line=next(line.strip() for line in self.example.splitlines() if line.strip().startswith('python -B .builder/'))
        parts=shlex.split(line);parts[0]=sys.executable;parts[2]=str(ROOT/'scripts/run.py')
        argv=[]
        replacements={'$RUNNER_TEMP/issues.json':str(self.issues_path),'$ISSUE_POLICY_PATH':str(self.policy_path)}
        for part in parts:
            if part=='${admission_args[@]}':
                if admission_path is not None:argv+=['--admission-snapshot',str(admission_path)]
            else:argv.append(replacements.get(part,part))
        before=self.snapshot();result=subprocess.run(argv,cwd=self.base,capture_output=True,text=True)
        self.assertEqual(self.snapshot(),before)
        return result

    def test_exact_example_preflight_and_select_supply_matching_policy(self):
        preflight=self.preflight();self.assertEqual(preflight.returncode,0,preflight.stderr)
        self.assertEqual(preflight.stdout.strip(),self.policy['repository'])
        result=self.selection();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([row['id'] for row in json.loads(result.stdout)['issues']['eligible']],['42'])
        self.assertIn('gh issue list --repo "$ISSUE_REPOSITORY"',self.example)
        self.assertIn('--limit 1000',self.example)
        self.assertIn('Empty depends_on below is unverified',self.example)
        self.assertIn('headless pass not configured',self.example)
        self.assertFalse((self.base/'.github').exists());self.assertFalse((self.base/'.factory-runs').exists())

    def test_preflight_rejects_wrong_scope_missing_policy_and_ambiguous_schema(self):
        for value in ({**self.policy,'repository':'OTHER/project'}, {**self.policy,'extra':'PRIVATE-SENTINEL'},
                      {k:v for k,v in self.policy.items() if k!='ready_label'}):
            self.policy_path.write_text(json.dumps(value),encoding='utf-8')
            result=self.preflight();self.assertNotEqual(result.returncode,0)
            self.assertIn('policy/schema and configured repository must agree',result.stderr)
            self.assertNotIn('PRIVATE-SENTINEL',result.stderr+result.stdout)
        self.policy_path.write_text('{"repository":"OTHER/project",'+json.dumps(self.policy)[1:],encoding='utf-8')
        self.assertNotEqual(self.preflight().returncode,0)
        self.policy_path.unlink();self.assertNotEqual(self.preflight().returncode,0)

    def test_select_rechecks_repository_and_supplied_labels(self):
        self.assertEqual(self.preflight().returncode,0)
        self.policy_path.write_text(json.dumps({**self.policy,'repository':'OTHER/project'}),encoding='utf-8')
        result=self.selection();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['issues']['eligible'],[])
        self.assertIn('does not match',json.loads(result.stdout)['issues']['rejected'][0]['reason'])
        self.policy_path.write_text(json.dumps(self.policy),encoding='utf-8')
        self.issue_rows[0]['labels'].append('blocked');self.issues_path.write_text(json.dumps(self.issue_rows),encoding='utf-8')
        self.assertEqual(json.loads(self.selection().stdout)['issues']['eligible'],[])

    def test_conditional_admission_argument_requires_actual_supplied_snapshot(self):
        from test_admission_review import fixture
        self.config,snapshot,self.issue_rows,self.policy=fixture(datetime.now(timezone.utc))
        self.write_factory();self.policy_path.write_text(json.dumps(self.policy),encoding='utf-8')
        self.issues_path.write_text(json.dumps(self.issue_rows),encoding='utf-8')
        self.assertEqual(self.preflight().returncode,0)
        missing=json.loads(self.selection().stdout)
        self.assertEqual(missing['issues']['eligible'],[])
        self.assertIn('snapshot is required',' '.join(missing['admission_review']['problems']))
        path=self.base/'supplied observations.json';path.write_text(json.dumps(snapshot),encoding='utf-8')
        result=self.selection(path);self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([r['id'] for r in json.loads(result.stdout)['issues']['eligible']],['42'])
        self.assertIn('if [[ -n "$ADMISSION_SNAPSHOT_PATH" ]]',self.example)

    def test_freeform_labels_keep_design_state_but_warn_and_do_not_enable_selection(self):
        for label in ('active','running','planned','PRIVATE-SENTINEL'):
            with self.subTest(label=label):
                self.config['operations']['issue_intake']['status']=label;before=copy.deepcopy(self.config)
                validate(self.config);result=watcher(self.config)
                self.assertEqual(result['state'],'configured_unverified');self.assertEqual(result['liveness'],'unverified')
                warning=next(row for row in result['diagnostics'] if 'issue_intake.status to equal enabled' in row)
                self.assertNotIn(label,warning);self.assertEqual(self.config,before)
                self.write_factory();selected=self.selection()
                self.assertEqual(json.loads(selected.stdout)['issues']['eligible'],[])
                with self.assertRaisesRegex(ValueError,'explicitly enabled'):run.schedule_text(self.factory,self.config,'cron')
        for label in ('enabled',' Enabled '):
            self.config['operations']['issue_intake']['status']=label;self.write_factory()
            self.assertFalse(any('status to equal enabled' in x for x in watcher(self.config)['diagnostics']))
            self.assertEqual([r['id'] for r in json.loads(self.selection().stdout)['issues']['eligible']],['42'])
        self.config['operations']['issue_intake']['status']='disabled'
        self.assertEqual(watcher(self.config)['state'],'disabled_design')

    def test_integrity_wording_does_not_claim_gate_table_validation(self):
        path=self.factory/'verification.md';text=path.read_text(encoding='utf-8')
        line=next(row for row in text.splitlines() if row.startswith('| G1 |'))
        path.write_text(text+'\n'+line+'\n',encoding='utf-8');before=self.snapshot()
        for operation in (lambda:check(self.factory),lambda:check_factory(self.factory)):
            output=io.StringIO()
            with contextlib.redirect_stdout(output):operation()
            self.assertEqual(output.getvalue().count('PASS:'),1)
            self.assertIn('Gate tables require separate',output.getvalue())
            self.assertNotIn('valid basic structure',output.getvalue())
        with self.assertRaisesRegex(ValueError,'Duplicate gate'):assess(self.factory,'pre-merge','SYNTHETIC')
        with self.assertRaisesRegex(ValueError,'Duplicate gate'):
            assess_scope(self.factory,{'purpose':'SYNTHETIC','gates':['A1'],'tasks':['T1']},'pre-merge','SYNTHETIC')
        self.assertEqual(self.snapshot(),before)

    def install_prior_helpers(self, custom=False):
        manifest=json.loads((self.factory/'manifest.json').read_bytes())
        for name,expected in updater.PRE_CONSISTENCY_CONTEXT.items():
            data=(ROOT/'scripts/fixtures'/('pre_consistency_'+name[:-3]+'.txt')).read_bytes()
            self.assertEqual(digest(data),expected)
            if custom and name=='readiness.py':data+=b'\n# custom synthetic runtime\n'
            relative='dashboard/'+name;(self.factory/relative).write_bytes(data);manifest['contracts'][relative]=digest(data)
        (self.factory/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')

    def test_known_prior_copies_preserved_or_explicitly_migrated_with_exact_backup(self):
        self.install_prior_helpers();before=self.snapshot()
        self.assertEqual(updater.prepare(self.factory,{})[2],{})
        root,old,new,plan=updater.prepare(self.factory,{},context_runtime=True)
        self.assertEqual(set(new),{'dashboard/readiness.py','dashboard/integrity.py','manifest.json'})
        self.assertEqual(self.snapshot(),before)
        with self.assertRaises(ValueError):updater.apply(root,old,new,plan,'wrong')
        self.assertEqual(self.snapshot(),before)
        backup=updater.apply(root,old,new,plan,plan)
        self.assertEqual({p.relative_to(backup).as_posix():p.read_bytes() for p in backup.rglob('*') if p.is_file()},
                         {name:before[name] for name in new})
        after=self.snapshot()
        self.assertTrue(all(after[name]==body for name,body in before.items() if name not in new))
        result=subprocess.run([sys.executable,'-B',str(self.factory/'dashboard/dashboard.py'),
            '--output',str(self.base/'overview.json'),'--format','json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((self.base/'overview.json').read_bytes())['context']['watcher'],watcher(self.config))

    def test_admission_compatible_prior_warning_copy_is_not_silently_upgraded(self):
        from test_admission_review import fixture
        self.config,_,_,_=fixture();self.write_factory();self.install_prior_helpers();before=self.snapshot()
        self.assertEqual(updater.prepare(self.factory,{})[2],{})
        self.assertEqual(self.snapshot(),before)
        self.assertIn('dashboard/readiness.py',updater.prepare(self.factory,{},context_runtime=True)[2])

    def test_custom_prior_copy_refuses_context_migration_without_writes(self):
        self.install_prior_helpers(custom=True);before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'Customized/unsupported'):updater.prepare(self.factory,{},context_runtime=True)
        self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
