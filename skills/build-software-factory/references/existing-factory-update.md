# Narrow existing-factory and operations update

For shorter generated phase entrypoints with complete linked guidance, see
[compact phase adoption](compact-phases.md). Its separate `--compact-phases`
preview refuses unsupported/custom skills and never silently migrates a factory.

After a successful update creates a backup, the CLI may print a nonblocking
[backup-ignore advisory](backup-advisory.md). It distinguishes unignored, tracked
and unknown status using project-local rules only. It does not change the write
outcome, root ignore rules or index; do not retry a completed write because the
optional check is unavailable. Preview and no-change apply create no backup and
do not run this advisory.

Do not rerun the scaffolder over an existing factory. Do not directly edit hashed config.operations, leave policy stale, or blindly recalculate every hash. The offline update helper changes only reviewed operational configuration, matching policy controls/default-gate guidance, relevant tool metadata, gate observations when needed and their manifest entries. It starts no external action.

## Preview and review

`scaffold.py --check <factory>` checks the factory against its own manifest; its
runtime advisory separately compares copied helpers with this installed builder's
normalized digests. A difference can be a customization or older code, not proof
of an available safe upgrade. Preview a specific `--gate-runtime`, `--recipe-runtime`,
`--context-runtime` or `--delivery-gates` without supplying a dummy operations file.
Review the named file diffs and before/after raw SHA256 values. The exact plan digest
is required for apply; unknown custom helpers are refused, not overwritten.
The preview also compares captured current and proposed verification rows. `ROW`
summaries identify retained, reset, updated, added or retired rows, newly archived
observations/plans, existing historical copies, and retained or changed requiredness.
These summaries expose gate IDs and fixed explanations, not free-form row values;
the complete diff still contains the reviewed file content and belongs in private
review storage. `RETAINED` describes unchanged fields, not fresh or passing evidence.
An `ARCHIVED` row is historical only. Review the exact diff and hashes even when a
summary says no new historical copy was added; summaries do not alter the plan digest
or authorize apply. An unrelated update retains gate observations, while a repeated
no-op reports unchanged current rows without inventing new resets or archives.
Delivery-gates is a contract migration and can also update policy, templates and
verification history. A runtime-only migration preserves config and policy bytes.
Do not change `upstream-provenance.json` merely because some helpers were updated:
the rest of the factory can still come from an older source and the builder may
not know its immutable source revision. Record verified provenance only through a
separately reviewed accurate change.

For an optional record of changed runtime component bytes, add
[`--migration-receipt`](migration-receipts.md) to an explicit runtime migration
preview. It preserves original factory provenance and records only the selected
runtime transitions, with declared builder labels and no inferred source revision.
The receipt participates in the reviewed plan and backups; it is neither a complete
history nor proof that the update completed or the installed source is authentic.

Known pristine helpers predating the factory-path and revision-help diagnostics can
be preserved, or migrated with the reviewed `--context-runtime --gate-runtime`
preview. Customized helpers still require manual review. `--delivery-gates`
can update known Verify/Release addenda with feature-confirmation guidance, retaining
custom instructions and backup evidence. It does not rewrite the living release
handoff or existing Plan/Build skills: adopt new handoff fields and those phases
through a separate reviewed edit, preserving project choices and prior observations.

Ambiguous duplicate policy keys and policy/config disagreement block the update;
preserve and reconcile both records through a reviewed synchronized recovery.
Known pristine v1.7 copied gate helpers remain unchanged by default; the installed
helper rejects duplicate policy keys, while a copied older helper needs an explicit
reviewed `--gate-runtime` upgrade to receive that diagnostic. A delivery migration
adds the shared boundaries contract when absent, checks only the six installed
phases unless Run was separately adopted, and refuses unknown customized delivery
addenda rather than replacing them. Resolve such content through manual review.

The optional portable CI/evidence template is not copied into existing factories
automatically. Read it from the installed builder, or review selective ci/ artifact
and manifest additions. Use the trusted installed helper outside the change checkout;
adopting any workflow/required-check policy remains separately authorized work.

