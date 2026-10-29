---
name: factory-plan
description: Perform the Plan phase of this project's local software factory using its artifacts and explicit gates.
---

# Plan

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Read the accepted brief, acceptance.md, tools.json and policy.md. Break work into owned tasks in task-plan.json; name dependencies, acceptance IDs, allowed paths and evidence. Use worker-handoff.md for delegation. Verify tools before enabling them and sequence overlapping writes.

## Exit gate
A dependency-valid plan, mapped acceptance criteria, feasible budgets and explicit human approval points. Do not launch workers as part of planning.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
