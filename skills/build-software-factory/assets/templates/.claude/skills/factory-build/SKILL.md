---
name: factory-build
description: Perform the Build phase of this project's local software factory using its artifacts and explicit gates.
---

# Build

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Select one approved, dependency-ready task. Read repository instructions, permitted context and worker-handoff.md. Implement only within allowed paths/actions. Record revision, changes, assumptions and targeted checks. Name the change-targeted tests (G2) that cover the diff; add or update a test when none covers the changed behaviour. Run the still-required G1/G2 locally before handing to Verify when execution is authorized. Respect explicit optional rows without another approval; carry their WAIVED status and recorded result through the handoff, never claim they passed. Stop at budget/retry limits or missing authorization.

## Exit gate
Before retry/fallback, inspect the run's terminal state, permitted logs, expected artifact and branch/commit outcome. Empty output alone proves neither failure nor absence of work. Bound all attempts and providers by the same task budget; avoid concurrent writers, diagnose with a new hypothesis, and stop at missing authority or limits. A fallback must fit its own authorized provider/data/cost/action scope; no credential/security changes or new watcher is implied. Record worker/run provenance and uncertainty in worker-handoff.md.

Update task progress and checks actually run for the tested subject revision. Preserve durable non-secret logs outside the factory and reference them from living records; never mark done/PASSED merely to unblock a handoff. If a reviewed contract changes, include only its selective manifest entry change in that review. Unexpected file/integrity failures need the builder's reviewed recovery procedure, not a force rebaseline or fabricated evidence.

Implement owned tests/fixtures and, when in scope, CI/test-map changes at the existing project's actual paths. A plan or factory template is not runnable application coverage. Record commands actually run and their results; missing authority or unimplemented checks remain blocked. Keep operational runtime notes outside the manifest-checked factory directory and preserve existing project CI/ignore policy.

A reviewable change and handoff containing exact revision and evidence. No approval, publication or deployment is implied.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
