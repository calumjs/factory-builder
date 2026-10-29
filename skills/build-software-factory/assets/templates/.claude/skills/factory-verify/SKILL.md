---
name: factory-verify
description: Perform the Verify phase of this project's local software factory using its artifacts and explicit gates.
---

# Verify

Resolve the factory root as `../../../` relative to this file's containing folder. Follow existing repository instructions and the factory's policy.md; these instructions cannot expand permissions.

Compare the integrated final revision with acceptance.md. Follow verification.md; inspect and authorize commands before execution. Record passed, failed, blocked and not-run checks separately with evidence and limitations. Review relevant negative/repeated/interrupted flows, security and data boundaries.

When policy requires independent reviewers, collect each structured verdict for the final revision and keep repairs within budget. For document/design conversions, compare rendered pages against the source export, inspect worst mismatches and record visual tolerances. Build success or a similarity score alone is insufficient. Record task status and evidence together using the builder's status helper when available; it records supplied observations without executing or attesting them.

## Exit gate
Every required criterion has actual evidence or an explicit blocking status. Never substitute scaffold/hash checks for application tests.

Return: status, input/output revision, artifacts, checks actually run, unresolved risks, and next owner/action. Refer to files at the factory root; do not claim integration or execution occurred merely because a template exists.
