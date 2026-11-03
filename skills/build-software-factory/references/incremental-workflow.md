# Incremental work against configured acceptance

These installed-builder helpers are offline and operate on an existing factory.
They grant no task pickup, execution, publication or release authority. Use only
with the user's existing local permissions and stable, quiescent inputs. A scoped
result is a view of selected operator-supplied records, not an attestation, whole-
project readiness, a CI policy or authorization to release. `gates.py` and
`ci_evidence.py` retain their project-wide behavior.

Use `python scripts/gate_plan_status.py --factory <factory>` for a read-only
planned-versus-recorded view, including missing, extra, stage and design
differences. A changed design can be an actual observed procedure, so inspect it;
the view does not automatically classify every difference as a failure.

Create a non-secret scope JSON in approved scratch, explicitly listing configured
gate IDs and existing task IDs:

```json
{"purpose":"Reviewed feature scope","gates":["A1","R1"],"tasks":["T2"]}
```

Run `python scripts/scoped_assessment.py --factory <factory> --scope <scope.json>
--stage pre-merge --revision <exact-subject>` using an authorized command. G1/G2
and the selected tasks' acceptance IDs are included automatically; G3 is included
post-merge. Selected tasks need done/passed evidence for the exact supplied subject.
The output includes a scope identity bound to the factory manifest, explicit scope
and selected task definitions; the selected planned/recorded rows, waivers and all
excluded rows are shown. A missing or invalid selection, stale subject, unresolved
target or required failed/not-run gate blocks the scoped result. The helper does
not verify that a supplied revision is a Git commit or execute an application test.
There is no automatic evidence carry-forward. Assess the whole project separately
with `gates.py`; only separately authorized actions may merge or deploy.

For one-off setup mixed with per-item work, see the [explicit setup/item scope example](headless-intake-preflight.md#research-ids-and-setup-versus-per-item-assessment).
It uses this existing helper and reports exclusions; it supplies no automatic
setup exemption, evidence carry-forward or project-wide readiness claim.

## Feature-to-contract preflight

Before a feature PR claims to close an issue, review its actual diff against the
issue's requested behavior. Map the behavior to explicit existing acceptance IDs
and owned tasks. Reuse a criterion only when its wording covers the change; new
behavior needs a reviewed synchronized contract update before claiming coverage.
Do not invent rows during an evidence-only follow-up. A `Closes` phrase, issue
title, file path or label cannot classify the change or prove this mapping.

For one appended criterion and task in a supported factory, the installed
[acceptance planner](acceptance-planning.md) previews synchronized config, brief,
acceptance, test-map and living-record changes. It requires an independently
accepted manifest pin, preserves existing observations and positional IDs, and
starts the proposed check as required NOT RUN. It writes nothing: preview success
is not registered scope, and existing recovery registration/adoption still needs
its own review. Unsupported or ambiguous shapes are refused rather than rewritten.
The separate [inactive candidate helper](acceptance-candidates.md) can materialize
that reviewed scope into a new disjoint directory with a verified original backup.
It preserves the original manifest until a second recovery review and never
overwrites or activates the current factory.

Keep a version-1 mapping outside the factory, for example in approved evidence:

```json
{"version":1,"subject":"<full-subject-commit-sha>","classification":"feature",
 "rationale":"Reviewed diff reuses an existing product criterion",
 "issues":[{"reference":"owner/project#123","tasks":["T2"],"acceptance":["A1"]}]}
```

Run the trusted installed builder's `python scripts/change_contract.py --factory
<factory> --input <change.json> --revision <independently-verified-full-subject-sha>`.
The read-only preflight rejects unknown/duplicate IDs, missing feature mappings,
task/acceptance mismatches within each issue, contract drift and stale supplied
subjects. It prints mapped wording, task definitions and a digest including mutable
task-plan bytes. A shared task or criterion may serve multiple issues. Tasks need
not be done at planning time; evidence and user-selected waivers remain unchanged.

`MAPPED FOR REVIEW` is a structural result, not proof of coverage or passing tests.
Compare the report to the actual subject and diff, and refresh it if either changes.
The helper does not resolve Git commits or discover PRs. A deliberate `maintenance`
classification may have no issue mappings with an explicit rationale, but tests,
docs and configuration changes can affect behavior: inspect them and retain relevant
checks. This helper neither detects dishonest classification nor enables a hosted
G0/G2 check. CI adoption/enforcement is separate authorized integration. Use the
existing gate/scoped assessment after actual test execution, with exact subjects.

For an explicitly selected project rule, [optional feature-contract CI composition](feature-contract-ci.md)
adds a committed base/subject delta check to the existing pre-merge CI adapter. It
preserves this mapper's reuse behavior; policy selection and job adoption remain explicit.

`incremental_records.py --factory <factory> --kind task --input <task.json>`
previews adding one task using the existing task schema; only `pending`/`blocked`
new statuses, existing acceptance IDs, valid dependencies and safe project-relative
allowed paths are accepted. It cannot add acceptance criteria. A new criterion needs
a separately reviewed synchronized contract update, not an invented ID. `--kind gate`
previews one existing configured gate observation with exactly `gate`, `result`,
`revision`, `environment`, `evidence`, `target`, `checked_at`, and `exit_status`
string fields. Preserve its stage, design and requiredness; changes to the user's
editable optional flag can still be made through an authorized living-record edit.
Empty unknown fields are allowed for nonpassing records. A PASSED record must satisfy
existing gate rules; prior rows are retained as quoted history. Use real observations
only, keep private data out of logs and inputs, and never infer PASS from a helper.

For a read-only starting template, use [observation-drafts.md](observation-drafts.md):
planned recipes stay separate from blank actual evidence. For explicit observations
already obtained for one subject, [batch-observations.md](batch-observations.md)
documents `--kind gate-batch`; any invalid item rejects the entire batch. G3 and V1
require separate reviewed steps, and excluded rows remain unchanged.

All record operations print an exact diff and a digest without writing. After review,
the same command plus `--apply --approve-plan <digest>` writes one living file using
an atomic replacement and a cooperative status lock, after rechecking source bytes.
The digest changes with the factory inputs, target file or proposed output. Stop and
re-preview on mismatch. This protects against cooperating writers and ordinary
changes between preview and apply; it is not an adversarial filesystem lock. Do not
run another updater or manual writer concurrently. Existing task event history and
unrelated gate rows are preserved. No root configuration, permissions or contracts
are rewritten. Old factories can use the trusted installed helpers without changing
their copied runtime; review a separate migration before adopting any new contracts.

For overlapping evidence branches, integrate serially: rebase the later change,
resolve conflicts deliberately, retain each subject's observations, unique task
events and Learn entries, and rerun the checks for the subject being assessed.
Never discard failures or blindly choose the newest row. The helper's lock is
cooperative local coordination; it is not a Git merge or arbitrary-writer lock.

For explicit base/left/right snapshots, [evidence-reconciliation.md](evidence-reconciliation.md)
describes a read-only helper that proposes all three evidence records, requires
source-bound current-row/status choices, and preserves branch history and Learn
append occurrences. It does not apply or attest the proposal.
