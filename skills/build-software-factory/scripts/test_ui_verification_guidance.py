"""Validate rendered guidance and JS event inventory with doubles, not a browser."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from integrity import check, digest
from scaffold import ROOT, render


class UiVerificationGuidanceTests(unittest.TestCase):
    def files(self):
        config=json.loads((ROOT/'assets/example-config.json').read_text())
        research=json.loads((ROOT/'assets/example-research.json').read_text())
        return render(config,research)

    def test_generated_build_link_resolves_to_hashed_canonical_guide(self):
        files=self.files();canonical=(ROOT/'references/ui-verification.md').read_text()
        self.assertEqual(files['ui-verification.md'],canonical)
        self.assertIn('[running-app UI verification](ui-verification.md)',files['phase-build-guide.md'])
        self.assertEqual(json.loads(files['manifest.json'])['contracts']['ui-verification.md'],digest(canonical))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,body in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode())
            check(root,quiet=True)

    def test_guide_preserves_acceptance_privacy_and_authority_boundaries(self):
        text=' '.join(self.files()['ui-verification.md'].split())
        for phrase in ('every applicable acceptance criterion','1440px and 390px',
                       'light and dark when both are supported','non-default loopback port',
                       'Never stop, reuse, reconfigure or overwrite an already-running server',
                       'Stop only your owned process','Verify must take its own screenshots',
                       'never reuse the builder','console errors/assertions, uncaught page errors',
                       'failed transport requests and HTTP 4xx/5xx responses separately',
                       'A pre-existing base failure is not automatically nonblocking',
                       'still-required acceptance','explicitly waived','narrow documented exception',
                       'Do not blanket-ignore','existing A-rows/G2','WAIVED rows',
                       'no new UI gate','does not attest that this procedure ran',
                       'Do not retry a denied route','not running-app evidence'):
            self.assertIn(phrase,text)

    def test_actual_snippet_handles_separate_signals_bounds_privacy_and_cleanup(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable; no installation attempted; collector execution unverified')
        text=(ROOT/'references/ui-verification.md').read_text()
        snippet=text.split('```javascript\n',1)[1].split('```',1)[0]
        harness=r'''
const assert = require('node:assert/strict');
const {EventEmitter} = require('node:events');
const collect = new Function(SNIPPET + '; return collectUiSignals;')();
const SECRET = 'PRIVATE_TOKEN_SENTINEL';
class Page extends EventEmitter {url(){return 'http://127.0.0.1:4177/profile?token='+SECRET+'#'+SECRET;}}
const config=()=>({subject:'a'.repeat(40),role:'verify',pageLabel:'profile-page',routeLabels:[['http://127.0.0.1:4177/profile','profile']]});
const noRead=()=>{throw new Error('must not read '+SECRET);};
const request=(url='http://u:'+SECRET+'@127.0.0.1:4177/profile?token='+SECRET,method='GET')=>({url:()=>url,method:()=>method,failure:noRead,headers:noRead,postData:noRead});
const response=(status,url,method)=>({status:()=>status,url:()=>url,request:()=>request(url,method),headers:noRead,body:noRead});
// Each real API callback path is exercised separately, with private payload traps.
const page=new Page();let unrelated=0;page.on('console',()=>unrelated++);
const capture=collect(page,config());capture.setStep('a1-save');
page.emit('console',{type:()=>'log',text:noRead,args:noRead});
page.emit('console',{type:()=>'error',text:noRead,args:noRead});
page.emit('console',{type:()=>'assert',text:noRead,args:noRead});
page.emit('pageerror',{get message(){return noRead();},get stack(){return noRead();}});
page.emit('requestfailed',request());
page.emit('response',response(404,'http://127.0.0.1:4177/profile?secret='+SECRET,'GET'));
page.emit('response',response(503,'https://private.invalid/'+SECRET,'POST'));
page.emit('response',response(200,'http://127.0.0.1:4177/profile','GET'));
page.emit('response',response(302,'http://127.0.0.1:4177/profile','GET'));
let snapshot=capture.snapshot();
assert.deepEqual(snapshot.events.map(e=>e.kind),['console_error','console_error','page_error','request_failed','http_error','http_error']);
assert.equal(snapshot.events.filter(e=>e.kind==='request_failed').length,1);
assert.deepEqual(snapshot.events.filter(e=>e.kind==='http_error').map(e=>e.status),[404,503]);
assert.equal(snapshot.events[3].requestRoute,'profile');assert.equal(snapshot.events[5].requestRoute,'unmapped');
assert.ok(snapshot.events.every(e=>e.step==='a1-save'&&e.pageRoute==='profile'));
for(const value of [SECRET,'private.invalid','http://','https://','token='])assert.ok(!JSON.stringify(snapshot).includes(value));
assert.equal(snapshot.callbackFailed,false);assert.equal(snapshot.dropped,0);
snapshot.events[0].kind=SECRET;assert.equal(capture.snapshot().events[0].kind,'console_error');
capture.detach();capture.detach();page.emit('console',{type:()=>'error'});
assert.equal(capture.snapshot().events.length,6);assert.equal(capture.snapshot().detached,true);assert.equal(unrelated,4);
assert.equal(page.listenerCount('console'),1);assert.equal(page.listenerCount('response'),0);
// Bounds are explicit, not silently clean; callback exceptions are redacted.
const boundedPage=new Page();const bounded=collect(boundedPage,{...config(),limit:3});
for(let i=0;i<50;i++)boundedPage.emit('pageerror',new Error(SECRET));
assert.equal(bounded.snapshot().events.length,3);assert.equal(bounded.snapshot().dropped,47);
boundedPage.emit('requestfailed',{url:noRead,method:()=>'GET'});
assert.equal(bounded.snapshot().callbackFailed,true);assert.ok(!JSON.stringify(bounded.snapshot()).includes(SECRET));
const invalidPage=new Page();const invalid=collect(invalidPage,config());
invalidPage.emit('response',response('404','http://127.0.0.1:4177/profile','GET'));
assert.equal(invalid.snapshot().callbackFailed,true);assert.equal(invalid.snapshot().events.length,0);
invalidPage.emit('requestfailed',request('x'.repeat(4097),SECRET));
assert.equal(invalid.snapshot().events[0].requestRoute,'unmapped');assert.equal(invalid.snapshot().events[0].method,'OTHER');
// Strict metadata protects against accidental object/string coercion and bad aliases.
for(const change of [{subject:{toString:()=> 'a'.repeat(40),private:SECRET}},{subject:'abc1234'},{subject:'a'.repeat(40)+'\n'},
  {role:'admin'},{pageLabel:SECRET+'\n'},{pageLabel:'page\n'},{limit:0},{limit:501},{limit:true},{limit:1.5},
  {routeLabels:Array.from({length:65},(_,i)=>['http://fixture.invalid/'+i,'route'])},
  {routeLabels:[['http://u:'+SECRET+'@fixture.invalid/','route']]},
  {routeLabels:[['http://fixture.invalid/?secret='+SECRET,'route']]},
  {routeLabels:[['http://fixture.invalid/#'+SECRET,'route']]},
  {routeLabels:[['file:///private/'+SECRET,'route']]},
  {routeLabels:[['http://fixture.invalid/','route'],['http://fixture.invalid/','other']]},
  {routeLabels:[['http://fixture.invalid/','unsafe label']]},{routeLabels:[['http://fixture.invalid/','page\n']]}]) {
  assert.throws(()=>collect(new Page(),{...config(),...change}),error=>!error.message.includes(SECRET));
}
assert.throws(()=>capture.setStep('private\n'+SECRET),error=>!error.message.includes(SECRET));
const longId=collect(new Page(),{...config(),subject:'b'.repeat(64)});assert.equal(longId.snapshot().subject.length,64);
console.log('separate signals, privacy, bounds, metadata and detach probes passed');
'''.replace('SNIPPET',json.dumps(snippet))
        result=subprocess.run([node,'-e',harness],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('separate signals, privacy, bounds, metadata and detach probes passed',result.stdout)


if __name__=='__main__':unittest.main()
