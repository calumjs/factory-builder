"""Explicit private checksum export from one pinned local commit; never publish."""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import re
import subprocess
import time
import unicodedata

from ci_evidence import relative
from release_identity import LocalGit, SHA
from verify_install import reject_redirected_ancestors

MAX_COMMIT = 1024 * 1024
MAX_TREE = 2 * 1024 * 1024
MAX_BLOB = 4 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_DEPTH = 20
MAX_PATH = 4096


def object_digest(kind, body, algorithm):
    return hashlib.new(algorithm, kind.encode('ascii') + b' ' +
                       str(len(body)).encode('ascii') + b'\0' + body).hexdigest()


class Objects:
    """Bounded verified object cache; no index, working files or parent traversal."""
    def __init__(self, git, width):
        self.git = git
        self.width = width
        self.algorithm = 'sha1' if width == 40 else 'sha256'
        self.cache = {}
        self.total = 0

    def deadline(self):
        if time.monotonic() >= self.git.deadline:
            raise ValueError('Checksum export deadline exceeded')

    def read(self, oid, kind):
        self.deadline()
        if re.fullmatch('[0-9a-f]{'+str(self.width)+'}', oid) is None:
            raise ValueError('Invalid object identity')
        if oid in self.cache:
            actual_kind, body = self.cache[oid]
            if actual_kind != kind:
                raise ValueError('Object type conflicts with tree entry')
            return body
        if self.git.read('cat-file', '-t', oid, limit=32) != kind.encode()+b'\n':
            raise ValueError('Expected exact commit, tree or blob object type')
        raw_size = self.git.read('cat-file', '-s', oid, limit=32)
        if re.fullmatch(rb'(?:0|[1-9][0-9]{0,19})\n', raw_size) is None:
            raise ValueError('Invalid object size')
        size = int(raw_size)
        bound = {'commit': MAX_COMMIT, 'tree': MAX_TREE, 'blob': MAX_BLOB}[kind]
        if size > bound or self.total + size > MAX_TOTAL:
            raise ValueError('Checksum object byte limit exceeded')
        body = self.git.read('cat-file', kind, oid, limit=bound)
        if len(body) != size or object_digest(kind, body, self.algorithm) != oid:
            raise ValueError('Raw object size or identity mismatch')
        self.total += size
        self.cache[oid] = (kind, body)
        return body


def root_tree(body, width):
    header, separator, _ = body.partition(b'\n\n')
    lines = header.split(b'\n')
    if not separator or b'\0' in header or not lines:
        raise ValueError('Malformed commit header')
    pattern = rb'tree ([0-9a-f]{' + str(width).encode() + rb'})'
    match = re.fullmatch(pattern, lines[0])
    # A continuation belongs to the preceding header and cannot hide another root.
    claims = [line for line in lines if line.lstrip().startswith(b'tree')]
    if match is None or claims != [lines[0]]:
        raise ValueError('Commit needs exactly one canonical root tree header')
    return match[1].decode('ascii')


def export(repo, revision):
    if not isinstance(revision, str) or SHA.fullmatch(revision) is None:
        raise ValueError('An independently pinned full commit SHA is required')
    revision = revision.lower()
    repo = reject_redirected_ancestors(repo)
    if not repo.is_dir():
        raise ValueError('Repository must be an existing directory')
    objects = Objects(LocalGit(repo), len(revision))
    tree = root_tree(objects.read(revision, 'commit'), len(revision))
    rows = []
    seen = set()
    count = 0
    logical_bytes = 0

    def visit(oid, prefix='', depth=0):
        nonlocal count, logical_bytes
        objects.deadline()
        if depth > MAX_DEPTH:
            raise ValueError('Checksum directory depth limit exceeded')
        body = objects.read(oid, 'tree')
        position = 0
        previous = None
        while position < len(body):
            objects.deadline()
            count += 1
            if count > MAX_ENTRIES:
                raise ValueError('Checksum entry limit exceeded')
            end = body.find(b'\0', position)
            if end < 0 or end + 1 + objects.width//2 > len(body):
                raise ValueError('Malformed tree record')
            record = body[position:end]
            mode, separator, raw_name = record.partition(b' ')
            if not separator or mode not in (b'40000', b'100644', b'100755'):
                raise ValueError('Only directories and regular files are supported; no symlinks or submodules')
            if b'/' in raw_name:
                raise ValueError('Tree name must be a single path component')
            name = relative(raw_name.decode('utf-8'))
            path = relative(prefix + name)
            if len(path.encode('utf-8')) > MAX_PATH:
                raise ValueError('Checksum path byte limit exceeded')
            normalized = unicodedata.normalize('NFC', path).casefold()
            if normalized in seen:
                raise ValueError('Duplicate or aliased committed path')
            seen.add(normalized)
            order = raw_name + (b'/' if mode == b'40000' else b'')
            if previous is not None and order <= previous:
                raise ValueError('Tree entries are not in canonical Git order')
            previous = order
            child = body[end+1:end+1+objects.width//2].hex()
            position = end+1+objects.width//2
            if mode == b'40000':
                visit(child, path+'/', depth+1)
            else:
                blob = objects.read(child, 'blob')
                logical_bytes += len(blob)
                if logical_bytes > MAX_TOTAL:
                    raise ValueError('Checksum logical file byte limit exceeded')
                rows.append({'path': path, 'mode': mode.decode('ascii'), 'size': len(blob),
                             'sha256': hashlib.sha256(blob).hexdigest()})
    visit(tree)
    objects.deadline()
    rows.sort(key=lambda row: row['path'].encode('utf-8'))
    return {'schema': 1, 'source_revision': revision, 'source_tree': tree,
            'git_object_algorithm': objects.algorithm, 'checksum_algorithm': 'sha256',
            'file_count': len(rows), 'total_file_bytes': logical_bytes, 'files': rows,
            'scope': 'All regular files in the selected root tree; raw committed bytes and modes. No parent history, index, working-tree files or filters.',
            'notice': 'Private path export explicitly requested by the caller. Independently pin and trust the commit and helper; this manifest does not authenticate provenance, establish authority, publish a release, or verify an installed cache. No MATCH verdict is provided.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, help='Trusted local repository containing the selected objects')
    parser.add_argument('--revision', required=True, help='Independently pinned full commit SHA; not HEAD, a tag or an expression')
    args = parser.parse_args(argv)
    try:
        result = export(args.repo, args.revision)
    except (ValueError, OSError, UnicodeError, TypeError, OverflowError, subprocess.TimeoutExpired):
        print('ERROR: checksum export refused: invalid, unavailable, redirected, corrupt, ambiguous or over-limit local inputs. No manifest was emitted; no fetch is attempted.', file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
