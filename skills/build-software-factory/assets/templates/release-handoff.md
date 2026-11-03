# Release handoff

A diagnostic handoff may always be prepared. Preparation grants no authority.

## Pre-action readiness
Status: BLOCKED (initial; not release-ready)
Reviewed artifact and pre-merge revision:
Evidence-storage revision (separate from tested subject; record after storage commit exists):
Durable evidence location, retention/access owner and availability check:
G1 production-equivalent local smoke, G2 change-targeted checks and required A/R evidence:
Outstanding failed / BLOCKED / NOT RUN checks:
Review verdict and exact revision:
Accepted scope, migrations and rollback plan:
Release owner, subject/target, coordination boundary and handoff evidence:
Migration-before-traffic or compatible expand/contract evidence; automatic promotion risk:
Owner start, latest observation and terminal timestamps (UTC); outcome SUCCESS / FAILED / CANCELLED / UNKNOWN:
If a terminal marker is absent, record UNKNOWN, not success. Check the actual action and durable evidence before reporting an outcome. A stale or missing owner needs diagnosis and an authorized handoff under the agreed coordination procedure; a local claim alone proves neither exclusion nor permission to take over.
Actual intended web/artifact target:
For recorded post-action assessment, supply the separately observed target explicitly:
`python <builder-scripts>/gates.py --factory <factory-root> --stage post-merge --revision <actual-subject> --target <actual-target>`.
The planned target is not deployment evidence. This command checks records and does not deploy or execute acceptance tests.
Changed-feature confirmation: comparison base, reviewed subject, changed paths, acceptance IDs and test-map/equivalent references:
Selected target-safe tests/assertions and G3 or named post-action row; approved actors, data/setup/cleanup prerequisites and unresolved authority:
Named authorizer, allowed action and boundaries:
Only mark READY FOR AUTHORIZED ACTION after all still-required pre-merge gates pass; use READY WITH WAIVERS when the user explicitly made checks optional and list them with recorded status. Pending post-action evidence is not a pre-merge dependency.

## Post-action confirmation
Status: PENDING / UNCONFIRMED (initial; no action performed)
Actual authorized action, merged revision and target:
Actual deployed/installed subject versus evidence-storage commit; any follow-up redeployment:
G3 actual-target smoke result, evidence, time and exit/manual observation:
Feature-specific subset actually collected/executed, acceptance/assertion outcomes, unique output/report location and gate-row evidence:
Excluded required scope and BLOCKED/NOT RUN reason or explicit optional waiver; any data written, cleanup outcome and residue:
Other required post-action acceptance/research checks:
Failure/unavailable-check report to release owner/orchestrator and diagnosis/rollback decision:
For no-release scope, explicit NOT APPLICABLE rationale and named acceptance:

## Attempt supervision (plan; no supervisor is installed)
For every authorized G3 or video attempt, record a unique attempt ID, phase,
subject revision, actual target, owner and coordination boundary; link each retry
or superseding attempt without overwriting the earlier record. Record start,
latest observed heartbeat and terminal time with time zone, plus status, evidence
and observer. A heartbeat is a timestamped observation, not proof the worker is
still alive, authorized or exclusively owns the target. Keep runtime records in
approved external evidence storage, not as new files inside the managed factory.

Use a separately authorized supervisor when one exists: observe exit status and
timeouts, write or reconcile terminal records independently of the worker, and
retain the actual logs or evidence. A process killed with no final marker cannot
write its own outcome. Classify absent or stale heartbeat/terminal evidence as
UNKNOWN/STALE and escalate; do not infer PASS, FAILED, ABORTED, or continuous
liveness from a missing marker or elapsed time alone. Mark ABORTED only with
credible evidence of termination or an authoritative supervisor observation;
keep its reason and source. On normal exit, record PASS only when the actual
required checks passed for this attempt; a normal nonzero exit or a failed check is FAILED,
and a successful exit without check evidence is UNKNOWN. A timeout is a supervisor
observation; unless termination is confirmed, the worker may still be running.
A replacement attempt never rewrites the prior outcome: mark the relationship as
superseded and retain the prior attempt's known result, or UNKNOWN if unresolved.

Synthetic interpretation examples (not observations):

| Situation | Interpretation |
| --- | --- |
| Normal zero exit plus matching passing check evidence | PASS for that attempt |
| Timeout; worker termination not confirmed | UNKNOWN/STALE, investigate |
| Supervisor confirms forced termination | ABORTED with termination evidence |
| A successor starts while old outcome is unresolved | Old attempt UNKNOWN; link successor |

The supervisor is a proposed project-specific integration, not a capability of the
record-only gate checker. Keep an optional gate WAIVED with its observed outcome;
no marker or supervision authorizes a merge, deployment, spend or narration.

## Enabled done-video handoff
Preference read from policy/config; disabled by default:
Verify's planned recording scope, synthetic/non-secret data and owner:
G3 prerequisite result:
V1 narrated demo status, shipped revision, actual target, artifact and observation time:
Recording/storage/publication authority (separate scopes):
Report blocked recording or follow-up explicitly; do not fabricate a demo or mark it complete without its artifact. When enabled and still required, V1 follows passing G3 unless G3 was explicitly waived (report that waiver); neither is required before the release action can exist.

Only report checked confirmation when every still-required post-action gate passes. If confirmation or a demo was deliberately optional, report COMPLETED WITH WAIVERS and list what was not checked; do not claim the waived checks passed. A failed or NOT RUN G3 is unconfirmed, never silent success. Merge, deployment, recording and publication remain separately authorized.
