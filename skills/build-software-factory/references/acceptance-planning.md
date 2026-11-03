# Append-only acceptance preview

`scripts/acceptance_plan.py` previews one new criterion, one pending/blocked task
and an explicit test design. It writes no files and has no apply, materialization,
registration or adoption mode. A successful preview is not registered scope,
delivery readiness, test evidence or authority to execute its supplied design.

Use a valid, stable schema-2 factory with the five existing living files. Supply
the raw SHA256 of its independently accepted manifest and its provenance reference;
do not obtain a new approval by hashing an unreviewed current manifest. The helper
checks the supplied pin against the captured manifest and checks contract integrity.
It cannot independently establish that the caller's pin/reference was trusted.

## Request and preview

This synthetic request is design data, not a project recommendation or an executed
check. The caller explicitly chooses the supported opaque A-keyed map adapter:

```json
{
  "schema_version": 1,
  "issue": "owner/project#123",
  "criterion": "SYNTHETIC: filtering retains the selected sort order",
  "task": {
    "id": "Tnew",
    "goal": "SYNTHETIC: implement and verify the appended criterion",
    "owner": "operator",
    "depends_on": ["T1"],
    "allowed_paths": ["src/filter.py"],
    "status": "pending"
  },
  "test_map": {
    "adapter": "a-keyed-opaque-v1",
    "design": {"check": "SYNTHETIC filtering and retained-sort check; UNEXECUTED"},
    "register_reason": ""
  }
}
```

Run with a trusted installed helper and literal paths:

```text
python -B <trusted-builder>/scripts/acceptance_plan.py --factory <factory> --request <request.json> --baseline-manifest-sha256 <independently-accepted-raw-sha256> --baseline-reference <provenance-reference>
```

The executable prints one JSON envelope, including exact base64-encoded proposed
bytes, escaped full diffs, original raw hashes and a review digest. Review supplied
content as untrusted data; do not execute commands embedded in it. The output may
contain private factory text. It has no output-file option. If an operator saves
the preview outside the factory, the same explicit command plus
`--validate-plan <saved-preview.json>` recomputes and compares the entire envelope.
This validates currency, not approval. A changed request, reference, file,
directory, identity or proposed byte requires a fresh preview and review. Never
save previews or runtime logs inside the factory as unregistered files.

## Supported synchronization

- Allocate exactly `A(n+1)` from the existing acceptance array. Existing criteria,
  positional IDs, task definitions, optional gates, waivers and observations remain
  unchanged. New scope is appended; no edit, deletion or reordering is supported.
- Append the criterion to config, the recognized acceptance list and the brief's
  Acceptance section. These sections must already agree. Ambiguous/custom section
  formats require separate manual review; the helper does not regenerate them.
  Text outside the insertion remains byte-identical. JSON insertion preserves old
  bytes, including escaped keys, whitespace and a UTF-8 BOM; Markdown supports
  consistent LF or CRLF. Mixed Markdown endings are refused.
- Append the supplied task only to the living `task-plan.json`, linked to the new
  ID. `config.tasks` remains the original seed. Dependencies are checked against
  the current living graph, including later tasks absent from the seed. Existing
  events and additional living metadata survive unchanged.
- Add one required, pre-merge `NOT RUN` verification row, with unknown actual
  subject, target, evidence, time and exit status. Existing requiredness is not
  inferred or rewritten. Stage overrides and new waivers are outside this slice;
  future overrides must synchronize config and policy controls explicitly.
- Existing `test-map.json` must be a named immutable contract with an object keyed
  only by existing A IDs. The explicit adapter leaves its values uninterpreted,
  as Run's worker-context reader does; it does not validate executable checks or
  completeness of coverage. Supply nonempty design data for the new key. Keep
  `register_reason` empty for an existing map. If no map exists, a nonempty specific
  reason explicitly requests previewing a new immutable named contract. External
  maps and other project formats require a separately reviewed adapter/change;
  nothing is moved or reclassified automatically.

The input request is limited to 64 KiB. Factory capture uses recovery's existing
bounded, regular UTF-8 file/path checks and strict JSON rejection. Unsupported
legacy manifests, unrelated contract drift, malformed existing rows/tasks and
unsupported section/map shapes fail without writes. Older six-phase factories
need not adopt Run, new phase templates or copied runtimes to use the installed
preview helper. Stable snapshots detect ordinary concurrent edits; coordinate
writers because repeated reads are not an atomic filesystem snapshot.

## Candidate and recovery boundaries

The envelope deliberately separates:

1. `candidate_changes`: exact proposed non-manifest bytes. A future candidate must
   retain the original manifest and all unselected bytes. Its contract drift would
   be intentional and it would remain unusable until independently reviewed recovery.
2. `recovery_decisions`: exact changed/new immutable contract names and reasons.
   Living task/evidence files are not hashed or registered as contracts.
3. `predicted_recovered_manifest`: a separately labeled prediction for review,
   **never candidate content**. Only selected contract hashes change. It cannot
   authorize replacing the original manifest or accepting unrelated drift.

The digest binds the explicit request, baseline pin/reference, factory identity,
complete original inventory and all proposed bytes. It grants no write authority.
The next implementation boundary is reviewed candidate materialization, followed
by a separate [recovery](recovery.md) preview/review/apply/verify flow against an
independently pinned baseline. That second review must bind the actual candidate
and final output. Backup, interrupted-output quarantine and adoption checks still
apply. Recovery's manifest-only adoption instructions cannot activate these scope
changes: multiple non-manifest files would differ from the original factory.
This first slice does not implement either materialization or adoption.
