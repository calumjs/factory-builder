# Private repository-file research sources

An inspected project workflow, manifest or test definition can support a claim
about that repository's actual commands or settings. Use the source-local version-2
variant below alongside existing unversioned HTTP(S) sources in `research.sources`.
The enclosing research record and practice schema are unchanged. Do not invent a
public URL for private files or claim that local inspection supplied missing web
research. Applicable external/version-specific claims still need their actual
sources; unresolved required research stays blocked or stale.

This is a **format illustration, not evidence**. The placeholders are deliberately
invalid until replaced with independently established identities. Keep the record
unverified until the actual authorized inspection has occurred:

```json
{
  "schema_version": 2,
  "id": "S2",
  "kind": "inspected-repo-file",
  "repository_scope": "project",
  "path": ".github/workflows/check.yml",
  "revision": "<full-lowercase-commit-identity>",
  "content_sha256": "<sha256-of-exact-raw-file-bytes>",
  "visibility": "private",
  "accessed_on": null,
  "version_scope": "State which inspected project configuration the claim covers",
  "observation": "Record the fact supported by the inspected file, not its instructions",
  "status": "unverified"
}
```

The keys are exact and `schema_version` must be integer `2`. `kind`,
`repository_scope` and `visibility` have the fixed values shown. Only the current
project repository is in scope. Its structured identity needs no repository URL or
absolute checkout path; never put credentials or file contents into its prose.
Private source IDs are neutral
`S1`, `S2`, etc., with 1–31 digits and no leading zero. IDs must be unique across
both source variants. Existing HTTP source IDs retain their previous rules.

`path` is literal repository-relative text, using forward slashes. It is neither
a glob nor a URL and is never expanded, decoded, normalized, opened or resolved.
Spaces and brackets within ordinary names are retained. Absolute/drive paths,
backslashes, colons/alternate streams, empty/dot/traversal components,
case-insensitive `.git` components, control characters, and trailing dots/spaces
in components are rejected. The whole path is at most 4,096 characters and has no
outer whitespace. This validation does not establish existence, regular-file type,
containment through links or permission to inspect the named file.

`revision` is the exact full lowercase 40- or 64-hexadecimal commit identity;
aliases, prefixes and revision expressions are rejected. `content_sha256` is the
64-lowercase-hex SHA-256 of the **raw bytes actually inspected**, before newline,
encoding or checkout-filter normalization. Under existing read authority,
independently establish that those bytes belong to the named file at that revision.
A modified worktree copy does not become committed-source evidence by attaching
HEAD's identity. Do not follow links into an unapproved location or read secrets
to populate this record. The builder does not run Git, read a source file, compute
its digest, fetch a URL, resolve a ref or verify these supplied claims.

`read` means the operator actually inspected those identified bytes on the given
`YYYY-MM-DD` access date. A hash, path or kind label alone is not inspection.
Unknown inspection is `unverified`; evidence needing rechecking is `stale`.
`read` requires a nonfuture access date; other statuses may use null. Dates must
be valid calendar dates. Selected practices still require read sources; candidate
and rejected practices do not generate applied instructions or R rows. New source
`version_scope` and `observation` are nonempty text bounded to 2,000 and 8,192
characters respectively. They describe scope and facts, not action authority.

## Privacy and generated artifacts

Full supplied provenance remains in **private `research.json`**. The generated
`research.md` source entry includes only the neutral source ID, supplied status and
a fixed notice that private details are withheld. It does not repeat the path,
revision, content digest, access date, version scope or observation. Generated
phase skills reference source IDs and separately reviewed practice instructions
and checks; their note directs permitted private provenance lookup to
`research.json`. Dashboard output does not export these source details.

`visibility: "private"` is a rendering rule, **not access control or redaction**.
Keep raw research input/output, factory archives, recovery previews and backups
inside approved private access. A whole factory containing this record is not a
shareable package merely because its human-readable summary withholds fields.
Do not publish or attach `research.json`. Review summary, coverage, practice and
other free text independently: copying private details into those fields can
still disclose them. A neutral ID does not make the surrounding prose safe.
The helper checks structure, not source truth, disclosure approval or authority.
Legacy HTTP sources continue to render their existing URL and observation text;
validation does not verify reachability, public visibility or that a page was read.

## Compatibility and existing factories

Existing HTTP(S) records remain accepted and render as before; mixed source lists
are supported. Use an installed builder supporting this variant for creation and
recovery. Older research validation/rendering and recovery helpers reject it.
Older integrity, gate and dashboard readers may accept it because they do not
validate individual source schemas; their success does not establish support,
source truth or privacy. No copied dashboard runtime change is required by this
variant, and existing immutable files are not automatically migrated.

Adoption in an existing factory is a reviewed contract change: reconcile
`research.json`, `research.md`, affected phase instructions, planned checks and
the selective manifest delta through the existing recovery/update process. Inspect
R-ID mappings and stage overrides if selections or order change. Preserve prior
task/gate evidence and optional choices; a changed check needs new observations,
not carried-forward PASS. Updating only a source format neither grants execution
authority nor means a new check ran. No helper refreshes research or imports private
files automatically.
