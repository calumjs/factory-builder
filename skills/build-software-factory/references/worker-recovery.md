# Worker health, bounded retries and authorized fallback

Use task-specific tool recipes and worker-handoff.md; no new operations.workers
schema is needed. Pin a provider only when required by the project. During intake
or Plan, identify any permitted fallback, tool availability, data boundary, output
format and execution authority. An alternative provider is not authorized merely
because the primary worker is unavailable.

At each bounded checkpoint, inspect the actual run ID and terminal/running state,
exit/status signal, last progress time, expected artifact and revision/branch in
the assigned checkout. Read permitted structured output and logs. Confirm whether
a commit/PR/artifact was created before retrying or switching workers; an empty
transcript alone is insufficient proof of provider failure or no work performed.
Do not infer liveness from an old task status or an accepted launch request.

Classify the observed condition before choosing an action:

| Condition | Response within existing scope |
|---|---|
| Running with credible recent progress | Continue within deadline; avoid duplicate launch. |
| Terminal success with expected artifact/revision | Validate artifact and checks; transcript alone does not prove quality. |
| Terminal success without required artifact | Treat task incomplete; inspect output/schema and escalate or retry with a new hypothesis. |
| Explicit transient provider/tool error | Diagnose; bounded retry only when safe and a new hypothesis exists. |
| Auth, permission, data-boundary or rejected action | Stop that action; do not change identity/security or switch tools to bypass the restriction. |
| Unknown/stalled state or missing output | Query terminal state/artifacts where authorized; avoid overlapping writers and report uncertainty. |
| Artifact exists despite failed/empty output | Preserve and inspect it; reconcile before any retry to prevent duplicate commits/PRs. |

Use existing budget.max_repair_attempts, max_minutes, max_workers and monetary
limits across the task, including all retries and fallback providers. A fallback
does not reset the budget. Before retrying, name the new hypothesis, bounded timeout,
expected artifact and verification. Repeated unchanged failures, an exhausted limit
or missing authority ends automatic attempts. Record exact status and evidence for
the owner; this skill does not authorize sending a notification by itself.

Fallback is allowed only if its provider, data egress, cost, local paths and actions
fit existing explicit scope. Otherwise prepare the smallest decision for the owner.
Use an isolated checkout where appropriate, reconcile any primary worker's uncertain
outcome, and ensure it cannot concurrently write the same files before transferring
the task. Never terminate a run outside authority. Record which worker/run produced
the final artifact, its exact revision and checks in the handoff; do not fabricate
health telemetry. If automatic pickup exists, use its already-authorized pause/kill
switch when needed, or request owner intervention; do not create or reconfigure a
watcher as a recovery side effect.
