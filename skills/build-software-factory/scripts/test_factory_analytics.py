"""Synthetic local analytics tests; no private stores or live experiments."""
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
import factory_analytics as analytics
from learning_table import learning_cells, validate_learning_log
from scaffold import ROOT, render
import run_traces


class AnalyticsSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_capture_hashes_canonical_json_and_rejects_duplicate_or_nonfinite_json(self):
        path = self.base/'explicit.json'
        raw = b'\xef\xbb\xbf{\r\n "schema_version": 1\r\n}\r\n'
        path.write_bytes(raw)
        value, pin = analytics.capture(path)
        self.assertEqual(value, {'schema_version':1})
        self.assertEqual(pin, analytics.digest(value))
        path.write_text('{"schema_version":1}')
        self.assertEqual(analytics.capture(path)[1],pin)
        self.assertEqual(analytics.digest({'a':1,'b':2}),analytics.digest({'b':2,'a':1}))
        self.assertNotEqual(analytics.digest([1,2]),analytics.digest([2,1]))
        for bad in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}'):
            path.write_text(bad)
            with self.assertRaises(ValueError):analytics.capture(path)
        path.write_bytes(b' '*(analytics.MAX_INPUT_BYTES+1))
        with self.assertRaises(ValueError):analytics.capture(path)
        with self.assertRaises(ValueError):analytics.capture(self.base)

    def test_learn_cells_preserve_delimiters_as_text_and_have_exact_width(self):
        text = analytics.learn_table(['date', r'<script>x</script> | back\slash', 'hypothesis', 'change', 'owner', 'measure', 'pending'])
        self.assertNotIn('<script>', text)
        self.assertIn('\\|', text)
        self.assertEqual(len(learning_cells(text.splitlines()[-1])), 7)
        validate_learning_log(text)
        with self.assertRaises(ValueError):analytics.learn_table(['x']*6)
        with self.assertRaises(ValueError):analytics.learn_table(['line\nbreak']+['x']*6)

    def test_output_refuses_every_input_and_oversized_report_before_writing(self):
        factory=self.base/'factory';factory.mkdir()
        paths=[self.base/(name+'.json') for name in ('trace','experiment','assignments','decision')]
        for path in paths:path.write_text('{}')
        for path in paths:
            with self.assertRaises(ValueError):analytics.write_output(factory,path,'replacement',paths,True)
            self.assertEqual(path.read_text(),'{}')
        output=self.base/'report.json'
        with self.assertRaises(ValueError):analytics.write_output(factory,output,'x'*(analytics.MAX_OUTPUT_BYTES+1),paths)
        self.assertFalse(output.exists())

    def test_fixed_selectors_keep_unavailable_zero_status_and_currency_distinct(self):
        source=json.loads((ROOT/'assets/example-run-traces.json').read_text())
        now=datetime(2026,11,3,8,1,tzinfo=timezone.utc)
        row=run_traces.summarize(source,now=now)['runs'][0]
        self.assertEqual(analytics.measurement(row,'output_tokens')['value'],1000)
        self.assertEqual(analytics.measurement(row,'active_minutes')['unit'],'minutes')
        self.assertIsNone(analytics.measurement(row,'failed_checks')['value'])
        for phase in row['phases']:
            phase['cost']={'status':'measured','value':0,'currency':'USD'}
        self.assertEqual(analytics.measurement(row,'cost','USD')['value'],0)
        self.assertIsNone(analytics.measurement(row,'cost','EUR')['value'])
        row['phases'][1]['cost']['status']='estimated'
        self.assertIn('mixed metric statuses within unit',analytics.measurement(row,'cost','USD')['reasons'])
        row['phases'][0]['output_tokens']={'status':'unavailable','value':None}
        self.assertIsNone(analytics.measurement(row,'output_tokens')['value'])
        with self.assertRaises(ValueError):analytics.measurement(row,'invented-quality-score')


NOW = datetime(2026,12,15,tzinfo=timezone.utc)


def fixture():
    return tuple(json.loads((ROOT/('assets/example-analytics-'+name+'.json')).read_text(encoding='utf-8')) for name in ('traces','experiment','assignments'))


