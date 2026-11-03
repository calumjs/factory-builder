# Optional runtime migration receipts

Add `--migration-receipt` to an explicitly selected `--gate-runtime`,
`--context-runtime` or `--recipe-runtime` preview. The flag proposes an optional
manifest-tracked `migration-receipts.json` alongside actual runtime changes:

```sh
python <trusted-builder>/scripts/update_operations.py --factory <factory> --gate-runtime --migration-receipt
python <trusted-builder>/scripts/update_operations.py --factory <factory> --gate-runtime --migration-receipt --apply --approve-plan <exact-preview-digest>
```

Review the complete private diff and exact digest. The receipt is part of that
approved local update, not an independent write, download or installation. Without
the flag, existing update behavior and any existing receipt file are preserved.
No changed runtime components means no receipt is appended, even when a runtime
flag is supplied or unrelated configuration changes are proposed.

Schema 1 contains `schema_version: 1` and a `receipts` array. Each appended receipt
has `scope: "runtime-only"`, an `installed_builder` object, and sorted `components`.
Each component records its factory-relative `path`, `before_raw_sha256` (null for
a new dependency), and `after_raw_sha256`, calculated from captured original and
proposed bytes. This deliberately distinguishes raw line endings from normalized
manifest digests. Only the fixed dashboard helper paths for dashboard, integrity,
gates, operations, recipes, assumptions, readiness and learning_table are supported.
Unchanged helpers, snapshots, templates, configuration and evidence are not assigned
new provenance, including during mixed updates.
These opted-in receipts are a partial record of selected runtime transitions, not
a complete chronology or proof that every intervening change was recorded. A prior
receipt's after hash does not certify the component's current bytes or state.

`installed_builder.declared_name` and `declared_version` are bounded labels read
from the installed plugin's metadata, or null when that metadata is absent. They
do not verify which release produced the bytes. `verified_source_revision` is
always null in this slice; no application origin, checkout HEAD, supplied SHA or
network lookup is used. The original `upstream-provenance.json` remains byte-for-byte
unchanged, including any historical whole-factory version or source claim.

The updater preserves prior receipt values when appending; JSON formatting may be
normalized and the complete change is shown in preview. Strict schema validation
rejects unknown fields, paths, duplicate component paths, malformed raw digests,
non-null source revisions and unsupported versions. Inputs reject duplicate JSON
keys and nonfinite values. History is capped at 128 receipts and 256 KiB; exceeding
either limit refuses the update rather than discarding history. Installed metadata
is limited to 64 KiB and individual declared labels to 128 printable characters.
Custom or unsupported ledgers require separate manual review when opting in.

The receipt's prior bytes or absence are captured for concurrent-change detection.
Its proposed bytes, changed component bytes and manifest are bound by the existing
plan digest. A changed receipt, component, metadata label or proposed update needs
a fresh preview. Backups retain prior receipts; initial receipt/dependency additions
are listed in `added-files.json`. Preserve those files and the manifest together.

Components are written before the receipt, and the manifest is written last. This
uses the updater's existing multi-file recovery model, not an atomic transaction or
an attestation of success. An interruption may leave changed files or a receipt
with a stale manifest; the command must not report success, and integrity remains
blocked until reviewed recovery. A receipt alone does not prove a completed update,
current component state, release identity, application verification or authority.
