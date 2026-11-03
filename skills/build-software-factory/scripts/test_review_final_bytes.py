"""Bounded post-review polish: adoption bytes, builder identities and CI errors."""
import json
import subprocess
import sys
import unittest

import review_records as rr
import test_review_migration as migration
import test_review_records as fixtures
from ci_evidence import assess_ci
from operations import operations
from scaffold import ROOT
import update_operations as updater


class ReviewFinalBytesTests(unittest.TestCase):
    def test_adoption_preserves_bom_and_every_existing_byte_including_trailing_crlf(self):
        for bom in (b'',b'\xef\xbb\xbf'):
            for tail in (b'',b'\r\n\r\n'):
                with self.subTest(bom=bool(bom),tail=bool(tail)):
                    fixture=migration.ReviewMigrationTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
                    path=fixture.root/'release-handoff.md'
                    raw=bom+path.read_bytes().replace(b'\n',b'\r\n').rstrip(b'\r\n')+tail
                    path.write_bytes(raw);before=fixture.snapshot();prepared=fixture.prepare()
                    proposed=prepared[2]['release-handoff.md']
                    self.assertEqual(fixture.snapshot(),before);self.assertTrue(proposed.startswith(raw))
                    self.assertEqual(proposed[:len(raw)],raw);self.assertEqual(rr.parse(proposed.decode('utf-8-sig')),rr.empty())
                    backup=updater.apply(*prepared,prepared[-1]);self.assertEqual((backup/'release-handoff.md').read_bytes(),raw)
                    self.assertEqual(path.read_bytes(),proposed);self.assertEqual(fixture.prepare()[2],{})

    def test_original_and_closing_builders_are_both_excluded_when_names_differ(self):
        config=fixtures.configuration();old=fixtures.supplied_round(config)
        old['builder']['identity']='builder-original';old['reviews'][0]['verdict']='request_changes'
        old['reviews'][0]['findings']=[{'id':'F1','severity':'major','claim':'Synthetic claim','evidence':'synthetic source','verification':None}]
        body=rr.section({'schema_version':1,'selected_round':'round1','rounds':[old]})
        for checker in ('builder-original','builder-closing','third-checker'):
            new=fixtures.supplied_round(config,'round2');new['builder']['identity']='builder-closing'
            new['resolutions']=[{'round_id':'round1','review_id':'review1','finding_id':'F1','reviewer':checker,
                                'disposition':'refuted','evidence':'Synthetic concrete reproduction','reason':'Synthetic source refutes the claim'}]
            supplied=rr.append_round(body,new).decode();policy=operations(config)['review']
            problems=rr.assessment(supplied,policy,new['policy_sha256'],'S1')
            self.assertEqual(bool(problems),checker!='third-checker')
            self.assertEqual(rr.assessment(supplied,{**policy,'independent':False},new['policy_sha256'],'S1'),[])

    def test_omitted_independence_retains_legacy_false_while_recommended_example_is_true(self):
        config=fixtures.configuration();config['operations']['review']={'record_schema':1,'required_approvals':1}
        self.assertIs(operations(config)['review']['independent'],False)
        recommended=json.loads((ROOT/'assets/example-review-config.json').read_bytes())
        self.assertIs(operations(recommended)['review']['independent'],True)

    def test_review_preview_reports_retained_bom_without_false_first_line_change(self):
        fixture=fixtures.ReviewFactoryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        path=fixture.root/'release-handoff.md';raw=b'\xef\xbb\xbf'+path.read_bytes();path.write_bytes(raw)
        input_path=fixture.root.parent/'synthetic-round.json';input_path.write_bytes(json.dumps(fixtures.supplied_round(fixture.config)).encode())
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/incremental_records.py'),'--factory',str(fixture.root),
                               '--kind','review','--input',str(input_path)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('UTF-8 BOM: retained',result.stdout)
        first=raw.decode('utf-8-sig').splitlines()[0]
        self.assertNotIn('-'+first+'\n',result.stdout);self.assertNotIn('+'+first+'\n',result.stdout)
        self.assertNotIn('\ufeff',result.stdout);self.assertEqual(path.read_bytes(),raw)

    def test_separate_storage_malformed_ledger_is_actionable_error_without_private_values(self):
        fixture=fixtures.ReviewFactoryTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        repo=fixture.root.parent;hooks=repo/'empty-hooks';hooks.mkdir()
        def git(*args):
            result=subprocess.run(['git','-c','core.autocrlf=false','-c','core.hooksPath='+str(hooks),'-c','user.name=Synthetic fixture',
                                   '-c','user.email=fixture@example.invalid','-C',str(repo),*args],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
        def commit():git('add','--all');git('commit','-qm','Synthetic review snapshot');return git('rev-parse','HEAD')
        git('init','-q');subject=commit();path=fixture.root/'release-handoff.md'
        path.write_bytes(path.read_bytes().replace(b'"schema_version": 1',b'"schema_version": "PRIVATE_FIXTURE_SENTINEL"'))
        storage=commit();before=path.read_bytes()
        with self.assertRaisesRegex(ValueError,'storage snapshot is malformed') as caught:assess_ci(repo,'factory',subject,storage,'pre-merge')
        self.assertIn('preserve both exact snapshots',str(caught.exception));self.assertNotIn('PRIVATE_FIXTURE_SENTINEL',str(caught.exception))
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/ci_evidence.py'),'--repo',str(repo),'--factory','factory',
                               '--subject',subject,'--storage',storage,'--stage','pre-merge'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stdout);error=json.loads(result.stderr)
        self.assertEqual(error['assessment'],'error');self.assertIn('review_records.py --factory',error['error'])
        self.assertNotIn('PRIVATE_FIXTURE_SENTINEL',result.stderr);self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
