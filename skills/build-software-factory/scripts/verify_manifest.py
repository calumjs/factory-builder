"""Compare installed bytes with an independently pinned exporter-v1 manifest.

No Git, network, cache update, publication or source-of-trust discovery occurs.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import unicodedata

from ci_evidence import full_sha, relative
from integrity import strict_json
from verify_install import inventory, reject_redirected_ancestors, MAX_FILE, MAX_TOTAL, MAX_ENTRIES, MAX_DEPTH

MAX_MANIFEST = 32 * 1024 * 1024
MAX_PATH = 4096
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
FIELDS = {'schema','source_revision','source_tree','git_object_algorithm','checksum_algorithm',
          'file_count','total_file_bytes','files','scope','notice'}


def identity(info):
    # Windows lstat/fstat can expose different ctime meanings after a rewrite.
    # Use the same stable identity/size/mtime basis as the existing inventory,
    # with explicit type/link checks; raw digest and a second read remain required.
    return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,info.st_mtime_ns)


def regular(info):
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not getattr(info,'st_file_attributes',0)&0x400


def read_pinned(path, pin):
    path = reject_redirected_ancestors(path)
    before = path.lstat()
    if not regular(before) or before.st_size > MAX_MANIFEST:
        raise ValueError('Manifest must be a bounded, unlinked regular file')
    fd = os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    try:
        opened = os.fstat(fd)
        if not regular(opened) or identity(opened) != identity(before):
            raise ValueError('Manifest changed before reading')
        pieces = []
        size = 0
        while True:
            chunk = os.read(fd,min(65536,MAX_MANIFEST+1-size))
            if not chunk:break
            pieces.append(chunk);size += len(chunk)
            if size > MAX_MANIFEST:raise ValueError('Manifest size bound exceeded')
        after = os.fstat(fd)
        last = path.lstat()
        if not regular(after) or not regular(last) or identity(after) != identity(before) or identity(last) != identity(before) or size != before.st_size:
            raise ValueError('Manifest changed while reading')
    finally:
        os.close(fd)
    raw = b''.join(pieces)
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('Manifest raw digest does not match the independent pin')
    return raw,identity(before)


def expected_files(raw, revision):
    value = strict_json(raw.decode('utf-8'))
    if not isinstance(value,dict) or set(value) != FIELDS or type(value['schema']) is not int or value['schema'] != 1:
        raise ValueError('Unsupported checksum manifest schema')
    width = len(revision)
    algorithm = 'sha1' if width == 40 else 'sha256'
    if value['source_revision'] != revision or value['git_object_algorithm'] != algorithm or value['checksum_algorithm'] != 'sha256':
        raise ValueError('Manifest identity or algorithms do not match the expected source')
    if not isinstance(value['source_tree'],str) or re.fullmatch('[0-9a-f]{'+str(width)+'}',value['source_tree']) is None:
        raise ValueError('Malformed source tree identity')
    for field in ('scope','notice'):
        if not isinstance(value[field],str) or not 1 <= len(value[field]) <= 1024 or not value[field].isprintable():
            raise ValueError('Malformed descriptive manifest metadata')
    if not isinstance(value['files'],list) or not 1 <= len(value['files']) <= MAX_ENTRIES:
        raise ValueError('Installation comparison requires a nonempty bounded manifest')
    if type(value['file_count']) is not int or value['file_count'] != len(value['files']):
        raise ValueError('Manifest file count is inconsistent')
    if type(value['total_file_bytes']) is not int or not 0 <= value['total_file_bytes'] <= MAX_TOTAL:
        raise ValueError('Manifest byte count is invalid')
    expected = {}
    nodes = {}
    previous = None
    total = 0
    for row in value['files']:
        if not isinstance(row,dict) or set(row) != {'path','mode','size','sha256'}:
            raise ValueError('Unsupported checksum file row')
        name = relative(row['path'])
        parts = name.split('/')
        if any(relative(part) != part for part in parts):raise ValueError('Noncanonical path component')
        encoded = name.encode('utf-8')
        if len(encoded) > MAX_PATH or len(parts)-1 > MAX_DEPTH:
            raise ValueError('Manifest path or depth bound exceeded')
        if previous is not None and encoded <= previous:
            raise ValueError('Manifest paths must be unique and UTF-8-byte sorted')
        previous = encoded
        for index in range(1,len(parts)+1):
            node = '/'.join(parts[:index]);kind = 'file' if index == len(parts) else 'directory'
            key = unicodedata.normalize('NFC',node).casefold()
            prior = nodes.get(key)
            if prior is not None and (prior != (node,kind) or kind == 'file'):
                raise ValueError('Manifest paths contain an alias or file/directory conflict')
            nodes[key] = (node,kind)
        if len(nodes) > MAX_ENTRIES:
            raise ValueError('Manifest logical entry bound exceeded')
        if row['mode'] not in ('100644','100755') or type(row['size']) is not int or not 0 <= row['size'] <= MAX_FILE:
            raise ValueError('Manifest regular-file mode or size is invalid')
        if not isinstance(row['sha256'],str) or SHA256.fullmatch(row['sha256']) is None:
            raise ValueError('Malformed raw file checksum')
        total += row['size']
        if total > MAX_TOTAL:raise ValueError('Manifest logical byte limit exceeded')
        expected[name] = {'size':row['size'],'sha256':row['sha256']}
    if total != value['total_file_bytes']:raise ValueError('Manifest total bytes are inconsistent')
    return value,expected


def compare_manifest(installed, manifest, manifest_sha256, revision):
    """Pins are supplied by an independent trusted channel, never derived here."""
    revision = full_sha(revision)
    if not isinstance(manifest_sha256,str) or SHA256.fullmatch(manifest_sha256) is None:
        raise ValueError('An independently pinned raw manifest SHA-256 is required')
    installed = reject_redirected_ancestors(installed).resolve(strict=True)
    manifest = reject_redirected_ancestors(manifest).resolve(strict=True)
    if not installed.is_dir() or manifest == installed or installed in manifest.parents:
        raise ValueError('Manifest must be outside the installed directory')
    root_before = installed.lstat()
    raw,manifest_identity = read_pinned(manifest,manifest_sha256)
    value,expected = expected_files(raw,revision)
    actual = inventory(installed,allowed=set(expected))
    # Detect ordinary concurrent edits. This is not a hostile-filesystem sandbox.
    if inventory(installed,allowed=set(expected)) != actual:
        raise ValueError('Installed inventory changed; use quiescent inputs')
    again,again_identity = read_pinned(manifest,manifest_sha256)
    reject_redirected_ancestors(installed)
    if raw != again or manifest_identity != again_identity or identity(root_before) != identity(installed.lstat()):
        raise ValueError('Manifest or installed root changed during comparison')
    missing = sorted(set(expected)-set(actual))
    extra = sorted(set(actual)-set(expected))
    changed = sorted(name for name in set(expected)&set(actual) if expected[name] != actual[name])
    rows = [{'path':name,'source_sha256':expected.get(name,{}).get('sha256'),
             'installed_sha256':actual.get(name,{}).get('sha256')}
            for name in sorted(set(expected)|set(actual))]
    return {'source_revision':revision,'source_tree':value['source_tree'],'manifest_sha256':manifest_sha256,
            'verification_source':'independently pinned exporter-v1 manifest',
            'source_files':len(expected),'installed_files':len(actual),'files':rows,
            'missing':missing,'extra':extra,'changed':changed,
            'comparison':'DIFFERENT' if missing or extra or changed else 'MATCH',
            'notice':'Exact regular-file inventory and raw-byte comparison against supplied pins only. Independently trust the manifest digest, expected commit and helper. No Git/source provenance, loaded-session identity, executable permission bits, empty-directory inventory or action authority is verified. No cache was updated; no network or credential discovery occurred. Quiescent trusted paths are required; hostile concurrent filesystems are unsupported.'}
