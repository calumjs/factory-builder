---
name: factory-build
description: Perform the Build phase of this project's local software factory using its artifacts and explicit gates.
---

# Build

1. Take one approved, dependency-ready task. Read repository instructions, the permitted context and worker-handoff.md. For a laptop fallback, follow launch-guide.md's source, trust and exact-command preflight first.
2. Implement only within the task's allowed paths and actions. Implement owned tests and fixtures, and in-scope CI or test-map changes, at the project's real paths, preserving the project's existing CI and ignore policy; a factory template is not application coverage.
3. Name the G2 change-targeted tests that cover the diff; add or update a test when none covers the changed behaviour. When execution is authorized, run the still-required G1/G2 locally before handing to Verify. Carry optional rows through as WAIVED with their recorded result.
4. Record the revision, changes, assumptions and checks actually run with status.py for the tested subject; keep durable logs outside this directory and reference them. If a reviewed contract must change, include only its selective manifest entry in that review.
5. Before any retry or fallback, inspect the run's terminal state, logs, expected artifact and branch/commit outcome. Retry only with a new hypothesis, within the same task budget, with no concurrent writers. Record worker/run provenance and remaining uncertainty in worker-handoff.md.
6. ci/README.md and ci/job.example.py are adoption proposals: adapt them only within CI-integration scope, with a pinned builder helper outside the change checkout, keeping tested S separate from storage E.

## Exit
A reviewable change and a handoff with the exact revision and evidence.
