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
Continue to use `verify_install.py --source` for the existing source-versus-installation
comparison, or its explicit pinned-manifest mode below. Release manifest
authentication and distribution remain separate work; do not treat a self-generated
file as independent provenance evidence.

## Compare an installation with an independently pinned manifest

Obtain the manifest's **raw file SHA-256** and expected **full source commit** from
an independently trusted channel. Inspect the actual installation path and use a
separately trusted helper. A digest calculated from the same untrusted download is
not an independent pin, and a manifest's own `source_revision` is not provenance.
This helper cannot decide whether the caller's trust decision is sound.

```text
python3 skills/build-software-factory/scripts/verify_install.py --installed <loaded-plugin-directory> --manifest <private-manifest.json> --manifest-sha256 <independently-trusted-raw-sha256> --revision <independently-trusted-full-source-commit>
```

The manifest must be outside the installation. `--manifest` and `--source` are
mutually exclusive, and the digest option is required only with `--manifest`.
Source mode retains its clean-checkout requirement and diagnostics. Manifest mode
uses no Git command, network, source checkout, credential lookup or cache update.
Neither mode proves which directory an already running session loaded.

The manifest reader supports only exporter schema 1, UTF-8 JSON without a BOM,
with the exact documented fields and no duplicate keys or non-JSON numeric values.
It validates the raw digest **before parsing**; reformatting whitespace or line
endings changes that digest. Source revision, tree width and algorithms must agree
with the supplied identity. Counts and sizes must be integers rather than booleans;
paths must be unique, UTF-8-byte sorted, safe and free of normalized case/Unicode
aliases in directories as well as filenames. A file cannot also be a directory
prefix. Unknown fields, unsupported versions, empty inventories and invalid hashes,
modes or totals are refused. Descriptive `scope`/`notice` text grants no authority
and is not echoed as a trusted result.

Bounds match the supported export inventory: 2,048 logical entries including
implied directories, 20 nested directories, 4,096 UTF-8 bytes per path, 4 MiB per
file and 32 MiB of logical file content. The JSON file is capped at 32 MiB to allow
the exporter's escaped path representation. Link/reparse ancestors, symlinks,
hard-linked files and other nonregular files are refused. Unexpected installed
files are named but never opened or hashed. The helper compares the exact regular-
file inventory and raw sizes/hashes twice and rereads the pinned manifest to detect
ordinary concurrent changes. It makes no hostile-filesystem guarantee and imposes
no wall-clock filesystem I/O timeout; use trusted, quiescent local paths.

The committed `100644`/`100755` modes are validated as source metadata. Installed
execute/permission bits and empty directories are **not** verified by this portable
byte comparator. Empty directories are not represented by exporter file rows.

Exit 0 with `comparison: MATCH` means installed regular-file bytes match the
supplied independently pinned manifest. Missing, extra, size-changed or hash-changed
files produce `comparison: DIFFERENT` and exit 1. Invalid, unsafe, changed or
untrusted inputs exit 2 with no comparison result. The private JSON names files
and the supplied source identity; review it before any separately authorized sharing.
No output file is created or overwritten. A MATCH is not release authentication,
source signature verification, execution permission, a cache refresh, a hosted CI
result or proof of installation in the active session. Release assets, tags,
distribution and existing factory launch-guide migrations remain outside this tool.
