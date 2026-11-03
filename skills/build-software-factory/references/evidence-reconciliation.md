# Three-way evidence preview

`scripts/reconcile_evidence.py` prepares a private, read-only proposal for overlapping
evidence branches. It reads three complete local factory snapshots: their common
base and each branch's version. It does not check out Git revisions, merge Git,
write a candidate, apply records, execute checks, or establish readiness. Use trusted
installed helpers and stable disposable snapshots; keep live writers stopped while
capturing and reviewing them. Source directories must be distinct and non-nested.

## Discover the choices

```sh
python scripts/reconcile_evidence.py --base /snapshots/base --left /snapshots/left --right /snapshots/right --subject FULL_SELECTED_SUBJECT
```

The JSON report contains `sources` fingerprints and `options.current_rows` and
`options.task_statuses`. Every differing current gate row and task status requires
an explicit choice, even if only one branch changed it. No newest-row or PASS
preference exists. Copy an exact offered `source` (`base`, `left`, or `right`) and
its `sha256`, and supply a short reason. Decisions belong in a separate local JSON
file outside all three snapshots:

```json
{
  "schema": 1,
  "sources": {"base": "COPY_REPORTED_HASH", "left": "COPY_REPORTED_HASH", "right": "COPY_REPORTED_HASH"},
  "subject": "FULL_SELECTED_SUBJECT",
  "current_rows": {
    "G3": {"source": "left", "sha256": "COPY_OFFERED_VALUE_HASH", "reason": "Explain this reviewed choice"}
  },
  "task_statuses": {}
}
```

Include exactly the reported choice keys; the example is not a usable approval.
Empty maps are required when there are no differences. Unknown, extra, missing or
stale keys and duplicate JSON keys are refused. Then repeat the command with
`--decisions /review/choices.json`. Choosing a required changed observation for a
different subject produces `CONFLICT`, with no proposed files. An existing empty
NOT RUN plan may be selected without fabricating a subject. Optional rows retain
their exact selected claims and waived flag, including older subjects. Unchanged
rows are retained without treating them as fresh; `current_rows_outside_subject`
lists current rows that do not name the selected subject. None of this assesses
whether the recorded claims satisfy G3, V1, or any other gate.

## What survives

- Current gate rows are copied exactly from a named side. Distinct unselected
  rows are preserved using the existing quoted-history format; existing branch
  history additions and failures survive. History retains subject, requiredness,
  result, evidence, target and timestamp. It is not current evidence.
- Task definitions must agree. Current status choices do not change the subjects
  or content of their underlying events. Events must have unique IDs within each
  source. Identical payloads sharing an ID across sources are retained once;
  conflicting payloads for an ID are refused. Output order is base, then left
  additions, then right additions with unseen IDs—not execution chronology.
- Learn has no stable row ID. Base rows are retained once, followed by **every**
  left append occurrence and **every** right append occurrence. Identical added
  text survives twice when both sides appended it. Each occurrence has source and
  row-position attribution in the report, not an invented persistent ID. Identical
  text is not proof of the same event or proof of independent events.

Base history, events and Learn rows must remain exact prefixes of both branches;
deletions, edits and reordering require separate reconciliation. This helper does
not arbitrate conflicting task registrations, acceptance IDs, plans, stage/design
changes, deliberate requiredness changes, or contract migrations. Preserve both
versions and reconcile those choices separately; refusal does not require making
optional gates mandatory. Unknown task/event fields, unsupported/custom tables,
fenced/comment-hidden gate or Learn tables, malformed quoted observations and
differing non-history prose are refused. The supported current gate table is the
generated eleven-column table. Learn uses the generated seven-column header and
one contiguous table; its surrounding prose must agree exactly. Gate blank-line
formatting is taken from base, while nonblank surrounding prose must agree.

## Read the proposal, then reconcile deliberately

`PROPOSED` contains exact UTF-8 text, SHA-256 hashes and base-to-proposal unified
diffs for `verification.md`, `task-plan.json`, and `learning-log.md`. It also contains
source attributions and a `plan_sha256` binding all three captured inventories,
the exact raw decision-file bytes, parsed choices and proposed bytes. JSON/row
formatting may be normalized in the explicit diff. This digest is a review identity,
not an approval token; there is no `--apply` or `--approve-plan` operation.

All non-target files, including hashed contracts, manifest and other living records,
must be byte-identical. Existing manifest validation and structural record parsers
check source and proposed snapshots. Inventories include directories, file hashes,
root paths and filesystem identity; all three are read again after derivation, as
are the decisions. Changes abort the preview. Redirected paths, parent traversal,
missing files and oversized inputs are refused. Limits are 2 MB per file, 32 MB per
source, 2,048 entries, depth 20, 4,096 rows/events per record and 32 MB serialized
report. These are ordinary change checks on stable trusted local inputs, not an
adversarial filesystem transaction or distributed concurrency guarantee.

Reports contain private record content and diffs because this explicit invocation
requests them. Keep them local; do not publish them as verification evidence. Exit
0 means only that a proposal was produced; exit 1 means choices/conflicts remain;
exit 2 means refused input and no proposal. No state is written on any path. A
subsequent authorized integration still needs deliberate conflict resolution and
the existing subject/target-aware gate checks. This slice does not provide an
atomic three-file apply, automatically register acceptance, rebind evidence, or
solve conflicting schemas and arbitrary concurrent writers.
