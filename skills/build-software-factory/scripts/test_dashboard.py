"""Behavioral overview tests against isolated synthetic factories only."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from add_dashboard import prepare, apply
from dashboard import page, read, run_records, parse_run_record, validate_run_record, summarize, observations, profile, write_output
from integrity import check, manifest_for
from scaffold import ROOT, render


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.factory = self.base/'.software-factory'
        self.factory.mkdir()
        self.config = json.loads((ROOT/'assets/example-config.json').read_text())
        self.research = json.loads((ROOT/'assets/example-research.json').read_text())
        self.files = render(self.config, self.research)
        self.write(self.files)
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, files):
        for name, value in files.items():
            path = self.factory/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.factory).as_posix(): p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def legacy(self):
        for path in (self.factory/'dashboard').iterdir():
            path.unlink()
        (self.factory/'dashboard').rmdir()
        files = {k: v for k, v in self.files.items() if not k.startswith('dashboard/') and k!='manifest.json'}
        (self.factory/'manifest.json').write_text(json.dumps(manifest_for(files)))

    def test_scaffold_has_openable_safe_dedicated_overview(self):
        html = (self.factory/'dashboard/index.html').read_text(encoding='utf-8')
        self.assertIn('Example project factory overview', html)
        self.assertIn('proposed scaffold', html)
        self.assertIn('blocked', html)
        self.assertNotIn('<script', html)
        self.assertIn("default-src 'none'", html)
        check(self.factory, quiet=True)

    def test_refresh_self_contained_and_no_factory_mutation(self):
        before = self.snapshot()
        output = self.base/'overview.html'
        result = subprocess.run([sys.executable, str(self.factory/'dashboard/dashboard.py'), '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Contract hashes/basic structure checked', output.read_text(encoding='utf-8'))
        self.assertEqual(before, self.snapshot())
        check(self.factory, quiet=True)
        old = output.read_bytes()
        again = subprocess.run([sys.executable, str(self.factory/'dashboard/dashboard.py'), '--output', str(output)], capture_output=True, text=True)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn('output already exists', again.stderr)
        self.assertIn('--replace', again.stderr)
        self.assertEqual(old, output.read_bytes())
        replaced = subprocess.run([sys.executable, str(self.factory/'dashboard/dashboard.py'), '--output', str(output), '--replace'], capture_output=True, text=True)
        self.assertEqual(replaced.returncode, 0, replaced.stderr)
        self.assertEqual(before, self.snapshot())

    def test_untrusted_run_notes_are_never_exported(self):
        runs=self.base/'.factory-runs';runs.mkdir()
        (runs/'run-test.json').write_text(json.dumps({'run_id':'run-test','outcome':'failed','started':self.now.isoformat(),'finished':self.now.isoformat(),'dispatched':['T1'],'notes':'PRIVATE-SECRET-SENTINEL'}))
        records,errors=run_records(runs,self.now,60)
        self.assertNotIn('PRIVATE-SECRET-SENTINEL',json.dumps([records,errors]))
        if os.name != 'nt' and (not hasattr(os,'O_NOFOLLOW') or os.open not in os.supports_dir_fd):
            self.assertEqual(records,[]);self.assertIn('unsupported',errors[0])
        else:
            self.assertEqual(records[0]['outcome'],'failed');self.assertNotIn('notes',records[0])

    @unittest.skipUnless(os.name=='nt','Windows native reader')
    def test_windows_history_valid_malformed_oversized_and_hardlink(self):
        runs=self.base/'.factory-runs';runs.mkdir()
        stamp=(self.now-timedelta(days=2)).isoformat()
        record={'run_id':'run-good','outcome':'failed','started':stamp,'finished':stamp,'dispatched':['T1'],'notes':'PRIVATE'}
        (runs/'run-good.json').write_text(json.dumps(record),encoding='utf-8')
        (runs/'run-bad.json').write_text('{malformed',encoding='utf-8')
        (runs/'run-large.json').write_bytes(b'x'*65537)
        outside=self.base/'hard-source';outside.write_text('PRIVATE',encoding='utf-8')
        os.link(outside,runs/'run-hard.json')
        records,errors=run_records(runs,self.now,60)
        self.assertEqual(len(records),1);self.assertEqual(records[0]['freshness'],'stale')
        self.assertEqual(records[0]['outcome'],'failed');self.assertTrue(errors)
        self.assertNotIn('PRIVATE',json.dumps([records,errors]))

    @unittest.skipUnless(os.name=='nt','Windows native reader')
    def test_windows_history_absent_empty_and_reparse_entry(self):
        runs=self.base/'.factory-runs'
        self.assertEqual(run_records(runs,self.now,60),([],[]))
        runs.mkdir();self.assertEqual(run_records(runs,self.now,60),([],[]))
        target=self.base/'target';target.mkdir();link=runs/'run-link.json'
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(target)],capture_output=True,text=True)
        if result.returncode:self.skipTest('Junction creation unavailable')
        try:
            records,errors=run_records(runs,self.now,60)
            self.assertEqual(records,[]);self.assertTrue(errors)
        finally:
            os.rmdir(link)

    @unittest.skipUnless(os.name=='nt','Windows native reader')
    def test_windows_history_directory_limit_fails_closed(self):
        runs=self.base/'.factory-runs';runs.mkdir()
        for index in range(201):(runs/f'run-{index}.json').write_text('{}')
        records,errors=run_records(runs,self.now,60)
        self.assertEqual(records,[]);self.assertIn('limit exceeded',errors[0])

    @unittest.skipUnless(os.name=='nt','Windows native reader')
    def test_windows_history_rejects_existing_write_handle(self):
        runs=self.base/'.factory-runs';runs.mkdir()
        name=runs/'run-busy.json';name.write_text('{}',encoding='utf-8')
        with name.open('w',encoding='utf-8') as open_writer:
            open_writer.write('unchanged private value');open_writer.flush()
            records,errors=run_records(runs,self.now,60)
            self.assertEqual(records,[]);self.assertTrue(errors)
        self.assertEqual(name.read_text(encoding='utf-8'),'unchanged private value')

    @unittest.skipUnless(os.name=='nt','Windows native reader')
    def test_windows_history_rejects_directory_junction(self):
        runs=self.base/'.factory-runs';target=self.base/'outside';target.mkdir()
        result=subprocess.run(['cmd','/c','mklink','/J',str(runs),str(target)],capture_output=True,text=True)
        if result.returncode: self.skipTest('Junction creation unavailable')
        try:
            records,errors=run_records(runs,self.now,60)
            self.assertEqual(records,[]);self.assertTrue(errors)
        finally:
            os.rmdir(runs)

    def test_run_record_rejects_nonstring_and_naive_timestamps(self):
        valid={'run_id':'run-test','outcome':'failed','started':self.now.isoformat(),'finished':self.now.isoformat(),'dispatched':[]}
        for field in ('started','finished'):
            for value in (None,1,{},'2026-01-01T00:00:00'):
                with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                    validate_run_record({**valid,field:value},'run-test.json',self.now,60)
        with self.assertRaisesRegex(ValueError,'nesting'):
            parse_run_record(('['*15000+']'*15000).encode(),'run-test.json',self.now,60)
        with self.assertRaisesRegex(ValueError,'UTC range'):
            validate_run_record({**valid,'started':'0001-01-01T00:00:00+01:00'},'run-test.json',self.now,60)

    def test_waived_failed_result_and_observation_are_visible(self):
        data=summarize(self.files,now=self.now)
        row=data['gates'][0];row.update(state='WAIVED',required=False,recorded_result='FAILED',observed_at='2026-01-01T00:00:00Z')
        html=page(data)
        for term in ('WAIVED','FAILED','2026-01-01T00:00:00Z'):self.assertIn(term,html)

    @unittest.skipUnless(hasattr(os,'O_NOFOLLOW') and hasattr(os,'O_DIRECTORY') and os.open in os.supports_dir_fd,'secure directory-relative reads unavailable')
    def test_run_records_report_stale_malformed_and_redirected_inputs(self):
        runs=self.base/'.factory-runs';runs.mkdir();stamp=(self.now-timedelta(days=2)).isoformat()
        record={'run_id':'run-good','outcome':'failed','started':stamp,'finished':stamp,'dispatched':['T1'],'notes':'PRIVATE'}
        (runs/'run-good.json').write_text(json.dumps(record))
        (runs/'run-bad.json').write_text('{malformed')
        target=self.base/'outside.json';target.write_text(json.dumps(record))
        (runs/'run-link.json').symlink_to(target)
        records,errors=run_records(runs,self.now,60)
        self.assertEqual(len(records),1);self.assertEqual(records[0]['freshness'],'stale')
        self.assertTrue(errors);self.assertNotIn('PRIVATE',json.dumps([records,errors]))

    @unittest.skipUnless(hasattr(os,'O_NOFOLLOW') and hasattr(os,'O_DIRECTORY') and os.open in os.supports_dir_fd,'secure directory-relative reads unavailable')
    def test_run_record_limit_fails_closed_before_partial_history(self):
        runs=self.base/'.factory-runs';runs.mkdir()
        for index in range(201):(runs/f'run-{index}.json').write_text('{}')
        records,errors=run_records(runs,self.now,60)
        self.assertEqual(records,[]);self.assertIn('limit exceeded',errors[0])

    def test_empty_tasks_are_unavailable_not_fabricated_activity(self):
        self.files['task-plan.json'] = json.dumps({'tasks': [], 'events': []})
        data = summarize(self.files)
        self.assertEqual(data['counts'], dict(pending=0, in_progress=0, blocked=0, done=0))
        self.assertEqual(data['workers'], [])
        self.assertIn('No recorded data', page(data))
        self.assertIn('Unavailable', data['usage'])

    def test_blocked_and_optional_failed_are_distinct(self):
        self.files['verification.md'] = self.files['verification.md'].replace('| G2 | pre-merge |', '| G2 | pre-merge |', 1)
        lines = self.files['verification.md'].splitlines()
        for i, line in enumerate(lines):
            if line.startswith('| G2 |'):
                cells = line.split('|'); cells[5]=' no '; cells[7]=' FAILED '; lines[i]='|'.join(cells)
        self.files['verification.md']='\n'.join(lines)
        data = summarize(self.files)
        row = next(g for g in data['gates'] if g['id']=='G2')
        self.assertEqual((row['state'], row['recorded_result']), ('WAIVED', 'FAILED'))
        self.assertEqual(data['counts']['blocked'], 1)

    def test_stale_sources_and_events_are_explicit(self):
        old = (self.now-timedelta(days=3)).timestamp()
        os.utime(self.factory/'task-plan.json', (old, old))
        data = read(self.factory, now=self.now)
        source = next(s for s in data['sources'] if s['artifact']=='task-plan.json')
        self.assertEqual(source['freshness'], 'stale')
        self.assertTrue(data['expires_at'])

    def test_events_sorted_by_actual_instant_not_timezone_string(self):
        def event(index, time):
            return {'id':str(index),'task_id':'T1','timestamp':time,'revision':'r1',
                    'environment':'fixture','check':'synthetic','result':'blocked','evidence':'synthetic',
                    'old_status':'pending','status':'blocked'}
        plan=json.loads(self.files['task-plan.json'])
        plan['events']=[event(i,'2026-10-30T12:00:00+14:00') for i in range(30)]
        plan['events'].append(event(31,'2026-10-30T11:00:00-10:00'))
        plan['events'].append(event(32,'invalid'))
        self.files['task-plan.json']=json.dumps(plan)
        data=summarize(self.files,now=datetime(2026,10,30,21,30,tzinfo=timezone.utc))
        self.assertEqual(len(data['events']),30)
        self.assertEqual(data['events'][0]['time'],'2026-10-30T11:00:00-10:00')
        self.assertEqual(data['events'][0]['freshness'],'recent')

    def test_malformed_and_missing_sources_fail_without_replacing_output(self):
        output = self.base/'overview.html'; output.write_text('old snapshot')
        (self.factory/'task-plan.json').write_text('{bad json')
        result = subprocess.run([sys.executable, str(self.factory/'dashboard/dashboard.py'), '--output', str(output), '--replace'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Dashboard unavailable', result.stderr)
        self.assertEqual(output.read_text(), 'old snapshot')
        (self.factory/'task-plan.json').unlink()
        with self.assertRaises((ValueError, OSError)):
            read(self.factory)

    def test_missing_duplicate_and_malformed_gate_rows(self):
        missing = dict(self.files)
        missing['verification.md']='\n'.join(line for line in missing['verification.md'].splitlines() if not line.startswith('| G2 |'))
        self.assertIn('Missing or wrong-stage gate: G2', summarize(missing)['errors'])
        row = next(line for line in self.files['verification.md'].splitlines() if line.startswith('| G1 |'))
        for suffix in (row, '| G1 | malformed |'):
            with self.assertRaises(ValueError):
                summarize({**self.files, 'verification.md':self.files['verification.md']+'\n'+suffix})

    def test_safe_text_and_allowlist_no_raw_private_data(self):
        self.config['dashboard']={'title':'<img src=x onerror=alert(1)>', 'work_item_label':'Packages', 'audience':'Maintainers'}
        self.config['data_policy']='PRIVATE_SENTINEL'
        files=render(self.config, self.research)
        data=summarize(files)
        html=page(data)
        self.assertIn('&lt;img', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(data)+html)
        self.assertNotIn(self.config['tasks'][0]['goal'], json.dumps(data))
        self.assertIn('Packages', html)

    def test_measured_proposed_stale_error_metrics(self):
        row={'name':'Latency', 'value':12, 'unit':'ms', 'source':'approved fixture', 'observed_at':self.now.isoformat(), 'status':'measured'}
        data=observations({'schema_version':1, 'metrics':[row]}, self.now, 60)
        self.assertEqual(data[0]['freshness'], 'measured')
        row['observed_at']=(self.now-timedelta(days=1)).isoformat()
        self.assertEqual(observations({'schema_version':1,'metrics':[row]},self.now,60)[0]['freshness'],'stale (measured)')
        row.update(status='proposed',value=None)
        self.assertIn('proposed', observations({'schema_version':1,'metrics':[row]},self.now,60)[0]['freshness'])
        for value in (True, float('nan'), float('inf'), '12'):
            row.update(status='measured',value=value)
            with self.assertRaises(ValueError):observations({'schema_version':1,'metrics':[row]},self.now,60)
        row.update(value=None,status='measured')
        with self.assertRaises(ValueError):observations({'schema_version':1,'metrics':[row]},self.now,60)

    def test_output_inside_factory_and_redirects_refused(self):
        with self.assertRaises(ValueError):write_output(self.factory, self.factory/'runtime.html', 'x')
        outside=self.base/'outside';outside.mkdir()
        for alias in (outside/'..'/self.factory.name/'verification.md', self.factory/'dashboard'/'..'/'verification.md'):
            with self.assertRaises(ValueError):write_output(self.factory,alias,'x',True)
        with self.assertRaises(ValueError):write_output(outside/'..'/self.factory.name,self.factory/'verification.md','x',True)
        path=self.base/'exists.html';path.write_text('preserve')
        with self.assertRaises(ValueError):write_output(self.factory,path,'x')
        self.assertEqual(path.read_text(),'preserve')

    def test_profile_backward_compatible_and_invalid_rejected(self):
        self.assertEqual(profile(self.config)['stale_after_minutes'],60)
        for value in ({'stale_after_minutes':0},{'stale_after_minutes':True},{'unknown':1},{'title':''},[]):
            with self.assertRaises(ValueError):profile({**self.config,'dashboard':value})

    @unittest.skipUnless(os.name=='nt','Windows namespace alias regression')
    def test_windows_namespace_output_alias_cannot_modify_factory(self):
        before=self.snapshot()
        for prefix in ('\\\\?\\','\\\\.\\'):
            with self.assertRaises(ValueError):write_output(self.factory,Path(prefix+str(self.factory/'verification.md')),'replacement',True)
        self.assertEqual(before,self.snapshot())

    def test_narrow_adoption_preview_apply_preserves_existing(self):
        self.legacy()
        before=self.snapshot()
        root,old,new,plan=prepare(self.factory)
        self.assertEqual(before,self.snapshot())
        with self.assertRaises(ValueError):apply(root,old,new,plan,'wrong')
        self.assertEqual(before,self.snapshot())
        backup=apply(root,old,new,plan,plan)
        self.assertEqual((backup/'manifest.json').read_bytes(),before['manifest.json'])
        after=self.snapshot()
        for name,data in before.items():
            if name!='manifest.json':self.assertEqual(after[name],data)
        check(self.factory,quiet=True)
        with self.assertRaises(ValueError):prepare(self.factory)

    def test_adoption_refuses_drift_and_concurrent_edit(self):
        self.legacy()
        root,old,new,plan=prepare(self.factory)
        (root/'task-plan.json').write_text('{"tasks":[],"events":[]}')
        with self.assertRaises(ValueError):apply(root,old,new,plan,plan)
        self.assertFalse((root/'dashboard').exists())
        (root/'policy.md').write_text('unreviewed')
        with self.assertRaises(ValueError):prepare(self.factory)

    def test_adoption_interruption_preserves_backup_and_blocks_integrity(self):
        self.legacy()
        root,old,new,plan=prepare(self.factory)
        with patch('add_dashboard.os.replace',side_effect=OSError('synthetic interrupted write')):
            with self.assertRaises(OSError):apply(root,old,new,plan,plan)
        self.assertEqual((root/'manifest.json').read_bytes(),old['manifest.json'])
        self.assertEqual((root.parent/'.factory-update-backups'/('dashboard-'+plan)/'manifest.json').read_bytes(),old['manifest.json'])
        with self.assertRaises(ValueError):check(root,quiet=True)


if __name__=='__main__':
    unittest.main()
