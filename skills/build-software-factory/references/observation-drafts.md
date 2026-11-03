# Recipe-aware observation drafts

Use the trusted installed builder on stable local inputs:

```text
python -B scripts/observation_drafts.py --factory <factory> --gate G1 --gate G2
```

This read-only helper prints a version-1 JSON review envelope. Select 1–32 exact,
distinct configured IDs; there is no implicit all-gates selection. It validates a
bounded factory snapshot, contract integrity, policy/config controls and gate-row
structure. Missing, duplicate or wrong-stage configured rows fail even when
optional. Existing extra rows are structurally checked, but unconfigured IDs
cannot be selected. A selected recipe whose design differs from its row needs a
reviewed synchronized plan update; the observation writer cannot change design.

Each `drafts` entry separates `planned_context` from `observation`. Recipe design,
environment, argv, environment **names** and target are configuration only. G1
and G2 retain their different recipe targets; G3's planned target is never copied
into an actual-target field. A/R and legacy gates without structured recipes have
null planned environment, target and recipe. Their configured design and retained
row design are both visible; an actual inspected procedure may differ. Do not
infer runtime settings from planned values or earlier recorded observations.

Every draft observation starts `NOT RUN`, with `environment: "unconfirmed"` and empty
revision, evidence, actual target, timestamp and exit status. The helper neither
creates waivers nor changes a user's required/optional choice. Existing optional
and not-applicable choices appear only in planned context. A draft is never a
pass, and its successful CLI exit means only that draft generation succeeded.

The envelope is deliberately **not** a new writer input schema. Each nested
`observation` uses exactly the existing eight fields accepted by
`incremental_records.py --kind gate`. After separately authorized execution,
prepare a standalone observation using actual observed values, then review the
writer's diff and digest before any authorized apply. Keep it outside the factory.
The writer retains the row's stage, design and requiredness. It rejects the entire
envelope, and changing only a draft's result to PASSED fails evidence validation,
including for optional rows. Submitting an unfinished NOT RUN observation is
schema-valid but would replace the current row if applied; do not apply it merely
to obtain a template or erase current failure/evidence. Prior evidence is not
copied into the draft. The writer validates supplied claims, not their truth.

For structured pre-merge recipes, each recipe's target is authoritative; omit a
global `--target` unless it is needed for other selected rows. Still-required
post-merge confirmation separately requires the observed actual target and exact
subject. Planned values alone never supply these facts.

## Export an explicitly supplied observation

After obtaining actual observations through separately authorized work, use
`--observation` to print one standalone object for the existing writer without
manually extracting it from the draft envelope. Supply exactly one `--gate` and
all seven observation flags; there are no default results, timestamps or settings:

```text
python -B scripts/observation_drafts.py --factory <factory> --observation --gate G1 --result <observed-result> --revision <exact-subject> --environment <observed-environment> --target <observed-target> --checked-at <observed-time-with-timezone> --exit-status <observed-exit-or-manual> --evidence <evidence-reference>
```

The placeholders above are not example evidence. Quote values according to your
shell. The helper preserves supplied strings exactly and never executes an argv
recipe, verifies an environment or fetches an evidence reference. It does not
infer that observed settings matched the recipe. In particular, G3 always needs
an independently supplied actual target; its configured target is never a default.

The helper checks the captured factory and calls the existing single-observation
writer's validation, discarding the proposed record. Recipe-conformant PASSED
claims must contain the actual environment and target strings, exact subject,
evidence, valid timestamp and successful exit/manual observation. Optional PASSED
claims are validated too; no waiver is created. V1 still requires the existing G3
record when G3 is required, including subject, target and chronology. A separate
G3 export does not record G3 or make V1 eligible. Use separate reviewed recording
steps; this mode exports one observation at a time.

All flags are required by presence, even for FAILED, BLOCKED and NOT RUN. Negative
records may explicitly supply empty fields where the underlying writer allows
them, and can retain actual mismatches with a recipe. This mode is stricter about
environment: empty or whitespace-only environment is refused for every result.
Use an explicit `unconfirmed` for an unknown negative environment. The underlying
writer otherwise falls back to the prior row's environment for an empty value;
the convenience mode does not rely on that fallback. It never fills missing facts.

On success, stdout contains exactly the existing eight-field JSON object; stderr
identifies it as operator-supplied and unverified, with no check executed or record
written. A successful export is not a gate pass or authority to act. Failure emits
no JSON. Keep approved saved output outside the factory, then preview it with
`incremental_records.py --factory <factory> --kind gate --input <observation.json>`.
Review the current writer diff and digest before a separately authorized apply;
export does not reserve the factory or replace that review. Mixing observation
flags into draft mode or selecting several gates in observation mode is an error.

Limits reuse the acceptance-links snapshot reader: 2 MB per file, 32 MB total,
2,048 entries, depth 20; output is at most 256,000 UTF-8 bytes. Explicit observation
fields are each bounded to 8,192 characters. Redirects, special
files, network/device paths and changing snapshots are refused. No subprocess,
environment-value lookup or factory write occurs. This is an installed-builder
helper, not a copied dashboard runtime addition. Use stable, trusted local files:
the two snapshots detect ordinary concurrent changes, not adversarial filesystem
races. Review output privately because planned configuration can contain project
details; error diagnostics do not echo those values.
