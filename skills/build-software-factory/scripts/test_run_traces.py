"""Synthetic supplied-trace validation and dashboard CLI tests; no real session stores."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import dashboard
from integrity import check
from scaffold import ROOT, render
import run_traces as traces

NOW = datetime(2026, 11, 3, 8, 1, tzinfo=timezone.utc)


def fixture():
    return json.loads((ROOT/'assets/example-run-traces.json').read_text(encoding='utf-8'))


class TraceTests(unittest.TestCase):
    def test_supplied_subjects_and_status_are_retained_without_private_reference(self):
        source = fixture()
        original = copy.deepcopy(source)
        data = traces.summarize(source, now=NOW)
        self.assertEqual(source, original)
        self.assertEqual(data['runs'][0]['subject'], source['runs'][0]['subject'])
        self.assertEqual(data['runs'][0]['output_tokens'], {'status':'supplied', 'value':1000})
        self.assertEqual(data['runs'][0]['phases'][0]['cost'], {'status':'unavailable', 'value':None, 'currency':None})
        self.assertNotIn('evidence_ref', json.dumps(data))
        self.assertNotIn(source['runs'][0]['evidence_ref'], json.dumps(data))
        self.assertIn('not independently verified', data['notice'])
        self.assertIn('private', data['privacy'])

    def test_cohorts_do_not_mix_statuses_and_report_empty_as_unavailable(self):
        source = fixture()
        for index, kind in enumerate(('measured', 'estimated')):
            row = copy.deepcopy(source['runs'][0]);row['run_id'] = 'extra-'+str(index)
            for phase in row['phases']:phase['output_tokens']['status'] = kind
            source['runs'].append(row)
        data = traces.summarize(source, now=NOW)
        self.assertEqual(data['excluded_runs'], 1)
        for average in data['averages']:
            self.assertEqual(average['included_count'], 1)
            self.assertEqual(average['excluded_count'], 3)
            self.assertEqual(average['mean_output_tokens'], 1000)
        empty = traces.summarize({'schema_version':1, 'runs':[]}, now=NOW)
        self.assertTrue(all(a['mean_output_tokens'] is None for a in empty['averages']))
        self.assertIn('unavailable', traces.panel(empty))

    def test_open_incomplete_stale_unavailable_and_mixed_exclusions_are_explicit(self):
        base = fixture()['runs'][0]
        rows = []
        for index in range(6):
            row = copy.deepcopy(base);row['run_id'] = str(index);rows.append(row)
        rows[0]['pr_state'] = 'open'
        rows[1]['complete'] = False
        rows[2]['observed_at'] = '2026-11-01T08:00:00Z'
        rows[3]['phases'][0]['output_tokens'] = {'status':'unavailable','value':None}
        rows[4]['phases'][0]['output_tokens']['status'] = 'estimated'
        rows[5]['phases'] = []
        result = traces.summarize({'schema_version':1,'runs':rows}, now=NOW)
        self.assertEqual(result['excluded_runs'], 6)
        self.assertEqual(result['exclusion_reasons']['missing or unavailable phase output tokens'], 2)
        self.assertEqual(len(result['exclusion_reasons']), 5)
        self.assertTrue(all(a['mean_output_tokens'] is None for a in result['averages']))
        self.assertIsNone(result['runs'][3]['output_tokens']['value'])
        self.assertIn('in progress (open)', traces.panel(result))
        self.assertIn('Stack unavailable', traces.panel(result))

    def test_actual_supplied_zero_is_not_confused_with_unavailable(self):
        source = fixture()
        for phase in source['runs'][0]['phases']:phase['output_tokens']['value'] = 0
        data = traces.summarize(source, now=NOW)
        self.assertEqual(data['averages'][1]['mean_output_tokens'], 0)
        self.assertIn('values total zero', traces.panel(data))

    def test_duplicate_run_binding_and_phase_model_are_refused(self):
        for same_subject in (True, False):
            source = fixture();row = copy.deepcopy(source['runs'][0])
            if not same_subject:row['subject'] = 'another-subject'
            source['runs'].append(row)
            with self.assertRaises(ValueError):traces.summarize(source, now=NOW)
        source = fixture();source['runs'][0]['phases'].append(copy.deepcopy(source['runs'][0]['phases'][0]))
        with self.assertRaises(ValueError):traces.summarize(source, now=NOW)

    def test_strict_schema_rejects_unknown_fields_versions_and_unbounded_records(self):
        edits = [lambda d:d.update(schema_version=True), lambda d:d.update(schema_version=2),
                 lambda d:d.update(transcript='PRIVATE'), lambda d:d['runs'][0].update(working_directory='PRIVATE'),
                 lambda d:d['runs'][0]['phases'][0].update(raw_log='PRIVATE'),
                 lambda d:d['runs'][0]['outcome'].update(missed_fixes=0),
                 lambda d:d['runs'][0].update(run_id=' '), lambda d:d['runs'][0].update(subject='x'*201),
                 lambda d:d['runs'][0].update(source_label='line\nbreak'), lambda d:d['runs'][0].update(complete=1),
                 lambda d:d['runs'][0].update(pr_state='assumed'), lambda d:d['runs'][0].update(risk='critical'),
                 lambda d:d['runs'][0].update(verdict='tests-passed'), lambda d:d['runs'][0]['phases'][0].update(phase='unknown'),
                 lambda d:d.update(runs=[d['runs'][0]]*(traces.MAX_RUNS+1)),
                 lambda d:d['runs'][0].update(phases=[d['runs'][0]['phases'][0]]*(traces.MAX_PHASES+1))]
        for edit in edits:
            source = fixture();edit(source)
            with self.subTest(edit=edits.index(edit)), self.assertRaises(ValueError):traces.summarize(source, now=NOW)

    def test_metric_status_types_limits_and_cost_currency_are_strict(self):
        for value in (-1, True, '1', 1.5, float('nan'), float('inf'), traces.MAX_NUMBER+1, None):
            source = fixture();source['runs'][0]['phases'][0]['output_tokens']['value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):traces.summarize(source, now=NOW)
        for bad in ({'status':'unavailable','value':0}, {'status':'measured','value':None},
                    {'status':'assumed','value':1}, {'status':'supplied','value':1,'extra':True}):
            source=fixture();source['runs'][0]['rounds']=bad
            with self.assertRaises(ValueError):traces.summarize(source,now=NOW)
        for cost in ({'status':'unavailable','value':None,'currency':'USD'},
                     {'status':'supplied','value':1,'currency':None},
                     {'status':'estimated','value':-1,'currency':'USD'},
                     {'status':'measured','value':1,'currency':'usd'}):
            source=fixture();source['runs'][0]['phases'][0]['cost']=cost
            with self.assertRaises(ValueError):traces.summarize(source,now=NOW)
        source=fixture()
        for phase in source['runs'][0]['phases']:phase['output_tokens']['value']=traces.MAX_NUMBER
        with self.assertRaises(ValueError):traces.summarize(source,now=NOW)

    def test_costs_remain_per_phase_and_are_never_priced_or_pooled(self):
        source=fixture()
        source['runs'][0]['phases'][0]['cost']={'status':'measured','value':1.25,'currency':'USD'}
        source['runs'][0]['phases'][1]['cost']={'status':'estimated','value':2,'currency':'EUR'}
        data=traces.summarize(source,now=NOW);html=traces.panel(data)
        self.assertIn('1.25 USD (measured)',html);self.assertIn('2 EUR (estimated)',html)
        self.assertNotIn('mean_cost',json.dumps(data));self.assertNotIn('total_cost',json.dumps(data))

    def test_as_of_and_freshness_are_deterministic_and_future_refused(self):
        source=fixture();source['runs'][0]['observed_at']='2026-11-03T08:02:00Z'
        with self.assertRaises(ValueError):traces.summarize(source,now=NOW)
        for stamp in ('bad','2026-11-03T08:00:00'):
            source=fixture();source['runs'][0]['observed_at']=stamp
            with self.assertRaises(ValueError):traces.summarize(source,now=NOW)
        with self.assertRaises(ValueError):traces.summarize(fixture(),now=NOW.replace(tzinfo=None))
        for window in (0,True,43201):
            with self.assertRaises(ValueError):traces.summarize(fixture(),now=NOW,stale_after_minutes=window)
        self.assertEqual(traces.summarize(fixture(),now=NOW,stale_after_minutes=1)['runs'][0]['freshness'],'recent')

    def test_html_escapes_exported_labels_and_withholds_evidence(self):
        source=fixture();sentinel='<img src=x onerror="bad()">'
        for key in ('run_id','subject','source_label'):source['runs'][0][key]=sentinel
        source['runs'][0]['phases'][0]['model']=sentinel
        source['runs'][0]['evidence_ref']='PRIVATE_REFERENCE_SECRET'
        data=traces.summarize(source,now=NOW);html=traces.panel(data)
        self.assertNotIn(sentinel,html);self.assertIn('&lt;img',html)
        self.assertNotIn('PRIVATE_REFERENCE_SECRET',html);self.assertNotIn('PRIVATE_REFERENCE_SECRET',json.dumps(data))
        self.assertIn('width:60.0%',html);self.assertIn('width:40.0%',html)


class TraceCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.factory=self.base/'.software-factory';self.factory.mkdir()
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        self.files=render(config,research)
        for name,body in self.files.items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
        self.source=self.base/'private-trace.json';self.source.write_text(json.dumps(fixture()),encoding='utf-8')
        self.output=self.base/'overview.html'

    def tearDown(self):self.tmp.cleanup()

    def snapshot(self):return {p.relative_to(self.factory).as_posix():p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}

    def cli(self,*extra):
        return subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_traces.py'),'--factory',str(self.factory),
                               '--trace',str(self.source),'--output',str(self.output),'--as-of',NOW.isoformat(),*extra],capture_output=True,text=True)

    def test_cli_renders_html_and_json_without_factory_or_input_changes(self):
        original=self.snapshot();source=self.source.read_bytes()
        result=self.cli();self.assertEqual(result.returncode,0,result.stderr)
        html=self.output.read_text(encoding='utf-8')
        self.assertIn('Supplied private run traces',html);self.assertIn('Factory passes',html)
        self.assertIn('Content-Security-Policy',html);self.assertNotIn('<script',html)
        self.assertNotIn('Private synthetic evidence reference',html)
        self.assertEqual(self.cli().returncode,1)
        self.assertEqual(self.output.read_text(encoding='utf-8'),html)
        result=self.cli('--format','json','--replace');self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(data['supplied_run_traces']['averages'][1]['included_count'],1)
        self.assertEqual(self.snapshot(),original);self.assertEqual(self.source.read_bytes(),source)
        self.assertFalse((self.factory/'dashboard/run_traces.py').exists());check(self.factory,quiet=True)

    def test_bad_private_inputs_leave_existing_output_unchanged_and_diagnostics_private(self):
        self.output.write_text('preserve existing output')
        cases=['{"schema_version":1,"schema_version":1,"runs":[]}',
               '{"schema_version":1,"runs":[],"PRIVATE_SECRET":"raw transcript"}',
               '{"schema_version":NaN,"runs":[]}', '{"schema_version":Infinity,"runs":[]}',
               'PRIVATE_SECRET not json', '['*2000+']'*2000]
        for raw in cases:
            self.source.write_text(raw)
            result=self.cli('--replace')
            self.assertEqual(result.returncode,1)
            self.assertNotIn('PRIVATE_SECRET',result.stderr);self.assertNotIn(str(self.source),result.stderr)
            self.assertEqual(result.stdout,'');self.assertEqual(self.output.read_text(),'preserve existing output')

    def test_reader_rejects_nested_duplicate_fields_oversize_and_directories(self):
        raw=json.dumps(fixture()).replace('"status": "supplied"','"status": "supplied", "status": "measured"',1)
        self.source.write_text(raw)
        with self.assertRaises(ValueError):traces.read_input(self.source)
        self.source.write_bytes(b' '*(traces.MAX_BYTES+1))
        with self.assertRaises(ValueError):traces.read_input(self.source)
        with self.assertRaises(ValueError):traces.read_input(self.base)

    def test_reader_refuses_changed_input_and_uses_no_directory_discovery(self):
        original=Path.stat
        calls=[]
        def changed(path,*args,**kwargs):
            if path==self.source:
                calls.append(path)
                if len(calls)==2:self.source.write_text('{}')
            return original(path,*args,**kwargs)
        with patch.object(Path,'glob',side_effect=AssertionError('discovery')), patch.object(Path,'rglob',side_effect=AssertionError('discovery')):
            self.assertEqual(traces.read_input(self.source)['schema_version'],1)
        # Simulate a file change after the initial metadata capture, without unsafe filesystem routes.
        with patch.object(Path,'stat',changed), self.assertRaises(ValueError):traces.read_input(self.source)

    def test_output_cannot_replace_input_or_live_factory(self):
        source=self.source.read_bytes();self.output=self.source
        self.assertEqual(self.cli('--replace').returncode,1);self.assertEqual(self.source.read_bytes(),source)
        self.output=self.factory/'verification.md';before=self.output.read_bytes()
        self.assertEqual(self.cli('--replace').returncode,1);self.assertEqual(self.output.read_bytes(),before)

    def test_default_dashboard_has_no_trace_data_or_panel(self):
        data=dashboard.summarize(self.files,now=NOW)
        self.assertNotIn('supplied_run_traces',data)
        self.assertNotIn('Supplied private run traces',dashboard.page(data))
        self.assertEqual(dashboard.page(data),dashboard.page(data,supplemental_html=''))


if __name__=='__main__':unittest.main()
