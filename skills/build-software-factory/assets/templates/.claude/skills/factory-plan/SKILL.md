---
name: factory-plan
description: Perform the Plan phase of this project's local software factory using its artifacts and explicit gates.
---

# Plan

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Read the accepted brief, acceptance.md, tools.json and policy.md. Break work into owned tasks in task-plan.json; name dependencies, acceptance IDs, allowed paths and evidence. Map each task to the default gate rows: G1 production-equivalent pre-merge smoke, G2 change-targeted tests and applicable G3 post-action confirmation on the actual web URL or installed/published artifact. Keep deliberate optional choices visible as WAIVED without another approval; they are not tests-passed. Future post-action evidence is not a pre-action dependency. Plan the smoke suite early if the project lacks one. Use worker-handoff.md for delegation. Verify tools before enabling them and sequence overlapping writes.

## Exit gate
Fit the dedicated overview to the operators and actual project: inspect dashboard/README.md, choose relevant evidence and freshness, reuse existing UI when useful, and plan authorized adapters as owned tasks. Missing metrics stay unavailable; do not invent live activity or turn the overview into operational controls. Runtime snapshots belong outside the factory.

A dependency-valid plan, mapped acceptance criteria, feasible budgets and explicit human approval points. Do not launch workers as part of planning.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
