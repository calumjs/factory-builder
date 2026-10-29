---
name: factory-release
description: Perform the Release phase of this project's local software factory using its artifacts and explicit gates.
---

# Release

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Complete release-handoff.md for the exact verified revision. Check acceptance, required review, migrations, rollback, target and authorizer. Without publication authority, deliver the handoff and stop. With scoped authority, perform only that action and verify its actual result.

## Exit gate
A prepared handoff or an explicitly authorized, verified release. Never auto-approve/merge a PR or assume deployment permission.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
