# Release handoff

A diagnostic handoff may always be prepared. Preparation grants no authority.

## Pre-action readiness
Status: BLOCKED (initial; not release-ready)
Reviewed artifact and pre-merge revision:
G1 production-equivalent local smoke, G2 change-targeted checks and required A/R evidence:
Outstanding failed / BLOCKED / NOT RUN checks:
Review verdict and exact revision:
Accepted scope, migrations and rollback plan:
Actual intended web/artifact target:
Named authorizer, allowed action and boundaries:
Only mark READY FOR AUTHORIZED ACTION after all still-required pre-merge gates pass; use READY WITH WAIVERS when the user explicitly made checks optional and list them with recorded status. Pending post-action evidence is not a pre-merge dependency.

## Post-action confirmation
Status: PENDING / UNCONFIRMED (initial; no action performed)
Actual authorized action, merged revision and target:
G3 actual-target smoke result, evidence, time and exit/manual observation:
Other required post-action acceptance/research checks:
Failure/unavailable-check report to release owner/orchestrator and diagnosis/rollback decision:
For no-release scope, explicit NOT APPLICABLE rationale and named acceptance:

## Enabled done-video handoff
Preference read from policy/config; disabled by default:
Verify's planned recording scope, synthetic/non-secret data and owner:
G3 prerequisite result:
V1 narrated demo status, shipped revision, actual target, artifact and observation time:
Recording/storage/publication authority (separate scopes):
Report blocked recording or follow-up explicitly; do not fabricate a demo or mark it complete without its artifact. When enabled and still required, V1 follows passing G3 unless G3 was explicitly waived (report that waiver); neither is required before the release action can exist.

Only report checked confirmation when every still-required post-action gate passes. If confirmation or a demo was deliberately optional, report COMPLETED WITH WAIVERS and list what was not checked; do not claim the waived checks passed. A failed or NOT RUN G3 is unconfirmed, never silent success. Merge, deployment, recording and publication remain separately authorized.
