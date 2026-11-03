# Export checksums from a pinned local commit

Use a separately trusted builder helper and an independently identified **full
commit SHA** already available in a trusted local repository:

```text
python3 skills/build-software-factory/scripts/export_checksums.py --repo <repository> --revision <full-commit-sha>
```

On Windows, use `py -3` or the actual approved interpreter. This explicit command
requests a **private inventory of repository-relative filenames** on stdout. Review
that inventory before saving or sharing it through any separately authorized path;
the helper does not attach, publish, create or replace any output file. Errors use
a fixed diagnostic and exit 2 without emitting a partial manifest. Success exits 0.

The deterministic version-1 JSON has `source_revision`, `source_tree`,
`git_object_algorithm`, `checksum_algorithm`, `file_count`, `total_file_bytes`,
`files`, `scope` and `notice`, plus `schema: 1`. Each file row contains exactly
`path`, `mode`, `size` and `sha256`. Paths are sorted by their UTF-8 bytes. SHA-256
is calculated over raw committed file bytes; file mode is recorded separately.
There is no timestamp, absolute repository path, checkout-state claim or plugin
version inference. An empty committed tree produces an explicit empty inventory.

The selected commit need not be HEAD. The reader verifies its raw object identity,
then every tree and blob reachable through its root tree. It checks object type and
size before bounded reads and independently recomputes each Git object ID from its
type, byte length and raw contents. Both SHA-1 and SHA-256 repositories are supported.
It does not traverse parent history or establish signature/provenance trust.
Git's [object format](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects),
[raw object reader](https://git-scm.com/docs/git-cat-file) and
[hash transition design](https://git-scm.com/docs/hash-function-transition)
describe the underlying formats.

Only regular committed files (`100644`, `100755`) and directories are supported.
Symlinks, submodules, malformed tree records, duplicate paths, normalized
case/Unicode aliases, noncanonical Git tree order and unsafe/nonprintable UTF-8
paths are refused. No checkout, index, untracked file, line-ending conversion or
Git content filter contributes bytes. Therefore a dirty checkout does not change
an export of the same pinned commit. This intentionally differs from
`verify_install.py`, which also requires its comparison source checkout to match
the pinned tree.

Bounds: 2,048 logical entries including directories and repeated subtree entries;
20 nested directory levels; 4,096 encoded bytes per full path; 1 MiB per commit;
2 MiB per tree; 4 MiB per blob; 32 MiB of unique object contents and separately
32 MiB of logical file contents, including repeated files; 90 seconds overall,
with each Git subprocess bounded to the remaining time or 30 seconds. Missing,
corrupt or over-limit objects stop the export. Ambient Git redirection variables,
replacement objects, automatic lazy fetch and Git transports are disabled. No
objects are obtained automatically; supply missing objects separately through an
authorized workflow. Repositories and helper execution still need their own trust;
this is not a sandbox for a malicious Git executable or repository configuration.

This is a **checksum exporter only**. A manifest generated from an untrusted commit
does not make that commit trusted. It does not compare an installation, prove which
cache a running session loaded, produce a MATCH verdict, consume a supplied manifest,
publish a release asset or tag, activate CI, or migrate an existing launch guide.
Continue to use `verify_install.py` for the existing source-versus-installation
comparison. Release manifest authentication, distribution and any future manifest
consumer require separate review; do not treat a self-generated file as independent
provenance evidence.
