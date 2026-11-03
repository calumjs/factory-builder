"""Execute emitted verification argv only against disposable synthetic snapshots."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import recover_factory
from recover_factory import dumps, rawhash, verification_argv
from scaffold import ROOT, render


PREFIX='VERIFY OUTPUT ARGV: '


class RecoveryVerificationArgvTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.parent=Path(self.temp.name)/"fixture space 'quote' & $literal [set] café";self.parent.mkdir()
        self.base=self.parent/'accepted baseline';self.source=self.parent/'reviewed source'
        self.output=self.parent/"recovered 'output' & $literal [one]"
        config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
        research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
        files=render(config,research)
        for root in (self.base,self.source):
            for name,body in files.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
        self.pin=rawhash((self.base/'manifest.json').read_bytes())
        policy=self.source/'policy.md';policy.write_bytes(policy.read_bytes()+b'\nSYNTHETIC reviewed instruction.\n')
        self.decisions=self.parent/'named decisions.json'
        self.decisions.write_text(dumps({'accept_changed':[{'path':'policy.md','reason':'SYNTHETIC reviewed edit'}],
                                         'register':[],'remove':[]}),encoding='utf-8')
        self.command=[sys.executable,'-B',str(ROOT/'scripts/recover_factory.py'),'--factory',str(self.source),
                      '--baseline',str(self.base),'--output',str(self.output),'--baseline-manifest-sha256',self.pin,
                      '--baseline-reference','SYNTHETIC independently accepted fixture','--decisions',str(self.decisions)]

    def snapshot(self,root):
        return {p.relative_to(root).as_posix():None if p.is_dir() else p.read_bytes() for p in root.rglob('*')}

    def run_command(self,argv):return subprocess.run(argv,capture_output=True,text=True,shell=False)

    def preview(self):
        before=self.snapshot(self.parent);result=self.run_command(self.command)
        self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn(PREFIX,result.stdout)
        self.assertEqual(before,self.snapshot(self.parent))
        plans=[line.removeprefix('REVIEW PLAN: ') for line in result.stdout.splitlines() if line.startswith('REVIEW PLAN: ')]
        self.assertEqual(len(plans),1);self.assertRegex(plans[0],r'^[0-9a-f]{64}$')
        return plans[0]

    def test_successful_apply_emits_exact_executable_argv_with_literal_paths(self):
        plan=self.preview();source=self.snapshot(self.source);baseline=self.snapshot(self.base)
        result=self.run_command(self.command+['--apply','--stable-inputs','--approve-plan',plan])
        self.assertEqual(result.returncode,0,result.stderr)
        lines=[line[len(PREFIX):] for line in result.stdout.splitlines() if line.startswith(PREFIX)]
        self.assertEqual(len(lines),1);argv=json.loads(lines[0])
        backup=self.parent/'.factory-recovery-backups'/plan
        self.assertEqual(argv,[sys.executable,'-B',str((ROOT/'scripts/recover_factory.py').resolve()),
                               '--verify-output',str(self.output.resolve()),'--backup',str(backup.resolve()),'--plan-id',plan])
        self.assertIn('\\u00e9',lines[0]);self.assertIn("'output'",argv[4]);self.assertIn('$literal [one]',argv[4])
        self.assertEqual(source,self.snapshot(self.source));self.assertEqual(baseline,self.snapshot(self.base))
        before=self.snapshot(self.parent);verified=self.run_command(argv)
        self.assertEqual(verified.returncode,0,verified.stderr)
        self.assertIn('SNAPSHOT BYTES/COMPLETION VERIFIED; not activated',verified.stdout)
        self.assertNotIn(PREFIX,verified.stdout);self.assertEqual(before,self.snapshot(self.parent))
        # Reusing the exact instruction cannot bless a later changed output.
        handoff=self.output/'release-handoff.md';handoff.write_bytes(handoff.read_bytes()+b'\nSYNTHETIC later change\n')
        before=self.snapshot(self.parent);failed=self.run_command(argv)
        self.assertNotEqual(failed.returncode,0);self.assertNotIn('SNAPSHOT BYTES/COMPLETION VERIFIED',failed.stdout)
        self.assertEqual(before,self.snapshot(self.parent))

    def test_wrong_digest_prints_no_completed_output_instruction_and_writes_nothing(self):
        self.preview();before=self.snapshot(self.parent)
        result=self.run_command(self.command+['--apply','--stable-inputs','--approve-plan','0'*64])
        self.assertNotEqual(result.returncode,0);self.assertNotIn(PREFIX,result.stdout)
        self.assertFalse(self.output.exists());self.assertEqual(before,self.snapshot(self.parent))

    def test_independent_baseline_pin_is_still_required(self):
        command=list(self.command);command[command.index('--baseline-manifest-sha256')+1]='0'*64
        before=self.snapshot(self.parent);result=self.run_command(command)
        self.assertNotEqual(result.returncode,0);self.assertIn('Pinned baseline manifest does not match',result.stderr)
        self.assertNotIn(PREFIX,result.stdout);self.assertEqual(before,self.snapshot(self.parent))

    def test_json_round_trip_keeps_argument_boundaries_without_shell_quoting(self):
        interpreter="C:/Program Files/Python's/python.exe"
        helper=self.parent/"trusted helper's copy.py"
        output="literal path with 'single' and \"double\" quotes; $(not-a-command)"
        backup='literal backup\\path with spaces'
        with patch.object(recover_factory.sys,'executable',interpreter),patch.object(recover_factory,'__file__',str(helper)):
            argv=verification_argv(output,backup,'synthetic-plan')
        decoded=json.loads(json.dumps(argv,ensure_ascii=True))
        self.assertEqual(decoded,[interpreter,'-B',str(helper.resolve()),'--verify-output',output,
                                  '--backup',backup,'--plan-id','synthetic-plan'])


if __name__=='__main__':unittest.main()
