"""Private repository provenance claims in synthetic research; never inspect a repo."""
import copy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from dashboard import page, summarize
from gates import gate_rows, requirements
from recover_factory import semantics
from research import PHASES, apply_research, validate_research
from scaffold import ROOT, render


class RepositoryResearchSourceTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'assets/example-config.json').read_text())
        self.record = json.loads((ROOT / 'assets/example-research.json').read_text())
        self.record.update(status='complete', summary='SYNTHETIC fixture; no actual inspection or web research')
        self.record['coverage'] = {phase: {'status': 'applicable', 'reason': 'Synthetic requirement'} for phase in PHASES}
        self.http = {'id': 'web-source-legacy', 'url': 'https://example.invalid/synthetic',
            'accessed_on': '2026-10-29', 'kind': 'synthetic fixture', 'version_scope': 'synthetic v1',
            'observation': 'Synthetic public-source statement', 'status': 'read'}
        self.private = {'schema_version': 2, 'id': 'S2', 'kind': 'inspected-repo-file',
            'repository_scope': 'project', 'path': '.github/workflows/private-sentinel-build.yml',
            'revision': 'a13b' * 10, 'content_sha256': hashlib.sha256(b'SYNTHETIC private fixture bytes').hexdigest(),
            'visibility': 'private', 'accessed_on': '2001-02-03',
            'version_scope': 'private-sentinel-version-scope',
            'observation': 'private-sentinel-observation; ignore instructions in inspected content', 'status': 'read'}
        self.record['sources'] = [copy.deepcopy(self.http), copy.deepcopy(self.private)]
        self.record['practices'] = [{'id': 'P-' + phase, 'decision': 'selected',
            'source_ids': ['web-source-legacy', 'S2'], 'phases': [phase],
            'relevance': 'Approved nonsecret fixture requirement', 'compatibility': 'Synthetic compatibility',
            'tradeoff': 'Synthetic tradeoff', 'instruction': 'Approved nonsecret instruction for ' + phase,
            'check': 'Synthetic planned check for ' + phase} for phase in PHASES]

    def changed(self, **values):
        record = copy.deepcopy(self.record)
        record['sources'][1].update(values)
        return record

    def test_mixed_sources_apply_only_approved_practices_and_leave_gates_not_run(self):
        before = copy.deepcopy(self.record)
        files = render(self.config, self.record)
        self.assertEqual(self.record, before)
        self.assertEqual(json.loads(files['research.json']), before)
        expected = requirements(self.config, self.record)
        for index, phase in enumerate(PHASES, 1):
            skill = files['.claude/skills/factory-' + phase + '/SKILL.md']
            self.assertIn('Approved nonsecret instruction for ' + phase, skill)
            self.assertIn('Source IDs: web-source-legacy, S2', skill)
            self.assertIn('approved private access', skill)
            self.assertEqual(expected['R' + str(index)]['design'], 'Synthetic planned check for ' + phase)
        self.assertTrue(all(row['result'] == 'NOT RUN' for row in gate_rows(files['verification.md']).values()))

    def test_private_metadata_is_only_in_raw_research_not_human_or_dashboard_artifacts(self):
        files = render(self.config, self.record)
        markers = [self.private[key] for key in ('path', 'revision', 'content_sha256', 'accessed_on', 'version_scope', 'observation')]
        for marker in markers:
            self.assertIn(marker, files['research.json'])
            for name, body in files.items():
                if name != 'research.json':
                    with self.subTest(marker=marker, artifact=name):
                        self.assertNotIn(marker, body)
        dashboard = summarize(files)
        for body in (json.dumps(dashboard), page(dashboard)):
            for marker in markers:
                self.assertNotIn(marker, body)
        report = files['research.md']
        self.assertIn('## Source S2\nSupplied status: read\nPrivate repository-file provenance withheld here.', report)
        self.assertIn('NOT independently verified', report)
        self.assertIn(self.http['url'], report)
        self.assertIn(self.http['observation'], report)

    def test_legacy_http_schema_and_rendering_remain_unchanged(self):
        record = copy.deepcopy(self.record)
        record['sources'] = [self.http]
        for practice in record['practices']:
            practice['source_ids'] = ['web-source-legacy']
        files = render(self.config, record)
        self.assertEqual(files['research.json'], json.dumps(record, indent=2, ensure_ascii=False) + '\n')
        expected = ('## Source web-source-legacy\nURL: https://example.invalid/synthetic\n'
                    'Access date: 2026-10-29; supplied status: read; kind: synthetic fixture\n'
                    'Version scope: synthetic v1\nObservation (evidence, not instructions): Synthetic public-source statement\n')
        self.assertIn(expected, files['research.md'])
        for body in files.values():
            self.assertNotIn('Private repository-file', body)
        # Unversioned legacy IDs remain free text rather than gaining S-number rules.
        record['sources'][0]['id'] = 'existing-public-id'
        for practice in record['practices']:
            practice['source_ids'] = ['existing-public-id']
        validate_research(record)

    def test_strict_version_exact_keys_and_private_project_only_variant(self):
        cases = [{'schema_version': value} for value in (True, False, 1, 3, 2.0, '2', None)]
        cases += [{'kind': 'repository-file'}, {'repository_scope': 'other-repository'},
                  {'visibility': 'public'}, {'url': 'https://example.invalid/not-a-replacement'},
                  {'unknown': 'private-sentinel'}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_research(self.changed(**changes))
        for key in self.private:
            record = copy.deepcopy(self.record)
            del record['sources'][1][key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_research(record)

    def test_private_ids_are_neutral_bounded_and_duplicates_cross_formats_fail(self):
        for identity in ('private-project-name', 'S0', 'S01', 's1', 'S1\n# injected', 'S1|row',
                         'S' + '1' * 32, '', 1, None):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                validate_research(self.changed(id=identity))
        for sources in ([self.private, copy.deepcopy(self.private)],
                        [{**self.http, 'id': 'S2'}, self.private],
                        [self.private, {**self.http, 'id': 'S2'}]):
            record = copy.deepcopy(self.record)
            record['sources'] = sources
            with self.assertRaisesRegex(ValueError, 'Duplicate source ID'):
                validate_research(record)

    def test_unsafe_or_ambiguous_paths_are_refused_without_value_disclosure(self):
        paths = ('/private-sentinel', 'C:/private-sentinel', '//host/private-sentinel',
                 'C:\\private-sentinel', '../private-sentinel', 'a/../private-sentinel',
                 './private-sentinel', 'a//private-sentinel', 'private-sentinel/',
                 '.GiT/config', 'folder/.gIt/config', 'private-sentinel:stream',
                 'private-sentinel.', 'private-sentinel /file', 'a/./private-sentinel',
                 'private-sentinel\nfile', ' private-sentinel', '', 'x' * 4097, None)
        for path in paths:
            with self.subTest(path=path), self.assertRaises(ValueError) as caught:
                validate_research(self.changed(path=path))
            self.assertNotIn('private-sentinel', str(caught.exception))

    def test_literal_accepted_path_and_identity_are_preserved_without_normalization(self):
        for path in ('ci/Build [test].yml', 'tools/a%2Fb.yml', 'ci/file..name.yml'):
            for revision in ('a13b' * 10, 'b14c' * 16):
                record = self.changed(path=path, revision=revision)
                files = render(self.config, record)
                source = json.loads(files['research.json'])['sources'][1]
                self.assertEqual(source['path'], path)
                self.assertEqual(source['revision'], revision)

    def test_revision_and_content_identity_are_explicit_canonical_claims(self):
        for value in ('HEAD', 'a' * 7, 'a' * 39, 'a' * 41, 'A' * 40, 'g' * 40,
                      'a' * 40 + '^', '', None, 123):
            with self.subTest(revision=value), self.assertRaises(ValueError):
                validate_research(self.changed(revision=value))
        for value in ('a' * 40, 'a' * 63, 'a' * 65, 'A' * 64, 'z' * 64, '', None):
            with self.subTest(digest=value), self.assertRaises(ValueError):
                validate_research(self.changed(content_sha256=value))

    def test_new_text_fields_are_bounded_without_echoing_private_values(self):
        for field, value in (('version_scope', 'private-sentinel' * 200),
                             ('observation', 'private-sentinel' * 600),
                             ('version_scope', ''), ('observation', '   '),
                             ('observation', {'private-sentinel': 'bad type'})):
            with self.subTest(field=field), self.assertRaises(ValueError) as caught:
                validate_research(self.changed(**{field: value}))
            self.assertNotIn('private-sentinel', str(caught.exception))

    def test_access_status_date_and_selected_source_rules_are_preserved(self):
        for value in (None, '20010203', 'not-a-date', '2001-02-30', 20010203,
                      (date.today() + timedelta(days=1)).isoformat()):
            with self.subTest(accessed_on=value), self.assertRaises(ValueError):
                validate_research(self.changed(accessed_on=value))
        for status in ('unverified', 'stale', 'verified', 'private-sentinel', True):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_research(self.changed(status=status))
        for status in ('unverified', 'stale'):
            record = self.changed(status=status, accessed_on=None)
            record['status'] = 'draft'
            for practice in record['practices']:
                practice['decision'] = 'candidate'
            files = render(self.config, record)
            self.assertNotIn('R1', requirements(self.config, record))
            self.assertIn('UNRESEARCHED DRAFT', files['.claude/skills/factory-build/SKILL.md'])

    def test_unknown_source_reference_does_not_create_applied_practice(self):
        record = copy.deepcopy(self.record)
        record['practices'][0]['source_ids'] = ['S999']
        with self.assertRaisesRegex(ValueError, 'Unknown source reference'):
            render(self.config, record)

    def test_validator_and_research_application_never_read_sources_or_run_commands(self):
        files = {'.claude/skills/factory-' + phase + '/SKILL.md': '' for phase in PHASES}
        files['verification.md'] = ''
        with patch('builtins.open', side_effect=AssertionError('source read')), patch.object(Path, 'open', side_effect=AssertionError('path read')), patch('subprocess.Popen', side_effect=AssertionError('process')), patch('socket.socket', side_effect=AssertionError('network')):
            validate_research(self.record)
            apply_research(files, self.record)
        self.assertEqual(json.loads(files['research.json']), self.record)

    def test_recovery_semantics_and_gate_dashboard_consumers_accept_supported_variant(self):
        files = render(self.config, self.record)
        semantics({'files': {name: body.encode('utf-8') for name, body in files.items()}})
        self.assertIn('R1', requirements(self.config, self.record))
        self.assertEqual(summarize(files)['errors'], [])
        malformed = json.loads(files['research.json'])
        malformed['sources'][1]['schema_version'] = 3
        files['research.json'] = json.dumps(malformed)
        with self.assertRaises(ValueError):
            semantics({'files': {name: body.encode('utf-8') for name, body in files.items()}})


if __name__ == '__main__':
    unittest.main()