class ExperimentTests(unittest.TestCase):
    def setUp(self): self.traces,self.experiment,self.assignments=fixture()

    def run_analysis(self, now=NOW):
        self.assignments['experiment_digest']=analytics.digest(self.experiment)
        return analytics.analyze(self.traces,self.experiment,self.assignments,experiment_pin=analytics.digest(self.experiment),as_of=now)

    def test_example_is_deterministic_per_metric_and_historical_observations_remain_eligible(self):
        before=copy.deepcopy((self.traces,self.experiment,self.assignments))
        result=self.run_analysis()
        self.assertEqual(result,self.run_analysis())
        self.assertEqual(before,(self.traces,self.experiment,self.assignments))
        self.assertEqual(result['metrics'][0]['variants'][0]['statistics'],{'n':2,'mean':2.5,'min':2,'max':3})
        self.assertGreater(result['observation_age_seconds']['oldest'],30*86400)
        self.assertNotIn('insufficient_evidence',result['limitations'])
        self.assertNotIn('stale',json.dumps(result))
        self.assertNotIn('assignment_evidence_ref',json.dumps(result))
        self.assertNotIn('evidence_ref',json.dumps(result))
        body={k:v for k,v in result.items() if k!='analysis_digest'}
        self.assertEqual(analytics.digest(body),result['analysis_digest'])

    def test_output_tokens_missing_does_not_exclude_active_minutes(self):
        self.traces['runs'][0]['phases'][0]['output_tokens']={'status':'unavailable','value':None}
        result=self.run_analysis()
        self.assertEqual(result['metrics'][0]['variants'][0]['included'],2)
        self.assertEqual(result['metrics'][2]['variants'][0]['included'],1)
        self.assertIn('insufficient_evidence',result['limitations'])

    def test_selected_phase_missing_is_unavailable_not_zero(self):
        self.traces['runs'][0]['phases']=[p for p in self.traces['runs'][0]['phases'] if p['phase']!='build']
        result=self.run_analysis()['metrics'][0]['variants'][0]
        self.assertEqual(result['included'],1)
        self.assertEqual(result['dispositions']['metric_unavailable'],1)
        self.assertEqual(result['statistics']['mean'],3)

    def test_supplied_zero_cost_is_eligible(self):
        for row in self.traces['runs']:row['phases'][0]['cost']['value']=0
        self.assertEqual(self.run_analysis()['metrics'][1]['variants'][0]['statistics']['mean'],0)

    def test_mixed_status_or_currency_within_selected_phase_excluded(self):
        for field,change,reason in [('active_minutes',{'status':'estimated'},'mixed_status'),('cost',{'currency':'EUR'},'incompatible_currency')]:
            with self.subTest(field=field):
                self.setUp()
                row=self.traces['runs'][0];extra=copy.deepcopy(row['phases'][0]);extra['model']='second-model';extra[field].update(change);row['phases'].append(extra)
                metric_index=0 if field=='active_minutes' else 1
                result=self.run_analysis()['metrics'][metric_index]['variants'][0]
                self.assertEqual(result['included'],1)
                self.assertEqual(result['dispositions'][reason],1)

    def test_other_source_and_status_cells_are_secondary_never_promoted(self):
        for row in self.traces['runs'][2:]:
            row['source_label']='different-source'
            row['phases'][0]['active_minutes']['status']='estimated'
        result=self.run_analysis()
        b=result['metrics'][0]['variants'][1]
        self.assertEqual(b['statistics'],{'n':0,'mean':None,'min':None,'max':None})
        self.assertEqual(b['secondary_descriptive_cells'][0]['n'],2)
        self.assertEqual(b['dispositions']['outside_declared_cell'],2)
        self.assertIn('insufficient_evidence',result['limitations'])

    def test_closed_and_open_first_attempts_show_survivor_and_censoring_limits(self):
        self.traces['runs'][2]['pr_state']='closed'
        self.traces['runs'][3]['pr_state']='open'
        result=self.run_analysis()
        for metric in result['metrics']:
            b=metric['variants'][1]
            self.assertEqual((b['allocated'],b['included'],b['excluded']),(2,0,2))
            self.assertEqual(b['dispositions']['closed'],1)
            self.assertEqual(b['dispositions']['open_censored'],1)
        self.assertIn('differential_inclusion',result['limitations'])
        self.assertIn('censored_open_attempts',result['limitations'])
        html=analytics.panel(result)
        self.assertIn('0/2',html)
        self.assertIn('open_censored',html)
        self.assertNotIn('winner',html)

    def test_every_first_attempt_exclusion_is_counted(self):
        mutations=[('no_inventory',lambda:self.assignments['units'].pop(0)),
          ('inventory_incomplete',lambda:self.assignments['units'][0].update(inventory_complete=False)),
          ('first_attempt_missing',lambda:self.assignments['units'][0].update(attempts=[])),
          ('error',lambda:self.assignments['units'][0]['attempts'][0].update(state='error',run_id=None,error_reason='supplied collection error')),
          ('out_of_window',lambda:self.assignments['units'][0]['attempts'][0].update(started_at='2026-10-31T08:00:00Z')),
          ('pr_state_unavailable',lambda:self.traces['runs'][0].update(pr_state='unavailable')),
          ('merged_incomplete',lambda:self.traces['runs'][0].update(complete=False))]
        for reason,mutate in mutations:
            with self.subTest(reason=reason):
                self.setUp();mutate();result=self.run_analysis()['metrics'][0]['variants'][0]
                self.assertEqual(result['dispositions'][reason],1)
                self.assertEqual(result['included'],1)

    def add_retry(self):
        row=copy.deepcopy(self.traces['runs'][0]);row['run_id']='retry-run';row['phases'][0]['active_minutes']['value']=1
        self.traces['runs'].append(row)
        retry=copy.deepcopy(self.assignments['units'][0]['attempts'][0]);retry.update(attempt_id='retry-attempt',ordinal=2,run_id='retry-run',started_at='2026-11-01T09:00:00Z')
        self.assignments['units'][0]['attempts'].append(retry)

    def test_retries_not_selected_and_missing_first_does_not_fallback(self):
        self.add_retry()
        result=self.run_analysis()['metrics'][0]['variants'][0]
        self.assertEqual(result['statistics']['mean'],2.5)
        self.assertEqual(result['units_with_later_attempts'],1)
        self.assertEqual(result['later_attempts_excluded'],1)
        self.assignments['units'][0]['attempts'].pop(0)
        self.assignments['units'][0]['attempts'][0]['ordinal']=1
        result=self.run_analysis()['metrics'][0]['variants'][0]
        self.assertEqual(result['dispositions']['first_attempt_missing'],1)
        self.assertEqual(result['included'],1)

    def test_ordinal_and_time_contradictions_refused(self):
        for change in ('ordinal','time','first'):
            with self.subTest(change=change):
                self.setUp();self.add_retry()
                attempts=self.assignments['units'][0]['attempts']
                if change=='ordinal': attempts[1]['ordinal']=3
                elif change=='time': attempts[1]['started_at']='2026-11-01T07:00:00Z'
                else:
                    attempts[0]['attempt_id']='another';attempts[1]['attempt_id']='attempt-0'
                with self.assertRaises(ValueError):self.run_analysis()

    def test_unbound_ordinal_one_is_ambiguous_exclusion_not_retry(self):
        self.assignments['units'][0]['attempts'][0]['attempt_id']='unbound-ordinal-one'
        result=self.run_analysis()
        for metric in result['metrics']:
            a=metric['variants'][0]
            self.assertEqual(a['included'],1)
            self.assertEqual(a['dispositions']['first_attempt_missing'],1)
            self.assertEqual(a['units_with_later_attempts'],0)
            self.assertEqual(a['later_attempts_excluded'],0)
            self.assertEqual(a['unbound_ordinal_one_attempts_excluded'],1)
        self.assertIn('Unbound ordinal-one claims excluded',analytics.panel(result))

    def test_shared_subject_independent_units_and_unassigned_trace_only_warn(self):
        for index in (1,2):
            self.traces['runs'][index]['subject']=self.traces['runs'][0]['subject']
            self.assignments['units'][index]['attempts'][0]['subject']=self.traces['runs'][0]['subject']
        extra=copy.deepcopy(self.traces['runs'][0]);extra['run_id']='unassigned';self.traces['runs'].append(extra)
        result=self.run_analysis()
        self.assertTrue(all(v['included']==2 for v in result['metrics'][0]['variants']))
        self.assertEqual(result['unassigned_traces_excluded'],1)
        self.assertIn('shared_subject_possible_dependence_not_duplicate_proof',result['limitations'])

    def test_duplicate_trace_attempt_or_allocation_refused(self):
        for kind in ('trace','run_mapping','attempt','unit','task','first_id'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='trace':self.traces['runs'].append(copy.deepcopy(self.traces['runs'][0]))
                elif kind=='run_mapping':self.assignments['units'][1]['attempts'][0]['run_id']='run-0'
                elif kind=='attempt':self.assignments['units'][1]['attempts'][0]['attempt_id']='attempt-0'
                else:
                    key={'unit':'unit_id','task':'task_id','first_id':'first_attempt_id'}[kind]
                    self.experiment['allocations'][1][key]=self.experiment['allocations'][0][key]
                with self.assertRaises(ValueError):self.run_analysis()

    def test_wrong_subject_storage_subject_never_substitutes(self):
        attempt=self.assignments['units'][0]['attempts'][0]
        attempt['storage_subject']=attempt['subject'];attempt['subject']='wrong-source'
        with self.assertRaises(ValueError):self.run_analysis()

    def test_pinned_attempt_cannot_move_to_another_task(self):
        self.assignments['units'][0]['attempts']=[]
        self.assignments['units'][1]['attempts'][0]['attempt_id']='attempt-0'
        with self.assertRaises(ValueError):self.run_analysis()

    def test_assignment_versions_unknown_fields_and_future_observation_refused(self):
        for change in ('version','extra','unit','future'):
            with self.subTest(change=change):
                self.setUp()
                if change=='version':self.assignments['schema_version']=True
                elif change=='extra':self.assignments['units'][0]['unexpected']='private'
                elif change=='unit':self.assignments['units'][0]['unit_id']='unknown'
                else:self.traces['runs'][0]['observed_at']='2027-01-01T00:00:00Z'
                with self.assertRaises(ValueError):self.run_analysis()

    def test_outcome_eligibility_does_not_require_any_phase(self):
        self.experiment['metrics'][0].update(selector='failed_checks',phase=None,unit='count')
        for row in self.traces['runs']:
            row['phases']=[]
            row['outcome']['failed_checks']={'status':'supplied','value':0}
        result=self.run_analysis()
        self.assertEqual(result['metrics'][0]['variants'][0]['statistics']['mean'],0)
        self.assertEqual(result['metrics'][0]['variants'][0]['included'],2)
        self.assertIsNone(result['metrics'][1]['variants'][0]['statistics']['mean'])

    def test_disposition_partitions_account_for_every_allocated_unit(self):
        self.traces['runs'][0]['pr_state']='closed'
        self.traces['runs'][2]['phases'][0]['active_minutes']={'status':'unavailable','value':None}
        for metric in self.run_analysis()['metrics']:
            for variant in metric['variants']:
                counts=variant['dispositions']
                self.assertEqual(sum(counts[key] for key in analytics.DISPOSITIONS[:10]),variant['allocated'])
                self.assertEqual(sum(counts[key] for key in analytics.DISPOSITIONS[10:]),counts['merged_complete'])
                self.assertEqual(variant['included']+variant['excluded'],variant['allocated'])

    def test_claimed_time_order_and_window_boundary(self):
        for bad in ('2026-11-04T00:00:00Z','2026-11-01T08:00:00'):
            self.assignments['units'][0]['attempts'][0]['started_at']=bad
            with self.assertRaises(ValueError):self.run_analysis()
        self.assignments['units'][0]['attempts'][0]['started_at']='2026-11-02T00:00:00Z'
        self.assertEqual(self.run_analysis()['metrics'][0]['variants'][0]['dispositions']['out_of_window'],1)

    def test_open_window_is_labelled(self):
        for row in self.traces['runs']:row['observed_at']='2026-11-01T08:30:00Z'
        result=self.run_analysis(datetime(2026,11,1,9,tzinfo=timezone.utc))
        self.assertIn('observation_window_open',result['limitations'])

    def test_model_difference_token_limitation(self):
        self.traces['runs'][2]['phases'][0]['model']='different-definition-model'
        self.assertIn('token_definitions_may_differ',self.run_analysis()['limitations'])

    def test_guardrail_breach_and_missing_are_not_masked_by_other_variant(self):
        for row in self.traces['runs'][2:]:row['phases'][0]['cost']['value']=9
        result=self.run_analysis()
        self.assertIn('guardrail_threshold_exceeded_observed',result['limitations'])
        self.traces['runs'][2]['phases'][0]['cost']={'status':'unavailable','value':None,'currency':None}
        result=self.run_analysis()
        self.assertIn('guardrail_unavailable_or_insufficient',result['limitations'])
        self.assertNotEqual(result['metrics'][1]['variants'][0]['threshold_state'],result['metrics'][1]['variants'][1]['threshold_state'])

    def test_design_validation_strict_versions_fields_cells_units_and_chronology(self):
        for mutate in (lambda e:e.update(schema_version=True),lambda e:e.update(extra='x'),lambda e:e.update(analysis_attempt='latest_pass'),
                       lambda e:e.update(assignment_unit='commit'),lambda e:e.update(min_units=1),lambda e:e.update(created_at='2026-11-01T01:00:00Z'),
                       lambda e:e['metrics'][0].update(phase=None),lambda e:e['metrics'][0].update(unit='seconds'),
                       lambda e:e['metrics'][0]['cell'].update(status='unavailable'),lambda e:e['metrics'][0]['cell'].update(currency='USD'),
                       lambda e:e['metrics'][0].update(role='secondary'),lambda e:e['metrics'][1]['threshold'].update(value=float('inf'))):
            with self.subTest(mutation=mutate):
                self.setUp();mutate(self.experiment)
                with self.assertRaises((ValueError,OverflowError)):self.run_analysis()

    def test_observational_and_before_after_are_claimed_designs(self):
        self.experiment['method']='observational'
        result=self.run_analysis();self.assertEqual(result['method_claim'],'observational')
        self.experiment['method']='before_after'
        with self.assertRaises(ValueError):self.run_analysis()
        self.experiment['variants'][1].update(start='2026-11-02T00:00:00Z',end='2026-11-03T00:00:00Z')
        self.assertIn('time_confounding',self.run_analysis()['limitations'])
        self.experiment['timing']='retrospective'
        self.assertIn('post_hoc_design',self.run_analysis()['limitations'])

    def test_pins_and_asof_bind_analysis_without_factory_mtimes(self):
        result=self.run_analysis()
        with self.assertRaises(ValueError):analytics.analyze(self.traces,self.experiment,self.assignments,experiment_pin='0'*64,as_of=NOW)
        self.assertNotEqual(result['analysis_digest'],self.run_analysis(datetime(2026,12,16,tzinfo=timezone.utc))['analysis_digest'])
        self.experiment['stopping_rule']='Changed design'
        with self.assertRaises(ValueError):analytics.analyze(self.traces,self.experiment,self.assignments,experiment_pin=analytics.digest(self.experiment),as_of=NOW)

    def test_overflow_per_unit_and_cohort_refused(self):
        for row in self.traces['runs']:row['phases'][0]['active_minutes']['value']=run_traces.MAX_NUMBER
        with self.assertRaises(ValueError):self.run_analysis()
        extra=copy.deepcopy(self.traces['runs'][0]['phases'][0]);extra['model']='other';self.traces['runs'][0]['phases'].append(extra)
        with self.assertRaises(ValueError):self.run_analysis()

    def test_decision_is_bound_and_never_clears_limits(self):
        self.traces['runs'][0]['pr_state']='open';result=self.run_analysis()
        decision={'schema_version':1,'analysis_digest':result['analysis_digest'],'decided_at':'2026-12-15T00:01:00Z','decision':'keep','owner':'operator','rationale':'Explicit private judgment'}
        checked=analytics.validate_decision(decision,result)
        self.assertIn('insufficient_evidence',analytics.panel(result,checked))
        self.assertIn('no adoption',analytics.learn_proposal(result,self.experiment,checked))
        for field,value in [('analysis_digest','0'*64),('decided_at','2026-12-14T00:00:00Z'),('decision','automatic-winner')]:
            broken={**decision,field:value}
            with self.assertRaises(ValueError):analytics.validate_decision(broken,result)

    def test_learn_uses_opaque_cells_and_html_escapes_private_labels(self):
        self.experiment['experiment_id']='<script>private-id</script>'
        self.experiment['learn']['hypothesis']=r'Could | this \\ change help <script>text</script>?'
        result=self.run_analysis();learn=analytics.learn_proposal(result,self.experiment)
        validate_learning_log(learn)
        for secret in (self.experiment['experiment_id'],self.traces['runs'][0]['source_label'],self.traces['runs'][0]['subject'],self.traces['runs'][0]['phases'][0]['model']):
            self.assertNotIn(secret,learn)
        self.assertNotIn('<script>',analytics.panel(result))
        self.assertNotIn('<script>',learn)


class AnalyticsCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.factory=self.base/'factory';self.factory.mkdir()
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        files=render(config,research)
        for name,text in files.items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
        self.traces,self.experiment,self.assignments=fixture()
        self.paths=[]
        for name,value in zip(('traces','experiment','assignments'),(self.traces,self.experiment,self.assignments)):
            path=self.base/(name+'.json');path.write_text(json.dumps(value),encoding='utf-8');self.paths.append(path)
        self.command=[sys.executable,'-B',str(ROOT/'scripts/factory_analytics.py'),'--factory',str(self.factory),'--trace',str(self.paths[0]),'--experiment',str(self.paths[1]),'--assignments',str(self.paths[2]),'--experiment-pin',analytics.digest(self.experiment),'--as-of',NOW.isoformat()]

    def invoke(self,output,extra=()):
        return subprocess.run(self.command+['--output',str(output)]+list(extra),capture_output=True,text=True)

    def test_end_to_end_private_json_html_learn_definition_and_decision_leave_factory_unchanged(self):
        before={p.relative_to(self.factory):p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}
        report=self.base/'result.json';run=self.invoke(report);self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(report.read_text())['analysis']
        html=self.base/'dashboard.html';run=self.invoke(html,('--format','html'));self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn('Private supplied experiment analysis',html.read_text())
        self.assertIn('Example project factory overview',html.read_text())
        draft=self.base/'learn.md';run=self.invoke(draft,('--format','learn'));self.assertEqual(run.returncode,0,run.stderr);validate_learning_log(draft.read_text())
        decision=self.base/'decision.json';decision.write_text(json.dumps({'schema_version':1,'analysis_digest':result['analysis_digest'],'decided_at':NOW.isoformat(),'decision':'inconclusive','owner':'operator','rationale':'Review more evidence'}))
        chosen=self.base/'chosen.json';run=self.invoke(chosen,('--decision',str(decision)));self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(chosen.read_text())['analysis'],result)
        definition=self.base/'definition.json'
        run=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/factory_analytics.py'),'--factory',str(self.factory),'--experiment',str(self.paths[1]),'--definition-only','--output',str(definition)],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(definition.read_text())['canonical_experiment_digest'],analytics.digest(self.experiment))
        self.assertNotIn('assignment_evidence_ref',definition.read_text())
        after={p.relative_to(self.factory):p.read_bytes() for p in self.factory.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_cli_refuses_aliases_factory_output_replacement_and_redacts_failures(self):
        for path in self.paths+[self.factory/'private-output.json']:
            original=path.read_bytes() if path.exists() else None
            run=self.invoke(path,('--replace',));self.assertNotEqual(run.returncode,0)
            if original is not None:self.assertEqual(path.read_bytes(),original)
        output=self.base/'prior.json';output.write_text('preserve')
        run=self.invoke(output);self.assertNotEqual(run.returncode,0);self.assertEqual(output.read_text(),'preserve')
        self.paths[0].write_text('{"secret-api-key":invalid}')
        run=self.invoke(self.base/'bad.json');self.assertNotEqual(run.returncode,0)
        self.assertNotIn(str(self.paths[0]),run.stderr);self.assertNotIn('secret-api-key',run.stderr)
        self.assertFalse((self.base/'bad.json').exists())

    def test_input_pair_alias_refused(self):
        with self.assertRaises(ValueError):analytics.distinct_inputs([self.paths[0],self.paths[0]])

    def test_factory_mtime_is_outside_analytics_digest(self):
        first=self.base/'first.json';second=self.base/'second.json'
        self.assertEqual(self.invoke(first).returncode,0)
        factory_file=next(p for p in self.factory.rglob('*') if p.is_file())
        os.utime(factory_file,(1_700_000_000,1_700_000_000))
        self.assertEqual(self.invoke(second).returncode,0)
        self.assertEqual(first.read_bytes(),second.read_bytes())

    def test_decision_output_alias_is_refused_without_overwrite(self):
        report=self.base/'result.json';self.assertEqual(self.invoke(report).returncode,0)
        result=json.loads(report.read_text())['analysis']
        decision=self.base/'decision.json'
        decision.write_text(json.dumps({'schema_version':1,'analysis_digest':result['analysis_digest'],'decided_at':NOW.isoformat(),'decision':'keep','owner':'operator','rationale':'Supplied choice'}))
        original=decision.read_bytes()
        run=self.invoke(decision,('--decision',str(decision),'--replace'))
        self.assertNotEqual(run.returncode,0)
        self.assertEqual(decision.read_bytes(),original)


if __name__=='__main__':unittest.main()
