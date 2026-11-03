"""Execute guide JavaScript with in-memory doubles, never Playwright or a browser."""
import json
import shutil
import subprocess
import unittest
from scaffold import ROOT, render
from phase_test_support import phase_text


class TargetedLatencyExampleTests(unittest.TestCase):
    def guide(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        return phase_text(render(config,research),'verify')

    def test_generated_example_preserves_scope_and_parity_constraints(self):
        text=self.guide()
        for phrase in ('Mutation delay was not exercised','A transport response alone is not a',
                       'Routing disables HTTP','service-worker-intercepted','not a measurement or',
                       'Keep separate interruption-during-write','beforeunload',
                       'zero required tests collected','missing required result is not a pass',
                       'do not sum retries as independent tests','--list','--repeat-each=2',
                       'do not install packages','no production-write or deployment authority'):
            self.assertIn(phrase,text)

    def test_extracted_javascript_ordering_failures_and_cleanup(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable; no installation attempted; snippet execution unverified')
        snippet=self.guide().split('### Optional targeted mutation-delay probe',1)[1].split('```javascript\n',1)[1].split('```',1)[0]
        harness=r'''
const assert = require('node:assert/strict');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const example = new AsyncFunction('page','baseURL','armCommittedSave','expectedMutation','assertPersistedValue','expectedValue','setTimeout', SNIPPET);
async function scenario(mode) {
  const events=[];let routeHandler;let resolveCommit,rejectCommit;let delayCount=0;
  const page={
    route:async(url,handler)=>{assert.equal(url,'http://fixture.invalid/api/items/fixture-item');routeHandler=handler;events.push('registered');},
    unroute:async(url,handler)=>{assert.equal(handler,routeHandler);events.push('removed');},
    getByRole:(role,options)=>{assert.equal(role,'button');assert.equal(options.name,'Save');return {click:async()=>{
      events.push('click');
      if(mode!=='unmatched') await routeHandler({request:()=>({method:()=>mode==='get'?'GET':'PATCH'}),fallback:async()=>{
        events.push('dispatched');if(mode==='route-failure')throw new Error('route failed');
      }});
      if(mode==='commit-failure'||mode==='commit-timeout')rejectCommit(new Error(mode));
      else {events.push('committed');resolveCommit();}
    }};},
    reload:async()=>{assert.ok(events.includes('committed'));events.push('reload');}
  };
  const arm=()=>{events.push('armed');return new Promise((resolve,reject)=>{resolveCommit=resolve;rejectCommit=reject;});};
  const durable=async()=>{assert.equal(events.at(-1),'reload');events.push('durable');};
  const timer=(resolve,ms)=>{assert.equal(ms,750);delayCount++;events.push('delay');resolve();};
  if(mode==='pass') {
    await example(page,'http://fixture.invalid',arm,{},durable,{},timer);
    assert.deepEqual(events,['registered','armed','click','delay','dispatched','committed','reload','durable','removed']);
  } else {
    await assert.rejects(example(page,'http://fixture.invalid',arm,{},durable,{},timer));
    assert.ok(events.includes('removed'));assert.ok(!events.includes('reload'));assert.ok(!events.includes('durable'));
  }
  assert.equal(delayCount,mode==='get'||mode==='unmatched'?0:1);
}
(async()=>{for(const mode of ['pass','get','unmatched','commit-failure','commit-timeout','route-failure'])await scenario(mode);console.log('six synthetic scenarios passed');})().catch(error=>{console.error(error);process.exitCode=1;});
'''.replace('SNIPPET',json.dumps(snippet))
        result=subprocess.run([node,'-e',harness],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('six synthetic scenarios passed',result.stdout)


if __name__=='__main__':unittest.main()
