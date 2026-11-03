# Worker handoff

Task ID / owner:
Goal and acceptance IDs:
Input artifacts and exact revision:
Dependencies and their evidence:
Allowed files and actions:
Forbidden actions / data-egress boundary:
Output artifact and expected schema:
Verification and evidence (name G1 smoke/G2 targeted suite; preserve explicit optional rows as WAIVED, never tests-passed):
Cost, time, concurrency and retry limits:
Worker/provider run ID, current terminal/running state and expected artifact/branch:
Last credible progress, artifact/existing-commit check, retry hypothesis and remaining shared budget:
Stop conditions and escalation owner:
Subject revision actually tested/deployed; separate evidence-storage revision/reference:
Durable non-secret evidence location outside the factory, access/retention owner:
Result: revision, changes, passed/failed/blocked/not-run, risks, next action.

## Ordered worker plan (unconfigured template)

This file is a hashed contract. For each task, copy it to an approved task-specific
location outside the managed factory before filling it. Review privacy and retention
for the copy. Changing this reusable template itself requires a reviewed selective
contract/manifest update; never silently rebaseline it.

| Priority | Provider / existing recipe | Authority and data, cost, path and action boundaries | Availability / evidence | Stop or pause conditions |
|---|---|---|---|---|
| 1 | Unconfirmed primary | Unconfirmed; no execution authority inferred | Unverified | Stop at missing authority, boundary or budget |
| 2 | No fallback configured | None | Unverified | Stop and request the owner's decision |

Plan may contain one worker or additional project-specific rows. These are proposals,
not permissions or a health checker. Select in the agreed order only after checking
the candidate's current availability and its own explicit authority/boundaries.
Use one shared cost, time, concurrency and retry budget for every attempt and provider.
An empty transcript alone does not establish failure or absence of an artifact.
Reconcile the previous run's state, artifact and uncertain writes before any retry or
switch. If no permitted candidate is available or a stop limit is reached, stop;
pause intake only through an already-authorized control or request owner intervention.
Record the actual worker, provider/run ID, revision and checks in the result. A plan
does not authorize notifications, provider switching, credentials or a live watcher.
