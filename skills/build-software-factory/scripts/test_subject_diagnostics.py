"""Abbreviation hints explain exact-subject failures without resolving identity."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from gates import assess, problems, subject_abbreviation_hint, waivers
from scaffold import ROOT, render

FULL40='abcdef0123456789abcdef0123456789abcdef01'
FULL64='abcdef0123456789'*4
GENERIC='G3 has stale or missing revision'


class SubjectDiagnosticTests(unittest.TestCase):
    @staticmethod
    def row(subject,required='yes'):
        return '| G3 | post-merge | Synthetic observation | fixture | '+required+' | '+subject+' | PASSED | synthetic-reference | fixture-artifact | 2026-11-01T00:00:00Z | 0 |\n'

    def assess_row(self,recorded,requested,required='yes'):
        return problems(self.row(recorded,required),'post-merge',requested,{'G3':{'stage':'post-merge','applicability':'applicable'}},'fixture-artifact')

    def test_supplied_short_subject_remains_blocked_with_actionable_fixed_hint(self):
        for full in (FULL40,FULL64):
            for size in (7,12,len(full)-1):
                with self.subTest(length=len(full),size=size):
                    found=self.assess_row(full,full[:size])
                    self.assertEqual(len(found),1);self.assertTrue(found[0].startswith(GENERIC))
                    self.assertIn('looks like a hexadecimal abbreviation',found[0])
                    self.assertIn('Independently verify the evidence provenance',found[0])
                    self.assertIn('exact full recorded subject with --revision',found[0])
                    self.assertIn('prefixes are not accepted or resolved',found[0])
                    self.assertNotIn(full,found[0]);self.assertNotIn(full[:size],found[0])

    def test_recorded_short_subject_requires_new_bound_evidence_not_auto_expansion(self):
        for full in (FULL40,FULL64):
            found=self.assess_row(full[:7],full)
            self.assertEqual(len(found),1);self.assertTrue(found[0].startswith(GENERIC))
            self.assertIn('recorded subject looks like a hexadecimal abbreviation',found[0])
            self.assertIn('Verify provenance and obtain a new evidence record',found[0])
            self.assertIn('do not automatically expand the existing observation',found[0])
            self.assertNotIn('pass the exact full recorded subject',found[0])

    def test_shorter_than_seven_characters_has_no_hint_in_either_direction(self):
        for size in (1,6):
            for recorded,requested in ((FULL40,FULL40[:size]),(FULL40[:size],FULL40)):
                self.assertEqual(self.assess_row(recorded,requested),[GENERIC])

    def test_nonmatching_full_or_short_and_nonhex_identifiers_remain_generic(self):
        cases=((FULL40,'f'*40),(FULL64,'f'*64),(FULL40,'fffffff'),('fffffff',FULL40),
               ('build-123456789','build-1'),('release-'+'x'*32,'release'),('',FULL40),
               (FULL40,'private-nonhex-sentinel'))
        for recorded,requested in cases:
            with self.subTest(recorded=recorded,requested=requested):
                self.assertEqual(self.assess_row(recorded,requested),[GENERIC])

    def test_two_full_length_identifiers_are_not_treated_as_abbreviations(self):
        for recorded,requested in (('a'*40,'a'*64),('a'*64,'a'*40)):
            self.assertIsNone(subject_abbreviation_hint(recorded,requested))
            self.assertEqual(self.assess_row(recorded,requested),[GENERIC])

    def test_exact_subjects_keep_existing_semantics_including_opaque_and_short_ids(self):
        for subject in (FULL40,FULL64,'abcdef0','opaque-artifact-v1'):
            self.assertEqual(self.assess_row(subject,subject),[])
            self.assertEqual(self.assess_row(subject,' '+subject+' '),[])
        self.assertEqual(self.assess_row(FULL40,FULL40.upper()),[GENERIC])
        self.assertTrue(self.assess_row(FULL40,FULL40[:7].upper()))

    def test_optional_row_is_still_a_waiver_without_subject_mismatch(self):
        self.assertEqual(self.assess_row(FULL40,FULL40[:7],'no'),[])
        self.assertEqual(self.assess_row(FULL40[:7],FULL40,'no'),[])
        self.assertEqual(waivers(self.row(FULL40,'no'),'post-merge'),['G3 WAIVED (recorded PASSED)'])

    def test_diagnostic_pure_path_never_calls_git_processes_or_files(self):
        with (patch.object(subprocess,'Popen',side_effect=AssertionError('no process')),
              patch.object(Path,'open',side_effect=AssertionError('no file access'))):
            self.assertTrue(self.assess_row(FULL40,FULL40[:7]))
            self.assertTrue(self.assess_row(FULL40[:7],FULL40))

    def test_cli_mismatch_blocks_without_writes_and_exact_subject_still_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'factory'
            config=json.loads((ROOT/'assets/example-config.json').read_text(encoding='utf-8'))
            config['operations']={'smoke_gates':{'target_kind':'artifact','deployed_url':'fixture-artifact'}}
            research=json.loads((ROOT/'assets/example-research.json').read_text(encoding='utf-8'))
            for name,body in render(config,research).items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body.encode('utf-8'))
            path=root/'verification.md'
            text='\n'.join(self.row(FULL40).strip() if line.startswith('| G3 |') else line for line in path.read_text(encoding='utf-8').splitlines())+'\n'
            path.write_bytes(text.encode('utf-8'))
            snapshot=lambda:{p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
            before=snapshot()
            with patch.object(subprocess,'Popen',side_effect=AssertionError('no external lookup')):
                self.assertTrue(assess(root,'post-merge',FULL40[:7],'fixture-artifact'))
            command=[sys.executable,'-B',str(ROOT/'scripts/gates.py'),'--factory',str(root),'--stage','post-merge','--target','fixture-artifact','--revision']
            short=subprocess.run(command+[FULL40[:7]],capture_output=True,text=True)
            self.assertEqual(short.returncode,1,short.stderr);self.assertIn('exact full recorded subject',short.stdout)
            full=subprocess.run(command+[FULL40],capture_output=True,text=True)
            self.assertEqual(full.returncode,0,full.stdout+full.stderr)
            self.assertEqual(before,snapshot())


if __name__=='__main__':unittest.main()
