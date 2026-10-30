---
name: factory-build
description: Perform the Build phase of this project's local software factory using its artifacts and explicit gates.
---

# Build

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Select one approved, dependency-ready task. Read repository instructions, permitted context and worker-handoff.md. Implement only within allowed paths/actions. Record revision, changes, assumptions and targeted checks. Name the change-targeted tests (G2) that cover the diff; add or update a test when none covers the changed behaviour. Run the still-required G1/G2 locally before handing to Verify when execution is authorized. Respect explicit optional rows without another approval; carry their WAIVED status and recorded result through the handoff, never claim they passed. Stop at budget/retry limits or missing authorization.

## Exit gate
A reviewable change and handoff containing exact revision and evidence. No approval, publication or deployment is implied.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
