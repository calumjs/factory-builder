"""Synthetic supplied-claim assessments; no provider, billing or dispatcher proof."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import admission_review as ar
from operations import operations, controls
from readiness import watcher
import run
from scaffold import ROOT, render, validate

NOW=datetime(2026,11,3,12,tzinfo=timezone.utc)


def fixture(now=NOW):
    config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
    config['budget'].update(max_cost=100,max_workers=3)
    policy={'version':1,'status':'specified','repository':'SYNTHETIC/example',
            'identity':{'kind':'label_actor_capability','capability':'write'},
            'starts':{'maximum':8,'window':'calendar_day','timezone':'UTC'},
            'max_in_flight_items':2,'completion':'draft_pr',
            'costs':{'currency':'USD','max_per_item':'3.00',
                     'period':{'maximum':'20.00','window':'calendar_month','timezone':'UTC'}},
            'snapshot_max_age_seconds':300}
    config['operations']={'autonomy':{'mode':'bounded','allowed_submitters':[], 'max_items_per_hour':10},
                          'issue_intake':{'mode':'continuous','status':'enabled','github_scope':policy['repository']},
                          'admission':policy}
    day,_=ar.period_bounds(now,'calendar_day','UTC');start,end=ar.period_bounds(now,'calendar_month','UTC')
    snapshot={'version':1,'repository':policy['repository'],'policy_sha256':ar.digest(policy),
              'observed_at':now.isoformat(),'coverage':{'starts_since':day.isoformat(),'complete':True,'source_reference':'synthetic complete inventory'},
              'period':{'start':start.isoformat(),'end':end.isoformat(),'spent':'0','reserved':'0',
                        'accounting_complete':True,'accounted_through':now.isoformat(),'source_reference':'synthetic accounting'},
              'cycles':[],'requests':[request('42',now)]}
    issues=[{'id':'42','submitter':'author','labels':['ready'],'depends_on':[]}]
    issue_policy={'repository':policy['repository'],'ready_label':'ready','excluded_labels':['paused']}
    return config,snapshot,issues,issue_policy


def request(iid,now=NOW):
    return {'request_id':'request-'+iid,'issue_id':iid,'cycle_id':'cycle-'+iid,'kind':'start','author':'author',
            'event':{'id':'event-'+iid,'label':'ready','actor':'labeler','occurred_at':now.isoformat()},
            'permission':{'actor':'labeler','capability':'write','decision':'allowed','observed_at':now.isoformat(),'reference':'synthetic permission'},
            'reserve':'1.00'}


def cycle(iid='old',state='active',spent='1.00',reserved='0.50'):
    return {'issue_id':iid,'cycle_id':'cycle-'+iid,'admitted_at':NOW.replace(hour=10).isoformat(),
            'state':state,'completed_at':None,'completion':None,'spent':spent,'reserved':reserved,
            'evidence':'synthetic cycle observation'}


class AdmissionPolicyTests(unittest.TestCase):
    def test_legacy_controls_remain_unextended_and_input_unchanged(self):
        config,_,_,_=fixture();del config['operations']['admission']
        config['operations']['autonomy']['allowed_submitters']=['author'];before=copy.deepcopy(config)
        self.assertEqual(set(controls(config)),{'concurrency','autonomy','review','visual_checks','issue_intake','done_videos','smoke_gates'})
        self.assertNotIn('admission',operations(config));self.assertEqual(config,before)
        validate(config)

    def test_specified_policy_and_draft_nulls_validate_without_activation(self):
        config,snapshot,issues,labels=fixture();before=copy.deepcopy(config)
        validate(config);self.assertEqual(controls(config)['admission'],config['operations']['admission'])
        self.assertEqual(config,before)
        policy=config['operations']['admission']
        for key in list(policy):
            if key not in ('version','status'):policy[key]=None
        policy['status']='draft';validate(config)
        self.assertEqual(ar.review(config,snapshot,issues,labels,NOW)['status'],'BLOCKED')
        self.assertTrue(any('Admission policy is draft' in n for n in watcher(config)['diagnostics']))

    def test_identity_conflicts_types_currency_and_unknown_fields_reject(self):
        mutations=[lambda c:c['operations']['autonomy'].update(allowed_submitters=['author']),
                   lambda c:c['operations']['admission'].update(max_in_flight_items=True),
                   lambda c:c['operations']['admission'].update(version=True),
                   lambda c:c['operations']['admission']['costs'].update(max_per_item=1.0),
                   lambda c:c['operations']['admission']['costs'].update(currency='EUR'),
                   lambda c:c['operations']['admission'].update(extra='unsupported'),
                   lambda c:c['operations']['admission']['starts'].update(timezone='../UTC')]
        for mutation in mutations:
            config,*_=fixture();mutation(config)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):validate(config)


class AdmissionReviewTests(unittest.TestCase):
    def setUp(self):self.config,self.snapshot,self.issues,self.labels=fixture()
    def assess(self):return ar.review(self.config,self.snapshot,self.issues,self.labels,NOW)
    def rebind(self):self.snapshot['policy_sha256']=ar.digest(self.config['operations']['admission'])
    def allowed(self):return [r['issue_id'] for r in self.assess()['allowed']]

    def test_request_binding_and_input_preservation(self):
        before=copy.deepcopy((self.config,self.snapshot,self.issues,self.labels));result=self.assess()
        self.assertEqual(result['status'],'RECORDED_POLICY_SATISFIED');self.assertEqual(result['allowed'],[{k:self.snapshot['requests'][0][k] for k in ('request_id','issue_id','cycle_id','kind','reserve')}])
        self.assertFalse(result['enforced']);self.assertFalse(result['independently_verified'])
        self.assertEqual(before,(self.config,self.snapshot,self.issues,self.labels))

    def test_author_actor_permission_label_and_repository_are_not_interchangeable(self):
        mutations=[lambda s:s['requests'][0].update(author='labeler'),
                   lambda s:s['requests'][0]['permission'].update(actor='author'),
                   lambda s:s['requests'][0]['event'].update(label='other'),
                   lambda s:s.update(repository='SYNTHETIC/other'),
                   lambda s:s.update(policy_sha256='0'*64),
                   lambda s:s['requests'][0]['permission'].update(decision='denied')]
        original=copy.deepcopy(self.snapshot)
        for mutate in mutations:
            self.snapshot=copy.deepcopy(original);mutate(self.snapshot)
            with self.subTest(mutation=mutate):self.assertEqual(self.allowed(),[])

    def test_named_actor_and_legacy_author_modes_use_only_their_explicit_principal(self):
        policy=self.config['operations']['admission'];policy['identity']={'kind':'label_actor_accounts','accounts':['labeler']}
        self.snapshot['requests'][0]['permission']=None;self.rebind();self.assertEqual(self.allowed(),['42'])
        policy['identity']['accounts']=['author'];self.rebind();self.assertEqual(self.allowed(),[])
        policy['identity']={'kind':'legacy_submitters'};self.config['operations']['autonomy']['allowed_submitters']=['author'];self.rebind()
        self.assertEqual(self.allowed(),['42'])

    def test_missing_stale_future_and_late_accounting_are_unknown(self):
        original=copy.deepcopy(self.snapshot)
        mutations=[lambda s:s['period'].update(accounting_complete=False),
                   lambda s:s['period'].update(accounting_complete=None),
                   lambda s:s['period'].update(accounted_through=(NOW-timedelta(seconds=1)).isoformat()),
                   lambda s:s['period'].update(accounted_through=(NOW+timedelta(seconds=1)).isoformat()),
                   lambda s:s.update(observed_at=(NOW-timedelta(seconds=301)).isoformat()),
                   lambda s:s['coverage'].update(complete=False),
                   lambda s:s['period'].update(spent=None)]
        for mutate in mutations:
            self.snapshot=copy.deepcopy(original);mutate(self.snapshot)
            with self.subTest(mutation=mutate):
                self.assertEqual(self.assess()['status'],'UNKNOWN');self.assertEqual(self.allowed(),[])
        self.snapshot=original;self.snapshot['period']['accounted_through']='2026-11-03T13:00:00+01:00'
        self.assertEqual(self.allowed(),['42'])

    def test_completed_admissions_count_and_uncertain_cycles_hold_capacity(self):
        completed=cycle(state='completed',reserved='0');completed.update(completed_at=NOW.isoformat(),completion='draft_pr')
        self.snapshot['cycles']=[completed];self.snapshot['period']['spent']='1.00'
        self.config['operations']['admission']['starts']['maximum']=1;self.rebind();self.assertEqual(self.allowed(),[])
        self.assertIn('Recorded calendar-day start allowance is exhausted',self.assess()['decisions'][0]['reasons'])
        self.config['operations']['admission']['starts']['maximum']=8
        self.config['operations']['admission']['max_in_flight_items']=1;self.rebind()
        self.snapshot['cycles']=[cycle(state='unknown')];self.snapshot['period']['reserved']='0.50'
        self.assertEqual(self.allowed(),[])
        self.snapshot['cycles'][0].update(state='completed',completed_at=NOW.isoformat(),completion='draft_pr')
        self.assertEqual(self.assess()['status'],'UNKNOWN')  # Outstanding reserve prevents terminal release.

    def test_retry_keeps_lifetime_cost_and_does_not_consume_new_start(self):
        self.snapshot['cycles']=[cycle('42',spent='2.00',reserved='0.50')]
        self.snapshot['cycles'][0]['admitted_at']='2026-10-20T10:00:00+00:00'
        self.snapshot['period'].update(spent='0.10',reserved='0.50')
        self.snapshot['requests'][0].update(kind='retry',reserve='0.50')
        self.config['operations']['admission']['starts']['maximum']=1;self.rebind()
        self.assertEqual(self.allowed(),['42'])
        self.snapshot['requests'][0]['reserve']='0.500001';self.assertEqual(self.allowed(),[])
        self.snapshot['requests'][0].update(kind='start',reserve='0');self.assertEqual(self.allowed(),[])

    def test_period_spend_cannot_understate_current_period_cycle_spend(self):
        self.snapshot['cycles']=[cycle(spent='2.00',reserved='0')]
        self.snapshot['period']['spent']='1.99'
        self.assertEqual(self.assess()['status'],'UNKNOWN')

    def test_period_reservations_and_sequential_proposals_use_exact_decimals(self):
        self.snapshot['period']['spent']='19.50';self.snapshot['requests'][0]['reserve']='0.30'
        self.snapshot['requests'].append(request('43'));self.snapshot['requests'][1]['reserve']='0.30'
        self.issues.append(dict(self.issues[0],id='43'))
        self.assertEqual(self.allowed(),['42'])
        self.snapshot['requests'].reverse();self.assertEqual(self.allowed(),['42'])
        self.snapshot['period']['reserved']='0.01';self.assertEqual(self.assess()['status'],'UNKNOWN')

    def test_zero_limits_deny_even_zero_requested_cost(self):
        self.snapshot['requests'][0]['reserve']='0'
        for target,key in [('policy','max_in_flight_items'),('starts','maximum'),('costs','max_per_item'),('period','maximum')]:
            config=copy.deepcopy(self.config);policy=config['operations']['admission']
            obj=policy if target=='policy' else policy['starts'] if target=='starts' else policy['costs'] if target=='costs' else policy['costs']['period']
            obj[key]=0 if target in ('policy','starts') else '0';snapshot=copy.deepcopy(self.snapshot);snapshot['policy_sha256']=ar.digest(policy)
            self.assertEqual(ar.review(config,snapshot,self.issues,self.labels,NOW)['allowed'],[])

    def test_duplicate_requests_events_cycles_and_ambiguous_issue_snapshots_fail_closed(self):
        original=copy.deepcopy(self.snapshot)
        for mutation in ('request','event','cycle','issue'):
            self.snapshot=copy.deepcopy(original);self.issues=fixture()[2]
            other=request('43');self.snapshot['requests'].append(other);self.issues.append(dict(self.issues[0],id='43'))
            if mutation=='request':other['request_id']='request-42'
            elif mutation=='event':other['event']['id']='event-42'
            elif mutation=='cycle':other['cycle_id']='cycle-42'
            else:self.issues.append(dict(self.issues[0]))
            self.assertEqual(self.assess()['status'],'UNKNOWN');self.assertEqual(self.allowed(),[])

    def test_permission_freshness_and_missing_timezone_data_do_not_guess(self):
        self.snapshot['requests'][0]['permission']['observed_at']=(NOW-timedelta(seconds=301)).isoformat()
        self.assertEqual(self.assess()['status'],'UNKNOWN')
        self.snapshot=fixture()[1]
        self.config['operations']['admission']['starts']['timezone']='Missing/Zone';self.rebind()
        self.assertEqual(self.assess()['status'],'UNKNOWN');self.assertIn('unavailable',self.assess()['problems'][0])

    def test_utc_needs_no_external_timezone_database(self):
        with patch('admission_review.ZoneInfo',side_effect=ZoneInfoNotFoundError('no database')):
            self.assertEqual(self.allowed(),['42'])

    def test_dst_calendar_day_bounds_when_zone_data_is_available(self):
        try:ZoneInfo('America/New_York')
        except ZoneInfoNotFoundError:self.skipTest('IANA database unavailable; unavailable-zone fail-closed test remains active')
        spring=ar.period_bounds(datetime(2026,3,8,12,tzinfo=timezone.utc),'calendar_day','America/New_York')
        autumn=ar.period_bounds(datetime(2026,11,1,12,tzinfo=timezone.utc),'calendar_day','America/New_York')
        self.assertEqual(spring[1]-spring[0],timedelta(hours=23))
        self.assertEqual(autumn[1]-autumn[0],timedelta(hours=25))


class AdmissionCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.parent=Path(self.temp.name)
        self.factory=self.parent/'.software-factory';self.now=datetime.now(timezone.utc)
        self.config,self.snapshot,self.issues,self.labels=fixture(self.now)
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        for name,body in render(self.config,research).items():
            path=self.factory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(body,encoding='utf-8')
        self.paths={}
        for name,value in [('issues',self.issues),('labels',self.labels),('snapshot',self.snapshot)]:
            path=self.parent/(name+'.json');path.write_text(json.dumps(value),encoding='utf-8');self.paths[name]=path
    def bytes(self):return {str(p.relative_to(self.parent)):p.read_bytes() for p in self.parent.rglob('*') if p.is_file()}
    def invoke(self,extra=(),command='select'):
        argv=[sys.executable,'-B',str(ROOT/'scripts/run.py'),'--factory',str(self.factory),command,
              '--issues',str(self.paths['issues']),'--issue-policy',str(self.paths['labels']),*extra]
        return subprocess.run(argv,capture_output=True,text=True,timeout=15)

    def test_actual_run_select_and_plan_require_exact_snapshot_and_preserve_every_file(self):
        before=self.bytes()
        for command in ('select','plan'):
            missing=self.invoke(command=command);self.assertEqual(missing.returncode,0,missing.stderr)
            self.assertEqual(json.loads(missing.stdout)['issues']['eligible'],[])
            allowed=self.invoke(['--admission-snapshot',str(self.paths['snapshot'])],command)
            self.assertEqual(allowed.returncode,0,allowed.stderr)
            result=json.loads(allowed.stdout);self.assertEqual([r['id'] for r in result['issues']['eligible']],['42'])
            self.assertFalse(result['admission_review']['enforced'])
        self.assertEqual(self.bytes(),before)

    def test_rebound_snapshot_cannot_admit_a_different_current_issue_author(self):
        self.issues[0]['submitter']='different-author';self.paths['issues'].write_text(json.dumps(self.issues),encoding='utf-8')
        result=self.invoke(['--admission-snapshot',str(self.paths['snapshot'])])
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['issues']['eligible'],[])

    def test_satisfied_review_does_not_override_existing_run_filters(self):
        original=copy.deepcopy(self.config)
        for case in ('stop','workers','time','rate','known-task','excluded','dependency'):
            config=copy.deepcopy(original);issues=copy.deepcopy(self.issues);plan={'tasks':[]}
            runs=self.parent/'runs'
            if case=='workers':config['budget']['max_workers']=0
            elif case=='time':config['budget']['max_minutes']=0
            elif case=='known-task':plan['tasks']=[{'id':'42','status':'done'}]
            elif case=='excluded':issues[0]['labels'].append('paused')
            elif case=='dependency':issues[0]['depends_on']=['other']
            with self.subTest(case=case),patch('run.kill_switch',return_value='synthetic stop' if case=='stop' else None),patch('run.dispatched_last_hour',return_value=10 if case=='rate' else 0):
                result=run.select(self.factory,config,plan,runs,issues,self.now,self.labels,self.snapshot)
                self.assertEqual(result['issues']['eligible'],[])

    def test_copied_dashboard_accepts_metadata_without_an_assessor_dependency(self):
        before=self.bytes();output=self.parent/'overview.json'
        result=subprocess.run([sys.executable,'-B',str(self.factory/'dashboard/dashboard.py'),'--format','json','--output',str(output)],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('Admission policy is specified',output.read_text(encoding='utf-8'))
        self.assertFalse((self.factory/'dashboard/admission_review.py').exists())
        after=self.bytes();del after['overview.json'];self.assertEqual(after,before)

    def test_malformed_duplicate_and_oversized_snapshot_files_refuse(self):
        for raw in ('{"version":1,"version":1}', ' '* (ar.MAX_BYTES+1)):
            self.paths['snapshot'].write_text(raw,encoding='utf-8');before=self.bytes()
            result=self.invoke(['--admission-snapshot',str(self.paths['snapshot'])])
            self.assertNotEqual(result.returncode,0);self.assertEqual(before,self.bytes())

    def test_standalone_assessment_uses_factory_policy_without_writing(self):
        before=self.bytes()
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/admission_review.py'),'--factory',str(self.factory),
             '--snapshot',str(self.paths['snapshot']),'--issues',str(self.paths['issues']),
             '--issue-policy',str(self.paths['labels'])],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'RECORDED_POLICY_SATISFIED')
        self.assertEqual(self.bytes(),before)


if __name__=='__main__':unittest.main()
