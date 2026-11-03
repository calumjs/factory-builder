"""Combined recorded tallies, explicit assessments and supplied trace presentation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import dashboard
import run_traces
from gates import gate_rows
from integrity import check, digest
from scaffold import ROOT, render
from test_run_traces import fixture, NOW
import update_operations as updater


class TracesDashboardIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.root=self.base/'factory'
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        config['acceptance']=['Synthetic acceptance criterion']
        config['operations']={'smoke_gates':{'target_kind':'no_release','post_merge_applicability':'not_applicable',
            'post_merge_rationale':'Synthetic no-release scope','accepted_by':'Synthetic owner',
            'pre_merge':'Synthetic G1','targeted':'Synthetic G2'},
            'done_videos':{'enabled':True,'triggers':['pre_merge_preview']}}
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        for name,body in render(config,research).items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
        path=self.root/'verification.md';lines=[]
        for line in path.read_text().splitlines():
            if line.startswith(('| G1 |','| G2 |','| A1 |','| V2 |')):
                cells=[v.strip() for v in line.strip('|').split('|')];cells[3]='fixture'
                cells[5:11]=['a'*40,'PASSED','private fixture evidence','fixture-target',NOW.isoformat(),'0']
                if cells[0]=='V2':cells[4]='no';cells[6]='FAILED';cells[10]='1'
                line='| '+' | '.join(cells)+' |'
            lines.append(line)
        path.write_bytes(('\n'.join(lines)+'\n').encode())

    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_assessment_tally_and_explicit_traces_remain_independent(self):
        before=self.snapshot()
        data=dashboard.read(self.root,now=NOW,assessment={'subject':'a'*40,'stage':'post-merge','actual_target':None,'reason':'Synthetic no-release assessment'})
        self.assertEqual(data['assessment']['state'],'satisfied')
        original=copy.deepcopy(data)
        supplied=fixture();supplied['runs'][0]['evidence_ref']='PRIVATE_TRACE_REFERENCE'
        traces=run_traces.summarize(supplied,now=NOW)
        html=dashboard.page(data,supplemental_html=run_traces.panel(traces))
        self.assertIn('SATISFIES RECORD RULES',html)
        self.assertIn('<span aria-hidden="true">3/4</span>',html)
        self.assertIn('1</b> recorded NOT APPLICABLE',html)
        self.assertIn('V2 WAIVED',html);self.assertIn('Supplied private run traces',html)
        self.assertIn('not independently verified',html);self.assertNotIn('PRIVATE_TRACE_REFERENCE',html)
        self.assertEqual(data,original);self.assertNotIn('supplied_run_traces',data)
        default=dashboard.read(self.root,now=NOW)
        self.assertNotIn('assessment',default);self.assertNotIn('supplied_run_traces',default)
        self.assertNotIn('Supplied private run traces',dashboard.page(default))
        self.assertEqual(before,self.snapshot())

    def test_published_predecessor_migrates_only_explicitly_to_both_presentations(self):
        prior=(ROOT/'scripts/fixtures/pre_trace_dashboard.txt').read_bytes()
        self.assertEqual(digest(prior),updater.PRE_TRACE_DASHBOARD['dashboard.py'])
        path=self.root/'dashboard/dashboard.py';path.write_bytes(prior)
        manifest_path=self.root/'manifest.json';manifest=json.loads(manifest_path.read_bytes())
        manifest['contracts']['dashboard/dashboard.py']=digest(prior);manifest_path.write_bytes(json.dumps(manifest).encode())
        check(self.root,quiet=True);before=self.snapshot()
        self.assertFalse(updater.prepare(self.root,{})[2])
        assumptions=json.loads((self.root/'config.json').read_bytes())['assumptions']
        _,_,without_opt_in,_=updater.prepare(self.root,{},assumptions_update=assumptions)
        self.assertNotIn('dashboard/dashboard.py',without_opt_in)
        self.assertEqual(before,self.snapshot())
        prepared=updater.prepare(self.root,{},context_runtime=True)
        self.assertEqual(before,self.snapshot());self.assertEqual(set(prepared[2]),{'dashboard/dashboard.py','manifest.json'})
        backup=updater.apply(*prepared,prepared[3]);check(self.root,quiet=True)
        self.assertEqual((backup/'dashboard/dashboard.py').read_bytes(),prior)
        self.assertEqual((self.root/'verification.md').read_bytes(),before['verification.md'])
        output=self.base/'copied-overview.html'
        result=subprocess.run([sys.executable,'-B',str(path),'--output',str(output)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('recorded NOT APPLICABLE',output.read_text());self.assertNotIn('Supplied private run traces',output.read_text())
        trace=self.base/'explicit-traces.json';trace.write_bytes(json.dumps(fixture()).encode())
        result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/run_traces.py'),'--factory',str(self.root),
            '--trace',str(trace),'--output',str(self.base/'explicit-overview.html'),'--as-of',NOW.isoformat()],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        combined=(self.base/'explicit-overview.html').read_text()
        self.assertIn('recorded NOT APPLICABLE',combined);self.assertIn('Supplied private run traces',combined)
        self.assertFalse((self.root/'dashboard/run_traces.py').exists())
        self.assertEqual(gate_rows((self.root/'verification.md').read_text())['V2']['result'],'FAILED')


if __name__=='__main__':unittest.main()
