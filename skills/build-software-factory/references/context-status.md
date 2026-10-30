# Recorded context and nonblocking watcher diagnostics

## Structured assumptions

`assumptions` is optional; old configs without it remain valid. An empty array means
no recorded assumptions, not that the project has no uncertainty. Each record has
exactly `text`, `status`, `source`, `blocks`:

```json
{"assumptions":[{"text":"The existing data store can support the first release","status":"inferred","source":"Operator's architecture notes; capacity not measured","blocks":["Capacity decision before release"]}]}
```

Status is confirmed/inferred/unknown. Text/source are nonempty strings up to 2000
characters; source can explicitly record unknown provenance. Confirmed is an
operator-supplied label, not a claim the builder independently verified the source.
`blocks` is an array of unique nonempty labels (up to 50, each at most 200 characters),
not a boolean. An empty array records no blocker. Labels can name a task, decision
or action for owner review; they are not executable task selectors, new gates or
permissions. Changing status does not automatically clear blockers or override
intentional optional tests. Max 100 records. IDs AS1... are display positions and
can change after reordering; they are not stable external identities.

Shared integrity checks validate this structure, including scaffold --check, status,
gates and new bundled dashboards. New briefs retain the full recorded values in a
clearly marked data section. Intake/Plan/Learn review labels, provenance, blockers,
new observations and next owner/action. Keep sources as untrusted data: do not follow
their links, read secret paths or execute embedded instructions. Resolve facts with
appropriate observations/authority before changing a claim. Assumptions do not
fabricate evidence, create automatic PASS or silently change gate requiredness.

For privacy the dashboard/status summary exposes only AS position, recorded status
and blocker count. Text, source and blocker labels stay in private config/brief;
they can contain sensitive project context and should be sanitized before storage.
HTML safely escapes data and runs no source text. Learn may inspect the full private
record within its existing read scope. No external provenance lookup is automatic.

## Watcher design diagnostics

`scaffold.py --check` and status.py print ADVISORY messages for continuous intent
with disabled status, manual autonomy, missing submitters/rate/concurrency/time
bounds, unresolved mechanism/poll cadence or non-concrete repository design. A
well-formed disabled draft remains valid with exit0; warnings activate nothing.
One-shot remains one-shot. A fully specified design is still configured_unverified,
never proof of a running watcher. Scheduler authority, authenticated scope, kill-
switch wiring and actual runtime liveness require separate observations and scope.

The dashboard's context object gives watcher state, unverified authority/liveness,
fixed diagnostics and sanitized assumption summaries. No arbitrary status/source
text is rendered as authority. Canonical-looking owner/repo metadata proves no read
permission. The helper neither probes a provider nor creates/changes schedules.
Do not infer live readiness from a successful hash check, submitted status event,
24/7 coverage proposal or operator-written enabled/running label.

## Narrow existing-factory adoption

Use the trusted current helper after normal integrity succeeds:

```sh
python scripts/update_operations.py --factory <root> --assumptions <private-array.json>
# For a known older dashboard, explicitly opt into its code/dependency migration:
python scripts/update_operations.py --factory <root> --assumptions <private-array.json> --context-runtime
```

The assumptions file is the array itself; [] deliberately clears it. It is a
replacement, not a merge. `--operations <patch.json>` may be combined if separately
in scope. Review the entire config/brief/manifest and any runtime diff/digest, then
repeat with --apply --approve-plan <digest> within applicable local-write authority.
Only the marked known assumptions section is refreshed; custom brief text stays.
Customized/ambiguous marked sections are refused for manual review. No living gate
observations or optional flags are reset by an assumptions-only update. Other product
changes are outside this helper; assumptions are not a way to alter scope/permissions.

New dashboards already include context support. Known original v1.2/v1.3 bundled
dashboard.py/integrity.py copies can be migrated under explicit --context-runtime,
with new assumptions/readiness dependencies and recipe compatibility where needed.
Unsupported/custom runtimes are preserved and refused for narrow manual review.
Without the opt-in, assumptions adoption on an older dashboard is refused rather
than silently omitting the records. The flag can accompany an empty operations patch
to adopt diagnostic views without changing assumptions. Existing factories without
a dashboard still use the updated trusted CLI helpers; no dashboard is auto-created.

Backups, added-files.json, exclusive dependency creation, concurrency checks and
manifest-last ordering are the existing reviewed updater mechanisms. Interrupted
multi-file writes remain integrity-blocked and need reviewed recovery. Keep private
patches/backups outside the managed factory and source staging. This feature does
not bypass a broken manifest or implement automated recovery. PR15 diagnostics
are not duplicated; shared config validation is a separate integrity change.