For optional structured smoke checks and explicit video triggers, read
[gates.md](gates.md). --gate-runtime is a separate reviewed
opt-in for known original dashboard operations.py/recipes.py/gates.py sources;
new fields are refused against incompatible copied runtimes without it. Existing
legacy-field recipe changes preserve known compatible helpers unless a runtime
migration is explicitly selected. Customized/unknown code remains refused.

First pin the actual loaded plugin source/version and required helper/dependency
paths using the [launch preflight](../assets/templates/launch-guide.md). A missing
gates.py in an older install is not fixed by a notice-only CI step. Update only
within authorized installation scope; then separately review this factory's
compatibility/migration. These guides are not automatically copied into existing
contracts. Read them from the installed builder or review a selective addition
with its manifest entry; do not rescaffold or rebaseline unrelated edits.

Known pristine assumption-aware dashboard integrity code published through v1.5.1
remains compatible for assumptions-only updates and is preserved by default. An
explicit `--context-runtime` plan may upgrade that exact source to detailed path
diagnostics, with original bytes backed up and its selective manifest entry reviewed.
Customized/unknown code is still preserved and refused for a separate manual review.

For the optional structured assumptions replacement and advisory dashboard context,
read [operations-config.md](operations-config.md). --assumptions accepts a private array;
--context-runtime explicitly migrates known older dashboard code/dependencies,
including recipe compatibility. Custom content/runtimes are preserved/refused.

When step 1 fails because contracts were hand-edited or files were added, follow
[reviewed integrity recovery](recovery.md) first. The optional
[staged recovery helper](recovery.md) creates a reviewed recovered copy;
activation remains separate. `update_operations.py` cannot preview or approve an
invalid source; detailed path diagnostics do not change that boundary. No force switch exists.

## Worked upgrade checklist

The complete [synthetic operations patch](../assets/example-operations-update.json)
combines continuous around-the-clock intent, structured G1/G2/G3 recipes and both
video triggers. It is an **operations object**, without an outer `operations` key
or product-config fields. Intake fields such as `coverage` and `cadence` are flat
members of `issue_intake`; command, environment, env names and target belong under
`smoke_gates.checks.G1` (likewise G2/G3).

This is a schema/workflow example, **not a working project pipeline**. Intake stays
disabled, autonomy manual with no allowed submitters, and videos disabled; selecting
triggers while disabled creates no V rows. Scheduler, provider and action authority
remain unverified. Its concrete Python argv are fail-stop fixtures: they would exit
with a synthetic message, not run application checks. The `.invalid` URL is a planned
fixture target, not a deployment. No fixture command has been executed as evidence.

1. Pin the trusted installed builder and exact existing factory. Run the integrity
   check below; resolve broken contracts or policy drift through reviewed recovery
   first. Do not recreate the factory. Schema 1 needs a separate migration.
2. Copy the example into private scratch and adapt only the intended changes to the
   project's inspected commands, actual design and existing preferences. Do not apply
   its manual/disabled values wholesale to a configured factory. Omitted top-level
   sections and section fields are preserved, but supplied nested values such as
   `checks` replace that whole map: include every existing recipe you intend to keep.
   No secrets or environment values belong in the patch. The example deliberately
   omits `smoke_gates.required` so existing smoke defaults and row waivers survive.
3. Preview using the trusted helper. The commands below use placeholders for your
   inspected Python interpreter, trusted skill root, approved factory and scratch
   patch; replace them before invocation:

   ```sh
   python <trusted-skill-root>/scripts/scaffold.py --check <factory-root>
   python <trusted-skill-root>/scripts/update_operations.py --factory <factory-root> --operations <scratch>/operations-update.json
   ```

   For a known older copied runtime, add only the needed reviewed flags to the
   preview: `--gate-runtime` for structured-gate compatibility, `--recipe-runtime`
   for known older recipe metadata, or `--context-runtime` for context diagnostics.
   `--delivery-gates` additionally adopts current Intake/Verify/Release addenda and
   delivery records. These are migrations, not bypasses; unknown custom code stays
   preserved and refused. A current compatible factory needs no migration flag.
4. Inspect the **complete** diff and `REVIEW PLAN` digest: intended fields, preserved
   custom policy/runtime, every recipe and trigger, row waivers/history/reset effects,
   backup paths and selective manifest entries. A valid patch or preview establishes
   no watcher, passing check, video or permission. With videos disabled, the explicit
   triggers remain stored design only; choosing enabled videos later is a separate
   preference update within existing scope, not capture/narration authorization.
