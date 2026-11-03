"""Offline release-preparation check of two explicitly chosen local commit trees.

Reads the complete tracked root package, never the index or working-tree contents.
This is a content/version check, not release approval or installed-cache validation.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from ci_evidence import bounded_run, relative
from integrity import safe_path

MANIFEST = '.claude-plugin/plugin.json'
MAX_TREE = 2 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_MANIFEST = 64 * 1024
MAX_PATH = 4096
DEADLINE = 90
SHA = re.compile(r'(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z')
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')


def commit_id(value):
    if not isinstance(value, str) or SHA.fullmatch(value) is None:
        raise ValueError('--base and --candidate must be explicit full commit SHAs; aliases and expressions are unsupported')
    return value.lower()


class LocalGit:
    def __init__(self, repo):
        self.repo = safe_path(repo)
        self.deadline = time.monotonic() + DEADLINE

    def read(self, *args, limit=MAX_TREE):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Release comparison time limit exceeded')
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_NO_REPLACE_OBJECTS='1', GIT_NO_LAZY_FETCH='1',
                   GIT_ALLOW_PROTOCOL='', GIT_PROTOCOL_FROM_USER='0',
                   GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
        argv = ['git', '--no-optional-locks', '--literal-pathspecs',
                '-c', 'core.fsmonitor=false', '-C', str(self.repo), *args]
        status, output = bounded_run(argv, env, limit, timeout=min(30, remaining))
        if status:
            raise ValueError('Local Git ' + args[0] + ' failed; verify the selected repository and exact local objects. No fetch is attempted; all Git transports are disabled')
        return output


def inventory(git, revision):
    if git.read('cat-file', '-t', revision, limit=32) != b'commit\n':
        raise ValueError('Each selected SHA must name a commit object directly, not a tag, tree or blob')
    raw = git.read('ls-tree', '-r', '-l', '-z', '--full-tree', revision)
    if not raw or not raw.endswith(b'\0'):
        raise ValueError('Missing or malformed committed package inventory')
    rows = raw[:-1].split(b'\0')
    if len(rows) > MAX_ENTRIES:
        raise ValueError('Committed package exceeds the 4096-entry comparison limit')
    entries = {}
    for row in rows:
        header, separator, path = row.partition(b'\t')
        fields = header.split()
        if not separator or len(fields) != 4 or len(path) > MAX_PATH:
            raise ValueError('Malformed or oversized committed package entry')
        mode, kind, oid, size = fields
        if mode not in (b'100644', b'100755') or kind != b'blob':
            raise ValueError('Package comparison supports regular tracked files only; symlinks and submodules need separate review')
        if re.fullmatch(rb'[0-9a-f]{' + str(len(revision)).encode() + rb'}', oid) is None:
            raise ValueError('Malformed committed package object ID')
        if re.fullmatch(rb'[0-9]{1,20}', size) is None:
            raise ValueError('Missing local blob or malformed package size; obtain the required objects separately, then retry')
        try:
            name = relative(path.decode('utf-8'))
        except (UnicodeError, ValueError) as error:
            raise ValueError('Package paths must be canonical printable UTF-8 repository paths') from error
        if len(name.split('/')) > 64 or name in entries:
            raise ValueError('Duplicate or excessively nested committed package path')
        entries[name] = (mode.decode('ascii'), oid.decode('ascii'), int(size))
    return entries


def stable_version(value):
    if not isinstance(value, str) or len(value) > 128 or VERSION.fullmatch(value) is None:
        raise ValueError('Plugin version must be stable MAJOR.MINOR.PATCH with no leading zeroes (maximum 128 characters); prerelease and build metadata are unsupported')
    return tuple(int(part) for part in value.split('.'))


def manifest(git, entries):
    if MANIFEST not in entries:
        raise ValueError('Missing committed ' + MANIFEST)
    _, oid, expected_size = entries[MANIFEST]
    if expected_size > MAX_MANIFEST:
        raise ValueError('Committed plugin manifest exceeds the 64 KiB limit')
    body = git.read('cat-file', 'blob', oid, limit=MAX_MANIFEST)
    algorithm = 'sha1' if len(oid) == 40 else 'sha256'
    actual = hashlib.new(algorithm, b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
    if len(body) != expected_size or actual != oid:
        raise ValueError('Committed plugin manifest bytes do not match their Git object identity')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate key in committed plugin manifest')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError('Non-JSON numeric constant in committed plugin manifest')

    try:
        data = json.loads(body.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Malformed UTF-8 JSON in committed ' + MANIFEST) from error
    if not isinstance(data, dict):
        raise ValueError('Committed plugin manifest must be a JSON object')
    name = data.get('name')
    if not isinstance(name, str) or not name or len(name) > 256 or name != name.strip() or not name.isprintable():
        raise ValueError('Committed plugin name must be a nonempty printable string without surrounding whitespace')
    version = data.get('version')
    stable_version(version)
    return {'name': name, 'version': version}


def compare(repo, base, candidate):
    base = commit_id(base)
    candidate = commit_id(candidate)
    git = LocalGit(repo)
    before = inventory(git, base)
    base_manifest = manifest(git, before)
    after = before if candidate == base else inventory(git, candidate)
    candidate_manifest = base_manifest if candidate == base else manifest(git, after)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    advanced = stable_version(candidate_manifest['version']) > stable_version(base_manifest['version'])
    blocked = bool(changed) and not advanced
    return {'schema': 1, 'assessment': 'blocked' if blocked else 'passed',
            'base': base, 'candidate': candidate,
            'base_plugin': base_manifest, 'candidate_plugin': candidate_manifest,
            'scope': 'all tracked regular files in the root package; working tree and index are not read',
            'changed_files': len(changed), 'changed_path_sample': changed[:20],
            'paths_omitted': max(0, len(changed) - 20), 'version_advanced': advanced,
            'diagnostic': ('Committed package content changed without a stable version advance. Prepare a reviewed version bump before releasing this candidate; no files were edited.' if blocked else
                           'Committed package content has an advanced stable version.' if changed else
                           'No committed package content changed; no version advance is needed.'),
            'limits': 'Caller selects the trusted prior release and candidate. This checks content/version consistency only, not release approval, compatibility or installed-cache freshness.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Local repository containing both already available commits')
    parser.add_argument('--base', required=True, help='Independently verified prior release full commit SHA')
    parser.add_argument('--candidate', required=True, help='Reviewed release candidate full commit SHA')
    args = parser.parse_args(argv)
    try:
        result = compare(Path(args.repo), args.base, args.candidate)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'schema': 1, 'assessment': 'error', 'error': str(error)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 1 if result['assessment'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
