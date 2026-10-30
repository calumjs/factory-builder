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

Both record operations print an exact diff and a digest without writing. After review,
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