5. Within the applicable local-write scope, apply that exact reviewed plan using the
   same patch and migration flags, then recheck:

   ```sh
   python <trusted-skill-root>/scripts/update_operations.py --factory <factory-root> --operations <scratch>/operations-update.json --apply --approve-plan <exact-preview-digest>
   python <trusted-skill-root>/scripts/scaffold.py --check <factory-root>
   python <trusted-skill-root>/scripts/gates.py --factory <factory-root> --plan
   ```

   Changed input requires a fresh preview. Review the backup and resulting rows;
   unexecuted required checks remain NOT RUN and explicit optional rows are WAIVED,
   never promoted to PASSED. Assess an actual stage only with its independently
   selected tested subject (and actual target after release). Keep the example's
   different per-gate targets distinct; a single `--target` is not needed for a
   pre-merge plan or assessment.

On an invalid patch, compare its section/key nesting with the linked example and
[operations-config.md](operations-config.md); do not broaden the update or erase
existing controls to satisfy validation. An empty `{}` patch is valid for a selected
migration; runtime/delivery flags can also be previewed without an operations file.
Product scope, acceptance and unrelated files require their own reviewed changes.

## Preservation and recovery

For a v1.2 factory with an existing dashboard, new recipe metadata requires a
compatible bundled validator. The updater refuses that patch by default. Preview
the same patch with `--recipe-runtime` to explicitly migrate the known pristine
v1.2 dashboard/operations.py and add dashboard/recipes.py; review those exact code
and manifest changes plus the normal plan digest before applying. New v1.3 factories
already include the dependency. Customized/unknown bundled runtimes or dependencies
are preserved and require a separate narrow manual compatibility review. No other
dashboard files or initial snapshot are replaced. Factories without a dashboard
need no such migration. This opt-in grants no runtime execution authority.

When a reviewed plan adds a dependency, backups include `added-files.json` naming
the additions plus the originals/manifest for changed files. Interrupted recovery
must inspect those additions and restore the reviewed original set together with
its manifest; do not merely restore hashes or blindly remove concurrent files.
New destinations are exclusively created, so a concurrent new file is not overwritten.

Optional flat issue_intake coverage fields and done_videos recipe fields use the
same preview-first update. Explicit scheduling changes refresh a known marked
policy proposal; explicit video changes refresh a known marked living handoff
proposal. Customized/ambiguous marked blocks are refused for manual review, never
discarded. Other handoff content remains. Old configs gain no hidden control fields;
default design values are separate proposals. Updating video preferences can reset
active observations as described below; retain waivers and history. New recipe
contract files are not silently copied into existing factories; read the installed
builder recipe or review a separate selective manifest addition. No actual schedule,
recording, narration, provider connection or delivery action runs.

Original changed files and manifest are backed up under the project's `.factory-update-backups/<plan-digest>/`, outside the managed factory. Add these private backups to reviewed ignore policy before staging. Existing custom skill content is retained; an opt-in adds a marked delivery/intake addendum that supersedes conflicting old instructions. Review that precedence deliberately. Research, acceptance, tasks, learning and unrelated project files are preserved.

Smoke/video preference changes or a delivery migration reset active gate observations to NOT RUN, preserving deliberate row-level requiredness choices unless the patch explicitly changes smoke defaults. Retired V1 observations remain historical when videos are disabled. Prior observations are retained as quoted historical rows, not reused as passing current evidence. Extra required checks are retained. Legacy eight-column rows migrate only when their shape is recognizable; malformed or ambiguous rows require manual review. Post-release-only checks remain staged after the action; a no-release exclusion is distinct from an unknown target.

When reactivating a retired V1/V2 row (re-enabling videos or restoring a removed
trigger), choose its current requiredness explicitly in the same update:
`--video-requiredness V1=no --video-requiredness V2=yes`, supplying only the rows
being activated. The preview labels each choice and binds the resulting row to
the normal `--apply --approve-plan <digest>` flow. Choosing optional adds no
separate permission or approval step. A supplied user choice can be used directly.
The helper refuses a missing choice for a gate identified in the explicit history
section instead of silently making an old optional check required. When
configuration still expects the gate but its current row is missing, historical
occurrence also requires an explicit restoration choice. History only
identifies prior occurrence: it never supplies instructions, preferences or
current evidence. Malformed/ambiguous history requires manual review.

Only newly activated video rows accept this option; existing active rows retain
their choices, and unused or duplicate options are refused. First activation
without history keeps the established required default, or can explicitly choose
optional. Every activated row starts NOT RUN with blank subject/evidence/target/
timestamp/exit status. Old observations stay historical. Review requiredness for
each new feature as before: a one-change waiver is not a persistent video policy,
and a new activation choice must not be inferred from an unrelated old feature.

For a narrow smoke/video plan change, optionally preview with `--selective-gates`
using the [selective update rules](selective-gate-updates.md). Unchanged recognized
plans retain their exact recorded observations; changed plans and dependent rows
reset with history. Review the per-row reasons and field paths before applying.
Retained evidence keeps its original subject and status; it is not reassessed or
transferred to a new revision. Broad reset remains the default and the fallback
for recognized legacy schemas, explicit smoke-required defaults or mixed runtime
changes. Malformed or duplicate rows are refused for manual review.

The helper writes the manifest last and keeps verified backups. Filesystem updates are not a multi-file atomic transaction: interruption can leave a blocked integrity state. Stop, inspect backups and any lock/temp file, restore the affected originals and manifest together or finish a newly reviewed plan. Never delete a lock owned by an active writer or bypass the failed integrity check. Run the contract check and stage-specific gate assessment afterwards. Valid hashes do not mean application checks ran or passed.

Known pristine copied gate and context helpers that predate bytecode suppression are preserved by default. To adopt the fix, explicitly preview `--gate-runtime --context-runtime`, review the exact files and backup, then apply the approved digest. Customized helpers are refused for manual review; never ignore unexpected `__pycache__` in the manifest.

Known copied helpers from the reviewed runtime-diagnostics baseline can use the
same explicit `--context-runtime --gate-runtime` preview to adopt safe dashboard
diagnostics, table wrapping, per-check targets and typed controls errors. This is
a selective code-and-manifest migration: config, policy, task events, gate
observations and deliberate waivers remain unchanged. Inspect the diff and exact
plan digest; custom helper bytes are refused. After applying a reviewed plan,
run the copied gate CLI and regenerate the dashboard from the same factory, then
check integrity again. A matching display and valid hashes do not attest test
execution or freshness. Existing root ignore rules remain a separate manual
review; generated runtime output and private backups belong outside the managed
factory file set.

For known v1.13 helpers, a reviewed `--context-runtime --gate-runtime` plan can add
the Learn-table parser dependency and adopt named JSON and observed-target
diagnostics. The dependency is listed in the plan, manifest and backup's
`added-files.json`; restore or adopt that reviewed set together if interrupted.
Unrelated updates preserve the older compatible bundle. Unknown/custom helper
or parser bytes are refused, and existing Learn observations are not rewritten.
Malformed learning rows must be repaired explicitly before integrity-dependent
migration; structural validation never supplies missing evidence or passing results.
The optional acceptance-links helper reads the same Learn structure from captured
bytes and leaves factory contracts, records and gate readiness untouched.

Known v1.17 Verify/Release delivery addenda can receive the persistence, parity
and failed-G3 retry guidance through an explicit `--delivery-gates` preview.
Review the evidence resets/history as well as instruction changes; failed prior
observations and optional choices are preserved, not carried forward as passes.
The known v1.17 copied gate helper can separately receive the abbreviation
diagnostics with `--gate-runtime`. Unrelated updates preserve both older forms.
Custom addenda/helper bytes are refused, and backups retain the originals. A
diagnostic update does not resolve a short SHA or establish new subject evidence.

When adopting optional `operations.admission`, follow the [admission runtime
migration](admission-runtime-migration.md). A copied dashboard needs both supported
operations validation and readiness reporting; updating only one is insufficient.
The existing explicit `--context-runtime` path supports known prior bytes and
preserves custom copies for manual review. Admission metadata alone does not reset
gate observations or activate any live limit, dispatcher or reservation.
